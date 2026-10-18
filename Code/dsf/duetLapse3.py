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
One control loop (main thread) and a video worker replace the mainLoop, nextAction, checkforConnection, terminate and makeVideo threads
Images are taken as soon as the layer or printer status changes (SBC: pushed by the WebSocket; standalone: at each status check)
Fixed pause (from the page or gcode) not stopping images
Fixed extratime not being added to the video at the end of a print
Fixed fast repeated login attempts when the printer is off at startup
Normal terminate exits cleanly instead of kill -9
Fixed gcode messages being ignored after the printer was reset (its message numbers start again)
Fixed duetLapse3 stopping (UNRECOVERABLE ERROR) when the printer reconnected
Wrong printer password: shown on the page, and no more tries until it is changed
The printer address, port and password can be changed on the page while the printer is not connected
Standalone boards: the SBC login is skipped
Fixed the control loop waking every 50ms while the printer was not connected
All the page's text is in ui/src/locales/en.json - ready for other languages.  Messages for the page carry a code (messages.py)
The page is told about changes as they happen (/api/events) instead of asking every 3 seconds
detect none is now detect timed (none is still accepted)
restart is now norestart (the opposite) - duetLapse3 gets ready for the next print unless norestart is set.  An old restart setting is still read
port is now UI_port, ip is UI_ip and duet is duet_ip.  The Config tab shows the printer address and page port in use
M3291 is a simple ring of the last 10 commands (global.DL3seq / DL3msg) that duetLapse3 only reads - no more Del / Clear
duetLapse3.json is compressed, base64 encoded and checksummed - recreated from the defaults if it is missing or fails the checksum
Settings renamed for clarity: duet_port, duet_password, image_dir, capture_on, capture_seconds, layer_interval, start_now, park (true/false), park_xy, park_wait,
  camera1_url, camera1_on, camera2_url, camera2_on, video_length, min_video_seconds, end_hold, ffmpeg_threads, no_log, no_video, delete_images, keep_files.
  instances oneip is one_per_folder.  keeplogs removed.  gcode change.<setting>= uses the new names
Removed unused code (getPidDirs, getThisInstance, lastaction, mainLoopIterate, getDuet's calledfrom) and printer_status.py
Removed poll - a capture pass runs at each status or layer change, otherwise every 5 seconds
Removed hidebuttons - the controls always show every button, greyed out when it can't be used
Removed maxffmpeg - ffmpeg threads are shared with the ffmpeg processes already running, and videos no longer wait for them
Removed the Info tab.  New Pause section (pause, movehead, rest) on the Config tab.  poll moved to Execution
Removed the Special Functions (execkey, M3291 settings) - the message macro is always M3291
nolog, verbose, keeplogs, novideo, deletepics, keepfiles moved to a new Files section
Fixed the printer password being shown on the Info tab and written to the log
Fixed timed capture (dontwait, or detect none with seconds) showing Waiting instead of Capturing when the printer is idle
Cameras can be switched off (enable1, enable2) without losing their url
Each camera has a folder in the print's folder, with images/ and videos/ folders: <print>/Camera1/images, <print>/Camera1/videos
Clean up at startup, deletepics and standby delete images but keep videos
Snapshot can make a video for one camera (/snapshot?camera=1 or 2) - the Video tab has a button for each camera
The page announces each video made (or not), wherever it was started - e.g. at the end of a print
New web page in Vue 3 + Vuetify 4 (built from ui/ into static/app) with the DWC 3.7 look - it follows DWC's light / dark theme
The page reads JSON from /api/... - the html tab routes (/tab/...) and the old ?display... calls are removed
ffmpeg: computed thread limit (ffmpegthreads, 0 = automatic), low priority (nice), -preset veryfast, -pix_fmt yuv420p, no shell
Added a Cameras tab - the camera urls, with a preview of each.  Saved urls are used straight away
The Video tab shows the Video settings - saved to duetLapse3.json and used straight away
Removed vidparam1 and vidparam2 (never used)
The controls are on the Status tab (the Controls tab is gone)
If port = 0 (or the port is in use) a free port is selected
The ip address in use is saved to duetLapse3.json and published to DWC as plugin data
The web server always runs
Removed the firmware version check
Version is read from the plugin manifest
Shared state moved to state.py, logging to logger_module.py, printer communication to duet_printer.py
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
import queue
import concurrent.futures
import psutil
import shutil
import pathlib
import stat
import signal
import base64
import hashlib
import zlib
import re
import math
import urllib.parse

import state  # Shared state - always use state.<name>
import camera
import logger_module
from logger_module import logger, currentFuncName
import duet_printer  # Communication with the printer
from messages import Message, coded
from duet_printer import (getDuet, loginPrinter, getDuetVersion, Jobname, Status, Layer, Position,
                          sendDuetGcode, isPlugin, stopPlugin, publishUiAddress)



def setstartvalues():
    logger.debug('*****  Initializing state and counters  *****')
    state.printState = 'Waiting'
    state.lastPrintState = 'Waiting'
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
    'Environment': {'duet_ip': '', 'duet_port': 80, 'duet_password': 'reprap', 'image_dir': '', 'instances': 'single'},
    'Files': {'no_log': False, 'verbose': False, 'no_video': False, 'delete_images': False, 'keep_files': False},
    'Execution': {'start_now': False, 'capture_seconds': 0, 'capture_on': 'layer', 'layer_interval': 1, 'standby': False, 'norestart': False},
    'Pause': {'park': False, 'park_xy': [0, 0], 'park_wait': 1},
    'Camera': {'camera1_url': '', 'camera1_on': True, 'camera2_url': '', 'camera2_on': True},
    'Video': {'end_hold': 0, 'fps': 10, 'min_video_seconds': 5, 'video_length': 0, 'ffmpeg_threads': 0},
    'UI': {'UI_port': 0, 'UI_ip': ''},
}
CHOICES = {'simulate': ['off', 'all', 'printer', 'camera'], 'instances': ['single', 'one_per_folder', 'many'],
           'capture_on': ['layer', 'pause', 'timed']}
configExtras = ['UI_ip']  # Written by duetLapse3, not read as a setting

def flatDefaults():
    return {key: val for section in DEFAULTS.values() for key, val in section.items()}

# duetLapse3.json is not plain JSON, so it is changed on the page rather than by hand.  It has two lines:
#   the sha256 checksum of the settings (as JSON), then the settings JSON compressed (zlib) and base64 encoded

def encodeConfig(config):
    text = json.dumps(config, indent=2).encode('utf-8')
    return hashlib.sha256(text).hexdigest() + '\n' + base64.b64encode(zlib.compress(text, 9)).decode('ascii') + '\n'

def decodeConfig(data):
    # The settings - ValueError if data is not in that form or its checksum does not match
    try:
        checksum, payload = data.split()
        text = zlib.decompress(base64.b64decode(payload, validate=True))
    except (ValueError, zlib.error) as e:  # binascii.Error is a ValueError
        raise ValueError('not a duetLapse3 settings file (' + str(e) + ')')
    if hashlib.sha256(text).hexdigest() != checksum:
        raise ValueError('the checksum does not match')
    config = json.loads(text.decode('utf-8'))
    if not isinstance(config, dict) or not all(isinstance(section, dict) for section in config.values()):
        raise ValueError('not a duetLapse3 settings file')
    return config

def readConfig(filename):
    with open(filename, encoding='ascii', errors='replace') as f:
        return decodeConfig(f.read())

def writeConfig(filename, config):
    # Written to a temporary file that then replaces the old one - so an interrupted save cannot leave a broken file
    temp = filename + '.tmp'
    with open(temp, 'w', encoding='ascii') as f:
        f.write(encodeConfig(config))
    os.replace(temp, filename)

def badSetting(filename, message):
    logger.critical('Invalid setting in ' + filename + ': ' + message)
    sys.exit(2)

def checkSetting(key, val, default):
    # Returns val as the same type as default.  Raises ValueError (with the reason) if it can't be
    if key == 'duet_port' and val in ['', None, 0, '0']:  # Blank means the standard http port
        return 80
    if isinstance(default, bool):  # Must be before int (bool is a kind of int)
        if isinstance(val, bool):
            return val
        if isinstance(val, str) and val.lower() in ['true', 'false']:
            return val.lower() == 'true'
        raise ValueError(Message('notBool', key + ' must be true or false, not ' + json.dumps(val), key = key, value = json.dumps(val)))
    if isinstance(default, int):
        try:
            return int(val)
        except (ValueError, TypeError):
            raise ValueError(Message('notWhole', key + ' must be a whole number, not ' + json.dumps(val), key = key, value = json.dumps(val)))
    if isinstance(default, list):
        try:
            val = [int(v) for v in val]
        except (ValueError, TypeError):
            val = []
        if len(val) != len(default):
            raise ValueError(Message('notList', key + ' must be a list of ' + str(len(default)) + ' numbers e.g. ' + json.dumps(default),
                                     key = key, count = len(default), example = json.dumps(default)))
        return val
    if key == 'capture_on' and val == 'none':  # The old name for timed
        return 'timed'
    if not isinstance(val, str):
        raise ValueError(Message('notText', key + ' must be text (in quotes), not ' + json.dumps(val), key = key, value = json.dumps(val)))
    if key in CHOICES and val not in CHOICES[key]:
        raise ValueError(Message('notChoice', key + ' must be one of ' + ', '.join(CHOICES[key]) + ', not "' + val + '"',
                                 key = key, choices = ', '.join(CHOICES[key]), value = val))
    return val

def loadSettings(filename):
    # Returns every setting: the defaults, replaced by any values in the config file
    # If the file does not exist, or can't be read or its checksum fails, it is created from the defaults
    config = None
    if not os.path.isfile(filename):
        logger.warning('No config file found at ' + filename + ' - creating it with default values')
    else:
        try:
            config = readConfig(filename)
        except (OSError, ValueError) as e:
            logger.warning('The config file ' + filename + ' could not be used: ' + str(e) + ' - creating it with default values')
    if config is None:
        config = {section: dict(keys) for section, keys in DEFAULTS.items()}
        try:
            writeConfig(filename, config)
        except OSError as e:
            logger.warning('Could not create config file ' + str(e))

    settings = flatDefaults()
    keys = {key for section in config.values() for key in section}
    for section in config.values():  # Sections are only for readability
        for key, val in section.items():
            if key in configExtras:
                continue
            if key == 'restart' and 'norestart' not in keys and isinstance(val, bool):  # The old setting - the opposite of norestart
                settings['norestart'] = not val
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
        section = next((sec for sec in config.values() if 'UI_ip' in sec), None)
        if section is None:
            section = config.setdefault('UI', {})
        if section.get('UI_ip') == ip:
            return
        section['UI_ip'] = ip
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


    # Derived  globals
    
    # Simulate
    state.simulate = args['simulate']

    # Environment
    
    setPrinter(args)

        
    state.image_dir = args['image_dir']
    
    
    state.instances = args['instances']
    
    state.no_log = args['no_log']
    
    state.verbose = args['verbose']

    state.port = args['UI_port']


    state.no_video = args['no_video']

    state.delete_images = args['delete_images']


    state.keep_files = args['keep_files']

    # Execution

    state.start_now = args['start_now']

    state.capture_seconds = args['capture_seconds']
    if state.capture_seconds != 0 and state.capture_seconds < state.minseconds:
        state.capture_seconds = state.minseconds

    state.capture_on = args['capture_on']

    state.park = args['park']

    state.layer_interval = args['layer_interval']
    if state.layer_interval < 1:
        state.layer_interval = 1

    state.park_xy = args['park_xy']

    state.park_wait = args['park_wait']
    if state.park_wait < 0:
        state.park_wait = 0

    state.standby = args['standby']

    state.norestart = args['norestart']
    state.restart = not state.norestart  # Get ready for the next print when one finishes

    # Camera

    state.camera1_url = args['camera1_url']

    state.camera2_url = args['camera2_url']

    state.camera1_on = args['camera1_on']

    state.camera2_on = args['camera2_on']

    # Video

    state.end_hold = args['end_hold']

    state.fps = args['fps']

    state.min_video_seconds = args['min_video_seconds']

    state.video_length = args['video_length']
    if state.video_length > 0:
       if state.video_length < state.min_video_seconds:
           state.video_length = state.min_video_seconds


    state.ffmpeg_threads = max(0, args['ffmpeg_threads'])



    ##### Configure the custom logger #####
    setdebug(state.verbose)

    # Create handler for console output - file output handler is created later if needed
    logger_module.setup_logger(state.duet, console = state.no_log is False)


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
    if state.image_dir == '':  # The settings folder - argument 1, or this program's folder
        state.image_dir = state.configdir
    # clean up the separators
    state.image_dir = state.image_dir.replace('\\', '/')
    if state.image_dir.startswith('.'):  #  this little trick so as not to drop ./ or ../
        state.image_dir = './' + state.image_dir
        state.image_dir = os.path.normpath(state.image_dir) # get slashes in correct direction


    state.topDir = os.path.join(state.image_dir, socket.getfqdn(), state.duetname)
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

    checkSeconds()

    # Select a free port if port = 0 (or the given port is in use) - same as duetPrintGuard
    state.ip, state.port = validate_port(state.port)
    state.httpListener = True
    saveUiAddress(state.ip)

    ########################################################################
    # Inform regarding valid and invalid combinations
    #########################################################################

    # Invalid Combinations that will abort program

    # Only http cameras are supported
    if state.simulate in ['all', 'camera'] and state.camera1_url == '':
        state.camera1_url = 'http://simulated'

    # A missing or invalid url does not stop duetLapse3 - the url can be set on the Cameras tab
    # Until then that camera is not used
    for key, name in [('camera1_url', 'Camera1'), ('camera2_url', 'Camera2')]:
        url = getattr(state, key)
        if url != '' and not camera.is_http_url(url):
            logger.info('************************************************************************************')
            logger.info('Invalid setting: ' + key + ' "' + url + '" is not an http url - ' + name + ' will not be used')
            logger.info('Use a snapshot url (preferred) or an MJPEG stream url - set it on the Cameras tab')
            logger.info('************************************************************************************\n')
            setattr(state, key, '')
    if cameraUrl(1) == '' and cameraUrl(2) == '':
        logger.info('************************************************************************************')
        logger.info('No camera in use - no images will be captured until one is set (and on) on the Cameras tab')
        logger.info('************************************************************************************\n')

    checkDependencies()  # Exits if ffmpeg is missing


    if (not state.park_xy == [0.0, 0.0]) and (not state.park) and state.capture_on != 'pause':
        logger.info('************************************************************************************')
        logger.info(
                'Invalid Combination: "park_xy {0:1.2f} {1:1.2f}" requires either "park true" or "capture_on pause".'.format(
                        state.park_xy[0], state.park_xy[1]))
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if state.park and state.capture_on == 'pause':
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: "park true" causes this program to pause printer when')
        logger.info('other events are detected, and "capture_on pause" requires the gcode on the printer')
        logger.info('contain its own pauses.  These cannot be used together.')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    return # init()


def issue_warnings():
    # Information and Warnings
    if state.capture_seconds <= 0 and 'timed' in state.capture_on:
        logger.info('************************************************************************************')
        logger.info('Warning:: capture_seconds ' + str(state.capture_seconds) + ' and capture_on ' + state.capture_on + ' nothing will be captured.')
        logger.info('Specify "capture_on timed" with "capture_seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************\n')

    if state.capture_seconds > 0 and (not 'timed' in state.capture_on):
        logger.info('************************************************************************************')
        logger.info('Warning: capture_seconds ' + str(state.capture_seconds) + ' and capture_on ' + state.capture_on + ' will trigger on both.')
        logger.info('Specify "capture_on timed" with "capture_seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************\n')

    if state.capture_seconds > 0  and 'timed' in state.capture_on:
        logger.info('************************************************************************************')
        logger.info('Warning: capture_seconds ' + str(state.capture_seconds) + ' and capture_on ' + state.capture_on)
        logger.info('This combination implies start_now and will be set automatically')
        logger.info('************************************************************************************\n')
        state.start_now = True

    if 'pause' in state.capture_on:
        logger.info('************************************************************************************')
        logger.info('* Note "capture_on pause" means that the G-Code on the printer already contains pauses,')
        logger.info('* and that this program will detect them, take a photo, and issue a resume.')
        logger.info('* Head position during those pauses is can be controlled by the pause.g macro ')
        logger.info('* on the duet, or by specifying "park_xy nnn nnn".')
        logger.info('*')
        logger.info('* If instead, it is desired that this program force the printer to pause with no')
        logger.info('* pauses in the gcode, specify either:')
        logger.info('* "park true capture_on layer" or "park true capture_seconds nnn".')
        logger.info('************************************************************************************\n')

    if state.park:
        logger.info('************************************************************************************')
        logger.info('* Note "park true" means this program will pause the printer when the capture_on and / or ')
        logger.info('* capture_seconds settings trigger.')
        logger.info('*')
        logger.info('* If instead, it is desired that this program detect pauses that are already in')
        logger.info('* in the gcode, specify:')
        logger.info('* "capture_on pause"')
        logger.info('************************************************************************************\n')

    if state.no_video and state.delete_images:
        logger.info('************************************************************************************')
        logger.info('Warning: The combination of no_video and delete_images will not create any output')
        logger.info('************************************************************************************\n')

    return # issue_warnings()


####################################################
# Log the settings being used
####################################################

def listOptions():
    logger.info("################### Options at start of this print job  #####################")
    for section, keys in DEFAULTS.items():
        logger.info('# ' + section)
        for key in keys:
            if key != 'duet_password':  # Never logged
                logger.info(key + '  =  ' + str(getattr(state, key, '')))
    logger.info('-----------------------------------------------------------------------\n\n')


####################################################
# Logfile setup
####################################################

def setuplogfile():  # Called at start - one logfile, in the config folder, for the whole run
    if state.no_log is False:
        state.logfilename = os.path.join(state.configdir, logFileName)
        logger_module.create_log_file(state.logfilename)

        logger.info('duetLapse3 Version --- ' + str(duetLapse3Version))
        logger.info('Process Id  ---  ' + str(state.pid) )
        logger.info('Settings from  ---  ' + state.configfile)
        logger.info('-------------------------------------------------------------------------------\n')
    else:
        state.logfilename = 'None (no_log is set)'


def setNextWorkingDir():  # Called at start and restart - the folder for the next job's images
    state.pidIncrement += 1
    state.nextWorkingDir = os.path.join(state.topDir, state.pid + '_' + str(state.pidIncrement))

####################################################
# Misc settings
####################################################
   
def setdebug(val): # How much output
    logger_module.set_log_level(val)



def checkSeconds():
    # Seconds needs to be an integer multiple of mainLoopPoll - capture passes are that far apart when nothing changes
    if state.capture_seconds != 0:
        multiplier,remainder = divmod(max(state.capture_seconds,state.minseconds), state.mainLoopPoll)    
        if remainder == 0: # use the max
            updateglobals('capture_seconds', str(max(state.capture_seconds,state.minseconds))) 
        else:  # round down
            updateglobals('capture_seconds', str(state.mainLoopPoll * multiplier))     
        
        # Check for start_now
        if state.capture_seconds > 0 and 'timed' in state.capture_on:
            updateglobals('start_now', 'True')       
      
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

RECONNECT_QUICK = 4     # Quick attempts (every mainLoopPoll seconds) before slowing down
RECONNECT_SLOW = 3*60   # Then try every 3 minutes

def reconnectDelay(attempts):
    return state.mainLoopPoll if attempts <= RECONNECT_QUICK else RECONNECT_SLOW

def setPrinter(settings):
    # Use the printer settings (duet_ip, duet_port, duet_password) in settings - from duetLapse3.json, or changed on the page
    if 'duet_ip' in settings:
        state.duet = str(settings['duet_ip']).strip() or localIp()  # Blank = this computer
        if state.simulate in ['all','printer']:
            state.duet = 'SIMULATED'
    if 'duet_port' in settings:
        state.duet_port = checkSetting('duet_port', settings['duet_port'], 80)
    if 'duet_password' in settings:
        state.duet_password = settings['duet_password']
        #  password is not displayed

def printerChanged(settings):
    # Called by the page when the printer settings are changed while the printer is not connected - try again at once
    setPrinter(settings)
    state.connectError = ''
    logger.info('Printer settings changed on the page - trying to connect to ' + duet_printer.printerAddress())
    state.connectRetry.set()
    wakeControlLoop()

def wrongPassword(code):
    # True (and the reason is shown on the page) if the printer refused the password - no more tries until it is changed
    if code != 403:
        return False
    if not state.connectError:
        state.connectError = Message('wrongPassword', 'The printer at ' + duet_printer.printerAddress() + ' did not accept the password',
                                     printer = duet_printer.printerAddress())
        logger.info('!!!!! ' + state.connectError + ' - no more tries until the printer settings are changed on the page !!!!!')
    return True

def waitForRetry(seconds):
    # Wait seconds (None = until the printer settings are changed on the page) - or less if they are changed or duetLapse3 is terminating
    end = None if seconds is None else time.time() + seconds
    while state.terminateState != 1 and (end is None or time.time() < end):
        if state.connectRetry.wait(1):
            state.connectRetry.clear()
            return

def checkforPrinter():
    # The first connection to the printer.  Keeps trying until connected (or terminated)
    attempts = 0
    while state.apiModel == '' and state.terminateState != 1:
        Model, code = loginPrinter()
        if Model == '' and wrongPassword(code):
            state.connectionState = False
            waitForRetry(None)
            attempts = 0
            continue
        if Model == '': #  Could not connect
            if attempts == 0:
                logger.info('#########################################################')
                logger.info('The printer at ' + duet_printer.printerAddress() + ' is not responding')
                logger.info('Check the ip address or logical printer name is correct\n')
                logger.info('Is the printer turned on?')
                logger.info('Duet software must support rr_model or /machine/status')
                logger.info('########################################################\n')
            state.connectionState = False
            attempts += 1
            logger.info('Will try to connect again in ' + str(reconnectDelay(attempts)) + ' seconds')
            waitForRetry(reconnectDelay(attempts))
            continue

        if state.firstConnect is None:
            state.firstConnect = False
            state.printerVersion = getDuetVersion(Model)
            if state.printerVersion is None:
                state.printerVersion = 'unknown'
            logger.info(f"""Version Check returned --> {state.printerVersion}""")

        state.connectionState = True
        state.connectError = ''
        state.apiModel = Model # We have a good connection
        logger.info('###############################################################')
        logger.info('Connected to printer at ' + duet_printer.printerAddress())
        logger.info('Using Duet version ' + state.printerVersion)
        logger.info('Using API interface ' + state.apiModel)
        logger.info('###############################################################\n')
        return


def printerLost():
    # Called by duet_printer when the printer has stopped answering - the control loop reconnects
    logger.info('----------------  Waiting for printer to reconnect -----------------')


def reconnectPrinter(model):
    # Called by the control loop while the printer is not connected.  True when connected again
    # model '' finds out what the printer is (its settings were changed on the page)
    model, code = loginPrinter(model)
    if code != 200 or model == '':
        wrongPassword(code)
        return False
    state.apiModel = model
    state.connectionState = True
    state.connectError = ''
    logger.info('-----------------------  Reconnected to printer ----------------------')
    logger.info('Carrying on in the ' + str(state.action) + ' state')
    return True


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
    state.filesVersion += 1
    return msg

def cameraFolder(directory):
    # The CameraN name if directory is a camera's subfolder of a print's folder, else ''
    name = os.path.basename(os.path.normpath(directory))
    return name if re.fullmatch(r'Camera[0-9]', name) else ''

def printFolder(directory):
    # (print folder, CameraN or '') for a print's folder, one of its CameraN folders, or a CameraN/images or CameraN/videos folder
    d = os.path.normpath(directory)
    name = os.path.basename(d)
    if name in ['images', 'videos'] and cameraFolder(os.path.dirname(d)):
        return os.path.dirname(os.path.dirname(d)), cameraFolder(os.path.dirname(d))
    if cameraFolder(d):
        return os.path.dirname(d), name
    return d, ''

def imageFolder(jobdir, cameraname):
    return os.path.join(jobdir, cameraname, 'images')

def videoFolder(jobdir, cameraname):
    return os.path.join(jobdir, cameraname, 'videos')

def countImages(folder, cameraname):
    try:
        return sum(1 for f in os.listdir(folder) if f.startswith(cameraname + '_') and f.endswith('.jpeg'))
    except OSError:
        return 0

videoEventsLock = threading.Lock()

def videoEvent(ok, message, camera = '', file = ''):
    # The result of making a video, for the page - it announces each one, wherever the video was started
    # (end of a print, restart, gcode, or the page).  The last 10 are kept
    with videoEventsLock:
        state.videoSeq += 1
        event = {'seq': state.videoSeq, 'time': time.time(), 'ok': ok, 'camera': camera,
                 'file': file, 'name': os.path.basename(file), 'message': message, 'messageCode': coded(message)}
        state.videoEvents = (state.videoEvents + [event])[-10:]

def createVideo(directory, cameras = None):
    # Make a video for each camera with images (or just the cameras listed e.g. ['Camera2']).
    # directory is a print's folder, or one camera's folder (CameraN, CameraN/images or CameraN/videos).
    # Images are in <print>/CameraN/images - videos go in <print>/CameraN/videos
    logger.info('Create Video from ' + str(directory))
    if not os.path.isdir(directory):
        msg = 'Error: No permission or directory not found'
        logger.info(msg)
        videoEvent(False, msg)
        return msg

    jobdir, camera = printFolder(directory)
    if camera:  # One camera's folder - only that camera
        cameras = [camera]

    found = {}  # cameraname: (folder with its images, number of images)
    for cameraname in ['Camera1', 'Camera2']:
        if cameras and cameraname not in cameras:
            continue
        folder = imageFolder(jobdir, cameraname)
        count = countImages(folder, cameraname)
        if count:
            found[cameraname] = (folder, count)

    if not found:
        msg = 'Cannot create a video.\n\
              Are there any images captured?'
        logger.info(msg)
        videoEvent(False, Message('videoNoImages', 'Cannot create a video - there are no images in ' + os.path.basename(jobdir), folder = os.path.basename(jobdir)))
        return msg

    for cameraname, (folder, frame) in found.items():
        if state.video_length > 0:
            if frame < state.video_length:
                thisfps = 1.0                         #  make it as long as we can     
            else:
                thisfps = float(frame/state.video_length)       #  set for video_length duration
        else:
            thisfps = float(state.fps)                      #  set for fixed fps


        if frame/thisfps < state.min_video_seconds:
            msg = 'Error: ' + cameraname + ': Cannot create video shorter than ' + str(state.min_video_seconds) + ' second(s).\n Length would have been ' + str(frame/thisfps) + ' second(s).' 
            logger.info(msg)
            logger.info('frame = ' + str(frame) + ' thisfps = ' + str(thisfps) + ' fps = ' + str(state.fps) + ' video_length = ' + str(state.video_length) + ' min_video_seconds = ' + str(state.min_video_seconds))
            videoEvent(False, Message('videoTooShort', cameraname + ': not enough images for a video (' + str(frame) + ' - ' + str(imagesForVideo()) + ' needed)',
                                      camera = cameraname, frames = frame, needed = imagesForVideo()), cameraname)
            return msg

        logger.info(cameraname + ': now making ' + str(frame) + ' frames into a video with fps = ' +str(thisfps))
        if 250 < frame:
            logger.info("This can take a while...")

        timestamp = time.strftime('%a-%H-%M', time.localtime())

        videos = videoFolder(jobdir, cameraname)
        try:
            os.makedirs(videos, exist_ok=True)
        except OSError as e:
            msg = 'Error: could not create ' + videos + ' -- ' + str(e)
            logger.info(msg)
            videoEvent(False, msg, cameraname)
            return msg
        fn = os.path.join(videos, os.path.basename(jobdir) + '_' + cameraname + '_' + timestamp + '.mp4')
        tmpfn = os.path.join(videos, '.tmpvideo.mp4')  # Hidden from the Files tab until it is finished
        location = os.path.join(folder, cameraname + '_%08d.jpeg')

        cmd = ffmpegCommand(thisfps, location, tmpfn)

        if runsubprocess(cmd) is False:
            msg = ('!!!!!  There was a problem creating the video for '+cameraname+' !!!!!')
            logger.info(msg)
            videoEvent(False, Message('videoProblem', 'There was a problem creating the video for ' + cameraname + ' (see the log)', camera = cameraname), cameraname)
            if os.path.isfile(tmpfn): 
                try:
                    os.remove(tmpfn)
                except OSError as e:
                    logger.info('Error deleting file ' + str(e))
            return msg
        else:
            try:
                shutil.move(tmpfn, fn)
                logger.info('Video processing completed for ' + cameraname)
                logger.info('Video is in file ' + fn)                
                msg = 'Video(s) successfully created'
                videoEvent(True, Message('videoCreated', 'Video created'), cameraname, fn)
            except shutil.Error as e:
                msg = 'Error on move of temp video file ' + str(e)
                logger.info(msg)
                videoEvent(False, msg, cameraname)
 
    return msg


def ffmpegRunning():
    # The ffmpeg processes running now - e.g. other duetLapse3s making videos for other printers
    count = 0
    for p in psutil.process_iter(['name']):  # Processes that end during the scan are skipped
        if 'ffmpeg' in (p.info['name'] or ''):
            count += 1
    return count

def ffmpegThreads():
    # Threads for one ffmpeg - the cpu cores that are free now, leaving one spare, shared with any ffmpeg already running
    # so that making videos does not overwhelm the computer (e.g. while printing)
    if state.ffmpeg_threads > 0:  # Set by the user
        return state.ffmpeg_threads
    cores = os.cpu_count() or 1
    try:
        load = os.getloadavg()[0]  # Average number of busy cores over the last minute
    except (AttributeError, OSError):  # Not available on Windows
        load = 0
    free = int(cores - load - 1)
    running = ffmpegRunning()
    threads = max(1, free // (running + 1))  # This one and those running share the free cores
    logger.info('ffmpeg threads = ' + str(threads) + ' (' + str(cores) + ' cores, load ' + '{:.1f}'.format(load) + ', other ffmpeg running ' + str(running) + ')')
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


def getRunningInstancePids():
    pidlist = []
    for p in psutil.process_iter(['name']):  # Processes that end during the scan are skipped
        if 'python' in (p.info['name'] or ''):  # Check all other python instances
            pidlist.append(str(p.pid))
    return pidlist


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
    jobname = getDuet(Jobname)

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
        if state.keep_files: return

        for dirs in dirlist: #  Delete old dirs and files
            split_dirs = dirs.split("_", 1)
            dirpid = split_dirs[0]

            if dirpid not in pidlist:  # only if not running
                fn = os.path.join(state.topDir, dirs)
                if os.path.isdir(fn):  # a print's folder - its videos are kept
                    deleteImages(fn)
                elif dirs.endswith('.log'):  # Per-print logs left by versions before 6.0
                    deleteFileFolder(fn)

    elif phase == 'standby':  # deleted images directory will be recreated on first capture
        if state.workingDirStatus != -1:
            deleteImages(state.workingDir)
            state.workingDirStatus = -1
            if os.path.isdir(state.workingDir):  # It has a video - the next images go in a new folder
                setNextWorkingDir()

    elif phase == 'restart':  # new image directory will be created on first capture
        pass

    elif phase == 'terminate':
        if state.keep_files: return

        if state.delete_images:
            for dirs in dirlist:
                fn = os.path.join(state.topDir, dirs)
                if os.path.isdir(fn):  # a print's folder - its videos are kept
                    deleteImages(fn)
                    state.workingDirStatus = -1
            # Assume sucess even if error from above
            state.workingDirStatus = -1
    return  # cleanupFiles

def startNow():
    #  Determine if program should logically start now
    if state.standby:
        state.action = 'standby'
        return False
    elif (state.capture_seconds > 0) and (state.start_now or 'timed' in state.capture_on):
        state.action = 'start'
        return True
    else:
        state.action = 'start'
        return False


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
    # single - only one duetLapse3 can run.  one_per_folder - one per settings folder (i.e. per printer).  many - no limit
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
        if instances == 'one_per_folder' and folder == state.configdir:
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
    
    state.duetStatus, _ = getDuet(Status)
    if state.connectionState is False or state.duetStatus == 'idle':
        return
    
    loopmax = 10  # sec
    loopinterval = 0.5  # sec
    loopcount = loopmax / loopinterval
    if state.park:  # duetLapse3 is controlling when to pause
        logger.debug('Requesting pause via M25')
        sendDuetGcode(state.apiModel, 'M25')  # Ask for a pause
        loop = 0
        while True:
            time.sleep(loopinterval)  # wait and try again    
            state.duetStatus, _ = getDuet(Status)
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
        if not state.park_xy == [0.0, 0.0]:  # optional repositioning of head
            logger.debug('Moving print head to X{0:4.2f} Y{1:4.2f}'.format(state.park_xy[0], state.park_xy[1]))
            sendDuetGcode(state.apiModel, 'G0 X{0:4.2f} Y{1:4.2f}'.format(state.park_xy[0], state.park_xy[1]))
            loop = 0
            while True:
                time.sleep(loopinterval)  # wait and try again
                xpos, ypos, _ = getDuet(Position)
                if state.connectionState is False:
                    return
                if (abs(xpos - state.park_xy[0]) < .05) and (
                        abs(ypos - state.park_xy[1]) < .05):  # close enough for government work
                    break
                else:
                    loop += 1
                if loop >= loopcount:  # limit the counter in case there is a problem
                    logger.info('Timeout after ' + str(loopmax) + 's')
                    logger.info('Target X,Y: ' + str(state.park_xy[0]) + ',' + str(state.park_xy[1]))
                    logger.info('Actual X,Y: ' + str(xpos) + ',' + str(ypos))
                    break
        time.sleep(state.park_wait)  # Wait to let camera feed catch up

    return


def unPause():  # Only gets called if duetStatus = paused
    if state.connectionState is False: # This traps the call being made unnecessarily
        return
    #  duetStatus, _ = getDuet(Status)
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
            state.duetStatus, _ = getDuet(Status)
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


def setCameraFiles():
    # Each camera's images go in its own folder in the print's folder: <print>/Camera1/images/Camera1_00000001.jpeg
    # (and its videos in <print>/Camera1/videos)
    for number in ['1', '2']:
        setattr(state, 'camfile' + number, os.path.join(state.workingDir, 'Camera' + number, 'images', 'Camera' + number + '_'))

def onePhoto(cameraname, weburl):

    if state.workingDirStatus == -1: # Create as late as possible
        state.workingDir = createworkingDir()
        setCameraFiles()

    if state.workingDirStatus == 0: # Keep checking until jobname is known
        state.workingDir = renameworkingDir(state.workingDir)
        setCameraFiles()

    if cameraname == 'Camera1':
        state.frame1 += 1
        s = str(state.frame1).zfill(8)
        fn = state.camfile1 + s + '.jpeg'
    else:
        state.frame2 += 1
        s = str(state.frame2).zfill(8)
        fn = state.camfile2 + s + '.jpeg'

    try:
        os.makedirs(os.path.dirname(fn), exist_ok=True)  # The camera's subfolder - made with its first image
    except OSError as e:
        logger.info('Could not create folder for ' + fn + ' -- ' + str(e))

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

    zn = getDuet(Layer)
    if state.connectionState is False:
        return
    if zn == -1:
        layer = 'None'
    else:
        layer = str(zn)

    if state.park and zn < 1:  # Dont capture anything until first layers is done
        logger.debug('Bypassing onePhoto from oneInterval because park is set and layer = ' + str(zn))
    else:    
        if 'layer' in state.capture_on:
            checkForPause(zn)
            if zn%state.layer_interval == 0: #  Every layer_interval layers
                if (not zn == state.zo1 and cameraname == 'Camera1') or (not zn == state.zo2 and cameraname == 'Camera2'):
                    # Layer changed, take a picture.
                    logger.info('Layer - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after layer change')
                    onePhoto(cameraname, weburl)

        elif ('pause' in state.capture_on) and (state.duetStatus == 'paused'):
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

    if (state.capture_seconds > 0) and (state.capture_seconds < elap) and (state.start_now or 'timed' in state.capture_on or zn >= 1):
        checkForPause(zn)
        logger.info('Time - ' + cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after ' + str(
                state.capture_seconds) + ' seconds')
        onePhoto(cameraname, weburl)

def cameraUrl(number):
    # The url of a camera that is in use - '' if it has no url or is switched off
    if not getattr(state, 'camera' + str(number) + '_on'):
        return ''
    return getattr(state, 'camera' + str(number) + '_url')

def imagesForVideo():
    # The fewest images that make a video - createVideo refuses one shorter than min_video_seconds
    if state.video_length > 0:  # Fewer images than video_length seconds are shown at 1 per second
        return max(1, int(state.min_video_seconds))
    return max(1, math.ceil(state.min_video_seconds * state.fps))

def getVideoMsg():
    seconds = None
    if state.video_length > 0:
        if state.frame1 > state.video_length:
            seconds = state.video_length
        elif state.frame1 >= state.min_video_seconds:  # As createVideo - min_video_seconds is enough
            seconds = state.frame1
    elif state.frame1 > 0 and state.frame1/state.fps >= state.min_video_seconds:  # As createVideo - min_video_seconds is enough
        seconds = state.frame1/state.fps
    if seconds is None:
        return Message('videoNotEnough', 'Not enough images for video to be created')
    return Message('videoWillBe', 'Video will be ' + str(seconds) + ' seconds long', seconds = str(seconds))

def makeVideo(directory, xtratime = False, cameras = None):  #  Adds and extra frame
    try:
        # Get a final frame
        # Make copies if appropriate

        if xtratime and state.end_hold >= 1: #  Do not add images if called from snapshot or video
            if cameraUrl(1) != '':   #  Camera 1
                logger.debug('For Camera1')
                oneInterval('Camera1', cameraUrl(1), True)
                ## if end_hold != 0 and frame1/fps > min_video_seconds:
                if state.frame1 > 0:
                    state.frame1 = copyLastFrame(state.camfile1, state.frame1)

            if cameraUrl(2) != '':   #  Camera 2
                logger.debug('For Camera2')
                oneInterval('Camera2', cameraUrl(2), True)
                ## if end_hold != 0 and frame2/fps > min_video_seconds:
                if state.frame2 > 0:
                    state.frame2 = copyLastFrame(state.camfile2, state.frame2)

        result = createVideo(directory, cameras)
        return result
    except Exception as e:
        logger.info('!!!!!#####!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN MAKE VIDEO -- ' + str(e))
        quit_forcibly()        

def copyLastFrame(f, frame):  # Makes copies and updates frame counter
    logger.info('Copying last frame to extend video by ' +str(state.end_hold) + ' seconds')
    fr = str(frame).zfill(8)
    sourcefile = f + fr + '.jpeg'
    copies = int(state.end_hold)*int(state.fps)
    #  copies = end_hold*fps
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
    # Runs in the control loop.  The video (if any) is finished first
    setdebug(True)  # Force verbose messaging

    state.terminateState = 1
    logger.info('Terminating')

    #  Make sure video creation is complete
    logger.debug('Wait for video to complete')
    waitforMakeVideo()

    cleanupFiles('terminate')

    if state.restart:
        # wait for jobname to be reset
        jobname = getDuet(Jobname)
        loopcounter = 0
        if jobname != '':
            logger.info('Waiting for printjob to complete')
        while jobname !='' and loopcounter < 30:  # Don't wait more than a minute
            time.sleep(2)
            loopcounter += 1
            jobname = getDuet(Jobname)
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
        closeHttpListener()
        logger.info('Program Terminated')
        if isPlugin(state.apiModel):
            stopPlugin(state.apiModel, 'duetLapse3')  # DSF stops this program
            time.sleep(10)
        exitProgram(0)

def quit_sigint(*args):
    logger.info('Terminating because of Ctl + C (SIGINT)')
    quit_forcibly()

def quit_sigterm(*args):
    logger.info('Terminating because of SIGTERM')
    quit_forcibly()  

def quit_forcibly():
    state.restart = False
    logger.info('!!!!! Forced Termination !!!!!')
    exitProgram(1)

def exitProgram(code):
    # Write out the log, then end the program and all its threads straight away
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            pass
    os._exit(code)

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
        state.min_video_seconds = max(0, thisminvideo)  # 0 is allowed, as at startup
        logger.info('min_video_seconds changed to: ' + str(state.min_video_seconds))
    except ValueError as e:
        logger.info('Error changing min_video_seconds: ' + str(e))

def changeMaxvideo(thismaxvideo):
    try:
        thismaxvideo = int(thismaxvideo)
        state.video_length = max(0, thismaxvideo)
        logger.info('video_length changed to: ' + str(state.video_length))
    except ValueError as e:
        logger.info('Error changing video_length: ' + str(e))

def deleteImages(folder):
    # Delete a print's images and keep its videos.  Folders left empty are removed (including the print's folder)
    for cameraname in ['Camera1', 'Camera2']:
        deleteFileFolder(imageFolder(folder, cameraname))
    for dirpath, _, _ in os.walk(folder, topdown=False):  # Remove empty folders, deepest first
        try:
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
        except OSError:
            pass
    logger.debug('Deleted the images in ' + folder)

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
        state.filesVersion += 1
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

    from fastapi.staticfiles import StaticFiles

    class RevalidatedStaticFiles(StaticFiles):
        # The browser checks (a quick 304 if unchanged) before using a cached copy - so an updated plugin's page is used
        async def get_response(self, path, scope):
            response = await super().get_response(path, scope)
            response.headers['Cache-Control'] = 'no-cache'
            return response

    routes.dl3 = sys.modules[__name__]  # Gives the routes access to this module's functions
    app = FastAPI(title='duetLapse3', version=duetLapse3Version)
    app.mount('/static/app', RevalidatedStaticFiles(directory=routes.appDir, check_dir=False), name='app')  # The built page (ui/)
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


###################################
#  Control
#  One control loop, in the main thread, does everything in order: commands (from the web page,
#  gcode messages and the end of a print), checking the printer, capture passes and reconnecting.
#  Videos are made one at a time by the video worker.  The web server and the SBC WebSocket have their own threads
###################################

commandQueue = queue.Queue()  # (command, done) - done is a threading.Event set once the command is carried out, or None
WAKE = 'wake'                 # Not a command - wakes the control loop (the printer status, layer or messages changed)
videoWorker = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='makeVideo')  # One video at a time, in order

def queueAction(command, done = None):
    # Ask the control loop to carry out command (start, standby, pause, continue, restart, completed).  From any thread
    if state.terminateState == 1: # Block it if terminating
        logger.info(command + ' ignored - terminating')
        if done is not None:
            done.set()
        return
    commandQueue.put((command, done))

def wakeControlLoop():
    # Called by duet_printer when the SBC pushes a status, layer or message change
    commandQueue.put((WAKE, None))

def startMakeVideo(directory, xtratime = False, thread = True, cameras = None):
    # Make the video(s) on the video worker.  thread = False waits for the result.  cameras e.g. ['Camera2'] - default all
    if state.terminateState == 1: # Block it if terminating
        return 'Cannot create video when Terminating'
    state.videoJob = videoWorker.submit(makeVideo, directory, xtratime, cameras)
    if thread:
        return
    return state.videoJob.result()

def waitforMakeVideo():
    job = state.videoJob
    if job is not None:
        logger.debug('********* Waiting for makeVideo to finish *********')
        try:
            job.result()
        except Exception as e:
            logger.info('Error making video ' + str(e))
    logger.debug('makeVideo is not running')


def controlLoop():
    # Runs until duetLapse3 ends.  Sleeps until a command arrives, the printer changes (SBC), or something is due:
    #   a status check and a capture pass every mainLoopPoll seconds, or a reconnect attempt
    # A capture pass also runs straight away when the printer status or layer changes - so layer images are taken at the layer change
    logger.info('###########################')
    logger.info('Starting control loop')
    logger.info('###########################\n')
    lastSeen = None     # (status, layer) at the last capture pass
    connected = state.connectionState
    reconnectAt = 0
    reconnectAttempts = 0
    reconnectModel = state.apiModel  # '' after the printer settings are changed on the page
    while True:
        try:
            if connected and not state.connectionState:  # Lost since the last time round
                reconnectAt, reconnectAttempts = time.time(), 0
            connected = state.connectionState

            if connected:
                due = min(state.lastCaptureLoop, state.lastStatusCall) + state.mainLoopPoll
            else:
                due = reconnectAt  # No capture passes until connected again
            try:
                command, done = commandQueue.get(timeout = min(60, max(0.05, due - time.time())))
            except queue.Empty:
                command, done = None, None

            if command is not None and command != WAKE:
                nextAction(command)
                if done is not None:
                    done.set()
                continue

            if not state.connectionState:
                if state.connectRetry.is_set():  # The printer settings were changed on the page
                    state.connectRetry.clear()
                    reconnectAt, reconnectAttempts, reconnectModel = 0, 0, ''
                if time.time() >= reconnectAt:
                    if reconnectPrinter(reconnectModel):
                        lastSeen = None
                        reconnectModel = state.apiModel
                        state.duetStatus, _ = getDuet(Status)  # The status now - not the one from before
                    elif state.connectError:  # Wrong password - no more tries until it is changed on the page
                        reconnectAt = math.inf
                    else:
                        reconnectAttempts += 1
                        reconnectAt = time.time() + reconnectDelay(reconnectAttempts)
                continue

            if command == WAKE or time.time() >= state.lastStatusCall + state.mainLoopPoll:
                state.duetStatus, _ = getDuet(Status)
                if not state.connectionState:
                    continue

            seen = (state.duetStatus, Layer())  # Layer comes from the same object model read - no extra request
            if seen != lastSeen or time.time() >= state.lastCaptureLoop + state.mainLoopPoll:  # e.g. timed (seconds) images
                lastSeen = seen
                capturePass()
        except Exception as e:
            logger.info('!!!!! UNRECOVERABLE ERROR ENCOUNTERED IN CONTROL LOOP -- ' + str(e))
            quit_forcibly()

def stateMachine(currentState):
    newState = currentState
    if currentState == 'Waiting':
        if state.duetStatus == 'processing' or state.start_now or (state.duetStatus in ['paused','pausing'] and state.capture_on != 'timed'):
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
        elif state.start_now or 'timed' in state.capture_on:  # Timed capture - carries on whatever the printer is doing
            pass
        else:
            newState = 'Waiting'
    elif currentState == 'Completed':
        pass
    else:
        logger.info('GROSS LOGIC ERROR IN STATE MACHINE')

    logger.debug('****** stateMachine:')
    logger.debug('newstate = ' + str(newState))
    logger.debug('currentState = ' + str(currentState))
    logger.debug('duetStatus = ' + str(state.duetStatus))
    logger.debug('lastDuetStatus = ' + str(state.lastDuetStatus))
    logger.debug('start_now = ' + str(state.start_now))
    logger.debug('capture_on = ' + str(state.capture_on))
    logger.debug('terminateState = ' + str(state.terminateState))
    logger.debug('******')

    if newState != currentState:
        logger.info('****** Print State changed to: ' + newState + ' from ' + currentState + '*****')
    return newState        

def capturePass():
    # One look at the printer: update the print state, take any images that are due, and end the job when the print has finished

    if state.connectionState is False or state.action == 'standby':
        logger.debug('No Capture needed')
        state.printState = 'Waiting'
        state.lastCaptureLoop = time.time()
        return

    if state.duetStatus != state.lastDuetStatus:
        logger.info('****** Duet status changed to: ' + str(state.duetStatus) + ' from ' + str(state.lastDuetStatus) + ' *****')

    state.printState = stateMachine(state.printState)

    if state.printState == 'Capturing' and state.action == 'start':  # pause stops images - but not the end of print check
        if cameraUrl(1) != '':
            logger.debug('Calling oneInterval for Camera 1')
            oneInterval('Camera1', cameraUrl(1))
        if cameraUrl(2) != '':
            logger.debug('Calling oneInterval for Camera 2')
            oneInterval('Camera2', cameraUrl(2))
        state.duetStatus, _ = getDuet(Status)  #  latest state to avoid polling delay
        if state.duetStatus == 'paused' and state.park: # will be ignored if a manual pause
            unPause()  # Nothing should be paused at this point
        state.printState = stateMachine(state.printState)

    if state.printState == 'Completed' and state.lastPrintState != 'Completed':  # Once - later passes may run before it is carried out
        logger.info('Print Job Completed')
        queueAction('completed')

    state.lastPrintState = state.printState
    state.lastDuetStatus = state.duetStatus
    state.lastCaptureLoop = time.time()

def nextAction(nextaction):
    # Carry out a command - in the control loop (or at startup)

    logger.debug('Calling nextaction ' + nextaction + ' from ' + currentFuncName(2) + ' --> '  + currentFuncName(1) + ' --> '  + currentFuncName(0))
    logger.info('++++++ ' + nextaction + ' state requested ++++++')

    if state.connectionState is False: #traps any requests during a disconnect
        logger.info('nextaction ignored - the printer is not connected')
        return

    state.action = nextaction  # default

    # This test is positionally sensitive
    if nextaction == 'completed':  # end of a print job
        state.printState = 'Completed'  # Update may have come from message Q
        if state.no_video:
            logger.info('Video creation was skipped')
        else:
            if state.workingDirStatus != -1:  startMakeVideo(state.workingDir, True)  # Add end_hold if appropriate
        nextaction = 'terminate'

    logger.debug('++++++ Determining next logical action ++++++')

    if nextaction == 'start':
        state.action = 'start'

    elif nextaction == 'standby':
        cleanupFiles(nextaction)  # clean up and start again
        setstartvalues()
        state.action = 'standby'

    elif nextaction == 'pause':
        state.action = 'pause'

    elif nextaction == 'continue':
        state.action = 'start'

    elif nextaction == 'restart':
        if state.no_video:
            logger.info('Video creation was skipped')
        else:
            if state.workingDirStatus != -1:
                startMakeVideo(state.workingDir, True) # Add end_hold if appropriate
            waitforMakeVideo() # Wait until done before deleting files
            restartAction()

        if state.standby:
            state.action = 'standby'
        else:
            state.action = 'start'

    elif nextaction == 'terminate':
        state.action = 'terminate'
        logger.info('++++++ Entering terminate state ++++++')
        terminate()  # On restart, this sets the new state
        return

    logger.info('++++++ Entering ' + state.action + ' state ++++++')
    logger.debug('nextAction exiting normally')
    return

###################################
#  Utility Functions
###################################
# gcode command prefix - matched ignoring case so older DuetLapse3. commands still work
commandPrefix = 'duetlapse3.'
messageMacro = 'M3291'  # The gcode macro that queues messages for duetLapse3 (M3291.g)

def handleMessages(seq, ring):
    # Called by duet_printer.Status when the printer's M3291 command count (global.DL3seq) changes.
    # Command number n is in ring[n mod len(ring)] - act on those since the last one handled
    last = state.lastMessageSeq
    state.lastMessageSeq = seq
    if last is None:  # First look since starting - commands from before then are not acted on
        logger.debug('M3291 commands so far: ' + str(seq))
        return
    if seq < last:  # The printer was reset - its count starts again
        logger.info('The printer was reset - M3291 command numbers start again from ' + str(seq))
        last = 0
    size = len(ring)
    if size == 0:
        return
    first = last + 1
    if seq - last > size:
        logger.info('!!!!! ' + str(seq - last - size) + ' M3291 command(s) were missed - more than ' + str(size) + ' arrived at once !!!!!')
        first = seq - size + 1
    for n in range(first, seq + 1):
        message = ring[n % size]
        if not isinstance(message, str):
            continue
        message = message.strip()
        logger.debug('M3291 command ' + str(n) + ': ' + message)
        if message.lower().startswith(commandPrefix):
            try:
                actionM3291(message)
            except Exception as e:
                logger.info('Error carrying out ' + message + ': ' + str(e))

def actionM3291(displaymessage):
    if  displaymessage.lower().startswith(commandPrefix):   
        nextaction = displaymessage[len(commandPrefix):].strip()
        if nextaction == state.action: #  Nothing to do
            logger.info('Already in ' + state.action + ' state')
            return

        if nextaction == 'graceful':
            queueAction('completed')
        elif nextaction == 'forced':
            quit_forcibly()
        elif nextaction in allowedNextAction(state.action) or nextaction == 'completed':
            logger.debug('M3291 command sending to queueAction: ' + nextaction)
            queueAction(nextaction)
        elif nextaction.startswith('snapshot'):
            if state.workingDirStatus != -1:
                startMakeVideo(state.workingDir)  # On the video worker - the control loop carries on
        elif nextaction.startswith('change.'):
            command = nextaction.split('change.')[1]
            changehandling(command)
        else:
            logger.info('The requested action: ' + nextaction + ' is not available at this time')
            logger.info('The current state is: ' + state.action)
    return

def changehandling(command):
    command = command.replace(' ','') # Make sure it is well formed
    changevariables = ['verbose', 'capture_seconds', 'capture_on', 'park_xy', 'start_now', 'park', 'norestart', 'standby', 'no_video', 'keep_files',
                       'min_video_seconds', 'video_length', 'end_hold', 'fps', 'park_wait']
    variable = command.split('=')[0]
    value = command.split('=')[1]
    if variable in changevariables:
        logger.debug('Changing variable with: ' + command)
        if variable == 'verbose' and value in ['True', 'False']:
            updateglobals(variable, value)
            setdebug(state.verbose)
        elif variable == 'capture_seconds':
            ## if int(value) >= minseconds or int(value) == 0:
            updateglobals(variable, value)
            checkSeconds()
        elif variable == 'capture_on' and value in ['layer', 'pause', 'timed']:
            updateglobals(variable, value)
        elif variable in ['park', 'norestart', 'standby', 'start_now', 'no_video', 'keep_files'] and value in ['True', 'False']:  # Booleans
            updateglobals(variable, value)
            state.restart = not state.norestart
        elif variable == 'park_xy':
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
        if 'layer' in state.capture_on or 'pause' in state.capture_on:
            logger.info('##########################################################')
            if 'layer' in state.capture_on:
                logger.info('Will start capturing images on first layer change')
            elif 'pause' in state.capture_on:
                logger.info('Will start capturing images on first pause in print stream')
            logger.info('##########################################################\n')

    if state.standby:
        logger.info('##########################################################')
        logger.info('Will not start until command=start received from http listener')
        logger.info('or ' + messageMacro +  ' B"duetLapse3.start" sent as gcode')
        logger.info('##########################################################\n')

    logger.info('##########################################################')
    logger.info('Video will be created when printing ends')
    logger.info('or if requested from the UI or ' + messageMacro +  ' B"duetLapse3.completed"')
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

    logger.info('Initiating with action set to ' + state.action)
    nextAction(state.action)

def main():
    # Hooks for the printer communication module
    duet_printer.onDisconnected = printerLost
    duet_printer.onMessages = handleMessages
    duet_printer.onChange = wakeControlLoop  # SBC - wake the control loop when the printer changes

    # Allow process running in background or foreground to be forcibly
    # shutdown with SIGINT (kill -2 <pid> or SIGTERM)
    signal.signal(signal.SIGINT, quit_sigint) # Ctrl + C
    signal.signal(signal.SIGTERM, quit_sigterm)
    # Globals
    # Set in startup code

    state.terminateState = -1  # 1 while terminating
    state.videoEvents, state.videoSeq = [], 0  # Videos made (or not) - announced by the page
    state.filesVersion = state.settingsVersion = 0  # Changes the page is told about (/api/events)
    state.connectionState = state.restarting = False
    state.connectError = ''
    state.connectRetry = threading.Event()
    state.workingDirStatus = -1

    # timers
    state.mainLoopPoll = 5 # seconds
    state.minseconds = 20  # seconds


    # Initial time for mainLoop events
    state.lastCaptureLoop = time.time()
    state.lastStatusCall = 0

    # logical state on start is unknown
    state.lastPrintState = state.lastDuetStatus = 'unknown' 

    # SBC session key
    state.urlHeaders = {}

    # Keep track of M3291 messages
    state.lastMessageSeq = None  # Set from the printer's count at the first look - see handleMessages

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
    controlLoop()  # Runs until duetLapse3 ends

###########################
# Program  begins here
###########################

if __name__ == "__main__":  # Do not run anything below if the file is imported by another program
    
    main()