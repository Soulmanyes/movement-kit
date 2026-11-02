#!/usr/bin/env python3
"""Installs Strafe Review into Momentum Mod, or takes it out again.

Usage: install.py [--game DIR] [--uninstall]

- Copies the recorder (recorder/panorama) into the game's custom/0-strafe-review folder, with a
  layout/hud/timer.xml that loads it: a copy of the timer.xml the game would use otherwise (another
  HUD mod's in custom/, else the game's own) with one more script include. The game mounts custom/
  folders in alphabetical order and the first file found wins, so the folder name sorts first.
  Type panorama_reload in game after updating it.
- Writes a block between "// movekit:strafe-review begin" and "end" into cfg/autoexec.cfg (replacing
  the older "// strafe-review begin" block where it stands): con_logfile yaw.log (the log the collector reads), and
  engine_no_focus_sleep 0, so replays watched while tabbed out record every tick. The first install
  keeps the original as autoexec.cfg.bak-strafe-review. Restart the game after installing.
- On Linux, links collector/strafe-review-run into ~/.local/bin for the Steam launch options.

The game folder comes from MOMENTUM_DIR or Steam's library folders, or --game.
--uninstall removes the recorder, the autoexec block and the link.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "collector"))
import steam  # found through the path above; it also puts movekit on the path

from movekit import cfgblock, vpk
from movekit.files import write_atomic

TOOL = "strafe-review"  # the autoexec block's name: // movekit:strafe-review begin ... end
# yaw.log is the name Source Yaw's yaws.cfg uses too; only one con_logfile is active, so both tools share it
BODY = ["con_logfile yaw.log", "engine_no_focus_sleep 0"]
OLD_MARKERS = ("// strafe-review begin", "// strafe-review end")  # before 2026-11-02; replaced in place
LINK = Path.home() / ".local" / "bin" / "strafe-review-run"
FOLDER = "0-strafe-review"  # in custom/; sorts before other mods, so our timer.xml is the one loaded
OLD_FOLDERS = ["strafe-review"]  # before 2026-10-28; removed on install
TIMER = Path("panorama") / "layout" / "hud" / "timer.xml"
INCLUDE = '<include type="module" src="file://{scripts}/hud/strafe-review.ts" />'
RECORDER = Path("panorama") / "scripts" / "hud" / "strafe-review.ts"
SETTINGS = steam.data_dir() / "settings.json"  # {"inGameLine": bool}, set on the review page
SHOW_LINE = re.compile(r"^const SHOW_LINE = (true|false);", re.MULTILINE)


def settings():
    try:
        got = json.loads(SETTINGS.read_text())
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def save_setting(key, value):
    got = settings()
    got[key] = value
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(SETTINGS, json.dumps(got, indent=2) + "\n")


def apply_settings(game):
    """Write the page's settings into the installed recorder; panorama_reload or a game restart applies them.
    Returns False when the recorder isn't installed."""
    ts = Path(game) / "custom" / FOLDER / RECORDER
    try:
        text = ts.read_text(encoding="utf-8")
    except OSError:
        return False
    show = "true" if settings().get("inGameLine") else "false"
    write_atomic(ts, SHOW_LINE.sub(f"const SHOW_LINE = {show};", text))
    return True


def set_autoexec(game, add):
    autoexec = Path(game) / "cfg" / "autoexec.cfg"
    def old_block(lines):
        return cfgblock.spans(lines, *OLD_MARKERS)

    if not cfgblock.set_block(autoexec, TOOL, BODY, add, ".bak-strafe-review", legacy=old_block):
        return
    print(f"{'updated' if add else 'removed the strafe-review block from'} {autoexec}")


def base_timer(game):
    """The timer.xml the game would load without us: the first custom/ folder in mount order that has
    one, else the game's own. A VPK with one in front of it can't be copied from; that gets a warning."""
    custom = Path(game) / "custom"
    ours = {FOLDER.lower(), *(f.lower() for f in OLD_FOLDERS)}
    entries = sorted(custom.iterdir(), key=lambda p: p.name.lower()) if custom.is_dir() else []
    for entry in entries:
        if entry.name.lower() in ours:
            continue
        if entry.is_dir() and (entry / TIMER).is_file():
            return entry / TIMER
        if entry.suffix.lower() == ".vpk" and TIMER.as_posix().lower() in vpk.files(entry):
            print(f"warning: {entry} has its own timer.xml, which ours replaces; that mod's timer may look "
                  "different", file=sys.stderr)
    return Path(game) / TIMER


def timer_with_recorder(text):
    """timer.xml text with our script included next to the others."""
    if "strafe-review.ts" in text:
        return text
    m = re.search(r"^([ \t]*)</scripts>", text, re.MULTILINE)
    if not m:
        raise ValueError("no </scripts> in timer.xml")
    indent = m.group(1) + ("\t" if "\t" in m.group(1) or not m.group(1) else "    ")
    nl = "\r\n" if "\r\n" in text else "\n"
    return text[:m.start()] + indent + INCLUDE + nl + text[m.start():]


def link_launcher(add):
    """Linux only: the Steam launch option wrapper, run from the repo (so keep the repo where it is)."""
    if sys.platform == "win32" or getattr(sys, "frozen", False):
        return
    if add:
        LINK.parent.mkdir(parents=True, exist_ok=True)
        if LINK.is_symlink() or LINK.exists():
            LINK.unlink()
        LINK.symlink_to(ROOT / "collector" / "strafe-review-run")
        print(f"linked {LINK}; Steam launch options: strafe-review-run %command%")
    elif LINK.is_symlink():
        LINK.unlink()
        print(f"removed {LINK}; take strafe-review-run out of the launch options too")


def install(game):
    for old in OLD_FOLDERS:
        shutil.rmtree(Path(game) / "custom" / old, ignore_errors=True)
    base = base_timer(game)
    text = timer_with_recorder(base.read_text(encoding="utf-8", errors="surrogateescape"))
    dest = Path(game) / "custom" / FOLDER
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(ROOT / "recorder" / "panorama", dest / "panorama")
    (dest / TIMER).parent.mkdir(parents=True, exist_ok=True)
    (dest / TIMER).write_text(text, encoding="utf-8", errors="surrogateescape", newline="")
    apply_settings(game)
    print(f"installed to {dest} (timer.xml based on {base})")
    set_autoexec(game, add=True)
    link_launcher(add=True)


def uninstall(game):
    for name in (FOLDER, *OLD_FOLDERS):
        dest = Path(game) / "custom" / name
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
            print(f"removed {dest}")
    set_autoexec(game, add=False)
    link_launcher(add=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", default=steam.find_game(), help="Momentum's game folder (holds cfg/ and custom/)")
    ap.add_argument("--uninstall", action="store_true", help="take Strafe Review out again")
    args = ap.parse_args()
    if not args.game or not (Path(args.game) / "cfg").is_dir():
        sys.exit("Momentum Mod not found in any Steam library; pass --game with its momentum folder")
    (uninstall if args.uninstall else install)(args.game)


if __name__ == "__main__":
    main()
