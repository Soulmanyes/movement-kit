#!/usr/bin/env python3
"""Checks launch_win.py (the Strafe Trainer's game launch on Windows) on Linux, with temp game
folders, a fake movekit session and a fake trainer platform. Moved out of Source Yaw's
check_launch_win.py with the trainer (Phase 13). HOME and the XDG folders point into a temp folder;
no game, port or input service needed.

Usage: python strafe-trainer/check_launch_win.py   (exits 1 on the first failure)

Covers: the trainer started as a thread for the game Steam's command starts, the autoexec block
written first, the session's events reaching it, everything stopped and closed at exit (input, tone,
session), an error in the trainer landing in run.log, another game and a trainer that is off
starting nothing, and the rollback guard (a Source Yaw with its own trainer.py).
"""
import os
import queue
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
        sys.path[:0] = [str(HERE.parent)]
        sys.modules["PIL"] = None  # the hub exe has no Pillow
        from movekit import games, session
        from movekit.hub import local_import

        launch_win = local_import(str(HERE / "x.py"), "launch_win")
        trainer = local_import(str(HERE / "x.py"), "trainer")
        store = launch_win.store

        common = tmp / "Steam" / "steamapps" / "common"
        dirs = {"css": common / "Counter-Strike Source" / "cstrike", "momentum": common / "Momentum Mod" / "momentum"}
        for d in dirs.values():
            (d / "cfg").mkdir(parents=True)
            (d / "cfg" / "config.cfg").write_text('bind "a" "+moveleft"\nbind "d" "+moveright"\n')
        games.find = dirs.get
        store.save("momentum", {**store.saved("momentum"), "enabled": True, "offset_key": "o"})

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
        exe = str(dirs["momentum"].parent / "momentum.exe")
        threads = launch_win.start([exe], kit=tmp / "kit")
        expect([t.name for t in threads], ["strafe-trainer"], "trainer started")
        autoexec = (dirs["momentum"] / "cfg" / "autoexec.cfg").read_text()
        expect(('bind "o" "sourceyaw_offsets"' in autoexec, "con_logfile yaw.log" in autoexec), (True, True),
               "autoexec block written before the game")
        wait_for(lambda: len(joined) == 1, "the trainer joining the session")
        expect(str(joined[0].log), str(dirs["momentum"] / "yaw.log"), "session log path")
        joined[0].events.put({"type": "token", "data": {"name": "SY_OFFSETS"}})
        wait_for(joined[0].events.empty, "the trainer reading the session's events")

        expect(len(at_exit), 1, "one exit step registered")
        at_exit[0]()  # what atexit runs when the exe exits after the game
        expect([t.is_alive() for t in threads], [False], "trainer stopped at exit")
        expect((joined[0].closed, sorted(closed)), (True, ["input", "tone"]), "closed at exit")
        expect(launch_win.LOG.read_text().rstrip().endswith("strafe-trainer: stopped"), True,
               "run.log ends with the trainer stopped")

        # an error in the trainer lands in run.log, the launch carries on
        trainer.platform = lambda: 1 / 0
        at_exit.clear()
        threads = launch_win.start([exe], kit=tmp / "kit")
        threads[0].join(2)
        log = launch_win.LOG.read_text()
        expect(("strafe-trainer: stopped by an error" in log, "ZeroDivisionError" in log), (True, True), "run.log")
        trainer.platform = Platform

        expect(launch_win.start([r"D:\Games\other.exe"], kit=tmp / "kit"), [], "another game: nothing started")
        # off: the trainer still starts and waits to be switched on, until the exe exits
        at_exit.clear()
        threads = launch_win.start([str(dirs["css"].parent / "hl2.exe")], kit=tmp / "kit")
        expect((len(threads), threads[0].is_alive()), (1, True), "CS:S with the trainer off: started, waiting")
        at_exit[0]()
        expect(threads[0].is_alive(), False, "the waiting trainer stops with the exe")
        (tmp / "kit" / "sourceyaw").mkdir(parents=True)
        (tmp / "kit" / "sourceyaw" / "trainer.py").write_text("")
        expect(launch_win.start([exe], kit=tmp / "kit"), [], "a Source Yaw with its own trainer: nothing started")
    print("check_launch_win: all passed")


if __name__ == "__main__":
    main()
