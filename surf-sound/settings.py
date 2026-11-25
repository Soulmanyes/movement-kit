"""Surf Sound's hub settings: which sound plays on the desktop while you ride a ramp or a ceiling.

Saved in <config>/movekit/surf-sound.json (paths.config_dir). The sound runner (sound_run.py, beside the
game) reads the file again every half second, so a change applies to a running game at once.

Custom sounds (custom.py makes them) live in <config>/movekit/surf-sound-sounds/, one WAV per pick,
named <slot>-<hash>.wav; "custom" maps a slot to {"file": that name, "name": the picked file's name}.

"mic" is the microphone the hub's Rec records from (mic.inputs()'s id; "" for the system's default
input). Only the hub reads it.

"levels" gives each sound (SLOTS) its own volume in %, VOLUME[0] to VOLUME[1]. There is no main volume:
settings saved before 1.2.0 had one ("volume"), which is dropped, so every sound starts at the default.
"""
import json
import math
import os
import re

from movekit import paths

SOUND_NAMES = ("wind", "rumble", "hiss", "grind", "stone", "squeak")  # noise.SOUNDS' keys (check_surf_sound.py compares)
# jump: off by default (1.4.0), so an update doesn't add a sound to every bhop
DEFAULTS = {"on": True, "sound": "wind", "ramp": True, "ceiling": True, "wall": True, "graze": True,
            "bonk": True, "jump": False, "watch": True, "custom": {}, "levels": {}, "mic": "",
            "ceiling_sound": "", "split_ceiling": False}
VOLUME = (0, 100)  # %, per sound
SLOTS = ("ramp", "ceiling", "wall", "graze", "bonk", "jump")  # the sounds a custom file or a volume can change
DEFAULTS["levels"] = dict.fromkeys(SLOTS, 80)
FILE_RE = re.compile(r"(ramp|ceiling|wall|graze|bonk|jump)-[0-9a-f]{12}\.wav")
NAME_MAX = 200


def sounds_dir():
    return paths.config_dir("movekit") / "surf-sound-sounds"


def loop_sounds(cfg):
    """{"ramp", "ceiling"}: each loop's built-in sound. "sound" is the ramp's. A headsurf plays the
    ramp's too unless "split_ceiling" (1.5.0) gives it its own: "ceiling_sound", "" meaning the ramp's."""
    split = cfg["split_ceiling"]
    return {"ramp": cfg["sound"], "ceiling": (split and cfg["ceiling_sound"]) or cfg["sound"]}


def loop_variants(cfg):
    """{"ramp", "ceiling"}: the variant each loop's built-in sound renders as (noise.BRIGHT). A headsurf
    sounds just like a ramp unless split: then it is the ceiling variant, the same sound since 1.6.0."""
    return {"ramp": "ramp", "ceiling": "ceiling" if cfg["split_ceiling"] else "ramp"}


def custom_files(cfg):
    """{slot: path} of cfg's custom sounds. Unless split_ceiling, a headsurf plays the ramp's file (or
    none): its own stays saved for when it is split again."""
    files = {slot: sounds_dir() / c["file"] for slot, c in cfg["custom"].items()}
    if not cfg["split_ceiling"]:
        files.pop("ceiling", None)
        if "ramp" in files:
            files["ceiling"] = files["ramp"]
    return files


def levels(cfg):
    """{slot: volume 0-1} of cfg."""
    return {slot: v / 100 for slot, v in cfg["levels"].items()}


def _number(v, what, low, high):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v):
        raise ValueError(f"{what} needs a number")
    return round(min(max(v, low), high))


def file():
    return paths.config_dir("movekit") / "surf-sound.json"


def check(cfg):
    """The settings with every value checked; ValueError on a bad one."""
    out = dict(DEFAULTS, custom={}, levels=dict(DEFAULTS["levels"]))
    if not isinstance(cfg, dict):
        raise ValueError("settings must be an object")  # noqa: TRY004 (the hub reports ValueError)
    for key in ("on", "ramp", "ceiling", "wall", "graze", "bonk", "jump", "watch", "split_ceiling"):
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
    levels = cfg.get("levels", {})  # an old "volume" (before 1.2.0) is ignored (owner 2026-11-24)
    if not isinstance(levels, dict):
        raise ValueError("levels must be an object")  # noqa: TRY004 (the hub reports ValueError)
    for slot, v in levels.items():
        if slot not in SLOTS:
            raise ValueError(f"volume for {slot!r}: there is no such sound")
        out["levels"][slot] = _number(v, f"the {slot} volume", *VOLUME)
    if "mic" in cfg:
        if not isinstance(cfg["mic"], str) or len(cfg["mic"]) > NAME_MAX:
            raise ValueError("mic must be a device name")
        out["mic"] = cfg["mic"]
    if "sound" in cfg:
        if cfg["sound"] not in SOUND_NAMES:
            raise ValueError(f"sound must be one of {', '.join(SOUND_NAMES)}")
        out["sound"] = cfg["sound"]
    if "ceiling_sound" in cfg:
        if cfg["ceiling_sound"] not in ("", *SOUND_NAMES):
            raise ValueError(f"ceiling_sound must be one of {', '.join(SOUND_NAMES)}")
        out["ceiling_sound"] = cfg["ceiling_sound"]
    if "split_ceiling" not in cfg and "ceiling" in out["custom"]:
        out["split_ceiling"] = True  # saved before 1.5.0 with a headsurf sound of its own: keep it

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
