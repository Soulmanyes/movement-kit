#!/usr/bin/env python3
"""Source Yaw's Windows code on a real Windows, without a game or a person: the sourceyaw-windows
CI job (Phase 12 in PLAN.md) runs it on windows-latest, with the same Python as the hub exe.

Usage: python sourceyaw/windows/check_windows.py   (Windows only; exits 1 on the first failure)

Checks what Linux can't: the config folder in %APPDATA%, no crosshair colour; launch_win through
module_hooks.launch (yaws.cfg without colour, the list switcher started and stopped, no trainer
thread: the trainer is its own module since Phase 13, checked by strafe-trainer/windows/); and the
hub section loading on Windows.
"""
import os
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCEYAW = HERE.parent
KIT = SOURCEYAW.parent


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")
    print(f"ok   {what}", flush=True)


def timed(what, fn, limit):
    start = time.perf_counter()
    result = fn()
    took = time.perf_counter() - start
    if took > limit:
        fail(f"{what} took {took:.2f} s (limit {limit} s)")
    print(f"ok   {what} in {took * 1000:.0f} ms", flush=True)
    return result


# ---------------------------------------------------------------- the checks

def fake_game(root, name):
    game_dir = root / "steamapps" / "common" / name / ("cstrike" if name.startswith("Counter") else "momentum")
    (game_dir / "cfg").mkdir(parents=True)
    (game_dir / "cfg" / "config.cfg").write_text('bind "SPACE" "+jump"\nbind "a" "+moveleft"\n'
                                                 'bind "d" "+moveright"\nbind "MOUSE1" "+left"\n')
    return game_dir


def check_launch(yawcore, game_dir):
    import module_hooks
    data = yawcore.load_settings("css")
    # a surf list with auto switching, so the list switcher starts; a trainer dict saved by 1.10
    data.update(surf={"entries": data["entries"][:2], "start": 0}, separate=True, auto_mode=True,
                trainer={"enabled": True, "tone_volume": 0.05})
    yawcore.save_settings(data, "css")
    import launch_win
    at_exit = []
    launch_win.atexit = types.SimpleNamespace(register=at_exit.append)
    ctx = types.SimpleNamespace(platform="win32", folder=SOURCEYAW)
    module_hooks.launch(ctx, [str(game_dir.parent / "cstrike_win64.exe"), "-steam"])
    cfg = (game_dir / "cfg" / "yaws.cfg").read_text()
    expect((cfg.startswith(yawcore.YAWS_HEADER), "yaws_colors" in cfg, "krosshair" in cfg.lower()),
           (True, False, False), "launch: yaws.cfg written, no colour")
    # by name: a count would also see the last step's threads ending meanwhile
    names = [t.name for t in threading.enumerate()]
    expect(("sourceyaw-mode" in names, "sourceyaw-trainer" in names), (True, False),
           "launch: list switcher running, no trainer")
    expect(len(at_exit), 1, "launch: exit step registered")
    time.sleep(1)
    timed("launch: exit step (helpers stopped)", at_exit[0], 6)
    log = launch_win.LOG.read_text(encoding="utf-8")
    expect(("Counter-Strike: Source started with" in log, "Traceback" in log), (True, False),
           f"launch: run.log ({launch_win.LOG})")


def check_hub(game_dir):
    from movekit import hub
    sections, problems = hub.discover(KIT, platform="win32")
    expect([p for p in problems if p[0] == "sourceyaw"], [], "hub: no sourceyaw problems")
    expect("sourceyaw" in [s.key for s in sections], True, "hub: sourceyaw listed")
    bridge = hub.Bridge(sections, problems)
    api = hub.local_import(SOURCEYAW / "hub_section.py", "settings_api")
    api.core.find_game = lambda game: game_dir if game == "css" else None

    def call(name, **args):
        got = bridge.call("sourceyaw", name, args)
        if not got["ok"]:
            fail(f"hub {name}: {got['error']}")
        return got["result"]

    st = call("load", game="css")
    expect((st["windows"], st["previews"], st["uses_krosshair"]), (True, [], False), "hub: load on Windows")
    expect("movement-kit.exe" in st["launch"]["text"], True, "hub: the core exe's launch option")


def main():
    if sys.platform != "win32":
        sys.exit("check_windows.py is for Windows")
    # run.log stays open (launch_win tees into it), which Windows won't delete
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        os.environ["APPDATA"] = str(tmp / "appdata")
        os.environ["LOCALAPPDATA"] = str(tmp / "localappdata")
        os.environ["USERPROFILE"] = os.environ["HOME"] = str(tmp / "home")
        sys.path[:0] = [str(SOURCEYAW), str(KIT)]
        import yawcore
        expect(yawcore.CONFIG_DIR, tmp / "appdata" / "sourceyaw", "config in %APPDATA%")
        expect({g["colors"] for g in yawcore.GAMES.values()}, {None}, "no crosshair colour on Windows")
        game_dir = fake_game(tmp / "Steam", "Counter-Strike Source")
        yawcore.find_game = lambda game: game_dir if game == "css" else None
        check_launch(yawcore, game_dir)
        check_hub(game_dir)
    print("check_windows: all passed")


if __name__ == "__main__":
    main()
