# startDuetLapse3
 
This is am optional helper program for use with DuetLapse3.
It provides a simple http interface for starting and terminating DuetLapse3 instances.


### Version 3.2.0
- [1]  Initial version.  Requires DuetLapse3 at version 3.2.0 or higher

### Version 3.2.1
- [1]  A minor change to prevent system messages when stopped with CTRL+C

### Version 3.2.2
- [1]  Made some cosmetic changes to the http responses.  Most now include the local time as part of the response.
- [2]  The status page will automatically refresh every 60 seconds.  Other pages will show the last time they were invoked.

### Version 3.2.3
- [1]  Fixed some inconsistencies when running on Windows due to slightly different behavior of python3.

### Version 3.3.0
- [1]  Completely revised the UI with the addition of buttons to make navigation easier.
- [2]  Added the ability to directly enter the start options for DuetLapse3.
- [3]  Added an optional argument (-args) to set default options for starting DuetLapse3

### Version 3.4.0
- [1] Changed how http terminate requests were handled for better cross-platform compatibility.
- [2] Added the ability to navigate the directory structure from a browser (new button)
- [3] Made some cosmetic changes to the html pages.

### Version 3.4.1
- [1] Changed the browser UI to a single page layout.
- [2] Added an optional argument (-topdir) to set the top level directory for file functions.
      If used - this would normally be set the same as DuetLapse or at the "duet ip" level
- [3] File functions expanded to allow "delete" and "zip".  This is "conservative" - will not allow deletion of files / directories of running instances.  Can only zip directories. 

### Version 3.4.2
- [1] Can now delete empty directories (provided they are not in use). This allows a complete cleanup of the directory tree.
- [2] Added file function to create a Video on directories containing jpeg files (provided they are not in use).
- [3] Added an optional argument (-maxffmpeg) that limits the number of concurrent ffmpeg instances.  Ffmpgeg can fail due to lack of resources - the default is 2 instances.

### Version 3.5.0

- [1]   Changed some system calls to allow for better error handling
- [2]   Updated documentation with additional notes
- [3]   Added a default logfile (startDuetLapse3.log)
- [4]   Added a new argument -nolog.  Logging will always use the console unless the program is running in the background.
- [5]   Added a new argument -verbose. Creates detailed debugging information.
- [6]   Failure to start DuetLapse3 (from the UI) is reported with reasons.  Successful starts are reported after 30 seconds.
- [7]   Shutdown, from the UI, requires confirmation.
- [8]   The use of http option nohup=yes is deprecated.
- [9]   Added new argument -fps.  Sets the default frames-per-seconds
- [10]  Added the ability to change the default frames-per-second (fps) when creating a video from the files menu.
- [11]  General UI improvements.

### Version 3.5.1
- [1]  Some minor improvements / bug fixes.
- [2]  Fixed an issue if logfile directory is missing.
- [3]  Restricted CPU utilization on video creation.


### Version 4.0.0
- [1]  ????.
- [2]  ????.
- [3]  ????.

## General Description

startDuetLapse 3 is designed to run continuously and accept http commands either from a browser, curl or other means of sending http get commands.<br>
It is used to start DuetLapse3 instances without the need of a separate script by passing the options as part of the http message.<br>
To avoid misuse - options are checked for validity before any attempt to start DuetLapse3.<br><br>
It can also terminate specific or all instances of DuetLapse3.

Only one instance of startDuetLapse3 can be running.

Feedback via issues on Duet forum https://forum.duet3d.com/topic/20932/duetlapse3

## Requirements 

* Python3 V3.7 or greater (must be accessible without specifying the path)
* Linux OS,  Windows 10, Windows Subsystem Linux (WSL) tested
* DuetLapse3 at version 3.5.0 or greater.

**Note that startDuetLapse3 will NOT run without DuetLapse3 being present and in the same directory.**<br>
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

Take note of editing the path variable(s) so that python3, and it's /libraries/modules can be found during execution.
  
## Usage

startDuetLapse runs as a http listener<br>
The http listener requires a port number using the -port option.<br>
Additionally a  -host option is provided but usually this can be omitted.

startDuetLapse3 can be started from the command line or, more usually using systemctl (not available on Win10 or WSL) or equivalent
.<br>
It is usually run in the background.<br>
Sample instructions for setting up using systemctl are here https://github.com/stuartofmt/DuetLapse3/blob/main/timelapse

```
Example command line for running startDuetLapse3 in the background (linux)

python3 ./startDuetLapse.py -port 8082 &

or if you plan to close the command console - use nohup

nohup python3 ./startDuetLapse.py -port 8082 &
```
If you provide the option -args, special care needs to be made in formatting it correctly.  In the example below note the following:
- [1]  double quote characters around the entire -args options list
- [2]  the use of ```&quot;``` and ```&apos;``` for all other double or single quotes inside the outer quotes used for the -args options list.

```
python3 ./startDuetLapse3.py -port 8082 -args="-duet 192.168.86.235 -port 8083 -standby -dontwait -seconds 15 -detect none -weburl1 http://192.168.86.230:8081/stream -camera1 other -camparam1=&quot;&apos;ffmpeg&apos; +ffmpegquiet + &apos; -y -i &apos; +weburl+ &apos; -vframes 1 &apos; +fn+debug&quot;"
```



On Windows things are slightly different - note the use of pythonw
which will run python in the background (tested with python 3.9)
 
```
Example command line for running startDuetLapse3 in the background (windows)
Note the use of pythonw and the output files to check if everything was successful

pythonw startDuetLapse3.py -port 8082 > startDuetLapse3.log 2>&1

```

If the script is run in foreground it can be shutdown using CTRL+C (on linux) or CTRL+Break (on Windows).<br>
If the script is run in background it can be stopped using http with command=shutdown.

**Note that the http listener will stop responding if startDuetLapse3 is run from a command console that is then closed.<br>
This will happen even if started in background.<br>
To avoid this - use nohup (linux) or start with pythonw (on Windows)<br>
An alternative if you are on Win10 is to use  Windows Subsystem for Linux (WSL) and run startDuetLapse as a linux application inside WSL.<br>**



startDuetLapse3 is typically controlled from a browser using the buttons and inputs (as of release 3.3.0).  The buttons essentially invoke the following commands.
These can still be used manually or invoked without the browser UI (for example using curl).  As of release 3.4.1 the response is html - so it needs to be handled accordingly.

```
http://<ipaddress>:<port>/?{instructions}

```

Valid {instructions} are:


command=status                     - Returns brief information about the running state of DuetLapse3 instances
                                     For each instance it proved the process id together with the options used to start the instance
                      
----

command=start&args=       - Starts an instance of DuetLapse3 with the options specified in args
NOTE IF ENTERED FROM THE BROWSER ADDRESS LINE certain symbols must be made url safe.  For example the + symbol must be replaced with %2b.  This is not required if using the input field in the UI.


```
Example

http://localhost:8082/?command=start&args=-duet 192.168.86.235 -detect none -seconds 15 -standby -port 8083 -camera1 stream -weburl1 http://192.168.86.230:8081/stream

```

**THE USE OF NOHUP IS DEPRECATED**

```
nohup=yes               - Will run DuetLapse3 with nohup (on Linux).  If on Windows the program will substitute pythonw.
                          Note that it is not part of the command=start&args= but a separate command
                          In most situations (startDuetLapse3 running in background) you will NOT need to use this option

```
Example

http://localhost:8082/?nohup=yes&command=start&args=-duet 192.168.86.235 -detect none -seconds 15 -standby -port 8083 -camera1 stream -weburl1 http://192.168.86.230:8081/stream

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

----

delete={name}                      - {name} is a filename or directory name RELATIVE to the -topdir setting

```
Example
Assuming -topdir is set to /home/pi/me.local/192-168-1-230
http://localhost:8082/?delete=/123454/     #Will delete the directory /home/pi/me.local/192-168-1-230/123456

Assuming -topdir is set to /home/pi/me.local
http://localhost:8082/?delete=/192-168-1-230/Camera1.mp4/     #Will delete the file /home/pi/me.local/192-168-1-230/Camera1.mp4
```

----

zip={dir}                          - {dir} is a directory name RELATIVE to the -topdir setting  

```
Example
Assuming -topdir is set to /home/pi/me.local/192-168-1-230
http://localhost:8082/?zip=/123454/     #Will create the file /home/pi/me.local/192-168-1-230/123456.zip
Note that zip ONLY works on directories
```

----


### Options

Options can be viewed with

```
python3 startDuetLapse3.py -h
```

The response will give the version number at the top.

The options are described here.  Each option is preceded by a dash -. Some options have parameters described in the square brackets.  Note the square brackets are NOT used in entering the options. If an option is not specified the default used.


#### -host [ip address]
If omitted the default is 0.0.0.0<br>
Generally this can be left out (default) as it will allow connection to the http listener from localhost:<port> (locally) or from another machine with network access using <actual-ip-address-of-server-running-DuetLapse3><port>.

```
**example**

-host 192.168.86.10      #Causes internal http listener (if active) to listen at ip address 192.168.86.10<br>

```

#### -port [port number]
This option is mandatory.<br>
If the selected port is already in use the program will not start

```
**example**

-port 8082      #Causes internal http listener to start and listen on port 8082<br>

```

#### -topdir [full path name]
If omitted - the default dir is the location of startDuetLapse3.py. 

```
**example**

-topdir /home/pi/mydir  #output files start at /home/pi/mydir

```

#### -maxffmpeg [number]
If omitted the default is 3
When DuetLapse3 tries to create a video it will limit the number of ffmpeg instances running to the specified number.  This can prevent ffmpeg failing because it cannot get resources (e.g. CPU / Memory)


#### -nolog
If omitted - the default is False
Logging will always use the console.  A logfile will be created unless -nolog is used.

```
**example**

-nolog console   #Only send messages to the console

```

#### -verbose
If omitted the default is False
Causes the output of system calls and more detailed messages to be logged.
Should usually only be used for debugging.

```
**example**

-verbose       #Causes addidtional logging information 

```

#### -fps
If omitted the default is 10
Sets the default frames-per-second when the video button is used.

```
**example**

-fps 20       #Causes videos to be created at 20 frames-per-second

```