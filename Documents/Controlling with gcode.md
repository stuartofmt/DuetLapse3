## Controlling DuetLapse3 with gcode

The program, among other things, monitors messages generated with the gcode M117 command.
Two message forms will cause the program to react.
- [1]  M117 DuetLapse3.(x) where (x) is one of the allowed settings.
- [2]  M117 (execkey) (command) where (execkey) is a prefix specified by the -execkey option and (command) is an arbitrary command that will be sent to the OS.

M117 gcode messages can be embedded in the print file, placed in a macro, or sent from the DWC console.<br>
**Note that as a practical matter, This functionality assumes a single instance of DuetLapse3 connected to a single printer.**<br>

DuetLapse3 uses a polling method and checks the printer every 5 seconds for M117 messages.<br>
To prevent a message being missed, IT IS MANDATORY that a delay (G4) be added after *every* M117 message intended for this program.<br>
The strong recommendation is that the delay is 10 seconds i.e. **G4 S10**


### M117 DuetLapse3.(x)
In the first form, the following settings are available:<br>
{list}.
These correspond to the same actions in the UI.<br>
Note that **terminate** is not supported instead use **graceful** or **forced** depending on your need.

There is also a special variant which can be used to change options on-the-fly.<br>
This is equivalent to setting an option in the commandline at startup.

```
M117 DuetLapse3.change.(variable)=(value)
G4 S10
```
The following variables are supported:<br>
{list}

Examples
```
M117 DuetLapse3.standby # Will place the program into standy
G4 S10
```

```
M117 DuetLapse3.start # Will start capturing image
G4 S10
```

```
M117 DuetLapse3.change.verbose=False #  will turn of verbose output
G4 S10
```
```
M117 DuetLapse3.change.seconds=20 # Will capture an image every 20 seconds
G4 S10
```

### M117 (execkey) (command)
This form allows an arbitrary command to be executed by the operating system.
The character sequence specified by -execkey is used to identify the command.

For example if -execkey was :do: the following message will attempt to run test.sh
```
M117 DuetLapse3 :do: ./test.sh "hello world"
G4 S10
```
Note: There are no additional single or double quotes used in the M117 gcode.<br>
The command portion is presented as it would be from the command line of the relevent OS.

### Test Example
This example demonstrates controlling DuetLapse3 using M117 messages.
It does not print anything but simulates a small print job.
DuetLapse3. messages are both inline (in the gcode) and called inside a macro.

Copy the following file to your printer job folder:

[M117Test.gcode](https://github.com/stuartofmt/DuetLapse3/blob/main/Examples/M117Test.gcode)

and this file to the macro folder:

[test_job_settings.g](https://github.com/stuartofmt/DuetLapse3/blob/main/Examples/test_job_settings.g)

Optionally (Linux only) create a file **test.sh** in the DuetLapse3 directory.
```
#!/bin/bash
echo "-----------"
echo "$1 $2"
echo "----------"

```
Dont forget to make the file executable:
```
chmod + x ./test.sh
```

Start DuetLapse3 with the following suggested options, in addition to those needed for -duet and -camera:<br>
-restart -verbose -standby -keepfiles 

**Note**
- [1]  The use of M117 DuetLapse3.standby early in the print job (in the macro) to prepare for capture. 
- [2]  The use of M117 DuetLapse3.start to control when capture will start.
- [3]  The use of M117 DuetLapse3.complated to indicate when capture will stop.

Placement of these options allows fine control over the timelapse.  This is especially useful if -restart is used and DuetLapse3 is running continuously.

Macros can be especially useful if running DuetLapse 3 continuously.<br>
You could (for example) having a standard set of options that are called at the end of each print job and specific macros (layer only, layer and time, timeonly, different -second settings etc.) for certain type of timelapse.
Embedding these macro calls from your slicer makes easy use of this functionality.
