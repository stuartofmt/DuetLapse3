#!python3
"""
Simple HTTP server for starting and stopping DuetLapse3
# Copyright (C) 2020 Stuart Strolin all rights reserved.
# Released under The MIT License. Full text available via https://opensource.org/licenses/MIT
#
#
# Developed on WSL with Debian Buster. Tested on Raspberry pi, Windows 10 and WSL. SHOULD work on most other linux distributions. 
"""
global startDuetLapse3Version
startDuetLapse3Version = '3.3.0'
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import sys
import threading
import subprocess
import shlex
import psutil
from DuetLapse3 import whitelist, checkInstances
import socket
import time
import platform
import urllib
import html

class whitelistParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if status:
            raise ValueError(message)
def init():

    # parse command line arguments
    parser = argparse.ArgumentParser(description='Helper Web Server for running DuetLapse3 remotely. V'+startDuetLapse3Version, allow_abbrev=False)
    #Environment
    parser.add_argument('-host',type=str,nargs=1,default=['0.0.0.0'],help='The ip address this service listens on. Default = 0.0.0.0')
    parser.add_argument('-port',type=int,nargs=1,default=[0],help='Specify the port on which the server listens. Default = 0')
    parser.add_argument('-args',type=str,nargs=argparse.PARSER,default=[''],help='Arguments. Default = ""')
    args=vars(parser.parse_args())

    global host, port, defaultargs

    host = args['host'][0]
    port = args['port'][0]
    defaultargs = args['args'][0]


###########################
# Integral Web Server
###########################

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

class MyHandler(BaseHTTPRequestHandler):
    
    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
    def _refresh(self, message):
        content = f'<html><head><meta http-equiv="refresh" content="60"> </head><body><h2>{message}</h2></body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!        

    def _html(self, message):
        content = f'<html><head></head><body><h2>{message}</h2></body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!
  
    def update_content(self):
        options = 'status, start, terminate'
        global pidlist
        pidlist = []
        localtime = time.strftime('%A - %H:%M',time.localtime())
        #portlist = []
        runninginstances, pidlist = getRunningInstances(thisinstance, referer)
        thisrunninginstance = getThisInstance(thisinstancepid)
    
        header =    ('startDuetLapse3 Version '+startDuetLapse3Version+'<br>'
                    '<h4>'
                    +thisrunninginstance+
                    '</h4>'   
                    )    
            
        status =    ('<h3>'
                    '<br>As of :  '+localtime+'<br><br>'
                    'Running instances of DuetLapse3 were:<br><br>'
                    +runninginstances+
                    '</h3>'    
                    )                                    
        
        buttons =   ('<div class="divider">'
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="status" />'
                    '<input type="submit" value="Status" style="background-color:green"/>'                    
                    '</form>'
                    '</div>'
                    '<div class="divider">'                                    
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="start" />'                                    
                    '<input type="submit" value="Start" style="background-color:orange"/>'
                    '</form>'
                    '</div>'                                    
                    '<div class="divider">'                                   
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="terminate" />'                                   
                    '<input type="submit" value="Terminate" style="background-color:yellow"/>'
                    '</form>'
                    '</div>'
                    '<div class="divider">'                                     
                    '<form action="http://'+referer+'">'
                    '<input type="hidden" name="command" value="shutdown" />'
                    '<input type="submit" value="Shutdown" style="background-color:red"/>'
                    '</form>'
                    '</div>'
                    '<style type="text/css">'
                    '{'
                    'position:relative;'
                    'width:200px;'
                    '}'
                    '.divider{'
                    'width:200px;'
                    'height:auto;'
                    'display:inline-block;'
                    '}'
                    '.pad30{'
                    'margin-left: 30px;' 
                    '}'
                    'input[type=submit] {'
                    'width: 10em;  height: 2em;'
                    '}'
                    '</style>'
                    )        
        return header , status , buttons;
        
    def do_GET(self):
        self._set_headers()
        global referer
        referer = self.headers['Host']       
        #Update main content
        header, status, buttons = self.update_content()

        path = self.path

        if ('favicon.ico' in path):
            return
            
        query_components = parse_qs(urlparse(self.path).query)
            
        command = ''
        if(query_components.get('command')):
            command = query_components['command'][0]


                

            if(query_components.get('nohup')):
                nohup = query_components['nohup'][0]
            else:
                nohup = ''
                
            if (nohup != 'yes'):  #normalize
                nohup = ''
                
            if(query_components.get('pids')):
                pids = query_components['pids'][0]
            else:
                pids = ''                
            
            #self.main()
               
            if (command == 'status'):
                refreshing = ('<h3><pre>'
                              'Status will update every 60 seconds'
                              '</pre></h3>'
                              )
                self.wfile.write(self._refresh(header+status+buttons+refreshing))
            
            elif (command == 'start'):
                whitelisterror = ''
                if(query_components.get('args')):
                    args = query_components['args'][0]
                    global defaultargs
                    #need to put back encoded punctuation
                    defaultargs = html.escape(args)
                    #Test to see if the options are valid
                    checkarguments = whitelistParser(description='Checking for valid inputs to DuetLapse3', allow_abbrev=False)
                    checkarguments = whitelist(checkarguments)
                    try:
                        checkedargs=vars(checkarguments.parse_args(shlex.split(args)))
                        duetport = checkedargs['port'][0]
                    except ValueError as message:
                        whitelisterror =    ('<h3>'
                                            'The following errors were detected:<br>'
                                            '<pre>'
                                            +str(message)+
                                            '</pre>'
                                            '</h3>'
                                            )                   
                        args = ''                    
                else:  
                    args = ''
                
                if (args != ''):
                    if win :
                        if (nohup == 'yes'):
                            cmd = 'pythonw DuetLapse3.py '+args
                        else:
                            cmd = 'python3 DuetLapse3.py '+args
                    else:  #Linux
                        if (nohup == 'yes'):
                            cmd = 'nohup python3 ./DuetLapse3.py '+args+' &'
                        else:
                            cmd = 'python3 ./DuetLapse3.py '+args+' &'
                            
                    subprocess.Popen(cmd, shell=True) #run the program
                    setstart =  ('<h3>'
                                'Attempting to start DuetLapse3 with following options:<br>'
                                '<pre>'
                                +cmd+
                                '</pre>'
                                '</h3>'
                                )                        

 
                    self.wfile.write(self._html( header+status+buttons+setstart))
                    
                else:
                    print('C: '+ defaultargs)
                    getstart =  ('<div>'                                    
                                '<form action="http://'+referer+'">'
                                '<input type="hidden" name="command" value="start" />'
                                '<input type="text" id="args" name="args" value="'+defaultargs+'" size="200"/>'                                    
                                '<input class = "pad30" type="submit" value="Start" style="background-color:orange"/>'
                                '</form>'
                                '</div>'
                                )                     
                    self.wfile.write(self._html( header+status+buttons+getstart+whitelisterror))
                                                
            elif (command == 'terminate'):
                if (pids != ''):
                    if (pids == 'all'):
                        for pid in pidlist:
                            try:
                                os.kill(pid, 2)
                            except:
                                pass
                        pidmsg = 'All running instances'
                    else:
                        pid = int(pids)
                        try:
                            os.kill(pid, 2)
                            pidmsg = 'The instance with pid = '+pids
                        except:
                            pidmsg = 'There was no instance with pid = '+pids
                    setterminate =   ('<h3>'
                                     'Terminating the following DuetLapse3 Instances.<br>'
                                     '<pre>'
                                     +pidmsg+'<br>'
                                     'Note that some instances may take several minutes to shut down'
                                     '</pre>'
                                     '</h3>'
                                     )
                    
                    self.wfile.write(self._html( header+status+buttons+setterminate))

                else:
                    getterminate =  ('<div>'                                    
                                    '<form action="http://'+referer+'">'
                                    '<input type="hidden" name="command" value="terminate" />'
                                    '<input type="text" id="pid" name="pids" value="all" size="6"/>'                                    
                                    '<input class = "pad30" type="submit" value="Terminate" style="background-color:yellow"/>'
                                    '</form>'
                                    '</div>'
                                    )
                    self.wfile.write(self._html( header+status+buttons+getterminate))                           

            elif (command == 'shutdown'):
                localtime = time.strftime('%A - %H:%M',time.localtime())
                self.wfile.write(self._html('Shutting Down startDuetLapse3.<br><br>'
                                            'At:  '+localtime+'<br><br>'
                                            '<h3>'
                                            'Any instances of DuetLapse3 will continue to run'
                                            '</h3>'
                                            ))
                print('!!!!!! Stopped by http request !!!!!!')
                terminate()

            else:
                self.wfile.write(self._html('Illegal value for command=<br>'
                                            '<h3>'
                                            '<pre>Valid options are:   '+options+'</pre></h3>'
                                            ))
                       
            return

        refreshing = ('<h3><pre>'
                      'Status will update every 60 seconds'
                      '</pre></h3>'
                      )
        self.wfile.write(self._refresh(header+status+buttons+refreshing))

        
        return

    def log_request(self, code=None, size=None):
        pass

    def log_message(self, format, *args):
        pass
    
def createHttpListener():
    global listener
    listener = HTTPServer((host, port), MyHandler)
    listener.serve_forever()
    
def closeHttpListener():
    global listener
    print('!!!!! Stop requested by http listener !!!!!')
    listener.shutdown()
    listener.server_close()
    print('Terminated')
    sys.exit(0)
    
def getOperatingSystem():
#  What OS are we using?
    global win
    operatingsystem = platform.system()
    if(operatingsystem == 'Windows'):
        win = True
    else:
        win = False
        
def getThisInstance(thisinstancepid):
    thisrunning = 'Could not find a process running with pid = '+str(thisinstancepid)
    for p in psutil.process_iter():
        if (('python3' in p.name() or 'pythonw' in p.name()) and thisinstancepid == p.pid):
            cmdlinestr = str(p.cmdline())
            #clean up the appearance
            cmdlinestr = cmdlinestr.replace('[','')
            cmdlinestr = cmdlinestr.replace(']','')
            cmdlinestr = cmdlinestr.replace(',','')
            cmdlinestr = cmdlinestr.replace("'",'')
            cmdlinestr = cmdlinestr.replace('  ','')
            pid = str(p.pid)
            thisrunning = 'This program is running with<br>Process id:    '+pid+'<br>Command line:    '+cmdlinestr+''
       
    return  thisrunning  
        
def getRunningInstances(thisinstance, referer):
    split_referer = referer.split(":", 1)
    refererip = split_referer[0]  
    running = ''
    pidlist = []
    for p in psutil.process_iter():
        if (('python3' in p.name() or 'pythonw' in p.name()) and not thisinstance in p.cmdline() and '-duet' in p.cmdline()): #Check all other python3 instances
            #Get the port if used else set it to zero 
            cmdline = p.cmdline()
            try:
                index = cmdline.index('-port')
                index += 1
                port = cmdline[index]
            except ValueError:
                 port = 0
            #clean up the appearance
            cmdlinestr = str(p.cmdline())
            cmdlinestr = cmdlinestr.replace('[','')
            cmdlinestr = cmdlinestr.replace(']','')
            cmdlinestr = cmdlinestr.replace(',','')
            cmdlinestr = cmdlinestr.replace("'",'')
            cmdlinestr = cmdlinestr.replace('  ','')
            pidlist.append(p.pid)
            pid = str(p.pid)
            if (port == 0):
                running = running+('Process id:  '+pid+'<br>'
                                   +cmdlinestr+'<br>'               
                                   )
            else:  #Formal for html link
                running = running+('Process id:  '+pid+'<br>'
                                   '<a href=\"http://'+refererip+':'+str(port)+'\?command=status" target="_blank">'                                  
                                   +cmdlinestr+'</a>'
                                   '<br>'               
                                   ) 
                
    if (running != ''):
        running = ('<pre>'
                  +running+
                  '<br>'
                  '</pre>'
                  )
    else:
        running = 'None'  
    return running, pidlist;
        
def terminate():
    try:    #this should close this thread
        httpthread.join(10)
    except:
        pass   
    os.kill(thisinstancepid, 9)
    
#Allows process running in background or foreground to be gracefully
# shutdown with SIGINT (kill -2 <pid> also handles KeyboardInterupt
import signal

def quit_gracefully(*args):
    print('!!!!!! Stopped by SIGINT or CTL+C  !!!!!!')
    terminate()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, quit_gracefully)    
        
"""
Main Program
"""
if __name__ == "__main__":
   
    global thisinstance, thisinstancepid
    getOperatingSystem()            #some commands are os specific
    thisinstance = os.path.basename(__file__)
    if not win:
        thisinstance = './'+thisinstance
    _ = checkInstances(thisinstance,'single')    #There can only be one instance running
    thisinstancepid = os.getpid()
    init()
    
    if (port != 0):
        try:
            sock = socket.socket()
            if sock.connect_ex((host, port)) == 0:
                print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                print('Sorry, port '+str(port)+' is already in use.')
                print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                sys.exit(2)
                
            httpthread = threading.Thread(target=createHttpListener, args=())
            httpthread.start()
            print('***** Started http listener *****')
            
        except KeyboardInterrupt:
            pass  #This is handled as SIGINT
    else:
        print('No port number was provided or port is already in use')
        sys.exit(2)
