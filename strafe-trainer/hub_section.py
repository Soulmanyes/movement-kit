"""The Strafe Trainer section (movekit/hub.py): its settings as a hub page (hub/), moved out of Source
Yaw's section in Phase 13.

hub.discover() loads this file on every OS before it looks at "os", so the top imports only the
standard library and movekit; the siblings (settings_api, store, gamecfg, trainer...) load on the
first call through hub.local_import.

The page keeps its form and sends it back whole: apply(game, form) clamps the numbers to the page's
ranges, saves through store.py and writes the autoexec block (gamecfg.py). On Windows the page
hides the offset display and the input service (data-linux): the trainer only plays its sounds there.
"""
import json
import math
import re
import sys
import threading
from pathlib import Path

from movekit import bindnames, games, keys, launchopt
from movekit.hub import local_import

TOOL = "strafe-trainer"
WINDOWS = sys.platform == "win32"
LIMITS = {
    "x": (0, 100), "y": (0, 100), "target": (-5, 5), "size": (10, 120),
    "repeat": (0, 1), "tone_volume": (5, 100), "tickrate": (16, 128),
    **{f"{cue}_{name}": limit for cue in ("wrong", "none", "overlap")
       for name, limit in (("ticks", (1, 20)), ("pitch", (60, 1000)))},
}
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_overlay = None


def _api():
    return local_import(__file__, "settings_api")


def _store():
    return local_import(__file__, "store")


def _gamecfg():
    return local_import(__file__, "gamecfg")


def _trainer():
    return local_import(__file__, "trainer")


def _game_dir(game):
    if game not in _store().GAMES:
        raise ValueError(f"unknown game {game!r}")
    return games.find(game)


def _number(form, name, low=None, high=None):
    """form[name] as a float kept inside the page's range; a blank box is refused."""
    value = form.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} needs a number")
    low, high = LIMITS[name] if low is None else (low, high)
    return float(min(max(value, low), high))


def _color(value, what):
    if not isinstance(value, str) or not COLOR.match(value):
        raise ValueError(f"{what} must be a colour like #00aaff")
    return value.lower()


def _tool_title(key):
    """Another tool's title from its module.json next to this folder, else its key."""
    try:
        return json.loads((Path(__file__).resolve().parent.parent / key / "module.json").read_text())["title"]
    except (OSError, ValueError, KeyError, TypeError):
        return key


# ---------------------------------------------------------------- notes

def offset_key_note(game, offset_key):
    """The note under the offset key."""
    if offset_key:
        other = keys.held_by_others(TOOL, game).get(offset_key.lower())
        if other:
            return {"text": f"⚠ {offset_key} is also {_tool_title(other)}'s key, so it stays theirs. "
                            "Pick another key", "warn": True}
        game_dir = _game_dir(game)
        commands = sorted({c for _, c in _gamecfg().conflicts(game_dir, offset_key)}) if game_dir else []
        if commands:
            return {"text": f"⚠ {offset_key} is bound to {', '.join(commands)} now. Apply replaces that",
                    "warn": True}
    return {"text": "In game, each press shows or hides the offset; Show offset sets how it "
                    "starts. Takes effect from the next game start", "warn": False}


def launch_option(game):
    """The launch options to paste into Steam and the note under them."""
    _game_dir(game)
    return launchopt.offer(game)


# ---------------------------------------------------------------- loading

def _form(cfg, game):
    """The settings in the page's units (percent for position and tone volume)."""
    cues = _store().CUES
    return {
        "enabled": cfg["enabled"], "when_jump": cfg["when_jump"], "when_timer": cfg["when_timer"],
        "show_offset": cfg["show_offset"], "offset_key": cfg["offset_key"],
        "x": round(cfg["x"] * 100, 4), "y": round(cfg["y"] * 100, 4), "size": cfg["size"],
        "colors": dict(cfg["colors"]),
        "repeat": cfg["repeat"], "tone_volume": round(cfg["tone_volume"] * 100, 4), "target": cfg["target"],
        **{key: cfg[key] for cue, switch in cues.items()
           for key in (switch, f"{cue}_sound", f"{cue}_pitch", f"{cue}_ticks")},
        "tickrate": None if game == "momentum" else cfg["tickrate"].get(game, 66),
    }


def _cue_sounds(sound_choices, cfg):
    """Every cue's sound choices: the tone, the game's sounds, and any saved sound this install
    doesn't have."""
    choices = [["tone", "Constant tone"], *sound_choices]
    for cue in _store().CUES:
        if cfg[f"{cue}_sound"] not in [v for v, _ in choices]:
            choices.append([cfg[f"{cue}_sound"], cfg[f"{cue}_sound"]])
    return choices


def load(game=None):
    """Everything the page shows for `game` (None: the last one used)."""
    store = _store()
    installed = [g for g in store.GAMES if games.find(g)]
    if game is None:
        game = store.last_game()
        if game not in installed and installed:
            game = installed[0]
    game_dir = _game_dir(game)
    from movekit import sounds
    found = sounds.available(game_dir, game) if game_dir else sounds.SOUNDS
    cfg = _api().trainer_config(store.saved(game))
    rates = ", ".join(f"{p}* {r}" for p, r in cfg["map_tickrates"].items())
    tickrate_note = (f"From the map: {rates}, others {cfg['tickrate']['momentum']}" if game == "momentum"
                     else f"From the map: {rates}; on other maps the server's tickrate")
    form = _form(cfg, game)
    info = games.GAMES[game]
    short = "CS:S" if game == "css" else info.name
    return {
        "game": game, "version": _trainer().VERSION, "name": info.name,
        "games": [{"id": g, "name": games.GAMES[g].name, "short": "CS:S" if g == "css" else games.GAMES[g].name}
                  for g in installed],
        "found": bool(game_dir),
        "problem": None if game_dir else f"{info.name} not found in your Steam libraries",
        "windows": WINDOWS,
        "steam_note": (f"{short} Properties → Launch Options. movement-kit.exe runs the trainer while "
                       "the game is open." if WINDOWS
                       else f"{short} Properties → Launch Options. movekit-run runs the trainer while "
                            "the game is open."),
        "cue_sounds": _cue_sounds([[s, s] for s in found], cfg),
        "trainer": form, "tickrate_note": tickrate_note,
        "trainer_status": _api().trainer_status(game_dir),
        "offset_note": offset_key_note(game, form["offset_key"]),
        "launch": launch_option(game),
        "limits": {k: list(v) for k, v in LIMITS.items()},
    }


def key_info():
    """For key capture (movekit/web/section.js): code and mouse-button maps, every bind name."""
    return bindnames.capture_info()


def set_game(game):
    """Remember `game` as the last one used; returns load(game)."""
    _game_dir(game)
    _store().set_last_game(game)
    return load(game)


def trainer_status(game):
    return _api().trainer_status(_game_dir(game))


# ---------------------------------------------------------------- sounds and the sample number

def play_cue(game, sound, tone_volume, pitch):
    """One cue's sound: the tone at `pitch` Hz for 0.4 s, or the game sound."""
    if sound != "tone":
        if not sound:
            return True
        game_dir = _game_dir(game)
        from movekit import sounds
        return bool(game_dir and sounds.play(game_dir, sound, game))
    volume = _number({"v": tone_volume}, "v", *LIMITS["tone_volume"]) / 100
    hz = _number({"v": pitch}, "v", *LIMITS["wrong_pitch"])
    trainer = _trainer()
    tone = trainer.platform().Tone(trainer.ToneSynth(volume, {"cue": hz}))
    tone.start()
    tone.mode = "cue"
    for delay, step in ((0.4, lambda: setattr(tone, "mode", None)), (0.6, tone.close)):
        threading.Timer(delay, step).start()
    return True


def show_in_game(on, game, trainer):
    """Shows (or hides) a sample offset in a game started through movekit-run."""
    global _overlay
    if WINDOWS:  # no offset overlay on Windows (the page hides the button)
        return False
    linux = local_import(__file__, "trainer_linux")
    if _overlay is None:
        _overlay = linux.Overlay()
    if not on:
        _overlay.hide()
        return False
    cfg = _value(game, trainer)
    linux.write_atlas(cfg)
    target = cfg["target"]
    _overlay.show(f"{target:+d}" if target else "0", 1, cfg["x"], cfg["y"])
    return True


# ---------------------------------------------------------------- saving

def _value(game, form, saved=None):
    """settings_api.trainer_value over the saved settings, with the numbers kept in range."""
    api, store = _api(), _store()
    if saved is None:
        saved = store.saved(game)
    clean = dict(form)
    cues = store.CUES
    for name in ("x", "y", "size", "repeat", "tone_volume", "target",
                 *[f"{cue}_{n}" for cue in cues for n in ("ticks", "pitch")]):
        clean[name] = _number(form, name)
    clean["tickrate"] = None if game == "momentum" or form.get("tickrate") is None else _number(form, "tickrate")
    clean["colors"] = {k: _color(form["colors"][k], f"the {k} colour") for k in ("early", "perfect", "late")}
    for name in ("enabled", "when_jump", "when_timer", "show_offset", *cues.values()):
        clean[name] = bool(form[name])
    # CS:S has no timer marker, so there only the jump key can turn the trainer on
    if not (clean["when_jump"] or (clean["when_timer"] and game == "momentum")):
        raise ValueError("Pick when the trainer listens: Jump held" + (" or Timer started" if game == "momentum" else ""))
    for cue in cues:
        clean[f"{cue}_sound"] = form.get(f"{cue}_sound") or "tone"
    clean["offset_key"] = form.get("offset_key") or ""
    if clean["offset_key"] and clean["offset_key"].lower() not in bindnames.VALID:
        raise ValueError(f"{clean['offset_key']} isn't a key the game can bind")
    return api.trainer_value(api.trainer_config(saved), clean, game)


def apply(game, form):
    """Saves the page's form and writes the autoexec block. saved False: `messages` says why."""
    game_dir = _game_dir(game)
    try:
        cfg = _value(game, form)
    except (KeyError, ValueError) as e:
        return {"saved": False, "messages": [str(e).strip("'")]}
    try:
        _store().save(game, cfg)
        _gamecfg().apply(game, cfg, game_dir)
    except OSError as e:
        return {"saved": False, "messages": [f"Not saved: {e.strerror}"]}
    if not game_dir:
        return {"saved": True, "messages": [(f"Saved. {games.GAMES[game].name} wasn't found, so its autoexec.cfg "
                                            "gets the trainer's lines at the next game start")]}
    return {"saved": True, "messages": ["Saved. Game already open? Run: exec autoexec"]}


SECTION = {
    "key": TOOL,
    "title": "Strafe Trainer",
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {
        "load": load, "keys": key_info, "set_game": set_game, "offset_key_note": offset_key_note,
        "trainer_status": trainer_status, "play_cue": play_cue, "show_in_game": show_in_game,
        "launch_option": launch_option, "apply": apply,
    },
    "order": 35,
}
