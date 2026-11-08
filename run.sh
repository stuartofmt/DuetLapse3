#!/bin/bash
# Start the program with its venv (made by Prepare in Prep_and_Package). With no venv - e.g. just
# unzipped from a release - it is made first, able to see the system's packages, and Code/dsf/requirements.txt
# (with Code/dsf/requirements-linux.txt, if there is one) is installed into it.
# The program runs in the background, apart from this terminal (closing it does not stop the program):
# stop it with its Terminate button.  ./run.sh console runs it in this terminal, showing its messages.
cd "$(dirname "$0")" || exit 1
console=
if [ "$1" = console ]; then console=1; shift; fi
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
if [ -n "$console" ]; then
	exec venv/bin/python -u Code/dsf/duetLapse3.py "$@"
fi
# A session of its own: no terminal, so closing this one does not stop it
setsid venv/bin/python -u Code/dsf/duetLapse3.py "$@" </dev/null >/dev/null 2>&1 &
pid=$!
echo "Starting Code/dsf/duetLapse3.py in the background - checking that it keeps running"
sleep 5
if ! kill -0 "$pid" 2>/dev/null; then
	wait "$pid"
	code=$?
	if [ "$code" -ne 0 ]; then
		echo "Code/dsf/duetLapse3.py stopped at once with an error (exit code $code) - ./run.sh console shows why"
		exit "$code"
	fi
	exit 0
fi
echo "Code/dsf/duetLapse3.py is running in the background (process $pid). Stop it with its Terminate button."
