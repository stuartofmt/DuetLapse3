# startDuetLapse3
 
This is am optional helper program for use with DuetLapse3.
It proveds a simple http interface for starting and terminating DuetLapse3 instances.



###Version 3.2.0###
- [1]  Initial version.  Requires DuetLapse3 at version 3.2.0 or higher

###Version 3.2.1###
- [1]  A minor change to prevent system messages when stopped with CTRL+C

## General Description

startDuetLapse 3 is designed to run continuously and accept http commands either from a browser, curl or other means of sending http get commands.<br>
It is used to start DuetLapse3 instances without the need of a separate script by passing the options as part of the http message.<br>
To avoid misuse - options are checked for validity before any attempt to start DuetLapse3.<br><br>
It can also terminate specific or all instances of DuetLapse3.


Feedback via issues on Duet forum https://forum.duet3d.com/topic/20932/duetlapse3

## Requirements 

* Python3 (must be accessible without specifying the path)
* Linux OS,  Windows 10, Windows Subsystem Linux (WSL) tested
* DuetLapse3 at version 3.2.0 or greater.

Note that startDuetLapse3 will NOT run without DuetLapse3 being present.<br>
It imports key functions from DuetLapse3

## Installation
Note that startDuelLapse3 needs to be installed in the same directory as DuetLapse3

For Linux:<br>
* cd to the directory you installed DuetLapse3
* wget https://github.com/stuartofmt/DuetLapse3/raw/main/startDuetLapse3.py
* chmod 744 startDuetLapse3.py

For windows<br>
Follow the instructions from one of the web sources to install python3 - for example:<br>
https://docs.python.org/3/using/windows.html 

Take note of editing the path variable(s) so that python3 and it's /libraries/modules can be found during execution.
  
## Usage

startDuetLapse runs as a http listener<br>
The http listener requires a port number using the -port option.<br>
Additionally a  -host option is provided but usually this can be omitted.

startDuetLapse3 can be started from the command line or, more usually using systemctl (not available on Win10 or WSL) or equivalent
.<br>
It is usually run in the background.<br>
Sample instuctions for setting up using systemctl are here https://github.com/stuartofmt/DuetLapse3/blob/main/timelapse

```
Example command line for running startDuetLapse3 in the background (linux)

python3 ./startDuetLapse.py -port 8082 &

or if you plan to close the command console - use nohup

nohup python3 ./startDuetLapse.py -port 8082 &
```
On windows things are slightly different - note the use of pythonw
which will run python in the background (tested with python 3.9)
 
```
Example command line for running startDuetLapse3 in the background (windows)
Note the use of pythonw and the output files to check if everything was successful

pythonw startDuetLapse3.py -port 8082 1>stdout.txt 2>stderr.txt

```

If the script is run in foreground it can be shutdown using CTl+C.<br>
If the script is run in background it can be stopped using http with command=shutdown.

**Note that the http listener will stop responding if startDuetLapse3 is run from a command console that is then closed.<br>
This will happen even if started in background.<br>
To avoid this - use nohup (linux).<br>
Windows does not have an (easy) equivalent to nohup so you would need to leave the command console open.<br>
An alternative if you are on Win10 is to use  Windows Subsystem for Linux (WSL) and run startDuetLapse as a linux application inside WSL.<br>**



startDuetLapse3 is typically controlled from a browser with commands of the form:

```
http://<ipaddress>:<port>/?<commands>

```

<pre>
Valid commands are:
command=status            - Returns brief information about the running state of DuetLapse3 instances
                            For each instance it proved the process id together with the options used to start the instance
----
command=start&args=       - Starts an instance of DuetLapse3 with the options specified in args

```
Example

http://localhost:8082/?command=start&args=-duet 192.168.86.235 -detect none -seconds 15 -standby -port 8083 -camera1 stream -weburl1 http://192.168.86.230:8081/stream.mjpg

```

nohup=yes               - Will run DuetLapse3 with nohup (only use on Linux).
                          Note that it is not part of the command=start&args= but a separate command
                          In most situations (startDuetLapse3 running in background) you will NOT need to use this option

```
Example

http://localhost:8082/?nohup=yes&command=start&args=-duet 192.168.86.235 -detect none -seconds 15 -standby -port 8083 -camera1 stream -weburl1 http://192.168.86.230:8081/stream.mjpg

```

----
command=terminate&pids=  - causes DuetLapse3 to terminate depending on the option specified in pids

```
Example

http://localhost:8082/?command=terminate&pids=all     #Will cause ALL instances of DuetLapse3 to terminate

http://localhost:8082/?command=terminate&pids=12345   #Will cause DuetLapse3 with process id 12345 to terminate 

```
----
command=shutdown   - causes startDuetLapse3 to shutdown.
</pre>


### Options

Options can be viewed with
```
python3 startDuetLapse3.py -h
```
The response will give the version number at the top.

The options are described here.  Each option is preceded by a dash -. Some options have parameters described in the square brackets (the square brackets are NOT used in entering the options. If an option is not specified the default used.


#### -host [ip address]
If omitted the default is 0.0.0.0<br>
Generally this can be left out (default) as it will allow connection to the http listener from localhost:<port> (locally) or from another machine with network access using <actual-ip-address-of-server-running-DuetLapse3><port>.
<pre>
**example**

-host 192.168.86.10      #Causes internal http listener (if active) to listen at ip address 192.168.86.10<br>
</pre>

#### -port [port number]
This option is mandatory.<br>
If the selected port is already in use the program will not start
<pre>
**example**

-port 8082      #Causes internal http listener to start and listen on port 8082<br>
</pre>
