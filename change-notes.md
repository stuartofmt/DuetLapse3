# duetLapse3 6.0.0 – change notes

What changed on 16 and 17 October 2026, described by what it does rather than how the code does it. This is the work for the 3.7.x branch (DWC / DSF 3.7).

## At a glance

- Renamed from **DuetLapse3** to **duetLapse3**. The plugin id has changed, so it installs as a new plugin.
- All settings are in **`duetLapse3.json`**. There are no command-line options any more.
- **Only http cameras**, using a snapshot URL or an MJPEG stream URL. USB and Pi cameras need a camera server.
- **New web page** in **Vue 3 and Vuetify 4** with the DWC 3.7 look, following DWC's light / dark theme. It's served with FastAPI and uvicorn, with new **Cameras**, **Video** and **Config** tabs, and settings saved from the page.
- On an SBC, the printer is followed over **DSF's WebSocket**, so **images are taken at the moment the layer changes**.
- Long-standing bugs fixed: pause didn't stop images, `end_hold` was never added, gcode messages didn't work on standalone printers, Continue never returned, and others (see [Bug fixes](#bug-fixes)).

## Installing and upgrading

- **New plugin id.** It installs to `plugins/duetLapse3`, and DWC shows it under **Plugins → duetLapse3**. Uninstall the old `DuetLapse3` plugin first.
- **Settings file.** Settings are in `sys/duetLapse3/duetLapse3.json`, replacing `sys/DuetLapse3/DuetLapse3.config`. Old settings have to be copied across by hand.
- **Python packages.** DSF installs them from `requirements.txt`: requests, psutil, dsf-python, fastapi, uvicorn and websocket-client.
- **Version.** It's 6.0.0, read from `plugin.json`, so the version only lives in one place.
- **DWC page.** It finds duetLapse3's address from the plugin data that duetLapse3 publishes at startup, instead of reading `-duet`/`-port` from the old `.config`. It shows "The duetLapse3 plugin has stopped" if the program stops, and shows the page again when it restarts. The page itself is a copy of duetPrintGuard's, which uses the current DWC API.
- **Old gcode still works.** Commands now start with `duetLapse3.`, but `DuetLapse3.` and any other capitalisation are still accepted.

## Settings

- **One settings file.** `duetLapse3.json` is the only source of settings. The command-line options (argparse), `-file` and the `logtype` option are gone.
- **Where the file is.** The program takes one optional argument: the folder for `duetLapse3.json` and `duetLapse3.log`. With no argument, that's the program's own folder. If the folder doesn't exist, it's created. If the file is missing, damaged or edited, it's created again with the defaults.
- **Simpler M3291.** The macro is now a short ring of the last 10 commands (`global.DL3seq`, `global.DL3msg`) that duetLapse3 only reads. It no longer sends `set global.DL3del` / `M3291 B"Del"` back after each command or `M3291 B"Clear"` at startup, so it needs no write access to the printer. `M3291 B"duetLapse3.…"` in slicer gcode is unchanged. Needs RepRapFirmware 3.5 or later.
- **ffmpeg on Windows.** The standalone `run.bat` installs `imageio-ffmpeg` (`Code/dsf/requirements-windows.txt`), which includes ffmpeg, so it doesn't have to be installed separately. ffmpeg on the PATH is still used first, and the plugin uses the system ffmpeg as before.
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
- **`instances: one_per_folder`** now means one duetLapse3 per settings folder (that is, per printer). The instance check also now spots copies started with a full path, which is how DSF starts plugins.
- **Removed settings:** `camera1`, `camera2`, `camparam1`, `camparam2`, `vidparam1`, `vidparam2` (never used), `logtype`, `host`, `poll` (images are taken at each status or layer change, and timed images are checked every 5 seconds), `maxffmpeg`, `hidebuttons` (the controls always show every button, greyed out when it can't be used), and the Special Functions section: `execkey` and `M3291`.
- **Special functions removed.** Gcode messages can no longer run commands on the SBC (`execkey`). The message macro is always `M3291`; it can no longer be renamed.
- **New Files section.** `no_log`, `verbose`, `no_video`, `delete_images` and `keep_files` moved from Environment to a new Files section. Sections are only for readability, so older files still work.
- **Settings renamed for clarity:**

  | Was | Now |
  | --- | --- |
  | `duet`, `duetport`, `password` | `duet_ip`, `duet_port`, `duet_password` |
  | `ip`, `port` | `UI_ip`, `UI_port` |
  | `basedir` | `image_dir` |
  | `detect`, `seconds`, `numlayers`, `dontwait` | `capture_on`, `capture_seconds`, `layer_interval`, `start_now` |
  | `pause` (yes / no), `movehead`, `rest` | `park` (true / false), `park_xy`, `park_wait` |
  | `weburl1`, `enable1`, `weburl2`, `enable2` | `camera1_url`, `camera1_on`, `camera2_url`, `camera2_on` |
  | `maxvideo`, `minvideo`, `extratime`, `ffmpegthreads` | `video_length`, `min_video_seconds`, `end_hold`, `ffmpeg_threads` |
  | `nolog`, `novideo`, `deletepics`, `keepfiles` | `no_log`, `no_video`, `delete_images`, `keep_files` |
  | `instances: oneip` | `instances: one_per_folder` |

  The gcode `duetLapse3.change.<setting>=` commands use the new names (e.g. `change.capture_seconds=30`). `keeplogs` is removed: per-print logs left by earlier versions are always cleaned up.
- **`restart` replaced by `norestart`** (the opposite). duetLapse3 now gets ready for the next print by default; set `norestart` to stop it when a print finishes. The Graceful terminate button is now **Finish capture**, and Forced terminate is **Terminate the program**. An old `restart` setting is still read.
- **`capture_on none` renamed `capture_on timed`.** `none` is still accepted and read as `timed`.
- **New settings:** `duet_port`, `ffmpeg_threads`, `camera1_on`, `camera2_on`.

## The web page

- **Rebuilt** as a Vue 3 and Vuetify 4 page with the DWC 3.7 look: DWC's tab bar, cards, fields, Roboto font and icons. It follows DWC's light or dark theme, including when you change it. It's built from `ui/` (see `ui/README.md`) into `Code/dsf/static/app`, and the built files are committed, so the plugin needs no Node.js.
- **Served** with FastAPI and uvicorn at `/` (and `/index`). The API is listed at `/docs`.
- **Data as JSON.** The page reads `/api/status`, `/api/info`, `/api/files`, `/api/settings` and `/api/cameras`. Saving replies with any errors per setting, which are shown in red under the field.
- **Updates as they happen.** Instead of asking for the status every 3 seconds, the page keeps one connection open (`/api/events`, Server-Sent Events) and duetLapse3 sends each change within about a second. Nothing is sent while nothing changes. The Images tab refreshes itself when images are captured, a video is made or files are deleted or zipped, and the settings tabs reload when the settings are saved elsewhere (unless they're being edited). If the connection can't be used, the page falls back to reading the status every 3 seconds.
- **Removed:** the old HTML templates (`dsf/www/`), the `/tab/...` routes and the old `?displayStatus` style calls.
- **Tabs:** Status (with the controls), Video, **Images**, **Cameras**, **Execution**, **Files**, **Config**. The controls moved onto the Status tab, so there's no separate Controls tab.
  - **Images** is the file browser (it was the Files tab).
  - **Execution** and **Files** hold the settings in those sections, moved off the Config tab.
  - **Ready for other languages.** All the page's text is in `ui/src/locales/en.json`, including duetLapse3's own messages (save results, setting errors, the video message and results, the wrong-password banner), which it now sends with a code and values. The language is `?lang=<code>`, otherwise the browser's language, otherwise English; a partial translation falls back to English for the rest. Only English exists so far.
  - **Info tab removed.** The page address is in the log, and the settings in use are written to the log at the start of each print.
  - **Config** has a new **Pause** section (`park`, `park_xy`, `park_wait`), and a blank `image_dir` shows the folder in use.
  - **Cameras:** each camera's URL with a preview, and an on/off switch (`camera1_on`, `camera2_on`) that keeps the URL. Saving checks the URLs, writes them to the json and starts using them straight away.
  - **Video:** the images captured by each camera, with how many are needed for a video. Then Snapshot (a button for each camera when there are two), plus the Video settings. Saving writes them to the json and starts using them straight away.
  - **Images:** a file browser with a breadcrumb path, list or grid view with thumbnails, search and sorting. Images and videos open in a viewer, and each item has an action menu.
  - **Config:** every other setting, with checking before saving. Changes take effect after a restart.
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

- **One log.** There's one `duetLapse3.log`, next to `duetLapse3.json`, started fresh each time duetLapse3 starts. It's no longer moved into each print's folder.
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
- **Timed capture status:** timed capture (`start_now`, or `capture_on timed` with `capture_seconds`) showed Waiting instead of Capturing when the printer was idle.
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

Everything above was tested against a fake printer (SBC with WebSocket, SBC without, and standalone) and a fake camera:

- capture timing and pause;
- `end_hold`;
- restart into a second print;
- a lost printer and reconnecting;
- starting with the printer off;
- gcode messages;
- Finish capture and Ctrl-C;
- the Config, Cameras and Video tabs;
- the new page in headless Chromium: every tab in light, dark and phone width, and clicking through the controls, Config and Files.

**None of it has been tried on a real printer or inside DWC yet.**

## Before releasing

- **Remove test output** from `Code/dsf/`: the `srsender/` image folder and `__pycache__/`. Add both to `.gitignore`.
- **Check on a real SBC:**
  - `WebSocket connected` appears in the log;
  - images arrive at each layer change;
  - the DWC page loads and finds the address;
  - pause, continue, restart and terminate all work.
- **Check on a standalone board:** that its `rr_model?flags=d99fn` response includes the `seqs` counters. Without them it still works, but with more requests.
- **Check the plugin uninstall:** whether uninstalling removes `sys/duetLapse3/`, which now also holds the images and videos.
