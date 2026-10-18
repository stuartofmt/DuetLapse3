; M3291 - pass a command to duetLapse3, e.g. from the slicer's start or end gcode
;
; Usage (one command per call):
;   M3291 B"duetLapse3.start"
;   M3291 B"duetLapse3.change.capture_seconds=30"
;
; How it works: global.DL3seq counts the commands, and each one is kept in global.DL3msg, a ring of the last
; few commands, at index DL3seq mod the ring size.  duetLapse3 only reads them: it remembers the last count
; it handled and acts on any newer commands.  Needs RepRapFirmware 3.5 or later (mod).
;
; Version 2.0

if !exists(param.B)
	echo "M3291: no B parameter - e.g. M3291 B""duetLapse3.start"""
	M99

if !exists(global.DL3seq)
	global DL3seq = 0
	global DL3msg = vector(10, "")   ; The ring size - duetLapse3 reads it from the array

set global.DL3seq = global.DL3seq + 1
set global.DL3msg[mod(global.DL3seq, #global.DL3msg)] = param.B
