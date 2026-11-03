# shellcheck shell=bash
# Source Yaw's launch hook, sourced by movekit-run (see movekit/movekit-run for the rules;
# install.sh registers it). Rewrites yaws.cfg and the crosshair colours from the app's
# settings. For CS:S it also swaps the crosshair colour while the game runs: it turns KROSSHAIR
# on for the game and points it at our own image, so crosshair-maker's files are never
# touched. Momentum Mod sets its crosshair colour itself, so it only needs the apply.
local CFG OLD_CFG RUNLOG LOG COLORS TRAINER AUTO
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/sourceyaw"
OLD_CFG="${XDG_CONFIG_HOME:-$HOME/.config}/css-yaw"
# settings from before the rename (done here because mkdir below would block it)
[ -d "$OLD_CFG" ] && [ ! -e "$CFG" ] && mv "$OLD_CFG" "$CFG"
RUNLOG="$CFG/run.log"
mkdir -p "$CFG"

{ date; echo "game: $GAME"; python3 "$HOOK_DIR/yawcore.py" --apply "$GAME"; } > "$RUNLOG" 2>&1
# shellcheck source=/dev/null
. "$CFG/watch.env" 2>/dev/null

if [ "$GAME" = css ] && [ "${COLORS:-0}" = 1 ] && [ -n "${LOG:-}" ] && [ -f "$CFG/current.png" ]; then
    export KROSSHAIR=1 KROSSHAIR_IMG="$CFG/current.png"
    # con_logfile appends forever; start fresh each launch, before the watcher or trainer reads it
    : > "$LOG"
    # started directly (not via a function) so $! is the watcher itself
    python3 "$HOOK_DIR/crosshair_watch.py" "$LOG" >> "$RUNLOG" 2>&1 &
    HELPERS="$HELPERS $!"
fi
# bhop/surf list switcher: writes an arm alias into cfg/sourceyaw_auto.cfg when a map loads
if [ "${AUTO:-0}" = 1 ] && [ -n "${LOG:-}" ]; then
    python3 "$HOOK_DIR/mode_watch.py" "$LOG" "$GAME" >> "$RUNLOG" 2>&1 &
    HELPERS="$HELPERS $!"
fi
# strafe trainer: reads keys from the input service and draws the offset through
# the Source Yaw overlay layer, which only loads when SOURCEYAW_OVERLAY=1
if [ "${TRAINER:-0}" = 1 ]; then
    export SOURCEYAW_OVERLAY=1 SOURCEYAW_OVERLAY_ATLAS="$CFG/overlay/atlas.png" \
        SOURCEYAW_OVERLAY_STATE="$CFG/overlay/state"
    python3 "$HOOK_DIR/trainer.py" "$GAME" >> "$RUNLOG" 2>&1 &
    HELPERS="$HELPERS $!"
fi
return 0
