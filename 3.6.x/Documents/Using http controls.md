# Using http to control DuetLapse3

Basic control can be achieved by sending http messages in the form:

```html
http://<ip-address><port>/?command=<valid command>
```

___
start      - Starts DuetLapse3 recording if the -standby option was used
             or after a standby command
standby    - Stops (but does not terminate) DuetLapse3 recording
             and discards any images capture.  Waits for a start command.
___
pause      - causes DuetLapse3 to temporarily stop capturing images.
             Note:  This does NOT pause the printer.
continue   - causes DuetLapse3 to resume capturing images.
___

restart    - causes DuetLapse3 to stop capturing images, create a video
             and then restart with a new capture set
___
terminate  - causes DuetLapse3 to stop capturing images, create a video and
             then terminate the program. This is the same as CTRL+C or SIGINT.
             Note: Depending on your system - it may take several minutes
             for the http listener to completely shutdown following a terminate request.
