# shellcheck shell=bash
# JHUD's launch hook, sourced by movekit-run (see movekit/movekit-run for the rules; install.py
# registers it). Installs again before Momentum Mod starts, so the kit's patched timer.xml and
# hud_default.kv3 follow a game update. Momentum only.
[ "$GAME" = momentum ] || return 0
python3 "$HOOK_DIR/install.py" --quiet || echo "movekit-run (jhud): install.py failed" >&2
return 0
