"""
Shared state for duetLapse3.

Every module does `import state` and reads / writes `state.<name>`.
Never use `from state import <name>` - that copies the value at import
time and later changes will not be seen.

Values here are placeholders only. The real initial values are set by
the functions noted against each group.
"""

###########################
# Command line options - set in init()
###########################

configdir = None  # Folder for duetLapse3.json and the logfile - argument 1, or the program's folder
configfile = None  # duetLapse3.json in configdir

# Simulate
simulate = None

# Environment
duet = None  # Printer address - blank in the settings = this computer
duetport = None  # Printer port
password = None
basedir = None
instances = None
nolog = None
verbose = None
port = None
keeplogs = None
novideo = None
deletepics = None
keepfiles = None

# Execution
dontwait = None
seconds = None
detect = None
pause = None
numlayers = None
movehead = None
rest = None
standby = None
norestart = None  # The setting - don't get ready for the next print
restart = None  # not norestart

# Cameras
weburl1 = None
weburl2 = None
enable1 = None  # Camera1 is used
enable2 = None  # Camera2 is used

# Video
extratime = None
fps = None
minvideo = None
maxvideo = None
ffmpegthreads = None  # 0 = automatic



###########################
# Derived from options / environment - set in init(), setdebug()
###########################

win = None  # True if running on Windows
pid = None  # pid for this instance - used for temp filenames
duetname = None
httpListener = None  # True if an integral http listener should be started
ip = None  # ip address of this machine - published for the DWC page

###########################
# Directories and logging - set in init(), setuplogfile(), createworkingDir(), onePhoto()
###########################

topDir = None
nextWorkingDir = None
workingDir = None
workingDirStatus = None
pidIncrement = None
logfilename = None

###########################
# Timers and limits - set in main()
###########################

mainLoopPoll = None
mainLoopIterate = None
minseconds = None
lastCaptureLoop = None
lastStatusCall = None

###########################
# Printer connection - set in main(), checkforPrinter(), loginPrinter()
###########################

apiModel = None
connectionState = None
firstConnect = None  # None until the first successful login
connectError = None  # Why the printer can not be connected (e.g. wrong password) - shown on the page.  '' = no error
connectRetry = None  # threading.Event - set when the printer settings are changed on the page, to try again at once
printerVersion = None
urlHeaders = None  # SBC session key

###########################
# Control - set in main(), terminate() and startMakeVideo()
###########################

terminateState = None  # 1 while terminating
videoJob = None  # The last video given to the video worker (a Future)
videoEvents = None  # The results of the last 10 videos - announced by the page
videoSeq = None  # Numbers the video results
filesVersion = None  # Changes when files are deleted or zipped - the page's Images tab refreshes (/api/events)
settingsVersion = None  # Changes when the settings are saved - the page's settings tabs reload (/api/events)
restarting = None

###########################
# Print and capture state - set in setstartvalues(), captureLoop(), nextAction()
###########################

action = None
lastaction = None
printState = None
lastPrintState = None
duetStatus = None
lastDuetStatus = None
timePriorPhoto1 = None
timePriorPhoto2 = None
frame1 = None  # Camera1 frame counter
frame2 = None  # Camera2 frame counter
zo1 = None  # Camera1 layer
zo2 = None  # Camera2 layer
camfile1 = None
camfile2 = None
lastImage = None
simulatedImage = None

###########################
# M3291 message queue - set in main(), parseM3291()
###########################

lastMessageSeq = None

###########################
# http listener - set in startHttpListener()
###########################

listener = None  # uvicorn.Server
listenerThread = None
