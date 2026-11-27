#!/usr/bin/env python3
"""Installs Paint Saver into Momentum Mod, or takes it out again.

Usage: install.py [--game DIR] [--launch] [--uninstall]

Momentum can't keep paint through a map reload. Paint Saver records where you paint and paints it again.
Two switches on its hub page (settings.json, read_settings) decide what this install puts in, both off at
first: saving (record paint and bind the paint keys to the alias that does it; off binds them back to
+paint) and loading while saving is off (with saving on, loading always works). They take effect at the
next game start, the one that runs the launch hook.
- The HUD script (panorama/scripts/hud/movekit-paint-saver.ts) logs each stroke's position and aim to
  yaw.log while the paint key is held. `mk_savepaint` in the console saves every stroke painted on the
  current map this session; `mk_clearpaint` drops the map's saved paint.
- At the next game start (--launch, from the launch hook, while the game is still closed) paintlog.py
  reads the new part of yaw.log into paint.json (paths.data_dir("paint-saver")), and savedlocs.py writes
  each map's saved paint into momentum/savedlocs.txt as a savestate block of its own, zzpaint_<map>.
  The game reads that file only at launch, which is why saved paint comes back after a restart.
- `mk_loadpaint` on a map with saved paint: the script imports that block, paints at each entry,
  deletes the imported entries again (the player's own savestates stay as they were) and restarts the
  track. Hands off the mouse meanwhile: it moves the marks.
- Paint drawn in noclip near or inside a wall or clip brush can come back off the first time: going to a
  savestate turns noclip off, and a savestate written inside a brush lifts the player less (owner,
  2026-11-27). The replay logs where each point put the player, and the next game start writes the
  missed points higher or lower, or moves them back along their aim, which paints the same mark from a
  spot the body fits (paintlog.py).

This install also:
- copies the script into custom/movekit-paint-saver, with the replay plan (per map: each stroke's colour,
  size and entry count) written into it, and hands the kit (movekit/panorama.py) the script's include in
  layout/hud/timer.xml. Type panorama_reload in game after installing.
- writes a `// movekit:paint-saver` block into cfg/autoexec.cfg: the console log (con_logfile yaw.log),
  MK_ markers hidden in the console, the aliases (+mkpaint sets the hostname cvar the script watches, as
  Panorama can't see the paint key) and a bind of every key bound to +paint in config.cfg to +mkpaint.
- on Linux, registers launch-hook.sh with movekit-run (movekit/launch.py). On Windows the kit's core runs
  module_hooks.launch instead.

--uninstall takes the patch, script, autoexec block and launch hook out, binds those keys back to +paint
in config.cfg and removes the zzpaint_ blocks from savedlocs.txt; paint.json stays (the hub's "Also
delete saved data" removes it). Do it with the game closed: the game writes both files again on exit.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False) and (ROOT.parent / "movekit").is_dir() and str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))  # the kit root (repo or core copy); the core exe bundles movekit
from movekit import (  # after the path above
    binds,
    cfgblock,
    games,
    keys,
    panorama,
    paths,
    steam,
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # paintlog, savedlocs
import paintlog  # after the path above
import savedlocs  # after the path above

VERSION = "1.0.0"  # Paint Saver's (module.json reads it); bump in the same commit as the release tag
TOOL = "paint-saver"
FOLDER = "movekit-paint-saver"
HOOK_ORDER = 100  # after the HUD modules (JHUD 40 .. Surf Sound 90); only syncs the kit
TS = "panorama/scripts/hud/movekit-paint-saver.ts"
PLAN_MARK = "/*MK_PLAN*/ {}"
STUCK_MARK = "/*MK_STUCK*/ {}"
BACKUP = ".bak-paint-saver"
PAINT, OURS = "+paint", "+mkpaint"
PATCHES = [  # for movekit/panorama.py
    {"file": "panorama/layout/hud/timer.xml", "before": "</scripts>",
     "line": '<include type="module" src="file://{scripts}/hud/movekit-paint-saver.ts" />'},
]


OFF_SAVE = "Paint Saver: saving paint is off. Turn it on in Movement Kit's Paint Saver page"
OFF_LOAD = "Paint Saver: loading paint is off while saving is. Turn either on in Movement Kit's Paint Saver page"


def block(paint_keys, save=True, load=True):
    """The autoexec block. save off: the paint keys aren't bound here and +mkpaint only paints (a bind
    the game kept in config.cfg still works until the next start unbinds it), and mk_savepaint says it's
    off. mk_clearpaint always works. No ";" in an echo: the alias would split there."""
    lines = ["// Paint Saver reads its markers and getpos answers from yaw.log", "con_logfile yaw.log",
             "// the kit's MK_ markers stay out of the console; yaw.log still gets them",
             "con_filter_enable 1", "con_filter_text_out MK_"]
    if save:
        lines += ["// the paint key, seen by the HUD script through the hostname cvar",
                  'alias +mkpaint "+paint; hostname mkpaint1"', 'alias -mkpaint "-paint; hostname mkpaint0"',
                  'alias mk_savepaint "hostname mkpaintsave"']
    else:
        lines += ["// saving is off (the hub's Paint Saver page)", f'alias +mkpaint "{PAINT}"',
                  'alias -mkpaint "-paint"', f'alias mk_savepaint "echo {OFF_SAVE}"']
    lines += ['alias mk_clearpaint "hostname mkpaintclear"',
              'alias mk_loadpaint "hostname mkpaintrestore"' if load else f'alias mk_loadpaint "echo {OFF_LOAD}"']
    if save:
        lines += [f'bind "{k}" "{OURS}"' for k in paint_keys]
    return lines


def settings_file():
    """The hub page's switches (module.json's "config:paint-saver")."""
    return paths.config_dir(TOOL) / "settings.json"


def read_settings():
    """{"save": bool, "load_off": bool}, both off until set. save: record paint and bind the paint keys
    for it; load_off: mk_loadpaint works while save is off (with save on it always does)."""
    out = {"save": False, "load_off": False}
    try:
        saved = json.loads(settings_file().read_text())
    except (OSError, ValueError):
        return out
    if isinstance(saved, dict):
        out.update({k: saved[k] for k in out if isinstance(saved.get(k), bool)})
    return out


def write_settings(s):
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"save": bool(s["save"]), "load_off": bool(s["load_off"])}) + "\n")
    tmp.replace(path)


def game_running():
    """Whether Momentum runs on this PC, by process name (as Sens Converter checks it)."""
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


def find_game():
    """Momentum's game folder as a Path, or None when it isn't there."""
    game = steam.game_dir(games.MOMENTUM)
    return game if game and (game / "cfg").is_dir() else None


def data_file():
    return paths.data_dir(TOOL) / "paint.json"


def report(result):
    for w in result["warnings"]:
        print(f"warning: {w}", file=sys.stderr)
    skipped = [r for r in result["patches"] if r["state"] == "skipped"]
    for row in skipped:
        print(f"warning: {row['tool']}'s patch to {row['file']} is left out ({row['reason']})", file=sys.stderr)
    return [r for r in skipped if r["tool"] == TOOL]


def paint_keys(game):
    """Keys config.cfg binds to +paint, or to +mkpaint (written by the game after an earlier install)."""
    text = binds.cfg_text(game / "cfg" / "config.cfg")
    found = binds.keys_bound_to(text, PAINT) + binds.keys_bound_to(text, OURS)
    return sorted(set(found), key=str.lower)


def update_paint(game, launch, quiet, load=True):
    """The replay plan for the HUD script. paint.json is read and updated from yaw.log (only at launch, or a
    first bookmark), and savedlocs.txt rewritten from it (only at launch, with the game closed). The plan
    is paint.json's "plan": what the last successful rewrite put in savedlocs.txt, so the script never
    expects a block other than the one the game has. load off: no paint blocks in savedlocs.txt and an
    empty plan; paint.json keeps the paint."""
    path = data_file()
    data = paintlog.load(path)
    # the paint as the last write put it in savedlocs.txt: a cut-short replay leaves those entries behind
    written = {m: paintlog.samples(s) for m, s in data["maps"].items()}
    if launch or "offset" not in data["log"]:
        rep = paintlog.read_log(game / "yaw.log", data)
        if rep and not quiet:
            print(f"yaw.log: {rep['strokes']} strokes, saved on {rep['saved'] or 'no map'}, "
                  f"cleared on {rep['cleared'] or 'no map'}, {rep['dropped']} never saved, "
                  f"{rep['moved']} blocked points moved, {rep['stuck']} given up on")
        if not launch:
            save_data(path, data)  # the bookmark; at launch the save below has it
    if launch:
        by_map = {m: paintlog.samples(s) for m, s in data["maps"].items()} if load else {}
        data["plan"] = {}  # until the rewrite is done: a failed one restores nothing
        save_data(path, data)
        try:
            rep = savedlocs.rewrite(game / "savedlocs.txt", by_map, leftovers=written)
        except (OSError, ValueError) as e:
            print(f"warning: couldn't update savedlocs.txt ({e}); saved paint won't come back this time",
                  file=sys.stderr)
            return {}
        for name, n in rep["removed"].items():
            print(f"removed {n} leftover paint savestates from {name}", file=sys.stderr)
        data["plan"] = paintlog.replay_plan(data["maps"]) if load else {}
        if not save_data(path, data):
            return {}
    plan = data.get("plan")
    return plan if load and isinstance(plan, dict) else {}


def save_data(path, data):
    try:
        paintlog.save(path, data)
    except OSError as e:
        print(f"warning: couldn't write {path} ({e})", file=sys.stderr)
        return False
    return True


def install(game, quiet=False, launch=False):
    """Returns this tool's skipped patches (see report). The hub page's switches (read_settings) decide
    what goes in; a change takes effect at the next game start."""
    game = Path(game)
    opts = read_settings()
    save, load = opts["save"], opts["save"] or opts["load_off"]
    plan = update_paint(game, launch, quiet, load)
    dest = game / "custom" / FOLDER
    shutil.rmtree(dest, ignore_errors=True)
    (dest / TS).parent.mkdir(parents=True)
    src = (ROOT / TS).read_text(encoding="utf-8")
    for mark in (PLAN_MARK, STUCK_MARK):
        if mark not in src:
            raise RuntimeError(f"{TS} has no {mark}")
    stuck = {m: n for m in plan if (n := paintlog.stuck(paintlog.load(data_file())["maps"].get(m, [])))}
    src = src.replace(PLAN_MARK, json.dumps(plan, separators=(",", ":")), 1)
    (dest / TS).write_text(src.replace(STUCK_MARK, json.dumps(stuck, separators=(",", ":")), 1), encoding="utf-8")
    found = paint_keys(game)
    cfgblock.set_block(game / "cfg" / "autoexec.cfg", TOOL, block(found, save, load), True, BACKUP)
    keys.record(TOOL, games.MOMENTUM.key, found if save else [])
    if not save and (launch or not game_running()):
        unbind(game)  # a running game would write its binds back over config.cfg when it quits
    skipped = report(panorama.install(game, FOLDER, TOOL, PATCHES))
    if not quiet:
        print(f"installed to {dest} (patched files in {panorama.KIT_FOLDER}); saving "
              f"{'on' if save else 'off'}, loading {'on' if load else 'off'}; saved paint on "
              f"{', '.join(plan) or 'no map yet'}")
        if save and not found:
            print(f"warning: no key is bound to {PAINT} in config.cfg, so no paint gets recorded", file=sys.stderr)
    link_launcher(add=True, quiet=quiet)
    return skipped


def unbind(game):
    """config.cfg's +mkpaint binds back to +paint."""
    path = game / "cfg" / "config.cfg"
    text = binds.cfg_text(path)
    if not text:
        return
    new = text
    for k in binds.keys_bound_to(text, OURS):
        new = new.replace(f'bind "{k}" "{OURS}"', f'bind "{k}" "{PAINT}"')
    if new != text:
        path.write_text(new, encoding="utf-8")
        print(f"bound {', '.join(binds.keys_bound_to(text, OURS))} back to {PAINT}")


def uninstall(game):
    if game is not None:
        game = Path(game)
        try:
            report(panorama.uninstall(game, FOLDER))
            synced = True
        except OSError as e:
            print(f"warning: couldn't update custom/{panorama.KIT_FOLDER} ({e}), so the script stays",
                  file=sys.stderr)
            synced = False
        cfgblock.set_block(game / "cfg" / "autoexec.cfg", TOOL, [], False, BACKUP)
        unbind(game)
        try:
            savedlocs.rewrite(game / "savedlocs.txt", {})
        except (OSError, ValueError) as e:
            print(f"warning: couldn't take the paint blocks out of savedlocs.txt ({e})", file=sys.stderr)
        dest = game / "custom" / FOLDER
        if synced and dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
            print(f"removed {dest}")
    keys.forget(TOOL)
    link_launcher(add=False)


def link_launcher(add, quiet=False):
    """Linux, not frozen: the launch hook that installs again at each Momentum start."""
    if sys.platform == "win32" or getattr(sys, "frozen", False):
        return
    from movekit import launch  # Linux only, so the exe doesn't carry it
    if add:
        launch.register(TOOL, HOOK_ORDER, ROOT / "launch-hook.sh")
        if not quiet:
            print(f"linked {launch.bin_link()}; Steam launch options: movekit-run %command%")
    else:
        launch.unregister(TOOL)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", type=Path, help="Momentum's game folder (holds cfg/ and custom/)")
    ap.add_argument("--launch", action="store_true",
                    help="the game is about to start: read yaw.log and write savedlocs.txt (the launch hook)")
    ap.add_argument("--uninstall", action="store_true", help="take Paint Saver out again")
    ap.add_argument("--quiet", action="store_true", help="print only warnings (the launch hook)")
    args = ap.parse_args()
    game = args.game if args.game and (args.game / "cfg").is_dir() else None if args.game else find_game()
    if args.uninstall:
        uninstall(game)
        if game is None:
            print("Momentum Mod not found, so nothing was removed from the game")
        return
    if game is None:
        sys.exit("Momentum Mod not found in any Steam library; pass --game with its momentum folder")
    install(game, quiet=args.quiet, launch=args.launch)


if __name__ == "__main__":
    main()
