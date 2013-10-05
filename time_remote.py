#!/usr/bin/python
# -*- coding: utf-8 -*-
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
import shlex, subprocess, cgi, sys, codecs, threading, time, locale, os
import RPi.GPIO as GPIO

PORT_NUMBER = 8081

howmany = "#Pics"
interval = "Interval"
shut_dur = "Open shutter (s)"

lockfile="/tmp/tmshoot.lock"
logfile="/tmp/shootlog"
pic_num = 0
html = ""

css = '''<style type='text/css'>
body{background:black;overflow:auto}
.submit{color:red;font-size:150px;font-weight:bold;height:25%;width:100%;background:white;border:solid 5px red;-webkit-border-radius: 10px 10px 10px 10px; border-radius: 10px 10px 10px 10px;}
.submit{-moz-box-shadow:inset 0px 0px 20px red;
-webkit-box-shadow:inset 0px 0px 20px red;
box-shadow:inset 0px 0px 40px red;}
.text{border:dashed 5px #1e69de;height:20%;color: #1e69de;font-size: 100px;text-align:center;width:100%;-webkit-border-radius: 10px 10px 10px 10px; border-radius: 10px 10px 10px 10px;}
.text{-moz-box-shadow:inset 0px 0px 20px #1e69de;
-webkit-box-shadow:inset 0px 0px 20px #1e69de;
box-shadow:inset 0px 0px 20px #1e69de;}
.error_events{width:100%;color: red;font-size:50px;font-weight: bold;text-align:center;}
</style>
'''

script = '''
function initForm(oForm, element_name, init_txt)
{
    frmElement = oForm.elements[element_name];
    frmElement.value = init_txt;
}
function clearFieldFirstTime(element)
{    
    if(element.counter==undefined)
    {
        element.counter = 1;
    }
    else
    {
        element.counter++;
    }
 
    if (element.counter == 1)
    {
        element.value = '';
    }
}
if (typeof (EventSource) !== "undefined") {
    var source = new EventSource('/feedback');
    source.onmessage = function (e) {
        document.getElementById("launch").value = e.data;
    };
} else {
    document.getElementById("error_events").innerHTML = "Your browser does not support Server Sent Events.";
}
'''

#This class will handles any incoming request from
#the browser 
class myHandler(BaseHTTPRequestHandler):
    #Handler for the GET requests
    def do_GET(self):
        global howmany
        global interval
        global shut_dur
        global html
        if self.path=="/":
            html = "<!DOCTYPE html><html>"
            html +='''<body>\n'''
            html += '''<head><script type='text/javascript'>
%s
</script></head>
<div class='form'>
<form method='POST'>
<br/><input class=text name='howmany' onfocus='clearFieldFirstTime(this);' value='%s'></input><br/>
<br/><input class=text name='interval' onfocus='clearFieldFirstTime(this);' value='%s'></input><br/>
<br/><input class=text name='shut_dur' onfocus='clearFieldFirstTime(this);' value='%s'></input><br/>
<br/><input type='submit' id='launch' class='submit' value='0'></input>
</form>
</div>
<br/><div class='error_events' id='error_events'></div>
</body>
</html>''' % (script, howmany, interval, shut_dur)
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(css)
            self.wfile.write(html)

        if self.path=="/feedback":
            html = '''Event: message\n'''
            html += '''retry: 0\n'''
            html += '''data: %d\n\n''' % pic_num
            self.send_response(200)
            self.send_header('Content-type','text/event-stream')
            self.send_header('Cache-control', 'no-cache')
            self.send_header('Connexion', 'keep-alive')
            self.end_headers()
            self.wfile.write(html)
            self.wfile.flush()

            

    #Handler for the POST requests
    def do_POST(self):
        global howmany
        global interval
        global shut_dur
        form = cgi.FieldStorage(
            fp=self.rfile, 
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
        })

        howmany = form.getvalue("howmany")
        interval = form.getvalue("interval")
        shut_dur = form.getvalue("shut_dur")
        if ("howmany" in form) and ("interval" in form) and ("shut_dur" in form) and ((self.check_if_int(howmany) == True) and (self.check_if_int(interval) == True) and (self.check_if_int(shut_dur) == True)):
            self.shoot_thread(int(howmany), int(interval), int(shut_dur))
        else:
            howmany = "#Pics"
            interval = "Interval"
            shut_dur = "Open shutter (s)"
        self.do_GET()
        return

    def check_if_int(self, val):
        try:
            int(val)
            return True
        except ValueError:
            return False

    def shoot_thread(self, howmany, interval, shut_dur):
        if os.path.exists( lockfile ) == False:
            thread1 = threading.Thread( target=self.shoot, args=(howmany, interval, shut_dur))
            thread1.start()

    def shoot(self, howmany, interval, shut_dur):
        global pic_num
        print "going for %d pictures" % howmany
        lockhandle = open(lockfile, "w")
        lockhandle.close()
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(16, GPIO.OUT)
        for i in range(howmany):
            if os.path.exists( lockfile ) == True:
                pic_num = (i+1)
                print "Picture #%d" % pic_num
                self.gpio_sig(shut_dur)
                if interval < 1:
                    interval = 1
                time.sleep(interval)
            else:
                GPIO.cleanup()
                return
        os.remove(lockfile)
        GPIO.cleanup()
        return

    def gpio_sig(self, shut_dur):
        if shut_dur < 1:
            shut_dur = 1
        print "Opening shutter for %d s" % shut_dur
        GPIO.output(16, 1)
        time.sleep(shut_dur)
        GPIO.output(16, 0)
        return

try:
    #Create a web server and define the handler to manage the
    #incoming request
    server = HTTPServer(('', PORT_NUMBER), myHandler)
    print 'Started httpserver on port ' , PORT_NUMBER
    
    #Wait forever for incoming http requests
    server.serve_forever()

except KeyboardInterrupt:
    print '\nShutting down the web server...'
    if os.path.exists( lockfile ) == True:
        os.remove(lockfile)
    server.socket.close()
