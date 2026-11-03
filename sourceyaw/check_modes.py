#!/usr/bin/env python3
"""Checks Source Yaw's bhop and surf lists (1.9.0) without a game.

Usage: python sourceyaw/check_modes.py [--mutations]   (exits 1 on the first failure)

Covers:
  - yaws.cfg without a surf list is byte-identical to 1.8.0's (that tag's yawcore.py, from git),
    for both games, with and without colours, the trainer and an offset key;
  - with a surf list, yaws.cfg run through a small console model (aliases, exec, echo, binds):
    the start yawspeed, cycling, the mode key, the auto file's arm landing on the list's start,
    an arm working once, Momentum's colour cfgs;
  - validate() for the surf list and the mode key;
  - mode_watch.Watcher on session events: arm on a map of the other list, clear on a mode token or
    a map of the current list, unknown maps change nothing;
  - apply(): the auto cfg emptied, stale colour cfgs gone, the mode key not unbound, watch.env's AUTO;
    remove_from_game deleting the auto cfg; crosshair images for the surf tokens;
  - the hub section's settings()/load() keeping the surf list, the mode key and the auto switch.
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
            else:
                fail(f"console: unknown command {command!r}")

    def press(self, key):
        self.echoes.clear()
        self.run(self.binds[key])
        return self.cvars["cl_yawspeed"]


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
    for game in core.GAMES:
        for crosshair in (True, False):
            for trainer in ({"enabled": False}, {"enabled": True, "offset_key": "k"}, {"enabled": True}):
                data = base_data(crosshair=crosshair, trainer=trainer)
                for unbind in ((), ("x", "c")):
                    expect(core.yaws_cfg(data, unbind, game), old.yaws_cfg(data, unbind, game),
                           f"yaws.cfg without a surf list, {game} crosshair={crosshair} trainer={trainer}")
                    cases += 1
                # keys the new version knows but a profile without a surf list ignores
                data.update(mode_key="g", auto_mode=True, map_modes={"bhop_": "bhop"})
                expect(core.yaws_cfg(data, (), game), old.yaws_cfg(data, (), game), "mode keys ignored without surf")
    print(f"ok   yaws.cfg without a surf list same as {OLD_TAG} ({cases} cases)")


def check_console(core, tmp):
    surf = {"entries": entries(30, 90, 120), "start": 0}
    for game in core.GAMES:
        data = base_data(surf=surf, mode_key="g", auto_mode=True, trainer={"enabled": True, "offset_key": "k"})
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
        expect((con.binds["q"], con.binds["g"], con.binds["k"]),
               (core.PRESS_ALIAS, core.MODE_ALIAS, core.OFFSETS_ALIAS), f"{game}: binds")
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
        # without auto the key cycles directly
        data["auto_mode"] = False
        con = Console(cfg)
        (cfg / "yaws.cfg").write_text(core.yaws_cfg(data, (), game))
        con.run("exec yaws")
        expect(con.binds["q"], "yaw_cycle", f"{game}: no auto, plain cycle bind")
        expect([con.press("q"), con.press("g")], ["210", "30"], f"{game}: no auto, mode key still works")
        if core.GAMES[game]["colors"] == "cvar":
            data["trainer"] = {"enabled": False}
            expect("con_logfile" in core.yaws_cfg(data, (), game), False, f"{game}: no log without auto or trainer")
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
           ["The mode key must differ from the offset key"], "mode key = offset key")
    expect(problems(mode_key="nope"), [], "mode key ignored without a surf list")
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
    data["surf"] = {"entries": entries(30), "start": 0}
    core.apply(data, game_dir, game="momentum")
    core.remove_from_game(game_dir, "momentum")
    expect((game_dir / f"cfg/{core.AUTO_CFG}.cfg").exists(), False, "remove_from_game deletes the auto cfg")
    # CS:S: an image per token, the bhop start in current.png
    core.write_crosshairs(base_data(surf={"entries": entries(90, 500), "start": 0}), True)
    names = sorted(p.name for p in core.CROSSHAIRS.iterdir())
    expect(names, ["YAWSURF_500.png", "YAWSURF_90.png", "YAW_210.png", "YAW_60.png", "YAW_90.png"],
           "crosshair images")
    print("ok   apply, colour cfgs, auto cfg, images")


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
    form = {"key": st["key"], "crosshair": st["crosshair"], "start": st["start"], "base": st["base"],
            "entries": st["entries"], "trainer": st["trainer"],
            "surf": {"entries": [{"speed": 30, "color": "#123456", "sound": ""}], "start": 0},
            "mode_key": "g", "auto_mode": False}
    got = section.apply("momentum", form)
    expect(got["saved"], True, f"apply with a surf list ({got['messages']})")
    st = section.load("momentum")
    expect((st["surf"], st["mode_key"], st["auto_mode"]),
           ({"entries": [{"speed": 30.0, "color": "#123456", "sound": ""}], "start": 0}, "g", False),
           "surf list, mode key and auto kept through apply and load")
    expect(st["notes"]["mode"]["warn"], False, "mode key note")
    expect(section.key_notes("momentum", "q", "", "q")["mode"]["warn"], True, "mode key = cycle key warns")
    form["surf"] = None
    section.apply("momentum", form)
    expect(section.load("momentum")["surf"], None, "surf list off")
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
        check_hub(tmp)
    print("all mode checks passed")


# ---------------------------------------------------------------- mutations

MUTATIONS = [
    ("arm lands one past the start", "yawcore.py",
     'alias sy_arm_{mode} "sy_{mode}_state; alias yaw_cycle {starts[mode]}"',
     'alias sy_arm_{mode} "sy_{mode}_state; {starts[mode]}"'),
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
     "ours = {data[\"key\"], offsets_key_of(data), mode_key_of(data)}", "ours = {data[\"key\"], offsets_key_of(data)}"),
    ("stale b/s colour cfgs kept", "yawcore.py", 'folder.glob("[bcs]*.cfg")', 'folder.glob("c*.cfg")'),
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
