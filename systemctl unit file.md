# systemctl unit file example
 
This document briefly describes setting up a unit file so that startDuetLapse will begin running after bootup.
Its accurate for Debian Buster but there may be differences for other distributions - so this douumant is only guidance.

Download the example file<br>
wget https://github.com/stuartofmt/DuetLapse3/raw/main/startDuetLapse3.service

Edit the example file paying particular attention to the following comments:
```
[Unit]
Description=startDuetLapse Service
After=multi-user.target
[Service]
WorkingDirectory=/home/pi/Lapse  #This needs to be the directory for BOTH startDuetLapse3.py and DuetLapse3.py
User=pi                          #Needs to be the usual login user
Type=idle
ExecStart=python3 /home/pi/Lapse/startDuetLapse3.py -port 8082  #The port number you want to use
Restart=always
[Install]
WantedBy=multi-user.target
```

Determine where your systemctl files are (usually this will be somewhere like /lib/systemd/system so we will use this in the following examples)
The following command can help narrow down the options
```
sudo find / -name system | grep systemd
```

- [1]  copy the service file to the systemd directory 

```
sudo cp ./startDuetLapse3.service /lib/systemd/system/startDuetLapse3.service
```
- [2] change the ownership to root

```
sudo chown root:root /lib/systemd/system/startDuetLapse3.service
```

- [3]  relaod systemd daemon so that it recognizes the new file

```
sudo systemctl daemon-reload
```
- [4]  start startDuetLapse3.service

```
sudo systemctl start startDuetLapse3.service
```
- [5]  check for errors

```
sudo systemctl status startDuetLapse3.service
```

Try this a couple of time just in case there was an error in the unit file that needs fixing.
If there is then you can edit it in the /lib/systemd/system directory then repeat steps 3, 4 and 5 above.


Finally - enable the unit file, reboot and test to see if its running

```
sudo systemctl enable startDuetLapse3.service
```


