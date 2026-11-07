#!/bin/bash
# Release this repository: runs the shared release script in DWC-Tools (Prep_and_Package branch), which tags the
# version in plugin.json and pushes the tag to start the Release workflow. Details:
#   https://github.com/stuartofmt/DWC-Tools/blob/Prep_and_Package/.github/workflows/plugin-release.yml.md
#
# Run it from VS Code's terminal (so the GitHub sign-in is available) - on Windows from Git Bash:
#   scripts/release.sh
# The DWC-Tools checkout is expected at ~/DWC/Tools/Prep_and_Package; if it is elsewhere, set DWC_TOOLS to it:
#   DWC_TOOLS=/path/to/Prep_and_Package scripts/release.sh
# (Copied by Prep_and_Package's Copy Plugin Release Workflow - copying again replaces it.)

set -euo pipefail

TOOLS="${DWC_TOOLS:-$HOME/DWC/Tools/Prep_and_Package}"
REAL="$TOOLS/scripts/release.sh"
if [ ! -f "$REAL" ]; then
	echo "Error: the shared release script is not at $REAL"
	echo "Check out the Prep_and_Package branch of https://github.com/stuartofmt/DWC-Tools there,"
	echo "or set DWC_TOOLS to where it is checked out."
	exit 1
fi

# The shared script works on the git repository holding the current folder: make that this one
cd "$(dirname "${BASH_SOURCE[0]}")"
exec bash "$REAL" "$@"
