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
body{background:white;overflow:auto}
input{border-width: 0px;width:100%;height:120px;-webkit-border-radius: 10px 10px 10px 10px; border-radius: 10px 10px 10px 10px;-webkit-box-shadow: 0px 0px 3px 0px #000000; box-shadow: 0px 0px 3px 0px #000000;}
.submit{font-size: 100px;text-align:center;background: #6db3f2; /* Old browsers */background: -moz-linear-gradient(top, #6db3f2 0%, #54a3ee 50%, #3690f0 51%, #1e69de 100%); /* FF3.6+ */background: -webkit-gradient(linear, left top, left bottom, color-stop(0%,#6db3f2), color-stop(50%,#54a3ee), color-stop(51%,#3690f0), color-stop(100%,#1e69de)); /* Chrome,Safari4+ */background: -webkit-linear-gradient(top, #6db3f2 0%,#54a3ee 50%,#3690f0 51%,#1e69de 100%); /* Chrome10+,Safari5.1+ */background: -o-linear-gradient(top, #6db3f2 0%,#54a3ee 50%,#3690f0 51%,#1e69de 100%); /* Opera 11.10+ */background: -ms-linear-gradient(top, #6db3f2 0%,#54a3ee 50%,#3690f0 51%,#1e69de 100%); /* IE10+ */background: linear-gradient(to bottom, #6db3f2 0%,#54a3ee 50%,#3690f0 51%,#1e69de 100%); /* W3C */filter: progid:DXImageTransform.Microsoft.gradient( startColorstr='#6db3f2', endColorstr='#1e69de',GradientType=0 ); /* IE6-9 */}
.text{color: #1e69de;font-size: 100px;text-align:center;}
.count{color: #1e69de;font-size: 200px;text-align:center;}
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
function fillfields(howmany_val, interval_val, shut_dur_val)
{
    initForm(document.forms[0], 'howmany', howmany_val);
    initForm(document.forms[0], 'interval', interval_val);
    initForm(document.forms[0], 'shut_dur', shut_dur_val);
}
    if (typeof (EventSource) !== "undefined") {
        var source = new EventSource('/feedback');
        source.onmessage = function (e) {
            document.getElementById("test").innerHTML = e.data;
        };
    } else {
        document.getElementById("test").innerHTML = "Your browser does not support Server Sent Events.";
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
<br/><br/><input type='submit' class='submit' value='Launch'></input>
</form>
</div>
<p class='count' id='test'></p>
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
            pic_num = (i+1)
            print "Picture #%d" % pic_num
            self.gpio_sig(shut_dur)
            if interval < 1:
                interval = 1
            time.sleep(interval)
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
