# duetLapse3 6.0.0 – change notes

What changed since the 3.6 version (DuetLapse3 5.3.7, for DWC / DSF 3.6), described by what it does rather than how the code does it. This is the work for the 3.7.x branch (DWC / DSF 3.7).

## At a glance

- **Everything is on the page.** The page is rebuilt with the DWC 3.7 look and DWC's light or dark theme, and updates by itself. All settings are saved from it. There are no command-line options or hand-edited config file. **Restart** applies saved settings without restarting the program.
- **New layout.** The tabs are Status, Video, Cameras, Config (General, Image Capture, Execution, File Settings) and Files (Images, Log).
- **Easier setup.** If the printer can't be reached, every tab shows a banner to correct its address, port and password. The Cameras tab has a preview and an on/off switch for each camera. On Windows, `run.bat` sets everything up, including ffmpeg.
- **Better capture.** On an SBC, images are taken at the moment the layer changes. There's no wait after a print, and duetLapse3 gets ready for the next print by default. Pause stops images, and **When paused in print job** takes one image per pause, then resumes the print.
- **Better files and videos.** Each print has a folder per camera, and videos are kept when images are cleaned up. Videos play in browsers and on phones. The Images tab is a file browser with thumbnails, search and a viewer.
- **Easier to see what's happening.** The Log tab follows the log live, each print gets its own log, and settings that aren't applied raise an alert on the page.
- **Long-standing bugs fixed:** see [Bug fixes](#bug-fixes).

### What you need to do

- **Reinstall.** The name and plugin id changed from **DuetLapse3** to **duetLapse3**, so uninstall the old plugin first. Old settings have to be entered again.
- **Change your slicer gcode.** `M3291 B"DuetLapse3.start"` becomes `M3291 B"/command/start"`, and setting changes become `/change?capture_seconds=30`. Old commands are logged as not recognised, and aren't carried out. See [gcode](docs/gcode.md).
- **Use an http camera.** A snapshot or MJPEG URL is required. USB, Pi and RTSP cameras need a camera server.
- **Check your firmware.** `M3291` needs RepRapFirmware 3.5 or later.
- **Removed features.** Special functions (running SBC commands from gcode), simulation mode and the Info tab are gone.

## Installing and upgrading

- **New plugin id.** It installs to `plugins/duetLapse3`, and DWC shows it under **Plugins → duetLapse3**. Uninstall the old `DuetLapse3` plugin first.
- **Settings file.** Settings are in `sys/duetLapse3/duetLapse3.json`, replacing `sys/DuetLapse3/DuetLapse3.config`. Old settings have to be copied across by hand.
- **Python packages.** DSF installs them from `requirements.txt`: requests, psutil, dsf-python, fastapi, uvicorn and websocket-client, each pinned to a version.
- **Python 3.11 or later.** duetLapse3 checks this when it starts, and stops with a message if the Python is older. 3.11 is what Raspberry Pi OS Bookworm has.
- **Version.** It's 6.0.0, read from `plugin.json`, so the version only lives in one place.
- **DWC page.** It finds duetLapse3's address from the plugin data that duetLapse3 publishes at startup, instead of reading `-duet`/`-port` from the old `.config`. It shows "The duetLapse3 plugin has stopped" if the program stops, and shows the page again when it restarts. The page itself is a copy of duetPrintGuard's, which uses the current DWC API.
- **Gcode commands changed.** Commands are now the web API's paths, such as `M3291 B"/command/start"`. The old `DuetLapse3.` and `duetLapse3.` spellings are logged as not recognised, and aren't carried out.

## Settings

- **One settings file.** `duetLapse3.json` is the only source of settings. The command-line options (argparse), `-file` and the `logtype` option are gone.
- **Where the file is.** The program takes one optional argument: the folder for `duetLapse3.json` and `duetLapse3.log`. With no argument, that's the program's own folder. If the folder doesn't exist, it's created. If the file is missing, damaged or edited, it's created again with the defaults.
- **Simpler M3291.** The macro is now a short ring of the last 10 commands (`global.DL3seq`, `global.DL3msg`) that duetLapse3 only reads. It no longer sends `set global.DL3del` / `M3291 B"Del"` back after each command or `M3291 B"Clear"` at startup, so it needs no write access to the printer. Needs RepRapFirmware 3.5 or later.
- **ffmpeg on Windows.** The standalone `run.bat` installs `imageio-ffmpeg` (`Code/dsf/requirements-windows.txt`), which includes ffmpeg, so it doesn't have to be installed separately. ffmpeg on the PATH is still used first, and the plugin uses the system ffmpeg as before.
- **Restart picks up the settings.** The Restart button (and `/command/restart`, from gcode or http) now reads `duetLapse3.json` again and uses it, as if duetLapse3 had been started again: all the settings, including another printer, image folder, page port and logging. If the saved settings can't be used, the page shows an alert and the current ones are kept, rather than stopping duetLapse3. The automatic restart at the end of a print doesn't read them.
- **Conflicting settings.** Save refuses settings that conflict, such as a Park Location with Park before image off. A gcode or API `/change` that would conflict isn't applied, and the page shows an alert.
- **Gcode commands go through the web API.** Each gcode command is now a request to the web API: `M3291 B"/command/start"`, `/snapshot`, `/terminate/terminateg`, `/terminate/terminatef` and the new `/change?<setting>=<value>` replace `duetLapse3.start` and the rest. Slicer gcode using the old spellings needs changing: they are logged as not recognised.
- **Print job names.** Images taken with no print job running went in a folder named after the previous job, because the printer keeps that name after a job ends. A folder now only gets a job's name while that job is running. If a print then starts, the folder takes its name.
- **No wait after a print.** duetLapse3 waited up to a minute after every print for the printer to clear the job name, which it doesn't do, so images could be missed if another print started straight away.
- **When to start.** `start_mode` (When to start) replaces `start_now` and `standby`: `on_print`, the default, `now` or `standby`. Having both on is no longer possible. `start_now` and `standby` in a settings file are ignored, so duetLapse3 goes back to starting when a print starts until this is set. Slicer gcode that changes them needs `/change?start_mode=`.
- **Park only when an image is due.** With Park before image and On layer change, the print was paused and parked at every check, about every 12 seconds, even when no image was due, starting during the first layer. It now parks once per image. No images are taken until the layer is above **Minimum Layers** (`park_min_layers`, default 3). It then parks every **Layers between Park** layers (`park_layer_interval`, default 3), and those are the only images while Park before image is on.
- **Printer switched off with an SBC.** When the Duet board lost power but the SBC stayed on, duetLapse3 logged `Error reading the M3291 commands` every second and "Reconnected to printer" every few seconds, for as long as the board was off. It now shows the printer as off and waits quietly until it's back.
- **Gcode fix.** `/change?layer_interval=` is now accepted, as documented.
- **Gcode security fix.** `change` values were run as Python code, so a crafted value in gcode could run code on the computer running duetLapse3. They are now checked like saved settings, and a bad value isn't applied and shows the alert.
- **Restart fixes.** Restart did nothing with No Video on, and couldn't be used in standby.
- **Terminate buttons when running on its own.** Finish capture and Terminate the program now show whenever duetLapse3 isn't running as the plugin. They were hidden for any printer with an SBC, so a standalone duetLapse3 (e.g. on Windows) talking to an SBC printer could only be stopped with Ctrl-C.
- **`capture_on: pause` (When paused in print job) resumes the print.** It never did (in earlier versions too): the print stayed paused and an image was taken every few seconds. Now each pause gets one image, then the print is resumed.
- **Already running on Windows.** Fixed duetLapse3 refusing to start on Windows ("Process is already running"): the venv's python.exe launcher was counted as a second copy.
- **Not shipped.** `duetLapse3.json` isn't in the repository or the plugin: duetLapse3 creates it with the defaults on first start, so an upgrade never overwrites your settings.
- **Not editable by hand.** `duetLapse3.json` is compressed (zlib) and base64 encoded, with a sha256 checksum, so settings are changed on the page. It's written safely (to a temporary file first), so an interrupted save can't damage it.
- **Checked at startup.** Every value is checked when duetLapse3 starts: its type (number, true/false, text, list) and, for some settings, the allowed values. A bad value stops startup with a message naming the setting. Unknown settings are ignored with a warning.
- **Where images and videos go.** `image_dir` blank now means the settings folder, so for the plugin that's `sys/duetLapse3/`, not inside the plugin's install folder. The files are still under `<computer name>/<printer address>/` folders.
- **The printer's address.**
  - `duet_ip` (was `duet`) is the printer address (SBC or standalone). Blank means this computer.
  - `duet_port` is the printer's port. Blank or 0 means 80.
  - duetLapse3 can run on a different computer from the printer.
- **The page address.**
  - `UI_port` (was `port`) 0, the default, picks a free port from 17800 upwards. A port that's already in use also falls back to a free one.
  - The page always listens on every address of the computer. The `host` setting is gone.
  - The computer's IP is shown in the log, saved to the json (`UI_ip`, was `ip`), and published for the DWC page.
- **`allow_multiple_instances`** replaces `instances` (`single`, `one_per_folder`, `many`). It defaults to off: only one duetLapse3 can run on the computer. When it's on, each duetLapse3 must use a different settings folder (this isn't checked). An `instances` value in a settings file is ignored. The instance check also now spots copies started with a full path, which is how DSF starts the plugin.
- **Removed settings:** `camera1`, `camera2`, `camparam1`, `camparam2`, `vidparam1`, `vidparam2` (never used), `logtype`, `host`, `simulate`, `poll` (images are taken at each status or layer change, and timed images are checked every 5 seconds), `maxffmpeg`, `hidebuttons` (the controls always show every button, greyed out when it can't be used), and the Special Functions section: `execkey` and `M3291`.
- **Special functions removed.** Gcode messages can no longer run commands on the SBC (`execkey`). The message macro is always `M3291`; it can no longer be renamed.
- **New Files section.** `no_log`, `verbose`, `no_video`, `delete_images` and `keep_files` moved from Environment to a new Files section. Sections are only for readability, so older files still work.
- **Settings renamed for clarity:**

  | Was | Now |
  | --- | --- |
  | `duet`, `duetport`, `password` | `duet_ip`, `duet_port`, `duet_password` |
  | `ip`, `port` | `UI_ip`, `UI_port` |
  | `basedir` | `image_dir` |
  | `detect`, `seconds`, `numlayers`, `dontwait` | `capture_on`, `capture_seconds`, `layer_interval`, `start_mode` (see below) |
  | `pause` (yes / no), `movehead`, `rest` | `park` (true / false), `park_xy`, `park_wait` |
  | `weburl1`, `enable1`, `weburl2`, `enable2` | `camera1_url`, `camera1_on`, `camera2_url`, `camera2_on` |
  | `maxvideo`, `minvideo`, `extratime`, `ffmpegthreads` | `video_length`, `min_video_seconds`, `end_hold`, `ffmpeg_threads` |
  | `nolog`, `novideo`, `deletepics`, `keepfiles` | `no_log`, `no_video`, `delete_images`, `keep_files` |

  The gcode `/change?<setting>=` commands use the new names (e.g. `/change?capture_seconds=30`). `keeplogs` is removed: per-print logs left by earlier versions are always cleaned up.
- **`restart` replaced by `norestart`** (the opposite). duetLapse3 now gets ready for the next print by default; set `norestart` to stop it when a print finishes. The Graceful terminate button is now **Finish capture**, and Forced terminate is **Terminate the program**. An old `restart` setting is still read.
- **`capture_on none` renamed `capture_on timed`.** `none` is still accepted and read as `timed`.
- **New settings:** `duet_port`, `ffmpeg_threads`, `camera1_on`, `camera2_on`, `allow_multiple_instances`, `start_mode`, `park_min_layers`, `park_layer_interval`.

## The web page

- **Rebuilt** as a Vue 3 and Vuetify 4 page with the DWC 3.7 look: DWC's tab bar, cards, fields, Roboto font and icons. It follows DWC's light or dark theme, including when you change it. It's built from `ui/` (see `ui/README.md`) into `Code/dsf/static/app`, and the built files are committed, so the plugin needs no Node.js.
- **Served** with FastAPI and uvicorn at `/` (and `/index`). The API is listed at `/docs`.
- **Data as JSON.** The page reads `/api/status`, `/api/files`, `/api/settings` and `/api/cameras`. Saving replies with any errors per setting, which are shown in red under the field.
- **Updates as they happen.** Instead of asking for the status every 3 seconds, the page keeps one connection open (`/api/events`, Server-Sent Events) and duetLapse3 sends each change within about a second. Nothing is sent while nothing changes. The Images tab refreshes itself when images are captured, a video is made or files are deleted or zipped, and the settings tabs reload when the settings are saved elsewhere (unless they're being edited). If the connection can't be used, the page falls back to reading the status every 3 seconds.
- **Removed:** the old HTML templates (`dsf/www/`), the `/tab/...` routes and the old `?displayStatus` style calls.
- **Tabs:** Status (with the controls), Video, **Cameras**, **Config**, **Files**. Config has its own tabs: **General**, **Image Capture**, **Execution** and **File Settings**. The main Files tab has **Images** and **Log**. The controls moved onto the Status tab, so there's no separate Controls tab.
  - **Images** is the file browser (it was the Files tab).
  - **Image Capture** holds Timed capture, Event capture and Layers between capture, and a new **Pause** section (`park`, `park_xy`, `park_wait`, `park_min_layers`, `park_layer_interval`). **Execution** has When to start and No restart. **File Settings** has the logging and image clean-up settings.
  - **Ready for other languages.** All the page's text is in `ui/src/locales/en.json`, including duetLapse3's own messages (save results, setting errors, the video message and results, the wrong-password banner), which it now sends with a code and values. The language is `?lang=<code>`, otherwise the browser's language, otherwise English; a partial translation falls back to English for the rest. The page is in English, German, French and Spanish.
  - **Log** shows the current logfile, updated as it grows, with follow, a filter, download and the previous log.
  - **Info tab removed.** The page address is in the log, and the settings in use are written to the log at the start of each print.
  - **Cameras:** each camera's URL with a preview, and an on/off switch (`camera1_on`, `camera2_on`) that keeps the URL. Saving checks the URLs, writes them to the json and starts using them straight away.
  - **Video:** the images captured by each camera, with how many are needed for a video. Then Snapshot (a button for each camera when there are two), plus the Video settings. Saving writes them to the json and starts using them straight away.
  - **Images:** a file browser with a breadcrumb path, list or grid view with thumbnails, search and sorting. Images and videos open in a viewer, and each item has an action menu.
  - **General:** the printer, image folder and page settings. All the Config tabs check values before saving, and changes take effect when you press **Restart**.
- **Action URLs:** `/command/...`, `/snapshot`, `/makevideo`, `/getfile`, `/zip`, `/delete`, `/terminate/...` and `/videosettings`. Old action URLs such as `/?command=start` still work.
- **Relative addresses.** The page uses relative URLs, so it works whatever address it's opened on (IP, hostname, VPN, localhost).
- **Tab in the address.** `?tab=<name>` opens a tab directly.

## Cameras

- **http only.** Each camera is a URL, either a **snapshot URL** (preferred) or an **MJPEG stream URL**, in which case the first frame is used.
- **No external tools.** Images are fetched in Python and saved exactly as the camera sends them, without re-compressing. `wget`, `fswebcam`, `raspistill` and capturing with ffmpeg are no longer used.
- **Removed:** USB and Pi cameras (use a camera server such as multiCam, ustreamer or crowsnest), and RTSP or H.264 streams.
- **Clear failures.** A camera that doesn't answer, returns something other than a JPEG, or streams forever is given up on with a clear log message after at most about 15s.
- **No camera needed to start.** duetLapse3 starts without a camera URL, and the Status tab says to set one on the Cameras tab. An invalid URL disables that camera rather than stopping the program.

## Capture and control

- **Images at the layer change.** On an SBC, images are taken within about 0.1s of the layer change, against 1–7s before, and no layers are missed. On a standalone board, images are taken at the next status check (within 5s).
- **Pause works.** Pause, from the page or gcode, now stops images. The end of the print is still detected and the video still made.
- **Page buttons** wait until the command is actually carried out, so the page shows the new state.
- **Lost printer.** If the printer stops answering, duetLapse3 keeps retrying (every 5s, then every 3 minutes) and carries on in the same state when it's back.
- **Exit codes.** Finish capture (with `norestart`) exits cleanly with code 0, and a forced terminate or Ctrl-C with code 1, instead of killing itself.

## Printer communication

- **SBC.** The printer's state is followed over DSF's WebSocket, the same way DWC does it, instead of polling `/machine/status`. That's about 80% fewer requests. If the WebSocket isn't available, duetLapse3 falls back to http polling and reconnects by itself.
- **Standalone.** One `rr_model` read per check returns the status, layer and position. The job and the M3291 commands are only re-read when the printer says they've changed (RRF's `seqs` counters).
- **One shared read.** Status, layer, job name and head position come from the same read instead of a request each.
- **Firmware version check removed.** The printer's firmware version is shown on the Status tab instead.
- **Can't connect.** While the printer isn't connected, every tab shows a banner with the printer address, port and password. **Save and connect** saves them to `duetLapse3.json` and tries again at once, with no restart needed.
- **Wrong password.** duetLapse3 stops trying and the banner says the password was refused, until it's changed on the page.
- **Standalone login.** Once the board has answered as standalone, the SBC login calls are skipped.

## Videos

- **Still made with ffmpeg**, now:
  - at low priority (`nice`), so the printer software always comes first;
  - with a CPU thread limit worked out from the free cores (`ffmpeg_threads`, 0 = automatic), shared with any other ffmpeg already running. `maxffmpeg` is gone: videos no longer wait for other ffmpeg processes to finish;
  - with the `veryfast` preset, which uses much less CPU;
  - with `-pix_fmt yuv420p`, so videos play in browsers and on phones whatever the camera's JPEG format.
- **Safe with spaces.** ffmpeg runs without a shell, so a path with spaces works.
- **One at a time.** Videos are made one at a time, in order, by a video worker.
- **A folder per camera, with images and videos.** Each print's folder has a folder for each camera, holding its images and its videos: `<print>/Camera1/images/` and `<print>/Camera1/videos/` (videos are named `<print>_Camera1_<Day-HH-MM>.mp4`). A video can be made from a whole print's folder or from one camera's folder.
- **Videos are kept when images are cleaned up.** The startup clean-up, `delete_images` and Standby delete only the images, keep the videos, and remove folders left empty. Folder layouts from earlier versions aren't read.
- **One camera's video.** `/snapshot?camera=1` (or `2`) makes a video for just that camera.
- **`end_hold`** is now added at the end of a print, so those videos are longer than before.

## Logging

- **Startup log.** Until the startup checks pass, messages go to the console and a new `duetLapse3.startup.log` in the program's folder. The first `duetLapse3.log` then starts with them, so they're on the Log tab. A start that stops (a bad setting, a conflict, already running, no ffmpeg) leaves the previous log as it was.
- **One log.** There's one `duetLapse3.log`, next to `duetLapse3.json`, started fresh each time duetLapse3 starts and for each print. The one before it is kept as `duetLapse3.previous.log`. It's no longer moved into each print's folder.
- **Messages.** Log messages use setting names (`capture_on pause`) instead of command-line options (`-detect pause`). The log shows the page address and the printer's full address.

## Bug fixes

Bugs that existed before this work:

- **Pause:** pause from the page or gcode didn't stop images being taken.
- **`end_hold`:** it was never added to the video at the end of a print.
- **Continue:** Continue from the page never returned and kept one CPU core busy.
- **Standalone gcode messages:** M3291 messages didn't work on standalone printers, and an error was logged at every status check.
- **Messages after a printer reset:** gcode messages were ignored after the printer was reset (its message numbers start again).
- **Standalone gcode encoding:** gcode sent to a standalone printer wasn't URL-encoded, so `#` or `&` broke it.
- **Terminate hanging:** terminate could hang if another Python process ended at the same moment.
- **Logins at startup:** when the printer was off at startup, duetLapse3 retried the login continuously.
- **Logfile on restart:** a restart could move the previous print's log onto the new print's name.
- **Startup checks:** the startup dependency check never ran.
- **Camera2 URL check:** Camera2's URL was checked against Camera1's setting.
- **DWC page:** the page inside DWC would not have loaded (`?theme=` was treated as an unknown API call).
- **Password:** the printer password was shown on the Info tab and written to the log at startup.
- **Passwords in the verbose log:** with Verbose Logging on, the printer password was written to the log in its login URLs, and a login in a camera URL could be too. They now appear as `***`.
- **Timed capture status:** timed capture (starting straight away, or `capture_on timed` with `capture_seconds`) showed Waiting instead of Capturing when the printer was idle.
- **Crash on reconnect:** duetLapse3 could stop (UNRECOVERABLE ERROR) when the printer came back quickly after being lost.
- **Busy while disconnected:** while waiting for the printer to reconnect, the control loop woke every 50 ms.

## Code structure

For maintainers: `duetLapse3.py` is split into modules.

| File | Contents |
| --- | --- |
| `duetLapse3.py` | Startup, settings, control loop, capture and video |
| `state.py` | Shared state |
| `logger_module.py` | Logging |
| `duet_printer.py` | All communication with the printer (http, WebSocket, plugin data) |
| `camera.py` | Image capture from http cameras |
| `routes.py` | Web page and API routes |
| `static/app/` | The built web page (from `ui/` at the top of the repository) |

## Testing so far

Almost all of this was tested against a test printer (SBC with WebSocket, SBC without, and standalone) and a test camera:

- capture timing and pause;
- `end_hold`;
- restart into a second print;
- a lost printer and reconnecting;
- starting with the printer off;
- gcode messages;
- Finish capture and Ctrl-C;
- the Config, Cameras and Video tabs;
- the new page in headless Chromium: every tab in light, dark and phone width, and clicking through the controls, Config and Files.
