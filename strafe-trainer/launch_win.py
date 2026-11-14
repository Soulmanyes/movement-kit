"""The Strafe Trainer's game launch on Windows: what launch-hook.sh does on Linux.

module_hooks.launch calls start() inside the core exe's launch process (movekit/dispatch.py: the
launch hooks, then the game, then the process exits with it), so the trainer is a thread of that
process and lives exactly as long as the game. Output goes to %APPDATA%\\strafe-trainer\\run.log.

Also `py launch_win.py GAME` from a checkout, to try the trainer without the hub (start the game
yourself, then this): it runs until Ctrl+C, with the trainer on for that run whatever is saved.
"""
import atexit
import sys
import threading
import time
import traceback
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False) and (_HERE.parent / "movekit").is_dir() and str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))  # the kit root (repo or core copy); the core exe bundles movekit
from movekit import games, logfile, paths  # after the path above
from movekit.hub import local_import

LOG = paths.config_dir("strafe-trainer") / "run.log"
LOG_MAX = 1_000_000
store = local_import(__file__, "store")
gamecfg = local_import(__file__, "gamecfg")


def old_sourceyaw_trainer(kit):
    """True while a Source Yaw from before Phase 13 (1.10.x, e.g. after a roll back) is installed:
    it runs its own trainer, and two would play every cue twice."""
    return (Path(kit) / "sourceyaw" / "trainer.py").is_file()


def start(argv, kit=None, force=False):
    """Starts the trainer for the game in argv; returns the threads started (none when it isn't
    CS:S or Momentum, or an old Source Yaw runs its own). A trainer that is off starts too: it
    waits in trainer.run until it is switched on in the hub."""
    logfile.tee(LOG, LOG_MAX)
    game = games.from_command(argv)
    if game is None:
        return []
    if kit is not None and old_sourceyaw_trainer(kit):
        print("strafe-trainer: Source Yaw still has its own trainer (1.10 or older); "
              "update Source Yaw to use this one", flush=True)
        return []
    gamecfg.apply(game, store.config(game))
    trainer = local_import(__file__, "trainer")
    if force:
        trainer.settings = lambda g: {**store.config(g), "enabled": True}
    stop = threading.Event()

    def body():
        try:
            trainer.run(game, trainer.platform(), stop)
        except Exception:  # noqa: BLE001 - logged, the game keeps running
            print(f"strafe-trainer: stopped by an error:\n{traceback.format_exc()}", flush=True)

    thread = threading.Thread(target=body, name="strafe-trainer", daemon=True)
    thread.start()

    def finish():
        # at the exe's exit, after the game closed: Raw Input unregistered, the tone device closed
        stop.set()
        thread.join(2)
        print("strafe-trainer: stopped" + (" (still running)" if thread.is_alive() else ""), flush=True)
    atexit.register(finish)
    print(f"strafe-trainer: {games.GAMES[game].name} started", flush=True)
    return [thread]


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in store.GAMES:
        sys.exit(f"usage: launch_win.py {'|'.join(store.GAMES)}")
    game_dir = games.find(sys.argv[1])
    if not game_dir:
        sys.exit(f"{games.GAMES[sys.argv[1]].name} not found in your Steam libraries")
    # as if Steam started the game: its folder's exe, plus -game
    threads = start([str(game_dir.parent / "game.exe"), "-game", game_dir.name], force=True)
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
