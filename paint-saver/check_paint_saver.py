"""Checks Paint Saver's log reader, savedlocs.txt editor, install.py and module hooks on a fake game folder.

- paintlog.apply_lines: strokes from MK_PAINT_DOWN/S/UP with the getpos answer right after each S marker
  (a glued "...restore.setpos" line too), a stray line between them drops only that sample, a manual getpos
  without a marker adds nothing; MK_PAINT_SAVE saves the map's pending strokes from every visit this session,
  MK_PAINT_CLEAR drops saved and pending, an unsaved stroke on another map is dropped.
- paintlog.read_log: the first run only bookmarks the end; later runs read only new lines, a cut last line
  waits; a new log (other head) is read from the start.
- savedlocs.rewrite_text: an untouched file stays byte for byte; zzpaint_ blocks are replaced, never
  duplicated; a cut-short restore's leftovers (a run from the first paint sample on) in a map block go and
  the rest is renumbered, a lone savestate on a paint sample stays; entries carry zero velocity and
  duckAmount 0.
- install: the script with the replay plan in it, the timer.xml include once, the autoexec block with the
  aliases and +mkpaint binds for config.cfg's +paint keys (and +mkpaint keys, after the game wrote them back);
  --launch reads yaw.log and writes savedlocs.txt, a plain install doesn't; uninstall binds +paint back and
  takes the zzpaint_ blocks out.

Usage: python paint-saver/check_paint_saver.py   (exits 1 on a failure)
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
sys.path.insert(0, str(HERE))
import paintlog  # after the path above
import savedlocs  # after the path above

TIMER = "<root>\n\t<scripts>\n\t\t<include type=\"module\" src=\"file://{scripts}/hud/timer.ts\" />\n\t</scripts>\n</root>\n"
INCLUDE = '<include type="module" src="file://{scripts}/hud/movekit-paint-saver.ts" />'
POS = "[client_mo] setpos {} {} {};setang {} {} 0.000000"
OWN = {"pos": [1.0, 2.0, 3.03125], "ang": [5.0, 90.0, 0.0], "duck": 0}
SAVEDLOCS = '"MOMSavelocSystem"\n{\n' + savedlocs.block("x", [OWN]).replace('"zzpaint_x"', '"surf_a"') + "}\n"


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def stroke(x, duck=0, n=2, c="255 0 0 255", s="2"):
    lines = [f'[panorama] MK_PAINT_DOWN {{"c":"{c}","s":"{s}"}}']
    for i in range(n):
        lines += [f'[panorama] MK_PAINT_S {{"d":{duck}}}', POS.format(x + i, 0.5, 64.03125, 10.0, 45.0)]
    return [*lines, "[panorama] MK_PAINT_UP"]


def check_apply():
    maps = {}
    lines = (["[engine] Host_NewGame on map surf_a", *stroke(0), "[engine] Host_NewGame on map surf_a",
              *stroke(10, duck=1, n=1),
              '[panorama] MK_PAINT_DOWN {"c":"0 0 255 255","s":"5"}', '[panorama] MK_PAINT_S {"d":0}',
              "[engine] This game doesn't support save/restore." + POS.format(20, 0, 0, 0, 0)[11:],
              '[panorama] MK_PAINT_S {"d":0}', "[client_mo] something else", POS.format(30, 0, 0, 0, 0),
              "[panorama] MK_PAINT_UP", POS.format(99, 0, 0, 0, 0), "[panorama] MK_PAINT_SAVE",
              "[engine] Host_NewGame on map surf_b", *stroke(50)])
    rep = paintlog.apply_lines(lines, maps)
    expect(list(maps), ["surf_a"], "only the saved map")
    expect([len(s["p"]) for s in maps["surf_a"]], [2, 1, 1], "strokes from both visits; the stray line drops one sample")
    expect(maps["surf_a"][1]["p"][0][5], 1, "duck flag")
    expect(maps["surf_a"][2]["p"][0][0], 20.0, "glued getpos line read")
    expect(maps["surf_a"][2]["c"], "0 0 255 255", "stroke colour")
    expect(rep["dropped"], 1, "surf_b's unsaved stroke dropped")
    rep = paintlog.apply_lines(["[engine] Host_NewGame on map surf_a", *stroke(70), "[panorama] MK_PAINT_SAVE"], maps)
    expect(len(maps["surf_a"]), 4, "a later save adds to the saved paint")
    paintlog.apply_lines(["[engine] Host_NewGame on map surf_a", *stroke(80), "[panorama] MK_PAINT_CLEAR"], maps)
    expect(maps, {}, "clear drops saved and pending")
    plan = paintlog.replay_plan({"m": [{"c": "1 2 3 4", "s": "3", "p": [[0] * 6] * 4}]})
    expect(plan, {"m": [["1 2 3 4", "3", 4, 0]]}, "replay plan")
    mixed = [{"c": "a", "s": "1", "p": [[0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 1], [2, 0, 0, 0, 0, 1], [3, 0, 0, 0, 0, 0]]},
             {"c": "b", "s": "2", "p": [[4, 0, 0, 0, 0, 0]]}]
    expect(paintlog.replay_plan({"m": mixed}),
           {"m": [["a", "1", 1, 0], ["a", "1", 1, 0], ["b", "2", 1, 0], ["a", "1", 2, 1]]},
           "replay plan: standing runs first, crouched last")
    expect([s["pos"][0] for s in paintlog.samples(mixed)], [0, 3, 4, 1, 2], "samples in the same order")
    expect([s["pos"][2] for s in paintlog.samples(mixed)], [-64, -64, -64, -47, -47],
           "samples written lower by the import's lift")


def check_read_log(tmp):
    log = tmp / "yaw.log"
    log.write_text("\n".join(["[engine] Host_NewGame on map surf_a", *stroke(0), "[panorama] MK_PAINT_SAVE", ""]))
    data = paintlog.empty()
    expect(paintlog.read_log(log, data), None, "first run only bookmarks")
    expect(data["maps"], {}, "nothing from before the install")
    with open(log, "a") as f:
        f.write("\n".join(["[engine] Host_NewGame on map surf_a", *stroke(5), "[panorama] MK_PAINT_SAVE", "[panorama] MK_PA"]))
    paintlog.read_log(log, data)
    expect(len(data["maps"]["surf_a"]), 1, "new lines read")
    with open(log, "a") as f:
        f.write("INT_CLEAR\n")
    paintlog.read_log(log, data)
    expect(data["maps"], {}, "the cut line read once whole")
    log.write_text("\n".join(["[engine] Host_NewGame on map surf_c", *stroke(0), "[panorama] MK_PAINT_SAVE", ""]))
    paintlog.read_log(log, data)
    expect(list(data["maps"]), ["surf_c"], "a new log read from the start")


def check_savedlocs():
    paint = [{"pos": [7.0, 8.0, 9.0], "ang": [1.0, 2.0, 0.0], "duck": 1}]
    expect(savedlocs.rewrite_text(SAVEDLOCS, {})[0], SAVEDLOCS, "nothing to do: the same bytes")
    once, _ = savedlocs.rewrite_text(SAVEDLOCS, {"surf_a": paint})
    twice, _ = savedlocs.rewrite_text(once, {"surf_a": paint})
    expect(once, twice, "rewriting again changes nothing")
    expect(once.count('"zzpaint_surf_a"'), 1, "one paint block")
    expect(once.startswith(SAVEDLOCS[:-2]), True, "the map block kept as it was")
    body = once.split('"zzpaint_surf_a"')[1]
    expect('"duckAmount"\t\t"0.000000"' in body and '"crouched"\t\t"1"' in body, True, "crouched, duckAmount 0")
    expect('"vel"\t\t"0.000000 0.000000 0.000000"' in body, True, "zero velocity")
    # a quit mid-restore leaves imported copies at the end of the map's list
    left = SAVEDLOCS.replace("\t\t}\n\t}\n}", savedlocs.entry(1, paint[0]).rstrip("\n") + "\n\t\t}\n\t}\n}")
    expect(left.count('"000000001"'), 1, "test file holds a leftover")
    clean, rep = savedlocs.rewrite_text(left, {"surf_a": paint})
    expect(rep["removed"], {"surf_a": 1}, "leftover found")
    expect(clean, once, "leftover removed")
    expect(savedlocs.rewrite_text(once, {})[0], SAVEDLOCS, "no paint: the block goes")
    two = [*paint, {"pos": [17.0, 8.0, 9.0], "ang": [1.0, 2.0, 0.0], "duck": 0}]
    own_dot = SAVEDLOCS.replace("\t\t}\n\t}\n}", savedlocs.entry(1, two[0]).rstrip("\n") + "\n\t\t}\n\t}\n}")
    expect(savedlocs.rewrite_text(own_dot, {"surf_a": two})[1]["removed"], {}, "a lone savestate where a dot was: kept")
    cut = SAVEDLOCS.replace("\t\t}\n\t}\n}", (savedlocs.entry(1, two[0]) + savedlocs.entry(2, two[1])
                                              + savedlocs.entry(3, OWN)).rstrip("\n") + "\n\t\t}\n\t}\n}")
    clean, rep = savedlocs.rewrite_text(cut, {"surf_a": two})
    expect(rep["removed"], {"surf_a": 2}, "a cut-short restore's run, with a savestate made after it")
    expect(clean.count('"pos"\t\t"1.000000 2.000000 3.031250"'), 2, "own savestates kept, renumbered")
    expect('"000000001"' in clean and '"000000002"' not in clean, True, "renumbered")


def check_install(tmp):
    for var, sub in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("LOCALAPPDATA", "data")):
        os.environ[var] = str(tmp / sub)
    os.environ["HOME"] = str(tmp / "home")
    game = tmp / "momentum"
    (game / "panorama/layout/hud").mkdir(parents=True)
    (game / "panorama/layout/hud/timer.xml").write_text(TIMER)
    (game / "cfg").mkdir()
    config = game / "cfg" / "config.cfg"
    config.write_text('bind "MOUSE5" "+paint"\nbind "h" "+paint"\nbind "w" "+forward"\n')
    (game / "savedlocs.txt").write_text(SAVEDLOCS)
    log = game / "yaw.log"
    log.write_text("[engine] old\n")
    os.environ["MOMENTUM_DIR"] = str(game)
    sys.path.insert(0, str(KIT))
    from movekit import hub, keys, launch, modules, panorama

    inst = hub.local_import(HERE / "install.py", "install")
    expect(modules.module_version(HERE, modules.read_manifest(HERE)), inst.VERSION, "module.json reads VERSION")
    timer = game / "custom" / panorama.KIT_FOLDER / "panorama/layout/hud/timer.xml"
    own = game / "custom" / inst.FOLDER / inst.TS
    autoexec = game / "cfg" / "autoexec.cfg"

    # both switches start off: the paint keys stay +paint, and the commands say they're off
    expect(inst.read_settings(), {"save": False, "load_off": False}, "switches off at first")
    expect(inst.install(game, quiet=True), [], "install skips nothing")
    text = autoexec.read_text()
    expect(("+mkpaint" in config.read_text(), "bind " in text, text.count('alias +mkpaint "+paint"')),
           (False, False, 1), "saving off: no binds, +mkpaint only paints")
    expect([f'echo {inst.OFF_SAVE}' in text, f'echo {inst.OFF_LOAD}' in text, ";" in inst.OFF_SAVE + inst.OFF_LOAD],
           [True, True, False], "saving off: mk_savepaint and mk_loadpaint say so")
    expect(keys.held_by_others("x", "momentum"), {}, "saving off: no keys held")
    inst.write_settings({"save": True, "load_off": False})
    expect(inst.install(game, quiet=True), [], "install skips nothing")
    expect(timer.read_text().count(INCLUDE), 1, "timer.xml includes Paint Saver once")
    expect("const PLAN: Record<string, [string, string, number, number?][]> = {};" in own.read_text(), True, "empty plan")
    text = autoexec.read_text()
    for line in ('bind "h" "+mkpaint"', 'bind "MOUSE5" "+mkpaint"', 'alias +mkpaint "+paint; hostname mkpaint1"',
                 'alias mk_savepaint "hostname mkpaintsave"', 'alias mk_loadpaint "hostname mkpaintrestore"',
                 "con_logfile yaw.log"):
        expect(text.count(line), 1, f"autoexec: {line}")
    expect("+forward" in text, False, "other binds left alone")
    expect(keys.held_by_others("x", "momentum"), {"h": "paint-saver", "mouse5": "paint-saver"}, "keys recorded")
    expect(json.loads(inst.data_file().read_text())["log"]["offset"], log.stat().st_size, "first install bookmarks")
    if sys.platform != "win32":
        expect(launch.registered().get("paint-saver", (None,))[0], inst.HOOK_ORDER, "launch hook registered")

    # a session: paint on surf_a, save, quit; the game writes +mkpaint back into config.cfg
    with open(log, "a") as f:
        f.write("\n".join(["[engine] Host_NewGame on map surf_a", *stroke(0, n=3), "[panorama] MK_PAINT_SAVE", ""]))
    config.write_text(config.read_text().replace('"+paint"', '"+mkpaint"'))
    inst.install(game, quiet=True)
    expect((game / "savedlocs.txt").read_text(), SAVEDLOCS, "a plain install leaves savedlocs.txt")
    expect(autoexec.read_text().count('bind "h" "+mkpaint"'), 1, "+mkpaint keys still found")
    expect("= {};" in own.read_text(), True, "a plain install: no plan for paint not yet in savedlocs.txt")
    inst.install(game, quiet=True, launch=True)
    loc = (game / "savedlocs.txt").read_text()
    expect(loc.count('"zzpaint_surf_a"'), 1, "launch writes the paint block")
    expect(len(re.findall(r'^\t\t\t"\d{9}"$', loc.split("zzpaint_surf_a")[1], re.MULTILINE)), 3, "three entries")
    expect('{"surf_a":[["255 0 0 255","2",3,0]]}' in own.read_text(), True, "plan in the script")
    inst.install(game, quiet=True, launch=True)
    expect((game / "savedlocs.txt").read_text(), loc, "launch again: the same file")

    # saving off, loading kept: keys back to +paint at the start, the block and plan stay
    inst.write_settings({"save": False, "load_off": True})
    inst.install(game, quiet=True, launch=True)
    text = autoexec.read_text()
    expect((config.read_text().count('"+paint"'), "bind " in text), (2, False), "saving off: keys bound back at launch")
    expect(('alias mk_loadpaint "hostname mkpaintrestore"' in text, (game / "savedlocs.txt").read_text() == loc,
            '{"surf_a":' in own.read_text()), (True, True, True), "loading while saving is off")
    # both off: no paint block, no plan, paint.json keeps the paint
    inst.write_settings({"save": False, "load_off": False})
    inst.install(game, quiet=True, launch=True)
    expect(((game / "savedlocs.txt").read_text(), "= {};" in own.read_text(), f"echo {inst.OFF_LOAD}" in autoexec.read_text()),
           (SAVEDLOCS, True, True), "loading off: block out, empty plan")
    expect(len(paintlog.load(inst.data_file())["maps"]["surf_a"]), 1, "loading off keeps the saved paint")
    inst.write_settings({"save": True, "load_off": False})
    inst.install(game, quiet=True, launch=True)
    expect((game / "savedlocs.txt").read_text(), loc, "on again: the same block")

    # the hub's buttons: sent through the net console, the game's echo read back from yaw.log
    section = hub.local_import(HERE / "hub_section.py", "hub_section")
    sent = []

    class Net:
        @staticmethod
        def is_open(game_key, config):
            return True

        @staticmethod
        def send(game_key, command, config):
            sent.append(command)
            with open(log, "a") as f:
                f.write("] mk_clearpaint\n[vstdlib] Paint Saver: cleared the saved paint on surf_a \n")
            return True

    section._netcon = lambda: (Net, tmp)
    expect(section.run("clear"), {"sent": True, "messages": ["cleared the saved paint on surf_a"]}, "button: the game's answer")
    expect(sent, ["mk_clearpaint"], "button: the command sent")
    section._netcon = lambda: None
    expect(section.run("load"), {"sent": False, "messages": [section.NOT_OPEN, "mk_loadpaint"]},
           "button without the net console: the command to type")

    hooks = hub.local_import(HERE / "module_hooks.py", "module_hooks")
    expect(callable(hooks.launch), True, "module hook launch")

    inst.uninstall(game)
    expect(config.read_text().count('"+paint"'), 2, "uninstall binds +paint back")
    expect((game / "savedlocs.txt").read_text(), SAVEDLOCS, "uninstall takes the paint block out")
    expect("mkpaint" in autoexec.read_text(), False, "autoexec block gone")
    expect(own.exists(), False, "script removed")
    expect(INCLUDE in timer.read_text() if timer.exists() else False, False, "include removed")
    expect(keys.held_by_others("x", "momentum"), {}, "keys forgotten")
    if sys.platform != "win32":
        expect("paint-saver" in launch.registered(), False, "launch hook removed")


def replay_lines(total, got, m="m"):
    """A replay's log: RESTORE, then each point's R marker and getpos answer (x, y, z)."""
    lines = [f'[panorama] MK_PAINT_RESTORE {{"map":"{m}","strokes":1,"total":{total},"before":0,"v":2}}']
    for k, (x, y, z) in enumerate(got, 1):
        lines += [f'[panorama] MK_PAINT_R {{"k":{k}}}', POS.format(x, y, z, 0.0, 0.0)]
    return lines


def check_replay_feedback():
    def pt(x, duck=0):
        return [float(x), 0.0, 100.0, 0.0, 0.0, duck]  # pitch 0, yaw 0: the aim is +x
    maps = {"m": [{"c": "a", "s": "1", "p": [pt(0), pt(10), pt(20)]}]}
    rep = paintlog.apply_lines(replay_lines(3, [(0, 0, 100), (10, 0, 88), (20, 0, 101.5)]), maps, "m")
    p = maps["m"][0]["p"]
    expect((rep["moved"], rep["stuck"]), (1, 0), "one missed point found")
    expect([len(p[0]), p[1][6:], len(p[2])], [6, [0.0, 1, 12.0], 6],
           "only the missed one changes (12 low: written 12 higher); a small fall counts as placed")
    expect([round(v, 3) for v in paintlog.samples(maps["m"])[1]["pos"]], [10.0, 0.0, 48.0],
           "the import's lift less 12")
    paintlog.apply_lines(replay_lines(3, [(0, 0, 100), (10, 0, 100), (20, 0, 100)]), maps, "m")
    expect(p[1][6:], [0.0, 1, 12.0], "a point that lands stays")
    # missed straight down every time: lifted _LIFT_TRIES times, then moved back, then given up
    seen = []
    for _ in range(paintlog.MAX_TRIES):
        x, y, z = paintlog.shift(p[1])
        paintlog.apply_lines(replay_lines(3, [(0, 0, 100), (x, y, z - 12), (20, 0, 100)]), maps, "m")
        seen.append(p[1][6:])
    expect(seen, [[0.0, 2, 24.0], [-16.0, 3, 0.0], [-32.0, 4, 0.0], [0.0, -1, 0.0], [0.0, -1, 0.0]],
           "lift, then back by the push and a margin (16 at least), then given up")
    expect((paintlog.stuck(maps["m"]), paintlog.samples(maps["m"])[1]["pos"]), (1, [10.0, 0.0, 36.0]),
           "a given-up point paints from its own spot")
    rep = paintlog.apply_lines(replay_lines(3, [(0, 0, 100), (9, 0, 0), (20, 0, 100)]), maps, "m")
    expect((rep["moved"], rep["stuck"], p[1][6:], len(p[0])), (0, 0, [0.0, -1, 0.0], 6), "given up stays given up")
    # pushed sideways: blocked where it is, so back along the aim (aiming 30 down: back is up), never forward
    side = {"m": [{"c": "a", "s": "1", "p": [[0.0, 0.0, 100.0, 30.0, 0.0, 0]]}]}
    paintlog.apply_lines(replay_lines(1, [(0, 20, 100)]), side, "m")
    q = side["m"][0]["p"][0]
    expect([round(v, 3) for v in [q[6], *paintlog.shift(q)]], [-24.0, -20.785, 0.0, 112.0], "back by push + margin")
    paintlog.apply_lines(replay_lines(1, [(-20.785, 0, 112)]), side, "m")
    expect(q[6:], [-24.0, 1, 0.0], "and it lands there")
    paintlog.apply_lines(replay_lines(4, [(5, 5, 5)] * 3), maps, "m")
    expect(len(p[0]), 6, "a replay of another plan (other total) is not read")
    paintlog.apply_lines([s.replace(',"v":2', "") for s in replay_lines(3, [(5, 5, 5)] * 3)], maps, "m")
    expect(len(p[0]), 6, "a replay from before the settle wait is not read")
    paintlog.apply_lines([*replay_lines(3, [(0, 0, 100)]), "[engine] Host_NewGame on map m",
                          '[panorama] MK_PAINT_R {"k":1}', POS.format(7, 7, 7, 0.0, 0.0)], maps, "m")
    expect(len(p[0]), 6, "a map load ends the replay")
    # the replay order is the one last written: a stroke saved in the same log doesn't shift k
    maps = {"m": [{"c": "a", "s": "1", "p": [pt(0)]}, {"c": "b", "s": "1", "p": [pt(50, 1)]}]}
    lines = [*stroke(30), "[panorama] MK_PAINT_SAVE", *replay_lines(2, [(0, 0, 100), (50, 0, 80)])]
    paintlog.apply_lines(lines, maps, "m")
    expect([len(maps["m"][0]["p"][0]), maps["m"][1]["p"][0][7], len(maps["m"][2]["p"][0])], [6, 1, 6],
           "k counts in the order as written, before this log's save")
    # leftovers of the last write are found even after a slide moved the point
    old = [{"pos": [1.0, 2.0, 3.0], "ang": [0.0, 0.0, 0.0], "duck": 0},
           {"pos": [4.0, 5.0, 6.0], "ang": [0.0, 0.0, 0.0], "duck": 0}]
    new = [old[0], {"pos": [20.0, 5.0, 6.0], "ang": [0.0, 0.0, 0.0], "duck": 0}]
    own = "".join(savedlocs.entry(i, s) for i, s in enumerate(old))
    text = f'"MOMSavelocSystem"\n{{\n\t"m"\n\t{{\n\t\t"cps"\n\t\t{{\n{own}\t\t}}\n\t}}\n}}\n'
    expect(savedlocs.rewrite_text(text, {"m": new}, {"m": old})[1]["removed"], {"m": 2}, "leftovers by the last write")
    expect(savedlocs.rewrite_text(text, {"m": new})[1]["removed"], {}, "not by the new one")


def main():
    check_apply()
    check_replay_feedback()
    check_savedlocs()
    with tempfile.TemporaryDirectory() as tmp:
        check_read_log(Path(tmp))
        (Path(tmp) / "inst").mkdir()
        check_install(Path(tmp) / "inst")
    print("check_paint_saver: all passed")


if __name__ == "__main__":
    main()
