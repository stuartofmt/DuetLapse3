#!python3

"""
#Python program to take Time Lapse photographs during a print on
#   a Duet based 3D printer and convert them into a video.
#
# From the original work of Danal Estes
# Copyright (C) 2020 Danal Estes all rights reserved.
# Released under The MIT License. Full text available via https://opensource.org/licenses/MIT
#
#Extended by Stuart Strolin
# Copyright (C) 2020 Stuart Strolin all rights reserved.
# Released under The MIT License. Full text available via https://opensource.org/licenses/MIT
#
#
# Developed on Raspberry Pi and WSL with Debian Buster and on Windows 10. SHOULD work on most other linux distributions.
# For USB or Pi camera, The Camera MUST be physically attached to the Pi computer.
# For Webcam, the camera must be network reachable and via a defined URL for a still image.
# For Stream   the camera must be network reachable and via a defined URL
# The Duet printer must be RepRap firmware V3 and must be network reachable.
#
#
"""

import subprocess
import sys
import platform
import argparse
import time
import requests
import json
import os
import socket
import threading
import psutil
import shutil
import pathlib

duetLapse3Version = '3.5.0'


def setstartvalues():
    global zo1, zo2, printState, capturing, duetStatus, timePriorPhoto1, timePriorPhoto2, frame1, frame2
    zo1 = -1  # Starting layer for Camera1
    zo2 = -1  # Starting layer for Camera2
    printState = 'Not Capturing'
    capturing = False
    duetStatus = 'Not yet determined'

    # initialize timers
    timePriorPhoto1 = time.time()
    timePriorPhoto2 = time.time()

    # reset the frame counters
    frame1 = 0
    frame2 = 0


###########################
# Methods begin here
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
    parser.add_argument('-poll', type=float, nargs=1, default=[5])
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
    parser.add_argument('-standby', action='store_true', help='Wait for command from http listener')
    # Camera
    parser.add_argument('-camera1', type=str, nargs=1, choices=['usb', 'pi', 'web', 'stream', 'other'], default=['usb'],
                        help='Mandatory Camera. Default = usb')
    parser.add_argument('-weburl1', type=str, nargs=1, default=[''], help='Url for Camera1 if web or stream')
    parser.add_argument('-camera2', type=str, nargs=1, choices=['usb', 'pi', 'web', 'stream', 'other'], default=[''],
                        help='Optional second camera. No Default')
    parser.add_argument('-weburl2', type=str, nargs=1, default=[''], help='Url for Camera2 if web or stream')
    # Video
    parser.add_argument('-extratime', type=float, nargs=1, default=[0], help='Time to repeat last image, Default = 0')
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
    return parser

###  Main routines for calling subprocesses


def runsubprocess(cmd):
    try:
        # r = subprocess.check_output(cmd, shell=True)
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
        logger.info('Command Exception: ' + str(cmd))
        logger.info(str(e))
        return False


def init():
    parser = argparse.ArgumentParser(
            description='Create time lapse video for Duet3D based printer. V' + duetLapse3Version, allow_abbrev=False)
    parser = whitelist(parser)
    args = vars(parser.parse_args())

    # Environment
    global duet, basedir, poll, instances, logtype, nolog, verbose, host, port
    global keeplogs, novideo, deletepics, maxffmpeg, keepfiles
    # Derived  globals
    global duetname, debug, ffmpegquiet, httpListener
    duet = args['duet'][0]
    basedir = args['basedir'][0]
    poll = args['poll'][0]
    instances = args['instances'][0]
    logtype = args['logtype'][0]
    nolog = args['nolog']
    verbose = args['verbose']
    host = args['host'][0]
    port = args['port'][0]
    keeplogs = args['keeplogs']
    novideo = args['novideo']
    deletepics = args['deletepics']
    maxffmpeg = args['maxffmpeg'][0]
    keepfiles = args['keepfiles']

    # Execution
    global dontwait, seconds, detect, pause, movehead, rest, standby
    dontwait = args['dontwait']
    seconds = args['seconds'][0]
    detect = args['detect'][0]
    pause = args['pause'][0]
    movehead = args['movehead']
    rest = args['rest'][0]
    if rest < 0:
        rest = 0
    standby = args['standby']
    # Camera
    global camera1, camera2, weburl1, weburl2
    camera1 = args['camera1'][0]
    camera2 = args['camera2'][0]
    weburl1 = args['weburl1'][0]
    weburl2 = args['weburl2'][0]

    # Video
    global extratime, fps
    extratime = str(args['extratime'][0])
    fps = str(args['fps'][0])

    # Overrides
    global camparam1, camparam2, vidparam1, vidparam2
    camparam1 = args['camparam1'][0]
    camparam2 = args['camparam2'][0]
    vidparam1 = args['vidparam1'][0]
    vidparam2 = args['vidparam2'][0]

    # UI
    global hidebuttons
    hidebuttons = args['hidebuttons']

    # Deprecated logtype
    if ('console' in logtype):  #
            nolog = True

    ##### Create a custom logger #####
    import logging
    global logger
    logger = logging.getLogger(__name__)

    if verbose:  #  Capture all log messages
        logger.setLevel(logging.DEBUG)
    else:        #  Ignore debug messages
        logger.setLevel(logging.INFO)

    # Create handler for console output - file output handler is created later if needed
    if nolog is False:  # Create log file as the default
        c_handler = logging.StreamHandler()
        c_format = logging.Formatter(duet + ' %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)

    ############################################################
    # Check to see if this instance is allowed to run
    ############################################################

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

    # duetname used for filenames and directories
    duetname = duet.replace('.', '-')

    # set directories for files
    global topdir, baseworkingdir, workingdir, loggingset, logname
    loggingset = False
    if basedir == '':
        basedir = os.path.dirname(os.path.realpath(__file__))
    #get the slashes going the right way
    if win:
        basedir = basedir.replace('/','\\')
    else:
        basedir = basedir.replace('\\','/')
    basedir = os.path.normpath(basedir) # Normalise the dir - no trailing slash

    if win:
        topdir = basedir + '\\' + socket.getfqdn() + '\\' + duetname
        baseworkingdir = topdir + '\\' + pid  # may be changed later
        logname = pid + '_' + time.strftime('%y-%m-%dT%H:%M:%S', time.localtime()) + '.log'
        logfilename = logname.replace(':', u'\u02f8')  # cannot use regular colon in windows file names
        logname = topdir + '\\' + logname  # This format used for HTML
        logfilename = topdir + '\\' + logfilename
        cmd = 'mkdir "' + topdir + '"' + debug
    else:
        topdir = basedir + '/' + socket.getfqdn() + '/' + duetname
        baseworkingdir = topdir + '/' + pid  # may be changed later
        logname = pid + '_' + time.strftime('%y-%m-%dT%H:%M:%S', time.localtime()) + '.log'
        logfilename = logname.replace(':', u'\u02f8')  # cannot use regular colon in windows file names
        logname = topdir + '/' + logname  #  This format used for html
        logfilename = topdir + '/' + logfilename
        cmd = 'mkdir -p "' + topdir + '"' + debug
    
    if runsubprocess(cmd) is False:
        logger.debug('Could not create ' + topdir)

    #  Clean up files
    cleanupFiles('startup')

##  Set up log file now that we have a name for it
    if nolog is False:
        f_handler = logging.FileHandler(logfilename, mode='w', encoding='utf-8')
        f_format = logging.Formatter('%(asctime)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)

    loggingset = True

    ####################################################
    # Display options selected.
    ####################################################
    logger.info('')
    logger.info("################### Options selected for this run #####################")
    logger.info("#Environment Settings:")
    logger.info("# printer         = {0:50s}".format(duet))
    logger.info("# basedir         = {0:50s}".format(basedir))
    logger.info("# poll            = {0:50s}".format(str(poll)))
    logger.info("# logtype         = {0:50s}".format(logtype))
    logger.info("# nolog           = {0:50s}".format(str(nolog)))
    logger.info("# verbose         = {0:50s}".format(str(verbose)))
    logger.info("# os              = {0:50s}".format(operatingsystem))
    logger.info("# host            = {0:50s}".format(str(host)))
    logger.info("# port            = {0:50s}".format(str(port)))
    logger.info("# pid             = {0:50s}".format(pid))
    logger.info("# keeplogs        = {0:50s}".format(str(keeplogs)))
    logger.info("# nolog           = {0:50s}".format(str(nolog)))
    logger.info("# novideo         = {0:50s}".format(str(novideo)))
    logger.info("# deletepics      = {0:50s}".format(str(deletepics)))
    logger.info("# maxffmpeg       = {0:50s}".format(str(maxffmpeg)))
    logger.info("# keepfiles       = {0:50s}".format(str(keepfiles)))
    logger.info("#Execution Setings:")
    logger.info("# dontwait        = {0:50s}".format(str(dontwait)))
    logger.info("# seconds         = {0:50s}".format(str(seconds)))
    logger.info("# detect          = {0:50s}".format(detect))
    logger.info("# pause           = {0:50s}".format(pause))
    if (movehead[0] != 0) and (movehead[1] != 0):
        logger.info("# movehead    = {0:6.2f} {1:6.2f} ".format(movehead[0], movehead[1]))
    logger.info("# standby         = {0:50s}".format(str(standby)))
    logger.info("#Camera1 Settings:")
    logger.info("# camera1         = {0:50s}".format(camera1))
    logger.info("# weburl1         = {0:50s}".format(weburl1))
    if camparam1 != '':
        logger.info("# Camera1 Override:")
        logger.info("# camparam1       = {0:50s}".format(camparam1))
    if camera2 != '':
        logger.info("# Camera2 Settings:")
        logger.info("# camera2         = {0:50s}".format(camera2))
        logger.info("# weburl2         = {0:50s}".format(weburl2))
    if camparam2 != '':
        logger.info("# Camera2 Override:")
        logger.info("# camparam2       = {0:50s}".format(camparam2))
    logger.info("# Video Settings:")
    logger.info("# extratime       = {0:50s}".format(extratime))
    logger.info("# fps             = {0:50s}".format(str(fps)))
    if vidparam1 != '':
        logger.info("# Video1 Override:")
        logger.info("# vidparam1       = {0:50s}".format(vidparam1))
    if vidparam2 != '':
        logger.info("# Video2 Override:")
        logger.info("# vidparam2       = {0:50s}".format(vidparam2))
    logger.info("# UI Settings:")
    logger.info("# hidebuttons     = {0:50s}".format(str(hidebuttons)))
    logger.info("###################################################################")
    logger.info('')

    ###############################################
    # derived parameters
    ##############################################

    # Polling interval should be at least = seconds so as not to miss interval
    if (poll > seconds) and (seconds != 0):
        poll = seconds  # Need to poll at least as often as seconds
    # if ('none' in detect and seconds != 0): poll = seconds  #No point in polling more often

    #  Port number must be given for httpListener to be active
    if port != 0:
        httpListener = True

    ########################################################################
    # Inform regarding valid and invalid combinations
    #########################################################################

    # Invalid Combinations that will abort program

    if (camera1 != 'other') and (camparam1 != ''):
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + camera1 + ' cannot be used with camparam1')
        logger.info('************************************************************************************')
        sys.exit(2)

    if (camera2 != 'other') and (camparam2 != ''):
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + camera2 + ' cannot be used with camparam2')
        logger.info('************************************************************************************')
        sys.exit(2)

    if (camera1 == 'usb' or camera1 == 'pi') and win:  # These do not work on WIN OS
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + camera1 + ' cannot be on Windows OS')
        logger.info('************************************************************************************')
        sys.exit(2)

    if (camera2 == 'usb' or camera2 == 'pi') and win:
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type ' + camera2 + ' cannot be on Windows OS')
        logger.info('************************************************************************************')
        sys.exit(2)

    if (seconds <= 0) and ('none' in detect):
        logger.info('')
        logger.info('************************************************************************************')
        logger.info(
            'Invalid Combination:: -seconds ' + str(seconds) + ' and -detect ' + detect + ' nothing will be captured.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************')
        sys.exit(2)

    if (not movehead == [0.0, 0.0]) and (not 'yes' in pause) and (not 'pause' in detect):
        logger.info('')
        logger.info('************************************************************************************')
        logger.info(
                'Invalid Combination: "-movehead {0:1.2f} {1:1.2f}" requires either "-pause yes" or "-detect pause".'.format(
                        movehead[0], movehead[1]))
        logger.info('************************************************************************************')
        sys.exit(2)

    if ('yes' in pause) and ('pause' in detect):
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: "-pause yes" causes this program to pause printer when')
        logger.info('other events are detected, and "-detect pause" requires the gcode on the printer')
        logger.info('contain its own pauses.  These cannot be used together.')
        logger.info('************************************************************************************')
        sys.exit(2)

    # Information and Warnings

    if standby and (not httpListener):
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('Warning: -standby ignored.  It has no effect unless http Listener is active.')
        logger.info('Specify -localhost and -port to activate http Listener')
        logger.info('************************************************************************************')

    if (seconds > 0) and (not 'none' in detect):
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds ' + str(seconds) + ' and -detect ' + detect + ' will trigger on both.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************')

    if startNow() and (not dontwait):
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds ' + str(seconds) + ' and -detect ' + detect)
        logger.info('This combination implies -dontwait and will be set automatically')
        logger.info('************************************************************************************')
        dontwait = True

    if 'pause' in detect:
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('* Note "-detect pause" means that the G-Code on the printer already contains pauses,')
        logger.info('* and that this program will detect them, take a photo, and issue a resume.')
        logger.info('* Head position during those pauses is can be controlled by the pause.g macro ')
        logger.info('* on the duet, or by specifying "-movehead nnn nnn".')
        logger.info('*')
        logger.info('* If instead, it is desired that this program force the printer to pause with no')
        logger.info('* pauses in the gcode, specify either:')
        logger.info('* "-pause yes -detect layer" or "-pause yes -seconds nnn".')
        logger.info('************************************************************************************')

    if 'yes' in pause:
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('* Note "-pause yes" means this program will pause the printer when the -detect and / or ')
        logger.info('* -seconds flags trigger.')
        logger.info('*')
        logger.info('* If instead, it is desired that this program detect pauses that are already in')
        logger.info('* in the gcode, specify:')
        logger.info('* "-detect pause"')
        logger.info('************************************************************************************')

    if novideo and deletepics:
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('Warning: The combination of -novideo and -deletepics will not create any output')
        logger.info('************************************************************************************')

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

        """  Redundant see ffmpeg test below - leave here if other method used in future
        if 'stream' in camera or 'ffmpeg' in camparam:
            if runsubprocess('ffmpeg -version') is False:
                logger.info("Module 'ffmpeg' is required. ")
                if not win:
                    logger.info("Obtain via 'sudo apt install ffmpeg'")
                sys.exit(3)
        """

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

    # Check to see if ffmpeg supports tpad
    # Done after checking that ffmpeg exist

    if (not tpad_supported()) and (float(extratime) > 0):
        logger.info('')
        logger.info('************************************************************************************')
        logger.info('Warning: This version of ffmpeg does not support -extratime')
        logger.info('-extratime has been set to 0')
        logger.info('************************************************************************************')
        extratime = '0'


    global apiModel

    # Get connected to the printer.

    apiModel, printerVersion = getDuetVersion()

    if apiModel == 'none':
        logger.info('')
        logger.info('###############################################################')
        logger.info('The printer at ' + duet + ' did not respond')
        logger.info('Check the ip address or logical printer name is correct')
        logger.info('Duet software must support rr_model or /machine/status')
        logger.info('###############################################################')
        logger.info('')
        sys.exit(4)

    majorVersion = int(printerVersion[0])

    if majorVersion >= 3:
        logger.info('')
        logger.info('###############################################################')
        logger.info(
                'Connected to printer at ' + duet + ' using Duet version ' + printerVersion + ' and API access using ' + apiModel)
        logger.info('###############################################################')
        logger.info('')
    else:
        logger.info('')
        logger.info('###############################################################')
        logger.info('The printer at ' + duet + ' needs to be at version 3 or above')
        logger.info('The version on this printer is ' + printerVersion)
        logger.info('###############################################################')
        logger.info('')
        sys.exit(5)

    # Allows process running in background or foreground to be gracefully
    # shutdown with SIGINT (kill -2 <pid>
    import signal

    def quit_gracefully(*args):
        logger.info('!!!!!! Stopped by SIGINT or CTL+C - Post Processing !!!!!!')
        nextAction('terminate')  # No need to thread as we are quitting
        # threading.Thread(target=nextAction, args=('terminate',)).start()

    if __name__ == "__main__":
        signal.signal(signal.SIGINT, quit_gracefully)


"""
End of init()
"""


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

        fn = ' "' + directory + '_' + cameraname + '_' + timestamp + '.mp4"'

        if win:
            cmd = 'ffmpeg' + ffmpegquiet + ' -r ' + fps + ' -i "' + directory + '\\' + cameraname + '_%08d.jpeg" -vcodec libx264 -y ' + fn + debug
        else:
            cmd = 'ffmpeg' + ffmpegquiet + ' -r ' + fps + ' -i "' + directory + '/' + cameraname + '_%08d.jpeg" -vcodec libx264 -y ' + fn + debug

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

def tpad_supported():
    if win:
        cmd = 'ffmpeg -filters | findstr "tpad"'
    else:
        cmd = 'ffmpeg -filters | grep tpad'

    if runsubprocess(cmd) is False:
        logger.info('This version of ffmpeg does not support tpad')
        return False

    return True

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
    global workingdir_exists, workingdir
    jobname = getDuetJobname(apiModel)
    if jobname != '':
        _, jobname = os.path.split(jobname)  # get the filename less any path
        jobname = jobname.replace(' ', '_')  # prevents quoting of file names
        jobname = jobname.replace('.gcode', '')  # get rid of the extension
        jobname = jobname.replace(':', u'\u02f8')  # replace any colons
        workingdir = baseworkingdir + '_' + jobname
    else:
        workingdir = baseworkingdir

    if win:
        cmd = 'mkdir "' + workingdir + '"' + debug
    else:
        cmd = 'mkdir -p "' + workingdir + '"' + debug

    if runsubprocess(cmd) is False:
        logger.debug('Could not create working directory ' + workingdir)
    else:
        workingdir_exists = True

    return workingdir


def cleanupFiles(phase):
    global workingdir_exists, keepfiles
    logger.info('Cleaning up phase:  ' + phase)
    #pidlist = []
    #dirlist = []
    pidlist = getRunningInstancePids()
    dirlist = getPidDirs()

    # Make and clean up directorys.
    # Make sure there is a directory for the resulting video

    if phase == 'startup':
        if keepfiles: return
        if win:
            for dirs in dirlist:
                split_dirs = dirs.split("-", 1)
                dirpid = split_dirs[0]
                if dirpid not in pidlist:
                    cmd = 'rmdir "' + topdir + '\\' + dirs + '" /s /q' + debug
                    if runsubprocess(cmd) is False:
                        logger.debug('Could not clean up ' + dirs)

            if (not keeplogs) and (len(pidlist) == 1):  # only delete logs if no other processes running
                #  Note position of last " so that shell expands *.log portion
                cmd = 'del /q "' + topdir + '\\"*.log' + debug
                if runsubprocess(cmd) is False:
                    logger.debug('Could not clean up log files')
        else:
            for dirs in dirlist:
                split_dirs = dirs.split("-", 1)
                dirpid = split_dirs[0]
                if dirpid not in pidlist:
                    cmd = 'rm -rf "' + topdir + '/' + dirs + '"' + debug
                    if runsubprocess(cmd) is False:
                        logger.debug('Could not clean up ' + dirs)

            if (not keeplogs) and (len(pidlist) == 1):  # only delete logs if no other processes running
                # Note position of last " so that shell expands *.log portion
                cmd = 'rm -f "' + topdir + '/"*.log' + debug
                if runsubprocess(cmd) is False:
                    logger.debug('Could not clean up log files')

    elif (phase == 'standby') or (phase == 'restart'):  # delete images directory will be recreated on first capture
        if workingdir_exists:
            if win:
                cmd = 'rmdir "' + workingdir + '" /s /q' + debug
            else:
                cmd = 'rm -rf "' + workingdir + '"' + debug
            if runsubprocess(cmd) is False:
                logger.debug('Could not delete ' + workingdir)
                workingdir_exists = True
            else:
                workingdir_exists = False

    elif phase == 'terminate':
        if keepfiles: return

        if deletepics:
            if win:
                cmd = 'rmdir "' + workingdir + '" /s /q' + debug
            else:
                cmd = 'rm -rf "' + workingdir + '"' + debug

            if runsubprocess(cmd) is False:
                logger.debug('Could not delete ' + workingdir)

    return  # cleanupFiles

def startNow():
    global action
    if standby and httpListener:
        action = 'standby'
        return False
    elif (seconds > 0) and (dontwait or 'none' in detect):
        action = 'start'
        return True
    else:
        action = 'start'
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
        logger.info('')
        logger.info('#############################')
        logger.info('Process is already running... shutting down.')
        logger.info('#############################')
        logger.info('')
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
    duetStatus = getDuetStatus(apiModel)
    loopmax = 10  # sec
    loopinterval = .5  # sec
    loopcount = loopmax / loopinterval

    if pause == 'yes':  # DuetLapse is controlling when to pause
        logger.info('Requesting pause via M25')
        sendDuetGcode(apiModel, 'M25')  # Ask for a pause
        loop = 0
        while True:
            time.sleep(loopinterval)  # wait and try again
            duetStatus = getDuetStatus(apiModel)
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
            logger.info('Moving print head to X{0:4.2f} Y{1:4.2f}'.format(movehead[0], movehead[1]))
            sendDuetGcode(apiModel, 'G1 X{0:4.2f} Y{1:4.2f}'.format(movehead[0], movehead[1]))
            loop = 0
            while True:
                time.sleep(loopinterval)  # wait and try again
                xpos, ypos, _ = getDuetPosition(apiModel)
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
    if getDuetStatus(apiModel) == 'paused':
        loopmax = 10 # sec
        loopinterval = .2 # sec  short so as to not miss start of next layer
        loopcount = loopmax / loopinterval
        logger.info('Requesting un pause via M24')
        sendDuetGcode(apiModel, 'M24')  # Ask for an un pause
        loop = 0
        while True:
            time.sleep(loopinterval)  # wait a short time so as to not miss transition on short layer
            if getDuetStatus(apiModel) in ['idle', 'processing']:
                break
            else:
                loop += 1
            if loop == loopcount:  # limit the counter in case there is a problem
                logger.info('Loop exceeded: Target was: unpause')
                break
    return


def onePhoto(cameraname, camera, weburl, camparam):
    global frame1, frame2, workingdir
    if not workingdir_exists:
        workingdir = createWorkingDir(baseworkingdir)  # created as late as possible - adds job fileName if available

    if cameraname == 'Camera1':
        frame1 += 1
        frame = frame1
    else:
        frame2 += 1
        frame = frame2

    s = str(frame).zfill(8)
    if win:
        fn = ' "' + workingdir + '\\' + cameraname + '_' + s + '.jpeg"'
    else:
        fn = ' "' + workingdir + '/' + cameraname + '_' + s + '.jpeg"'

    if 'usb' in camera:
        cmd = 'fswebcam --quiet --no-banner ' + fn + debug

    if 'pi' in camera:
        cmd = 'raspistill -t 1 -w 1280 -h 720 -ex sports -mm matrix -n -o ' + fn + debug

    if 'stream' in camera:
        cmd = 'ffmpeg' + ffmpegquiet + ' -y -i ' + weburl + ' -vframes 1 ' + fn + debug

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
        else:
            frame2 -= 1
            if frame2 < 0:
                frame2 = 0
    else:   #  Success
        if cameraname == 'Camera1':
            timePriorPhoto1 = time.time()
        else:
            timePriorPhoto2 = time.time()


def oneInterval(cameraname, camera, weburl, camparam):
    global frame1, frame2
    global timePriorPhoto1, timePriorPhoto2

    # select the prior frame counter
    if cameraname == 'Camera1':
        frame = frame1
    else:
        frame = frame2

    global zo1, zo2
    zn = getDuetLayer(apiModel)
    if zn == -1:
        layer = 'None'
    else:
        layer = str(zn)

    if 'layer' in detect:
        if (not zn == zo1 and cameraname == 'Camera1') or (not zn == zo2 and cameraname == 'Camera2'):
            # Layer changed, take a picture.
            checkForPause(zn)
            logger.info(cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after layer change')
            onePhoto(cameraname, camera, weburl, camparam)

    elif ('pause' in detect) and (duetStatus == 'paused'):
        checkForPause(zn)
        logger.info(cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' at pause in print gcode')
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

    if (seconds > 0) and (seconds < elap) and (dontwait or zn >= 1):
        checkForPause(zn)
        logger.info(cameraname + ': capturing frame ' + str(frame) + ' at layer ' + layer + ' after ' + str(
                seconds) + ' seconds')
        onePhoto(cameraname, camera, weburl, camparam)

#############################################################################
##############  Duet API access Functions
#############################################################################

def urlCall(url, timelimit, post):
    logger.debug('url: ' + str(url) + ' post: ' + str(post))
    loop = 0
    limit = 2  # Started at 2 - seems good enough to catch transients
    error  =''
    while loop < limit:
        try:
            if post is False:
                r = requests.get(url, timeout=timelimit)
            else:
                r = requests.post(url, data=post)
            break
        except requests.ConnectionError as e:
            logger.info('')
            logger.info(
                    '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            logger.info('There was a network failure')
            logger.info(str(e))
            logger.info(
                    '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            logger.info('')
            error = 'Connection Error'
        except requests.exceptions.Timeout as e:
            logger.info('')
            logger.info(
                    '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            logger.info('There was a timeout failure')
            logger.info(str(e))
            logger.info(
                    '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            logger.info('')
            error = 'Timed Out'
        time.sleep(1)
        loop += 1 
 
    if loop >= limit:  # Create dummy response
        class r:
            ok = False
            status_code = 9999
            reason = error

    return r


def getDuetVersion():
    # Used to get the status information from Duet
    try:
        # model = 'rr_model'
        URL = ('http://' + duet + '/rr_model?key=boards')
        r = urlCall(URL, 3, False)
        j = json.loads(r.text)
        version = j['result'][0]['firmwareVersion']
        return 'rr_model', version
    except:
        try:
            model = '/machine/system'
            URL = ('http://' + duet + '/machine/status')
            r = urlCall(URL, 3, False)
            j = json.loads(r.text)
            version = j['boards'][0]['firmwareVersion']
            return 'SBC', version
        except:
            return 'none', '0'


def getDuetJobname(model):
    # Used to get the print jobname from Duet
    if model == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=job.file.fileName')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                jobname = j['result']
                if jobname is None:
                    jobname = ''
                return jobname
            except:
                pass
    else:
        URL = ('http://' + duet + '/machine/status/')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                jobname = j['job']['file']['fileName']
                if jobname is None:
                    jobname = ''
                return jobname
            except:
                pass
    logger.info('getDuetJobname failed to get data. Code: ' + str(r.status_code) + ' Reason: ' + str(r.reason))
    return ''


def getDuetStatus(model):
    # Used to get the status information from Duet
    if model == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=state.status')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                status = j['result']
                return status
            except:
                pass
    else:
        URL = ('http://' + duet + '/machine/status/')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                status = j['state']['status']
                return status
            except:
                pass
    logger.info('getDuetStatus failed to get data. Code: ' + str(r.status_code) + ' Reason: ' + str(r.reason))
    return 'disconnected'


def getDuetLayer(model):
    # Used to get the status information from Duet
    if model == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=job.layer')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                layer = j['result']
                if layer is None:
                    layer = -1
                return layer
            except:
                pass
    else:
        URL = ('http://' + duet + '/machine/status/')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                layer = j['job']['layer']
                if layer is None:
                    layer = -1
                return layer
            except:
                pass
    logger.info('getDuetLayer failed to get data. Code: ' + str(r.status_code) + ' Reason: ' + str(r.reason))
    return 'disconnected'


def getDuetPosition(model):
    # Used to get the current head position from Duet
    if model == 'rr_model':
        URL = ('http://' + duet + '/rr_model?key=move.axes')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                Xpos = j['result'][0]['machinePosition']
                Ypos = j['result'][1]['machinePosition']
                Zpos = j['result'][2]['machinePosition']
                return Xpos, Ypos, Zpos
            except:
                pass
    else:
        URL = ('http://' + duet + '/machine/status')
        r = urlCall(URL, 3, False)
        if r.ok:
            try:
                j = json.loads(r.text)
                Xpos = j['move']['axes'][0]['machinePosition']
                Ypos = j['move']['axes'][1]['machinePosition']
                Zpos = j['move']['axes'][2]['machinePosition']
                return Xpos, Ypos, Zpos
            except:
                pass

    logger.info('getDuetPosition failed.  Code: ' + str(r.status_code) + ' Reason: ' + str(r.reason))
    logger.info('Returning coordinates as -1, -1, -1')
    return -1, -1, -1


def sendDuetGcode(model, command):
    # Used to get the status information from Duet
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
    onePhoto('Camera1', camera1, weburl1, camparam1)
    if camera2 != '':
        onePhoto('Camera2', camera1, weburl1, camparam1)
    createVideo(workingdir)

def terminate():
    global httpListener, listener, nextactionthread, httpthread
    cleanupFiles('terminate')
    # close the nextaction thread if necessary.  nextAction will have close the capturethread
    try:
        nextactionthread.join(10)
    except:
        pass
    # close the httpthread if necessary
    time.sleep(1)  # Give time for the last html to display
    try:
        httpthread.join(10)
    except:
        pass
    logger.info('Program Terminated')
    os.kill(int(pid), 9)


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
            logger.debug(btn)
            buttons = eval(btn)
        else:
            buttons = statusbutton + startbutton + standbybutton + pausebutton + continuebutton
            buttons = buttons + snapshotbutton + filesbutton + infobutton + restartbutton + terminatebutton + fpsbutton
            buttons = buttons + cssstyle

        return buttons

    def update_status(self):
        #global pidlist
        #pidlist = []
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
        else:
            imagelocation = 'Waiting for first image to be created'

        infotxt = []
        infotxt.append('<b>This instance is using the following options:</b><br><br>')
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
        global referer, refererip
        referer = self.headers['Host']  # Should always be there
        if not referer:  # Lets try authority
            referer = self.headers['authority']
            if not referer:
                referer = 'localhost'  # Best guess if all else fails
        split_referer = referer.split(":", 1)
        refererip = split_referer[0]  # just interested in the calling address as we know our port number

        global action, selectMessage, refreshing
        #options = ['status', 'start', 'standby', 'pause', 'continue', 'snapshot', 'restart', 'terminate']

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

            if win:
                file = file.replace('/', '\\')
                if os.path.isdir(file):
                    cmd = 'rmdir /s /q "' + file + '"'
                else:
                    cmd = 'del /q "' + file + '"'
            else:
                cmd = 'rm -rf "' + file + '"'

            if runsubprocess(cmd) is False:
                logger.info('!!!!! An error occurred trying to delete ' + file + ' !!!!!')

            selectMessage = self.display_dir(filepath)

        if query_components.get('zip'):
            file = query_components['zip'][0]
            filepath, _ = os.path.split(file)
            filepath = filepath + '/'
            file = topdir + file
            zipedfile = file + '.zip'

            if win:
                file = file.replace('/', '\\')
                zipedfile = zipedfile.replace('/', '\\')

            # threading.Thread(target=make_archive, args=(file, zipedfile,)).start()
            result = make_archive(file, zipedfile)
            selectMessage = '<h3>' + result + '<br></h3>' + self.display_dir(filepath)
            # selectMessage = self.display_dir(filepath)

        if query_components.get('terminate'):  # This form is only called from the UI - see also command=terminate
            terminatetype = query_components['terminate'][0]
            logger.info('Terminate Called from UI')
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
            logger.info('!!!!! http ' + command + ' request received !!!!!')

            if command == 'status':
                if selectMessage == None:
                    selectMessage = refreshing

                if action == 'standby':
                    allowed = ['start']
                elif action == 'pause':
                    allowed = ['standby', 'continue', 'snapshot', 'restart']
                elif action == 'snapshot' and lastaction == 'pause':  # same as pause
                    allowed = ['standby', 'continue', 'snapshot', 'restart']
                elif action == 'restart':
                    if standby:
                        allowed = ['start']
                    else:
                        allowed = ['standby', 'pause', 'snapshot', 'restart']
                else:
                    allowed = ['standby', 'pause', 'snapshot', 'restart']

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
                threading.Thread(target=nextAction, args=(command,)).start()

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
                threading.Thread(target=nextAction, args=(command,)).start()

            # pause / continue
            elif command == 'pause':
                txt = []
                txt.append('<h3>')
                txt.append('DuetLapse3 is paused.<br><br>')
                txt.append('</h3>')
                selectMessage = ''.join(txt)

                threading.Thread(target=nextAction, args=(command,)).start()

            elif command == 'continue':
                txt = []
                txt.append('<h3>')
                txt.append('DuetLapse3 is continuing.<br><br>')
                txt.append('</h3>')
                selectMessage = ''.join(txt)

                threading.Thread(target=nextAction, args=(command,)).start()

            # snapshot / restart / terminate

            elif command == 'snapshot':
                txt = []
                txt.append('<h3>')
                txt.append('Attempting to create an interim snapshot video')
                txt.append('</h3>')
                txt.append('<div class="info-disp">')
                txt.append('Check the files menu for completed snapshots<br>')
                txt.append('Depending on the number of images - this could take some time<br><br>')
                txt.append('After the snapshot DuetLapse3 returns to the prior state i.e. <b>start or pause</b><br>')
                txt.append('</div>')
                selectMessage = ''.join(txt)

                threading.Thread(target=nextAction, args=(command,)).start()

            elif command == 'restart':
                txt = []
                txt.append('<h3>')
                txt.append('Restarting DuetLapse3')
                txt.append('</h3>')
                txt.append('<div class="info-disp">')
                txt.append('Will create a video with the current images.<br>')
                txt.append('All captured images will be deleted.<br>')
                txt.append('The restart behavior is the same as initially used to start DuetLapse3<br>')
                txt.append('</div>')
                selectMessage = ''.join(txt)

                threading.Thread(target=nextAction, args=(command,)).start()

            elif command == 'terminate':  #only called explicitely - backward compatible
                    selectMessage = self.terminate_process('graceful')

            else:
                selectMessage = self.ignoreCommandMsg(command, action)

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

    def ignoreCommandMsg(self, command, action):
        txt = []
        txt.append('<h3>')
        txt.append(command + ' request has been ignored<br><br>')
        txt.append(action + ' state is currently enabled')
        txt.append('</h3>')
        msg = ''.join(txt)

        return msg

    def terminate_process(self, type):
        logger.info('Entering Terminate process')
        if type == None: type = ''

        if type == 'graceful':
            txt = []
            txt.append('<h3>')
            txt.append('Terminating DuetLapse3<br><br>')
            txt.append('Will finish last image capture, create a video, then terminate.')
            txt.append('</h3>')
            selectMessage = ''.join(txt)

            threading.Thread(target=nextAction, args=('terminate',)).start()
        elif type == 'forced':
            txt = []
            txt.append('<h3>')
            txt.append('Forced Termination of DuetLapse3<br><br>')
            txt.append('No video will be created.')
            txt.append('</h3>')
            selectMessage = ''.join(txt)

            threading.Thread(target=terminate, args=()).start()

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
        # Don't forget explicit trailing slash when normalizing. Issue17324
        trailing_slash = path.rstrip().endswith('/')
        requested_dir = topdir + path
        if win:
            requested_dir = requested_dir.replace('/','\\') #since linux path format being passed

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
                logger.info('Connection reset - normal if displaying file')
            except:
                logger.info('Error sending file')

        return ''

    def list_dir(self, path):  # Copied from super class
        # Pass the directory tree and determine what can be done with each file / dir
        jpegfile = '.jpeg'
        deletablefiles = ['.mp4','.zip'] #Different to startDUetLapse3
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
        # Pass the direstory tree and determine what can be done with each file / dir - NOT USED
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

        for name in list:  #this loop is DuetLapse3 specific - different to startDuetLapse3
            if not name.startswith(pid) and not name.endswith('.jpeg'):
                continue  # only display for this instance

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

            # else:  # r.append('</tr>') #end the row

        r.append('</table>')

        response = ''.join(r)
        return response

"""
    end of requesthandler
"""

def createHttpListener():
    global listener
    listener = ThreadingHTTPServer((host, port), MyHandler)
    listener.serve_forever()
    sys.exit(7)  # May not be needed since never returns from serve_forever


###################################
#  Main Control Functions
###################################

def captureLoop():  # Run as a thread
    global capturing, printState, duetStatus, nextactionthread
    capturing = True
    disconnected = 0
    printState = 'Not Capturing'
    lastDuetStatus = ''

    while capturing:  # action can be changed by httpListener or SIGINT or CTL+C

        duetStatus = getDuetStatus(apiModel)

        if duetStatus == 'disconnected':  # provide some resiliency for temporary disconnects
            disconnected += 1
            logger.info('Printer is disconnected - Trying to reconnect')
            if disconnected > 10:  # keep trying for a while just in case it was a transient issue
                logger.info('')
                logger.info(
                        '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info('Printer was disconnected from Duet for too long')
                logger.info('Finishing this capture attempt')
                logger.info(
                        '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info('')
                printState = 'Disconnected'
                nextactionthread = threading.Thread(target=nextAction,
                                                    args=('terminate',)).start()  # Note comma in args is needed
                # nextactionthread.start()
                return

        if duetStatus != lastDuetStatus:  # What to do next?
            logger.info('****** Duet status changed to: ' + duetStatus + ' *****')
            # logical states for printer are printing, completed
            if (duetStatus == 'idle') and (printState in ['Capturing', 'Busy']):  # print job has finished
                printState = 'Completed'  # logger.info('****** Print State changed to ' + printState + ' *****')
            elif (duetStatus in ['processing', 'idle']) or (duetStatus == 'paused' and detect == 'pause'):
                printState = 'Capturing'  # logger.info('****** Print State changed to: ' + printState + ' *****')
            elif duetStatus == 'busy':
                printState = 'Busy'  # logger.info('****** Print State changed to: ' + printState + ' *****')
            else:
                printState = 'Waiting'
            logger.info('****** Print State changed to: ' + printState + ' *****')

        if printState == 'Capturing':
            oneInterval('Camera1', camera1, weburl1, camparam1)
            if camera2 != '':
                oneInterval('Camera2', camera2, weburl2, camparam2)
            unPause()  # Nothing should be paused at this point
            disconnected = 0
        elif printState == 'Completed':
            logger.info('Print Job Completed')
            printState = 'Not Capturing'
            # use a thread here as it will allow this thread to close.
            nextactionthread = threading.Thread(target=nextAction,
                                                args=('terminate',)).start()  # Note comma in args is needed
            return

        if capturing:  # If no longer capturing - sleep is by-passed for speedier exit response
            lastDuetStatus = duetStatus
            #how long since last image capture
            time.sleep(poll)  # poll every n seconds - placed here to speed startup

    logger.info('Exiting Capture loop')
    capturing = False
    printState = 'Not Capturing'
    return  # The return ends the thread


def nextAction(nextaction):  # can be run as a thread
    global action, capturethread, capturing, lastaction
    lastaction = action
    action = nextaction  # default

    # All nextactions assume the capturethread is shutdown
    try:
        capturing = False  # Signals captureThread to shutdown
        time.sleep(1)  # Wait a few seconds to avoid race condition e.g. printer paused to capture image
        capturethread.join(10)  # Timeout is to wait up to 10 seconds for capture thread to stop
    except:
        pass

    # This test is positionally sensitive
    if nextaction == 'completed':  # end of a print job
        if httpListener:  # controlled by http listener
            nextaction = 'restart'
        else:  # running as a one-off
            nextaction = 'terminate'

    logger.info('++++++ Entering ' + action + ' state ++++++')

    if nextaction == 'start':
        capturing = True
    elif nextaction == 'standby':
        cleanupFiles(nextaction)  # clean up and start again
        setstartvalues()
    if nextaction == 'pause':
        pass
    elif nextaction == 'continue':
        capturing = True
        action = 'start'
    elif nextaction == 'snapshot':
        makeVideo()
        if lastaction == 'pause':
            action = lastaction
            capturing = False
        else:
            capturing = True
    elif nextaction == 'restart':
        makeVideo()
        cleanupFiles(nextaction)  # clean up and start again
        setstartvalues()
        startNow()
        if standby:
            action = 'standby'
        else:
            action = 'start'
            capturing = True
    elif nextaction == 'terminate':
        if novideo:
            logger.info('Video creation was skipped')
        else:
            makeVideo()
        terminate()
    elif nextaction == 'disconnected':
        terminate()

    if capturing:
        action = 'start'
        logger.info('++++++ Entering ' + action + ' state ++++++')
        capturethread = threading.Thread(target=captureLoop, args=()).start()  # capturethread.start()

    return


def startMessages():
    if startNow():
        logger.info('')
        logger.info('##########################################################')
        logger.info('Will start capturing images immediately')
        logger.info('##########################################################')
        logger.info('')
    else:
        logger.info('')
        logger.info('##########################################################')
        if 'layer' in detect:
            logger.info('Will start capturing images on first layer change')
        elif 'pause' in detect:
            logger.info('Will start capturing images on first pause in print stream')
        logger.info('##########################################################')
        logger.info('')

    if standby:
        logger.info('')
        logger.info('##########################################################')
        logger.info('Will not start until command=start received from http listener')
        logger.info('##########################################################')
        logger.info('')

    logger.info('')
    logger.info('##########################################################')
    logger.info('Video will be created when printing ends')
    logger.info('or if program termination is requested from the browser interface')
    logger.info('##########################################################')
    logger.info('')
    logger.info('##########################################################')
    logger.info('If running from a console using the command line')
    if win:
        logger.info('Press Ctrl+Break one time to stop the program and create a video.')
        logger.info('On machines without the Break key - try Fn+Ctl+B')
    else:
        logger.info('Press Ctrl+C one time to stop the program and create a video.')
    logger.info('##########################################################')
    logger.info('')

    return


def startHttpListener(host, port):
    global httpthread
    sock = socket.socket()
    if (host == '0.0.0.0') and win:  # Windows does not report properly with 0.0.0.0
        portcheck = sock.connect_ex(('127.0.0.1', port))
    else:
        portcheck = sock.connect_ex((host, port))

    if portcheck == 0:
        logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        logger.info('Sorry, port ' + str(port) + ' is already in use.')
        logger.info('Shutting down this instance.')
        logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        sys.exit(8)

    # import threading
    httpthread = threading.Thread(target=createHttpListener, args=()).start()
    logger.info('')
    logger.info('##########################################################')
    logger.info('***** Started http listener *****')
    logger.info('##########################################################')
    logger.info('')


###########################
# Program  begins here
###########################
if __name__ == "__main__":  # Do not run anything below if the file is imported by another program

    # Globals.
    global httpListener, win, pid, action, workingdir_exists
    httpListener = False  # Indicates if an integral httpListener should be started
    win = False  # Windows OS
    pid = ''  # pid for this instance - used for temp filenames
    workingdir_exists = False

    setstartvalues()  # Default startup global values

    init()

    startMessages()

    startNow()  # Determine starting action

    try:
        if httpListener:
            startHttpListener(host, port)

        nextAction(action)

    except KeyboardInterrupt:
        pass  # This is handled as SIGINT