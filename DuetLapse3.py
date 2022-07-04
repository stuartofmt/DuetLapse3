#!python3

"""
#Python program to take Time Lapse photographs during a print on
#   a Duet based 3D printer and convert them into a video.
#
# From the original work of Danal Estes
# Copyright (C) 2020 Danal Estes all rights reserved.
# Released under The MIT License. Full text available via https://opensource.org/licenses/MIT
#
# Rewritten and extended by Stuart Strolin
# Copyright (C) 2020 Stuart Strolin all rights reserved.
# Released under The MIT License. Full text available via https://opensource.org/licenses/MIT
#
#
# Developed on Raspberry Pi and WSL with Debian Buster and on Windows 10/11. SHOULD work on most other linux distributions.
# For USB or Pi camera, The Camera MUST be physically attached to the Pi computer.
# For Webcam, the camera must be network reachable and via a defined URL for a still image.
# For Stream   the camera must be network reachable and via a defined URL
# The Duet printer must be RepRap firmware V3 and must be network reachable.
#
#
"""

from operator import truediv  #  To support proper division
import subprocess
import sys
import platform
import argparse
import time
import requests
import json
import os
import glob
import socket
import threading
import psutil
import shutil
import pathlib
import signal
import logging

duetLapse3Version = '4.0.0'
#  Added support for M117 control using DuetLapse3. prefix
#  Added -restart to cause a restart at end of print
#  Changed - extratime so as not to require tpad support in ffmpeg
#  Added the ability to execute an arbitrary program by sending M117 gcode with execkey prefix 
#  Goes into a retry loop if no printer connection at start or during execution
#  Can now run continuously.
#  Efficiency improvements.
#  Added -minvideo to set minimum video length (seconds default 5)
#  Changed default -poll to minimum of 12 seconds.
#  Changed default -seconds to minimum of 12 seconds.
#  Supressed a lot of output unless -verbose is used
#  Changed logfile naming convention.  Initially the logfile is created with a timestamp. When the print starts the logfile is renamed to reflect the name of the print job



def setstartvalues():
    global zo1, zo2, printState, captureLoopState, gcodeLoopState,  duetStatus, timePriorPhoto1, timePriorPhoto2, frame1, frame2

    printState = 'Not Capturing'
    stopCaptureLoop()
    duetStatus = 'Not yet determined'

    # initialize timers
    timePriorPhoto1 = time.time()
    timePriorPhoto2 = time.time()

    # reset the frame counters and layer (zo) state
    frame1 = 0 # Camera1
    zo1 = -1  
    frame2 = 0 # Camera2
    zo2 = -1  

###########################
# General purpose methods begin here
###########################

def returncode(code):  # Defined here - used by calling programs
    codes = { 0 : 'Not Used',
              1 : 'Not Used',
              2 : 'Invalid options combination',
              3 : 'Missing software dependency',
              4 : 'No response from Printer',
              5 : 'Incorrect Printer version',
              6 : 'Process is already running',
              7 : 'HTTP server terminated',
              8 : 'Port already in use'
            }
    if code in codes:
        text = codes[code]
    else:
        text = str(code) + ' is an unidentified Code'
    return text


def whitelist(parser):
    # Environment
    parser.add_argument('-duet', type=str, nargs=1, default=['localhost'],
                        help='Name of duet or ip address. Default = localhost')
    parser.add_argument('-poll', type=float, nargs=1, default=[12])
    parser.add_argument('-basedir', type=str, nargs=1, default=[''], help='default = This program directory')
    parser.add_argument('-instances', type=str, nargs=1, choices=['single', 'oneip', 'many'], default=['single'],
                        help='Default = single')
    parser.add_argument('-logtype', type=str, nargs=1, choices=['console', 'file', 'both'], default=['both'],
                        help='Deprecated.  Use -nolog')
    parser.add_argument('-nolog', action='store_true', help='Do not use log file')
    parser.add_argument('-verbose', action='store_true', help='Detailed output')
    parser.add_argument('-host', type=str, nargs=1, default=['0.0.0.0'],
                        help='The ip address this service listens on. Default = 0.0.0.0')
    parser.add_argument('-port', type=int, nargs=1, default=[0],
                        help='Specify the port on which the server listens. Default = 0')
    parser.add_argument('-keeplogs', action='store_true', help='Does not delete logs.')
    parser.add_argument('-novideo', action='store_true', help='Does not create a video.')
    parser.add_argument('-deletepics', action='store_true', help='Deletes images on Terminate')
    parser.add_argument('-maxffmpeg', type=int, nargs=1, default=[2],
                        help='Max instances of ffmpeg during video creation. Default = 2')
    parser.add_argument('-keepfiles', action='store_true', help='Dont delete files on startup or shutdown')
    # Execution
    parser.add_argument('-dontwait', action='store_true', help='Capture images immediately.')
    parser.add_argument('-seconds', type=float, nargs=1, default=[0])
    parser.add_argument('-detect', type=str, nargs=1, choices=['layer', 'pause', 'none'], default=['layer'],
                        help='Trigger for capturing images. Default = layer')
    parser.add_argument('-pause', type=str, nargs=1, choices=['yes', 'no'], default=['no'],
                        help='Park head before image capture.  Default = no')
    parser.add_argument('-movehead', type=float, nargs=2, default=[0.0, 0.0],
                        help='Where to park head on pause, Default = 0,0')
    parser.add_argument('-rest', type=float, nargs=1, default=[1],
                        help='Delay before image capture after a pause.  Default = 1')
    parser.add_argument('-standby', action='store_true', help='Wait for command to start.')
    parser.add_argument('-restart', action='store_true', help='Will restart when print finishes')
    # Camera
    parser.add_argument('-camera1', type=str, nargs=1, choices=['usb', 'pi', 'web', 'stream', 'other'], default=['usb'],
                        help='Mandatory Camera. Default = usb')
    parser.add_argument('-weburl1', type=str, nargs=1, default=[''], help='Url for Camera1 if web or stream')
    parser.add_argument('-camera2', type=str, nargs=1, choices=['usb', 'pi', 'web', 'stream', 'other'], default=[''],
                        help='Optional second camera. No Default')
    parser.add_argument('-weburl2', type=str, nargs=1, default=[''], help='Url for Camera2 if web or stream')
    # Video
    parser.add_argument('-extratime', type=float, nargs=1, default=[0], help='Time to repeat last image, Default = 0')
    parser.add_argument('-minvideo', type=float, nargs=1, default=[5], help='Minimum video length, Default = 5')
    # Overrides
    parser.add_argument('-camparam1', type=str, nargs=1, default=[''],
                        help='Camera1 Capture overrides. Use -camparam1="parameters"')
    parser.add_argument('-camparam2', type=str, nargs='*', default=[''],
                        help='Camera2 Capture overrides. Use -camparam2="parameters"')
    parser.add_argument('-vidparam1', type=str, nargs=1, default=[''],
                        help='Camera1 Video overrides. Use -vidparam1="parameters"')
    parser.add_argument('-vidparam2', type=str, nargs=1, default=[''],
                        help='Camera2 Video overrides. Use -vidparam2="parameters"')
    parser.add_argument('-fps', type=int, nargs=1, default=[10], help='Frames-per-second for video. Default = 10')
    parser.add_argument('-hidebuttons', action='store_true', help='Hides buttons not logically available.')
    #Special Functions
    parser.add_argument('-execkey', type=str, nargs=1, default=[''],
                        help='string to identify executable command')
    return parser

###  Main routines for calling subprocesses


def runsubprocess(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True)

        if str(result.stderr) != '':
            logger.info('Command Failure: ' + str(cmd))
            logger.debug(str(result.stderr))
            return False
        else:
            logger.debug('Command Success : ' + str(cmd))
            if result.stdout != '':
                logger.debug(str(result.stdout))
            return True
    except (subprocess.CalledProcessError, OSError) as e:
        logger.info('Command Exception: ' + str(cmd))
        logger.info(str(e))
        return False




def init():
    global inputs
    parser = argparse.ArgumentParser(
            description='Create time lapse video for Duet3D based printer. V' + duetLapse3Version, allow_abbrev=False)
    parser = whitelist(parser)
    args = vars(parser.parse_args())
    inputs = {}

    global duet, basedir, poll, pollcheck, instances, logtype, nolog, verbose, host, port
    global keeplogs, novideo, deletepics, maxffmpeg, keepfiles
    # Derived  globals
    global duetname, debug, ffmpegquiet, httpListener
    
    # Environment
    inputs.update({'# Environment':''})
    
    duet = args['duet'][0]
    inputs.update({'duet': str(duet)})

    basedir = args['basedir'][0]
    inputs.update({'basedir': str(basedir)})
    
    poll = args['poll'][0]
    if poll < 12:
        poll = 12
    inputs.update({'poll': str(poll)})
    pollcheck = int(poll/4) #  Check quicker than poll interval
    
    instances = args['instances'][0]
    inputs.update({'instances': str(instances)})
    
    logtype = args['logtype'][0]
    inputs.update({'logtype': str(logtype)})
    
    nolog = args['nolog']
    # Deprecated logtype
    if ('console' in logtype):
            nolog = True
    inputs.update({'nolog': str(nolog)})
    
    verbose = args['verbose']
    inputs.update({'verbose': str(verbose)})

    host = args['host'][0]
    inputs.update({'host': str(host)})

    port = args['port'][0]
    inputs.update({'port': str(port)})

    keeplogs = args['keeplogs']
    inputs.update({'keeplogs': str(keeplogs)})

    novideo = args['novideo']
    inputs.update({'novideo': str(novideo)})

    deletepics = args['deletepics']
    inputs.update({'deletepics': str(deletepics)})

    maxffmpeg = args['maxffmpeg'][0]
    inputs.update({'maxffmpeg': str(maxffmpeg)})

    keepfiles = args['keepfiles']
    inputs.update({'keepfiles': str(keepfiles)})

    # Execution
    global dontwait, seconds, detect, pause, movehead, rest, standby, restart
    inputs.update({'# Execution' : ''})

    dontwait = args['dontwait']
    inputs.update({'dontwait': str(dontwait)})

    seconds = args['seconds'][0]
    inputs.update({'seconds': str(seconds)})
    if seconds != 0 and seconds < 12: # If used set to minimum of 12 seconds
        seconds = 12

    detect = args['detect'][0]
    inputs.update({'detect': str(detect)})

    pause = args['pause'][0]
    inputs.update({'pause': str(pause)})

    movehead = args['movehead']
    inputs.update({'movehead': str(movehead)})

    rest = args['rest'][0]
    if rest < 0:
        rest = 0
    inputs.update({'rest': str(rest)})

    standby = args['standby']
    inputs.update({'standby': str(standby)})

    restart = args['restart']
    inputs.update({'restart': str(restart)})

    # Camera
    global camera1, camera2, weburl1, weburl2
    inputs.update({'# Camera': ''})

    camera1 = args['camera1'][0]
    inputs.update({' camera1': str( camera1)})

    camera2 = args['camera2'][0]
    inputs.update({'camera2': str(camera2)})

    weburl1 = args['weburl1'][0]
    inputs.update({'weburl1': str(weburl1)})

    weburl2 = args['weburl2'][0]
    inputs.update({'weburl2': str(weburl2)})

    # Video
    global extratime, fps, minvideo
    inputs.update({'# Video': ''})

    extratime = args['extratime'][0]
    inputs.update({'extratime': str(extratime)})

    fps = str(args['fps'][0])
    inputs.update({'fps': str(fps)})

    minvideo = args['minvideo'][0]
    inputs.update({'minvideo': str(minvideo)})

    # Overrides
    global camparam1, camparam2, vidparam1, vidparam2
    inputs.update({'# Overrides': ''})

    camparam1 = args['camparam1'][0]
    inputs.update({'camparam1': str(camparam1)})

    camparam2 = args['camparam2'][0]
    inputs.update({'camparam2': str(camparam2)})

    vidparam1 = args['vidparam1'][0]
    inputs.update({'vidparam1': str(vidparam1)})

    vidparam2 = args['vidparam2'][0]
    inputs.update({'vidparam2': str(vidparam2)})

    # UI
    global hidebuttons
    inputs.update({'# UI': ''})

    hidebuttons = args['hidebuttons']
    inputs.update({'hidebuttons': str(hidebuttons)})

    #  Special Functions
    global execkey

    inputs.update({'# Special Functions': ''})
    execkey = args['execkey'][0]
    inputs.update({'execkey': str(execkey)})


    ##### Create a custom logger #####
    global logger
    logger = logging.getLogger(__name__)

    setdebug(verbose)

    # Create handler for console output - file output handler is created later if needed
    if nolog is False:  # Create log file as the default
        c_handler = logging.StreamHandler()
        c_format = logging.Formatter(duet + ' %(threadName)s - %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)


    ########################################################################
    # Check to see if this instance is allowed to run
    #########################################################################
    #  What OS are we using?
    global win
    operatingsystem = platform.system()
    if operatingsystem == 'Windows':
        win = True
    else:
        win = False

    thisinstance = os.path.basename(__file__)
    if not win:
        thisinstance = './' + thisinstance
    checkInstances(thisinstance, instances)

    ####################################################
    # Setup for logging and filenames
    ####################################################

    # pid is used to create unique filenames
    global pid
    pid = str(os.getpid())

    # set debug value
    setdebug(verbose)

    # duetname used for filenames and directories
    duetname = duet.replace('.', '-')

    # set directories for files
    global topdir, baseworkingdir, workingdir, loggingset, logname
    loggingset = False
    if basedir == '':
        basedir = os.path.dirname(os.path.realpath(__file__))
    
    basedir = basedir.replace('\\','/') # Could be user error
    basedir = os.path.normpath(basedir) # Normalise the dir - no trailing slash
 
    topdir = os.path.normpath(basedir + '/' + socket.getfqdn() + '/' + duetname)
    baseworkingdir = os.path.normpath(topdir + '/' + pid)  # may be changed later
    if not os.path.isdir(topdir): # If not already exists - create
        try:
            os.makedirs(topdir)  # Use recursive form to create intermediate directories
        except OSError as e:
            logger.info('Could not create dir ' + str(e))

    #  Clean up older files
    cleanupFiles('startup')

    setuplogfile()

    ####################################################
    # Display the options being used
    ####################################################

    listoptions()
    
    ###############################################
    # derived parameters
    ##############################################

    poll_seconds()

    #  Port number must be given for httpListener to be active
    if port != 0:
        httpListener = True

    ########################################################################
    # Inform regarding valid and invalid combinations
    #########################################################################

    # Invalid Combinations that will abort program

    if (camera1 != 'other') and (camparam1 != ''):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + camera1 + ' cannot be used with camparam1')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if (camera2 != 'other') and (camparam2 != ''):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + camera2 + ' cannot be used with camparam2')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if (camera1 == 'usb' or camera1 == 'pi') and win:  # These do not work on WIN OS
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + camera1 + ' cannot be on Windows OS')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if (camera2 == 'usb' or camera2 == 'pi') and win:
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + camera2 + ' cannot be on Windows OS')
        logger.info('************************************************************************************\n')
        sys.exit(2)


    if (not movehead == [0.0, 0.0]) and (not 'yes' in pause) and (not 'pause' in detect):
        logger.info('************************************************************************************')
        logger.info(
                'Invalid Combination: "-movehead {0:1.2f} {1:1.2f}" requires either "-pause yes" or "-detect pause".'.format(
                        movehead[0], movehead[1]))
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if ('yes' in pause) and ('pause' in detect):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: "-pause yes" causes this program to pause printer when')
        logger.info('other events are detected, and "-detect pause" requires the gcode on the printer')
        logger.info('contain its own pauses.  These cannot be used together.')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    return # init()

def issue_warnings():
    # Information and Warnings
    global dontwait
    if seconds <= 0 and 'none' in detect:
        logger.info('************************************************************************************')
        logger.info('Warning:: -seconds ' + str(seconds) + ' and -detect ' + detect + ' nothing will be captured.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************\n')

    if seconds > 0 and (not 'none' in detect):
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds ' + str(seconds) + ' and -detect ' + detect + ' will trigger on both.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************\n')

    if seconds > 0  and 'none' in detect:
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds ' + str(seconds) + ' and -detect ' + detect)
        logger.info('This combination implies -dontwait and will be set automatically')
        logger.info('************************************************************************************\n')
        dontwait = True

    if 'pause' in detect:
        logger.info('************************************************************************************')
        logger.info('* Note "-detect pause" means that the G-Code on the printer already contains pauses,')
        logger.info('* and that this program will detect them, take a photo, and issue a resume.')
        logger.info('* Head position during those pauses is can be controlled by the pause.g macro ')
        logger.info('* on the duet, or by specifying "-movehead nnn nnn".')
        logger.info('*')
        logger.info('* If instead, it is desired that this program force the printer to pause with no')
        logger.info('* pauses in the gcode, specify either:')
        logger.info('* "-pause yes -detect layer" or "-pause yes -seconds nnn".')
        logger.info('************************************************************************************\n')

    if 'yes' in pause:
        logger.info('************************************************************************************')
        logger.info('* Note "-pause yes" means this program will pause the printer when the -detect and / or ')
        logger.info('* -seconds flags trigger.')
        logger.info('*')
        logger.info('* If instead, it is desired that this program detect pauses that are already in')
        logger.info('* in the gcode, specify:')
        logger.info('* "-detect pause"')
        logger.info('************************************************************************************\n')

    if novideo and deletepics:
        logger.info('************************************************************************************')
        logger.info('Warning: The combination of -novideo and -deletepics will not create any output')
        logger.info('************************************************************************************\n')

    return # issue_warnings()


def listoptions():
    for var in inputs: # update the values
        if var in globals():
            val = globals()[var]
            newvalue = {var:val}
            inputs.update(newvalue)
    # output the options
    logger.info("################### Options at start of this print job  #####################")
    col_width = max(len(row) for row in inputs) + 2  # width of first column
    for label, value in inputs.items():
       logger.info("".join(label.ljust(col_width) + str(value)))
    logger.info('-----------------------------------------------------------------------\n\n')

def setuplogfile():
    global loggingset, logname, logfilename
    #  Set up log file now that we have a name for it
    logfilename = topdir + '/' + pid + '_' + time.strftime('%y-%m-%dT%H:%M:%S', time.localtime()) + '.log'
    logfilename = logfilename.replace(':', u'\u02f8')  # cannot use regular colon in windows file names
    logfilename = os.path.normpath(logfilename)

    if nolog is False:
        filehandler = None
        for handler in logger.handlers:
            if handler.__class__.__name__ == "FileHandler":
                filehandler = handler
                break # There is only ever one
        
        if filehandler != None:  #  Get rid of it
            filehandler.flush()
            filehandler.close()
            logger.removeHandler(filehandler)
            time.sleep(3) # Wait for any messages to propogate

        f_handler = logging.FileHandler(logfilename, mode='w', encoding='utf-8')
        f_format = logging.Formatter('%(asctime)s - %(threadName)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)
        logger.debug('Created logfile at ' + logfilename)

    loggingset = True


def renamelogfile(): # called from createworkingdir 
    global logname, logfilename

    if nolog is False:
        filehandler = None
        for handler in logger.handlers:
            if handler.__class__.__name__ == "FileHandler":
                filehandler = handler
                break # There is only ever one
        
        if filehandler != None:  #  Get rid of it
            filehandler.flush()
            filehandler.close()
            logger.removeHandler(filehandler)
        
        newlogfilename = os.path.normpath(workingdir + '.log')
        newlogfilename = newlogfilename.replace(':', u'\u02f8')  # cannot use regular colon in windows file names

        #  shutil.move(logfilename, newlogfilename)
        try:
            shutil.move(logfilename, newlogfilename)
        except shutil.Error as e:
            logger.info('Error on move ' + str(e))

        f_handler = logging.FileHandler(newlogfilename, mode='a', encoding='utf-8')
        f_format = logging.Formatter('%(asctime)s - %(threadName)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)
        logfilename = newlogfilename
   
def setdebug(val): # How much output
    global debug, ffmpegquiet, logger
    try:
        if val:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
    except NameError:
        pass

    if val:
        debug = ''
        ffmpegquiet = ' -loglevel quiet'
    else:
        ffmpegquiet = ' -loglevel quiet'
        if not win:
            debug = ' > /dev/null 2>&1'
        else:
            debug = ' > nul 2>&1'


def poll_seconds():
    global seconds, poll, pollcheck
        # Polling interval needs to be in integer multiple of seconds
    if seconds != 0:
        if seconds <= poll:
            poll = seconds
        elif seconds % poll == 0: # poll is an integer divisor - no need to change
            pass
        else:
            poll = seconds / (int(seconds/poll)+1)

    pollcheck = int(poll/4) #  Check quicker than poll interval


    def checkDependencies(id):
        if id == 1:
            camera = camera1
            camparam  = camparam1
        else:
            camera = camera2
            camparam  = camparam2

        if 'usb' in camera:
            if runsubprocess('fswebcam --version') is False:
                logger.info("Module 'fswebcam' is required. ")
                if not win:
                    logger.info("Obtain via 'sudo apt install fswebcam'")
                sys.exit(3)

        if 'pi' in camera:
            logger.info('NOTE: THE -camera pi OPTION IS DEPRECATED')

        if 'pi' in camera or 'raspistill' in camparam:
            if runsubprocess('raspistill --help') is False:
                logger.info("Module 'raspistill' is required BUT is only available for Pi version Buster or lower. ")
                if not win:
                    logger.info("Obtain via 'sudo apt install raspistill'")
                sys.exit(3)

        if 'web' in camera or 'wget' in camparam:
            if runsubprocess('wget --version') is False:
                logger.info("Module 'wget' is required. ")
                if not win:
                    logger.info("Obtain via 'sudo apt install wget'")
                sys.exit(3)

        if runsubprocess('ffmpeg -version') is False:
            logger.info("Module 'ffmpeg' is required. ")
            if not win:
                logger.info("Obtain via 'sudo apt install ffmpeg'")
            sys.exit(3)

    checkDependencies(1)
    if camera2 != '':
        checkDependencies(2)

    """
    ########################################################################
    # Make sure we can connect to the printer
    #########################################################################
    """

def checkforPrinter():
    global apiModel, printerVersion, firstConnect, connectionState 
    # Get the initial connection to the printer.    
    while apiModel == '' and terminateState != 1: #  Keep trying until connected or terminating
        Model, printerVersion = getDuetVersion('') # Wait for connection
        if Model == '': #  Could not connect
            logger.info('#########################################################')
            logger.info('The printer at ' + duet + ' is not responding')
            logger.info('Check the ip address or logical printer name is correct\n')
            logger.info('Is the printer turned on?')
            logger.info('Duet software must support rr_model or /machine/status')
            logger.info('########################################################\n')
            connectionState = False
            startcheckforConnection()
            continue

        try:
            firstConnect
        except NameError:
            firstConnect = False
            majorVersion = int(printerVersion[0])

            if majorVersion >= 3:
                connectionState = True
                apiModel = Model # We have a good connection
                logger.info('###############################################################')
                logger.info('Connected to printer at ' + duet)
                logger.info('Using Duet version ' + printerVersion)
                logger.info('Using  API interface ' + apiModel)
                logger.info('###############################################################\n')
                sendDuetGcode(apiModel,'M117 ""') #  Clear the display message
                return
            else:
                logger.info('###############################################################')
                logger.info('The printer at ' + duet + ' needs to be at version 3 or above')
                logger.info('The version on this printer is ' + printerVersion)
                logger.info('###############################################################\n')
                sys.exit(5)
    

def checkforConnection():
    global apiModel, connectionState, checkforconnectionState
    checkforconnectionState = 1
    connectionState = False
    elapsed = 0
    shortcheck = 5
    quickcheck = 20 # check every shortcheck for up to this number of seconds
    longcheck = 3*60 # longer check interval
    checking = True
    logger.info('----------------  Waiting for printer to reconnect -----------------')
    while checking and terminateState != 1:
        if elapsed <= quickcheck: # Check every shortcheck
            model = getDuetVersion(apiModel)[0]
            if model == '': # Still not connected
                #terminate()
                logger.debug('Retrying connection every ' + str(shortcheck) + ' seconds')
                time.sleep(shortcheck)
                elapsed = elapsed + shortcheck
            else:
                checking = False
        else:  #  Check every longcheck
            model = getDuetVersion(apiModel)[0]
            if model == '': # Still not connected
                logger.debug('Retrying connection every ' + str(longcheck) + ' seconds')
                time.sleep(longcheck)
            else:
                checking = False

    apiModel = model
    connectionState = True
    sendDuetGcode(apiModel,'M117 ""') #  Clear the display message
    logger.info('-----------------------  Reconnected to printer ----------------------')    
    startnextAction('reconnected')
    checkforconnectionState = -1


#####################################################
##  Utility Functions
#####################################################

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
        msg = 'Error: There was a problem creating the zip file'
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
        return
    frame = 0
    Cameras = []
    C1 = C2 = False
    for name in list:
        if 'Camera1' in name and C1 is False:
            Cameras.append('Camera1')
            C1 = True
        if 'camera2' in name and C2 is False:
            Cameras.append('Camera2')
            C2 = True
        if C1 is True and C2 is True:
            break
    
    if C1 is False and C2 is False:
        logger.info('Cannot create video.  Could not determine which camera was used')
        return

    for cameraname in Cameras:
        if cameraname == 'Camera1':
            frame = frame1
        elif cameraname == 'Camera2':
            frame = frame2

        if frame/int(fps) < minvideo:
            msg = 'Error: ' + cameraname + ': Cannot create video of less than ' + str(minvideo) + ' seconds.'
            logger.info(msg)
            return

        logger.info(cameraname + ': now making ' + str(frame) + ' frames into a video')
        if 250 < frame:
            logger.info("This can take a while...")

        timestamp = time.strftime('%a-%H-%M', time.localtime())

        fn = directory + '_' + cameraname + '_' + timestamp + '.mp4'
        fn = os.path.normpath(fn)

        if printState == 'Completed':
            threadsin = ''  #  Dont limit ffmpeg
            threadsout = ''  #  Dont limit ffmpeg
        else:
            threadsin = ' -threads 1 '
            threadsout = ' -threads 2 '

        location = os.path.normpath(directory + '/' + cameraname + '_%08d.jpeg')
        cmd = 'ffmpeg' + threadsin + ffmpegquiet + ' -r ' + fps + ' -i ' + location + ' -vcodec libx264 -y ' + threadsout + fn + debug

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
    return


def ffmpeg_available():
    count = 0
    max_count = maxffmpeg  # Default is 2
    for p in psutil.process_iter():
        if 'ffmpeg' in p.name():  # Check to see if it's running
            count += 1
        if count >= max_count:
            logger.debug('Waiting for ffmpeg to become available')
            return False
    logger.debug('There are ' + str(count) + ' instances of ffmpeg running')
    return True

def getRunningInstancePids():
    pidlist = []
    for p in psutil.process_iter():
        if ((
                'python3' in p.name() or 'pythonw' in p.name()) and '-duet' in p.cmdline()):  # Check all other python3 instances
            pidlist.append(str(p.pid))
    return pidlist


def getPidDirs():
    dirlist = []
    if os.path.isdir(topdir):
        for item in os.listdir(topdir):
            if os.path.isdir(os.path.join(topdir, item)):
                dirlist.append(item)

    return dirlist


def createWorkingDir(baseworkingdir):
    global workingdir_exists, workingdir, workingdirs
    jobname = getDuet('Jobname from createworkingdir', Jobname)
    if connectionState is False:
        return
    if jobname != '':
        _, jobname = os.path.split(jobname)  # get the filename less any path
        jobname = jobname.replace(' ', '_')  # prevents quoting of file names
        jobname = jobname.replace('.gcode', '')  # get rid of the extension
        jobname = jobname.replace(':', u'\u02f8')  # replace any colons with raised colon
        workingdir = baseworkingdir + '_' + jobname
    else:
        workingdir = baseworkingdir

    olddir = ''
    for dir in workingdirs:
        logger.info(dir)
        if workingdir in dir: # partial match
            olddir = dir # get the last.  They are in order in the list
    if  olddir != '':
        if '--' in olddir:
            dirparts = olddir.split('--')
            increment = int(dirparts[1])
            increment += 1
            workingdir = dirparts[0] + '--' + str(increment)
            logger.info(workingdir)
        else:
            workingdir = workingdir + '--1'
    
    workingdir = os.path.normpath(workingdir)

    try:
        os.mkdir(workingdir)
        logger.debug('Created working directory ' + workingdir)
        workingdirs.append(workingdir)
        workingdir_exists = True
        renamelogfile()  # change the logfle to match the working dir
    except OSError as e:
        logger.info('Could not create working directory ' + str(e))

    return workingdir


def cleanupFiles(phase):
    global workingdir_exists, keepfiles, workingdirs
    logger.debug('Cleaning up files for phase:  ' + phase)
    pidlist = getRunningInstancePids()
    dirlist = getPidDirs()

    # Make and clean up directorys.

    if phase == 'startup':
        if keepfiles: return
        for dirs in dirlist:
            split_dirs = dirs.split("-", 1)
            dirpid = split_dirs[0]
            if dirpid not in pidlist:
                olddir = topdir + '/' + dirs
                try:
                    shutil.rmtree(olddir)
                except shutil.Error as e:
                    logger.info('Error on remove dir ' + str(e))
                
        if (not keeplogs) and (len(pidlist) == 1):  # only delete logs if no other processes running
            # Note position of last " so that shell expands *.log portion
            pattern = r'"' + topdir + '/*.log"'
            for oldlog in glob.iglob(pattern, recursive=True):
                try:
                    os.remove(oldlog)
                except OSError as e:
                    logger.info('Error on remove log ' + str(e))

    elif (phase == 'standby') or (phase == 'restart'):  # deleted images directory will be recreated on first capture
        if workingdir_exists:  # Will not be the case after restart
            olddir = workingdir
            try:
                shutil.rmtree(olddir)
                logger.debug('Deleted workingdir' + workingdir)
                workingdirs.remove(workingdir)
                workingdir_exists = False
            except shutil.Error as e:
                logger.info('Error on remove dir ' + str(e))
                workingdir_exists = True

    elif phase == 'terminate':
        if keepfiles: return

        if deletepics:
            for olddir in workingdirs:
                try:
                    shutil.rmtree(olddir)
                    logger.debug('Deleted workingdir' + workingdir)
                    workingdir_exists = False
                except shutil.Error as e:
                    logger.info('Error on remove dir ' + str(e))
            # Assume sucess even if error from above
            workingdirs = []
            workingdir_exists = False

    return  # cleanupFiles

def startNow():
    #  Determine if program should logically start now
    global action
    if standby:
        action = 'standby'
        return False
    elif (seconds > 0) and (dontwait or 'none' in detect):
        action = 'start'
        return True
    else:
        action = 'start'
        return False


def getThisInstance(thisinstancepid):
    global pid
    thisrunning = 'Could not find a process running with pid = ' + str(thisinstancepid)
    for p in psutil.process_iter():
        if ('python3' in p.name() or 'pythonw' in p.name()) and thisinstancepid == p.pid:
            cmdline = str(p.cmdline())
            cmdline = cmdline.replace('[', '')
            cmdline = cmdline.replace(']', '')
            cmdline = cmdline.replace(',', '')
            cmdline = cmdline.replace("'", '')
            cmdline = cmdline.replace('  ', ' ')
            pid = str(p.pid)
            thisrunning = cmdline

    return thisrunning


#####################################################
##  Processing Functions
#####################################################

def checkInstances(thisinstance, instances):
    proccount = 0
    allowed = 0

    for p in psutil.process_iter():

        if ('python3' in p.name() or 'pythonw' in p.name()) and thisinstance in p.cmdline():
            proccount += 1
            if 'single' in instances:
                allowed += 1
            if 'oneip' in instances:
                if duet in p.cmdline():
                    allowed += 1

    if allowed > 1:
        logger.info('#############################')
        logger.info('Process is already running... shutting down.')
        logger.info('#############################\n')
        sys.exit(6)

    return proccount


def checkForPause(layer):
    # Checks to see if we should pause and reposition heads.
    # Do not pause until printing has completed layer 1.
    # This solves potential issues with the placement of pause commands in the print stream
    # Before or After layer change
    # As well as timed during print start-up

    if (layer < 2):  # Do not try to pause
        return
    duetStatus, _ = getDuet('Status from Check for Pause', Status)
    if connectionState is False:
        return
    loopmax = 10  # sec
    loopinterval = .5  # sec
    loopcount = loopmax / loopinterval

    if pause == 'yes':  # DuetLapse is controlling when to pause
        logger.debug('Requesting pause via M25')
        sendDuetGcode(apiModel, 'M25')  # Ask for a pause
        loop = 0
        while True:
            time.sleep(loopinterval)  # wait and try again
            duetStatus, _ = getDuet('Status check for pause pause = yes', Status)
            if connectionState is False:
                return
            if duetStatus == 'paused':
                break
            else:
                loop += 1
            if loop == loopcount:  # limit the counter in case there is a problem
                logger.info('Timeout after ' + str(loopmax))
                logger.info('Target was: paused')
                logger.info('Actual was: ' + duetStatus)
                break

    if duetStatus == 'paused':
        if not movehead == [0.0, 0.0]:  # optional repositioning of head
            logger.debug('Moving print head to X{0:4.2f} Y{1:4.2f}'.format(movehead[0], movehead[1]))
            sendDuetGcode(apiModel, 'G1 X{0:4.2f} Y{1:4.2f}'.format(movehead[0], movehead[1]))
            loop = 0
            while True:
                time.sleep(loopinterval)  # wait and try again
                xpos, ypos, _ = getDuet('Position paused = yes', Position())
                if connectionState is False:
                    return
                if (abs(xpos - movehead[0]) < .05) and (
                        abs(ypos - movehead[1]) < .05):  # close enough for government work
                    break
                else:
                    loop += 1
                if loop == loopcount:  # limit the counter in case there is a problem
                    logger.info('Timeout after ' + str(loopmax) + 's')
                    logger.info('Target X,Y: ' + str(movehead[0]) + ',' + str(movehead[1]))
                    logger.info('Actual X,Y: ' + str(xpos) + ',' + str(ypos))
                    break
        time.sleep(rest)  # Wait to let camera feed catch up
    else:
        pass
    return


def unPause():
    if connectionState is False:
        return
    duetStatus, _ = getDuet('Status from unPause', Status)
    if connectionState is False: # Check after each getDuet
        return
    if duetStatus == 'paused':
        loopmax = 10 # sec
        loopinterval = .2 # sec  short so as to not miss start of next layer
        loopcount = loopmax / loopinterval
        logger.debug('Requesting un pause via M24')
        sendDuetGcode(apiModel, 'M24')  # Ask for an un pause
        loop = 0
        while True:
            time.sleep(loopinterval)  # wait a short time so as to not miss transition on short layer
            duetStatus, _ = getDuet('Status from loop unPause', Status)
            if connectionState is False:
                return
            if duetStatus in ['idle', 'processing']:
                break
            else:
                loop += 1
            if loop == loopcount:  # limit the counter in case there is a problem
                logger.info('Loop exceeded: Target was: unpause')
                break
    return


def onePhoto(cameraname, camera, weburl, camparam):
    global frame1, frame2, workingdir, camfile1, camfile2

    if not workingdir_exists:
        workingdir = createWorkingDir(baseworkingdir)  # created as late as possible - adds job fileName if available
        camfile1 = workingdir + '/Camera1_'
        camfile2 = workingdir + '/Camera2_'

    if cameraname == 'Camera1':
        frame1 = frame1 + 1
        s = str(frame1).zfill(8)
        fn = camfile1 + s + '.jpeg'
    else:
        frame2 = frame2 + 1
        s = str(frame2).zfill(8)
        fn = camfile2 + s + '.jpeg'
    
    fn = os.path.normpath(fn)

    if 'usb' in camera:
        cmd = 'fswebcam --quiet --no-banner ' + fn + debug

    if 'pi' in camera:
        cmd = 'raspistill -t 1 -w 1280 -h 720 -ex sports -mm matrix -n -o ' + fn + debug

    if 'stream' in camera:
        cmd = 'ffmpeg -threads 1' + ffmpegquiet + ' -y -i ' + weburl + ' -vframes 1 -threads 1' + fn + debug

    if 'web' in camera:
        cmd = 'wget --auth-no-challenge -nv -O ' + fn + ' "' + weburl + '" ' + debug

    if 'other' in camera:
        cmd = eval(camparam)

    global timePriorPhoto1, timePriorPhoto2

    if runsubprocess(cmd) is False:
        logger.info('!!!!!!!!!!!  There was a problem capturing an image !!!!!!!!!!!!!!!')
        # Decrement the frame counter because we did not capture anything
        if cameraname == 'Camera1':
            frame1 -= 1
            if frame1 < 0:
                frame1 = 0
            return
        else:
            frame2 -= 1
            if frame2 < 0:
                frame2 = 0
            return
    else:   #  Success
        if cameraname == 'Camera1':
            timePriorPhoto1 = time.time()
            return
        else:
            timePriorPhoto2 = time.time()
            return

def oneInterval(cameraname, camera, weburl, camparam):
    if connectionState is False:
        return
    global frame1, frame2
    global timePriorPhoto1, timePriorPhoto2

    # set the logical frame number
    # frame1 and frame 2 are incremented in onePhoto before image is captured
    if cameraname == 'Camera1':
        frame = frame1 + 1
    else:
        frame = frame2 + 1

    global zo1, zo2
    zn = getDuet('Layer from oneInterval', Layer)
    if connectionState is False:
        return
    if zn == -1:
        layer = 'None'
    else:
        layer = str(zn)

    if 'layer' in detect:
        if (not zn == zo1 and cameraname == 'Camera1') or (not zn == zo2 and cameraname == 'Camera2'):
            # Layer changed, take a picture.
            checkForPause(zn)
            logger.info('Layer - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after layer change')
            onePhoto(cameraname, camera, weburl, camparam)

    elif ('pause' in detect) and (duetStatus == 'paused'):
        checkForPause(zn)
        logger.info('Pause - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' at pause in print gcode')
        onePhoto(cameraname, camera, weburl, camparam)

    # update the layer counter
    if cameraname == 'Camera1':
        zo1 = zn
    else:
        zo2 = zn

        # Note that onePhoto() updates timePriorPhoto1 and timePriorPhoto2
    if cameraname == 'Camera1':
        elap = (time.time() - timePriorPhoto1)
    else:
        elap = (time.time() - timePriorPhoto2)

    logger.debug('elapsed: ' + str(elap))

    if (seconds > 0) and (seconds < elap) and (dontwait or 'none' in detect or zn >= 1):
        checkForPause(zn)
        logger.info('Time - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after ' + str(
                seconds) + ' seconds')
        onePhoto(cameraname, camera, weburl, camparam)

#############################################################################
##############  Duet API access Functions
#############################################################################

def getDuet(name, function): #  Helper function to call other specific getDuet(x) calls
    # Retries if there is a network problem
    # Relies on called functions to return 'disconnected' if they cannot get the requested info
    # Only handles functions without arguments
    # Changes connectionState to False if there is a persistent fault
    global connectionState
    disconnected = 0
    getstatus = False
    while getstatus is False:
        #  The working code gets executed here
        logger.debug('Calling function ' + name + ' with ' + apiModel)
        result = function()  # The passed in function

        if isinstance(result, tuple): # More than one return variable
            connect = str(result[0])
            responseitems = len(result)
        else:
            connect = str(result)
            responseitems = 1

        if connect == 'disconnected' and terminateState != 1:
            connectionState = False # Stop additional calls
            disconnected += 1
            logger.debug('Number of disconnects ' + str(disconnected))
            time.sleep(1)
            if disconnected > 2:  #  Persistent error state
                #  connectionState = False
                startnextAction('waitforconnection')
                response = [] # start with a list
                for i in range(responseitems):
                    response.append(None) # Dummy return
                return tuple(response)  # turn the response into a tuple 
                #checkforConnection() #  Wait for the printer to respond again
                #disconnected = 0
        else:
            getstatus = True # We have a status

    connectionState = True
    return result


def urlCall(url, timelimit, post):
    # Makes all the calls to the printer
    # If post is True then make a http post call
    logger.debug('url: ' + str(url) + ' post: ' + str(post))
    loop = 0
    limit = 2  # Started at 2 - seems good enough to catch transients
    error  = ''
    while loop < limit:
        try:
            if post is False:
                r = requests.get(url, timeout=timelimit)
            else:
                r = requests.post(url, data=post)
            break
        except requests.ConnectionError as e:
            logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            logger.info('Cannot connect to the printer')
            logger.debug(str(e))
            logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n')
            error = 'Connection Error'
        except requests.exceptions.Timeout as e:
            logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            logger.info('The printer connection timed out')
            logger.debug(str(e))
            logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n')
            error = 'Timed Out'

        time.sleep(1)
        loop += 1 
 
    if loop >= limit:  # Create dummy response
        class r:
            ok = False
            status_code = 9999
            reason = error

    return r


def getDuetVersion(model):
    # Used to get the connection information from Duet
    # ALso used to test for reconnection if there is a disconnect
    if model == '' or model == 'rr_model':
            URL = ('http://' + duet + '/rr_model?key=boards')
            r = urlCall(URL, 3, False)
            if r.ok:
                try:
                    j = json.loads(r.text)
                    version = j['result'][0]['firmwareVersion']
                    return 'rr_model', version
                except:
                    pass

    if model == '' or model == 'SBC': 
            #  model = '/machine/system'
            URL = ('http://' + duet + '/machine/status')
            r = urlCall(URL, 3, False)
            if r.ok:
                try:
                    j = json.loads(r.text)
                    version = j['boards'][0]['firmwareVersion']
                    return 'SBC', version
                except:
                    pass
    
    return '' , ''


def Jobname():
    # Used to get the print jobname from Duet
    if apiModel == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=job.file.fileName')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                jobname = j['result']
                if jobname is None:
                    jobname = ''
                return jobname
            except Exception as e:
                logger.debug('Could not get jobname')
                logger.debug(e)

    elif apiModel == 'SBC':
        URL = ('http://' + duet + '/machine/status/')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                jobname = j['job']['file']['fileName']
                if jobname is None:
                    jobname = ''
                return jobname
            except Exception as e:
                logger.debug('Could not get jobname')
                logger.debug(e)

    return 'disconnected'


def Status():
    # Used to get the status information from Duet
    status = display = ''
    if apiModel == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=state')
        logger.debug('Getting Status')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                status = j['result']['status']
                display = j['result']['displayMessage']
                if display != '':
                    parseM117(display)
                return status, display
            except Exception as e:
                logger.debug('Could not get Status')
                logger.debug(e)

    elif apiModel == 'SBC':
        URL = ('http://' + duet + '/machine/status/')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                status = j['state']['status']
                display = j['state']['displayMessage']
                if display != '':
                    parseM117(display)
                return status, display
            except Exception as e:
                logger.debug('Could not get Status')
                logger.debug(e)

    return 'disconnected', ''


def Layer():
    # Used to get the the current layer
    if apiModel == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=job.layer')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                layer = j['result']
                if layer is None:
                    layer = -1
                return layer
            except Exception as e:
                logger.debug('Could not get Layer Info')
                logger.debug(e)

    elif apiModel == 'SBC':
        URL = ('http://' + duet + '/machine/status/')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                layer = j['job']['layer']
                if layer is None:
                    layer = -1
                return layer
            except Exception as e:
                logger.debug('Could not get Layer Info')
                logger.debug(e)

    return 'disconnected'


def Position():
    # Used to get the current head position from Duet
    if apiModel == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=move.axes')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                Xpos = j['result'][0]['machinePosition']
                Ypos = j['result'][1]['machinePosition']
                Zpos = j['result'][2]['machinePosition']
                return Xpos, Ypos, Zpos
            except Exception as e:
                logger.debug('Could not get Position Info')
                logger.debug(e)
    elif apiModel == 'SBC':
        URL = ('http://' + duet + '/machine/status')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                Xpos = j['move']['axes'][0]['machinePosition']
                Ypos = j['move']['axes'][1]['machinePosition']
                Zpos = j['move']['axes'][2]['machinePosition']
                return Xpos, Ypos, Zpos
            except Exception as e:
                logger.debug('Could not get Position Info')
                logger.debug(e)

    return 'disconnected'


def sendDuetGcode(model, command):
    # Used to send a command to Duet
    if model == 'rr_model':
        URL = 'http://' + duet + '/rr_gcode?gcode=' + command
        r = urlCall(URL, 3, False)
    else:
        URL = 'http://' + duet + '/machine/code'
        r = urlCall(URL, 3, command)

    if r.ok:
        return

    logger.info('sendDuetGCode failed with code: ' + str(r.status_code) + ' and reason: ' + str(r.reason))
    return


def makeVideo():  #  Adds and extra frame
    global makeVideoState, frame1, frame2
    makeVideoState = 1
    # Get a final frame
    # Make copies if appropriate

    if action not in ['snapshot', 'pause', 'start']: #  Would have been called as part of snapshot - so do not add images
        logger.debug('For Camera1')
        onePhoto('Camera1', camera1, weburl1, camparam1)  # For Camera 1
        if extratime != 0 and frame1/int(fps) > minvideo:
            frame1 = copyLastFrame(camfile1, frame1)

        if camera2 != '':   #  Camera 2
            logger.debug('For Camera2')
            onePhoto('Camera2', camera2, weburl2, camparam2)
            if extratime != 0 and frame2/int(fps) > minvideo:
                frame2 = copyLastFrame(camfile2, frame2)

    createVideo(workingdir)
    makeVideoState = -1

def copyLastFrame(f, frame):
    logger.info('Copying last frame to extend video by ' +str(extratime) + ' seconds')
    fr = str(frame).zfill(8)
    sourcefile = os.path.normpath(f + fr + '.jpeg')
    copies = int(extratime)*int(fps)
    for i in range(1, copies):
        nf = str(frame + i).zfill(8)
        targetfile = os.path.normpath(f + nf + '.jpeg')

        try:
            shutil.copy(sourcefile, targetfile)
        except shutil.Error as e:
            logger.info('Error on copy ' + str(e))
    return int(nf) # Must be an integer for later math



def terminate():
    global httpListener, listener, httpthread, terminateState, restarting, workingdir_exists
    # Force verbose messaging
    setdebug(True)

    terminateState = 1
    logger.info('Terminating')
    # Gracefully stop any threads that need to complete

    stopCaptureLoop()
    waitforcaptureLoop()  # Do not want to respond

    waitforNextAction() # Do not want to respond

    #  Make sure video is complete
    logger.info('Wait for video to complete')
    waitforMakeVideo()
    
    # Try to shutdown any open threads

    cleanupFiles('terminate')

    if restart:
        setdebug(verbose)

        restarting = True
        logger.info('----------')
        logger.info('RESTARTING\n\n')
        setuplogfile() # Create a new log file
        terminateState = -1
        workingdir_exists = False # Force creation of a new workingdir
        startNow() # reset the initial conditions
        listoptions() # List the current values
        issue_warnings() # list any warnings about setting combinations
        startup() # Warp speed Mr Sulu
    else:
        stopgcodeLoop()
        waitforgcodeLoop()
        closeHttpListener()
        logger.info('Program Terminated')
        os.kill(int(pid), 9)

def quit_forcibly(*args):
    global restart 
    restart = False
    logger.info('!!!!!! Stopped by SIGINT or CTL+C - Post Processing !!!!!!')
    terminateThread()


###########################
# Integral Web Server
###########################

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import urllib
from urllib.parse import urlparse, parse_qs
import html
#import io


class MyHandler(SimpleHTTPRequestHandler):
    # Default selectMessage
    global refreshing, selectMessage
    txt = []
    txt.append('<h3>')
    txt.append('Status will update every 60 seconds')
    txt.append('</h3>')
    refreshing = ''.join(txt)
    selectMessage = refreshing

    def shutdown(self):
        self.server._BaseServer__shutdown_request = True
        logger.debug('Sent shutdown request')

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
        content = f'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"><html><head><meta http-equiv = "refresh" content = "15; url = https://localhost:8082" /></head><body><h2>{message}</h2></body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!

    def _redirect(self, url, message):
        content = f'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"><html><head><meta http-equiv = "refresh" content = "60; url = ' + url + '" /></head><body><h2>' + message + '</h2></body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!

    def update_buttons(self, allowed):

        txt = []
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="status" />')
        txt.append('<input type="submit" value="Status" style="background-color:green"/>')
        txt.append('</form>')
        txt.append('</div>')
        statusbutton = ''.join(txt)

        txt = []
        value = 'start'
        if value in allowed:
            disable = ''
        else:
            disable = 'disabled'
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="' + value + '" />')
        txt.append('<input type="submit" value="Start" ' + disable + ' style="background-color:orange"/>')
        txt.append('</form>')
        txt.append('</div>')
        startbutton = ''.join(txt)

        txt = []
        value = 'standby'
        if value in allowed:
            disable = ''
        else:
            disable = 'disabled'
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="' + value + '" />')
        txt.append('<input type="submit" value="Standby" ' + disable + ' style="background-color:orange"/>')
        txt.append('</form>')
        txt.append('</div>')
        standbybutton = ''.join(txt)

        txt = []
        value = 'pause'
        if value in allowed:
            disable = ''
        else:
            disable = 'disabled'
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="' + value + '" />')
        txt.append('<input type="submit" value="Pause" ' + disable + ' style="background-color:pink"/>')
        txt.append('</form>')
        txt.append('</div>')
        pausebutton = ''.join(txt)

        txt = []
        value = 'continue'
        if value in allowed:
            disable = ''
        else:
            disable = 'disabled'
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="' + value + '" />')
        txt.append('<input type="submit" value="Continue" ' + disable + ' style="background-color:pink"/>')
        txt.append('</form>')
        txt.append('</div>')
        continuebutton = ''.join(txt)

        txt =[]
        value = 'snapshot'
        if value in allowed:
            disable = ''
        else:
            disable = 'disabled'
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="' + value + '" />')
        txt.append('<input type="submit" value="Snapshot" ' + disable + ' style="background-color:green"/>')
        txt.append('</form>')
        txt.append('</div>')
        snapshotbutton = ''.join(txt)

        txt = []
        value = 'restart'
        if value in allowed:
            disable = ''
        else:
            disable = 'disabled'
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="command" value="' + value + '" />')
        txt.append('<input type="submit" value="Restart" ' + disable + ' style="background-color:yellow"/>')
        txt.append('</form>')
        txt.append('</div>')
        restartbutton = ''.join(txt)

        txt = []
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="terminate" value='' />')
        txt.append('<input type="submit" value="Terminate" style="background-color:yellow"/>')
        txt.append('</form>')
        txt.append('</div>')
        terminatebutton = ''.join(txt)

        txt = []
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="files" value= ' + topdir + ' />')
        txt.append('<input type="submit" value="Files" style="background-color:green"/>')
        txt.append('</form>')
        txt.append('</div>')
        filesbutton = ''.join(txt)

        txt = []
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="hidden" name="info" value= '' />')
        txt.append('<input type="submit" value="Info" style="background-color:green"/>')
        txt.append('</form>')
        txt.append('</div>')
        infobutton = ''.join(txt)

        txt = []
        txt.append('<div class="inline">')
        txt.append('<form action="http://' + referer + '">')
        txt.append('<input type="text" id="fps" name="fps" value=' + fps + ' style="background-color:lime; width:30px; border:none"/>')
        txt.append('fps')
        txt.append('</form>')
        txt.append('</div>')
        fpsbutton = ''.join(txt)

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
        txt.append('width:auto; height:auto; overflow:auto; resize:both; border:1px solid; font-size:16px; line-height:16px;')
        txt.append('}')
        txt.append('} </style>')
        txt.append('<style> textarea {')
        txt.append('width:550px; height:100px; wrap:soft;')
        txt.append('box-sizing: border-box; border: 2px solid #ccc; border-radius: 4px; background-color: #f8f8f8;')
        txt.append('font-size: 16px;')
        txt.append('} </style>')
        cssstyle = ''.join(txt)

        if hidebuttons:
            btn = ''
            for button in allowed:
                btn = btn + ' + ' + button + 'button'
            btn = 'statusbutton' + btn + '+ filesbutton + infobutton + terminatebutton + fpsbutton + cssstyle'
            buttons = eval(btn)
        else:
            buttons = statusbutton + startbutton + standbybutton + pausebutton + continuebutton
            buttons = buttons + snapshotbutton + filesbutton + infobutton + restartbutton + terminatebutton + fpsbutton
            buttons = buttons + cssstyle

        return buttons

    def update_status(self):
        localtime = time.strftime('%A - %H:%M', time.localtime())
        if zo1 < 0:
            thislayer = 'None'
        else:
            thislayer = str(zo1)

        txt = []
        txt.append('DuetLapse3 Version ' + duetLapse3Version + '<br>')
        txt.append('<h3>')
        txt.append('Connected to printer:  ' + duet + '<br>')
        txt.append('Process Id:  ' + pid + '     Port: ' + str(port))
        txt.append('<br><br>')
        txt.append('Last Update:    ' + localtime + '<br>')
        txt.append('Capture Status:            =    ' + printState + '<br>')
        txt.append('DuetLapse3 State:          =    ' + action + '<br>')
        txt.append('Duet Status:               =    ' + duetStatus + '<br>')
        txt.append('Images Captured:           =    ' + str(frame1) + '<br>')
        txt.append('Current Layer:             =    ' + thislayer)
        txt.append('</h3>')
        status = ''.join(txt)
        return status

    def update_info(self):
        thisrunninginstance = getThisInstance(int(pid))

        if workingdir_exists:
            imagelocation = workingdir
            logname = logfilename
        else:
            imagelocation = 'Waiting for first image to be created'
            logname = 'Waiting for first image to be created'

        infotxt = []
        infotxt.append('<b>This instance WAS STARTED with the following options:</b><br><br>')
        infotxt.append(thisrunninginstance + '<br><br>')
        infotxt.append('<b>Logs and Videos are located here:</b><br><br>')
        infotxt.append(topdir + '<br><br>')
        infotxt.append('<b>Images are located here:</b><br><br>')
        infotxt.append(imagelocation + '<br><br>')
        infotxt.append('<b>The logfile for this instance is:</b><br><br>')
        infotxt.append(logname)
        information = ''.join(infotxt)

        txt = []
        txt.append('<h3>')
        txt.append('Process Id:    ' + pid + '<br>')
        txt.append('</h3>')
        txt.append('<div class="info-disp">')
        txt.append(information)
        txt.append('</div>')
        info = ''.join(txt)

        return info

    def do_GET(self):
        try:
            global referer, refererip
            referer = self.headers['Host']  # Should always be there
            if not referer:  # Lets try authority
                referer = self.headers['authority']
                if not referer:
                    referer = 'localhost'  # Best guess if all else fails
            split_referer = referer.split(":", 1)
            refererip = split_referer[0]  # just interested in the calling address as we know our port number

            global action, selectMessage, refreshing

            if 'favicon.ico' in self.path:
                return

            query_components = parse_qs(urlparse(self.path).query)
            logger.debug(str(self.path))

            #  Files request gets trapped here
            if (query_components and not query_components.get('command') and not query_components.get('delete')) or (
                    not query_components and self.path != '/'):

                selectMessage = self.display_dir(self.path)

            if query_components.get('delete'):
                file = query_components['delete'][0]
                filepath, _ = os.path.split(file)
                filepath = filepath + '/'
                filepath = filepath.replace(u'\u02f8', ':')  # make it look nice
                file = file.replace(':', u'\u02f8')  # get rid of any regular colons
                file = topdir + file
                file = os.path.normpath(file)

                if os.path.isdir(file):
                    try:
                        shutil.rmtree(file)
                    except shutil.Error as e:
                        logger.info('Error deleting dir ' + str(e))
                else:    
                    try:
                        os.remove(file)
                    except OSError as e:
                        logger.info('Error deleting file ' + str(e))

                selectMessage = self.display_dir(filepath)

            if query_components.get('zip'):
                file = query_components['zip'][0]
                filepath, _ = os.path.split(file)
                filepath = filepath + '/'
                file = topdir + file
                zipedfile = file + '.zip'

                file = os.path.normpath(file)
                zipedfile = os.path.normpath(zipedfile)
                result = make_archive(file, zipedfile)
                selectMessage = '<h3>' + result + '<br></h3>' + self.display_dir(filepath)

            if query_components.get('terminate'):  # This form is only called from the UI - see also command=terminate
                if action == 'snapshot':
                    selectMessage = '<br><h3>Cannot terminate while DuetLapse3 State: = snapshot.<br> Check status and wait.</h3>'
                else:
                    terminatetype = query_components['terminate'][0]
                    logger.debug('Terminate Called from UI')
                    selectMessage = self.terminate_process(terminatetype)

            if query_components.get('info'):
                selectMessage = self.update_info()

            global fps
            if (query_components.get('fps')):
                thisfps = query_components['fps'][0]
                try:
                    thisfps = int(thisfps)
                    if thisfps > 0:
                        fps = thisfps
                        logger.info('fps changed to: ' + str(fps))
                except ValueError:
                    pass
                fps = str(fps)

                selectMessage = '<h3>fps Changed</h3>'

            if query_components.get('command'):
                command = query_components['command'][0]
                logger.debug('!!!!! http ' + command + ' request received !!!!!')

                if command == 'status':
                    if selectMessage == None:
                        selectMessage = refreshing
                    allowed = allowedNextAction(action)

                    buttons = self.update_buttons(allowed)
                    status = self.update_status()
                    # Display Page
                    self._set_headers()
                    self.wfile.write(self._refresh(status + buttons + selectMessage))  # returns after 60 sec

                    selectMessage = refreshing
                    return

                # start / standby
                elif command == 'start':
                    selectMessage = ('<h3>'
                                         'Starting DuetLapse3.<br><br>'
                                         '</h3>')
                    startnextAction(command)

                elif command == 'standby':  # can be called at any time
                    txt = []
                    txt.append('<h3>')
                    txt.append( 'Putting DuetLapse3 in standby mode<br><br>')
                    txt.append('</h3>')
                    txt.append('<div class="info-disp">')
                    txt.append('Will NOT create a video.<br>')
                    txt.append('All captured images will be deleted<br>')
                    txt.append('This is the same as if DuetLapse was started with -standby<br><br>')
                    txt.append('</div>')
                    selectMessage = ''.join(txt)
                    startnextAction(command)

                # pause / continue
                elif command == 'pause':
                    txt = []
                    txt.append('<h3>')
                    txt.append('DuetLapse3 is paused.<br><br>')
                    txt.append('</h3>')
                    selectMessage = ''.join(txt)

                    startnextAction(command)

                elif command == 'continue':
                    txt = []
                    txt.append('<h3>')
                    txt.append('DuetLapse3 is continuing.<br><br>')
                    txt.append('</h3>')
                    selectMessage = ''.join(txt)

                    startnextAction(command)

                # snapshot / restart / terminate

                elif command == 'snapshot':
                    txt = []
                    txt.append('<h3>')
                    txt.append('Attempting to create an interim snapshot video')
                    txt.append('</h3>')
                    txt.append('<div class="info-disp">')
                    txt.append('Check the files menu for completed snapshots<br>')
                    txt.append('Depending on the number of images - this could take a lot of time<br>')
                    txt.append('10 to 60+ minutes<br>')
                    txt.append('During this time - images will continue to be captured<br><br>')
                    txt.append('After the snapshot DuetLapse3 returns to the prior state i.e. <b>start or pause</b><br>')
                    txt.append('</div>')
                    selectMessage = ''.join(txt)

                    startnextAction(command)

                elif command == 'restart':
                    txt = []
                    txt.append('<h3>')
                    txt.append('Restarting DuetLapse3')
                    txt.append('</h3>')
                    txt.append('<div class="info-disp">')
                    txt.append('Check the files menu for completed video<br>')
                    txt.append('Depending on the number of images - this could take a lot of time<br>')
                    txt.append('5 to 30+ minutes be needed depending on the computer<br>')
                    txt.append('No more images will be captured<br><br>')
                    txt.append('All captured images will be deleted.<br>')
                    txt.append('The restart behavior is the same as initially used to start DuetLapse3<br>')
                    txt.append('</div>')
                    selectMessage = ''.join(txt)

                    startnextAction(command)

                elif command == 'terminate':  #only called explicitely - backward compatible
                        selectMessage = self.terminate_process('graceful')

                else:
                    selectMessage = self.ignoreCommandMsg(command, action)

            new_url = 'http://' + referer + '/?command=status'
            self.redirect_url(new_url)
            return
        except:
            return
    """
    End of do_Get
    """

    def log_request(self, code=None, size=None):
        pass

    def log_message(self, format, *args):
        pass

    def ignoreCommandMsg(self, command, action):
        txt = []
        txt.append('<h3>')
        txt.append(command + ' request has been ignored<br><br>')
        txt.append(action + ' state is currently enabled')
        txt.append('</h3>')
        msg = ''.join(txt)

        return msg

    def terminate_process(self, ttype):
        if ttype not in ['graceful', 'forced']:
           ttype = ''
           logger.debug('Terminate type requested')
        else:
           logger.debug(ttype + ' terminate requested')

        if ttype == 'graceful':
            txt = []
            txt.append('<h3>')
            txt.append('Terminating DuetLapse3<br><br>')
            txt.append('Will finish last image capture, create a video, then terminate.')
            txt.append('</h3>')
            selectMessage = ''.join(txt)

            startnextAction('completed')
        elif ttype == 'forced':
            txt = []
            txt.append('<h3>')
            txt.append('Forced Termination of DuetLapse3<br><br>')
            txt.append('No video will be created.')
            txt.append('</h3>')
            selectMessage = ''.join(txt)
            quit_forcibly()

        else:
            txt = []
            txt.append('<h3>')
            txt.append('Select the type of Termination<br><br>')
            txt.append('Graceful will create video.  Forced will not<br>')
            txt.append('</h3>')
            txt.append('<br>')
            message = ''.join(txt)

            txt = []
            txt.append('<div class="inline">')
            txt.append('<form action="http://' + referer + '">')
            txt.append('<input type="hidden" name="terminate" value="graceful" />')
            txt.append('<input type="submit" value="Graceful" style="background-color:yellow"/>')
            txt.append('</form>')
            txt.append('</div>')
            gracefulbutton = ''.join(txt)

            txt = []
            txt.append('<div class="inline">')
            txt.append('<form action="http://' + referer + '">')
            txt.append('<input type="hidden" name="terminate" value="forced" />')
            txt.append('<input type="submit" value="Forced" style="background-color:red"/>')
            txt.append('</form>')
            txt.append('</div>')
            forcedbutton = ''.join(txt)

            selectMessage = message+gracefulbutton+forcedbutton

        return selectMessage


    def display_dir(self, path):
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        # Don't forget explicit trailing slash when normalizing. Issue 17324
        trailing_slash = path.rstrip().endswith('/')
        requested_dir = topdir + path

        if trailing_slash:  # this is a dir request
            response = self.list_dir(requested_dir)
            return response
        else:  # this is a file request
            requested_dir = requested_dir.replace('%CB%B8',
                                                  u'\u02f8')  # undoes raised colons that were replaced by encoding
            ctype = self.guess_type(requested_dir)
            logger.debug(str(ctype))

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
                logger.debug('Connection reset - normal if displaying file')
            except:
                logger.info('Error sending file')

        return ''

    def list_dir(self, path):  # Copied from super class
        # Pass the directory tree and determine what can be done with each file / dir
        jpegfile = '.jpeg'
        deletablefiles = ['.mp4','.zip'] #  Different to startDuetLapse3
        jpegfolder = []
        deletelist = []
        for thisdir, subdirs, files in os.walk(topdir):
            if not subdirs and not files:  # Directory is empty
                deletelist.append(os.path.join(thisdir, ''))
                if thisdir == topdir:
                    txt = []
                    txt.append('<h3>')
                    txt.append('There are no files to display at this time<br><br>')
                    txt.append('You likely need to start an instance of DuetLapse3 first')
                    txt.append('</h3>')
                    response = ''.join(txt)
                    return response

            for file in files:
                if any(ext in file for ext in deletablefiles):
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

        # Parse the direstory tree and determine what can be done with each file / dir - NOT USED
        try:
            list = os.listdir(path)
        except OSError:
            txt = []
            txt.append('<h3>')
            txt.append('There are no files or directories named '+displaypath+'<br>')
            txt.append('or you do not have permission to access')
            txt.append('</h3>')
            response = ''.join(txt)
            return response

        #  list.sort(key=lambda a: a.lower())
        list.sort(key=lambda fn: os.path.getmtime(os.path.join(path, fn))) # Have to use full path to stat file

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

        for name in list:  #this loop is DuetLapse3 specific - different to startDuetLapse3
            if not name.startswith(pid) and not name.endswith('.jpeg'):
                continue  # only display for this instance

            fullname = os.path.join(path, name)
            fullname = os.path.normpath(fullname) #  no trailing slash will add in later if its a directory
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

            deletebutton = zipbutton = vidbutton = ''
            if fullname in deletelist and not fullname in jpegfolder:  #Different to startDuetLapse3
                txt = []
                txt.append('<td>')
                txt.append('<form action="http://' + referer + '">')
                txt.append('<input type="hidden" name="delete" value="' + action_name + '" />')
                txt.append('<input type="submit" value="Delete" style="background-color:red"/>')
                txt.append('</form>')
                txt.append('</td>')
                deletebutton = ''.join(txt)


            r.append(deletebutton)
            r.append('</tr>')

        r.append('</table>')

        response = ''.join(r)
        return response

"""
    end of requesthandler
"""

def allowedNextAction(thisaction):
                if thisaction == 'standby':
                    return ['start']
                elif thisaction == 'pause':
                    return ['standby', 'continue', 'snapshot', 'restart']
                elif thisaction == 'snapshot' and lastaction == 'pause':  # same as pause
                    return ['standby', 'continue', 'snapshot', 'restart']
                elif thisaction == 'restart':
                    if standby:
                        return ['start']
                    else:
                        return ['standby', 'pause', 'snapshot', 'restart']
                else:
                    return ['standby', 'pause', 'snapshot', 'restart']


def startHttpListener():
    global listener
    try:
        listener = ThreadingHTTPServer((host, port), MyHandler)
        threading.Thread(name='httpServer', target=listener.serve_forever, daemon=False).start()  #Avoids blocking
        logger.info('##########################################################')
        logger.info('***** Started http listener *****')
        logger.info('##########################################################\n')
    except Exception as e:
        logger.info('There was a problem starting the http listener')
        logger.info(e)
        logger.info('Is it running from a prior start ?')
        logger.info('Continuing')


def closeHttpListener():
    global listener
    try:
        listener.shutdown()
        logger.debug('!!!!! http listener stopped  !!!!!')
    except Exception as e:
        logger.debug('Could not terminate http listener')
        logger.debug(e)


def execRun(displaymessage):
        cmd = displaymessage.split(execkey)[1]
        logger.info('!!!!!!!!  Make call to execute !!!!!!!!')
        logger.info(cmd)
        subprocess.Popen(cmd, shell=True, start_new_session=True)  # run the program
        sendDuetGcode(apiModel,'M117 ""')


###################################
#  Thread Control functions
##################################
# Threads have tri-states
# -1 is stopped
# 0 is request to stop
# 1 is running

def startCaptureLoop():
    #  global captureLoopState
    if captureLoopState == 1 or terminateState == 1: # Already running or don't start
        return
    threading.Thread(name='captureLoop', target=captureLoop, args=(), daemon=False).start()

def stopCaptureLoop():
    global captureLoopState
    if captureLoopState == 1:
        captureLoopState = 0  # Signals capture thread to shutdown

def waitforcaptureLoop():
    #  global captureLoopState
    if captureLoopState == -1:
        logger.debug('captureLoop is not running')
    while captureLoopState >= 0:  # only one thread at a time may cause delay in http page update
        time.sleep(pollcheck) # Check 4 times per poll interval
        logger.debug('********* Waiting for captureLoop to complete *********')
    logger.debug('Exited captureLoop')


def startgcodeLoop():
    #  global gcodeLoopState
    if gcodeLoopState == 1 or terminateState == 1:  #  Already running or don't start
        return
    threading.Thread(name='gcodeLoop', target=gcodeLoop, args=(), daemon=False).start()

def stopgcodeLoop():
    global gcodeLoopState
    if gcodeLoopState == 1:
        gcodeLoopState = 0  # Signals capture thread to shutdown

def waitforgcodeLoop():
    if gcodeLoopState == -1:
        logger.debug('gcodeLoop is not running')
        return
    while gcodeLoopState >= 0:  # only one thread at a time may cause delay in http page update
        time.sleep(pollcheck) 
        logger.debug('********* Waiting for gcodeLoop to complete *********')
    logger.debug('Exited gcodeLoop')



def startnextAction(command): # Does not run in a loop
    if terminateState == 1: # Block it if terminating
        return
    waitforNextAction()  
    threading.Thread(name='nextAction', target=nextAction, args=(command,), daemon=False).start()


def waitforNextAction():
    if nextActionState == -1:
        logger.info('nextAction is available')
        return
    while nextActionState >= 0:  # Only one thread at a time may cause delay in http page update
        time.sleep(1)
        logger.debug('********* Waiting for nextAction to complete *********')
    logger.debug('nextaction is ready')
    

def startcheckforConnection():
    if checkforconnectionState == 1 or terminateState == 1:  #  Already running or don't start
        return
    threading.Thread(name='checkforConnection', target=checkforConnection, args=(), daemon=False).start()

def terminateThread(): # Can only be run once - but calles as a thread to allow other threads to finish
    if terminateState == 1: #    Already Terminating
        return
    threading.Thread(name='terminate', target=terminate, args=(), daemon=False).start()


def waitforMakeVideo():
    global makeVideoState
    while makeVideoState >= 0: # wait till its completed
        time.sleep(5)  # Makevideo is fairly slow
        logger.debug('********* Waiting for makeVideo thread to finish *********')
    logger.debug('makeVideo is not running')


def startMakeVideo(): # Does not run in a loop - so we block it before running it
    if terminateState == 1: # Block it if terminating
        return
    waitforMakeVideo()      
    threading.Thread(name='makeVideo', target=makeVideo, args=(), daemon=False).start()



###################################
#  Main Control Functions
###################################

def gcodeLoop():
    # Used for handling M117 Messages
    # Runs continously except during terminate processing
    global gcodeLoopState, action, duetStatus

    if connectionState is False:
        return

    gcodeLoopState = 1 # Running
    logger.info('###########################')
    logger.info('Starting gcode Listener')
    logger.info('###########################\n')

    while gcodeLoopState == 1 and terminateState != 1 and connectionState:  # Setting to 0 stops
        duetStatus, _ = getDuet('Status from gcodelistener', Status)
        if gcodeLoopState == 1:
            time.sleep(5)  #  Check frequently
    gcodeLoopState = -1 # Not Running
    return


def captureLoop():  # Run as a thread

    global printState, duetStatus, captureLoopState
    
    if connectionState is False:
        return
    
    captureLoopState = 1
    printState = 'Not Capturing'

    lastDuetStatus = 'idle' # logical state on start of each thread instance

    logger.debug('Starting Capture Loop')

    while captureLoopState == 1:  # Set to 0 to stop. e.g  By http listener or SIGINT or CTL+C
        if duetStatus != lastDuetStatus:  # What to do next?
            logger.info('****** Duet status changed to: ' + str(duetStatus) + ' *****')
            # logical states for printer are printing, completed
            if (duetStatus == 'idle') and (printState in ['Capturing', 'Busy']):  # print job has finished
                printState = 'Completed'
                logger.debug('****** Print State changed to ' + printState + ' *****')
            elif (duetStatus in ['processing', 'idle']) or (duetStatus == 'paused' and detect == 'pause'):
                printState = 'Capturing'
                logger.debug('****** Print State changed to: ' + printState + ' *****')
            elif duetStatus == 'busy':
                printState = 'Busy'
                logger.debug('****** Print State changed to: ' + printState + ' *****')
            else:
                printState = 'Waiting'
            logger.info('****** Print State changed to: ' + printState + ' *****')

        if printState == 'Capturing':
            oneInterval('Camera1', camera1, weburl1, camparam1)
            if camera2 != '':
                oneInterval('Camera2', camera2, weburl2, camparam2)
            unPause()  # Nothing should be paused at this point
        elif printState == 'Completed':
            logger.info('Print Job Completed')
            printState = 'Not Capturing'
            # use a thread here as it will allow this thread to close.
            startnextAction('completed')
            break # Do not want to wait to end

        if captureLoopState == 1 and terminateState != 1 and connectionState:  # If still running then sleep
            lastDuetStatus = duetStatus
            time.sleep(poll)

    printState = 'Not Capturing'
    captureLoopState = -1
    return  # End of captureLoop


def nextAction(nextaction):  # can be run as a thread
    global action, printState, captureLoopState, lastaction, logger, nextActionState, standby, gcodeLoopState, restart
    logger.info('++++++ ' + nextaction + ' state requested ++++++')
    # All nextactions need the capture thread to be shut down
    stopCaptureLoop()
    # This section needs to ge first as it checks for reconnection after network issue
    if nextaction == 'waitforconnection': # Go into connection check loop
        startcheckforConnection() 
        nextActionState = -1
        return
    elif nextaction == 'reconnected':
        startgcodeLoop() # restart the gcode monitor
        time.sleep(5) # Give the gcodeloop time to get nest status
        nextaction = lastaction
        logger.info('Resuming after reconnect with nextaction = ' + nextaction)

    if connectionState is False: #traps any requests during a disconnect
        nextActionState = -1
        return

    nextActionState = 1
    action = nextaction  # default

    # This test is positionally sensitive
    if nextaction == 'completed':  # end of a print job
        printState = 'Completed'  # Update may have come from if came from M117
        if novideo:
            logger.info('Video creation was skipped')
        else:
            startMakeVideo()
        nextaction = 'terminate'

    logger.debug('++++++ Determining next logical action ++++++')

    if nextaction == 'start':
        startCaptureLoop()
        action = 'start'

    elif nextaction == 'standby':
        cleanupFiles(nextaction)  # clean up and start again
        setstartvalues()
        action = 'standby'

    elif nextaction == 'pause':
        action = 'pause'
 
    elif nextaction == 'continue':
        startCaptureLoop()
        action = 'start'

    elif nextaction == 'snapshot':
        startMakeVideo()
        logger.debug('Snapshot being created, last action was ' + lastaction)
        if lastaction == 'pause':
            action = 'pause'
        else:
            action = 'start'
            startCaptureLoop()

    elif nextaction == 'restart':
        if novideo:
            logger.info('Video creation was skipped')
        else:
            startMakeVideo()
            waitforMakeVideo() # Wait until done before deleting files
        cleanupFiles(nextaction)  # clean up and start again
        setstartvalues()
        startNow()
        if standby:
            action = 'standby'
        else:
            action = 'start'
            startCaptureLoop()
    elif nextaction == 'terminate':
        terminateThread() #  Allows nextAction to finish
        action = 'terminate'

    logger.info('++++++ Entering ' + action + ' state ++++++')
    try:
        lastaction = action
    except NameError:
        lastaction = action
    nextActionState = -1
    return

###################################
#  Utility Functions
###################################


def parseM117(displaymessage):
    global action
    displaymessage = displaymessage.strip() # get rid of leading / trailing blanks

    if displaymessage.startswith('DuetLapse3.'):
        sendDuetGcode(apiModel,'M117 ""') #  Clear the display message

        logger.info('M117 Command: ' + displaymessage)
        nextaction = displaymessage.split('DuetLapse3.')[1]

        if nextaction == action: #  Nothing to do
            logger.info('Already in ' + action + ' state')
            return

        if nextaction == 'graceful':
            startnextAction('completed')
        elif nextaction == 'forced':
            quit_forcibly()
        elif nextaction in allowedNextAction(action) or nextaction == 'completed':
            logger.debug ('M117 sending to startnextAction: ' + nextaction)
            startnextAction(nextaction)
        elif nextaction.startswith('change.'):
            command = nextaction.split('change.')[1]
            changehandling(command)
        else:
            logger.info('The requested action: ' + nextaction + ' is not available at this time')
            logger.info('The current state is: ' + action)

    elif execkey != '' and displaymessage.startswith(execkey):
        sendDuetGcode(apiModel,'M117 ""') #  Clear the display message
        execRun(displaymessage) # Run the command 


def changehandling(command):
    global logger
    command = command.replace(' ','') # Make sure it is well formed
    changevariables = ['verbose', 'seconds', 'poll', 'detect', 'dontwait', 'pause', 'restart', 'novideo', 'keepfiles','minvideo','extratime', 'fps', 'rest',  'execkey']
    variable = command.split('=')[0]
    value = command.split('=')[1]
    if variable in changevariables:
        logger.debug('Changing variable with: ' + command)
        if variable == 'verbose' and value in ['True', 'False']:
            updateglobals(variable, value)
            setdebug(verbose)
        elif variable == 'seconds':
            if int(value) >= 12 or int(value) == 0:
                updateglobals(variable, value)
                poll_seconds()
                if seconds > 0 and 'none' in detect:
                    updateglobals('dontwait', 'True')
        elif variable == 'poll':
            if int(value) >= 12:
                updateglobals(variable, value)
                poll_seconds()
        elif variable == 'detect' and value in ['layer', 'pause', 'none']:
            command = "detect='" + value + "'"
            updateglobals(variable, value)
        elif variable == 'pause' and value in ['yes', 'no']:
            updateglobals(variable, value)
        elif variable in ['restart', 'novideo', 'keepfies'] and value in ['True', 'False']:  # Booleans
            updateglobals(variable, value)
        else:  #  General numeric or string
            updateglobals(variable, value)
    else:
        logger.info('Changing variable with: ' + command + ' is not supported')

def updateglobals(var,val):
    convert = ''
    if var in globals():  # Otherwise do nothing
        #  Determine the original type
        #  use type() instead of isinstance() to avoid subtype issues
        vartype = str(type(globals()[var]))
        if 'int' in vartype:
            convert = 'int'
        elif 'float' in vartype:
            convert = 'float'
        elif 'bool' in vartype:
            convert = 'bool'
        elif val in globals() or 'str' in vartype:  # val cannot be a globals value
            val = '"' + val + '"' # force the string literal
            convert = 'str'
        else:
            logger.debug(var + ' is a global of type ' + convert + ' will force to string')
            convert = 'str'

    else:
        logger.info(var + ' is not a global variable')
        return

    if convert != '':  # Only handle the types above
        #  Change the value
        #  Need to declare that we are working with the global in exec
        changevar = 'global ' + var + '; ' + var + ' = ' + val
        exec(changevar)
        # restore to the correct type
        changetype = 'global ' + var + '; ' + var + ' = ' + convert + '(' + var + ')'
        exec(changetype)
        logger.info(var + ' has been changed to ' + str(val))

    else:
        logger.debug('unknown type. No change on ' + var)
        return
         
def startMessages():
    if startNow():
        logger.info('##########################################################')
        logger.info('Will start capturing images immediately')
        logger.info('##########################################################\n')
    else:
        if 'layer' in detect or 'pause' in detect:
            logger.info('##########################################################')
            if 'layer' in detect:
                logger.info('Will start capturing images on first layer change')
            elif 'pause' in detect:
                logger.info('Will start capturing images on first pause in print stream')
            logger.info('##########################################################\n')

    if standby:
        logger.info('##########################################################')
        logger.info('Will not start until command=start received from http listener')
        logger.info('or M117 DuetLapse3.start send in gcode')
        logger.info('##########################################################\n')

    logger.info('##########################################################')
    logger.info('Video will be created when printing ends')
    logger.info('or if requested from the browser interface or M117 DuetLapse3. message')
    logger.info('##########################################################\n')

    logger.info('##########################################################')
    logger.info('If running from a console using the command line')
    if win:
        logger.info('Press Ctrl+Break one time to stop the program and create a video.')
        logger.info('On machines without the Break key - try Fn+Ctl+B')
    else:
        logger.info('Press Ctrl+C one time to stop the program and create a video.')
    logger.info('##########################################################\n')

    return

def checkforvalidport():
    global host, port
    sock = socket.socket()
    if (host == '0.0.0.0') and win:  # Windows does not report properly with 0.0.0.0
        host = '127.0.0.1'

    portcheck = sock.connect_ex((host, port))

    if portcheck == 0:
        logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        logger.info('Sorry, port ' + str(port) + ' is already in use.')
        logger.info('Shutting down this instance.')
        logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        sys.exit(8)


def startup():

    setstartvalues()  # Default startup global values

    checkforPrinter()  # Needs to be connected before gcodeloop

    if httpListener and restarting is False:
        startHttpListener()

    startgcodeLoop()


    logger.info('Initiating with action set to ' + action)
    nextAction(action)


###########################
# Program  begins here
###########################
if __name__ == "__main__":  # Do not run anything below if the file is imported by another program
    
    # Allow process running in background or foreground to be gracefully
    # shutdown with SIGINT (kill -2 <pid>)
    signal.signal(signal.SIGINT, quit_forcibly) # Ctrl + C

    # Globals 
    global httpListener, win, pid, action, apiModel, workingdir_exists, workingdirs
    global nextActionState, makeVideoState, captureLoopState, gcodeLoopState, terminateState
    global connectionState, restarting, checkforconnectionState
    # Status flag for threads
    nextActionState = captureLoopState = makeVideoState = gcodeLoopState = terminateState = checkforconnectionState =  -1  #  All set as not running
    connectionState = restarting = False
    commands = ['start','standby','pause','continue', 'snapshot', 'restart', 'terminate']
    
    httpListener = False  # Indicates if an integral httpListener should be started
    win = False  # Windows OS
    pid = ''  # pid for this instance - used for temp filenames
    workingdirs = []
    workingdir_exists = False
    apiModel = ''

    init()
    issue_warnings()
    port_ok = checkforvalidport() # Exits if invalid
    startMessages()
    startup()
