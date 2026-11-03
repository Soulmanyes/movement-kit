#!/usr/bin/env python3
"""Swaps the CS:S crosshair when the yaw_cycle bind echoes "YAW_<speed>" ("YAWSURF_<speed>" for the surf list; started by launch-hook.sh through movekit-run).

  crosshair_watch.py LOG

The tokens come from the movekit session for LOG (movekit/session.py), which applies the rules the
old yaw-watch.sh had: a token counts as soon as something follows it, without waiting for the line
break; chat is ignored. launch-hook.sh starts the game with KROSSHAIR_IMG pointing at current.png,
and KROSSHAIR reloads that file whenever its mtime changes. It also empties LOG first,
since con_logfile appends forever.
"""
import os
import re
import shutil
import signal
import sys
from pathlib import Path

import yawcore

from movekit import session  # after yawcore, which puts movekit on the path

IMG = yawcore.CONFIG_DIR / "crosshairs"
CURRENT = yawcore.CONFIG_DIR / "current.png"
YAW = re.compile(r"YAW(?:SURF)?_\d+(?:\.\d+)?")


def swap(name, img=IMG, current=CURRENT):
    """Show crosshair <img>/<name>.png; False if there is none for that speed."""
    src = Path(img) / f"{name}.png"
    if not src.is_file():
        return False
    # copy then rename, so the layer never reads a half-written PNG
    tmp = Path(current).with_suffix(".png.tmp")
    shutil.copyfile(src, tmp)
    os.replace(tmp, current)
    return True


def handle(event, img=IMG, current=CURRENT):
    """Swap the crosshair for a YAW_<speed> or YAWSURF_<speed> token event; True if it did."""
    name = event["data"].get("name") if event["type"] == "token" else None
    return bool(name and YAW.fullmatch(name) and swap(name, img, current))


def run(log, img=IMG, current=CURRENT, port=session.PORT):
    joined = session.join(log, port=port)
    print(f"crosshair: session events for {log} ({joined.mode})", flush=True)
    try:
        while True:
            handle(joined.events.get(), img, current)
    finally:
        joined.close()


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LOG")
    if not log:
        sys.exit("crosshair: no log given; open Source Yaw and press Apply")
    # movekit-run stops its helpers with SIGTERM: leave through finally, freeing the session's port
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        run(log)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
