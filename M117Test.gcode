; Test gcode file for demonstrating DuetLapse3. style messages
;
M98 P"/macros/test_job_settings.g"
;
T0             ; turn on the tool
M561           ; Remove any Bed Compensation
G90 ; use absolute coordinates
M83 ; extruder relative mode
;
M117 :do: ./test.sh "Test Job1"
G4 S10
;
G28 ; home all
;
M117 :do: ./test.sh "Home Completed"
G4 S10
;
;
M117 DuetLapse3.start   ; start
G4 S10
;
G0 X0 X0
G0 X100 X100
;
G4 S180 ; enough time for > 1 sec of video
;
G0 X0 X0
G0 X100 X100
;
M117 DuetLapse3.completed   ; Job done
G4 S10
;
M0
