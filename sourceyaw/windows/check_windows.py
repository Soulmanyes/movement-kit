#!/usr/bin/env python3
"""Source Yaw's Windows code on a real Windows, without a game or a person: the sourceyaw-windows
CI job (Phase 12 in PLAN.md) runs it on windows-latest, with the same Python as the hub exe.

Usage: python sourceyaw/windows/check_windows.py   (Windows only; exits 1 on the first failure)

Checks what Linux can't: the Win32 struct layouts with the real wintypes; Raw Input's hidden
window starting, getting keys and mouse injected with SendInput as evdev events, and closing in
time (twice, as a second launch in one process would); the waveOut tone opening, playing and
closing; the focus check running; trainer.run with the Windows platform stopping when told;
launch_win through module_hooks.launch (yaws.cfg without colour, helpers started and stopped);
and the hub section loading on Windows with the trainer status and the tone preview.

If SendInput's input doesn't reach Raw Input (a runner without an interactive desktop), that part
gives a ::warning:: instead of failing: the owner's own test on Windows covers it then.
"""
import ctypes
import os
import sys
import tempfile
import threading
import time
import types
from ctypes import wintypes
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


def warn(msg):
    print(f"::warning::{msg}", flush=True)


def timed(what, fn, limit):
    start = time.perf_counter()
    result = fn()
    took = time.perf_counter() - start
    if took > limit:
        fail(f"{what} took {took:.2f} s (limit {limit} s)")
    print(f"ok   {what} in {took * 1000:.0f} ms", flush=True)
    return result


# ---------------------------------------------------------------- SendInput

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 32)]
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_SCANCODE, KEYEVENTF_KEYUP = 0x0008, 0x0002
MOUSEEVENTF_MOVE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0001, 0x0002, 0x0004


def send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    return ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def key(scan, up=False):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
    return INPUT(INPUT_KEYBOARD, INPUT._U(ki=KEYBDINPUT(0, scan, flags, 0, 0)))


def mouse(flags, dx=0):
    return INPUT(INPUT_MOUSE, INPUT._U(mi=MOUSEINPUT(dx, 0, 0, flags, 0, 0)))


def collect(source, want, seconds=2.0):
    """Events read until every (type, code, value) in `want` came, or `seconds` passed."""
    got, end = [], time.monotonic() + seconds
    while time.monotonic() < end and not all(any(e[1:] == w for e in got) for w in want):
        got += source.read(0.05) or []
    return got


# ---------------------------------------------------------------- the checks

def check_raw_input(trainer_win):
    for attempt in (1, 2):  # a second launch step in one process registers a new window class
        source = timed(f"Raw Input start #{attempt}", trainer_win.RawInput, 2)
        sent = send(key(0x1E), key(0x1E, up=True), mouse(MOUSEEVENTF_MOVE, 7),
                    mouse(MOUSEEVENTF_LEFTDOWN), mouse(MOUSEEVENTF_LEFTUP))
        want = [(1, 30, 1), (1, 30, 0), (1, 272, 1), (1, 272, 0)]
        got = collect(source, want)
        if sent != 5:
            warn(f"SendInput sent {sent} of 5 inputs (error {ctypes.get_last_error()})")
        elif not got:
            warn("injected input didn't reach Raw Input on this runner; the owner's test covers it")
        else:
            missing = [w for w in want if not any(e[1:] == w for e in got)]
            if missing:
                fail(f"Raw Input #{attempt}: missing {missing} in {got}")
            moves = [e for e in got if e[1:3] == (2, 0)]
            print(f"ok   Raw Input #{attempt}: key A and mouse1 as evdev events, "
                  f"{len(moves)} move(s) {[e[3] for e in moves]}", flush=True)
            times = [e[0] for e in got]
            expect(times == sorted(times) and abs(times[-1] - time.perf_counter()) < 5, True,
                   "event times from perf_counter, in order")
        timed(f"Raw Input close #{attempt}", source.close, 1.5)
        expect(source.thread.is_alive(), False, f"Raw Input thread #{attempt} ended")
        expect(source.read(0.01), None, f"read() after close #{attempt}: gone")


def check_tone(trainer, trainer_win):
    tone = trainer_win.Tone(trainer.ToneSynth(0.0, {"wrong": 220, "overlap": 110}))
    if not tone.hwo:
        warn("no sound device on this runner: the waveOut tone wasn't played")
        tone.close()
        return
    tone.start()
    for mode in ("wrong", None, "overlap", "wrong", None):
        tone.mode = mode
        time.sleep(0.15)
    timed("tone close", tone.close, 1.5)
    expect(tone.thread.is_alive(), False, "tone thread ended")
    print(f"ok   tone played; ran dry {tone.dry} times in 0.75 s", flush=True)


def fake_game(root, name):
    game_dir = root / "steamapps" / "common" / name / ("cstrike" if name.startswith("Counter") else "momentum")
    (game_dir / "cfg").mkdir(parents=True)
    (game_dir / "cfg" / "config.cfg").write_text('bind "SPACE" "+jump"\nbind "a" "+moveleft"\n'
                                                 'bind "d" "+moveright"\nbind "MOUSE1" "+left"\n')
    return game_dir


def check_trainer_run(trainer, trainer_win, yawcore, game_dir):
    focus = trainer_win.Focus(game_dir)
    time.sleep(0.4)
    expect(focus.focused, False, "focus: the runner's foreground isn't the game")
    focus.stopped.set()
    orig = trainer.settings
    trainer.settings = lambda game: {**orig(game), "enabled": True, "tone_volume": 0.0}
    try:
        stop = threading.Event()
        threading.Timer(1.5, stop.set).start()
        code = timed("trainer.run with the Windows platform, stopped after 1.5 s",
                     lambda: trainer.run("css", trainer.platform(), stop), 4)
        expect(code, 0, "trainer.run returns 0 when stopped")
    finally:
        trainer.settings = orig


def check_launch(yawcore, game_dir):
    import module_hooks
    data = yawcore.load_settings("css")
    data.update(trainer={**(data.get("trainer") or {}), "enabled": True, "tone_volume": 0.05})
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
    expect("sourceyaw-trainer" in [t.name for t in threading.enumerate()], True, "launch: trainer thread running")
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
    status = call("trainer_status", game="css")
    expect((status["installed"], status["binds"]), (True, "Strafe, turn and jump keys come from your binds in the game"),
           "hub: trainer status")
    expect(call("play_cue", game="css", sound="tone", tone_volume=5, pitch=220), True, "hub: tone preview")
    time.sleep(0.8)


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
        import trainer
        import trainer_win
        import yawcore
        expect(yawcore.CONFIG_DIR, tmp / "appdata" / "sourceyaw", "config in %APPDATA%")
        expect({g["colors"] for g in yawcore.GAMES.values()}, {None}, "no crosshair colour on Windows")
        sizes = {s.__name__: ctypes.sizeof(s) for s in (trainer_win.RAWINPUTHEADER, trainer_win.RAWMOUSE,
                                                         trainer_win.RAWKEYBOARD, trainer_win.RAWINPUT,
                                                         trainer_win.RAWINPUTDEVICE, trainer_win.WAVEHDR)}
        expect(sizes, {"RAWINPUTHEADER": 24, "RAWMOUSE": 24, "RAWKEYBOARD": 16, "RAWINPUT": 48,
                       "RAWINPUTDEVICE": 16, "WAVEHDR": 48}, "struct sizes, 64-bit Windows")
        expect(type(trainer.platform()).__name__, "Windows", "trainer.platform() on Windows")
        game_dir = fake_game(tmp / "Steam", "Counter-Strike Source")
        yawcore.find_game = lambda game: game_dir if game == "css" else None
        check_raw_input(trainer_win)
        check_tone(trainer, trainer_win)
        check_trainer_run(trainer, trainer_win, yawcore, game_dir)
        check_launch(yawcore, game_dir)
        check_hub(game_dir)
    print("check_windows: all passed")


if __name__ == "__main__":
    main()
