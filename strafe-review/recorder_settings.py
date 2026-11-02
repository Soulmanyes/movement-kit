"""Writes the HUD settings (hud/settings.py) into Strafe Review's installed recorder.

Imports only the standard library at load (movekit when writing), and changes nothing on import, so the hub's HUD
section can load it by path (movekit.hub.local_import) next to other tools' modules. install.py
uses it too, so a fresh install carries the saved settings.
"""
import re
from pathlib import Path

FOLDER = "0-strafe-review"  # in custom/; sorts before other mods, so our timer.xml is the one loaded
RECORDER = Path("panorama") / "scripts" / "hud" / "strafe-review.ts"
SHOW_LINE = re.compile(r"^const SHOW_LINE = (true|false);", re.MULTILINE)


def recorder(game):
    """The installed recorder script in Momentum's game folder."""
    return Path(game) / "custom" / FOLDER / RECORDER


def apply(game, show_line):
    """Write show_line into the installed recorder; panorama_reload or a game restart applies it.
    Returns False when the recorder isn't installed."""
    # imported here, so install.py may import this module before steam.py puts movekit on the path
    from movekit.files import write_atomic

    ts = recorder(game)
    try:
        text = ts.read_text(encoding="utf-8")
    except OSError:
        return False
    write_atomic(ts, SHOW_LINE.sub(f"const SHOW_LINE = {'true' if show_line else 'false'};", text))
    return True
