# Getting Started

This is a brief guide to undertand the configuration options sufficient to test for correct operation.

It is strongly recommended that these steps be performed **BEFORE** installing DuetLapse3.

DuetLapse3 can be installed as a self-contained, stand alone program (see instructions here)

<https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/Standalone%20quick%20installation%20guide.md>

or as a plugin on an SBC Duet (see instructions here):

<https://github.com/stuartofmt/DuetLapse3/blob/main/plugin/plugin%20installation%20guide.md>

**All these actions should be performed on the computer that DuetLapse3 WILL BE installed**

This is so that any network or camera connectivity issues are discovered.

**Perform these steps in sequence and do not continue to the next step until everything is validated.**

## 0 -- Ensure there are sufficient resources on your computer

Before installing DuetLapse3 is STRONGLY RECOMENDED that:

1 -- A minimum of 5GB of memory is available.

For example on a Pi 3B+ this would be 1GB of RAM and 4GB Swap

2 -- On a Pi 128MB be allocated to GPU

See notes here:

<https://github.com/stuartofmt/Pi-Notes/blob/master/General-Setup.md>

## 1 -- Identify the ip address of your printer

This is the ip used in the url you use to access DWC.  It should be a static IP addess i.e. does NOT change when the printer restarts.  This ip address is used in the -duet option.

On linux this can usually be determined with:

```text
hostname -I 
```

**Example option setting**

```text
-duet 192.168.1.30
```

## 2 - Know your computers ip address and select an unused port

Select an unused port number.

Current, in use port numbers can usually be discoved with this conmand

```bash
sudo ss -tulw | grep -i listen
```

A port number greater then 8080 is suggested,  e.g. 8084.

This port number cannot be used by any other process on your computer.

**Example option settings**

```text
-port 8084
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

**Note:  If your software also streams images, then using the streaming function will usually be preferable.**

Verify that it is installed correctly by running the following command.

```bash
wget --version
```

Consult your camera setup instructions to determine the url for accessing the camera.

**In these instructions `http://camera-url` is a placeholder and needs to be changed to the actual url to your camera**

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

DuetLapse3 uses `ffmpeg` to access streamed cameras.

Verify that it is installed correctly by running the following command.

```bash
ffmpeg -version
```

Consult your camera setup instructions to determine the url for accessing the camera.

Typically, this will involve some third party software

e.g. [videostream](https://github.com/stuartofmt/videostream)

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

DuetLapse3 uses `fswebcam` to access USB cameras.

Verify that it is installed correctly by running the following command.

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

At this time(start 2023), the recommended approach is to use streaming software stream.

[videostream](https://github.com/stuartofmt/videostream) with the -size 5 option works as a good starting point.  

**Example option settings**

```text
-weburl1 http://camera-url
-camera1 stream
```

## 4 - setting -basedir

The -basedir option determines where the working files for DuetLapse will be placed.

For initial testing the following are STRONGLY recommended:

1. For standalone, use the same directory where DuetLapse3 will be installed. i.e. use a period.

```text
-basedir .
```

2. For SBC, it is especially important that -basedir IS NOT in the same directory as DuetLapse3 as this can cause issues when installing / uninstalling.

The following entry is recomended:

```text
-basedir /opt/dsf/sd/DuetLapse3
```

## 5 - Create a configuration file

From the results of sections 1 - 4 above, create a configuration file by substituting your values into the example below.

Additional options given in this example are for initial testing and can be modified according to your needs.

**Example configuration file for streaming camera**

```text
-duet 192.168.1.30
-port 8084
-basedir /opt/dsf/sd/DuetLapse3
-camera1 stream
-weburl1 http://camera-url
-seconds 20
-verbose
-keepfiles
-restart
```

## 6 - Run DuetLapse3

Test Duetlapse3 using the configuration file created in step 5.

The options provided in the example will cause DuetLapse3 to capture images once every 20 seconds and DOES NOT require a print job to be running.
