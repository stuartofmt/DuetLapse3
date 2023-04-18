# Getting Started

This is a brief guide to installing DuetLapse3 as a self-contained, stand alone program.

**All the actions in the getting started guide should be on the computer that will be running DuetLapse3 BEFORE proceeding.**

## 0 -- Create a configuration File

Follow the steps in the getting started guide and create a minimal configuration file.

<https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/Getting%20Started.md>

## 1 -- Install DuetLapse 3

For Linux:

- mkdir DuetLapse  - or other directory of your choice
- cd DuetLapse
- wget <https://github.com/stuartofmt/DuetLapse3/raw/main/DuetLapse3.py>
- chmod 744 DuetLapse3.py

For windows:
Follow the instructions from one of the web sources - for example:
<https://docs.python.org/3/using/windows.html>

***Note:** Make sure to edit the path variable(s) so that python3 and /libraries/modules can be found.*
  
Verify DuetLapse3 is installed correctly by running the following command from the installation folder.

Depending on how you have installed `python`  the command may be `py, python, or python3`

```bash
python ./DuetLapse3.py -h
```

If there are dependencies that need to be installed, this command will identify them.

**Make sure your configuration file is in the same directry as DuetLapse3.py**

Test DuetLapse3.

```bash
python3 ./DuetLapse3.py -file ./DuetLapse3.config
```

The console output will alert you to any issues.

The user interface will be accessible by :

<http://localhost:[port]> (e.g. `http://localhost:8081`) or

 <http://[ip]:[port]> (e.g. `http://192.168.1.10:8081`)

If you are running the browser on the same computer that is running DuetLapse: localhost will likely work.

If the browser is running on a remote computer then `[ip]` is the address of the computer that is running DuetLapse

If the program is run in foreground it can be stopped at any time, using CTRL+C (on linux) or CTRL+Break(on Windows). The best approach, when running on linux, is to use systemctl.

***Note:*** *The http server will stop responding if DuetLapse3 is run from a command console that is then closed.
