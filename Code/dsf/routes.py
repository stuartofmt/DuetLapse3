"""
FastAPI routes for the duetLapse3 web page

The page (www/index.html) loads each tab from a /tab/... route and calls the action routes.
The older API, http://<ip>:<port>/?<api>=<value> (e.g. ?command=start), still works - see legacy_api.
"""
import html
import os
import re
import time
import urllib.parse

from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response

import camera
import state  # Shared state - always use state.<name>
from logger_module import logger

# The duetLapse3 main module, set by duetLapse3.startHttpListener before the server starts.
# duetLapse3 runs as __main__, so importing it here would load a second copy.
dl3 = None

router = APIRouter()

# html templates are in the www sub directory
wwwDir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'www')

def render_html(template, **values):
    # Fill {{name}} placeholders in a www template.  <!-- comments --> are removed.
    # Templates are read on every call so they can be edited without a restart
    with open(os.path.join(wwwDir, template), encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'<!--.*?-->\n?', '', content, flags=re.DOTALL).strip()
    return re.sub(r'\{\{(\w+)\}\}', lambda m: str(values[m.group(1)]), content)


###########################
# Building the tabs
###########################

def display_controls():
    allowed_buttons = dl3.allowedNextAction(state.action)
    allbuttons = ['start', 'standby', 'pause', 'continue', 'restart']

    if state.hidebuttons:  # hide buttons if option was set
        shown = [button for button in allowed_buttons if button in allbuttons]
    else:
        shown = allbuttons

    buttons = ''
    for button in shown:
        if button in allowed_buttons:
            disable = ''
        else:
            disable = 'disabled'
        buttons += render_html('buttons/' + button + '.html', disabled = disable)

    if state.apiModel != 'SBC':
        buttons += render_html('buttons/terminate.html')

    return buttons


def display_video():
    return render_html('video.html', fps = state.fps, minvideo = state.minvideo,
                       maxvideo = state.maxvideo, videomsg = dl3.getVideoMsg())


def display_status():
    localtime = time.strftime('%A - %H:%M', time.localtime())
    if state.zo1 < 0:
        thislayer = 'None'
    else:
        thislayer = str(state.zo1)

    if state.lastImage != '':
        image = render_html('status_image.html', src = state.lastImage)
    elif state.weburl1 == '':
        image = render_html('status_nocamera.html')
    else:
        image = render_html('status_noimage.html')

    return render_html('status.html', version = dl3.duetLapse3Version, duet3d_version = state.printerVersion,
                       duet = state.duet, pid = state.pid, localtime = localtime,
                       print_state = state.printState, action = state.action,
                       duet_status = state.duetStatus, frames = state.frame1,
                       layer = thislayer, image = image)


def display_info():
    if state.workingDirStatus != -1:
        imagelocation = state.workingDir
    else:
        imagelocation = 'Waiting for first image to be created'

    options = dl3.getOptions()

    optionlist = ''
    count = 0
    for label, value in options.items():
        if label.startswith('#'):  #  Omit the section info
            continue
        if (count % 3) == 0: # 3 columns
            optionlist += render_html('info_newrow.html')
        optionlist += render_html('info_option.html', label = label, value = value)
        count += 1

    return render_html('info.html', pid = state.pid, options = optionlist, topdir = state.topDir,
                       imagelocation = imagelocation, logfilename = state.logfilename)


def update_command(command):
    # start / standby / pause / continue / restart
    # Wait (except for start) until nextAction has changed state.action, so the page shows the new state
    waitfor = {'standby': ['standby'], 'pause': ['pause'],
               'continue': ['start'],  # continue returns to the start state
               'restart': ['start', 'standby']}
    if command in ['start', 'standby', 'pause', 'continue', 'restart']:
        dl3.startnextAction(command)
        if command in waitfor:
            while state.action not in waitfor[command]: # Dont return until success
                time.sleep(0.1)

    elif command == 'terminate':  #command=terminate - backward compatible
        terminate_process('terminatehttp')
    return


def terminate_process(ttype):
    if ttype not in ['terminatehttp','terminateg', 'terminatef']:
       logger.info (ttype + ' invalid terminate requested')
       return

    if ttype == 'terminatehttp':
        dl3.startnextAction('completed')
    elif ttype == 'terminateg':
        dl3.startnextAction('completed')
        #  dl3.startnextAction('terminate')
    elif ttype == 'terminatef':
        if dl3.isPlugin(state.apiModel):
            dl3.stopPlugin(state.apiModel, 'duetLapse3')
        else:
            dl3.quit_forcibly()

    return


def display_terminate_buttons():
    if state.restart:
        restartmsg = '\\nA restart will occur after the Terminate'
        pageaction = "repeatDisplayStatus();"
    else:
        restartmsg = ''
        pageaction = "document.body.innerHTML = '';"

    if state.workingDirStatus != -1:
        vidmsg = dl3.getVideoMsg()
    else:
        vidmsg = 'There are no images available'

    return render_html('terminate.html', vidmsg = vidmsg,
                       restartmsg = restartmsg, pageaction = pageaction)


def display_files(path):
    if path == 'true':
        path = state.topDir

    if os.path.isdir(path):  # if its a dir then list it
        response = list_dir(path)
        return response
    else:
        return 'Requested path ' + path + ' is not a dir.'


def list_dir(path):
    # Pass the directory tree and determine what can be done with each file / dir
    logger.debug('list_dir called with path = ' + path)

    jpegfiles = ['.jpeg', '.jpg']
    deletablefiles = ['.mp4','.zip', '.log'] #  Different to startDuetLapse3
    fullfilenames = []
    jpegfolder = []
    deletelist = []

    try:
        displaypath = urllib.parse.unquote(path, errors='surrogatepass')
    except UnicodeDecodeError:
        displaypath = urllib.parse.unquote(path)

    displaypath = html.escape(displaypath, quote=False)                   # this is to handle differences between html and OS representations

    # Parse the directory tree and determine what can be done with each file / dir
    try:
        listdir = os.listdir(path)
    except FileNotFoundError as e:
        logger.info('No files found: ' + str(e))
        return render_html('files/nofiles.html', path = displaypath)

    #  sort the list by datetime last modified
    listdir.sort(key=lambda fn: -os.path.getmtime(os.path.join(path, fn))) # Sort in reverse order

    dirPid = str(state.pid) + '_' + str(state.pidIncrement)  # get current pid + suffix

    for sfn in listdir:
        fn = os.path.join(path, sfn)
        fullfilenames.append(fn)
        fn_elements =  os.path.splitext(fn)
        ext = fn_elements[1]
        if os.path.isdir(fn):
            if dirPid not in fn:
                deletelist.append(fn)
                try:
                    fndir = os.listdir(fn)  #  Check the subdirectory
                except FileNotFoundError as e:
                    logger.info('Subdirectory error:' + str(e))
                for jp in fndir:  # break if we find one
                    jp_elements =  os.path.splitext(jp)
                    jpext = jp_elements[1]
                    if jpext in jpegfiles:
                        jpegfolder.append(fn)
                        break
        elif ext in deletablefiles:
            if sfn == 'startup.log':  # use the short filename
                continue
            if dirPid not in fn:
                if ext in ['mp4']:  # can delete mp4 from current print snapshot
                    continue
                deletelist.append(fn)

    #  get the structure information

    if path == state.topDir:
        child_dir = False
    else:
        parentdir = os.path.split(path)[0]
        child_dir = True

    rows = ''

    # add parent dir to the html
    if child_dir:
        displayname = './'
        rows += render_html('files/parent.html', path = parentdir.replace('\\', '\\\\'), name = html.escape(displayname, quote=False))


    # Add actions to files / dirs 
    for fullname in fullfilenames:          
        if os.path.islink(fullname):   # A link to a directory displays with @
            displayname = fullname + "@"

        displayname = os.path.split(fullname)[1]
        jsname = fullname.replace('\\', '\\\\')

        buttons = ''
        if fullname in deletelist:
            buttons += render_html('files/delete.html', path = jsname)
            if fullname in jpegfolder:
                buttons += render_html('files/zip.html', path = jsname)
                buttons += render_html('files/video.html', path = jsname)

        if os.path.isdir(fullname):
            rows += render_html('files/dir.html', path = jsname, name = html.escape(displayname, quote=False), buttons = buttons)
        else:
            rows += render_html('files/file.html', path = urllib.parse.quote(fullname, errors='surrogatepass'),
                                name = html.escape(displayname, quote=False), buttons = buttons)

    dir_table = render_html('files/table.html', rows = rows)

    logger.debug('Finished parsing the files directory')
    return dir_table

    """
        end of requesthandler
    """

def get_file(path):
    if not os.path.isfile(path):
        return PlainTextResponse('Requested file ' + path + ' is not a file.', status_code=404)
    logger.debug('Trying to get file ' + path)
    fn = os.path.basename(path)
    if fn.endswith('.log'):
        return FileResponse(path, filename=fn)  # must be downloaded
    return FileResponse(path, filename=fn, content_disposition_type='inline')  # Can be displayed in browser


###########################
# Config tab - duetLapse3.json
###########################

def escape(value):
    return html.escape(str(value), quote=True)

def config_input(key, value, default):
    # The input for one setting - its type comes from the default
    if key in dl3.configExtras:  # Set by duetLapse3
        return render_html('config/readonly.html', value = escape(value))
    if isinstance(default, bool):
        checked = 'checked' if str(value).lower() == 'true' else ''
        return render_html('config/bool.html', key = key, checked = checked)
    if key in dl3.CHOICES:
        options = ''
        for choice in dl3.CHOICES[key]:
            selected = 'selected' if choice == value else ''
            options += render_html('config/option.html', value = escape(choice), selected = selected)
        return render_html('config/select.html', key = key, options = options)
    if isinstance(default, list):
        values = value if isinstance(value, list) and len(value) == len(default) else default
        return ''.join(render_html('config/list_item.html', key = key, value = escape(v)) for v in values)
    if isinstance(default, int):
        return render_html('config/number.html', key = key, value = escape(value))
    if key == 'password':
        return render_html('config/password.html', key = key, value = escape(value))
    return render_html('config/text.html', key = key, value = escape(value))

cameraSection = 'Camera'  # The section of DEFAULTS shown on the Cameras tab instead of the Config tab

def display_config(message = ''):
    try:
        config = dl3.readConfig(state.configfile)
    except (OSError, ValueError) as e:
        config = {}
        message = render_html('config/message.html', color = 'red',
                              message = escape('Could not read the settings file - showing the defaults. ' + str(e)))
    values = {k: v for section in config.values() if isinstance(section, dict) for k, v in section.items()}

    sections = ''
    for section, keys in dl3.DEFAULTS.items():
        if section == cameraSection:  # On the Cameras tab
            continue
        rows = ''
        for key, default in keys.items():
            rows += render_html('config/row.html', key = key, input = config_input(key, values.get(key, default), default),
                                help = escape(dl3.HELP.get(key, '')))
        sections += render_html('config/section.html', name = escape(section), rows = rows)

    return render_html('config/config.html', configfile = escape(state.configfile), message = message, sections = sections)

def update_config_file(settings):
    # Check every value in settings, then save them all to duetLapse3.json - or nothing if any are invalid
    # Settings stay in the section they are in.  Keys duetLapse3 does not know are kept
    # Returns a list of errors ([] if saved)
    try:
        config = dl3.readConfig(state.configfile)
    except FileNotFoundError:
        config = {}
    except (OSError, ValueError) as e:
        return ['Could not read the settings file. ' + str(e)]
    location = {key: name for name, section in config.items() if isinstance(section, dict) for key in section}

    errors = []
    for section, keys in dl3.DEFAULTS.items():
        for key, default in keys.items():
            if key in dl3.configExtras or key not in settings:
                continue
            try:
                value = dl3.checkSetting(key, settings[key], default)
            except ValueError as e:
                errors.append(str(e))
                continue
            if key in dl3.configOmit and key not in location and value == default:
                continue  # Not in the file and not changed - leave it out
            config.setdefault(location.get(key, section), {})[key] = value

    if errors:
        return errors
    try:
        dl3.writeConfig(state.configfile, config)
    except OSError as e:
        return [str(e)]
    logger.info('Settings saved to ' + state.configfile + ': ' + ', '.join(settings))
    return []

def save_message(errors, success):
    if errors:
        return render_html('config/message.html', color = 'red', message = 'Not saved:<br>' + '<br>'.join(escape(e) for e in errors))
    return render_html('config/message.html', color = 'green', message = success)

def save_config(settings):
    errors = update_config_file(settings)
    return save_message(errors, 'Saved. Restart duetLapse3 for the changes to take effect.')


###########################
# Cameras tab - the camera urls in duetLapse3.json, each with a preview
###########################

cameraUrls = ['weburl1', 'weburl2']  # Camera1, Camera2

def display_cameras():
    try:
        config = dl3.readConfig(state.configfile)
    except (OSError, ValueError):
        config = {}
    values = {k: v for section in config.values() if isinstance(section, dict) for k, v in section.items()}

    cameras = ''
    for number, key in enumerate(cameraUrls, start = 1):
        url = values.get(key, '')
        if url:
            preview = render_html('cameras/preview.html', number = number, src = escape('/camera/preview?url=' + urllib.parse.quote(url, safe = '')))
        else:
            preview = render_html('cameras/nopreview.html', number = number)
        cameras += render_html('cameras/camera.html', number = number, key = key, value = escape(url),
                               help = escape(dl3.HELP.get(key, '')), preview = preview)
    return render_html('cameras/cameras.html', configfile = escape(state.configfile), cameras = cameras)

def save_cameras(settings):
    # Save the camera urls to duetLapse3.json and use them straight away
    urls = {key: str(settings.get(key, '')).strip() for key in cameraUrls}
    errors = []
    if not camera.is_http_url(urls['weburl1']):
        errors.append('Camera1 needs an http url (a snapshot url or an MJPEG stream url)')
    if urls['weburl2'] != '' and not camera.is_http_url(urls['weburl2']):
        errors.append('Camera2 url must be an http url, or blank for no second camera')
    if not errors:
        errors = update_config_file(urls)
    if not errors:
        for key, url in urls.items():
            if state.simulate in ['all', 'camera']:
                continue  # Keep the simulated camera
            if getattr(state, key) != url:
                logger.info(key + ' changed to ' + url)
                setattr(state, key, url)
    return save_message(errors, 'Saved. The cameras are in use now.')

def preview_image(url):
    if state.simulate in ['all', 'camera']:
        return Response(state.simulatedImage, media_type = 'image/jpeg', headers = {'Cache-Control': 'no-store'})
    if not camera.is_http_url(url):
        return PlainTextResponse('Not an http url', status_code = 400)
    data = camera.fetch_image(url)  # The same capture as the time lapse
    if data is None:
        return PlainTextResponse('No image from ' + url, status_code = 502)
    return Response(data, media_type = 'image/jpeg', headers = {'Cache-Control': 'no-store'})


def make_video(path, xtratime):
    return dl3.startMakeVideo(path, xtratime, False) or ''  # False => nothread therefore blocking


###########################
# Page and tabs
# The routes are plain def (not async) so FastAPI runs them in a thread - several of them wait
###########################

@router.get('/', response_class=HTMLResponse)
def index(request: Request):
    if request.url.query:  # The older ?<api>=<value> form
        return legacy_api(request)
    return render_html('index.html', poll_ms = state.poll*1000)

@router.get('/tab/status', response_class=HTMLResponse)
def tab_status():
    return display_status()

@router.get('/tab/controls', response_class=HTMLResponse)
def tab_controls():
    return display_controls()

@router.get('/tab/video', response_class=HTMLResponse)
def tab_video():
    return display_video()

@router.get('/tab/files', response_class=HTMLResponse)
def tab_files(path: str = 'true'):  # 'true' = the top directory
    return display_files(path)

@router.get('/tab/info', response_class=HTMLResponse)
def tab_info():
    return display_info()

@router.get('/tab/terminate', response_class=HTMLResponse)
def tab_terminate():
    if state.apiModel == 'SBC':  # Not available with SBC
        return ''
    return display_terminate_buttons()


@router.get('/tab/config', response_class=HTMLResponse)
def tab_config():
    return display_config()

@router.get('/tab/cameras', response_class=HTMLResponse)
def tab_cameras():
    return display_cameras()

@router.post('/cameras/save', response_class=HTMLResponse)
def cameras_save(settings: dict = Body(...)):  # {weburl1: url, weburl2: url} from saveCameras() in index.html
    return save_cameras(settings)

@router.get('/camera/preview')
def camera_preview(url: str):  # One image from the camera url, fetched by duetLapse3
    return preview_image(url)

@router.post('/config/save', response_class=HTMLResponse)
def config_save(settings: dict = Body(...)):  # {setting: value} from saveConfig() in index.html
    return save_config(settings)


###########################
# Actions
###########################

@router.get('/command/{command}')
def command(command: str):  # start, standby, pause, continue, restart, terminate
    update_command(command)
    return Response(status_code=204)

@router.get('/terminate/{ttype}')
def terminate(ttype: str):  # terminateg (graceful), terminatef (forced) or terminatehttp
    terminate_process(ttype)
    return Response(status_code=204)

@router.get('/snapshot', response_class=PlainTextResponse)
def snapshot():
    if state.workingDirStatus != -1:
        return make_video(state.workingDir, False)  # False => no extratime
    return 'There are no images captured yet.\nTry again later.'

@router.get('/makevideo', response_class=PlainTextResponse)
def makevideo(path: str, xtratime: bool = False):
    return make_video(path, xtratime)

@router.get('/videosettings')
def videosettings(fps: str = None, minvideo: str = None, maxvideo: str = None):
    if fps is not None:
        dl3.changeFps(fps)
    if minvideo is not None:
        dl3.changeMinvideo(minvideo)
    if maxvideo is not None:
        dl3.changeMaxvideo(maxvideo)
    return Response(status_code=204)

@router.get('/delete')
def delete(path: str):
    dl3.deleteFileFolder(path)
    return Response(status_code=204)

@router.get('/zip')
def zip_folder(path: str):
    dl3.make_archive(path)
    return Response(status_code=204)

@router.get('/getfile')
def getfile(path: str):
    return get_file(path)


###########################
# The older API - http://<ip>:<port>/?<api>=<value>
###########################

# Calls that return something to display
legacyPages = {
    'displayStatus': lambda args: display_status(),
    'displayControls': lambda args: display_controls(),
    'displayVideo': lambda args: display_video(),
    'displayFiles': lambda args: display_files(args),
    'displayInfo': lambda args: display_info(),
    'displayTerminate': lambda args: tab_terminate(),
    'snapshot': lambda args: snapshot(),
    'video': lambda args: make_video(args[0], args[1] == 'True'),  # ?video=<path>&video=True|False
}

# Calls that only do something
legacyActions = {
    'command': lambda args: update_command(args),
    'delete': lambda args: dl3.deleteFileFolder(args),
    'zip': lambda args: dl3.make_archive(args),
    'terminate': lambda args: terminate_process(args),
    'fps': lambda args: dl3.changeFps(args),
    'minvideo': lambda args: dl3.changeMinvideo(args),
    'maxvideo': lambda args: dl3.changeMaxvideo(args),
}

def legacy_api(request):
    query = urllib.parse.parse_qs(request.url.query)
    logger.debug('!!!!! http call: ' + str(query) + ' !!!!!')
    result = None
    for api, value in query.items():
        args = value[0] if len(value) == 1 else value
        if api == 'getfile':
            return get_file(args)
        elif api in legacyPages:
            result = legacyPages[api](args)
        elif api in legacyActions:
            legacyActions[api](args)
        else:
            return HTMLResponse('The API call "' + api + '" with value "' + str(args) + '" is not supported\
                                <br><br>' + str(query) + '<br>')
    if result is not None:
        return HTMLResponse(result)
    return Response(status_code=204)
