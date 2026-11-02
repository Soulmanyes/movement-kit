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


def config_dir(app):
    """%APPDATA%\\<app> on Windows, $XDG_CONFIG_HOME/<app> (~/.config/<app>) elsewhere."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / app
