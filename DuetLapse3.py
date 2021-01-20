#!/usr/bin/env python3
# Python Script to take Time Lapse photographs during a print on 
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
# Developed on Raspberry Pi with Debian Buster. SHOULD work on most other linux didtributions. 
# For USB or Pi camera, The Camera MUST be physically attached to the computer.  
# For Webcam, the camera must be network reachable and via a defined URL for a still image.
# For Stream   the camera must be network reachable and via a defined URL
# The Duet printer must be RepRap firmware V3 and must be network reachable. 
# 
#

import subprocess
import sys
import argparse
import time
import requests
import json
import os

# Globals.
zo1 = -1                         # Starting layer for Camera1
zo2 = -1                         # Starting layer for Camera2
frame1 = 0                       # Frame counter Camera1 file names
frame2 = 0                       # Frame counter Camera2 file names
printerState = 'waiting'         #State machine for print idle before print, printing, idle after print. 
timePriorPhoto1 = 0              # Camera1 - Time of last interval based photo, in time.time() format.
timePriorPhoto2 = 0              # Camera2 - Time of last interval based photo, in time.time() format.
alreadyPaused  = False           # If printer is paused, have we taken our actions yet? 

###########################
# Methods begin here
###########################


def init():
    # parse command line arguments
    parser = argparse.ArgumentParser(description='Create time lapse video for Duet3D based printer. V3.0.4', allow_abbrev=False)
    #Environment
    parser.add_argument('-duet',type=str,nargs=1,default=['localhost'],help='Name of duet or ip address. Default = localhost')
    parser.add_argument('-poll',type=float,nargs=1,default=[5])
    parser.add_argument('-basedir',type=str,nargs=1,default=[''],help='default = This script  directory')
    parser.add_argument('-instances',type=str,nargs=1,choices=['single','oneip','many'],default=['single'],help='Default = single')
    parser.add_argument('-logtype',type=str,nargs=1,choices=['console','file','both'],default=['both'],help='Default = both')
    parser.add_argument('-verbose',action='store_true',help='Output stdout and stderr from system calls')
    #Execution
    parser.add_argument('-dontwait',action='store_true',help='Capture images immediately.')
    parser.add_argument('-seconds',type=float,nargs=1,default=[0])
    parser.add_argument('-detect',type=str,nargs=1,choices= ['layer', 'pause', 'none'],default=['layer'],help='Trigger for capturing images. Default = layer')
    parser.add_argument('-pause',type=str,nargs=1,choices= ['yes', 'no'],default=['no'],help='Park head before image capture.  Default = no')
    parser.add_argument('-movehead',type=float,nargs=2,default=[0.0,0.0], help='Where to park head on pause, Default = 0,0')   
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
    global duet, basedir, poll, instances, logtype, verbose
    global duetname, debug  #Derived    
    duet     = args['duet'][0]
    basedir  = args['basedir'] [0]
    poll  = args['poll'][0]
    instances = args['instances'] [0]
    logtype   = args['logtype'] [0]    
    verbose = args['verbose']

    #Execution
    global dontwait, seconds, detect, pause, movehead        
    dontwait = args['dontwait']
    seconds  = args['seconds'][0]
    detect   = args['detect'][0]
    pause    = args['pause'][0]
    movehead = args['movehead']  

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
    
    #derived parameters
    #duetname used for filenames and directories
    duetname = duet.replace('.' , '-')
    #Set output from system calls
    if verbose :
        debug = ''
    else:
        debug = ' > /dev/null 2>&1'
    #Polling interval should be at least = seconds so as not to miss interval
    if (poll > seconds and seconds != 0): poll = seconds    #Need to poll at least as often as seconds
    if ('none' in detect and seconds != 0): poll = seconds  #No point in polling more often
    
    # set basedir scripts directory
    if (basedir == ''): basedir = os.path.dirname(os.path.realpath(__file__))
    
    #Check to see if this instance is allowed to run  
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
           sys.exit(1)
           
# Make and clean up directorys.
    #Make sure there is a directory for the resulting video
    subprocess.call('mkdir '+basedir+'/'+duetname+debug, shell=True)
    #Clean up the tmp directory
    subprocess.call('rm -rf '+basedir+'/'+duetname+'/tmp'+debug, shell=True)
    subprocess.call('mkdir '+basedir+'/'+duetname+'/tmp'+debug, shell=True)

    
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
  
    # Inform regarding valid and invalid combinations
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
        
    if ((seconds > 0) and (not 'none' in detect)):
        logger.info('************************************************************************************')
        logger.info('Warning: -seconds '+str(seconds)+' and -detect '+detect+' will trigger on both.')
        logger.info('Specify "-detect none" with "-seconds > 0" to trigger on seconds alone.')
        logger.info('************************************************************************************')
        
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

    def checkDependencies(camera):        
        # Check for required libraries
        if ('usb' in camera):
            if (20 > len(subprocess.check_output('whereis fswebcam', shell=True))):
                logger.info("Module 'fswebcam' is required. ")
                logger.info("Obtain via 'sudo apt install fswebcam'")
                sys.exit(2)

        if ('pi' in camera):
            if (20 > len(subprocess.check_output('whereis raspistill', shell=True))):
                logger.info("Module 'raspistill' is required. ")
                logger.info("Obtain via 'sudo apt install raspistill'")
                sys.exit(2)

        if ('stream' in camera):
            if (20 > len(subprocess.check_output('whereis ffmpeg', shell=True))):
                logger.info("Module 'ffmpeg' is required. ")
                logger.info("Obtain via 'sudo apt install ffmpeg'")
                sys.exit(2)

        if ('web' in camera):
            if (20 > len(subprocess.check_output('whereis wget', shell=True))):
                logger.info("Module 'wget' is required. ")
                logger.info("Obtain via 'sudo apt install wget'")
                sys.exit(2)

        if (20 > len(subprocess.check_output('whereis ffmpeg', shell=True))):
            logger.info("Module 'ffmpeg' is required. ")
            logger.info("Obtain via 'sudo apt install ffmpeg'")
            sys.exit(2)

    checkDependencies(camera1)
    if (camera2 != ''): checkDependencies(camera2)

    
    # Get connected to the printer.
    
    global apiModel

# Get connected to the printer.
    logger.info('Determine machine type and API Version')
    apiModel, printerVersion = getDuetVersion()
    if (apiModel == 'none'):
        logger.info('The printer at '+duet+' did not respond')
        logger.info('Check the ip address or logical printer name is correct')
        logger.info('Duet software must support rr_model or /machine/status')
        sys.exit(2)
    
    logger.info('API access is with : '+apiModel+' model')
    
    majorVersion = int(printerVersion[0])

    if (majorVersion >= 3):
        logger.info('Connected to printer at '+duet+' using version '+printerVersion)
    else:
        logger.info('The printer at '+duet+' needs to be at version 3 or above')
        logger.info('The version on this printer is '+printerVersion)
        sys.exit(2)
    

    # Tell user options in use. 
    logger.info('')
    logger.info("################### Options in force for this run #####################")
    logger.info("# Environment:      {0:50s}".format(''))
    logger.info("# printer         = {0:50s}".format(duet))
    logger.info("# basedir         = {0:50s}".format(basedir))
    logger.info("# poll            = {0:50s}".format(str(poll))) 
    logger.info("# logtype         = {0:50s}".format(str(logtype))) 
    logger.info("# verbose         = {0:50s}".format(str(verbose)))
    logger.info("# Execution:        {0:50s}".format(''))    
    logger.info("# dontwait    =     {0:50s}".format(str(dontwait)))
    logger.info("# seconds     =     {0:50s}".format(str(seconds)))   
    logger.info("# detect      =     {0:50s}".format(detect))
    logger.info("# pause       =     {0:50s}".format(pause))
    if (movehead[0] != 0 and movehead[1] != 0):
        logger.info("# movehead    = {0:6.2f} {1:6.2f} ".format(movehead[0],movehead[1]))
    logger.info("# Camera 1 Settings:{0:50s}".format(''))
    logger.info("# camera1     =     {0:50s}".format(camera1))
    logger.info("# weburl1     =     {0:50s}".format(weburl1))
    if (camparam1 != ''):
        logger.info("# Camera1 Override: {0:50s}".format(''))    
        logger.info("# camparam1       = {0:50s}".format(camparam1))
    if (camera2 != ''):
        logger.info("# Camera2 Settings: {0:50s}".format(''))
        logger.info("# camera2     =     {0:50s}".format(camera2))
        logger.info("# weburl2     =     {0:50s}".format(weburl2))
    if (camparam2 != ''):
        logger.info("# Camera2 Override: {0:50s}".format(''))
        logger.info("# camparam2    =    {0:50s}".format(camparam2))   
    logger.info("# Video             {0:50s}".format(''))
    logger.info("# extratime   =     {0:50s}".format(extratime))
    if (vidparam1 != ''):
        logger.info("# Video1 Override:  {0:50s}".format(''))
        logger.info("# vidparam1    =    {0:50s}".format(vidparam1))
    if (vidparam2 != ''):
        logger.info("# Video2 Override:  {0:50s}".format(''))
        logger.info("# vidparam2    =    {0:50s}".format(vidparam2))
    logger.info("###################################################################")
    logger.info('')

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
    
    if (cameraname =='Camera1'):
        frame1 += 1
        frame = frame1
    else:
        frame2 += 1
        frame = frame2
        
    s=str(frame).zfill(8)
    fn = basedir+'/'+duetname+'/tmp/'+cameraname+'-'+s+'.jpeg'

    if ('usb' in camera): 
        cmd = 'fswebcam --quiet --no-banner '+fn+debug
            
    if ('pi' in camera): 
        cmd = 'raspistill -t 1 -ex sports -mm matrix -n -o '+fn+debug
            
    if ('stream' in camera):
        cmd = 'ffmpeg -y -i '+weburl+ ' -vframes 1 ' +fn+debug
        
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
    fn = basedir+'/'+duetname+'/'+cameraname+'-'+time.strftime('%a-%H:%M',time.localtime())+'.mp4'

    if (vidparam == ''):
        cmd  = 'ffmpeg -r 10 -i '+basedir+'/'+duetname+'/tmp/'+cameraname+'-%08d.jpeg -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn+debug
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
        logger.info('Testing: '+model+' at address '+duet)
        logger.info(URL)
        logger.info('')
        r = requests.get(URL, timeout=5)
        j = json.loads(r.text)
        version = j['result'][0]['firmwareVersion']
        return 'rr_model', version;
    except:
        try:
            model='/machine/system'
            URL=('http://'+duet+'/machine/status')              
            logger.info('Testing: '+model+' at address '+duet)
            logger.info(URL)
            logger.info('')
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
        r = requests.get(URL, timeout=5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                status = j['result']
                return status           
            except:
                pass
    else:
        URL=('http://'+duet+'/machine/status/')
        r = requests.get(URL, timeout=5)
        if(r.ok):
            try:
                j = json.loads(r.text)
                status = j['state']['status']
                return status
            except:
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


###########################
# Main begins here
###########################
init()

if (dontwait):
    logger.info('Not Waiting for print to start on printer '+duet)
    logger.info('Will start taking pictured immediately')
else:
    logger.info('Waiting for print to start on printer '+duet)

logger.info('Video will be created when printing ends.')
logger.info('Or, press Ctrl+C one time to stop capture and create video.')
logger.info('')


timePriorPhoto1 = time.time()
timePriorPhoto2 = time.time()

#Allows process running in background or foreground to be gracefully
# shutdown with SIGINT (kill -2 <pid>
import signal

def quit_gracefully(*args):
    logger.info('Stopped by SIGINT - Post Processing')
    finish()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, quit_gracefully)

logger.info('****** Printer State changed to '+printerState+' *****')

def finish():
    unPause()   #clear any final pause
    postProcess('Camera1', camera1, vidparam1)
    if (camera2 != ''): postProcess('Camera2', camera2, vidparam2)
    sys.exit(0)

disconnected = 0
try: 
    while(1):
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
        elif (dontwait and printerState != 'paused'):
            printerState = 'dontwait'
            logger.info('****** Printer State changed to '+printerState+' *****')
            dontwait = False         #once capture starts dontwait has no further meaning
        
        if(duetStatus == 'disconnected'):
            disconnected += 1
            if (disconnected > 10):
                logger.info('Printer was disconnected - Post Processing')
                finish()

        if (printerState == 'printing' or printerState == 'dontwait' or printerState == 'paused'):
            oneInterval('Camera1', camera1, weburl1, camparam1)
            if (camera2 != ''): oneInterval('Camera2', camera2, weburl2, camparam2)
            unPause()  #Nothing should be paused at this point
            disconnected = 0
        elif (printerState == 'completed'):
            logger.info('End of Print Job - Post Processing')
            finish()
            
except KeyboardInterrupt:
    logger.info('Stopped by Ctl+C - Post Processing')
    finish()
   
