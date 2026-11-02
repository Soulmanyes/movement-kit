#!/usr/bin/env python3
"""Checks the Linux core (3.7b.4 in PLAN.md) without touching this system: HOME and every data and
config folder point into a temp folder, and GitHub is a fake on a local port.

Usage: python movekit/check_linux_core.py   (exits 1 on the first failure)

Covers: install-hub.sh's copy mode (the core's folders only, no checks or caches, no tool folders,
the launcher running the copy, ~/.local/bin/movekit-run on the copy); a fresh copy listing no
modules and no sections; a module folder surviving a second copy over the core; movekit-run
passing a game through with no modules, and staying on the core when a tool registers from its
own copy and when the last tool unregisters; --uninstall keeping the core while a module is
installed and removing it after; the copy's core update (Manager.linux_core_installer) from a
source archive; Manager.adopt (Source Yaw installed before the core: installed once with its old
auto switch, the flag kept, nothing in a git checkout, tried again after a failure); auto switches
written by another program surviving a held Manager's next save and showing on its cards; and
Source Yaw's GTK updater, once it is a module, using the core's manager for its auto switch and
its update instead of installing itself.
"""
import http.server
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))
TMP = Path(tempfile.mkdtemp(prefix="check-linux-core-"))
for var, sub in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state")):
    os.environ[var] = str(TMP / sub)
os.environ["HOME"] = str(TMP / "home")
(TMP / "home").mkdir()
os.environ.pop("MOVEKIT_KIT_ROOT", None)
os.environ.pop("MOVEKIT_MODULES_API", None)

from movekit import hub, launch, modules, paths  # after the environment above

KIT = modules.core_kit()
BIN = Path(os.environ["HOME"]) / ".local" / "bin" / "movekit-run"


def fail(msg):
    print(f"FAIL: {msg} (left in {TMP})")
    sys.exit(1)


def ok(what):
    print(f"ok   {what}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def sh(*args, cwd=None):
    run = subprocess.run(["sh", *map(str, args)], cwd=cwd, capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, check=False)
    if run.returncode != 0:
        fail(f"sh {' '.join(map(str, args))}: {run.stderr.strip() or run.stdout.strip()}")
    return run.stdout


class GitHub:
    """GitHub's release list and the files it names."""

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

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.api = self.base + "/releases"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def add(self, tag, files=(), **extra):
        r = {"tag_name": tag, "html_url": "", "body": f"notes {tag}", "assets": [], **extra}
        for name, body in files:
            path = f"/files/{tag}/{name}"
            self.files[path] = body
            r["assets"].append({"name": name, "browser_download_url": self.base + path})
        self.releases.insert(0, r)


HOOKS = '''import os
from pathlib import Path


def install(ctx):
    Path(os.environ["HOME"], "installed-" + ctx.manifest["key"]).write_text("")
'''


def module_zip(key, version):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{key}/module.json", json.dumps({
            "key": key, "title": key, "os": ["linux"], "tag_prefix": f"{key}-v",
            "version_from": "tool.py", "needs_core": "1.0.0", "needs": [], "data": []}))
        z.writestr(f"{key}/tool.py", f'VERSION = "{version}"\n')
        z.writestr(f"{key}/module_hooks.py", HOOKS)
    return buf.getvalue()


def check_copy():
    sh(REPO / "movekit" / "install-hub.sh", "--copy")
    names = sorted(p.name for p in KIT.iterdir())
    expect(names, ["LICENSE", "hud", "movekit"], "the copy holds the core only")
    left = [p for p in KIT.rglob("*") if p.name.startswith("check_") or p.name == "__pycache__"]
    expect(left, [], "no checks or caches in the copy")
    for f in ("hub.py", "modules.py", "launch.py", "movekit-run", "web/home.html", "icons"):
        if not (KIT / "movekit" / f).exists():
            fail(f"the copy has no movekit/{f}")
    if not os.access(KIT / "movekit" / "movekit-run", os.X_OK):
        fail("movekit-run in the copy isn't executable")
    desktop = (paths.data_dir("applications") / "io.github.soulmanyes.MovementKit.desktop").read_text()
    if f'Exec=python3 "{KIT}/movekit/hub.py"' not in desktop:
        fail(f"the launcher doesn't run the copy: {desktop}")
    expect(BIN.resolve(), (KIT / "movekit" / "movekit-run").resolve(), "movekit-run links to the copy")
    ok("install-hub.sh --copy: core only, launcher and movekit-run on the copy")

    reply = json.loads(subprocess.run([sys.executable, "-m", "movekit.modules", "cards"], cwd=KIT,
                                      capture_output=True, text=True, check=False,
                                      env={**os.environ, "MOVEKIT_MODULES_API": "http://127.0.0.1:9/x"}
                                      ).stdout)
    expect([c["key"] for c in reply["cards"]], ["core"], "a fresh copy lists no modules")
    expect(reply["cards"][0]["checkout"], False, "the copy isn't a checkout")
    sections, problems = hub.kit_sections(modules.Manager(kit_root=KIT), root=KIT)
    expect(([s.key for s in sections], list(problems)), ([], []), "a fresh copy has no sections")
    ok("a fresh copy: no modules, no sections, not a checkout")

    fake = KIT / "fake"
    fake.mkdir()
    (fake / "module.json").write_text("{}")
    (KIT / "movekit" / "stale.py").write_text("")
    sh(REPO / "movekit" / "install-hub.sh", "--copy")
    if not (fake / "module.json").is_file():
        fail("a second copy removed a module folder")
    if (KIT / "movekit" / "stale.py").exists():
        fail("a second copy kept a file the core no longer has")
    if any(p.name.startswith(".core-") for p in KIT.iterdir()):
        fail("the copy left its staging folders")
    ok("a second copy replaces the core and keeps the module folders")

    sh(KIT / "movekit" / "install-hub.sh", "--uninstall")
    if not (KIT / "movekit").is_dir() or not BIN.is_symlink():
        fail("--uninstall removed the core while a module is installed")
    shutil.rmtree(fake)
    ok("--uninstall keeps the core while a module is installed")


def check_launch_link():
    game = subprocess.run([str(BIN), "/bin/echo", "the game ran"], capture_output=True, text=True,
                          check=False)
    expect(game.stdout.strip(), "the game ran", "movekit-run with no modules starts the game")
    # a tool installed with its own installer, with its own movekit copy (Source Yaw's install.sh)
    tool = TMP / "data" / "sometool"
    shutil.copytree(REPO / "movekit", tool / "movekit",
                    ignore=shutil.ignore_patterns("check_*", "__pycache__"))
    (tool / "launch-hook.sh").write_text("true\n")
    py = [sys.executable, str(tool / "movekit" / "launch.py")]
    subprocess.run([*py, "register", "sometool", "50", str(tool / "launch-hook.sh")], check=True)
    expect(BIN.resolve(), (KIT / "movekit" / "movekit-run").resolve(), "register keeps movekit-run on the core")
    subprocess.run([*py, "unregister", "sometool"], check=True)
    expect(BIN.resolve(), (KIT / "movekit" / "movekit-run").resolve(),
           "the last unregister keeps movekit-run on the core")
    expect(launch.registered(), {}, "no hooks left")
    game = subprocess.run([str(BIN), "/bin/echo", "still runs"], capture_output=True, text=True, check=False)
    expect(game.stdout.strip(), "still runs", "movekit-run after the last tool went")
    shutil.rmtree(tool)
    ok("movekit-run: game with no modules, stays on the core through register and unregister")


def check_core_update(gh):
    # a source archive like GitHub's: one top folder holding the repo, here with a marked core
    src = TMP / "src" / "movement-kit-hub-v1.0.1"
    for d in ("movekit", "hud"):
        shutil.copytree(REPO / d, src / d, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(REPO / "LICENSE", src / "LICENSE")
    (src / "movekit" / "marker-1.0.1").write_text("")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(src, arcname=src.name)
    gh.add("hub-v1.0.1", tarball_url=None)
    gh.releases[0]["tarball_url"] = gh.base + "/source/hub-v1.0.1.tar.gz"
    gh.files["/source/hub-v1.0.1.tar.gz"] = buf.getvalue()
    keep = KIT / "keepme"
    keep.mkdir()
    (keep / "module.json").write_text("{}")
    mgr = modules.Manager(kit_root=KIT, api=gh.api)
    mgr.core_installer = mgr.linux_core_installer
    mgr.check(force=True)
    card = next(c for c in mgr.cards() if c["key"] == "core")
    expect((card["update"], card["can_update"]), (True, True), "the copy's core card offers the update")
    mgr.update("core")
    if not (KIT / "movekit" / "marker-1.0.1").is_file():
        fail("the core update didn't copy the new core")
    if not (keep / "module.json").is_file():
        fail("the core update removed a module folder")
    expect(mgr.state["modules"]["core"].get("installed"), "hub-v1.0.1", "the core update is marked")
    expect(BIN.resolve(), (KIT / "movekit" / "movekit-run").resolve(), "movekit-run after the core update")
    shutil.rmtree(keep)
    gh.releases.clear()
    ok("the copy's core updates from the release's source archive, modules kept")

    # the hub window's manager: the installer on a copy, none in a checkout
    expect(hub.make_manager(kit_root=KIT).core_installer is not None, True, "hub gives a copy its installer")
    expect(hub.make_manager().core_installer, None, "hub gives a checkout no core installer")
    ok("the hub's manager: core installer on a copy only")


def check_adopt(gh):
    old = paths.data_dir("sourceyaw")
    old.mkdir(parents=True)
    (old / "yawcore.py").write_text('VERSION = "1.6.0"\n')
    cfg = paths.config_dir("sourceyaw")
    cfg.mkdir(parents=True)
    (cfg / "updates.json").write_text(json.dumps({"auto": True}))
    flag = "adopted-sourceyaw"

    # offline: raises, the flag stays unset, so the next start tries again
    mgr = modules.Manager(kit_root=KIT, api="http://127.0.0.1:9/releases")
    try:
        mgr.adopt("sourceyaw", old / "yawcore.py", [cfg / "updates.json"], flag)
        fail("adopt offline didn't raise")
    except OSError:
        pass
    expect(mgr.state.get(flag), None, "no flag after a failed adopt")
    # no module release yet: raises too
    mgr = modules.Manager(kit_root=KIT, api=gh.api)
    try:
        mgr.adopt("sourceyaw", old / "yawcore.py", [cfg / "updates.json"], flag)
        fail("adopt with no module release didn't raise")
    except RuntimeError:
        pass
    expect(mgr.state.get(flag), None, "no flag with no module release")

    gh.add("sourceyaw-v1.7.0", [("sourceyaw-module.zip", module_zip("sourceyaw", "1.7.0"))])
    # the hub's own step, as the window runs it
    hub.adopt_old_installs(mgr)
    expect("sourceyaw" in mgr.installed(), True, "adopt installed the module")
    expect(mgr.version("sourceyaw"), "1.7.0", "adopted version")
    expect(mgr.info("sourceyaw")["auto"], True, "adopt kept the old auto switch")
    expect(mgr.state.get(flag), True, "adopt set its flag")
    if not (Path(os.environ["HOME"]) / "installed-sourceyaw").is_file():
        fail("adopt didn't run the install hook")
    mgr.uninstall("sourceyaw")
    expect(mgr.adopt("sourceyaw", old / "yawcore.py", [cfg / "updates.json"], flag), False,
           "adopt runs once")
    expect("sourceyaw" in mgr.installed(), False, "an uninstalled module isn't adopted again")

    checkout = modules.Manager(kit_root=REPO, data=TMP / "checkout-data", api=gh.api)
    expect(checkout.adopt("sourceyaw", old / "yawcore.py", [], flag), False, "no adopt in a checkout")
    expect(checkout.state.get(flag), None, "no flag written in a checkout")
    gh.releases.clear()
    ok("adopt: once, old auto switch kept, retried after a failure, never in a checkout")


def check_shared_auto():
    held = modules.Manager(kit_root=KIT)
    held.set_auto("alpha", False)
    other = modules.Manager(kit_root=KIT)
    other.set_auto("alpha", True)
    expect(held.info("alpha")["auto"], False, "the held manager before cards()")
    expect(next(c for c in held.cards() if c["key"] == "core")["key"], "core", "cards")
    expect(held.info("alpha")["auto"], True, "cards() takes another program's switch")
    other.set_auto("alpha", False)
    held.note("something", 1)  # a save of the held manager
    expect(json.loads(held.state_file.read_text())["modules"]["alpha"]["auto"], False,
           "another program's switch survives the held manager's save")
    held.set_auto("alpha", True)
    expect(json.loads(held.state_file.read_text())["modules"]["alpha"]["auto"], True,
           "the held manager's own change wins")
    ok("auto switches: another program's survive a held manager's save and show on its cards")


def check_gtk_updater(gh):
    # an installed Source Yaw, as install.sh lays it out: its files and a copy of movekit
    app = TMP / "data" / "sourceyaw-app"
    shutil.copytree(REPO / "sourceyaw", app, ignore=shutil.ignore_patterns(
        "__pycache__", "check_*", "overlay", "inputd", "icons"))
    shutil.copytree(REPO / "movekit", app / "movekit", ignore=shutil.ignore_patterns("check_*", "__pycache__"))
    code = '''
import json, sys
sys.path.insert(0, sys.argv[1])
import updater
u = updater.Updater("x/y", "1.6.0", sys.argv[1], sys.argv[2])
out = {"managed": u.managed, "auto": u.auto}
u.auto = True
out["auto_after"] = u.auto
calls = []
updater.kit.install_source = lambda *a, **k: calls.append("self-install")
u._manager = lambda *a, **k: calls.append(list(a))
u._install({"tag": "sourceyaw-v9.9.9"})
out["install"] = calls
print(json.dumps(out))
'''

    def run():
        res = subprocess.run([sys.executable, "-c", code, str(app), str(TMP / "gtk-updates.json")],
                             capture_output=True, text=True, check=False)
        if res.returncode:
            fail(f"GTK updater: {res.stderr.strip()}")
        return json.loads(res.stdout)

    out = run()
    expect((out["managed"], out["install"]), (False, ["self-install"]), "not a module: installs itself")
    expect(json.loads((TMP / "gtk-updates.json").read_text())["auto"], True, "not a module: its own switch")

    (KIT / "sourceyaw").mkdir()
    (KIT / "sourceyaw" / "module.json").write_text("{}")
    mgr = modules.Manager(kit_root=KIT)
    mgr.set_auto("sourceyaw", False)
    out = run()
    expect(out["managed"], True, "a module: managed")
    expect(out["install"], [["update", "sourceyaw"]], "a module: the update goes to the core's manager")
    expect(out["auto"], False, "a module: the switch read from the manager")
    expect(out["auto_after"], True, "a module: the switch written through the manager")
    expect(modules.Manager(kit_root=KIT).info("sourceyaw")["auto"], True, "the manager's switch is on")
    shutil.rmtree(KIT / "sourceyaw")
    ok("Source Yaw's GTK updater: as a module, switch and update through the core's manager")

    # the same with the real manager command and a fake GitHub: the window and the manager agree
    os.environ["MOVEKIT_MODULES_API"] = gh.api  # the window's manager command reads it
    gh.add("sourceyaw-v1.6.0", [("sourceyaw-module.zip", module_zip("sourceyaw", "1.6.0"))])
    hub_mgr = modules.Manager(kit_root=KIT, api=gh.api)
    hub_mgr.check(force=True)  # not the adopt check's list, still cached
    hub_mgr.install("sourceyaw")
    expect(hub_mgr.version("sourceyaw"), "1.6.0", "the module installed")
    hub_mgr.check(force=True)  # the hub looked before the next release came out
    code = '''
import json, sys
sys.path.insert(0, sys.argv[1])
import updater
u = updater.Updater("x/y", sys.argv[3], sys.argv[1], sys.argv[2])
latest = u.check(force=sys.argv[4] == "force")
out = {"latest": latest and latest["tag"], "installed": bool(latest and u.installed(latest))}
if sys.argv[5] == "install":
    u.install(latest)
    out["failed"] = u.state.get("failed")
print(json.dumps(out))
'''

    def gtk(version, action="", force=""):
        res = subprocess.run([sys.executable, "-c", code, str(app), str(TMP / "gtk2.json"), version,
                              force, action], capture_output=True, text=True, check=False)
        if res.returncode:
            fail(f"GTK updater ({version} {action}): {res.stderr.strip()}")
        return json.loads(res.stdout)

    expect(gtk("1.6.0"), {"latest": None, "installed": False}, "up to date")
    gh.add("sourceyaw-v1.7.0", [("sourceyaw-module.zip", module_zip("sourceyaw", "1.7.0"))])
    # A: a release since the hub's look; the window's update gets it through the manager
    expect(gtk("1.6.0", "install"), {"latest": "sourceyaw-v1.7.0", "installed": False, "failed": None},
           "a new release, updated from the window")
    expect(modules.Manager(kit_root=KIT).version("sourceyaw"), "1.7.0", "the module folder updated")
    # B: the hub updated the module while a 1.7.0 window ran: waiting for a restart, no install
    gh.add("sourceyaw-v1.7.1", [("sourceyaw-module.zip", module_zip("sourceyaw", "1.7.1"))])
    hub_mgr.check(force=True)
    hub_mgr.update("sourceyaw")
    expect(gtk("1.7.0"), {"latest": "sourceyaw-v1.7.1", "installed": True}, "updated while the window ran")
    # C: a tag whose module zip isn't up yet isn't offered
    gh.add("sourceyaw-v1.8.0")
    expect(gtk("1.7.1"), {"latest": None, "installed": False}, "a release with no module zip")
    hub_mgr.uninstall("sourceyaw")
    gh.releases.clear()
    del os.environ["MOVEKIT_MODULES_API"]
    ok("Source Yaw's GTK updater with the real manager: new release, updated by the hub, no zip yet")


def check_uninstall_core():
    sh(KIT / "movekit" / "install-hub.sh", "--uninstall")
    if KIT.exists() or BIN.exists() or BIN.is_symlink():
        fail("--uninstall with no modules left the core or movekit-run")
    ok("--uninstall with no modules removes the core and movekit-run")


def main():
    gh = GitHub()
    check_copy()
    check_launch_link()
    check_core_update(gh)
    check_adopt(gh)
    check_shared_auto()
    check_gtk_updater(gh)
    check_uninstall_core()
    gh.server.shutdown()
    shutil.rmtree(TMP, ignore_errors=True)
    print("check_linux_core: all passed")


if __name__ == "__main__":
    main()
