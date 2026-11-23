#!/usr/bin/env python3
"""Checks Source Yaw's yawspeed profiles (1.15.0, yawcore.PROFILE_CMD) without a game.

Usage: python sourceyaw/check_profiles.py   (exits 1 on the first failure)

Covers, in check_modes.py's console model:
  - two lists with profiles: the console command, cycling in a profile, the mode key landing on
    a list's current profile and back, profile arms (once, and nothing on the current profile),
    the mode arm and the map-load switch (quiet too) landing on the current profile, colours;
  - one list with profiles: the console command and arms, the press bound through the auto cfg;
    with the surf list the one in game, its one-list ids and no aliases for bhop's profiles;
  - every yaws.cfg line under the console's 512 characters, also with ten profiles per list and
    24-character names, and every alias name under the engine's 32;
  - maps on a list with one profile change nothing (no arm aliases to call);
  - validate() for names, empty profiles, maps and CS:S's one colour per speed;
  - mode_watch.Watcher: a profile's maps win over the list prefix, longest first, a map with no
    profile goes back to the picked one after a map switch only;
  - the map-load profile switch (Momentum): apply() puts `exec sourceyaw_mapload` in the gamemode
    cfgs, the watcher writes that file per map, and the gamemode cfg then lands on the map's
    profile, from either list, and back on the picked one; not with load_switch off or in CS:S;
  - apply(): colour cfgs and crosshair images for every profile, watch.env's AUTO;
  - the hub section's load()/apply() keeping names, maps and profiles unchanged.
Everything runs in a temp folder: HOME and the XDG folders point there.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_modes as cm
from check_modes import Console, base_data, entries, expect


def two_lists(**more):
    data = base_data(
        name="main", maps=[],
        sets=[{"name": "kz", "entries": entries(300, 400), "start": 0, "maps": ["bhop_kz_"]}],
        surf={"entries": entries(30, 90, 120), "start": 0, "name": "surf", "maps": [],
              "sets": [{"name": "fast", "entries": entries(500, 600), "start": 1, "maps": ["surf_fast"]}]},
        mode_key="g", auto_mode=True, separate=True)
    data.update(more)
    return data


def console(core, cfg, data, game):
    cfg.mkdir(parents=True, exist_ok=True)
    text = core.yaws_cfg(data, (), game)
    long = [line for line in text.splitlines() if len(line) >= 512]
    expect(long, [], f"{game}: yaws.cfg lines under 512 characters")
    (cfg / "yaws.cfg").write_text(text)
    (cfg / f"{core.AUTO_CFG}.cfg").write_text("")
    if core.GAMES[game]["colors"] == "cvar":
        (cfg / core.COLOR_DIR).mkdir(exist_ok=True)
        core.write_color_cfgs(data, cfg.parent)
    con = Console(cfg)
    con.run("exec yaws")
    return con


def check_two_lists(core, tmp):
    for game in core.GAMES:
        data = two_lists()
        expect(core.validate(data, game), [], f"{game}: profiles validate")
        cfg = tmp / game / "cfg"
        con = console(core, cfg, data, game)
        auto = cfg / f"{core.AUTO_CFG}.cfg"
        expect(con.cvars["cl_yawspeed"], "90", f"{game}: starts on the picked bhop profile")
        expect(con.binds["q"], core.PRESS_ALIAS, f"{game}: press through the auto cfg")
        con.echoes.clear()
        con.run("yawset_kz")
        expect((con.cvars["cl_yawspeed"], con.echoes), ("300", ["SY_MODE_BHOP", "YAW_300"]),
               f"{game}: yawset_kz sets its start")
        expect(con.sounds[-1:], ["buttons/blip1"], f"{game}: with its sound")
        if core.GAMES[game]["colors"] == "cvar":
            expect(con.cvars["cl_crosshair_color"], "255 0 0 255", f"{game}: kz's colour")
        expect([con.press("q") for _ in range(3)], ["400", "300", "400"], f"{game}: kz cycle")
        expect(con.press("g"), "30", f"{game}: mode key to surf")
        expect(con.press("g"), "300", f"{game}: mode key back lands on kz's start, not main's")
        # profile arms from the watcher
        auto.write_text("sourceyaw_arm_set_b\n")
        expect(con.press("q"), "90", f"{game}: arm of main lands on its start")
        expect(con.press("q"), "210", f"{game}: the arm works once")
        expect(con.press("q"), "60", f"{game}: arm of the current profile does nothing")
        auto.write_text("sourceyaw_arm_set_bp1\n")
        expect(con.press("q"), "300", f"{game}: arm of kz")
        auto.write_text("")
        con.echoes.clear()
        con.run("yawset_fast")
        expect((con.cvars["cl_yawspeed"], con.echoes), ("600", ["SY_MODE_SURF", "YAWSURF_600"]),
               f"{game}: yawset_fast switches list and profile")
        expect(con.press("q"), "500", f"{game}: fast cycle")
        expect(con.press("g"), "300", f"{game}: mode key to bhop's current profile")
        expect(con.press("g"), "600", f"{game}: mode key to surf's current profile")
        auto.write_text("sourceyaw_arm_bhop\n")
        expect(con.press("q"), "300", f"{game}: list arm lands on the list's current profile")
        auto.write_text("sourceyaw_arm_set_sp1\n")
        expect(con.press("q"), "600", f"{game}: arm of a profile of the other list")
        expect(con.echoes, ["SY_MODE_SURF", "YAWSURF_600"], f"{game}: it echoes the switch")
        auto.write_text("sourceyaw_arm_set_s\n")
        expect(con.press("q"), "30", f"{game}: arm of the picked surf profile")
        auto.write_text("")
        con.run(f"{core.LOAD_ALIAS}bhop")
        expect(con.cvars["cl_yawspeed"], "300", f"{game}: map-load switch to bhop's current profile")
        # quiet map-load switch
        quiet = dict(data, load_sound=False)
        con = console(core, cfg, quiet, game)
        con.run("yawset_fast")
        con.press("g")  # bhop main 90
        con.sounds.clear()
        con.run(f"{core.LOAD_ALIAS}surf")
        expect((con.cvars["cl_yawspeed"], con.sounds), ("600", []), f"{game}: quiet switch to fast's start")
        expect(con.press("q"), "500", f"{game}: the press after it cycles on")
        if core.GAMES[game]["colors"] == "cvar":
            con.run(f"{core.LOAD_ALIAS}bhop")
            expect(con.cvars["cl_crosshair_color"], "0 255 0 255", f"{game}: quiet switch sets main's colour")
    print("ok   two lists: console command, mode key, arms, map-load switch")


def check_one_list(core, tmp):
    for game in core.GAMES:
        data = base_data(name="main", maps=[],
                         sets=[{"name": "kz", "entries": entries(300, 400), "start": 1, "maps": ["kz_"]}])
        cfg = tmp / "one" / game / "cfg"
        con = console(core, cfg, data, game)
        auto = cfg / f"{core.AUTO_CFG}.cfg"
        expect((con.cvars["cl_yawspeed"], con.binds["q"]), ("90", core.PRESS_ALIAS), f"{game}: one list start")
        expect(con.press("q"), "210", f"{game}: one list cycles")
        con.run("yawset_kz")
        expect(con.cvars["cl_yawspeed"], "400", f"{game}: one list yawset_kz")
        expect([con.press("q"), con.press("q")], ["300", "400"], f"{game}: kz cycles")
        auto.write_text("sourceyaw_arm_set_c\n")
        expect([con.press("q"), con.press("q")], ["90", "210"], f"{game}: arm of main, once")
        auto.write_text("sourceyaw_arm_set_cp1\n")
        expect([con.press("q"), con.press("q")], ["400", "300"], f"{game}: arm of kz, once")
        if core.GAMES[game]["colors"] != "krosshair":
            expect("con_logfile yaw.log" in (cfg / "yaws.cfg").read_text(), True, f"{game}: log for the watcher")
        # one list in game, the surf one: its profiles go by the one-list ids, bhop's get none
        surf = base_data(sets=[{"name": "kz", "entries": entries(300), "start": 0, "maps": ["kz_"]}],
                         separate=False, active="surf",
                         surf={"entries": entries(30, 120), "start": 0, "name": "surf", "maps": [],
                               "sets": [{"name": "fast", "entries": entries(500, 600), "start": 1,
                                         "maps": ["surf_fast"]}]})
        expect(core.validate(surf, game), [], f"{game}: surf-only profiles validate")
        con = console(core, tmp / "one-surf" / game / "cfg", surf, game)
        auto = tmp / "one-surf" / game / "cfg" / f"{core.AUTO_CFG}.cfg"
        expect(("yawset_kz" in con.aliases, con.cvars["cl_yawspeed"]), (False, "30"),
               f"{game}: surf list in game, bhop's profiles left out")
        con.run("yawset_fast")
        expect((con.cvars["cl_yawspeed"], con.press("q")), ("600", "500"), f"{game}: yawset_fast on one list")
        plan = core.watch_plan(surf)
        expect((plan["rules"], plan["picked"]), ([("surf_fast", "cp1", "surf")], {"surf": "c"}),
               f"{game}: one-list ids in the watch plan")
        auto.write_text("sourceyaw_arm_set_c\n")
        expect(con.press("q"), "30", f"{game}: revert arm set_c lands on the picked surf profile")
        # maps without a second profile: nothing to arm
        lone = base_data(maps=["kz_"])
        expect((core.watch_on(lone), core.map_rules(lone)), (False, []), f"{game}: maps on a lone profile ignored")
        expect(core.yaws_cfg(lone, (), game), core.yaws_cfg(base_data(), (), game),
               f"{game}: name and maps alone change nothing in yaws.cfg")
    print("ok   one list: console command, arms")


def check_many(core):
    """Ten profiles per list with 24-character names: console lines under 512 characters, alias
    names under the engine's 32 (Cmd_Alias_f refuses longer ones)."""
    def lst(mode):
        sets = [{"name": f"{mode}_{k:02d}".ljust(24, "x"), "entries": entries(*range(100 + k, 200 + k, 10)),
                 "start": 0, "maps": [f"{mode}_map_{k}_", f"{mode}_other_{k}_"]} for k in range(1, 10)]
        return {"name": mode.ljust(24, "z"), "maps": [], "sets": sets}
    data = base_data(**lst("bhop"), surf={"entries": entries(30, 90), "start": 0, **lst("surf")},
                     mode_key="g", separate=True)
    for game in core.GAMES:
        crosshair = core.GAMES[game]["colors"] != "krosshair"  # CS:S: one colour per speed
        data["crosshair"] = crosshair
        expect(core.validate(data, game), [], f"{game}: ten profiles per list validate")
        text = core.yaws_cfg(data, (), game)
        expect([line[:60] for line in text.splitlines() if len(line) >= 512], [], f"{game}: lines under 512")
        names = {line.split()[1] for line in text.splitlines() if line.startswith("alias ")}
        expect(sorted(n for n in names if len(n) >= 32), [], f"{game}: alias names under 32 characters")
    print("ok   ten profiles per list fit the console's limits")


def check_validate(core):
    def problems(game="momentum", **more):
        return core.validate(two_lists(**more), game)
    expect(problems(name="Main X"), ["Profile name 'Main X': use 1-24 lowercase letters, digits or _"], "bad name")
    expect(problems(name="fast"), ["Two profiles are called 'fast'"], "same name in both lists")
    bad = two_lists()
    bad["sets"][0]["entries"] = []
    expect(core.validate(bad, "css"), ["Profile 'kz' needs at least one yawspeed"], "empty profile")
    bad = two_lists()
    bad["sets"][0]["maps"] = ["bhop kz"]
    expect(core.validate(bad), ["Profile 'kz': 'bhop kz' isn't a map name or prefix"], "bad map")
    clash = two_lists()
    clash["sets"][0]["entries"] = [{"speed": 90, "color": "#abcdef", "sound": None}]
    expect(core.validate(clash, "momentum"), [], "same speed, other colour: fine in Momentum")
    expect(core.validate(clash, "css"),
           ["Yawspeed 90 needs the same colour in profiles 'main' and 'kz' (CS:S crosshairs go by speed)"],
           "same speed, other colour: CS:S refuses")
    expect(core.validate(dict(clash, crosshair=False), "css"), [], "CS:S without colours: fine")
    # the surf list's profiles aren't in game with separate off: their names don't count
    expect(core.validate(two_lists(name="fast", separate=False), "momentum"), [], "unused list's names")
    print("ok   validate profiles")


def check_watcher(core, watch, tmp):
    path = tmp / "auto-profiles.cfg"
    plan = core.watch_plan(two_lists(sets=[
        {"name": "kz", "entries": entries(300), "start": 0, "maps": ["bhop_kz_"]},
        {"name": "kzlong", "entries": entries(350), "start": 0, "maps": ["bhop_kz_long"]}]))
    expect(plan["rules"][0], ("bhop_kz_long", "bp2", "bhop"), "longest prefix first")
    expect(plan["picked"], {"bhop": "b", "surf": "s"}, "picked profiles")
    w = watch.Watcher(path, plan["map_modes"], rules=plan["rules"], picked=plan["picked"])
    w.clear()

    def load(name):
        return w.handle({"type": "map_loaded", "data": {"name": name}})

    expect(load("bhop_arcane"), None, "bhop map, no profile: nothing")
    expect(load("bhop_kz_x"), "set_bp1", "kz map arms kz")
    expect(path.read_text(), "sourceyaw_arm_set_bp1\n", "arm written")
    expect(load("BHOP_KZ_LONGJUMP"), "set_bp2", "longest prefix wins, any case")
    expect(load(None), None, "unknown map: nothing")
    expect(load("bhop_arcane"), "set_b", "a map with no profile goes back to the picked one")
    expect(load("bhop_other"), "", "then the list rule again (bhop on bhop: cleared)")
    expect(load("surf_fast_x"), "set_sp1", "surf profile map")
    expect(load("kz_x"), "set_s", "no list prefix: back to the picked profile of the profile's list")
    expect(load("kz_y"), None, "after that: nothing")
    expect(load("surf_fast2"), "set_sp1", "surf_fast again")
    expect(load("bhop_y"), "set_b", "bhop map after a map switch: bhop's picked profile")
    plan = core.watch_plan(two_lists(auto_mode=False))
    expect(plan["map_modes"], {}, "auto by prefix off: no list rules")
    w = watch.Watcher(path, plan["map_modes"], rules=plan["rules"], picked=plan["picked"])
    expect(load("surf_x"), None, "auto off: a surf map alone does nothing")
    print("ok   watcher: profile maps")


def check_mapload(core, watch, tmp):
    game_dir = tmp / "mapload/momentum"
    cfg = game_dir / "cfg"
    cfg.mkdir(parents=True)
    (cfg / "config.cfg").write_text('cl_crosshair_color "0 255 0 255"\n')
    data = two_lists()
    expect((core.watch_plan(data, "momentum")["mapload"], core.watch_plan(data, "css")["mapload"],
            core.watch_plan(data)["mapload"]), (True, False, False), "map-load file only where gamemode cfgs run")
    core.apply(data, game_dir, game="momentum")
    mapload = cfg / f"{core.MAPLOAD_CFG}.cfg"
    expect(mapload.read_text(), "", "apply makes an empty map-load file")
    expect(f"exec {core.MAPLOAD_CFG}\n{core.LOAD_ALIAS}surf" in (cfg / "surf.cfg").read_text(), True,
           "the surf cfg execs it before the load alias")
    plan = core.watch_plan(data, "momentum")
    w = watch.Watcher(cfg / f"{core.AUTO_CFG}.cfg", plan["map_modes"], rules=plan["rules"],
                      picked=plan["picked"], mapload=mapload)
    con = Console(cfg)
    con.run("exec yaws")

    def load(name, gamemode):
        """A map loads: the watcher sees it first, then the game runs the gamemode cfg; the
        watcher reads the echoes back as the session would."""
        w.handle({"type": "map_loaded", "data": {"name": name}})
        con.echoes.clear()
        con.run(f"exec {gamemode}")
        for echo in con.echoes:
            w.handle({"type": "token", "data": {"name": echo}})
        return con.cvars["cl_yawspeed"]

    expect(load("surf_fast_x", "surf"), "600", "surf_fast from bhop: fast's start at load")
    expect(mapload.read_text(), "", "the list switch's echo empties the map-load file")
    expect(con.press("q"), "500", "the press after it cycles fast")
    expect(load("surf_tequila", "surf"), "30", "a surf map with no profile: back to the picked surf one")
    expect(load("surf_fast_y", "surf"), "600", "surf_fast while on surf: switches in place")
    expect(load("bhop_kz_a", "bhop"), "300", "kz map from surf: kz's start at load")
    con.press("q")
    expect(load("bhop_kz_b", "bhop"), "300", "another kz map: kz starts over")
    expect(load("bhop_arcane", "bhop"), "90", "bhop map with no profile: main again")
    expect(load("bhop_other", "bhop"), "90", "no switch: nothing changes")
    con.press("q")
    expect(load("bhop_other", "bhop"), "210", "a plain map load keeps the current yawspeed")
    expect(load("surf_fast_z", "bhop"), "210", "a surf profile on a bhop-gamemode map goes with the gamemode")
    expect(con.press("g"), "600", "but surf's pointer is on fast")
    expect(load("bhop_arcane", "bhop"), "90", "bhop map after it: main")
    expect(load("surf_plain", "surf"), "30", "then a plain surf map: surf's picked one, not fast")
    # quiet: the start yawspeed without its sound
    quiet = dict(data, load_sound=False)
    core.apply(quiet, game_dir, game="momentum")
    con = Console(cfg)
    con.run("exec yaws")
    con.sounds.clear()
    expect((load("surf_fast_q", "surf"), con.sounds), ("600", []), "quiet map-load switch to fast")
    # the owner's settings shape: surf 45/90/210 starting on 90, tequila 45/120/210 starting on 120
    own = base_data(surf={"entries": entries(45, 90, 210), "start": 1, "name": "surf", "maps": [],
                          "sets": [{"name": "tequila", "entries": entries(45, 120, 210), "start": 1,
                                    "maps": ["surf_tequila"]}]},
                    mode_key="m", auto_mode=True, separate=True, null_turns=True)
    expect(core.watch_plan(own, "momentum")["mapload"], True, "owner's settings: map-load file on")
    core.apply(own, game_dir, game="momentum")
    plan = core.watch_plan(own, "momentum")
    for first in ("bhop", "surf"):
        w = watch.Watcher(cfg / f"{core.AUTO_CFG}.cfg", plan["map_modes"], rules=plan["rules"],
                          picked=plan["picked"], mapload=mapload)
        con = Console(cfg)
        con.run("exec yaws")
        if first == "surf":
            expect(load("surf_mesa", "surf"), "90", "owner: plain surf map on 90")
        expect(load("surf_tequila", "surf"), "120", f"owner: surf_tequila from {first} on 120, no press")
        expect(load("surf_mesa", "surf"), "90", f"owner: next surf map back on 90 ({first})")
    # exec yaws on a map (the here file): its list and profile, never the bhop list on a surf map
    here = cfg / f"{core.HERE_CFG}.cfg"
    expect((here.read_text(), "exec sourceyaw_here" in (cfg / "yaws.cfg").read_text()), ("", True),
           "apply makes the here file, yaws.cfg runs it")

    def rerun():
        con.echoes.clear()
        con.run("exec yaws")
        return con.cvars["cl_yawspeed"], [e for e in con.echoes if e.startswith("SY_MODE")][-1]

    w = watch.Watcher(cfg / f"{core.AUTO_CFG}.cfg", plan["map_modes"], rules=plan["rules"],
                      picked=plan["picked"], mapload=mapload, here=here)
    con = Console(cfg)
    con.run("exec yaws")
    load("surf_tequila", "surf")
    expect(rerun(), ("120", "SY_MODE_SURF"), "exec yaws on surf_tequila: tequila's start, surf list")
    expect(con.press("q"), "210", "and it cycles tequila")
    load("surf_mesa", "surf")
    expect(rerun(), ("90", "SY_MODE_SURF"), "exec yaws on a plain surf map: the surf list")
    # Apply adds a profile for this map: the watcher takes the new settings, exec yaws lands on it
    more = dict(own, surf=dict(own["surf"], sets=[*own["surf"]["sets"], {
        "name": "mesa", "entries": entries(45, 900), "start": 1, "maps": ["surf_mesa"]}]))
    core.apply(more, game_dir, game="momentum")
    new = core.watch_plan(more, "momentum")
    w.plan(new["map_modes"], new["rules"], new["picked"], mapload, here)
    expect(rerun(), ("900", "SY_MODE_SURF"), "after Apply, exec yaws on surf_mesa: the new profile")
    expect(load("surf_mesa", "surf"), "900", "and the map's next load")
    w.handle({"type": "map_left", "data": {}})
    con.sounds.clear()
    expect((here.read_text(), rerun(), con.sounds), ("sy_menu_surf\n", ("90", "SY_MODE_SURF"), []),
           "in the menu: the last list played, on its picked profile, no sound")
    # the next game start: the watcher stops and starts again, the file keeps the last list
    w.clear()
    w = watch.Watcher(cfg / f"{core.AUTO_CFG}.cfg", new["map_modes"], rules=new["rules"],
                      picked=new["picked"], mapload=mapload, here=here)
    w.clear()
    con = Console(cfg)
    con.run("exec yaws")
    expect((w.last, w.mode, con.cvars["cl_yawspeed"], [e for e in con.echoes if e.startswith("SY_MODE")][-1],
            con.sounds), ("surf", "surf", "90", "SY_MODE_SURF", []),
           "game start after a surf map: the surf list, silent; the watcher knows it")
    expect(w.handle({"type": "map_loaded", "data": {"name": "bhop_arcane"}}), "bhop",
           "then a bhop map: the watcher arms bhop (it doesn't think the game is on bhop)")
    load("bhop_arcane", "bhop")
    expect(rerun(), ("90", "SY_MODE_BHOP"), "exec yaws on a bhop map: bhop")
    w.handle({"type": "map_left", "data": {}})
    expect(rerun(), ("90", "SY_MODE_BHOP"), "menu after a bhop map: bhop")
    load("surf_mesa", "surf")
    w.handle({"type": "token", "data": {"name": core.MODE_TOKENS["bhop"]}})  # the mode key
    w.handle({"type": "map_left", "data": {}})
    expect(here.read_text(), "sy_menu_bhop\n", "mode key on a surf map, then the menu: bhop")
    expect(core.last_list(here), "bhop", "last_list reads it")
    expect(core.last_list(cfg / "nothing.cfg"), None, "last_list: no file, no list")
    load("surf_mesa", "surf")
    # a bhop profile's maps don't pull the bhop list onto a surf map
    odd = dict(more, sets=[{"name": "kz", "entries": entries(300), "start": 0, "maps": ["surf_mesa", "kz_"]}])
    core.apply(odd, game_dir, game="momentum")
    new = core.watch_plan(odd, "momentum")
    w.plan(new["map_modes"], new["rules"], new["picked"], mapload, here)
    expect(load("surf_mesa", "surf"), "900", "bhop profile with a surf map: the surf one wins")
    expect("sourceyaw_arm_" in (cfg / f"{core.AUTO_CFG}.cfg").read_text(), False, "no arm for the bhop profile")
    expect(rerun(), ("900", "SY_MODE_SURF"), "exec yaws there: surf")
    expect(load("kz_x", "bhop"), "300", "a map of no list: the profile's own list")
    # what run() reads again when Apply saves (the settings file's stamp changes)
    stamp = watch._settings_stamp()
    core.save_settings(more, "momentum")
    expect(watch._settings_stamp() != stamp, True, "saving changes the stamp")
    got = watch._plan("momentum", cfg)
    expect((got["mapload"], got["here"], ("surf_mesa", "sp2", "surf") in got["rules"]), (mapload, here, True),
           "run()'s plan from the file")
    w = watch.Watcher(cfg / f"{core.AUTO_CFG}.cfg", **got)
    expect(w.picked, {"bhop": "b", "surf": "s"}, "a Watcher from it")
    # off: no file, no exec, the press arm only
    core.apply(dict(data, load_switch=False), game_dir, game="momentum")
    expect((mapload.exists(), (cfg / "surf.cfg").exists()), (False, False), "load_switch off: no map-load file")
    core.apply(base_data(), game_dir, game="momentum")
    expect(mapload.exists(), False, "no profiles: no map-load file")
    core.apply(data, game_dir, game="momentum")
    core.remove_from_game(game_dir, "momentum")
    expect(mapload.exists(), False, "remove_from_game deletes it")
    print("ok   map-load profile switch (Momentum)")


def check_mapload_one_list(core, watch, tmp):
    """One list (separate off) with a profile's maps: the owner's surf_sync_h set, 2026-11-23."""
    game_dir = tmp / "mapload-one/momentum"
    cfg = game_dir / "cfg"
    cfg.mkdir(parents=True)
    (cfg / "config.cfg").write_text('cl_crosshair_color "0 255 0 255"\n')
    data = base_data(name="main", maps=[], separate=False,
                     sets=[{"name": "sync", "entries": entries(45, 1000, 210), "start": 1,
                            "maps": ["surf_sync_h"]}])
    plan = core.watch_plan(data, "momentum")
    expect((plan["mapload"], plan["here"], plan["picked"]), (True, True, {"bhop": "c"}),
           "one list with profile maps: map-load file and here file")
    core.apply(data, game_dir, game="momentum")
    mapload, here = cfg / f"{core.MAPLOAD_CFG}.cfg", cfg / f"{core.HERE_CFG}.cfg"
    expect((mapload.read_text(), here.read_text()), ("", ""), "apply makes both files, empty")
    for gamemode in ("surf", "bhop"):
        text = (cfg / f"{gamemode}.cfg").read_text()
        expect((f"exec {core.MAPLOAD_CFG}" in text, core.LOAD_ALIAS in text), (True, False),
               f"{gamemode} cfg: the map-load file only, no list load alias")
    expect(f"exec {core.HERE_CFG}" in (cfg / "yaws.cfg").read_text(), True, "yaws.cfg execs the here file")
    w = watch.Watcher(cfg / f"{core.AUTO_CFG}.cfg", plan["map_modes"], rules=plan["rules"],
                      picked=plan["picked"], mapload=mapload, here=here)
    con = Console(cfg)
    con.run("exec yaws")

    def load(name, gamemode):
        w.handle({"type": "map_loaded", "data": {"name": name}})
        con.echoes.clear()
        con.run(f"exec {gamemode}")
        for echo in con.echoes:
            w.handle({"type": "token", "data": {"name": echo}})
        return con.cvars["cl_yawspeed"]

    expect(load("surf_sync_h", "surf"), "1000", "the profile's map: its start at load")
    expect(con.press("q"), "210", "the press cycles the profile")
    con.run("exec yaws")
    expect(con.cvars["cl_yawspeed"], "1000", "exec yaws on that map: the profile again")
    expect(con.press("q"), "210", "and the press stays on it")
    expect(load("surf_other", "surf"), "90", "a map with no profile: main again")
    con.run("exec yaws")
    expect(con.cvars["cl_yawspeed"], "90", "exec yaws there: main")
    w.handle({"type": "map_left", "data": {}})
    expect(here.read_text(), "", "off a map: an empty here file")
    expect(load("surf_sync_h2", "bhop"), "1000", "any gamemode cfg switches it")
    # Apply with the game open: the next press reruns yaws.cfg once (the guard), then cycles
    auto = cfg / f"{core.AUTO_CFG}.cfg"
    w.handle({"type": "map_left", "data": {}})
    expect(load("surf_other", "surf"), "90", "back on main")
    expect(con.press("q"), "210", "a press with nothing new: no rerun")
    core.apply(dict(data, entries=entries(70, 140, 280), start=1), game_dir, game="momentum")
    expect([con.press("q"), con.press("q")], ["280", "70"], "after Apply: the new list from the next press, once")
    w.handle({"type": "map_loaded", "data": {"name": "surf_sync_h"}})
    expect(auto.read_text().splitlines()[-1], "sourceyaw_arm_set_cp1", "an arm goes after the guard")
    expect((con.press("q"), con.unknown), ("1000", []), "the arm still works under the guard")
    # back to the first settings: the guard of their yaws.cfg ran before, still a rerun
    core.apply(data, game_dir, game="momentum")
    gen = (cfg / "yaws.cfg").read_text().split(f"alias {core.LOADED_ALIAS} ")[1].strip()
    con.press("q")
    expect(con.aliases[core.LOADED_ALIAS], gen, "Apply A, B, then A again: reruns each time")
    # a game whose yaws.cfg predates the guard: unknown sy_loaded, then the rerun
    old = Console(cfg)
    old.run((cfg / "yaws.cfg").read_text().replace(f"alias {core.LOADED_ALIAS}", "//"))
    auto.write_text(auto.read_text().replace("sourceyaw_arm_set_cp1\n", ""))
    expect((old.press("q"), old.unknown), ("210", ["sy_loaded"]),
           "an older yaws.cfg: rerun on the press, on the map's profile (the here file)")
    expect(old.press("q"), "45", "then no more reruns")
    # quiet: the start yawspeed without its sound
    core.apply(dict(data, load_sound=False), game_dir, game="momentum")
    con = Console(cfg)
    con.run("exec yaws")
    w.handle({"type": "map_left", "data": {}})
    load("surf_other", "surf")
    con.sounds.clear()
    expect((load("surf_sync_h", "surf"), con.sounds), ("1000", []), "quiet map-load switch")
    # load_switch off: the press arm only; no profile maps: no files, no gamemode block
    core.apply(dict(data, load_switch=False), game_dir, game="momentum")
    expect((mapload.exists(), here.exists(), (cfg / "surf.cfg").exists()), (False, True, False),
           "load_switch off: no map-load file, the here file stays")
    core.apply(base_data(separate=False), game_dir, game="momentum")
    expect((mapload.exists(), here.exists()), (False, False), "no profiles: neither file")
    print("ok   map-load profile switch, one list (Momentum)")


def check_watch_run(core, watch, tmp, separate=False):
    """run() itself: started with no profile maps (the owner's case, 2026-11-23: a profile made for
    the map in game), it puts the here file on the new profile, then writes WATCH_READ. With
    `separate`, the profile is in the surf list."""
    import queue
    import threading
    import time

    game_dir = tmp / f"watch-run-{separate}/momentum"
    cfg = game_dir / "cfg"
    cfg.mkdir(parents=True)
    (cfg / "config.cfg").write_text('cl_crosshair_color "0 255 0 255"\n')
    data = base_data(name="main", maps=[], separate=separate)
    if separate:
        data.update(surf={"entries": entries(30, 90, 120), "start": 0, "name": "surf", "maps": [], "sets": []},
                    mode_key="g")
    core.save_settings(data, "momentum")
    core.apply(data, game_dir, game="momentum")
    here, auto = cfg / f"{core.HERE_CFG}.cfg", cfg / f"{core.AUTO_CFG}.cfg"
    if not separate:  # separate lists with auto have both already
        expect((here.exists(), auto.exists()), (False, False), "no profile maps: no here file, no auto cfg")
    joined = []

    class FakeJoined:
        mode = "fake"

        def __init__(self, log, port=None):
            self.events = queue.SimpleQueue()
            joined.append(self)

        def close(self):
            pass

    real_join, watch.session.join = watch.session.join, FakeJoined
    stop = threading.Event()
    thread = threading.Thread(target=watch.run, args=(str(game_dir / "yaw.log"), "momentum", 0, stop))
    thread.start()

    def read_up_to_date(timeout=5):
        want = str(core.SETTINGS.stat().st_mtime_ns)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if core.WATCH_READ.exists() and core.WATCH_READ.read_text().strip() == want:
                return True
            time.sleep(0.02)
        return False

    try:
        expect(read_up_to_date(), True, "run(): WATCH_READ at start")
        if not separate:
            expect(auto.exists(), False, "run() with no auto cfg in use: none made")
        joined[0].events.put({"type": "map_loaded", "data": {"name": "surf_shoria"}})
        time.sleep(0.2)
        shoria = {"name": "shoria", "entries": entries(45, 210), "start": 0, "maps": ["surf_shoria"]}
        new = dict(data, surf=dict(data["surf"], sets=[shoria])) if separate else dict(data, sets=[shoria])
        time.sleep(0.01)  # a new stamp
        core.save_settings(new, "momentum")
        core.apply(new, game_dir, game="momentum")
        expect(read_up_to_date(), True, "run(): WATCH_READ after Apply")
        expect(here.read_text().startswith("sy_pstate_"), True,
               "here file on the map's new profile by the time WATCH_READ says so")
    finally:
        stop.set()
        thread.join(5)
        watch.session.join = real_join
    print(f"ok   watcher run(): profile made in game{' (separate lists)' if separate else ''}")


def check_files(core, tmp):
    game_dir = tmp / "files/momentum"
    (game_dir / "cfg").mkdir(parents=True)
    (game_dir / "cfg/config.cfg").write_text('cl_crosshair_color "0 255 0 255"\n')
    core.apply(two_lists(), game_dir, game="momentum")
    colors = sorted(p.name for p in (game_dir / "cfg" / core.COLOR_DIR).iterdir())
    expect(colors, ["b1.cfg", "b2.cfg", "b3.cfg", "bp1_1.cfg", "bp1_2.cfg",
                    "s1.cfg", "s2.cfg", "s3.cfg", "sp1_1.cfg", "sp1_2.cfg"], "a colour cfg per profile yawspeed")
    expect("AUTO=1" in core.WATCH_ENV.read_text(), True, "watcher on")
    core.apply(base_data(name="main", sets=[{"name": "kz", "entries": entries(300), "start": 0, "maps": ["kz_"]}]),
               game_dir, game="momentum")
    expect("AUTO=1" in core.WATCH_ENV.read_text(), True, "watcher on for one list's profile maps")
    core.apply(base_data(), game_dir, game="momentum")
    expect(("AUTO=0" in core.WATCH_ENV.read_text(),
            sorted(p.name for p in (game_dir / "cfg" / core.COLOR_DIR).iterdir())),
           (True, ["c1.cfg", "c2.cfg", "c3.cfg"]), "profiles gone: watcher off, their colour cfgs gone")
    core.write_crosshairs(two_lists(), True)
    expect(sorted(p.name for p in core.CROSSHAIRS.iterdir()),
           ["YAWSURF_120.png", "YAWSURF_30.png", "YAWSURF_500.png", "YAWSURF_600.png", "YAWSURF_90.png",
            "YAW_210.png", "YAW_300.png", "YAW_400.png", "YAW_60.png", "YAW_90.png"],
           "CS:S: a crosshair image per profile speed")
    print("ok   apply: colour cfgs, crosshair images, watcher")


def check_hub(tmp):
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
    sys.path.insert(0, str(cm.KIT))
    from movekit import hub
    section = hub.local_import(HERE / "hub_section.py", "hub_section")
    core = section._core()
    game_dir = tmp / "hub-profiles/momentum"
    (game_dir / "cfg").mkdir(parents=True)
    (game_dir / "cfg/config.cfg").write_text('cl_crosshair_color "0 255 0 255"\n')
    core.find_game = lambda game: game_dir
    core.flatpak_steam_only = lambda game="css": False
    core.SETTINGS.unlink(missing_ok=True)
    st = section.load("momentum")
    expect((st["name"], st["maps"], st["sets"], st["profile_cmd"]), ("bhop", [], [], "yawset_"), "new: one profile")
    kz = {"name": "KZ", "entries": [{"speed": 300, "color": "#ff0000", "sound": ""}], "start": 0,
          "maps": "bhop_kz_, kz_ BHOP_KZ_"}
    form = {"key": st["key"], "crosshair": st["crosshair"], "start": st["start"], "base": st["base"],
            "entries": st["entries"], "name": "main", "maps": [], "sets": [kz],
            "surf": {"entries": [{"speed": 30, "color": "#123456", "sound": ""}], "start": 0,
                     "name": "surf", "maps": ["surf_"], "sets": []},
            "separate": True, "active": "bhop", "mode_key": "g", "auto_mode": True,
            "load_switch": True, "load_sound": True}
    got = section.apply("momentum", form)
    expect(got["saved"], True, f"apply with profiles ({got['messages']})")
    saved = core.load_settings("momentum")
    st = section.load("momentum")
    expect((st["name"], st["sets"][0]["name"], st["sets"][0]["maps"]), ("main", "kz", ["bhop_kz_", "kz_"]),
           "names lowercase, maps split, lowercase, no repeats")
    expect((st["surf"]["name"], st["surf"]["maps"]), ("surf", ["surf_"]), "surf list's profile kept")
    again = {k: st[k] for k in form if k in st}
    again["surf"] = {k: st["surf"][k] for k in ("entries", "start", "name", "maps", "sets")}
    got = section.apply("momentum", again)
    expect(got["saved"], True, "apply the loaded form unchanged")
    expect(core.load_settings("momentum"), saved, "load and apply round trip keeps the settings")
    got = section.apply("momentum", dict(form, sets=[dict(kz, name="main")]))
    expect((got["saved"], got["messages"]), (False, ["Two profiles are called 'main'"]), "duplicate name refused")
    got = section.apply("momentum", dict(form, sets=[dict(kz, maps=5)]))
    expect(got["saved"], False, "maps of the wrong type refused")
    got = section.apply("momentum", dict(form, profile_auto=False))
    st = section.load("momentum")
    expect((got["saved"], st["profile_auto"], st["sets"][0]["maps"]), (True, False, ["bhop_kz_", "kz_"]),
           "profile by map off from the page: saved, the maps kept")
    print("ok   hub section keeps profiles")


def check_profile_auto(core):
    """Profile by map (profile_auto) off: the maps stay saved but switch nothing; bhop or surf by
    map prefix (auto_mode) works on its own. Settings from before the switch get it on only when a
    profile has maps."""
    data = two_lists()
    expect(bool(core.map_rules(data)), True, "profile by map on: map rules")
    off = two_lists(profile_auto=False)
    expect((core.map_rules(off), core.watch_plan(off)["rules"]), ([], []), "profile by map off: no map rules")
    expect((core.watch_on(off), core.watch_plan(off)["map_modes"] != {}), (True, True),
           "profile by map off, bhop or surf by prefix on: the watcher still switches lists")
    neither = two_lists(profile_auto=False, auto_mode=False)
    expect((core.watch_on(neither), core.here_on(neither)), (False, False), "both off: no watcher, no here file")
    expect(f"exec {core.HERE_CFG}" in core.yaws_cfg(neither, (), "momentum"), False, "both off: yaws.cfg runs no here file")
    one = two_lists(separate=False, profile_auto=False)
    one["single"] = core.single_list(one)
    one["single"]["sets"] = [{"name": "kz", "entries": entries(300, 400), "start": 0, "maps": ["bhop_kz_"]}]
    expect((core.map_rules(one), core.watch_on(one)), ([], False), "one list, profile by map off: no watcher")

    core.save_settings(off, "momentum")
    loaded = core.load_settings("momentum")
    expect((loaded["profile_auto"], loaded["sets"][0]["maps"]), (False, ["bhop_kz_"]), "off saved, the maps kept")
    old = {k: v for k, v in data.items() if k != "profile_auto"}
    core.save_settings(old, "momentum")
    expect(core.load_settings("momentum")["profile_auto"], True, "older settings with profile maps: on")
    bare = base_data(name="main", maps=[], sets=[{"name": "b", "entries": entries(1, 2), "start": 0, "maps": []}])
    core.save_settings(bare, "momentum")
    expect(core.load_settings("momentum")["profile_auto"], False, "older settings without profile maps: off")
    print("ok   profile by map switch")


def run_all():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for var, sub in (("HOME", "home"), ("XDG_CONFIG_HOME", "home/.config"),
                         ("XDG_DATA_HOME", "home/.local/share"), ("XDG_CACHE_HOME", "home/.cache")):
            os.environ[var] = str(tmp / sub)
        import mode_watch
        import yawcore as core
        core.find_game = lambda game: None
        core.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        check_two_lists(core, tmp / "console")
        check_one_list(core, tmp)
        check_many(core)
        check_validate(core)
        check_profile_auto(core)
        check_watcher(core, mode_watch, tmp)
        check_mapload(core, mode_watch, tmp)
        check_mapload_one_list(core, mode_watch, tmp)
        check_watch_run(core, mode_watch, tmp)
        check_watch_run(core, mode_watch, tmp, separate=True)
        check_files(core, tmp)
        check_hub(tmp)
    print("all profile checks passed")


if __name__ == "__main__":
    run_all()
