"""Z Penalty's hub settings: the sound played in game when a penalised stretch starts.

Saved in <config>/movekit/z-penalty.json (paths.config_dir). The game can't read that file, so
install.py writes the setting into the panel script's SOUND line (bake) when it copies the script,
and the hub page runs the install again on Apply. The script plays it with `playvol <name> <volume>`
through GameInterfaceAPI.ConsoleCommand (probe 14.1, 2026-11-09: works in Momentum).
"""
import json
import math
import os
import re
from pathlib import Path

from movekit import paths

DEFAULTS = {"on": False, "name": "buttons/blip1", "volume": 60}
VOLUME = (0, 100)
# a sound path under sound/, without the extension; nothing a console command could read as more
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,99}$")
LINE_RE = re.compile(r"^const SOUND = .*// movekit:sound$", re.MULTILINE)


def file():
    return paths.config_dir("movekit") / "z-penalty.json"


def check(cfg):
    """The settings with every value checked; ValueError on a bad one."""
    out = dict(DEFAULTS)
    if not isinstance(cfg, dict):
        raise ValueError("settings must be an object")  # noqa: TRY004 (the hub reports ValueError)
    if "on" in cfg:
        if not isinstance(cfg["on"], bool):
            raise ValueError("on must be true or false")
        out["on"] = cfg["on"]
    if "name" in cfg:
        if not isinstance(cfg["name"], str) or not NAME_RE.match(cfg["name"]) or ".." in cfg["name"]:
            raise ValueError(f"not a sound name: {cfg['name']!r}")
        out["name"] = cfg["name"]
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
        return dict(DEFAULTS)


def save(cfg):
    cfg = check(cfg)
    path = file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=1) + "\n")
    os.replace(tmp, path)
    return cfg


def sound_line(cfg):
    return f"const SOUND = {json.dumps(check(cfg))}; // movekit:sound"


def bake(text, cfg):
    """The panel script's text with its SOUND line set to cfg."""
    new, n = LINE_RE.subn(lambda _: sound_line(cfg), text)
    if n != 1:
        raise ValueError(f"the script has {n} SOUND lines, not 1")
    return new


def bake_file(src, dest, cfg):
    Path(dest).write_text(bake(Path(src).read_text(encoding="utf-8"), cfg), encoding="utf-8")
