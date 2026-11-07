# duetLapse3

Time-lapse videos of prints on Duet3D printers. duetLapse3 takes an image from one or two cameras each layer (or at a set interval, or on pause) and turns them into a video when the print finishes.

This branch is version 6 for DWC / DSF 3.7. It runs as a DWC plugin on an SBC (for example, a Raspberry Pi), with its own page under **Plugins → duetLapse3** in DWC. It can also [run on its own](#running-without-dwc), on Linux, macOS or Windows.

More documents:

- [Controlling duetLapse3 from gcode](docs/gcode.md) - the `M3291` commands for slicer start / end gcode
- [Web API](docs/web-api.md) - the URLs the page uses, for scripts

# Installing as a plugin

1. In DWC, go to **Settings → Plugins → External plugins → Install plugin** and choose the duetLapse3 zip.
2. The plugin installs the `M3291.g` macro in `/sys`. duetLapse3 uses it to receive [commands from gcode](docs/gcode.md). It needs RepRapFirmware 3.5 or later.
3. Start the plugin, open its page, and on the [Cameras](#cameras) tab enter your camera's URL and press **Save**.

## The duetLapse3 page

Open **Plugins → duetLapse3** in DWC. The page has the same look as DWC 3.7 and follows its light or dark theme. It also works on its own in a browser, at the address shown in the log. Inside DWC, the plugin page shows a message if duetLapse3 stops, and shows the page again when it restarts.

The page updates by itself as things change - there's no need to reload it.

The settings are kept in `duetLapse3.json` (in `sys/duetLapse3` for the plugin) and are changed on the page: the file can't be edited by hand. If it is missing or damaged, duetLapse3 makes a new one with the default values.

The page is in the browser's language when there is a translation for it, otherwise English. Add `?lang=<code>` to the address to choose one, e.g. `?lang=en`. Only English exists so far; see [ui/README.md](ui/README.md) to add a language.

### If the printer can't be found

While duetLapse3 isn't connected to the printer, every tab shows a banner. duetLapse3 keeps trying; to change the printer's address, port or password, enter them and press **Save and connect**. If the printer refuses the password, duetLapse3 stops trying until it is changed here.

![The printer banner](docs/images/printer-banner.png)

### Status

![The Status tab](docs/images/status.jpg)

- **Controls:**
  - **Start** - start taking images.
  - **Standby** - stop and delete the images, without making a video.
  - **Pause** / **Continue** - stop taking images for now, and carry on.
  - **Restart** - make the video, read the settings again, then get ready for the next print. Any changes you've saved are picked up, as if duetLapse3 had been started again, including a different printer, image folder or page port (the page moves to the new port). If the saved settings can't be used, an alert shows at the top of the page and the current ones are kept. Restart can also be used in standby. The automatic restart at the end of a print doesn't read the settings.
  - Buttons that can't be used now are greyed out.
- **Finish capture** and **Terminate the program** appear here when duetLapse3 runs on its own. As a plugin they're hidden, because DWC starts and stops it.
  - **Finish capture** makes the video, then gets ready for the next print, or stops if **No restart** is set.
  - **Terminate the program** stops straight away, without a video.
- **Status** - what duetLapse3 and the printer are doing, the images captured by each camera, the current layer, how long the video will be, and the printer's address and firmware.
- **Last image** - the latest image captured.

### Video

![The Video tab](docs/images/video.png)

- **Make a video now** - the images captured by each camera against the number needed for a video. **Snapshot** makes a video of the images so far (one button for each camera when there are two); it's greyed out until there are enough images.
- When a video is made - here, at the end of a print, or from gcode - a message in the corner says so, with a link to open it.
- The video settings are used as soon as they are saved:

| Setting | Name in `duetLapse3.json` | Default | What it does |
| --- | --- | --- | --- |
| Extra Time | `end_hold` | `0` | Seconds to hold the last image at the end of the video |
| Video FPS | `fps` | `10` | Video frames per second |
| Minimum video length | `min_video_seconds` | `5` | No video is made if it would be shorter than this (seconds) |
| Maximum video length | `video_length` | `0` | 0 = off. Otherwise the images are fitted into a video this many seconds long |
| Video Creation Load | `ffmpeg_threads` | `0` | CPU cores ffmpeg may use for each video. 0 = automatic: the cores that are free, leaving one spare, shared with any other ffmpeg running. ffmpeg also runs at low priority, so making a video doesn't slow the printer |

### Cameras

![The Cameras tab](docs/images/cameras.jpg)

duetLapse3 takes its images from one or two http cameras. Each needs a URL that is either:

- **a snapshot URL** (preferred), which returns one JPEG image, for example `http://192.168.1.20:8081/snapshot`, or
- **an MJPEG stream URL**, for example `http://192.168.1.20:8081/stream`. duetLapse3 takes the first image from the stream.

A snapshot URL is quicker and uses less of the SBC and the camera server. Other kinds of stream, such as RTSP or H.264, can't be used. USB and Pi cameras need a camera server to give them a URL, for example multiCam, ustreamer, mjpg-streamer or crowsnest. A URL that needs a login can include it: `http://user:password@192.168.1.20/snapshot`.

- **Preview** shows a new image from the URL. To check a URL, you can also open it in a browser: a snapshot URL shows a still image, a stream URL shows live video.
- **Save** saves both URLs (`camera1_url`, `camera2_url`) and starts using them straight away.
- The switch beside each camera turns it on or off (`camera1_on`, `camera2_on`). Off keeps the URL but takes no images.

### Config

The settings, on four tabs of their own. Changes take effect when you press **Restart** on the Status tab. **Save** checks every value first and saves nothing if any are wrong, or if settings conflict, such as a Park Location with Park before image off.

#### General

![The General tab](docs/images/config.png)

| Setting | Name in `duetLapse3.json` | Default | What it does |
| --- | --- | --- | --- |
| Printer IP address | `duet_ip` | blank | The printer's address (SBC or standalone). Blank = the computer duetLapse3 runs on, which is right for the plugin. The address in use is shown below the field |
| Printer port | `duet_port` | `80` | The printer's port. Blank or 0 = 80 |
| Printer password | `duet_password` | `reprap` | The printer's password |
| Image folder | `image_dir` | blank | Where images and videos go. Blank = the settings folder (`sys/duetLapse3` for the plugin); the folder in use is shown in the field. Inside it they go in `<computer name>/<printer address>/` folders |
| Allow multiple instances | `allow_multiple_instances` | off | Let more than one duetLapse3 run on this computer. When off, a second one stops at once (exit code 6). When on, each one must use a different settings folder (see [Running without DWC](#running-without-dwc)) |
| UI port | `UI_port` | `0` | Port for the duetLapse3 page. 0 picks a free port from 17800 upwards; the port in use is shown below the field |
| Open browser at startup | `open_browser` | on | Open the page in this computer's default browser when duetLapse3 starts. Not used when running as a DWC plugin, or on Linux without a desktop (e.g. over ssh) |
| UI ip | `UI_ip` | | Set by duetLapse3 to this computer's IP address (the page's address) |

#### Image Capture

![The Image Capture tab](docs/images/capture.png)

When images are taken.

| Setting | Name in `duetLapse3.json` | Default | What it does |
| --- | --- | --- | --- |
| Timed capture | `capture_seconds` | `0` | Also take an image every n seconds (0 = off). The least is 20 |
| Event capture | `capture_on` | On layer change | **On layer change** (`layer`): an image at each layer change. **When paused in print job** (`pause`): each time the print's own gcode pauses it (e.g. an `M226` added by the slicer), the head moves to Park Location if set, then duetLapse3 takes an image and resumes the print. Any other pause is resumed too, including one made by hand in DWC. **Timed Only** (`timed`): images only by Timed capture, starting straight away |
| Layers between capture | `layer_interval` | `1` | With On layer change, take an image every n layers. Not used with Park before image on: see Layers between Park |
| Park before image | `park` | off | Pause the print and park the head before each image (from layer 1), then resume |
| Park Location | `park_xy` | `0, 0` | Where to park the head (X, Y). 0, 0 = don't move it |
| Rest Time | `park_wait` | `1` | Seconds to wait after parking, before the image |
| Minimum Layers | `park_min_layers` | `3` | With Park before image on, no images are taken, and the print isn't paused, until the layer is above this. The default 3 means the first image is at layer 4 |
| Layers between Park | `park_layer_interval` | `3` | With Park before image on and Event capture On layer change, park and take an image every n layers, starting at the first layer above Minimum Layers. With both at 3, the images are at layers 4, 7, 10 and so on. Layers between capture isn't used while Park before image is on |

**Parking pauses the print** for each image. Setting **Minimum Layers** or **Layers between Park** lower parks more often, and earlier in the print, which may result in poor prints.

#### Execution

![The Execution tab](docs/images/execution.png)

When duetLapse3 starts and stops.

| Setting | Name in `duetLapse3.json` | Default | What it does |
| --- | --- | --- | --- |
| When to start | `start_mode` | When a print starts | See below |
| No restart | `norestart` | off | Stop duetLapse3 when the print finishes, instead of getting ready for the next print. As a plugin, it then has to be started again in DWC |

**When to start** has three choices:

| Choice | Value | What happens |
| --- | --- | --- |
| **When a print starts** | `on_print` | The usual setup. duetLapse3 waits, then starts capturing when a print begins |
| **Straight away** | `now` | Starts capturing as soon as duetLapse3 is ready, whatever the printer is doing. This includes after each print, so images are taken between prints, and they go in the next print's video |
| **Wait for the Start command** | `standby` | Does nothing until the Start button or command. Then it starts capturing when a print begins. A print that runs without it gets no images |

With **When a print starts**:

1. **Waiting:** with the printer idle, the Status tab shows Waiting and no images are taken.
2. **The print begins:** when the printer's status becomes `processing`, duetLapse3 starts capturing. A print that's already running when it starts counts too, and so does one that's paused or pausing, unless Event capture is Timed Only.
3. **Images:** these follow the settings on the [Image Capture](#image-capture) tab.
4. **The print ends:** it makes the video, starts a new log and gets ready for the next print, unless **No restart** is on.

With **Wait for the Start command**, it goes back to waiting for the command after each print.

There are two exceptions when Event capture is **Timed Only**:

- **Timed capture above 0:** duetLapse3 doesn't wait for a print. It starts capturing straight away, or as soon as you press Start with **Wait for the Start command**.
- **Timed capture 0:** no images are taken, so there's no video.

#### File Settings

![The File Settings tab](docs/images/files.png)

Logging, and what happens to the images and videos.

| Setting | Name in `duetLapse3.json` | Default | What it does |
| --- | --- | --- | --- |
| Disable Logging | `no_log` | off | No log file. Only useful on a read-only file system |
| Verbose Logging | `verbose` | off | Very detailed logging, for finding problems |
| No Video | `no_video` | off | Don't make a video |
| Delete Images | `delete_images` | off | Delete the images when a print finishes, after its video is made (videos are kept) |
| Keep Files | `keep_files` | off | Don't delete images when duetLapse3 starts or a print finishes. Standby still deletes them, and videos are always kept |

The log is `duetLapse3.log`, next to `duetLapse3.json`. A new log starts each time duetLapse3 starts and for each print: at the end of a print, or when you press **Restart**. The one before it is kept as `duetLapse3.previous.log`. See both on the [Log](#log) tab.

### Files

The images, videos and log, on two tabs of their own.

#### Images

![The Images tab](docs/images/images-grid.jpg)

Browse the images, videos and zip files. Each print has its own folder, named after the print job, with a folder for each camera holding its `images` and `videos`.

- View the folder as a list or a grid with thumbnails, search it, and sort by date, name or size.
- Click an image or a video to view it. In the viewer, the arrows (or the arrow keys) step through the images.
- Each item's **⋮** menu has download, make a video, zip and delete. The folder of the print being captured can't be deleted.
- The tab refreshes by itself as images are captured and videos are made.

![The image viewer](docs/images/images-viewer.jpg)

#### Log

![The Log tab](docs/images/log.png)

The current log file, `duetLapse3.log`. It opens at the newest line and new lines appear as they are written. **Previous log** downloads the log from before the current one.

- **Follow** keeps the newest line in view. Scrolling up to read turns it off, and scrolling back to the end turns it on again.
- The box at the top shows only the lines containing what you type.
- The buttons reload the log and download the whole file. A long log opens at its last 256 KB, and the page keeps up to 10,000 lines; the download has everything.
- Passwords are not written to the log: the printer's password and any login in a camera URL appear as `***`.

If **Disable Logging** is on (Config, File Settings tab), there is no log to show. For much more detail, turn on **Verbose Logging** on the same tab and press **Restart**.

## Running without DWC

duetLapse3 can also run on its own, on the same computer as the printer or another one. Download the standalone zip from the release, unzip it, and run `run.bat` (Windows) or `run.sh` (Linux, macOS). The first time, it makes a Python environment and installs what duetLapse3 needs.

Or run it with Python yourself:

```bash
python duetLapse3.py [folder]
```

- `folder` is where `duetLapse3.json` and `duetLapse3.log` are. If you leave it out, they go in the same folder as `duetLapse3.py`.
- **More than one duetLapse3:** with **Allow multiple instances** on, each one must be started with a different `folder`. duetLapse3 doesn't check this. Two sharing a folder would use the same settings and mix up each other's logs.
- On the first run it can't find the printer yet: enter the printer's address (and port, if it isn't 80) in the [banner](#if-the-printer-cant-be-found) on the page and press **Save and connect**.
- The page is at `http://<this computer>:<port>`. It answers on every address of the computer (its IP, `localhost`, a hostname). The address is shown in the log (`duetLapse3 page: http://…`).
- **ffmpeg** makes the videos. On Linux install it with `sudo apt install ffmpeg` (macOS: `brew install ffmpeg`). On Windows nothing extra is needed: `run.bat` installs `imageio-ffmpeg` (from `Code\dsf\requirements-windows.txt`), which includes ffmpeg. An ffmpeg on the PATH is used first, if there is one. The included ffmpeg is a GPL build (it contains the x264 H.264 encoder).
