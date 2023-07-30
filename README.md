## DuetLapse3

#### This is a significantly modified version of the original DuetLapse created by Danal Estes https://github.com/DanalEstes/DuetLapse
#### The core ideas are his work.

## General Description

DuetLapse3 provides a highly configurable program for creating timelapse videos from printers using the Deut3D software.

It can be run as a one-of or continuously in the background.

It is also available as a plugin for Duet3D SBC

A companion program startDuetLapse3 provides administration capabilities and is especially useful if multiple instances of DuetLapse3 are running and connected to multiple printers.

For most users, startDuetLapse3 will not be used.

**In addition to a browser interface DuetLapse3 can be controlled directly from gcode.**

### A quick installation guide for the DuetLapse3 plugin is in this document:

[Plugin installation guide.md](https://github.com/stuartofmt/DuetLapse3/blob/main/plugin/plugin%20installation%20guide.md)

### A quick installation guide for standalone DuetLapse3 is in this document:

[Standalone quick installation guide.md](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/Standalone%20quick%20installation%20guide.md)

### Details of DuetLapse3 options are in this document:

[DuetLapse3.md](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/DuetLapse3.md)

**In addition to a browser interface DuetLapse3 can be controlled directly from gcode.**

[Controlling with gcode.md](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/Controlling%20with%20gcode.md)

**Useage examples are in this document**

[DuetLapse3 Useage Examples.md](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/DuetLapse3%20Useage%20Examples.md)

## Version History

Deleted verion history prior to 5.0

### Version 5.2.2

- [1]  Fixed bug in -pause layer detection
- [2]  Added wait loop before restart to ensure previous job had finished - a timing thing dependent on when "Complete" sent and the finish of gcode
- [3]  Added more specific check for version number of dsf

### Version 5.2.1

- [1]  DWC Plugin added
- [2]Fixed snapshot when called from gcode
- [3]Fixed calculation type error on extratime
- [4]rationalized timers
- [5]changed M117 messages to M291
- [6]Refreshes tab on regaining focus from browser
- [7]Changed G1 to G0 in movehead
- [8]Process all M291 messages without delay
- [9]Refactored loop control to prevent thread blocking
- [10]Prevent first layer capture if -pause yes
- [11]Added -password
- [12]Changed nackground tab color - better for dark theme

### Version 5.0.0
- [1]  Completely revised UI
- [2]  Added display of last captured image to UI
- [3]  Added ability to specify a config file with -file option
       This avoids the need for long command lines. Options in command line over-write those in config file
- [4]  Added -maxvideo.  Limits the maximum length of video by varying fps as needed
- [5]  Added ability to change -fps -minvideo and -maxvideo in the UI
- [6]  UI gives indication of video creation status
- [5]  Misc bug fixes