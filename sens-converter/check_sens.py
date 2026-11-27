#!/usr/bin/env python3
"""Checks sens-converter/hub_section.py: the sensitivity formula (the owner's example: 800 DPI and
sens 0.8 at m_yaw 0.022 is sens 1.466667 at 1600 DPI and m_yaw 0.006), config.cfg's rewrite, and
Apply with the game closed, open with the net console, and open without it. Touches no real game
files: the game folder and the game checks are stand-ins.

Usage: python sens-converter/check_sens.py   (exits 1 on a failure)
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

spec = importlib.util.spec_from_file_location("sens_section", HERE / "hub_section.py")
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

fails = []


def expect(got, want, what):
    if got != want:
        fails.append(f"{what}: got {got!r}, expected {want!r}")


def near(got, want, what, tol=1e-9):
    if abs(got - want) > tol:
        fails.append(f"{what}: got {got}, expected {want}")


# formula
near(sc.new_sens(800, 0.8, 0.022, 1600, 0.006), 800 * 0.8 * 0.022 / (1600 * 0.006), "new sens")
expect(sc.fmt(sc.new_sens(800, 0.8, 0.022, 1600, 0.006)), "1.466667", "the owner's example")
near(sc.cm_per_360(800, 0.8, 0.022), sc.cm_per_360(1600, sc.new_sens(800, 0.8, 0.022, 1600, 0.006), 0.006),
     "cm/360 kept")
expect(sc.fmt(2.0), "2", "fmt drops trailing zeros")
expect(sc.fmt(0.006, 8), "0.006", "fmt of m_yaw")
expect(sc.fmt(1600, 0), "1600", "fmt keeps an integer's zeros")
expect(sc.fmt(1600.0), "1600", "fmt keeps zeros before the point")

with tempfile.TemporaryDirectory() as tmp:
    game = Path(tmp) / "momentum"
    (game / "cfg").mkdir(parents=True)
    cfg = game / "cfg" / "config.cfg"
    original = 'bind "w" "+forward"\r\nm_pitch "0.022"\r\nm_yaw "0.022"\r\nsensitivity "1.65"\r\nvolume "0.5"\r\n'
    cfg.write_bytes(original.encode())

    # read and write config.cfg
    expect(sc.read_mouse(cfg), {"m_yaw": 0.022, "sensitivity": 1.65}, "read_mouse")
    sc.write_mouse(cfg, {"sensitivity": "1.466667", "m_yaw": "0.006"})
    expect(cfg.read_bytes().decode(),
           'bind "w" "+forward"\r\nm_pitch "0.022"\r\nm_yaw "0.006"\r\nsensitivity "1.466667"\r\nvolume "0.5"\r\n',
           "write_mouse in place, CRLF kept, m_pitch untouched")
    expect(cfg.with_name("config.cfg" + sc.BACKUP).read_bytes().decode(), original, "backup of the first version")
    cfg.write_text('volume "1"')
    sc.write_mouse(cfg, {"sensitivity": "2", "m_yaw": "0.01"})
    expect(cfg.read_text(), 'volume "1"\nsensitivity "2"\nm_yaw "0.01"\n', "missing lines added at the end")
    cfg.write_text('sensitivity "1"\nsensitivity "3"\nm_yaw "0.022"\n')
    sc.write_mouse(cfg, {"sensitivity": "2", "m_yaw": "0.022"})
    expect(cfg.read_text(), 'sensitivity "2"\nm_yaw "0.022"\n', "a second sensitivity line dropped")

    # Apply, with stand-ins for the game folder, the running check and Source Yaw's net console
    sc.games.find = lambda key: game
    form = {"old_dpi": "800", "old_sens": "0.8", "old_m_yaw": "0.022", "new_dpi": "1600", "new_m_yaw": "0.006"}
    cfg.write_text('sensitivity "1.65"\nm_yaw "0.022"\n')

    sc.game_running = lambda: False
    r = sc.apply(form)
    expect((r["saved"], r["sens"], r["m_yaw"]), (True, "1.466667", "0.006"), "Apply, game closed")
    expect(sc.read_mouse(cfg), {"sensitivity": 1.466667, "m_yaw": 0.006}, "Apply wrote config.cfg")
    expect(sc.load()["current"], {"sensitivity": 1.466667, "m_yaw": 0.006}, "load reads it back")

    sent = []

    class Net:
        def __init__(self, open_, ok):
            self.open_, self.ok = open_, ok

        def is_open(self, g, config):
            return self.open_

        def send(self, g, command, config):
            sent.append(command)
            return self.ok

    cfg.write_text('sensitivity "1.65"\nm_yaw "0.022"\n')
    sc.game_running = lambda: True
    sc._netcon = lambda: (Net(True, True), Path(tmp))
    r = sc.apply(form)
    expect(r["saved"], True, "Apply, game open with the net console")
    expect(sent, ["sensitivity 1.466667; m_yaw 0.006; host_writeconfig"], "the command sent")
    expect(cfg.read_text(), 'sensitivity "1.65"\nm_yaw "0.022"\n', "config.cfg left to the open game")

    for net, what in ((lambda: None, "no Source Yaw"), (lambda: (Net(False, True), Path(tmp)), "not started by the kit"),
                      (lambda: (Net(True, False), Path(tmp)), "game didn't answer")):
        sc._netcon = net
        r = sc.apply(form)
        expect((r["saved"], r["messages"][-1]), (False, "sensitivity 1.466667; m_yaw 0.006"), f"Apply, game open, {what}")
    expect(cfg.read_text(), 'sensitivity "1.65"\nm_yaw "0.022"\n', "config.cfg untouched while the game is open")

    sc.game_running = lambda: False
    for bad, what in (({**form, "new_dpi": "0"}, "DPI 0"), ({**form, "old_sens": "abc"}, "not a number"),
                      ({**form, "new_m_yaw": "inf"}, "inf")):
        expect(sc.apply(bad)["saved"], False, f"Apply refuses {what}")
    expect(sc.apply({**form, "old_sens": "0,8"})["sens"], "1.466667", "a decimal comma")
    expect(sc.apply({**form, "new_sens": "1.5"})["sens"], "1.5", "the bottom sens as typed")
    expect(sc.apply({**form, "new_sens": "0"})["saved"], False, "Apply refuses a bottom sens of 0")

    # the boxes kept between starts, in a scratch config folder
    os.environ["XDG_CONFIG_HOME"] = str(Path(tmp) / "config")
    expect(sc.read_inputs(), {}, "no saved boxes yet")
    kept = {"old_dpi": "800", "old_m_yaw": "0.022", "new_dpi": "1600"}
    sc.save({**form, "junk": "x"})
    expect(sc.read_inputs(), kept, "only the DPIs and the old m_yaw are saved")
    expect(sc.load()["inputs"], kept, "load gives the saved boxes")
    sc.inputs_file().write_text("[1]")
    expect(sc.read_inputs(), {}, "a broken file reads as none")

    sc.games.find = lambda key: None
    expect(sc.load()["problem"] is not None, True, "load without Momentum")
    expect(sc.apply(form)["saved"], False, "Apply without Momentum")

for f in fails:
    print("FAIL:", f)
if fails:
    sys.exit(1)
print("sens converter: formula, config.cfg and Apply ok")
