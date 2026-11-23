#!/usr/bin/env python3
"""Checks netcon.py: the launch's arguments and saved state, Apply's send against a fake net
console (the protocol as Momentum's engine speaks it: PASS, then commands, output echoed back),
and launch-hook.sh adding the arguments to movekit-run's GAME_ARGS.

Everything runs in a temp folder. Linux only (the hook part needs bash).
"""
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import netcon  # after the path


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")
    print(f"ok   {what}")


class FakeNetcon:
    """A net console on 127.0.0.1: `password` as the engine checks it; `silent` never answers.
    `commands` gets every command run."""

    def __init__(self, password, silent=False):
        self.password, self.silent, self.commands, self.connections = password, silent, [], 0
        self.times = []  # time.monotonic() of each command
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen()
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            self.connections += 1
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn):
        authed, buf = False, b""
        with conn:
            while True:
                try:
                    chunk = conn.recv(4096)
                except OSError:
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.decode().strip()
                    if self.silent:
                        continue
                    if line.startswith("PASS "):
                        authed = line[5:] == self.password
                        continue
                    if not authed:
                        conn.sendall(b"This server is password protected for console access. "
                                     b"Must send PASS command\r\n")
                        continue
                    self.commands.append(line)
                    self.times.append(time.monotonic())
                    if line.startswith("echo "):
                        conn.sendall(f"[vstdlib] {line[5:]} \r\n".encode())

    def close(self):
        self.server.shutdown(socket.SHUT_RDWR)  # wakes accept(), which close() alone leaves listening
        self.server.close()


def state(config, game="momentum"):
    return json.loads(netcon.state_file(game, config).read_text())


def check_launch_args(config):
    expect(netcon.launch_args("css", ["hl2.sh", "-game", "cstrike"], 1, config), [], "CS:S: no net console")
    expect(netcon.state_file("css", config).exists(), False, "CS:S: no state file")
    expect(netcon.launch_args("momentum", ["momentum.sh", "-NetConPort", "27999"], 1, config), [],
           "own -netconport in the launch options: left alone")
    expect(netcon.state_file("momentum", config).exists(), False, "own -netconport: no state file")
    args = netcon.launch_args("momentum", ["momentum.sh", "-steam"], 4242, config)
    saved = state(config)
    expect(args, ["-netconport", str(saved["port"]), "-netconpassword", saved["password"]], "Momentum: the arguments")
    expect(saved["pid"], 4242, "the launch's pid saved")
    expect(len(saved["password"]), 32, "a 128-bit password")
    expect(stat.S_IMODE(netcon.state_file("momentum", config).stat().st_mode), 0o600, "state file owner-only")
    again = netcon.launch_args("momentum", ["momentum.sh"], 4242, config)
    expect(again[3] != args[3], True, "a new password each launch")


def save(config, port, password, pid):
    netcon.state_file("momentum", config).write_text(json.dumps({"port": port, "password": password, "pid": pid}))


def check_send(config):
    me = os.getpid()
    fake = FakeNetcon("right")
    save(config, fake.port, "right", me)
    expect(netcon.send("momentum", "exec yaws", config), True, "send: the game ran it")
    expect(fake.commands[0], "exec yaws", "send: exec yaws first")
    expect(fake.commands[1].startswith("echo SY_NETCON_"), True, "send: then the done marker")
    expect(netcon.send("css", "exec yaws", config), False, "send: never for CS:S")

    save(config, fake.port, "wrong", me)
    fake.commands.clear()
    expect(netcon.send("momentum", "exec yaws", config), False, "send: wrong password")
    expect(fake.commands, [], "send: wrong password ran nothing")

    dead = subprocess.Popen(["true"])
    dead.wait()
    save(config, fake.port, "right", dead.pid)
    before = fake.connections
    expect(netcon.send("momentum", "exec yaws", config), False, "send: the launch has exited")
    time.sleep(0.1)
    expect(fake.connections, before, "send: no connection for a dead launch (the password stays home)")
    fake.close()

    save(config, fake.port, "right", me)
    expect(netcon.send("momentum", "exec yaws", config), False, "send: nothing listening")

    silent = FakeNetcon("right", silent=True)
    save(config, silent.port, "right", me)
    start = time.monotonic()
    expect(netcon.send("momentum", "exec yaws", config, timeout=0.3), False, "send: a game that doesn't answer")
    expect(time.monotonic() - start < 1, True, "send: gives up quickly")
    silent.close()

    netcon.state_file("momentum", config).write_text("{")
    expect(netcon.send("momentum", "exec yaws", config), False, "send: broken state file")
    netcon.state_file("momentum", config).unlink()
    expect(netcon.send("momentum", "exec yaws", config), False, "send: no state file (game not started by the kit)")


HOOK_RUN = """
run_hook() {{ local HOOK_DIR; HOOK_DIR="{here}"; . "$1"; }}
HELPERS=""
{declare}
run_hook "{here}/launch-hook.sh"
declare -p GAME_ARGS 2>/dev/null || echo "no GAME_ARGS"
"""


def check_hook(tmp):
    env = dict(os.environ, HOME=str(tmp / "home"), XDG_CONFIG_HOME=str(tmp / "home/.config"),
               XDG_DATA_HOME=str(tmp / "home/.local/share"), GAME="momentum")
    config = tmp / "home/.config/sourceyaw"

    def run(declare):
        script = HOOK_RUN.format(here=HERE, declare=declare)
        got = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=60, check=False)
        return got.stdout.strip().splitlines()[-1] if got.stdout.strip() else got.stderr

    out = run('GAME_CMD=(momentum.sh -steam); GAME_ARGS=()')
    saved = state(config)
    expect(out, f'declare -a GAME_ARGS=([0]="-netconport" [1]="{saved["port"]}" [2]="-netconpassword" '
                f'[3]="{saved["password"]}")', "hook: the arguments in GAME_ARGS")
    expect(saved["pid"] > 0, True, "hook: movekit-run's pid saved")
    netcon.state_file("momentum", config).unlink()
    expect(run('GAME_CMD=(momentum.sh -netconport 27999); GAME_ARGS=()'), "declare -a GAME_ARGS=()",
           "hook: own -netconport, nothing added")
    expect(run(""), "no GAME_ARGS", "hook: an older core, nothing added")
    expect(netcon.state_file("momentum", config).exists(), False, "hook: older core, no state file")
    env["GAME"] = "css"
    expect(run('GAME_CMD=(hl2.sh); GAME_ARGS=()'), "declare -a GAME_ARGS=()", "hook: CS:S, nothing added")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        config = tmp / "config"
        config.mkdir()
        check_launch_args(config)
        check_send(config)
        if sys.platform != "win32":
            check_hook(tmp)
    print("all netcon checks passed")


if __name__ == "__main__":
    main()
