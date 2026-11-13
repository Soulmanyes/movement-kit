#!/usr/bin/env python3
"""Checks strafe-trainer/settings_api.py without a window: everything in a temp folder. Moved out
of Source Yaw's check_settings_api.py with the trainer (Phase 13).

Usage: python strafe-trainer/check_settings_api.py   (exits 1 on the first failure)

Covers, loaded the hub's way (hub.local_import, strafe-trainer/ not on sys.path): trainer_config
(defaults, colours and tickrate merged per key; settings from before per-cue sounds migrated),
trainer_value (unit conversion and rounding, tickrate kept where the map sets it, per-cue sounds
and the old shared keys kept for a roll back), trainer_status (input service installed or not,
binds the service doesn't forward); local_import returning the same trainer module, and no bare
trainer, store or settings_api left in sys.modules. HOME and the XDG folders point into the temp
folder.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


FORM = {"enabled": True, "when_jump": True, "when_timer": True, "show_offset": False, "offset_key": "o", "x": 33.0, "y": 57.12345,
        "size": 40.0, "colors": {"early": "#112233", "perfect": "#445566", "late": "#778899"},
        "repeat": 0.354, "tone_volume": 45.0, "target": -2.0, "tickrate": 85.0,
        "cue_wrong_key": True, "wrong_sound": "tone", "wrong_pitch": 330.0, "wrong_ticks": 4.0,
        "cue_no_key": False, "none_sound": "buttons/blip1.wav", "none_pitch": 200.0, "none_ticks": 5.0,
        "cue_overlap": False, "overlap_sound": "tone", "overlap_pitch": 130.0, "overlap_ticks": 2.0}


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for var, sub in (("HOME", "home"), ("XDG_CONFIG_HOME", "home/.config"),
                         ("XDG_DATA_HOME", "home/.local/share"), ("XDG_CACHE_HOME", "home/.cache")):
            os.environ[var] = str(tmp / sub)
        sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
        sys.path.insert(0, str(KIT))
        from movekit import hub
        api = hub.local_import(HERE / "hub_section.py", "settings_api")
        store = api.store

        # trainer_config / trainer_value
        cfg = api.trainer_config({"colors": {"late": "#010203"}, "tickrate": {"css": 70}, "x": 0.4})
        trainer = api._trainer()
        expect(hub.local_import(HERE / "hub_section.py", "trainer") is trainer, True,
               "local_import's trainer is settings_api's")
        expect(cfg["colors"], {**store.DEFAULTS["colors"], "late": "#010203"}, "colours merged")
        expect(cfg["tickrate"], {"css": 70, "momentum": 100}, "tickrate merged")
        expect(cfg["x"], 0.4, "saved value kept")
        expect(api.trainer_config(None), store.DEFAULTS, "config with nothing saved")
        value = api.trainer_value(cfg, FORM, "css")
        expect({k: value[k] for k in ("x", "y", "size", "repeat", "tone_volume", "target", "tickrate")},
               {"x": 0.33, "y": 0.571, "size": 40, "repeat": 0.35, "tone_volume": 0.45,
                "target": -2, "tickrate": {"css": 85, "momentum": 100}},
               "trainer value converted")
        expect({k: value[k] for c in ("wrong", "none", "overlap") for k in value if k.startswith(c + "_")},
               {"wrong_sound": "tone", "wrong_pitch": 330, "wrong_ticks": 4,
                "none_sound": "buttons/blip1.wav", "none_pitch": 200, "none_ticks": 5,
                "overlap_sound": "tone", "overlap_pitch": 130, "overlap_ticks": 2}, "per-cue values")
        expect((value["cue_wrong_key"], value["cue_no_key"], value["cue_overlap"]), (True, False, False),
               "cue switches")
        expect((value["sound"], value["tone_pitch"]), ("tone", 330), "old shared keys for a roll back")
        # saved by Source Yaw 1.9.0: one sound and pitch for both wrong-key cues, the no-key tone at 2/3
        old = api.trainer_config({"sound": "buttons/blip2.wav", "tone_pitch": 300, "wrong_ticks": 5})
        expect({k: old[k] for k in ("wrong_sound", "none_sound", "wrong_pitch", "none_pitch",
                                    "wrong_ticks", "none_ticks", "overlap_sound", "cue_wrong_key")},
               {"wrong_sound": "buttons/blip2.wav", "none_sound": "buttons/blip2.wav", "wrong_pitch": 300,
                "none_pitch": 200, "wrong_ticks": 5, "none_ticks": 5, "overlap_sound": "tone",
                "cue_wrong_key": True}, "1.9.0 settings migrated")
        silent = api.trainer_config({"sound": ""})
        expect((silent["cue_wrong_key"], silent["cue_no_key"], silent["wrong_sound"], silent["cue_overlap"]),
               (False, False, "tone", True), "1.9.0 'no sound' turns both wrong-key cues off")
        again = api.trainer_config(value)
        expect((again["none_sound"], again["none_pitch"]), ("buttons/blip1.wav", 200),
               "per-cue values win over the old shared keys")
        expect(value["hide_after"], store.DEFAULTS["hide_after"], "fields without a control kept")
        mom = api.trainer_value(cfg, {**FORM, "tickrate": None}, "momentum")
        expect(mom["tickrate"], {"css": 70, "momentum": 100}, "tickrate kept where the map sets it")
        expect(cfg["colors"]["late"], "#010203", "trainer_value leaves cfg alone")
        json.dumps(value)

        # trainer_status (Linux: the input service)
        if not api.WINDOWS:
            game = tmp / "cstrike"
            (game / "cfg").mkdir(parents=True)
            (game / "cfg/config.cfg").write_text('bind "space" "+jump"\nbind "a" "+moveleft"\n'
                                                 'bind "mouse4" "+left"\n')
            trainer.INPUTD_CONFIG = str(tmp / "inputd.conf")
            st = api.trainer_status(None)
            expect((st["installed"], st["binds"]), (False, None), "status with no service, no game")
            expect(st["service"].endswith(api.inputd_command()), True, "install command in the note")
            expect(api.inputd_command().endswith("strafe-trainer/inputd/install-inputd.sh"), True,
                   "install command from this module's folder")
            Path(trainer.INPUTD_CONFIG).write_text("keys = KEY_SPACE KEY_A\n")
            st = api.trainer_status(game)
            expect(st["installed"], True, "status with the service")
            expect(st["binds"], "⚠ Not forwarded by the input service: mouse4 (turn left). "
                                "Add them to /etc/sourceyaw-inputd.conf", "unforwarded binds")
            Path(trainer.INPUTD_CONFIG).write_text("keys = KEY_SPACE KEY_A BTN_SIDE\n")
            expect(api.trainer_status(game)["binds"],
                   "Strafe, turn and jump keys come from your binds in the game", "all binds forwarded")
            json.dumps(st)

        bare = [m for m in ("trainer", "store", "settings_api", "gamecfg") if m in sys.modules]
        expect(bare, [], "bare modules after loading the hub's way")
    print("check_settings_api: all passed")


if __name__ == "__main__":
    main()
