# Controlling DuetLapse3 with gcode

DuetLapse3, among other things, monitors messages generated with the gcode M291 (in Duet3D Releases prior to 3.5) and using a custom gcode M3291 (from Duet3d Release 3.5).
Three message forms will cause the program to react.

- [1]  Control DuetLapse3.
- [2]  Change a DuetLapse3 option
- [3]  Have DuetLapse3 execute another program.

gcode messages can be embedded in the print file, placed in a macro as part of a print job, or sent from the DWC console.

## Control DuetLapse3

### M291 (Deprecated)

For Duet3D release prior to 3.5 ONLY.  M291 messages can be used to control DuetLapse3 using the following form:

```text
M291 P"DuetLapse3.(x)" S0 T15
```

**Note:**

**(1) - There should only be one instance of DuetLapse3 connected to the printer.**

**(2) - M291 message (requiring acknowledgement) should NOT be used for other purposes.**

**(3) - M292 messages should not be actioned by a user e.g. from DWC.**

**Note the mandatory use of P, "", and use of S0 and T15 (non blocking with a timeout)**

The constraints abaove are due to the current (Feb '23) mechanism used by the firmware for M291 messages.


### M3291

Starting with  Duet3D release 3.5, a custom M3291 gcode is used.  This overcomes the limitations of M291 by implementing a "private" message scheme. M3291 uses the the following form:

```text
M3291 B"DuetLapse3.(x)"
```

**Note the use of the B parameter**

Examples in the rest of this document will use the M3291 form

## Control DuetLapse3

The following controls are available:
start, standby, pause, continue, restart, snapshot, completed, graceful, forced

These correspond to the same actions in the UI.
Note that **terminate** is not supported.  Instead use `graceful` or `forced` depending on your need.

e.g. Change DuetLapse3 from `standby` to `start`

```text
M3291 B"DuetLapse3.start"
            
```

## Change a DuetLapse3 option

M291 messages can be used to change DuetLapse3 options using the following form:

```text
M3291 B"DuetLapse3.change.(variable)=(value)" 
```

The following variables are supported:
verbose, seconds, poll, detect, dontwait, pause, movehead, restart, novideo, keepfiles, minvideo, maxvideo, extratime, fps, rest , execkey

e.g. Change -seconds to 60

```text
M3291 B"DuetLapse3.change.seconds=60" 
```

## Execute another program

M291 messages can be used to have DuetLapse3 execute another program using the following form:

```text
M3291 B"(execkey) (program to run)" 
```

The character sequence specified by -execkey is used to identify the command. For example if -execkey was `:do:` the following message will attempt to run `test.sh "hello world"`

```text
M3291 B":do: ./test.sh %22hello world%22" 
```

Note: Anything that needs to be quoted inside the message i.e. in the command portion, needs to be percent encoded.

%22 --> double quote
%27 --> single quote

## Test Example

The following examples demonstrates controlling DuetLapse3 using M291 and M3291 messages.
It simulates a small print job (no heating , no filament use).

### For Duet3D prior to 3.5 (Deprecated) 
Copy the following file to your printer job folder:

[M291Test.gcode](https://github.com/stuartofmt/DuetLapse3/blob/main/Examples/3.4/M291Test.gcode)

and this file to the macro folder:

[test_job_settings.g](https://github.com/stuartofmt/DuetLapse3/blob/main/Examples/3.4/M291_test_job_settings.g)

### For Duet#D from 3.5
Copy the following file to your printer job folder:

[M291Test.gcode](https://github.com/stuartofmt/DuetLapse3/blob/main/Examples/3.5/M3291Test.gcode)

and this file to the macro folder:

[test_job_settings.g](https://github.com/stuartofmt/DuetLapse3/blob/main/Examples/3.5/M3291_test_job_settings.g)


Start DuetLapse3 with the following suggested options, in addition to those needed for -duet and -camera:
-restart -verbose -standby -keepfiles

## Note

- [1]  The use of M3291 B"DuetLapse3.standby"   early in the print job (in the macro) to prepare for capture.
- [2]  The use of M3291 B"DuetLapse3.start"  to control when capture will start.
- [3]  The use of M3291 B"DuetLapse3.completed"   to indicate when capture will stop.

Placement of these options allows fine control over the timelapse.  This is especially useful if -restart is used and DuetLapse3 is running continuously.

Macros can be especially useful if running DuetLapse3 continuously.
You could (for example) having a standard set of options that are called at the end of each print job and specific macros (layer only, layer and time, time only, different -second settings etc.) for certain type of timelapse.
Embedding these macro calls from your slicer makes easy use of this functionality.

## Further Examples

```text
M3291 B"DuetLapse3.standby"    # Will place the program into standby
```

```text
M3291 B"DuetLapse3.start"     # Will start capturing image
```

```text
M3291 B"DuetLapse3.change.verbose=False"    #  will turn of verbose output
```

```text
M3291 B"DuetLapse3.change.seconds=60"    # Will capture an image every 60 seconds
```

```text
M3291 B"DuetLapse3.change.movehead=1,200"    # move the print head to (x=1, Y=200) if pause=yes is used
```
