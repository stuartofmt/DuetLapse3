# Controlling duetLapse3 from gcode

You can control duetLapse3 from gcode, for example from your slicer's start or end gcode, or from a macro. Use the `M3291` macro, which the plugin installs in `/sys`:

```text
M3291 B"duetLapse3.start"
```

One command per `M3291` call. `M3291` needs RepRapFirmware 3.5 or later.

## Commands

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
| `duetLapse3.change.<setting>=<value>` | Change a setting while running (see below) |

The older spelling `DuetLapse3.` also works, so existing slicer gcode doesn't need to change.

## Changing a setting

`duetLapse3.change.<setting>=<value>` changes a setting until duetLapse3 restarts. It isn't saved: to keep a change, make it on the duetLapse3 page.

```text
M3291 B"duetLapse3.change.capture_seconds=30"
M3291 B"duetLapse3.change.park=True"
M3291 B"duetLapse3.change.park_xy=10,200"
```

These settings can be changed:

| Setting | Values |
| --- | --- |
| `capture_on` | `layer`, `pause` or `timed` |
| `capture_seconds` | seconds (0 = off) |
| `layer_interval` | number of layers |
| `park`, `start_now`, `standby`, `norestart`, `no_video`, `keep_files`, `verbose` | `True` or `False` |
| `park_xy` | two numbers: `X,Y` |
| `park_wait`, `end_hold`, `min_video_seconds`, `video_length` | seconds |
| `fps` | frames per second |

See the [README](../README.md) for what each setting does.

## How it works

`M3291.g` keeps the last 10 commands on the printer: `global.DL3seq` counts them, and `global.DL3msg` holds them. duetLapse3 remembers the last command it acted on and carries out any newer ones, in order.

- duetLapse3 only reads these globals, so it works the same with an SBC or a standalone board, and on the same computer as the printer or another one.
- Commands sent while duetLapse3 isn't running are not carried out when it starts.
- If more than 10 commands arrive before duetLapse3 next reads them, it carries out the last 10 and logs how many it missed. In practice this doesn't happen: on an SBC each command is seen as it arrives, and a standalone board is checked every 5 seconds.
