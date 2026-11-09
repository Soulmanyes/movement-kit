#!/bin/sh
# Installs the hub (movekit/hub.py, one window for the kit's modules and settings) on Linux.
#   ./movekit/install-hub.sh              add the launcher and its icon
#   ./movekit/install-hub.sh --copy       the same, from a copy (see below), also in a git checkout
#   ./movekit/install-hub.sh --uninstall  remove them
# From a git checkout the launcher runs the hub in place, so `git pull` updates it; nothing is
# copied. Anywhere else (a release download, curl | sh below, the core's own update) it copies the
# core (movekit/ and hud/) to ~/.local/share/movekit/kit, links ~/.local/bin/movekit-run (the
# Steam launch option) to that copy, and runs the hub from there. The tools are modules the hub
# installs next to the core; a new copy starts with none, and an update leaves them as they are.
# Without cloning the repo:
#   curl -fsSL https://raw.githubusercontent.com/Soulmanyes/movement-kit/main/movekit/install-hub.sh | sh
# Needs pywebview (python-pywebview on Arch); it only warns if that's missing.
# The whole script is one { } block, so a download cut off midway runs nothing.
{
set -eu

APP_ID=io.github.soulmanyes.MovementKit  # hub.py's APP_ID; docks match the window to the launcher by it
DATA=${XDG_DATA_HOME:-$HOME/.local/share}
APPS=$DATA/applications
ICONS=$DATA/icons/hicolor/scalable/apps
KIT=$DATA/movekit/kit   # movekit.modules.core_kit()
BIN=${MOVEKIT_BIN_DIR:-$HOME/.local/bin}  # movekit-dev points it at the dev kit
CORE="movekit hud"      # the core's folders; every other folder in $KIT is a module

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }

HERE=$(cd "$(dirname "$0")" && pwd)
# run through curl | sh: the repo isn't next to the script, so fetch the newest hub release and
# run its installer
if [ ! -f "$HERE/hub.py" ]; then
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    say "Downloading Soulmanyes's Movement Kit"
    # the newest hub-v* tag; main if there is none yet (the repo holds every tool's tags)
    tag=$(curl -fsSL https://api.github.com/repos/Soulmanyes/movement-kit/git/matching-refs/tags/hub-v 2>/dev/null |
        sed -n 's|.*"ref": *"refs/tags/\(hub-v[0-9.]*\)".*|\1|p' | sort -V | tail -n 1) || tag=
    ref=${tag:+tags/$tag}
    curl -fsSL "https://github.com/Soulmanyes/movement-kit/archive/refs/${ref:-heads/main}.tar.gz" |
        tar -xz -C "$tmp" --strip-components=1
    sh "$tmp/movekit/install-hub.sh" "$@"
    exit
fi
SRC=$(dirname "$HERE")  # the kit root this script came with

mode=checkout
[ -e "$SRC/.git" ] || mode=copy
[ "$SRC" = "$KIT" ] && mode=installed   # the copy's own script: only the launcher
case ${1:-} in
    --copy) [ "$mode" = installed ] || mode=copy ;;
    --uninstall|"") ;;
    *) echo "usage: install-hub.sh [--copy | --uninstall]" >&2; exit 2 ;;
esac

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$APPS/$APP_ID.desktop" "$ICONS/$APP_ID.svg"
    say "Removed the hub's launcher"
    if [ -d "$KIT/movekit" ]; then
        left=$(for d in "$KIT"/*/; do [ -f "$d/module.json" ] && basename "$d"; done || true)
        if [ -n "$left" ]; then
            echo "Kept the core in $KIT: modules are still installed ($(echo $left))."
            echo "Uninstall them in the hub first, then run this again."
        else
            # movekit-run goes with the core unless a tool installed before the core still has a copy
            if [ "$(readlink "$BIN/movekit-run" 2>/dev/null)" = "$KIT/movekit/movekit-run" ]; then
                rm -f "$BIN/movekit-run"
            fi
            rm -rf "$KIT"
            say "Removed the core from $KIT"
            echo "Take movekit-run out of the games' launch options, or they won't start."
        fi
    fi
    exit 0
fi

if [ "$mode" = copy ]; then
    say "Copying the core to $KIT"
    mkdir -p "$KIT"
    new=$KIT/.core-new old=$KIT/.core-old
    rm -rf "$new" "$old"
    mkdir -p "$new" "$old"
    for d in $CORE; do
        cp -r "$SRC/$d" "$new/$d"
        # the checks and caches stay behind
        find "$new/$d" \( -name 'check_*' -o -name '__pycache__' \) -prune -exec rm -rf {} +
    done
    [ -f "$SRC/LICENSE" ] && cp "$SRC/LICENSE" "$new/LICENSE"
    chmod 755 "$new/movekit/movekit-run" "$new/movekit/install-hub.sh"
    # swap folder by folder: movekit-run is gone only between two renames, never half copied
    for d in $CORE LICENSE; do
        [ -e "$new/$d" ] || continue
        [ -e "$KIT/$d" ] && mv "$KIT/$d" "$old/$d"
        mv "$new/$d" "$KIT/$d"
    done
    rm -rf "$new" "$old"
    HUB=$KIT/movekit/hub.py
    ICON_SRC=$KIT/movekit/icons
    # the launch option; it starts the game with no modules too (launch.py keeps it on the core)
    mkdir -p "$BIN"
    ln -sfn "$KIT/movekit/movekit-run" "$BIN/movekit-run"
else
    HUB=$HERE/hub.py
    ICON_SRC=$HERE/icons
fi

mkdir -p "$APPS" "$ICONS"
cp "$ICON_SRC/$APP_ID.svg" "$ICONS/$APP_ID.svg"
cat > "$APPS/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Soulmanyes's Movement Kit
GenericName=Movement tool settings
Comment=Install and set up Source Yaw, the HUD, Gain Converter and Strafe Review
Exec=python3 "$HUB"
Icon=$APP_ID
StartupWMClass=$APP_ID
Categories=Game;Utility;
Keywords=counter-strike;css;momentum;surf;bhop;strafe;gain;yawspeed;
DESKTOP
command -v update-desktop-database >/dev/null && update-desktop-database -q "$APPS" || true
say "Added \"Soulmanyes's Movement Kit\" to the app launcher"
if [ "$mode" = copy ]; then
    echo "Install the tools from its Modules page. Launch option for the games, before %command%:"
    echo "    movekit-run"
fi

if ! python3 -c "import webview" 2>/dev/null; then
    echo "The hub needs pywebview: sudo pacman -S python-pywebview (Arch), pip install pywebview elsewhere."
fi
}
