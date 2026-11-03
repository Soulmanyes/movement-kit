#!/usr/bin/env python3
"""Checks movekit/panorama.py against a fake Momentum folder in a temp folder.

Usage: python movekit/check_panorama.py   (exits 1 on the first failure)

Covers: the base file from the game, from another mod's folder in custom/ (mount order, any case) and
past a VPK that has it (a warning); two tools patching the same file, both kept, in tool order; the
indent and CRLF line endings of the base kept; a patch already in the base applied once (an old copy
picked as the base); a find/replace patch; a patch that doesn't fit skipped with the tool's other
patches to that file, the other tool kept; bad manifests and bad patches refused; the kit folder never
picked as the base; sync run twice giving the same files, and nothing left behind in custom/ but the
kit folder; uninstalling one tool keeping the other; no patches left removing the kit folder.
XDG_DATA_HOME and LOCALAPPDATA point into the temp folder (the lock file).
"""
import json
import os
import struct
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))

TIMER = "panorama/layout/hud/timer.xml"
TRAINER = "panorama/scripts/hud/strafe-trainer.ts"
GAME_TIMER = "<root>\r\n\t<scripts>\r\n\t\t<include src=\"timer.ts\" />\r\n\t</scripts>\r\n</root>\r\n"
GAME_TRAINER = "const a = {\n\tresizeX: true,\n\tresizeY: false,\n};\n"
REC = '<include src="rec.ts" />'
JH = '<include src="jhud.ts" />'


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}:\n got  {got!r}\n want {want!r}")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def vpk_with(path, rel):
    """A one-file VPK v1 whose tree lists rel (no data)."""
    folder, _, file = rel.rpartition("/")
    name, _, ext = file.rpartition(".")
    tree = (ext.encode() + b"\0" + folder.encode() + b"\0" + name.encode() + b"\0"
            + struct.pack("<IHHIIH", 0, 0, 0x7FFF, 0, 0, 0xFFFF) + b"\0\0\0")
    path.write_bytes(struct.pack("<III", 0x55AA1234, 1, len(tree)) + tree)


def states(report):
    return [(r["tool"], r["state"]) for r in report["patches"]]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        os.environ["XDG_DATA_HOME"] = os.environ["LOCALAPPDATA"] = str(tmp / "data")
        from movekit import panorama
        game = tmp / "momentum"
        custom = game / "custom"
        kit = custom / panorama.KIT_FOLDER
        write(game / TIMER, GAME_TIMER)
        write(game / TRAINER, GAME_TRAINER)
        custom.mkdir()

        # nothing registered: no kit folder
        expect(panorama.sync(game), {"patches": [], "warnings": []}, "report with no tools")
        expect(kit.exists(), False, "kit folder with no tools")

        # one tool, base from the game: the line goes in front of </scripts>, one tab deeper, CRLF kept
        rec = {"file": TIMER, "before": "</scripts>", "line": REC}
        report = panorama.install(game, "0-strafe-review", "strafe-review", [rec])
        expect(states(report), [("strafe-review", "applied")], "recorder patch")
        expect(report["patches"][0]["base"], str(game / TIMER), "base is the game's own")
        one = GAME_TIMER.replace("\t</scripts>", f"\t\t{REC}\r\n\t</scripts>")
        expect(read(kit / TIMER), one, "timer.xml with the recorder")
        expect((kit / panorama.NOTE).is_file(), True, "README in the kit folder")
        expect(json.loads(read(custom / "0-strafe-review" / panorama.MANIFEST))["tool"], "strafe-review",
               "manifest written")

        # a second tool on the same file: both includes, in tool order (jhud before strafe-review)
        panorama.install(game, "movekit-jhud", "jhud", [{"file": TIMER, "before": "</scripts>", "line": JH}])
        both = GAME_TIMER.replace("\t</scripts>", f"\t\t{JH}\r\n\t\t{REC}\r\n\t</scripts>")
        expect(read(kit / TIMER), both, "timer.xml with both tools")

        # sync again: same files, nothing else in custom/ or the game folder
        before = {p: read(p) for p in kit.rglob("*") if p.is_file()}
        panorama.sync(game)
        expect({p: read(p) for p in kit.rglob("*") if p.is_file()}, before, "second sync")
        expect(sorted(p.name for p in custom.iterdir()), ["0-movekit", "0-strafe-review", "movekit-jhud"],
               "custom/ after sync")
        expect(sorted(p.name for p in game.iterdir()), ["custom", "panorama"], "game folder after sync")

        # another mod's folder (sorts later, any case) is the base, not the game's file nor our own folder
        write(custom / "PanoDev" / TIMER, GAME_TIMER.replace("timer.ts", "dev-timer.ts"))
        report = panorama.sync(game)
        expect(report["patches"][0]["base"], str(custom / "PanoDev" / TIMER), "base from another mod")
        expect(read(kit / TIMER), both.replace("timer.ts", "dev-timer.ts"), "timer.xml on the mod's copy")

        # a VPK in front of it gets a warning and the search goes on
        vpk_with(custom / "a-hud.vpk", TIMER)
        report = panorama.sync(game)
        expect(len(report["warnings"]), 1, "VPK warning")
        expect(report["patches"][0]["base"], str(custom / "PanoDev" / TIMER), "base past the VPK")
        (custom / "a-hud.vpk").unlink()

        # an old copy that already has the recorder's include (an old Strafe Review's own timer.xml):
        # chosen as the base, the include isn't added twice and only jhud's goes in
        old = GAME_TIMER.replace("\t</scripts>", f"\t\t{REC}\r\n\t</scripts>")
        write(custom / "0-strafe-review" / TIMER, old)
        report = panorama.sync(game)
        expect(states(report), [("jhud", "applied"), ("strafe-review", "present")], "old copy as base")
        expect(read(kit / TIMER).count(REC), 1, "recorder include once")
        expect(read(kit / TIMER), old.replace("\t</scripts>", f"\t\t{JH}\r\n\t</scripts>"), "old copy patched")
        (custom / "0-strafe-review" / TIMER).unlink()

        # a find/replace patch, and a tool whose second patch doesn't fit: none of its patches to that
        # file apply, the other tool's do
        panorama.install(game, "movekit-trainer-height", "trainer-height",
                         [{"file": TRAINER, "find": "resizeY: false,", "replace": "resizeY: true,"}])
        expect(read(kit / TRAINER), GAME_TRAINER.replace("resizeY: false,", "resizeY: true,"), "find/replace")
        panorama.install(game, "movekit-jhud", "jhud", [
            {"file": TIMER, "before": "</scripts>", "line": JH},
            {"file": TIMER, "before": "</styles>", "line": "<include src=\"j.scss\" />"}])
        report = panorama.sync(game)
        rows = [r for r in report["patches"] if r["tool"] == "jhud"]
        expect([r["state"] for r in rows], ["skipped", "skipped"], "jhud skipped whole")
        expect("0 lines" in rows[1]["reason"], True, "reason names the missing anchor")
        expect(JH in read(kit / TIMER), False, "jhud's first patch taken out")
        expect(REC in read(kit / TIMER), True, "recorder kept")

        # bad patches: refused by install before writing, left out (with a warning) when on disk
        for bad in ({"file": "cfg/autoexec.cfg", "find": "a", "replace": "b"},
                    {"file": "panorama/../x", "find": "a", "replace": "b"},
                    {"file": TIMER}, {"file": TIMER, "find": "a", "replace": "a"},
                    {"file": TIMER, "before": "</scripts>", "line": "a\nb"}):
            try:
                panorama.install(game, "movekit-bad", "bad", [bad])
                fail(f"bad patch accepted: {bad}")
            except (ValueError, TypeError):
                pass
        expect((custom / "movekit-bad").exists(), False, "nothing written for a bad patch")
        write(custom / "movekit-bad" / panorama.MANIFEST, "{not json")
        write(custom / "movekit-dupe" / panorama.MANIFEST, json.dumps({"tool": "jhud", "patches": []}))
        report = panorama.sync(game)
        expect(len([w for w in report["warnings"] if "left out" in w]), 2, "bad and duplicate manifests")
        expect(REC in read(kit / TIMER), True, "a bad manifest leaves the others")

        # status writes nothing
        mtime = (kit / TIMER).stat().st_mtime_ns
        expect(panorama.status(game)["patches"], report["patches"], "status equals the sync report")
        expect((kit / TIMER).stat().st_mtime_ns, mtime, "status wrote nothing")

        # uninstall keeps the others; with none left the kit folder goes
        panorama.uninstall(game, "movekit-trainer-height")
        expect((kit / TRAINER).exists(), False, "trainer file gone with its tool")
        expect(REC in read(kit / TIMER), True, "recorder kept after another uninstall")
        for folder in ("0-strafe-review", "movekit-jhud"):
            panorama.uninstall(game, folder)
        expect(kit.exists(), False, "kit folder with no patches left")
        panorama.uninstall(game, "movekit-never-installed")  # nothing to remove: no error
    print("panorama: all checks passed")


if __name__ == "__main__":
    main()
