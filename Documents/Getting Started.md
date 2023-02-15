# Getting Started

This is a brief guide to getting started with DuetLapse3. It will provide a set of options sufficient to test for correct operation.

**All these actions should be performed on the computer that has DuetLapse3 installed** This is so that any network issues are discoverd.

**Perform these steps in sequence and do not continue to the next step until everything is validated.**

## 1 -- Install DuetLapse 3

Verify DuetLapse3 is installed correctly by running the following command from the installation folder.  Depending on how you have installed `python`  the command may be `py, python, or python3`

```bash
python ./DuetLapse3.py -h
```

if there are dependencies that need to be installed, this command will identify them.

## 2 -- Identify the ip address of your printer

This is the ip used in the url you use to access DWC.  It should be a static IP addess i.e. does NOT change when the printer restarts.  This ip address is used in the -duet option.

**Example option setting**

```text
-duet 192.168.1.30
```

## 3 -- Prove that your camera is working

Broadly, there are four types of camera commonly used with DuetLapse3

- A camera that delivers still images via a url
- A camera that steams video via a url
- A USB camera
- A Pi camera connected to a Raspberry Pi via a ribbon cable.

Depending on your type of cammera, verify that it is working correctly and is accessible to the computer that will run DuetLapse3, by following the applicable steps below.

### Still image camera

DuetLapse3 uses `wget` to access still image cameras.
** Note:  If your software also streams images, then using the streaming function will usually be preferable.

Verify that it is installed correctly by running the following command.

```bash
wget --version
```

Consult your camera setup instructions to determine the url for accessing the camera.

Verify that using `http://camera-url` (in a browser on the same machine that is running DuetLapse) displays an image.

Verify that running this command creates an image in test.jpeg.

```bash
wget --auth-no-challenge -nv -O ./test.jpeg http://camera-url
```

**Example option settings**

```text
-camera1 web
-weburl1 http://camera-url
```

### Streaming camera

DuetLapse3 uses `ffmpeg` to access streamed cameras.  Verify that it is installed correctly by running the following command.

```bash
ffmpeg -version
```

Consult your camera setup instructions to determine the url for accessing the camera.  Typically, this will involve some third party software e.g. [videostream](https://github.com/stuartofmt/videostream)

Verify that using `http://camera-url` (in a browser on the same machine that is running DuetLapse) displays a video.

Verify that running this command creates an image in test.jpeg.

```bash
ffmpeg -y -i http://camera-url -vframes 1 ./test.jpeg
```

**Example option settings**

```text
-camera1 stream
-weburl1 http://camera-url
```

### USB camera

DuetLapse3 uses `fswebcam` to access USB cameras.  Verify that it is installed correctly by running the following command.

```bash
fswebcam --version
```

Verify that running this command creates an image in test.jpeg.

```bash
fswebcam --quiet --no-banner ./test.jpeg
```

**Example option settings**

```text
-camera1 usb
```

### Pi Camera

For a directly connected (ribbon cable) Pi camera, there are several possible approaches.  The standard software used for the Pi camera changed with the Debian Bullseye release. Follow the instructions for setting up and testing the pi camera according to the level of your operating system.

At this time(start 2023), the recommended approach is to use streaming software stream. [videostream](https://github.com/stuartofmt/videostream) with the -size 2 option works as a good starting point.  

**Example option settings**

```text
-weburl1 http://camera-url
-camera1 stream
```

## 4 - Know your computers ip address and select an unused port

Know the ip address of the computer running DuetLapse3 and select an unused port number.  A port number greater then 8080 is suggested,  e.g. 8084.  This port number cannot be used by any other process on your computer.

**Example option settings**

```text
-port 8084
```

## 5 - Create a configuration file

From the results of sections 1 - 4 above, create a configuration file in the same folder as DuetLapse3. The configuration file can have any name e.g. DuetLapse3.config.  Additional options given in this example are for initial testing and can be modified according to your needs.

**Example configuration file for streaming camera**

```text
-duet 
-port
-camera1
-weburl1
-seconds 20
-dontwait
-verbose
-keepfiles
```

## 5 - Run DuetLapse3

Test Duetlapse 3 using the configuration file created in step 4.

The options provided in the example will cause DuetLapse to capture images once every 15 seconds and DOES NOT require a print job to be running.

**Example**

```bash
python ./DuetLapse3.py -file ./DuetLapse3.config
```

The console output will alert you to any issues.

The user interface will be accessible by :
<http://localhost:[port]> (e.g. `http://localhost:8081`) or <http://[ip]:[port]> (e.g. `http://192.168.1.10:8081`)

If you are running the browser on the same computer that is running DuetLapse: localhost will likely work.

If the browser is running on a remote computer then `[ip]` is the address of the computer that is running DuetLapse