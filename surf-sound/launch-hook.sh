# shellcheck shell=bash
# Surf Sound's launch hook, sourced by movekit-run (see movekit/movekit-run for the rules; install.py
# registers it). Installs again before Momentum Mod starts, so the kit's patched timer.xml follows a
# game update, then runs the sound runner (sound_run.py) beside the game; it stays silent while the
# sound is off in the hub, and movekit-run stops it when the game exits. Momentum only.
[ "$GAME" = momentum ] || return 0
local RUNLOG
RUNLOG="${XDG_CONFIG_HOME:-$HOME/.config}/movekit/surf-sound-run.log"
mkdir -p "$(dirname "$RUNLOG")"
python3 "$HOOK_DIR/install.py" --quiet || echo "movekit-run (surf-sound): install.py failed" >&2
{ date; echo "surf-sound: sound runner"; } > "$RUNLOG"
python3 "$HOOK_DIR/sound_run.py" >> "$RUNLOG" 2>&1 &
HELPERS="$HELPERS $!"
return 0
