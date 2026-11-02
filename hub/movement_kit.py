#!/usr/bin/env python3
"""Soulmanyes's Movement Kit for Windows: the core exe (3.7b in PLAN.md). The tools are modules it
downloads (movekit/modules.py); the exe itself carries only the hub, movekit and the HUD settings.

    movement-kit.exe                     open the hub: the Modules page and the installed modules'
                                         sections (movekit/hub.py)
    movement-kit.exe %command%           as a Steam launch option: each installed module's launch step
                                         (Strafe Review: install the recorder, start its server, open
                                         the review page), then the game. The game starts whatever
                                         the modules do, also with none installed (movekit/dispatch.py).
    movement-kit.exe --run-script FILE [ARGS...]
                                         run a module's Python script by path in this process, as
                                         python would (module installers, Strafe Review's server)
    movement-kit.exe --modules OUT CMD [KEY] [--delete-data]
                                         the Modules page's calls with no window, the reply as JSON in
                                         the file OUT (the exe has no console): CMD is cards, check,
                                         install, update, rollback, uninstall, auto-on or auto-off
    movement-kit.exe --check-sections OUT [KEY.NAME[:JSON] ...]
                                         write the sections found to OUT as JSON, with the replies of
                                         the section functions named (the smoke test)

Output goes to movement-kit.log in %LOCALAPPDATA%\\movekit too. A copy that came from Strafe
Review's own exe line (the bridge release) is still called strafe-review.exe, so Steam's launch
option keeps working; on its first start it installs the Strafe Review module (migrate()), and the
old exe's --serve/--restarted/--collect go to that module (legacy()).
On Linux the hub runs from the repo or a copy (movekit/hub.py) and movekit-run is the launch option.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False):
    # from the repo (tests): the kit root holds movekit and hud; hub/ holds hub_release
    sys.path[:0] = [str(HERE.parent), str(HERE)]

import hub_release

RUN_SCRIPT = "--run-script"
MODULES = "--modules"
CHECK_SECTIONS = "--check-sections"
# Strafe Review's own modes from before the core: an old strafe-review.exe that updated itself into
# the core (the bridge) starts the new exe with these to bring its server back
LEGACY = {"--serve": ["--serve"], "--restarted": ["--collect"], "--collect": ["--collect"]}
MIGRATED = "migrated-from-strafe-review"  # state flag: the bridge's one-time install happened or isn't needed


def run_script(path, args):
    """python FILE ARGS, inside the exe: the script's folder first on the path, as python puts it."""
    import runpy

    sys.argv = [path, *args]
    sys.path.insert(0, str(Path(path).resolve().parent))
    runpy.run_path(path, run_name="__main__")
    return 0


def core_installer(latest):
    """Install a core update: the exe in the release zip, swapped in under this exe's own name
    (strafe-review.exe stays strafe-review.exe). The new version runs from the next start."""
    from movekit import modules, updater

    exe = updater.frozen_exe()
    if not exe:
        raise RuntimeError("Only the exe updates itself; a copy from the repo updates with git pull")
    if not latest.get("asset"):
        raise RuntimeError(f"The {latest['tag']} release has no {modules.CORE_ASSET}")
    updater.swap_exe(exe, latest["asset"], modules.AGENT, modules.CORE_ASSET, hub_release.EXE)


def manager():
    import os

    from movekit import modules, updater

    api = os.environ.get("MOVEKIT_MODULES_API", modules.API)  # tests point it at a fake GitHub
    kit = os.environ.get("MOVEKIT_KIT_ROOT")  # and the kit at a temp folder (from the repo it's the checkout)
    return modules.Manager(kit_root=kit or None, api=api, core_version=hub_release.VERSION,
                           core_installer=core_installer if updater.frozen_exe() else None)


def migrate(mgr, log=print):
    """The bridge (3.7b): a copy that came from Strafe Review's own exe has Strafe Review's data
    folder but no module yet. Install the module once, keeping the old auto-update switch. Offline,
    it's tried again on the next start; the game starts either way."""
    from movekit import paths

    if mgr.checkout or mgr.state.get(MIGRATED):
        return
    old = paths.data_dir("strafe-review")
    if old.is_dir() and "strafe-review" not in mgr.installed():
        try:
            mgr.check(force=True)
            mgr.install("strafe-review")
        except Exception as e:  # noqa: BLE001 - retried next start; nothing may stop the hub or the game
            log(f"movement kit: couldn't install the Strafe Review module yet: {e}")
            return
        auto = False
        for name in ("updates.json", "hub-updates.json"):  # Strafe Review's and 3.7's hub line's
            try:
                auto = auto or bool(json.loads((old / name).read_text()).get("auto"))
            except (OSError, ValueError, AttributeError):
                pass
        mgr.set_auto("strafe-review", auto)
        log("movement kit: installed the Strafe Review module (moved over from strafe-review.exe)")
    mgr.note(MIGRATED, True)


def legacy(mgr, flag):
    """Run Strafe Review's mode for an old flag through the installed module (see LEGACY)."""
    if mgr is None or "strafe-review" not in mgr.installed():
        print(f"movement kit: {flag} is Strafe Review's, which isn't installed", file=sys.stderr)
        return 1
    return run_script(str(mgr.folder("strafe-review") / "strafe_review.py"), LEGACY[flag])


def modules_cli(out, cmd, rest):
    mgr = manager()
    key = next((a for a in rest if not a.startswith("--")), None)
    reply = {"ok": True}
    try:
        if cmd == "check":
            mgr.check(force=True)
        elif cmd in ("install", "update", "rollback"):
            getattr(mgr, cmd)(key)
        elif cmd == "uninstall":
            mgr.uninstall(key, delete_data="--delete-data" in rest)
        elif cmd in ("auto-on", "auto-off"):
            mgr.set_auto(key, cmd == "auto-on")
        elif cmd != "cards":
            raise ValueError(f"unknown command {cmd!r}")
    except Exception as e:  # noqa: BLE001 - the reply carries it
        reply = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    reply["cards"] = mgr.cards()
    Path(out).write_text(json.dumps(reply), encoding="utf-8")
    return 0 if reply["ok"] else 1


def main():
    from movekit import dispatch, hub, logfile, modules, updater

    args = sys.argv[1:]
    if args[:1] == [RUN_SCRIPT] and len(args) >= 2:
        return run_script(args[1], args[2:])
    logfile.tee(modules.data_dir() / "movement-kit.log")
    if args[:1] == [MODULES] and len(args) >= 3:
        return modules_cli(args[1], args[2], args[3:])
    if args[:1] == [CHECK_SECTIONS] and len(args) >= 2:
        hub.check_sections(args[1], calls=args[2:], manager=manager())
        return 0
    exe = updater.frozen_exe()
    if exe:
        updater.clean_old(exe)
    try:
        mgr = manager()
        migrate(mgr)
    except Exception as e:  # noqa: BLE001 - the game, or the hub, still starts
        print(f"movement kit: the module manager failed: {e}", file=sys.stderr)
        mgr = None
    if args[:1] and args[0] in LEGACY:
        return legacy(mgr, args[0])
    if args:
        return dispatch.run(mgr, args)
    hub.run(manager=mgr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
