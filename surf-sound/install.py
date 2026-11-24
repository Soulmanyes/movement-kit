#!/usr/bin/env python3
"""Installs Surf Sound into Momentum Mod, or takes it out again.

Usage: install.py [--game DIR] [--uninstall]

- Copies its script (panorama/scripts/hud/movekit-surf-sound.ts) into the game's custom/movekit-surf-sound
  folder, and hands the kit (movekit/panorama.py) one patch: the script's include in layout/hud/timer.xml.
  The kit writes that file into custom/0-movekit, made from the copy the game would use otherwise
  (another HUD mod's in custom/, else the game's own). The script draws nothing, so it needs no HUD
  customizer entry. Type panorama_reload in game after installing.
- Writes a `// movekit:surf-sound` block into cfg/autoexec.cfg (movekit.cfgblock) that turns the console
  log on (con_logfile yaw.log): the script's MK_SURFSND_* markers reach the sound runner (sound_run.py)
  through it. It also hides every MK_ marker in the console (con_filter_text_out MK_); yaw.log still
  gets them.
- On Linux, registers launch-hook.sh with movekit-run (movekit/launch.py), which runs this install
  again when Momentum starts, so a game update to timer.xml carries over, and starts the sound runner.
  On Windows the kit's core does both through module_hooks.launch.

The game folder comes from MOMENTUM_DIR or Steam's library folders, or --game.
--uninstall removes the patch, the script, the autoexec block and the launch hook. With no game found it
still removes the launch hook.
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False) and (ROOT.parent / "movekit").is_dir() and str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))  # the kit root (repo or core copy); the core exe bundles movekit
from movekit import cfgblock, games, panorama, steam  # after the path above

VERSION = "1.2.1"  # Surf Sound's (module.json reads it); bump in the same commit as the release tag
TOOL = "surf-sound"
FOLDER = "movekit-surf-sound"  # its own files; a new name, so the mount order doesn't matter
HOOK_ORDER = 90  # after the HUD modules (JHUD 40 ... Z Penalty 80); all only sync the kit
TS = "panorama/scripts/hud/movekit-surf-sound.ts"
BACKUP = ".bak-surf-sound"
BLOCK = ["// Surf Sound's runner reads the script's markers from yaw.log", "con_logfile yaw.log",
         "// the kit's MK_ markers stay out of the console; yaw.log still gets them",
         "con_filter_enable 1", "con_filter_text_out MK_"]
PATCHES = [  # for movekit/panorama.py
    {"file": "panorama/layout/hud/timer.xml", "before": "</scripts>",
     "line": '<include type="module" src="file://{scripts}/hud/movekit-surf-sound.ts" />'},
]


def find_game():
    """Momentum's game folder as a Path, or None when it isn't there."""
    game = steam.game_dir(games.MOMENTUM)
    return game if game and (game / "cfg").is_dir() else None


def report(result):
    """Print what the kit couldn't do; returns this tool's skipped patches. A skipped patch means the
    game changed that file: without the include Surf Sound doesn't load."""
    for w in result["warnings"]:
        print(f"warning: {w}", file=sys.stderr)
    skipped = [r for r in result["patches"] if r["state"] == "skipped"]
    for row in skipped:
        print(f"warning: {row['tool']}'s patch to {row['file']} is left out ({row['reason']})",
              file=sys.stderr)
    return [r for r in skipped if r["tool"] == TOOL]


def install(game, quiet=False):
    """Returns this tool's skipped patches (see report)."""
    game = Path(game)
    dest = game / "custom" / FOLDER
    shutil.rmtree(dest, ignore_errors=True)
    (dest / TS).parent.mkdir(parents=True)
    shutil.copyfile(ROOT / TS, dest / TS)
    cfgblock.set_block(game / "cfg" / "autoexec.cfg", TOOL, BLOCK, True, BACKUP)
    # after the copy: the kit's timer.xml must never include a script that isn't there
    skipped = report(panorama.install(game, FOLDER, TOOL, PATCHES))
    if not quiet:
        print(f"installed to {dest} (patched files in {panorama.KIT_FOLDER})")
    link_launcher(add=True, quiet=quiet)
    return skipped


def uninstall(game):
    if game is not None:
        game = Path(game)
        # the patches go first, so the kit's timer.xml never includes a script that's gone
        try:
            report(panorama.uninstall(game, FOLDER))
            synced = True
        except OSError as e:
            print(f"warning: couldn't update custom/{panorama.KIT_FOLDER} ({e}), so the script stays",
                  file=sys.stderr)
            synced = False
        cfgblock.set_block(game / "cfg" / "autoexec.cfg", TOOL, [], False, BACKUP)
        dest = game / "custom" / FOLDER
        if synced and dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
            print(f"removed {dest}")
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
    ap.add_argument("--uninstall", action="store_true", help="take Surf Sound out again")
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
    install(game, quiet=args.quiet)


if __name__ == "__main__":
    main()
