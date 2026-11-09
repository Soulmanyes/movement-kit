#!/usr/bin/env python3
"""Z Penalty's tone on a real Windows, without a game or a person: the z-penalty-windows CI job runs
it on windows-latest, with the same Python as the hub exe.

Usage: python z-penalty/windows/check_windows.py   (Windows only; exits 1 on the first failure)

Checks what Linux can't: the core's waveOut tone (movekit/tone.py, the Strafe Trainer's player)
opening, playing and closing in time; tone.play for the hub's preview; tone_run.run following
ZPEN_ON/ZPEN_OFF in a log and stopping when told (with the real player, or a silent stand-in when the
runner has no sound device: GitHub's Windows runners have none, so there the waveOut part is left to
the owner's test); and module_hooks.launch starting
the tone runner thread for Momentum (a fake game folder) and not for another game.
"""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent.parent)]  # the kit root
from movekit import modules, tone  # after the path above
from movekit.hub import local_import

HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
KIT = MODULE.parent


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


def check_tone():
    expect(tone.player(), tone.WindowsTone, "tone.player() on Windows")
    player = tone.WindowsTone(tone.ToneSynth(0.0, {"on": 330}))
    if not player.hwo:
        warn("no sound device on this runner: the waveOut tone wasn't played")
        player.close()
        return False
    player.start()
    for mode in ("on", None, "on", None):
        player.mode = mode
        time.sleep(0.15)
    timed("tone close", player.close, 1.5)
    expect(player.thread.is_alive(), False, "tone thread ended")
    print(f"ok   tone played; ran dry {player.dry} times in 0.6 s", flush=True)
    expect(tone.play(0.0, 330, 0.1), True, "tone.play (the hub's preview)")
    time.sleep(0.5)
    return True


class Silent:
    """A stand-in player for a runner with no sound device: same interface, no audio."""

    def __init__(self, synth):
        self.synth, self.mode = synth, None

    def start(self):
        pass

    def close(self):
        pass


def check_run(tmp, base):
    """tone_run.run on Windows (file reads, the session, threads), with the waveOut player when the
    runner has a sound device, else the stand-in."""
    tr = local_import(str(MODULE / "x.py"), "tone_run")
    sett = local_import(str(MODULE / "x.py"), "settings")
    sett.save({"on": True, "pitch": 330, "volume": 0})
    made = []

    class Recorded(base):
        def __init__(self, synth):
            super().__init__(synth)
            made.append(self)

    log = tmp / "yaw.log"
    log.write_text("")
    stop = threading.Event()
    th = threading.Thread(target=tr.run, args=(log, stop, Recorded, 0.002))
    th.start()

    def wait_for(mode, what):
        end = time.monotonic() + 2
        while time.monotonic() < end:
            if made and made[-1].mode == mode:
                return
            time.sleep(0.005)
        fail(f"run: {what}")
    try:
        time.sleep(0.2)
        with log.open("a") as f:
            f.write("[panorama] ZPEN_ON\n")
        wait_for("on", "ZPEN_ON didn't turn the tone on")
        print("ok   run: ZPEN_ON turns the waveOut tone on", flush=True)
        with log.open("a") as f:
            f.write("[panorama] ZPEN_OFF\n")
        wait_for(None, "ZPEN_OFF didn't turn the tone off")
        print("ok   run: ZPEN_OFF turns it off", flush=True)
    finally:
        stop.set()
        th.join(3)
    expect(th.is_alive(), False, "run stops when told")


def check_launch(tmp):
    game_dir = tmp / "Steam" / "steamapps" / "common" / "Momentum Mod Playtest" / "momentum"
    for rel in ("cfg", "panorama/layout/hud", "cfg/hud"):
        (game_dir / rel).mkdir(parents=True, exist_ok=True)
    (game_dir / "panorama/layout/hud/timer.xml").write_text("<root>\n\t<scripts>\n\t</scripts>\n</root>\n")
    (game_dir / "cfg/hud/hud_default.kv3").write_text("{\n    CustomizerSettings = \n    {\n    }\n}")
    os.environ["MOMENTUM_DIR"] = str(game_dir)
    tr = local_import(str(MODULE / "module_hooks.py"), "tone_run")
    started = []
    real = tr.start
    tr.start = lambda argv: started.append(argv) or real(argv)
    hooks = modules.Manager(kit_root=KIT, data=tmp / "mgr")._hooks("z-penalty")
    ctx = modules.Context(MODULE, KIT, modules.read_manifest(MODULE))
    exe = str(game_dir.parent / "momentum.exe")
    hooks.launch(ctx, [exe, "-game", "momentum"])
    expect(len(started), 1, "launch hook starts the tone runner for Momentum")
    expect("con_logfile yaw.log" in (game_dir / "cfg/autoexec.cfg").read_text(), True, "launch hook writes the autoexec block")
    hooks.uninstall(ctx)


def main():
    if sys.platform != "win32":
        sys.exit("Windows only")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        os.environ["APPDATA"] = str(tmp / "appdata")
        os.environ["LOCALAPPDATA"] = str(tmp / "local")
        check_run(tmp, tone.WindowsTone if check_tone() else Silent)
        check_launch(tmp)
    print("check_windows: all passed")


if __name__ == "__main__":
    main()
