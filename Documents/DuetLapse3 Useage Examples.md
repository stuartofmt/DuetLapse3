## DuetLapse3 Usage Examples

Many options can be combined.  For example, the program can trigger on both "seconds" and "detect layer". It will inform you if you select conflicting options.
***Note:** that these examples are from the command line.  If running from a program (or to avoid issues closing the console) adding a **&** at the end (in linux) will run the program in background.  Also consider (in Linux) running program using systemctl*

Example: Capture an image every 20 seconds, do not respond to layer changes or pauses, use a webcam at the specified url:
```
python3 ./DuetLapse3.py  -duet 192.168.7.101 -seconds 20 -detect none -camera1 web -weburl1 http://userid:password@192.168.7.140/cgi-bin/currentpic.cgi

```
Example: Start the http listener on 192.198.86.10  using port 8082, capture an image on layer changes (default), force pauses (at layer change) and move head to X10 Y10 before creating an image, use the default USB camera.
```
python3 ./DuetLapse3.py -duet 192.168.7.101 -host 192.168.86.10 -port 8082 -pause yes -movehead 10 10

```
Example: Two camera example. Start capturing immediately at a minumum of one image every 3 second. Camera2 uses camparam and vidparam2 overrides. Run in background.
```
/usr/bin/python3 ./DuetLapse3.py -duet 192.168.86.235 -basedir /home/pi/Lapse -instances oneip -dontwait -seconds 3 -camera1 stream -weburl1 http://192.168.86.230:8081/stream.mjpg  -camera2 other -weburl2 http://192.168.86.230:8081/stream.mjpg -camparam2="'ffmpeg -y -i '+weburl+ ' -vframes 1 ' +fn+debug" -vidparam2="'ffmpeg -r 1 -i '+basedir+'/'+duetname+'/tmp/'+cameraname+'-%08d.jpeg -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn+debug" -extratime 0 &
```