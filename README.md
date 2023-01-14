## DuetLapse3
 
#### This is a significantly modified version of the original DuetLapse created by Danal Estes https://github.com/DanalEstes/DuetLapse
#### The core ideas are his work.

## General Description

DuetLapse3 provides a highly configurable program for creating timelapse videos from printers using the Deut3D software.
It can be run as a one-of or continuously in the background.

A companion program startDuetLapse 3 provides administration capabilities and is especially useful if multiple instances of DuetLapse3 are running and connected to multiple printers.

### Details of DuetLapse3 are in this document:

[DuetLapse3.md](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/DuetLapse3.md)

**In addition to a browser interface DuetLapse3 can be controlled directly from gcode.**

[Controlling with gcode.md](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/Controlling%20with%20gcode.md)

### Details of startDuetLapse3 are in this document:

[startDuetLapse3.md](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/startDuetLapse3.md)

### Useage examples are in this document:
[DuetLapse3 Useage Examples.md](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/DuetLapse3%20Useage%20Examples.md)


## Version History

Deleted verion history prior to 4.0

### Version 5.0.0
- [1]  Completely revised UI
- [2]  Added display of last captured image to UI
- [3]  Added ability to specify a config file with -file option
       This avoids the need for long command lines. Options in command line over-write those in config file
- [4]  Added -maxvideo.  Limits the maximum length of video by varying fps as needed
- [5]  Added ability to change -fps -minvideo and -maxvideo in the UI
- [6]  UI gives indication of video creation status
- [5]  Misc bug fixes

### Version 4.1.0
- [1]  Added support for M117 DuetLapse.change.movehead=x,y
- [2]  Added Delete, Zip, Video in UI for completed jobs in currently running instance
- [3]  Suppressed long message when a client (browser) disconnects during UI update

### Version 4.0.0
- [1]  Added the ability to control the program with gcode M117 messages
- [2]  Added the ability to execute an arbitrary program by sending M117 gcode with a configurable prefix
- [3]  Added -restart option to allow a program to continue running at end of print
- [4]  Significantly improved ability to continue running after extended network interruptions.
- [5]  Can continue to run even if printer is turned off
- [6]  Changed - extratime handling so as not to require tpad support in ffmpeg
- [7]  Added -minvideo option to set minimum video length (seconds default 5)
- [8]  Changed default -poll to minimum of 12 seconds.
- [9]  Changed default -seconds to minimum of 12 seconds.
- [10] Suppressed a lot of output unless -verbose is used
- [11] Changed logfile naming convention to better support - restart.<br>
Initially the logfile is created with a timestamp. When the print starts the logfile is renamed to reflect the name of the print job
