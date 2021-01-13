# DuetLapse3

## This is a modified version of the original DuetLapse created by Danal Estes
https://github.com/DanalEstes/DuetLapse
## The bulk of the functionality is his work.

The modifications include:
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

## General Description
Provides the ability to generate time lapse videos from for Duet based 3D printers.

Designed and tested on Raspberry Pi but should work on other linux platform. Supports cameras via
- [1] USB,
- [2] Pi (ribbon cable)
- [3] Webcam delivering streaming video
- [4] Webcam delivering still images

Produces a video with H.264 encoding in an MP4 container. 

Captures images based on time, layer change, or pause.  Works with existing pauses in G-Code, or can force pauses at other trigger events. Optionally moves the print head to a specified position before capturing images.

Feedback via issues on Duet forum https://forum.duet3d.com/

## Requirements 

* Python3
* Duet printer must be RRF V3 or later (i.e. support the rr_model calls)
* ffmpeg version 4.x (this may need to be compiled if your system has an older version as standard)
* Python dependencies that are missing will be called out by the script
* Duet printer must be reachable via network
* Depending on camera type, one or more of the following may be required:
  * fswebcam (for USB cameras)
  * raspistill (for Pi cam or Ardu cam)
  * wget (for Web cameras)

## Installation
* mkdir DuetLapse  - or other directory of your choice
* cd DuetLapse
* wget https://github.com/stuartofmt/DuetLapse3/blob/main/DuetLapse3.py
* chmod 744 DuetLapse3.py
  
## Usage

The python script can be started from the command line or, more usually, from a bash or similar script.  Although there are defaults for many of the options - it's unlikely that the script will do exactly what you want with just the defaults.
The script will usually be started just before you starting a printing - but this is not critical.  Depending on options (e.g. dontwait) it will either immediately start creating still images or wait until the printer changes status from "Idle" to "Processing".  At the end of the print job the script combines the still images into a mp4 video to create the time lapse.  If the script is run in foreground it can be stopped (before the print job completes) using CTl+C.  If the script is run in background it can be stopped using SIGINT (kill -2 <pid> in linux).  The example bash script here https://github.com/stuartofmt/DuetLapse3/blob/main/timelapse   gives examples for starting and stopping the program. 

### Options

Options can be viewed with
```
DuetLapse3.py -h
```
The options are described here.  Each option is preceded by a dash -. Some options have parameters described in the square brackets (the square brackets are NOT used in entering the options. If an option is not specified the default used.

#### -duet [ip address]

**Mandatory - This is a required option.**  The parameter is the network location of your duet printer.  It can be given as a hostname or an explicit ip address.
As a simple test - a browser should be able to access the Duet Web Controller using http://<ip address> from the same computer that is running DuetLapse3.py.
**example**
-duet 192.168.1.10     #Connect to the printer at 192.168.86.10
-duet localhost        #Connect to the printer at localhost

#### -basedir [full path name]
If omitted - the default dir is the location of DuetLapse3.py.  This is the logical root for output files See Directory Structure (below).
If supplied, do NOT put in a trailing slash /<br>
**example**
-basedir /home/pi/mydir  #output files start at /home/pi/mydir

#### -instances [single||oneip||many]
If omitted - the default is single. Used to control the number of instances of DuetLapse3.py that can run simultaneously.
In most cases the default will be suitable.
**example**
-instances single   #There can only be one instance of DuetLapse3.py running
-instance oneip     #For each printer (set by -duet), there can only be one instance of DuetLapse3.py running
-instances many     #No restriction on the number of instances

#### -logtype [console||file||both]
If omitted - the default is both
**example**
-logtype console   #Only send messages to the console
-logtype file      #Only send messages to the logfile (see Directory Structure for logfile name and location) 
-logtype many      #Send messages to both the console and file

#### -verbose
If omitted the default is False
**example**
-verbose       #Causes the output of system calls to be looged according to the setting of -logtype

#### -poll [seconds]
If omitted the default is 5 seconds.  This is the time between checking to see if am image needs to be captured.
If -seconds (see below) is less than -poll then poll is reduced to the value of -seconds. 

#### -dontwait
If omitted - the default is False
**example**
-dontwait    #Images will be captured immediately.  Does not wait for the printer to start.

#### -seconds [seconds]
If omitted the default is 0 seconds (i.e. ignored). Can be any positive number.
**example**
-seconds 10  #Images will be captures at least every 10 seconds

#### -detect [layer||pause||none]
If omitted the default is layer
**example**

-detect layer     #Will capture an image on each layer change
-detect pause     #Will capture an image if the printer is paused by the print gcode
-detect none      #Will not capture an image other than as secified by -seconds

*Notes on the use of -detect pause*
When a pause is detected in the print gcode an image will be captured and a resume print command issued.
The head position during those pauses is can be controlled by the pause.g macro on the duet,
or by specifying "-movehead nnn nnn".  Do not use both.
CANNOT be used in conjunction with -pause yes (see below)

#### -pause [yes||no]
If omitted the default is no. If - pause yes it will pause the printer when an image is captured.
**example**
-pause yes      #Pause the printer each time an image is captured.

#### -movehead [Xposition,Yposition]
if omitted the head is not moved - equivalent to -movehead 0,0.  Specifies a position to move the head to before capturing an image.
Valid positions must be greater then 0.0 and less than the maximum allowed by your printer
**example*
-movehead 10,5    #Will move the head to X=10, Y=5 before capturing an image

#### -extratime [second]
If omitted the default is 0.  When creating the video - extends the duration of the last frame by the specified number of seconds.
**example**
-extratime 10     #Makes the last frame captured 10 seconds long

#### -camera1 [usb||pi||web||stream||other]
If omitted the default is usb. Determines how images are captured.
**example*
-camera1 usb      #Uses
-camera1 pi       #Uses
-camera1 web      #Uses wget to capture images from a camera that provides still jpeg
-camera1 stream   #Uses ffmpeg to capture images from a video feed
-camera1 other    #Canonly be used in conjunction with -camparam1 (see below)

#### -weburl1 [url]
If omitted it has no value. url specifies the location to capture images for camera1. Only used for -camera1 of types web, stream, or other
**example**
-weburl http://192.168.86.10/stream.mpeg  #capture images from this location

#### -camera2 [usb||pi||web||stream||other]
If omitted has no default (unlike camera1). Has the same parameters as -camera1

#### -webur2 [url]
Has the same parameters as -weburl2

#### -camparam1="[command]"
If omitted has no default. Used in conjunction with -camera1 to define how the images will be captured.
**Note the use of the = and quoting of the command string.** Single quotes should be used in the command string when needed.
There are 3 internal variables that can be used weburl (which has the value of weburl1), fn (which is the file for the captured images) , debug (which controls verbose logging)
**example**
-camparam1="'ffmpeg -y -i '+weburl+ ' -vframes 1 ' +fn+debug"
This example is the same as if -camera1 stream was used. The value of weburl1 would be substituted for weburl and the output goes the the file specification fn. the results are verbose of not is defermined by the internal variable debug.  In general both fn and debug should be used.  The use of weburl would depend on the capture method being used.

#### -vidparam1="[command]"
If omitted has no default. Defines an alternate video capture command.  If provided - is used instead of the standard capture command.
**Note the use of the = and quoting of the command string.**  Single quotes should be used in the command string when needed.
There are 3 internal variables that can be used basedir (has the same meaning as -basedir), cameraname (is the literal "Camera1"), extratime (is the value of -extratime), fn (which is the output file for -camera1) , debug (which controls verbose logging)
**example**
-vidparam1="'ffmpeg -r 1 -i '+basedir+'/'+duetname+'/tmp/'+cameraname+'-%08d.jpeg -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn+debug"
This example is the same as the standard video creation for -camera1.

#### -camparam2 and -vidparam2
Have the same parameters as -camparam1 and -vidparam1.  Variable references are for Camera2


### Directory Structure

The directory structure organized to allow multiple instances of DuetLapse3 to keep files separate.  
```
basedir/
       duet-address/   
                    tmp/
``` 
**duet-address** is derived from the -duet option.  Periods are replaced by a dash for example -duet 192.168.1.10 creates the sub directory 192-168-1-10, -duet myduet.local becomes myduet-local.
The duet-address subdirectory contains the video files as well as a log file *DuetLapse3.log* relating to the specific printer.  The video files are named according to this scheme  "Camera-Day-Hour:Min.mp4"  e.g  Camera1-Thur-22:31.mp4
**tmp** is used to capture the still images for the printer. It is cleared out at the *start* of each capture.  This way - if anything goes wrong with the video creation a command line use of ffmpeg (or other program) can be used to attempt recovery.  
 
## Usage Examples

Many options can be combined.  For example, the script can trigger on both "seconds" and "detect layer". It will inform you if you select conflicting options.
Note that these examples are from the command line.  If running from a script (or to avoid issues closing the console) adding a **&** at the end (in linux) will run the script in background.

Example: Use a webcam that requires a UserId and Password, capture an image every 20 seconds, do not respind to layer changes or pauses:
```
./DuetLapse3.py -camera1 web -weburl1 http://userid:password@192.168.7.140/cgi-bin/currentpic.cgi -duet 192.168.7.101 -seconds 20 -detect none

```
Example: Default to USB camera.  Capture an image on layer changes. Force pauses (at layer change) and move head to X10 Y10 before creating an image.
```
./DuetLapse3.py -duet 192.168.7.101 -pause yes -movehead 10 10

```
Example: Two camera example. Start capturing immediately at a minumum of one image every 3 second. Camera2 uses camparam and vidparam2 overrides. Run in background.
```
/usr/bin/python3 $PROCESS -duet 192.168.86.235 -basedir /home/pi/Lapse -instances oneip -dontwait -seconds 3 -camera1 stream -weburl1 http://192.168.86.230:8081/stream.mjpg  -camera2 other -weburl2 http://192.168.86.230:8081/stream.mjpg -camparam2="'ffmpeg -y -i '+weburl+ ' -vframes 1 ' +fn+debug" -vidparam2="'ffmpeg -r 1 -i '+basedir+'/'+duetname+'/tmp/'+cameraname+'-%08d.jpeg -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn+debug" -extratime 0 &
```


  

