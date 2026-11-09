"""The Strafe Trainer's settings logic without a window (moved out of Source Yaw's settings_api in
Phase 13): what the section shows and saves, as plain JSON-able data.

Siblings load through movekit.hub.local_import (see trainer.py). trainer_linux loads only on Linux,
on first use.
"""
import sys
from pathlib import Path

from movekit.hub import local_import

store = local_import(__file__, "store")
WINDOWS = sys.platform == "win32"


def _trainer():
    return local_import(__file__, "trainer")


def trainer_config(saved):
    """The settings the page starts from: `saved` (a stored dict, maybe from before each cue had its
    own sound) over the defaults, with colours and per-game tickrates merged."""
    defaults = store.DEFAULTS
    saved = store.migrate(saved)
    cfg = {**defaults, **saved}
    cfg["colors"] = {**defaults["colors"], **saved.get("colors", {})}
    cfg["tickrate"] = {**defaults["tickrate"], **saved.get("tickrate", {})}
    return cfg


def trainer_value(cfg, form, game):
    """The dict to save: `cfg` (from trainer_config) with the form's values on top.

    `form` holds what the page shows, in its units: enabled, show_offset, offset_key,
    x and y (percent), size, colors {early, perfect, late}, repeat, tone_volume (percent), target,
    tickrate (ticks per second for `game`, or None where the map sets it, as on Momentum), and per
    cue (store.CUES) its switch plus <cue>_sound, <cue>_pitch and <cue>_ticks.
    The other-key cue's sound and pitch are also saved as the old shared `sound` and `tone_pitch`,
    which the Source Yaw versions that had the trainer (1.9.0 and older) read."""
    cfg = dict(cfg)
    cfg.update({
        "enabled": form["enabled"],
        "show_offset": form["show_offset"],
        "offset_key": form["offset_key"],
        "x": round(form["x"] / 100, 3),
        "y": round(form["y"] / 100, 3),
        "size": int(form["size"]),
        "colors": dict(form["colors"]),
        "repeat": round(form["repeat"], 2),
        "tone_volume": round(form["tone_volume"] / 100, 2),
        "target": int(form["target"]),
    })
    for cue, switch in store.CUES.items():
        cfg[switch] = form[switch]
        cfg[f"{cue}_sound"] = form[f"{cue}_sound"]
        cfg[f"{cue}_pitch"] = int(form[f"{cue}_pitch"])
        cfg[f"{cue}_ticks"] = int(form[f"{cue}_ticks"])
    cfg["sound"], cfg["tone_pitch"] = cfg["wrong_sound"], cfg["wrong_pitch"]
    if form.get("tickrate") is not None:
        cfg["tickrate"] = {**cfg["tickrate"], game: int(form["tickrate"])}
    return cfg


def inputd_command(here=None):
    """The command that installs the input service (from this module's folder)."""
    here = Path(here) if here else Path(__file__).resolve().parent
    return f"sudo sh {here / 'inputd/install-inputd.sh'}"


def trainer_status(game_dir):
    """What the trainer card shows around its controls, for the game's mod folder (or None):
      installed     the input service is installed
      service       note under "Input service"
      command       the install command, to copy
      binds         note under "Keys", or None without a game folder"""
    trainer = _trainer()
    if WINDOWS:
        # Raw Input: no service to install, and every key with an evdev twin reaches the trainer
        binds = None
        if game_dir:
            _, unseen = trainer.read_binds(game_dir, None)
            binds = ("⚠ The Strafe Trainer can't read these keys on Windows: " + ", ".join(unseen) if unseen
                     else "Strafe, turn and jump keys come from your binds in the game")
        return {"installed": True, "service": "", "command": "", "binds": binds}
    installed = trainer.forwarded() is not None
    if installed:
        service = "Installed: forwards only the keys in /etc/sourceyaw-inputd.conf"
    else:
        service = ("Not installed. It reads your keyboard as root and passes on only the "
                   "trainer's keys. Run in a terminal: " + inputd_command())
    binds = None
    if game_dir:
        _, unseen = trainer.read_binds(game_dir)
        binds = ("⚠ Not forwarded by the input service: " + ", ".join(unseen)
                 + ". Add them to /etc/sourceyaw-inputd.conf" if unseen
                 else "Strafe, turn and jump keys come from your binds in the game")
    return {"installed": installed, "service": service, "command": inputd_command(), "binds": binds}
