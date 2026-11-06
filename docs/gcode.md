# Controlling duetLapse3 from gcode

You can control duetLapse3 from gcode, for example from your slicer's start or end gcode, or from a macro. Use the `M3291` macro, which the plugin installs in `/sys`:

```text
M3291 B"/command/start"
```

One command per `M3291` call. `M3291` needs RepRapFirmware 3.5 or later.

## Commands

| Command | What it does |
| --- | --- |
| `/command/start` | Start taking images |
| `/command/standby` | Stop and delete the images, without making a video |
| `/command/pause` | Stop taking images for now |
| `/command/continue` | Carry on after a pause |
| `/command/restart` | Make the video, start a new log, read the saved settings again, then get ready for the next print |
| `/snapshot` | Make a video of the images so far |
| `/terminate/terminateg` | Finish capture: make the video, then get ready for the next print (or stop, if `norestart` is set) |
| `/terminate/terminatef` | Terminate straight away, without a video |
| `/change?<setting>=<value>` | Change a setting while running (see below) |

Each command is a request to the [web API](web-api.md), so it does the same as calling that URL. `/snapshot?camera=1` or `?camera=2` makes a video for one camera. Only the commands above can be sent from gcode: the other URLs, such as `/delete`, can't.

The spellings from earlier versions, such as `duetLapse3.start`, no longer work. They are logged as not recognised, so slicer gcode that uses them needs changing.

## Changing a setting

`/change?<setting>=<value>` changes a setting in memory and takes effect immediately. It doesn't change the saved settings, so it lasts until the `/command/restart` command or the Restart button reads them again, or duetLapse3 is started again. To keep a change, make it on the duetLapse3 page.

```text
M3291 B"/change?capture_seconds=30"
M3291 B"/change?park=True&park_xy=10,200"
```

You can change several settings at once, joined with `&`. They are checked together, and either all of them are used or none.

A change with a bad value, or that conflicts with the settings in use, isn't applied: an alert shows at the top of the duetLapse3 page, and in the log. Separate commands are checked one at a time as they arrive, so settings that depend on each other, such as `park` and `park_xy`, are best changed in one command.

For example, this turns parking off and clears the park location. Sent as two separate commands, the first would be refused, because a Park Location can't be set with Park before image off:

```text
M3291 B"/change?park=False&park_xy=0,0"
```



These settings can be changed:

| Setting | Values |
| --- | --- |
| `capture_on` | `layer`, `pause` or `timed` |
| `capture_seconds` | seconds (0 = off) |
| `layer_interval` | number of layers |
| `start_mode` | `on_print`, `now` or `standby`. `now` and `on_print` act at once. `standby` applies from the end of the current print |
| `park`, `norestart`, `no_video`, `keep_files`, `verbose` | `True` or `False` |
| `park_xy` | two numbers: `X,Y` |
| `park_wait`, `end_hold`, `min_video_seconds`, `video_length` | seconds |
| `fps` | frames per second |

See the [README](../README.md) for what each setting does.

## How it works

`M3291.g` keeps the last 10 commands on the printer: `global.DL3seq` counts them, and `global.DL3msg` holds them. duetLapse3 remembers the last command it acted on and sends any newer ones, in order, to its own web API.

- duetLapse3 only reads these globals, so it works the same with an SBC or a standalone board, and on the same computer as the printer or another one.
- Commands sent while duetLapse3 isn't running are not carried out when it starts.
- If more than 10 commands arrive before duetLapse3 next reads them, it carries out the last 10 and logs how many it missed. In practice this doesn't happen: on an SBC each command is seen as it arrives, and a standalone board is checked every 5 seconds.
