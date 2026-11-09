"""Sets up the dev kit (movekit/movekit-dev): a second Movement Kit that runs from this git
checkout with its own files, next to the installed kit and without changing it. Linux only.

movekit-dev points XDG_DATA_HOME, XDG_STATE_HOME and XDG_CACHE_HOME into the dev root
(~/.local/share/movekit-dev) and MOVEKIT_BIN_DIR at its bin/, so the hub's state, the launch hooks,
the movekit-run link and every module's installed copy land there. `setup` (run by movekit-dev
inside that environment) then:
  - keeps a copy of ~/.config/{movekit,sourceyaw,strafe-trainer} from before the first dev run, in
    <root>/config-before-dev (settings are shared with the installed kit, and the first run of a
    new module may import old ones, so this is the way back);
  - seeds <root>/data/movekit from the installed kit's state (binds, HUD settings, notes seen),
    without its kit, hooks, locks or rollback copies;
  - links the installed kit's Vulkan layers into the dev tree, except its own overlay ones
    (sourceyaw-*), so a game started by the dev kit loads the dev overlay and still gets Steam's;
  - links fonts and themes, which the hub window reads from XDG_DATA_HOME;
  - writes the "Movement Kit (dev)" app menu entry into the real applications folder;
  - installs into the dev tree the modules the installed kit has (and what their split_out hook
    names, e.g. Strafe Trainer out of Source Yaw), by running their install hooks from the checkout.
    Install hooks also write the game side (cfg blocks, custom/ folders) into the real game
    folders, which both kits share; run the installed kit's install again to put its own back.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movekit import devsteam, games, modules, paths

CHECKOUT = Path(__file__).resolve().parent.parent
APP_ID = "io.github.soulmanyes.MovementKit"  # movekit/hub.py's; the dev kit's is APP_ID + ".Dev"
SHARED_CONFIGS = ("movekit", "sourceyaw", "strafe-trainer")
NOT_SEEDED = {"kit", "hooks", "previous", "staging", "modules.lock", "panorama.lock"}
OWN_LAYERS = "sourceyaw-"  # the kit's Vulkan layer manifests (the trainer overlay, KROSSHAIR)
LINKED_DATA = ("fonts", "themes")


def live_data():
    return Path(os.environ.get("MOVEKIT_LIVE_DATA") or Path.home() / ".local/share")


def dev_root():
    return Path(os.environ["MOVEKIT_DEV_ROOT"])


def snapshot_configs(root, log):
    """~/.config/<shared> as it was before the dev kit first ran, once."""
    keep = root / "config-before-dev"
    if keep.exists():
        return
    keep.mkdir(parents=True)
    for name in SHARED_CONFIGS:
        src = paths.config_dir(name)
        if src.is_dir():
            shutil.copytree(src, keep / name, symlinks=True)
    log(f"kept a copy of the shared settings in {keep}")


def seed_state(live, dev, log):
    """The installed kit's own state, copied (not linked: the dev kit changes it)."""
    dev.mkdir(parents=True, exist_ok=True)
    for item in sorted(live.iterdir()) if live.is_dir() else ():
        if item.name in NOT_SEEDED or (dev / item.name).exists():
            continue
        if item.is_dir():
            shutil.copytree(item, dev / item.name, symlinks=True)
        else:
            shutil.copy2(item, dev / item.name)
    log(f"seeded {dev} from {live}")


def link_layers(live, dev, log):
    """Links to the installed Vulkan layer manifests, without the kit's own."""
    dev.mkdir(parents=True, exist_ok=True)
    for old in dev.iterdir():
        if old.is_symlink():
            old.unlink()
    for manifest in sorted(live.glob("*.json")) if live.is_dir() else ():
        if not manifest.name.startswith(OWN_LAYERS) and not (dev / manifest.name).exists():
            (dev / manifest.name).symlink_to(manifest)
    log(f"Vulkan layers: {', '.join(sorted(p.name for p in dev.iterdir())) or 'none'}")


def link_data(live, dev):
    for name in LINKED_DATA:
        if (live / name).is_dir() and not (dev / name).exists():
            (dev / name).symlink_to(live / name)


def desktop_entry(live, log):
    """The app menu entry, in the real applications folder (the dev one isn't on the menu's path)."""
    apps = live / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    entry = apps / f"{APP_ID}.Dev.desktop"
    entry.write_text("\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Movement Kit (dev)",
        "Comment=The Movement Kit from the git checkout, with its own files",
        f"Exec={CHECKOUT / 'movekit' / 'movekit-dev'}",
        f"Icon={APP_ID}",
        f"StartupWMClass={APP_ID}.Dev",
        "Categories=Game;Utility;",
        "",
    ]))
    log(f"app menu entry: {entry}")


def live_modules(live_kit):
    """Keys of the modules the installed kit has (folders with a module.json, the core left out)."""
    keys = []
    for folder in sorted(live_kit.iterdir()) if live_kit.is_dir() else ():
        if (folder / modules.MANIFEST).is_file():
            try:
                keys.append(modules.read_manifest(folder)["key"])
            except ValueError:
                continue
    return keys


def install_modules(wanted, log):
    """Hide every checkout module in the dev state, then install the wanted ones (and what their
    split_out hooks name) through the manager, so their install hooks run in the dev tree."""
    state = modules.data_dir() / "modules.json"
    data = json.loads(state.read_text()) if state.is_file() else {}
    mgr = modules.Manager(kit_root=CHECKOUT)
    entries = data.setdefault("modules", {})
    for key in mgr.available():
        entries.setdefault(key, {})["removed"] = True
    state.write_text(json.dumps(data, indent=1))
    mgr = modules.Manager(kit_root=CHECKOUT)
    failed = []
    for key in [k for k in wanted if k in mgr.available()]:
        try:
            mgr.install(key)
            mgr._split_out(key)  # what an update of the installed kit would add next to it
            log(f"installed {key}")
        except Exception as e:  # noqa: BLE001 - noted, the others go on
            failed.append(key)
            log(f"{key}: {type(e).__name__}: {e}")
    for key in sorted(set(mgr.installed()) - set(wanted)):
        log(f"installed {key} (split out)")
    return failed


def setup(args):
    root, live = dev_root(), live_data()
    log = print
    for sub in ("data", "state", "cache", "bin"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    snapshot_configs(root, log)
    fresh = not (modules.data_dir() / "modules.json").is_file()
    if fresh or args.reseed:
        seed_state(live / "movekit", modules.data_dir(), log)
    link_layers(live / "vulkan" / "implicit_layer.d", paths.data_dir("vulkan") / "implicit_layer.d", log)
    link_data(live, root / "data")
    desktop_entry(live, log)
    if fresh or args.reinstall:
        failed = install_modules(live_modules(live / "movekit" / "kit"), log)
        if failed:
            sys.exit(f"devkit: these failed to install: {', '.join(failed)}")
    log("dev kit ready: movekit-dev opens the hub")


def main():
    ap = argparse.ArgumentParser(description="The Movement Kit dev kit (run through movekit-dev).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="make the dev tree; later runs only refresh links and the app entry")
    s.add_argument("--reseed", action="store_true", help="copy the installed kit's state again (keeps dev files that exist)")
    s.add_argument("--reinstall", action="store_true", help="run the install hooks of the installed kit's modules again")
    g = sub.add_parser("game", help="start a game under the dev kit's launch wrapper (movekit/devsteam.py)")
    g.add_argument("key", choices=sorted(games.GAMES))
    g.add_argument("args", nargs=argparse.REMAINDER, help="passed to the game")
    sub.add_parser("steam-entries", help="add '<game> (dev kit)' to the Steam library (Steam closed)")
    args = ap.parse_args()
    if not paths.dev():
        sys.exit("devkit: run this through movekit/movekit-dev")
    if args.cmd == "setup":
        setup(args)
    elif args.cmd == "game":
        devsteam.run_game(args.key, args.args)
    else:
        devsteam.steam_entries()


if __name__ == "__main__":
    main()
