"""The in-game display settings, shared by every tool that draws something in game.

Keys (bool unless noted; DEFAULTS has each one's value when unset):
  inGameLine   legacy: Strafe Review before 1.9.0 shows its jump-1 line (landing speed, gain,
               mistakes). Since 1.9.0 that line is First Jump HUD, set in the game's HUD customizer;
               the key stays for the old versions (their install.py reads it).

The file is hud.json in the kit's data folder (%LOCALAPPDATA%\\movekit on Windows,
~/.local/share/movekit elsewhere). Until the first save there, the values come from the old file,
settings.json in Strafe Review's data folder, where the review page kept them before the HUD
took them over (PLAN.md 3.9). The old file is left alone: a strafe-review v1.5.0 exe that hasn't
updated yet still reads it. Keys this module doesn't know are kept as they are.

Saving only stores a value; the tool that draws it writes it into the game (for the old jump-1
line: recorder_settings.py in Strafe Review before 1.9.0).
"""
import json

from movekit import paths
from movekit.files import write_atomic

DEFAULTS = {"inGameLine": False}


def file():
    return paths.data_dir("movekit") / "hud.json"


def old_file():
    """Where the values were kept before hud.json; read only while hud.json doesn't exist."""
    return paths.data_dir("strafe-review") / "settings.json"


def _stored():
    path = file() if file().exists() else old_file()
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def load():
    """Every known setting: the stored value when it has the right type, else the default."""
    got = _stored()
    return {k: got[k] if type(got.get(k)) is type(v) else v for k, v in DEFAULTS.items()}


def get(key):
    return load()[key]


def save(key, value):
    """Store one setting. Raises KeyError for an unknown key, TypeError for a wrong type."""
    if key not in DEFAULTS:
        raise KeyError(f"no HUD setting {key!r}")
    if type(value) is not type(DEFAULTS[key]):
        raise TypeError(f"{key} must be {type(DEFAULTS[key]).__name__}, not {type(value).__name__}")
    got = _stored()
    got[key] = value
    file().parent.mkdir(parents=True, exist_ok=True)
    write_atomic(file(), json.dumps(got, indent=2) + "\n")
