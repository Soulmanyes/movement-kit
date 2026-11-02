#!/usr/bin/env python3
"""Checks Source Yaw's use of the movekit session on temp files and local ports; no game needed.

Usage: python sourceyaw/check_session_use.py   (exits 1 on the first failure)

Covers the trainer's GameEvents (offsets toggle, map tickrate by prefix, CS:S's
nameless map line, menu and map) and crosshair_watch.py against a live log: a token without its
line break swaps the crosshair, chat and unknown speeds don't, and it still works while the
session port serves another log.
"""
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crosshair_watch  # noqa: I001 - before movekit: yawcore (imported by both) puts it on the path
import trainer

from movekit import session  # trainer put movekit on the path


def check(what, got, want):
    if got != want:
        sys.exit(f"FAIL {what}: got {got!r}, want {want!r}")
    print(f"ok   {what}")


def ev(kind, **data):
    return {"type": kind, "data": data}


def check_game_events():
    cfg = {"map_tickrates": {"surf_": 66, "bhop_": 100}, "tickrate": {"css": 66}}
    g = trainer.GameEvents(cfg, "css", 66, in_map=False, showing=True)
    g.handle(ev("token", name="SY_OFFSETS"))
    check("offsets toggle hides", g.showing, False)
    g.handle(ev("token", name="SY_OFFSETS"))
    check("and shows again", g.showing, True)
    g.handle(ev("token", name="YAW_210"))
    check("other tokens leave it", g.showing, True)
    g.handle(ev("map_loaded", name="bhop_eazy"))
    check("bhop_ map: in a map at 100 tick", (g.in_map, g.tickrate), (True, 100))
    g.handle(ev("map_loaded", name=None))
    check("CS:S nameless map line keeps the tickrate", (g.in_map, g.tickrate), (True, 100))
    g.handle(ev("map_loaded", name="de_dust2"))
    check("other map: the game's tickrate", g.tickrate, 66)
    g.handle(ev("map_left"))
    check("menu", g.in_map, False)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def write(path, data):
    with open(path, "ab") as f:
        f.write(data)


def wait_for(cond, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def check_crosshair(tmp, port, what):
    tmp = Path(tmp)
    img, current, log = tmp / "img", tmp / "current.png", tmp / "yaw.log"
    img.mkdir()
    for speed in ("YAW_90", "YAW_210"):
        (img / f"{speed}.png").write_bytes(speed.encode())
    current.write_bytes(b"start")
    log.write_bytes(b"")
    threading.Thread(target=crosshair_watch.run, args=(log, img, current, port), daemon=True).start()
    time.sleep(0.5)  # let it join and reach the end of the log
    write(log, b"YAW_210 ")  # the echo, no line break yet
    check(f"{what}: token without a line break swaps", wait_for(lambda: current.read_bytes() == b"YAW_210"), True)
    write(log, b"\nBob :  YAW_90 hi\nYAW_300 \n")
    time.sleep(0.5)
    check(f"{what}: chat and an unknown speed leave it", current.read_bytes(), b"YAW_210")
    write(log, b"YAW_90 YAW_210 YAW_90 ")
    check(f"{what}: run-together echoes end on the last", wait_for(lambda: current.read_bytes() == b"YAW_90"), True)
    check(f"{what}: no temp file left", sorted(p.name for p in tmp.iterdir()), ["current.png", "img", "yaw.log"])


def main():
    check_game_events()
    with tempfile.TemporaryDirectory() as tmp:
        check_crosshair(tmp, free_port(), "hosting")
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
        port = free_port()
        other_log = Path(other) / "momentum.log"
        other_log.write_bytes(b"")
        got = session.start(other_log, port=port)  # Strafe Review serving Momentum's log
        check_crosshair(tmp, port, "port serves another log")
        got[0].stop.set()
        got[1].shutdown()
    print("all session-use checks passed")


if __name__ == "__main__":
    main()
