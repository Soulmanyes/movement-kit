"""Where a tool keeps its own files, per OS."""
import os
import sys
from pathlib import Path


def data_dir(app):
    """%LOCALAPPDATA%\\<app> on Windows, $XDG_DATA_HOME/<app> (~/.local/share/<app>) elsewhere."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / app
