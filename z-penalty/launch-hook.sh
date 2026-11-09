# shellcheck shell=bash
# Z Penalty's launch hook, sourced by movekit-run (see movekit/movekit-run for the rules; install.py
# registers it). Installs again before Momentum Mod starts, so the kit's patched timer.xml and
# hud_default.kv3 follow a game update, then runs the tone runner (tone_run.py) beside the game; it
# stays silent while the tone is off in the hub, and movekit-run stops it when the game exits.
# Momentum only.
[ "$GAME" = momentum ] || return 0
local RUNLOG
RUNLOG="${XDG_CONFIG_HOME:-$HOME/.config}/movekit/z-penalty-run.log"
mkdir -p "$(dirname "$RUNLOG")"
python3 "$HOOK_DIR/install.py" --quiet || echo "movekit-run (z-penalty): install.py failed" >&2
{ date; echo "z-penalty: tone runner"; } > "$RUNLOG"
python3 "$HOOK_DIR/tone_run.py" >> "$RUNLOG" 2>&1 &
HELPERS="$HELPERS $!"
return 0
