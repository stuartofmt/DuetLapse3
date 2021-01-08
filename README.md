# DuetLapse3

##This is a modified version of the original DuetLapse created by Danal Estes

The modifications include:
- [1] Added functionality
- [2] Removal of dependency on DuetWebAPI.py by Danal Estes - now a single Python3 script
- [3] Support for streaming video feeds
- [4] More generalized MP4 output that can be displayed on ipad / iphone etc.
- [?] SUpport for Windows

##General Description
Provides the ability to generate time lapse videos from for Duet based 3D printers.

Designed and tested on Raspberry Pi but should work on other linux platform. Supports cameras via
- [1] USB,
- [2] Pi (ribbon cable)
- [3] Webcam delivering streaming video
- [4] Webcam delivering still images

Produces a video with H.264 encoding in an MP4 container. 

Captures images based on time, layer change, or pause.  Works with existing pauses in G-Code, or can force pauses at other trigger events. Optionally moves head to a specified position before capturing paused images.

Feedback via issues on Duet forum https://forum.duet3d.com/
Status of Features.  Unchecked features are planned, coming soon:

## Installation
* mkdir DuetLapse
* cd DuetLapse
* wget https://raw.githubusercontent.com/stuartofmt/DuetLapse/master/DuetLapse3.py
* chmod 744 DuetLapse.py


## Requirements 

* Python3
* Duet printer must be RRF V3 (support the rr_model calls)
* ffmped version 4.x (this may need to be compiled if your system has an older version as standard)
* Duet printer must be reachable via network
* Depending on camera type, one of
  * fswebcam (for USB cameras)
  * raspistill (for Pi cam or Ardu cam)
  * wget (for Web cameras)
  
## Usage

The python script can be started from the command line or, more usually, from a bash or similar script (see example bash script here  ).  Although there are defaults for many of the options - it's unlikely that the script will do anything useful with just the defaults.
The script will usually be started you starting a printing - but this is not critical.  Depending on options (e.g. dontwait) it will either imeediately start creating still images or wait until the printer changes status from "Idle" to "Processing".  At the end of the print job the script combines the still images into a mp4 video to create the time lapse.  If the script is run in foreground it can be stopped (before the print job completes) using CTl+C.  If the script is run in background it can be stopped using SIGINT (kill -2 <pid> in linux).  The example bash script gives an example of using SIGINT. 

###Options###

####-duet####

*-duet <ip address>*  This is a required.  The parameter <ip address> is the network location of your duet printer.  It can be given as a hostname or an explicit ip.
 example -duet 192.168.1.10 or -duet localhost or -duet myduetprinter.local.   As a simple test - a browser shoul be able to access Duet Web Controller using http://<ip address>


###Directory Structure###

The directory structure is as follows

## Usage Notes

This script is in rapid development, and runnith ./DuetLapse.py -h is likely to give more recent usage information. 

The only required flag is -duet to specify the printer to which the script will connect.  If not specified, camera defaults to "USB" and detection defaults to "layer". Example:
```
./DuetLapse.py -duet 192.168.7.101 
```

Many options can be combined.  For example, the script can trigger on both "seconds" and "detect layer". It will inform you if you select conflicting options. 

Example: Use a webcam that requires a UserId and Password, trigger every 30 seconds, do not detect any other triggers:
```
./DuetLapse.py -camera web -weburl http://userid:password@192.168.7.140/cgi-bin/currentpic.cgi -duet 192.168.7.101 -seconds 20 -detect none
```
Example: Default to USB camera and detecting layer changes, force pauses (at layer change) and move head to X10 Y10 before taking picture.
```
./DuetLapse.py -duet 192.168.7.101 -pause yes -movehead 10 10
```


  

