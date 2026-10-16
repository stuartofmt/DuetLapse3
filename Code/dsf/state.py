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

inputs = None  # dict of option name -> display value (see getOptions)
configfile = None  # json config file given by -config ('' if none)

# Simulate
simulate = None

# Environment
duet = None
password = None
basedir = None
poll = None
instances = None
logtype = None
nolog = None
verbose = None
host = None
port = None
keeplogs = None
novideo = None
deletepics = None
maxffmpeg = None
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
restart = None

# Cameras
camera1 = None
camera2 = None
weburl1 = None
weburl2 = None

# Video
extratime = None
fps = None
minvideo = None
maxvideo = None

# Overrides
camparam1 = None
camparam2 = None
vidparam1 = None
vidparam2 = None

# UI
hidebuttons = None

# Special
execkey = None
M3291 = None

###########################
# Derived from options / environment - set in init(), setdebug()
###########################

win = None  # True if running on Windows
pid = None  # pid for this instance - used for temp filenames
duetname = None
httpListener = None  # True if an integral http listener should be started
ip = None  # ip address of this machine - published for the DWC page
debug = None  # shell redirect appended to commands
ffmpegquiet = None

###########################
# Directories and logging - set in init(), setuplogfile(), createworkingDir(), onePhoto()
###########################

topDir = None
nextWorkingDir = None
workingDir = None
workingDirStatus = None
pidIncrement = None
loggingset = None
logfilename = None

###########################
# Timers and limits - set in main()
###########################

mainLoopPoll = None
mainLoopIterate = None
minPoll = None
minseconds = None
lastCaptureLoop = None
lastStatusCall = None

###########################
# Printer connection - set in main(), checkforPrinter(), loginPrinter()
###########################

apiModel = None
connectionState = None
firstConnect = None  # None until the first successful login
printerVersion = None
urlHeaders = None  # SBC session key

###########################
# Thread / loop status flags - set in main()
# -1 = not running, 0 = stop requested, 1 = running
###########################

nextActionState = None
makeVideoState = None
captureLoopState = None
mainLoopState = None
terminateState = None
checkforconnectionState = None
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
# http listener - set in startHttpListener(), MyHandler
###########################

listener = None
listenerThread = None
referer = None  # None until the first http request is received
