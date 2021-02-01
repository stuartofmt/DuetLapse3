# DuetLapse3
 
## This is a modified version of the original DuetLapse created by Danal Estes
https://github.com/DanalEstes/DuetLapse
## The core functionality is his work.

The modifications include:

###Version 3.0.0###
- [1]  Removal of dependency on DuetWebAPI.py (by Danal Estes).  DuetLapse3.py is a standalone Python3 script.
- [2]  Added support for 2 cameras
- [3]  Reorganized Directory Structure to allow logical separation of files (by printer)
- [4]  Added configurable base directory 
- [5]  Added logfile support
- [6]  Added verbose option
- [7]  Added control over multiple instances
- [8]  Added ability to gracefully terminate when executing in background
- [9]  Added ability to extend the video duration of the last image
- [10] Generalized capture with Camera type "other" and arbitrary capture commands
- [11] Generalized video creation with optional commands

###Version 3.0.3###
- [1]  Added support for SBC BUT cannot support -pause yes or -detect pause.  Will be added soon.

###Version 3.0.4###
- [1]  All functionality supported for SBC
- [2]  More robust error handling
- [3]  Improvements to pause logic and confirmation of printer head position during pause image capture.

###Version 3.1.0###
- [1]  Added support for Windows
- [2]  Added automatic detection of operating system (Linux or Windows)
- [3]  Added integrated http listener for basic browser based control
- [4]  Changed file naming convention to make filenames unique if multiple instances of DuetLapse3 are running.

###Version 3.1.1###
- [1]  if -extratime not specified (default 0) will use ffmpeg syntax compatible with version < 4.2 (4.1.6 tested)

## General Description
Provides the ability to generate time lapse videos from for Duet based 3D printers.

Designed and tested on Raspberry Pi but should work on other linux platform. Supports cameras via
- [1] USB,
- [2] Pi (ribbon cable)
- [3] Webcam delivering streaming video
- [4] Webcam delivering still images

Produces a video with H.264 encoding in an MP4 container. 

Captures images based on time, layer change, or pause.  Works with existing pauses in G-Code, or can force pauses at other trigger events. Optionally moves the print head to a specified position before capturing images.

Feedback via issues on Duet forum https://forum.duet3d.com/topic/20932/duetlapse3

## Requirements 

* Python3
* Duet printer must be RRF V3 or later (i.e. support either the  rr_model or /machine calls)
* To use -extratime: ffmpeg version newer than 4.2 (this may need to be compiled if your system has an older version as standard)
  The following instructions may help https://github.com/stuartofmt/DuetLapse3/blob/main/ffmpeg.md
* If not using -extratime ffmpeg version 4.1.6
* Python dependencies that are missing will be called out by the script
* Duet printer must be reachable via network
* Depending on camera type, one or more of the following may be required:
  * fswebcam (for USB cameras)
  * raspistill (for Pi cam or Ardu cam)
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

Take note of editing the path variable(s) so that python3 and it's /libraries/modules can be found during execution.
  
## Usage

The python script can be started from the command line or, more usually, from a bash or similar script.  Although there are defaults for many of the options - it's unlikely that the script will do exactly what you want with just the defaults.
The script will usually be started just before you starting a printing - but this is not critical.  Depending on options (e.g. dontwait) it will either immediately start creating still images or wait until the printer changes status from "Idle" to "Processing".<br>
At the end of the print job the script combines the still images into a mp4 video to create the time lapse.<br>
If the script is run in foreground it can be stopped (before the print job completes) using CTl+C.  If the script is run in background it can be stopped using SIGINT (kill -2 <pid> in linux).  The example bash script here https://github.com/stuartofmt/DuetLapse3/blob/main/timelapse  gives examples for starting and stopping the program on a Linux system.

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
start      - Starts DuetLapse3 recording if the -standby option was used or after a standby command
standby    - Stops (but does not terminate) DuetLapse3 recording and discards any images capture.  Waits for a start command.
----
pause      - causes DuetLapse3 to temporarily stop capturing images
continue   - causes DuetLapse3 to resume capturing images after a pause
----
snapshot   - causes DuetLapse3 to make an interim video and then continue
restart    - causes DuetLapse3 to stop capturing images, create a video and then restart with a new capture set
terminate  - causes DuetLapse3 to stop capturing images, create a video and then terminate the program. This is the same as CTRL+C or SIGINT.<br>
             Note that depending on your system - it may take several minutes for the http listener to completely shutdown following a terminate request.
</pre>

**Note that the http listener will stop responding if DuetLapse3 is run from a command console that is then closed.  This will happen even if started in background.  To avoid this - use nohup (linux).<br>
Windows does not have an (easy) equivalent to nohup so you would need to leave the command console open.  An alternative if you are on Win10 is to use  Windows Subsystem for Linux (WSL) and run DuetLapse as a linux application inside WSL.<br>
If running in nohup mode CTRL+C cannot be used so you need to send the terminate command (?command=terminate) from the http listener**

### Options

Options can be viewed with
```
python3 DuetLapse3.py -h
```
The response will give the version number at the top.

The options are described here.  Each option is preceded by a dash -. Some options have parameters described in the square brackets (the square brackets are NOT used in entering the options. If an option is not specified the default used.

#### -duet [ip address]

**Mandatory - This is a required option.**  The parameter is the network location of your duet printer.  It can be given as a hostname or an explicit ip address.
As a simple test - a browser should be able to access the Duet Web Controller using http://<ip address> from the same computer that is running DuetLapse3.py.
<pre>  
**example**

-duet 192.168.1.10     #Connect to the printer at 192.168.86.10<br>
-duet localhost        #Connect to the printer at localhost<br>
</pre>

#### -basedir [full path name]
If omitted - the default dir is the location of DuetLapse3.py.  This is the logical root for output files See Directory Structure (below).
If supplied, do NOT put in a trailing slash /
<pre>
**example**

-basedir /home/pi/mydir  #output files start at /home/pi/mydir
</pre>

#### -instances [single||oneip||many]
If omitted - the default is single. Used to control the number of instances of DuetLapse3.py that can run simultaneously.
In most cases the default will be suitable.
<pre>
**example**

-instances single   #There can only be one instance of DuetLapse3.py running<br>
-instance oneip     #For each printer (set by -duet), there can only be one instance of DuetLapse3.py running<br>
-instances many     #No restriction on the number of instances<br>
</pre>

#### -logtype [console||file||both]
If omitted - the default is both
<pre>
**example**

-logtype console   #Only send messages to the console<br>
-logtype file      #Only send messages to the logfile (see Directory Structure for logfile name and location)<br>
-logtype many      #Send messages to both the console and file<br>
</pre>

#### -verbose
If omitted the default is False
<pre>
**example**

-verbose       #Causes the output of system calls to be logged according to the setting of -logtype<br>
</pre>

#### -poll [seconds]
If omitted the default is 5 seconds.  This is the time between checking to see if am image needs to be captured.
If -seconds (see below) is less than -poll then poll is reduced to the value of -seconds.

#### -host [ip address]
If omitted the default is 0.0.0.0<br>
Generally this can be left out (default) as it will allow connection to the http listener from localhost:<port> (locally) or from another machine with network access using <actual-ip-address-of-server-running-DuetLapse3><port>.
<pre>
**example**

-host 192.168.86.10      #Causes internal http listener (if active) to listen at ip address 192.168.86.10<br>
</pre>

#### -port [port number]
If omitted the default is 0 AND the internal http listener is NOT started.<br>
Depending on the system, the is may be reported in different ways e.g. 127.0.0.1 as opposed to the actual ip address.<br>
Note that it is generally better to specify the actual ip address as this makes it easier for an external browser to connect.
**The http listener is only started if a port number is specified**
<pre>
**example**

-port 8082      #Causes internal http listener to start and listen on port 8082<br>
</pre>

#### -standby
If omitted the default is False<br>
If the http listener is active (i.e. -port is specified) - this option will cause DuetLapse3 to wait for a start command from the http listener before capturing images.<br>
It is useful for having DuetLapse running but not actually doing anything until commanded to do so.
<pre>
**example**

-stopcmd #Causes internal http listener to start and listen on port 8082<br>
</pre>

#### -dontwait
If omitted - the default is False
<pre>
**example**

-dontwait    #Images will be captured immediately (without first waiting for a layer change or pause) if -seconds > 0.
             #Otherise images will first start being captured on the first layer change or pause (see -detect).
</pre>

#### -seconds [seconds]
If omitted the default is 0 seconds (i.e. ignored). Can be any positive number.
<pre>
**example**

-seconds 10  #Images will be captures at least every 10 seconds<br>
</pre>

#### -detect [layer||pause||none]
If omitted the default is layer
<pre>
**example**

-detect layer     #Will capture an image on each layer change<br>
-detect pause     #Will capture an image if the printer is paused by the print gcode **M226**<br>
-detect none      #Will not capture an image other than as secified by -seconds<br>
</pre>
*Notes on the use of -detect pause*<br>
When a pause is detected in the print gcode (supplied by an M226) an image will be captured and a resume print command issued.
The head position during those pauses is can be controlled by the pause.g macro on the duet,
or by specifying "-movehead nnn nnn".<br>
If both are specified pause.g will run first then -movehead will reposition the heads. **It is best not use both.**<br>
**CANNOT be used in conjunction with -pause yes (see below)**

#### -pause [yes||no]
If omitted the default is no. If - pause yes it will pause the printer when an image is captured.
<pre>
**example**

-pause yes      #Pause the printereach time an image is captured.<br>
</pre>
*Notes on the use of -pause yes*<br>
DuetLapse3 will pause the printer each time an image is to be captured.
The head position during those pauses can be controlled by the pause.g macro on the duet,
or by specifying "-movehead nnn nnn".<br>
If both are specified pause.g will run first then -movehead will reposition the heads. **It is best not use both.**<br>
**CANNOT be used in conjunction with -detect pause (see above)**

#### -movehead [Xposition,Yposition]
if omitted the head is not moved - equivalent to -movehead 0,0.  Specifies a position to move the head to before capturing an image.
Valid positions must be greater then 0.0 and less than the maximum allowed by your printer
<pre>
**example**

-movehead 10,5    #Will move the head to X=10, Y=5 before capturing an image<br>
</pre>

#### -extratime [second]
If omitted the default is 0.  When creating the video - extends the duration of the last frame by the specified number of seconds.<br>
To use - requires ffmpeg at version 4.2+
<pre>
**example**

-extratime 10     #Makes the last frame captured 10 seconds long<br>
</pre>
*Notes on the use of - extratime*
Applies to the last frame captured.  So if, for example, your print job moves the Z axis at the end of the print.  The last frame would occur when the Z axis stops moving - not when the last layer is printed.

#### -camera1 [usb||pi||web||stream||other]
If omitted the default is usb. Determines how images are captured.
<pre>
**example**

-camera1 usb      #Uses the camera associated with fswebcam<br>
-camera1 pi       #Uses the camera associated with the rasberry pi camera's standard installation<br>
-camera1 web      #Uses wget to capture images from a camera that provides still jpeg<br>
-camera1 stream   #Uses ffmpeg to capture images from a video feed<br>
-camera1 other    #Canonly be used in conjunction with -camparam1 (see below)<br>
</pre>

#### -weburl1 [url]
If omitted it has no value. url specifies the location to capture images for camera1. Only used for -camera1 of types web, stream, or other
<pre>
**example**

-weburl http://192.168.86.10/stream.mpeg  #capture images from this location
</pre>

#### -camera2 [usb||pi||web||stream||other]
If omitted has no default (unlike camera1). Has the same parameters as -camera1

#### -webur2 [url]
Has the same parameters as -weburl2

#### -camparam1="[command]"
If omitted has no default. Used in conjunction with -camera1 to define how the images will be captured.<br>
**Note the use of the = and quoting of the command string.** Single quotes should be used in the command string when needed.<br>
There are 3 internal variables that can be used weburl (which has the value of weburl1), fn (which is the file for the captured images) , debug (which controls verbose logging)
<pre>
**example**

-camparam1="'ffmpeg -y -i '+weburl+ ' -vframes 1 ' +fn+debug"<br>
</pre>
This example is the same as if -camera1 stream was used. The value of weburl1 would be substituted for weburl and the output goes the the file specification fn. the results are verbose of not is defermined by the internal variable debug.  In general both fn and debug should be used.  The use of weburl would depend on the capture method being used.

*Notes on the use of -camparam1*<br>
The following are the standard commands for reference

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
**Note the use of the = and quoting of the command string.**  Single quotes should be used in the command string when needed.<br>
There are 3 internal variables that can be used basedir (has the same meaning as -basedir), cameraname (is the literal "Camera1"), extratime (is the value of -extratime), fn (which is the output file for -camera1) , debug (which controls verbose logging)
<pre>
**example**

-vidparam1="'ffmpeg -r 1 -i '+basedir+'/'+duetname+'/tmp/'+cameraname+'-%08d.jpeg -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn+debug"<br>
</pre>
This example is the same as the standard video creation.

#### -camparam2 and -vidparam2
Have the same parameters as -camparam1 and -vidparam1.  Variable references are for Camera2


### Directory Structure

The directory structure organized to allow multiple instances of DuetLapse3 to keep files separate.  
```
basedir/
       duet-address/   
                    tmp/
``` 
**duet-address** is derived from the -duet option.  Periods are replaced by a dash for example -duet 192.168.1.10 creates the sub directory 192-168-1-10, -duet myduet.local becomes myduet-local.<br>
The duet-address subdirectory contains the video files as well as a log file *DuetLapse3.log* relating to the specific printer.  The video files are named according to this scheme  "<Camera><pid>-Day-Hour:Min.mp4"  where <Camera> is Camera1 or Camera2 and <pid> is the process id. e.g  Camera110978-Thur-22:31.mp4<br>
**tmp** is used to capture the still images for the printer. It is cleared out when DuetLapse3 starts or restarts.  This way - if anything goes wrong with the video creation a command line use of ffmpeg (or other program) can be used to attempt recovery.  
 
## Usage Examples

Many options can be combined.  For example, the script can trigger on both "seconds" and "detect layer". It will inform you if you select conflicting options.
Note that these examples are from the command line.  If running from a script (or to avoid issues closing the console) adding a **&** at the end (in linux) will run the script in background.

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


  

