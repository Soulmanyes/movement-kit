#!/usr/bin/env python3
"""Installs Z Penalty into Momentum Mod, or takes it out again.

Usage: install.py [--game DIR] [--uninstall]

- Copies its script (panorama/scripts/hud/movekit-z-penalty.ts) into the game's custom/movekit-z-penalty folder,
  with the hub's sound setting written into its SOUND line (settings.py), and hands the kit (movekit/panorama.py) two patches: the script's include in layout/hud/timer.xml,
  and Z Penalty's entry in cfg/hud/hud_default.kv3, without which Momentum's HUD customizer won't take the
  panel. The kit writes both files into custom/0-movekit, made from the copies the game would use
  otherwise (another HUD mod's in custom/, else the game's own). Type panorama_reload in game after
  installing.
- On Linux, registers launch-hook.sh with movekit-run (movekit/launch.py), which runs this install
  again when Momentum starts, so a game update to either file carries over. On Windows the kit's
  core does that through module_hooks.launch.

The game folder comes from MOMENTUM_DIR or Steam's library folders, or --game.
--uninstall removes the patches, the script and the launch hook. With no game found it still
removes the launch hook. The player's saved HUD presets keep their Z Penalty settings; the
customizer ignores them while it isn't installed.
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False) and (ROOT.parent / "movekit").is_dir() and str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))  # the kit root (repo or core copy); the core exe bundles movekit
from movekit import games, panorama, steam  # after the path above
from movekit.hub import local_import

VERSION = "1.0.0"  # Z Penalty's (module.json reads it); bump in the same commit as the release tag
TOOL = "z-penalty"
FOLDER = "movekit-z-penalty"  # its own files; a new name, so the mount order doesn't matter
HOOK_ORDER = 80  # after the other HUD modules (JHUD 40, Strafe Speed Histogram 50, First Jump 60, Zone Exit 70); all only sync the kit
TS = "panorama/scripts/hud/movekit-z-penalty.ts"
LAYOUT = "cfg/hud/hud_default.kv3"
ANCHOR = "    CustomizerSettings = "  # the first entry in the game's hud_default.kv3, once
# The customizer's defaults for Z Penalty's panel (id MovekitZPenalty): position in its 1920x1080 units, then
# every setting the script lists in STYLES, with the values of its DEFAULTS (check_z_penalty.js compares).
ENTRY = """    MovekitZPenalty = 
    {
        enabled = true
        offsetX = 1100
        offsetY = 440
        width = 200
        dynamicStyles = 
        {
            font = "$fontPrimary"
            fontSize = 22
            fontColor = "$fontColor"
            backgroundColor = "rgba(0, 0, 0, 0)"
            rampsOnly = true
            alwaysShow = false
            showLabel = true
            showNumber = true
            showTicks = true
            showBar = true
            barHeight = 120
            barWidth = 12
            barMax = 300
            trackColor = "rgba(255, 255, 255, 0.15)"
            bandColor = "rgba(255, 176, 50, 0.35)"
            markerColor = "rgba(255, 255, 255, 0.9)"
            penaltyColor = "rgba(255, 176, 50, 1)"
            holdMs = 1500
            fadeMs = 300
        }
    }
"""
PATCHES = [  # for movekit/panorama.py
    {"file": "panorama/layout/hud/timer.xml", "before": "</scripts>",
     "line": '<include type="module" src="file://{scripts}/hud/movekit-z-penalty.ts" />'},
    {"file": LAYOUT, "find": ANCHOR, "replace": ENTRY + ANCHOR},
]


def find_game():
    """Momentum's game folder as a Path, or None when it isn't there."""
    game = steam.game_dir(games.MOMENTUM)
    return game if game and (game / "cfg").is_dir() else None


def report(result):
    """Print what the kit couldn't do; returns this tool's skipped patches. A skipped patch means the
    game changed that file: without the include Z Penalty doesn't load, without the entry the HUD
    customizer doesn't take it (it then logs a warning and stays hidden)."""
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
    # the hub's sound setting goes into the copy (settings.py); the repo's script keeps the default
    sound = local_import(__file__, "settings")
    sound.bake_file(ROOT / TS, dest / TS, sound.load())
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
    ap.add_argument("--uninstall", action="store_true", help="take Z Penalty out again")
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
