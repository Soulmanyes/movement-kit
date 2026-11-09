#!/usr/bin/env python3
"""Checks the Strafe Trainer hub section (strafe-trainer/hub_section.py) without a window. Moved out
of Source Yaw's check_hub_section.py with the trainer (Phase 13).

Usage: python strafe-trainer/check_hub_section.py   (exits 1 on the first failure)

Covers: discovery finding the section on Linux and on Windows without a problem, loading nothing
of its own with hub_section.py; no bare trainer, store or settings_api left behind, also after a
call that loads the trainer; load() for both games (cue sound choices, Momentum's tickrate from the
map); Apply keeping the numbers in the page's ranges, an empty cue sound becoming the tone, a bad
colour refused; the tone and Show in game with only the sound device and overlay faked. Then
Windows, faked on Linux: no input service, keys with no Raw Input code, Show in game off.
Everything runs in a temp folder: HOME and the XDG folders point there, the games are fake folders.
"""
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
KEY = "strafe-trainer"
BARE = ("trainer", "store", "settings_api", "gamecfg", "trainer_linux")


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for var, sub in (("HOME", "home"), ("XDG_CONFIG_HOME", "home/.config"),
                         ("XDG_DATA_HOME", "home/.local/share"), ("XDG_CACHE_HOME", "home/.cache")):
            os.environ[var] = str(tmp / sub)
        dirs = {"css": tmp / "steam/Counter-Strike Source/cstrike",
                "momentum": tmp / "steam/Momentum Mod Playtest/momentum"}
        for folder in dirs.values():
            (folder / "cfg").mkdir(parents=True)
            (folder / "cfg/config.cfg").write_text('bind "a" "+moveleft"\nbind "d" "+moveright"\n')

        sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
        sys.path.insert(0, str(KIT))
        from movekit import games, hub
        games.find = dirs.get

        sections, problems = hub.discover(KIT)
        expect([p for p in problems if p[0] == KEY], [], "problems on Linux")
        if KEY not in [s.key for s in sections]:
            fail("discovery didn't find the strafe-trainer section")
        prefix = hub._module_name(HERE, "")
        loaded = sorted(m for m in sys.modules if m.startswith(prefix) and not m.endswith(".hub_section"))
        expect(loaded, [], "modules loaded with hub_section.py")
        win, win_problems = hub.discover(KIT, platform="win32")
        expect([p for p in win_problems if p[0] == KEY], [], "problems on Windows")
        expect(KEY in [s.key for s in win], True, "listed on Windows")
        bridge = hub.Bridge(sections, problems)

        def call(name, **args):
            got = bridge.call(KEY, name, args)
            if not got["ok"]:
                fail(f"{name}: {got['error']}")
            return got["result"]

        # the module the bridge calls into (the Windows discovery above loaded its own copy)
        section = types.SimpleNamespace(globals=next(s for s in sections if s.key == KEY).api["load"].__globals__)
        api = hub.local_import(HERE / "hub_section.py", "settings_api")
        store = api.store

        # ------------------------------------------------------------ load
        st = call("load", game="css")
        expect((st["game"], st["found"], st["problem"]), ("css", True, None), "load css")
        expect([g["id"] for g in st["games"]], ["css", "momentum"], "installed games")
        expect(st["cue_sounds"][0], ["tone", "Constant tone"], "first cue choice")
        expect(st["trainer"]["tickrate"], 66, "CS:S tickrate")
        call("trainer_status", game="css")  # loads trainer.py
        expect([m for m in BARE if m in sys.modules], [], "bare modules after loading the trainer")
        mom = call("load", game="momentum")
        expect(mom["trainer"]["tickrate"], None, "Momentum: tickrate from the map")

        # ------------------------------------------------------------ ranges
        def form_of(st):
            return json.loads(json.dumps(st["trainer"]))

        f = form_of(st)
        f.update(x=-5, y=250, size=1, wrong_ticks=99, repeat=3, tone_volume=0, wrong_pitch=5000,
                 none_ticks=50, none_pitch=1, overlap_ticks=0, overlap_pitch=9, target=-9,
                 tickrate=500, none_sound="")
        expect(call("apply", game="css", form=f)["saved"], True, "apply out-of-range numbers")
        t = store.config("css")
        expect((t["x"], t["y"], t["size"], t["wrong_ticks"], t["repeat"], t["tone_volume"], t["wrong_pitch"],
                t["none_ticks"], t["none_pitch"], t["overlap_ticks"], t["overlap_pitch"], t["target"],
                t["tickrate"]["css"]),
               (0, 1, 10, 20, 1, 0.05, 1000, 20, 60, 1, 60, -5, 128), "numbers clamped")
        expect(t["none_sound"], "tone", "an empty cue sound becomes the tone")
        f = form_of(st)
        f["colors"]["late"] = "yellow"
        expect(call("apply", game="css", form=f)["saved"], False, "bad colour")
        f = form_of(st)
        f["x"] = None
        expect(call("apply", game="css", form=f)["saved"], False, "blank number")

        # ------------------------------------------------------------ the tone and Show in game
        trainer = api._trainer()
        tones = []

        class FakeTone:
            def __init__(self, synth):
                self.modes, self.closed = [], False
                tones.append(((synth.volume, synth.pitches), self))

            def start(self):
                pass

            def __setattr__(self, name, value):
                if name == "mode":
                    self.modes.append(value)
                object.__setattr__(self, name, value)

            def close(self):
                self.closed = True

        # the real platform (trainer_linux, loaded by path as in the hub) with only its tone faked
        platform = trainer.platform()
        expect(type(platform).__name__, "Linux", "the hub's trainer finds its platform")
        type(platform).Tone = FakeTone
        expect(call("play_cue", game="css", sound="tone", tone_volume=45, pitch=330), True, "play the tone")
        time.sleep(0.8)
        (args, tone), = tones
        expect((args, tone.modes, tone.closed), ((0.45, {"cue": 330}), ["cue", None], True), "tone played")
        tones.clear()
        expect(call("play_cue", game="css", sound="tone", tone_volume=45, pitch=5), True, "pitch clamped")
        time.sleep(0.8)
        expect(tones[0][0], (0.45, {"cue": 60}), "pitch clamped to 60")
        expect(call("play_cue", game="css", sound="", tone_volume=45, pitch=330), True, "no sound plays nothing")
        shown = []

        class FakeOverlay:
            def show(self, text, row, x, y):
                shown.append((text, row, x, y))

            def hide(self):
                shown.append("hidden")

        linux = hub.local_import(HERE / "hub_section.py", "trainer_linux")
        linux.Overlay = FakeOverlay
        linux.write_atlas = lambda cfg: shown.append(("atlas", cfg["size"]))
        tr = dict(st["trainer"], target=2, x=25, y=75, size=40)
        expect(call("show_in_game", on=True, game="css", trainer=tr), True, "show in game")
        expect(call("show_in_game", on=False, game="css", trainer=tr), False, "hide in game")
        expect(shown, [("atlas", 40), ("+2", 1, 0.25, 0.75), "hidden"], "overlay")

        expect([m for m in BARE if m in sys.modules], [], "bare modules at the end")
        check_windows(call, section, api, dirs, st)
    print("ok: strafe-trainer hub section")


def check_windows(call, section, api, dirs, st):
    """The section as Windows sees it, faked on Linux: the WINDOWS switches."""
    section.globals["WINDOWS"] = api.WINDOWS = True
    status = call("trainer_status", game="css")
    expect((status["installed"], status["service"], status["command"]), (True, "", ""),
           "Windows: no input service")
    (dirs["css"] / "cfg/config.cfg").write_text('bind "SPACE" "+jump"\nbind "F13" "+moveleft"\n')
    expect(call("trainer_status", game="css")["binds"],
           "⚠ The Strafe Trainer can't read these keys on Windows: f13 (strafe left)", "Windows: keys with no code")
    expect(call("show_in_game", on=True, game="css", trainer=st["trainer"]), False, "Windows: no Show in game")
    expect(call("load", game="css")["windows"], True, "Windows: load says so")


if __name__ == "__main__":
    main()
