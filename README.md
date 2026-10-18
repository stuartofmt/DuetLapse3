## UNDER CONSTRUCTION

# duetLapse3

Time-lapse videos of prints on Duet3D printers. duetLapse3 takes an image from one or two cameras each layer (or at a set interval, or on pause) and turns them into a video when the print finishes.

This branch is version 6 for DWC / DSF 3.7. It runs as a DWC plugin on an SBC (for example, a Raspberry Pi), with its own page under **Plugins → duetLapse3** in DWC.

## Upgrading from DuetLapse3 (version 5 or earlier)

The plugin has been renamed from `DuetLapse3` to `duetLapse3`, so DWC treats it as a different plugin.

1. **Uninstall the old `DuetLapse3` plugin** before you install this one.
2. **Move your settings.** The settings file is now `sys/duetLapse3/duetLapse3.json`, replacing `sys/DuetLapse3/DuetLapse3.config`. Set your values again on the duetLapse3 page (see [Settings](#settings)): the old `.config` file and command-line options are no longer read.
3. **The port is now chosen automatically** if `UI_port` is 0, and the DWC page finds it without any setup. If you give a port and it is already in use, duetLapse3 picks a free one instead of stopping.
4. **gcode commands.** Commands now start with `duetLapse3.`, but the old `DuetLapse3.` still works, so you don't need to change existing slicer gcode.
5. **No firmware version check.** duetLapse3 no longer refuses to run on a firmware version it doesn't expect. The firmware version is shown on the Status tab.
6. **One logfile.** The log is now `duetLapse3.log`, next to `duetLapse3.json` (`sys/duetLapse3/duetLapse3.log` for the plugin). It starts fresh each time duetLapse3 starts, instead of a separate log for each print.
7. **Only http cameras are supported.** Set `camera1_url` (and `camera2_url` for a second camera) on the Cameras tab to the camera's snapshot URL, or its MJPEG stream URL (see [Cameras](#cameras)). USB and Pi cameras can no longer be used directly: use a camera server such as multiCam, ustreamer or crowsnest to give them a URL. The `camera1`, `camera2`, `camparam1` and `camparam2` settings have been removed (if they are in the json, they are ignored with a warning).

## Installing

1. In DWC, go to **Settings → Plugins → External plugins → Install plugin** and choose the duetLapse3 zip.
2. The plugin installs the `M3291.g` macro in `/sys`. duetLapse3 uses it to receive commands from gcode.
3. Start the plugin, open its page, and on the **Cameras** tab enter your camera's URL (see [Cameras](#cameras)) and press **Save**.

DSF installs the Python packages duetLapse3 needs (from `requirements.txt`) when the plugin is installed.

## Settings

Settings are in `sys/duetLapse3/duetLapse3.json`. Change them on the **Cameras**, **Video**, **Execution**, **Files** and **Config** tabs of the duetLapse3 page. Settings on the Execution, Files and Config tabs take effect when duetLapse3 is restarted.

The file can't be edited by hand: it is compressed and encoded, with a checksum. If it is missing, damaged or edited, duetLapse3 creates a new one with the default values (and says so in the log). If a setting has the wrong kind of value, duetLapse3 says which one in the log and doesn't start.

The log is `duetLapse3.log`, in the same folder.

The main settings are:

| Setting | Default | What it does |
| --- | --- | --- |
| `camera1_url` | | Required. URL of Camera1: a snapshot URL (preferred) or an MJPEG stream URL |
| `camera2_url` | | URL of an optional second camera |
| `camera1_on`, `camera2_on` | `true` | Whether each camera is used. Off keeps its URL but takes no images |
| `capture_on` | `layer` | When to take images: `layer` (each layer change), `pause` (when the job pauses itself) or `timed` (only by `capture_seconds`) |
| `capture_seconds` | `0` | Also take an image every n seconds (0 = off) |
| `layer_interval` | `1` | Take an image every n layers |
| `park` | `false` | Pause the print and park the head before each image (from layer 1), then resume |
| `park_xy` | `[0, 0]` | Where to park the head (X, Y) when `park` is on. `[0, 0]` = don't move it |
| `park_wait` | `1` | Seconds to wait after parking, before the image |
| `start_now` | `false` | Start taking images straight away, without waiting for a print |
| `standby` | `false` | Wait for a start command before doing anything |
| `norestart` | `false` | Stop duetLapse3 when the print finishes, instead of getting ready for the next print. As a plugin, it then has to be started again in DWC |
| `fps` | `10` | Video frames per second |
| `min_video_seconds` | `5` | Shortest video to make (seconds) |
| `video_length` | `0` | Fixed video length in seconds (0 = off) |
| `end_hold` | `0` | Seconds to hold the last image at the end of the video |
| `ffmpeg_threads` | `0` | CPU threads ffmpeg may use for each video. 0 = automatic: the cores that are free when the video starts, always leaving one spare, shared with any other ffmpeg already running (e.g. another duetLapse3 making a video). ffmpeg also runs at low priority, so making a video doesn't slow the printer |
| `no_video` | `false` | Don't make a video |
| `delete_images` | `false` | Delete the images when duetLapse3 terminates |
| `keep_files` | `false` | Don't delete files on startup or shutdown |
| `no_log` | `false` | No logfile |
| `image_dir` | | Where images and videos go. Blank = the settings folder (with `duetLapse3.json` and the log): `sys/duetLapse3` for the plugin. Inside it they go in `<computer name>/<printer address>/` folders |
| `duet_password` | `reprap` | Printer password |
| `verbose` | `false` | Detailed logging |
| `UI_port` | `0` | Port for the duetLapse3 page. 0 picks a free port from 17800 upwards. The Config tab shows the port in use |
| `UI_ip` | | Set by duetLapse3 to this computer's IP address (the page's address). You don't need to change it |
| `instances` | `single` | `single`: only one duetLapse3 can run. `one_per_folder`: one for each settings folder. `many`: no limit |
| `duet_ip` | (blank) | The printer's address (SBC or standalone). Blank = the computer duetLapse3 runs on, which is right for the plugin |
| `duet_port` | `80` | The printer's port. Blank or 0 = 80 |
| `simulate` | `off` | For testing: `all`, `printer` or `camera` are simulated |

## Cameras

duetLapse3 gets its images from http cameras. Each camera needs a URL that is either:

- **a snapshot URL** (preferred), which returns one JPEG image, for example `http://192.168.1.20:8081/snapshot`, or
- **an MJPEG stream URL**, for example `http://192.168.1.20:8081/stream`. duetLapse3 takes the first image from the stream and closes the connection.

A snapshot URL is quicker and uses less of the SBC and the camera server. The image is saved exactly as the camera sends it, without being re-compressed.

To check a URL, use **Preview** on the Cameras tab, or open it in a browser: a snapshot URL shows a single still image, and a stream URL shows live video. Other kinds of stream, such as RTSP or H.264, can't be used.

USB and Pi cameras need a camera server to give them a URL, for example multiCam, ustreamer, mjpg-streamer or crowsnest. A URL that needs a login can include it: `http://user:password@192.168.1.20/snapshot`.

## The duetLapse3 page

Open **Plugins → duetLapse3** in DWC. The page has the same look as DWC 3.7 and follows its light or dark theme. It also works on its own in a browser, at the address shown in the log. It has seven tabs:

- **Status:** the controls (start, standby, pause, continue, restart and terminate), what duetLapse3 is doing, and the last image.
- **Video:** the images captured by each camera against the number needed for a video, make a video now (**Snapshot**, one for each camera when there are two), and the video settings (the Video section of `duetLapse3.json`). **Save** saves them and starts using them straight away.
- **Images:** browse the images, videos and zip files. Each print has a folder with a folder for each camera, holding its `images` and `videos`. Browse them as a list or a grid with thumbnails, with search and sorting. Images and videos open in a viewer. Each item's menu has download, make a video, zip and delete.
- **Cameras:** the URL of each camera, with a preview, and a switch to turn the camera on or off (the URL is kept). **Preview** shows a new image from the URL in the box, and **Save** saves the URLs to `duetLapse3.json` and starts using them straight away.
- **Execution:** when images are taken (the Execution section of `duetLapse3.json`).
- **Files:** logging, and what happens to images, videos and logs: `no_log`, `verbose`, `no_video`, `delete_images` and `keep_files` (the Files section).
- **Config:** the other settings in `duetLapse3.json`, including the Pause section (`park`, `park_xy` and `park_wait`). `image_dir` shows the folder in use when it's blank, `duet_ip` the printer address in use, and `UI_port` the page's port.

On the Execution, Files and Config tabs, **Save** checks every value first and saves nothing if any are wrong. Restart duetLapse3 for the changes to take effect.

Inside DWC, the plugin page shows a message if duetLapse3 stops, and shows the page again when it restarts.

The page is in the browser's language when there is a translation for it, otherwise English. Add `?lang=<code>` to the address to choose one, e.g. `?lang=en`. Only English exists so far; see `ui/README.md` to add a language.

## Controlling duetLapse3 from gcode

Use the `M3291` macro to send a command, for example in your slicer's start or end gcode:

```text
M3291 B"duetLapse3.start"
```

| Command | What it does |
| --- | --- |
| `duetLapse3.start` | Start taking images |
| `duetLapse3.standby` | Stop and delete the images, without making a video |
| `duetLapse3.pause` | Stop taking images for now |
| `duetLapse3.continue` | Carry on after a pause |
| `duetLapse3.restart` | Make the video, then get ready for the next print |
| `duetLapse3.snapshot` | Make a video of the images so far |
| `duetLapse3.graceful` | Finish capture: make the video, then get ready for the next print (or stop, if `norestart` is set) |
| `duetLapse3.forced` | Terminate straight away, without a video |
| `duetLapse3.change.<setting>=<value>` | Change a setting while running (until duetLapse3 restarts - it isn't saved), e.g. `duetLapse3.change.capture_seconds=30` |

The settings `change.` can set are `capture_seconds`, `capture_on`, `layer_interval`, `park`, `park_xy`, `park_wait`, `start_now`, `standby`, `norestart`, `no_video`, `keep_files`, `fps`, `min_video_seconds`, `video_length`, `end_hold` and `verbose`. On/off settings take `True` or `False`, and `park_xy` takes two numbers, e.g. `duetLapse3.change.park_xy=10,200`.

## Running without DWC

duetLapse3 can also run on its own:

```bash
python duetLapse3.py [folder]
```

- `folder` is where `duetLapse3.json` and `duetLapse3.log` are. If you leave it out, they go in the same folder as `duetLapse3.py`.
- All settings are in `duetLapse3.json` (see [Settings](#settings)), changed on the page. On the first run it can't find the printer yet: enter the printer's address (and port, if it isn't 80) in the banner on the page and press **Save and connect**. duetLapse3 can run on a different computer from the printer.
- For testing, `"simulate": "all"` runs without a printer or camera.

The page is at `http://<this computer>:<port>`. It answers on every address of the computer (its IP, `localhost`, a hostname). The address is shown in the log (`duetLapse3 page: http://…`).

## Web API

The duetLapse3 page uses these URLs, and you can call them yourself, for example from a script. All of them use GET. A list of the routes is also at `http://<this computer>:<port>/docs`.

| URL | What it does |
| --- | --- |
| `/command/<command>` | `start`, `standby`, `pause`, `continue` or `restart` |
| `/snapshot` | Make a video of the images so far (`?camera=1` or `?camera=2` for one camera) |
| `/makevideo?path=<folder>&xtratime=false` | Make a video from an image folder |
| `/videosettings?fps=<n>&minvideo=<n>&maxvideo=<n>` | Change the video settings (give any of them): `minvideo` sets `min_video_seconds`, `maxvideo` sets `video_length`. The parameter names are kept from earlier versions |
| `/getfile?path=<file>` | Download a file |
| `/zip?path=<folder>` | Zip an image folder |
| `/delete?path=<file or folder>` | Delete a file or folder |
| `/terminate/terminateg` | Finish capture: make the video, then get ready for the next print (or stop, if `norestart` is set) |
| `/terminate/terminatef` | Terminate the program straight away, without a video |

The page reads its data as JSON, which scripts can use too:

| URL | What it returns |
| --- | --- |
| `/api/status` | What duetLapse3 and the printer are doing, images captured, layer, last image |
| `/api/events` | The same status as Server-Sent Events, sent whenever it changes, plus `files` and `settings` events when files are deleted or zipped and when the settings are saved |
| `/api/files?path=<folder>` | The files in a folder (blank = the top folder) |

The Config, Execution, Files, Video and Cameras tabs save with a POST of the settings as JSON to `/config/save` (Config, Execution and Files), `/video/save` and `/cameras/save`. `/camera/preview?url=<camera url>` returns one image from a camera url. The page itself is built from `ui/` (see `ui/README.md`).

Action URLs from earlier versions, such as `http://<this computer>:<port>/?command=start`, still work. The old `?displayStatus` style calls, which returned parts of the old page, have been removed; use `/api/status` and the other JSON URLs instead.
