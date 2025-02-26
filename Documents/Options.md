# DuetLapse3 Options

## Overview

Designed and tested on Raspberry Pi but should work on other linux platform. Supports cameras via:

- [1] USB
- [2] Pi (ribbon cable)
- [3] Webcam or software delivering streaming video
- [4] Webcam or software delivering still images

Produces a video with H.264 encoding in an MP4 container.

Capture images based on time, layer change, or pause.  Works with existing pauses in G-Code, or can force pauses at other trigger events. Optionally moves the print head to a specified position before capturing images.

Feedback via issues on Duet forum <https://forum.duet3d.com/topic/20932/duetlapse3>

## Requirements

- Python3  V3.7 or greater
- As standalone Duet printer must be RRF V3 or later (i.e. support either the  rr_model or /machine calls)
- As plugin Duet printer must be RRF V3.4 or later (i.e. /machine calls)
- Python dependencies that are missing will be called out by the program
- Duet printer must be reachable via the network
- Depending on camera type, one or more programs may need to be available on your computer.

## Usage

Although there are defaults for many of the options - it's unlikely that the program will do exactly what you want.

Options can be specified on the command line, in a configuration file ( see -file below) or using a combination.  If both a configuration file is used and command line options are provided, the configration file take precidence over any duplicate entries.

Examples of command line options are shown here:

<https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/DuetLapse3%20Useage%20Examples.md>

The program will usually be started just before you starting printing job - but this is not critical.  Depending on options (e.g. dontwait) it will either immediately start creating still images or wait until the printer starts printing.

At the end of the print job the program combines the still images into a mp4 video to create the time-lapse.

### Controlling DuetLapse3

There are three ways to control DuetLapse.  All three require that its integrated http server is activated by using the -port option (see below).  THIS IS HIGHLY RECOMMENDED. The three ways are:

1) Browser based UI
2) Sending http messages e.g. froma browser or using curl
3) From a gcode print (or DWC UI) using M3291 messages

#### Browser based UI

The user interface is described here:
[Controlling with the UI](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/User%20Interface.md)

#### http messages

http methods for controlling DUetLapse3 can be found here:

[Controlling with http](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/Using%20http%20controls.md)

#### gcode messages

DuetLapse3 can be controlled directly from gcode using M3291 messages

[Controlling with gcode.md](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/Controlling%20with%20gcode.md)

## Options

DuetLapse3 has many options that control its behavior.  Each option is preceded by a dash -

Some options have parameters described in square brackets. The square brackets are NOT used in entering the options. If an option is not specified the default is used.

Comments in the example (preceded by #) must not be included in the command line or configuration file.

Options can be viewed in the UI on the "Info" tab or from a console using:

```bash
python3 DuetLapse3.py -h
```

___

#### -file [filename]

Optional (but highly recommended).  A configuration file (text format) with one option per line.  The path to the configuration file (relative or absolute) must be given.
  
**example**

```bash
-file ./DuetLapse3.config     # Read options from this file
```
___

#### -# [quoted comment string]

Recommended if using a configuration file just to make it clearer.
  
**example**

```bash
-# "This is a comment"
```
___

#### -duet [ip address]

**Mandatory - This is a required option.**  The parameter is the network location of your duet printer.  It can be given as a hostname or an explicit ip address.
As a simple test - a browser should be able to access the Duet Web Controller using "http://<ip address>" from the same computer that is running DuetLapse3.py.
  
**example**

```text
-duet 192.168.1.10     #Connect to the printer at 192.168.86.10
-duet localhost        #Connect to the printer at localhost
```

___

#### -basedir [full path name]

If omitted - the default dir is the location of DuetLapse3.py.  This is the logical root for output files See Directory Structure (below).

**example**

```text
-basedir /home/pi/mydir  #output files start at /home/pi/mydir
```

___

#### -instances [single||oneip||many]

If omitted - the default is single. Used to control the number of instances of DuetLapse3.py that can run simultaneously.
In most cases the default will be suitable.

**example**

```text
-instances single   #There can only be one instance of DuetLapse3.py running
-instance oneip     #For each printer (set by -duet), there can only be one
                    #instance of DuetLapse3.py running
-instances many     #No restriction on the number of instances
```

___

#### -logtype [console||file||both]  -- DEPRECATED (see -nolog))

If omitted - the default is both

**example**

```text
-logtype console   #Only send messages to the console
-logtype file      #Only send messages to the logfile.
                   #See Directory Structure for logfile name and location
-logtype many      #Send messages to both the console and file
```

___

#### -nolog

If omitted - the default is False
Logging will always use the console.  A logfile will be created unless -nolog is used.

**example**

```text
-nolog console   #Only send messages to the console
```

___

#### -verbose

If omitted the default is False
Causes the output of system calls and more detailed messages to be logged.
Should usually only be used for debugging.

**example**

```text
-verbose       #Causes addidtional logging information 
```

#### -poll [seconds]

If omitted the default (and minimum) is 10 seconds.  This is the time between checking to see if am image needs to be captured.
If -seconds (see below) is less than -poll then poll is reduced to the value of -seconds.

___

#### -host [ip address]

If omitted the default is 0.0.0.0
Generally this can be left out (default) as it will allow connection to the http listener from <http://localhost:[port]> (locally) or from another machine with network access using <http://actual-ip-address-of-server-running-DuetLapse3[port]>

**example**

```text
-host 192.168.86.10      #Causes internal http listener (if active) to listen
                         #at ip address 192.168.86.10
```

___

#### -port [port number]

If omitted the default is 0 AND the internal http listener is NOT started.
Typical choices for port numbers will br greater than 8000.
The selected port number MUST be different to one already in use.
**The http listener is only start if a port number is specified**

**example**

```text
-port 8082      #Causes internal http listener to start and listen on port 8082
```

___

#### -standby

If omitted the default is False
This option will cause DuetLapse3 to wait for a start command from the http listener or M3291 (depending on version) command before capturing images.
It is useful for having DuetLapse running but not actually doing anything until commanded to do so.
This option takes precedence over -dontwait.

___

#### -restart

If omitted the default is False
If set, the DuetLapse3 will restart at the end of a print job into the same state that it was originally started (i.e. start or standby)
___

#### -dontwait

If omitted - the default is False

**example**

```text
-dontwait    #Images will be captured immediately (without first waiting for a layer change)
             # if -seconds > 0.
             #Otherise images will first start being captured on the first
             #layer change or pause (see -detect).
             # The -pause option is not be used until the first layer is printed
```

***Note:** If -pause yes is used with dontwait, the program will capture images (based on -seconds) before printing starts.
** Pauses and any -movehead repositions will NOT happen until after the first layer is complete. **
___

#### -seconds [seconds]

If omitted the default is 0 seconds (i.e. ignored). Can be any positive number greater then or equal to 20.
The number of seconds is adjusted in the program to be a multiple of the default polling interval. 

**example**

```text
-seconds 40  #Images will be captures approximately every 40 seconds
```

***Note:** If used with -pause be careful not to set -seconds too low.  Doing this can lead to a lot of non-printing head repositioning which can result in poor print quality.* 
___

#### -detect [layer||pause||none]

If omitted the default is layer.

**example**

```text
-detect layer     # Will capture an image on each layer change
-detect pause     # Will capture an image if the printer is paused by the print gcode
                  # **M226**
                  # A manual pause is treated the same as one imbeded in the print gcode
-detect none      # Will not capture an image other than as secified by -seconds
```

***Notes on the use of -detect pause**
When a pause is detected in the print gcode (supplied by an M226) an image will be captured and a resume print command issued.
The head position during pauses is controlled by the pause.g macro on the duet,
and "-movehead Xposition Yposition".
See the notes on pause.g in the section on -pause*

**-detect pause CANNOT be used at the same time as -pause yes**

___

#### -pause [yes||no]

If omitted the default is no. If - pause yes the program will pause the printer when an image is captured.
The print job can be manually paused / resumed in the normal manner.

**example**

```text
-pause yes      #Pause the printer each time an image is captured.
```

***Notes on the use of -pause yes**
DuetLapse3 will pause the printer each time an image is to be captured.
The head position during pauses is controlled by the pause.g macro on the duet,
and by specifying "-movehead Xposition Yposition". If both are specified pause.g will run first then -movehead will reposition the heads. **You may want to edit pause.g to remove the head park gcode (see example below) if you want to use movehead**
If you use -detect layer as well, be careful with prints that have areas with quick layer changes as frequent pauses can cause poor print quality.*

**See also -rest**

Example pause.g

```text
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
___

#### -movehead [Xposition,Yposition]

if omitted the head is not moved - equivalent to -movehead 0,0.  Specifies a position to move the head to before capturing an image.
Valid positions must be greater than 0.0 and less than the maximum allowed by your printer

**example**

```text
-movehead 10,5    #Will move the head to X=10, Y=5 before capturing an image
```

***Note:** The pause.g macro will run first then -movehead will reposition the heads. 
After the image is captured resume.g is run
**If you use -movehead, it is better if pause.g does not reposition the heads as well (see comments above).**
___

#### -rest [seconds]

If omitted the default is 1 second. Can be 0 or any positive number.
Delays image capture after a pause to allow the image source (e.g. web camera) to "catch up". There is usually some delay in image availability relative to the actual position of the print head. if -rest is too short, the print head may not appear to be stationary (or in the correct position) in the video.

**example**

```text
-rest 3  #Images will be captures 3 seconds after a pause
```

___

#### -extratime [second]

If omitted the default is 0.  When creating the video - extends the duration of the last frame by the specified number of seconds.

**example**

```text
-extratime 10     #Makes the last frame captured 10 seconds long
```

***Notes on the use of - extratime**
Applies to the last frame captured.  So if, for example, your print job moves the Z axis at the end of the print.  The last frame would occur when the Z axis stops moving - not when the last layer is printed.*
___

#### -camera1 [usb||pi||web||stream||other]

If omitted the default is usb. Determines how images are captured.
**-camera pi is deprecated (see notes below)**

**example**

```text
-camera1 usb      #Uses the camera associated with fswebcam
-camera1 pi       #Uses the camera associated with the rasberry pi
                  #camera's standard installation
-camera1 web      #Uses wget to capture images from a camera that
                  #provides still jpeg
-camera1 stream   #Uses ffmpeg to capture images from a video feed
-camera1 other    #Can only be used in conjunction with -camparam1
                  #(see below)
```

**Note: If you are using a Raspberry Pi camera there can be issues using -camera pi. The defaults for the Pi camera can lead to problems when creating the video.  This is because there may not be enough RAM (depends on your Pi model).**

At this time(start 2023), the recommended approach is to use streaming software e.g. [videostream] (https://github.com/stuartofmt/videostream) with the -size 2 option works as a good starting point. 

**Example option settings**

```text
-weburl1 http://camera-url
-camera1 stream
```

If you just want to use the pi camera directly, then the following is recommended:

**For Raspberry pi earlier than the Bullseye release:**

```
-camera1 other  -camparam1 "'raspistill -t 1 -w 1280 -h 720 -ex sports -mm matrix -n -o ' + fn + debug"
```

**For Raspberry pi with Bullseye release (and later):**
**Note that because of the way the pi libraries are coded, there is a difference when using -verbose and not using -verbose**


**If NOT using -verbose**

```text
-camera1 other  -camparam1 "'libcamera-still -t 1 --nopreview --width 1640 --height 1232 -o ' + fn + debug"
```

**If using -verbose**

```text
-camera1 other  -camparam1 "'libcamera-still -t 1 --nopreview --width 1640 --height 1232 -o ' + fn + debug + ' 2>/dev/null'"
```

___

#### -weburl1 [url]

If omitted it has no value. url specifies the location to capture images for camera1. Only used for -camera1 of types web, stream, or other

**example**

```text
-weburl http://192.168.86.10/stream  #capture images from this location
```

___

#### -camera2 [usb||pi||web||stream||other]

If omitted has no default (unlike camera1). Has the same parameters as -camera1
___

#### -webur2 [url]

Has the same parameters as -weburl2
___

#### -camparam1="[command]"

If omitted has no default. Used in conjunction with -camera1 to define how the images will be captured.

**Note the use of quoting of the command string.**
**Single quotes should be used inside the command string when quotes are needed.**
**Also not the need for a space at the end of the inner quote before appending a placeholde**
There are 3 placeholder literals that can be used.  These are weburl, fn and debug.  **You do not put in your own values.** They are calculated at runtime:

- weburl take the value of weburl1
- fn represents the image filenames
- debug represents the state of -verbose

**example**

```text
-camera1 other
-camparam1="'ffmpeg -y -i '+weburl+ ' -vframes 1 ' +fn + debug"
```

This example above is the same as if -camera1 stream was used. The value of weburl1 would be substituted for weburl and the output goes to the runtime file fn. The results are detailed if -verbose was set.  Both and fn and debug should be used.  The use of weburl would depend on the capture method.

***Notes on the use of -camparam1**
The following are the standard commands for reference.*

-camera usb
'fswebcam --quiet --no-banner '+fn+debug

-camera pi
'raspistill -t 1 -ex sports -mm matrix -n -o '+ fn + debug

-camera stream
'ffmpeg -y -i '+weburl+ ' -vframes 1 ' + fn + debug

-camera web
'wget --auth-no-challenge -nv -O '+fn+' "'+ weburl + '" ' + debug
___

#### -vidparam1="[command]"

If omitted has no default. Defines an alternate video capture command.  If provided - it is used instead of the standard capture command.

***Note the use of quoting of the command string.**  Single quotes should be used in the command string when needed.
There are 3 placeholder variables that MUST BE USED  **Do not substitute actual values for these.**

basedir (has the same meaning as -basedir),

cameraname signifies the first camera,

tmpfn (which is the temporary output file) and optionally,

debug (which controls verbose logging).

In the following example (which uses ffmpeg) , the elements that you would change are:  **-r 10** and **-vcodec libx264 -y**  the rest would be used without change.

You can use another video creation application if you wish.

**example**

```text
-vidparam1="'ffmpeg -r 10 -i '+basedir+'/'+duetname+'/tmp/'+cameraname+'-%08d.jpeg -vcodec libx264 -y '+ tmpfn + debug"
```

This example is the same as the standard video creation.
___

#### -camparam2 and -vidparam2

Have the same parameters as -camparam1 and -vidparam1.  Variable references are for Camera2
___

#### -keeplogs

If omitted the default is False
If **-keeplogs** is NOT used.  The FIRST instance of DuetLapse3 (with no other instances running) will delete the old logfiles.  If -keeplogs is used then the logfiles will not be deleted.  This means that if you typically use -keeplogs you can affect a cleanup by running a single instance of DuetLapse3 without -keeplogs.
___

#### -deletepics

If omitted the default is False
if **-deletepics** is used.  When DuetLapse3 terminates - basedir/computername/duetip/processid directory will be deleted (i.e. the images will be deleted).
___

#### -novideo

If omitted the default is False
If **-novideo** is used. When DuetLapse3 terminates - no video will be created.  If BOTH **-novideo** and **-deletepics** are specified- this means that if you want to use the images you need to have done so before terminating that instance of DuetLapse3. For example using the snapshot feature provided by the html listener.
___

#### -keepfile

If omitted the default is False
If **-keepfiles** is used. When DuetLapse3 starts or terminates - no files are deleted.  If BOTH **-keepfiles** and **-deletepics** are specified deletepics is ignored.
___

#### -maxffmpeg

If omitted the default is 2
When DuetLapse3 tries to create a video it will fail if ffmpeg runs out of system resources (e.g. CPU / Memory).
This option limits the number of concurrent ffmpeg instances.

**example**

```text
-maxffmpeg 5       #Allows up to 5 instances off ffmpeg to run concurrently
```

___

#### -fps [frames-per-second]

If omitted the default is 10
Sets the default frames-per-second when the snapshot button is used.

**example**

```text
-fps 20       #Causes videos to be created at 20 frames-per-second

```

___

#### -minvideo [seconds]

If omitted the default is 5 seconds
If there are not enough frames to create a video of this length, no video will be created.

**example**

**example**

```text
-fps 15
-minvideo 10  # Would need 150 frames to be captured before a video is created
```

___

#### -maxvideo

If omitted there is no limit on the length of the video.
Sets the maximum length for the resulting video by adjusting the frames-per-second. There is a lower limit of one frame-per-second.

**example**

```text
-fps 15
-maxvideo 10  # Ignores fps and calculates the frame rate to achieve 10 seconds of video
```

___

#### -hidebuttons

If omitted the default is False
Hides menu buttons that are currently invalid - otherwise, invalid buttons are greyed out

**example**

```text
-hidebuttons       #Hides menu buttons that are invalid

```

___
#### -execkey [string]

If omitted the feature is disabled.
If used, the string should be something unique and unlikely to appear in an M3291 message by accident.
See the following document for more details:

[Controlling with gcode.md](https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/Controlling%20with%20gcode.md)

**example**

```text
-execkey :do: # M3291 messages starting with :do: will treated as an OS command.
```

#### -password [string]

If you have a password set on your Duet3D you will need to use this option.
  
**example**

```bash
-password mypassword
```

___

### Directory Structure

The directory structure is described below.  Repeating units are shown with [].

```text
basedir/
   |
   computername/
   |   |
   |   duetip/
   |      |
   |      |processid_sequence_jobname/         #_jobname if available
   |      |
   |      |[/processid_sequence_jobname]
   |
   |
   [computername 
     #repeat of structure above
   ]         
```

The interpretation is:
Starting from the basedir:

- [1] For each computer that DuetLapse3 is running on there will be a separate directory(computername).  Technically the computername will be the fully qualified domain name (FQDN).  Each computer needs to have a unique FQDN.
- [2] Underneath the computername directory  there will be a separate directory for each Duet that computer is connected to (duetip).   All videos for this computer and duet combination go into this directory as well as the respective logfiles.
- [3] Underneath the duetip directory will be joblevel directories (processid_sequence_jobname). Sequence numbers are incremented for each job. If the current printjob has not started there will be no _jobname portion.

**Note:**

- [1]  Videos and logfiles are prefixed by the processid_sequence.
- [2]  Spaces in filenames are replaced by underscrore.
- [3]  Initially, the logfile will be of the form startup.log
- [4]  After the jobname is known, the logfile will be renamed to processid_sequence_jobname.