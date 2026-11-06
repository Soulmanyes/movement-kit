#!/usr/bin/env python3
"""Checks launch_win.py (Source Yaw's game launch on Windows, Phase 12 in PLAN.md) on Linux, with
Windows' "no crosshair colour" switched on, temp game folders, a fake movekit session and a fake
trainer platform. HOME and the XDG folders point into a temp folder; no game or port needed.

Usage: python sourceyaw/check_launch_win.py   (exits 1 on the first failure)

Covers: which game Steam's command starts (exe folder, -game, neither), yaws.cfg written without
colour lines, the list switcher and trainer started as threads that get the session's events,
everything stopped and cleaned up at exit, all without Pillow (auto cfg cleared, sessions and input closed), a thread's
error landing in run.log, another game left alone, and a real launcher process exiting
right after the game, through atexit.
"""
import os
import queue
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def wait_for(test, what, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if test():
            return
        time.sleep(0.02)
    fail(f"timed out waiting for {what}")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        os.environ.update(HOME=str(tmp), XDG_CONFIG_HOME=f"{tmp}/config", XDG_DATA_HOME=f"{tmp}/data",
                          XDG_CACHE_HOME=f"{tmp}/cache")
        sys.path.insert(0, str(HERE))
        sys.modules["PIL"] = None  # the hub exe has no Pillow
        import launch_win  # noqa: I001, RUF100 - movekit after yawcore, which puts it on the path
        import mode_watch
        import trainer
        import yawcore

        from movekit import session

        for game in yawcore.GAMES.values():  # as on Windows
            game["colors"] = None
        common = tmp / "Steam" / "steamapps" / "common"
        dirs = {"css": common / "Counter-Strike Source" / "cstrike", "momentum": common / "Momentum Mod" / "momentum"}
        for d in dirs.values():
            (d / "cfg").mkdir(parents=True)
        yawcore.find_game = dirs.get

        # which game Steam starts
        css_exe = str(dirs["css"].parent / "cstrike_win64.exe").upper().replace("/", "\\")
        expect([launch_win.game_of([css_exe]),
                launch_win.game_of([str(dirs["momentum"].parent / "bin" / "win64" / "momentum.exe"), "-novid"]),
                launch_win.game_of([r"D:\Other\hl2.exe", "-game", r"D:\Other\cstrike"]),
                launch_win.game_of([r"D:\Other\hl2.exe", "-game"]),
                launch_win.game_of([r"D:\Games\other.exe"]), launch_win.game_of([])],
               ["css", "momentum", "css", None, None, None], "game from Steam's command")

        # Momentum with a surf list, auto mode and the trainer
        speeds = [{"speed": s, "color": "#ff0000", "sound": None} for s in (60, 90, 210)]
        data = {**yawcore.load_settings("momentum"), "key": "q", "entries": speeds, "start": 0,
                "surf": {"entries": speeds[:2], "start": 0}, "separate": True, "mode_key": "g",
                "auto_mode": True, "map_modes": {"surf_": "surf", "bhop_": "bhop"},
                "trainer": {"enabled": True}}
        expect(yawcore.validate(data), [], "settings valid")
        yawcore.save_settings(data, "momentum")

        joined = []

        class FakeJoined:
            mode = "fake"

            def __init__(self, log, port=None):
                self.log, self.events, self.closed = log, queue.SimpleQueue(), False
                joined.append(self)

            def close(self):
                self.closed = True

        session.join = FakeJoined
        closed = []

        class Source:
            def read(self, timeout):
                time.sleep(timeout)
                return []

            def close(self):
                closed.append("input")

        class Platform:
            FORWARDED_ONLY = False
            UNSEEN, GONE = "keys with no code", "input gone"
            clock = staticmethod(time.time)

            class Tone:
                def __init__(self, synth):
                    self.mode = None

                def start(self):
                    pass

                def close(self):
                    closed.append("tone")

            def overlay(self, cfg):
                return None

            def open_input(self):
                return Source()

            def focus(self, game, game_dir):
                return type("Focus", (), {"focused": True})()

            def play(self, game_dir, sound, game):
                pass

        trainer.platform = Platform
        # the exit step, captured: atexit._run_exitfuncs would also delete the temp folder
        at_exit = []
        launch_win.atexit = type("AtExit", (), {"register": staticmethod(at_exit.append)})
        threads = launch_win.start([str(dirs["momentum"].parent / "momentum.exe")])
        expect(sorted(t.name for t in threads), ["sourceyaw-mode", "sourceyaw-trainer"], "helpers started")
        cfg = (dirs["momentum"] / "cfg" / "yaws.cfg").read_text()
        expect(("yaws_colors" in cfg, "// play is a local-only sound cue.\n" in cfg, "con_logfile yaw.log" in cfg),
               (False, True, True), "yaws.cfg without colour, with the console log")
        wait_for(lambda: len(joined) == 2, "both helpers joining the session")
        expect({str(j.log) for j in joined}, {str(dirs["momentum"] / "yaw.log")}, "session log path")
        auto = dirs["momentum"] / "cfg" / f"{yawcore.AUTO_CFG}.cfg"
        for j in joined:
            j.events.put({"type": "map_loaded", "data": {"name": "surf_utopia"}})
        wait_for(lambda: auto.exists() and auto.read_text().strip(), "the list switcher arming surf")

        expect(len(at_exit), 1, "one exit step registered")
        at_exit[0]()  # what atexit runs when the exe exits after the game
        expect([t.is_alive() for t in threads], [False, False], "helpers stopped at exit")
        expect((auto.read_text().strip(), [j.closed for j in joined], sorted(closed)),
               ("", [True, True], ["input", "tone"]), "cleaned up at exit")

        # a helper's error lands in run.log
        broken = launch_win._thread("broken", lambda: 1 / 0)
        broken.join(2)
        log = launch_win.LOG.read_text()
        expect(("broken: stopped by an error" in log, "ZeroDivisionError" in log, "Momentum Mod started with" in log),
               (True, True, True), "run.log")
        expect(launch_win.start([r"D:\Games\other.exe"]), [], "another game: nothing started")
        expect(mode_watch.session is session, True, "mode_watch shares the session module")

        # the real exit order: Python waits for non-daemon threads before atexit, so a helper that
        # isn't a daemon would keep the launcher (and Steam's "running") alive after the game
        data["trainer"] = {"enabled": False}  # the real trainer would need a real input service
        yawcore.save_settings(data, "momentum")
        auto.write_text("sourceyaw_arm_surf\n")
        script = tmp / "launch.py"
        script.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            "sys.modules['PIL'] = None\n"
            f"sys.path.insert(0, {str(HERE)!r})\n"
            "import launch_win, yawcore\n"
            "for g in yawcore.GAMES.values():\n"
            "    g['colors'] = None\n"
            f"yawcore.find_game = lambda g: Path({str(dirs['momentum'])!r}) if g == 'momentum' else None\n"
            f"launch_win.start([{str(dirs['momentum'].parent / 'momentum.exe')!r}])\n"
            "import time; time.sleep(0.5)  # the game, briefly\n")
        env = {**os.environ, "MOVEKIT_SESSION_PORT": "8797"}
        started = time.monotonic()
        try:
            done = subprocess.run([sys.executable, str(script)], env=env, timeout=10, check=False,
                                  capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            fail("the launcher didn't exit after the game: a helper thread keeps it alive")
        expect(done.returncode, 0, f"launcher exit code ({done.stderr[-300:]})")
        expect(time.monotonic() - started < 8, True, "launcher exits soon after the game")
        expect(auto.read_text(), "", "auto cfg cleared at the real exit")
        expect(launch_win.LOG.read_text().rstrip().endswith("sourceyaw: helpers stopped"), True,
               "run.log ends with the helpers stopped")
    print("check_launch_win: all passed")


if __name__ == "__main__":
    main()
