
Designed and tested on Raspberry Pi but should work on other linux platform. Supports cameras via
- [1] USB
- [2] Pi (ribbon cable)
- [3] Webcam or software delivering streaming video
- [4] Webcam or software delivering still images

Produces a video with H.264 encoding in an MP4 container. 

Capture images based on time, layer change, or pause.  Works with existing pauses in G-Code, or can force pauses at other trigger events. Optionally moves the print head to a specified position before capturing images.

Feedback via issues on Duet forum https://forum.duet3d.com/topic/20932/duetlapse3

## Requirements 

* Python3  V3.7 or greater
* Duet printer must be RRF V3 or later (i.e. support either the  rr_model or /machine calls)
* To use -extratime: ffmpeg version newer than 4.2 (this may need to be compiled if your system has an older version as standard)
  The following instructions may help https://github.com/stuartofmt/DuetLapse3/blob/main/ffmpeg.md
* If not using -extratime ffmpeg version 4.1.6
* Python dependencies that are missing will be called out by the program
* Duet printer must be reachable via network
* Depending on camera type, one or more of the following may be required:
  * fswebcam (for USB cameras)
  * raspistill or libcamera-still (for Pi cam or Ardu cam)
  * wget (for Web cameras)

## Installation
For Linux:<br>
* mkdir DuetLapse  - or other directory of your choice
* cd DuetLapse
* wget https://github.com/stuartofmt/DuetLapse3/raw/main/DuetLapse3.py
* chmod 744 DuetLapse3.py

For windows<br>
Follow the instructions from one of the web sources - for example:<br>
https://docs.python.org/3/using/windows.html 

***Note:** Make sure to edit the path variable(s) so that python3 and /libraries/modules can be found.*
  
## Usage

The python program can be started from the command line or, more usually, from the companion program startDuetLapse3.  Although there are defaults for many of the options - it's unlikely that the program will do exactly what you want with just the defaults.
The program will usually be started just before you starting a printing - but this is not critical.  Depending on options (e.g. dontwait) it will either immediately start creating still images or wait until the printer changes status from "Idle" to "Processing".<br>
At the end of the print job the program combines the still images into a mp4 video to create the time-lapse.<br>
If the program is run in foreground it can be stopped (before the print job completes) using CTRL+C (on linux) or CTRL+Break(on Windows).  If the program is run in background it can be stopped using SIGINT (kill -2 <pid> in linux).
 
An **Integrated http listener** is available for basic control of DuetLapse3 (not the attached printer).<br>
The http listener is activated by specifying a port number using the -port option.<br>
In conjunction with the -host option it provides the following functionality from a browser (or curl or other method of performing a http get).
```
http://<ip-address><port>/?command=<valid command>
```
<pre>
Valid commands are:
status     - returns brief information about the running state of DuetLapse3
----
start      - Starts DuetLapse3 recording if the -standby option was used
             or after a standby command
standby    - Stops (but does not terminate) DuetLapse3 recording
             and discards any images capture.  Waits for a start command.
----
pause      - causes DuetLapse3 to temporarily stop capturing images.
             Note:  This does NOT pause the printer.*
continue   - causes DuetLapse3 to resume capturing images.
----
snapshot   - causes DuetLapse3 to make an interim video and then return to its previous state (start or pause).
restart    - causes DuetLapse3 to stop capturing images, create a video
             and then restart with a new capture set
terminate  - causes DuetLapse3 to stop capturing images, create a video and
             then terminate the program. This is the same as CTRL+C or SIGINT.<br>
             Note: Depending on your system - it may take several minutes
             for the http listener to completely shutdown following a terminate request.
</pre>

***Note:*** *The http listener will stop responding if DuetLapse3 is run from a command console that is then closed.<br>
This will happen even if started in background.  To avoid this - use nohup (linux) or pythonw (Windows)<br>
An alternative if you are on Win10 is to use  Windows Subsystem for Linux (WSL) and run DuetLapse as a linux application inside WSL.<br>
If running in nohup mode CTRL+C cannot be used so, you need to send the terminate command (?command=terminate) from the http listener
The same applies if running in Windows with pythonw*

### Options

Options can be viewed with
```
python3 DuetLapse3.py -h
```
The response will give the version number at the top.

The options are described here.  Each option is preceded by a dash -. Some options have parameters described in the square brackets. The square brackets are NOT used in entering the options. If an option is not specified the default used.

#### -duet [ip address]

**Mandatory - This is a required option.**  The parameter is the network location of your duet printer.  It can be given as a hostname or an explicit ip address.
As a simple test - a browser should be able to access the Duet Web Controller using http://<ip address> from the same computer that is running DuetLapse3.py.
  
**example**
```
-duet 192.168.1.10     #Connect to the printer at 192.168.86.10
-duet localhost        #Connect to the printer at localhost
```

#### -basedir [full path name]
If omitted - the default dir is the location of DuetLapse3.py.  This is the logical root for output files See Directory Structure (below).

**example**
```
-basedir /home/pi/mydir  #output files start at /home/pi/mydir
```

#### -instances [single||oneip||many]
If omitted - the default is single. Used to control the number of instances of DuetLapse3.py that can run simultaneously.
In most cases the default will be suitable.

**example**
```
-instances single   #There can only be one instance of DuetLapse3.py running
-instance oneip     #For each printer (set by -duet), there can only be one
                    #instance of DuetLapse3.py running
-instances many     #No restriction on the number of instances
```

#### -logtype [console||file||both]  -- DEPRECATED (see -nolog))
If omitted - the default is both

**example**
```
-logtype console   #Only send messages to the console
-logtype file      #Only send messages to the logfile.
                   #See Directory Structure for logfile name and location
-logtype many      #Send messages to both the console and file
```

#### -nolog
If omitted - the default is False
Logging will always use the console.  A logfile will be created unless -nolog is used.

**example**
```
-nolog console   #Only send messages to the console
```

#### -verbose
If omitted the default is False
Causes the output of system calls and more detailed messages to be logged.
Should usually only be used for debugging.

**example**
```
-verbose       #Causes addidtional logging information 

```

#### -poll [seconds]
If omitted the default is 5 seconds.  This is the time between checking to see if am image needs to be captured.
If -seconds (see below) is less than -poll then poll is reduced to the value of -seconds.

#### -host [ip address]
If omitted the default is 0.0.0.0<br>
Generally this can be left out (default) as it will allow connection to the http listener from localhost:<port> (locally) or from another machine with network access using <actual-ip-address-of-server-running-DuetLapse3><port>.

**example**
```
-host 192.168.86.10      #Causes internal http listener (if active) to listen
                         #at ip address 192.168.86.10
```

#### -port [port number]
If omitted the default is 0 AND the internal http listener is NOT started.<br>
Typical choices for port numbers will br greater than 8000.
The selected port number MUST be different to one already in use.
**The http listener is only start if a port number is specified**

**example**
```
-port 8082      #Causes internal http listener to start and listen on port 8082
```

#### -standby
If omitted the default is False<br>
If the http listener is active (i.e. -port is specified) - this option will cause DuetLapse3 to wait for a start command from the http listener before capturing images.<br>
It is useful for having DuetLapse running but not actually doing anything until commanded to do so.

**example**
```
-standby #Causes internal http listener to start and listen on port 8082
         #Will not start capturing
```

#### -dontwait
If omitted - the default is False

**example**
```
-dontwait    #Images will be captured immediately (without first waiting for a
             # layer change) if -seconds > 0.
             #Otherise images will first start being captured on the first
             #layer change or pause (see -detect).
             # The -pause option is not used untill the first layer is printed
```

***Note:** If -pause yes is used with dontwait, the program will capture images (based on -seconds) before printing starts.<br>
Pauses and any -movehead repositions will NOT happen until after the first layer is complete. <br>* 

#### -seconds [seconds]
If omitted the default is 0 seconds (i.e. ignored). Can be any positive number.

**example**
```
-seconds 10  #Images will be captures at least every 10 seconds
```

***Note:** If used with -pause be careful not to set -seconds too low.  Doing this can lead to a lot of non-printing head repositioning which can result in poor print quality.* 

#### -detect [layer||pause||none]
If omitted the default is layer.

**example**
```
-detect layer     #Will capture an image on each layer change
-detect pause     #Will capture an image if the printer is paused by the print gcode
                  #**M226**
                  #A manual pause is treated the same as one imbeded in the print gcode
-detect none      #Will not capture an image other than as secified by -seconds
```

***Notes on the use of -detect pause**<br>
When a pause is detected in the print gcode (supplied by an M226) an image will be captured and a resume print command issued.
The head position during pauses is controlled by the pause.g macro on the duet,
and "-movehead Xposition Yposition".<br>
See the notes on pause.g in the section on -pause<br>*

**-detect pause CANNOT be used at the same time as -pause yes**


#### -pause [yes||no]
If omitted the default is no. If - pause yes the program will pause the printer when an image is captured.
The print job can be manually paused / resumed in the normal manner.

**example**
```
-pause yes      #Pause the printer each time an image is captured.
```

***Notes on the use of -pause yes<br>**
DuetLapse3 will pause the printer each time an image is to be captured.
The head position during pauses is controlled by the pause.g macro on the duet,
and by specifying "-movehead Xposition Yposition". If both are specified pause.g will run first then -movehead will reposition the heads. **You may want to edit pause.g to remove the head park gcode (see example below).**<br>
If you use -detect layer as well, be careful with prints that have areas with quick layer changes as frequent pauses can cause poor print quality.<br>*

Example pause.g
```
; pause.g
; called when a print from SD card is paused
;

if state.currentTool != -1
  M83				; relative extruder moves
  G1 E-4 F2500		; retract 4mm
G91					; relative moves
G1 Z5 F5000			; raise nozzle 5mm
G90					; absolute moves
G1 F10000           ; just set the speed 
;G1 X0 Y0            ; go to X=0 Y=0 or comment out if using -movehead
```

**-pause CANNOT be used in conjunction with -detect pause (see above)**

#### -movehead [Xposition,Yposition]
if omitted the head is not moved - equivalent to -movehead 0,0.  Specifies a position to move the head to before capturing an image.
Valid positions must be greater than 0.0 and less than the maximum allowed by your printer

**example**
```
-movehead 10,5    #Will move the head to X=10, Y=5 before capturing an image
```

***Note:** The pause.g macro will run first then -movehead will reposition the heads. 
After the image is captured resume.g is run<br>*
**If you use -movehead, it is better if pause.g does not reposition the heads as well (see comments above).**<br>

#### -rest [seconds]
If omitted the default is 1 second. Can be 0 or any positive number.
Delays image capture after a pause to allow for any latency (e.g. web camera) where the feed is delayed relative to the actual position of the print head. if -rest is too short, the print head may not appear to be stationary in the video.

**example**
```
-rest 3  #Images will be captures 3 seconds after a pause
```

#### -extratime [second]
If omitted the default is 0.  When creating the video - extends the duration of the last frame by the specified number of seconds.<br>
If this option is not available in your version of ffmpeg it will be ignored.  Version 4.2+ of ffmpeg should support this feature, but it is not guaranteed.

**example**
```
-extratime 10     #Makes the last frame captured 10 seconds long
```

***Notes on the use of - extratime**<br>
Applies to the last frame captured.  So if, for example, your print job moves the Z axis at the end of the print.  The last frame would occur when the Z axis stops moving - not when the last layer is printed.*

#### -camera1 [usb||pi||web||stream||other]
If omitted the default is usb. Determines how images are captured.
**-camera pi is deprecated (see notes below)**

**example**
```
-camera1 usb      #Uses the camera associated with fswebcam
-camera1 pi       #Uses the camera associated with the rasberry pi
                  #camera's standard installation
-camera1 web      #Uses wget to capture images from a camera that
                  #provides still jpeg
-camera1 stream   #Uses ffmpeg to capture images from a video feed
-camera1 other    #Can only be used in conjunction with -camparam1
                  #(see below)
```

***Note:** If you are using a Raspberry Pi camera there can be issues using -camera pi. The defaults for the Pi camera can lead to problems when creating the video.  This is because there may not be enough RAM (depends on your Pi model).<br>*

*The recommended approach is to use videostream with the -size 2 option https://github.com/stuartofmt/videostream <br>
Then use DuetLapse3 options -camera other together with -camparam and -weburl.  For example:<br>*

```
-weburl1 http://192.168.86.230:8081/stream -camera1 other -camparam1="'ffmpeg' +ffmpegquiet + ' -y -i ' +weburl+ ' -vframes 1 ' +fn+debug"
```

If you just want to use the pi camera directly, then the following is recommended:<br>

For Raspberry pi earlier than the Bullseye release:

```
-camera1 other  -camparam1 "'raspistill -t 1 -w 1280 -h 720 -ex sports -mm matrix -n -o ' + fn + debug"
```

For Raspberry pi with Bullseye release (and later):
If NOT using -verbose
```
-camera1 other  -camparam1 "'libcamera-still -t 1 --nopreview --width 1640 --height 1232 -o ' + fn + debug"
```
If using -verbose
```
-camera1 other  -camparam1 "'libcamera-still -t 1 --nopreview --width 1640 --height 1232 -o ' + fn + debug + ' 2>/dev/null'"
```
This is because of the way libcamera is coded.

#### -weburl1 [url]
If omitted it has no value. url specifies the location to capture images for camera1. Only used for -camera1 of types web, stream, or other

**example**
```
-weburl http://192.168.86.10/stream  #capture images from this location
```

#### -camera2 [usb||pi||web||stream||other]
If omitted has no default (unlike camera1). Has the same parameters as -camera1

#### -webur2 [url]
Has the same parameters as -weburl2

#### -camparam1="[command]"
If omitted has no default. Used in conjunction with -camera1 to define how the images will be captured.<br>

***Note the use of the = and quoting of the command string.***
*Single quotes should be used in the command string when needed.<br>
There are 3 internal variables that can be used weburl (which has the value of weburl1), fn (which is the file for the captured images) , debug (which controls verbose logging)*

**example**
```
-camparam1="'ffmpeg -y -i '+weburl+ ' -vframes 1 ' +fn+debug"
```

This example is the same as if -camera1 stream was used. The value of weburl1 would be substituted for weburl and the output goes to the file specification fn. The results are verbose of not is determined by the internal variable debug.  In general both fn and debug should be used.  The use of weburl would depend on the capture method being used.

***Notes on the use of -camparam1**<br>
The following are the standard commands for reference.*

-camera usb<br>
'fswebcam --quiet --no-banner '+fn+debug

-camera pi<br>
'raspistill -t 1 -ex sports -mm matrix -n -o '+fn+debug

-camera stream<br>
'ffmpeg -y -i '+weburl+ ' -vframes 1 ' +fn+debug

-camera web<br>
'wget --auth-no-challenge -nv -O '+fn+' "'+weburl+'" '+debug

#### -vidparam1="[command]"
If omitted has no default. Defines an alternate video capture command.  If provided - is used instead of the standard capture command.

***Note the use of = and quoting of the command string.**  Single quotes should be used in the command string when needed.<br>
There are 3 internal variables that can be used basedir (has the same meaning as -basedir), cameraname (is the literal "Camera1"), extratime (is the value of -extratime), fn (which is the output file for -camera1) , debug (which controls verbose logging)*

**example**

```
-vidparam1="'ffmpeg -r 1 -i '+basedir+'/'+duetname+'/tmp/'+cameraname+'-%08d.jpeg -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn+debug"
```

This example is the same as the standard video creation.

#### -camparam2 and -vidparam2
Have the same parameters as -camparam1 and -vidparam1.  Variable references are for Camera2

#### -keeplogs
If omitted the default is False
If **-keeplogs** is NOT used.  The FIRST instance of DuetLapse3 (with no other instances running) will delete the old logfiles.  If -keeplogs is used then the logfiles will not be deleted.  This means that if you typically use -keeplogs you can affect a cleanup by running a single instance of DuetLapse3 without -keeplogs.

#### -deletepics
If omitted the default is False
if **-deletepics** is used.  When DuetLapse3 terminates - basedir/computername/duetip/processid directory will be deleted (i.e. the images will be deleted).

#### -novideo
If omitted the default is False
If **-novideo** is used. When DuetLapse3 terminates - no video will be created.  If BOTH **-novideo** and **-deletepics** are specified- this means that if you want to use the images you need to have done so before terminating that instance of DuetLapse3. For example using the snapshot feature provided by the html listener.

#### -keepfile
If omitted the default is False
If **-keepfiles** is used. When DuetLapse3 starts or terminates - no files are deleted.  If BOTH **-keepfiles** and **-deletepics** are specified deletepics is ignored.

#### -maxffmpeg
If omitted the default is 2
When DuetLapse3 tries to create a video it will fail if ffmpeg runs out of system resources (e.g. CPU / Memory).
This option limits the number of concurrent ffmpeg instances.

**example**
```
-maxffmpeg 5       #Allows up to 5 instances off ffmpeg to run concurrently

```

#### -fps
If omitted the default is 10
Sets the default frames-per-second when the snapshot button is used.

**example**
```
-fps 20       #Causes videos to be created at 20 frames-per-second

```

#### -hidebuttons
If omitted the default is False
Hides menu buttons that are currently invalid - otherwise, invalid buttons are greyed out

**example**
```
-hidebuttons       #Hides menu buttons that are currently invalid

```


### Directory Structure
The directory structure is (with repeating units [] as appropriate to your use-case)
```
basedir/
   |
   computername/
   |   |
   |   duetip/
   |      |
   |      |processid_jobname/         #_jobname if available
   |      |
   |      |[/processid_jobname}
   |
   |
   [computername 
     #repeat of structure above
   ]         
```

For many (most ?)  users it will simply look like this

```
basedir/
   |
   computername/
      |
      duetip/
         |
         |processid_jobname/         #_jobname if available
```
The interpretation is:
Starting from the basedir
- [1] For each computer that DuetLapse3 is running on there will be a separate directory(computername).  Technically the computername will be the fully qualified domain name (FQDN).  In any case - each computer needs to (and in any case should) have a unique FQDN
- [2] Underneath the computername directory  there will be a separate directory for each Duet that computer is connected to (duetip).   All videos for this computer and duet combination go into this directory as well as the respective  logfiles.
- [3] Underneath the duetip directory will be temporary directories (processid_jobname).If the printjob has not started at that time - there will be no _jobname portion.  This handles the situation where  multiple instances of DuetLapse3 are running on the same computer against the same Duet. This directory is created when the first image is captured.

***Note:** that the Videos and logfiles are prefixed by the processid.
To provide cross-platform compatibility, colons are replaced by raised colons (more-or-less look the same).  Spaces in filenames are replaced by underscrore.*  
 
## Usage Examples

Many options can be combined.  For example, the program can trigger on both "seconds" and "detect layer". It will inform you if you select conflicting options.
***Note:** that these examples are from the command line.  If running from a program (or to avoid issues closing the console) adding a **&** at the end (in linux) will run the program in background.*

Example: Capture an image every 20 seconds, do not respond to layer changes or pauses, use a webcam at the specified url:
```
python3 ./DuetLapse3.py  -duet 192.168.7.101 -seconds 20 -detect none -camera1 web -weburl1 http://userid:password@192.168.7.140/cgi-bin/currentpic.cgi

```
Example: Start the http listener on 192.198.86.10  using port 8082, capture an image on layer changes (default), force pauses (at layer change) and move head to X10 Y10 before creating an image, use the default USB camera.
```
python3 ./DuetLapse3.py -duet 192.168.7.101 -host 192.168.86.10 -port 8082 -pause yes -movehead 10 10

```
Example: Two camera example. Start capturing immediately at a minumum of one image every 3 second. Camera2 uses camparam and vidparam2 overrides. Run in background.
```
/usr/bin/python3 ./DuetLapse3.py -duet 192.168.86.235 -basedir /home/pi/Lapse -instances oneip -dontwait -seconds 3 -camera1 stream -weburl1 http://192.168.86.230:8081/stream.mjpg  -camera2 other -weburl2 http://192.168.86.230:8081/stream.mjpg -camparam2="'ffmpeg -y -i '+weburl+ ' -vframes 1 ' +fn+debug" -vidparam2="'ffmpeg -r 1 -i '+basedir+'/'+duetname+'/tmp/'+cameraname+'-%08d.jpeg -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn+debug" -extratime 0 &
```
Major Revisions in progress
