#!/bin/bash
# Release the plugin version that is in plugin.json (the first one found in the repository).
#
# This script does NOT change plugin.json. It:
#   1. reads "version" and "dwcVersion" from plugin.json and works out the tag name:
#      v<version>-dwc<dwcVersion>, e.g. v1.2.3-dwc3.7, or v<version> if plugin.json has no dwcVersion
#      (a plugin with no DWC interface, which the Release workflow zips instead of building)
#   2. reports whether that tag has already been used (on this computer or on GitHub)
#   3. asks whether to release with this tag or create a new one:
#        - use this tag: pushes the branch, creates the tag and pushes it on its own
#        - new tag:      tells you to update and commit plugin.json first, then exits
#
# With no plugin.json the repository is not a plugin: the Release workflow releases only its standalone ZIP,
# which needs a standalone/ folder (made by Prep_and_Package's Prepare with "Create standalone" ticked), and
# the version comes from the tag. This script then shows the latest v* tag, asks for the version to release and
# uses the tag v<version>.
#
# Pushing the tag starts the Release workflow (.github/workflows/release.yml). Approve the run in the
# repository's Actions tab when it pauses at dwc-release-approval.
#
# Run from VS Code's terminal (so the GitHub sign-in is available):  ./scripts/release.sh
# On Windows run it from Git Bash (it comes with Git for Windows, and can be VS Code's terminal).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Use the first plugin.json found: the repository root first, then the shallowest subfolder (skipping
# .git, node_modules and venv). The Release workflow stops if there is more than one, so warn about that.
MANIFESTS=$(find . \( -name .git -o -name node_modules -o -name venv \) -prune -o -type f -name plugin.json -print \
	| awk -F/ '{ print NF "\t" $0 }' | sort -n -k1,1 -k2 | cut -f2- | sed 's|^\./||')
MANIFEST=$(echo "$MANIFESTS" | head -n1)
if [ -n "$MANIFESTS" ] && [ "$(echo "$MANIFESTS" | wc -l)" -gt 1 ]; then
	echo "Warning: more than one plugin.json found - using $MANIFEST. Others:"
	echo "$MANIFESTS" | tail -n +2 | sed 's/^/  /'
	echo "(The Release workflow stops if there is more than one plugin.json in subfolders.)"
	echo
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ -z "$MANIFEST" ]; then
	# No plugin.json: only a standalone ZIP is released (from standalone/), its version only in the tag
	[ -d standalone ] || { echo "Error: there is no plugin.json and no standalone/ folder, so there is nothing to release."
		echo "Run Prepare in Prep_and_Package with \"Create standalone\" ticked, commit standalone/ and try again."; exit 1; }
	echo "No plugin.json in this repository: only its standalone ZIP (standalone/ folder) will be released."
	LATEST=$(git tag -l 'v*' --sort=-v:refname | head -n1)
	echo "Latest tag: ${LATEST:-none}"
	read -rp "Version to release (e.g. 1.2.3): " VERSION
	VERSION=${VERSION#v}
	[[ "$VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?(-[0-9A-Za-z.-]+)?$ ]] \
		|| { echo "Error: \"$VERSION\" is not a version number such as 1.2.3."; exit 1; }
	DWC_VERSION=""
	TAG="v$VERSION"
else
	# Python reads plugin.json: python3 on Linux, but on Windows (Git Bash) usually python or py - and python3 there may
	# be only the Microsoft Store placeholder - so each is tried until one really runs.
	PYTHON=""
	for p in python3 python py; do
		if command -v "$p" >/dev/null 2>&1 && "$p" -c "import json" >/dev/null 2>&1; then PYTHON=$p; break; fi
	done
	[ -n "$PYTHON" ] || { echo "Error: Python is needed to read $MANIFEST, but none of python3, python or py works."; exit 1; }
	# tr: Python on Windows ends its output with \r\n, and the \r would end up in the tag name
	VERSION=$("$PYTHON" -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$MANIFEST" | tr -d '\r')
	DWC_VERSION=$("$PYTHON" -c "import json,sys; v=json.load(open(sys.argv[1])).get('dwcVersion'); print('' if v is None else str(v).strip())" "$MANIFEST" | tr -d '\r')
	if [ -z "$DWC_VERSION" ]; then
		TAG="v$VERSION"   # No DWC interface: the plugin is zipped, not built, and is not tied to a DWC version
	else
		# The tag includes dwcVersion, so it must be a plain version (not e.g. "auto"); same rule as the Release workflow.
		[[ "$DWC_VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?(-[0-9A-Za-z.-]+)?$ ]] \
			|| { echo "Error: $MANIFEST needs a numeric dwcVersion for the tag name, not \"$DWC_VERSION\"."; exit 1; }
		TAG="v$VERSION-dwc$DWC_VERSION"
	fi
fi

# Release channel (scripts/release-channel.txt, default "latest"; same rules as scripts/manifest.mjs).
# It only decides whether the GitHub Release is marked Latest; the tag is the same either way.
CHANNEL=""
[ -f scripts/release-channel.txt ] && CHANNEL=$(sed -e 's/#.*//' -e 's/[[:space:]]//g' scripts/release-channel.txt | grep -m1 . || true)
CHANNEL=${CHANNEL:-latest}
case "$CHANNEL" in
	latest|maintenance) ;;
	*) echo "Error: scripts/release-channel.txt must say \"latest\" or \"maintenance\", not \"$CHANNEL\"."; exit 1 ;;
esac

echo "Branch:       $BRANCH"
if [ -n "$MANIFEST" ]; then
	echo "Version:      $VERSION  (from $MANIFEST)"
	echo "DWC version:  ${DWC_VERSION:-none (no DWC interface - the plugin is zipped, not built)}"
	# A standalone/ folder: the Release workflow also builds a standalone ZIP (scripts/release-standalone.mjs)
	[ -d standalone ] && echo "Standalone:   also released as standalone-<id>-$VERSION.zip (standalone/ folder)"
else
	echo "Version:      $VERSION  (standalone - no plugin.json)"
fi
echo "Channel:      $CHANNEL$([ "$CHANNEL" = latest ] && echo "  (Release marked Latest)" || echo "  (Release not marked Latest)")"
echo "Release tag:  $TAG"
echo

# --- Has this tag already been used? ---------------------------------------------------------------
USED_LOCAL=false
USED_REMOTE=false
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && USED_LOCAL=true
git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1 && USED_REMOTE=true

if $USED_LOCAL || $USED_REMOTE; then
	echo "Tag $TAG has ALREADY been used:"
	$USED_LOCAL  && echo "  - it exists on this computer"
	$USED_REMOTE && echo "  - it exists on GitHub"
else
	echo "Tag $TAG has not been used yet."
fi
echo

# --- Use this tag, or create a new one? ------------------------------------------------------------
echo "  1) Use tag $TAG"
echo "  2) Create a new tag"
read -rp "Choose 1 or 2: " CHOICE
echo

case "$CHOICE" in
	1) ;;
	2)
		if [ -z "$MANIFEST" ]; then
			echo "Run this script again and enter the new version."
			exit 0
		fi
		echo "To use a new tag:"
		echo "  1. Change \"version\" in $MANIFEST to the new version number."
		echo "  2. Commit that change (and push it)."
		echo "  3. Run this script again."
		exit 0
		;;
	*)
		echo "Cancelled - nothing changed."
		exit 0
		;;
esac

# --- Checks before using the tag -------------------------------------------------------------------
if $USED_LOCAL || $USED_REMOTE; then
	echo "Cannot use $TAG because it already exists. Either choose a new tag (option 2), or delete"
	echo "the existing one first and run this script again:"
	$USED_REMOTE && echo "  git push origin --delete $TAG"
	$USED_LOCAL  && echo "  git tag -d $TAG"
	exit 1
fi

# The tag is put on the current commit, so plugin.json must be committed with this version.
if [ -n "$MANIFEST" ] && ! git diff --quiet HEAD -- "$MANIFEST"; then
	echo "Error: $MANIFEST has uncommitted changes. Commit it first, then run this script again."
	exit 1
fi

# --- Release ---------------------------------------------------------------------------------------
echo "This will:"
echo "  - push branch $BRANCH to GitHub"
echo "  - create tag $TAG on the current commit ($(git log -1 --format='%h %s'))"
echo "  - push tag $TAG (this starts the Release workflow)"
read -rp "Continue? [y/N] " ANSWER
[[ "$ANSWER" =~ ^[Yy]$ ]] || { echo "Cancelled - nothing changed."; exit 0; }

git push origin "$BRANCH"
git tag "$TAG"
git push origin "$TAG"

echo
echo "Done. Tag $TAG pushed - approve the Release run at:"
echo "  $(git remote get-url origin | sed 's/\.git$//')/actions"
