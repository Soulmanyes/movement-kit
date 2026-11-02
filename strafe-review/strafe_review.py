#!/usr/bin/env python3
"""Strafe Review in one program, the entry point of the Windows exe.

    strafe-review.exe                 install or update the recorder, then collect and serve the
                                      page and open it in the browser (keep the window open while
                                      playing; closing it stops collecting)
    strafe-review.exe %command%       as a Steam launch option: install, start the server in the
                                      background, open the page, run the game
    strafe-review.exe --collect       install, then collect and serve without opening the page (the
                                      hub's "Open review" starts the hub exe this way, 3.7 in PLAN.md)

Everything it prints also goes to strafe-review.log in %LOCALAPPDATA%\\strafe-review (the background
copy's only output). If a copy is already serving, a double-click only opens the page. The server
reads yaw.log from the start and skips attempts already saved, so attempts played while it wasn't
running are picked up on the next start. On Linux, movekit-run (collector/launch-hook.sh) stays the launch option.
"""
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _bundled():
    """This file sits inside a one-file exe's unpacked bundle (Strafe Review's own exe until the bridge
    release, 3.7b in PLAN.md), whose layout is at sys._MEIPASS. A module loaded from disk by the kit's
    core exe is frozen too, but its files are its own folder."""
    bundle = getattr(sys, "_MEIPASS", None)
    return bool(bundle) and Path(__file__).resolve().is_relative_to(Path(bundle).resolve())


ROOT = Path(sys._MEIPASS) if _bundled() else Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / "collector"), str(ROOT / "viewer")]  # finds the imports below
import collector
import install
import server
import steam
import updater

from movekit import logfile
from movekit.dispatch import game_env  # one copy, shared with the kit's core exe

PORT = int(os.environ.get("STRAFE_REVIEW_PORT", "8765"))  # the variable is for tests
URL = f"http://127.0.0.1:{PORT}/"
SERVE = "--serve"  # internal: the background copy the launch option starts
COLLECT = "--collect"  # install, then serve with no page opened (the hub starts this)
RESTARTED = "--restarted"  # internal: a double-click copy started again after an update (no new tab)
LOG = steam.data_dir() / "strafe-review.log"
LOG_MAX = 1 << 20  # bytes; a longer log is started over
START_WAIT = 10  # seconds the launch option waits for the server it started before opening the page


def log_to_file():
    """Send this copy's output to strafe-review.log too."""
    logfile.tee(LOG, LOG_MAX)


def serving():
    """True if something answers on the port (this program, or a server started by hand)."""
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
            return True
    except OSError:
        return False


def try_install():
    """Install or update the recorder and the autoexec block; a failure is shown, not fatal."""
    if not collector.GAME:
        print(f"Strafe Review: {collector.NOT_FOUND}; the recorder isn't installed", file=sys.stderr)
        return
    try:
        install.install(collector.GAME)
    except OSError as e:
        print(f"Strafe Review: install failed: {e}", file=sys.stderr)


def me():
    """The command that starts this program: the old one-file exe itself (after an update, the new exe
    at the same path); in the kit's core exe, this file through its --run-script; else python."""
    if _bundled():
        return [sys.executable]
    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-script", str(Path(__file__).resolve())]
    return [sys.executable, str(Path(__file__).resolve())]


def fresh_env():
    # a fresh PyInstaller instance with its own unpack folder; without this it would share this one's,
    # which is deleted when this copy exits
    return {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}


def start_console():
    """After an update: the double-click copy again, in a new console window, without a new tab."""
    if sys.platform == "win32":
        subprocess.Popen([*me(), RESTARTED], env=fresh_env(), creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen([*me(), RESTARTED], env=fresh_env(), start_new_session=True)


def start_background(*extra):
    """Start a copy of this program that only serves, detached so it outlives the game."""
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "env": fresh_env()}
    if sys.platform != "win32":
        kw["start_new_session"] = True
        subprocess.Popen([*me(), SERVE, *extra], **kw)
        return
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    try:
        # out of Steam's job object, if it has one, so Steam doesn't count the server as part of the game
        subprocess.Popen([*me(), SERVE, *extra], creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kw)
    except OSError:  # the job doesn't allow breaking away
        subprocess.Popen([*me(), SERVE, *extra], creationflags=flags, **kw)


def open_when_serving(wait):
    for _ in range(wait * 2 or 1):
        if serving():
            webbrowser.open(URL)
            return
        time.sleep(0.5)


def prepare_launch():
    """What the launch option does before the game starts: install, start the server in the
    background unless one runs, and open the page once it answers (a thread, returned). The kit's
    core runs the game itself and calls this through module_hooks.launch."""
    try_install()
    started = not serving()
    if started:
        start_background()
    # the page opens while the game starts, so it updates live during play; a server started just
    # now may need a moment before it answers
    opener = threading.Thread(target=open_when_serving, args=(START_WAIT if started else 0,))
    opener.start()
    return opener


def launch(game_cmd):
    opener = prepare_launch()
    status = subprocess.call(game_cmd, env=game_env())
    opener.join()
    return status


def main():
    args = sys.argv[1:]
    log_to_file()
    updater.clean_old()
    if args[:1] == [SERVE]:
        # no install here, even after an update: the game may be starting and mounting custom/; the
        # launch wrapper (the new exe after an update) installs at every game start
        server.RESTART = lambda: start_background(RESTARTED)
        return server.main(["--port", str(PORT), "--no-browser"])
    if args == [COLLECT]:
        # installing here is safe: the hub starts this by hand, as a double-click would
        try_install()
        server.RESTART = lambda: start_background(RESTARTED)
        return server.main(["--port", str(PORT), "--no-browser"])
    if args == [RESTARTED]:
        try_install()
        server.RESTART = start_console
        return server.main(["--port", str(PORT), "--no-browser"])
    if args:
        return launch(args)
    if serving():
        webbrowser.open(URL)
        return None
    try_install()
    server.RESTART = start_console
    return server.main(["--port", str(PORT)])


if __name__ == "__main__":
    sys.exit(main())
