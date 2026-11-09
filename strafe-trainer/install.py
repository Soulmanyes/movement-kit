#!/usr/bin/env python3
"""Installs the Strafe Trainer's game side, or takes it out again.

Usage: install.py [--uninstall] [--apply GAME] [--quiet]

- Copies the trainer settings from Source Yaw once, for each game that has none here yet
  (store.import_from_sourceyaw: Source Yaw held the trainer until Phase 13).
- Writes the `// movekit:strafe-trainer` block into each found game's autoexec.cfg while the
  trainer is on there (gamecfg.py), and records the offset key for the other tools.
- Linux: builds the overlay layer (overlay/, needs a C compiler and make), puts the library in
  ~/.local/share/strafe-trainer/overlay and its manifest in vulkan/implicit_layer.d, and registers
  launch-hook.sh with movekit-run. Without a compiler the trainer still plays its sounds.

--apply GAME: what the launch does before the game starts: the block again (a changed key in
config.cfg, a game update) and, on Linux, the layer manifest pointing at this module's library.
--uninstall: the blocks, the recorded keys, the launch hook, the layer and its manifest. The
input service (a root service) stays; uninstall it with: sudo sh inputd/install-inputd.sh remove
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False) and (_HERE.parent / "movekit").is_dir() and str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))  # the kit root (repo or core copy); the core exe bundles movekit
from movekit import games, keys, paths  # after the path above
from movekit.hub import local_import

ROOT = Path(__file__).resolve().parent
TOOL = "strafe-trainer"
HOOK_ORDER = 55  # after Source Yaw's (50), which may empty yaw.log for CS:S before its readers start
store = local_import(__file__, "store")
gamecfg = local_import(__file__, "gamecfg")

LAYER_NAME = "sourceyaw-overlay"  # the layer kept Source Yaw's names (Phase 13): nothing in play shows them
OVERLAY_DIR = paths.data_dir(TOOL) / "overlay"
LIBRARY = OVERLAY_DIR / f"{LAYER_NAME}.so"
MANIFESTS = paths.data_dir("vulkan") / "implicit_layer.d"
MANIFEST = MANIFESTS / f"{LAYER_NAME}.json"
# Source Yaw's copy before Phase 13; its install.sh (1.11.0 and later) deletes it
OLD_LIBRARY_DIR = paths.data_dir("sourceyaw") / "overlay"


def linux():
    return sys.platform.startswith("linux") and not getattr(sys, "frozen", False)


def apply_game(game, quiet=False):
    path = gamecfg.apply(game, store.config(game))
    if path and not quiet:
        print(f"{games.GAMES[game].name}: {path}")


def build_overlay(quiet=False):
    """Build the layer and put it in place; False when it can't be built here."""
    if not shutil.which("cc") or not shutil.which("make"):
        print("The offset display needs a C compiler and make (the sounds work without them)", file=sys.stderr)
        return False
    run = subprocess.run(["make", "-C", str(ROOT / "overlay")], capture_output=True, text=True, check=False)
    if run.returncode != 0:
        print("Building the offset display failed: " + (run.stderr.strip().splitlines() or ["make"])[-1],
              file=sys.stderr)
        return False
    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    tmp = LIBRARY.with_suffix(".so.new")
    shutil.copyfile(ROOT / "overlay" / "lib" / f"{LAYER_NAME}.so", tmp)
    tmp.chmod(0o755)
    tmp.replace(LIBRARY)  # a running game keeps the old file open
    write_manifest()
    if not quiet:
        print(f"offset display: {LIBRARY}")
    return True


def write_manifest():
    """Point the layer manifest at this module's library (a rolled-back Source Yaw may have pointed
    it at its own copy). Only while the library is there."""
    if not LIBRARY.is_file():
        return False
    text = (ROOT / "overlay" / f"{LAYER_NAME}.json.in").read_text().replace("@LIBRARY@", str(LIBRARY))
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    if not MANIFEST.is_file() or MANIFEST.read_text() != text:
        MANIFEST.write_text(text)
    return True


def remove_overlay():
    # the manifest only while it is ours: an older Source Yaw may have it pointing at its own copy
    if MANIFEST.is_file() and str(OVERLAY_DIR) in MANIFEST.read_text():
        MANIFEST.unlink()
    shutil.rmtree(OVERLAY_DIR, ignore_errors=True)


def link_launcher(add, quiet=False):
    if not linux():
        return
    from movekit import launch  # Linux only, so the exe doesn't carry it
    if add:
        launch.register(TOOL, HOOK_ORDER, ROOT / "launch-hook.sh")
        if not quiet:
            print(f"linked {launch.bin_link()}; Steam launch options: movekit-run %command%")
    else:
        launch.unregister(TOOL)


def install(quiet=False):
    copied = store.import_from_sourceyaw()
    if copied and not quiet:
        print("copied the trainer settings from Source Yaw: " + ", ".join(copied))
    for game in store.GAMES:
        apply_game(game, quiet)
    if linux():
        build_overlay(quiet)
        link_launcher(True, quiet)


def uninstall():
    for game in store.GAMES:
        game_dir = games.find(game)
        if game_dir:
            gamecfg.remove(game_dir)
    keys.forget(TOOL)
    if linux():
        remove_overlay()
        link_launcher(False)
        print("The input service stays. Remove it with: sudo sh "
              f"{ROOT / 'inputd/install-inputd.sh'} remove")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--uninstall", action="store_true", help="take the trainer's game side out again")
    ap.add_argument("--apply", choices=store.GAMES, help="the launch step for one game")
    ap.add_argument("--quiet", action="store_true", help="print only warnings")
    args = ap.parse_args()
    if args.uninstall:
        uninstall()
    elif args.apply:
        apply_game(args.apply, quiet=args.quiet)
        if linux():
            write_manifest()
    else:
        install(quiet=args.quiet)


if __name__ == "__main__":
    main()
