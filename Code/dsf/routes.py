"""
FastAPI routes for the duetLapse3 web page

The page is built from ui/ (Vue 3 + Vuetify 4, built with Vite) into static/app - see ui/README.md.
It reads its data from the /api/... routes (JSON) and uses the action routes (/command/..., /snapshot, ...).
The older API, http://<ip>:<port>/?<api>=<value> (e.g. ?command=start), still works for the actions - see legacy_api.
"""
import os
import threading
import urllib.parse

from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

import camera
import duet_printer  # Communication with the printer
import state  # Shared state - always use state.<name>
from logger_module import logger

# The duetLapse3 main module, set by duetLapse3.startHttpListener before the server starts.
# duetLapse3 runs as __main__, so importing it here would load a second copy.
dl3 = None

router = APIRouter()

# The built page (see ui/README.md)
appDir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static', 'app')


###########################
# Data for the page
###########################

def status_data():
    return {
        'version': dl3.duetLapse3Version,
        'printerVersion': state.printerVersion,
        'printer': duet_printer.printerAddress(),
        'connected': bool(state.connectionState),
        'pid': state.pid,
        'printState': state.printState,
        'action': state.action,
        'duetStatus': state.duetStatus,
        'frames': state.frame1,
        'frames2': state.frame2,
        'imagesNeeded': dl3.imagesForVideo(),  # The fewest images (per camera) that make a video
        'layer': None if state.zo1 is None or state.zo1 < 0 else state.zo1,
        'lastImage': state.lastImage,
        'camera1': dl3.cameraUrl(1) != '',  # In use - has a url and is switched on
        'camera2': dl3.cameraUrl(2) != '',
        'videoMessage': dl3.getVideoMsg(),
        'imagesAvailable': state.workingDirStatus != -1,
        'allowed': dl3.allowedNextAction(state.action),  # The commands that can be used now
        'hideButtons': bool(state.hidebuttons),
        'canTerminate': state.apiModel != 'SBC',  # DSF stops the plugin itself
        'restart': bool(state.restart),
        'poll': state.poll,
    }

def info_data():
    options = []
    for label, value in dl3.getOptions().items():
        if label.startswith('#'):  # Section names
            continue
        options.append({'label': label, 'value': str(value)})
    return {
        'pid': state.pid,
        'pageAddress': 'http://' + str(state.ip) + ':' + str(state.port),
        'options': options,
        'topDir': state.topDir,
        'imageLocation': state.workingDir if state.workingDirStatus != -1 else '',
        'logFile': state.logfilename,
        'configFile': state.configfile,
    }

def files_data(path):
    # The files and folders in path ('' = the top folder), and what can be done with each
    if path in ['', 'true']:
        path = state.topDir
    if not os.path.isdir(path):
        return None
    try:
        names = os.listdir(path)
    except OSError as e:
        logger.info('No files found: ' + str(e))
        names = []

    jpegfiles = ['.jpeg', '.jpg']
    deletablefiles = ['.mp4', '.zip', '.log']
    kinds = {'.jpeg': 'image', '.jpg': 'image', '.png': 'image', '.mp4': 'video', '.zip': 'zip', '.log': 'log'}
    dirPid = str(state.pid) + '_' + str(state.pidIncrement)  # The current job - not deletable

    entries = []
    for name in names:
        full = os.path.join(path, name)
        try:
            info = os.stat(full)
        except OSError:
            continue
        isDir = os.path.isdir(full)
        ext = os.path.splitext(name)[1].lower()
        deletable = False
        imageFiles = []
        if isDir:
            imageFiles = folderImages(full, jpegfiles)
            deletable = dirPid not in full
        elif ext in deletablefiles and name != 'startup.log' and dirPid not in full:
            deletable = True
        images = len(imageFiles) > 0
        entries.append({'name': name, 'path': full, 'isDir': isDir, 'kind': 'folder' if isDir else kinds.get(ext, 'file'),
                        'size': None if isDir else info.st_size, 'modified': info.st_mtime,
                        'images': len(imageFiles) if isDir else None,
                        'thumbnail': thumbnail(full, imageFiles) if images else (full if kinds.get(ext) == 'image' else None),
                        'canDelete': deletable, 'canZip': deletable and images, 'canVideo': deletable and images})
    entries.sort(key = lambda e: -e['modified'])  # Newest first

    isTop = os.path.realpath(path) == os.path.realpath(state.topDir)
    return {'path': path, 'top': state.topDir, 'parent': None if isTop else os.path.dirname(path), 'entries': entries}

def folderImages(folder, jpegfiles):
    # The images (full paths) in a folder and in its Camera1 / Camera2 subfolders - where a print's images are kept
    found = []
    try:
        names = os.listdir(folder)
    except OSError as e:
        logger.info('Subdirectory error:' + str(e))
        return found
    for name in names:
        full = os.path.join(folder, name)
        if os.path.splitext(name)[1].lower() in jpegfiles:
            found.append(full)
        elif dl3.cameraFolder(full) and os.path.isdir(full):
            try:
                found += [os.path.join(full, f) for f in os.listdir(full) if os.path.splitext(f)[1].lower() in jpegfiles]
            except OSError:
                pass
    return sorted(found, key = os.path.basename)

def thumbnail(folder, imageFiles):
    # The latest Camera1 image (or the latest image if there is no Camera1 image)
    camera1 = [f for f in imageFiles if os.path.basename(f).startswith('Camera1_')]
    return (camera1 or imageFiles)[-1]

def get_file(path):
    if not os.path.isfile(path):
        return PlainTextResponse('Requested file ' + path + ' is not a file.', status_code=404)
    logger.debug('Trying to get file ' + path)
    fn = os.path.basename(path)
    if fn.endswith('.log'):
        return FileResponse(path, filename=fn)  # must be downloaded
    return FileResponse(path, filename=fn, content_disposition_type='inline')  # Can be displayed in browser

def make_video(path, xtratime, cameras = None):
    return dl3.startMakeVideo(path, xtratime, False, cameras) or ''  # False => waits for the video


###########################
# Settings - duetLapse3.json
###########################

# Sections of DEFAULTS shown on their own tab instead of the Config tab
cameraSection = 'Camera'  # Cameras tab
videoSections = ['Video', 'Overrides']  # Video tab
cameraUrls = ['weburl1', 'weburl2']  # Camera1, Camera2
cameraEnables = ['enable1', 'enable2']

def config_values():
    # ({setting: value} from duetLapse3.json, error message or '')
    try:
        config = dl3.readConfig(state.configfile)
    except (OSError, ValueError) as e:
        return {}, 'Could not read the settings file - showing the defaults. ' + str(e)
    return {k: v for section in config.values() if isinstance(section, dict) for k, v in section.items()}, ''

def setting_type(key, default):
    if isinstance(default, bool):  # Before int - bool is a kind of int
        return 'bool'
    if isinstance(default, int):
        return 'int'
    if isinstance(default, list):
        return 'list'
    if key == 'password':
        return 'password'
    return 'str'

def settings_data(names):
    # The settings in the named sections of DEFAULTS - their values, type, choices and help
    values, error = config_values()
    sections = []
    for name in names:
        settings = []
        for key, default in dl3.DEFAULTS[name].items():
            settings.append({'key': key, 'value': values.get(key, default), 'default': default,
                             'type': setting_type(key, default), 'choices': dl3.CHOICES.get(key),
                             'help': dl3.HELP.get(key, ''), 'readonly': key in dl3.configExtras})
        sections.append({'name': name, 'settings': settings})
    return {'configFile': state.configfile, 'error': error, 'sections': sections}

def tab_sections(tab):
    if tab == 'video':
        return videoSections
    return [name for name in dl3.DEFAULTS if name != cameraSection and name not in videoSections]

def update_config_file(settings):
    # Check every value in settings, then save them all to duetLapse3.json - or nothing if any are invalid
    # Settings stay in the section they are in.  Keys duetLapse3 does not know are kept
    # Returns {setting: error} ({} if saved) - '' is used for an error that is not about one setting
    try:
        config = dl3.readConfig(state.configfile)
    except FileNotFoundError:
        config = {}
    except (OSError, ValueError) as e:
        return {'': 'Could not read the settings file. ' + str(e)}
    location = {key: name for name, section in config.items() if isinstance(section, dict) for key in section}

    errors = {}
    for section, keys in dl3.DEFAULTS.items():
        for key, default in keys.items():
            if key in dl3.configExtras or key not in settings:
                continue
            try:
                value = dl3.checkSetting(key, settings[key], default)
            except ValueError as e:
                errors[key] = str(e)
                continue
            config.setdefault(location.get(key, section), {})[key] = value

    if errors:
        return errors
    try:
        dl3.writeConfig(state.configfile, config)
    except OSError as e:
        return {'': str(e)}
    logger.info('Settings saved to ' + state.configfile + ': ' + ', '.join(settings))
    return {}

def save_result(errors, success):
    # The reply to a save - 400 with the errors if nothing was saved
    if errors:
        return JSONResponse({'saved': False, 'errors': errors, 'message': 'Not saved - some settings are invalid'}, status_code=400)
    return {'saved': True, 'errors': {}, 'message': success}

def save_config(settings):
    errors = update_config_file(settings)
    return save_result(errors, 'Saved. Restart duetLapse3 for the changes to take effect.')

def video_length_errors(settings):
    # minvideo can't be more than maxvideo (unless maxvideo is 0 - off)
    values, _ = config_values()
    defaults = dl3.flatDefaults()
    try:
        minvideo = dl3.checkSetting('minvideo', settings.get('minvideo', values.get('minvideo', defaults['minvideo'])), defaults['minvideo'])
        maxvideo = dl3.checkSetting('maxvideo', settings.get('maxvideo', values.get('maxvideo', defaults['maxvideo'])), defaults['maxvideo'])
    except ValueError:
        return {}  # Reported when the values are checked
    if maxvideo > 0 and minvideo > maxvideo:
        return {'minvideo': 'minvideo (' + str(minvideo) + ') can not be more than maxvideo (' + str(maxvideo) + ')',
                'maxvideo': 'maxvideo must be 0 (off) or at least minvideo (' + str(minvideo) + ')'}
    return {}

def save_video(settings):
    # Save the Video and Overrides settings to duetLapse3.json and use them straight away
    keys = [key for section in videoSections for key in dl3.DEFAULTS[section]]
    settings = {key: value for key, value in settings.items() if key in keys}
    errors = video_length_errors(settings)
    if not errors:
        errors = update_config_file(settings)
    if not errors:
        defaults = dl3.flatDefaults()
        for key, value in settings.items():
            value = dl3.checkSetting(key, value, defaults[key])  # Already checked - this converts it
            if key == 'fps':
                dl3.changeFps(value)
            elif key == 'minvideo':
                dl3.changeMinvideo(value)
            elif key == 'maxvideo':
                dl3.changeMaxvideo(value)
            elif getattr(state, key) != value:
                logger.info(key + ' changed to ' + str(value))
                setattr(state, key, value)
        if state.maxvideo > 0 and state.maxvideo < state.minvideo:  # As at startup
            state.maxvideo = state.minvideo
    return save_result(errors, 'Saved. The video settings are in use now.')

def cameras_data():
    values, error = config_values()
    return {'configFile': state.configfile, 'error': error,
            'cameras': [{'number': number, 'key': key, 'url': values.get(key, ''), 'help': dl3.HELP.get(key, ''),
                         'enableKey': cameraEnables[number - 1], 'enabled': values.get(cameraEnables[number - 1], True) is not False}
                        for number, key in enumerate(cameraUrls, start = 1)]}

def save_cameras(settings):
    # Save the camera urls to duetLapse3.json and use them straight away
    urls = {key: str(settings.get(key, '')).strip() for key in cameraUrls}
    errors = {}
    if state.enable1 and not camera.is_http_url(urls['weburl1']):
        errors['weburl1'] = 'Camera1 needs an http url (a snapshot url or an MJPEG stream url) - or switch it off'
    elif urls['weburl1'] != '' and not camera.is_http_url(urls['weburl1']):
        errors['weburl1'] = 'Camera1 url must be an http url, or blank'
    if urls['weburl2'] != '' and not camera.is_http_url(urls['weburl2']):
        errors['weburl2'] = 'Camera2 url must be an http url, or blank for no second camera'
    if not errors:
        errors = update_config_file(urls)
    if not errors:
        for key, url in urls.items():
            if state.simulate in ['all', 'camera']:
                continue  # Keep the simulated camera
            if getattr(state, key) != url:
                logger.info(key + ' changed to ' + url)
                setattr(state, key, url)
    return save_result(errors, 'Saved. The cameras are in use now.')

def enable_camera(key, enabled):
    # Switch a camera on or off - saved to duetLapse3.json and used straight away
    if key not in cameraEnables:
        return JSONResponse({'saved': False, 'errors': {'': 'Unknown camera ' + str(key)}, 'message': 'Not saved'}, status_code=400)
    errors = update_config_file({key: bool(enabled)})
    if not errors:
        setattr(state, key, bool(enabled))
        logger.info('Camera' + key[-1] + (' switched on' if enabled else ' switched off'))
    return save_result(errors, 'Camera' + key[-1] + (' is on' if enabled else ' is off - no images will be taken from it'))

def preview_image(url):
    if state.simulate in ['all', 'camera']:
        return Response(state.simulatedImage, media_type = 'image/jpeg', headers = {'Cache-Control': 'no-store'})
    if not camera.is_http_url(url):
        return PlainTextResponse('Not an http url', status_code = 400)
    data = camera.fetch_image(url)  # The same capture as the time lapse
    if data is None:
        return PlainTextResponse('No image from ' + url, status_code = 502)
    return Response(data, media_type = 'image/jpeg', headers = {'Cache-Control': 'no-store'})


###########################
# Commands
###########################

def update_command(command):
    # start / standby / pause / continue / restart - carried out by the control loop, one at a time.
    # Wait (up to 10 seconds) until it is done, so the page shows the new state
    if command in ['start', 'standby', 'pause', 'continue', 'restart']:
        done = threading.Event()
        dl3.queueAction(command, done)
        done.wait(10)

    elif command == 'terminate':  #command=terminate - backward compatible
        terminate_process('terminatehttp')
    return

def terminate_process(ttype):
    if ttype not in ['terminatehttp','terminateg', 'terminatef']:
       logger.info (ttype + ' invalid terminate requested')
       return

    if ttype in ['terminatehttp', 'terminateg']:
        dl3.queueAction('completed')
    elif ttype == 'terminatef':
        if duet_printer.isPlugin(state.apiModel):
            duet_printer.stopPlugin(state.apiModel, 'duetLapse3')
        else:
            dl3.quit_forcibly()
    return


###########################
# The page
# The routes are plain def (not async) so FastAPI runs them in a thread - several of them wait
###########################

@router.get('/')
@router.get('/index')  # Same as duetPrintGuard
def index(request: Request):
    # Other query parameters (e.g. ?theme=dark&mobile=true from the DWC page) are for the page
    if any(api in legacyPages or api in legacyActions or api == 'getfile' for api in request.query_params):
        return legacy_api(request)  # The older ?<api>=<value> form
    page = os.path.join(appDir, 'index.html')
    if not os.path.isfile(page):
        return PlainTextResponse('The duetLapse3 page has not been built - see ui/README.md', status_code=500)
    return FileResponse(page, headers = {'Cache-Control': 'no-cache'})  # So an updated plugin's page is used

@router.get('/api/status')
def api_status():
    return status_data()

@router.get('/api/info')
def api_info():
    return info_data()

@router.get('/api/files')
def api_files(path: str = ''):  # '' = the top folder
    data = files_data(path)
    if data is None:
        return JSONResponse({'detail': 'Requested path ' + path + ' is not a folder.'}, status_code=404)
    return data

@router.get('/api/settings')
def api_settings(tab: str = 'config'):  # config or video
    return settings_data(tab_sections(tab))

@router.get('/api/cameras')
def api_cameras():
    return cameras_data()

@router.post('/config/save')
def config_save(settings: dict = Body(...)):  # {setting: value}
    return save_config(settings)

@router.post('/video/save')
def video_save(settings: dict = Body(...)):  # {setting: value}
    return save_video(settings)

@router.post('/cameras/save')
def cameras_save(settings: dict = Body(...)):  # {weburl1: url, weburl2: url}
    return save_cameras(settings)

@router.post('/cameras/enable')
def cameras_enable(settings: dict = Body(...)):  # {key: enable1 | enable2, enabled: true | false}
    return enable_camera(settings.get('key'), settings.get('enabled'))

@router.get('/camera/preview')
def camera_preview(url: str):  # One image from the camera url, fetched by duetLapse3
    return preview_image(url)


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
def snapshot(camera: int = 0):  # camera 1 or 2 makes a video for that camera only - default both
    if state.workingDirStatus != -1:
        return make_video(state.workingDir, False, ['Camera' + str(camera)] if camera in [1, 2] else None)  # False => no extratime
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

# Calls that return something
legacyPages = {
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
    if result is not None:
        return PlainTextResponse(result)
    return Response(status_code=204)
