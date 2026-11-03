#!/usr/bin/env python3
"""Installs Strafe Trainer Height into Momentum Mod, or takes it out again.

Usage: install.py [--game DIR] [--uninstall]

- Copies its stylesheet (panorama/styles/hud/strafe-trainer-height.scss) into the game's
  custom/movekit-trainer-height folder, and hands the kit's Panorama files (movekit/panorama.py) two
  patches: the stylesheet's include in layout/hud/strafe-trainer.xml, and resizeY: true in
  scripts/hud/strafe-trainer.ts, so the strafe trainer's height can be dragged in the HUD editor.
  The kit writes both files into custom/0-movekit, made from the copies the game would use otherwise
  (another HUD mod's in custom/, else the game's own). Type panorama_reload in game after installing.
- Removes custom/strafe-trainer-height, the same mod installed by hand before it was a module.
- On Linux, registers launch-hook.sh with movekit-run (movekit/launch.py), which runs this install
  again when Momentum starts, so a game update to either file carries over. On Windows the kit's
  core does that through module_hooks.launch.

The game folder comes from MOMENTUM_DIR or Steam's library folders, or --game.
--uninstall removes the patches, the stylesheet and the launch hook. With no game found it still
removes the launch hook.
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False) and (ROOT.parent / "movekit").is_dir() and str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))  # the kit root (repo or core copy); the core exe bundles movekit
from movekit import games, panorama, steam  # after the path above

VERSION = "1.0.0"  # Strafe Trainer Height's (module.json reads it); bump in the same commit as the release tag
TOOL = "trainer-height"
FOLDER = "movekit-trainer-height"  # its own files; a new name, so the mount order doesn't matter
OLD_FOLDERS = ["strafe-trainer-height"]  # the mod as installed by hand (install.sh) before 2026-11-03
HOOK_ORDER = 30  # after Strafe Review's (20); both only sync the kit, so the order doesn't matter
SCSS = "panorama/styles/hud/strafe-trainer-height.scss"
PATCHES = [  # for movekit/panorama.py
    {"file": "panorama/layout/hud/strafe-trainer.xml", "before": "</styles>",
     "line": '<include src="file://{resources}/styles/hud/strafe-trainer-height.scss" />'},
    {"file": "panorama/scripts/hud/strafe-trainer.ts", "find": "resizeY: false,", "replace": "resizeY: true,"},
]


def find_game():
    """Momentum's game folder as a Path, or None when it isn't there."""
    game = steam.game_dir(games.MOMENTUM)
    return game if game and (game / "cfg").is_dir() else None


def report(result):
    """Print what the kit couldn't do; returns this tool's skipped patches. A skipped patch means the
    game changed that file, and the trainer keeps its own height."""
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
    # first: an old copy left in custom/ would be taken as the base the kit patches
    for old in OLD_FOLDERS:
        if (game / "custom" / old).exists():
            shutil.rmtree(game / "custom" / old, ignore_errors=True)
            print(f"removed {game / 'custom' / old}")
    dest = game / "custom" / FOLDER
    shutil.rmtree(dest, ignore_errors=True)
    (dest / SCSS).parent.mkdir(parents=True)
    shutil.copyfile(ROOT / SCSS, dest / SCSS)
    # after the copy: the kit's strafe-trainer.xml must never include a stylesheet that isn't there
    skipped = report(panorama.install(game, FOLDER, TOOL, PATCHES))
    if not quiet:
        print(f"installed to {dest} (patched files in {panorama.KIT_FOLDER})")
    link_launcher(add=True, quiet=quiet)
    return skipped


def uninstall(game):
    if game is not None:
        game = Path(game)
        # the patches go first, so the kit's strafe-trainer.xml never includes a stylesheet that's gone
        try:
            report(panorama.uninstall(game, FOLDER))
            synced = True
        except OSError as e:
            print(f"warning: couldn't update custom/{panorama.KIT_FOLDER} ({e}), so the stylesheet stays",
                  file=sys.stderr)
            synced = False
        for name in ((FOLDER,) if synced else ()) + tuple(OLD_FOLDERS):
            dest = game / "custom" / name
            if dest.exists():
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
    ap.add_argument("--uninstall", action="store_true", help="take Strafe Trainer Height out again")
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
