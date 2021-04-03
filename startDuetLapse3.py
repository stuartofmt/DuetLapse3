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
startDuetLapse3Version = '3.4.2'
import argparse
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
import requests
import shutil


class whitelistParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if status:
            raise ValueError(message)


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
    parser.add_argument('-maxffmpeg', type=int, nargs=1, default=[2],help='Max instances of ffmpeg during video creation. Default = 2')
    args = vars(parser.parse_args())

    global host, port, defaultargs, topdir, maxffmpeg

    host = args['host'][0]
    port = args['port'][0]
    defaultargs = args['args'][0]
    topdir = args['topdir'][0]
    maxffmpeg = args['maxffmpeg'][0]


###########################
# make Web calls
###########################
def blindUrlCall(url, timelimit):  # Fire and forget - assumed to be successful
    threading.Thread(target=urlCall, args=(url, timelimit)).start()


def urlCall(url, timelimit):
    loop = 0
    limit = 2  # Started at 2 - seems good enough to catch transients
    while (loop < limit):
        try:
            # headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36', "Upgrade-Insecure-Requests": "1","DNT": "1","Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language": "en-US,en;q=0.5","Accept-Encoding": "gzip, deflate"}
            r = requests.get(url, timeout=timelimit)
            break
        except requests.ConnectionError as e:
            print('There was a network failure: ' + str(e))
            loop += 1
        except requests.exceptions.Timeout as e:
            print('There was a timeout failure: ' + str(e))
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
import io
import pathlib


class MyHandler(SimpleHTTPRequestHandler):
    # Default selectMessage
    global refreshing, selectMessage, lastdir
    lastdir = ''
    txt = []
    txt.append('<h3><pre>')
    txt.append('Status will update every 60 seconds')
    txt.append('</pre></h3>')
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
        txt.append('startDuetLapse3 Version ' + startDuetLapse3Version + '<br>')
        txt.append('<h3>')
        txt.append('<br>As of :  ' + localtime + '<br>')
        txt.append('Running instances of DuetLapse3 are:<br><br>' + runninginstances + '</h3>')
        status = ''.join(txt)

        txt = []
        txt.append('<div class="divider">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="status" />')
        txt.append('<input type="submit" value="Status" style="background-color:green"/>')
        txt.append('</form>')
        txt.append('</div>')
        statusbutton = ''.join(txt)

        txt = []
        txt.append('<div class="divider">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="start" />')
        txt.append('<input type="submit" value="Start" style="background-color:orange"/>')
        txt.append('</form>')
        txt.append('</div>')
        startbutton = ''.join(txt)

        txt = []
        txt.append('<div class="divider">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="terminate" />')
        txt.append('<input type="submit" value="Terminate" style="background-color:yellow"/>')
        txt.append('</form>')
        txt.append('</div>')
        terminatebutton = ''.join(txt)

        txt = []
        txt.append('<div class="divider">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="shutdown" />')
        txt.append('<input type="submit" value="Shutdown" style="background-color:red"/>')
        txt.append('</form>')
        txt.append('</div>')
        shutdownbutton = ''.join(txt)

        txt = []
        txt.append('<div class="divider">')
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
        txt.append('.divider{')
        txt.append('width:200px;')
        txt.append('height:auto;')
        txt.append('display:inline-block;')
        txt.append('}')
        txt.append('.divider1{')
        txt.append('width:10em;')
        txt.append('height:2em;')
        txt.append('margin: auto;')
        txt.append('}')
        txt.append('.pad30{')
        txt.append('margin-left: 30px;')
        txt.append('}')
        txt.append('input[type=submit] {')
        txt.append('width: 10em;  height: 2em;')
        txt.append('}')
        txt.append('</style>')
        buttonstyle = ''.join(txt)

        buttons = statusbutton + startbutton + terminatebutton + filesbutton + shutdownbutton + buttonstyle

        return header, status, buttons;

    def do_GET(self):
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

        if ((query_components and query_components.get('files')) or (not query_components and self.path != '/')):
            #We use the linuz path convention here - corrected for win later
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

            if win:
                file = file.replace('/', '\\')
                if os.path.isdir(file):
                    cmd = 'rmdir /s /q "' + file + '"'
                else:
                    cmd = 'del /q "' + file + '"'
            else:
                cmd = 'rm -rf "' + file + '"'

            try:
                subprocess.call(cmd, shell=True)
                print('!!!!! http delete processed for ' + file + ' !!!!!')
            except:
                print('!!!!! An error occured trying to delete ' + file + ' !!!!!')

            selectMessage = self.display_dir(filepath)

        if (query_components.get('zip')):
            file = query_components['zip'][0]
            filepath, _ = os.path.split(file)
            filepath = filepath + '/'
            file = topdir + file
            zipedfile = file + '.zip'

            if win:
                file = file.replace('/', '\\')
                zipedfile = zipedfile.replace('/', '\\')

            #threading.Thread(target=make_archive, args=(file, zipedfile,)).start()
            result = make_archive(file, zipedfile)
            selectMessage = '<h3>' + result + '<br></h3>' + self.display_dir(filepath)
            #selectMessage = self.display_dir(filepath)

        if (query_components.get('video')):
            file = query_components['video'][0]
            filepath, _ = os.path.split(file)
            filepath = filepath + '/'
            file = topdir + file

            if win:
                file = file.replace('/', '\\')

            #threading.Thread(target=createVideo, args=(file,)).start()
            result = createVideo(file)

            selectMessage = '<h3>'+result+'<br></h3>'+self.display_dir(filepath)

        if (query_components.get('command')):
            # Update main content
            header, status, buttons = self.update_content()

            command = query_components['command'][0]
            """        
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
            """
            if (command == 'status'):
                self._set_headers()
                if selectMessage == None:
                    selectMessage = refreshing
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
                txt.append('<h3><pre>')
                txt.append('Illegal value for command=<br>')
                txt.append('Valid options are:   ' + options + '</pre></h3>')
                selectMessage = ''.join(txt)  # redirect to status page
        new_url = 'http://' + referer + '/?command=status'
        self.redirect_url(new_url)
        return
        """
        End of do_Get
        """

    def log_request(self, code=None, size=None):
        pass

    def log_message(self, format, *args):
        pass

    # http listener custom functions

    def start_process(self, query_components):
        if query_components.get('nohup'):
            nohup = query_components['nohup'][0]
        else:
            nohup = ''

        if (nohup != 'yes'):  # normalize
            nohup = ''

        whitelisterror = ''
        if (query_components.get('args')):
            args = query_components['args'][0]
            global defaultargs
            # need to put back encoded punctuation
            defaultargs = html.escape(args)
            # Test to see if the options are valid
            checkarguments = whitelistParser(description='Checking for valid inputs to DuetLapse3', allow_abbrev=False)
            checkarguments = whitelist(checkarguments)
            try:
                checkedargs = vars(checkarguments.parse_args(shlex.split(args)))
                duetport = checkedargs['port'][0]
            except ValueError as message:
                txt = []
                txt.append('<h3>')
                txt.append('The following errors were detected:<br>')
                txt.append('<pre>' + str(message) + '</pre>')
                txt.append('</h3>')
                selectMessage = ''.join(txt)
                args = ''
                return selectMessage
        else:
            args = ''

        if (args != ''):
            if win:
                if (nohup == 'yes'):
                    cmd = 'pythonw DuetLapse3.py ' + args
                else:
                    cmd = 'python3 DuetLapse3.py ' + args
            else:  # Linux
                if (nohup == 'yes'):
                    cmd = 'nohup python3 ./DuetLapse3.py ' + args + ' &'
                else:
                    cmd = 'python3 ./DuetLapse3.py ' + args + ' &'

            subprocess.Popen(cmd, shell=True)  # run the program
            txt = []
            txt.append('<h3>')
            txt.append('Attempting to start DuetLapse3 with following options:<br>')
            txt.append('<pre>' + cmd + '<br><br>')
            txt.append('</pre>')
            txt.append('</h3>')
            selectMessage = ''.join(txt)
        else:
            txt = []
            txt.append('<div>')
            txt.append('<form action="http://' + referer + '">')
            txt.append('<input type="hidden" name="command" value="start" />')
            txt.append('<input type="text" id="args" name="args" value="' + defaultargs + '" size="200"/>')
            txt.append('<br><br>')
            txt.append('<input type="submit" value="Start" style="background-color:orange"/>')
            txt.append('</form>')
            txt.append('</div>')
            selectMessage = ''.join(txt)
        return selectMessage

    def terminate_process(self, query_components):
        if (query_components.get('pids')):
            pids = query_components['pids'][0]
        else:
            pids = ''

        if (pids != ''):

            if (pids == 'all'):
                pidmsg = 'All running instances'
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
                        # blindUrlCall(URL, 5)
                        urlCall(URL, 5)
            txt = []
            txt.append('<h3>')
            txt.append('Terminating the following DuetLapse3 Instances.<br>')
            txt.append('<pre>' + pidmsg + '<br>')
            txt.append('Note that some instances may take several minutes to shut down<br><br>')
            txt.append('</pre>')
            txt.append('</h3>')
            selectMessage = ''.join(txt)
        else:
            if win:
                txt = []
                txt.append('<h3><pre>')
                txt.append('NOTE: Only instances with http ports will terminate gracefully<br>')
                txt.append('All others will just shutdown (no video created)<br>')
                txt.append('This is a windows limitation')
                txt.append('</pre></h3>')
                winnote = ''.join(txt)
            else:
                winnote = ''

            txt = []
            txt.append('<div>')
            txt.append('<form action="http://' + referer + '">' + winnote + '<br>')
            txt.append('<input type="hidden" name="command" value="terminate" />')
            txt.append('<input type="text" id="pid" name="pids" value="all" size="6"/>')
            txt.append('<input class = "pad30" type="submit" value="Terminate" style="background-color:yellow"/>')
            txt.append('</form>')
            txt.append('</div>')
            selectMessage = ''.join(txt)
        return selectMessage

    def shutdown_process(self, query_components):
        txt = []
        txt.append('<h1><pre>')
        txt.append('Shutting Down startDuetLapse3.<br>')
        txt.append('Any instances of DuetLapse3 will continue to run')
        txt.append('</pre></h1>')
        selectMessage = ''.join(txt)

        print('!!!!!! Shutdown by http request !!!!!!')
        threading.Thread(target=shut_down, args=()).start()

        return selectMessage

    def display_dir(self, path):
        path = path.split('?', 1)[0]  #get rid of any query arguments
        path = path.split('#', 1)[0]
        # Don't forget explicit trailing slash when normalizing. Issue17324
        trailing_slash = path.rstrip().endswith('/') #get rid of whitespace and verify trailing slash
        requested_dir = topdir + path
        if win:
            requested_dir = requested_dir.replace('/','\\') #since linux path format being passed

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
                print('Problem opening file: ' + requested_dir)

            try:
                self.send_response(200)
                self.send_header("Content-type", ctype)
                self.send_header("Content-Length", str(fs[6]))
                self.end_headers()
                self.copyfile(f, self.wfile)
                f.close()
            except ConnectionError:
                print('Connection reset - normal if displaying file')
            except:
                print('Error sending file')

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
                    txt.append('<h3><pre>')
                    txt.append('There are no files to display at this time<br>')
                    txt.append('You likely need to start an instance of DuetLapse3 first')
                    txt.append('</pre></h3>')
                    response = ''.join(txt)
                    return response

            for file in files:
                if any (ext in file for ext in deletablefiles):
                    deletelist.append(os.path.join(thisdir, file))

                elif file.lower().endswith(jpegfile.lower()) and subdirs == []:  # if ANY jpeg in bottom level folder
                    jpegfolder.append(os.path.join(thisdir, ''))
                    deletelist.append(os.path.join(thisdir, ''))
                    break  # Assume all files are jpeg
        """
        for each in deletelist:
            print('Delete = '+each)
      
        for folder in jpegfolder:
            print('Jpeg = '+folder)
        """

        try:
            displaypath = urllib.parse.unquote(path, errors='surrogatepass')
        except UnicodeDecodeError:
            displaypath = urllib.parse.unquote(path)

        displaypath = html.escape(displaypath, quote=False)

        try:
            list = os.listdir(path)
        except OSError:
            txt = []
            txt.append('<h3><pre>')
            txt.append('There are no files or directories named '+displaypath+'<br>')
            txt.append('or you do not have permission to access')
            txt.append('</pre></h3>')
            response = ''.join(txt)
            return response

        list.sort(key=lambda a: a.lower())

        subdir = path.replace(topdir, '') #path relative to topdir
        parentdir, _ = os.path.split(subdir) # Get rid of trailing information
        parentdir, _ = os.path.split(parentdir)  # Go back up one level

        r = []
        r.append('<style>table {font-family: arial, sans-serif;border-collapse: collapse;}')
        r.append('td {border: 1px solid #dddddd;text-align: left;padding: 0px;}')
        r.append('tr:nth-child(even) {background-color: #dddddd;}</style>')
        r.append('<table>')
        r.append('<tr><th style="width:400px"></th><th style="width:100px"></th></tr>')

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
            if fullname in deletelist and actionable:
                txt = []
                txt.append('<td>')
                txt.append('<form action="http://' + referer + '">')
                txt.append('<input type="hidden" name="delete" value="' + action_name + '" />')
                txt.append('<input type="submit" value="Delete" style="background-color:red"/>')
                txt.append('</form>')
                txt.append('</td>')
                deletebutton = ''.join(txt)

            if fullname in jpegfolder and actionable:
                txt = []
                txt.append('<td>')
                txt.append('<form action="http://' + referer + '">')
                txt.append('<input type="hidden" name="zip" value="' + action_name + '" />')
                txt.append('<input type="submit" value="Zip" style="background-color:yellow"/>')
                txt.append('</form>')
                txt.append('</td>')
                zipbutton = ''.join(txt)

                txt = []
                txt.append('<td>')
                txt.append('<form action="http://' + referer + '">')
                txt.append('<input type="hidden" name="video" value="' + action_name + '" />')
                txt.append('<input type="submit" value="Video" style="background-color:green"/>')
                txt.append('</form>')
                txt.append('</td>')
                vidbutton = ''.join(txt)

            action = deletebutton + zipbutton + vidbutton
            r.append(action)
            r.append('</tr>')

            # else:  # r.append('</tr>') #end the row

        r.append('</table>')

        response = ''.join(r)
        return response


"""
end of requesthandler
"""


def make_archive(source, destination):
    base = os.path.basename(destination)
    name = base.split('.')[0]
    format = base.split('.')[1]
    archive_from = os.path.dirname(source)
    archive_to = os.path.basename(source.strip(os.sep))
    try:
        shutil.make_archive(name, format, archive_from, archive_to)
        shutil.move('%s.%s' % (name, format), destination)
        msg = ('Zip processing completed')
    except:
        msg = 'Error: There was a problem creating the zip file'

    return msg



def createVideo(directory):
    # loop through directory count # files and detect if Camera1 / Camera2
    ffmpegquiet = ' -loglevel quiet'
    if not win:
        debug = ' > /dev/null 2>&1'
    else:
        debug = ' > nul 2>&1'

    try:
        list = os.listdir(directory)
    except OSError:
        msg = 'Error: No permission or directory not found'
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
                cam2 = true
                Cameras.append('Camera2')
        frame += 1

    for cameraname in Cameras:
        if frame < 10:
            msg = 'Error: ' + cameraname + ': Cannot create video with only ' + str(frame) + ' frames.  Minimum required is 10'
            return msg

        print(cameraname + ': now making ' + str(frame) + ' frames into a video')
        if 250 < frame:
            print("This can take a while...")

        timestamp = time.strftime('%a-%H-%M', time.localtime())

        fn = ' "' + directory + '_' + cameraname + '_' + timestamp + '.mp4"'

        if win:
            cmd = 'ffmpeg' + ffmpegquiet + ' -r 10 -i "' + directory + '\\' + cameraname + '_%08d.jpeg" -vcodec libx264 -y ' + fn + debug
        else:
            cmd = 'ffmpeg' + ffmpegquiet + ' -r 10 -i "' + directory + '/' + cameraname + '_%08d.jpeg" -vcodec libx264 -y ' + fn + debug

        while True:
            if ffmpeg_available():
                try:
                    subprocess.call(cmd, shell=True)
                except:
                    msg = ('!!!!!!!!!!!  There was a problem creating the video for '+cameraname+' !!!!!!!!!!!!!!!')
                break
            time.sleep(10)  # wait a while before trying again

        print('Video processing complete for ' + cameraname)
        print('Video is in file ' + fn)
        msg = 'Video(s) successfully created'
    return msg


def ffmpeg_available():
    count = 0
    max_count = maxffmpeg
    for p in psutil.process_iter():
        if 'ffmpeg' in p.name():  # Check to see if it's running
            count += 1
        if count >= max_count:
            print('Waiting on ffmpeg to become available')
            return False

    return True


def createHttpListener():
    global listener
    listener = ThreadingHTTPServer((host, port), MyHandler)
    daemon_threads = True
    listener.serve_forever()


def closeHttpListener():
    global listener
    print('!!!!! Stop requested by http listener !!!!!')
    listener.shutdown()
    listener.server_close()
    print('Shutdown')
    sys.exit(0)


def getOperatingSystem():
    #  What OS are we using?
    global win
    operatingsystem = platform.system()
    if (operatingsystem == 'Windows'):
        win = True
    else:
        win = False


def getThisInstance(thisinstancepid):
    thisrunning = 'Could not find a process running with pid = ' + str(thisinstancepid)
    for p in psutil.process_iter():
        if (('python3' in p.name() or 'pythonw' in p.name()) and thisinstancepid == p.pid):
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
        if ((
                'python3' in p.name() or 'pythonw' in p.name()) and not thisinstance in p.cmdline() and '-duet' in p.cmdline()):  # Check all other python3 instances
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
                running = running + ('Process id:  ' + pid + '<br>' + cmdlinestr + '<br>')
            else:  # Formal for html link
                running = running + ('Process id:  ' + pid + '<br>'
                                                             '<a href=\"http://' + refererip + ':' + str(
                        port) + '\?command=status" target="_blank">' + cmdlinestr + '</a>'
                                                                                    '<br>')

    if (running != ''):
        running = ('<pre>' + running + '<br>'
                                       '</pre>')
    else:
        running = 'None'
    return running, pidlist;


def shut_down():
    time.sleep(1)  # give pending actions a chance to finish
    try:  # this should close this thread
        httpthread.join(10)
    except:
        pass
    os.kill(thisinstancepid, 9)


# Allows process running in background or foreground to be gracefully
# shutdown with SIGINT (kill -2 <pid> also handles KeyboardInterupt
import signal


def quit_gracefully(*args):
    print('!!!!!! Stopped by SIGINT or CTL+C  !!!!!!')
    shut_down()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, quit_gracefully)

"""
Main Program
"""
if __name__ == "__main__":

    global thisinstance, thisinstancepid, topdir
    getOperatingSystem()  # some commands are os specific
    thisinstance = os.path.basename(__file__)

    if not win:
        thisinstance = './' + thisinstance
    _ = checkInstances(thisinstance, 'single')  # There can only be one instance running
    thisinstancepid = os.getpid()
    init()

    if (topdir == ''):
        topdir = os.path.dirname(os.path.realpath(__file__))
    #get the slashes going the right way
    if win:
        topdir = topdir.replace('/','\\')
    else:
        topdir = topdir.replace('\\','/')
    topdir = os.path.normpath(topdir) # Normalise the dir - no trailing slash



    if (port != 0):
        try:
            sock = socket.socket()
            if sock.connect_ex((host, port)) == 0:
                print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                print('Sorry, port ' + str(port) + ' is already in use.')
                print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                sys.exit(2)
            # Does this need to be threaded with ThreadingHTTPServer ?
            # or just call createHttpListener()
            httpthread = threading.Thread(target=createHttpListener, args=()).start()
            # httpthread.start()
            print('***** Started http listener *****')

        except KeyboardInterrupt:
            pass  # This is handled as SIGINT
    else:
        print('No port number was provided or port is already in use')
        sys.exit(2)
