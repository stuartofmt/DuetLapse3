; Example Macro for setting M291 messages to control 
; DuetLapse3
;
;M117 Running test job  macro
;
M291 P"DuetLapse3.change.verbose=True" S2 ; Turn on verbose logging
;
M291 P"DuetLapse3.standby" S2   ; Makes sure there is a clean set of directories. Ignored if -standby used
;
M291 P"DuetLapse3.change.seconds=25" S2
;
M291 P"DuetLapse3.change.minvideo=1" S2
;
M291 P"DuetLapse3.change.extratime=4" S2
;
M291 P"DuetLapse3.change.detect=layer" S2
;
M291 P"DuetLapse3.change.pause=yes" S2 ; Cannot use -pause yes with -detect pause
;
M291 P"DuetLapse3.change.execkey=:do:" S2
;
M291 P"DuetLapse3.change.movehead=70,70" S2
