#!/bin/sh
# Adds the hub (movekit/hub.py, one settings window for the kit's tools) to the app launcher.
# The launcher runs the hub from this checkout, so `git pull` updates it; nothing is copied.
#   ./movekit/install-hub.sh              add the launcher and its icon
#   ./movekit/install-hub.sh --uninstall  remove them
# Needs pywebview (python-pywebview on Arch); it only warns if that's missing.
set -eu

APP_ID=io.github.soulmanyes.MovementKit  # hub.py's APP_ID; docks match the window to the launcher by it
HERE=$(cd "$(dirname "$0")" && pwd)
APPS=${XDG_DATA_HOME:-$HOME/.local/share}/applications
ICONS=${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$APPS/$APP_ID.desktop" "$ICONS/$APP_ID.svg"
    say "Removed the hub's launcher"
    exit 0
fi

mkdir -p "$APPS" "$ICONS"
cp "$HERE/icons/$APP_ID.svg" "$ICONS/$APP_ID.svg"
cat > "$APPS/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Soulmanyes's Movement Kit
GenericName=Movement tool settings
Comment=Settings for Source Yaw, the HUD, Gain Converter and Strafe Review
Exec=python3 "$HERE/hub.py"
Icon=$APP_ID
StartupWMClass=$APP_ID
Categories=Game;Utility;
Keywords=counter-strike;css;momentum;surf;bhop;strafe;gain;yawspeed;
DESKTOP
command -v update-desktop-database >/dev/null && update-desktop-database -q "$APPS" || true
say "Added \"Soulmanyes's Movement Kit\" to the app launcher"

if ! python3 -c "import webview" 2>/dev/null; then
    echo "The hub needs pywebview: sudo pacman -S python-pywebview (Arch), pip install pywebview elsewhere."
fi
