# duetLapse3 6.0.0 – change notes

What changed on 16 and 17 October 2026, described by what it does rather than how the code does it. This is the work for the 3.7.x branch (DWC / DSF 3.7).

## At a glance

- Renamed from **DuetLapse3** to **duetLapse3**. The plugin id has changed, so it installs as a new plugin.
- All settings are in **`duetLapse3.json`**. There are no command-line options any more.
- **Only http cameras**, using a snapshot URL or an MJPEG stream URL. USB and Pi cameras need a camera server.
- **New web page**, served with FastAPI and uvicorn: new **Cameras**, **Video** and **Config** tabs, with settings saved from the page.
- On an SBC, the printer is followed over **DSF's WebSocket**, so **images are taken at the moment the layer changes**.
- Long-standing bugs fixed: pause didn't stop images, `extratime` was never added, gcode messages didn't work on standalone printers, Continue never returned, and others (see [Bug fixes](#bug-fixes)).

## Installing and upgrading

- **New plugin id.** It installs to `plugins/duetLapse3`, and DWC shows it under **Plugins → duetLapse3**. Uninstall the old `DuetLapse3` plugin first.
- **Settings file.** Settings are in `sys/duetLapse3/duetLapse3.json`, replacing `sys/DuetLapse3/DuetLapse3.config`. Old settings have to be copied across by hand.
- **Python packages.** DSF installs them from `requirements.txt`: requests, psutil, dsf-python, fastapi, uvicorn and websocket-client.
- **Version.** It's 6.0.0, read from `plugin.json`, so the version only lives in one place.
- **DWC page.** It finds duetLapse3's address from the plugin data that duetLapse3 publishes at startup, instead of reading `-duet`/`-port` from the old `.config`. It shows "The duetLapse3 plugin has stopped" if the program stops, and shows the page again when it restarts. The page itself is a copy of duetPrintGuard's, which uses the current DWC API.
- **Old gcode still works.** Commands now start with `duetLapse3.`, but `DuetLapse3.` and any other capitalisation are still accepted.

## Settings

- **One settings file.** `duetLapse3.json` is the only source of settings. The command-line options (argparse), `-file` and the `logtype` option are gone.
- **Where the file is.** The program takes one optional argument: the folder for `duetLapse3.json` and `duetLapse3.log`. With no argument, that's the program's own folder. If the folder doesn't exist, it's created. If the json is missing, it's created with the defaults.
- **Checked at startup.** Every value is checked when duetLapse3 starts: its type (number, true/false, text, list) and, for some settings, the allowed values. A bad value stops startup with a message naming the setting. Unknown settings are ignored with a warning.
- **Where images and videos go.** `basedir` blank now means the settings folder, so for the plugin that's `sys/duetLapse3/`, not inside the plugin's install folder. The files are still under `<computer name>/<printer address>/` folders.
- **The printer's address.**
  - `duet` is the printer address (SBC or standalone). Blank means this computer.
  - `duetport` is the printer's port. Blank or 0 means 80.
  - duetLapse3 can run on a different computer from the printer.
- **The page address.**
  - `port` 0, the default, picks a free port from 17800 upwards. A port that's already in use also falls back to a free one.
  - The page always listens on every address of the computer. The `host` setting is gone.
  - The computer's IP is shown in the log and on the Info tab, saved to the json (`ip`), and published for the DWC page.
- **`instances: oneip`** now means one duetLapse3 per settings folder (that is, per printer). The instance check also now spots copies started with a full path, which is how DSF starts plugins.
- **Removed settings:** `camera1`, `camera2`, `camparam1`, `camparam2`, `logtype`, `host`.
- **New settings:** `duetport`, `ffmpegthreads`.

## The web page

- **Rebuilt** on FastAPI and uvicorn. It's at `/` (and `/index`), and the API is listed at `/docs`.
- **Tabs:** Status, Controls, Video, Files, Info, **Cameras**, **Config**.
  - **Cameras:** each camera's URL with a preview. Saving checks the URLs, writes them to the json and starts using them straight away.
  - **Video:** Snapshot, plus the Video and Overrides settings. Saving writes them to the json and starts using them straight away.
  - **Config:** every other setting, with checking before saving. Changes take effect after a restart.
  - **Info:** shows the page address.
- **New URLs** for the tabs (`/tab/...`) and actions (`/command/...`, `/snapshot`, `/makevideo`, `/getfile`, `/zip`, `/delete`, `/terminate/...`, `/videosettings`).
- **Old URLs still work,** such as `/?command=start` and `/?displayStatus=true`. Other query parameters, such as the DWC page's `?theme=`, are ignored.
- **The HTML** is in template files under `dsf/www/`, so it can be edited without touching the Python. Templates are read on every request.
- **Relative addresses.** The page uses relative URLs, so it works whatever address it's opened on (IP, hostname, VPN, localhost).

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
- **Exit codes.** A graceful terminate exits cleanly with code 0, and a forced terminate or Ctrl-C with code 1, instead of killing itself.

## Printer communication

- **SBC.** The printer's state is followed over DSF's WebSocket, the same way DWC does it, instead of polling `/machine/status`. That's about 80% fewer requests. If the WebSocket isn't available, duetLapse3 falls back to http polling and reconnects by itself.
- **Standalone.** One `rr_model` read per check returns the status, layer and position. The job and message queue are only re-read when the printer says they've changed (RRF's `seqs` counters).
- **One shared read.** Status, layer, job name and head position come from the same read instead of a request each.
- **Firmware version check removed.** The printer's firmware version is shown on the Status tab instead.

## Videos

- **Still made with ffmpeg**, now:
  - at low priority (`nice`), so the printer software always comes first;
  - with a CPU thread limit worked out from the free cores (`ffmpegthreads`, 0 = automatic);
  - with the `veryfast` preset, which uses much less CPU;
  - with `-pix_fmt yuv420p`, so videos play in browsers and on phones whatever the camera's JPEG format.
- **Safe with spaces.** ffmpeg runs without a shell, so a path with spaces works.
- **One at a time.** Videos are made one at a time, in order, by a video worker.
- **`extratime`** is now added at the end of a print, so those videos are longer than before.

## Logging

- **One log.** There's one `duetLapse3.log`, next to `duetLapse3.json`, started fresh each time duetLapse3 starts. It's no longer moved into each print's folder.
- **Messages.** Log messages use setting names (`detect pause`) instead of command-line options (`-detect pause`). The log shows the page address and the printer's full address.

## Bug fixes

Bugs that existed before this work:

- **Pause:** pause from the page or gcode didn't stop images being taken.
- **`extratime`:** it was never added to the video at the end of a print.
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
| `printer_status.py` | Reference for printer statuses and what they mean to duetLapse3 (not used by the program yet) |
| `www/` | HTML templates |

## Testing so far

Everything above was tested against a fake printer (SBC with WebSocket, SBC without, and standalone) and a fake camera:

- capture timing and pause;
- `extratime`;
- restart into a second print;
- a lost printer and reconnecting;
- starting with the printer off;
- gcode messages;
- graceful terminate and Ctrl-C;
- the Config, Cameras and Video tabs.

**None of it has been tried on a real printer or inside DWC yet.**

## Before releasing

- **Reset the shipped settings.** `Code/sd/sys/duetLapse3/duetLapse3.json` still contains test values: `verbose`, `dontwait`, `seconds` 3, `detect` none, a camera URL and an `ip`. Put it back to the defaults.
- **Remove test output** from `Code/dsf/`: the `srsender/` image folder and `__pycache__/`. Add both to `.gitignore`.
- **Check on a real SBC:**
  - `WebSocket connected` appears in the log;
  - images arrive at each layer change;
  - the DWC page loads and finds the address;
  - pause, continue, restart and terminate all work.
- **Check on a standalone board:** that its `rr_model?flags=d99fn` response includes the `seqs` counters. Without them it still works, but with more requests.
- **Check the plugin uninstall:** whether uninstalling removes `sys/duetLapse3/`, which now also holds the images and videos.
