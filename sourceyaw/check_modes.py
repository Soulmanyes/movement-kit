#!/usr/bin/env python3
"""Checks Source Yaw's bhop and surf lists (1.9.0) without a game.

Usage: python sourceyaw/check_modes.py [--mutations]   (exits 1 on the first failure)

Covers:
  - yaws.cfg without a surf list is byte-identical to 1.8.0's (that tag's yawcore.py, from git),
    for both games, with and without colours; a saved "trainer" dict (the strafe trainer left
    for its own module in Phase 13) changes nothing;
  - with a surf list, yaws.cfg run through a small console model (aliases, exec, echo, binds):
    the start yawspeed, cycling, the mode key, the auto file's arm landing on the list's start,
    an arm working once, a gamemode cfg's load alias switching only from the other list (silent
    with load_sound off),
    Momentum's colour cfgs;
  - validate() for the surf list and the mode key;
  - mode_watch.Watcher on session events: arm on a map of the other list, clear on a mode token or
    a map of the current list, unknown maps change nothing;
  - apply(): the auto cfg emptied, stale colour cfgs gone, the mode key not unbound, watch.env's AUTO;
    the gamemode cfg blocks by map_modes (the player's own lines kept, our empty files deleted, none
    for CS:S, none with load_switch off); remove_from_game deleting the auto cfg and the blocks; crosshair images for the surf tokens;
  - the hub section's settings()/load() keeping the surf list, the mode key, the auto switch and the
    map-load switch settings;
  - null turnbinds (1.13.0): the +left/+right keys nulled in the console model, found again once the
    game has saved them nulled, put back plain with the option off and by remove_from_game.
--mutations breaks the code in a few ways and expects this check to fail each time.
Everything runs in a temp folder: HOME and the XDG folders point there, the games are fake folders.
"""
import importlib.util
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
OLD_TAG = "sourceyaw-v1.8.0"


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


# ---------------------------------------------------------------- a small Source console

def split_commands(text):
    """Commands of one line or alias body: split on ; and newlines outside quotes, comments gone."""
    out, cur, quoted = [], "", False
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"':
            quoted = not quoted
            cur += c
        elif not quoted and text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif not quoted and c in ";\n":
            out.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    out.append(cur.strip())
    return [c for c in out if c]


def words(command):
    return shlex.split(command, posix=True)


class Console:
    """Aliases, exec (inserted before the rest of the buffer, as the engine does), echo, binds."""

    def __init__(self, cfg_dir):
        self.cfg_dir = Path(cfg_dir)
        self.aliases, self.binds, self.cvars = {}, {}, {}
        self.echoes, self.sounds = [], []
        # kbutton_t's two key slots per turn button (in_main.cpp KeyDown/KeyUp); 0 = free
        self.buttons = {"left": [0, 0], "right": [0, 0]}
        self.code = None  # the key code a bound key's +/- commands get (Momentum passes it on)

    def run(self, text):
        buffer = split_commands(text)
        steps = 0
        while buffer:
            steps += 1
            if steps > 10000:
                fail("console: endless alias loop")
            command = buffer.pop(0)
            w = words(command)
            name, args = w[0], w[1:]
            if name == "alias":
                self.aliases[args[0]] = args[1] if len(args) > 1 else ""
            elif name in self.aliases:
                buffer[:0] = split_commands(self.aliases[name])
            elif name == "exec":
                path = self.cfg_dir / (args[0] if args[0].endswith(".cfg") else args[0] + ".cfg")
                if path.exists():
                    buffer[:0] = split_commands(path.read_text())
            elif name == "echo":
                self.echoes.append(" ".join(args))
            elif name == "play":
                self.sounds.append(args[0])
            elif name == "bind":
                self.binds[args[0]] = args[1]
            elif name == "unbind":
                self.binds.pop(args[0], None)
            elif name in ("cl_yawspeed", "cl_crosshair_color", "con_logfile"):
                self.cvars[name] = args[0]
            elif name in ("+left", "-left", "+right", "-right"):
                if self.code is not None:
                    args = [str(self.code)]
                self.button(name[1:], name[0] == "+", args[0] if args else "")
            else:
                fail(f"console: unknown command {command!r}")

    def press(self, key):
        self.echoes.clear()
        self.run(self.binds[key])
        return self.cvars["cl_yawspeed"]

    def button(self, name, down, arg):
        """KeyDown/KeyUp of the Source SDK's in_main.cpp: a key code per slot, -1 for none given;
        an up without a code frees both slots."""
        slots = self.buttons[name]
        k = int(arg) if arg else -1
        if down:
            if k in slots:
                return
            if not slots[0]:
                slots[0] = k
            elif not slots[1]:
                slots[1] = k
        elif not arg:
            slots[:] = [0, 0]
        elif k in slots:
            slots[slots.index(k)] = 0

    def hold(self, key, down=True, code=None):
        """A key down (or up: the bind's -command, as the engine runs for a +command bind). With
        `code`, the +/- turn commands it runs get that key code in place of their own, as Momentum
        does. Returns the way the view turns: ["left"], ["right"] or []."""
        command = self.binds[key]
        self.code = code
        self.run(command if down else "-" + command[1:])
        self.code = None
        net = (any(self.buttons["left"]) - any(self.buttons["right"])) * float(self.cvars["cl_yawspeed"])
        return ["left"] if net > 0 else ["right"] if net < 0 else []


# ---------------------------------------------------------------- the checks

def load_old_yawcore():
    """1.8.0's yawcore.py from git, or None when the tag isn't there."""
    try:
        text = subprocess.run(["git", "-C", str(KIT), "show", f"{OLD_TAG}:sourceyaw/yawcore.py"],
                              capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    path = Path(tempfile.mkdtemp()) / "yawcore_old.py"
    path.write_text(text)
    sys.path.insert(0, str(KIT))  # its own `from movekit import ...`
    spec = importlib.util.spec_from_file_location("yawcore_old", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def entries(*speeds):
    colors = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]
    return [{"speed": s, "color": colors[i % 4], "sound": f"buttons/blip{i + 1}" if i % 2 == 0 else None}
            for i, s in enumerate(speeds)]


def base_data(**more):
    data = {"key": "q", "crosshair": True, "start": 1, "base": "builtin", "original_color": "0 255 0 255",
            "trainer": {"enabled": False}, "entries": entries(60, 90, 210)}
    data.update(more)
    return data


def check_unchanged(core):
    old = load_old_yawcore()
    if old is None:
        print(f"skip: {OLD_TAG} not in git, 1.8.0 comparison not run")
        return
    cases = 0

    def old_cfg(data, unbind, game):
        # 1.8.0 with the trainer off: the trainer's lines left Source Yaw in Phase 13
        return old.yaws_cfg(dict(data, trainer={"enabled": False}), unbind, game)
    for game in core.GAMES:
        for crosshair in (True, False):
            for trainer in ({"enabled": False}, {"enabled": True, "offset_key": "k"}, {"enabled": True}):
                data = base_data(crosshair=crosshair, trainer=trainer)
                for unbind in ((), ("x", "c")):
                    want = old_cfg(data, unbind, game)
                    expect(core.yaws_cfg(data, unbind, game), want,
                           f"yaws.cfg without a surf list, {game} crosshair={crosshair} trainer={trainer}")
                    cases += 1
                # keys the new version knows but a profile without a surf list ignores
                data.update(mode_key="g", auto_mode=True, map_modes={"bhop_": "bhop"})
                expect(core.yaws_cfg(data, (), game), old_cfg(data, (), game), "mode keys ignored without surf")
                # a saved surf list that isn't separate: only the active list, written as 1.8.0 did
                surf = {"entries": entries(30, 120), "start": 1}
                data.update(surf=surf, separate=False, active="bhop")
                expect(core.yaws_cfg(data, (), game), old_cfg(data, (), game), "surf saved, bhop active")
                data["active"] = "surf"
                as_old = dict(data, entries=surf["entries"], start=surf["start"])
                expect(core.yaws_cfg(data, (), game), old_cfg(as_old, (), game), "surf saved, surf active")
                cases += 2
    print(f"ok   yaws.cfg without a surf list same as {OLD_TAG} ({cases} cases)")


def check_console(core, tmp):
    surf = {"entries": entries(30, 90, 120), "start": 0}
    for game in core.GAMES:
        data = base_data(surf=surf, mode_key="g", auto_mode=True)
        expect(core.validate(data), [], f"{game}: surf settings validate")
        cfg = tmp / game / "cfg"
        cfg.mkdir(parents=True)
        (cfg / "yaws.cfg").write_text(core.yaws_cfg(data, ("x",), game))
        (cfg / f"{core.AUTO_CFG}.cfg").write_text("")
        if core.GAMES[game]["colors"] == "cvar":
            (cfg / core.COLOR_DIR).mkdir()
            core.write_color_cfgs(data, cfg.parent)
        con = Console(cfg)
        con.binds["x"] = "something"
        con.run("exec yaws")
        expect(con.cvars["cl_yawspeed"], "90", f"{game}: starts on the bhop list's start")
        expect("x" in con.binds, False, f"{game}: stale key unbound")
        expect((con.binds["q"], con.binds["g"]), (core.PRESS_ALIAS, core.MODE_ALIAS), f"{game}: binds")
        expect("k" in con.binds, False, f"{game}: no offset key bind (Strafe Trainer's since Phase 13)")
        expect(con.echoes[-1], "SY_MODE_BHOP", f"{game}: start echoes the bhop mode")
        presses = [con.press("q") for _ in range(4)]
        expect(presses, ["210", "60", "90", "210"], f"{game}: bhop cycle")
        expect(con.echoes, ["YAW_210"], f"{game}: bhop token")
        expect(con.press("g"), "30", f"{game}: mode key to the surf start")
        expect(con.echoes, ["SY_MODE_SURF", "YAWSURF_30"], f"{game}: mode key echoes")
        expect([con.press("q") for _ in range(3)], ["90", "120", "30"], f"{game}: surf cycle")
        expect(con.echoes, ["YAWSURF_30"], f"{game}: surf token")
        expect(con.press("g"), "90", f"{game}: mode key back to the bhop start")
        if core.GAMES[game]["colors"] == "cvar":
            expect(con.cvars["cl_crosshair_color"], "0 255 0 255", f"{game}: bhop start colour")
            con.press("g")
            expect(con.cvars["cl_crosshair_color"], "255 0 0 255", f"{game}: surf start colour")
            con.press("g")
        # auto: the watcher arms the surf list; the next press lands on its start
        con.press("q")  # bhop 210
        (cfg / f"{core.AUTO_CFG}.cfg").write_text("sourceyaw_arm_surf\n")
        expect(con.press("q"), "30", f"{game}: armed press lands on the surf start")
        expect(con.echoes, ["SY_MODE_SURF", "YAWSURF_30"], f"{game}: armed press echoes")
        # the watcher hasn't emptied the file yet: the arm must not fire again
        expect(con.press("q"), "90", f"{game}: an arm works once")
        (cfg / f"{core.AUTO_CFG}.cfg").write_text("")
        # arming the list already on does nothing
        (cfg / f"{core.AUTO_CFG}.cfg").write_text("sourceyaw_arm_surf\n")
        expect(con.press("q"), "120", f"{game}: arming the current list does nothing")
        (cfg / f"{core.AUTO_CFG}.cfg").write_text("sourceyaw_arm_bhop\n")
        expect(con.press("q"), "90", f"{game}: armed press lands on the bhop start")
        # a gamemode cfg on map load (Momentum): switches at once, only from the other list
        (cfg / f"{core.AUTO_CFG}.cfg").write_text("")
        con.press("g")  # to the surf start (30)
        con.press("g")  # back to the bhop start (90)
        con.echoes.clear()
        con.run(f"{core.LOAD_ALIAS}surf")
        expect((con.cvars["cl_yawspeed"], con.echoes), ("30", ["SY_MODE_SURF", "YAWSURF_30"]),
               f"{game}: surf map load switches to the surf start")
        expect(con.press("q"), "90", f"{game}: the press after a map-load switch cycles on")
        con.echoes.clear()
        con.run(f"{core.LOAD_ALIAS}surf")
        expect((con.cvars["cl_yawspeed"], con.echoes), ("90", []), f"{game}: surf map on surf: nothing")
        con.run(f"{core.LOAD_ALIAS}bhop")
        expect(con.cvars["cl_yawspeed"], "90", f"{game}: bhop map load switches to the bhop start")
        expect(con.echoes[-2:], ["SY_MODE_BHOP", "YAW_90"], f"{game}: bhop map load echoes")
        expect(con.press("q"), "210", f"{game}: the press after a bhop map load cycles on")
        # a stale arm from the watcher after a map-load switch does nothing
        (cfg / f"{core.AUTO_CFG}.cfg").write_text("sourceyaw_arm_bhop\n")
        expect(con.press("q"), "60", f"{game}: arm of the list already on after a map load")
        (cfg / f"{core.AUTO_CFG}.cfg").write_text("")
        # load_sound off: the same switch without the start yawspeed's sound
        con.run(f"{core.LOAD_ALIAS}bhop")  # back to bhop (with sound, as before)
        (cfg / "yaws.cfg").write_text(core.yaws_cfg(dict(data, load_sound=False), ("x",), game))
        con.run("exec yaws")
        con.sounds.clear()
        con.echoes.clear()
        con.run(f"{core.LOAD_ALIAS}surf")
        expect((con.cvars["cl_yawspeed"], con.echoes, con.sounds), ("30", ["SY_MODE_SURF", "YAWSURF_30"], []),
               f"{game}: quiet map-load switch")
        expect(con.press("q"), "90", f"{game}: the press after a quiet switch cycles on")
        expect(con.sounds, [], f"{game}: surf 90 has no sound of its own")
        con.run(f"{core.LOAD_ALIAS}bhop")
        expect((con.cvars["cl_yawspeed"], con.sounds), ("90", []), f"{game}: quiet switch back to bhop")
        con.press("q")
        con.press("q")
        expect(con.sounds, ["buttons/blip3", "buttons/blip1"], f"{game}: presses still play their sounds")
        if core.GAMES[game]["colors"] == "cvar":
            con.run(f"{core.LOAD_ALIAS}surf")
            expect(con.cvars["cl_crosshair_color"], "255 0 0 255", f"{game}: quiet switch sets the colour")
        # without auto the key cycles directly
        data["auto_mode"] = False
        con = Console(cfg)
        (cfg / "yaws.cfg").write_text(core.yaws_cfg(data, (), game))
        con.run("exec yaws")
        expect(con.binds["q"], "yaw_cycle", f"{game}: no auto, plain cycle bind")
        expect([con.press("q"), con.press("g")], ["210", "30"], f"{game}: no auto, mode key still works")
        if core.GAMES[game]["colors"] == "cvar":
            data["trainer"] = {"enabled": True, "offset_key": "k"}
            expect("con_logfile" in core.yaws_cfg(data, (), game), False, f"{game}: no log without auto")
            data["auto_mode"] = True
            expect("con_logfile yaw.log" in core.yaws_cfg(data, (), game), True, f"{game}: log on for auto")
    print("ok   console model: start, cycles, mode key, arms once, colours")


def check_validate(core):
    def problems(**more):
        return core.validate(base_data(**more))
    expect(problems(surf={"entries": [], "start": 0}), ["Add at least one surf yawspeed"], "empty surf list")
    expect(problems(surf={"entries": entries(30, 30), "start": 0}), ["Each surf yawspeed must be different"],
           "surf duplicates")
    expect(problems(surf={"entries": entries(60, 90), "start": 0}), [], "a speed in both lists is fine")
    expect(problems(surf={"entries": entries(30), "start": 0}, mode_key="q"),
           ["The mode key must differ from the yaw key"], "mode key = yaw key")
    expect(problems(surf={"entries": entries(30), "start": 0}, mode_key="nope"),
           ["'nope' is not a key name the game knows"], "bad mode key")
    expect(problems(surf={"entries": entries(30), "start": 0}, mode_key="k",
                    trainer={"enabled": True, "offset_key": "k"}),
           [], "the offset key is Strafe Trainer's since Phase 13")
    expect(problems(mode_key="nope"), [], "mode key ignored without a surf list")
    expect(problems(surf={"entries": [], "start": 0}, separate=False), [], "unused empty surf list is fine")
    expect(problems(surf={"entries": [], "start": 0}, separate=False, active="surf"),
           ["Add at least one yawspeed"], "active surf list empty")
    expect(problems(surf={"entries": entries(30), "start": 0}, separate=False, mode_key="q"), [],
           "mode key ignored while not separate")
    print("ok   validate")


def check_watcher(watch, tmp):
    path = tmp / "auto.cfg"
    path.write_text("sourceyaw_arm_surf\n")  # left over
    w = watch.Watcher(path, {"bhop_": "bhop", "surf_": "surf"})
    w.clear()
    expect(path.read_text(), "", "cleared at start")

    def ev(kind, **data):
        return {"type": kind, "data": data}

    expect(w.handle(ev("map_loaded", name="bhop_arcane")), None, "bhop map on bhop: nothing")
    expect(path.read_text(), "", "file stays empty")
    expect(w.handle(ev("map_loaded", name="surf_utopia")), "surf", "surf map arms surf")
    expect(path.read_text(), "sourceyaw_arm_surf\n", "arm written")
    expect(w.handle(ev("map_loaded", name=None)), None, "unknown map: nothing")
    expect(w.handle(ev("map_loaded", name="kz_x")), None, "other prefix: nothing")
    expect(path.read_text(), "sourceyaw_arm_surf\n", "arm kept over unknown maps")
    expect(w.handle(ev("token", name="YAW_90")), None, "yaw token: nothing")
    expect(w.handle(ev("token", name="SY_MODE_SURF")), "", "mode token clears")
    expect((path.read_text(), w.mode), ("", "surf"), "cleared, mode surf")
    expect(w.handle(ev("map_loaded", name="SURF_other")), None, "surf map on surf (any case): nothing")
    expect(w.handle(ev("map_loaded", name="bhop_x")), "bhop", "bhop map arms bhop")
    expect(w.handle(ev("map_loaded", name="surf_y")), "", "back to a surf map before a press clears")
    expect(path.read_text(), "", "cleared")
    w.handle(ev("map_loaded", name="bhop_x"))
    expect(w.handle(ev("token", name="SY_MODE_SURF")), "", "mode key to the same list still clears")
    expect(w.mode, "surf", "mode from the token")
    w.handle(ev("map_loaded", name="bhop_x"))
    path.write_text("")  # the hub's Apply mid-game
    expect(w.handle(ev("map_loaded", name="bhop_y")), "bhop", "re-arms after the file was emptied elsewhere")
    expect(path.read_text(), "sourceyaw_arm_bhop\n", "arm written again")
    print("ok   mode watcher")


def check_files(core, tmp):
    core.CONFIG_DIR.mkdir(parents=True, exist_ok=True)  # the hub's first Apply makes it
    game_dir = tmp / "files/momentum"
    (game_dir / "cfg").mkdir(parents=True)
    (game_dir / "cfg/config.cfg").write_text('bind "g" "sourceyaw_mode"\nbind "z" "sourceyaw_press"\n'
                                             'cl_crosshair_color "0 255 0 255"\n')
    (game_dir / f"cfg/{core.AUTO_CFG}.cfg").write_text("sourceyaw_arm_surf\n")
    data = base_data(surf={"entries": entries(30, 120), "start": 1}, mode_key="g")
    notes = core.apply(data, game_dir, game="momentum")
    expect(notes, ["'z' gets unbound next time yaws.cfg runs"], "apply notes: old press key unbound, mode key kept")
    expect((game_dir / f"cfg/{core.AUTO_CFG}.cfg").read_text(), "", "apply empties the auto cfg")
    colors = sorted(p.name for p in (game_dir / "cfg" / core.COLOR_DIR).iterdir())
    expect(colors, ["b1.cfg", "b2.cfg", "b3.cfg", "s1.cfg", "s2.cfg"], "colour cfgs per list")
    expect("AUTO=1" in core.WATCH_ENV.read_text(), True, "watch.env AUTO on")
    del data["surf"]
    core.apply(data, game_dir, game="momentum")
    colors = sorted(p.name for p in (game_dir / "cfg" / core.COLOR_DIR).iterdir())
    expect(colors, ["c1.cfg", "c2.cfg", "c3.cfg"], "b/s colour cfgs gone without a surf list")
    expect((game_dir / f"cfg/{core.AUTO_CFG}.cfg").exists(), False, "auto cfg gone without a surf list")
    expect("AUTO=0" in core.WATCH_ENV.read_text(), True, "watch.env AUTO off")
    data.update(surf={"entries": entries(30, 120), "start": 0}, separate=False, active="surf")
    core.apply(data, game_dir, game="momentum")
    colors = {p.name: p.read_text() for p in (game_dir / "cfg" / core.COLOR_DIR).iterdir()}
    expect(colors, {"c1.cfg": 'cl_crosshair_color "255 0 0 255"\n', "c2.cfg": 'cl_crosshair_color "0 255 0 255"\n'},
           "one list in game: the active surf list's colours as c<i>")
    expect(core.load_settings("momentum")["surf"]["entries"][1]["speed"], 120, "unused list saved")
    data["surf"] = {"entries": entries(30), "start": 0}
    data["separate"] = True
    cfg = game_dir / "cfg"
    (cfg / "kz.cfg").write_text("sv_airaccelerate 100\n")  # the player's own gamemode cfg
    (cfg / "rj.cfg").write_text("")  # the player's own empty one: never ours to delete
    core.apply(data, game_dir, game="momentum")
    block = "// movekit:sourceyaw begin\n{}\n// movekit:sourceyaw end\n"
    expect((cfg / "surf.cfg").read_text(), block.format(f"{core.LOAD_ALIAS}surf"), "surf.cfg block")
    expect((cfg / "bhop.cfg").read_text(), block.format(f"{core.LOAD_ALIAS}bhop"), "bhop.cfg block")
    expect((cfg / "kz.cfg").read_text(), "sv_airaccelerate 100\n", "unmapped gamemode cfg untouched")
    expect((cfg / "bhophl.cfg").exists(), False, "no cfg for an unmapped gamemode")
    data["map_modes"] = {"kz_": "bhop", "surf_": "surf"}
    core.apply(data, game_dir, game="momentum")
    expect((cfg / "kz.cfg").read_text(), "sv_airaccelerate 100\n\n" + block.format(f"{core.LOAD_ALIAS}bhop"),
           "map_modes picks the gamemode cfgs; own lines kept")
    expect((cfg / "bhop.cfg").exists(), False, "bhop.cfg deleted once unmapped")
    data["auto_mode"] = False
    core.apply(data, game_dir, game="momentum")
    expect(sorted(p.name for p in cfg.glob("*.cfg") if p.name in ("surf.cfg", "bhop.cfg", "kz.cfg")),
           ["kz.cfg"], "auto off: our gamemode cfgs gone, the player's kept")
    expect((cfg / "kz.cfg").read_text(), "sv_airaccelerate 100\n", "auto off: kz.cfg back to its own lines")
    data["auto_mode"] = True
    data["load_switch"] = False
    core.apply(data, game_dir, game="momentum")
    expect([(cfg / f).exists() for f in ("surf.cfg", "kz.cfg")], [False, True],
           "map-load switch off: our gamemode cfgs gone")
    expect((game_dir / f"cfg/{core.AUTO_CFG}.cfg").exists(), True, "map-load switch off: the press arm stays")
    data["load_switch"] = True
    core.apply(data, game_dir, game="momentum")
    core.remove_from_game(game_dir, "momentum")
    expect((game_dir / f"cfg/{core.AUTO_CFG}.cfg").exists(), False, "remove_from_game deletes the auto cfg")
    expect([(cfg / f).exists() for f in ("surf.cfg", "kz.cfg")], [False, True],
           "remove_from_game takes the gamemode blocks out")
    expect((cfg / "rj.cfg").exists(), True, "an empty gamemode cfg without our block stays")
    # CS:S runs no gamemode cfgs
    css_dir = tmp / "files/cstrike"
    (css_dir / "cfg").mkdir(parents=True)
    core.apply(base_data(surf={"entries": entries(30), "start": 0}), css_dir, game="css")
    expect(sorted(p.name for p in (css_dir / "cfg").iterdir()), [f"{core.AUTO_CFG}.cfg", "yaws.cfg"],
           "CS:S: no gamemode cfgs")
    # CS:S: an image per token, the bhop start in current.png
    core.write_crosshairs(base_data(surf={"entries": entries(90, 500), "start": 0}), True)
    names = sorted(p.name for p in core.CROSSHAIRS.iterdir())
    expect(names, ["YAWSURF_500.png", "YAWSURF_90.png", "YAW_210.png", "YAW_60.png", "YAW_90.png"],
           "crosshair images")
    print("ok   apply, colour cfgs, auto cfg, images")


def turn_cases(con, what, codes):
    """Every press and release order of two nulled turn keys; `codes` {key: code} as the engine
    passes it on (None: none, Source 2013)."""
    def hold(key, down=True):
        return con.hold(key, down, codes[key] if codes else None)

    for first, second in (("MOUSE1", "MOUSE2"), ("MOUSE2", "MOUSE1")):
        own = {"MOUSE1": ["left"], "MOUSE2": ["right"]}
        for up in ((first, second), (second, first)):
            expect(hold(first), own[first], f"{what}: {first} down")
            expect(hold(second), own[second], f"{what}: {second} down while {first} held: {second} wins")
            expect(hold(up[0], False), own[up[1]], f"{what}: {up[0]} up: back to the held {up[1]}")
            expect(hold(up[1], False), [], f"{what}: {first}, {second} down, {up[0]}, {up[1]} up: no turn")
            expect(float(con.cvars["cl_yawspeed"]) > 0, True, f"{what}: positive yawspeed once both are up")
    expect(hold("MOUSE1", False), [], f"{what}: a release with nothing held does nothing")


def check_turns(core, tmp):
    game_dir = tmp / "turns/momentum"
    cfg = game_dir / "cfg"
    cfg.mkdir(parents=True)
    (cfg / "config.cfg").write_text('bind "MOUSE1" "+left"\nbind "MOUSE2" "+right"\nbind "q" "+left"\n')
    data = base_data(null_turns=True)
    notes = core.apply(data, game_dir, game="momentum")
    expect(notes, ["Turn keys nulled: MOUSE1, MOUSE2"], "null turns: notes (the cycle key q left out)")
    con = Console(cfg)
    con.run((cfg / "yaws.cfg").read_text())
    expect((con.binds["MOUSE1"], con.binds["MOUSE2"], con.binds["q"]), ("+sy_left", "+sy_right", "yaw_cycle"),
           "null turns: binds")
    turn_cases(con, "Source 2013", None)
    # Momentum gives the +/- commands an alias runs the code of the key that ran it, whatever
    # code the alias gives: a -left from MOUSE2 can't let go of MOUSE1's +left
    turn_cases(con, "Momentum", {"MOUSE1": 107, "MOUSE2": 108})
    # cycling while turning right keeps the sign; both keys up: positive again
    con.hold("MOUSE2")
    con.press("q")
    expect(con.cvars["cl_yawspeed"], "-210", "yaw cycle while turning right keeps it right")
    con.hold("MOUSE2", False)
    expect(con.cvars["cl_yawspeed"], "210", "both up: positive yawspeed")
    # with a bhop and a surf list too
    data2 = base_data(null_turns=True, surf={"entries": entries(30, 120), "start": 1}, mode_key="g")
    core.apply(data2, game_dir, game="momentum")
    con = Console(cfg)
    con.run((cfg / "yaws.cfg").read_text())
    turn_cases(con, "Momentum, two lists", {"MOUSE1": 107, "MOUSE2": 108})
    con.hold("MOUSE2")
    con.press("g")
    expect(con.cvars["cl_yawspeed"], "-120", "mode switch while turning right keeps it right")
    con.hold("MOUSE2", False)
    # the game saves the nulled binds in config.cfg on exit
    (cfg / "config.cfg").write_text('bind "MOUSE1" "+sy_left"\nbind "MOUSE2" "+sy_right"\n')
    expect(core.apply(data, game_dir, game="momentum"), ["Turn keys nulled: MOUSE1, MOUSE2"],
           "null turns: keys found again once nulled")
    con = Console(cfg)
    con.run((cfg / "yaws.cfg").read_text())
    expect(con.binds["MOUSE1"], "+sy_left", "still nulled on the next launch")
    notes = core.apply(dict(data, null_turns=False), game_dir, game="momentum")
    expect(notes, ["'MOUSE1' goes back to +left", "'MOUSE2' goes back to +right"], "null turns off: notes")
    con = Console(cfg)
    con.run((cfg / "yaws.cfg").read_text())
    expect((con.binds["MOUSE1"], con.binds["MOUSE2"]), ("+left", "+right"), "null turns off: plain binds back")
    (cfg / "config.cfg").write_text('bind "MOUSE1" "+left"\n')
    core.apply(dict(data, null_turns=False), game_dir, game="momentum")
    expect("MOUSE1" in (cfg / "yaws.cfg").read_text(), False, "null turns off, plain binds: nothing written")
    (cfg / "config.cfg").write_text('bind "c" "+duck"\n')
    expect(core.apply(data, game_dir, game="momentum"),
           ["Null turnbinds: no +left/+right binds found in config.cfg"], "null turns: no turn keys")
    (cfg / "config.cfg").write_text('bind "MOUSE1" "+sy_left"\nbind "MOUSE2" "+sy_right"\nbind "w" "+forward"\n')
    core.remove_from_game(game_dir, "momentum")
    expect((cfg / "config.cfg").read_text(), 'bind "MOUSE1" "+left"\nbind "MOUSE2" "+right"\nbind "w" "+forward"\n',
           "remove_from_game puts the turn keys back")
    # someone's own null script (CS:S): recognised and left alone
    css = tmp / "turns/cstrike"
    (css / "cfg").mkdir(parents=True)
    (css / "cfg/turnbind.cfg").write_text('alias +nleft "-right;+left;alias chknleft +left"\n'
                                          'alias +nright "-left;+right;alias chknright +right"\n')
    (css / "cfg/config.cfg").write_text('bind "MOUSE1" "+nleft"\nbind "MOUSE2" "+nright"\nbind "c" "+duck"\n'
                                        'bind "x" "+left"\n')
    notes = core.apply(data, css, game="css")
    expect(notes, ["Turn keys nulled: x",
                   "Left as they are, on your own turn aliases: MOUSE1 (+nleft), MOUSE2 (+nright)"],
           "own null aliases recognised")
    expect("MOUSE1" in (css / "cfg/yaws.cfg").read_text(), False, "own null aliases not rebound")
    (css / "cfg/config.cfg").write_text('bind "MOUSE1" "+nleft"\n')
    expect(core.apply(data, css, game="css"),
           ["Left as they are, on your own turn aliases: MOUSE1 (+nleft)"], "only own aliases: no 'none found'")
    expect(len(core.apply(data, css, game="momentum")), 2, "own aliases in Momentum: a warning too")


def check_hub(tmp):
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
    sys.path.insert(0, str(KIT))
    from movekit import hub
    section = hub.local_import(HERE / "hub_section.py", "hub_section")
    core = section._core()
    games = {"css": tmp / "hub/cstrike", "momentum": tmp / "hub/momentum"}
    for folder in games.values():
        (folder / "cfg").mkdir(parents=True)
        (folder / "cfg/config.cfg").write_text('cl_crosshair_color "0 255 0 255"\n')
    core.find_game = lambda game: games[game]
    core.flatpak_steam_only = lambda game="css": False
    core.SETTINGS.unlink(missing_ok=True)  # start from a new profile
    st = section.load("momentum")
    expect((st["surf"], st["mode_key"], st["auto_mode"]), (None, "", True), "load without a surf list")
    expect((st["map_load"], st["load_switch"], st["load_sound"]), (True, True, True),
           "Momentum: map-load switch with its sound by default")
    expect(section.load("css")["map_load"], False, "CS:S: no map-load switch")
    form = {"key": st["key"], "crosshair": st["crosshair"], "start": st["start"], "base": st["base"],
            "entries": st["entries"],
            "surf": {"entries": [{"speed": 30, "color": "#123456", "sound": ""}], "start": 0},
            "separate": True, "active": "bhop", "mode_key": "g", "auto_mode": False,
            "load_switch": False, "load_sound": False}
    got = section.apply("momentum", form)
    expect(got["saved"], True, f"apply with a surf list ({got['messages']})")
    st = section.load("momentum")
    expect((st["load_switch"], st["load_sound"]), (False, False), "map-load switch settings kept")
    expect((st["null_turns"], st["turn_keys"]), (False, []), "null turns off by default, no turn keys")
    (games["momentum"] / "cfg/config.cfg").write_text('bind "MOUSE1" "+sy_left"\nbind "g" "+right"\n')
    section.apply("momentum", dict(form, null_turns=True))
    st = section.load("momentum")
    expect((st["null_turns"], st["turn_keys"]), (True, ["MOUSE1"]), "null turns kept, mode key g left out")
    (games["momentum"] / "cfg/turnbind.cfg").write_text('alias +nleft "-right;+left"\n')
    (games["momentum"] / "cfg/config.cfg").write_text('bind "MOUSE2" "+nleft"\n')
    expect(section.load("momentum")["own_turns"], [["MOUSE2", "+nleft"]], "own turn aliases on the page")
    (games["momentum"] / "cfg/turnbind.cfg").unlink()
    form["null_turns"] = False
    (games["momentum"] / "cfg/config.cfg").write_text('cl_crosshair_color "0 255 0 255"\n')
    st = section.load("momentum")
    expect((st["surf"], st["mode_key"], st["auto_mode"]),
           ({"entries": [{"speed": 30.0, "color": "#123456", "sound": ""}], "start": 0}, "g", False),
           "surf list, mode key and auto kept through apply and load")
    expect(st["notes"]["mode"]["warn"], False, "mode key note")
    expect(section.key_notes("momentum", "q", "q")["mode"]["warn"], True, "mode key = cycle key warns")
    st = section.load("momentum")
    expect((st["separate"], st["active"]), (True, "bhop"), "separate kept")
    form.update(separate=False, active="surf")
    section.apply("momentum", form)
    st = section.load("momentum")
    expect((st["separate"], st["active"], len(st["surf"]["entries"])), (False, "surf", 1),
           "separate off keeps the surf list, surf active")
    form.update(surf=None, separate=True, active="bhop")
    section.apply("momentum", form)
    st = section.load("momentum")
    expect((st["surf"], st["separate"]), (None, False), "no surf list: not separate")
    print("ok   hub section keeps the surf list, mode key and auto switch")


def run_all():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for var, sub in (("HOME", "home"), ("XDG_CONFIG_HOME", "home/.config"),
                         ("XDG_DATA_HOME", "home/.local/share"), ("XDG_CACHE_HOME", "home/.cache")):
            os.environ[var] = str(tmp / sub)
        sys.path.insert(0, str(HERE))
        import mode_watch
        import yawcore as core
        core.find_game = lambda game: None
        check_unchanged(core)
        check_console(core, tmp / "console")
        check_validate(core)
        check_watcher(mode_watch, tmp)
        check_files(core, tmp)
        check_turns(core, tmp)
        check_hub(tmp)
    print("all mode checks passed")


# ---------------------------------------------------------------- mutations

MUTATIONS = [
    ("arm lands one past the start", "yawcore.py",
     'alias sy_arm_{mode} "sy_{mode}_state; alias yaw_cycle {starts[mode]}"',
     'alias sy_arm_{mode} "sy_{mode}_state; {starts[mode]}"'),
    ("map load switches from the list already on", "yawcore.py",
     "alias {LOAD_ALIAS}{mode} sy_noop; ", ""),
    ("map load arms instead of switching", "yawcore.py",
     "alias {LOAD_ALIAS}{other} sy_load_{other}; ", "alias {LOAD_ALIAS}{other} sy_arm_{other}; "),
    ("map-load switch can't be turned off", "yawcore.py",
     'if not auto_on(data) or not data.get("load_switch", True):', 'if not auto_on(data):'),
    ("load sound setting ignored", "yawcore.py",
     'loud = bool(data.get("load_sound", True))', "loud = True"),
    ("hub drops the load sound", "hub_section.py",
     'load_sound=bool(form.get("load_sound", True))', "load_sound=True"),
    ("gamemode cfgs ignore map_modes", "yawcore.py",
     'mode = prefix_value(f"{gamemode}_", table)', 'mode = gamemode'),
    ("gamemode cfgs left behind", "yawcore.py",
     "            path.unlink()\n", "            pass\n"),
    ("someone else's empty gamemode cfg deleted", "yawcore.py",
     "        if had_block:\n", "        if True:\n"),
    ("arm works more than once", "yawcore.py",
     "alias sourceyaw_arm_{mode} sy_noop; ", ""),
    ("one token for both lists", "yawcore.py",
     'return f"{SURF_PREFIX if surf else \'YAW_\'}{fmt_speed(value)}"', 'return f"YAW_{fmt_speed(value)}"'),
    ("watcher arms on a map of the current list", "mode_watch.py",
     "arm = None if want == self.mode else want", "arm = want"),
    ("watcher ignores mode tokens", "mode_watch.py",
     'if kind == "token" and data.get("name") in TOKEN_MODES:', 'if False:'),
    ("hub drops the surf list", "hub_section.py",
     "entries, surf=surf, mode_key", "entries, surf=None, mode_key"),
    ("mode key unbound by apply", "yawcore.py",
     "ours = {data[\"key\"], mode_key_of(data)}", "ours = {data[\"key\"]}"),
    ("stale b/s colour cfgs kept", "yawcore.py", 'folder.glob("[bcs]*.cfg")', 'folder.glob("c*.cfg")'),
    ("separate ignored", "yawcore.py",
     'return bool(data.get("surf")) and bool(data.get("separate", True))', 'return bool(data.get("surf"))'),
    ("active list ignored", "yawcore.py",
     'return "surf" if data.get("active") == "surf" and data.get("surf") else "bhop"', 'return "bhop"'),
    ("nulled turn keys not found again", "yawcore.py",
     "        for command in (plain, null):\n", "        for command in (plain,):\n"),
    ("null turns off leaves keys on the aliases", "yawcore.py",
     'return ["", "// null turnbinds off: back to plain turns", *back] if back else []', "return []"),
    ("null alias doesn't fall back to the held key", "yawcore.py",
     "-left {left}; sy_goleft; sy_rback", "-left {left}; sy_goleft"),
    ("turn keys share a code (Source 2013 frees both)", "yawcore.py",
     'TURN_CODES = {"+left": 9001, "+right": 9002}', 'TURN_CODES = {"+left": 9001, "+right": 9001}'),
    ("right key turns with +right (the other key can't let go in Momentum)", "yawcore.py",
     'sy_goright; +left {right}"', 'sy_goright; -left {left}; +right {right}"'),
    ("yawspeed alias drops the turn's sign", "yawcore.py",
     '"alias sy_neg {name}_n", "sy_dir"]', '"alias sy_neg {name}_n"]'),
    ("yawspeed stays negative after a right turn", "yawcore.py",
     "-left {right}; sy_goleft; sy_lback", "-left {right}; sy_lback"),
    ("uninstall leaves nulled binds", "yawcore.py", "    unnull_config(cstrike)\n", ""),
    ("own turn aliases not recognised", "yawcore.py",
     "        if binds.resolve(command, wanted, alias_map):\n", "        if False:\n"),
    ("hub drops null turns", "hub_section.py",
     'null_turns=bool(form.get("null_turns", False))', "null_turns=False"),
    ("hub drops separate", "hub_section.py",
     'separate=bool(form.get("separate")) and surf is not None', 'separate=surf is not None'),
]


def run_mutations():
    import shutil
    caught = 0
    for name, file, old, new in MUTATIONS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "kit"
            shutil.copytree(KIT, copy, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))
            target = copy / "sourceyaw" / file
            text = target.read_text()
            if text.count(old) != 1:
                fail(f"mutation {name!r}: pattern found {text.count(old)} times")
            target.write_text(text.replace(old, new))
            # the old yawcore comes from this repo's git, not the copy's
            env = dict(os.environ, GIT_DIR=str(KIT / ".git"))
            res = subprocess.run([sys.executable, str(copy / "sourceyaw/check_modes.py")],
                                 capture_output=True, text=True, env=env, check=False)
            if res.returncode == 0:
                fail(f"mutation not caught: {name}")
            caught += 1
            print(f"ok   caught: {name} ({(res.stdout + res.stderr).strip().splitlines()[-1]})")
    print(f"all {caught} mutations caught")


if __name__ == "__main__":
    if sys.argv[1:] == ["--mutations"]:
        run_mutations()
    else:
        run_all()
