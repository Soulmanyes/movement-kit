#!/usr/bin/env python3
"""Picks Source Yaw's bhop or surf list, or yawspeed profile, from the map's name (started by
launch-hook.sh at every launch that logs the console, whatever the settings: a surf list with
auto_mode on, or a profile with maps, made while the game runs then works after Apply).

  mode_watch.py LOG GAME

The game can't be sent commands from outside. So yaws.cfg binds the yaw key to
`exec sourceyaw_auto; yaw_cycle`, and this helper writes into cfg/sourceyaw_auto.cfg:
  - a map loads whose prefix (map_modes) means the other list: the arm alias of that list, so the
    next press starts it;
  - the game reports a list switch (SY_MODE_BHOP/SURF, echoed by an arm or the mode key), or a map
    of the current list loads: nothing (the file is emptied).
The current list is known from those tokens only. A map name that isn't known changes nothing.
Yawspeed profiles with maps (1.15.0, yawcore.PROFILE_CMD): a map whose name starts with one of a
profile's maps (the longest match wins) gets that profile's arm, sourceyaw_arm_set_<id>; the game
ignores it while the profile is already the current one. The next map that matches no profile
after such a switch arms its list's picked profile again, so a profile picked by map doesn't stick;
one picked in the console does.
Where the game runs gamemode cfgs (Momentum) with the map-load switch on, the profile switches as
the map loads too: on every map load this helper writes cfg/sourceyaw_mapload.cfg (yawcore.MAPLOAD_CFG),
which the gamemode cfg execs, with that map's profile (or the picked one it goes back to), else
nothing. The press arm stays as the fallback for a gamemode cfg that runs before the file is written.
With both lists in game it also keeps cfg/sourceyaw_here.cfg (yawcore.HERE_CFG) on the loaded map's
list and profile, so `exec yaws` on a map lands there, not on the bhop list yaws.cfg starts on. Off
a map it holds the list last played (the mode key counts), so the menu and the next game start land
on that one too. With one list and profile maps it keeps the here file too, for the map's profile;
off a map it's empty there. A
profile's maps never pull in the other list on a map whose prefix (map_modes) names a list: only
the mode key changes lists there. Apply in the hub saves the settings; the watcher reads them again
then, and puts the here file on the new rules at once; then it writes the settings stamp it read
to yawcore.WATCH_READ, which Apply waits for before it runs exec yaws in the game.
The tokens and map loads come from the movekit session for LOG (movekit/session.py).
"""
import queue  # noqa: I001, RUF100 - movekit must come after yawcore (see below)
import signal
import sys
from pathlib import Path

import yawcore

from movekit import session  # after yawcore, which puts movekit on the path

TOKEN_MODES = {token: mode for mode, token in yawcore.MODE_TOKENS.items()}
ARM = "sourceyaw_arm_"


class Watcher:
    """What the session's events mean for the auto cfg. `path` is cfg/sourceyaw_auto.cfg."""

    def __init__(self, path, map_modes, mode="bhop", rules=(), picked=None, mapload=None, here=None):
        self.path = Path(path)
        self.by_map = None  # (id, mode) of the profile the last matching map armed, if not a picked one
        self.map = None  # the map loaded, if any
        self.last = None  # the list last played on a map: the here file's off a map
        self.plan(map_modes, rules, picked, mapload, here)
        # yaws.cfg starts the game on the bhop list, then the here file on the last list played
        self.mode = self.last or mode

    def plan(self, map_modes, rules=(), picked=None, mapload=None, here=None):
        """Takes (new) settings: yawcore.watch_plan's parts, and the paths of the map-load file and
        the here file (None: not used). The here file follows them at once."""
        self.map_modes = map_modes
        self.rules = list(rules)  # [(map prefix, profile id, mode)], longest prefix first
        self.picked = dict(picked or {})  # {mode: id of the profile picked in the hub}
        self.mapload = Path(mapload) if mapload else None  # cfg/sourceyaw_mapload.cfg
        self.here = Path(here) if here else None  # cfg/sourceyaw_here.cfg
        if self.last is None and self.here:  # the last session's, kept in the file
            self.last = yawcore.last_list(self.here)
        self._here()

    def _lines(self):
        try:
            return self.path.read_text().splitlines()
        except OSError:
            return []

    @property
    def armed(self):
        """The list the file arms now, or None. Read from the file each time: the hub's Apply
        rewrites it behind the watcher's back."""
        for line in self._lines():
            if line.startswith(ARM):
                return line.removeprefix(ARM).strip() or None
        return None

    def _write(self, arm):
        """Puts `arm` (None: none) after the file's other lines: Apply's rerun guard stays."""
        if arm == self.armed and self.path.exists():
            return
        if not self.path.parent.is_dir() or (arm is None and not self.path.exists()):
            return  # no auto cfg while the settings don't use one (yawcore.apply removed it)
        lines = [line for line in self._lines() if not line.startswith(ARM)] + ([f"{ARM}{arm}"] if arm else [])
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text("".join(f"{line}\n" for line in lines))
        tmp.replace(self.path)

    def clear(self):
        if self.path.parent.is_dir():
            self._write(None)
        self._load(None)
        self.map = None
        self._here()

    @staticmethod
    def _put(path, text):
        if not path or not path.parent.is_dir():
            return
        try:
            if path.read_text() == text:
                return
        except OSError:
            pass
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text)
        tmp.replace(path)

    def _load(self, profile, also=()):
        """Writes the map-load file: (id, mode) of the profile to switch to, or None for nothing.
        `also`: ids of profiles of the other list to point that list back at first."""
        text = "".join(f"sy_pstate_{pid}; " for pid in also)
        self._put(self.mapload, f"{text}sy_pstate_{profile[0]}; sy_lif_{profile[1]}\n" if profile else "")

    def _here(self):
        """Writes the here file for self.map: its list's load alias, after its profile's pointers
        when a profile has the map (yaws.cfg has just put every list on its picked profile). Off a
        map, or on a map of no list, it's the last list played (its picked profile), if any."""
        want = yawcore.prefix_value(self.map, self.map_modes)
        rule = self._rule(self.map)
        mode = want if want in yawcore.MODES else rule[1] if rule else None
        if mode:
            text = f"sy_pstate_{rule[0]}; sy_lif_{mode}; " if rule else ""
            text += f"{yawcore.LOAD_ALIAS}{mode}\n"
        else:  # silent, as yaws.cfg is at launch; one list: yaws.cfg's own start
            text = f"{yawcore.MENU_ALIAS}{self.last}\n" if self.last and len(self.picked) > 1 else ""
        self._put(self.here, text)

    def handle(self, event):
        """Updates the file for one session event; returns the arm written, "" for a clear, else None."""
        kind, data = event["type"], event["data"]
        if kind == "token" and data.get("name") in TOKEN_MODES:
            self.mode = TOKEN_MODES[data["name"]]
            if self.map is not None:  # the mode key on a map: that's the list played now
                self.last = self.mode
                self._here()  # on a map of no list, exec yaws stays on it
            self._load(None)  # it ran (or this map didn't need it): not again on a late map load
            before = self.armed
            self._write(None)
            return "" if before else None
        if kind == "map_left":
            self.map = None
            self._here()
            return None
        if kind == "map_loaded":
            name = data.get("name")
            self.map = name
            want = yawcore.prefix_value(name, self.map_modes)
            rule = self._rule(name)
            if want in yawcore.MODES or rule:
                self.last = want if want in yawcore.MODES else rule[1]
            self._here()
            load, also = None, ()
            if rule:
                pid, mode = rule
                self.by_map = None if pid == self.picked.get(mode) else rule
                arm = f"set_{pid}"
                load = rule
            elif self.by_map and name is not None:
                mode = want if want in yawcore.MODES else self.by_map[1]
                left = self.by_map[1]  # the list the map's profile was on
                self.by_map = None
                arm = f"set_{self.picked[mode]}" if mode in self.picked else None
                load = (self.picked[mode], mode) if mode in self.picked else None
                if left != mode and left in self.picked:  # the arm alone would leave it on the map's profile
                    also = (self.picked[left],)
            elif want in yawcore.MODES:
                arm = None if want == self.mode else want
            else:
                self._load(None)
                return None
            self._load(load, also)
            before = self.armed
            self._write(arm)
            return (arm or "") if arm != before else None
        return None

    def _rule(self, name):
        """(profile id, mode) of the longest profile map prefix `name` starts with, or None. A
        profile of the other list than the one the map's prefix names doesn't count."""
        if name is None:
            return None
        want = yawcore.prefix_value(name, self.map_modes)
        for prefix, pid, mode in self.rules:
            if name.lower().startswith(prefix) and (want not in yawcore.MODES or mode == want):
                return pid, mode
        return None


def _settings_stamp():
    try:
        return yawcore.SETTINGS.stat().st_mtime_ns
    except OSError:
        return None


def _read(stamp):
    """Tells Apply the watcher is on the settings of `stamp` (yawcore.WATCH_READ)."""
    try:
        tmp = yawcore.WATCH_READ.with_name(yawcore.WATCH_READ.name + ".tmp")
        tmp.write_text(f"{stamp}\n")
        tmp.replace(yawcore.WATCH_READ)
    except OSError as e:
        print(f"mode: {yawcore.WATCH_READ.name} not written: {e}", flush=True)


def _plan(game, cfg):
    """Watcher.plan's arguments from the saved settings."""
    plan = yawcore.watch_plan(yawcore.load_settings(game), game)
    return {"map_modes": plan["map_modes"], "rules": plan["rules"], "picked": plan["picked"],
            "mapload": cfg / f"{yawcore.MAPLOAD_CFG}.cfg" if plan["mapload"] else None,
            "here": cfg / f"{yawcore.HERE_CFG}.cfg" if plan["here"] else None}


def run(log, game, port=session.PORT, stop=None):
    """Arms and clears the auto cfg from the session's events until `stop` (a threading.Event) is
    set, or forever; clears it on the way out. On Windows it runs as a thread of the launch."""
    cfg = Path(log).parent / "cfg"
    stamp = _settings_stamp()
    watcher = Watcher(cfg / f"{yawcore.AUTO_CFG}.cfg", **_plan(game, cfg))
    watcher.clear()
    _read(stamp)
    joined = session.join(log, port=port)
    print(f"mode: session events for {log} ({joined.mode})", flush=True)
    try:
        while stop is None or not stop.is_set():
            if _settings_stamp() != stamp:  # Apply in the hub: the new profiles and maps
                stamp = _settings_stamp()
                try:
                    watcher.plan(**_plan(game, cfg))
                    _read(stamp)
                    print("mode: settings read again", flush=True)
                except (OSError, ValueError) as e:  # caught mid-write: the next stamp change retries
                    print(f"mode: settings not read: {e}", flush=True)
                    stamp = None
            try:
                event = joined.events.get(timeout=0.5)
            except queue.Empty:
                continue
            done = watcher.handle(event)
            if done:
                print(f"mode: {event['data'].get('name')} -> arm {done}", flush=True)
    finally:
        joined.close()
        watcher.clear()


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in yawcore.GAMES:
        sys.exit(f"usage: mode_watch.py LOG {'|'.join(yawcore.GAMES)}")
    # movekit-run stops its helpers with SIGTERM: leave through finally, freeing the session's port
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        run(sys.argv[1], sys.argv[2])
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
