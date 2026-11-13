#!/usr/bin/env python3
"""Checks the Strafe Trainer's GameEvents: what movekit session events mean for it. No game needed.
Moved out of Source Yaw's check_session_use.py with the trainer (Phase 13).

Usage: python strafe-trainer/check_game_events.py   (exits 1 on the first failure)

Covers the offsets toggle (SY_OFFSETS, the token kept from Source Yaw), the map tickrate by prefix,
CS:S's nameless map line, menu and map, Momentum's pause menu.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]
from movekit.hub import local_import  # after the kit root is on the path

trainer = local_import(str(HERE / "x.py"), "trainer")


def check(what, got, want):
    if got != want:
        sys.exit(f"FAIL {what}: got {got!r}, want {want!r}")
    print(f"ok   {what}")


def ev(kind, **data):
    return {"type": kind, "data": data}


def main():
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
    check("playing in a map", g.playing, True)
    g.handle(ev("menu_shown"))
    check("pause menu: still in the map, not playing", (g.in_map, g.playing), (True, False))
    g.handle(ev("menu_hidden"))
    check("pause menu closed: playing again", g.playing, True)
    g.handle(ev("menu_shown"))
    g.handle(ev("map_loaded", name="surf_mesa"))
    check("a map load clears a lost menu_hidden", g.playing, True)
    g.handle(ev("menu_shown"))
    g.handle(ev("map_left"))
    check("menu", (g.in_map, g.menu, g.playing), (False, False, False))
    print("all game event checks passed")


if __name__ == "__main__":
    main()
