"""The Strafe Review section (movekit/hub.py): is it running, its setup and updates, and "Open review".

The review page stays in the browser. This section only talks to the running server over HTTP
(127.0.0.1, port 8765 or STRAFE_REVIEW_PORT) and never imports Strafe Review's modules: they put
bare module names (steam, collector, updater) on sys.path. Requests come from Python, not from the
page, because the server takes POSTs only from its own origin (server.py local_request).

Every call returns quickly (the hub runs a section's calls one at a time): start() only spawns the
server, and the page polls status() until it answers.
"""
import json
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
SERVER = HERE / "viewer" / "server.py"
UNIT = "strafe-review"  # the systemd user unit collector/launch-hook.sh starts on Linux
PASS_ENV = ("MOMENTUM_DIR", "XDG_DATA_HOME", "WAYLAND_DISPLAY", "DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE")


def port():
    """Read on each call, so a check can point the section at a test server."""
    return int(os.environ.get("STRAFE_REVIEW_PORT", "8765"))


def url():
    return f"http://127.0.0.1:{port()}/"


def _request(path, body=None, timeout=2):
    """GET (body None) or JSON POST to the server. Raises OSError when nothing answers, and
    RuntimeError with the server's text on an HTTP error."""
    data = None if body is None else json.dumps(body).encode()
    req = Request(url() + path.lstrip("/"), data=data, method="GET" if body is None else "POST")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=timeout) as res:
            return json.loads(res.read())
    except HTTPError as e:
        text = e.read().decode("utf-8", "replace").strip()
        raise RuntimeError(text or f"HTTP {e.code}") from None
    except URLError as e:
        raise OSError(str(e.reason)) from None


def status():
    """{"serving": false} when nothing answers on the port; else the server's /api/status (setup and
    collector). Updates are the Modules page's (movekit/modules.py, 3.7b in PLAN.md)."""
    try:
        st = _request("api/status")
    except (OSError, ValueError):
        return {"serving": False, "url": url()}
    return {"serving": True, "url": url(), "status": st}


def _command():
    """The command that runs the server in the background."""
    if getattr(sys, "frozen", False):  # the core exe (3.7b): install, then serve, through --run-script
        return [sys.executable, "--run-script", str(HERE / "strafe_review.py"), "--collect"]
    return [sys.executable, str(SERVER), "--port", str(port()), "--no-browser"]


def _spawn(cmd):
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        kw["env"] = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    else:
        kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)


def _start_unit(cmd):
    """Linux: the same systemd user unit the launch hook starts, so it outlives the hub and
    `systemctl --user stop strafe-review` stops it. False when systemd-run isn't there or fails."""
    if not shutil.which("systemd-run"):
        return False
    env = [f"--setenv={k}={os.environ[k]}" for k in PASS_ENV if os.environ.get(k)]
    try:
        done = subprocess.run(["systemd-run", "--user", "--quiet", "--collect", f"--unit={UNIT}", *env, *cmd],
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def start():
    """Start the server unless something answers on the port. Returns at once: started is False when
    it was already running; the page polls status() until it answers."""
    if status()["serving"]:
        return {"started": False}
    cmd = _command()
    if not (sys.platform.startswith("linux") and not getattr(sys, "frozen", False) and _start_unit(cmd)):
        _spawn(cmd)
    return {"started": True}


def open_review():
    """Open the review page in the default browser (not in the hub window). Only while it serves."""
    if not status()["serving"]:
        raise RuntimeError("Strafe Review isn't running")
    webbrowser.open(url())
    return {"opened": url()}


def stop():
    """Stop the server, like the review page's Stop button."""
    return _request("api/stop", {})


SECTION = {
    "key": "strafe-review",
    "title": "Strafe Review",
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {"status": status, "start": start, "open_review": open_review, "stop": stop},
    "order": 15,
}
