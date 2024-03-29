# DuetLapse3 Plugin for Duet3D SBC

This is a brief guide to installing DuetLapse3 plugin for SBC.

The plugin may rely on specific versions os DSF.  Select and install from the appropriate folder.

**All the actions in the getting started guide should be performed on the SBC BEFORE proceeding.**

## 0 -- Create a configuration File

Follow the steps in the getting started guide and create a minimal configuration file.

<https://github.com/stuartofmt/DuetLapse3/blob/main/Documents/Getting%20Started.md>

Be especially careful to use:

```text
-basedir /opt/dsf/sd/DuetLapse3
```

## 1 -- Download the plugin

Download the x.y.z.DuetLapse3.zip file from the folder applicable to your version of DSF.

## 2 -- Setup the configuraton file

Using DWC, go to the system directory.

Using New Directory, create a directoty named `DuetLapse3` (the name and capitalization is important)

Open the newly created `DuetLapse3` directory.

Using New File, create a file named `DuetLapse3.config` (the name and capitalization is important)

Copy the contents of your configuration into the file and Save

## 3 -- (optional but recommended) monitor the installation process

Open a terminal on the SBC and enter this command.

`sudo journalctl -f`

Keep the terminal open during installation to check for any errors.

## 4 -- Install DuetLapse3 plugin

Using DWC, go to plugins --> EXTERNAL PLUGINS

Click Install Plugin, select the DuetLapse3.zip file and follow the installation steps.

## 4 -- Start the plugin

Using DWC, go to plugins --> EXTERNAL PLUGINS

Click on Start for the DuetLapse3 entry

The plugin should now have a status of started

Click on Plugins --> DuetLapse3

You should now see the DuetLapse3 interface.
