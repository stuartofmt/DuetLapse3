# Controlling DuetLapse3 with gcode


DuetLapse3, among other things, monitors messages generated with the gcode M291.
Three message forms will cause the program to react.

- [1]  Control DuetLapse3.
- [2]  Change a DuetLapse3 option
- [3]  Have DuetLapse3 execute another program.

M291 gcode messages can be embedded in the print file, placed in a macro as part of a print job, or sent from the DWC console.

**Note that as a practical matter, controlling DuetLapse with M291 messages only works with a single instance of DuetLapse3 connected to a single printer.**

**Note that M292 messages intended to be processed by DuetLapse3 should not be actioned by a user e.g. from DWC**

## Control DuetLapse3

M291 messages can be used to control DuetLapse3 using the following form:

```text
M291 P"DuetLapse3.(x)" S2
```

**Note the mandatory use of P, "", and S2**

The following controls are available:
start, standby, pause, continue, restart, snapshot, completed, graceful, forced

These correspond to the same actions in the UI.
Note that **terminate** is not supported.  Instead use `graceful` or `forced` depending on your need.

e.g. Change DuetLapse3 from `standby` to `start`

```text
M291 P"DuetLapse3.start" S2
```

## Change a DuetLapse3 option

M291 messages can be used to change DuetLapse3 options using the following form:

```text
M291 P"DuetLapse3.change.(variable)=(value)" S2
```

The following variables are supported:
verbose, seconds, poll, detect, dontwait, pause, movehead, restart, novideo, keepfiles, minvideo, maxvideo, extratime, fps, rest , execkey

e.g. Change -seconds to 60

```text
M291 P"DuetLapse3.change.seconds=60" S2
```

## Execute another program

M291 messages can be used to have DuetLapse3 execute another program using the following form:

```text
M291 P"(execkey) (program to run)" S2
```

The character sequence specified by -execkey is used to identify the command. For example if -execkey was `:do:` the following message will attempt to run `test.sh "hello world"`

```text
M291 P":do: ./test.sh %22hello world%22" S2
```

Note: Anything that needs to be quoted inside the message i.e. in the command portion, needs to be percent encoded.

%22 --> double quote
%27 --> single quote

## Test Example

This example demonstrates controlling DuetLapse3 using M291 messages.
It does not print anything but simulates a small print job.
DuetLapse3. Messages are both inline (in the gcode) and called inside a macro.

Copy the following file to your printer job folder:

[M291Test.gcode](https://github.com/stuartofmt/DuetLapse3/blob/main/Examples/M291Test.gcode)

and this file to the macro folder:

[test_job_settings.g](https://github.com/stuartofmt/DuetLapse3/blob/main/Examples/test_job_settings.g)

Optionally (Linux only) create a file **test.sh** in the DuetLapse3 directory.

```bash
#!/bin/bash
echo "-----------"
echo "$1 $2"
echo "----------"
```

Don't forget to make the file executable:

```bash
chmod + x ./test.sh
```

Start DuetLapse3 with the following suggested options, in addition to those needed for -duet and -camera:
-restart -verbose -standby -keepfiles

## Note

- [1]  The use of M291 P"DuetLapse3.standby" S2  early in the print job (in the macro) to prepare for capture.
- [2]  The use of M291 P"DuetLapse3.start" S2 to control when capture will start.
- [3]  The use of M291 P"DuetLapse3.complated" S2  to indicate when capture will stop.

Placement of these options allows fine control over the timelapse.  This is especially useful if -restart is used and DuetLapse3 is running continuously.

Macros can be especially useful if running DuetLapse3 continuously.
You could (for example) having a standard set of options that are called at the end of each print job and specific macros (layer only, layer and time, time only, different -second settings etc.) for certain type of timelapse.
Embedding these macro calls from your slicer makes easy use of this functionality.

## Further Examples

```text
M291 P"DuetLapse3.standby" S2   # Will place the program into standby
```

```text
M291 P"DuetLapse3.start" S2    # Will start capturing image
```

```text
M291 P"DuetLapse3.change.verbose=False" S2   #  will turn of verbose output
```

```text
M291 P"DuetLapse3.change.seconds=60" S2   # Will capture an image every 60 seconds
```

```text
M291 P"DuetLapse3.change.movehead=1,200" S2   # move the print head (x=1, Y=200) if pause=yes is used
```
