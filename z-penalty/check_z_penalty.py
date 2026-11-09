"""Checks Z Penalty's install.py and module hooks on a fake game folder (14.2 in PLAN.md).

- install: the script is in custom/movekit-z-penalty, the kit's timer.xml includes it once and the kit's
  hud_default.kv3 holds Z Penalty's entry once, in front of CustomizerSettings; the Linux launch hook is
  registered; installing again changes nothing.
- another tool's include in timer.xml (Strafe Review's) and the same file's include by a second
  tool are kept, and uninstalling Z Penalty leaves them.
- a game update that changes hud_default.kv3 so the anchor is gone leaves the entry out and reports
  it; the timer.xml include stays.
- uninstall: patches first, then the script (a failed sync keeps it); the launch hook goes; with no
  game found it still finishes. The module hooks do the same through the module manager's Context.

- the sound setting (settings.py): bad names and volumes are refused; the installed copy carries the
  saved setting in its SOUND line and nothing else differs; the hub section's apply saves it and
  writes it into the game's copy.

The display logic and the kv3 entry's values are checked by check_z_penalty.js.

Usage: python z-penalty/check_z_penalty.py   (exits 1 on a failure)
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent

TIMER = "<root>\n\t<scripts>\n\t\t<include type=\"module\" src=\"file://{scripts}/hud/timer.ts\" />\n\t</scripts>\n</root>\n"
LAYOUT = ("<!-- kv3 encoding:text:version{e21c7f3c} format:generic:version{7412167c} -->\n{\n"
          "    CustomizerSettings = \n    {\n        offsetX = 300\n    }\n"
          "    JumpStats = \n    {\n        enabled = true\n    }\n}")
OTHER = [{"file": "panorama/layout/hud/timer.xml", "before": "</scripts>", "line": '<include src="other.ts" />'}]
INCLUDE = '<include type="module" src="file://{scripts}/hud/movekit-z-penalty.ts" />'


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def fake_game(root):
    game = root / "momentum"
    for rel, text in (("panorama/layout/hud/timer.xml", TIMER), ("cfg/hud/hud_default.kv3", LAYOUT)):
        (game / rel).parent.mkdir(parents=True, exist_ok=True)
        (game / rel).write_text(text)
    return game


def check_sound(sett, inst, hub, game, own, src):
    """settings.check, the baked SOUND line, and the hub section's apply."""
    for bad in ({"name": "a; quit"}, {"name": "../x"}, {"name": ""}, {"name": 5}, {"volume": "9"},
                {"volume": True}, {"volume": float("nan")}, {"on": 1}, []):
        try:
            sett.check(bad)
            fail(f"settings.check took {bad!r}")
        except ValueError:
            pass
    expect(sett.check({"volume": 250})["volume"], 100, "volume clamped high")
    expect(sett.check({"volume": -3.4})["volume"], 0, "volume clamped low")
    expect(sett.load(), sett.DEFAULTS, "no saved file: defaults")
    sett.file().parent.mkdir(parents=True, exist_ok=True)
    sett.file().write_text("{broken")
    expect(sett.load(), sett.DEFAULTS, "unreadable file: defaults")
    try:
        sett.bake(src + "\n" + src, sett.DEFAULTS)
        fail("bake took a script with two SOUND lines")
    except ValueError:
        pass

    section = hub.local_import(HERE / "hub_section.py", "hub_section")
    want = {"on": True, "name": "buttons/button14", "volume": 35}
    out = section.apply(want)
    expect(out["sound"], want, "apply returns the saved sound")
    expect(out["written"], True, "apply wrote the game's copy")
    expect(sett.load(), want, "apply saved the sound")
    text = own.read_text(encoding="utf-8")
    expect(text, sett.bake(src, want), "game's copy carries the saved SOUND line")
    expect(text.count('"name": "buttons/button14"'), 1, "the name in the SOUND line once")
    expect(section.load()["sound"], want, "load shows the saved sound")
    inst.install(game, quiet=True)
    expect(own.read_text(encoding="utf-8"), sett.bake(src, want), "a later install keeps the saved sound")
    try:
        section.apply({"name": "x\"; quit"})
        fail("apply took a bad name")
    except ValueError:
        pass
    expect(sett.load(), want, "a refused apply keeps the saved sound")
    inst.uninstall(game)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for var, sub in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("LOCALAPPDATA", "data")):
            os.environ[var] = str(tmp / sub)
        os.environ["HOME"] = str(tmp / "home")  # ~/.local/bin/movekit-run
        game = fake_game(tmp)
        os.environ["MOMENTUM_DIR"] = str(game)
        sys.path.insert(0, str(KIT))
        from movekit import hub, launch, modules, panorama

        inst = hub.local_import(HERE / "install.py", "install")
        expect(modules.module_version(HERE, modules.read_manifest(HERE)), inst.VERSION, "module.json reads VERSION")
        kit = game / "custom" / panorama.KIT_FOLDER
        timer, layout = kit / "panorama" / "layout" / "hud" / "timer.xml", kit / "cfg" / "hud" / "hud_default.kv3"
        own = game / "custom" / inst.FOLDER / inst.TS
        linux = sys.platform != "win32"
        want_layout = LAYOUT.replace(inst.ANCHOR, inst.ENTRY + inst.ANCHOR)

        panorama.install(game, "0-other", "other", OTHER)
        expect(inst.install(game), [], "install skips nothing")
        sett = hub.local_import(HERE / "settings.py", "settings")
        src = (HERE / inst.TS).read_text(encoding="utf-8")
        expect(own.read_text(encoding="utf-8"), sett.bake(src, sett.DEFAULTS), "script copied, default SOUND line")
        expect(timer.read_text().count(INCLUDE), 1, "timer.xml includes Z Penalty once")
        expect(timer.read_text().count("other.ts"), 1, "the other tool's timer.xml include kept")
        expect(layout.read_text(), want_layout, "hud_default.kv3: the entry once, before CustomizerSettings")
        expect(layout.read_text().count("MovekitZPenalty = "), 1, "one entry")
        if linux:
            expect(launch.registered().get("z-penalty", (None,))[0], inst.HOOK_ORDER, "launch hook registered")
        before = {p: p.read_bytes() for p in kit.rglob("*") if p.is_file()}
        expect(inst.install(game, quiet=True), [], "second install skips nothing")
        expect({p: p.read_bytes() for p in kit.rglob("*") if p.is_file()}, before, "installing again changes nothing")

        # another HUD mod with its own hud_default.kv3 in custom/: that copy is the base
        mod = game / "custom" / "a-hudmod" / "cfg" / "hud" / "hud_default.kv3"
        mod.parent.mkdir(parents=True)
        mod.write_text(LAYOUT.replace("offsetX = 300", "offsetX = 111"))
        inst.install(game, quiet=True)
        expect("offsetX = 111" in layout.read_text() and layout.read_text().count("MovekitZPenalty = ") == 1, True,
               "a mod's kv3 as the base, entry once")
        mod.unlink()

        # a game update without the anchor: the entry is left out and reported, the include stays
        real_layout = game / "cfg" / "hud" / "hud_default.kv3"
        real_layout.write_text(LAYOUT.replace("CustomizerSettings", "Settings"))
        skipped = inst.install(game, quiet=True)
        expect([r["file"] for r in skipped], ["cfg/hud/hud_default.kv3"], "changed kv3 reported")
        expect(layout.exists(), False, "no kit copy of a kv3 no patch fits")
        expect(timer.read_text().count(INCLUDE), 1, "the include stays when the entry is left out")
        real_layout.write_text(LAYOUT)

        # uninstall: its lines go, the other tool's stay
        inst.install(game, quiet=True)
        inst.uninstall(game)
        expect((game / "custom" / inst.FOLDER).exists(), False, "own folder removed")
        expect(INCLUDE in timer.read_text(), False, "timer.xml without its include")
        expect(timer.read_text().count("other.ts"), 1, "the other tool's include kept")
        expect(layout.exists(), False, "no kit copy of hud_default.kv3")
        if linux:
            expect("z-penalty" in launch.registered(), False, "launch hook removed")

        # a failed sync keeps the script, so the kit's timer.xml never includes a missing file
        inst.install(game, quiet=True)
        real = panorama.uninstall
        def broken(*_a, **_k):
            raise OSError("locked")
        panorama.uninstall = broken
        try:
            inst.uninstall(game)
        finally:
            panorama.uninstall = real
        expect(own.is_file(), True, "script kept when the sync fails")
        expect(INCLUDE in timer.read_text(), True, "include kept when the sync fails")
        inst.uninstall(game)
        panorama.uninstall(game, "0-other")
        expect(kit.exists(), False, "kit folder gone with no patches left")

        # no game: uninstall still finishes (launch hook)
        inst.install(game, quiet=True)
        inst.uninstall(None)
        if linux:
            expect("z-penalty" in launch.registered(), False, "launch hook removed with no game")
        inst.uninstall(game)

        # the module hooks, as the kit's module manager calls them
        hooks = modules.Manager(kit_root=KIT, data=tmp / "mgr")._hooks("z-penalty")
        ctx = modules.Context(HERE, KIT, modules.read_manifest(HERE))
        hooks.install(ctx)
        expect(INCLUDE in timer.read_text() and own.is_file() and layout.is_file(), True, "install hook")
        layout.unlink()
        hooks.launch(ctx, ["game.exe"])
        expect(layout.read_text(), want_layout, "launch hook syncs again")
        hooks.uninstall(ctx)
        expect(kit.exists() or own.exists(), False, "uninstall hook")
        os.environ["MOMENTUM_DIR"] = str(tmp / "nogame")
        try:
            hooks.install(ctx)
            fail("install hook with no game didn't raise")
        except RuntimeError:
            pass
        hooks.uninstall(ctx)
        hooks.launch(ctx, ["game.exe"])  # no game: nothing, no error
        os.environ["MOMENTUM_DIR"] = str(game)
        check_sound(sett, inst, hub, game, own, src)
    print("check_z_penalty: all good")


if __name__ == "__main__":
    main()
