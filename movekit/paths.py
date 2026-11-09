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


def bin_dir():
    """Where the launch wrapper's links go: $MOVEKIT_BIN_DIR (the dev kit's own, see movekit-dev),
    else ~/.local/bin, which Steam has in its PATH."""
    return Path(os.environ.get("MOVEKIT_BIN_DIR") or Path.home() / ".local" / "bin")


def dev():
    """True in the dev kit (movekit-dev): a second kit from the git checkout whose files live in a
    tree of their own, so it never changes the installed kit."""
    return os.environ.get("MOVEKIT_DEV") == "1"
