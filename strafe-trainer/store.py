"""The Strafe Trainer's settings: one dict per game in paths.config_dir("strafe-trainer")/settings.json
({"game": last used, "profiles": {game: settings}}), the defaults, and the one-time import from
Source Yaw, where the trainer lived until Phase 13.

Before Phase 13 the settings sat under "trainer" in each game's Source Yaw profile
(~/.config/sourceyaw/settings.json, %APPDATA%\\sourceyaw on Windows). import_from_sourceyaw() copies
each game's dict that has no own profile yet; Source Yaw's file is only read, so a rolled-back
Source Yaw still finds its old settings.
"""
import json
from pathlib import Path

from movekit import files, paths

CONFIG_DIR = paths.config_dir("strafe-trainer")
SETTINGS = CONFIG_DIR / "settings.json"
GAMES = ("css", "momentum")

DEFAULTS = {
    "enabled": False,
    "tone_volume": 0.3,            # 0-1, for the constant tone
    "repeat": 0.2,                 # game sound: seconds between plays while wrong; 0 = once
    # the cues (CUES): on/off, sound ("tone" or a game sound), the tone's Hz, and the
    # ticks the mistake must last before it sounds
    "cue_wrong_key": True, "wrong_sound": "tone", "wrong_pitch": 220, "wrong_ticks": 3,
    "cue_no_key": True, "none_sound": "tone", "none_pitch": 147, "none_ticks": 3,
    "cue_overlap": True, "overlap_sound": "tone", "overlap_pitch": 110, "overlap_ticks": 1,
    "target": -1,                  # the offset counted as best (shown green)
    "show_offset": True,           # at launch; offset_key flips it in game
    "offset_key": "",              # key bound in the trainer's autoexec block to show or hide the offset
    "x": 0.5, "y": 0.56,           # number's centre, as a fraction of the screen
    "size": 36,                    # font size in pixels
    "colors": {"early": "#ff5a5a", "perfect": "#5aff78", "late": "#ffc83c"},
    "hide_after": 2.0,             # seconds the last offset stays up
    "window": 0.25,                # seconds a key switch may be from a turn to count
    "mouse_threshold": 4,          # mouse counts the other way that make a turn
    # CS:S servers pick their own tickrate; Momentum's follows the map's game mode
    "tickrate": {"css": 66, "momentum": 100},
    "map_tickrates": {"surf_": 66, "bhop_": 100},
}

# cue -> its on/off setting: "wrong" turning with the other strafe key held, "none" turning with
# no strafe key held, "overlap" both strafe keys held. Its other settings are <cue>_sound,
# <cue>_pitch and <cue>_ticks.
CUES = {"wrong": "cue_wrong_key", "none": "cue_no_key", "overlap": "cue_overlap"}


def migrate(saved):
    """Settings saved before each cue had its own sound (Source Yaw 1.9.0 and older: one `sound`
    and `tone_pitch` for both wrong-key cues, the no-key tone at 2/3 of that pitch, one
    `wrong_ticks`) in today's keys."""
    saved = dict(saved or {})
    if "wrong_sound" not in saved and "sound" in saved:
        if not saved["sound"]:  # "" played nothing
            saved["cue_wrong_key"] = saved["cue_no_key"] = False
        saved["wrong_sound"] = saved["none_sound"] = saved["sound"] or "tone"
    if "wrong_pitch" not in saved and "tone_pitch" in saved:
        saved["wrong_pitch"] = int(saved["tone_pitch"])
        saved["none_pitch"] = max(40, round(int(saved["tone_pitch"]) * 2 / 3))
    if "none_ticks" not in saved and "wrong_ticks" in saved:
        saved["none_ticks"] = saved["wrong_ticks"]
    return saved


def _read(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _whole():
    data = _read(SETTINGS) or {}
    if not isinstance(data.get("profiles"), dict):
        data["profiles"] = {}
    return data


def _write(whole):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    files.write_atomic(SETTINGS, json.dumps(whole, indent=2) + "\n")


def saved(game):
    """The game's saved dict as stored (migrated), {} when there is none."""
    return migrate(_whole()["profiles"].get(game))


def config(game):
    """The game's settings over the defaults (colours and per-game tickrates merged too)."""
    data = saved(game)
    cfg = {**DEFAULTS, **data}
    cfg["colors"] = {**DEFAULTS["colors"], **data.get("colors", {})}
    cfg["tickrate"] = {**DEFAULTS["tickrate"], **data.get("tickrate", {})}
    cfg["map_tickrates"] = dict(data.get("map_tickrates") or DEFAULTS["map_tickrates"])
    return cfg


def save(game, cfg):
    whole = _whole()
    whole["profiles"][game] = cfg
    whole["game"] = game
    _write(whole)


def last_game():
    return _whole().get("game", "css")


def set_last_game(game):
    whole = _whole()
    whole["game"] = game
    _write(whole)


def enabled_games():
    return [g for g in GAMES if config(g)["enabled"]]


# ---------------------------------------------------------------- from Source Yaw

def sourceyaw_settings_file():
    """Source Yaw's settings.json (it keeps them in ~/.config on Linux, as paths.config_dir does)."""
    return paths.config_dir("sourceyaw") / "settings.json"


def sourceyaw_trainers(path=None):
    """{game: trainer dict} from Source Yaw's settings. A file from before Momentum support held
    just the CS:S settings."""
    raw = _read(path or sourceyaw_settings_file())
    if raw is None:
        return {}
    profiles = raw.get("profiles") if "profiles" in raw else {"css": raw}
    if not isinstance(profiles, dict):
        return {}
    return {g: p["trainer"] for g, p in profiles.items()
            if g in GAMES and isinstance(p, dict) and isinstance(p.get("trainer"), dict)}


def import_from_sourceyaw(path=None):
    """Copy each game's trainer settings from Source Yaw that has no own profile here; returns the
    games copied. Source Yaw's file stays as it is."""
    found = sourceyaw_trainers(path)
    whole = _whole()
    copied = [g for g in GAMES if g in found and g not in whole["profiles"]]
    if not copied:
        return []
    for game in copied:
        whole["profiles"][game] = migrate(found[game])
    if "game" not in whole:
        raw = _read(path or sourceyaw_settings_file()) or {}
        whole["game"] = raw.get("game") if raw.get("game") in GAMES else copied[0]
    _write(whole)
    return copied

