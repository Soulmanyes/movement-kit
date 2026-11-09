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

- install writes the autoexec block (con_logfile yaw.log) once; uninstall takes it out.
- the tone settings (settings.py): bad values are refused, numbers clamped, an old sound file still
  loads; the hub section's apply saves them.
- the tone runner (tone_run.py): ZPEN_ON/ZPEN_OFF turn a fake tone on and off, map_left and MAX_ON
  stop it, a settings change rebuilds or closes it, and run() reads the markers from a growing log.

The display logic and the kv3 entry's values are checked by check_z_penalty.js.

Usage: python z-penalty/check_z_penalty.py   (exits 1 on a failure)
"""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import ClassVar

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


def check_tone_settings(sett, hub):
    """settings.check and load, and the hub section's apply."""
    for bad in ({"pitch": "9"}, {"pitch": True}, {"volume": float("nan")}, {"volume": None}, {"on": 1}, []):
        try:
            sett.check(bad)
            fail(f"settings.check took {bad!r}")
        except ValueError:
            pass
    expect(sett.check({"volume": 250, "pitch": 5})["volume"], 100, "volume clamped high")
    expect(sett.check({"pitch": 5})["pitch"], sett.PITCH[0], "pitch clamped low")
    expect(sett.check({"pitch": 99999})["pitch"], sett.PITCH[1], "pitch clamped high")
    expect(sett.load(), sett.DEFAULTS, "no saved file: defaults")
    sett.file().parent.mkdir(parents=True, exist_ok=True)
    sett.file().write_text("{broken")
    expect(sett.load(), sett.DEFAULTS, "unreadable file: defaults")
    sett.file().write_text('{"on": true, "name": "buttons/blip1", "volume": 60}')
    expect(sett.load(), {**sett.DEFAULTS, "on": True, "volume": 60}, "a file from the sound version still loads")
    section = hub.local_import(HERE / "hub_section.py", "hub_section")
    want = {"on": True, "pitch": 440, "volume": 35}
    expect(section.apply(want)["tone"], want, "apply returns the saved tone")
    expect(sett.load(), want, "apply saved the tone")
    try:
        section.apply({"pitch": "high"})
        fail("apply took a bad pitch")
    except ValueError:
        pass
    expect(sett.load(), want, "a refused apply keeps the saved tone")


class FakeTone:
    made: ClassVar[list] = []

    def __init__(self, synth):
        self.synth, self.mode, self.started, self.closed = synth, None, False, False
        FakeTone.made.append(self)

    def start(self):
        self.started = True

    def close(self):
        self.closed = True


def check_runner(sett, hub, tmp):
    """tone_run.Runner and run(): markers to the tone, the cap, map_left, live settings."""
    tr = hub.local_import(HERE / "tone_run.py", "tone_run")
    clock = [100.0]
    sett.save({"on": True, "pitch": 300, "volume": 50})
    FakeTone.made = []
    r = tr.Runner(sett, FakeTone, clock=lambda: clock[0])
    r.reload()
    tone = FakeTone.made[-1]
    expect([tone.started, tone.mode, tone.synth.pitches, tone.synth.volume], [True, None, {"on": 300}, 0.5],
           "tone made from the settings, silent")
    token = lambda name: {"type": "token", "data": {"name": name}}
    r.handle(token("ZPEN_ON"))
    expect(tone.mode, "on", "ZPEN_ON: tone on")
    r.handle(token("ZPEN_OFF"))
    expect(tone.mode, None, "ZPEN_OFF: tone off")
    r.handle(token("ZPEN_ON"))
    r.handle({"type": "map_left", "data": {}})
    expect(tone.mode, None, "map_left: tone off")
    r.handle(token("ZPEN_ON"))
    clock[0] += tr.MAX_ON - 0.1
    r.tick()
    expect(tone.mode, "on", "still on before MAX_ON")
    clock[0] += 0.2
    r.tick()
    expect(tone.mode, None, "off after MAX_ON without ZPEN_OFF")
    # a settings change while sounding: a new tone at the new pitch, still on
    r.handle(token("ZPEN_ON"))
    sett.save({"on": True, "pitch": 500, "volume": 50})
    clock[0] += tr.SETTINGS_EVERY
    r.reload()
    expect([tone.closed, FakeTone.made[-1].synth.pitches, FakeTone.made[-1].mode], [True, {"on": 500}, "on"],
           "a new pitch: old tone closed, new one sounding")
    sett.save({"on": False, "pitch": 500, "volume": 50})
    clock[0] += tr.SETTINGS_EVERY
    r.reload()
    expect([FakeTone.made[-1].closed, r.tone], [True, None], "switched off: the tone closed")
    r.handle(token("ZPEN_ON"))  # nothing to sound, no error
    r.close()

    # run() on a log: markers as the game writes them, in a thread
    sett.save({"on": True, "pitch": 300, "volume": 50})
    log = tmp / "yaw.log"
    log.write_text("old line ZPEN_ON\n")  # an earlier game run: skipped
    FakeTone.made = []
    stop = threading.Event()
    th = threading.Thread(target=tr.run, args=(log, stop, FakeTone, 0.002))
    th.start()

    def wait_for(mode, what):
        end = time.monotonic() + 2
        while time.monotonic() < end:
            if FakeTone.made and FakeTone.made[-1].mode == mode:
                return
            time.sleep(0.005)
        fail(f"run: {what}")
    try:
        time.sleep(0.1)
        expect(FakeTone.made[-1].mode, None, "run: the old log's marker is skipped")
        with log.open("a") as f:
            f.write("[panorama] ZPEN_ON\n")
        wait_for("on", "ZPEN_ON in the log didn't turn the tone on")
        with log.open("a") as f:
            f.write("[panorama] ZPEN_OFF\n")
        wait_for(None, "ZPEN_OFF in the log didn't turn the tone off")
    finally:
        stop.set()
        th.join(2)
    expect([th.is_alive(), FakeTone.made[-1].closed], [False, True], "run: stops and closes the tone")


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
        expect(own.read_bytes(), (HERE / inst.TS).read_bytes(), "script copied")
        autoexec = game / "cfg" / "autoexec.cfg"
        expect(autoexec.read_text().count("con_logfile yaw.log"), 1, "autoexec block: the console log on")
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
        expect("movekit:z-penalty" in autoexec.read_text(), False, "autoexec block removed")
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
        check_tone_settings(sett, hub)
        check_runner(sett, hub, tmp)
    print("check_z_penalty: all good")


if __name__ == "__main__":
    main()
