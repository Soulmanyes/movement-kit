#!/usr/bin/env python3
"""Checks the Strafe Trainer's own parts on a fake game (Phase 13): no Steam, game or sound.
HOME and the XDG folders point into a temp folder.

Usage: python strafe-trainer/check_install.py   (exits 1 on the first failure)

Covers: the one-time copy of the trainer settings from Source Yaw (old cue keys migrated, Source
Yaw's file untouched, a game with its own profile kept, the old CS:S-only file); the autoexec block
(console log, offset alias and key, a stale key unbound, the key left out while another tool binds
it, the block gone when off, uninstall); the hub section's load, offset-key note and Apply; and the
rollback guard (no trainer while a Source Yaw with its own trainer.py is installed).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="strafe-trainer-check-"))
os.environ.update(HOME=str(TMP), XDG_CONFIG_HOME=str(TMP / "config"), XDG_DATA_HOME=str(TMP / "data"),
                  XDG_CACHE_HOME=str(TMP / "cache"))
sys.path[:0] = [str(HERE.parent)]
from movekit import games, keys
from movekit.hub import local_import

store = local_import(str(HERE / "x.py"), "store")
gamecfg = local_import(str(HERE / "x.py"), "gamecfg")
section = local_import(str(HERE / "x.py"), "hub_section")
launch_win = local_import(str(HERE / "x.py"), "launch_win")


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")
    print(f"ok   {what}")


def fake_game(name):
    mod = TMP / "steam" / name / ("cstrike" if name == "css" else "momentum")
    (mod / "cfg").mkdir(parents=True)
    return mod


def block_of(mod):
    text = (mod / "cfg" / "autoexec.cfg").read_text() if (mod / "cfg" / "autoexec.cfg").exists() else ""
    lines = text.splitlines()
    if "// movekit:strafe-trainer begin" not in lines:
        return None
    a, b = lines.index("// movekit:strafe-trainer begin"), lines.index("// movekit:strafe-trainer end")
    return lines[a + 1:b]


def check_import():
    sy = TMP / "config" / "sourceyaw" / "settings.json"
    sy.parent.mkdir(parents=True)
    old = {"game": "momentum", "profiles": {
        "css": {"key": "f", "trainer": {"enabled": True, "sound": "", "tone_pitch": 300, "offset_key": "o"}},
        "momentum": {"key": "f", "trainer": {"enabled": False, "wrong_sound": "tone", "wrong_pitch": 200}}}}
    sy.write_text(json.dumps(old))
    before = sy.read_text()
    expect(store.import_from_sourceyaw(), ["css", "momentum"], "games copied from Source Yaw")
    expect(sy.read_text(), before, "Source Yaw's file untouched")
    css = store.config("css")
    expect((css["enabled"], css["offset_key"], css["cue_wrong_key"], css["wrong_pitch"], css["none_pitch"]),
           (True, "o", False, 300, 200), "CS:S settings migrated (old shared sound and pitch)")
    expect(store.last_game(), "momentum", "last game taken from Source Yaw")
    store.save("momentum", {**store.saved("momentum"), "wrong_pitch": 400})
    old["profiles"]["momentum"]["trainer"]["wrong_pitch"] = 999
    sy.write_text(json.dumps(old))
    expect(store.import_from_sourceyaw(), [], "nothing copied twice")
    expect(store.config("momentum")["wrong_pitch"], 400, "own profile kept")
    raw = TMP / "old-settings.json"
    raw.write_text(json.dumps({"key": "f", "trainer": {"enabled": True}}))
    expect(store.sourceyaw_trainers(raw), {"css": {"enabled": True}}, "CS:S-only file from before Momentum")


def check_block(css):
    (css / "cfg" / "config.cfg").write_text('bind "p" "sourceyaw_offsets"\nbind "o" "+use"\n')
    (css / "cfg" / "autoexec.cfg").write_text("exec mine\n")
    cfg = store.config("css")
    gamecfg.apply("css", cfg, css)
    expect(block_of(css), ["// the strafe trainer reads map loads and the offset key's echo from yaw.log",
                           "con_logfile yaw.log", 'unbind "p"', 'alias sourceyaw_offsets "echo SY_OFFSETS"',
                           'bind "o" "sourceyaw_offsets"'], "block with the offset key")
    expect((css / "cfg" / "autoexec.cfg").read_text().startswith("exec mine\n"), True, "own lines kept")
    expect(keys.held_by_others("sourceyaw", "css"), {"o": "strafe-trainer"}, "offset key recorded")
    keys.record("sourceyaw", "css", ["o"])
    gamecfg.apply("css", cfg, css)
    expect([ln for ln in block_of(css) if ln.startswith("bind")], [], "no bind while Source Yaw binds the key")
    keys.forget("sourceyaw")
    gamecfg.apply("css", {**cfg, "enabled": False}, css)
    expect((block_of(css), keys.held_by_others("x", "css")), (None, {}), "block and key gone when off")
    gamecfg.apply("css", cfg, css)
    gamecfg.remove(css)
    expect(block_of(css), None, "remove")


def check_section(css, mom):
    found = {"css": css, "momentum": mom}
    games.find = lambda key: found.get(key)
    page = section.load("css")
    expect((page["game"], page["found"], page["trainer"]["offset_key"], page["trainer"]["enabled"]),
           ("css", True, "o", True), "section load")
    expect(page["offset_note"]["warn"], True, "o bound to +use: warned")
    keys.record("sourceyaw", "css", ["k"])
    note = section.offset_key_note("css", "k")
    expect((note["warn"], "Source Yaw" in note["text"]), (True, True), "another tool's key: warned by title")
    keys.forget("sourceyaw")
    form = dict(page["trainer"], offset_key="j", x=250)
    got = section.apply("css", form)
    expect(got["saved"], True, f"apply: {got}")
    expect((store.config("css")["offset_key"], store.config("css")["x"]), ("j", 1.0), "saved, x clamped to 100%")
    expect('bind "j" "sourceyaw_offsets"' in block_of(css), True, "apply wrote the block")
    expect(section.apply("css", dict(form, offset_key="nokey"))["saved"], False, "a key the game can't bind")
    expect(section.set_game("momentum")["game"], "momentum", "set_game")


def check_guard(css):
    kit = TMP / "kit"
    (kit / "sourceyaw").mkdir(parents=True)
    (kit / "sourceyaw" / "trainer.py").write_text("")
    exe = str(css.parent / "hl2.exe")
    expect(launch_win.start([exe], kit=kit), [], "no trainer next to a Source Yaw with its own")
    (kit / "sourceyaw" / "trainer.py").unlink()
    store.save("css", {**store.saved("css"), "enabled": False})
    expect(launch_win.start([exe], kit=kit), [], "no trainer while it is off")


def main():
    css, mom = fake_game("css"), fake_game("momentum")
    check_import()
    check_block(css)
    check_section(css, mom)
    check_guard(css)
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)
    print("check_install: all passed")


if __name__ == "__main__":
    main()
