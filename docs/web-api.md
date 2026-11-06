# duetLapse3 web API

The duetLapse3 page uses these URLs, and you can call them yourself, for example from a script. They are on the page's address, `http://<this computer>:<port>`, which is shown in the log (`duetLapse3 page: http://…`). A list of the routes is also at `http://<this computer>:<port>/docs`.

## Actions

All of these use GET.

| URL | What it does |
| --- | --- |
| `/command/<command>` | `start`, `standby`, `pause`, `continue` or `restart`. Ignored and logged if it isn't allowed in the current state |
| `/change?<setting>=<value>` | Change settings in memory, used straight away and not saved. Give one or more, e.g. `/change?park=True&park_xy=10,200`: all of them are used or none, with a 400 reply listing the errors and an alert on the page. The settings are listed in [gcode](gcode.md#changing-a-setting) |
| `/snapshot` | Make a video of the images so far (`?camera=1` or `?camera=2` for one camera) |
| `/makevideo?path=<folder>&xtratime=false` | Make a video from an image folder |
| `/videosettings?fps=<n>&minvideo=<n>&maxvideo=<n>` | Change the video settings (give any of them): `minvideo` sets `min_video_seconds`, `maxvideo` sets `video_length`. The parameter names are kept from earlier versions |
| `/getfile?path=<file>` | Download a file |
| `/zip?path=<folder>` | Zip an image folder |
| `/delete?path=<file or folder>` | Delete a file or folder |
| `/terminate/terminateg` | Finish capture: make the video, then get ready for the next print (or stop, if `norestart` is set) |
| `/terminate/terminatef` | Terminate the program straight away, without a video |
| `/camera/preview?url=<camera url>` | One image from a camera URL |

## Data

The page reads its data as JSON:

| URL | What it returns |
| --- | --- |
| `/api/status` | What duetLapse3 and the printer are doing, images captured, layer, last image, and `settingsAlert`: why settings were not applied, if they weren't |
| `/api/events` | The same status as Server-Sent Events, sent whenever it changes, plus `files` and `settings` events when files are deleted or zipped and when the settings are saved, and `log` events when the log file grows or a new one starts |
| `/api/files?path=<folder>` | The files in a folder (blank = the top folder) |
| `/api/log?offset=<n>&number=<n>` | The log file from byte `offset`, in whole lines, with the `offset` and log `number` to ask for next. With no offset, or if a new log has started since `number`: the last 256 KB. `previous` is the path of the previous log |
| `/api/settings?tab=<tab>` | The settings shown on a tab (`config`, `execution`, `files` or `video`), with their values |
| `/api/cameras` | Each camera's URL and whether it is on |

## Saving settings

These take a POST with the settings as JSON, e.g. `{"capture_seconds": 30}`. Every value is checked first, and nothing is saved if any are wrong or if settings conflict: the reply then lists the errors, one per setting (a conflict is listed under `""`).

| URL | Settings |
| --- | --- |
| `/config/save` | Any of the settings on the Config, Execution and Files tabs. They take effect on `/command/restart`, which reads the settings again |
| `/video/save` | The video settings, used straight away |
| `/cameras/save` | `camera1_url` and `camera2_url`, used straight away |
| `/cameras/enable` | `{"key": "camera1_on", "enabled": false}` - switch a camera on or off |
| `/settings/alert/clear` | No settings: closes the alert given by `settingsAlert` in `/api/status` |
| `/printer/connect` | `duet_ip`, `duet_port` and `duet_password`, while the printer is not connected - saved, then duetLapse3 tries to connect at once |

## Earlier versions

Action URLs from earlier versions, such as `http://<this computer>:<port>/?command=start`, still work. The old `?displayStatus` style calls, which returned parts of the old page, have been removed; use `/api/status` and the other JSON URLs instead.

The page itself is built from `ui/` (see [ui/README.md](../ui/README.md)).
