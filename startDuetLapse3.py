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
startDuetLapse3Version = '3.2.2'
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import sys
import threading
import subprocess
import shlex
import psutil
from DuetLapse3 import whitelist
import socket
import time

def init():

    # parse command line arguments
    parser = argparse.ArgumentParser(description='Helper Web Server for running DuetLapse3 remotely. V'+startDuetLapse3Version, allow_abbrev=False)
    #Environment
    parser.add_argument('-host',type=str,nargs=1,default=['0.0.0.0'],help='The ip address this service listens on. Default = 0.0.0.0')
    parser.add_argument('-port',type=int,nargs=1,default=[0],help='Specify the port on which the server listens. Default = 0')
    args=vars(parser.parse_args())

    global host, port

    host = args['host'][0]
    port = args['port'][0]
         

###########################
# Integral Web Server
###########################

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

class MyHandler(BaseHTTPRequestHandler):
    #global thisinstance
    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
    def _refresh(self, message):
        content = f'<html><head><meta http-equiv="refresh" content="60"> </head><body><h2>{message}</h2></body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!        

    def _html(self, message):
        content = f"<html><body><h2>{message}</h2></body></html>"
        return content.encode("utf8")  # NOTE: must return a bytes object!
    
    def do_GET(self):
        self._set_headers()
        options = 'status, start, terminate'
        qs = {}
        path = self.path

        if ('favicon.ico' in path):
            return
                       
        query_components = parse_qs(urlparse(self.path).query)
            
        command = ''
        if(query_components.get('command')):
            command = query_components['command'][0]
            if(query_components.get('args')):
                args = query_components['args'][0]
                checkarguments = argparse.ArgumentParser(description='Checking for valid inputs to DuetLapse3', allow_abbrev=False)
                checkarguments = whitelist(checkarguments)
                try:
                    checkedargs=vars(checkarguments.parse_args(shlex.split(args)))
                    duetport = checkedargs['port'][0]

                except:
                    self.wfile.write(self._html('There was one or more invalid arguments for DuetLapse3<br><h3>Check for the correct syntax.<br><br>'+args+'</h3>'))
                    return
            else:
                args = ''
                
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
            
            #get information on running instances                             
            pidlist = []
            runninginstances, pidlist = getRunningInstances(thisinstance)
            thisrunninginstance = getThisInstance(thisinstancepid)
            localtime = time.strftime('%A - %H:%M',time.localtime())
            
            self.wfile.write(self._html('startDuetLapse3 Version '+startDuetLapse3Version+'<br><br>'
                                        '<h4>'
                                        +thisrunninginstance+
                                        '</h4>'   
                                           ))
               
            if (command == 'status'):
                self.wfile.write(self._refresh('<h3>'
                                               '<br><br>Local time is:  '+localtime+'<br><br>'
                                               'Currently running instances of DuetLapse3 are:<br><br>'
                                               +runninginstances+
                                               '</h3>'
                                               ))
            
            elif (command == 'start'):
                if (args != ''):
                    basecmd = 'python3 ./DuetLapse3.py '+args
                    if (nohup == 'yes'):
                        cmd = 'nohup '+basecmd+' &'
                    else:
                        cmd = basecmd+' &'
                        
                    subprocess.Popen(cmd, shell=True) #run the program
                    self.wfile.write(self._html('Starting DuetLapse3.<br><br>'
                                                'Local time is:  '+localtime+'<br><br>'
                                                '<h3>'
                                                +cmd+
                                                '</h3>'
                                                ))
                    
                else:
                    self.wfile.write(self._html('Start request Ignored<br>'
                                                '<h3>'
                                                'command=start also requires arg={DuetLapse3 option}<br>'
                                                'and optionally nohup=yes'
                                                '</h3>'
                                                )) 
                                                
            elif (command == 'terminate'):
                if (pids != ''):
                    basecmd = 'python3 ./DuetLapse3.py '+args
                    if (pids == 'all'):
                        for pid in pidlist:
                            try:
                                os.kill(pid, 2)
                            except:
                                pass
                        pidmsg = 'For all running instances'
                    else:
                        pid = int(pids)
                        try:
                            os.kill(pid, 2)
                            pidmsg = 'For instance with pid = '+pids
                        except:
                            pidmsg = 'There was no instance with pid = '+pids

                    self.wfile.write(self._html('Sending Terminate to DuetLapse3.<br><br>'
                                                'Local time is:  '+localtime+'<br><br>'
                                                '<h3>'
                                                '<pre>'
                                                +pidmsg+'<br>'
                                                'Note that some instances can take several minutes to shut down'
                                                '</pre>'
                                                '</h3>'
                                                ))                       
                else:
                    self.wfile.write(self._html('terminate request Ignored<br>'
                                                '<h3>'
                                                'command=terminate also requires pids=all or pids={processid}<br>'
                                                '</h3>'
                                                ))                                      

            elif (command == 'shutdown'):
                self.wfile.write(self._html('Shutting Down startDuetLapse3.<br><br>'
                                            'Local time is:  '+localtime+'<br><br>'
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
        self.wfile.write(self._html('Invalid Request<br>'
                                    '<h3>'
                                    '<pre>Valid request are command=<br>'
                                    'with options:   '+options+'</pre><br>'
                                    'if command=start is used then args= must be used<br>'
                                    'with valid options for DuetLapse3<br>'
                                    'additionally nohup=yes can be added<br><br>'
                                    'If command=terminate is used pids= must be used<br>'
                                    'with either pids=all or pids={process id}'
                                    '</h3>'
                                    ))       
        return

    def log_request(self, code=None, size=None):
        pass

    def log_message(self, format, *args):
        pass
    
def createHttpListener():
    global listener
    listener = HTTPServer((host, port), MyHandler)
    listener.serve_forever()
    #sys.exit(0)  #May not be needed since never returns from serve_forever
    
def closeHttpListener():
    global listener
    print('!!!!! Stop requested by http listener !!!!!')
    listener.shutdown()
    listener.server_close()
    print('Terminated')
    sys.exit(0)
    
def checkInstances(thisinstance):
    proccount = 0
    for p in psutil.process_iter():
        if ('python3' in p.name() and thisinstance in p.cmdline()):
            proccount += 1
            if (proccount > 1):
                print('')
                print('#############################')
                print('Process is already running... shutting down.')
                print('#############################')
                print('')
                sys.exit(2)
    return  
    
def getThisInstance(thisinstancepid):
    for p in psutil.process_iter():
        if ('python3' in p.name() and thisinstancepid == p.pid):
            cmdline = str(p.cmdline())
            #clean up the appearance
            cmdline = cmdline.replace('python3','')
            cmdline = cmdline.replace('[','')
            cmdline = cmdline.replace(']','')
            cmdline = cmdline.replace(',','')
            cmdline = cmdline.replace("'",'')
            cmdline = cmdline.replace('  ','')
            pid = str(p.pid)
            thisrunning = 'This program is running with<br>Process id:    '+pid+'<br>Command line:    '+cmdline+''
    return  thisrunning  
        
def getRunningInstances(thisinstance):
    running = ''
    pidlist = []
    for p in psutil.process_iter():
        if ('python3' in p.name() and not thisinstance in p.cmdline() and '-duet' in p.cmdline()): #Check all other python3 instances
            cmdline = str(p.cmdline())
            #clean up the appearance
            cmdline = cmdline.replace('python3','')
            cmdline = cmdline.replace('[','')
            cmdline = cmdline.replace(']','')
            cmdline = cmdline.replace(',','')
            cmdline = cmdline.replace("'",'')
            cmdline = cmdline.replace('  ','')
            pidlist.append(p.pid)
            pid = str(p.pid)
            running = running+('Process id:  '+pid+'<br>'
                               +cmdline+'<br>'               
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
    thisinstance = __file__
    checkInstances(thisinstance)    #There can only be one instance running
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
