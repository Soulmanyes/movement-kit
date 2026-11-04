#!/usr/bin/env python3
"""Checks the HUD settings and their section without a window: everything in a temp folder.

Usage: python hud/check_hud.py   (exits 1 on the first failure)

Covers: the store (defaults, a round trip, unknown keys kept, wrong types and unknown keys refused,
a stored value of the wrong type read as the default, a broken file), the hub section found by
discovery and called through the bridge (get with no game, not installed and installed; module cards
from hud_card, the legacy JHUD card and when the section shows; the legacy jump-1 line toggle only
while a Strafe Review from before 1.9.0 is installed (a copy of its recorder_settings.py, LEGACY_SETTINGS
below, in a fake kit), set_line writing its recorder; panorama_status with no patches, applied, skipped
and no game; a non-bool refused), loading it leaving no bare steam, install or recorder_settings module
behind, and Strafe Review's install.py and recorder no longer carrying the line's setting.
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
# strafe-review/recorder_settings.py as Strafe Review 1.8.0 shipped it (the part the HUD section uses)
LEGACY_SETTINGS = '''import re
from pathlib import Path

FOLDER = "0-strafe-review"
RECORDER = Path("panorama") / "scripts" / "hud" / "strafe-review.ts"
SHOW_LINE = re.compile(r"^const SHOW_LINE = (true|false);", re.MULTILINE)


def recorder(game):
    return Path(game) / "custom" / FOLDER / RECORDER


def apply(game, show_line):
    from movekit.files import write_atomic

    ts = recorder(game)
    try:
        text = ts.read_text(encoding="utf-8")
    except OSError:
        return False
    write_atomic(ts, SHOW_LINE.sub(f"const SHOW_LINE = {'true' if show_line else 'false'};", text))
    return True
'''


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
        from movekit import hub, panorama

        # the store
        expect(settings.file(), tmp / "data" / "movekit" / "hud.json", "settings file")
        old = tmp / "data" / "strafe-review" / "settings.json"
        expect(settings.old_file(), old, "old settings file")
        expect(settings.load(), {"inGameLine": False}, "defaults with no file")

        # the old file (Strafe Review's data folder) counts until hud.json exists, and stays as it was
        old.parent.mkdir(parents=True)
        old.write_text("{not json")
        expect(settings.get("inGameLine"), False, "a broken old file reads as defaults")
        old.write_text('{"inGameLine": true, "kept": 1}')
        expect(settings.get("inGameLine"), True, "value from the old file")
        expect(settings.file().exists(), False, "reading doesn't write hud.json")
        settings.save("inGameLine", False)
        expect(json.loads(settings.file().read_text()), {"inGameLine": False, "kept": 1}, "first save carries the old keys")
        expect(old.read_text(), '{"inGameLine": true, "kept": 1}', "old file after the first save")
        old.write_text('{"inGameLine": true}')
        expect(settings.get("inGameLine"), False, "the old file is ignored once hud.json exists")
        settings.file().unlink()
        old.unlink()
        if (tmp / "data" / "strafe-review").exists():
            (tmp / "data" / "strafe-review").rmdir()
        settings.save("inGameLine", False)
        expect((tmp / "data" / "strafe-review").exists(), False, "saving doesn't make Strafe Review's folder")
        settings.file().unlink()
        settings.file().parent.mkdir(parents=True, exist_ok=True)
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

        # an old Strafe Review's recorder_settings, in a fake kit folder
        legacy = tmp / "oldkit" / "strafe-review" / "recorder_settings.py"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(LEGACY_SETTINGS)
        game = tmp / "game"
        ts = game / "custom" / "0-strafe-review" / "panorama" / "scripts" / "hud" / "strafe-review.ts"
        ts.parent.mkdir(parents=True)
        ts.write_text(TS)
        if (KIT / "strafe-review" / "recorder_settings.py").exists():
            fail("the checkout's Strafe Review still has recorder_settings.py")

        # the section, through discovery and the bridge
        sections, problems = hub.discover(KIT)
        expect([p for p in problems if p[0] == "hud"], [], "hud problems")
        if "hud" not in [s.key for s in sections]:
            fail("discovery didn't find the hud section")
        expect([s.key for s in sections][-1], "hud", "the HUD section comes after the tools in the sidebar")
        bridge = hub.Bridge(sections, problems)
        # a checkout counts its module folders as installed, so the cards come from their module.json files
        jcard = json.loads((KIT / "jhud" / "module.json").read_text())["hud_card"]
        manifests = {p.parent.name: json.loads(p.read_text()) for p in KIT.glob("*/module.json")}
        jhud = sorted(({"key": k, **m["hud_card"]} for k, m in manifests.items() if "hud_card" in m),
                      key=lambda c: (c["title"].lower(), c["key"]))
        expect([c["key"] for c in jhud], ["first-jump", "jhud", "strafe-histogram", "zone-exit"], "the checkout's HUD cards")
        settings.save("inGameLine", False)
        hud_sec = sections[[s.key for s in sections].index("hud")]
        live = hud_sec.api["get"].__globals__  # the section as discovery loaded it
        expect(bridge.call("hud", "get"), {"ok": True, "result": {"inGameLine": False, "recorder": "no game", "legacyLine": False,
                                                            "cards": jhud}},
               "get, a current Strafe Review: no legacy toggle")
        os.environ["MOMENTUM_DIR"] = str(game)
        expect(bridge.call("hud", "get")["result"]["recorder"], "not installed", "get, a current Strafe Review: no legacy recorder")
        os.environ["MOMENTUM_DIR"] = str(tmp / "nogame")
        live["_recorder_file"] = lambda: legacy
        expect(bridge.call("hud", "get"), {"ok": True, "result": {"inGameLine": False, "recorder": "no game", "legacyLine": True,
                                                            "cards": jhud}},
               "get, an old Strafe Review, no game")
        expect(bridge.call("hud", "set_line", {"on": True}),
               {"ok": True, "result": {"inGameLine": True, "applied": False}}, "set_line, no game")
        os.environ["MOMENTUM_DIR"] = str(tmp / "bare")
        (tmp / "bare").mkdir()
        expect(bridge.call("hud", "get")["result"]["recorder"], "not installed", "get, no recorder")
        os.environ["MOMENTUM_DIR"] = str(game)
        expect(bridge.call("hud", "get")["result"], {"inGameLine": True, "recorder": "installed", "legacyLine": True,
                                                       "cards": jhud},
               "get, an old Strafe Review, installed")
        # the section shows for Strafe Trainer Height alone too; the jump-1 line's card then hides
        expect(hud_sec.show_with, ["strafe-review", "trainer-height"], "hud shows with the modules it has cards for")
        # and with any module that has a hud_card (JHUD, the Strafe Speed Histogram, ...), or an old
        # JHUD from before hud_card
        card = {"title": "Zeta", "text": "set in the customizer"}
        for found, want in [({}, False), ({"gain-converter": {}}, False), ({"jhud": {}}, True),
                            ({"new-hud": {"hud_card": card}}, True)]:
            expect(hub._shown(hud_sec, found), want, f"hud section shown with {sorted(found)}")
        sec = hub.local_import(KIT / "hud" / "hub_section.py", "hub_section")
        expect(sec.cards({"b": {"hud_card": card}, "jhud": {}, "c": {"hud_card": {**card, "title": "alpha"}},
                          "gain-converter": {}}),
               [{"key": "c", "title": "alpha", "text": card["text"]},
                {"key": "jhud", **sec.LEGACY_CARDS["jhud"]},
                {"key": "b", **card}], "cards: own, legacy, none, by title")
        expect(sec.cards({"jhud": {"hud_card": card}}), [{"key": "jhud", **card}], "a module's own card beats the legacy one")
        # the legacy card is for JHUD 1.0.0 (bhop only, no hud_card), so only its title follows module.json
        expect(sec.LEGACY_CARDS["jhud"]["title"], jcard["title"], "the legacy JHUD card has JHUD's title")
        state = tmp / "data" / "movekit" / "modules.json"
        state.write_text(json.dumps({"modules": {"strafe-review": {"removed": True}}}))
        expect(bridge.call("hud", "get")["result"]["legacyLine"], False, "get, the old Strafe Review uninstalled")
        state.write_text(json.dumps({"modules": {k: {"removed": True} for k in ("jhud", "strafe-histogram", "first-jump", "zone-exit")}}))
        expect(bridge.call("hud", "get")["result"]["cards"], [], "get, the card modules uninstalled")
        state.unlink()
        expect(bridge.call("hud", "set_line", {"on": True})["result"]["applied"], True, "set_line, installed")
        expect(ts.read_text(), TS.replace("false", "true"), "recorder after set_line(True)")
        # the kit's patched files card: none yet, then the recorder's include applied, then one that
        # doesn't fit (the game's timer.xml has no </scripts>) reported as skipped
        expect(bridge.call("hud", "panorama_status")["result"], {"game": True, "patches": [], "warnings": []},
               "panorama_status, no patches")
        timer = game / "panorama" / "layout" / "hud" / "timer.xml"
        timer.parent.mkdir(parents=True)
        timer.write_text("<root>\n\t<scripts>\n\t</scripts>\n</root>\n")
        rec_patch = [{"file": "panorama/layout/hud/timer.xml", "before": "</scripts>", "line": "<include x />"}]
        panorama.install(game, "0-strafe-review", "strafe-review", rec_patch)
        rows = bridge.call("hud", "panorama_status")["result"]["patches"]
        expect([(r["tool"], r["state"]) for r in rows], [("strafe-review", "applied")], "panorama_status, applied")
        timer.write_text("<root></root>\n")
        rows = bridge.call("hud", "panorama_status")["result"]["patches"]
        expect([(r["tool"], r["state"], bool(r["reason"])) for r in rows], [("strafe-review", "skipped", True)],
               "panorama_status, skipped")
        panorama.uninstall(game, "0-strafe-review")
        os.environ["MOMENTUM_DIR"] = str(tmp / "missing")
        expect(bridge.call("hud", "panorama_status")["result"]["game"], False, "panorama_status, no game")
        os.environ["MOMENTUM_DIR"] = str(game)
        bad = bridge.call("hud", "set_line", {"on": "yes"})
        expect(bad["ok"], False, "set_line with a non-bool")
        expect(settings.get("inGameLine"), True, "store after a refused set_line")
        for name in ("steam", "install", "recorder_settings", "collector"):
            if name in sys.modules:
                fail(f"loading the hud section left a bare {name!r} module")

        # Strafe Review's install no longer writes the line's setting (its own process: it puts collector/
        # on the path), and its recorder has no line
        code = "import sys; sys.path.insert(0, sys.argv[1]); import install; print(hasattr(install, 'apply_settings'))"
        out = subprocess.run([sys.executable, "-c", code, str(KIT / "strafe-review"), str(game)],
                             check=False, capture_output=True, text=True, env=os.environ)
        expect((out.returncode, out.stdout.strip()), (0, "False"), f"install.apply_settings gone ({out.stderr.strip()})")
        recorder = (KIT / "strafe-review" / "recorder" / "panorama" / "scripts" / "hud" / "strafe-review.ts").read_text()
        expect("SHOW_LINE" in recorder or "inGameLine" in (KIT / "strafe-review" / "install.py").read_text(), False,
               "Strafe Review carries no jump-1 line setting")
    print("check_hud: all good")


if __name__ == "__main__":
    main()
