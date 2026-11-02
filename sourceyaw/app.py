#!/usr/bin/env python3
"""Source Yaw's launcher: opens the Movement Kit hub on its Source Yaw section.

Source Yaw's own GTK window retired in Phase 3.8 (PLAN.md); its settings live in the hub. This file
keeps the old ways in working: the "Source Yaw" app menu entry, ~/.local/bin/sourceyaw, and an old
window that restarts itself here after updating. Standard library only.
"""
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

DATA = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
HUB_ENTRY = DATA / "applications" / "io.github.soulmanyes.MovementKit.desktop"
INSTALL = "curl -fsSL https://raw.githubusercontent.com/Soulmanyes/movement-kit/main/movekit/install-hub.sh | sh"


def find_hub():
    """The hub.py the hub's app menu entry runs (a git checkout or the installed core), else the
    installed core's; None without a hub."""
    places = []
    try:
        line = re.search(r"^Exec=(.*)$", HUB_ENTRY.read_text(), re.MULTILINE)
        places += [Path(a) for a in shlex.split(line.group(1)) if a.endswith("hub.py")] if line else []
    except (OSError, ValueError):
        pass
    places.append(DATA / "movekit" / "kit" / "movekit" / "hub.py")
    return next((p for p in places if p.is_file()), None)


def main():
    hub = find_hub()
    if hub:
        os.execv(sys.executable, [sys.executable, str(hub), "--section", "sourceyaw"])
    text = f"Source Yaw's settings are in Soulmanyes's Movement Kit now. Install it with:\n    {INSTALL}"
    print(text, file=sys.stderr)
    if not sys.stderr.isatty() and shutil.which("notify-send"):
        subprocess.run(["notify-send", "Source Yaw", text], check=False)
    sys.exit(1)


if __name__ == "__main__":
    main()
