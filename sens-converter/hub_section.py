"""Sens Converter's hub section (movekit/hub.py): the sensitivity that keeps your horizontal mouse
speed (cm/360) when DPI or m_yaw changes, and Apply, which sets it and m_yaw in Momentum Mod.

The turn per mouse count is sensitivity * m_yaw degrees, so the same cm/360 at another DPI and
m_yaw takes new_sens = old_sens * old_dpi * old_m_yaw / (new_dpi * new_m_yaw). m_pitch is left
alone, so vertical speed follows DPI and sens on purpose.

Apply, with the game closed, rewrites the sensitivity and m_yaw lines of Momentum's cfg/config.cfg
(the game reads it at start and writes it back when it quits, so an edit made while it runs would
be lost). With the game open and started through the kit with Source Yaw installed, it sends the
values through the game's net console instead (sourceyaw/netcon.py, loaded from Source Yaw's
folder, so this module needs nothing from Source Yaw otherwise). Open any other way, Apply changes
nothing and gives the console line to type.

hub.discover() loads this file on every OS before it looks at "os", so it imports only the
standard library and movekit.
"""
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from movekit import cfgblock, games, paths
from movekit.files import write_atomic
from movekit.hub import local_import

VERSION = "1.0.0"  # bump in the same commit as the sens-converter-v* tag

GAME = "momentum"
BACKUP = ".bak-sens-converter"  # config.cfg's copy from before the first Apply
DIGITS = 6  # decimals written for sensitivity
CVAR = re.compile(r'^\s*(sensitivity|m_yaw)\s+"?([^"\s]*)"?', re.IGNORECASE)
SOURCEYAW = Path(__file__).resolve().parent.parent / "sourceyaw"  # a sibling module at the kit root
# the page's boxes kept between starts; the other two (old sens, new m_yaw) open on the game's values
FIELDS = ("old_dpi", "old_m_yaw", "new_dpi")


def inputs_file():
    """The page's last box values (module.json's "config:sens-converter")."""
    return paths.config_dir("sens-converter") / "inputs.json"


def read_inputs():
    """{field: text} saved by save(); fields never saved are left out."""
    try:
        saved = json.loads(inputs_file().read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(saved, dict):
        return {}
    return {k: v for k, v in saved.items() if k in FIELDS and isinstance(v, str) and len(v) <= 32}


def new_sens(old_dpi, old_sens, old_m_yaw, new_dpi, new_m_yaw):
    """The sensitivity that turns the same angle per inch at new_dpi and new_m_yaw."""
    return old_sens * old_dpi * old_m_yaw / (new_dpi * new_m_yaw)


def cm_per_360(dpi, sens, m_yaw):
    return 360 / (dpi * sens * m_yaw) * 2.54


def fmt(value, digits=DIGITS):
    """A cvar value: up to `digits` decimals, no trailing zeros."""
    text = f"{value:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _config(game_dir=None):
    game_dir = game_dir if game_dir is not None else games.find(GAME)
    return Path(game_dir) / "cfg" / "config.cfg" if game_dir else None


def read_mouse(cfg):
    """{sensitivity, m_yaw} as floats from a config.cfg; a missing or broken value is left out."""
    found = {}
    try:
        lines, _ = cfgblock.read_cfg(cfg)
    except OSError:
        return found
    for line in lines:
        m = CVAR.match(line)
        if m:
            try:
                value = float(m.group(2))
            except ValueError:
                continue
            if math.isfinite(value) and value > 0:
                found[m.group(1).lower()] = value
    return found


def write_mouse(cfg, values):
    """Set each cvar in values ({name: text}) in config.cfg: its line is replaced where it stands
    (a second line for it is dropped), a missing one goes at the end. Keeps the file's line endings
    and a copy of it from before the first change."""
    lines, nl = cfgblock.read_cfg(cfg)
    out, done = [], set()
    for line in lines:
        m = CVAR.match(line)
        name = m.group(1).lower() if m else None
        if name in values:
            if name not in done:
                out.append(f'{name} "{values[name]}"{nl}')
                done.add(name)
            continue
        out.append(line)
    if out and not out[-1].endswith(("\n", "\r")):
        out[-1] += nl
    out += [f'{name} "{text}"{nl}' for name, text in values.items() if name not in done]
    text = "".join(out)
    if text != "".join(lines):
        cfgblock._backup(cfg, (BACKUP,))
        write_atomic(cfg, text)


def game_running():
    """Whether Momentum runs on this PC, by process name."""
    if sys.platform == "win32":
        try:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq momentum.exe", "/NH"], capture_output=True,
                                 text=True, timeout=5, check=False,
                                 creationflags=0x08000000).stdout  # CREATE_NO_WINDOW
        except (OSError, subprocess.SubprocessError):
            return False
        return "momentum.exe" in out.lower()
    for proc in Path("/proc").iterdir():
        try:
            if proc.name.isdigit() and (proc / "comm").read_text().strip() == games.MOMENTUM.process:
                return True
        except OSError:
            continue
    return False


def _netcon():
    """Source Yaw's netcon.py and its settings folder, or None when Source Yaw isn't here."""
    if not (SOURCEYAW / "netcon.py").exists():
        return None
    try:
        return local_import(SOURCEYAW / "hub_section.py", "netcon"), paths.config_dir("sourceyaw")
    except Exception:  # noqa: BLE001 - an old or broken Source Yaw only costs the live apply
        return None


def load():
    """What the page shows: the game's current sensitivity and m_yaw, or why there are none."""
    cfg = _config()
    if not cfg:
        return {"version": VERSION, "current": {}, "inputs": read_inputs(),
                "problem": "Momentum Mod not found in your Steam libraries"}
    return {"version": VERSION, "current": read_mouse(cfg), "inputs": read_inputs(), "problem": None}


def save(form):
    """Keep the boxes' text ({field: text}) for the next time the page opens."""
    values = {k: str(form.get(k, ""))[:32] for k in FIELDS}
    path = inputs_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, json.dumps(values, indent=1) + "\n")
    return True


def _number(form, name, what):
    try:
        value = float(str(form.get(name, "")).replace(",", "."))
    except ValueError:
        raise ValueError(f"{what}: type a number") from None
    if not (math.isfinite(value) and value > 0):
        raise ValueError(f"{what}: must be more than 0")
    return value


def apply(form):
    """Set the bottom row's sensitivity (new_sens) and m_yaw in Momentum. Without new_sens, it is
    worked out from the top row (old_dpi, old_sens, old_m_yaw) and new_dpi. Returns {saved, sens,
    m_yaw, messages}."""
    try:
        new_dpi, new_m_yaw = _number(form, "new_dpi", "New DPI"), _number(form, "new_m_yaw", "New m_yaw")
        if str(form.get("new_sens", "")).strip():
            sens = _number(form, "new_sens", "New sensitivity")
        else:
            old_dpi, old_sens = _number(form, "old_dpi", "Old DPI"), _number(form, "old_sens", "Old sensitivity")
            old_m_yaw = _number(form, "old_m_yaw", "Old m_yaw")
            sens = new_sens(old_dpi, old_sens, old_m_yaw, new_dpi, new_m_yaw)
    except ValueError as e:
        return {"saved": False, "messages": [str(e)]}
    values = {"sensitivity": fmt(sens), "m_yaw": fmt(new_m_yaw, 8)}
    result = {"sens": values["sensitivity"], "m_yaw": values["m_yaw"]}
    command = "; ".join(f"{k} {v}" for k, v in values.items())
    dpi_note = f"Set {fmt(new_dpi, 0)} DPI on your mouse, and in Momentum's mouse settings for its cm/360."

    if game_running():
        net = _netcon()
        if net and net[0].is_open(GAME, net[1]) and net[0].send(GAME, f"{command}; host_writeconfig", net[1]):
            return {**result, "saved": True, "messages": ["Set in the open game", dpi_note]}
        return {**result, "saved": False, "messages": [
            ("Momentum is open, so config.cfg can't be changed now (the game writes it back when it quits). "
             "Close it and press Apply again, or type this in its console:"), command]}

    cfg = _config()
    if not cfg:
        return {**result, "saved": False, "messages": ["Momentum Mod not found in your Steam libraries"]}
    try:
        write_mouse(cfg, values)
    except OSError as e:
        return {**result, "saved": False, "messages": [f"Not saved: {e.strerror}"]}
    return {**result, "saved": True, "messages": ["Saved to config.cfg: the game uses it from its next start",
                                                   dpi_note]}


SECTION = {
    "key": "sens-converter",
    "title": "Sens Converter",
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {"load": load, "apply": apply, "save": save},
    "order": 35,
}
