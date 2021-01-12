# DuetLapse3

## This is a modified version of the original DuetLapse created by Danal Estes
## The bulk of the functionality is his work.

The modifications include:
- [1] Removal of dependency on DuetWebAPI.py (by Danal Estes).  DuetLapse3.py is a standalone Python3 script
- [2] Added support for 2 cameras
- [3] Reorganized Directory Structure to allow logical separation of files (by printer)
- [4] Added configurable base directory 
- [5] Added logfile support
- [6] Added verbose option
- [7] Added control over multiple instances
- [8] Added ability to gracefully terminate when executing in background
- [9] Added ability to extend the video duration of the last image

## General Description
Provides the ability to generate time lapse videos from for Duet based 3D printers.

Designed and tested on Raspberry Pi but should work on other linux platform. Supports cameras via
- [1] USB,
- [2] Pi (ribbon cable)
- [3] Webcam delivering streaming video
- [4] Webcam delivering still images

Produces a video with H.264 encoding in an MP4 container. 

Captures images based on time, layer change, or pause.  Works with existing pauses in G-Code, or can force pauses at other trigger events. Optionally moves head to a specified position before capturing paused images.

Feedback via issues on Duet forum https://forum.duet3d.com/

## Requirements 

* Python3
* Duet printer must be RRF V3 or later (i.e. support the rr_model calls)
* ffmped version 4.x (this may need to be compiled if your system has an older version as standard)
* Python libraries will be called out by the script if not present
* Duet printer must be reachable via network
* Depending on camera type, one of
  * fswebcam (for USB cameras)
  * raspistill (for Pi cam or Ardu cam)
  * wget (for Web cameras)

## Installation
* mkdir DuetLapse
* cd DuetLapse
* wget https://raw.githubusercontent.com/stuartofmt/DuetLapse3/master/DuetLapse3.py
* chmod 744 DuetLapse.py
  
## Usage

The python script can be started from the command line or, more usually, from a bash or similar script (see example bash script here  ).  Although there are defaults for many of the options - it's unlikely that the script will do anything useful with just the defaults.
The script will usually be started you starting a printing - but this is not critical.  Depending on options (e.g. dontwait) it will either imeediately start creating still images or wait until the printer changes status from "Idle" to "Processing".  At the end of the print job the script combines the still images into a mp4 video to create the time lapse.  If the script is run in foreground it can be stopped (before the print job completes) using CTl+C.  If the script is run in background it can be stopped using SIGINT (kill -2 <pid> in linux).  The example bash script gives an example of using SIGINT. 

### Options

Options can be viewed with
```
DuetLapse3.py -h
```

#### -duet {ip address}

This is a required option.  The parameter {ip address} is the network location of your duet printer.  It can be given as a hostname or an explicit ip.
example -duet 192.168.1.10 or -duet localhost or -duet myduetprinter.local.   As a simple test - a browser shoul be able to access Duet Web Controller using http://<ip addreinstances

#### -basedir

#### -instances

#### -logtype

#### -verbose

#### -dontwait

#### -seconds

#### -detect

#### -pause

#### -movehead

#### -extratime

#### -camera1

#### -weburl1

#### -camera2

#### -webur2

#### -camparam1

#### -vidparam1

#### -camera 2, weburl2, camparam2 and vidparam2
Allows for a second camera to be defined.  There is no default type.  If used the same requirements as camera 1 apply.


### Directory Structure

The directory structure organized to allow multiple instances of DuetLapse3 to keep files separate.  
```
basedir/
       duet-address/   
                    tmp/
``` 
**duet-address** is derived from the -duet option.  Periods are replaced by a dash for example -duet 192.168.1.10 creates the sub directory 192-168-1-10, -duet myduet.local becomes myduet-local.
The duet-address subdirectory contains the video files as well as a log file *DuetLapse3.log* relating to the specific printer.  The video files are named according to this scheme  "TimeLapse-Day-Hour:Min.mp4"  e.g  Timelapse-Thur-22:31.mp4
**tmp** is used to capture the still images for the printer. It is cleared out at the *start* of each capture.  This way - if anything goes wrong with the video creation a command line use of ffmpeg can be used to attempt recovery.  
 

## Usage Examples

Many options can be combined.  For example, the script can trigger on both "seconds" and "detect layer". It will inform you if you select conflicting options.
Note that these examples are from the command line.  If running from a script (or to avoid issues closing the console) adding a **&** at the end (in linux) will run the script in background.

Example: Use a webcam that requires a UserId and Password, trigger every 30 seconds, do not detect any other triggers:
```
./DuetLapse3.py -camera web -weburl http://userid:password@192.168.7.140/cgi-bin/currentpic.cgi -duet 192.168.7.101 -seconds 20 -detect none
```
Example: Default to USB camera and detecting layer changes, force pauses (at layer change) and move head to X10 Y10 before taking picture.
```
./DuetLapse3.py -duet 192.168.7.101 -pause yes -movehead 10 10
```


  

