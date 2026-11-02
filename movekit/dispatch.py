"""The core's launch option (3.7b in PLAN.md): `movement-kit.exe %command%` on Windows.

run() gives every installed module its launch hook (movekit/modules.py), then starts the game with
the command Steam gave and returns its exit code. A module whose hook is missing, broken or raises
is skipped and logged: the game starts whatever the modules do, also with none installed. On Linux
movekit-run (movekit/launch.py) is the launch option and passes through the same way.

Standard library only.
"""
import os
import subprocess
import sys


def game_env():
    """The environment for the game. A PyInstaller exe changes the library search path for its own
    unpacked libraries, which the game must not load; restored as PyInstaller's docs describe.
    None means "this process's environment as it is"."""
    if not getattr(sys, "frozen", False):
        return None
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.kernel32.SetDllDirectoryW(None)
        return None
    env = dict(os.environ)
    for key in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        orig = env.pop(key + "_ORIG", None)
        if orig is not None:
            env[key] = orig
        else:
            env.pop(key, None)
    return env


def hooks(manager, argv, log):
    """Each installed module's launch hook, in key order; failures are logged, never raised."""
    try:
        keys = sorted(manager.installed())
    except Exception as e:  # noqa: BLE001 - a broken kit folder must not keep the game from starting
        log(f"movement kit: couldn't list the modules ({e}); starting the game without them")
        return
    for key in keys:
        try:
            manager.run_hook(key, "launch", list(argv))
        except Exception as e:  # noqa: BLE001 - one module's failure mustn't stop the game or the rest
            log(f"movement kit: {key}'s launch step failed: {type(e).__name__}: {e}")


def run(manager, argv, log=print):
    """Launch hooks, then the game (argv); returns the game's exit code."""
    if manager is not None:
        hooks(manager, argv, log)
    try:
        return subprocess.call(list(argv), env=game_env())
    except OSError as e:
        log(f"movement kit: couldn't start the game {argv[:1]}: {e}")
        return 1
