; Version 3.5+
; Example Macro for setting M291 messages to control 
; DuetLapse3
;
M117 "Running test job  macro"
;
M3291 B"DuetLapse3.change.verbose=True"  ; Turn on verbose logging
;
M3291 B"DuetLapse3.standby"    ; Makes sure there is a clean set of directories. Ignored if -standby used
;
M3291 B"DuetLapse3.change.seconds=25" 
;
M3291 B"DuetLapse3.change.minvideo=1" 
;
M3291 B"DuetLapse3.change.maxvideo=2" 
;
M3291 B"DuetLapse3.change.extratime=4" 
;
M3291 B"DuetLapse3.change.detect=layer" 
