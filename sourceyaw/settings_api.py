"""Source Yaw's settings logic without a window: what its settings show and save, as plain data.

Written in 3.5 so the GTK window and the hub's Source Yaw section (Phase 3.6) shared one copy; the
GTK window retired in 3.8, and the hub section is the one caller left. Everything here takes and
returns JSON-able data (tuples come back as lists over the hub bridge). Text comes back raw, and
the page puts it in as text.

Siblings: with sourceyaw/ on sys.path (yawcore's CLI, the checks) they're imported by name, the same
modules the caller uses. The hub doesn't (tool folders share file names, see movekit/hub.py), so
there this file loads them by path under hub.local_import's names. Either way there is one module
object per file. The strafe trainer's settings moved to its own module in Phase 13 (strafe-trainer/).
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


# ---------------------------------------------------------------- saving

def collect(key, crosshair, start, base, original_color, trainer, entries,
            surf=None, mode_key="", auto_mode=True, map_modes=None, separate=False, active="bhop",
            load_switch=True, load_sound=True):
    """The settings dict that yawcore.validate checks and yawcore.apply writes. `trainer` is the
    saved "trainer" dict, kept as it was (None: none): the Strafe Trainer has its own settings since
    Phase 13, and a Source Yaw rolled back to 1.10 still reads this one.
    `start` is the index of the yawspeed a game starts on, `entries` the yawspeeds in order (the
    bhop list). `surf` is the saved surf list {entries, start}, or None. With `separate` both lists
    are in game; without it only the `active` one ("bhop" or "surf"), and the other stays saved.
    `load_switch`: with auto on, switch lists as a map loads where the game runs gamemode cfgs
    (Momentum), else on the next press; `load_sound`: play the start yawspeed's sound then."""
    data = {"key": key, "crosshair": crosshair, "start": start,
            "base": base,
            # Momentum: the user's own crosshair colour, put back when colours are off
            "original_color": original_color,
            "entries": entries,
            "mode_key": mode_key, "auto_mode": auto_mode,
            "load_switch": load_switch, "load_sound": load_sound,
            "separate": separate, "active": active if active in ("bhop", "surf") else "bhop",
            "map_modes": dict(map_modes or {"bhop_": "bhop", "surf_": "surf"})}
    if surf is not None:
        data["surf"] = surf
    if trainer is not None:
        data["trainer"] = trainer
    return data
