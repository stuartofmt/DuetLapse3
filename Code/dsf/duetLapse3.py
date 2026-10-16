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
Options can be read from duetLapse3.json - path to the file or its folder as the first argument
Command line options take priority over duetLapse3.json
If port = 0 (or the port is in use) a free port is selected
The ip address in use is saved to duetLapse3.json and published to DWC as plugin data
The web server always runs
Removed the firmware version check
Version is read from the plugin manifest
Shared state moved to state.py, logging to logger_module.py, html to www/
gcode commands accept duetLapse3. or DuetLapse3. (any case)
"""

import subprocess
import sys
import platform
import argparse
import shlex
import time
import requests
import socket
import threading
import psutil
import shutil
import pathlib
import stat
import signal
import logging
import base64
import re

import state  # Shared state - always use state.<name>
import logger_module
from logger_module import logger

#  Used for debugging by calling currenFuncName(x)
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
currentFuncName = lambda n=0: sys._getframe(n + 1).f_code.co_name


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


####################################################
# json config file
####################################################

configFileName = 'duetLapse3.json'
configExtras = ['ip']  # Keys in the config file that are not command line options
configOmit = ['duet', 'host']  # Command line only - left out of a new config file

def configDefaults(parser):
    # Option defaults from the parser - single values are not wrapped in a list
    defaults = {}
    for act in parser._actions:
        if act.dest in ['help', '#', 'file', 'config']:
            continue
        val = act.default
        if isinstance(val, list) and act.nargs in [1, '*']:
            val = val[0]
        defaults[act.dest] = val
    return defaults

def readConfig(filename):
    with open(filename, encoding='utf-8') as f:
        return json.load(f)

def writeConfig(filename, config):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
        f.write('\n')

def loadConfig(filename, parser):
    # Returns the config file settings as parser defaults
    # If the file does not exist, it is created from the parser defaults
    if not os.path.isfile(filename):
        logger.warning('No config file found at ' + filename + ' - creating it with default values')
        config = {'Options': {k: v for k, v in configDefaults(parser).items() if k not in configOmit}}
        config['Options']['ip'] = ''
        try:
            writeConfig(filename, config)
        except OSError as e:
            logger.warning('Could not create config file ' + str(e))
    else:
        config = readConfig(filename)

    actions = {act.dest: act for act in parser._actions}
    defaults = {}
    for section in config.values():  # Sections are only for readability
        for key, val in section.items():
            if key in configExtras:
                continue
            if key not in actions or key in ['help', '#', 'file', 'config']:
                logger.warning('Ignoring unknown option "' + key + '" in ' + filename)
                continue
            if actions[key].nargs in [1, '*']:
                val = [val]  # parser expects a list
            defaults[key] = val
    return defaults

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

def publishUiAddress(ip, port):
    # The DWC page reads these from the object model to build its iframe url - same as duetPrintGuard
    try:
        from dsf.connections import CommandConnection
    except ImportError:
        logger.warning('dsf-python is not installed - cannot publish UI address to plugin data')
        return
    command_connection = CommandConnection()
    try:
        command_connection.connect()
        command_connection.set_plugin_data('duetLapse3', 'ip', ip)
        command_connection.set_plugin_data('duetLapse3', 'port', port)
        logger.info('Published UI address ' + ip + ':' + str(port) + ' to plugin data')
    except Exception as e:
        logger.warning('Could not publish UI address to plugin data: ' + str(e))
    finally:
        command_connection.close()


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
    parser.add_argument('-simulate', type=str, nargs=1, choices=['all', 'printer', 'camera'], default=['off'],
                        help='Default is off')
    parser.add_argument('-M3291', type=str, nargs=1, default=['M3291'],
                        help='Default is M3291')
    parser.add_argument('-#', type=str, nargs=1, default=[''],
                        help='Comment')
    return parser

################################################
##  Main routines for calling subprocesses
################################################


def runsubprocess(cmd):
    logger.debug('RUNNING SUBPROCESS WITH ' + str(cmd))
    try:
        if cmd.startswith('wget'):
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True, timeout= 10)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True)

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
    parser = argparse.ArgumentParser(
            description='Create time lapse video for Duet3D based printer. V' + duetLapse3Version, allow_abbrev=False)
    parser = whitelist(parser)

    parser.add_argument('-file', type=argparse.FileType('r'), help='file of options', action=LoadFromFilex)
    parser.add_argument('config', type=str, nargs='?', default='',
                        help='json config file, or the directory containing ' + configFileName)

    # Options in the json config file replace the defaults - command line options still take priority
    state.configfile = parser.parse_known_args()[0].config
    if os.path.isdir(state.configfile):
        state.configfile = os.path.join(state.configfile, configFileName)
    if state.configfile != '':
        parser.set_defaults(**loadConfig(state.configfile, parser))

    args = vars(parser.parse_args())  # Save as a dict

    state.inputs = {}

    # Derived  globals
    
    # Simulate
    state.inputs.update({'# Simulate': ''})
    state.simulate = args['simulate'][0]
    state.inputs.update({'simulate': str(state.simulate)})

    # Environment
    state.inputs.update({'# Environment':''})
    
    state.duet = args['duet'][0]
    if state.simulate in ['all','printer']:
        state.duet = 'SIMULATED'
    state.inputs.update({'duet': str(state.duet)})

    state.password = args['password'][0]  
    #  password is not displayed
    if state.password == 'reprap':
        state.inputs.update({'password': 'Default'})
    else:
        state.inputs.update({'password': '*******'})

        
    state.basedir = args['basedir'][0]
    state.inputs.update({'basedir': str(state.basedir)})
    
    state.poll = args['poll'][0]
    if state.poll < state.minPoll:
        state.poll = state.minPoll
    state.inputs.update({'poll': str(int(state.poll))})
    
    state.instances = args['instances'][0]
    state.inputs.update({'instances': str(state.instances)})
    
    state.logtype = args['logtype'][0]
    state.inputs.update({'logtype': str(state.logtype)})
    
    state.nolog = args['nolog']
    # Deprecated logtype
    if ('console' in state.logtype):
            state.nolog = True
    state.inputs.update({'nolog': str(state.nolog)})
    
    state.verbose = args['verbose']
    state.inputs.update({'verbose': str(state.verbose)})

    state.host = args['host'][0]
    state.inputs.update({'host': str(state.host)})

    state.port = args['port'][0]
    state.inputs.update({'port': str(state.port)})

    state.keeplogs = args['keeplogs']
    state.inputs.update({'keeplogs': str(state.keeplogs)})

    state.novideo = args['novideo']
    state.inputs.update({'novideo': str(state.novideo)})

    state.deletepics = args['deletepics']
    state.inputs.update({'deletepics': str(state.deletepics)})

    state.maxffmpeg = args['maxffmpeg'][0]
    state.inputs.update({'maxffmpeg': str(state.maxffmpeg)})

    state.keepfiles = args['keepfiles']
    state.inputs.update({'keepfiles': str(state.keepfiles)})

    # Execution
    state.inputs.update({'# Execution' : ''})

    state.dontwait = args['dontwait']
    state.inputs.update({'dontwait': str(state.dontwait)})

    state.seconds = args['seconds'][0]
    if state.seconds != 0 and state.seconds < state.minseconds:
        state.seconds = state.minseconds
    state.inputs.update({'seconds': str(state.seconds)})

    state.detect = args['detect'][0]
    state.inputs.update({'detect': str(state.detect)})

    state.pause = args['pause'][0]
    state.inputs.update({'pause': str(state.pause)})

    state.numlayers = args['numlayers'][0]
    if state.numlayers < 1:
        state.numlayers = 1
    state.inputs.update({'numlayers': int(state.numlayers)})

    state.movehead = args['movehead']
    state.inputs.update({'movehead': str(state.movehead)})

    state.rest = args['rest'][0]
    if state.rest < 0:
        state.rest = 0
    state.inputs.update({'rest': str(state.rest)})

    state.standby = args['standby']
    state.inputs.update({'standby': str(state.standby)})

    state.restart = args['restart']
    state.inputs.update({'restart': str(state.restart)})

    # Camera
    state.inputs.update({'# Camera': ''})

    state.camera1 = args['camera1'][0]
    state.inputs.update({'camera1': str(state.camera1)})

    state.camera2 = args['camera2'][0]
    state.inputs.update({'camera2': str(state.camera2)})

    state.weburl1 = args['weburl1'][0]
    state.inputs.update({'weburl1': str(state.weburl1)})

    state.weburl2 = args['weburl2'][0]
    state.inputs.update({'weburl2': str(state.weburl2)})

    # Video
    state.inputs.update({'# Video': ''})

    state.extratime = args['extratime'][0]
    state.inputs.update({'extratime': str(state.extratime)})

    state.fps = args['fps'][0]
    state.inputs.update({'fps': str(state.fps)})

    state.minvideo = args['minvideo'][0]
    state.inputs.update({'minvideo': str(state.minvideo)})

    state.maxvideo = args['maxvideo'][0]
    if state.maxvideo > 0:
       if state.maxvideo < state.minvideo:
           state.maxvideo = state.minvideo

    state.inputs.update({'maxvideo': str(state.maxvideo)})

    # Overrides
    state.inputs.update({'# Overrides': ''})

    state.camparam1 = args['camparam1'][0]
    state.inputs.update({'camparam1': str(state.camparam1)})

    state.camparam2 = args['camparam2'][0]
    state.inputs.update({'camparam2': str(state.camparam2)})

    state.vidparam1 = args['vidparam1'][0]
    state.inputs.update({'vidparam1': str(state.vidparam1)})

    state.vidparam2 = args['vidparam2'][0]
    state.inputs.update({'vidparam2': str(state.vidparam2)})

    # UI
    state.inputs.update({'# UI': ''})

    state.hidebuttons = args['hidebuttons']
    state.inputs.update({'hidebuttons': str(state.hidebuttons)})

    #  Special Functions

    state.inputs.update({'# Special Functions': ''})
    state.execkey = args['execkey'][0]
    state.inputs.update({'execkey': str(state.execkey)})

    state.M3291 = args['M3291'][0]
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

    thisinstance = os.path.basename(__file__)
    if not state.win:
        thisinstance = './' + thisinstance
    checkInstances(thisinstance, state.instances)

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
    state.loggingset = False
    state.pidIncrement = 0 # Used to create a new path for each job.
    if state.basedir == '':
        state.basedir = os.path.dirname(os.path.realpath(__file__))
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

    if (state.camera1 == 'stream' or state.camera1 == 'web') and (not state.weburl1.startswith('http://')):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + state.camera1 + ' cannot be used without a url')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if (state.camera2 == 'stream' or state.camera2 == 'web') and (not state.weburl1.startswith('http://')):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + state.camera2 + ' cannot be used without a url')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if (state.camera1 != 'other') and (state.camparam1 != ''):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + state.camera1 + ' cannot be used with camparam1')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if (state.camera2 != 'other') and (state.camparam2 != ''):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + state.camera2 + ' cannot be used with camparam2')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if (state.camera1 == 'usb' or state.camera1 == 'pi') and state.win:  # These do not work on WIN OS
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + state.camera1 + ' cannot be on Windows OS')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if (state.camera2 == 'usb' or state.camera2 == 'pi') and state.win:
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + state.camera2 + ' cannot be on Windows OS')
        logger.info('************************************************************************************\n')
        sys.exit(2)


    if (not state.movehead == [0.0, 0.0]) and (not 'yes' in state.pause) and (not 'pause' in state.detect):
        logger.info('************************************************************************************')
        logger.info(
                'Invalid Combination: "-movehead {0:1.2f} {1:1.2f}" requires either "-pause yes" or "-detect pause".'.format(
                        state.movehead[0], state.movehead[1]))
        logger.info('************************************************************************************\n')
        sys.exit(2)

    if ('yes' in state.pause) and ('pause' in state.detect):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: "-pause yes" causes this program to pause printer when')
        logger.info('other events are detected, and "-detect pause" requires the gcode on the printer')
        logger.info('contain its own pauses.  These cannot be used together.')
        logger.info('************************************************************************************\n')
        sys.exit(2)

    return # init()


def issue_warnings():
    # Information and Warnings
    if state.seconds <= 0 and 'none' in state.detect:
        logger.info('************************************************************************************')
        logger.info('Warning:: -seconds ' + str(state.seconds) + ' and -detect ' + state.detect + ' nothing will be captured.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************\n')

    if state.seconds > 0 and (not 'none' in state.detect):
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds ' + str(state.seconds) + ' and -detect ' + state.detect + ' will trigger on both.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************\n')

    if state.seconds > 0  and 'none' in state.detect:
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds ' + str(state.seconds) + ' and -detect ' + state.detect)
        logger.info('This combination implies -dontwait and will be set automatically')
        logger.info('************************************************************************************\n')
        state.dontwait = True

    if 'pause' in state.detect:
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

    if 'yes' in state.pause:
        logger.info('************************************************************************************')
        logger.info('* Note "-pause yes" means this program will pause the printer when the -detect and / or ')
        logger.info('* -seconds flags trigger.')
        logger.info('*')
        logger.info('* If instead, it is desired that this program detect pauses that are already in')
        logger.info('* in the gcode, specify:')
        logger.info('* "-detect pause"')
        logger.info('************************************************************************************\n')

    if state.novideo and state.deletepics:
        logger.info('************************************************************************************')
        logger.info('Warning: The combination of -novideo and -deletepics will not create any output')
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
            logger.info('-' + label)
        else:
            logger.info('-' + label + '  =  ' + value)
    logger.info('-----------------------------------------------------------------------\n\n')


####################################################
# Logfile setup
####################################################

def setuplogfile():  #Called at start and restart
    #  Set up log file now that we have a name for it
    
    state.logfilename = os.path.join(state.topDir, 'startup.log')
    state.pidIncrement += 1
    state.nextWorkingDir = os.path.join(state.topDir, state.pid + '_' + str(state.pidIncrement))

    if state.nolog is False:
        # wait allows any messages to propogate to the old logfile
        logger_module.create_log_file(state.logfilename, wait = state.mainLoopPoll)

        logger.info('duetLapse3 Version --- ' + str(duetLapse3Version))
        logger.info('Process Id  ---  ' + str(state.pid) )
        logger.info('-------------------------------------------------------------------------------\n')

    state.loggingset = True


def renamelogfile(thisDir): # called from createworkingDir 
    logger.debug('Calling stack ' + currentFuncName(2) + ' --> '  + currentFuncName(1) + ' --> '  + currentFuncName(0))

    if state.nolog is False:
        state.logfilename = logger_module.move_log_file(thisDir + '.log')

####################################################
# Misc settings
####################################################
   
def setdebug(val): # How much output
    logger_module.set_log_level(val)

    if val:
        state.debug = ''
        state.ffmpegquiet = ''
    else:
        state.ffmpegquiet = ' -loglevel quiet'
        if not state.win:
            state.debug = ' > /dev/null 2>&1'
        else:
            state.debug = ' > nul 2>&1'


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
      
def checkDependencies(id):
    if id == 1:
        camera = state.camera1
        camparam  = state.camparam1
    else:
        camera = state.camera2
        camparam  = state.camparam2

    if 'usb' in camera:
        if runsubprocess('fswebcam --version') is False:
            logger.info("Module 'fswebcam' is required. ")
            if not state.win:
                logger.info("Obtain via 'sudo apt install fswebcam'")
            sys.exit(3)

    if 'pi' in camera:
        logger.info('NOTE: THE -camera pi OPTION IS DEPRECATED')

    if 'pi' in camera or 'raspistill' in camparam:
        if runsubprocess('raspistill --help') is False:
            logger.info("Module 'raspistill' is required BUT is only available for Pi version Buster or lower. ")
            if not state.win:
                logger.info("Obtain via 'sudo apt install raspistill'")
            sys.exit(3)

    if 'web' in camera or 'wget' in camparam:
        if runsubprocess('wget --version') is False:
            logger.info("Module 'wget' is required. ")
            if not state.win:
                logger.info("Obtain via 'sudo apt install wget'")
            sys.exit(3)

    if runsubprocess('ffmpeg -version') is False:
        logger.info("Module 'ffmpeg' is required. ")
        if not state.win:
            logger.info("Obtain via 'sudo apt install ffmpeg'")
        sys.exit(3)

    checkDependencies(1)
    if state.camera2 != '':
        checkDependencies(2)

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
            logger.info('The printer at ' + state.duet + ' is not responding')
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
        logger.info('Connected to printer at ' + state.duet)
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

        if state.printState == 'Completed':
            threadsin = ''  #  Dont limit ffmpeg
            threadsout = ''  #  Dont limit ffmpeg
        else:
            threadsin = ' -threads 1 '
            threadsout = ' -threads 2 '

        #  cmd = 'ffmpeg' + threadsin + ffmpegquiet + ' -r ' + str(thisfps) + ' -i ' + location + ' -vcodec libx264 -y ' + threadsout + tmpfn + debug
        cmd = 'ffmpeg' + state.ffmpegquiet + ' -r ' + str(thisfps) + ' -i ' + location + ' -vcodec libx264 -y ' + tmpfn + state.debug

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


def ffmpeg_available():
    count = 0
    max_count = state.maxffmpeg  # Default is 2
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
        renamelogfile(state.nextWorkingDir)  # change the logfle to match the working dir
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
        renamelogfile(nextWorkingDir)  # change the logfle to match the working dir
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
    for p in psutil.process_iter():
        if ('python3' in p.name() or 'pythonw' in p.name()) and thisinstancepid == p.pid:
            cmdline = str(p.cmdline())
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

def checkInstances(thisinstance, instances):
    proccount = 0
    allowed = 0

    for p in psutil.process_iter():

        if ('python3' in p.name() or 'pythonw' in p.name()) and thisinstance in p.cmdline():
            proccount += 1
            if 'single' in instances:
                allowed += 1
            if 'oneip' in instances:
                if state.duet in p.cmdline():
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


def onePhoto(cameraname, camera, weburl, camparam):

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

    if 'usb' in camera:
        cmd = 'fswebcam --quiet --no-banner ' + fn + state.debug

    if 'pi' in camera:
        cmd = 'raspistill -t 1 -w 1280 -h 720 -ex sports -mm matrix -n -o ' + fn + state.debug

    if 'stream' in camera:
        #  cmd = 'ffmpeg -threads 1' + ffmpegquiet + ' -y -i ' + weburl + ' -vframes 1 -threads 1 ' + fn + debug
        cmd = 'ffmpeg' + state.ffmpegquiet + ' -y -i ' + weburl + ' -frames:v 1 -update true ' + fn + state.debug

    if 'web' in camera:
        # Only for use if the url delivers single images (not for streaming)
        # ? on use of --auth-no-challenge
        if state.debug:
            cmd = 'wget --auth-no-challenge -v --tries 2 -O ' + fn + ' "' + weburl + '" ' + state.debug
        else:   
            cmd = 'wget --auth-no-challenge -v --tries 2 -O ' + fn + ' "' + weburl + '" ' + state.debug
            #cmd = 'wget --auth-no-challenge -nv --timeout 10 --tries 1 -O ' + fn + ' "' + weburl + '" ' + debug

    if 'other' in camera:
        # camparam may reference shared values e.g. debug, ffmpegquiet
        cmd = eval(camparam, {**globals(), **vars(state)}, locals())


    if state.simulate in ['all','camera']:
        with open(fn, 'wb') as outputfile:
            outputfile.write(state.simulatedImage)
    elif runsubprocess(cmd) is False: #  order is important
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
    if state.referer is not None:  # May not be defined yet
        state.lastImage = 'http://' + state.referer + '?getfile=' + fn
    if cameraname == 'Camera1':
        state.timePriorPhoto1 = time.time()
        return
    else:
        state.timePriorPhoto2 = time.time()
        return

def oneInterval(cameraname, camera, weburl, camparam, finalframe = False):
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
                    onePhoto(cameraname, camera, weburl, camparam)

        elif ('pause' in state.detect) and (state.duetStatus == 'paused'):
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
        onePhoto(cameraname, camera, weburl, camparam)

#############################################################################
##############  Duet API access Functions
#############################################################################


def getDuet(calledfrom, function): #  Helper function to call other specific getDuet(x) calls
    # Retries if there is a network problem
    # Relies on called functions to return 'disconnected' if they cannot get the requested info
    # Changes connectionState to False if there is a persistent fault
    disconnected = 0
    getstatus = False
    while getstatus is False:
        #  The working code gets executed here
        
        logger.debug('Calling ' + function.__name__ + ' from ' + currentFuncName(2) + ' --> '  + currentFuncName(1) + ' --> '  + currentFuncName(0))

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

        if connect == 'disconnected' and state.terminateState != 1:
            state.connectionState = False # Stop additional calls
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

    state.connectionState = True
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
                r = requests.get(url, timeout=timelimit, headers=state.urlHeaders)
            else:
                r = requests.post(url, timeout=timelimit, data=post, headers=state.urlHeaders)
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
                code = loginPrinter(state.apiModel)[1] # Try to get a new key
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
    if state.simulate in ['all','printer']:
        logger.info('Simulated success - loginPrinter')
        return 'simulated_API', 200
    state.urlHeaders = {}
    logger.info('Logging in to Printer')

    if model == '' or model == 'rr_model':
        URL = ('http://' + state.duet + '/rr_disconnect') # Close any open session
        r = urlCall(URL,  False)
        URL = ('http://' + state.duet + '/rr_connect?password=' + state.password) # Connect with password
        r = urlCall(URL,  False)
        code = r.status_code
        if code == 200:
            j=json.loads(r.text)
            err = j['err']
            if err == 0:
                if j['apiLevel'] != None: # Check to see if in SBC emulation mode
                    if j['apiLevel'] == 1:
                        logger.debug('Emulation mode detected - Disconnect and try SBC')
                        URL = ('http://' + state.duet + '/rr_disconnect') # Close any open session
                        r = urlCall(URL,  False)
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
        URL = ('http://' + state.duet + '/machine/disconnect') # Close any open session
        r = urlCall(URL,  False)
        URL = ('http://' + state.duet + '/machine/connect?password=' + state.password) # Connect with password
        r = urlCall(URL,  False)
        code = r.status_code
        if code == 200:
            logger.debug('!!!!! Connected to SBC printer !!!!!')
            j = json.loads(r.text)
            sessionKey = j['sessionKey']
            state.urlHeaders = {'X-Session-Key': sessionKey}
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
    if state.simulate in ['all','printer']:
        logger.info('Simulated success - getDuetVersion')
        return 'simulated'
    # Get the firmware version
    logger.info('!!!!! Getting the firmware version !!!!!')
    if model == 'rr_model':
        URL = ('http://' + state.duet + '/rr_model?key=boards')
        r = urlCall(URL,  False)
        if r.status_code == 200:
            j = {}
            try:
                j = json.loads(r.text)
            except:
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info("json.loads(r.text) could not be parsed")
                logger.info(j)
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            try:
                version = j['result'][0]['firmwareVersion']
                return version
            except KeyError:
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info("j['result'][0]['firmwareVersion'] does not exist")
                logger.info(j)
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            except:
                logger.info('!!!!! Could not get standalone firmware version !!!!!')
        else:
            logger.info('!!!!! Error getting rr_model?key=boards code = ' + str(r.status_code) + '!!!!!') 

    elif model == 'SBC':       
        URL = ('http://' + state.duet + '/machine/status')
        r = urlCall(URL,  False)
        if r.status_code == 200:
            j = {}
            try:
                j = json.loads(r.text)
            except:
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info("json.loads(r.text) could not be parsed")
                logger.info(j)
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            try:
                version = j['boards'][0]['firmwareVersion']
                return version
            except KeyError:
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info("j['boards'][0]['firmwareVersion'] does not exist")
                logger.info(j)
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            except:
                logger.info('!!!!! Could not get SBC firmware version !!!!!')
        else:
            logger.info('!!!!! Error getting /machine/status code = ' + str(r.status_code) + '!!!!!')
    else:
        logger.info('!!!!! Could not get version for installation type =  ' + model +  '  !!!!!')
        logger.info('!!!!! THIS SHOULD NEVER HAPPEN !!!!!')
        return ''  # Failed to determine API and firmware version

def Jobname():
    # Used to get the print jobname from Duet
    if state.simulate in ['all','printer']:
        return 'simulated_job'
    if state.apiModel == 'rr_model':
        URL = ('http://' + state.duet + '/rr_model?key=job.file.fileName')
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
                logger.debug(str(e))

    elif state.apiModel == 'SBC':
        URL = ('http://' + state.duet + '/machine/status')
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
                logger.debug(str(e))

    return 'disconnected'

def Status():
    state.lastStatusCall = time.time()
    # Used to get the status information from Duet
    # Note return "disconnected" in different place than ususal due to post processing of messages
    status = ''
    if state.simulate in ['all','printer']:
        logger.info('Simulated status is Idle')
        return 'idle', ''
    
    j = {}
    msgQueue = []
    if state.apiModel == 'rr_model':
        URL = ('http://' + state.duet + '/rr_model?key=state')
        r = urlCall(URL,  False)
        msgQueue = []    
        if r.ok:
            try:
                j = json.loads(r.text)
                status = j['result']['status']
                logger.debug('Standalone Status is ' + status)  
            except Exception as e:
                logger.debug('Could not get Standalone Status')
                logger.debug(str(e))
                return 'disconnected', '' 
        else:
            return 'disconnected', ''      

    elif state.apiModel == 'SBC':
        URL = ('http://' + state.duet + '/machine/status')
        # while True: #  The max queue depth is 8 so we clear as many messages as we can in one go
        r = urlCall(URL,  False)
        if r.ok:
            try:
                j = json.loads(r.text)
                status = j['state']['status']
                logger.debug('SBC Status is ' + status)     
            except Exception as e:
                logger.debug('Could not get SBC Status')
                logger.debug(str(e))
                return 'disconnected', '' 
        else:
            return 'disconnected', ''
    
    #  Check for message commands
    try:
        queue = []
        dellist = []
        #  use .get method for safety
        if j['global'].get('DL3msg') != None: # initialized
            queue = j['global']['DL3msg']
            logger.debug(f'DL3Msg queue = {queue}')
            if j['global'].get('DL3del') != None: # something to delete
                dellist = j['global']['DL3del']
                logger.debug(f'DL3del queue = {dellist}')  
            if queue[0] > state.lastMessageSeq or len(dellist) > 0:
                msgQueue = parseM3291(queue,dellist)
    except Exception as e:
        logger.info('Error Processing message queue')
        logger.info(str(e))

    for item in msgQueue:
        logger.debug(item)
        actionM3291(item)

    return status, ''



def Layer():
    # Used to get the the current layer
    if state.simulate in ['all','printer']:
        return -1
    if state.apiModel == 'rr_model':
        URL = ('http://' + state.duet + '/rr_model?key=job.layer')
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
                logger.debug(str(e))

    elif state.apiModel == 'SBC':
        URL = ('http://' + state.duet + '/machine/status')
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
                logger.debug(str(e))

    return 'disconnected'


def Position():
    # Used to get the current head position from Duet
    if state.simulate in ['all', 'printer']:
        return 0,0,0
    if state.apiModel == 'rr_model':
        URL = ('http://' + state.duet + '/rr_model?key=move.axes')
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
                logger.debug(str(e))
    elif state.apiModel == 'SBC':
        URL = ('http://' + state.duet + '/machine/status')
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
                logger.debug(str(e))

    return 'disconnected'


def sendDuetGcode(model, command):
    # Used to send a command to Duet
    if state.simulate in ['all','printer']:
        return
    if model == 'rr_model':
        URL = 'http://' + state.duet + '/rr_gcode?gcode=' + command
        r = urlCall(URL,  False)
    else:
        URL = 'http://' + state.duet + '/machine/code'
        r = urlCall(URL,  command)

    if r.ok:
        return

def isPlugin(model):
    if model == 'SBC':
        URL = ('http://' + state.duet + '/machine/status')
        r = urlCall(URL,  False)
        if r.ok:
            try:
                j = json.loads(r.text)
                if j['plugins'] != None:
                    if j['plugins']['duetLapse3'] != None: # duetLapse3 is registered plugin
                        if str(j['plugins']['duetLapse3']['pid']) == state.pid: # Running as a plugin
                            logger.info('Running as a plugin')
                            return True
                logger.info('Not Running as a plugin')
            except Exception as e:
                logger.debug('Could not get plugin information')
                logger.debug(str(e))
    else:
        logger.debug('isPlugin ignored - only valid for SBC')
        return False
            
def stopPlugin(model, command):
    # Used to send a command to Duet
    if model == 'SBC':
        URL = 'http://' + state.duet + '/machine/stopPlugin'
        r = urlCall(URL,  command)
        if r.ok:
            logger.info('Sent stopPlugin to plugin manager')
        else:    
            logger.info('stopPlugin failed with code: ' + str(r.status_code) + ' and reason: ' + str(r.reason))
    else:
        logger.info('Stop Plugin ignored - only valid for SBC')
    return

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
            logger.debug('For Camera1')
            oneInterval('Camera1', state.camera1, state.weburl1, state.camparam1, True)  # For Camera 1
            ## if extratime != 0 and frame1/fps > minvideo:
            if state.frame1 > 0:
                state.frame1 = copyLastFrame(state.camfile1, state.frame1)

            if state.camera2 != '':   #  Camera 2
                logger.debug('For Camera2')
                oneInterval('Camera2', state.camera2, state.weburl2, state.camparam2, True)
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
        setuplogfile() # Create a new log file
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
# Integral Web Server
###########################

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import urllib
from urllib.parse import urlparse, parse_qs
import html
#import io

# html templates are in the www sub directory
wwwDir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'www')

def render_html(template, **values):
    # Fill {{name}} placeholders in a www template.  <!-- comments --> are removed.
    # Templates are read on every call so they can be edited without a restart
    with open(os.path.join(wwwDir, template), encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'<!--.*?-->\n?', '', content, flags=re.DOTALL).strip()
    return re.sub(r'\{\{(\w+)\}\}', lambda m: str(values[m.group(1)]), content)


class MyHandler(SimpleHTTPRequestHandler):

    def shutdown(self):
        self.server._BaseServer__shutdown_request = True
        logger.debug('Sent shutdown request')

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

    def display_controls(self):
        allowed_buttons = allowedNextAction(state.action)
        allbuttons = ['start', 'standby', 'pause', 'continue', 'restart']

        if state.hidebuttons:  # hide buttons if option was set
            shown = [button for button in allowed_buttons if button in allbuttons]
        else:
            shown = allbuttons

        buttons = ''
        for button in shown:
            if button in allowed_buttons:
                disable = ''
            else:
                disable = 'disabled'
            buttons += render_html('buttons/' + button + '.html', referer = state.referer, disabled = disable)

        if state.apiModel != 'SBC':
            buttons += render_html('buttons/terminate.html')

        return buttons

    def display_video(self):
        return render_html('video.html', referer = state.referer, fps = state.fps, minvideo = state.minvideo,
                           maxvideo = state.maxvideo, videomsg = getVideoMsg())

    def display_status(self):
        localtime = time.strftime('%A - %H:%M', time.localtime())
        if state.zo1 < 0:
            thislayer = 'None'
        else:
            thislayer = str(state.zo1)

        if state.lastImage != '':
            image = render_html('status_image.html', src = state.lastImage)
        else:
            image = render_html('status_noimage.html')

        return render_html('status.html', version = duetLapse3Version, duet3d_version = state.printerVersion,
                           duet = state.duet, pid = state.pid, localtime = localtime,
                           print_state = state.printState, action = state.action,
                           duet_status = state.duetStatus, frames = state.frame1,
                           layer = thislayer, image = image)

    def display_info(self):
        if state.workingDirStatus != -1:
            imagelocation = state.workingDir
        else:
            imagelocation = 'Waiting for first image to be created'

        options = getOptions()

        optionlist = ''
        count = 0
        for label, value in options.items():
            if label.startswith('#'):  #  Omit the section info
                continue
            if (count % 3) == 0: # 3 columns
                optionlist += render_html('info_newrow.html')
            optionlist += render_html('info_option.html', label = label, value = value)
            count += 1

        return render_html('info.html', pid = state.pid, options = optionlist, topdir = state.topDir,
                           imagelocation = imagelocation, logfilename = state.logfilename)

    def display_page(self):
        return render_html('index.html', referer = state.referer, poll_ms = state.poll*1000)

    def do_GET(self):
        try:
            state.referer = self.headers['Host']  # Should always be there
            if not state.referer:  # Lets try authority
                state.referer = self.headers['authority']
                if not state.referer:
                    state.referer = 'localhost'  # Best guess if all else fails


            if 'favicon.ico' in self.path:
                return

            query_components = parse_qs(urlparse(self.path).query)
            logger.debug('!!!!! http call: ' + str(query_components) + ' !!!!!')

            if query_components is None or len(query_components) == 0 :
                # Display Page
                self._set_headers()
                self.wfile.write(self.display_page().encode("utf8"))
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
                    if state.apiModel != 'SBC':
                        result = self.display_terminate_buttons()
                elif api == 'snapshot':
                    if state.workingDirStatus != -1:
                        result = startMakeVideo(state.workingDir, False, False) # False => no extratime and nothread therefore blocking
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
            while state.action != command: # Dont return until success
                pass

        # pause / continue
        elif command == 'pause':
            startnextAction(command)
            while state.action != command: # Dont return until success
                pass

        elif command == 'continue':
            startnextAction(command) # Dont return until success
            while state.action != command:
                pass

        elif command == 'restart':
            startnextAction(command)
            while state.action not in ['start', 'standby']: # Dont return until success
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
            startnextAction('completed')
            #  startnextAction('terminate')
        elif ttype == 'terminatef':
            if isPlugin(state.apiModel):
                stopPlugin(state.apiModel, 'duetLapse3')
            else:
                quit_forcibly()

        return

    def display_terminate_buttons(self):
        if state.restart:
            restartmsg = '\\nA restart will occur after the Terminate'
            pageaction = "repeatDisplayStatus();"
        else:
            restartmsg = ''
            pageaction = "document.body.innerHTML = '';"

        if state.workingDirStatus != -1:
            vidmsg = getVideoMsg()
        else:
            vidmsg = 'There are no images available'

        return render_html('terminate.html', referer = state.referer, vidmsg = vidmsg,
                           restartmsg = restartmsg, pageaction = pageaction)



    def display_files(self, path):
        if path == 'true':
            path = state.topDir

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
            return render_html('files/nofiles.html', path = displaypath)

        #  sort the list by datetime last modified
        listdir.sort(key=lambda fn: -os.path.getmtime(os.path.join(path, fn))) # Sort in reverse order
        
        dirPid = str(state.pid) + '_' + str(state.pidIncrement)  # get current pid + suffix

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

        if path == state.topDir:
            child_dir = False
        else:
            parentdir = os.path.split(path)[0]
            child_dir = True

        rows = ''

        # add parent dir to the html
        if child_dir:
            displayname = './'
            rows += render_html('files/parent.html', path = parentdir.replace('\\', '\\\\'), name = html.escape(displayname, quote=False))


        # Add actions to files / dirs 
        for fullname in fullfilenames:          
            if os.path.islink(fullname):   # A link to a directory displays with @
                displayname = fullname + "@"

            displayname = os.path.split(fullname)[1]
            jsname = fullname.replace('\\', '\\\\')

            buttons = ''
            if fullname in deletelist:
                buttons += render_html('files/delete.html', referer = state.referer, path = jsname)
                if fullname in jpegfolder:
                    buttons += render_html('files/zip.html', referer = state.referer, path = jsname)
                    buttons += render_html('files/video.html', referer = state.referer, path = jsname)

            if os.path.isdir(fullname):
                rows += render_html('files/dir.html', path = jsname, name = html.escape(displayname, quote=False), buttons = buttons)
            else:
                rows += render_html('files/file.html', path = urllib.parse.quote(fullname, errors='surrogatepass'),
                                    name = html.escape(displayname, quote=False), buttons = buttons)

        dir_table = render_html('files/table.html', rows = rows)

        logger.debug('Finished parsing the files directory')
        return dir_table
    
        """
            end of requesthandler
        """

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

    try: # check if running
        if state.listenerThread.is_alive():
            logger.debug('http listener is already running')
            return
    except AttributeError:
        state.listenerThread = None

    try:
        state.listener = ThreadingHTTPServer((state.host, state.port), MyHandler)
        state.listenerThread = threading.Thread(name='httpServer', target=state.listener.serve_forever, daemon=False).start()  #Avoids blocking
        logger.info('##########################################################')
        logger.info(f"""***** Started http listener on port {state.port}*****""")
        logger.info('##########################################################\n')
    except Exception as e:
        if 'Errno 98' in str(e):
            logger.debug('http listener is already running')
        else:
            logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  There was a problem starting the http listener !!!!!!!!!!!!!!!!!!!!!')
            logger.info(str(e))
            sys.exit(1)


def closeHttpListener():
    try:
        state.listener.shutdown()
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
            logger.debug('Calling oneInterval for Camera 1')
            oneInterval('Camera1', state.camera1, state.weburl1, state.camparam1)
            if state.camera2 != '':
                logger.debug('Calling oneInterval for Camera 2')
                oneInterval('Camera2', state.camera2, state.weburl2, state.camparam2)
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


def validate_port(port=0, start_port=17800, max_tries=100):
    #  Get the local ip address
    this_ip_address = ''
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))  # doesn't even have to be reachable
        this_ip_address = s.getsockname()[0]
    except Exception as e:
        logger.critical(f'''Unknown error trying to get the local IP address''')
        logger.critical(f'''{e}''')
        force_quit(1)
    finally:
        s.close()

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