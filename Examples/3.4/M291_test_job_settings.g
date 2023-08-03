; Version 3.4
;
; Example Macro for setting M291 messages to control 
; DuetLapse3
;
M117 Running test job  macro
;
M291 P"DuetLapse3.change.verbose=True" S0 T15 ; Turn on verbose logging
;
M291 P"DuetLapse3.standby" S0 T15   ; Makes sure there is a clean set of directories. Ignored if -standby used
;
M291 P"DuetLapse3.change.seconds=25" S0 T15
;
M291 P"DuetLapse3.change.minvideo=1" S0 T15
;
M291 P"DuetLapse3.change.extratime=4" S0 T15
;
M291 P"DuetLapse3.change.detect=layer" S0 T15
;