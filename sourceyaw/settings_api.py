"""Source Yaw's settings logic without a window: what its settings show and save, as plain data.

Written in 3.5 so the GTK window and the hub's Source Yaw section (Phase 3.6) shared one copy; the
GTK window retired in 3.8, and the hub section is the one caller left. Everything here takes and
returns JSON-able data (tuples come back as lists over the hub bridge). Text comes back raw, and
the page puts it in as text.

Siblings: with sourceyaw/ on sys.path (yawcore's CLI, the checks) they're imported by name, the same
modules the caller uses. The hub doesn't (tool folders share file names, see movekit/hub.py), so
there this file loads them by path under hub.local_import's names. trainer.py needs `import yawcore`
to work, so yawcore sits in sys.modules under that name only while trainer loads. Either way there
is one module object per file. trainer is Linux-only (fcntl, the input service), so it loads on
first use: setup_problem, base_options and collect work without it.
"""
import importlib.util
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _on_path():
    """True when sourceyaw/ is on sys.path (yawcore's CLI, the checks), so siblings go by plain name."""
    return any(Path(p or ".").resolve() == HERE for p in sys.path)


def _sibling(name, module_name):
    """sourceyaw/<name>.py, as the same module object the rest of the process uses."""
    if _on_path():
        return importlib.import_module(name)
    path = HERE / f"{name}.py"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules[module_name]
        raise
    return mod


# hub.local_import's names (movekit/hub.py _module_name), so a section that also asks local_import
# for yawcore gets this same module; written out here so this file doesn't import the hub
_PREFIX = "movekit_section_" + re.sub(r"\W", "_", HERE.name) + "."
core = _sibling("yawcore", _PREFIX + "yawcore")
_trainer = None


def _trainer_module():
    global _trainer
    if _trainer is None:
        bare = "yawcore" not in sys.modules
        if bare:
            sys.modules["yawcore"] = core  # for trainer.py's own `import yawcore`
        try:
            _trainer = _sibling("trainer", _PREFIX + "trainer")
        finally:
            if bare:
                sys.modules.pop("yawcore", None)
    return _trainer


# ---------------------------------------------------------------- setup

def setup_problem(game, cstrike):
    """Why Apply can't work for `game` (its mod folder `cstrike`, or None), or None if it can."""
    if not cstrike and core.flatpak_steam_only(game):
        return ("Flatpak Steam isn't supported: movekit-run can't run inside "
                "its sandbox. Use Steam from your distro's packages")
    if not cstrike:
        return f"{core.GAMES[game]['name']} not found in your Steam libraries"
    return None


# ---------------------------------------------------------------- crosshair

def base_options(base_choice):
    """[(value, label)] for the crosshair base picker; base_choice is the saved "base"."""
    options = []
    cm = core.crosshair_maker_png()
    if cm:
        options.append(("crosshair-maker", f"crosshair-maker: {cm.stem}"))
    options.append(("builtin", "Plain cross"))
    if base_choice not in ("crosshair-maker", "builtin"):
        options.append((base_choice, os.path.basename(base_choice)))
    options.append(("pick", "Choose an image…"))
    return options


# ---------------------------------------------------------------- strafe trainer

def trainer_config(saved):
    """The trainer settings the window starts from: the saved "trainer" dict over the defaults.
    Unlike trainer.settings(), this also merges "tickrate" per game. Settings saved before each cue
    had its own sound come through trainer.migrate."""
    trainer = _trainer_module()
    defaults = trainer.TRAINER_DEFAULTS
    saved = trainer.migrate(saved)
    cfg = {**defaults, **saved}
    cfg["colors"] = {**defaults["colors"], **saved.get("colors", {})}
    cfg["tickrate"] = {**defaults["tickrate"], **saved.get("tickrate", {})}
    return cfg


def trainer_value(cfg, form, game):
    """The trainer dict to save: `cfg` (from trainer_config) with the form's values on top.

    `form` holds what the window shows, in its units: enabled, show_offset, offset_key,
    x and y (percent), size, colors {early, perfect, late}, repeat, tone_volume (percent), target,
    tickrate (ticks per second for `game`, or None where the map sets it, as on Momentum), and per
    cue (trainer.CUES) its switch plus <cue>_sound, <cue>_pitch and <cue>_ticks.
    The other-key cue's sound and pitch are also saved as the old shared `sound` and `tone_pitch`,
    so a rolled-back Source Yaw (1.9.0 or older) still reads them."""
    cues = _trainer_module().CUES
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
    for cue, switch in cues.items():
        cfg[switch] = form[switch]
        cfg[f"{cue}_sound"] = form[f"{cue}_sound"]
        cfg[f"{cue}_pitch"] = int(form[f"{cue}_pitch"])
        cfg[f"{cue}_ticks"] = int(form[f"{cue}_ticks"])
    cfg["sound"], cfg["tone_pitch"] = cfg["wrong_sound"], cfg["wrong_pitch"]
    if form.get("tickrate") is not None:
        cfg["tickrate"] = {**cfg["tickrate"], game: int(form["tickrate"])}
    return cfg


def inputd_command():
    """The command that installs the trainer's input service."""
    return f"sudo sh {core.HERE / 'inputd/install-inputd.sh'}"


def trainer_status(cstrike):
    """What the trainer group shows around its controls, for the game's mod folder `cstrike`
    (or None):
      installed     the input service is installed
      service       note under "Input service"
      command       the install command, to copy
      binds         note under "Keys", or None without a game folder"""
    trainer = _trainer_module()
    if core.WINDOWS:
        # Raw Input: no service to install, and every key with an evdev twin reaches the trainer
        binds = None
        if cstrike:
            _, unseen = trainer.read_binds(cstrike, None)
            binds = ("⚠ Source Yaw can't read these keys on Windows: " + ", ".join(unseen) if unseen
                     else "Strafe, turn and jump keys come from your binds in the game")
        return {"installed": True, "service": "", "command": "", "binds": binds}
    installed = trainer.forwarded() is not None
    if installed:
        service = "Installed: forwards only the keys in /etc/sourceyaw-inputd.conf"
    else:
        service = ("Not installed. It reads your keyboard as root and passes on only the "
                   "trainer's keys. Run in a terminal: " + inputd_command())
    binds = None
    if cstrike:
        _, unseen = trainer.read_binds(cstrike)
        binds = ("⚠ Not forwarded by the input service: " + ", ".join(unseen)
                 + ". Add them to /etc/sourceyaw-inputd.conf" if unseen
                 else "Strafe, turn and jump keys come from your binds in the game")
    return {"installed": installed, "service": service, "command": inputd_command(),
            "binds": binds}


# ---------------------------------------------------------------- saving

def collect(key, crosshair, start, base, original_color, trainer, entries,
            surf=None, mode_key="", auto_mode=True, map_modes=None, separate=False, active="bhop"):
    """The settings dict that yawcore.validate checks and yawcore.apply writes.
    `start` is the index of the yawspeed a game starts on, `entries` the yawspeeds in order (the
    bhop list). `surf` is the saved surf list {entries, start}, or None. With `separate` both lists
    are in game; without it only the `active` one ("bhop" or "surf"), and the other stays saved."""
    data = {"key": key, "crosshair": crosshair, "start": start,
            "base": base,
            # Momentum: the user's own crosshair colour, put back when colours are off
            "original_color": original_color,
            "trainer": trainer,
            "entries": entries,
            "mode_key": mode_key, "auto_mode": auto_mode,
            "separate": separate, "active": active if active in ("bhop", "surf") else "bhop",
            "map_modes": dict(map_modes or {"bhop_": "bhop", "surf_": "surf"})}
    if surf is not None:
        data["surf"] = surf
    return data
