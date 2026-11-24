"""Surf Sound's hub settings: which sound plays on the desktop while you ride a ramp or a ceiling.

Saved in <config>/movekit/surf-sound.json (paths.config_dir). The sound runner (sound_run.py, beside the
game) reads the file again every half second, so a change applies to a running game at once.

Custom sounds (custom.py makes them) live in <config>/movekit/surf-sound-sounds/, one WAV per pick,
named <slot>-<hash>.wav; "custom" maps a slot to {"file": that name, "name": the picked file's name}.
"""
import json
import math
import os
import re

from movekit import paths

SOUND_NAMES = ("wind", "rumble", "hiss", "grind", "stone")  # noise.SOUNDS' keys (check_surf_sound.py compares)
DEFAULTS = {"on": True, "sound": "wind", "volume": 30, "ramp": True, "ceiling": True, "wall": True, "graze": True,
            "bonk": True, "watch": True, "custom": {}}
VOLUME = (0, 100)  # %
SLOTS = ("ramp", "ceiling", "wall", "graze", "bonk")  # the sounds a custom file can replace
FILE_RE = re.compile(r"(ramp|ceiling|wall|graze|bonk)-[0-9a-f]{12}\.wav")
NAME_MAX = 200


def sounds_dir():
    return paths.config_dir("movekit") / "surf-sound-sounds"


def custom_files(cfg):
    """{slot: path} of cfg's custom sounds."""
    return {slot: sounds_dir() / c["file"] for slot, c in cfg["custom"].items()}


def file():
    return paths.config_dir("movekit") / "surf-sound.json"


def check(cfg):
    """The settings with every value checked; ValueError on a bad one."""
    out = dict(DEFAULTS, custom={})
    if not isinstance(cfg, dict):
        raise ValueError("settings must be an object")  # noqa: TRY004 (the hub reports ValueError)
    for key in ("on", "ramp", "ceiling", "wall", "graze", "bonk", "watch"):
        if key in cfg:
            if not isinstance(cfg[key], bool):
                raise ValueError(f"{key} must be true or false")
            out[key] = cfg[key]
    if "graze" not in cfg and "bonk" in cfg:
        out["graze"] = out["bonk"]  # saved before light head hits had their own switch
    custom = cfg.get("custom", {})
    if not isinstance(custom, dict):
        raise ValueError("custom must be an object")  # noqa: TRY004 (the hub reports ValueError)
    for slot, c in custom.items():
        if slot not in SLOTS:
            raise ValueError(f"custom sound for {slot!r}: there is no such sound")
        if not (isinstance(c, dict) and isinstance(c.get("file"), str) and FILE_RE.fullmatch(c["file"])
                and c["file"].startswith(slot + "-") and isinstance(c.get("name"), str)):
            raise ValueError(f"custom {slot} sound: a bad file entry")
        out["custom"][slot] = {"file": c["file"], "name": c["name"][:NAME_MAX]}
    if "sound" in cfg:
        if cfg["sound"] not in SOUND_NAMES:
            raise ValueError(f"sound must be one of {', '.join(SOUND_NAMES)}")
        out["sound"] = cfg["sound"]
    if "volume" in cfg:
        v = cfg["volume"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v):
            raise ValueError("volume needs a number")
        out["volume"] = round(min(max(v, VOLUME[0]), VOLUME[1]))
    return out


def load():
    """The saved settings, or the defaults when there are none or they can't be read."""
    try:
        return check(json.loads(file().read_text()))
    except (OSError, ValueError):
        return check({})


def save(cfg):
    cfg = check(cfg)
    path = file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=1) + "\n")
    os.replace(tmp, path)
    return cfg
