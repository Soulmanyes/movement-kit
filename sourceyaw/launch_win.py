"""Source Yaw's game launch on Windows (Phase 12 in PLAN.md): what launch-hook.sh does on Linux.

module_hooks.launch calls start() inside the hub exe's launch process (movekit/dispatch.py: the
launch hooks, then the game, then the process exits with it), so the helpers here are threads of
that process and live exactly as long as the game:
  - yaws.cfg rewritten from the saved settings (yawcore.apply_at_launch),
  - the list switcher (mode_watch.run) when auto mode is on.
The strafe trainer is its own module since Phase 13 (strafe-trainer/launch_win.py).
No crosshair colour on Windows. Everything prints to %APPDATA%\\sourceyaw\\run.log, the only
place a windowed exe's output and a thread's traceback can be read afterwards.

Also `py launch_win.py GAME` from a checkout, to try the helpers without the hub (start the game
yourself, then this): they run until Ctrl+C.
"""

import atexit  # noqa: I001, RUF100 - movekit must come after yawcore (see below)
import sys
import threading
import time
import traceback

import yawcore

from movekit import games as kit_games  # after yawcore, which puts movekit on the path
from movekit import logfile

LOG = yawcore.CONFIG_DIR / "run.log"
LOG_MAX = 1_000_000


def game_of(argv, find_game=None):
    """The game Steam is starting (movekit.games.from_command), or None (another game: Source Yaw
    stays out of it)."""
    return kit_games.from_command(argv, find_game or yawcore.find_game)


def _thread(name, target, *args):
    """A daemon thread whose exception lands in the log (a windowed exe has nowhere else)."""
    def body():
        try:
            target(*args)
        except Exception:  # noqa: BLE001 - logged, the game keeps running
            print(f"{name}: stopped by an error:\n{traceback.format_exc()}", flush=True)
    thread = threading.Thread(target=body, name=f"sourceyaw-{name}", daemon=True)
    thread.start()
    return thread


def start(argv):
    """Sets Source Yaw up for the game in argv and starts its helpers; returns at once. Returns
    the threads it started (none when the game isn't one of Source Yaw's or isn't set up)."""
    logfile.tee(LOG, LOG_MAX)
    game = game_of(argv)
    if game is None:
        print(f"sourceyaw: {argv[:1]} isn't CS:S or Momentum Mod; nothing to do", flush=True)
        return []
    if not yawcore.set_up(game) or not yawcore.apply_at_launch(game):
        return []
    data = yawcore.load_settings(game)
    log = yawcore.find_game(game) / "yaw.log"
    stop = threading.Event()
    threads = []
    if yawcore.auto_on(data):
        import mode_watch
        threads.append(_thread("mode", mode_watch.run, str(log), game, mode_watch.session.PORT, stop))

    def finish():
        # at the exe's exit, after the game closed: let each helper close its own things
        # (the auto cfg cleared)
        stop.set()
        for thread in threads:
            thread.join(2)
        alive = [t.name for t in threads if t.is_alive()]
        print(f"sourceyaw: helpers stopped{' except ' + ', '.join(alive) if alive else ''}", flush=True)
    atexit.register(finish)
    print(f"sourceyaw: {yawcore.GAMES[game]['name']} started with "
          f"{', '.join(t.name for t in threads) or 'yaws.cfg only'}", flush=True)
    return threads


def main():
    args = sys.argv[1:]
    if len(args) != 1 or args[0] not in yawcore.GAMES:
        sys.exit(f"usage: launch_win.py {'|'.join(yawcore.GAMES)}")
    game_dir = yawcore.find_game(sys.argv[1])
    if not game_dir:
        sys.exit(f"{yawcore.GAMES[sys.argv[1]]['name']} not found in your Steam libraries")
    # as if Steam started the game: its folder's exe, plus -game
    threads = start([str(game_dir.parent / "game.exe"), "-game", game_dir.name])
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
