#!/usr/bin/env python3
"""Checks the small helpers the tools share since Phase 13 (out of Source Yaw's yawcore, so the
Strafe Trainer needs no Source Yaw): movekit.keys, maps, files.in_folder, sounds and the games'
process names. No game needed.

Usage: python movekit/check_helpers.py   (exits 1 on the first failure)
"""
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="movekit-helpers-"))
os.environ["XDG_DATA_HOME"] = str(TMP / "data")  # keys.py's file; before movekit.paths is used
os.environ["LOCALAPPDATA"] = str(TMP / "data")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from movekit import files, games, keys, maps, sounds  # after the path above


def check(what, got, want):
    if got != want:
        sys.exit(f"FAIL {what}: got {got!r}, want {want!r}")
    print(f"ok   {what}")


def main():
    # keys: each tool's binds per game, others' keys without case
    check("nothing recorded", keys.held_by_others("sourceyaw", "css"), {})
    keys.record("sourceyaw", "css", ["F", "mouse4", ""])
    keys.record("strafe-trainer", "css", ["O"])
    keys.record("strafe-trainer", "momentum", ["p"])
    check("others' keys in css (Source Yaw asks)", keys.held_by_others("sourceyaw", "css"), {"o": "strafe-trainer"})
    check("others' keys in css (Strafe Trainer asks)", keys.held_by_others("strafe-trainer", "css"),
          {"f": "sourceyaw", "mouse4": "sourceyaw"})
    check("another game's keys stay apart", keys.held_by_others("sourceyaw", "momentum"), {"p": "strafe-trainer"})
    keys.record("strafe-trainer", "css", [])
    check("an empty record drops the game", keys.held_by_others("sourceyaw", "css"), {})
    keys.forget("strafe-trainer")
    check("forget", keys.held_by_others("sourceyaw", "momentum"), {})
    (TMP / "data" / "movekit" / "binds.json").write_text("not json")
    check("a broken file reads as empty", keys.held_by_others("x", "css"), {})
    keys.record("x", "css", ["a"])
    check("and is replaced on the next record", keys.held_by_others("y", "css"), {"a": "x"})

    # maps.prefix_value
    table = {"bhop_": 100, "SURF_": 66}
    check("prefix any case", (maps.prefix_value("surf_beginner", table), maps.prefix_value("Bhop_X", table)),
          (66, 100))
    check("no prefix: default", maps.prefix_value("kz_x", table, 7), 7)
    check("unknown map: None", maps.prefix_value(None, table, 7), None)

    # files.in_folder (Windows paths, either slash, any case)
    game = r"C:\Steam\steamapps\common\Counter-Strike Source"
    check("in_folder", [files.in_folder(game + r"\cstrike_win64.exe", game.replace("\\", "/")),
                        files.in_folder(game.upper() + r"\BIN\X.EXE", game),
                        files.in_folder(game + r" Beta\hl2.exe", game)], [True, True, False])

    # games: what the trainer needs to know about each game
    check("process names", {k: g.process for k, g in games.GAMES.items()},
          {"css": "cstrike_linux64", "momentum": "momentum"})
    check("every game has sound VPKs", all(g.sound_vpks for g in games.GAMES.values()), True)

    # sounds: a loose file wins, a cached one is found, a missing one is None
    install = TMP / "game"
    mod = install / "cstrike"
    (mod / "sound/buttons").mkdir(parents=True)
    (mod / "sound/buttons/blip1.wav").write_bytes(b"RIFF")
    cache = TMP / "cache"
    (cache / "css/buttons").mkdir(parents=True)
    (cache / "css/buttons/blip2.wav").write_bytes(b"RIFF")
    check("loose sound", sounds.sound_file(mod, "buttons/blip1", "css", cache), mod / "sound/buttons/blip1.wav")
    check("cached sound", sounds.sound_file(mod, "buttons/blip2", "css", cache), cache / "css/buttons/blip2.wav")
    check("missing sound (no VPKs here)", sounds.sound_file(mod, "buttons/button10", "css", cache), None)
    check("available", sounds.available(mod, "css", cache), ["buttons/blip1", "buttons/blip2"])
    check("play a missing sound", sounds.play(mod, "buttons/button10", "css", cache), False)
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)
    print("check_helpers: all passed")


if __name__ == "__main__":
    main()
