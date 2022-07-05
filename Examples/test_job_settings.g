;  Example macro using DuetLapse3. style messages
;
M117 Running jobopen macro
G4 S10
;
M117 DuetLapse3.change.verbose=True ; Turn on verbose logging
G4 S10
;
M117 DuetLapse3.standby   ; Makes sure there is a clean set of directories. Ignored if -standby used
G4 S10
;
M117 DuetLapse3.change.seconds=12
G4 S10
;
M117 DuetLapse3.change.minvideo=1
G4 S10
;
M117 DuetLapse3.change.extratime=4
G4 S10
;
M117 DuetLapse3.change.detect=none
G4 S10
;
M117 DuetLapse3.change.dontwait=True
;
M117 DuetLapse3.change.execkey=:do:
G4 S10
