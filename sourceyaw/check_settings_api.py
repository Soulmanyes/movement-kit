#!/usr/bin/env python3
"""Checks sourceyaw/settings_api.py without a window: everything in a temp folder.

Usage: python sourceyaw/check_settings_api.py   (exits 1 on the first failure)

Covers, loaded the hub's way (hub.local_import, sourceyaw/ not on sys.path): setup_problem (found,
not found, Flatpak-only), base_options (with and without crosshair-maker, a custom image),
trainer_config (defaults, colours and tickrate merged per key), trainer_value (unit conversion and
rounding, tickrate kept where the map sets it), trainer_status (tone or game sound, input service
installed or not, binds the service doesn't forward), collect feeding yawcore.validate; no bare
yawcore or trainer left behind, trainer using the same yawcore, and local_import returning the
same modules. Then, in a child process the
app's way (sourceyaw/ on sys.path, settings_api imported first): the plain yawcore and trainer
modules are the ones it uses. HOME and the XDG folders point into the temp folder.
"""
import json
import os
import subprocess
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


FORM = {"enabled": True, "show_offset": False, "offset_key": "o", "x": 33.0, "y": 57.12345,
        "size": 40.0, "colors": {"early": "#112233", "perfect": "#445566", "late": "#778899"},
        "sound": "tone", "wrong_ticks": 4.0, "repeat": 0.354, "tone_volume": 45.0,
        "tone_pitch": 330.0, "cue_wrong_key": True, "cue_no_key": False, "target": -2.0,
        "tickrate": 85.0}

APP_WAY = f"""
import sys
sys.path.insert(0, {str(HERE)!r})
import settings_api
import trainer
import yawcore
assert settings_api.core is yawcore, "settings_api has its own yawcore"
assert settings_api._trainer_module() is trainer, "settings_api has its own trainer"
assert trainer.yawcore is yawcore
assert not [m for m in sys.modules if m.startswith("movekit_section_")], "path-loaded copies"
print("ok")
"""


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for var, sub in (("HOME", "home"), ("XDG_CONFIG_HOME", "home/.config"),
                         ("XDG_DATA_HOME", "home/.local/share"), ("XDG_CACHE_HOME", "home/.cache")):
            os.environ[var] = str(tmp / sub)
        sys.path.insert(0, str(KIT))
        if any(Path(p or ".").resolve() == HERE for p in sys.path):
            sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
        from movekit import hub
        api = hub.local_import(HERE / "hub_section.py", "settings_api")
        core = api.core
        expect(hub.local_import(HERE / "hub_section.py", "yawcore") is core, True,
               "local_import's yawcore is settings_api's")

        # setup_problem
        real_flatpak = core.flatpak_steam_only
        core.flatpak_steam_only = lambda game="css": False
        expect(api.setup_problem("css", tmp), None, "setup with a game folder")
        expect(api.setup_problem("momentum", None), "Momentum Mod not found in your Steam libraries",
               "setup without a game")
        core.flatpak_steam_only = lambda game="css": True
        expect(api.setup_problem("css", None).startswith("Flatpak Steam isn't supported"), True,
               "setup with Flatpak Steam only")
        expect(api.setup_problem("css", tmp), None, "Flatpak doesn't matter with a game folder")
        core.flatpak_steam_only = real_flatpak

        # base_options
        real_cm = core.crosshair_maker_png
        core.crosshair_maker_png = lambda: Path("/x/my cross.png")
        expect(api.base_options("/some/dir/pic.png"),
               [("crosshair-maker", "crosshair-maker: my cross"), ("builtin", "Plain cross"),
                ("/some/dir/pic.png", "pic.png"), ("pick", "Choose an image…")], "base options")
        core.crosshair_maker_png = lambda: None
        expect(api.base_options("builtin"), [("builtin", "Plain cross"), ("pick", "Choose an image…")],
               "base options without crosshair-maker")
        core.crosshair_maker_png = real_cm

        # trainer_config / trainer_value
        cfg = api.trainer_config({"colors": {"late": "#010203"}, "tickrate": {"css": 70}, "x": 0.4})
        trainer = api._trainer_module()
        expect(trainer.yawcore is core, True, "trainer uses the same yawcore")
        expect(hub.local_import(HERE / "hub_section.py", "trainer") is trainer, True,
               "local_import's trainer is settings_api's")
        expect(cfg["colors"], {**trainer.TRAINER_DEFAULTS["colors"], "late": "#010203"}, "colours merged")
        expect(cfg["tickrate"], {"css": 70, "momentum": 100}, "tickrate merged")
        expect(cfg["x"], 0.4, "saved value kept")
        expect(api.trainer_config(None), trainer.TRAINER_DEFAULTS, "config with nothing saved")
        value = api.trainer_value(cfg, FORM, "css")
        expect({k: value[k] for k in ("x", "y", "size", "wrong_ticks", "repeat", "tone_volume",
                                      "tone_pitch", "target", "tickrate")},
               {"x": 0.33, "y": 0.571, "size": 40, "wrong_ticks": 4, "repeat": 0.35, "tone_volume": 0.45,
                "tone_pitch": 330, "target": -2, "tickrate": {"css": 85, "momentum": 100}},
               "trainer value converted")
        expect(value["hide_after"], trainer.TRAINER_DEFAULTS["hide_after"], "fields without a control kept")
        mom = api.trainer_value(cfg, {**FORM, "tickrate": None}, "momentum")
        expect(mom["tickrate"], {"css": 70, "momentum": 100}, "tickrate kept where the map sets it")
        expect(cfg["colors"]["late"], "#010203", "trainer_value leaves cfg alone")
        json.dumps(value)

        # trainer_status
        game = tmp / "cstrike"
        (game / "cfg").mkdir(parents=True)
        (game / "cfg/config.cfg").write_text('bind "space" "+jump"\nbind "a" "+moveleft"\n'
                                             'bind "mouse4" "+left"\n')
        trainer.INPUTD_CONFIG = str(tmp / "inputd.conf")
        st = api.trainer_status(None, "buttons/blip1.wav")
        expect((st["tone"], st["wrong_note"], st["installed"], st["binds"]), (False, "", False, None),
               "status with a game sound, no service, no game")
        expect(st["service"].endswith(api.inputd_command()), True, "install command in the note")
        Path(trainer.INPUTD_CONFIG).write_text("keys = KEY_SPACE KEY_A\n")
        st = api.trainer_status(game, "tone")
        expect((st["tone"], st["wrong_note"], st["none_note"], st["installed"]),
               (True, "Higher tone", "Lower tone", True), "status with the tone and the service")
        expect(st["binds"], "⚠ Not forwarded by the input service: mouse4 (turn left). "
                            "Add them to /etc/sourceyaw-inputd.conf", "unforwarded binds")
        Path(trainer.INPUTD_CONFIG).write_text("keys = KEY_SPACE KEY_A BTN_SIDE\n")
        expect(api.trainer_status(game, "tone")["binds"],
               "Strafe, turn and jump keys come from your binds in the game", "all binds forwarded")
        json.dumps(st)

        # collect
        entries = [{"speed": 100 + i, "color": "#ff0000", "sound": None} for i in range(3)]
        data = api.collect("f", True, 1, "builtin", None, value, entries)
        expect(sorted(data), ["auto_mode", "base", "crosshair", "entries", "key", "map_modes", "mode_key",
                              "original_color", "start", "trainer"], "collect keys")
        expect(core.validate(data), [], "collected settings validate")
        surf = {"entries": [{"speed": 60, "color": "#00ff00", "sound": None}], "start": 0}
        data = api.collect("f", True, 1, "builtin", None, value, entries, surf=surf, mode_key="g")
        expect((data["surf"], data["mode_key"], data["auto_mode"]), (surf, "g", True), "collect with a surf list")
        expect(core.validate(data), [], "collected surf settings validate")

        bare = [m for m in ("yawcore", "trainer", "settings_api") if m in sys.modules]
        expect(bare, [], "bare modules after loading the hub's way")

    out = subprocess.run([sys.executable, "-c", APP_WAY], capture_output=True, text=True, check=False,
                         env={**os.environ, "PYTHONPATH": ""})
    if out.returncode or out.stdout.strip() != "ok":
        fail("the app's way: " + (out.stderr.strip().splitlines() or ["no output"])[-1])
    print("check_settings_api: all passed")


if __name__ == "__main__":
    main()
