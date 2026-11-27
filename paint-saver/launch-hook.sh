# shellcheck shell=bash
# Paint Saver's launch hook, sourced by movekit-run (see movekit/movekit-run for the rules; install.py
# registers it). Runs the install with --launch before Momentum Mod starts: the paint saved last session
# (read from yaw.log) goes into savedlocs.txt, which the game reads only at launch, and into the HUD
# script's replay plan. Momentum only.
[ "$GAME" = momentum ] || return 0
python3 "$HOOK_DIR/install.py" --quiet --launch || echo "movekit-run (paint-saver): install.py failed" >&2
return 0
