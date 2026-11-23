#!/usr/bin/env python3
"""Momentum Mod's net console: lets Apply in the hub run `exec yaws` in the open game.

The game's engine listens for console commands over TCP when it starts with
`-netconport N -netconpassword PW`: a client sends `PASS PW`, then commands, one per line, and
gets the console output back. The launch adds those two arguments (movekit-run's GAME_ARGS on
Linux, the launch hook's return value on Windows): a free port and a new random password each
launch, kept in netcon-<game>.json in the settings folder (owner-only), with the pid of the launch
process, which lives as long as the game. Apply reads that file and sends the command only while
that process is alive, so a left-over file never sends the password to a port another program
took since.

The engine listens on every address, not only this PC's: the random password is what keeps the
console to this PC. CS:S's engine has no net console, so only Momentum gets the arguments; a game
started with its own -netconport (set in Steam's launch options) is left alone and Apply falls
back to the next press of the cycle key (yawcore.LOADED_ALIAS).

  netcon.py --launch GAME PID [GAME COMMAND LINE...]   prints the arguments to add, one per line
"""
import json
import os
import secrets
import socket
import sys

GAMES = ("momentum",)  # games whose engine has the net console
PORT_ARG, PASSWORD_ARG = "-netconport", "-netconpassword"
REJECTED = b"password protected"  # the engine's reply to commands without the right PASS
TIMEOUT = 1.0  # seconds Apply waits for the game, in all


def state_file(game, config=None):
    """The launch's port, password and pid for `game`, in `config` (yawcore.CONFIG_DIR by default:
    the hub passes its own copy's, as it loads yawcore under another name)."""
    if config is None:
        import yawcore

        config = yawcore.CONFIG_DIR
    return config / f"netcon-{game}.json"


def free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def launch_args(game, argv, pid, config=None):
    """The arguments to add to the game's command line `argv`, saving the port and password for
    Apply: [] for a game without the net console, or one whose command line sets it already."""
    if game not in GAMES or any(a.lower() == PORT_ARG for a in argv):
        return []
    port, password = free_port(), secrets.token_hex(16)
    path = state_file(game, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"port": port, "password": password, "pid": pid}, f)
    tmp.replace(path)
    return [PORT_ARG, str(port), PASSWORD_ARG, password]


def alive(pid):
    """Whether process `pid` still runs."""
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        try:
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _state(game, config):
    """(port, password) of the open game's net console, or None: no game of the kit's launch open."""
    if game not in GAMES:
        return None
    try:
        state = json.loads(state_file(game, config).read_text())
        port, password, pid = int(state["port"]), str(state["password"]), int(state["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (port, password) if alive(pid) else None


def is_open(game, config=None):
    """Whether `game` runs, started by the kit with the net console (send can reach it)."""
    return _state(game, config) is not None


def send(game, command, config=None, timeout=TIMEOUT):
    """Runs `command` in the open game through the net console; True once the game ran it. False
    when the game isn't open, wasn't started with the launch's arguments, or doesn't answer."""
    state = _state(game, config)
    if state is None:
        return False
    port, password = state
    done = f"SY_NETCON_{secrets.token_hex(4)}".encode()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(f"PASS {password}\n{command}\necho {done.decode()}\n".encode())
            reply = b""
            while done not in reply and REJECTED not in reply:
                chunk = s.recv(4096)
                if not chunk:
                    break
                reply += chunk
    except OSError:  # refused, timed out, reset
        return False
    return done in reply and REJECTED not in reply


def main():
    if len(sys.argv) < 4 or sys.argv[1] != "--launch" or not sys.argv[3].isdigit():
        sys.exit("usage: netcon.py --launch GAME PID [GAME COMMAND LINE...]")
    for arg in launch_args(sys.argv[2], sys.argv[4:], int(sys.argv[3])):
        print(arg)


if __name__ == "__main__":
    main()
