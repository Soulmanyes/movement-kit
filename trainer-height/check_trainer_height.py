"""Checks Strafe Trainer Height's install.py and module hooks on a fake game folder (4.3 in PLAN.md).

- install: the old hand-installed custom/strafe-trainer-height goes (before the kit picks it as the
  base), the stylesheet is in custom/movekit-trainer-height, both game files in custom/0-movekit are
  patched once, and the Linux launch hook is registered; installing again changes nothing.
- another tool's patches to the same files (Strafe Review's timer.xml include, and a line in
  strafe-trainer.xml) are kept alongside, and uninstalling this module leaves them.
- a game update that removes resizeY: false, leaves that patch out and reports it; the install
  still works.
- uninstall: patches first, then the stylesheet; the launch hook goes; with no game found it still
  finishes. The module hooks do the same through the kit's module manager's Context.

Usage: python trainer-height/check_trainer_height.py   (exits 1 on a failure)
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent

XML = """<root>
\t<styles>
\t\t<include src="file://{resources}/styles/main.scss" />
\t</styles>
\t<scripts>
\t\t<include type="module" src="file://{scripts}/hud/strafe-trainer.ts" />
\t</scripts>
\t<MomHudStrafeTrainer class="strafetrainer" />
</root>
"""
TS = "const cfg = {\n\tresizeX: true,\n\tresizeY: false,\n};\n"
TIMER = "<root>\n\t<scripts>\n\t\t<include src=\"a.ts\" />\n\t</scripts>\n</root>\n"
OTHER = [  # another tool's patches, the way Strafe Review hands its own to the kit
    {"file": "panorama/layout/hud/timer.xml", "before": "</scripts>", "line": '<include src="other.ts" />'},
    {"file": "panorama/layout/hud/strafe-trainer.xml", "before": "</scripts>", "line": '<include src="other2.ts" />'},
]
INCLUDE = '<include src="file://{resources}/styles/hud/strafe-trainer-height.scss" />'


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def fake_game(root):
    game = root / "momentum"
    for rel, text in (("panorama/layout/hud/strafe-trainer.xml", XML), ("panorama/scripts/hud/strafe-trainer.ts", TS),
                      ("panorama/layout/hud/timer.xml", TIMER)):
        (game / rel).parent.mkdir(parents=True, exist_ok=True)
        (game / rel).write_text(text)
    (game / "cfg").mkdir()
    # the mod as installed by hand: whole copies of the two files, already changed
    old = game / "custom" / "strafe-trainer-height" / "panorama"
    for rel, text in (("layout/hud/strafe-trainer.xml", XML.replace("\t</styles>", f"\t\t{INCLUDE}\n\t</styles>")),
                      ("scripts/hud/strafe-trainer.ts", TS.replace("resizeY: false,", "resizeY: true, // old")),
                      ("styles/hud/strafe-trainer-height.scss", "// old\n")):
        (old / rel).parent.mkdir(parents=True, exist_ok=True)
        (old / rel).write_text(text)
    return game


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
        xml, ts, timer = (kit / "panorama" / "layout" / "hud" / "strafe-trainer.xml",
                          kit / "panorama" / "scripts" / "hud" / "strafe-trainer.ts",
                          kit / "panorama" / "layout" / "hud" / "timer.xml")
        own = game / "custom" / inst.FOLDER / inst.SCSS
        linux = sys.platform != "win32"

        panorama.install(game, "0-other", "other", OTHER)
        expect(inst.install(game), [], "install skips nothing")
        expect((game / "custom" / "strafe-trainer-height").exists(), False, "old hand-installed folder removed")
        expect(own.read_bytes(), (HERE / inst.SCSS).read_bytes(), "stylesheet copied")
        want_xml = XML.replace("\t</styles>", f"\t\t{INCLUDE}\n\t</styles>").replace(
            "\t</scripts>", '\t\t<include src="other2.ts" />\n\t</scripts>')
        expect(xml.read_text(), want_xml, "strafe-trainer.xml: both tools' lines, from the game's own file")
        expect(ts.read_text(), TS.replace("resizeY: false,", "resizeY: true,"), "strafe-trainer.ts patched once")
        expect(timer.read_text().count("other.ts"), 1, "the other tool's timer.xml include kept")
        if linux:
            expect(launch.registered().get("trainer-height", (None,))[0], inst.HOOK_ORDER, "launch hook registered")
        before = {p: p.read_bytes() for p in kit.rglob("*") if p.is_file()}
        expect(inst.install(game, quiet=True), [], "second install skips nothing")
        expect({p: p.read_bytes() for p in kit.rglob("*") if p.is_file()}, before, "installing again changes nothing")

        # a game update that drops the line the .ts patch looks for: left out and reported, the rest stays
        orig_ts = (game / "panorama" / "scripts" / "hud" / "strafe-trainer.ts").read_text()
        (game / "panorama" / "scripts" / "hud" / "strafe-trainer.ts").write_text(orig_ts.replace("resizeY", "sizeY"))
        skipped = inst.install(game, quiet=True)
        expect([r["file"] for r in skipped], ["panorama/scripts/hud/strafe-trainer.ts"], "changed .ts reported")
        expect(ts.exists(), False, "no kit copy of a .ts no patch fits")
        expect(xml.read_text(), want_xml, "the .xml patch stays when the .ts one is left out")
        (game / "panorama" / "scripts" / "hud" / "strafe-trainer.ts").write_text(orig_ts)

        # uninstall: this module's lines go, the other tool's stay
        inst.uninstall(game)
        expect(own.parent.parent.parent.parent.exists(), False, "own folder removed")
        expect(xml.read_text(), XML.replace("\t</scripts>", '\t\t<include src="other2.ts" />\n\t</scripts>'),
               "strafe-trainer.xml keeps only the other tool's line")
        expect(ts.exists(), False, "no kit copy of strafe-trainer.ts")
        expect(timer.read_text().count("other.ts"), 1, "timer.xml unchanged")
        if linux:
            expect("trainer-height" in launch.registered(), False, "launch hook removed")

        # a failed sync keeps the stylesheet, so the kit's .xml never includes a missing file
        inst.install(game, quiet=True)
        real = panorama.uninstall
        def broken(*_a, **_k):
            raise OSError("locked")
        panorama.uninstall = broken
        try:
            inst.uninstall(game)
        finally:
            panorama.uninstall = real
        expect(own.is_file(), True, "stylesheet kept when the sync fails")
        expect(INCLUDE in xml.read_text(), True, "include kept when the sync fails")
        inst.uninstall(game)
        panorama.uninstall(game, "0-other")
        expect(kit.exists(), False, "kit folder gone with no patches left")

        # no game: uninstall still finishes (launch hook), install refuses
        inst.install(game, quiet=True)
        inst.uninstall(None)
        if linux:
            expect("trainer-height" in launch.registered(), False, "launch hook removed with no game")
        inst.uninstall(game)

        # the module hooks, as the kit's module manager calls them
        hooks = modules.Manager(kit_root=KIT, data=tmp / "mgr")._hooks("trainer-height")
        ctx = modules.Context(HERE, KIT, modules.read_manifest(HERE))
        hooks.install(ctx)
        expect(INCLUDE in xml.read_text() and own.is_file(), True, "install hook")
        xml.unlink()
        hooks.launch(ctx, ["game.exe"])
        expect(INCLUDE in xml.read_text(), True, "launch hook syncs again")
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
    print("check_trainer_height: all good")


if __name__ == "__main__":
    main()
