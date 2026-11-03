#!/usr/bin/env python3
"""Smoke test of the built core exe (3.7b in PLAN.md) against a fake GitHub and a fake Momentum
folder, no game or Steam needed.

Usage: python hub/smoke_test.py dist/movement-kit(.exe)
       python hub/smoke_test.py --repo        (the core from the repo: python hub/movement_kit.py)

Run by .github/workflows/hub-windows.yml and strafe-review-windows.yml on the Windows build; it runs
on Linux too. The modules come from this checkout as their release zips (.github/scripts/module_zip.py),
so they run from the download folder, never from the exe. Checks:
0. Modules: a fresh core lists none; Strafe Review and Gain Converter install from the fake GitHub
   (Strafe Review's install hook puts the recorder into the fake game); --check-sections finds their
   sections and the HUD's, and the HUD section finds the recorder and writes its setting into it.
1. Open review (the module's --collect, through the core's --run-script): pages served, the recorder,
   the CRLF autoexec block and the kit's timer.xml (custom/0-movekit, on panoDev's) in place, /api/status sees the setup, and an attempt written
   into yaw.log the way the game writes it is collected, listed and announced on the movekit session.
2. A second server (the old exe's --serve, sent to the module) refuses the busy port.
3. Launch option: the module's launch step starts the server and opens the page, the "game" runs and
   its exit code comes back, the background server's output is in strafe-review.log.
4. The page's Stop button ends the server and frees the session port.
5. Uninstall both modules: the recorder and the autoexec block are gone; the launch option still runs
   the game with no modules.
6. The bridge: a copy named strafe-review(.exe) with Strafe Review's old data folder installs the
   module on its first launch, keeping the old auto switch.
7. (Built exe only) the core update: hub-v99.0.0's zip is swapped in under the copy's own name, and
   the old exe is cleaned up on the next start.
The browser is a stand-in that writes the URL to a file.
"""
import http.server
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PORT = 8790
URL = f"http://127.0.0.1:{PORT}/"
SESSION_PORT = 8791  # not the live 8766
SESSION = f"http://127.0.0.1:{SESSION_PORT}"
HERE = Path(__file__).resolve().parent
KIT_REPO = HERE.parent
WIN = sys.platform == "win32"
REPO = sys.argv[1:2] == ["--repo"]
SECTIONS = ["strafe-review", "gain-converter", "hud"]  # sidebar order with both modules installed
SMOKE_ID = "smoketest1"
FAKE_TIMER = """<root>
\t<scripts>
\t\t<include type="module" src="file://{{scripts}}/hud/timer.ts" />
\t</scripts>
\t<MomHudTimer id="mod-{mod}" />
</root>
"""
sys.path.insert(0, str(KIT_REPO / ".github" / "scripts"))
import module_zip  # from the repo, after the path above


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def get(path):
    try:
        with urllib.request.urlopen(URL.rstrip("/") + path, timeout=2) as r:
            return r.status, r.read()
    except OSError:
        return None, b""


def post(path, body=None):
    req = urllib.request.Request(URL.rstrip("/") + path, data=json.dumps(body or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def session_status():
    try:
        with urllib.request.urlopen(SESSION + "/status", timeout=2) as r:
            return json.loads(r.read())
    except OSError:
        return None


def session_events(kind, timeout=10):
    """The data of the first kept session event of type `kind` ([] if none comes within `timeout` s)."""
    end = time.time() + timeout
    try:
        with urllib.request.urlopen(SESSION + "/events?after=0", timeout=2) as r:
            event = None
            while time.time() < end:
                line = r.readline().decode().rstrip("\r\n")
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: ") and event == kind:
                    return [json.loads(line[6:])["data"]]
    except OSError:  # the read timed out: nothing more kept
        pass
    return []


def wait_serving(timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if get("/")[0] == 200:
            return
        time.sleep(0.5)
    fail(f"nothing serves {URL} after {timeout} s")


def wait_down(timeout=15):
    end = time.time() + timeout
    while time.time() < end and get("/")[0] is not None:
        time.sleep(0.5)
    return get("/")[0] is None


def opened(tmp):
    f = tmp / "opened.txt"
    return f.read_text().split() if f.exists() else []


def write_attempt(path):
    """Append one attempt as the recorder writes it: the game keeps the log open and writes CRLF lines,
    a chunk at a time."""
    data = json.dumps({"format": 1, "id": SMOKE_ID, "map": "bhop_smoke", "started": 1, "interval": 0.01,
                       "style": 0, "track": {"type": 0, "number": 0}, "label": "own", "player": None,
                       "cols": ["tick", "vx", "vy", "vz"], "rows": "0,0,0,0;1,10,0,0", "events": [],
                       "reason": "reset", "runTime": 0.01, "gaps": 0, "ended": 2})
    n = 3
    size = -(-len(data) // n)
    parts = [data[i * size:(i + 1) * size] for i in range(n)]
    with open(path, "ab", buffering=0) as f:
        f.write(b"[panorama] unrelated line\r\n")
        for i, part in enumerate(parts, 1):
            f.write(f"[panorama] SRREC {SMOKE_ID} {i}/{n} {part}\r\n".encode())
            time.sleep(0.6)
        f.write(f"[panorama] SRREC {SMOKE_ID} end n={n} chars={len(data)}\r\n".encode())
        time.sleep(3)  # still open while the collector reads, like the game


class GitHub:
    """A local stand-in for GitHub's release list and its assets."""

    def __init__(self):
        self.releases, self.files = [], {}
        gh = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps(gh.releases).encode() if self.path.startswith("/releases") \
                    else gh.files.get(self.path)
                if body is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def release(self, tag, files):
        assets = []
        for name, path in files:
            self.files[f"/f/{tag}/{name}"] = Path(path).read_bytes()
            assets.append({"name": name, "browser_download_url": f"{self.base}/f/{tag}/{name}"})
        self.releases.insert(0, {"tag_name": tag, "html_url": "", "body": f"notes {tag}", "assets": assets})


def version_of(tool):
    import re

    m = json.loads((KIT_REPO / tool / "module.json").read_text())
    return re.search(r'^VERSION = "([^"]+)"', (KIT_REPO / tool / m["version_from"]).read_text(), re.MULTILINE).group(1)


class Core:
    """Runs the core (the exe, or the repo's movement_kit.py) with the test's environment."""

    def __init__(self, cmd, env, tmp):
        self.cmd, self.env, self.tmp = cmd, env, tmp

    def run(self, *args, timeout=120, env=None, cmd=None):
        return subprocess.run([*(cmd or self.cmd), *map(str, args)], env=env or self.env, timeout=timeout,
                              capture_output=True, text=True, check=False)

    def modules(self, *args, env=None, cmd=None):
        out = self.tmp / "reply.json"
        out.unlink(missing_ok=True)
        r = self.run("--modules", out, *args, env=env, cmd=cmd)
        reply = json.loads(out.read_text()) if out.is_file() else None
        if r.returncode != 0 or not reply or not reply["ok"]:
            fail(f"--modules {' '.join(args)}: exit {r.returncode}, {reply}, stderr {r.stderr[-400:]!r}")
        return reply

    def stop_all(self, kit):
        """End every server the test started: the exe's copies, and module scripts run from the kit."""
        if WIN:
            if not REPO:
                subprocess.call(["taskkill", "/F", "/T", "/IM", Path(self.cmd[0]).name],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.call(["powershell", "-NoProfile", "-Command",
                             (f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{kit}*' }}"
                              " | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.call(["pkill", "-f", str(kit)])
            if not REPO:
                subprocess.call(["pkill", "-f", f"^{self.cmd[0]}"])
        time.sleep(1)


def main():
    if not sys.argv[1:]:
        sys.exit(__doc__.split("\n\n")[1])
    tmp = Path(tempfile.mkdtemp(prefix="core-smoke-"))
    cmd = [sys.executable, str(HERE / "movement_kit.py")] if REPO else [str(Path(sys.argv[1]).resolve())]
    game = tmp / "game"
    (game / "cfg").mkdir(parents=True)
    (game / "panorama" / "layout" / "hud").mkdir(parents=True)
    (game / "panorama" / "layout" / "hud" / "timer.xml").write_text(FAKE_TIMER.format(mod="game"))
    # another HUD mod with its own timer.xml, mounted before ours (like panoDev): ours must be based on it
    other = game / "custom" / "panoDev" / "panorama" / "layout" / "hud"
    other.mkdir(parents=True)
    (other / "timer.xml").write_text(FAKE_TIMER.format(mod="panoDev"))
    (game / "cfg" / "autoexec.cfg").write_bytes(b"exec something\r\n")  # CRLF, as Windows editors write it
    (game / "yaw.log").write_text("")
    browser = tmp / "browser.py"
    browser.write_text(f"import sys\nopen({str(tmp / 'opened.txt')!r}, 'a').write(sys.argv[1] + '\\n')\n")

    gh = GitHub()
    zips = tmp / "zips"
    for tool in ("strafe-review", "gain-converter"):
        module_zip.build(tool, zips)
        gh.release(f"{tool}-v{version_of(tool)}", [(f"{tool}-module.zip", zips / f"{tool}-module.zip"),
                                                   (f"{tool}-module.json", zips / f"{tool}-module.json")])
    data = tmp / "data"
    kit = data / "movekit" / "kit"
    env = {
        **os.environ,
        "MOMENTUM_DIR": str(game),
        "STRAFE_REVIEW_PORT": str(PORT),
        "MOVEKIT_SESSION_PORT": str(SESSION_PORT),
        "MOVEKIT_MODULES_API": gh.base + "/releases",
        "LOCALAPPDATA": str(data),
        "XDG_DATA_HOME": str(data),
        "XDG_CONFIG_HOME": str(tmp / "config"),
        "HOME": str(tmp / "home"),  # install.py links the launcher under it on Linux
        # forward slashes: webbrowser splits BROWSER like a POSIX shell, which eats backslashes
        "BROWSER": f'"{Path(sys.executable).as_posix()}" "{browser.as_posix()}" %s',
    }
    if REPO:
        env["MOVEKIT_KIT_ROOT"] = str(kit)  # from the repo the kit would be the checkout
    core = Core(cmd, env, tmp)
    ours = game / "custom" / "0-strafe-review" / "panorama"
    kit_timer = game / "custom" / "0-movekit" / "panorama" / "layout" / "hud" / "timer.xml"
    try:
        print("0. modules")
        reply = core.modules("cards")
        if [c["key"] for c in reply["cards"] if c["installed"]] != ["core"]:
            fail(f"a fresh core lists installed modules: {reply['cards']}")
        core.modules("check")
        core.modules("install", "strafe-review")
        core.modules("install", "gain-converter")
        installed = [c["key"] for c in core.modules("cards")["cards"] if c["installed"]]
        if installed != ["core", "gain-converter", "strafe-review"]:
            fail(f"installed after two installs: {installed}")
        if not (kit / "strafe-review" / "strafe_review.py").is_file():
            fail(f"the Strafe Review module isn't in {kit}")
        if not (ours / "scripts" / "hud" / "strafe-review.ts").is_file():
            fail("the module's install hook didn't put the recorder in")
        calls = ["hud.get"]
        r = core.run("--check-sections", tmp / "sections.json", *calls)
        found = json.loads((tmp / "sections.json").read_text()) if (tmp / "sections.json").is_file() else {}
        hud = found.get("calls", {}).get("hud.get", {})
        if r.returncode != 0 or found.get("sections") != SECTIONS or found.get("problems"):
            fail(f"--check-sections: exit {r.returncode}, {found}, stderr {r.stderr[-400:]!r}")
        # a current Strafe Review has no jump-1 line of its own (First Jump HUD draws it), so no toggle
        if not (hud.get("ok") and hud["result"].get("legacyLine") is False):
            fail(f"HUD section calls: {found.get('calls')}")
        print(f"   ok: both modules installed from the fake GitHub; sections {', '.join(SECTIONS)}; the HUD"
              " section answers, with no legacy jump-1 toggle")

        print("1. Open review (the module's --collect)")
        first = subprocess.Popen([*cmd, "--run-script", str(kit / "strafe-review" / "strafe_review.py"),
                                  "--collect"], env=env)
        wait_serving()
        for path in ("/", "/drill", "/compare", "/static/app.js", "/static/style.css", "/web/tokens.css"):
            code, _ = get(path)
            if code != 200:
                fail(f"{path} answered {code}")
        code, body = get("/api/status")
        st = json.loads(body) if code == 200 else {}
        if not (st.get("game") and Path(st["game"]).samefile(game) and st.get("recorder") and st.get("autoexecBlock")
                and st.get("collecting") and st.get("log", {}).get("exists")):
            fail(f"/api/status answered {code} {body[:300]!r}")
        write_attempt(game / "yaw.log")
        end = time.time() + 15
        while time.time() < end and SMOKE_ID not in get("/api/attempts")[1].decode():
            time.sleep(0.5)
        if SMOKE_ID not in get("/api/attempts")[1].decode():
            fail(f"the attempt written to yaw.log wasn't collected; status: {get('/api/status')[1][:400]!r}")
        saved = session_events("attempt_saved")
        if saved != [{"dir": "bhop_smoke", "id": SMOKE_ID}]:
            fail(f"attempt_saved events on the session: {saved}")
        timer = kit_timer.read_text()
        if "mod-panoDev" not in timer or timer.count("strafe-review.ts") != 1:
            fail(f"timer.xml isn't panoDev's with our include:\n{timer}")
        if (ours / "layout" / "hud" / "timer.xml").exists():
            fail("the recorder's folder has a timer.xml of its own; it belongs in 0-movekit")
        autoexec = (game / "cfg" / "autoexec.cfg").read_bytes()
        want = b"exec something\r\n\r\n// movekit:strafe-review begin\r\ncon_logfile yaw.log\r\nengine_no_focus_sleep 0\r\n// movekit:strafe-review end\r\n"
        if autoexec != want:
            fail(f"autoexec.cfg is {autoexec!r}")
        if opened(tmp):
            fail(f"--collect opened the browser: {opened(tmp)}")
        print("   ok: pages, recorder, timer.xml, CRLF autoexec block, status, attempt collected from a live"
              " log and announced on the session")

        print("2. a second server")
        r = core.run("--serve")
        if r.returncode == 0 or "in use" not in r.stderr:
            fail(f"second server on the busy port: exit {r.returncode}, stderr {r.stderr[-400:]!r}")
        if first.poll() is not None:
            fail("the first server died")
        print("   ok: the old exe's --serve reached the module and refused the busy port")
        post("/api/stop")
        if not wait_down():
            fail("the server still answers after /api/stop")
        core.stop_all(kit)

        print("3. launch option")
        r = core.run(sys.executable, "-c", "import sys; sys.exit(3)")
        if r.returncode != 3:
            fail(f"game exit code came back as {r.returncode}; stderr {r.stderr[-400:]!r}")
        wait_serving()
        end = time.time() + 15
        while time.time() < end and opened(tmp) != [URL]:
            time.sleep(0.5)
        if opened(tmp) != [URL]:
            fail(f"browser calls: {opened(tmp)}")
        log = data / "strafe-review" / "strafe-review.log"
        if "viewer on http" not in (log.read_text(errors="replace") if log.exists() else ""):
            fail(f"the background server's output isn't in {log}")
        print("   ok: exit code 3 handed back, background server running, page opened, output in strafe-review.log")

        print("4. Stop button")
        code, _ = post("/api/stop")
        if code != 200 or not wait_down():
            fail(f"/api/stop answered {code}, or the server still answers")
        time.sleep(1)
        if session_status() is not None:
            fail("the session still answers after /api/stop")
        print("   ok: the background server and its session ended")

        print("5. uninstall")
        core.modules("uninstall", "strafe-review")
        core.modules("uninstall", "gain-converter")
        if (game / "custom" / "0-movekit").exists():
            fail("custom/0-movekit is left after uninstalling")
        if ours.exists() or b"movekit:strafe-review" in (game / "cfg" / "autoexec.cfg").read_bytes():
            fail("the recorder or the autoexec block is left after uninstalling")
        if (kit / "strafe-review").exists():
            fail("the module folder is left after uninstalling")
        r = core.run(sys.executable, "-c", "import sys; sys.exit(4)")
        if r.returncode != 4:
            fail(f"the launch option with no modules: exit {r.returncode}, stderr {r.stderr[-400:]!r}")
        print("   ok: recorder, autoexec block and module folder gone; the game runs with no modules")

        print("6. the bridge")
        app = tmp / "app"
        app.mkdir()
        if REPO:
            copy_cmd = cmd
        else:
            shutil.copy2(cmd[0], app / ("strafe-review" + Path(cmd[0]).suffix))
            copy_cmd = [str(app / ("strafe-review" + Path(cmd[0]).suffix))]
        data2 = tmp / "data2"
        old = data2 / "strafe-review"
        old.mkdir(parents=True)
        (old / "updates.json").write_text(json.dumps({"auto": True}))
        env2 = {**env, "LOCALAPPDATA": str(data2), "XDG_DATA_HOME": str(data2)}
        if REPO:
            env2["MOVEKIT_KIT_ROOT"] = str(data2 / "movekit" / "kit")
        r = core.run(sys.executable, "-c", "import sys; sys.exit(5)", env=env2, cmd=copy_cmd)
        if r.returncode != 5:
            fail(f"the bridge's first launch: exit {r.returncode}, stderr {r.stderr[-400:]!r}")
        cards = {c["key"]: c for c in core.modules("cards", env=env2, cmd=copy_cmd)["cards"]}
        if not (cards.get("strafe-review", {}).get("installed") and cards["strafe-review"]["auto"]):
            fail(f"after the bridge's first launch: {cards.get('strafe-review')}")
        if not wait_down(1):
            post("/api/stop")
            wait_down()
        core.stop_all(data2 / "movekit" / "kit")
        print("   ok: the first launch of strafe-review" + ("" if REPO else Path(cmd[0]).suffix)
              + " installed the module and kept auto-update on")

        if not REPO:
            print("7. core update")
            exe = Path(cmd[0])
            with zipfile.ZipFile(tmp / "core.zip", "w") as z:
                z.write(exe, "movement-kit.exe")  # as the release zip names it, also for a Linux test build
            gh.release("hub-v99.0.0", [("hub-windows.zip", tmp / "core.zip")])
            copy = Path(copy_cmd[0])
            before = copy.stat().st_mtime_ns
            core.modules("check", env=env2, cmd=copy_cmd)
            core.modules("update", "core", env=env2, cmd=copy_cmd)
            if copy.stat().st_mtime_ns == before or not copy.with_name(copy.name + ".old").exists():
                fail("the core update didn't swap the exe")
            core.run(sys.executable, "-c", "import time; time.sleep(3)", env=env2, cmd=copy_cmd)
            if copy.with_name(copy.name + ".old").exists():
                fail("the old exe wasn't cleaned up on the next start")
            print("   ok: hub-v99.0.0 swapped in under strafe-review" + exe.suffix + "; the old exe cleaned up")
    finally:
        core.stop_all(tmp)
        shutil.rmtree(tmp, ignore_errors=True)
    print("smoke test passed")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()
