# DuetLapse3 Usage Examples

Many options can be combined.  For example, the program can trigger on both "seconds" and "detect layer". It will inform you if you select conflicting options.

Example: Using a config file.  Start the http server using port 8082. Capture an image every 30 seconds, do not respond to layer changes or pauses, use a streaming webcam at the specified url:

```python
python3 ./DuetLapse3.py  -file ./DuetLapse3.config

Example Content of DetLapse3.config
-duet 192.168.7.101
-port 8082
-seconds 30
-detect none
-camera1 stream -weburl1 http://192.168.7.140/stream
```

Example: Using DuetLapse3.config with changes.  Start the http server using port 8082. Capture an image every 60 seconds, respond to layer changes, use a streaming webcam at the specified url:

```text
python3 ./DuetLapse3.py  -file ./DuetLapse3.config -seconds 60 -detect layer

Example Content of DetLapse3.config
-duet 192.168.7.101
-port 8082
-seconds 30
-detect none
-camera1 stream
-weburl1 http://192.168.7.140/stream
```

Example: Start the http server using port 8082. Capture an image every 60 seconds, do not respond to layer changes or pauses, use a streaming webcam at the specified url:

```text
python3 ./DuetLapse3.py  -duet 192.168.7.101 -port 8082 -seconds 60 -detect none -camera1 stream -weburl1 http://192.168.7.140/stream
```

Example: Start the http server using port 8082, capture an image on layer changes (default), force pauses (at layer change) and move head to X10 Y10 before creating an image, use the default USB camera.

```text
python3 ./DuetLapse3.py -duet 192.168.7.101 -port 8082 -pause yes -movehead 10 10
```

Example: Two camera example. Start capturing immediately at a minumum of one image every 30 second. Camera2 uses camparam and vidparam2 overrides. Run in background.

```text
/usr/bin/python3 ./DuetLapse3.py -duet 192.168.86.235 -basedir /home/pi/Lapse -instances oneip -dontwait -seconds 30 -camera1 stream -weburl1 http://192.168.86.230:8081/stream.mjpg  -camera2 other -weburl2 http://192.168.86.230:8081/stream.mjpg -camparam2="'ffmpeg -y -i '+weburl+ ' -vframes 1 ' +fn+debug" -vidparam2="'ffmpeg -r 1 -i '+basedir+'/'+duetname+'/tmp/'+cameraname+'-%08d.jpeg -c:v libx264 -vf tpad=stop_mode=clone:stop_duration='+extratime+',fps=10 '+fn+debug" -extratime 0 &
```

Example: Start the http server using port 8082. Capture an image every 40 seconds, do not respond to layer changes or pauses, use a  webcam (that delivers still images) at the specified url:

```text
python3 ./DuetLapse3.py  -duet 192.168.7.101 -port 8082 -seconds 40 -detect none -camera1 web -weburl1 http://userid:password@192.168.7.140/cgi-bin/currentpic.cgi
```
