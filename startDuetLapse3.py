#!python3
"""
Simple HTTP server for starting and stopping DuetLapse3
# Copyright (C) 2020 Stuart Strolin all rights reserved.
# Released under The MIT License. Full text available via https://opensource.org/licenses/MIT
#
#
# Developed on WSL with Debian Buster. Tested on Raspberry pi, Windows 10 and WSL. SHOULD work on most other linux distributions. 
"""

import argparse
import os
import sys
import threading
import subprocess
import shlex
import psutil
from DuetLapse3 import whitelist, checkInstances, returncode
import socket
import time
import platform
import requests
import shutil
import signal
import logging

startDuetLapse3Version = '4.0.0'
#  Efficiency improvements and minor bug fixes

class whitelistParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if status:
            raise ValueError(message)


def runsubprocess(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True)
        if str(result.stderr) != '':
            logger.info('Command Failure: ' + str(cmd))
            logger.debug(str(result.stderr))
            return False
        else:
            logger.info('Command Success : ' + str(cmd))
            if result.stdout != '':
                logger.debug(str(result.stdout))
            return True
    except (subprocess.CalledProcessError, OSError) as e:
        logger.info('Exception: ' + str(cmd))
        logger.info(str(e))
        return False


def init():
    # parse command line arguments
    parser = argparse.ArgumentParser(
            description='Helper Web Server for running DuetLapse3 remotely. V' + startDuetLapse3Version,
            allow_abbrev=False)
    # Environment
    parser.add_argument('-host', type=str, nargs=1, default=['0.0.0.0'],
                        help='The ip address this service listens on. Default = 0.0.0.0')
    parser.add_argument('-port', type=int, nargs=1, default=[0],
                        help='Specify the port on which the server listens. Default = 0')
    parser.add_argument('-args', type=str, nargs=argparse.PARSER, default=[''], help='Arguments. Default = ""')
    parser.add_argument('-topdir', type=str, nargs=1, default=[''], help='default = This program directory')
    parser.add_argument('-maxffmpeg', type=int, nargs=1, default=[2], help='Max instances of ffmpeg during video creation. Default = 2')
    parser.add_argument('-nolog', action='store_true', help='Do not create a log file')
    parser.add_argument('-verbose', action='store_true', help='Detailed Logging')
    parser.add_argument('-fps', type=int, nargs=1, default=[10], help='Frames-per-second for video. Default = 10')
    args = vars(parser.parse_args())

    global host, port, defaultargs, topdir, maxffmpeg, nolog, verbose, debug, ffmpegquiet, fps

    host = args['host'][0]
    port = args['port'][0]
    defaultargs = args['args'][0]
    topdir = args['topdir'][0]
    maxffmpeg = args['maxffmpeg'][0]
    nolog = args['nolog']
    verbose = args['verbose']
    fps = str(args['fps'][0])



    # How much output
    if verbose:
        debug = ''
        ffmpegquiet = ' -loglevel quiet'
    else:
        ffmpegquiet = ' -loglevel quiet'
        if not win:
            debug = ' > /dev/null 2>&1'
        else:
            debug = ' > nul 2>&1'

    # Create a custom logger
    global logfilename, logger
    logger = logging.getLogger(__name__)
    if verbose:  #  Capture all log messages
        logger.setLevel(logging.DEBUG)
    else:        #  Ignore debug messages
        logger.setLevel(logging.INFO)

    # Create handlers and formats
    c_handler = logging.StreamHandler()
    c_format = logging.Formatter(' %(message)s')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)
    logfilename = ''
    if nolog is False:
        if topdir == '':
            dir = os.path.dirname(os.path.abspath(__file__))
        else:
            dir = topdir
        logfilename = dir + '/startDuetLapse3.log'


        dir = os.path.normpath(dir)
        logfilename = os.path.normpath(logfilename)
        try:
            os.makedirs(dir)
        except OSError as e:
            logger.info('Could not create dir ' + str(e))            

        f_handler = logging.FileHandler(logfilename, mode='w', encoding='utf-8')
        f_format = logging.Formatter('%(asctime)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)
        logger.info('Log file created at ' + logfilename)

###########################
# make Web calls
###########################

def urlCall(url, timelimit):
    logger.debug(str(url))
    loop = 0
    limit = 2  # Started at 2 - seems good enough to catch transients
    while (loop < limit):
        try:
            # headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36', "Upgrade-Insecure-Requests": "1","DNT": "1","Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language": "en-US,en;q=0.5","Accept-Encoding": "gzip, deflate"}
            r = requests.get(url, timeout=timelimit)
            if r.ok:
                logger.info('Call Successful')
            else:
                logger.info('Call Failed')

            logger.info(url)
            break
        except requests.ConnectionError as e:
            logger.info('There was a network failure: ' + str(e))
            loop += 1
        except requests.exceptions.Timeout as e:
            logger.info('There was a timeout failure: ' + str(e))
            loop += 1
        time.sleep(1)

    return True


###########################
# Integral Web Server
###########################

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import urllib
from urllib.parse import urlparse, parse_qs
import html
import pathlib


class MyHandler(SimpleHTTPRequestHandler):
    # Default selectMessage
    global refreshing, selectMessage, lastdir
    lastdir = ''
    txt = []
    txt.append('<h3>')
    txt.append('Status will update every 60 seconds')
    txt.append('</h3>')
    refreshing = ''.join(txt)
    selectMessage = refreshing

    def redirect_url(self, url):
        self.send_response(303)
        self.send_header('Location', url)
        self.end_headers()

    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def _refresh(self, message):
        content = f'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"><html><head><meta http-equiv="refresh" content="60"></head><body><h2>{message}</h2></body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!

    def _html(self, message):
        content = f'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"><html><head></head><body><h2>{message}</h2></body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!

    def update_content(self):
        global pidlist
        pidlist = []
        localtime = time.strftime('%A - %H:%M', time.localtime())
        # portlist = []
        runninginstances, pidlist = getRunningInstances(thisinstance, refererip)
        thisrunninginstance = getThisInstance(thisinstancepid)

        txt = []
        txt.append('startDuetLapse3 Version ' + startDuetLapse3Version + '<br>')
        txt.append('<h4>' + thisrunninginstance + '</h4>')
        header = ''.join(txt)

        txt = []
        txt.append('<h3>')
        txt.append('startDuetLapse3 Version ' + startDuetLapse3Version + '<br>')
        txt.append('As of :  ' + localtime + '<br>')
        txt.append('</h3>')
        txt.append('<h4>')
        txt.append('Running instances of DuetLapse3 are:<br>' + runninginstances)
        txt.append('</h4>')
        status = ''.join(txt)

        txt = []
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="status" />')
        txt.append('<input type="submit" value="Status" style="background-color:green"/>')
        txt.append('</form>')
        txt.append('</div>')
        statusbutton = ''.join(txt)

        txt = []
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="start" />')
        txt.append('<input type="submit" value="Start" style="background-color:orange"/>')
        txt.append('</form>')
        txt.append('</div>')
        startbutton = ''.join(txt)

        txt = []
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="terminate" />')
        txt.append('<input type="submit" value="Terminate" style="background-color:yellow"/>')
        txt.append('</form>')
        txt.append('</div>')
        terminatebutton = ''.join(txt)

        txt = []
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="shutdown" />')
        txt.append('<input type="hidden" name="shutdownask" value="True"/>')
        txt.append('<input type="submit" value="Shutdown" style="background-color:red"/>')
        txt.append('</form>')
        txt.append('</div>')
        shutdownbutton = ''.join(txt)

        txt = []
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="files" value= ' + topdir + ' />')
        txt.append('<input type="submit" value="Files" style="background-color:green"/>')
        txt.append('</form>')
        txt.append('</div>')
        filesbutton = ''.join(txt)

        txt = []
        txt.append('<style type="text/css">')
        txt.append('{')
        txt.append('position:relative;')
        txt.append('width:200px;')
        txt.append('}')
        txt.append('.inline{')
        txt.append('margin-left: 5px; margin-bottom:8px;')
        txt.append('display:inline-block;')
        txt.append('}')
        txt.append('.pad30{')
        txt.append('margin-left: 30px;')
        txt.append('}')
        txt.append('input[type=submit] {')
        txt.append('width: 6em;  height: 2em;')
        txt.append('background:#ccc; border:0 none; cursor:pointer; -webkit-border-radius: 5px;border-radius: 5px;')
        txt.append('}')
        txt.append('.process-disp{')
        txt.append('width:550px; height:25px; overflow:auto; resize:both; border:1px solid; font-size:12px; line-height:12px;')
        txt.append('}')
        txt.append('.info-disp{')
        txt.append('width:550px; height:auto; overflow:auto; resize:both; border:1px solid; font-size:16px; line-height:16px;')
        txt.append('}')
        txt.append('} </style>')
        txt.append('<style> textarea {')
        txt.append('width:550px; height:100px; wrap:soft;')
        txt.append('box-sizing: border-box; border: 2px solid #ccc; border-radius: 4px; background-color: #f8f8f8;')
        txt.append('font-size: 16px;')
        txt.append('} </style>')
        cssstyle = ''.join(txt)

        buttons = statusbutton + startbutton + terminatebutton + filesbutton + shutdownbutton + cssstyle

        return header, status, buttons

    def do_GET(self):
        try:
            options = 'status, start, terminate'
            global referer, refererip, selectMessage, refreshing, lastdir
            referer = self.headers['Host']  # Should always be there for HTTP/1.1
            if not referer:  # Lets try authority
                referer = self.headers['authority']
                if not referer:
                    referer = 'localhost'  # Best guess if all else fails
            split_referer = referer.split(":", 1)
            refererip = split_referer[0]  # just interested in the calling address as we know our port number
            # Update main content
            header, status, buttons = self.update_content()

            if ('favicon.ico' in self.path):
                return

            query_components = parse_qs(urlparse(self.path).query)

            if not query_components and self.path != '/':
                logger.debug(str(self.path))
            else:
                logger.debug(str(query_components))

            if ((query_components and query_components.get('files')) or (not query_components and self.path != '/')):
                #We use the linux path convention here - corrected for win later
                if query_components.get('files'):  # called from the file button
                    if lastdir == '':
                        thisdir = '/'
                    else:
                        thisdir = lastdir
                else:
                    thisdir = self.path

                lastdir, _ = os.path.split(thisdir)  # only interested in the path portion cuz could be file display request
                if not lastdir.endswith('/'): #force it to be recognized as a dir
                    lastdir = lastdir +'/'
                selectMessage = self.display_dir(thisdir)

            if (query_components.get('delete')):
                file = query_components['delete'][0]
                filepath, _ = os.path.split(file)
                filepath = filepath + '/'
                file = topdir + file
                file = os.path.normpath(file)
                if os.path.isdir(file):
                    try:
                        shutil.rmtree(file)
                    except shutil.Error as e:
                        logger.info('Error deleting dir ' + str(e))
                elif os.path.isfile(file): 
                    try:
                        os.remove(file)
                    except OSError as e:
                        logger.info('Error deleting file ' + str(e))


                selectMessage = self.display_dir(filepath)

            if (query_components.get('zip')):
                file = query_components['zip'][0]
                filepath, _ = os.path.split(file)
                filepath = filepath + '/'
                file = topdir + file
                zipedfile = file + '.zip'

                file = os.path.normpath(file)
                zipedfile = os.path.normpath(zipedfile)
                result = make_archive(file, zipedfile)
                selectMessage = '<h3>' + result + '<br></h3>' + self.display_dir(filepath)

            if (query_components.get('video')):
                global fps
                if (query_components.get('fps')):
                    thisfps = query_components['fps'][0]
                    try:
                        thisfps = int(thisfps)
                        if thisfps > 0:
                            fps = thisfps
                            logger.info('fps changed to ' + str(fps))
                    except ValueError:
                        pass
                fps = str(fps)
                file = query_components['video'][0]
                filepath, _ = os.path.split(file)
                filepath = filepath + '/'
                file = topdir + file

                file = os.path.normpath(file)

                result = createVideo(file)

                selectMessage = '<h3>'+result+'<br></h3>'+self.display_dir(filepath)

            if (query_components.get('command')):
                # Update main content
                header, status, buttons = self.update_content()

                command = query_components['command'][0]

                if (command == 'status'):
                    if selectMessage == None:
                        selectMessage = refreshing
                    self._set_headers()
                    self.wfile.write(self._refresh(status + buttons + selectMessage))
                    selectMessage = refreshing
                    return

                elif (command == 'start'):
                    selectMessage = self.start_process(query_components)

                elif (command == 'terminate'):
                    selectMessage = self.terminate_process(query_components)

                elif (command == 'shutdown'):
                    selectMessage = self.shutdown_process(query_components)

                else:
                    txt = []
                    txt.append('<h3>')
                    txt.append('Illegal: command=' + command + '<br><br>')
                    txt.append('</h3>')
                    txt.append('<div class="info-disp">')
                    txt.append('Valid options are: command= ' + options + '</h3>')
                    txt.append('</div>')
                    selectMessage = ''.join(txt)  # redirect to status page
            new_url = 'http://' + referer + '/?command=status'
            self.redirect_url(new_url)
            return
        except: #supress disconnect messages
            return
        #  --------------
        #  End of do_Get
        #  --------------

    def log_request(self, code=None, size=None):
        pass

    def log_message(self, format, *args):
        pass

    # http listener custom functions

    def start_process(self, query_components):
        global defaultargs
        if (query_components.get('args')):
            args = query_components['args'][0]
            args = args.replace('\n', '')  # remove any newline
            # need to put back encoded punctuation
            defaultargs = html.escape(args)
            # Test to see if the options are valid
            checkarguments = whitelistParser(description='Checking for valid inputs to DuetLapse3', allow_abbrev=False)
            checkarguments = whitelist(checkarguments)
            try:
                checkarguments.parse_args(shlex.split(args))
            except ValueError as message:
                logger.debug(str(message))
                txt = []
                txt.append('<h3>')
                txt.append('The following errors were detected:<br>')
                txt.append('</h3>')
                txt.append('<div class="info-disp">')
                txt.append(str(message))
                txt.append('</div>')
                selectMessage = ''.join(txt)
                args = ''
                return selectMessage
        else:
            args = ''

        if (args != ''):
            if win:
                cmd = 'python3 DuetLapse3.py ' + args
            else:  # Linux
                cmd = 'python3 ./DuetLapse3.py ' + args

            newproc = subprocess.Popen(cmd, shell=True, start_new_session=True)  # run the program

            #  Wait to see if DuetLapse3 starts cleanly
            looptime = 30 #  sec
            interval  = 0.5 # sec
            loop = 0
            Running = True
            while loop < (looptime/interval):
                if newproc.poll() != None:
                    Running = False
                    break
                time.sleep(interval)
                loop += 1

            if Running:
                txt = []
                txt.append('<h3>')
                txt.append('DuetLapse3 started.')
                txt.append('</h3>')
                selectMessage = ''.join(txt)
            else:  #  process terminated

                logger.info('Failed to start after ' +str(loop*interval) + ' s with error: ' + returncode(newproc.poll()))

                txt = []
                txt.append('<h3>')
                txt.append('DuetLapse3 failed to start after ' +str(loop*interval) + 's because:   ' + returncode(newproc.poll()) + '<br><br>')
                txt.append('</h3>')
                txt.append('<textarea>')
                txt.append(cmd)
                txt.append('</textarea>')
                selectMessage = ''.join(txt)
        else:
            txt = []
            txt.append('<form action="http://' + referer + '">')
            txt.append('<input type="hidden" name="command" value="start" />')
            txt.append('<br>')
            txt.append('<textarea id="args" name="args">')
            txt.append(defaultargs)
            txt.append('</textarea>')
            txt.append('<br><br>')
            txt.append('<input type="submit" value="Start" style="background-color:orange"/>')
            txt.append('</form>')
            selectMessage = ''.join(txt)
        return selectMessage

    def terminate_process(self, query_components):
        if (query_components.get('pids')):
            pids = query_components['pids'][0]
        else:
            pids = ''

        if (pids != ''):

            if (pids == 'all'):
                pidmsg = 'All running instances.'
            else:
                pidmsg = 'For instances with process id: ' + str(pids)

            for pid in pidlist:
                thispid = pid[0]
                thisport = pid[1]
                if (pids == 'all' or pids == str(thispid)):
                    if (thisport == 0):
                        try:
                            os.kill(thispid, 2)
                        except:
                            pass
                    else:
                        URL = 'http://' + refererip + ':' + str(thisport) + '/?command=terminate'
                        urlCall(URL, 5)
            txt = []
            txt.append('<h3>')
            txt.append('Terminating the following DuetLapse3 Instances.<br>')
            txt.append('</h3>')
            txt.append('<div class="info-disp">')
            txt.append(pidmsg)
            txt.append('<br><br>Note that some instances may take several minutes to shut down.')
            txt.append('</div')
            selectMessage = ''.join(txt)
        else:
            if win:
                txt = []
                txt.append('NOTE: Only instances with http ports will terminate gracefully.<br><br>')
                txt.append('All others will just shutdown (no video created)<br><br>')
                txt.append('This is a windows limitation.<br>')
                osnote = ''.join(txt)
            else:
                osnote = ''

            txt = []
            txt.append('<div class="info-disp">')
            txt.append('<form action="http://' + referer + '">' + osnote + '<br>')
            txt.append('<input type="hidden" name="command" value="terminate" />')
            txt.append('<input type="text" id="pid" name="pids" value="all"/>')
            txt.append('<input class = "pad30" type="submit" value="Terminate" style="background-color:yellow"/>')
            txt.append('</form>')
            txt.append('</div>')
            selectMessage = ''.join(txt)
        return selectMessage

    def shutdown_process(self, query_components):
        if query_components.get('shutdownask'):
            shutdown = False
        else:
            shutdown = True

        if shutdown is True:
            txt = []
            txt.append('<h3>')
            txt.append('Shutting Down startDuetLapse3.<br>')
            txt.append('</h3>')

            logger.info('!!!!!! DuetLapse3 was shutdown by http request !!!!!!')

            threading.Thread(name='shut_down', target=shut_down, args=(), daemon=False).start()
        else:
            if win:
                txt = []
                txt.append('DuetLapse3 instances will NOT be shutdown<br><br>')
                txt.append('This is a windows limitation<br><br>')
                txt.append('Use Terminate to shutdown running instances<br>')
                osnote = ''.join(txt)
            else:
                txt = []
                txt.append('If startDuetLapse3 is running as a service (e.g. under systemctl)<br>')
                txt.append('DuetLapse3 instances that were started by this program WILL be shutdown<br><br>')
                txt.append('If startDuetLapse3 is running from a console<br>')
                txt.append('DuetLapse3 instances started by this program will NOT be shutdown<br><br>')
                txt.append('This is a linux behavior<br>')
                osnote = ''.join(txt)

            txt = []
            txt.append('<div class="info-disp">')
            txt.append('<form action="http://' + referer + '">' + osnote + '<br>')
            txt.append('<input type="hidden" name="command" value="shutdown" />')
            txt.append('<input class = "pad5" type="submit" value="Shutdown" style="background-color:red"/>')
            txt.append('</form>')
            txt.append('</div>')

        selectMessage = ''.join(txt)
        return selectMessage

    def display_dir(self, path):
        path = path.split('?', 1)[0]  #get rid of any query arguments
        path = path.split('#', 1)[0]
        # Don't forget explicit trailing slash when normalizing. Issue17324
        trailing_slash = path.rstrip().endswith('/') #get rid of whitespace and verify trailing slash
        requested_dir = topdir + path

        if trailing_slash:  # this is a dir request
            response = self.list_dir(requested_dir)
            return response
        else:  # this is a file request
            requested_dir = requested_dir.replace('%CB%B8',
                                                  u'\u02f8')  # redoes raised colons that were replaced by encoded

            ctype = self.guess_type(requested_dir)

            try:
                f = open(requested_dir, 'rb')
                fs = os.fstat(f.fileno())
            except:
                logger.info('Problem opening file: ' + requested_dir)

            try:
                self.send_response(200)
                self.send_header("Content-type", ctype)
                self.send_header("Content-Length", str(fs[6]))
                self.end_headers()
                self.copyfile(f, self.wfile)
                f.close()
            except ConnectionError:
                logger.info('Connection reset - normal if displaying file')
            except:
                logger.info('Error sending file')

        return

    def list_dir(self, path):  # Copied from super class
        global lastdir
        # Pass the direstory tree and determine what can be done with each file / dir
        jpegfile = '.jpeg'
        deletablefiles = ['.mp4', '.log', '.zip']
        jpegfolder = []
        deletelist = []
        for thisdir, subdirs, files in os.walk(topdir):
            if not subdirs and not files:  # Directory is empty
                deletelist.append(os.path.join(thisdir, ''))
                if thisdir == topdir:
                    txt = []
                    txt.append('<h3>')
                    txt.append('There are no files to display at this time<br>')
                    txt.append('You likely need to start an instance of DuetLapse3 first')
                    txt.append('</h3>')
                    response = ''.join(txt)
                    return response

            for file in files:
                if any (ext in file for ext in deletablefiles):
                    deletelist.append(os.path.join(thisdir, file))

                elif file.lower().endswith(jpegfile.lower()) and subdirs == []:  # if ANY jpeg in bottom level folder
                    jpegfolder.append(os.path.join(thisdir, ''))
                    deletelist.append(os.path.join(thisdir, ''))
                    break  # Assume all files are jpeg

        try:
            displaypath = urllib.parse.unquote(path, errors='surrogatepass')
        except UnicodeDecodeError:
            displaypath = urllib.parse.unquote(path)

        displaypath = html.escape(displaypath, quote=False)

        try:
            list = os.listdir(path)
        except OSError:
            try:
                path = pathlib.Path(path)
                path = path.parent
                list = os.listdir(path)
            except OSError:
                txt = []
                txt.append('<h3>')
                txt.append('There are no files or directories named '+displaypath+'<br>')
                txt.append('or you do not have permission to access')
                txt.append('</h3>')
                response = ''.join(txt)
                return response

        # list.sort(key=lambda a: a.lower())
        list.sort(key=lambda fn: os.path.getmtime(os.path.join(path, fn))) # Have to use full path to stat file

        subdir = path.replace(topdir, '') #path relative to topdir
        parentdir, _ = os.path.split(subdir) # Get rid of trailing information
        parentdir, _ = os.path.split(parentdir)  # Go back up one level

        r = []
        r.append('<style>table {font-family: arial, sans-serif;border-collapse: collapse;}')
        #r.append('td {border: 1px solid #dddddd;text-align: left;padding: 0px;}')
        r.append('td {border: none; text-align: left;padding: 0px;}')
        r.append('tr:nth-child(even) {background-color: #dddddd;}</style>')
        r.append('<table>')
        r.append('<tr><th style="width:400px;"></th><th style="width:100px;"></th></tr>')


        if parentdir == subdir:  # we are at the top level
            child_dir = False
        else:
            child_dir = True
        # add parent dir
        if child_dir:
            if (not parentdir.endswith('/')) and (not parentdir.endswith('\\')):
                parentdir = parentdir + '/'  # identify it as a dir and not a file
            if parentdir == '/' or parentdir =='\\':
                parentdir = parentdir + '?files='  # go back to the top level directory
            if win:
                displayname = '.\\'
            else:
                displayname = './'
            r.append('<tr>')  # start the row
            r.append('<td><a href="%s">%s</a></td>' % (parentdir, html.escape(displayname, quote=False)))
            r.append('</tr>')  # end the row

        for name in list:
            fullname = os.path.join(path, name)
            fullname = os.path.normpath(fullname) #no trailing slash will add in later if its a directory
            action_name = fullname.replace(topdir, '')  # used to force delete and zip and video to be relative to topdir
            # we do this after above assignment so that we don't have problems with slash direction between OS's
            # Note: a link to a directory displays with @ and folder  with /
            linkname = displayname = name
            if os.path.islink(fullname):
                displayname = name + "@"

            if os.path.isdir(fullname):
                if win:
                    displayname = name + "\\"
                    linkname = name + "\\"
                    fullname = fullname +'\\'
                else:
                    displayname = name + "/"
                    linkname = name + "/"
                    fullname = fullname +'/'

            linkname = subdir + linkname  # make it relative
            linkname = linkname.replace('\\','/')  #use the html convention
            displayname = displayname.replace(u'\u02f8', ':')  # make it look nice replace raised colons

            r.append('<tr>')  # start the row
            r.append('<td><a href="%s">%s</a></td>' % (
                    urllib.parse.quote(linkname, errors='surrogatepass'), html.escape(displayname, quote=False)))
            actionable = True
            for pidstart in pidlist:  # can only delete for non-running instances
                if displayname.startswith(str(pidstart[0])):
                    actionable = False

            deletebutton = zipbutton = vidbutton = ''
            if fullname in deletelist and actionable and fullname != logfilename:
                txt = []
                txt.append('<td>')
                txt.append('<div class="inline">')
                txt.append('<form action="http://' + referer + '">')
                txt.append('<input type="hidden" name="delete" value="' + action_name + '" />')
                txt.append('<input type="submit" value="Delete" style="background-color:red"/>')
                txt.append('</form>')
                txt.append('</div>')
                txt.append('</td>')
                deletebutton = ''.join(txt)

            if fullname in jpegfolder and actionable:
                txt = []
                txt.append('<td>')
                txt.append('<div class="inline">')
                txt.append('<form action="http://' + referer + '">')
                txt.append('<input type="hidden" name="zip" value="' + action_name + '" />')
                txt.append('<input type="submit" value="Zip" style="background-color:yellow"/>')
                txt.append('</form>')
                txt.append('</td>')
                txt.append('</div>')
                zipbutton = ''.join(txt)

                txt = []
                txt.append('<td>')
                txt.append('<div class="inline">')
                txt.append('<form action="http://' + referer + '">')
                txt.append('<input type="hidden" name="video" value="' + action_name + '" />')
                txt.append('<input type="submit" value="Video" style="background-color:green"/>')
                txt.append('<input type="text" id="fps" name="fps" value=' + fps +  ' style="background-color:lime; width:30px; border:none"/>')
                txt.append('fps<br>')
                txt.append('</form>')
                txt.append('</div>')
                txt.append('</td>')
                vidbutton = ''.join(txt)

            action = deletebutton + zipbutton + vidbutton
            r.append(action)
            r.append('</tr>')

        r.append('</table>')

        response = ''.join(r)
        return response


#  ---------------------
#  End of requesthandler
#  ---------------------


def make_archive(source, destination):
    base = os.path.basename(destination)
    format = pathlib.Path(destination).suffix
    name = destination.replace(format,'')
    format = format.replace('.','')
    archive_from = os.path.dirname(source)
    archive_to = os.path.basename(source.strip(os.sep))
    try:
        shutil.make_archive(name, format, archive_from, archive_to)
        shutil.move('%s.%s' % (name, format), destination)
        msg = ('Zip processing completed')
    except Exception as msg1:
        msg = 'Error: There was a problem creating the zip file --'
        msg = msg + str(msg1)
    return msg

def createVideo(directory):
    # loop through directory count # files and detect if Camera1 / Camera2
    msg = 'Create Video'
    logger.info(msg)
    try:  #  Check to make sure we can create the video at the required destination
        list = os.listdir(directory)
    except OSError:
        msg = 'Error: No permission or directory not found'
        logger.info(msg)
        return msg

    cam1 = False
    cam2 = False
    frame = 0
    Cameras = []
    for name in list:
        if not cam1:
            if 'Camera1' in name:
                cam1 = True
                Cameras.append('Camera1')
        elif not cam2:
            if 'camera2' in name:
                cam2 = True
                Cameras.append('Camera2')
        frame += 1

    for cameraname in Cameras:
        if frame < int(fps):
            msg = 'Error: ' + cameraname + ': Cannot create video of less than 1 second: ' + fps + ' frames are required.'
            logger.info(msg)
            return msg

        logger.info(cameraname + ': now making ' + str(frame) + ' frames into a video')
        if 250 < frame:
            logger.info("This can take a while...")

        timestamp = time.strftime('%a-%H-%M', time.localtime())

        fn = os.path.normpath(directory + '_' + cameraname + '_' + timestamp + '.mp4')
        location = os.path.normpath(directory + '/' + cameraname + '_%08d.jpeg')
        cmd = 'ffmpeg -threads 1 ' + ffmpegquiet + ' -r ' + fps + ' -i ' + location + ' -vcodec libx264 -y -threads 2 ' + fn + debug
 

#  Wait for up to minutes for ffmpeg capacity to  become available
        #  If still not available - try anyway
        minutes = 5
        increment = 15  #  seconds
        loop = 0
        while loop < minutes*60:
            if ffmpeg_available():
                break
            else:
                time.sleep(increment)  # wait a while before trying again
                loop += increment
                logger.debug('Have waited ' + str(loop) + ' seconds for ffmpeg capacity')


        if runsubprocess(cmd) is False:
            msg = ('!!!!!!!!!!!  There was a problem creating the video for '+cameraname+' !!!!!!!!!!!!!!!')
            logger.info(msg)
        else:
            logger.info('Video processing completed for ' + cameraname)
            logger.info('Video is in file ' + fn)
            msg = 'Video(s) successfully created'

    return msg


def ffmpeg_available():
    count = 0
    max_count = maxffmpeg  # Default is 2
    for p in psutil.process_iter():
        if 'ffmpeg' in p.name():  # Check to see if it's running
            count += 1
        if count >= max_count:
            logger.info('Waiting for ffmpeg to become available')
            return False
    logger.info('There are ' + str(count) + ' instances of ffmpeg running')
    return True


def createHttpListener():
    global listener
    try:
        listener = ThreadingHTTPServer((host, port), MyHandler)
        threading.Thread(name='httpServer', target=listener.serve_forever, daemon=False).start()  #Avoids blocking
        logger.info('Started the http listener')
    except Exception as e:
        logger.info('There was a problem starting the http listener')
        sys.exit(7)


def closeHttpListener():
    global listener
    try:
        listener.shutdown()
        logger.info('!!!!! http listener stopped  !!!!!')
    except Exception as e:
        logger.debug('Could not terminate http listener')
        logger.debug(e)


def getOperatingSystem():
    #  What OS are we using?
    global win
    operatingsystem = platform.system()
    if (operatingsystem == 'Windows'):
        win = True
    else:
        win = False


def getThisInstance(thisinstancepid):
    thisrunning = ''
    for p in psutil.process_iter():
        if ('python3' in p.name() or 'pythonw' in p.name()) and thisinstancepid == p.pid:
            cmdlinestr = str(p.cmdline())
            # clean up the appearance
            cmdlinestr = cmdlinestr.replace('[', '')
            cmdlinestr = cmdlinestr.replace(']', '')
            cmdlinestr = cmdlinestr.replace(',', '')
            cmdlinestr = cmdlinestr.replace("'", '')
            cmdlinestr = cmdlinestr.replace('  ', '')
            pid = str(p.pid)
            thisrunning = 'This program is running with<br>Process id:    ' + pid + '<br>Command line:    ' + cmdlinestr + ''

    return thisrunning


def getRunningInstances(thisinstance, refererip):
    running = ''
    pidlist = []

    for p in psutil.process_iter():

        #if (('python3' in p.name() or 'pythonw' in p.name()) and not thisinstance in p.cmdline() and '-duet' in p.cmdline()):  # Check all other python3 instances
        if 'python' in p.name():
            #logger.info(thisinstance)
            cmdstring = ''.join(p.cmdline())
            if not 'DuetLapse3.py' in cmdstring or 'startDuetLapse3.py' in cmdstring:
                continue      # Only want DuetLapse3.py instances
            # Get the port if used else set it to zero
            cmdline = p.cmdline()
            try:
                index = cmdline.index('-port')
                index += 1
                port = cmdline[index]
            except ValueError:
                port = 0

            # clean up the appearance
            cmdlinestr = str(p.cmdline())
            cmdlinestr = cmdlinestr.replace('[', '')
            cmdlinestr = cmdlinestr.replace(']', '')
            cmdlinestr = cmdlinestr.replace(',', '')
            cmdlinestr = cmdlinestr.replace("'", '')
            cmdlinestr = cmdlinestr.replace('  ', '')
            pidlist.append((p.pid, port))
            pid = str(p.pid)

            if (port == 0):
                txt = []
                txt.append('Process id:  ' + pid + '<br>')
                txt.append('<div class="process-disp">')
                txt.append(cmdlinestr)
                txt.append('</a>')
                txt.append('<br>')
                txt.append('</div>')
                running = running + ''.join(txt)
            else:  # Format for html link
                txt = []
                txt.append('Process id:  ' + pid + ' -- Port:  ' + str(port) + '<br>')
                txt.append('<div class="process-disp">')
                txt.append('<a href=\"http://' + refererip + ':' + str(port))
                txt.append('\?command=status" target="_blank">' + cmdlinestr)
                txt.append('</a>')
                txt.append('<br>')
                txt.append('</div>')
                running = running + ''.join(txt)

    if running == '':
        running = 'None'

    return running, pidlist


def shut_down():

    # closeHttpListener()

    #Shutdown all the open threads
    for thread in threading.enumerate():
        if thread.name == 'MainThread' or thread == threading.current_thread():
            continue
        logger.debug('Attempting to shutdown ' + str(thread.name))
        try:
            thread.join(10)
        except Exception as e:
            logger.info('Could not terminate ' + str(thread.name))
            logger.debug(e)
    logger.info('Program Terminated')
    os.kill(int(thisinstancepid), 9)



# Allows process running in background or foreground to be gracefully
# shutdown with SIGINT (kill -2 <pid> also handles KeyboardInterrupt

def quit_gracefully(*args):
    logger.info('!!!!!! Stopped by SIGINT or CTL+C  !!!!!!')
    logger.info('Terminating DuetLapse3 instances')
    logger.info(str(pidlist))
    for pid in pidlist:
        thispid = pid[0]
        try:
            logger.info(str(thispid))
            os.kill(thispid, 2)
        except OSError:
            pass
    shut_down()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, quit_gracefully)

"""
Main Program
"""
if __name__ == "__main__":

    #  global thisinstance, thisinstancepid, topdir
    #  global refreshing, selectMessage, lastdir
    refreshing = selectMessage = lastdir = ''
    getOperatingSystem()  # some commands are os specific
    thisinstance = os.path.basename(__file__)

    if not win:
        thisinstance = './' + thisinstance

    _ = checkInstances(thisinstance, 'single')  # There can only be one instance running
    thisinstancepid = os.getpid()
    
    init()

    if topdir == '':
        topdir = os.path.dirname(os.path.realpath(__file__))
    # Get the slashes going the right way
    topdir = os.path.normpath(topdir)

    if port != 0:
        try:
            sock = socket.socket()
            if sock.connect_ex((host, port)) == 0:
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info('Sorry, port ' + str(port) + ' is already in use.')
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                sys.exit(2)

            createHttpListener()

        except KeyboardInterrupt:
            pass  # This is handled as SIGINT
    else:
        logger.info('No port number was provided or port is already in use')
        sys.exit(2)
