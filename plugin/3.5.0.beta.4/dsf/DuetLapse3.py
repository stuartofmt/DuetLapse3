#!/usr/bin/python3

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
# Developed on Raspberry Pi and WSL with Debian Bullseye and on Windows 10/11. SHOULD work on most other linux distributions.
# For USB or Pi camera, The Camera MUST be physically attached to the Pi computer.
# For Webcam, the camera must be network reachable and via a defined URL for a still image.
# For Stream   the camera must be network reachable and via a defined URL
# The Duet printer must be RepRap firmware V3 and must be network reachable.
#
#
"""

duetLapse3Version = '5.3.0'

"""
CHANGES
# Fixed snapshot when called from gcode
# Added second variable to video api --> xtratime
# Fixed calculation type error on extratime
# rationalized timers
# added throttle for status calls
# changed M117 messages to M291
# 5.1.1
# Refreshes tab on regaining focus from browser
# Changed G1 to G0 in movehead
# 5.2.0
# Process all M291 messages without delay
# Refactored loop control to prevent thread blocking
# Prevent first layer capture if -pause yes
# Added -password
# 5.2.1
# Changed background tab color - better for dark theme
# 5.2.2
# Fixed bug in -pause layer detection
# Added wait loop before restart to ensure previous job had finished
# fixed a timing thing dependent on when "Complete" sent from finish gcode
# 5.2.3
# Fixed bug caused by calling unpause inappropriately
# 5.2.4
# Added emulation mode check to support V3.5
# Added stopPlugin call to plugin manager
# 5.3.0
# Added capture every nth layer
# Fixed incorrect POST on M292
# Changed firmware version to use ['boards'][0]['firmwareVersion']
"""

"""
# Experimental
import pathlib
import subprocess
import sys

modules = {'platform', 'argparse', 'shlex', 'time', 'requests', 'json', 'os', 'socket', 'threading', 'psutil', 'shutil', 'stat', 'pathlib', 'signal', 'logging'}

for m in modules:
    try:
        #import m
        globals()[m] = __import__(m)
    except ImportError:
        print('Trying to install: ' + m)
        cmd = 'pip3 install ' + m
        subprocess.run(cmd , shell=True)
    finally:
        if m not in sys.modules:
            try:
                #import m
                globals()[m] = __import__(m)
            except ImportError:
                print('Could not import: ' + m)



"""
import subprocess
import sys
import platform
import argparse
import shlex
import time
import requests
import json
import os
import socket
import threading
import psutil
import shutil
import pathlib
import stat
import signal
import logging
# from systemd.journal import JournalHandler


def setstartvalues():
    global zo1, zo2, printState, captureLoopState, mainLoopState,  duetStatus, timePriorPhoto1, timePriorPhoto2, frame1, frame2, lastImage
    logger.debug('*****  Initializing state and counters  *****')
    printState = 'Waiting'
    stopCaptureLoop()
    duetStatus = 'Printer is not connected'

    # initialize timers
    timePriorPhoto1 = time.time()
    timePriorPhoto2 = time.time()

    # frame counters and layer (zo) state
    frame1 = 0 # Camera1
    zo1 = -1  
    frame2 = 0 # Camera2
    zo2 = -1 

    # last image captured
    lastImage = ''

###########################
# General purpose methods begin here
###########################

def returncode(code):  # Defined here - used by calling programs
    codes = { 0 : 'Not Used',
              1 : 'OS error',
              2 : 'Invalid options combination',
              3 : 'Missing software dependency',
              4 : 'No response from Printer',
              5 : 'Incorrect Printer version',
              6 : 'Process is already running',
              7 : 'HTTP server terminated',
              8 : 'Port already in use',
              9 : 'Cannot connect to printer'
            }
    if code in codes:
        text = codes[code]
    else:
        text = str(code) + ' is an unidentified Code'
    return text


class LoadFromFilex (argparse.Action):
    def __call__ (self, parser, namespace, values, option_string = None):
        with values as file:
            try:
                import copy

                old_actions = parser._actions
                file_actions = copy.deepcopy(old_actions)

                for act in file_actions:
                    act.required = False

                parser._actions = file_actions
                parser.parse_args(shlex.split(file.read()), namespace)
                parser._actions = old_actions

            except Exception as e:
                logger.info('Error: ' +  str(e))
                return


def whitelist(parser):
    # Environment
    parser.add_argument('-duet', type=str, nargs=1, default=['localhost'],
                        help='Name of duet or ip address. Default = localhost')
    parser.add_argument('-password', type=str, nargs=1, default=['reprap'],
                        help='Password for printer. Default = reprap')
    parser.add_argument('-poll', type=int, nargs=1, default=[12])
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
    parser.add_argument('-seconds', type=int, nargs=1, default=[0])
    parser.add_argument('-detect', type=str, nargs=1, choices=['layer', 'pause', 'none'], default=['layer'],
                        help='Trigger for capturing images. Default = layer')
    parser.add_argument('-pause', type=str, nargs=1, choices=['yes', 'no'], default=['no'],
                        help='Park head before image capture.  Default = no')
    parser.add_argument('-numlayers', type=int, nargs=1, default=[1],
                        help='Number of layers before capture.  Default = 1')
    parser.add_argument('-movehead', type=int, nargs=2, default=[0, 0],
                        help='Where to park head on pause, Default = 0,0')
    parser.add_argument('-rest', type=int, nargs=1, default=[1],
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
    parser.add_argument('-extratime', type=int, nargs=1, default=[0], help='Time to repeat last image, Default = 0')
    parser.add_argument('-minvideo', type=int, nargs=1, default=[5], help='Minimum video length (sec), Default = 5')
    parser.add_argument('-maxvideo', type=int, nargs=1, default=[0], help='Fixed video length (sec), Default = inactive')
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
    parser.add_argument('-execkey', type=str, nargs=1, default=[''],help='string to identify executable command')

    return parser

################################################
##  Main routines for calling subprocesses
################################################


def runsubprocess(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True)

        if str(result.stderr) != '':
            logger.info('Command Failure: ' + str(cmd))
            logger.debug('Error = ' + str(result.stderr))
            logger.debug('Output = ' + str(result.stdout))
            return False
        else:
            logger.debug('Command Success : ' + str(cmd))
            if result.stdout != '':
                logger.debug(str(result.stdout))
            return True
    except (subprocess.CalledProcessError, OSError) as e:
        logger.info('Command Exception: ' + str(cmd))
        logger.info('Exception = ' + str(e))
        return False




def init():
    global inputs
    parser = argparse.ArgumentParser(
            description='Create time lapse video for Duet3D based printer. V' + duetLapse3Version, allow_abbrev=False)
    parser = whitelist(parser)

    parser.add_argument('-file', type=argparse.FileType('r'), help='file of options', action=LoadFromFilex)

    args = vars(parser.parse_args())  # Save as a dict

    inputs = {}

    global duet, password, basedir, poll, instances, logtype, nolog, verbose, host, port
    global keeplogs, novideo, deletepics, maxffmpeg, keepfiles
    # Derived  globals
    global duetname, debug, ffmpegquiet, httpListener

    # Environment
    inputs.update({'# Environment':''})
    
    duet = args['duet'][0]
    inputs.update({'duet': str(duet)})

    password = args['password'][0]
    #  password is not displayed
        
    basedir = args['basedir'][0]
    inputs.update({'basedir': str(basedir)})
    
    poll = args['poll'][0]
    if poll < minPoll:
        poll = minPoll
    inputs.update({'poll': str(int(poll))})
    
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
    global dontwait, seconds, detect, pause, numlayers, movehead, rest, standby, restart
    inputs.update({'# Execution' : ''})

    dontwait = args['dontwait']
    inputs.update({'dontwait': str(dontwait)})

    seconds = args['seconds'][0]
    if seconds != 0 and seconds < minseconds:
        seconds = minseconds
    inputs.update({'seconds': str(seconds)})

    detect = args['detect'][0]
    inputs.update({'detect': str(detect)})

    pause = args['pause'][0]
    inputs.update({'pause': str(pause)})

    numlayers = args['numlayers'][0]
    if numlayers < 1:
        numlayers = 1
    inputs.update({'numlayers': int(numlayers)})

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
    inputs.update({'camera1': str(camera1)})

    camera2 = args['camera2'][0]
    inputs.update({'camera2': str(camera2)})

    weburl1 = args['weburl1'][0]
    inputs.update({'weburl1': str(weburl1)})

    weburl2 = args['weburl2'][0]
    inputs.update({'weburl2': str(weburl2)})

    # Video
    global extratime, fps, minvideo, maxvideo
    inputs.update({'# Video': ''})

    extratime = args['extratime'][0]
    inputs.update({'extratime': str(extratime)})

    fps = args['fps'][0]
    inputs.update({'fps': str(fps)})

    minvideo = args['minvideo'][0]
    inputs.update({'minvideo': str(minvideo)})

    maxvideo = args['maxvideo'][0]
    if maxvideo > 0:
       if maxvideo < minvideo:
           maxvideo = minvideo

    inputs.update({'maxvideo': str(maxvideo)})

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
    logger.propagate = False

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
    global topDir, nextWorkingDir, workingDir, loggingset, logname, pidIncrement
    loggingset = False
    pidIncrement = 0 # Used to create a new path for each job.
    if basedir == '':
        basedir = os.path.dirname(os.path.realpath(__file__))
    # clean up the separators
    basedir = basedir.replace('\\', '/')
    if basedir.startswith('.'):  #  this little trick so as not to drop ./ or ../
        basedir = './' + basedir
        basedir = os.path.normpath(basedir) # get slashes in correct direction


    topDir = os.path.join(basedir, socket.getfqdn(), duetname)
    logger.debug('The top level dir is ' + topDir)
    
    pidID = pid + '_' + str(pidIncrement)
    nextWorkingDir = os.path.join(topDir, pidID)  # used to seed workinDir

    if not os.path.isdir(topDir): # If not already exists - create
        try:
            os.makedirs(topDir)  # Use recursive form to create intermediate directories
        except OSError as e:
            logger.info('Could not create dir ' + str(e))
            sys.exit(1)
    
    # Should not happen (almost like winning the lottery)
    for item in listTopDir():
        if item.startswith(pidID):  # Wow - a pid collision
            pidIncrement += 1
            nextWorkingDir = os.path.join(topDir, pid + '_' + str(pidIncrement))


    #  Clean up older files
    cleanupFiles('startup')

    setuplogfile()
    
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


####################################################
# Display the options being used
####################################################

def getOptions():
    for var in inputs: # update the values
        if var in globals():
            val = globals()[var]
            newvalue = {var:val}
            inputs.update(newvalue)
    return inputs

def listOptions():
    options = getOptions()
    logger.info("################### Options at start of this print job  #####################")  
    for label, value in options.items():
        value = str(value)
        if label.startswith('#'):
            logger.info(label)
        elif value == '':
            logger.info('-' + label)
        else:
            logger.info('-' + label + '  =  ' + value)
    logger.info('-----------------------------------------------------------------------\n\n')


####################################################
# Logfile setup
####################################################

def setuplogfile():  #Called at start and restart
    global loggingset, logname, logfilename, nextWorkingDir, pidIncrement
    #  Set up log file now that we have a name for it
    
    logfilename = os.path.join(topDir, 'startup.log')
    pidIncrement += 1
    nextWorkingDir = os.path.join(topDir, pid + '_' + str(pidIncrement))

    if nolog is False:
        filehandler = None
        for handler in logger.handlers:
            if handler.__class__.__name__ == "FileHandler":
                filehandler = handler
        
            if filehandler != None:  #  Get rid of it
                filehandler.flush()
                filehandler.close()
                logger.removeHandler(filehandler)
                time.sleep(mainLoopPoll) # Wait for any messages to propogate

        f_handler = logging.FileHandler(logfilename, mode='w', encoding='utf-8')
        f_format = logging.Formatter('%(asctime)s - %(threadName)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)
        logger.info('DuetLapse3 Version --- ' + str(duetLapse3Version))
        logger.info('Process Id  ---  ' + str(pid) )
        logger.info('-------------------------------------------------------------------------------\n')

    loggingset = True


def renamelogfile(thisDir): # called from createworkingDir 
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
        
        newlogfilename = thisDir + '.log'

        try:
            logger.debug('Renaming logfile to ' + newlogfilename)
            shutil.move(logfilename, newlogfilename)
        except shutil.Error as e:
            logger.info('Error on move of logfile ' + str(e))

        f_handler = logging.FileHandler(newlogfilename, mode='a', encoding='utf-8')
        f_format = logging.Formatter('%(asctime)s - %(threadName)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)
        logfilename = newlogfilename

####################################################
# Misc settings
####################################################
   
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
    global seconds, poll
        # Polling interval needs to be in integer multiple of mainLoopPoll
    if poll < minPoll:
        poll = minPoll
    multiplier,remainder = divmod(poll, mainLoopPoll)
    if remainder == 0: # No need to change
        pass
    else:
        poll = mainLoopPoll * multiplier # round down
    
    # Seconds needs to be an integer multiple of mainLoopPoll       
    if seconds != 0:
        if seconds < minseconds:
            seconds = minseconds
        multiplier,remainder = divmod(seconds, mainLoopPoll)    
        if remainder == 0: # No need to change
            pass
        else:
            seconds = mainLoopPoll * multiplier # round down  
        # poll needs to be lesser of poll and seconds.
        poll = min(poll, seconds) 
        # Check for dontwait
        if seconds > 0 and 'none' in detect:
            updateglobals('dontwait', 'True')       
      
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
        Model = loginPrinter()[0]
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
            printerVersion = getDuetVersion(Model)
            majorVersion = int(printerVersion[:1]) # use slicing

            if majorVersion >= 3:
                connectionState = True
                apiModel = Model # We have a good connection
                logger.info('###############################################################')
                logger.info('Connected to printer at ' + duet)
                logger.info('Using Duet version ' + printerVersion)
                logger.info('Using  API interface ' + apiModel)
                logger.info('###############################################################\n')
                return
            else:
                logger.info('###############################################################')
                logger.info('The printer at ' + duet + ' needs to be at version 3 or above')
                logger.info('The version on this printer is ' + printerVersion)
                logger.info('###############################################################\n')
                sys.exit(5)
    

def checkforConnection():
    global apiModel, connectionState, checkforconnectionState
    try:
        checkforconnectionState = 1
        connectionState = False
        elapsed = 0
        shortcheck = mainLoopPoll
        quickcheck = mainLoopPoll*4  # check up to 4 times
        longcheck = 3*60 # every 3 minutes
        checking = True
        logger.info('----------------  Waiting for printer to reconnect -----------------')
        while checking and terminateState != 1:
            if elapsed <= quickcheck: # Check every shortcheck
                model, code = loginPrinter(apiModel)
                if code != 200: # Still not connected
                    #terminate()
                    logger.debug('Retrying connection every ' + str(shortcheck) + ' seconds')
                    time.sleep(shortcheck)
                    elapsed = elapsed + shortcheck
                else:
                    checking = False
            else:  #  Check every longcheck
                model, code = loginPrinter(apiModel)
                if code != 200: # Still not connected
                    logger.debug('Retrying connection every ' + str(longcheck) + ' seconds')
                    time.sleep(longcheck)
                else:
                    checking = False

        apiModel = model
        connectionState = True
        logger.info('-----------------------  Reconnected to printer ----------------------')    
        startnextAction('reconnected')
        checkforconnectionState = -1
        return
    except Exception as e:
        logger.info('!!!!!#####!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN CHECK FOR CONNECTION -- ' + str(e))
        quit_forcibly()        


#####################################################
##  Utility Functions
#####################################################

def listTopDir():
    try:
        listdir = os.listdir(topDir)
    except FileNotFoundError as e:
        logger.info('--------------------------------- FATAL ERROR --------------------------------')
        logger.info('Trying to list dir -- ' + topDir + '\n')
        logger.info(str(e))
        sys.exit(1)
    return listdir

def make_archive(source):
    destination = source + '.zip'
    format = pathlib.Path(destination).suffix
    name = destination.replace(format,'')
    format = format.replace('.','')
    archive_from = os.path.dirname(source)
    archive_to = os.path.basename(source.strip(os.sep))
    try:
        shutil.make_archive(name, format, archive_from, archive_to)
        shutil.move('%s.%s' % (name, format), destination)
        msg = 'Zip processing completed'
        logger.info(msg)
    except Exception as msg1:
        msg = 'Error: There was a problem creating the zip file'
        msg = msg + str(msg1)
        logger.info(msg)
    return msg

def createVideo(directory):
    global makeVideoState
    makeVideoState = 1  # Can be called from makeVideo or directly from http server
    # loop through directory count # files and detect if Camera1 / Camera2
    logger.info('Create Video from ' + str(directory))
    if not os.path.isdir(directory):
        msg = 'Error: No permission or directory not found'
        logger.info(msg)
        makeVideoState = -1
        return msg

    # Scan the directory and count the number of images

    f1 = f2 = 0
    Cameras = []
    C1 = C2 = False

    try:
        listdir = os.listdir(directory)
    except FileNotFoundError as e:
        msg = 'Error: Could not list video directory'
        logger.info(msg)
        logger.info(str(e))
        return msg

    for fn in listdir:
        if fn.startswith('Camera1_') and fn.endswith('.jpeg'):
            C1 = True
            f1 += 1
        elif fn.startswith('Camera2_') and fn.endswith('.jpeg'):
            C2 = True
            f2 += 1
    
    if C1 is False and C2 is False:
        msg = 'Cannot create a video.\n\
              Are there any images captured?'
        logger.info(msg)
        makeVideoState = -1
        return msg

    if C1: Cameras.append('Camera1')
    if C2: Cameras.append('Camera2')

    for cameraname in Cameras:
        if cameraname == 'Camera1':
            frame = f1
        elif cameraname == 'Camera2':
            frame = f2

        if maxvideo > 0:
            if frame < maxvideo:
                thisfps = 1.0                         #  make it as long as we can     
            else:
                thisfps = float(frame/maxvideo)       #  set for  maxvideo duration
        else:
            thisfps = float(fps)                      #  set for fixed fps


        if frame/thisfps < minvideo:
            msg = 'Error: ' + cameraname + ': Cannot create video shorter than ' + str(minvideo) + ' second(s).\n Length would have been ' + str(frame/thisfps) + ' second(s).' 
            logger.info(msg)
            logger.info('frame = ' + str(frame) + ' thisfps = ' + str(thisfps) + ' fps = ' + str(fps) + ' maxvideo = ' + str(maxvideo) + ' minvideo = ' + str(minvideo))
            makeVideoState = -1
            return msg

        logger.info(cameraname + ': now making ' + str(frame) + ' frames into a video with fps = ' +str(thisfps))
        if 250 < frame:
            logger.info("This can take a while...")

        timestamp = time.strftime('%a-%H-%M', time.localtime())

        fn = directory + '_' + cameraname + '_' + timestamp + '.mp4'
        tmpfn = os.path.join(directory, '_tmpvideo.mp4')
        location = os.path.join(directory, cameraname + '_%08d.jpeg')

        if printState == 'Completed':
            threadsin = ''  #  Dont limit ffmpeg
            threadsout = ''  #  Dont limit ffmpeg
        else:
            threadsin = ' -threads 1 '
            threadsout = ' -threads 2 '

        cmd = 'ffmpeg' + threadsin + ffmpegquiet + ' -r ' + str(thisfps) + ' -i ' + location + ' -vcodec libx264 -y ' + threadsout + tmpfn + debug

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
            msg = ('!!!!!  There was a problem creating the video for '+cameraname+' !!!!!')
            logger.info(msg)
            if os.path.isfile(tmpfn): 
                try:
                    os.remove(tmpfn)
                except OSError as e:
                    logger.info('Error deleting file ' + str(e))
            makeVideoState = -1
            return msg
        else:
            try:
                shutil.move(tmpfn, fn)
                logger.info('Video processing completed for ' + cameraname)
                logger.info('Video is in file ' + fn)                
                msg = 'Video(s) successfully created'
            except shutil.Error as e:
                msg = 'Error on move of temp video file ' + str(e)
                logger.info(msg)
 
    makeVideoState = -1
    return msg


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
        if 'python' in p.name():  # Check all other python instances
            pidlist.append(str(p.pid))
    return pidlist


def getPidDirs():
    dirlist = []
    if os.path.isdir(topDir):
        for item in listTopDir():
            if os.path.isdir(os.path.join(topDir, item)):
                dirlist.append(item)

    return dirlist

def createworkingDir():
    global workingDirStatus, nextWorkingDir, pidIncrement
 
    try:
        os.mkdir(nextWorkingDir)
        logger.debug('Created working directory: ' + nextWorkingDir)
        renamelogfile(nextWorkingDir)  # change the logfle to match the working dir
        workingDirStatus = 0
    except OSError as e:
        logger.info('Could not create working directory ' + str(e))
        workingDirStatus = -1
    return nextWorkingDir

def renameworkingDir(thisDir):
    global workingDirStatus
    jobname = getDuet('Jobname from renameworkingDir', Jobname)

    if connectionState is False or jobname == '':
        logger.debug('jobname was not available')
        return thisDir
    #  Create a safe form of jobname
    _, jobname = os.path.split(jobname)  # get the filename less any path
    jobname = jobname.replace(' ', '_')  # prevents quoting of file names
    jobname = jobname.replace('.gcode', '')  # get rid of the extension
    jobname = jobname.replace(':', '_')  # replace any colons because Win does not like
    jobname = jobname.replace('(', '_')  # replace any ( because ffmpeg does not like    
    jobname = jobname.replace(')', '_')  # replace any ) because ffmpeg does not like
    jobname = jobname.replace('__', '_')  # replace and ugly double _ with single _
    if jobname.endswith('_'):
        jobname = jobname[:-1]           # get rid of the last character

    if thisDir.endswith(jobname): # No change
        workingDirStatus = 1
        return thisDir
    nextWorkingDir = thisDir + '_' + jobname

    try:
        shutil.move(thisDir, nextWorkingDir)
        logger.debug('Renaming working directory: ' + nextWorkingDir)
        renamelogfile(nextWorkingDir)  # change the logfle to match the working dir
        workingDirStatus = 1
    except shutil.Error as e:
        logger.info('Error on move of workingDir ' + str(e))
        workingDirStatus = 0
    return nextWorkingDir


def cleanupFiles(phase):
    global workingDirStatus, keepfiles
    logger.debug('*****  Cleaning up files for phase:  ' + phase + '  *****')
    pidlist = getRunningInstancePids()

    dirlist = listTopDir()

    # Make and clean up directorys.

    if phase == 'startup':
        if keepfiles: return

        for dirs in dirlist: #  Delete old dirs and files
            split_dirs = dirs.split("_", 1)
            dirpid = split_dirs[0]

            if dirpid not in pidlist:  # only if not running
                fn = os.path.join(topDir, dirs)
                if os.path.isdir(fn):  # a directory
                    deleteFileFolder(fn)
                elif (not keeplogs) and dirs.endswith('.log'):  # logfiles
                    deleteFileFolder(fn)

    elif phase == 'standby':  # deleted images directory will be recreated on first capture
        if workingDirStatus != -1:
            deleteFileFolder(workingDir)
            workingDirStatus = -1

    elif phase == 'restart':  # new image directory will be created on first capture
        pass

    elif phase == 'terminate':
        if keepfiles: return

        if deletepics:
            for dirs in dirlist:
                fn = os.path.join(topDir, dirs)
                if os.path.isdir(fn):
                    deleteFileFolder(fn)
                    workingDirStatus = -1
            # Assume sucess even if error from above
            workingDirStatus = -1
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
    global duetStatus
    # Checks to see if we should pause and reposition heads.
    # Do not pause until printing has completed layer 2.
    # This solves potential issues with the placement of pause commands in the print stream
    # Before or After layer change
    # As well as timed during print start-up

    if (layer < 1):  # Do not try to pause
        return
    
    duetStatus, _ = getDuet('Status from Check for Pause', Status)
    if connectionState is False or duetStatus == 'idle':
        return
    
    loopmax = 10  # sec
    loopinterval = 0.5  # sec
    loopcount = loopmax / loopinterval
    if pause == 'yes':  # DuetLapse is controlling when to pause
        logger.debug('Requesting pause via M25')
        sendDuetGcode(apiModel, 'M25')  # Ask for a pause
        loop = 0
        while True:
            time.sleep(loopinterval)  # wait and try again    
            duetStatus, _ = getDuet('Status check for pause = yes', Status)
            if connectionState is False:
                return
            if duetStatus == 'paused':
                break
            else:
                loop += 1
            if loop >= loopcount:  # limit the counter in case there is a problem
                logger.info('Timeout after ' + str(loopmax))
                logger.info('Target was: paused')
                logger.info('Actual was: ' + duetStatus)
                break

    if duetStatus == 'paused':
        if not movehead == [0.0, 0.0]:  # optional repositioning of head
            logger.debug('Moving print head to X{0:4.2f} Y{1:4.2f}'.format(movehead[0], movehead[1]))
            sendDuetGcode(apiModel, 'G0 X{0:4.2f} Y{1:4.2f}'.format(movehead[0], movehead[1]))
            loop = 0
            while True:
                time.sleep(loopinterval)  # wait and try again
                xpos, ypos, _ = getDuet('Position paused = yes', Position)
                if connectionState is False:
                    return
                if (abs(xpos - movehead[0]) < .05) and (
                        abs(ypos - movehead[1]) < .05):  # close enough for government work
                    break
                else:
                    loop += 1
                if loop >= loopcount:  # limit the counter in case there is a problem
                    logger.info('Timeout after ' + str(loopmax) + 's')
                    logger.info('Target X,Y: ' + str(movehead[0]) + ',' + str(movehead[1]))
                    logger.info('Actual X,Y: ' + str(xpos) + ',' + str(ypos))
                    break
        time.sleep(rest)  # Wait to let camera feed catch up

    return


def unPause():  # Only gets called if duetStatus = paused
    global duetStatus
    if connectionState is False: # This traps the call being made unnecessarily
        return
    #  duetStatus, _ = getDuet('Status from unPause', Status)
    # if connectionState is False: # Need to check after each getDuet
    #     return
    if duetStatus == 'paused':
        loopmax = 10 # sec
        loopinterval = 0.5 # sec  short so as to not miss start of next layer
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
            if loop >= loopcount:  # limit the counter in case there is a problem
                logger.info('Loop exceeded: Target was: unpause')
                break
    return


def onePhoto(cameraname, camera, weburl, camparam):
    global frame1, frame2, workingDir, camfile1, camfile2, lastImage, referer

    if workingDirStatus == -1: # Create as late as possible
        workingDir = createworkingDir()
        camfile1 = os.path.join(workingDir, 'Camera1_')

        camfile2 = os.path.join(workingDir, 'Camera2_')
    
    if workingDirStatus == 0: # Keep checking until jobname is known
        workingDir = renameworkingDir(workingDir)
        camfile1 = workingDir + '/Camera1_'
        camfile2 = workingDir + '/Camera2_'

    if cameraname == 'Camera1':
        frame1 += 1
        s = str(frame1).zfill(8)
        fn = camfile1 + s + '.jpeg'
    else:
        frame2 += 1
        s = str(frame2).zfill(8)
        fn = camfile2 + s + '.jpeg'
    if 'usb' in camera:
        cmd = 'fswebcam --quiet --no-banner ' + fn + debug

    if 'pi' in camera:
        cmd = 'raspistill -t 1 -w 1280 -h 720 -ex sports -mm matrix -n -o ' + fn + debug

    if 'stream' in camera:
        cmd = 'ffmpeg -threads 1' + ffmpegquiet + ' -y -i ' + weburl + ' -vframes 1 -threads 1 ' + fn + debug

    if 'web' in camera:
        # Only for use if the url delivers single images (not for streaming)
        # ? on use of --auth-no-challenge
        if debug:
            cmd = 'wget --auth-no-challenge -v -O ' + fn + ' "' + weburl + '" ' + debug
        else:   
            cmd = 'wget --auth-no-challenge -nv -O ' + fn + ' "' + weburl + '" ' + debug

    if 'other' in camera:
        cmd = eval(camparam)

    global timePriorPhoto1, timePriorPhoto2

    if runsubprocess(cmd) is False:
        logger.info('!!!!!  There was a problem capturing an image !!!!!')
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
        try:
           referer  # May not be defined yet
        except NameError:
            pass
        else:
            lastImage = 'http://' + referer + '?getfile=' + fn
        if cameraname == 'Camera1':
            timePriorPhoto1 = time.time()
            return
        else:
            timePriorPhoto2 = time.time()
            return

def oneInterval(cameraname, camera, weburl, camparam, finalframe = False):
    if connectionState is False:
        logger.debug('Bypassing oneInterval because of connectionState')
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

    if pause == 'yes' and zn < 1:  # Dont capture anything until first layers is done
        logger.debug('Bypassing onePhoto from oneInterval because -pause = ' + pause + ' and layer = ' +str(zn))
    else:    
        if 'layer' in detect and zn%numlayers == 0: #  Every numlayers layer
            if (not zn == zo1 and cameraname == 'Camera1') or (not zn == zo2 and cameraname == 'Camera2'):
                # Layer changed, take a picture.
                checkForPause(zn)
                logger.info('Layer - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after layer change')
                onePhoto(cameraname, camera, weburl, camparam)

        elif ('pause' in detect) and (duetStatus == 'paused'):
            checkForPause(zn)
            logger.info('Pause - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' at pause in print gcode')
            onePhoto(cameraname, camera, weburl, camparam)
        elif finalframe:
            # get a final frame
            checkForPause(zn)
            logger.info('finalframe - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after layer change')
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
    # Changes connectionState to False if there is a persistent fault
    global connectionState
    disconnected = 0
    getstatus = False
    while getstatus is False:
        #  The working code gets executed here
        logger.debug('Calling function ' + name + ' with ' + apiModel)

        if 'NoneType' in str(type(function)):
            result = function  # Function with variables
        else:
            result = function()   

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
        else:
            getstatus = True # We have a status

    connectionState = True
    return result


def urlCall(url, post):
    # Makes all the calls to the printer
    # If post is True then make a http post call
    timelimit = 5  # timout for call to return
    loop = 0
    limit = 2  # seems good enough to catch transients
    loginRetry = 0
    while loop < limit:
        error  = ''
        code = 9999
        logger.debug(str(loop) +' url: ' + str(url) + ' post: ' + str(post))
        try:
            if post is False:
                r = requests.get(url, timeout=timelimit, headers=urlHeaders)
            else:
                r = requests.post(url, data=post, headers=urlHeaders)
        except requests.ConnectionError as e:
            logger.info('Cannot connect to the printer\n')
            logger.debug(str(e))
            logger.debug('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n')
            error = 'Connection Error'
        except requests.exceptions.Timeout as e:
            logger.info('The printer connection timed out\n')
            logger.debug(str(e))
            logger.debug('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n')
            error = 'Timed Out'

        if error == '': # call returned something
            code = r.status_code
            if code == 200:
                return r
            elif code == 401: # Dropped session
                loginRetry += 1
                code = loginPrinter(apiModel)[1] # Try to get a new key
                if code == 200:
                    loop = 0
                    continue  # go back and try the last call
                else: # cannot login
                    if loginRetry > 1: # Failed to get new key
                        break
            # any other http error codes are to be handled by caller            
        time.sleep(1)
        loop += 1      # Try again
 
    # Call failed - Create dummy response
    class r:
        ok = False
        status_code = code
        reason = error
    return r

def loginPrinter(model = ''):
    global urlHeaders
    urlHeaders = {}
    logger.info('Logging in to Printer')

    if model == '' or model == 'rr_model':
        URL = ('http://' + duet + '/rr_disconnect') # Close any open session
        r = urlCall(URL,  False)
        URL = ('http://' + duet + '/rr_connect?password=' + password) # Connect with password
        r = urlCall(URL,  False)
        code = r.status_code
        if code == 200:
            j=json.loads(r.text)
            err = j['err']
            if err == 0:
                if j['apiLevel'] != None: # Check to see if in SBC emulation mode
                    if j['apiLevel'] == 1:
                        logger.debug('Connected but in emulation mode')
                    else: # in case standalone returns apiLevel: False in future
                        logger.debug('!!!!! Connected to printer Standalone !!!!!')
                        model = 'rr_model'
                else:
                    logger.debug('!!!!! Connected to printer Standalone !!!!!')
                    model = 'rr_model'
            elif err == 1:
                logger.info('!!!!! Standalone Password is invalid !!!!!')
                code = 403 # mimic SBC codes
            elif err == 2:
                logger.info('!!!!! No more Standalone connections available !!!!!')
                code = 503 # mimic SBC codes
        elif code == 404: # Ignore as it indicated Standalone was not there
            pass
        else:
            logger.info('!!!!!  Could not connect. code = ' + str(code) + ' reason = ' + r.reason + ' !!!!!')

    if model == '' or model == 'SBC':
        URL = ('http://' + duet + '/machine/disconnect') # Close any open session
        r = urlCall(URL,  False)
        URL = ('http://' + duet + '/machine/connect?password=' + password) # Connect with password
        r = urlCall(URL,  False)
        code = r.status_code
        if code == 200:
            logger.debug('!!!!! Connected to SBC printer !!!!!')
            j = json.loads(r.text)
            sessionKey = j['sessionKey']
            urlHeaders = {'X-Session-Key': sessionKey}
            model = 'SBC'
            #  Could not connect to printer   
        elif code == 403:
                logger.info('!!!!! SBC Password is invalid !!!!!')
        elif code == 503:
                logger.info('!!!!! No more SBC connections available !!!!!')
        elif code == 502:
                logger.info('!!!!!  Incorrect DCS version  !!!!!')
        else:
            logger.info('!!!!!  Could not connect.  Error code = ' + str(code) + ' !!!!!')
    
    return model, code    

def getDuetVersion(model):
    # Get the firmware
    if model == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=boards')
        r = urlCall(URL,  False)
        if r.status_code == 200:
            try:
                j = json.loads(r.text)
                version = j['result'][0]['firmwareVersion']
                return version
            except:
                logger.info('!!!!! Could not get standalone firmware version !!!!!')
        else:
            logger.info('!!!!! Error getting rr_model?key=boards code = ' + str(r.status_code) + '!!!!!') 

    if model == 'SBC':       
        URL = ('http://' + duet + '/machine/status')
        r = urlCall(URL,  False)
        if r.status_code == 200:
            try:
                j = json.loads(r.text)
                version = j['boards'][0]['firmwareVersion']
                return version
            except:
                logger.info('!!!!! Could not get SBC firmware version !!!!!')
        else:
            logger.info('!!!!! Error getting /machine/status code = ' + str(r.status_code) + '!!!!!')

    return 0  # Failed to determine API and firmware version

def Jobname():
    # Used to get the print jobname from Duet
    if apiModel == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=job.file.fileName')
        r = urlCall(URL,  False)
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
        URL = ('http://' + duet + '/machine/status')
        r = urlCall(URL,  False)
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
    global lastStatusCall
    lastStatusCall = time.time()
    # Used to get the status information from Duet
    status = display = ''
    if apiModel == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=state')
        while True: #  The max queue depth is 8 so we clear as many as we can in one go
            r = urlCall(URL,  False)
            if r.ok:
                try:
                    j = json.loads(r.text)
                    status = j['result']['status']
                    logger.debug('Status is ' + status)
                    message = ''
                    if j['result'].get('messageBox') != None:
                        if j['result']['messageBox'].get('message') != None:
                            message = j['result']['messageBox']['message']
                            seq = j['result']['messageBox']['seq']
                            if message != '' and seq != lastMessageSeq:
                                parseM291(message,seq)
                                continue
                            else:
                                break
                        else:
                            break
                    else:
                        break     
                except Exception as e:
                    logger.debug('Could not get Status')
                    logger.debug(e)

        return status, message        

    elif apiModel == 'SBC':
        URL = ('http://' + duet + '/machine/status')
        while True: #  The max queue depth is 8 so we clear as many as we can in one go
            r = urlCall(URL,  False)
            if r.ok:
                try:
                    j = json.loads(r.text)
                    status = j['state']['status']
                    logger.debug('Status is ' + status)
                    message = ''
                    if j['state'].get('messageBox') != None:
                        if j['state']['messageBox'].get('message') != None: 
                            message = j['state']['messageBox']['message']
                            seq = j['state']['messageBox']['seq']
                            if message != '' and seq != lastMessageSeq:
                                parseM291(message,seq)
                                continue
                            else:
                                break
                        else:
                            break
                    else:
                        break        
                except Exception as e:
                    logger.debug('Could not get Message')
                    logger.debug(e)

        return status, message

    return 'disconnected', ''

def Layer():
    # Used to get the the current layer
    if apiModel == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=job.layer')
        r = urlCall(URL,  False)
        if r.ok:
            try:
                j = json.loads(r.text)
                layer = j['result']
                if layer is None:
                    layer = -1
                logger.debug('Current Layer is ' + str(layer))
                return layer
            except Exception as e:
                logger.debug('Could not get Layer Info')
                logger.debug(e)

    elif apiModel == 'SBC':
        URL = ('http://' + duet + '/machine/status')
        r = urlCall(URL,  False)
        if r.ok:
            try:
                j = json.loads(r.text)
                layer = j['job']['layer']
                if layer is None:
                    layer = -1
                logger.debug('Current Layer is ' + str(layer))    
                return layer
            except Exception as e:
                logger.debug('Could not get Layer Info')
                logger.debug(e)

    return 'disconnected'


def Position():
    # Used to get the current head position from Duet
    if apiModel == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=move.axes')
        r = urlCall(URL,  False)
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
        r = urlCall(URL,  False)
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
        r = urlCall(URL,  False)
    else:
        URL = 'http://' + duet + '/machine/code'
        r = urlCall(URL,  command)

    if r.ok:
        return

def isPlugin(model):
    if model == 'rr_model':
        logger.debug('isPlugin ignored - shoud never be called')
    else:
        URL = ('http://' + duet + '/machine/status')
        r = urlCall(URL,  False)
        if r.ok:
            try:
                j = json.loads(r.text)
                if j['plugins'] != None:
                    if j['plugins']['DuetLapse3'] != None: # DuetLapse3 is registered plugin
                        if str(j['plugins']['DuetLapse3']['pid']) == pid: # Running as a plugin
                            logger.info('Running as a plugin')
                            return True
                logger.info('Not Running as a plugin')
            except Exception as e:
                logger.debug('Could not get plugin information')
                logger.debug(e)
    return False
            
def stopPlugin(model, command):
    # Used to send a command to Duet
    if model == 'rr_model':
        logger.info('Stop Plugin ignored - should never be called')
    else:
        URL = 'http://' + duet + '/machine/stopPlugin'
        r = urlCall(URL,  command)
        if r.ok:
            logger.info('Sent stopPlugin to plugin manager')
        else:    
            logger.info('stopPlugin failed with code: ' + str(r.status_code) + ' and reason: ' + str(r.reason))
    return

def makeVideo(directory, xtratime = False):  #  Adds and extra frame
    global makeVideoState, frame1, frame2
    try:
        makeVideoState = 1
        # Get a final frame
        # Make copies if appropriate

        if xtratime and extratime >= 1: #  Do not add images if called from snapshot or video
            logger.debug('For Camera1')
            oneInterval('Camera1', camera1, weburl1, camparam1, True)  # For Camera 1
            ## if extratime != 0 and frame1/fps > minvideo:
            if frame1 > 0:
                frame1 = copyLastFrame(camfile1, frame1)

            if camera2 != '':   #  Camera 2
                logger.debug('For Camera2')
                oneInterval('Camera2', camera2, weburl2, camparam2, True)
                ## if extratime != 0 and frame2/fps > minvideo:
                if frame2 > 0:
                    frame2 = copyLastFrame(camfile2, frame2)

        result = createVideo(directory)
        makeVideoState = -1
        return result
    except Exception as e:
        logger.info('!!!!!#####!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN MAKE VIDEO -- ' + str(e))
        quit_forcibly()        

def copyLastFrame(f, frame):  # Makes copies and updates frame counter
    logger.info('Copying last frame to extend video by ' +str(extratime) + ' seconds')
    fr = str(frame).zfill(8)
    sourcefile = f + fr + '.jpeg'
    copies = int(extratime)*int(fps)
    #  copies = extratime*fps
    logger.debug('Using file --- ' + sourcefile + ' to make ' + str(copies) + ' copies')
    for i in range(1, copies):
        nf = str(frame + i).zfill(8)
        targetfile = f + nf + '.jpeg'

        try:
            shutil.copy(sourcefile, targetfile)
        except shutil.Error as e:
            logger.info('Error on copy ' + str(e))
    return int(nf) # Must be an integer for later math

def restartAction():
        global workingDirStatus, pidIncrement, nextWorkingDir
        workingDirStatus = -1 # Force creation of a new workingDir
        setuplogfile() # Create a new log file
        startNow() # determine start state
        listOptions() # List the current values
        issue_warnings() # list any warnings about setting combinations
        startup() # Warp speed Mr Sulu

def terminate():
    global httpListener, listener, httpthread, terminateState, restarting, workingDirStatus
    # Force verbose messaging
    setdebug(True)

    terminateState = 1
    logger.info('Terminating')
    # Gracefully stop the captureLoop
    stopCaptureLoop()
    waitforcaptureLoop()

    #  Make sure video creation is complete
    logger.debug('Wait for video to complete')
    waitforMakeVideo()

    # Make sure anything called from nextAction is complete
    # This is more for log timing / sequencing 
    waitforNextAction()

    cleanupFiles('terminate')

    if restart:
        # wait for jobname to be reset
        jobname = getDuet('Jobname from terminate', Jobname)
        loopcounter = 0
        if jobname != '':
            logger.info('Waiting for printjob to complete')
        while jobname !='' and loopcounter < 30:  # Don't wait more than a minute
            time.sleep(2)
            loopcounter += 1
            jobname = getDuet('Jobname from terminate', Jobname)
        if loopcounter >= 30:
            logger.info('jobname was not reset')
        # ready to restart
        setdebug(verbose)        
        restarting = True    
        logger.info('----------')
        logger.info('RESTARTING')
        logger.info('----------')

        terminateState = -1
        restartAction()
    else:
        stopmainLoop()
        waitformainLoop()
        closeHttpListener()
        logger.info('Program Terminated')
        if isPlugin(apiModel):
            stopPlugin(apiModel, 'DuetLapse3')
        else:
            quit_forcibly()

def quit_sigint(*args):
    logger.info('Terminating because of Ctl + C (SIGINT)')
    quit_forcibly()

def quit_sigterm(*args):
    logger.info('Terminating because of SIGTERM')
    quit_forcibly()  

def quit_forcibly():
    global restart 
    restart = False
    logger.info('!!!!! Forced Termination !!!!!')
    os.kill(os.getpid(), 9)  # Brutal but effective

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
    refreshing =    '<h4>\
                    Status will update every 60 seconds\
                    </h4>'
    selectMessage = refreshing

    def shutdown(self):
        self.server._BaseServer__shutdown_request = True
        logger.debug('Sent shutdown request')

    def redirect_url(self, url):
        self.send_response(303)
        self.send_header('Location', url)
        self.end_headers()

    def _set_headers(self):
        #self.send_response(200)
        #self.send_header("Content-type", "text/html")
        self.send_response(200)
        self.send_header('Age', '0')
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', "text/html")
        self.end_headers()

    def _set_headers204(self):
        self.send_response(204)
        self.send_header("Content-type", "application/json")
        self.end_headers()

    def _refresh(self, message):
        content = f'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"><html><head><meta http-equiv="refresh" content="60"; http-equiv="Content-Security-Policy" content="frame-ancestors *:*"/></head><body>{message}</body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!

    def _no_refresh(self, message):
        content = f'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"><html><head><meta http-equiv="Content-Security-Policy" content="frame-ancestors *:*"/></head><body>{message}</body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!

    def _html(self, message):
        content = f'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"><html><head><meta http-equiv = "refresh" content = "15; http-equiv="Content-Security-Policy" content="frame-ancestors *:*"/; url = https://localhost:' + port + '" /></head><body>{message}</body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!

    def _redirect(self, url, message):
        content = f'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"><html><head><meta http-equiv = "refresh" content = "60; http-equiv="Content-Security-Policy" content="frame-ancestors *.*"/; url = ' + url + '" /></head><body>' + message + '</body></html>'
        return content.encode("utf8")  # NOTE: must return a bytes object!

    def display_controls(self):
        allowed_buttons = allowedNextAction(action)
        # start
        if 'start' in allowed_buttons:
            disable = ''
        else:
            disable = 'disabled'


        startbutton =   '<div class="inline">\
                        <button class="button" style="background-color:yellow" onclick="\
                        fetch(\'http://' + referer + '?command=start\');\
                        repeatDisplayStatus();\
                        " ' + disable + ' >Start</button>\
                        </div>'

        # standby
        if 'standby' in allowed_buttons:
            disable = ''
        else:
            disable = 'disabled'

        standby_msg =   'Standby.\\n\
                        Does NOT create a video.\\n\
                        All captured images will be deleted.'

        standbybutton = '<div class="inline">\
                        <button class="button" style="background-color:yellow" onclick="(async () => {\
                        let response = await fetch(\'http://' + referer + '?command=standby\');\
                        alert(\'' + standby_msg + '\');\
                        await displayControls();\
                        })()" ' + disable + ' >Standby</button>\
                        </div>'

        # pause
        if 'pause' in allowed_buttons:
            disable = ''
        else:
            disable = 'disabled'
        
        pausebutton =   '<div class="inline">\
                        <button class="button" style="background-color:pink" onclick="(async () => {\
                        let response = await fetch(\'http://' + referer + '?command=pause\');\
                        await displayControls();\
                        })()" ' + disable + ' >Pause</button>\
                        </div>'

        # continue
        if 'continue' in allowed_buttons:
            disable = ''
        else:
            disable = 'disabled'

        continuebutton =    '<div class="inline">\
                            <button class="button" style="background-color:pink" onclick="(async () => {\
                            let response = await fetch(\'http://' + referer + '?command=continue\');\
                            await displayControls();\
                            })()" ' + disable + ' >Continue</button>\
                            </div>'

        # restart
        if 'restart' in allowed_buttons:
            disable = ''
        else:
            disable = 'disabled'

        restart_msg =   'Restarting.\\n\
                        Will try to create a video.\\n\\n\
                        All captured images will be deleted.\\n\
                        Unless -keepfiles was set'

        restartbutton = '<div class="inline">\
                        <button class="button" style="background-color:yellow" onclick="(async () => {\
                        let response = await fetch(\'http://' + referer + '?command=restart\');\
                        alert(\'' + restart_msg + '\');\
                        await repeatDisplayStatus();\
                        })()" ' + disable + ' >Restart</button>\
                        </div>'

        # terminate
        terminatebutton =   '<div class="inline">\
                            <button class="button" style="background-color:orange" class="tablinks"onclick="displayTerminate(event)">Terminate</button>\
                            </div>'

        # hide buttons if option was set
        if hidebuttons:
            btnstring = ''
            for button in allowed_buttons:
                btn = button + 'button'
                btnstring = btnstring + eval(btn)
            buttons = btnstring + terminatebutton
        else:
            buttons = startbutton + standbybutton + pausebutton + continuebutton + restartbutton + terminatebutton

        return buttons

    def display_video(self):

        options =  '<form action="http://' + referer + '" onsubmit="setTimeout(function() {displayVideo();}, 1500)">\
                   <label for="fps">fps:</label>\
                   <input type="text" id="fps" name="fps" value=' + str(fps) + ' style="background-color:lime; width:30px; border:none" />\
                   <label for="minvideo">minvideo:</label>\
                   <input type="text" id="minvideo" name="minvideo" value=' + str(minvideo) + ' style="background-color:lime; width:30px; border:none"/>\
                   <label for="maxvideo">maxvideo:</label>\
                   <input type="text" id="maxvideo" name="maxvideo" value=' + str(maxvideo) + ' style="background-color:lime; width:30px; border:none"/>\
                   <br><br>\
                   <input type="submit" value="Update">\
                   </form>'

        if maxvideo > 0:
            if frame1 > maxvideo:
                videolength = 'Video will be ' + str(maxvideo) + ' seconds long'
            elif frame1 > minvideo:
                videolength = 'Video will be ' + str(frame1) + ' seconds long'
            else:
                videolength = 'Not enough images for video to be created'
        else:
            if frame1/fps > minvideo:
                videolength = 'Video will be ' + str(frame1/fps) + ' seconds long'
            else:
                videolength = 'Insufficient images for video to be created'

        options += '<br><b>' + videolength + '&nbsp;&nbsp;&nbsp;&nbsp;'

        # snapshot
        snapshotbutton =    '<div class="inline">\
                            <button class="button" style="background-color:yellow" onclick="(async () => {\
                            let promise = await fetch(\'http://' + referer + '?snapshot=true\');\
                            let result = await promise.text();\
                            alert(result);\
                            await displayVideo();\
                            })()">Snapshot</button>\
                            </div>'

        options += snapshotbutton

        return options

    def display_status(self):
        global lastImage
        localtime = time.strftime('%A - %H:%M', time.localtime())
        if zo1 < 0:
            thislayer = 'None'
        else:
            thislayer = str(zo1)

        txt = []
        #  Set style for 2 flex columns
        status =    '<style>\
                    * {box-sizing: border-box;}\
                    .column {float: left; width: 50%; padding: 10px;}\
                    .row:after {content: "";display: table;clear: both;}\
                    @media screen and (max-width: 400px) {.column {width: 100%;}}\
                    </style>'
                    
        status +=   '<div class="row">\
                    <div class="column">\
                    DuetLapse3 Version ' + str(duetLapse3Version) + '<br>\
                    Connected to printer at:  ' + str(duet) + ':' + str(port) + '<br><br>\
                    Process Id:  ' + str(pid) + '<br>\
                    Last Update:    ' + str(localtime) + '<br>\
                    Capture Status:= ' + str(printState) + '<br>\
                    DuetLapse3 State:= ' + str(action) + '<br>\
                    Duet Status:= ' + str(duetStatus) + '<br>\
                    Images Captured:= ' + str(frame1) + '<br>\
                    Current Layer:= ' + str(thislayer) + '<br>\
                    </div>\
                    <div class="column">'
        if lastImage != '':
            status += '<p><a href=' + lastImage + ' target="_blank"> <img src=' + lastImage + ' alt="No image available" width="400""></a></p>'
        else:
            status += 'Waiting for first image to be captured'

        status +=   '</div>\
                    </div>'
        return status

    def display_info(self):
        if workingDirStatus != -1:
            imagelocation = workingDir
        else:
            imagelocation = 'Waiting for first image to be created'


        info = '<div>\
                <b>Process Id:</b> ' + pid + '<br>\
                <b>Option Settings:</b><br>\
                <table style="width:auto">\
                <tr valign="top">'
        
        options = getOptions()

        count = 0
        for label, value in options.items():
            if label.startswith('#'):  #  Omit the section info
                continue
            if (count % 3) == 0: # 3 columns
                info += '</tr><tr valign="top">'
            info += '<td align="left"><b>' + label + ' </b><br>' + str(value) + '</td>'
            count += 1
        
        info += '</tr></table>\
                <br><hr /><b>Logs and Videos are located here:</b>&nbsp; &nbsp;' + topDir+ '\
                <br><hr /><b>Images are located here:</b>&nbsp; &nbsp;' + imagelocation + '\
                <br><hr /><b>The current logfile is:</b>&nbsp; &nbsp;' +logfilename + '\
                </div>'

        return info

    def display_page(self):   
        html_display_page = '<!DOCTYPE html>\
                        <html>\
                        <head>\
                        <metaname="viewport"content="width=device-width,initial-scale=1">\
                        <style>\
                        body{font-family:Arial;}\
                        /*Style the tab*/\
                        .tab{\
                        overflow:hidden;\
                        border:1px solid #ccc;\
                        background-color:#f1f1f1;\
                        }\
                        /*Style the buttons inside the tab*/\
                        .tab button{\
                        background-color:inherit;\
                        float:left;\
                        border:none;\
                        outline:none;\
                        cursor:pointer;\
                        padding:14px 16px;\
                        transition:0.3s;\
                        font-size:17px;\
                        }\
                        /*Change background color of buttons on hover*/\
                        .tab button:hover{\
                        background-color:#ddd;\
                        }\
                        \
                        /*Create an active/current tab link class*/\
                        .tab button.active{\
                        background-color:#ccc;\
                        }\
                        \
                        /*Style the tab content*/\
                        .tabcontent{\
                        padding:6px 12px;\
                        border:1px solid #ccc;\
                        background-color:lightblue;\
                        border-top:none;\
                        font-size:12px;\
                        }\
                        \
                        .button{\
                        height:auto;\
                        border-radius: 20px;\
                        }\
                        .inline{\
                        margin-left: 5px; margin-bottom:8px;\
                        display:inline-block;\
                        }\
                        \
                        form {\
                            display:grid;\
                            grid-template-columns: max-content max-content;\
                            grid-gap:10px;\
                        }\
                        form label {\
                           text-align:right;\
                        }\
                        </style>\
                        <script>\
                        document.addEventListener("visibilitychange", function() {\
                        if (!document.hidden){\
                            location.reload();\
                        }\
                        });\
                        let nIntervalId;\
                        function loadLasttab(evt) {\
                            clearInterval(nIntervalId);\
                            nIntervalId = undefined;\
                            let lastTab =sessionStorage.getItem("lastTab");\
                            let path =sessionStorage.getItem("path");\
                            if (path == null) {\
                                path = "true"\
                            }\
                            if (lastTab == "Status") {\
                                repeatDisplayStatus(event);\
                            } else if (lastTab == "Controls") {\
                                displayControls(event);\
                            } else if (lastTab == "Video") {\
                                displayVideo(event);\
                            } else if (lastTab == "Files") {\
                                displayFiles(event, path);\
                            } else if (lastTab == "Info") {\
                                displayInfo(event);\
                            } else {\
                                console.log("Default Tab");\
                                repeatDisplayStatus(event);\
                            }\
                        }\
                        function repeatDisplayStatus(evt){\
                            displayStatus();\
                            if (!nIntervalId) {\
                                nIntervalId = setInterval(displayStatus, ' + str(poll*1000) + ' );\
                            }\
                        }\
                        async function displayStatus(evt){\
                            sessionStorage.setItem("lastTab", "Status");\
                            let content = document.getElementById("tab-content");\
                            const getUrl = "http://' + referer + '/?displayStatus=true";\
                            let promise = await fetch(getUrl);\
                            let result = await promise.text();\
                            content.innerHTML = result;\
                        }\
                        async function displayControls(evt){\
                            sessionStorage.setItem("lastTab", "Controls");\
                            if (nIntervalId) {\
                                clearInterval(nIntervalId);\
                                nIntervalId = undefined;\
                            }\
                            let content = document.getElementById("tab-content");\
                            const getUrl = "http://' + referer + '/?displayControls=true";\
                            let promise = await fetch(getUrl);\
                            let result = await promise.text();\
                            content.innerHTML = result;\
                        }\
                        async function displayVideo(evt){\
                            sessionStorage.setItem("lastTab", "Video");\
                            if (nIntervalId) {\
                                clearInterval(nIntervalId);\
                                nIntervalId = undefined;\
                            }\
                            let content = document.getElementById("tab-content");\
                            const getUrl = "http://' + referer + '/?displayVideo=true";\
                            let promise = await fetch(getUrl);\
                            let result = await promise.text();\
                            content.innerHTML = result;\
                        }\
                        async function displayFiles(evt, path){\
                            sessionStorage.setItem("lastTab", "Files");\
                            sessionStorage.setItem("path", path);\
                            if (nIntervalId) {\
                                clearInterval(nIntervalId);\
                                nIntervalId = undefined;\
                            }\
                            let content = document.getElementById("tab-content");\
                            const getUrl = `http://' + referer + '/?displayFiles=${path}`;\
                            let promise = await fetch(getUrl);\
                            let result = await promise.text();\
                            content.innerHTML = result;\
                        }\
                        async function displayInfo(evt){\
                            sessionStorage.setItem("lastTab", "Info");\
                            if (nIntervalId) {\
                                clearInterval(nIntervalId);\
                                nIntervalId = undefined;\
                            }\
                            let content = document.getElementById("tab-content");\
                            const getUrl = "http://' + referer + '/?displayInfo=true";\
                            let promise = await fetch(getUrl);\
                            let result = await promise.text();\
                            content.innerHTML = result;\
                        }\
                        async function displayTerminate(evt){\
                            if (nIntervalId) {\
                                clearInterval(nIntervalId);\
                                nIntervalId = undefined;\
                            }\
                            let content = document.getElementById("tab-content");\
                            const getUrl = "http://' + referer + '/?displayTerminate=true";\
                            let promise = await fetch(getUrl);\
                            let result = await promise.text();\
                            content.innerHTML = result;\
                        }\
                        function imgTab(evt, src){\
                            window.open(src);\
                        }\
                        </script>\
                        </head>\
                        <body onload="loadLasttab()">\
                        <div class="tab">\
                        <button class="tablinks" onclick="repeatDisplayStatus(event)">Status</button>\
                        <button class="tablinks" onclick="displayControls(event)">Controls</button>\
                        <button class="tablinks" onclick="displayVideo(event)">Video</button>\
                        <button class="tablinks" onclick="displayFiles(event,\'true\')">Files</button>\
                        <button class="tablinks" onclick="displayInfo(event)">Info</button>\
                        </div>\
                        <div id="tab-content" class="tabcontent" style="width:inherit; max-height:200px; overflow-y:auto"></div>\
                        </body>\
                        </html>'
        return html_display_page

    def do_GET(self):
        try:
            global referer, refererip
            referer = self.headers['Host']  # Should always be there
            if not referer:  # Lets try authority
                referer = self.headers['authority']
                if not referer:
                    referer = 'localhost'  # Best guess if all else fails
            if ':' in referer:
                split_referer = referer.split(":", 1)
                refererip = split_referer[0]  # just interested in the calling address as we know our port number


            global action, selectMessage, refreshing

            if 'favicon.ico' in self.path:
                return

            query_components = parse_qs(urlparse(self.path).query)
            logger.debug('!!!!! http call: ' + str(query_components) + ' !!!!!')

            if query_components is None or len(query_components) == 0 :
                # Display Page
                self._set_headers()
                self.wfile.write(self._no_refresh(self.display_page()))
                return
            numQueries = len(query_components)
            queriesProcessed = 0

            for api, value in query_components.items():
                queriesProcessed += 1
                if len(value) == 1:
                    api_args = value[0]
                else:
                    api_args = value

                if not api in ['displayStatus', 'displayControls', 'displayVideo', 'displayFiles', 'displayInfo', 'displayTerminate', 'snapshot', 'command', 'delete', 'zip', 'video', 'terminate', 'fps', 'minvideo', 'maxvideo', 'getfile']:
                    msg = 'The API call "' + api + '" with value "' + api_args + '" is not supported\
                           <br><br>' + str(query_components) + '<br>'
                    self._set_headers()
                    self.wfile.write(msg.encode("utf8"))
                    return
                
                result= ''
                if api == 'displayStatus':
                    result = self.display_status()
                elif api == 'displayControls':
                    result = self.display_controls()
                elif api == 'displayVideo':
                    result = self.display_video()
                elif api == 'displayFiles':
                    result = self.display_files(api_args)
                elif api == 'displayInfo':
                    result = self.display_info()
                elif api == 'displayTerminate':
                    result = self.display_terminate_buttons()
                elif api == 'snapshot':
                    if workingDirStatus != -1:
                        result = startMakeVideo(workingDir, False, False) # False => no extratime and nothread therefore blocking
                    else:
                        result = 'There are no images captured yet.\\nTry again later.'
                elif api == 'video':
                        if api_args[1] == 'True':
                            xtratime = True
                        else:
                            xtratime = False
                        result = startMakeVideo(api_args[0], xtratime, False)  # False => nothread therefore blocking
                if result != '' and queriesProcessed == numQueries:  # return the display
                    self._set_headers()
                    self.wfile.write(result.encode("utf8"))
                    continue
                                
                # An API Call (No Content)  actions that do not change html
                if api == 'command':
                    self.update_command(api_args)
                elif api == 'delete':
                    deleteFileFolder(api_args)
                elif api == 'zip':
                    make_archive(api_args)
                elif api == 'terminate':
                    self.terminate_process(api_args)
                elif api == 'fps':
                    changeFps(api_args)
                elif api == 'minvideo':
                    changeMinvideo(api_args)
                elif api == 'maxvideo':
                    changeMaxvideo(api_args)
                # api calls that close the connection need to negate queriesProcessed
                elif api == 'getfile':
                    self.get_file(api_args)
                    queriesProcessed -= 1 #  get_file closes the connection
                if queriesProcessed == numQueries:
                    # Send a 204
                    self._set_headers204()

            return
        except Exception as e:
            if 'Broken pipe' in str(e):
                 logger.debug(str(e))           
            else:
                logger.info(str(e))

            try:
                self.wfile.close()
                self.wfile = None
            except:
                logger.info('Could not close wfile')
            return
    # End of do_Get

    
    def update_command(self, command):
        # start / standby
        if command == 'start':
            startnextAction(command)

        elif command == 'standby':  # can be called at any time
            startnextAction(command)
            while action != command: # Dont return until success
                pass

        # pause / continue
        elif command == 'pause':
            startnextAction(command)
            while action != command: # Dont return until success
                pass

        elif command == 'continue':
            startnextAction(command) # Dont return until success
            while action != command:
                pass

        elif command == 'restart':
            startnextAction(command)
            while action not in ['start', 'standby']: # Dont return until success
                pass

        elif command == 'terminate':  #command=terminate - backward compatible
            self.terminate_process('terminatehttp')
        return

    def log_request(self, code=None, size=None):
        pass

    def log_message(self, format, *args):
        pass

    def terminate_process(self, ttype):
        if ttype not in ['terminatehttp','terminateg', 'terminatef']:
           logger.info (ttype + ' invalid terminate requested')
           return

        if ttype == 'terminatehttp':
            startnextAction('completed')
        elif ttype == 'terminateg':
            startnextAction('terminate')
        elif ttype == 'terminatef':
            if isPlugin(apiModel):
                stopPlugin(apiModel, 'DuetLapse3')
            else:
                quit_forcibly()

        return

    def display_terminate_buttons(self):
        if restart:
           pageAction = 'repeatDisplayStatus();'
        else:
            pageAction = "document.body.innerHTML = \'\';"

        if workingDirStatus != -1:
            theDir = workingDir
        else:
            theDir = 'nodir'

        graceful_button =  '<td>\
                            <div class="inline">\
                            <button class="button" style="background-color:green" onclick="(async () => {\
                            let theDir = \'' + theDir + '\';\
                            console.log(theDir);\
                            if (theDir != \'nodir\') {\
                            alert(\'Graceful Terminate\\nWill attempt to create a video.\\nThis can take some time to complete.\');\
                            let fullname_encoded = encodeURIComponent(\'' + theDir.replace('\\', '\\\\') + '\');\
                            console.log(fullname_encoded);\
                            let promise = await fetch(`http://' + referer + '?video=${fullname_encoded}&video=True`);\
                            let result = await promise.text();\
                            alert(result);\
                            } else {\
                            alert(\'There are no images available.\\nNo video will be created.\');\
                            }\
                            fetch(\'http://' + referer + '?terminate=terminateg\');\
                            let restart = \'' + str(restart) +'\';\
                            if (restart == \'True\') {\
                            alert(\'Restart in Progress\');\
                            } else {\
                            alert (\'Shutting Down\');\
                            }\
                            ' + pageAction + '\
                            })()">Graceful Terminate</button>\
                            </div>\
                            </td>'

        forced_button =     '<td>\
                            <div class="inline">\
                            <button class="button" style="background-color:red" onclick="fetch(\'http://' + referer + '?terminate=terminatef\'); document.body.innerHTML = \'\';  alert(\'Forced Terminate in Progress\\nA video will NOT be created.\');">Forced Terminate</button>\
                            </div>\
                            </td>'

        return graceful_button + forced_button



    def display_files(self, path):
        if path == 'true':
            path = topDir

        if os.path.isdir(path):  # if its a dir then list it
            response = self.list_dir(path)
            return response
        else:
            return 'Requested path ' + path + ' is not a dir.'


    def get_file(self, path):
        if os.path.isfile(path):
            logger.debug('Trying to get file ' + path)
            fn = os.path.split(path)[1]
            ctype = self.guess_type(path)
            logger.debug(str(ctype))

            try:
                f = open(path, 'rb')
                fs = os.fstat(f.fileno())
            except:
                logger.info('Problem opening file: ' + path)

            try:
                self.send_response(200)
                self.send_header("Content-type", ctype)
                self.send_header("Content-Length", str(fs[6]))
                if fn.endswith('.log'):
                    self.send_header("Content-Disposition", 'attachment; filename=' + os.path.split(path)[1])  # must be downloaded
                else:
                    self.send_header("Content-Disposition", 'filename=' + os.path.split(path)[1]) #  Can be displayed in browser
                self.end_headers()
                self.copyfile(f, self.wfile)
                f.close()
            except ConnectionError:
                 # Note some browsers will block downloading a file more than once
                 # This resets the connection - one reason why we end up here
                logger.debug('Connection reset - normal if displaying file')
            except:
                logger.info('Error sending file')
        else:
            return 'Requested file ' + path + ' is not a file.'
    
    def list_dir(self, path):  # Copied from super class
        # Pass the directory tree and determine what can be done with each file / dir
        logger.debug('list_dir called with path = ' + path)

        jpegfiles = ['.jpeg', '.jpg']
        deletablefiles = ['.mp4','.zip', '.log'] #  Different to startDuetLapse3
        fullfilenames = []
        jpegfolder = []
        deletelist = []
      
        try:
            displaypath = urllib.parse.unquote(path, errors='surrogatepass')
        except UnicodeDecodeError:
            displaypath = urllib.parse.unquote(path)

        displaypath = html.escape(displaypath, quote=False)                   # this is to handle differences between html and OS representations

        # Parse the directory tree and determine what can be done with each file / dir
        try:
            listdir = os.listdir(path)
        except FileNotFoundError as e:
            logger.info('No files found: ' + str(e))
            response =  '<h4>\
                        There are no files or directories named '+displaypath+'<br>\
                        or  you do not have access permission\
                        </h4>'
            return response

        #  sort the list by datetime last modified
        listdir.sort(key=lambda fn: -os.path.getmtime(os.path.join(path, fn))) # Sort in reverse order
        
        dirPid = str(pid) + '_' + str(pidIncrement)  # get current pid + suffix

        for sfn in listdir:
            fn = os.path.join(path, sfn)
            fullfilenames.append(fn)
            fn_elements =  os.path.splitext(fn)
            ext = fn_elements[1]
            if os.path.isdir(fn):
                if dirPid not in fn:
                    deletelist.append(fn)
                    try:
                        fndir = os.listdir(fn)  #  Check the subdirectory
                    except FileNotFoundError as e:
                        logger.info('Subdirectory error:' + str(e))
                    for jp in fndir:  # break if we find one
                        jp_elements =  os.path.splitext(jp)
                        jpext = jp_elements[1]
                        if jpext in jpegfiles:
                            jpegfolder.append(fn)
                            break
            elif ext in deletablefiles:
                if sfn == 'startup.log':  # use the short filename
                    continue
                if dirPid not in fn:
                    if ext in ['mp4']:  # can delete mp4 from current print snapshot
                        continue
                    deletelist.append(fn)

        #  get the structure information

        if path == topDir:
            child_dir = False
        else:
            parentdir = os.path.split(path)[0]
            child_dir = True

        dir_table =     '<style>table {font-family: arial, sans-serif;border-collapse: collapse;}\
                        td {border:none; text-align:left; padding: 0px;}\
                        tr:nth-child(even) {background-color: #dddddd;}\
                        </style>\
                        <table>\
                        <tr><th style="width:400px"></th><th style="width:100px;"></th></tr>'

        # add parent dir to the html
        if child_dir:
            displayname = './'
            child = '<td><a href="%s">%s</a></td>' % ('javascript:displayFiles(event,\'' + parentdir.replace('\\', '\\\\') + '\')', html.escape(displayname, quote=False))
            dir_table += '<tr>' + child + '</tr>'


        # Add actions to files / dirs 
        for fullname in fullfilenames:          
            if os.path.islink(fullname):   # A link to a directory displays with @
                displayname = fullname + "@"

            displayname = os.path.split(fullname)[1]
 
            if os.path.isdir(fullname):
                row = '<td><a href="%s">%s</a></td>' % ('javascript:displayFiles(event,\'' + fullname.replace('\\', '\\\\') + '\')', html.escape(displayname, quote=False))
            else:
                row = '<td><a href="%s">%s</a></td>' % ('?getfile=' + urllib.parse.quote(fullname, errors='surrogatepass'), html.escape(displayname, quote=False))

            dir_table += '<tr>' + row

            deletebutton = zipbutton = vidbutton = ''

            if fullname in deletelist:
                deletebutton =  '<td>\
                                <div class="inline">\
                                <button class="button" style="background-color:red" onclick="(async () => {\
                                let fullname_encoded = encodeURIComponent(\'' + fullname.replace('\\', '\\\\') + '\');\
                                let response = await fetch(`http://' + referer + '?delete=${fullname_encoded}`);\
                                await displayFiles(event,\'true\');\
                                })()">Delete</button>\
                                </div>\
                                </td>'

                if fullname in jpegfolder:
                    zipbutton = '<td>\
                                <div class="inline">\
                                <button class="button" style="background-color:yellow" onclick="(async () => {\
                                let fullname_encoded = encodeURIComponent(\'' + fullname.replace('\\', '\\\\') + '\');\
                                let response = await fetch(`http://' + referer + '?zip=${fullname_encoded}`);\
                                await displayFiles(event,\'true\');\
                                })()">Zip</button>\
                                </div>\
                                </td>'

                    vidbutton = '<td>\
                                <div class="inline">\
                                <button class="button" style="background-color:green" onclick="(async () => {\
                                let fullname_encoded = encodeURIComponent(\'' + fullname.replace('\\', '\\\\') + '\');\
                                let promise = await fetch(`http://' + referer + '?video=${fullname_encoded}&video=False`);\
                                let result = await promise.text();\
                                alert(result);\
                                await displayFiles(event,\'true\');\
                                })()">Video</button>\
                                </div>\
                                </td>'
 
            dir_table += deletebutton + zipbutton + vidbutton + '</tr>'

        dir_table += '</table>'

        logger.debug('Finished parsing the files directory')
        return dir_table
    
        """
            end of requesthandler
        """

def changeFps(thisfps):
    global fps
    try:
        thisfps = int(thisfps)
        fps = max(1, thisfps)
        logger.info('-fps changed to: ' + str(fps))
    except ValueError as e:
        logger.info('Error changing fps: ' + str(e))

def changeMinvideo(thisminvideo):
    global minvideo
    try:
        thisminvideo = int(thisminvideo)
        minvideo = max(1,thisminvideo)
        logger.info('-minvideo changed to: ' + str(minvideo))
    except ValueError as e:
        logger.info('Error changing minvideo: ' + str(e))

def changeMaxvideo(thismaxvideo):
    global maxvideo
    try:
        thismaxvideo = int(thismaxvideo)
        maxvideo = max(0, thismaxvideo)
        logger.info('-maxvideo changed to: ' + str(maxvideo))
    except ValueError as e:
        logger.info('Error changing maxvideo: ' + str(e))

def deleteFileFolder(fname):
    fn = pathlib.Path(fname)  #  fn is a pathlib object

    if fn.exists():
        def remove_readonly(func, path, exc_info):
            if func not in (os.unlink, os.rmdir) or exc_info[1].winerror != 5:
                raise exc_info[1]
            os.chmod(path, stat.S_IWRITE)
            func(path)

        if fn.is_file():
            try:
                fn.unlink()
                logger.debug('Deleted file ' + fname)
            except Exception as e:
                logger.info('Error deleting file ' + str(e))
        elif fn.is_dir():
                shutil.rmtree(fn, onerror=remove_readonly)
    return


def allowedNextAction(thisaction):
    if thisaction == 'standby':
        return ['start']
    elif thisaction == 'pause':
        return ['standby', 'continue', 'restart']
    elif thisaction == 'restart':
        if standby:
            return ['start']
        else:
            return ['standby', 'pause', 'restart']
    else:
        return ['standby', 'pause', 'restart']


def startHttpListener():
    global listener
    try:
        listener = ThreadingHTTPServer((host, port), MyHandler)
        threading.Thread(name='httpServer', target=listener.serve_forever, daemon=False).start()  #Avoids blocking
        logger.info('##########################################################')
        logger.info('***** Started http listener *****')
        logger.info('##########################################################\n')
    except Exception as e:
        if 'Errno 98' in e:
            logger.debug('http listener is already running')
        else:
            logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  There was a problem starting the http listener !!!!!!!!!!!!!!!!!!!!!')
            logger.info(e)
            sys.exit(1)


def closeHttpListener():
    global listener
    try:
        listener.shutdown()
        logger.debug('!!!!! http listener stopped  !!!!!')
    except Exception as e:
        logger.debug('Could not terminate http listener')
        logger.debug(e)


def execRun(displaymessage):
        cmd = displaymessage.split(execkey)[1].strip()
        logger.info('!!!!!  Make call to execute !!!!!')
        logger.info(cmd)
        subprocess.Popen(cmd, shell=True, start_new_session=True)  # run the program


###################################
#  Thread and Function Controls
##################################
# Threads and blocking functions have tri-states
# -1 is stopped
# 0 is request to stop
# 1 is running

def startCaptureLoop():
    #  global captureLoopState
    captureLoopState = 1

def stopCaptureLoop():
    global captureLoopState
    if captureLoopState == 1:
        captureLoopState = 0  # Signals capture loop to stop

def waitforcaptureLoop():
    global captureLoopState
    if captureLoopState == -1:
        logger.debug('captureLoop is not running')
        return
    loopcounter = 0
    while captureLoopState != -1 and loopcounter < poll*3:  # wait for up to 3 poll intervals
        logger.debug('********* captureLoopState is ' + str(captureLoopState) + ' - Waiting to complete *********')
        time.sleep(poll/4) # Check 4 times per poll interval
        loopcounter += 1
    if captureLoopState != -1:
        captureLoopState = -1  # Forced
        logger.debug('Timed out trying to exit captureLoop')


def startmainLoop():
    #  global mainLoopState
    if mainLoopState == 1 or terminateState == 1:  #  Already running so don't start
        return
    threading.Thread(name='mainLoop', target=mainLoop, args=(), daemon=False).start()

def stopmainLoop():
    global mainLoopState
    if mainLoopState == 1:
        mainLoopState = 0  # Signals capture thread to shutdown

def waitformainLoop():
    global mainLoopState
    if mainLoopState == -1:
        logger.debug('mainLoop is not running')
        return
    loopcounter = 0
    while mainLoopState != -1 and loopcounter < mainLoopPoll*3:  # wait for up to 3 poll intervals
        logger.debug('********* mainLoopState is ' + str(mainLoopState) + ' - Waiting to complete *********')
        time.sleep(mainLoopPoll/4) # Check 4 times per poll interval
        loopcounter += 1
    if mainLoopState != -1:
        mainLoopState = -1  # Forced
        logger.debug('Timed out trying to exit mainLoop')


def startnextAction(command): # Does not run in a loop
    if terminateState == 1: # Block it if terminating
        return
    waitforNextAction()  
    threading.Thread(name='nextAction', target=nextAction, args=(command,), daemon=False).start()


def waitforNextAction():
    if nextActionState == -1:
        logger.info('nextAction is available')
        return
    while nextActionState != -1:  # Only one thread at a time may cause delay in http page update
        logger.debug('********* nextActionState is ' + str(nextActionState) + ' - Waiting to complete *********')
        time.sleep(1)

    logger.debug('nextaction is ready')
    

def startcheckforConnection():
    if checkforconnectionState == 1 or terminateState == 1:  #  Already running or don't start
        return
    threading.Thread(name='checkforConnection', target=checkforConnection, args=(), daemon=False).start()

def terminateThread(): # Can only be run once - but called as a thread to allow other threads to finish
    if terminateState == 1: #    Already Terminating
        return
    threading.Thread(name='terminate', target=terminate, args=(), daemon=False).start()


def waitforMakeVideo():
    global makeVideoState
    while makeVideoState >= 0: # wait till its completed
        time.sleep(mainLoopPoll)  # Makevideo is fairly slow
        logger.debug('********* Waiting for makeVideo thread to finish *********')
    logger.debug('makeVideo is not running')


def startMakeVideo(directory, xtratime = False, thread = True): # Does not run in a loop - so we block it before running it
    if terminateState == 1: # Block it if terminating
        return 'Cannot create video when Terminating'
    waitforMakeVideo()
    if thread:      
        threading.Thread(name='makeVideo', target=makeVideo, args=(directory,), daemon=False).start()
        return
    else:
        return makeVideo(directory, xtratime)


###################################
#  Main Control Functions
###################################

def mainLoop():
    # Used for handling M291 Messages
    # Runs continously except during terminate processing
    global mainLoopState, action, duetStatus, lastCaptureLoop, lastStatusCall
    duetStatus = 'unknown'
    try:

        if connectionState is False:
            return

        mainLoopState = 1 # Running
        logger.info('###########################')
        logger.info('Starting mainLoop')
        logger.info('###########################\n')
        while mainLoopState == 1 and terminateState != 1 and connectionState:  # Setting to 0 stops
            if time.time() >= lastStatusCall + mainLoopPoll:  # within 30 seconds
                duetStatus, _ = getDuet('Status from mainLoop', Status)
            if time.time() >= lastCaptureLoop + poll:
                captureLoop()
            if mainLoopState == 1:
                time.sleep(mainLoopIterate)
        mainLoopState = -1 # Not Running
        return
    except Exception as e:
        logger.info('!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN MAIN LOOP -- ' + str(e))
        quit_forcibly()

def stateMachine(currentState):
    newState = currentState
    if currentState == 'Waiting':
        if duetStatus == 'processing' or dontwait or (duetStatus == 'paused' and detect != 'none'):
            newState = 'Capturing'
    elif currentState == 'Capturing':
        if duetStatus == ('idle' and lastDuetStatus == 'processing') or terminateState == 1:
            newState = 'Completed'

    if newState != currentState:
        logger.info('****** Print State changed to: ' + newState + ' *****')
    return newState        

def captureLoop():  # Single instance only
    global printState, lastPrintState, duetStatus, captureLoopState, lastDuetStatus, lastCaptureLoop

    if connectionState is False or captureLoopState == 0 or action == 'standby':
        logger.debug('No Capture needed')
        printState = 'Waiting'
        captureLoopState = -1
        lastCaptureLoop = time.time()
        return

    try:
        captureLoopState = 1

        if duetStatus != lastDuetStatus:
            logger.info('****** Duet status changed to: ' + str(duetStatus) + ' *****')

        printState = stateMachine(printState)
        
        if printState == 'Capturing':
            logger.debug('Calling oneInterval for Camera 1')
            oneInterval('Camera1', camera1, weburl1, camparam1)
            if camera2 != '':
                logger.debug('Calling oneInterval for Camera 2')
                oneInterval('Camera2', camera2, weburl2, camparam2)
            duetStatus, _ = getDuet('Capture Loop pause check', Status)

            if duetStatus == 'paused' and (pause == 'yes' or detect == pause): # will be ignored is manual pause
                unPause()  # Nothing should be paused at this point

            # Check for latest state to avoid polling delay
            printState = stateMachine(printState)

        if printState == 'Completed':
            logger.info('Print Job Completed')
            printState = 'Waiting'
            # use a thread here as it will allow this thread to close.
            startnextAction('completed')
            logger.info('Exiting captureLoop')  
    except Exception as e:
        logger.info('!!!!!#####!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN CAPTURE LOOP -- ' + str(e))
        quit_forcibly()
        
    lastPrintState = printState
    lastDuetStatus = duetStatus
    lastCaptureLoop = time.time()
    captureLoopState = -1  # not running           

def nextAction(nextaction):  # can be run as a thread
    global action, printState, captureLoopState, lastaction, logger, nextActionState, standby, mainLoopState, restart
    if nextActionState == 0:
        logger.debug('nextAction stopped')
        nextActionState = -1
        return

    try:
        logger.info('++++++ ' + nextaction + ' state requested ++++++')
        # All nextactions need the capture thread to be shut down
        logger.debug('nextAction requested stopCaptureLoop')
        stopCaptureLoop()
        waitforcaptureLoop()
        logger.debug('nextAction satisfied waitforCaptureLoop')

        # This section needs to ge first as it checks for reconnection after network issue
        if nextaction == 'waitforconnection': # Go into connection check loop
            logger.info('nextAction waiting for lost connection')
            startcheckforConnection() 
            nextActionState = -1
            return
        elif nextaction == 'reconnected':
            startmainLoop() # restart the main loop
            time.sleep(mainLoopPoll) # Give the mainloop time to get next status
            nextaction = lastaction
            logger.info('nextAction resuming after reconnect target = ' + nextaction)

        if connectionState is False: #traps any requests during a disconnect
            nextActionState = -1
            logger.debug('nextaction aborted because connectionState is False')
            return

        nextActionState = 1
        action = nextaction  # default

        # This test is positionally sensitive
        if nextaction == 'completed':  # end of a print job
            printState = 'Completed'  # Update may have come from M117
            if novideo:
                logger.info('Video creation was skipped')
            else:
                if workingDirStatus != -1:  startMakeVideo(workingDir, True)  # Add extratime if appropriate
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

        elif nextaction == 'restart':
            if novideo:
                logger.info('Video creation was skipped')
            else:
                if workingDirStatus != -1:  startMakeVideo(workingDir, True) # Add extratimeif appropriate
                waitforMakeVideo() # Wait until done before deleting files
            restartAction()
            
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
            lastaction
            lastaction = action
        except NameError:
            lastaction = action
        logger.debug('nextAction exiting normally')
        nextActionState = -1
        return
    except Exception as e:
        logger.info('!!!!!#####!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN NEXT ACTION -- ' + str(e))
        quit_forcibly()

###################################
#  Utility Functions
###################################


def parseM291(displaymessage,seq):
    global action, lastMessageSeq
    logger.debug('Parsing message = ' + displaymessage + ' with seq # = ' +str(seq))
    if seq == lastMessageSeq:
        return
    
    lastMessageSeq = seq

    displaymessage = displaymessage.strip() # get rid of leading / trailing blanks

    if displaymessage.startswith('DuetLapse3.'):
        #  sendDuetGcode(apiModel,'M292%20P0%20S' + str(seq)) #  Clear the message
        sendDuetGcode(apiModel,'M292 P0 S' + str(seq)) #  Clear the message
        logger.debug('Cleared M291 Command: ' + displaymessage + ' seq ' + str(seq))

        nextaction = displaymessage.split('DuetLapse3.')[1].strip()

        if nextaction == action: #  Nothing to do
            logger.info('Already in ' + action + ' state')
            return

        if nextaction == 'graceful':
            startnextAction('completed')
        elif nextaction == 'forced':
            quit_forcibly()
        elif nextaction in allowedNextAction(action) or nextaction == 'completed':
            logger.debug ('M291 sending to startnextAction: ' + nextaction)
            startnextAction(nextaction)
        elif nextaction.startswith('snapshot'):
            if workingDirStatus != -1:
                startMakeVideo(workingDir, False, False)
        elif nextaction.startswith('change.'):
            command = nextaction.split('change.')[1]
            changehandling(command)
        else:
            logger.info('The requested action: ' + nextaction + ' is not available at this time')
            logger.info('The current state is: ' + action)

    elif execkey != '' and displaymessage.startswith(execkey):
        # sendDuetGcode(apiModel,'M292%20P0%20S' + str(seq)) #  Clear the message
        sendDuetGcode(apiModel,'M292 P0 S' + str(seq)) #  Clear the message
        logger.debug('Cleared M291 execkey: ' + displaymessage + ' seq ' + str(seq))
        displaymessage = urllib.parse.unquote(displaymessage)
        execRun(displaymessage) # Run the command 
    return

def changehandling(command):
    global logger
    command = command.replace(' ','') # Make sure it is well formed
    changevariables = ['verbose', 'seconds', 'poll', 'detect', 'movehead', 'dontwait', 'pause', 'restart','standby', 'novideo', 'keepfiles','minvideo','maxvideo', 'extratime', 'fps', 'rest',  'execkey']
    variable = command.split('=')[0]
    value = command.split('=')[1]
    if variable in changevariables:
        logger.debug('Changing variable with: ' + command)
        if variable == 'verbose' and value in ['True', 'False']:
            updateglobals(variable, value)
            setdebug(verbose)
        elif variable == 'seconds':
            ## if int(value) >= minseconds or int(value) == 0:
            updateglobals(variable, value)
            poll_seconds()
        elif variable == 'poll':
            ## if int(value) >= minPoll:
            updateglobals(variable, value)
            poll_seconds()
        elif variable == 'detect' and value in ['layer', 'pause', 'none']:
            command = "detect='" + value + "'"
            updateglobals(variable, value)
        elif variable == 'pause' and value in ['yes', 'no']:
            updateglobals(variable, value)
        elif variable in ['restart', 'standby', 'novideo', 'keepfies'] and value in ['True', 'False']:  # Booleans
            updateglobals(variable, value)
        elif variable == 'movehead':
            if ',' in value: # Convert to list of integers, otherwise ignore
                v = value.split(',')
                v0 = int(v[0])
                v1 = int(v[1])
                value = []
                value = str([v0, v1])
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
        elif 'list' in vartype:
            convert = 'list'
        elif val in globals() or 'str' in vartype:  # val cannot be a globals value
            val = '"' + val + '"' # force the string literal
            convert = 'str'
        else:
            logger.debug(var + ' is a global of type ' + vartype + ' will force to string')
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
        logger.info('unknown type. No change on ' + var)
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
        logger.info('or M291 P"DuetLapse3.start" S2  sent as gcode')
        logger.info('##########################################################\n')

    logger.info('##########################################################')
    logger.info('Video will be created when printing ends')
    logger.info('or if requested from the UI or M291 "DuetLapse3.completed" S2')
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

    if httpListener and restarting is False:
        startHttpListener()

    checkforPrinter()  # Needs to be connected before mainloop

    startmainLoop()

    logger.info('Initiating with action set to ' + action)
    nextAction(action)

def main():
    # Allow process running in background or foreground to be forcibly
    # shutdown with SIGINT (kill -2 <pid> or SIGTERM)
    signal.signal(signal.SIGINT, quit_sigint) # Ctrl + C
    signal.signal(signal.SIGTERM, quit_sigterm)
    # Globals
    # Set in startup code
    global httpListener, win, pid, action, apiModel, workingDir, workingDirStatus
    global connectionState, restarting

    # Status flag for threads
    global nextActionState, makeVideoState, captureLoopState, mainLoopState, terminateState, checkforconnectionState
    nextActionState = captureLoopState = makeVideoState = mainLoopState = terminateState = checkforconnectionState =  -1  #  All set as not running
    connectionState = restarting = False
    workingDirStatus = -1

    # timers
    global mainLoopPoll, minseconds, minPoll, mainLoopIterate
    mainLoopPoll = 5 # seconds
    mainLoopIterate = mainLoopPoll/3
    minPoll = 10  # seconds
    minseconds = 20  # seconds


    # Initial time for mainLoop events
    global lastCaptureLoop, lastStatusCall
    lastCaptureLoop = time.time()
    lastStatusCall = 0

    # logical state on start is unknown
    global lastDuetStatus, lastPrintState
    lastPrintState = lastDuetStatus = 'unknown' 

    # SBC session key
    global urlHeaders
    urlHeaders = {}

    # Keep track of M291 messages
    global lastMessageSeq
    lastMessageSeq = 0

    # Allowed Commands
    commands = ['start','standby','pause','continue', 'restart', 'terminate']
 
    
    httpListener = False  # Indicates if an integral httpListener should be started
    win = False  # Windows OS
    pid = ''  # pid for this instance - used for temp filenames

    apiModel = ''

    init()
    listOptions()
    issue_warnings()
    port_ok = checkforvalidport() # Exits if invalid
    startMessages()
    startup()

###########################
# Program  begins here
###########################

if __name__ == "__main__":  # Do not run anything below if the file is imported by another program
    
    main()