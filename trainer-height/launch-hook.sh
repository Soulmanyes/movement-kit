# shellcheck shell=bash
# Strafe Trainer Height's launch hook, sourced by movekit-run (see movekit/movekit-run for the rules;
# install.py registers it). Installs again before Momentum Mod starts, so the kit's patched
# strafe-trainer.xml and strafe-trainer.ts follow a game update. Momentum only.
[ "$GAME" = momentum ] || return 0
python3 "$HOOK_DIR/install.py" --quiet || echo "movekit-run (trainer-height): install.py failed" >&2
return 0
