# shellcheck shell=bash
# The Strafe Trainer's launch hook, sourced by movekit-run (see movekit/movekit-run for the rules;
# install.py registers it). Writes the autoexec block again, then runs trainer.py beside the game:
# keys from the input service, the offset drawn by the overlay layer, which only loads when
# SOURCEYAW_OVERLAY=1 (the layer kept Source Yaw's names).
local DATA RUNLOG
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/strafe-trainer"
RUNLOG="${XDG_CONFIG_HOME:-$HOME/.config}/strafe-trainer/run.log"
mkdir -p "$(dirname "$RUNLOG")"
# a Source Yaw from before Phase 13 (1.10 or older, e.g. rolled back) runs its own trainer
if [ -f "${XDG_DATA_HOME:-$HOME/.local/share}/sourceyaw/trainer.py" ]; then
    { date; echo "strafe-trainer: Source Yaw still has its own trainer (1.10 or older); update Source Yaw"; } > "$RUNLOG"
    return 0
fi
{ date; echo "game: $GAME"; python3 "$HOOK_DIR/install.py" --apply "$GAME" --quiet; } > "$RUNLOG" 2>&1
if python3 "$HOOK_DIR/trainer.py" "$GAME" --enabled >> "$RUNLOG" 2>&1; then
    export SOURCEYAW_OVERLAY=1 SOURCEYAW_OVERLAY_ATLAS="$DATA/overlay/atlas.png" \
        SOURCEYAW_OVERLAY_STATE="$DATA/overlay/state"
    python3 "$HOOK_DIR/trainer.py" "$GAME" >> "$RUNLOG" 2>&1 &
    HELPERS="$HELPERS $!"
fi
return 0
