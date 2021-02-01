# startDuetLapse3
 
This is a helper program for use with DuetLapse3.
It proveds a simple http interface for starting and terminating DuetLapse3 instances.



###Version 3.2.0###
- [1]  Initial version.  Requires DuetLapse3 at version 3.2.0 or higher


## General Description

startDuetLapse 3 is designed to run continuously and accept http commands either from a browser, curl or other means of sending http get commands.<br>
It is used to start DuetLapse3 instances without the need of a separate script by passing the options as part of the http message.<br>
To avoid misuse - options are checked for validity before any attempt to start DuetLapse3.<br><br>
It can also terminate specific or all instances of DuetLapse3.
