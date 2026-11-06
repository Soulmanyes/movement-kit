#!/usr/bin/env python3
"""Picks Source Yaw's bhop or surf list from the map's name (started by launch-hook.sh when the
profile has a surf list and auto_mode is on).

  mode_watch.py LOG GAME

The game can't be sent commands from outside. So yaws.cfg binds the yaw key to
`exec sourceyaw_auto; yaw_cycle`, and this helper writes into cfg/sourceyaw_auto.cfg:
  - a map loads whose prefix (map_modes) means the other list: the arm alias of that list, so the
    next press starts it;
  - the game reports a list switch (SY_MODE_BHOP/SURF, echoed by an arm or the mode key), or a map
    of the current list loads: nothing (the file is emptied).
The current list is known from those tokens only. A map name that isn't known changes nothing.
The tokens and map loads come from the movekit session for LOG (movekit/session.py).
"""
import queue  # noqa: I001, RUF100 - movekit must come after yawcore (see below)
import signal
import sys
from pathlib import Path

import yawcore

from movekit import session  # after yawcore, which puts movekit on the path

TOKEN_MODES = {token: mode for mode, token in yawcore.MODE_TOKENS.items()}


class Watcher:
    """What the session's events mean for the auto cfg. `path` is cfg/sourceyaw_auto.cfg."""

    def __init__(self, path, map_modes, mode="bhop"):
        self.path = Path(path)
        self.map_modes = map_modes
        self.mode = mode  # yaws.cfg starts the game on the bhop list

    @property
    def armed(self):
        """The list the file arms now, or None. Read from the file each time: the hub's Apply
        empties it behind the watcher's back."""
        try:
            text = self.path.read_text().strip()
        except OSError:
            return None
        return text.removeprefix("sourceyaw_arm_") or None

    def _write(self, arm):
        if arm == self.armed and self.path.exists():
            return
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(f"sourceyaw_arm_{arm}\n" if arm else "")
        tmp.replace(self.path)

    def clear(self):
        if self.path.parent.is_dir():
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text("")
            tmp.replace(self.path)

    def handle(self, event):
        """Updates the file for one session event; returns the arm written, "" for a clear, else None."""
        kind, data = event["type"], event["data"]
        if kind == "token" and data.get("name") in TOKEN_MODES:
            self.mode = TOKEN_MODES[data["name"]]
            before = self.armed
            self._write(None)
            return "" if before else None
        if kind == "map_loaded":
            want = yawcore.prefix_value(data.get("name"), self.map_modes)
            if want not in yawcore.MODES:
                return None
            arm = None if want == self.mode else want
            before = self.armed
            self._write(arm)
            return (arm or "") if arm != before else None
        return None


def run(log, game, port=session.PORT, stop=None):
    """Arms and clears the auto cfg from the session's events until `stop` (a threading.Event) is
    set, or forever; clears it on the way out. On Windows it runs as a thread of the launch."""
    data = yawcore.load_settings(game)
    watcher = Watcher(Path(log).parent / "cfg" / f"{yawcore.AUTO_CFG}.cfg",
                      data.get("map_modes") or yawcore.DEFAULT_MAP_MODES)
    watcher.clear()
    joined = session.join(log, port=port)
    print(f"mode: session events for {log} ({joined.mode})", flush=True)
    try:
        while stop is None or not stop.is_set():
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
