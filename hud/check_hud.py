#!/usr/bin/env python3
"""Checks the HUD settings and their section without a window: everything in a temp folder.

Usage: python hud/check_hud.py   (exits 1 on the first failure)

Covers: the store (defaults, a round trip, unknown keys kept, wrong types and unknown keys refused,
a stored value of the wrong type read as the default, a broken file), Strafe Review's
recorder_settings (rewrite both ways, False when the recorder isn't installed), the hub section
found by discovery and called through the bridge (get with no game, not installed and installed;
set_line writing the recorder; a non-bool refused), loading it leaving no bare steam, install or
recorder_settings module behind, and install.apply_settings reading the same store.
XDG_DATA_HOME, LOCALAPPDATA and MOMENTUM_DIR point into the temp folder, so the real settings and
game are never touched.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
TS = "// recorder\nconst SHOW_LINE = false;\nlet x = 1;\n"


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        os.environ["XDG_DATA_HOME"] = os.environ["LOCALAPPDATA"] = str(tmp / "data")
        os.environ["MOMENTUM_DIR"] = str(tmp / "nogame")  # no such folder yet: "no game"
        sys.path.insert(0, str(KIT))
        from hud import settings
        from movekit import hub

        # the store
        expect(settings.file(), tmp / "data" / "strafe-review" / "settings.json", "settings file")
        expect(settings.load(), {"inGameLine": False}, "defaults with no file")
        settings.file().parent.mkdir(parents=True)
        settings.file().write_text("{not json")
        expect(settings.get("inGameLine"), False, "a broken file reads as defaults")
        settings.file().write_text('{"inGameLine": "yes", "other": 3}')
        expect(settings.get("inGameLine"), False, "a stored value of the wrong type")
        settings.save("inGameLine", True)
        expect(settings.get("inGameLine"), True, "round trip")
        expect(json.loads(settings.file().read_text()), {"inGameLine": True, "other": 3}, "unknown keys kept")
        for key, value, err in [("nope", True, KeyError), ("inGameLine", 1, TypeError)]:
            try:
                settings.save(key, value)
                fail(f"save({key!r}, {value!r}) didn't raise")
            except err:
                pass

        # Strafe Review's recorder_settings, loaded the way the section loads it
        rec = hub.local_import(KIT / "strafe-review" / "recorder_settings.py", "recorder_settings")
        game = tmp / "game"
        expect(rec.apply(game, True), False, "apply with no recorder")
        ts = rec.recorder(game)
        ts.parent.mkdir(parents=True)
        ts.write_text(TS)
        expect(rec.apply(game, True), True, "apply on an installed recorder")
        expect(ts.read_text(), TS.replace("false", "true"), "recorder after apply(True)")
        rec.apply(game, False)
        expect(ts.read_text(), TS, "recorder after apply(False)")

        # the section, through discovery and the bridge
        sections, problems = hub.discover(KIT)
        expect([p for p in problems if p[0] == "hud"], [], "hud problems")
        if "hud" not in [s.key for s in sections]:
            fail("discovery didn't find the hud section")
        bridge = hub.Bridge(sections, problems)
        settings.save("inGameLine", False)
        expect(bridge.call("hud", "get"), {"ok": True, "result": {"inGameLine": False, "recorder": "no game"}}, "get, no game")
        expect(bridge.call("hud", "set_line", {"on": True}),
               {"ok": True, "result": {"inGameLine": True, "applied": False}}, "set_line, no game")
        os.environ["MOMENTUM_DIR"] = str(tmp / "bare")
        (tmp / "bare").mkdir()
        expect(bridge.call("hud", "get")["result"]["recorder"], "not installed", "get, no recorder")
        os.environ["MOMENTUM_DIR"] = str(game)
        expect(bridge.call("hud", "get")["result"], {"inGameLine": True, "recorder": "installed"}, "get, installed")
        expect(bridge.call("hud", "set_line", {"on": True})["result"]["applied"], True, "set_line, installed")
        expect(ts.read_text(), TS.replace("false", "true"), "recorder after set_line(True)")
        bad = bridge.call("hud", "set_line", {"on": "yes"})
        expect(bad["ok"], False, "set_line with a non-bool")
        expect(settings.get("inGameLine"), True, "store after a refused set_line")
        for name in ("steam", "install", "recorder_settings", "collector"):
            if name in sys.modules:
                fail(f"loading the hud section left a bare {name!r} module")

        # Strafe Review's install reads the same store (its own process: it puts collector/ on the path)
        settings.save("inGameLine", False)
        code = "import sys; sys.path.insert(0, sys.argv[1]); import install; print(install.apply_settings(sys.argv[2]))"
        out = subprocess.run([sys.executable, "-c", code, str(KIT / "strafe-review"), str(game)],
                             check=False, capture_output=True, text=True, env=os.environ)
        expect((out.returncode, out.stdout.strip()), (0, "True"), f"install.apply_settings ({out.stderr.strip()})")
        expect(ts.read_text(), TS, "recorder after install.apply_settings with the line off")
    print("check_hud: all good")


if __name__ == "__main__":
    main()
