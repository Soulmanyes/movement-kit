#!/usr/bin/env python3
"""Checks sourceyaw/settings_api.py without a window: everything in a temp folder.

Usage: python sourceyaw/check_settings_api.py   (exits 1 on the first failure)

Covers, loaded the hub's way (hub.local_import, sourceyaw/ not on sys.path): setup_problem (found,
not found, Flatpak-only), base_options (with and without crosshair-maker, a custom image), collect
feeding yawcore.validate and keeping a saved "trainer" dict as it was (for a roll back: the trainer
is its own module since Phase 13, checked by strafe-trainer/check_settings_api.py),
module_hooks.split_out (Strafe Trainer named only when a game had the trainer on); no bare yawcore
left behind, and local_import returning the same modules. Then, in a child process the app's way
(sourceyaw/ on sys.path, settings_api imported first): the plain yawcore is the one it uses.
HOME and the XDG folders point into the temp folder.
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


APP_WAY = f"""
import sys
sys.path.insert(0, {str(HERE)!r})
import settings_api
import yawcore
assert settings_api.core is yawcore, "settings_api has its own yawcore"
assert not hasattr(settings_api, "trainer_config"), "trainer settings left in Source Yaw"
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

        # collect
        entries = [{"speed": 100 + i, "color": "#ff0000", "sound": None} for i in range(3)]
        value = {"enabled": True, "offset_key": "o", "x": 0.33}  # a saved trainer dict, from 1.10
        data = api.collect("f", True, 1, "builtin", None, value, entries)
        expect(data["trainer"], value, "saved trainer dict kept as it was")
        expect("trainer" in api.collect("f", True, 1, "builtin", None, None, entries), False,
               "no trainer key without a saved one")
        expect(sorted(data), ["active", "auto_mode", "base", "crosshair", "entries", "key", "map_modes",
                              "mode_key", "original_color", "separate", "start", "trainer"], "collect keys")
        expect(core.validate(data), [], "collected settings validate")
        surf = {"entries": [{"speed": 60, "color": "#00ff00", "sound": None}], "start": 0}
        data = api.collect("f", True, 1, "builtin", None, value, entries, surf=surf, mode_key="g", separate=True)
        expect((data["surf"], data["mode_key"], data["auto_mode"]), (surf, "g", True), "collect with a surf list")
        expect(core.validate(data), [], "collected surf settings validate")

        # module_hooks.split_out: Strafe Trainer installed on update only when a game had the trainer on
        from movekit import paths
        hooks = hub.local_import(HERE / "module_hooks.py", "module_hooks")
        settings = paths.config_dir("sourceyaw") / "settings.json"
        settings.unlink(missing_ok=True)
        expect(hooks.split_out(None), [], "split_out with no settings")
        settings.parent.mkdir(parents=True, exist_ok=True)
        for raw, want, what in (
                ({"profiles": {"css": {"trainer": {"enabled": False}}, "momentum": {"key": "q"}}}, [],
                 "split_out with the trainer off everywhere"),
                ({"profiles": {"css": {"trainer": {"enabled": False}},
                               "momentum": {"trainer": {"enabled": True}}}}, ["strafe-trainer"],
                 "split_out with the trainer on in one game"),
                ({"key": "q", "trainer": {"enabled": True}}, ["strafe-trainer"],
                 "split_out on the old CS:S-only file")):
            settings.write_text(json.dumps(raw))
            expect(hooks.split_out(None), want, what)
        settings.write_text("{not json")
        expect(hooks.split_out(None), [], "split_out with a broken file")

        bare = [m for m in ("yawcore", "settings_api") if m in sys.modules]
        expect(bare, [], "bare modules after loading the hub's way")

    out = subprocess.run([sys.executable, "-c", APP_WAY], capture_output=True, text=True, check=False,
                         env={**os.environ, "PYTHONPATH": ""})
    if out.returncode or out.stdout.strip() != "ok":
        fail("the app's way: " + (out.stderr.strip().splitlines() or ["no output"])[-1])
    print("check_settings_api: all passed")


if __name__ == "__main__":
    main()
