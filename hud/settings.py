"""The in-game display settings, shared by every tool that draws something in game.

Keys (bool unless noted; DEFAULTS has each one's value when unset):
  inGameLine   Strafe Review's recorder shows the jump-1 line (landing speed, gain, mistakes)

The file is settings.json in Strafe Review's data folder (%LOCALAPPDATA%\\strafe-review on Windows,
~/.local/share/strafe-review elsewhere), where the review page kept it before hud/ took it over.
Installed strafe-review v1.5.0 exes read and write it there, so it stays until the hub release
(PLAN.md 3.7). Keys this module doesn't know are kept as they are.

Saving only stores a value; the tool that draws it writes it into the game (for the jump-1 line:
strafe-review/recorder_settings.py).
"""
import json

from movekit import paths
from movekit.files import write_atomic

DEFAULTS = {"inGameLine": False}


def file():
    return paths.data_dir("strafe-review") / "settings.json"


def _stored():
    try:
        got = json.loads(file().read_text(encoding="utf-8"))
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
