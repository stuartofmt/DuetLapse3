# systemctl setup
 
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

Determine where your systemctl files are. Usually this will be somewhere like /lib/systemd/system.<br>
This directory will be used in the following commands.

If your distribution does not use this directory and you are unsure what it is - you can narrow down the options with:

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

If there is an error - you can edit it in the /lib/systemd/system directory then repeat steps 3, 4 and 5 above.


Finally - enable the unit file, reboot and test to see if its running

```
sudo systemctl enable startDuetLapse3.service
```
