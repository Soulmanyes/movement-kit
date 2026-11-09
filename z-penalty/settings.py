"""Z Penalty's hub settings: the constant tone that sounds on the desktop while the penalty is on.

Saved in <config>/movekit/z-penalty.json (paths.config_dir). The tone runner (tone_run.py, beside the
game) reads the file again every half second, so a change applies to a running game at once.

A file from before the tone (it held a game sound's `name`) still loads: unknown keys are ignored.
"""
import json
import math
import os

from movekit import paths

DEFAULTS = {"on": False, "pitch": 330, "volume": 30}
PITCH = (40, 2000)  # Hz
VOLUME = (0, 100)  # %


def file():
    return paths.config_dir("movekit") / "z-penalty.json"


def _number(cfg, key, low, high):
    v = cfg[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v):
        raise ValueError(f"{key} needs a number")
    return round(min(max(v, low), high))


def check(cfg):
    """The settings with every value checked; ValueError on a bad one."""
    out = dict(DEFAULTS)
    if not isinstance(cfg, dict):
        raise ValueError("settings must be an object")  # noqa: TRY004 (the hub reports ValueError)
    if "on" in cfg:
        if not isinstance(cfg["on"], bool):
            raise ValueError("on must be true or false")
        out["on"] = cfg["on"]
    if "pitch" in cfg:
        out["pitch"] = _number(cfg, "pitch", *PITCH)
    if "volume" in cfg:
        out["volume"] = _number(cfg, "volume", *VOLUME)
    return out


def load():
    """The saved settings, or the defaults when there are none or they can't be read."""
    try:
        return check(json.loads(file().read_text()))
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(cfg):
    cfg = check(cfg)
    path = file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=1) + "\n")
    os.replace(tmp, path)
    return cfg
