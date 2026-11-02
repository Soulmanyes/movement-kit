#!/usr/bin/env python3
"""Checks yawcore.launch_option, the launch options the app suggests; no Steam needed.

Usage: python sourceyaw/check_launch_option.py   (exits 1 on the first failure)

movekit-run is added before %command%; any name that already runs Source Yaw (movekit-run, the old
sourceyaw-run, css-yaw-run, a full path to yaw-run or movekit-run) counts as set up, and is only
rewritten when it can't work here (a full path where the short name works, or the other way).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yawcore  # also puts movekit on the path

FULL = "/home/u/.local/share/sourceyaw/movekit/movekit-run"
CASES = [
    # (current, run, want options, want "already there")
    ("", "movekit-run", "movekit-run %command%", False),
    (None, "movekit-run", "movekit-run %command%", False),
    ("-novid", "movekit-run", "movekit-run %command% -novid", False),
    ("game-performance %command% -novid", "movekit-run", "game-performance movekit-run %command% -novid", False),
    ("movekit-run %command%", "movekit-run", "movekit-run %command%", True),
    ("A=1 game-performance sourceyaw-run %command%", "movekit-run",
     "A=1 game-performance sourceyaw-run %command%", True),
    ("css-yaw-run %command%", "movekit-run", "css-yaw-run %command%", True),
    ("A=1 game-performance strafe-review-run sourceyaw-run %command%", "movekit-run",
     "A=1 game-performance strafe-review-run sourceyaw-run %command%", True),
    # strafe-review-run alone runs only Strafe Review
    ("strafe-review-run %command%", "movekit-run", "strafe-review-run movekit-run %command%", False),
    ("/old/share/sourceyaw/yaw-run %command%", "movekit-run", "movekit-run %command%", False),
    ("sourceyaw-run %command%", FULL, f"{FULL} %command%", False),
    (f"{FULL} %command%", FULL, f"{FULL} %command%", True),
]


def main():
    for current, run, want, already in CASES:
        got = yawcore.launch_option(current, run)
        if got != (want, already):
            sys.exit(f"FAIL {current!r} with {run}: got {got!r}, want {(want, already)!r}")
        print(f"ok   {current!r} -> {want!r}{' (already there)' if already else ''}")
    print("all launch option checks passed")


if __name__ == "__main__":
    main()
