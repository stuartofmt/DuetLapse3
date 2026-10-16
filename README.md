## UNDER CONSTRUCTION

# duetLapse3

Time-lapse videos of prints on Duet3D printers. duetLapse3 takes an image from one or two cameras each layer (or at a set interval, or on pause) and turns them into a video when the print finishes.

This branch is version 6 for DWC / DSF 3.7. It runs as a DWC plugin on an SBC (for example, a Raspberry Pi), with its own page under **Plugins → duetLapse3** in DWC.

## Upgrading from DuetLapse3 (version 5 or earlier)

The plugin has been renamed from `DuetLapse3` to `duetLapse3`, so DWC treats it as a different plugin.

1. **Uninstall the old `DuetLapse3` plugin** before you install this one.
2. **Move your settings.** The settings file is now `sys/duetLapse3/duetLapse3.json`, replacing `sys/DuetLapse3/DuetLapse3.config`. Copy your values across (see [Settings](#settings)). Settings that are not in the json use their defaults.
3. **The port is now chosen automatically** if `port` is 0, and the DWC page finds it without any setup. If you give a port and it is already in use, duetLapse3 picks a free one instead of stopping.
4. **gcode commands.** Commands now start with `duetLapse3.`, but the old `DuetLapse3.` still works, so you don't need to change existing slicer gcode.
5. **No firmware version check.** duetLapse3 no longer refuses to run on a firmware version it doesn't expect. The firmware version is shown on the Status tab.

## Installing

1. In DWC, go to **Settings → Plugins → External plugins → Install plugin** and choose the duetLapse3 zip.
2. The plugin installs the `M3291.g` macro in `/sys`. duetLapse3 uses it to receive commands from gcode.
3. Edit `sys/duetLapse3/duetLapse3.json` if you need to change anything (see below), then start the plugin.

DSF installs the Python packages duetLapse3 needs (from `requirements.txt`) when the plugin is installed.

## Settings

Settings are in `sys/duetLapse3/duetLapse3.json`. You can edit it in DWC under **System → sys → duetLapse3**. Restart the plugin after changing it.

The file is split into sections only to make it easier to read: any setting can go in any section. If the file is missing, duetLapse3 creates it with the default values.

```json
{
  "Execution": {
    "detect": "layer",
    "seconds": 0
  },
  "Camera": {
    "camera1": "web",
    "weburl1": "http://192.168.1.20:8081/snapshot"
  },
  "UI": {
    "port": 0,
    "ip": ""
  }
}
```

The main settings are:

| Setting | Default | What it does |
| --- | --- | --- |
| `camera1` | `usb` | Camera type: `usb`, `pi`, `web`, `stream` or `other` |
| `weburl1` | | Image URL for camera1 when it is `web` or `stream` |
| `camera2`, `weburl2` | | Optional second camera |
| `detect` | `layer` | When to take images: `layer`, `pause` or `none` |
| `seconds` | `0` | Also take an image every n seconds (0 = off) |
| `numlayers` | `1` | Take an image every n layers |
| `pause` | `no` | `yes` parks the head before each image |
| `movehead` | `[0, 0]` | Where to park the head (X, Y) when `pause` is `yes` |
| `rest` | `1` | Seconds to wait after parking, before the image |
| `dontwait` | `false` | Start taking images straight away, without waiting for a print |
| `standby` | `false` | Wait for a start command before doing anything |
| `restart` | `false` | Get ready for the next print when this one finishes |
| `fps` | `10` | Video frames per second |
| `minvideo` | `5` | Shortest video to make (seconds) |
| `maxvideo` | `0` | Fixed video length in seconds (0 = off) |
| `extratime` | `0` | Seconds to hold the last image at the end of the video |
| `novideo` | `false` | Don't make a video |
| `deletepics` | `false` | Delete the images when duetLapse3 terminates |
| `keepfiles` | `false` | Don't delete files on startup or shutdown |
| `keeplogs` | `false` | Don't delete old logs |
| `basedir` | | Where images, videos and logs go (default: the program's folder) |
| `password` | `reprap` | Printer password |
| `poll` | `12` | Seconds between printer status checks |
| `verbose` | `false` | Detailed logging |
| `hidebuttons` | `false` | Only show the buttons that can be used now |
| `port` | `0` | Port for the duetLapse3 page. 0 picks a free port from 17800 upwards |
| `ip` | | Set by duetLapse3 to this computer's IP address. You don't need to change it |
| `M3291` | `M3291` | Name of the message macro, if you renamed `M3291.g` |
| `execkey` | | Prefix for messages that run a command on the SBC |
| `camparam1`, `camparam2`, `vidparam1`, `vidparam2` | | Advanced: override the capture or video commands |

## The duetLapse3 page

Open **Plugins → duetLapse3** in DWC. It has five tabs:

- **Status:** what duetLapse3 is doing, and the last image.
- **Controls:** start, standby, pause, continue, restart and terminate.
- **Video:** change the video settings, or make a video now (Snapshot).
- **Files:** download, zip, delete or make videos from earlier images, videos and logs.
- **Info:** the settings in use and where files are kept.

The page shows a message if the plugin stops, and shows the page again when the plugin restarts.

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
| `duetLapse3.graceful` | Make the video and terminate |
| `duetLapse3.forced` | Terminate straight away, without a video |
| `duetLapse3.change.<setting>=<value>` | Change a setting while running, e.g. `duetLapse3.change.seconds=30` |

## Running without DWC

duetLapse3 can also run on its own:

```bash
python duetLapse3.py [settings] [options]
```

- `settings` is optional: the path to a `duetLapse3.json`, or to the folder it is in.
- Any setting can be given on the command line as `-<setting> <value>`, for example `-duet 192.168.1.5 -camera1 web -weburl1 http://...`. Command-line options take priority over the json.
- Two options are only used on the command line:
  - `-duet` is the printer's address (default `localhost`).
  - `-host` is the address the page listens on (default `0.0.0.0`).
- `-file <file>` reads options from a text file, as in earlier versions.
- `-simulate all` runs without a printer or camera, for testing.

The page is at `http://<this computer>:<port>`. The port in use is shown in the log.
