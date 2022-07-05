# Currently being actively changed = do not use = likely just today

## DuetLapse3
 
#### This is a modified version of the original DuetLapse created by Danal Estes https://github.com/DanalEstes/DuetLapse
#### The core ideas are his work.

[General Description - links to DuetLapse3.md and startDuetLapse3.md and Usage Examples.md and Controlling with gcode.md]
## General Description
Provides the ability to generate time-lapse videos from for Duet based 3D printers.

##Version History

### Version 3.0.0
- [1]  Removal of dependency on DuetWebAPI.py (by Danal Estes).  DuetLapse3.py is a standalone Python3 program.
- [2]  Added support for 2 cameras
- [3]  Reorganized Directory Structure to allow logical separation of files (by printer)
- [4]  Added configurable base directory 
- [5]  Added logfile support
- [6]  Added verbose option
- [7]  Added control over multiple instances
- [8]  Added ability to gracefully terminate when executing in background
- [9]  Added ability to extend the video duration of the last image (depends on ffmpeg version)
- [10] Generalized capture with Camera type "other" and arbitrary capture commands
- [11] Generalized video creation with optional commands

### Version 3.0.3
- [1]  Added support for SBC.

###Version 3.0.4
- [1]  All functionality supported for SBC
- [2]  More robust error handling
- [3]  Improvements to pause logic and confirmation of printer head position during pause image capture.

### Version 3.1.0
- [1]  Added support for Windows
- [2]  Added automatic detection of operating system (Linux or Windows)
- [3]  Added integrated http listener for basic browser based control
- [4]  Changed file naming convention to make filenames unique if multiple instances of DuetLapse3 are running.

### Version 3.1.1
- [1]  if -extratime not specified (default 0) will use ffmpeg syntax compatible with versions < 4.2 (4.1.6 tested)

### Version 3.2.0
- [1]  Adds the ability to work with startDuetLapse3.  See the description here:<br>
       https://github.com/stuartofmt/DuetLapse3/blob/main/startDuetLapse3.md<br>
       In summary startDuetLapse3 provides the ability to remotely start / stop DuetLapse3.<br>
- [2]  Added checks to prevent startup with ports that are already in use.<br>
- [3]   Changed the shutdown method to reduce low level 'noise' messages.<br>
- [4]  Restructured to provide better efficiency. Typically, this is less than 1% CPU when idle.<br>
- [5]  Fixed a bug that was introduced in the prior version (not detecting layer changes)<br>
- [6]  Made further improvements to the handling of pauses.<br>
       There are some edge cases where a printer can get stuck in a paused state.<br>
       The documentation has been updated.  See especially -dontwait
       
### Version 3.2.2
- [1]  Added resilience to lost connectivity with Duet.  If disconnected the issue will be reported and attempts to reconnect will be made<br>
- [2]  Made some cosmetic changes to the http responses.  Most now include the local time as part of the response.
- [3]  The status page will automatically refresh every 60 seconds.  Other pages will show the last time they were invoked.

###Version 3.2.3
- [1] Fixed some inconsistencies when running on Windows due to slightly different behavior of python3.

### Version 3.3.0
- [1] Completely revised the UI when running the http listener.  The main change the addition of buttons to make navigation easier.

### Version 3.4.0
- [1] Completely revised the directory and file-naming structure to facilitate many-to-many relationships between computers running DuetLapse3, Duet Printers and multiple instances of DuetLapse3.
- [2] Changed how http terminate requests were handled for better cross-platform compatibility.
- [3] Added the ability to navigate the directory structure from a browser (new button).Also in startDuetLapse3.
- [4] Added three new options: -keeplogs, -deletepics and -novideo
- [5] Made some cosmetic changes to the html pages.

### Version 3.4.1
- [1] Changed the browser UI to a single page layout.
- [2] The file function is restricted to the specific instance.
- [3] File functions expanded to allow deletion of video files. startDuetLapse3 has more options.
- [4] If using -detect layer capture starts on layer 0 (previously was layer 1).
- [5] An additional image is captured immediately before a video is created, independent of other settings.
- [6] If the version of ffmpeg does not support -extratime it is ignored. 

### Version 3.4.2
- [1] Added a new options: -keepfiles to prevent file deletion on startup and shutdown(See also startDuetLapse3 improvements)
- [2] Terminate (from the UI) now offers two options: Graceful and Forces.  Graceful is the same as in prior versions.  Forced does a quick shutdown with no image capture.
- [3] Added an optional argument (-maxffmpeg) that limits the number of concurrent ffmpeg instances. Ffmpgeg can fail due to lack of resources - the default is 2 instances.
      This only applies to video creation.  Image capture, because it is transient, is not limited.

### Version 3.4.3 and 3.4.4
- [1] Minor bug fixes

### Version 3.5.0
- [1]  Changed some system calls to allow for better error handling.
- [2]  Fixed an issue with sending gcodes to SBC
- [3]  Improved the handling of  -pause yes and - movehead
- [4]  Added an optional argument -rest that delays image capture after a pause. This is because the camera feed can be delayed with respect to the actual head position.
- [5]  Updated documentation with additional notes
- [6]  Deprecated the use of -camera pi due to changes in Raspberry Pi (see notes in the section on -camera).
- [7]  Added a new argument -nolog and deprecated -logtype.  Logging will always use the console unless the program is running in the background.
- [8]  If -verbose is used, much more detail is created.  Should usually only be used for debugging.
- [9]   Added new argument -fps.  Sets the default frames-per-seconds
- [10]  Added the ability to change the default frames-per-second (fps) from the main menu.
- [11]  Added a new argument -hidebuttons.  Hides menu buttons that are currently invalid. Otherwise, invalid buttons are greyed out.
- [12]  General UI improvements.
- [13]  After Snapshot, returns to the previous logical state either 'start' or 'pause' 

### Version 4.0.0
[Add description]
