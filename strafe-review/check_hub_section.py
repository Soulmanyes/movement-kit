#!/usr/bin/env python3
"""Checks the Strafe Review hub section without a window, against a real viewer/server.py on a free port.

Usage: python strafe-review/check_hub_section.py   (exits 1 on the first failure)

Covers: discovery and the bridge finding the section; loading it leaving no bare steam, collector,
install, server or updater module behind; status with nothing on the port; open_review refusing
then; status against a running server; the update calls gone (the Modules page has them, 3.7b);
start() not starting a second copy; open_review opening the server's URL (webbrowser patched);
stop() ending the server (a POST, so the server's local_request accepts the section's POSTs); the server serving the
shared /web/tokens.css that style.css imports; and start() bringing a stopped server back (the
detached fallback, systemd-run hidden, so no user unit is made).
Everything runs in a temp folder: XDG_DATA_HOME, LOCALAPPDATA and MOMENTUM_DIR point there, and the
update check goes to a closed port instead of GitHub.
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen

KIT = Path(__file__).resolve().parent.parent
BARE = ("steam", "collector", "install", "server", "updater")


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait(call, want, what, seconds=15):
    for _ in range(seconds * 4):
        if call() == want:
            return
        time.sleep(0.25)
    fail(f"{what}: not {want!r} after {seconds} s")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        port = free_port()
        os.environ["XDG_DATA_HOME"] = os.environ["LOCALAPPDATA"] = str(tmp / "data")
        os.environ["MOMENTUM_DIR"] = str(tmp / "nogame")
        os.environ["STRAFE_REVIEW_PORT"] = str(port)
        os.environ["STRAFE_REVIEW_UPDATE_API"] = f"http://127.0.0.1:{free_port()}/releases"
        sys.path.insert(0, str(KIT))
        from movekit import hub

        sections, problems = hub.discover(KIT)
        expect([p for p in problems if p[0] == "strafe-review"], [], "strafe-review problems")
        if "strafe-review" not in [s.key for s in sections]:
            fail("discovery didn't find the strafe-review section")
        bad = [m for m in BARE if m in sys.modules]
        expect(bad, [], "bare modules after loading the sections")
        bridge = hub.Bridge(sections, problems)

        def call(name, **args):
            return bridge.call("strafe-review", name, args)

        def serving():
            return call("status")["result"]["serving"]

        got = call("status")
        expect(got, {"ok": True, "result": {"serving": False, "url": f"http://127.0.0.1:{port}/"}}, "status, nothing on the port")
        expect(call("open_review")["ok"], False, "open_review with nothing running")

        cmd = [sys.executable, str(KIT / "strafe-review" / "viewer" / "server.py"), "--port", str(port),
               "--no-collect", "--no-browser", "--store", str(tmp / "store")]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        spawned = []
        try:
            wait(serving, True, "server started by the check")
            res = call("status")["result"]
            expect(res["status"]["collecting"], False, "status from the server: collecting")
            expect(res["status"]["saved"], 0, "status from the server: saved")
            expect("update" in res, False, "status without the update info")
            for gone in ("check_updates", "set_auto", "install_update"):
                expect(call(gone)["ok"], False, f"{gone} is no longer a section call")
            expect(call("start")["result"], {"started": False}, "start while serving")

            opened = []
            webbrowser.open = opened.append
            expect(call("open_review")["result"], {"opened": f"http://127.0.0.1:{port}/"}, "open_review")
            expect(opened, [f"http://127.0.0.1:{port}/"], "the URL handed to the browser")

            with urlopen(f"http://127.0.0.1:{port}/web/tokens.css", timeout=2) as r:
                css = r.read().decode()
            expect(css, (KIT / "movekit" / "web" / "tokens.css").read_text(), "/web/tokens.css")
            with urlopen(f"http://127.0.0.1:{port}/static/style.css", timeout=2) as r:
                if '@import url("/web/tokens.css")' not in r.read().decode():
                    fail("style.css doesn't import /web/tokens.css")

            expect(call("stop")["ok"], True, "stop")
            proc.wait(timeout=10)
            wait(serving, False, "server after stop")

            # start(): the detached fallback (no systemd-run), so no user unit is created
            which = shutil.which
            shutil.which = lambda name, *a, **k: None if name == "systemd-run" else which(name, *a, **k)
            real_popen = subprocess.Popen

            def popen(args, **kw):
                p = real_popen([*args, "--no-collect", "--store", str(tmp / "store")], **kw)
                spawned.append(p)
                return p

            subprocess.Popen = popen
            try:
                expect(call("start")["result"], {"started": True}, "start while stopped")
            finally:
                subprocess.Popen = real_popen
                shutil.which = which
            expect(len(spawned), 1, "copies start() spawned")
            if "--port" not in spawned[0].args or str(port) not in spawned[0].args:
                fail(f"start() command lacks the port: {spawned[0].args}")
            wait(serving, True, "server started by start()")
            call("stop")
            spawned[0].wait(timeout=10)
        finally:
            for p in [proc, *spawned]:
                if p.poll() is None:
                    p.kill()
                    p.wait()
    print("check_hub_section: all passed")


if __name__ == "__main__":
    main()
