#!/usr/bin/env python3

"""
#Python Script to take Time Lapse photographs during a print on 
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
# Developed on Raspberry Pi with Debian Buster and on Windows 10. SHOULD work on most other linux didtributions. 
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

# Globals.
alreadyPaused  = False           # If printer is paused, have we taken our actions yet?
httpListener = False             # Indicates if an integral httpListener should be started
win = False                      # Windows OS
pid = 0                          # pid for this instance - used for temp filenames

def setStartValues():
    global zo1, zo2, printerState, timePriorPhoto1, timePriorPhoto2, frame1, frame2, action, startnow
    zo1 = -1                         # Starting layer for Camera1
    zo2 = -1                         # Starting layer for Camera2
    printerState = 'waiting' 
    timePriorPhoto1 = 0 #reset time of last image capture
    timePriorPhoto2 = 0
    frame1 = 0       #reset the frame counters
    frame2 = 0
    action = 'run'
    startnow = False
    
setStartValues()    
###########################
# Methods begin here
###########################


def init():
    # parse command line arguments
    parser = argparse.ArgumentParser(description='Create time lapse video for Duet3D based printer. V3.1.0', allow_abbrev=False)
    #Environment
    parser.add_argument('-duet',type=str,nargs=1,default=['localhost'],help='Name of duet or ip address. Default = localhost')
    parser.add_argument('-poll',type=float,nargs=1,default=[5])
    parser.add_argument('-basedir',type=str,nargs=1,default=[''],help='default = This script  directory')
    parser.add_argument('-instances',type=str,nargs=1,choices=['single','oneip','many'],default=['single'],help='Default = single')
    parser.add_argument('-logtype',type=str,nargs=1,choices=['console','file','both'],default=['both'],help='Default = both')
    parser.add_argument('-verbose',action='store_true',help='Output stdout and stderr from system calls')
    parser.add_argument('-host',type=str,nargs=1,default=['0.0.0.0'],help='The ip address this service listens on. Default = localhost')
    parser.add_argument('-port',type=int,nargs=1,default=[0],help='Specify the port on which the server listens. Default = 0')
    #Execution
    parser.add_argument('-dontwait',action='store_true',help='Capture images immediately.')
    parser.add_argument('-seconds',type=float,nargs=1,default=[0])
    parser.add_argument('-detect',type=str,nargs=1,choices= ['layer', 'pause', 'none'],default=['layer'],help='Trigger for capturing images. Default = layer')
    parser.add_argument('-pause',type=str,nargs=1,choices= ['yes', 'no'],default=['no'],help='Park head before image capture.  Default = no')
    parser.add_argument('-movehead',type=float,nargs=2,default=[0.0,0.0], help='Where to park head on pause, Default = 0,0')
    parser.add_argument('-standby',action='store_true',help='Wait for command from http listener')
    #Camera
    parser.add_argument('-camera1',type=str,nargs=1,choices=['usb','pi','web','stream','other'],default=['usb'],help='Mandatory Camera. Default = usb')
    parser.add_argument('-weburl1',type=str,nargs=1,default=[''],help='Url for Camera1 if web or stream') 
    parser.add_argument('-camera2',type=str,nargs=1,choices=['usb','pi','web','stream','other'],default=[''],help='Optional second camera. No Default')
    parser.add_argument('-weburl2',type=str,nargs=1,default=[''],help='Url for Camera2 if web or stream')
    #Video
    parser.add_argument('-extratime',type=float,nargs=1,default=[0],help='Time to repeat last image, Default = 0')
    #Overrides
    parser.add_argument('-camparam1',type=str,nargs=1,default=[''],help='Camera1 Capture overrides. Use -camparam1="parameters"')
    parser.add_argument('-camparam2',type=str,nargs='*',default=[''],help='Camera2 Capture overrides. Use -camparam2="parameters"')
    parser.add_argument('-vidparam1',type=str,nargs=1,default=[''],help='Camera1 Video overrides. Use -vidparam1="parameters"')    
    parser.add_argument('-vidparam2',type=str,nargs=1,default=[''],help='Camera2 Video overrides. Use -vidparam2="parameters"')     

    args=vars(parser.parse_args())

    #Environment
    global duet, basedir, poll, instances, logtype, verbose, host, port
    #Derived  globals
    global duetname, debug, ffmpegquiet, httpListener   
    duet     = args['duet'][0]
    basedir  = args['basedir'] [0]
    poll  = args['poll'][0]
    instances = args['instances'] [0]
    logtype   = args['logtype'] [0]    
    verbose = args['verbose']
    host = args['host'][0]
    port = args['port'][0]

    #Execution
    global dontwait, seconds, detect, pause, movehead, standby       
    dontwait = args['dontwait']
    seconds  = args['seconds'][0]
    detect   = args['detect'][0]
    pause    = args['pause'][0]
    movehead = args['movehead']  
    standby = args['standby']
    #Camera
    global camera1, camera2, weburl1, weburl2     
    camera1   = args['camera1'][0]
    camera2   = args['camera2'][0]
    weburl1   = args['weburl1'][0]
    weburl2   = args['weburl2'][0]


    #Video
    global extratime   
    extratime = str(args['extratime'] [0])
    
    #Overrides
    global camparam1, camparam2, vidparam1, vidparam2
    camparam1   = args['camparam1'][0]
    camparam2   = args['camparam2'][0]
    vidparam1   = args['vidparam1'][0]    
    vidparam2   = args['vidparam2'][0] 
    
    ############################################################
    #Check to see if this instance is allowed to run  
    ############################################################
    
    proccount = 0
    allowed = 0
       
    import psutil
    for p in psutil.process_iter():      
         if 'python3' in p.name() and __file__ in p.cmdline():
              proccount += 1
              if ('single' in instances):
                  allowed += 1
              if ('oneip' in instances):
                   if duet in p.cmdline():
                        allowed += 1
    
    if (allowed > 1):
           print('')
           print('#############################')
           print('Process is already running... shutting down.')
           print('#############################')
           print('')
           sys.exit(0)
               
    ####################################################
    # Setup for logging and filenames
    ####################################################
    
    #pid is used to create unique filenames
    global pid       
    pid = str(os.getpid())
        
    #  What OS are we using? Affects cleanupFiles() and logger setup
    global win
    operatingsystem = platform.system()
    if(operatingsystem == 'Windows'):
        win = True
    else:
        win = False
    print(operatingsystem)        
    # How much output
    if (verbose) :
        debug = ''
        ffmpegquiet = ''
    else:
        ffmpegquiet = ' -loglevel quiet'
        if (not win):
            debug = ' > /dev/null 2>&1'
        else:
            debug = ' > nul 2>&1'
            
    # set base directory for files
    if (basedir == ''): basedir = os.path.dirname(os.path.realpath(__file__))
 
    #duetname used for filenames and directories
    duetname = duet.replace('.' , '-')
    
    #  Set up directories and clean up files 
    cleanupFiles()
    
    # Create a custom logger
    import logging
    global logger
    logger = logging.getLogger('DuetLapse3')
    logger.setLevel(logging.DEBUG)

# Create handlers and formats
    if ('console' in logtype or 'both' in logtype) : 
        c_handler = logging.StreamHandler()
        c_format = logging.Formatter(duet+' %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)
   
   
    if ('file' in logtype or 'both' in logtype) :
        if (proccount > 1):
             f_handler = logging.FileHandler(basedir+'/'+duetname+'/DuetLapse3.log', mode='a')
        else:
             f_handler = logging.FileHandler(basedir+'/'+duetname+'/DuetLapse3.log', mode='w')        

        f_format = logging.Formatter(duet+' - %(asctime)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)    
    
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
    logger.info("# verbose         = {0:50s}".format(str(verbose)))
    logger.info("# os              = {0:50s}".format(operatingsystem))
    logger.info("# host            = {0:50s}".format(str(host)))    
    logger.info("# port            = {0:50s}".format(str(port)))
    logger.info("# pid            = {0:50s}".format(pid))
    logger.info("#Execution Setings:")    
    logger.info("# dontwait        = {0:50s}".format(str(dontwait)))
    logger.info("# seconds         = {0:50s}".format(str(seconds)))   
    logger.info("# detect          = {0:50s}".format(detect))
    logger.info("# pause           = {0:50s}".format(pause))
    if (movehead[0] != 0 and movehead[1] != 0):
        logger.info("# movehead    = {0:6.2f} {1:6.2f} ".format(movehead[0],movehead[1]))
    logger.info("# standby     = {0:50s}".format(str(standby)))
    logger.info("#Camera1 Settings:")
    logger.info("# camera1         = {0:50s}".format(camera1))
    logger.info("# weburl1         = {0:50s}".format(weburl1))
    if (camparam1 != ''):
        logger.info("# Camera1 Override:")    
        logger.info("# camparam1       = {0:50s}".format(camparam1))
    if (camera2 != ''):
        logger.info("# Camera2 Settings:")
        logger.info("# camera2     =     {0:50s}".format(camera2))
        logger.info("# weburl2     =     {0:50s}".format(weburl2))
    if (camparam2 != ''):
        logger.info("# Camera2 Override:")
        logger.info("# camparam2    =    {0:50s}".format(camparam2))   
    logger.info("# Video Settings:")
    logger.info("# extratime   =     {0:50s}".format(extratime))
    if (vidparam1 != ''):
        logger.info("# Video1 Override:")
        logger.info("# vidparam1    =    {0:50s}".format(vidparam1))
    if (vidparam2 != ''):
        logger.info("# Video2 Override:")
        logger.info("# vidparam2    =    {0:50s}".format(vidparam2))
    logger.info("###################################################################")
    logger.info('')
           
 
    
    ###############################################
    #derived parameters
    ##############################################
                         
    #Polling interval should be at least = seconds so as not to miss interval
    if (poll > seconds and seconds != 0): poll = seconds    #Need to poll at least as often as seconds
    if ('none' in detect and seconds != 0): poll = seconds  #No point in polling more often
        
    #  Port number must be given for httpListener to be active
    if (port != 0):
        httpListener = True
        
    global action    
    if (standby and httpListener):   #will not begin running until it gets continue command from httpListener 
        action = 'stopped'
       
    ########################################################################       
    # Inform regarding valid and invalid combinations
    #########################################################################
    
    #Valid
        
    if (standby and not httpListener):
        logger.info('************************************************************************************')
        logger.info('Warning: -standby ignored.  It has no effect unless http Listener is active.')
        logger.info('Specify -localhost and -port to activate http Listener')
        logger.info('************************************************************************************')        
        
    if ((seconds > 0) and (not 'none' in detect)):
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds '+str(seconds)+' and -detect '+detect+' will trigger on both.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************')
        
    if (startnowCheck()):
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds '+str(seconds)+' and -detect '+detect)
        logger.info('This combination implies -dontwait')
        logger.info('************************************************************************************')
        
    if ('pause' in detect):
        logger.info('************************************************************************************')
        logger.info('* Note "-detect pause" means that the G-Code on the printer already contains pauses,')
        logger.info('* and that this script will detect them, take a photo, and issue a resume.')
        logger.info('* Head position during those pauses is can be controlled by the pause.g macro ')
        logger.info('* on the duet, or by specifying "-movehead nnn nnn".')
        logger.info('*')
        logger.info('* If instead, it is desired that this script force the printer to pause with no')
        logger.info('* pauses in the gcode, specify either:')
        logger.info('* "-pause yes -detect layer" or "-pause yes -seconds nnn".')
        logger.info('************************************************************************************')


    if ('yes' in pause):
        logger.info('************************************************************************************')
        logger.info('* Note "-pause yes" means this script will pause the printer when the -detect and / or ')
        logger.info('* -seconds flags trigger.')
        logger.info('*')
        logger.info('* If instead, it is desired that this script detect pauses that are already in')
        logger.info('* in the gcode, specify:')
        logger.info('* "-detect pause"')
        logger.info('************************************************************************************')
        
    #invalid
    
 
#    if (standby and httpListener and dontwait):
#        logger.info('************************************************************************************')
#        logger.info('Invalid Combination: -standby with -dontwait and http Listener active.')
#        logger.info('Specify none or one of -dontwait or -standby if using http Listener')
#        logger.info('************************************************************************************') 
#        sys.exit(2)
    
    logger.info('')
    if (camera1 !='other' and camparam1 !=''):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type '+camera1+' cannot be used with camparam1')  
        logger.info('************************************************************************************')
        sys.exit(2)
        
    if (camera2 !='other' and camparam2 !=''):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type '+camera2+' cannot be used with camparam2')  
        logger.info('************************************************************************************')
        sys.exit(2)
        
    if ((camera1 =='usb' or camera1 == 'pi')  and win):   #  These do not work on WIN OS
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type '+camera1+' cannot be on Windows OS')  
        logger.info('************************************************************************************')
        sys.exit(2)
        
    if ((camera2 =='usb' or camera2 == 'pi')  and win):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: Camera type '+camera2+' cannot be on Windows OS')  
        logger.info('************************************************************************************')
        sys.exit(2)

    if ((seconds <= 0) and ('none' in detect)):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination:: -seconds '+str(seconds)+' and -detect '+detect+' nothing will be captured.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************')
        sys.exit(2)
        
    if ((not movehead == [0.0,0.0]) and ((not 'yes' in pause) and (not 'pause' in detect))):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: "-movehead {0:1.2f} {1:1.2f}" requires either "-pause yes" or "-detect pause".'.format(movehead[0],movehead[1]))
        logger.info('************************************************************************************')
        sys.exit(2)

    if (('yes' in pause) and ('pause' in detect)):
        logger.info('************************************************************************************')
        logger.info('Invalid Combination: "-pause yes" causes this script to pause printer when')
        logger.info('other events are detected, and "-detect pause" requires the gcode on the printer')
        logger.info('contain its own pauses.  These cannot be used together.')
        logger.info('************************************************************************************')
        sys.exit(2)
        

    def checkDependencies(camera):        
        #
        if (not win):
           finder = 'whereis'
        else:
            finder = 'where'
            
        if ('usb' in camera):
            if (20 > len(subprocess.check_output(finder+' fswebcam', shell=True))):
                logger.info("Module 'fswebcam' is required. ")
                logger.info("Obtain via 'sudo apt install fswebcam'")
                sys.exit(2)

        if ('pi' in camera):
            if (20 > len(subprocess.check_output(finder+' raspistill', shell=True))):
                logger.info("Module 'raspistill' is required. ")
                logger.info("Obtain via 'sudo apt install raspistill'")
                sys.exit(2)

        if ('stream' in camera):
            if (20 > len(subprocess.check_output(finder+' ffmpeg', shell=True))):
                logger.info("Module 'ffmpeg' is required. ")
                logger.info("Obtain via 'sudo apt install ffmpeg'")
                sys.exit(2)

        if ('web' in camera):
            if (20 > len(subprocess.check_output(finder+' wget', shell=True))):
                logger.info("Module 'wget' is required. ")
                logger.info("Obtain via 'sudo apt install wget'")
                sys.exit(2)
        
        if (20 > len(subprocess.check_output(finder+' ffmpeg', shell=True))):
            logger.info("Module 'ffmpeg' is required. ")
            logger.info("Obtain via 'sudo apt install ffmpeg'")

            sys.exit(2)

    checkDependencies(camera1)
    if (camera2 != ''): checkDependencies(camera2)

    
    # Get connected to the printer.
    
    global apiModel

# Get connected to the printer.

    apiModel, printerVersion = getDuetVersion()
    if (apiModel == 'none'):
        logger.info('')
        logger.info('###############################################################')
        logger.info('The printer at '+duet+' did not respond')
        logger.info('Check the ip address or logical printer name is correct')
        logger.info('Duet software must support rr_model or /machine/status')
        logger.info('###############################################################')
        logger.info('')
        sys.exit(2)
    
    majorVersion = int(printerVersion[0])

    if (majorVersion >= 3):
        logger.info('')
        logger.info('###############################################################')
        logger.info('Connected to printer at '+duet+' using version '+printerVersion+' and API access using '+apiModel)
        logger.info('###############################################################')
        logger.info('')
    else:
        logger.info('')
        logger.info('###############################################################')
        logger.info('The printer at '+duet+' needs to be at version 3 or above')
        logger.info('The version on this printer is '+printerVersion)
        logger.info('###############################################################')
        logger.info('')
        sys.exit(2)
    
    #Allows process running in background or foreground to be gracefully
    # shutdown with SIGINT (kill -2 <pid>
    import signal

    def quit_gracefully(*args):
        logger.info('!!!!!! Stopped by SIGINT - Post Processing !!!!!!')
        makeVideo()
        terminate()

    if __name__ == "__main__":
        signal.signal(signal.SIGINT, quit_gracefully)

"""
End of init()
"""

#####################################################
##  Utility Functions
#####################################################

def cleanupFiles():           
    """
       Add logic if multiple instances allowed for file cleanup 
    """    
    # Make and clean up directorys.
    #Make sure there is a directory for the resulting video
    global win
    if (win):
        subprocess.call('mkdir "'+basedir+'\\'+duetname+'"'+debug, shell=True)
        #Clean up the tmp directory
        subprocess.call('rmdir "'+basedir+'\\'+duetname+'\\tmp" /s /q'+debug, shell=True)
        subprocess.call('mkdir "'+basedir+'\\'+duetname+'\\tmp"'+debug, shell=True)
    else:
        subprocess.call('mkdir "'+basedir+'/'+duetname+'"'+debug, shell=True)
        #Clean up the tmp directory
        subprocess.call('rm -rf "'+basedir+'/'+duetname+'/tmp"'+debug, shell=True)
        subprocess.call('mkdir "'+basedir+'/'+duetname+'/tmp"'+debug, shell=True)
        
        
def startnowCheck():
    global startnow
    if (seconds > 0 and (dontwait or 'none' in detect)):
        startnow = True
    else:
        startnow = False
    return startnow

#####################################################
##  Processing Functions
#####################################################

def checkForPause():
    # Checks to see if we should pause or are paused; if so, returns after pause and head movement complete.
    global alreadyPaused
    alreadyPaused = False
    if (printerState == 'printing' and pause == 'yes'):  #DuetLapse is controlling when to pause
        logger.info('Requesting pause via M25')
        sendDuetGcode(apiModel, 'M25')    # Ask for a pause
        loop = 0
        while (loop < 10):  #limit the counter in case there is a problem
            time.sleep(1)  # wait a second and try again
            if(getDuetStatus(apiModel) == 'paused'):
                alreadyPaused = True
                loop = 99
            loop += 1
        if (loop == 99):
               logger.info('Loop exceeded: Target was: paused')
          
    if (alreadyPaused or printerState == 'paused'):  
        if(not movehead == [0.0,0.0]):   #optional repositioning of head
            logger.info('Moving print head to X{0:4.2f} Y{1:4.2f}'.format(movehead[0],movehead[1]))
            sendDuetGcode(apiModel, 'G0 X{0:4.2f} Y{1:4.2f}'.format(movehead[0],movehead[1]))
            loop = 0
            while (loop < 10): #limit the counter in case there is a problem
               time.sleep(1)  # wait a second and try again
               xpos, ypos, _ = getDuetPosition(apiModel)
               if ((abs(xpos - movehead[0]) < .2) and (abs(ypos - movehead[1]) < .2)):   #close enough for government work
                   loop = 99 
               loop += 1
            if (loop == 99):
               logger.info('Loop exceeded for X,Y: '+str(xpos)+','+str(ypos)+' Target was: '+str(movehead[0])+','+str(movehead[1]))

    return

def unPause():
    global alreadyPaused
    if (alreadyPaused or printerState == 'paused'):
        logger.info('Requesting un pause via M24')
        sendDuetGcode(apiModel,'M24')

def onePhoto(cameraname, camera, weburl, camparam): 
    global frame1, frame2
    
    if (cameraname == 'Camera1'):
        frame1 += 1
        frame = frame1
    else:
        frame2 += 1
        frame = frame2
        
    s=str(frame).zfill(8)
    fn = '"'+basedir+'/'+duetname+'/tmp/'+cameraname+pid+'-'+s+'.jpeg"'

    if ('usb' in camera): 
        cmd = 'fswebcam --quiet --no-banner '+fn+debug
            
    if ('pi' in camera): 
        cmd = 'raspistill -t 1 -ex sports -mm matrix -n -o '+fn+debug
            
    if ('stream' in camera):
        cmd = 'ffmpeg'+ffmpegquiet+' -y -i '+weburl+ ' -vframes 1 ' +fn+debug
        
    if ('web' in camera): 
        cmd = 'wget --auth-no-challenge -nv -O '+fn+' "'+weburl+'" '+debug
        
    if ('other' in camera):
        cmd = eval(camparam)
            
    subprocess.call(cmd, shell=True)
    global timePriorPhoto1, timePriorPhoto2
    if (cameraname == 'Camera1'):
        timePriorPhoto1 = time.time()
    else:
        timePriorPhoto2 = time.time()
    
def oneInterval(cameraname, camera, weburl, camparam):
    global frame1, frame2
    global timePriorPhoto1, timePriorPhoto2
    
    #select the prior frame counter
    if (cameraname =='Camera1'):
        frame = frame1
    else:
        frame = frame2
        
    #update the layer counter
    global zo1, zo2
    zn = getDuetLayer(apiModel)
    if (cameraname == 'Camera1'):
        zo1 = zn
    else:
        zo2 = zn
    
    if ('layer' in detect):
        if ((not zn == zo1 and cameraname == 'Camera1') or (not zn == zo2 and cameraname == 'Camera2')):
            # Layer changed, take a picture.
            checkForPause()
            logger.info(cameraname+': capturing frame '+str(frame)+' at layer '+str(zn)+' after layer change')           
            onePhoto(cameraname, camera, weburl, camparam)            

    elif ('pause' in detect and printerState == 'paused'):
            checkForPause()
            logger.info(cameraname+': capturing frame '+str(frame)+' at layer '+str(zn)+' at pause in print gcode')
            onePhoto(cameraname, camera, weburl, camparam)
    
    #Note that onePhoto() updates timePriorPhoto1 and timePriorPhoto2
    if (cameraname == 'Camera1'):
        elap = (time.time() - timePriorPhoto1)
    else:
        elap = (time.time() - timePriorPhoto2)

    if ((seconds > 0) and (seconds < elap)):
        checkForPause()
        logger.info(cameraname+': capturing frame '+str(frame)+' at layer '+str(zn)+' after '+str(seconds)+' seconds')
        onePhoto(cameraname, camera, weburl, camparam)

def postProcess(cameraname, camera, vidparam):
    
    logger.info('')
    if (cameraname == 'Camera1'):
        frame = frame1
    else:
        frame = frame2
        
    if (frame < 10):
        logger.info(cameraname+': Cannot create video with only '+str(frame)+' frames')
        return
     
    logger.info(cameraname+': now making '+str(frame)+' frames into a video')
    if (250 < frame): logger.info("This can take a while...")
    fn = '"'+basedir+'/'+duetname+'/'+cameraname+pid+'-'+time.strftime('%a-%H-%M',time.localtime())+'.mp4"'

    if (vidparam == ''):
        if (float(extratime) > 0):  #needs ffmpeg > 4.2
            if(win):
                #Windows version does not like fps=10 argument   
                cmd  = 'ffmpeg'+ffmpegquiet+' -r 10 -i "'+basedir+'/'+duetname+'/tmp/'+cameraname+pid+'-%08d.jpeg" -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+' '+fn+debug
            else:
                cmd  = 'ffmpeg'+ffmpegquiet+' -r 10 -i "'+basedir+'/'+duetname+'/tmp/'+cameraname+pid+'-%08d.jpeg" -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn+debug
        else: #Using an earlier version of ffmpeg that does not support tpad (and hence extratime)
            cmd  = 'ffmpeg'+ffmpegquiet+' -r 10 -i "'+basedir+'/'+duetname+'/tmp/'+cameraname+pid+'-%08d.jpeg" -vcodec libx264 -y '+fn+debug
    else:
        cmd = eval(vidparam)    
              
    subprocess.call(cmd, shell=True)
    logger.info('Video processing complete for '+cameraname)
    logger.info('Video is in file '+fn)
    
#############################################################################
##############  Duet API access Functions
#############################################################################

def  getDuetVersion():
#Used to get the status information from Duet
    try:
        model = 'rr_model'
        URL=('http://'+duet+'/rr_model?key=boards')
        r = requests.get(URL, timeout=5)
        j = json.loads(r.text)
        version = j['result'][0]['firmwareVersion']
        return 'rr_model', version;
    except:
        try:
            model='/machine/system'
            URL=('http://'+duet+'/machine/status')              
            r = requests.get(URL, timeout=5)
            j = json.loads(r.text)
            version = j['boards'][0]['firmwareVersion']
            return 'SBC', version;
        except:
            return 'none', '0';
      

def  getDuetStatus(model):
#Used to get the status information from Duet
    if (model == 'rr_model'):
        URL=('http://'+duet+'/rr_model?key=state.status')
        r = requests.get(URL, timeout=120)  #Long timeout to handle restart of Duet
        if(r.ok):
            try:
                j = json.loads(r.text)
                status = j['result']
                return status           
            except:
                pass
    else:
        URL=('http://'+duet+'/machine/status/')
        r = requests.get(URL, timeout=120)  #Long timeout to handle restart of Duet
        if(r.ok):
            try:
                j = json.loads(r.text)
                status = j['state']['status']
                return status
            except requests.exceptions.RequestException as e:
                pass
    logger.info('getDuetStatus failed to get data. Code: '+str(r.status_code)+' Reason: '+str(r.reason))
    return 'disconnected'


def  getDuetLayer(model):
#Used to get the status information from Duet
    if (model == 'rr_model'):
        URL=('http://'+duet+'/rr_model?key=job.layer')
        r = requests.get(URL, timeout=5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                layer = j['result']
                return layer           
            except:
                pass
    else:
        URL=('http://'+duet+'/machine/status/')
        r = requests.get(URL, timeout=5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                layer = j['job']['layer']
                return layer
            except:
                pass
    logger.info('getDuetLayer failed to get data. Code: '+str(r.status_code)+' Reason: '+str(r.reason))
    return 'disconnected'
        
def  getDuetPosition(model):
#Used to get the current head position from Duet
    if (model == 'rr_model'):
        URL=('http://'+duet+'/rr_model?key=move.axes')
        r = requests.get(URL, timeout=5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                Xpos = j['result'][0]['machinePosition']
                Ypos = j['result'][1]['machinePosition']
                Zpos = j['result'][2]['machinePosition']
                return Xpos, Ypos, Zpos;
            except:
                pass
    else:
        URL=('http://'+duet+'/machine/status')
        r = requests.get(URL, timeout=5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                Xpos = j['move']['axes'][0]['machinePosition']
                Ypos = j['move']['axes'][1]['machinePosition']
                Zpos = j['move']['axes'][2]['machinePosition']
                return Xpos, Ypos, Zpos;
            except:
                pass
                
    logger.info('getDuetPosition failed.  Code: '+str(r.status_code)+' Reason: '+str(r.reason))
    logger.info('Returning coordinates as 9999, 9999, 9999')
    return 9999, 9999, 9999;
                
def  sendDuetGcode(model, command):     
#Used to get the status information from Duet
    if (model == 'rr_model'):
        URL=('http://'+duet+'/rr_gcode?gcode='+command)
        r = requests.get(URL, timeout=5)
    else:
        URL=('http://'+duet+'/machine/code')
        r = requests.post(URL, data=command)

    if (r.ok):
       return
        
    logger.info('sendDuetGCode failed with code: '+str(r.status_code)+'and reason: '+str(r.reason))
    return

def makeVideo():
    postProcess('Camera1', camera1, vidparam1)
    if (camera2 != ''): postProcess('Camera2', camera2, vidparam2)
    
def terminate():
    global httpListener, listener
    if(httpListener):
        logger.info('Waiting for http listener to shutdown.')
        listener.shutdown()
        listener.server_close()
    logger.info('Program Terminated')
    sys.exit(0)

###########################
# Integral Web Server
###########################
"""
Use Threading HTTPServer as it's likely more robust with Chrome
Less likely to hold connection, timeout and then block other requests
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

class MyHandler(BaseHTTPRequestHandler):

    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def _html(self, message):
        content = f"<html><body><h2>{message}</h2></body></html>"
        return content.encode("utf8")  # NOTE: must return a bytes object!
    
    def do_GET(self):
        global action
        options = 'status, start, standby, pause, continue, snapshot, restart, terminate'
        qs = {}
        path = self.path
        if ('favicon.ico' in path):
            return
                       
        query_components = parse_qs(urlparse(self.path).query)
        self._set_headers()
            
        command = ''
        if(query_components.get('command')):
            command = query_components['command'][0]
            self._set_headers()
            
            logger.info('!!!!! http '+command+' request !!!!!')
                     
            if (command == 'status'):
                self.wfile.write(self._html('Status of printer on '+duet+'<br><h3>Printer State: '+printerState+'<br>DuetLapse3 State: '+action+'<br>Images Captured: '+str(frame1)+'<br>Current Layer: '+str(zo1)+'</h3>'))              
            
            elif (command == 'start'):
                if (action == 'stopped'):
                    action = command
                    self.wfile.write(self._html('Starting DuetLapse3.<br><h3>Waiting for next command</h3>'))              
                else:
                    self.wfile.write(self._html('Start request Ignored<br><h3>DuetLapse3 is already running</h3>'))
            
            elif (command == 'standby'):
                if (action != 'wait'):
                    action = command
                    self.wfile.write(self._html('Putting DuetLapse3 in standby mode<br><h3>Will NOT create a video and will wait for start command<br>All captured images will be deleted</h3>'))              
                else:
                    self.wfile.write(self._html('Standby request Ignored<br><h3>DuetLapse3 is already waiting</h3>'))
            
            elif (command == 'pause'):
                if (action != 'wait'):
                    action = command
                    self.wfile.write(self._html('Pausing DuetLapse3.<br><h3>Waiting for next command</h3>'))              
                else:
                    self.wfile.write(self._html('Pause request Ignored<br><h3>DuetLapse3 is already paused</h3>'))
                    
            elif (command == 'continue'):
                if (action == 'wait'):  #only makes sense to continue on pause
                    action = command
                    self.wfile.write(self._html('Continuing DuetLapse3.'))
                else:
                    self.wfile.write(self._html('Continue request ignored<br><h3>DuetLapse3 is NOT paused</h3>'))

            elif (command == 'snapshot'):
                if (action == 'run' or action == 'wait'):
                    action = command
                    self.wfile.write(self._html('Creating an interim Video<br><h3>Will first create a video with the current images then continue</h3>'))
                else:
                    self.wfile.write(self._html('Snapshot request Ignored<br><h3>DuetLapse3 is NOT in running or paused state</h3>'))                    
                                      
            elif (command == 'restart'):
                if (action == 'run' or action == 'wait'):
                    action = command
                    self.wfile.write(self._html('Restarting DuetLapse3<br><h3>Will first create a video with the current images then restart</h3>'))
                else:
                    self.wfile.write(self._html('Restart request Ignored<br><h3>DuetLapse3 is NOT in running or paused state</h3>'))

            elif (command == 'terminate'):
                action = command
                self.wfile.write(self._html('Terminating DuetLapse3<br><h3>Will finish last image capture, create a video, then terminate.</h3>'))
                logger.info('!!!!! Stopped by http Terminate request !!!!!')

            else:
                self.wfile.write(self._html('Illegal value for ?command=<br><h3>Valid options are:   '+options+'</h3>'))
            
            return
        
        self.wfile.write(self._html('Invalid Argument<br><h3>The only valid argument is ?command=<br><h3>Valid options are:   '+options+'</h3>'))       
        return

        def log_request(self, code=None, size=None):
            pass

        def log_message(self, format, *args):
            pass
    
def createHttpListener():
    global listener
    import threading
    listener = HTTPServer((host, port), MyHandler)
    listener.serve_forever()
    sys.exit(0)  #May not be needed since never returns from serve_forever

###########################
# Main begins here
###########################
init()

if (httpListener):
    import threading
    httpthread = threading.Thread(target=createHttpListener, args=())
    httpthread.start()
    logger.info('')
    logger.info('##########################################################')
    logger.info('***** Started http listener *****')
    logger.info('##########################################################')
    logger.info('')
    
if (startnow and not action == 'stopped'):
    logger.info('')
    logger.info('##########################################################')
    logger.info('Will start capturing images immediately')
    logger.info('##########################################################')
    logger.info('')
elif (not startnow and not 'none' in detect):
    logger.info('')
    logger.info('##########################################################')
    if('layer' in detect):
        logger.info('Will start capturing images on first layer change')
    elif('pause' in detect):
        logger.info('Will start capturing images on first pause in print stream')
    logger.info('##########################################################')
    logger.info('')

if (action == 'stopped'):
    logger.info('')
    logger.info('##########################################################')
    logger.info('Will not start until command=start recieved from http listener')
    logger.info('##########################################################')
    logger.info('')

logger.info('')
logger.info('##########################################################')
logger.info('Video will be created when printing ends.')
logger.info('Or, press Ctrl+C one time to stop capture and create video.')
logger.info('##########################################################')
logger.info('')


timePriorPhoto1 = time.time()
timePriorPhoto2 = time.time()

disconnected = 0
logger.info('****** Printer State changed to '+printerState+' *****')
try:
    while(1):

        while('run' in action):  #action can be changed by httpListener or SIGINT or CTL+C
            time.sleep(poll)  # poll every n seconds
            global duetStatus
            duetStatus=getDuetStatus(apiModel)    
            # logical states for printer
            if (duetStatus == 'idle' and (printerState == 'printing' or printerState == 'paused')):
                printerState = 'completed'
                logger.info('****** Printer State changed to '+printerState+' *****')            
            elif (duetStatus == 'processing' and printerState != 'printing'):
                printerState = 'printing'
                logger.info('****** Printer State changed to '+printerState+' *****')
            elif (duetStatus == 'paused' and printerState != 'paused'):
                printerState = 'paused'
                logger.info('****** Printer State changed to '+printerState+' *****')
            elif ((duetStatus == 'pausing' or duetStatus == 'resuming') and printerState != 'pausing'):
                printerState = 'pausing'
                logger.info('****** Printer State changed to '+printerState+' *****')
            elif (startnow and printerState != 'paused'):
                printerState = 'startnow'
                logger.info('****** Printer State changed to '+printerState+' *****')
                startnow = False         #once capture starts startnow has no further meaning
            elif (duetStatus == 'idle' and printerState == 'pausing'):  # We missed the pause state
                printerState = 'paused'
                logger.info('****** Printer State changed to '+printerState+' *****')
            
            if(duetStatus == 'disconnected'):
                disconnected += 1
                logger.info('Printer is disconnected - Trying to reconnect')
                if (disconnected > 10):
                    logger.info('Printer was disconnected - Post Processing')
                    action = 'terminate'  #Save what we can
                    break

            if (printerState == 'printing' or printerState == 'startnow' or (printerState == 'paused' and detect == 'paused')):
                oneInterval('Camera1', camera1, weburl1, camparam1)
                if (camera2 != ''): oneInterval('Camera2', camera2, weburl2, camparam2)
                unPause()  #Nothing should be paused at this point
                disconnected = 0
            elif (printerState == 'completed'):
                logger.info('End of Print Job - Post Processing')
                if (httpListener):
                    action = 'restart'
                else:
                    action = 'terminate'
        #outer loop
        #Check for processing change instructions 
        #from the http listener
        
        if (action == 'start'): #Start
            action = 'run'
            logger.info('++++++ Entering '+action+' state ++++++')
        elif (action == 'stop'):  #the same as a restart but does to waiting
            logger.info('++++++ Entering '+action+' state ++++++')
            cleanupFiles()   #clean up and start again
            setStartValues()
            startnowCheck()
            action = 'stopped'  # Do nothing
            logger.info('****** Printer State changed to '+printerState+' *****')           
        elif (action == 'pause'):
            logger.info('++++++ Entering '+action+' state ++++++')
            action = 'wait'  # Do nothing
        elif (action == 'continue'):
            action = 'run'   #Continue from where we left off
            logger.info('++++++ Entering '+action+' state ++++++')
        elif (action == 'snapshot'):
            logger.info('++++++ Entering '+action+' state ++++++')
            makeVideo()
            action = 'run'         
        elif (action == 'restart'):
            logger.info('++++++ Entering '+action+' state ++++++')
            makeVideo()
            cleanupFiles()   #clean up and start again
            setStartValues()
            startnowCheck()
            logger.info('****** Printer State changed to '+printerState+' *****')
        elif(action == 'terminate'):
            logger.info('++++++ Entering '+action+' state ++++++')
            makeVideo()
            terminate()
            
        time.sleep(5)  # poll every 5 seconds
        
except KeyboardInterrupt:
    logger.info('!!!!!! Stopped by Ctl+C - Post Processing !!!!!!')
    makeVideo()
    terminate()
   
