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
# Cameras must be network reachable http cameras, with a snapshot url or an MJPEG stream url.
# The Duet printer must be RepRap firmware V3 and must be network reachable.
#
#
"""

import json
import os

def _plugin_version():
    # The version from the plugin manifest - installed by DSF as plugins/<id>.json, or plugin.json in the source tree
    here = os.path.dirname(os.path.abspath(__file__))
    for manifest in (os.path.join(here, '..', '..', 'duetLapse3.json'), os.path.join(here, '..', 'plugin.json')):
        try:
            with open(manifest, encoding='utf-8') as f:
                return json.load(f)['version']
        except (OSError, ValueError, KeyError):
            continue
    return 'unknown'

duetLapse3Version = _plugin_version()

"""
CHANGES
 Fixed snapshot when called from gcode
 Added second variable to video api --> xtratime
 Fixed calculation type error on extratime
 rationalized timers
 added throttle for status calls
 changed M117 messages to M291
 5.1.1
 Refreshes tab on regaining focus from browser
 Changed G1 to G0 in movehead
 5.2.0
 Process all M291 messages without delay
 Refactored loop control to prevent thread blocking
 Prevent first layer capture if -pause yes
 Added -password
 5.2.1
 Changed background tab color - better for dark theme
 5.2.2
 Fixed bug in -pause layer detection
 Added wait loop before restart to ensure previous job had finished
 fixed a timing thing dependent on when "Complete" sent from finish gcode
 5.2.3
 Fixed bug caused by calling unpause inappropriately
 5.2.4
 Added emulation mode check to support V3.5
 Added stopPlugin call to plugin manager
5.3.0
Added -numlayers to enable capture every nth layer
Changed firmware version to use ['boards'][0]['firmwareVersion']
Displayed password as 'Default' or '*******'
5.3.1
removed port number from connection status in UI
added explicit version check
5.3.2
Added -simulate mode for testing
Fixed possible race condition in graceful_termination
Fixed problem from 5.3.1 in statemachine
Removed M291 and M292 message system - too complicated
Added custom M3291 queueing mechanism
Added -M3291 option to allow different Mcode name
5.3.3
reenabled connection retry (accidentally bypassed)
added 127.0.0.1 replacement for url calls if plugin
5.3.4
Added check for version returning None.
5.3.5 and 5.3.6 were cosmetic
5.3.7
Changed logic in runsubprocess for determining success (stdout inconsistent)
Added 10s timeout to wget commands.  Accidental connection to stream will not return
changed ffmpeg image capture to use -frames:v 1 -update true - should be more efficient
removed terminate button when using SBC
added argument -# to allow comments in config file
6.0.0
Renamed to duetLapse3 (plugin id, files, config folder and route)
Settings are read from duetLapse3.json - no command line options (argparse removed, including -file)
Argument 1 is the folder for duetLapse3.json and duetLapse3.log - default is the program's folder
One logfile (duetLapse3.log) for the whole run, instead of a logfile for each print job
basedir blank = the settings folder (argument 1, or the program's folder) - the plugin's images are no longer inside the plugin folder
instances = oneip now means one instance per settings folder
Added a Config tab to view and change duetLapse3.json
ffmpeg: computed thread limit (ffmpegthreads, 0 = automatic), low priority (nice), -preset veryfast, -pix_fmt yuv420p, no shell
Added a Cameras tab - the camera urls, with a preview of each.  Saved urls are used straight away
The Video tab shows the Video and Overrides settings - saved to duetLapse3.json and used straight away
If port = 0 (or the port is in use) a free port is selected
The ip address in use is saved to duetLapse3.json and published to DWC as plugin data
The web server always runs
Removed the firmware version check
Version is read from the plugin manifest
Shared state moved to state.py, logging to logger_module.py, html to www/, printer communication to duet_printer.py
Printer status, layer, job name and position come from one object model read (shared for up to 1 second)
Standalone: one rr_model?flags=d99fn read per poll - job and global only re-read when their seqs counter changes
Fixed M3291 gcode messages not working on standalone printers (global was never read)
Fixed standalone gcode not being url encoded
duet (printer address, blank = this computer) and duetport (blank or 0 = 80) - host removed, the page listens on every address
SBC: the object model is kept up to date by DSF's WebSocket (as DWC does) - http is used when it is not connected
gcode commands accept duetLapse3. or DuetLapse3. (any case)
Web server is now FastAPI / uvicorn - the routes are in routes.py
New URLs for the page and API (/tab/..., /command/..., etc) - the older ?<api>=<value> URLs still work
Fixed Continue never returning (and using a cpu) when sent from the page
Fixed terminate hanging if another python process ended at the same time
Only http cameras are supported: -weburl1 (and optionally -weburl2) is a snapshot or MJPEG stream url
Images are captured in python - wget, fswebcam and raspistill are no longer used
Removed USB and Pi camera support, ffmpeg capture of streams (RTSP / H.264) and -camera1, -camera2, -camparam1, -camparam2
"""

import subprocess
import sys
import platform
import time
import socket
import threading
import psutil
import shutil
import pathlib
import stat
import signal
import base64
import urllib.parse

import state  # Shared state - always use state.<name>
import camera
import logger_module
from logger_module import logger, currentFuncName
import duet_printer  # Communication with the printer
from duet_printer import (getDuet, loginPrinter, getDuetVersion, Jobname, Status, Layer, Position,
                          sendDuetGcode, isPlugin, stopPlugin, publishUiAddress)



def setstartvalues():
    logger.debug('*****  Initializing state and counters  *****')
    state.printState = 'Waiting'
    stopCaptureLoop()
    state.duetStatus = 'Printer is not connected'

    # initialize timers
    state.timePriorPhoto1 = time.time()
    state.timePriorPhoto2 = time.time()

    # frame counters and layer (zo) state
    state.frame1 = 0 # Camera1
    state.zo1 = -1  
    state.frame2 = 0 # Camera2
    state.zo2 = -1 

    # last image captured
    state.lastImage = ''

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


####################################################
# Settings - read from duetLapse3.json
####################################################

configFileName = 'duetLapse3.json'
logFileName = 'duetLapse3.log'

# Every setting and its default.  The type of the default is the type of the setting.
# The sections match duetLapse3.json - they are only for readability
DEFAULTS = {
    'Simulate': {'simulate': 'off'},
    'Environment': {'duet': '', 'duetport': 80, 'password': 'reprap', 'basedir': '', 'poll': 12,
                    'instances': 'single', 'nolog': False, 'verbose': False, 'keeplogs': False, 'novideo': False,
                    'deletepics': False, 'maxffmpeg': 2, 'keepfiles': False},
    'Execution': {'dontwait': False, 'seconds': 0, 'detect': 'layer', 'pause': 'no', 'numlayers': 1,
                  'movehead': [0, 0], 'rest': 1, 'standby': False, 'restart': False},
    'Camera': {'weburl1': '', 'weburl2': ''},
    'Video': {'extratime': 0, 'fps': 10, 'minvideo': 5, 'maxvideo': 0, 'ffmpegthreads': 0},
    'Overrides': {'vidparam1': '', 'vidparam2': ''},
    'UI': {'port': 0, 'ip': '', 'hidebuttons': False},
    'Special Functions': {'execkey': '', 'M3291': 'M3291'},
}
CHOICES = {'simulate': ['off', 'all', 'printer', 'camera'], 'instances': ['single', 'oneip', 'many'],
           'detect': ['layer', 'pause', 'none'], 'pause': ['yes', 'no']}
# Shown on the Config tab
HELP = {
    'simulate': 'For testing: all, printer or camera are simulated',
    'duet': 'Printer address (SBC or standalone).  Blank = this computer',
    'duetport': 'Printer port.  Blank or 0 = 80',
    'password': 'Printer password',
    'basedir': 'Where images and videos go (blank = the settings folder, with duetLapse3.json and the log)',
    'poll': 'Seconds between printer status checks',
    'instances': 'single: only one duetLapse3.  oneip: one per settings folder.  many: no limit',
    'nolog': 'No logfile',
    'verbose': 'Detailed logging',
    'keeplogs': "Don't delete per-print logs left by earlier versions",
    'novideo': "Don't make a video",
    'deletepics': 'Delete the images when duetLapse3 terminates',
    'maxffmpeg': 'Most ffmpeg instances to run at once when making videos',
    'keepfiles': "Don't delete files on startup or shutdown",
    'dontwait': 'Start taking images straight away, without waiting for a print',
    'seconds': 'Also take an image every n seconds (0 = off)',
    'detect': 'When to take images',
    'pause': 'yes parks the head before each image',
    'numlayers': 'Take an image every n layers',
    'movehead': 'Where to park the head (X, Y) when pause is yes',
    'rest': 'Seconds to wait after parking, before the image',
    'standby': 'Wait for a start command before doing anything',
    'restart': 'Get ready for the next print when this one finishes',
    'weburl1': 'Required. Camera1 snapshot url (preferred) or MJPEG stream url',
    'weburl2': 'Optional second camera url',
    'extratime': 'Seconds to hold the last image at the end of the video',
    'fps': 'Video frames per second',
    'minvideo': 'Shortest video to make (seconds)',
    'maxvideo': 'Fixed video length in seconds (0 = off)',
    'ffmpegthreads': 'Threads for each video (0 = automatic, from the free cpu cores)',
    'vidparam1': 'Advanced: override the Camera1 video command',
    'vidparam2': 'Advanced: override the Camera2 video command',
    'port': 'Port for this page (0 = pick a free port)',
    'ip': 'Set by duetLapse3 - the ip address of this computer',
    'hidebuttons': 'Only show the buttons that can be used now',
    'execkey': 'Prefix for messages that run a command on the SBC',
    'M3291': 'Name of the message macro, if you renamed M3291.g',
}
configExtras = ['ip']  # Written by duetLapse3, not read as a setting

def flatDefaults():
    return {key: val for section in DEFAULTS.values() for key, val in section.items()}

def readConfig(filename):
    with open(filename, encoding='utf-8') as f:
        return json.load(f)

def writeConfig(filename, config):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
        f.write('\n')

def badSetting(filename, message):
    logger.critical('Invalid setting in ' + filename + ': ' + message)
    sys.exit(2)

def checkSetting(key, val, default):
    # Returns val as the same type as default.  Raises ValueError (with the reason) if it can't be
    if key == 'duetport' and val in ['', None, 0, '0']:  # Blank means the standard http port
        return 80
    if isinstance(default, bool):  # Must be before int (bool is a kind of int)
        if isinstance(val, bool):
            return val
        if isinstance(val, str) and val.lower() in ['true', 'false']:
            return val.lower() == 'true'
        raise ValueError(key + ' must be true or false, not ' + json.dumps(val))
    if isinstance(default, int):
        try:
            return int(val)
        except (ValueError, TypeError):
            raise ValueError(key + ' must be a whole number, not ' + json.dumps(val))
    if isinstance(default, list):
        try:
            val = [int(v) for v in val]
        except (ValueError, TypeError):
            val = []
        if len(val) != len(default):
            raise ValueError(key + ' must be a list of ' + str(len(default)) + ' numbers e.g. ' + json.dumps(default))
        return val
    if not isinstance(val, str):
        raise ValueError(key + ' must be text (in quotes), not ' + json.dumps(val))
    if key in CHOICES and val not in CHOICES[key]:
        raise ValueError(key + ' must be one of ' + ', '.join(CHOICES[key]) + ', not "' + val + '"')
    return val

def loadSettings(filename):
    # Returns every setting: the defaults, replaced by any values in the config file
    # If the file does not exist, it is created from the defaults
    if not os.path.isfile(filename):
        logger.warning('No config file found at ' + filename + ' - creating it with default values')
        config = {section: dict(keys) for section, keys in DEFAULTS.items()}
        try:
            writeConfig(filename, config)
        except OSError as e:
            logger.warning('Could not create config file ' + str(e))
    else:
        try:
            config = readConfig(filename)
        except (OSError, ValueError) as e:
            badSetting(filename, str(e))

    settings = flatDefaults()
    for section in config.values():  # Sections are only for readability
        for key, val in section.items():
            if key in configExtras:
                continue
            if key not in settings:
                logger.warning('Ignoring unknown setting "' + key + '" in ' + filename)
                continue
            try:
                settings[key] = checkSetting(key, val, settings[key])
            except ValueError as e:
                badSetting(filename, str(e))
    return settings

def saveUiAddress(ip):
    # Record the ip address in use in the config file (if it changed) - same as duetPrintGuard
    # The port is not saved so that 0 keeps selecting a free port at each startup
    if state.configfile == '':
        return
    try:
        config = readConfig(state.configfile)
        section = next((sec for sec in config.values() if 'ip' in sec), None)
        if section is None:
            section = config.setdefault('UI', {})
        if section.get('ip') == ip:
            return
        section['ip'] = ip
        writeConfig(state.configfile, config)
        logger.info('Saved UI address ' + ip + ' to ' + state.configfile)
    except (OSError, ValueError) as e:
        logger.warning('Could not save ip address to ' + state.configfile + ' ' + str(e))



################################################
##  Main routines for calling subprocesses
################################################


def runsubprocess(cmd):
    logger.debug('RUNNING SUBPROCESS WITH ' + str(cmd))
    try:
        # A list of arguments runs without a shell, so paths with spaces etc. are safe
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=isinstance(cmd, str))

        logger.debug('Return Code = ' + str(result.returncode))
        logger.debug('stdout = ' + str(result.stdout))
        logger.debug('stderr = ' + str(result.stderr))
        ## if str(result.stderr) == '0' or str(result.stderr) == '':   # some apps dont provide stderr
        if result.returncode == 0:
            logger.debug('Command Success : ' + str(cmd))
            if result.stdout != '':
                logger.debug(str(result.stdout))
            return True
        else:
            logger.info('Command Failure: ' + str(cmd))
            logger.debug('Error = ' + str(result.stderr))
            logger.debug('Response = ' + str(result.stdout))
            return False
    except (subprocess.TimeoutExpired):
        logger.info('Call Timed Out: ' + str(cmd))
        return False
    except (subprocess.CalledProcessError, OSError) as e:
        logger.info('Command Exception: ' + str(cmd))
        logger.info('Exception = ' + str(e))
        return False

def init():
    # Argument 1 is the folder for duetLapse3.json and the logfile - default is this program's folder
    if len(sys.argv) > 1:
        state.configdir = os.path.realpath(sys.argv[1])
        if not os.path.isdir(state.configdir):  # Create it - duetLapse3.json is then created with the defaults
            try:
                os.makedirs(state.configdir)
                print('Created folder ' + state.configdir)
            except OSError as e:
                print('Folder ' + sys.argv[1] + ' could not be created - Exiting. ' + str(e))
                sys.exit(1)
    else:
        state.configdir = os.path.dirname(os.path.realpath(__file__))
    state.configfile = os.path.join(state.configdir, configFileName)

    args = loadSettings(state.configfile)

    state.inputs = {}

    # Derived  globals
    
    # Simulate
    state.inputs.update({'# Simulate': ''})
    state.simulate = args['simulate']
    state.inputs.update({'simulate': str(state.simulate)})

    # Environment
    state.inputs.update({'# Environment':''})
    
    state.duet = args['duet'].strip() or localIp()  # Blank = this computer
    if state.simulate in ['all','printer']:
        state.duet = 'SIMULATED'
    state.inputs.update({'duet': str(state.duet)})

    state.duetport = args['duetport']
    state.inputs.update({'duetport': str(state.duetport)})

    state.password = args['password']  
    #  password is not displayed
    if state.password == 'reprap':
        state.inputs.update({'password': 'Default'})
    else:
        state.inputs.update({'password': '*******'})

        
    state.basedir = args['basedir']
    state.inputs.update({'basedir': str(state.basedir)})
    
    state.poll = args['poll']
    if state.poll < state.minPoll:
        state.poll = state.minPoll
    state.inputs.update({'poll': str(int(state.poll))})
    
    state.instances = args['instances']
    state.inputs.update({'instances': str(state.instances)})
    
    state.nolog = args['nolog']
    state.inputs.update({'nolog': str(state.nolog)})
    
    state.verbose = args['verbose']
    state.inputs.update({'verbose': str(state.verbose)})

    state.port = args['port']
    state.inputs.update({'port': str(state.port)})

    state.keeplogs = args['keeplogs']
    state.inputs.update({'keeplogs': str(state.keeplogs)})

    state.novideo = args['novideo']
    state.inputs.update({'novideo': str(state.novideo)})

    state.deletepics = args['deletepics']
    state.inputs.update({'deletepics': str(state.deletepics)})

    state.maxffmpeg = args['maxffmpeg']
    state.inputs.update({'maxffmpeg': str(state.maxffmpeg)})

    state.keepfiles = args['keepfiles']
    state.inputs.update({'keepfiles': str(state.keepfiles)})

    # Execution
    state.inputs.update({'# Execution' : ''})

    state.dontwait = args['dontwait']
    state.inputs.update({'dontwait': str(state.dontwait)})

    state.seconds = args['seconds']
    if state.seconds != 0 and state.seconds < state.minseconds:
        state.seconds = state.minseconds
    state.inputs.update({'seconds': str(state.seconds)})

    state.detect = args['detect']
    state.inputs.update({'detect': str(state.detect)})

    state.pause = args['pause']
    state.inputs.update({'pause': str(state.pause)})

    state.numlayers = args['numlayers']
    if state.numlayers < 1:
        state.numlayers = 1
    state.inputs.update({'numlayers': int(state.numlayers)})

    state.movehead = args['movehead']
    state.inputs.update({'movehead': str(state.movehead)})

    state.rest = args['rest']
    if state.rest < 0:
        state.rest = 0
    state.inputs.update({'rest': str(state.rest)})

    state.standby = args['standby']
    state.inputs.update({'standby': str(state.standby)})

    state.restart = args['restart']
    state.inputs.update({'restart': str(state.restart)})

    # Camera
    state.inputs.update({'# Camera': ''})

    state.weburl1 = args['weburl1']
    state.inputs.update({'weburl1': str(state.weburl1)})

    state.weburl2 = args['weburl2']
    state.inputs.update({'weburl2': str(state.weburl2)})

    # Video
    state.inputs.update({'# Video': ''})

    state.extratime = args['extratime']
    state.inputs.update({'extratime': str(state.extratime)})

    state.fps = args['fps']
    state.inputs.update({'fps': str(state.fps)})

    state.minvideo = args['minvideo']
    state.inputs.update({'minvideo': str(state.minvideo)})

    state.maxvideo = args['maxvideo']
    if state.maxvideo > 0:
       if state.maxvideo < state.minvideo:
           state.maxvideo = state.minvideo

    state.inputs.update({'maxvideo': str(state.maxvideo)})

    state.ffmpegthreads = max(0, args['ffmpegthreads'])
    state.inputs.update({'ffmpegthreads': str(state.ffmpegthreads)})

    # Overrides
    state.inputs.update({'# Overrides': ''})

    state.vidparam1 = args['vidparam1']
    state.inputs.update({'vidparam1': str(state.vidparam1)})

    state.vidparam2 = args['vidparam2']
    state.inputs.update({'vidparam2': str(state.vidparam2)})

    # UI
    state.inputs.update({'# UI': ''})

    state.hidebuttons = args['hidebuttons']
    state.inputs.update({'hidebuttons': str(state.hidebuttons)})

    #  Special Functions

    state.inputs.update({'# Special Functions': ''})
    state.execkey = args['execkey']
    state.inputs.update({'execkey': str(state.execkey)})

    state.M3291 = args['M3291']
    state.inputs.update({'M3291': str(state.M3291)})


    ##### Configure the custom logger #####
    setdebug(state.verbose)

    # Create handler for console output - file output handler is created later if needed
    logger_module.setup_logger(state.duet, console = state.nolog is False)


    ########################################################################
    # Check to see if this instance is allowed to run
    #########################################################################
    #  What OS are we using?
    operatingsystem = platform.system()
    if operatingsystem == 'Windows':
        state.win = True
    else:
        state.win = False

    checkInstances(state.instances)

    ####################################################
    # Setup for logging and filenames
    ####################################################

    # pid is used to create unique filenames
    state.pid = str(os.getpid())

    # set debug value
    setdebug(state.verbose)

    # duetname used for filenames and directories
    state.duetname = state.duet.replace('.', '-')

    # set directories for files
    state.pidIncrement = 0 # Used to create a new path for each job.
    if state.basedir == '':  # The settings folder - argument 1, or this program's folder
        state.basedir = state.configdir
    # clean up the separators
    state.basedir = state.basedir.replace('\\', '/')
    if state.basedir.startswith('.'):  #  this little trick so as not to drop ./ or ../
        state.basedir = './' + state.basedir
        state.basedir = os.path.normpath(state.basedir) # get slashes in correct direction


    state.topDir = os.path.join(state.basedir, socket.getfqdn(), state.duetname)
    logger.debug('The top level dir is ' + state.topDir)
    
    pidID = state.pid + '_' + str(state.pidIncrement)
    state.nextWorkingDir = os.path.join(state.topDir, pidID)  # used to seed workinDir

    if not os.path.isdir(state.topDir): # If not already exists - create
        try:
            os.makedirs(state.topDir)  # Use recursive form to create intermediate directories
        except OSError as e:
            logger.info('Could not create dir ' + str(e))
            sys.exit(1)
            
    # Should not happen (almost like winning the lottery)
    for item in listTopDir():
        if item.startswith(pidID):  # Wow - a pid collision
            state.pidIncrement += 1
            state.nextWorkingDir = os.path.join(state.topDir, state.pid + '_' + str(state.pidIncrement))


    #  Clean up older files
    cleanupFiles('startup')

    setuplogfile()
    setNextWorkingDir()
    
    ###############################################
    # derived parameters
    ##############################################

    poll_seconds()

    # Select a free port if port = 0 (or the given port is in use) - same as duetPrintGuard
    state.ip, state.port = validate_port(state.port)
    state.httpListener = True
    saveUiAddress(state.ip)

    ########################################################################
    # Inform regarding valid and invalid combinations
    #########################################################################

    # Invalid Combinations that will abort program

    # Only http cameras are supported
    if state.simulate in ['all', 'camera'] and state.weburl1 == '':
        state.weburl1 = 'http://simulated'

    # A missing or invalid url does not stop duetLapse3 - the url can be set on the Cameras tab
    # Until then that camera is not used
    for key, name in [('weburl1', 'Camera1'), ('weburl2', 'Camera2')]:
        url = getattr(state, key)
        if url != '' and not camera.is_http_url(url):
            logger.info('************************************************************************************')
            logger.info('Invalid setting: ' + key + ' "' + url + '" is not an http url - ' + name + ' will not be used')
            logger.info('Use a snapshot url (preferred) or an MJPEG stream url - set it on the Cameras tab')
            logger.info('************************************************************************************\n')
            setattr(state, key, '')
    if state.weburl1 == '':
        logger.info('************************************************************************************')
        logger.info('No url for Camera1 (weburl1) - no images will be captured until it is set on the Cameras tab')
        logger.info('************************************************************************************\n')

    checkDependencies()  # Exits if ffmpeg is missing


    if (not state.movehead == [0.0, 0.0]) and (not 'yes' in state.pause) and (not 'pause' in state.detect):
        logger.info('************************************************************************************')
        logger.info(
                'Invalid Combination: "movehead {0:1.2f} {1:1.2f}" requires either "pause yes" or "detect pause".'.format(
                        state.movehead[0], state.movehead[1]))
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if ('yes' in state.pause) and ('pause' in state.detect):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: "pause yes" causes this program to pause printer when')
        logger.info('other events are detected, and "detect pause" requires the gcode on the printer')
        logger.info('contain its own pauses.  These cannot be used together.')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    return # init()


def issue_warnings():
    # Information and Warnings
    if state.seconds <= 0 and 'none' in state.detect:
        logger.info('************************************************************************************')
        logger.info('Warning:: seconds ' + str(state.seconds) + ' and detect ' + state.detect + ' nothing will be captured.')
        logger.info('Specify "detect none" with "seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************\n')

    if state.seconds > 0 and (not 'none' in state.detect):
        logger.info('************************************************************************************')
        logger.info('Warning: seconds ' + str(state.seconds) + ' and detect ' + state.detect + ' will trigger on both.')
        logger.info('Specify "detect none" with "seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************\n')

    if state.seconds > 0  and 'none' in state.detect:
        logger.info('************************************************************************************')
        logger.info('Warning: seconds ' + str(state.seconds) + ' and detect ' + state.detect)
        logger.info('This combination implies dontwait and will be set automatically')
        logger.info('************************************************************************************\n')
        state.dontwait = True

    if 'pause' in state.detect:
        logger.info('************************************************************************************')
        logger.info('* Note "detect pause" means that the G-Code on the printer already contains pauses,')
        logger.info('* and that this program will detect them, take a photo, and issue a resume.')
        logger.info('* Head position during those pauses is can be controlled by the pause.g macro ')
        logger.info('* on the duet, or by specifying "movehead nnn nnn".')
        logger.info('*')
        logger.info('* If instead, it is desired that this program force the printer to pause with no')
        logger.info('* pauses in the gcode, specify either:')
        logger.info('* "pause yes detect layer" or "pause yes seconds nnn".')
        logger.info('************************************************************************************\n')

    if 'yes' in state.pause:
        logger.info('************************************************************************************')
        logger.info('* Note "pause yes" means this program will pause the printer when the detect and / or ')
        logger.info('* seconds flags trigger.')
        logger.info('*')
        logger.info('* If instead, it is desired that this program detect pauses that are already in')
        logger.info('* in the gcode, specify:')
        logger.info('* "detect pause"')
        logger.info('************************************************************************************\n')

    if state.novideo and state.deletepics:
        logger.info('************************************************************************************')
        logger.info('Warning: The combination of novideo and deletepics will not create any output')
        logger.info('************************************************************************************\n')

    return # issue_warnings()


####################################################
# Display the options being used
####################################################

def getOptions():
    for var in state.inputs: # update the values
        if hasattr(state, var):
            val = getattr(state, var)
            newvalue = {var:val}
            state.inputs.update(newvalue)
    return state.inputs

def listOptions():
    options = getOptions()
    logger.info("################### Options at start of this print job  #####################")  
    for label, value in options.items():
        value = str(value)
        if label.startswith('#'):
            logger.info(label)
        elif value == '':
            logger.info(label)
        else:
            logger.info(label + '  =  ' + value)
    logger.info('-----------------------------------------------------------------------\n\n')


####################################################
# Logfile setup
####################################################

def setuplogfile():  # Called at start - one logfile, in the config folder, for the whole run
    if state.nolog is False:
        state.logfilename = os.path.join(state.configdir, logFileName)
        logger_module.create_log_file(state.logfilename)

        logger.info('duetLapse3 Version --- ' + str(duetLapse3Version))
        logger.info('Process Id  ---  ' + str(state.pid) )
        logger.info('Settings from  ---  ' + state.configfile)
        logger.info('-------------------------------------------------------------------------------\n')
    else:
        state.logfilename = 'None (nolog is set)'


def setNextWorkingDir():  # Called at start and restart - the folder for the next job's images
    state.pidIncrement += 1
    state.nextWorkingDir = os.path.join(state.topDir, state.pid + '_' + str(state.pidIncrement))

####################################################
# Misc settings
####################################################
   
def setdebug(val): # How much output
    logger_module.set_log_level(val)



def poll_seconds():
        # Polling interval needs to be in integer multiple of mainLoopPoll
    if state.poll < state.minPoll:
        state.poll = state.minPoll
    multiplier,remainder = divmod(state.poll, state.mainLoopPoll)
    if remainder == 0: # No need to change
        pass
    else:
        state.poll = state.mainLoopPoll * multiplier # round down
    
    # Seconds needs to be an integer multiple of mainLoopPoll       
    if state.seconds != 0:
        multiplier,remainder = divmod(max(state.seconds,state.minseconds), state.mainLoopPoll)    
        if remainder == 0: # use the max
            updateglobals('seconds', str(max(state.seconds,state.minseconds))) 
        else:  # round down
            updateglobals('seconds', str(state.mainLoopPoll * multiplier))     
        
        # poll needs to be lesser of poll and seconds.
        updateglobals('poll', str(min(state.poll, state.seconds))) 
        
        # Check for dontwait
        if state.seconds > 0 and 'none' in state.detect:
            updateglobals('dontwait', 'True')       
      
def checkDependencies():
    # ffmpeg is needed to make the videos
    if runsubprocess('ffmpeg -version') is False:
        logger.info("Module 'ffmpeg' is required. ")
        if not state.win:
            logger.info("Obtain via 'sudo apt install ffmpeg'")
        sys.exit(3)

    """
    ########################################################################
    # Make sure we can connect to the printer
    #########################################################################
    """

def checkforPrinter():
    # Get the initial connection to the printer.    
    while state.apiModel == '' and state.terminateState != 1: #  Keep trying until connected or terminating
        Model = loginPrinter()[0]
        if Model == '': #  Could not connect
            logger.info('#########################################################')
            logger.info('The printer at ' + duet_printer.printerAddress() + ' is not responding')
            logger.info('Check the ip address or logical printer name is correct\n')
            logger.info('Is the printer turned on?')
            logger.info('Duet software must support rr_model or /machine/status')
            logger.info('########################################################\n')
            state.connectionState = False
            startcheckforConnection()
            continue

        if state.firstConnect is None:
            state.firstConnect = False
            state.printerVersion = getDuetVersion(Model)
            if state.printerVersion is None:
                state.printerVersion = 'unknown'
            logger.info(f"""Version Check returned --> {state.printerVersion}""")

        state.connectionState = True
        state.apiModel = Model # We have a good connection
        logger.info('###############################################################')
        logger.info('Connected to printer at ' + duet_printer.printerAddress())
        logger.info('Using Duet version ' + state.printerVersion)
        logger.info('Using API interface ' + state.apiModel)
        logger.info('###############################################################\n')
        return


def checkforConnection():
    try:
        state.checkforconnectionState = 1
        state.connectionState = False
        elapsed = 0
        shortcheck = state.mainLoopPoll
        quickcheck = state.mainLoopPoll*4  # check up to 4 times
        longcheck = 3*60 # every 3 minutes
        checking = True
        logger.info('----------------  Waiting for printer to reconnect -----------------')
        while checking and state.terminateState != 1:
            if elapsed <= quickcheck: # Check every shortcheck
                model, code = loginPrinter(state.apiModel)
                if code != 200: # Still not connected
                    #terminate()
                    logger.debug('Retrying connection every ' + str(shortcheck) + ' seconds')
                    time.sleep(shortcheck)
                    elapsed = elapsed + shortcheck
                else:
                    checking = False
            else:  #  Check every longcheck
                model, code = loginPrinter(state.apiModel)
                if code != 200: # Still not connected
                    logger.debug('Retrying connection every ' + str(longcheck) + ' seconds')
                    time.sleep(longcheck)
                else:
                    checking = False

        state.apiModel = model
        state.connectionState = True
        logger.info('-----------------------  Reconnected to printer ----------------------')    
        startnextAction('reconnected')
        state.checkforconnectionState = -1
        return
    except Exception as e:
        logger.info('!!!!!#####!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN CHECK FOR CONNECTION -- ' + str(e))
        quit_forcibly()        


#####################################################
##  Utility Functions
#####################################################

def listTopDir():
    try:
        listdir = os.listdir(state.topDir)
    except FileNotFoundError as e:
        logger.info('--------------------------------- FATAL ERROR --------------------------------')
        logger.info('Trying to list dir -- ' + state.topDir + '\n')
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
    state.makeVideoState = 1  # Can be called from makeVideo or directly from http server
    # loop through directory count # files and detect if Camera1 / Camera2
    logger.info('Create Video from ' + str(directory))
    if not os.path.isdir(directory):
        msg = 'Error: No permission or directory not found'
        logger.info(msg)
        state.makeVideoState = -1
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
        state.makeVideoState = -1
        return msg

    if C1: Cameras.append('Camera1')
    if C2: Cameras.append('Camera2')

    for cameraname in Cameras:
        if cameraname == 'Camera1':
            frame = f1
        elif cameraname == 'Camera2':
            frame = f2

        if state.maxvideo > 0:
            if frame < state.maxvideo:
                thisfps = 1.0                         #  make it as long as we can     
            else:
                thisfps = float(frame/state.maxvideo)       #  set for  maxvideo duration
        else:
            thisfps = float(state.fps)                      #  set for fixed fps


        if frame/thisfps < state.minvideo:
            msg = 'Error: ' + cameraname + ': Cannot create video shorter than ' + str(state.minvideo) + ' second(s).\n Length would have been ' + str(frame/thisfps) + ' second(s).' 
            logger.info(msg)
            logger.info('frame = ' + str(frame) + ' thisfps = ' + str(thisfps) + ' fps = ' + str(state.fps) + ' maxvideo = ' + str(state.maxvideo) + ' minvideo = ' + str(state.minvideo))
            state.makeVideoState = -1
            return msg

        logger.info(cameraname + ': now making ' + str(frame) + ' frames into a video with fps = ' +str(thisfps))
        if 250 < frame:
            logger.info("This can take a while...")

        timestamp = time.strftime('%a-%H-%M', time.localtime())

        fn = directory + '_' + cameraname + '_' + timestamp + '.mp4'
        tmpfn = os.path.join(directory, '_tmpvideo.mp4')
        location = os.path.join(directory, cameraname + '_%08d.jpeg')

        cmd = ffmpegCommand(thisfps, location, tmpfn)

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
            msg = ('!!!!!  There was a  creating the video for '+cameraname+' !!!!!')
            logger.info(msg)
            if os.path.isfile(tmpfn): 
                try:
                    os.remove(tmpfn)
                except OSError as e:
                    logger.info('Error deleting file ' + str(e))
            state.makeVideoState = -1
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
 
    state.makeVideoState = -1
    return msg


def ffmpegThreads():
    # Threads for one ffmpeg - shared from the cpu cores that are free now, leaving one spare
    # so that making a video does not overwhelm the computer (e.g. while printing)
    if state.ffmpegthreads > 0:  # Set by the user
        return state.ffmpegthreads
    cores = os.cpu_count() or 1
    try:
        load = os.getloadavg()[0]  # Average number of busy cores over the last minute
    except (AttributeError, OSError):  # Not available on Windows
        load = 0
    free = int(cores - load - 1)
    threads = max(1, free // max(1, state.maxffmpeg))  # Up to maxffmpeg can run at once
    logger.info('ffmpeg threads = ' + str(threads) + ' (' + str(cores) + ' cores, load ' + '{:.1f}'.format(load) + ', maxffmpeg ' + str(state.maxffmpeg) + ')')
    return threads


def ffmpegCommand(fps, location, outfile):
    # ffmpeg runs at low priority so the printer software, cameras and web page always come first
    cmd = []
    if not state.win and shutil.which('nice'):
        cmd += ['nice', '-n', '19']
    cmd += ['ffmpeg']
    if not state.verbose:
        cmd += ['-loglevel', 'quiet']
    cmd += ['-r', str(fps), '-i', location,
            '-vcodec', 'libx264',
            '-preset', 'veryfast',  # Much less cpu than the default, for a slightly bigger file
            '-pix_fmt', 'yuv420p',  # Plays in browsers and on phones whatever the camera's JPEG format
            '-threads', str(ffmpegThreads()),
            '-y', outfile]
    return cmd


def ffmpeg_available():
    count = 0
    max_count = state.maxffmpeg  # Default is 2
    for p in psutil.process_iter(['name']):  # Processes that end during the scan are skipped
        if 'ffmpeg' in (p.info['name'] or ''):  # Check to see if it's running
            count += 1
        if count >= max_count:
            logger.debug('Waiting for ffmpeg to become available')
            return False
    logger.debug('There are ' + str(count) + ' instances of ffmpeg running')
    return True

def getRunningInstancePids():
    pidlist = []
    for p in psutil.process_iter(['name']):  # Processes that end during the scan are skipped
        if 'python' in (p.info['name'] or ''):  # Check all other python instances
            pidlist.append(str(p.pid))
    return pidlist


def getPidDirs():
    dirlist = []
    if os.path.isdir(state.topDir):
        for item in listTopDir():
            if os.path.isdir(os.path.join(state.topDir, item)):
                dirlist.append(item)

    return dirlist

def createworkingDir():
    logger.debug('Calling stack ' + currentFuncName(2) + ' --> '  + currentFuncName(1) + ' --> '  + currentFuncName(0))
    try:
        os.mkdir(state.nextWorkingDir)
        logger.debug('Created working directory: ' + state.nextWorkingDir)
        state.workingDirStatus = 0
    except OSError as e:
        logger.info('Could not create working directory ' + str(e))
        state.workingDirStatus = -1
    return state.nextWorkingDir

def renameworkingDir(thisDir):
    jobname = getDuet('renameworkingDir', Jobname)

    if state.connectionState is False or jobname == '':
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
        state.workingDirStatus = 1
        return thisDir
    nextWorkingDir = thisDir + '_' + jobname

    try:
        shutil.move(thisDir, nextWorkingDir)
        logger.debug('Renaming working directory: ' + nextWorkingDir)
        state.workingDirStatus = 1
    except shutil.Error as e:
        logger.info('Error on move of workingDir ' + str(e))
        state.workingDirStatus = 0
    return nextWorkingDir


def cleanupFiles(phase):
    logger.debug('*****  Cleaning up files for phase:  ' + phase + '  *****')
    pidlist = getRunningInstancePids()

    dirlist = listTopDir()

    # Make and clean up directorys.

    if phase == 'startup':
        if state.keepfiles: return

        for dirs in dirlist: #  Delete old dirs and files
            split_dirs = dirs.split("_", 1)
            dirpid = split_dirs[0]

            if dirpid not in pidlist:  # only if not running
                fn = os.path.join(state.topDir, dirs)
                if os.path.isdir(fn):  # a directory
                    deleteFileFolder(fn)
                elif (not state.keeplogs) and dirs.endswith('.log'):  # logfiles
                    deleteFileFolder(fn)

    elif phase == 'standby':  # deleted images directory will be recreated on first capture
        if state.workingDirStatus != -1:
            deleteFileFolder(state.workingDir)
            state.workingDirStatus = -1

    elif phase == 'restart':  # new image directory will be created on first capture
        pass

    elif phase == 'terminate':
        if state.keepfiles: return

        if state.deletepics:
            for dirs in dirlist:
                fn = os.path.join(state.topDir, dirs)
                if os.path.isdir(fn):
                    deleteFileFolder(fn)
                    state.workingDirStatus = -1
            # Assume sucess even if error from above
            state.workingDirStatus = -1
    return  # cleanupFiles

def startNow():
    #  Determine if program should logically start now
    if state.standby:
        state.action = 'standby'
        return False
    elif (state.seconds > 0) and (state.dontwait or 'none' in state.detect):
        state.action = 'start'
        return True
    else:
        state.action = 'start'
        return False


def getThisInstance(thisinstancepid):
    thisrunning = 'Could not find a process running with pid = ' + str(thisinstancepid)
    for p in psutil.process_iter(['name', 'cmdline']):  # Processes that end during the scan are skipped
        name = p.info['name'] or ''
        if ('python3' in name or 'pythonw' in name) and thisinstancepid == p.pid:
            cmdline = str(p.info['cmdline'] or [])
            cmdline = cmdline.replace('[', '')
            cmdline = cmdline.replace(']', '')
            cmdline = cmdline.replace(',', '')
            cmdline = cmdline.replace("'", '')
            cmdline = cmdline.replace('  ', ' ')
            state.pid = str(p.pid)
            thisrunning = cmdline

    return thisrunning


#####################################################
##  Processing Functions
#####################################################

def instanceConfigDir(proc):
    # The settings folder of a running duetLapse3 (from its command line), or None if it is not duetLapse3
    cmdline = proc.info['cmdline'] or []
    for i, part in enumerate(cmdline):
        if os.path.basename(part) == os.path.basename(__file__):
            if len(cmdline) > i + 1:
                folder = cmdline[i + 1]
            else:
                folder = os.path.dirname(part)  # Default is the program's folder
            try:
                return os.path.realpath(os.path.join(proc.cwd(), folder))
            except (psutil.Error, OSError):
                return ''  # Can't tell which folder
    return None


def checkInstances(instances):
    # single - only one duetLapse3 can run.  oneip - one per settings folder (i.e. per printer).  many - no limit
    proccount = 0
    allowed = 0

    for p in psutil.process_iter(['name', 'cmdline']):  # Processes that end during the scan are skipped
        name = p.info['name'] or ''
        if not ('python' in name or 'pythonw' in name):
            continue
        folder = instanceConfigDir(p)
        if folder is None:
            continue
        proccount += 1  # Includes this instance
        if 'single' in instances:
            allowed += 1
        if 'oneip' in instances and folder == state.configdir:
            allowed += 1

    if allowed > 1:
        logger.info('#############################')
        logger.info('Process is already running... shutting down.')
        logger.info('#############################\n')
        sys.exit(6)

    return proccount


def checkForPause(layer):
    # Checks to see if we should pause and reposition heads.
    # Do not pause until printing has completed layer 2.
    # This solves potential issues with the placement of pause commands in the print stream
    # Before or After layer change
    # As well as timed during print start-up

    if (layer < 1):  # Do not try to pause
        return
    
    state.duetStatus, _ = getDuet('Check for Pause', Status)
    if state.connectionState is False or state.duetStatus == 'idle':
        return
    
    loopmax = 10  # sec
    loopinterval = 0.5  # sec
    loopcount = loopmax / loopinterval
    if state.pause == 'yes':  # DuetLapse is controlling when to pause
        logger.debug('Requesting pause via M25')
        sendDuetGcode(state.apiModel, 'M25')  # Ask for a pause
        loop = 0
        while True:
            time.sleep(loopinterval)  # wait and try again    
            state.duetStatus, _ = getDuet('check for pause = yes', Status)
            if state.connectionState is False:
                return
            if state.duetStatus == 'paused':
                break
            else:
                loop += 1
            if loop >= loopcount:  # limit the counter in case there is a problem
                logger.info('Timeout after ' + str(loopmax))
                logger.info('Target was: paused')
                logger.info('Actual was: ' + state.duetStatus)
                break

    if state.duetStatus == 'paused':
        if not state.movehead == [0.0, 0.0]:  # optional repositioning of head
            logger.debug('Moving print head to X{0:4.2f} Y{1:4.2f}'.format(state.movehead[0], state.movehead[1]))
            sendDuetGcode(state.apiModel, 'G0 X{0:4.2f} Y{1:4.2f}'.format(state.movehead[0], state.movehead[1]))
            loop = 0
            while True:
                time.sleep(loopinterval)  # wait and try again
                xpos, ypos, _ = getDuet('Position paused = yes', Position)
                if state.connectionState is False:
                    return
                if (abs(xpos - state.movehead[0]) < .05) and (
                        abs(ypos - state.movehead[1]) < .05):  # close enough for government work
                    break
                else:
                    loop += 1
                if loop >= loopcount:  # limit the counter in case there is a problem
                    logger.info('Timeout after ' + str(loopmax) + 's')
                    logger.info('Target X,Y: ' + str(state.movehead[0]) + ',' + str(state.movehead[1]))
                    logger.info('Actual X,Y: ' + str(xpos) + ',' + str(ypos))
                    break
        time.sleep(state.rest)  # Wait to let camera feed catch up

    return


def unPause():  # Only gets called if duetStatus = paused
    if state.connectionState is False: # This traps the call being made unnecessarily
        return
    #  duetStatus, _ = getDuet('Status from unPause', Status)
    # if connectionState is False: # Need to check after each getDuet
    #     return
    if state.duetStatus == 'paused':
        loopmax = 10 # sec
        loopinterval = 0.5 # sec  short so as to not miss start of next layer
        loopcount = loopmax / loopinterval
        logger.debug('Requesting un pause via M24')
        sendDuetGcode(state.apiModel, 'M24')  # Ask for an un pause
        loop = 0
        while True:
            time.sleep(loopinterval)  # wait a short time so as to not miss transition on short layer            
            state.duetStatus, _ = getDuet('unPause loop', Status)
            if state.connectionState is False:
                return
            if state.duetStatus in ['idle', 'processing']:
                break
            else:
                loop += 1
            if loop >= loopcount:  # limit the counter in case there is a problem
                logger.info('Loop exceeded: Target was: unpause')
                break
    return


def onePhoto(cameraname, weburl):

    if state.workingDirStatus == -1: # Create as late as possible
        state.workingDir = createworkingDir()
        state.camfile1 = os.path.join(state.workingDir, 'Camera1_')

        state.camfile2 = os.path.join(state.workingDir, 'Camera2_')
    
    if state.workingDirStatus == 0: # Keep checking until jobname is known
        state.workingDir = renameworkingDir(state.workingDir)
        state.camfile1 = state.workingDir + '/Camera1_'
        state.camfile2 = state.workingDir + '/Camera2_'

    if cameraname == 'Camera1':
        state.frame1 += 1
        s = str(state.frame1).zfill(8)
        fn = state.camfile1 + s + '.jpeg'
    else:
        state.frame2 += 1
        s = str(state.frame2).zfill(8)
        fn = state.camfile2 + s + '.jpeg'

    if state.simulate in ['all','camera']:
        with open(fn, 'wb') as outputfile:
            outputfile.write(state.simulatedImage)
    elif camera.capture_image(weburl, fn) is False: #  order is important
        logger.info('!!!!!  There was a problem capturing an image !!!!!')
        # Decrement the frame counter because we did not capture anything
        if cameraname == 'Camera1':
            state.frame1 -= 1
            if state.frame1 < 0:
                state.frame1 = 0
            return
        else:
            state.frame2 -= 1
            if state.frame2 < 0:
                state.frame2 = 0
            return
    #  Success
    state.lastImage = '/getfile?path=' + urllib.parse.quote(fn)
    if cameraname == 'Camera1':
        state.timePriorPhoto1 = time.time()
        return
    else:
        state.timePriorPhoto2 = time.time()
        return

def oneInterval(cameraname, weburl, finalframe = False):
    if state.connectionState is False:
        logger.debug('Bypassing oneInterval because of connectionState')
        return

    # set the logical frame number
    # frame1 and frame 2 are incremented in onePhoto before image is captured
    if cameraname == 'Camera1':
        frame = state.frame1 + 1
    else:
        frame = state.frame2 + 1

    zn = getDuet('Layer from oneInterval', Layer)
    if state.connectionState is False:
        return
    if zn == -1:
        layer = 'None'
    else:
        layer = str(zn)

    if state.pause == 'yes' and zn < 1:  # Dont capture anything until first layers is done
        logger.debug('Bypassing onePhoto from oneInterval because -pause = ' + state.pause + ' and layer = ' +str(zn))
    else:    
        if 'layer' in state.detect:
            checkForPause(zn)
            if zn%state.numlayers == 0: #  Every numlayers layer
                if (not zn == state.zo1 and cameraname == 'Camera1') or (not zn == state.zo2 and cameraname == 'Camera2'):
                    # Layer changed, take a picture.
                    logger.info('Layer - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after layer change')
                    onePhoto(cameraname, weburl)

        elif ('pause' in state.detect) and (state.duetStatus == 'paused'):
            checkForPause(zn)
            logger.info('Pause - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' at pause in print gcode')
            onePhoto(cameraname, weburl)
        elif finalframe:
            # get a final frame
            checkForPause(zn)
            logger.info('finalframe - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after layer change')
            onePhoto(cameraname, weburl)


    # update the layer counter
    if cameraname == 'Camera1':
        state.zo1 = zn
    else:
        state.zo2 = zn

    # Note that onePhoto() updates timePriorPhoto1 and timePriorPhoto2
    if cameraname == 'Camera1':
        elap = (time.time() - state.timePriorPhoto1)
    else:
        elap = (time.time() - state.timePriorPhoto2)

    logger.debug('elapsed: ' + str(elap))

    if (state.seconds > 0) and (state.seconds < elap) and (state.dontwait or 'none' in state.detect or zn >= 1):
        checkForPause(zn)
        logger.info('Time - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after ' + str(
                state.seconds) + ' seconds')
        onePhoto(cameraname, weburl)

def getVideoMsg():
    if state.maxvideo > 0:
        if state.frame1 > state.maxvideo:
            videolength = 'Video will be ' + str(state.maxvideo) + ' seconds long'
        elif state.frame1 > state.minvideo:
            videolength = 'Video will be ' + str(state.frame1) + ' seconds long'
        else:
            videolength = 'Not enough images for video to be created'
    else:
        if state.frame1/state.fps > state.minvideo:
            videolength = 'Video will be ' + str(state.frame1/state.fps) + ' seconds long'
        else:
            videolength = 'Insufficient images for video to be created'
    return videolength        

def makeVideo(directory, xtratime = False):  #  Adds and extra frame
    try:
        state.makeVideoState = 1
        # Get a final frame
        # Make copies if appropriate

        if xtratime and state.extratime >= 1: #  Do not add images if called from snapshot or video
            if state.weburl1 != '':   #  Camera 1
                logger.debug('For Camera1')
                oneInterval('Camera1', state.weburl1, True)
                ## if extratime != 0 and frame1/fps > minvideo:
                if state.frame1 > 0:
                    state.frame1 = copyLastFrame(state.camfile1, state.frame1)

            if state.weburl2 != '':   #  Camera 2
                logger.debug('For Camera2')
                oneInterval('Camera2', state.weburl2, True)
                ## if extratime != 0 and frame2/fps > minvideo:
                if state.frame2 > 0:
                    state.frame2 = copyLastFrame(state.camfile2, state.frame2)

        result = createVideo(directory)
        state.makeVideoState = -1
        return result
    except Exception as e:
        logger.info('!!!!!#####!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN MAKE VIDEO -- ' + str(e))
        quit_forcibly()        

def copyLastFrame(f, frame):  # Makes copies and updates frame counter
    logger.info('Copying last frame to extend video by ' +str(state.extratime) + ' seconds')
    fr = str(frame).zfill(8)
    sourcefile = f + fr + '.jpeg'
    copies = int(state.extratime)*int(state.fps)
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
        state.workingDirStatus = -1 # Force creation of a new workingDir
        setNextWorkingDir()
        logger.info('################### Restarted - images will go in ' + state.nextWorkingDir + ' ###################')
        startNow() # determine start state
        listOptions() # List the current values
        issue_warnings() # list any warnings about setting combinations
        startup() # Warp speed Mr Sulu

def terminate():
    # Force verbose messaging
    setdebug(True)

    state.terminateState = 1
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

    if state.restart:
        # wait for jobname to be reset
        jobname = getDuet('terminate', Jobname)
        loopcounter = 0
        if jobname != '':
            logger.info('Waiting for printjob to complete')
        while jobname !='' and loopcounter < 30:  # Don't wait more than a minute
            time.sleep(2)
            loopcounter += 1
            jobname = getDuet('terminate loop', Jobname)
            if state.simulate in ['all','printer']: # forces a reset
                jobname = ''
        if loopcounter >= 30:
            logger.info('jobname was not reset')
        # ready to restart
        setdebug(state.verbose)        
        state.restarting = True    
        logger.info('----------')
        logger.info('RESTARTING')
        logger.info('----------')

        state.terminateState = -1
        restartAction()
    else:
        stopmainLoop()
        waitformainLoop()
        closeHttpListener()
        logger.info('Program Terminated')
        if isPlugin(state.apiModel):
            stopPlugin(state.apiModel, 'duetLapse3')
        else:
            quit_forcibly()

def quit_sigint(*args):
    logger.info('Terminating because of Ctl + C (SIGINT)')
    quit_forcibly()

def quit_sigterm(*args):
    logger.info('Terminating because of SIGTERM')
    quit_forcibly()  

def quit_forcibly():
    state.restart = False
    logger.info('!!!!! Forced Termination !!!!!')
    os.kill(os.getpid(), 9)  # Brutal but effective

###########################
# Integral Web Server - the routes are in routes.py
###########################

def changeFps(thisfps):
    try:
        thisfps = int(thisfps)
        state.fps = max(1, thisfps)
        logger.info('-fps changed to: ' + str(state.fps))
    except ValueError as e:
        logger.info('Error changing fps: ' + str(e))

def changeMinvideo(thisminvideo):
    try:
        thisminvideo = int(thisminvideo)
        state.minvideo = max(1,thisminvideo)
        logger.info('-minvideo changed to: ' + str(state.minvideo))
    except ValueError as e:
        logger.info('Error changing minvideo: ' + str(e))

def changeMaxvideo(thismaxvideo):
    try:
        thismaxvideo = int(thismaxvideo)
        state.maxvideo = max(0, thismaxvideo)
        logger.info('-maxvideo changed to: ' + str(state.maxvideo))
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
        if state.standby:
            return ['start']
        else:
            return ['standby', 'pause', 'restart']
    else:
        return ['standby', 'pause', 'restart']


def startHttpListener():
    # FastAPI app served by uvicorn in its own thread, so it runs alongside the capture and main loops
    if state.listenerThread is not None and state.listenerThread.is_alive():
        logger.debug('http listener is already running')
        return

    import uvicorn
    from fastapi import FastAPI
    import routes

    routes.dl3 = sys.modules[__name__]  # Gives the routes access to this module's functions
    app = FastAPI(title='duetLapse3', version=duetLapse3Version)
    app.include_router(routes.router)

    config = uvicorn.Config(app, host='0.0.0.0', port=state.port,  # Every address of this computer - state.ip is the one shown
                            log_config=None, access_log=False,
                            timeout_graceful_shutdown=2)  # Don't wait long for open connections on shutdown
    state.listener = uvicorn.Server(config)
    state.listenerThread = threading.Thread(name='httpServer', target=state.listener.run, daemon=False)
    state.listenerThread.start()

    # Wait for uvicorn to start (or fail - e.g. the port is in use)
    timeout = time.time() + 10
    while not state.listener.started and state.listenerThread.is_alive() and time.time() < timeout:
        time.sleep(0.1)

    if not state.listener.started:
        logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  There was a problem starting the http listener !!!!!!!!!!!!!!!!!!!!!')
        sys.exit(1)

    logger.info('##########################################################')
    logger.info(f"""***** Started http listener on port {state.port}*****""")
    logger.info('duetLapse3 page: http://' + state.ip + ':' + str(state.port))
    logger.info('##########################################################\n')


def closeHttpListener():
    try:
        state.listener.should_exit = True
        logger.debug('!!!!! http listener stopped  !!!!!')
    except Exception as e:
        logger.debug('Could not terminate http listener')
        logger.debug(str(e))


def execRun(displaymessage):
        cmd = displaymessage.split(state.execkey)[1].strip()
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
    if state.captureLoopState == 1:
        state.captureLoopState = 0  # Signals capture loop to stop

def waitforcaptureLoop():
    if state.captureLoopState == -1:
        logger.debug('captureLoop is not running')
        return
    loopcounter = 0
    while state.captureLoopState != -1 and loopcounter < state.poll*3:  # wait for up to 3 poll intervals
        logger.debug('********* captureLoopState is ' + str(state.captureLoopState) + ' - Waiting to complete *********')
        time.sleep(state.poll/4) # Check 4 times per poll interval
        loopcounter += 1
    if state.captureLoopState != -1:
        state.captureLoopState = -1  # Forced
        logger.debug('Timed out trying to exit captureLoop')

def startmainLoop():
    #  global mainLoopState
    if state.mainLoopState == 1 or state.terminateState == 1:  #  Already running so don't start
        return
    threading.Thread(name='mainLoop', target=mainLoop, args=(), daemon=False).start()

def stopmainLoop():
    if state.mainLoopState == 1:
        state.mainLoopState = 0  # Signals capture thread to shutdown

def waitformainLoop():
    if state.mainLoopState == -1:
        logger.debug('mainLoop is not running')
        return
    loopcounter = 0
    while state.mainLoopState != -1 and loopcounter < state.mainLoopPoll*3:  # wait for up to 3 poll intervals
        logger.debug('********* mainLoopState is ' + str(state.mainLoopState) + ' - Waiting to complete *********')
        time.sleep(state.mainLoopPoll/4) # Check 4 times per poll interval
        loopcounter += 1
    if state.mainLoopState != -1:
        state.mainLoopState = -1  # Forced
        logger.debug('Timed out trying to exit mainLoop')


def startnextAction(command): # Does not run in a loop
    if state.terminateState == 1: # Block it if terminating
        return
    waitforNextAction()  
    threading.Thread(name='nextAction', target=nextAction, args=(command,), daemon=False).start()


def waitforNextAction():
    if state.nextActionState == -1:
        logger.info('nextAction is available')
        return
    while state.nextActionState != -1:  # Only one thread at a time may cause delay in http page update
        logger.debug('********* nextActionState is ' + str(state.nextActionState) + ' - Waiting to complete *********')
        time.sleep(1)

    logger.debug('nextaction is ready')
    

def startcheckforConnection():
    if state.checkforconnectionState == 1 or state.terminateState == 1:  #  Already running or don't start
        return
    threading.Thread(name='checkforConnection', target=checkforConnection, args=(), daemon=False).start()

def terminateThread(): # Can only be run once - but called as a thread to allow other threads to finish
    if state.terminateState == 1: #    Already Terminating
        return
    threading.Thread(name='terminate', target=terminate, args=(), daemon=False).start()


def waitforMakeVideo():
    while state.makeVideoState >= 0: # wait till its completed
        time.sleep(state.mainLoopPoll)  # Makevideo is fairly slow
        logger.debug('********* Waiting for makeVideo thread to finish *********')
    logger.debug('makeVideo is not running')


def startMakeVideo(directory, xtratime = False, thread = True): # Does not run in a loop - so we block it before running it
    if state.terminateState == 1: # Block it if terminating
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
    # Used for handling direct DL3 Messages
    # Runs continously except during terminate processing
    state.duetStatus = 'unknown'
    try:
        if state.connectionState is False:
            return
        state.mainLoopState = 1 # Running
        logger.info('###########################')
        logger.info('Starting mainLoop')
        logger.info('###########################\n')
        while state.mainLoopState == 1 and state.terminateState != 1 and state.connectionState:  # Setting to 0 stops
            if time.time() >= state.lastStatusCall + state.mainLoopPoll:  # within 30 seconds   
                state.duetStatus, _ = getDuet('mainLoop', Status)
            if time.time() >= state.lastCaptureLoop + state.poll:
                captureLoop()
            if state.mainLoopState == 1:
                time.sleep(state.mainLoopIterate)
        state.mainLoopState = -1 # Not Running
        return
    except Exception as e:
        logger.info('!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN MAIN LOOP -- ' + str(e))
        quit_forcibly()

def stateMachine(currentState):
    newState = currentState
    if currentState == 'Waiting':
        if state.duetStatus == 'processing' or state.dontwait or (state.duetStatus in ['paused','pausing'] and state.detect != 'none'):
            newState = 'Capturing'
        elif state.duetStatus == 'cancelling':
            newState = 'Completed'
    elif currentState == 'Capturing':
        if state.duetStatus == 'processing':
            pass
        elif (state.duetStatus == 'idle' and state.lastDuetStatus in ['processing','cancelling']) or state.terminateState == 1:
            newState = 'Completed'
        elif state.duetStatus == 'cancelling':
            newState = 'Completed'
        elif state.duetStatus in ['pausing','paused'] and state.lastDuetStatus in ['processing','paused','pausing','resuming']:
            pass
        elif state.duetStatus == 'resuming' and state.lastDuetStatus in ['processing','paused','pausing','resuming']:
            pass
        elif state.duetStatus == 'busy':
            pass
        else:
            newState = 'Waiting'
    elif currentState == 'Completed':
        pass
    else:
        logger.info('GROSS LOGIC ERROR IN STATE MACHINE')

    logger.debug('****** stateMachine:')
    logger.debug('newstate = ' + newState)
    logger.debug('currentState = ' + currentState)
    logger.debug('duetStatus = ' + state.duetStatus)
    logger.debug('lastDuetStatus = ' + state.lastDuetStatus)
    logger.debug('dontwait = ' + str(state.dontwait))
    logger.debug('detect = ' + state.detect)
    logger.debug('terminateState = ' + str(state.terminateState))
    logger.debug('******')

    if newState != currentState:
        logger.info('****** Print State changed to: ' + newState + ' from ' + currentState + '*****')
    return newState        

def captureLoop():  # Single instance only

    if state.connectionState is False or state.captureLoopState == 0 or state.action == 'standby':
        logger.debug('No Capture needed')
        state.printState = 'Waiting'
        state.captureLoopState = -1
        state.lastCaptureLoop = time.time()
        return

    try:
        state.captureLoopState = 1

        if state.duetStatus != state.lastDuetStatus:
            logger.info('****** Duet status changed to: ' + str(state.duetStatus) + ' from ' + str(state.lastDuetStatus) + ' *****')

        state.printState = stateMachine(state.printState)

        if state.printState == 'Capturing':
            if state.weburl1 != '':
                logger.debug('Calling oneInterval for Camera 1')
                oneInterval('Camera1', state.weburl1)
            if state.weburl2 != '':
                logger.debug('Calling oneInterval for Camera 2')
                oneInterval('Camera2', state.weburl2)
                state.duetStatus, _ = getDuet('pause check loop', Status)
            if state.duetStatus == 'paused' and (state.pause == 'yes' or state.detect == state.pause): # will be ignored if a manual pause
                unPause()  # Nothing should be paused at this point
            #  latest state to avoid polling delay
            state.printState = stateMachine(state.printState)

        if state.printState == 'Completed':
            logger.info('Print Job Completed')
            # printState = 'Waiting'
            # use a thread here as it will allow this thread to close.
            startnextAction('completed')
            logger.info('Exiting captureLoop')  
    except Exception as e:
        logger.info('!!!!!#####!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN CAPTURE LOOP -- ' + str(e))
        quit_forcibly()
        
    state.lastPrintState = state.printState
    state.lastDuetStatus = state.duetStatus
    state.lastCaptureLoop = time.time()
    state.captureLoopState = -1  # not running           

def nextAction(nextaction):  # can be run as a thread
    
    logger.debug('Calling nextaction ' + nextaction + ' from ' + currentFuncName(2) + ' --> '  + currentFuncName(1) + ' --> '  + currentFuncName(0))

    if state.nextActionState == 0:
        logger.debug('nextAction stopped')
        state.nextActionState = -1
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
            state.nextActionState = -1
            return
        elif nextaction == 'reconnected':
            startmainLoop() # restart the main loop
            time.sleep(state.mainLoopPoll) # Give the mainloop time to get next status
            nextaction = state.lastaction
            logger.info('nextAction resuming after reconnect target = ' + nextaction)

        if state.connectionState is False: #traps any requests during a disconnect
            state.nextActionState = -1
            logger.debug('nextaction aborted because connectionState is False')
            return

        state.nextActionState = 1
        state.action = nextaction  # default

        # This test is positionally sensitive
        if nextaction == 'completed':  # end of a print job
            state.printState = 'Completed'  # Update may have come from message Q
            if state.novideo:
                logger.info('Video creation was skipped')
            else:
                if state.workingDirStatus != -1:  startMakeVideo(state.workingDir, True)  # Add extratime if appropriate
            nextaction = 'terminate'

        logger.debug('++++++ Determining next logical action ++++++')

        if nextaction == 'start':
            startCaptureLoop()
            state.action = 'start'

        elif nextaction == 'standby':
            cleanupFiles(nextaction)  # clean up and start again
            setstartvalues()
            state.action = 'standby'

        elif nextaction == 'pause':
            state.action = 'pause'
    
        elif nextaction == 'continue':
            startCaptureLoop()
            state.action = 'start'

        elif nextaction == 'restart':
            if state.novideo:
                logger.info('Video creation was skipped')
            else:
                if state.workingDirStatus != -1:
                    startMakeVideo(state.workingDir, True) # Add extratime if appropriate
                waitforMakeVideo() # Wait until done before deleting files
                restartAction()

            if state.standby:
                state.action = 'standby'
            else:
                state.action = 'start'
                startCaptureLoop()
        elif nextaction == 'terminate':
            terminateThread() #  Allows nextAction to finish
            state.action = 'terminate'

        logger.info('++++++ Entering ' + state.action + ' state ++++++')
        state.lastaction = state.action
        logger.debug('nextAction exiting normally')
        state.nextActionState = -1
        return
    except Exception as e:
        logger.info('!!!!!#####!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN NEXT ACTION -- ' + str(e))
        quit_forcibly()

###################################
#  Utility Functions
###################################
# gcode command prefix - matched ignoring case so older DuetLapse3. commands still work
commandPrefix = 'duetlapse3.'

def handleMessages(queue, dellist):
    # Called by duet_printer.Status when the printer's M3291 message queue has something new
    try:
        actions = parseM3291(queue, dellist)
    except Exception as e:
        logger.info('Error Processing message queue')
        logger.info(str(e))
        return
    for item in actions:
        logger.debug(item)
        actionM3291(item)

def parseM3291(queue = [], dellist = []):
    # If missed deletions - cleanup and try again on next poll
    if len(dellist) > 0:
        logger.debug('Delayed delete on DL3msg queue')
        sendDuetGcode(state.apiModel, state.M3291 + ' B"Del"')
        return {}    

    logger.debug('Parsing message queue = ' + str(queue))    
    state.lastMessageSeq = queue[0]
    processed = []
    actionqueue = []
    for i in range(1,len(queue)):
        if queue[i] is None:
            continue
        message = queue[i].strip() # get rid of leading / trailing blanks
        if message.lower().startswith(commandPrefix) or (state.execkey != '' and message.startswith(state.execkey)):
            actionqueue.append(message)
        processed.append(i)
    
    if len(processed) != 0:
        delqueue = '{'
        for i in processed:
            delqueue += str(i) + ','   
        delqueue += '}'

        sendDuetGcode(state.apiModel, 'set global.DL3del =' + delqueue)
        sendDuetGcode(state.apiModel, state.M3291 + ' B"Del"')

    return actionqueue


def actionM3291(displaymessage):
    if  displaymessage.lower().startswith(commandPrefix):   
        nextaction = displaymessage[len(commandPrefix):].strip()
        if nextaction == state.action: #  Nothing to do
            logger.info('Already in ' + state.action + ' state')
            return

        if nextaction == 'graceful':
            startnextAction('completed')
        elif nextaction == 'forced':
            quit_forcibly()
        elif nextaction in allowedNextAction(state.action) or nextaction == 'completed':
            logger.debug ('DL3msg queue sending to startnextAction: ' + nextaction)
            startnextAction(nextaction)
        elif nextaction.startswith('snapshot'):
            if state.workingDirStatus != -1:
                startMakeVideo(state.workingDir, False, False)
        elif nextaction.startswith('change.'):
            command = nextaction.split('change.')[1]
            changehandling(command)
        else:
            logger.info('The requested action: ' + nextaction + ' is not available at this time')
            logger.info('The current state is: ' + state.action)

    elif state.execkey != '' and displaymessage.startswith(state.execkey):
        displaymessage = urllib.parse.unquote(displaymessage)
        execRun(displaymessage) # Run the command 
    return

def changehandling(command):
    command = command.replace(' ','') # Make sure it is well formed
    changevariables = ['verbose', 'seconds', 'poll', 'detect', 'movehead', 'dontwait', 'pause', 'restart','standby', 'novideo', 'keepfiles','minvideo','maxvideo', 'extratime', 'fps', 'rest',  'execkey']
    variable = command.split('=')[0]
    value = command.split('=')[1]
    if variable in changevariables:
        logger.debug('Changing variable with: ' + command)
        if variable == 'verbose' and value in ['True', 'False']:
            updateglobals(variable, value)
            setdebug(state.verbose)
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
    if hasattr(state, var):  # Otherwise do nothing
        #  Determine the original type
        #  use type() instead of isinstance() to avoid subtype issues
        vartype = str(type(getattr(state, var)))
        if 'int' in vartype:
            convert = 'int'
        elif 'float' in vartype:
            convert = 'float'
        elif 'bool' in vartype:
            convert = 'bool'
        elif 'list' in vartype:
            convert = 'list'
        elif hasattr(state, val) or 'str' in vartype:  # val cannot be a globals value
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
        #  exec runs with state as its globals so the assignment lands in state
        changevar = var + ' = ' + val
        exec(changevar, vars(state))
        # restore to the correct type
        changetype = var + ' = ' + convert + '(' + var + ')'
        exec(changetype, vars(state))
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
        if 'layer' in state.detect or 'pause' in state.detect:
            logger.info('##########################################################')
            if 'layer' in state.detect:
                logger.info('Will start capturing images on first layer change')
            elif 'pause' in state.detect:
                logger.info('Will start capturing images on first pause in print stream')
            logger.info('##########################################################\n')

    if state.standby:
        logger.info('##########################################################')
        logger.info('Will not start until command=start received from http listener')
        logger.info('or ' + state.M3291 +  ' P"duetLapse3.start" sent as gcode')
        logger.info('##########################################################\n')

    logger.info('##########################################################')
    logger.info('Video will be created when printing ends')
    logger.info('or if requested from the UI or ' + state.M3291 +  ' P"duetLapse3.completed"')
    logger.info('##########################################################\n')

    logger.info('##########################################################')
    logger.info('If running from a console using the command line')
    if state.win:
        logger.info('Press Ctrl+Break one time to stop the program and create a video.')
        logger.info('On machines without the Break key - try Fn+Ctl+B')
    else:
        logger.info('Press Ctrl+C one time to stop the program and create a video.')
    logger.info('##########################################################\n')

    return

#  port_in_use, validate_port and force_quit are from duetPrintGuard

def port_in_use(ip_address, port):
    #  A successful connection means something is already listening there
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((ip_address, port)) == 0


def localIp():
    # The ip address of this computer on the network
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))  # doesn't even have to be reachable
        return s.getsockname()[0]
    except Exception as e:
        logger.critical(f'''Unknown error trying to get the local IP address''')
        logger.critical(f'''{e}''')
        force_quit(1)
    finally:
        s.close()


def validate_port(port=0, start_port=17800, max_tries=100):
    this_ip_address = localIp()

    if port:
        #  A port was provided - check that it is available
        if port_in_use(this_ip_address, port):
            logger.warning(f'''Port {port} is already in use - falling back to searching from {start_port}''')
            port = 0
    else:
        logger.info(f'''No port number was provided - searching for a free port starting at {start_port}''')

    if not port:
        #  No usable port yet - search for one starting at start_port
        for candidate in range(start_port, start_port + max_tries):
            if not port_in_use(this_ip_address, candidate):
                port = candidate
                break
        else:
            logger.critical(f'''No free port found between {start_port} and {start_port + max_tries - 1}''')
            force_quit(1)

    logger.info(f'''IP address {this_ip_address} with port {port} is available''')
    return this_ip_address, port


def force_quit(code):
    logger.critical(f'''Terminating the program with exit code {code}''')
    sys.exit(code)


def startup():
    setstartvalues()  # Default startup global values

    
    if state.httpListener and state.restarting is False:
        startHttpListener()


    checkforPrinter()  # Needs to be connected before following are executed

    if isPlugin(state.apiModel):  # Switch to local host as it may be more reliable than actual ip
        state.duet = "127.0.0.1"
        logger.info("Switching to 127.0.0.1")
        publishUiAddress(state.ip, state.port)

    logger.info('Initializing DL3msg queue')
    sendDuetGcode(state.apiModel,state.M3291 + ' B"Clear"') # Clear the message queue
     
    startmainLoop()

    logger.info('Initiating with action set to ' + state.action)
    nextAction(state.action)

def main():
    # Hooks for the printer communication module
    duet_printer.onDisconnected = lambda: startnextAction('waitforconnection')
    duet_printer.onMessages = handleMessages

    # Allow process running in background or foreground to be forcibly
    # shutdown with SIGINT (kill -2 <pid> or SIGTERM)
    signal.signal(signal.SIGINT, quit_sigint) # Ctrl + C
    signal.signal(signal.SIGTERM, quit_sigterm)
    # Globals
    # Set in startup code

    # Status flag for threads
    state.nextActionState = state.captureLoopState = state.makeVideoState = state.mainLoopState = state.terminateState = state.checkforconnectionState =  -1  #  All set as not running
    state.connectionState = state.restarting = False
    state.workingDirStatus = -1

    # timers
    state.mainLoopPoll = 5 # seconds
    state.mainLoopIterate = state.mainLoopPoll/3
    state.minPoll = 10  # seconds
    state.minseconds = 20  # seconds


    # Initial time for mainLoop events
    state.lastCaptureLoop = time.time()
    state.lastStatusCall = 0

    # logical state on start is unknown
    state.lastPrintState = state.lastDuetStatus = 'unknown' 

    # SBC session key
    state.urlHeaders = {}

    # Keep track of M3291 messages
    state.lastMessageSeq = 0

    # Allowed Commands 
    # commands = ['start','standby','pause','continue', 'restart', 'terminate']
 
    
    state.httpListener = False  # Indicates if an integral httpListener should be started
    state.win = False  # Windows OS
    state.pid = ''  # pid for this instance - used for temp filenames

    state.apiModel = ''

    init()
    # Simulated Image
    state.simulatedImage = base64.b64decode('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')

    listOptions()
    issue_warnings()
    startMessages()
    startup()

###########################
# Program  begins here
###########################

if __name__ == "__main__":  # Do not run anything below if the file is imported by another program
    
    main()