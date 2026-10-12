; Version 3.5+ 
; Test gcode file for demonstrating DuetLapse3. style messages
; Note the use of layer change comments required since 3.3RC2
; For tracking layer changes
;
M98 P"/macros/M3291_test_job_settings.g"
;
T0             ; turn on the tool
M561           ; Remove any Bed Compensation
G90 ; use absolute coordinates
M83 ; extruder relative mode
;
G28 ; home all
;
G0 Z50 ; move the print head to where it can be seen by camera
;
M3291 B"DuetLapse3.start"    ; start
;
; 30 sec 1 layer simulation
;LAYER_CHANGE
;Z:10
G0 Z10
G0 X80 Y80
G4 S5
G0 X120 Y80
G4 S5
G0 X120 Y120
G4 S5
G0 X80 Y120
G4 S5
;LAYER_CHANGE
;Z:11
G91
G0 Z1 ; move Z down 1mm - simulates a new layer
G90
G4 S10
;
; 30 sec 1 layer simulation
G0 Z10
G0 X80 Y80
G4 S5
G0 X120 Y80
G4 S5
G0 X120 Y120
G4 S5
G0 X80 Y120
G4 
;LAYER_CHANGE
;Z:12
G91
G0 Z1 ; move Z down 1mm - simulates a new layer
G90
G4 S10
;
; 30 sec 1 layer simulation
G0 Z10
G0 X80 Y80
G4 S5
G0 X120 Y80
G4 S5
G0 X120 Y120
G4 S5
G0 X80 Y120
G4 S5
;LAYER_CHANGE
;Z:13
G91
G0 Z1 ; move Z down 1mm - simulates a new layer
G90
G4 S10
;
; 30 sec 1 layer simulation
G0 Z10
G0 X80 Y80
G4 S5
G0 X120 Y80
G4 S5
G0 X120 Y120
G4 S5
G0 X80 Y120
G4 S4
;LAYER_CHANGE
;Z:14
G91
G0 Z1 ; move Z down 1mm - simulates a new layer
G90
G4 S10
;
; 30 sec 1 layer simulation
G0 Z10
G0 X80 Y80
G4 S5
G0 X120 Y80
G4 S5
G0 X120 Y120
G4 S5
G0 X80 Y120
G4 S5
;LAYER_CHANGE
;Z:15
G91
G0 Z1 ; move Z down 1mm - simulates a new layer
G90
G4 S10
;
; 30 sec 1 layer simulation
G0 Z10
G0 X80 Y80
G4 S5
G0 X120 Y80
G4 S5
G0 X120 Y120
G4 S5
G0 X80 Y120
G4 S5
;LAYER_CHANGE
;Z:16
G91
G0 Z1 ; move Z down 1mm - simulates a new layer
G90
G4 S10
;
M3291 B"DuetLapse3.change.seconds=0"    ; stops any timed capture (avoids follow on capture if -restart)
;
M3291 B"DuetLapse3.completed"    ; Stop capturing images at this point
;
; Simulate post completion moves
G91           ;relative mode
G0 Z1         ;E Move the bed away a little. Note use of E after comment for correct layer count
G0 Z10
G90           ;Back to absolute mode 
G0 X100 Y100
G0 Z20
G0 X0 Y0      ;Get the print head out of the way
M400  ; wait for current moves to finish
M117 "Job  complete"