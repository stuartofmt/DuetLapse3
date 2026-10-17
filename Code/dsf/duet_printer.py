"""
Communication with the printer

All the requests to the Duet - the standalone rr_ api or the SBC /machine api, chosen by
state.apiModel - and publishing the page address to the DSF plugin data.
For an SBC, the object model is kept up to date by DSF's WebSocket, with http used whenever it is not connected.

duetLapse3 sets the hooks below at startup, so this module does not depend on the rest of the program.
"""
import json
import threading
import time
import urllib.parse

import requests
import websocket  # websocket-client

import state  # Shared state - always use state.<name>
from logger_module import logger, currentFuncName

def printerAddress():
    # host[:port] of the printer.  A port in the duet setting (the old way, e.g. 192.168.1.5:8080) is still used
    if ':' in state.duet or state.duetport in [80, None]:
        return state.duet
    return state.duet + ':' + str(state.duetport)

# Hooks - set by duetLapse3
onDisconnected = None  # Called when the printer has stopped answering (after 3 tries)
onMessages = None      # Called with (queue, dellist) when the printer's M3291 message queue has something new
onChange = None        # SBC - called when the WebSocket brings a change to the status, layer or M3291 messages


def getDuet(calledfrom, function): #  Helper function to call other specific getDuet(x) calls
    # Retries if there is a network problem
    # Relies on called functions to return 'disconnected' if they cannot get the requested info
    # Changes connectionState to False if there is a persistent fault
    disconnected = 0
    getstatus = False
    while getstatus is False:
        #  The working code gets executed here
        
        logger.debug('Calling ' + function.__name__ + ' from ' + currentFuncName(2) + ' --> '  + currentFuncName(1) + ' --> '  + currentFuncName(0))

        if 'NoneType' in str(type(function)):
            result = function  # Function with variables
        else:
            result = function()   

        if isinstance(result, tuple): # More than one return variable
            connect = str(result[0])
            responseitems = len(result)
        else:
            connect = str(result)
            responseitems = 1

        if connect == 'disconnected' and state.terminateState != 1:
            state.connectionState = False # Stop additional calls
            disconnected += 1
            logger.debug('Number of disconnects ' + str(disconnected))
            time.sleep(1)
            if disconnected > 2:  #  Persistent error state
                #  connectionState = False
                if onDisconnected is not None:
                    onDisconnected()
                response = [] # start with a list
                for i in range(responseitems):
                    response.append(None) # Dummy return
                return tuple(response)  # turn the response into a tuple 
        else:
            getstatus = True # We have a status

    state.connectionState = True
    return result


def urlCall(url, post):
    # Makes all the calls to the printer
    # If post is True then make a http post call
    timelimit = 5  # timout for call to return
    loop = 0
    limit = 2  # seems good enough to catch transients
    loginRetry = 0
    while loop < limit:
        error  = ''
        code = 9999
        logger.debug(str(loop) +' url: ' + str(url) + ' post: ' + str(post))
        try:
            if post is False:
                r = requests.get(url, timeout=timelimit, headers=state.urlHeaders)
            else:
                r = requests.post(url, timeout=timelimit, data=post, headers=state.urlHeaders)
        except requests.ConnectionError as e:
            logger.info('Cannot connect to the printer\n')
            logger.debug(str(e))
            logger.debug('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n')
            error = 'Connection Error'
        except requests.exceptions.Timeout as e:
            logger.info('The printer connection timed out\n')
            logger.debug(str(e))
            logger.debug('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n')
            error = 'Timed Out'

        if error == '': # call returned something
            code = r.status_code
            if code == 200:
                return r
            elif code == 401: # Dropped session
                loginRetry += 1
                code = loginPrinter(state.apiModel)[1] # Try to get a new key
                if code == 200:
                    loop = 0
                    continue  # go back and try the last call
                else: # cannot login
                    if loginRetry > 1: # Failed to get new key
                        break
            # any other http error codes are to be handled by caller            
        time.sleep(1)
        loop += 1      # Try again
 
    # Call failed - Create dummy response
    class r:
        ok = False
        status_code = code
        reason = error
    return r

def loginPrinter(model = ''):
    if state.simulate in ['all','printer']:
        logger.info('Simulated success - loginPrinter')
        return 'simulated_API', 200
    state.urlHeaders = {}
    logger.info('Logging in to Printer')

    if model == '' or model == 'rr_model':
        URL = ('http://' + printerAddress() + '/rr_disconnect') # Close any open session
        r = urlCall(URL,  False)
        URL = ('http://' + printerAddress() + '/rr_connect?password=' + state.password) # Connect with password
        r = urlCall(URL,  False)
        code = r.status_code
        if code == 200:
            j=json.loads(r.text)
            err = j['err']
            if err == 0:
                if j['apiLevel'] != None: # Check to see if in SBC emulation mode
                    if j['apiLevel'] == 1:
                        logger.debug('Emulation mode detected - Disconnect and try SBC')
                        URL = ('http://' + printerAddress() + '/rr_disconnect') # Close any open session
                        r = urlCall(URL,  False)
                    else: # in case standalone returns apiLevel: False in future
                        logger.debug('!!!!! Connected to printer Standalone !!!!!')
                        model = 'rr_model'
                else:
                    logger.debug('!!!!! Connected to printer Standalone !!!!!')
                    model = 'rr_model'
            elif err == 1:
                logger.info('!!!!! Standalone Password is invalid !!!!!')
                code = 403 # mimic SBC codes
            elif err == 2:
                logger.info('!!!!! No more Standalone connections available !!!!!')
                code = 503 # mimic SBC codes
        elif code == 404: # Ignore as it indicated Standalone was not there
            pass
        else:
            logger.info('!!!!!  Could not connect. code = ' + str(code) + ' reason = ' + r.reason + ' !!!!!')

    if model == '' or model == 'SBC':
        URL = ('http://' + printerAddress() + '/machine/disconnect') # Close any open session
        r = urlCall(URL,  False)
        URL = ('http://' + printerAddress() + '/machine/connect?password=' + state.password) # Connect with password
        r = urlCall(URL,  False)
        code = r.status_code
        if code == 200:
            logger.debug('!!!!! Connected to SBC printer !!!!!')
            j = json.loads(r.text)
            sessionKey = j['sessionKey']
            state.urlHeaders = {'X-Session-Key': sessionKey}
            model = 'SBC'
            startWebSocket()

            #  Could not connect to printer   
        elif code == 403:
                logger.info('!!!!! SBC Password is invalid !!!!!')
        elif code == 503:
                logger.info('!!!!! No more SBC connections available !!!!!')
        elif code == 502:
                logger.info('!!!!!  Incorrect DCS version  !!!!!')
        else:
            logger.info('!!!!!  Could not connect.  Error code = ' + str(code) + ' !!!!!')
    
    return model, code    

def getDuetVersion(model):
    if state.simulate in ['all','printer']:
        logger.info('Simulated success - getDuetVersion')
        return 'simulated'
    # Get the firmware version
    logger.info('!!!!! Getting the firmware version !!!!!')
    if model == 'rr_model':
        URL = ('http://' + printerAddress() + '/rr_model?key=boards')
        r = urlCall(URL,  False)
        if r.status_code == 200:
            j = {}
            try:
                j = json.loads(r.text)
            except:
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info("json.loads(r.text) could not be parsed")
                logger.info(j)
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            try:
                version = j['result'][0]['firmwareVersion']
                return version
            except KeyError:
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info("j['result'][0]['firmwareVersion'] does not exist")
                logger.info(j)
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            except:
                logger.info('!!!!! Could not get standalone firmware version !!!!!')
        else:
            logger.info('!!!!! Error getting rr_model?key=boards code = ' + str(r.status_code) + '!!!!!') 

    elif model == 'SBC':       
        URL = ('http://' + printerAddress() + '/machine/status')
        r = urlCall(URL,  False)
        if r.status_code == 200:
            j = {}
            try:
                j = json.loads(r.text)
            except:
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info("json.loads(r.text) could not be parsed")
                logger.info(j)
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            try:
                version = j['boards'][0]['firmwareVersion']
                return version
            except KeyError:
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                logger.info("j['boards'][0]['firmwareVersion'] does not exist")
                logger.info(j)
                logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            except:
                logger.info('!!!!! Could not get SBC firmware version !!!!!')
        else:
            logger.info('!!!!! Error getting /machine/status code = ' + str(r.status_code) + '!!!!!')
    else:
        logger.info('!!!!! Could not get version for installation type =  ' + model +  '  !!!!!')
        logger.info('!!!!! THIS SHOULD NEVER HAPPEN !!!!!')
        return ''  # Failed to determine API and firmware version

###########################
# Object model - one read is shared by Status, Layer, Jobname and Position
###########################

MODEL_MAX_AGE = 1.0  # Seconds.  Reads within this time share one request.  Sending gcode starts a new read
_model = None        # The last object model read from the printer
_modelTime = 0       # When it was read
_seqs = None         # Standalone - the change counters from the last read
_modelLock = threading.Lock()  # Read from more than one thread (mainLoop, the web page, makeVideo)

def invalidateModel():
    global _modelTime
    _modelTime = 0

def getModel(maxAge = MODEL_MAX_AGE):
    # The printer's object model - read again if older than maxAge seconds.  None if the printer did not answer
    global _model, _modelTime
    live = wsModel()
    if live is not None:  # SBC with the WebSocket connected - always up to date, no request needed
        return live
    with _modelLock:
        if _model is not None and time.time() - _modelTime <= maxAge:
            return _model
        model = readModel()
        if model is not None:
            _model, _modelTime = model, time.time()
        return model

def readModel():
    if state.apiModel == 'SBC':
        return getJson('/machine/status')  # The whole object model in one request - used when the WebSocket is not connected
    if state.apiModel == 'rr_model':
        return readStandaloneModel()
    return None

def getJson(path):
    r = urlCall('http://' + printerAddress() + path, False)
    if not r.ok:
        return None
    try:
        return json.loads(r.text)
    except ValueError as e:
        logger.debug('Could not read ' + path + ' -- ' + str(e))
        return None

def rrModel(key, flags):
    # rr_model is the http version of M409
    j = getJson('/rr_model?key=' + key + '&flags=' + flags)
    if not isinstance(j, dict) or 'result' not in j:
        return None
    return j['result']

def merge(old, new):
    # old with the values in new added (new values win) - used to add the live values to the full ones,
    # and the WebSocket's patches to its model.  Returns new objects - old is never changed
    if isinstance(old, dict) and isinstance(new, dict):
        result = dict(old)
        for key, value in new.items():
            result[key] = merge(old.get(key), value)
        return result
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        # A null in place of an object means that item has not changed
        return [o if (n is None and isinstance(o, dict)) else merge(o, n) for o, n in zip(old, new)]
    return new

def readStandaloneModel():
    # Usually one request: the frequently changing values (status, layer, position) and the seqs change counters
    # - the same way DWC reads a standalone board.  job and global are only read again when their counter changes
    global _seqs
    live = rrModel('', 'd99fn')
    if not isinstance(live, dict):
        return None
    model = merge(_model or {}, live)
    seqs = live.get('seqs')
    for key in ['job', 'global']:  # job.file.fileName and global (the M3291 messages) are not live values
        changed = not isinstance(seqs, dict) or not isinstance(_seqs, dict) or seqs.get(key) != _seqs.get(key)
        if changed or key not in model:
            value = rrModel(key, 'd99vn')
            if value is None:
                return None
            model[key] = merge(value, live.get(key, {}))
    if 'state' not in live:  # Should always be there
        value = rrModel('state', 'd99vn')
        if value is None:
            return None
        model['state'] = value
    _seqs = seqs
    return model


###########################
# SBC WebSocket - DSF pushes object model changes as they happen (as it does for DWC)
# Works on the SBC itself and from another computer.  gcode is still sent over http
###########################

WS_PING_INTERVAL = 8   # Seconds with no update before sending PING - keeps the connection and session alive
WS_RETRY_INTERVAL = 5  # Seconds between attempts to reconnect
_ws = None            # The open WebSocket, or None
_wsModel = None       # The object model kept up to date by the WebSocket - None when not connected
_wsThread = None
_wsLock = threading.Lock()

def wsModel():
    # The WebSocket's object model, or None if it is not connected (then http is used)
    if state.apiModel != 'SBC':
        return None
    return _wsModel

def startWebSocket():
    # Called after an SBC login.  The reader keeps running and reconnects by itself (with the latest session key)
    global _wsThread
    with _wsLock:
        if _wsThread is not None and _wsThread.is_alive():
            return
        _wsThread = threading.Thread(name='webSocket', target=_wsReader, daemon=True)
        _wsThread.start()

def _watched(model):
    # The parts of the object model the control loop reacts to straight away
    def get(*path):
        value = model
        for key in path:
            if not isinstance(value, dict):
                return None
            value = value.get(key)
        return value
    return (get('state', 'status'), get('job', 'layer'), json.dumps(get('global', 'DL3msg')), json.dumps(get('global', 'DL3del')))

def _wsUrl():
    key = state.urlHeaders.get('X-Session-Key', '') if isinstance(state.urlHeaders, dict) else ''
    return 'ws://' + printerAddress() + '/machine' + ('?sessionKey=' + urllib.parse.quote(key) if key else '')

def _wsReader():
    global _ws, _wsModel
    connected = False
    while state.terminateState != 1:
        try:
            _ws = websocket.create_connection(_wsUrl(), timeout = 10)
            model = json.loads(_ws.recv())  # The first message is the whole object model
            if not isinstance(model, dict) or 'state' not in model:
                raise ValueError('The first message was not the object model')
            _wsModel = model
            _ws.send('OK\n')  # Ready for the next update
            if onChange is not None:
                onChange()
            connected = True
            logger.info('WebSocket connected to ' + printerAddress() + ' - printer updates are pushed, not polled')
            _ws.settimeout(WS_PING_INTERVAL)
            while state.terminateState != 1:
                try:
                    message = _ws.recv()
                except websocket.WebSocketTimeoutException:
                    _ws.send('PING\n')
                    continue
                if not message or message.startswith('PONG'):
                    continue
                patch = json.loads(message)
                before = _wsModel
                _wsModel = merge(_wsModel, patch)  # A new object - readers never see a half-applied patch
                _ws.send('OK\n')
                if onChange is not None and _watched(before) != _watched(_wsModel):
                    onChange()  # Wake the control loop - e.g. a layer change, so the image is taken now
        except (websocket.WebSocketException, OSError, ValueError) as e:
            if connected:
                logger.info('WebSocket to ' + printerAddress() + ' lost (' + str(e) + ') - using http until it reconnects')
            else:
                logger.debug('WebSocket to ' + printerAddress() + ' not available (' + str(e) + ') - using http')
            connected = False
        finally:
            _wsModel = None  # Fall back to http
            if _ws is not None:
                try:
                    _ws.close()
                except Exception:
                    pass
                _ws = None
        time.sleep(WS_RETRY_INTERVAL)


###########################
# Values from the object model
###########################

def Jobname():
    # Used to get the print jobname from Duet
    if state.simulate in ['all','printer']:
        return 'simulated_job'
    model = getModel()
    try:
        jobname = model['job']['file']['fileName']
        if jobname is None:
            jobname = ''
        return jobname
    except (TypeError, KeyError) as e:
        logger.debug('Could not get jobname')
        logger.debug(str(e))
    return 'disconnected'

def Status():
    state.lastStatusCall = time.time()
    # Used to get the status information from Duet
    # Note return "disconnected" in different place than ususal due to post processing of messages
    if state.simulate in ['all','printer']:
        logger.info('Simulated status is Idle')
        return 'idle', ''

    j = getModel()
    messages = None
    try:
        status = j['state']['status']
        logger.debug(state.apiModel + ' Status is ' + status)
    except (TypeError, KeyError) as e:
        logger.debug('Could not get Status')
        logger.debug(str(e))
        return 'disconnected', ''

    #  Check for message commands
    try:
        queue = []
        dellist = []
        #  use .get method for safety
        if j['global'].get('DL3msg') != None: # initialized
            queue = j['global']['DL3msg']
            logger.debug(f'DL3Msg queue = {queue}')
            if j['global'].get('DL3del') != None: # something to delete
                dellist = j['global']['DL3del']
                logger.debug(f'DL3del queue = {dellist}')  
            if queue[0] < state.lastMessageSeq:  # The printer was reset - its message numbers start again
                logger.info('The printer message queue was reset - message numbers start again from ' + str(queue[0]))
                state.lastMessageSeq = 0
            if queue[0] > state.lastMessageSeq or len(dellist) > 0:
                messages = (queue, dellist)
    except Exception as e:
        logger.info('Error Processing message queue')
        logger.info(str(e))

    if messages is not None and onMessages is not None:
        onMessages(*messages)  # duetLapse3 acts on them

    return status, ''

def Layer():
    # Used to get the the current layer
    if state.simulate in ['all','printer']:
        return -1
    model = getModel()
    try:
        layer = model['job']['layer']
        if layer is None:
            layer = -1
        logger.debug('Current Layer is ' + str(layer))
        return layer
    except (TypeError, KeyError) as e:
        logger.debug('Could not get Layer Info')
        logger.debug(str(e))
    return 'disconnected'

def Position():
    # Used to get the current head position from Duet - always read fresh, as it is used to wait for the head to move
    if state.simulate in ['all', 'printer']:
        return 0,0,0
    model = getModel(maxAge = 0)
    try:
        if model is not None and 'move' not in model and state.apiModel == 'rr_model':
            model = {'move': {'axes': rrModel('move.axes', 'd99vn')}}  # Not in this firmware's live values
        axes = model['move']['axes']
        return axes[0]['machinePosition'], axes[1]['machinePosition'], axes[2]['machinePosition']
    except (TypeError, KeyError, IndexError) as e:
        logger.debug('Could not get Position Info')
        logger.debug(str(e))
    return 'disconnected'


def sendDuetGcode(model, command):
    # Used to send a command to Duet
    if state.simulate in ['all','printer']:
        return
    if model == 'rr_model':
        URL = 'http://' + printerAddress() + '/rr_gcode?gcode=' + urllib.parse.quote(command, safe = '')  # e.g. # or & in the gcode
        r = urlCall(URL,  False)
    else:
        URL = 'http://' + printerAddress() + '/machine/code'
        r = urlCall(URL,  command)
    invalidateModel()  # The gcode may change the printer - read it again next time

    if r.ok:
        return

def isPlugin(model):
    if model == 'SBC':
        URL = ('http://' + printerAddress() + '/machine/status')
        r = urlCall(URL,  False)
        if r.ok:
            try:
                j = json.loads(r.text)
                if j['plugins'] != None:
                    if j['plugins']['duetLapse3'] != None: # duetLapse3 is registered plugin
                        if str(j['plugins']['duetLapse3']['pid']) == state.pid: # Running as a plugin
                            logger.info('Running as a plugin')
                            return True
                logger.info('Not Running as a plugin')
            except Exception as e:
                logger.debug('Could not get plugin information')
                logger.debug(str(e))
    else:
        logger.debug('isPlugin ignored - only valid for SBC')
        return False
            
def stopPlugin(model, command):
    # Used to send a command to Duet
    if model == 'SBC':
        URL = 'http://' + printerAddress() + '/machine/stopPlugin'
        r = urlCall(URL,  command)
        if r.ok:
            logger.info('Sent stopPlugin to plugin manager')
        else:    
            logger.info('stopPlugin failed with code: ' + str(r.status_code) + ' and reason: ' + str(r.reason))
    else:
        logger.info('Stop Plugin ignored - only valid for SBC')
    return


def publishUiAddress(ip, port):
    # The DWC page reads these from the object model to build its iframe url - same as duetPrintGuard
    try:
        from dsf.connections import CommandConnection
    except ImportError:
        logger.warning('dsf-python is not installed - cannot publish UI address to plugin data')
        return
    command_connection = CommandConnection()
    try:
        command_connection.connect()
        command_connection.set_plugin_data('duetLapse3', 'ip', ip)
        command_connection.set_plugin_data('duetLapse3', 'port', port)
        logger.info('Published UI address ' + ip + ':' + str(port) + ' to plugin data')
    except Exception as e:
        logger.warning('Could not publish UI address to plugin data: ' + str(e))
    finally:
        command_connection.close()
