#!/bin/bash
# Start the program with its venv (made by Prepare in Prep_and_Package). With no venv - e.g. just
# unzipped from a release - it is made first, able to see the system's packages, and Code/dsf/requirements.txt
# (with Code/dsf/requirements-linux.txt, if there is one) is installed into it.
cd "$(dirname "$0")" || exit 1
reqs=(-r "Code/dsf/requirements.txt")
[ -f "Code/dsf/requirements-linux.txt" ] && reqs+=(-r "Code/dsf/requirements-linux.txt")
if [ ! -x venv/bin/python ]; then
	echo "First run: making the venv and installing Code/dsf/requirements.txt into it"
	python3 -m venv --system-site-packages venv || {
		echo "Could not make the venv. On Debian or Raspberry Pi OS the venv module needs: sudo apt install python3-venv"
		rm -rf venv   # a half-made venv would be taken as ready next time
		exit 1
	}
	venv/bin/python -m pip install "${reqs[@]}" || {
		echo "Could not install the requirements into the venv - see the pip messages above"
		rm -rf venv
		exit 1
	}
fi
exec venv/bin/python -u Code/dsf/duetLapse3.py "$@"
