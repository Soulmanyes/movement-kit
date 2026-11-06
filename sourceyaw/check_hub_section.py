#!/usr/bin/env python3
"""Checks the Source Yaw hub section (sourceyaw/hub_section.py) without a window.

Usage: python sourceyaw/check_hub_section.py   (exits 1 on the first failure)

Covers: discovery finding the section on Linux and leaving it out on Windows without a problem
(hub_section.py loads on every OS); no bare yawcore, trainer or settings_api left behind, also after
a call that loads the trainer; load() for both games; the key maps giving only bind names CS:S
knows; the key, offset-key and launch-option notes in the retired GTK window's words; previews as 33x33 PNG data
URLs; the form's numbers kept in the window's ranges and a blank box or a bad colour refused;
new_entry; set_autoexec; sounds, the tone, Show in game, KROSSHAIR's install and the file dialog
with their side effects stubbed; and Apply writing byte-identical files to the GTK window's way
(settings_api.collect + yawcore.apply with its rounding; the window retired in 3.8, the files must
not change), for both games.
Everything runs in a temp folder: HOME and the XDG folders point there, the games are fake folders.
"""
import base64
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import types
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
BARE = ("yawcore", "trainer", "settings_api", "app")


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def tree_hashes(*folders):
    out = {}
    for folder in folders:
        for f in sorted(Path(folder).rglob("*")):
            if f.is_file():
                out[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def restore(snapshot, folder):
    shutil.rmtree(folder, ignore_errors=True)
    shutil.copytree(snapshot, folder)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for var, sub in (("HOME", "home"), ("XDG_CONFIG_HOME", "home/.config"),
                         ("XDG_DATA_HOME", "home/.local/share"), ("XDG_CACHE_HOME", "home/.cache")):
            os.environ[var] = str(tmp / sub)
        games = {"css": tmp / "steam/Counter-Strike Source/cstrike",
                 "momentum": tmp / "steam/Momentum Mod Playtest/momentum"}
        for game, folder in games.items():
            (folder / "cfg").mkdir(parents=True)
            (folder / "cfg/config.cfg").write_text('bind "1" "say hi"\nbind "q" "yaw_cycle"\n')
            if game == "momentum":
                (folder / "cfg/config.cfg").write_text('bind "1" "say hi"\ncl_crosshair_color "10 20 30 255"\n')
        (games["css"] / "cfg/autoexec.cfg").write_text('bind "e" "+use"\n')

        sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
        sys.path.insert(0, str(KIT))
        from movekit import hub

        sections, problems = hub.discover(KIT)
        expect([p for p in problems if p[0] == "sourceyaw"], [], "sourceyaw problems on Linux")
        if "sourceyaw" not in [s.key for s in sections]:
            fail("discovery didn't find the sourceyaw section")
        # hub_section.py loads on every OS, so loading it must import nothing past the standard library
        loaded = sorted(m for m in sys.modules if m.startswith("movekit_section_sourceyaw.")
                        and m != "movekit_section_sourceyaw.hub_section")
        expect(loaded, [], "modules loaded with hub_section.py")
        expect("PIL" in sys.modules, False, "Pillow loaded with the sections")
        win, win_problems = hub.discover(KIT, platform="win32")
        expect([p for p in win_problems if p[0] == "sourceyaw"], [], "sourceyaw problems on Windows")
        expect("sourceyaw" in [s.key for s in win], False, "sourceyaw listed on Windows")
        bridge = hub.Bridge(sections, problems)

        def call(name, **args):
            got = bridge.call("sourceyaw", name, args)
            if not got["ok"]:
                fail(f"{name}: {got['error']}")
            return got["result"]

        api = hub.local_import(HERE / "hub_section.py", "settings_api")
        core = api.core
        core.find_game = lambda game: games[game]
        core.flatpak_steam_only = lambda game="css": False

        # ------------------------------------------------------------ load
        st = call("load", game="css")
        expect((st["game"], st["found"], st["problem"], st["uses_krosshair"]), ("css", True, None, True),
               "load css")
        expect([g["id"] for g in st["games"]], ["css", "momentum"], "installed games")
        expect(st["key"], "q", "default key")
        expect(len(st["previews"]), len(st["entries"]), "a preview per yawspeed")
        expect(st["autoexec"], False, "autoexec off at first")
        expect(st["sounds"][0], ["", "None"], "first sound choice")
        expect(st["cue_sounds"][0], ["tone", "Constant tone"], "first cue choice")
        expect(st["launch"]["note"].startswith("Couldn't read your Steam launch options"), True, "launch note")
        call("trainer_status", game="css")  # loads trainer.py, which imports yawcore by name
        expect([m for m in BARE if m in sys.modules], [], "bare modules after loading the trainer")
        mom = call("load", game="momentum")
        expect((mom["uses_krosshair"], mom["krosshair"], mom["trainer"]["tickrate"]), (False, None, None),
               "load momentum")
        expect(mom["entries"][0]["color"], "#0a141e", "Momentum starts from the game's crosshair colour")

        # ------------------------------------------------------------ keys and notes
        keys = call("keys")
        valid = set(keys["valid"])
        expect(valid, core.VALID_KEYS, "the fallback list is every bind name")
        expect(sorted(v for v in [*keys["codes"].values(), *keys["mouse"].values()] if v not in valid), [],
               "mapped names CS:S doesn't know")
        expect(keys["codes"]["Digit1"], "1", "Digit1")
        expect(keys["codes"]["NumpadEnter"], "kp_enter", "NumpadEnter")
        expect(keys["mouse"]["3"], "mouse4", "mouse button 3")
        notes = call("key_notes", game="css", key="1", offset_key="q")
        expect(notes["key"], {"text": "⚠ 1 is bound to say hi now. Apply replaces that", "warn": True},
               "cycle key bound to something else")
        expect(notes["offset"]["text"].startswith("In game, each press"), True, "offset key bound to yaw_cycle")
        notes = call("key_notes", game="css", key="e", offset_key="E")
        expect(notes["key"]["text"], "⚠ e is bound to +use now. Apply replaces that, but the bind in "
               "autoexec.cfg may still win if it comes after exec yaws.cfg", "autoexec conflict")
        expect(notes["offset"]["text"], "⚠ E is also the cycle key, so it stays the cycle key. Pick another key",
               "offset key equals cycle key")
        expect(call("key_notes", game="css", key="q", offset_key="1")["offset"]["text"],
               "⚠ 1 is bound to say hi now. Apply replaces that", "offset key bound")
        expect(call("key_notes", game="css", key="q", offset_key="")["key"]["warn"], False, "q is ours")

        # ------------------------------------------------------------ previews and entries
        urls = call("previews", game="css", base="builtin", colors=["#ff0000", "#00ff00"])
        expect(len(urls), 2, "previews")
        from PIL import Image
        im = Image.open(io.BytesIO(base64.b64decode(urls[0].split(",", 1)[1]))).convert("RGBA")
        expect(im.size, (33, 33), "preview size")
        expect({p[:3] for p in core._pixels(im) if p[3]}, {(255, 0, 0)}, "preview colour")
        bad = bridge.call("sourceyaw", "previews", {"game": "css", "base": "builtin", "colors": ["red"]})
        expect(bad["ok"], False, "a colour name refused")
        expect(call("new_entry", entries=[{"speed": 210.5}]), {"speed": 270.5, "color": "#00aaff", "sound": ""},
               "new entry")
        expect(call("new_entry", entries=[])["speed"], 150, "new entry with none")

        # ------------------------------------------------------------ ranges
        def form_of(st):
            return json.loads(json.dumps({"key": st["key"], "crosshair": st["crosshair"], "start": st["start"],
                                          "base": st["base"], "entries": st["entries"], "trainer": st["trainer"]}))

        f = form_of(st)
        f["entries"][0]["speed"] = 5000
        f["trainer"].update(x=-5, y=250, size=1, wrong_ticks=99, repeat=3, tone_volume=0, wrong_pitch=5000,
                            none_ticks=50, none_pitch=1, overlap_ticks=0, overlap_pitch=9, target=-9,
                            tickrate=500, none_sound="")
        got = call("settings", game="css", form=f)
        t = got["trainer"]
        expect(got["entries"][0]["speed"], 2000, "speed clamped")
        expect((t["x"], t["y"], t["size"], t["wrong_ticks"], t["repeat"], t["tone_volume"], t["wrong_pitch"],
                t["none_ticks"], t["none_pitch"], t["overlap_ticks"], t["overlap_pitch"], t["target"],
                t["tickrate"]["css"]),
               (0, 1, 10, 20, 1, 0.05, 1000, 20, 60, 1, 60, -5, 128), "trainer clamped")
        expect(t["none_sound"], "tone", "an empty cue sound becomes the tone")
        f = form_of(st)
        f["entries"][1]["speed"] = None
        expect(call("apply", game="css", form=f), {"saved": False, "messages": ["speed needs a number"]},
               "blank speed")
        f = form_of(st)
        f["trainer"]["colors"]["late"] = "yellow"
        expect(call("apply", game="css", form=f)["saved"], False, "bad trainer colour")
        f = form_of(st)
        f["start"] = 7
        expect(call("settings", game="css", form=f)["start"], 0, "start out of range")
        f = form_of(st)
        f["entries"][1]["speed"] = f["entries"][0]["speed"]
        expect(call("apply", game="css", form=f), {"saved": False, "messages": ["Each yawspeed must be different"]},
               "validate")

        # ------------------------------------------------------------ autoexec
        expect(call("set_autoexec", game="css", on=True)["ok"], True, "autoexec on")
        expect(core.autoexec_runs_yaws(games["css"]), True, "autoexec.cfg runs yaws.cfg")
        expect(call("set_autoexec", game="css", on=False)["message"], "Removed from autoexec.cfg", "autoexec off")
        expect(bridge.call("sourceyaw", "set_autoexec", {"game": "css", "on": 1})["ok"], False, "non-bool refused")

        # ------------------------------------------------------------ side effects, stubbed
        played = []
        core.play_sound = lambda cstrike, sound, game="css": played.append((sound, game)) or sound != "gone"
        expect(call("play_sound", game="css", sound="buttons/blip1"), True, "play a sound")
        expect(call("play_sound", game="css", sound="gone"), False, "a missing sound")
        expect(call("play_sound", game="css", sound=""), True, "None plays nothing")
        expect(played, [("buttons/blip1", "css"), ("gone", "css")], "sounds played")
        trainer = api._trainer_module()
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
        shown = []

        class FakeOverlay:
            def show(self, text, row, x, y):
                shown.append((text, row, x, y))

            def hide(self):
                shown.append("hidden")

        trainer.Overlay = FakeOverlay
        trainer.write_atlas = lambda cfg: shown.append(("atlas", cfg["size"]))
        tr = dict(st["trainer"], target=2, x=25, y=75, size=40)
        expect(call("show_in_game", on=True, game="css", trainer=tr), True, "show in game")
        expect(call("show_in_game", on=False, game="css", trainer=tr), False, "hide in game")
        expect(shown, [("atlas", 40), ("+2", 1, 0.25, 0.75), "hidden"], "overlay")

        core.krosshair_installed = lambda: None
        core.can_install_krosshair = lambda: True

        def slow_install():
            time.sleep(0.3)
            raise RuntimeError("offline")
        core.install_krosshair = slow_install
        got = call("install_krosshair")
        expect((got["installing"], got["can_install"]), (True, True), "install started")
        while call("krosshair")["installing"]:
            time.sleep(0.05)
        expect((call("krosshair")["error"], call("krosshair")["finished"]), ("offline", True), "install error")

        picked = tmp / "mine.png"
        Image.new("RGBA", (5, 5), (1, 2, 3, 255)).save(picked)

        class FakeWindow:
            answer = None

            def create_file_dialog(self, kind, directory="", file_types=()):
                expect((kind, file_types), (10, ("PNG images (*.png)",)), "file dialog")
                return self.answer
        fake = types.SimpleNamespace(windows=[FakeWindow()], FileDialog=types.SimpleNamespace(OPEN=10))
        sys.modules["webview"] = fake
        try:
            expect(call("pick_image", base="builtin")["pick"], None, "dialog cancelled")
            fake.windows[0].answer = (str(picked),)
            got = call("pick_image", base="builtin")
            expect((got["pick"], got["base_options"][-2]), (str(picked), [str(picked), "mine.png"]), "image picked")
        finally:
            del sys.modules["webview"]

        # ------------------------------------------------------------ Apply = the GTK window's way
        for game, game_dir in games.items():
            st = call("load", game=game)
            f = form_of(st)
            f.update(key="1", start=1, base="builtin" if game == "css" else st["base"])
            f["entries"].append({"speed": 293.95354, "color": "#123abc", "sound": ""})
            f["entries"][0]["sound"] = "buttons/blip2"
            f["trainer"].update(enabled=True, offset_key="k", x=33.0, y=57.12345, sound="buttons/blip2",
                                repeat=0.354, colors={"early": "#112233", "perfect": "#445566", "late": "#778899"})
            if game == "css":
                f["trainer"]["tickrate"] = 85.0
            config, cfg_dir = core.CONFIG_DIR, game_dir / "cfg"
            snaps = {config: tmp / "snap-config", cfg_dir: tmp / "snap-cfg"}
            for src, snap in snaps.items():
                restore(src, snap)

            got = call("apply", game=game, form=f)
            expect(got["saved"], True, f"{game}: apply")
            expect(got["messages"][-1], "Saved. Game already open? Run: exec yaws", f"{game}: last message")
            ours = tree_hashes(config, cfg_dir)
            for src, snap in snaps.items():
                restore(snap, src)

            # the GTK window's way: Window.collect with EntryRow.value's rounding, then yawcore.apply
            data = core.load_settings(game)
            tform = dict(f["trainer"], tickrate=None if game == "momentum" else f["trainer"]["tickrate"])
            trainer_saved = api.trainer_value(api.trainer_config(data.get("trainer")), tform, game)
            entries = [{"speed": round(float(e["speed"]), 4), "color": e["color"], "sound": e["sound"] or None}
                       for e in f["entries"]]
            gtk = api.collect(f["key"], f["crosshair"], f["start"], f["base"], data.get("original_color"),
                              trainer_saved, entries)
            core.apply(gtk, game_dir, game=game)
            theirs = tree_hashes(config, cfg_dir)
            if ours != theirs:
                diff = sorted(k for k in ours.keys() | theirs.keys() if ours.get(k) != theirs.get(k))
                fail(f"{game}: Apply wrote different files than the GTK way: {diff}")
            expect(call("load", game=game)["entries"][2]["speed"], 293.9535, f"{game}: saved speed")

        expect([m for m in BARE if m in sys.modules], [], "bare modules at the end")
    print("ok: sourceyaw hub section")


if __name__ == "__main__":
    main()
