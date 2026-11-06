#!/usr/bin/env python3
"""Checks movekit.modules (3.7b in PLAN.md) without touching this system: fixture modules, a fake
GitHub on a local port, and every data and config folder pointed into a temp folder.

Usage: python movekit/check_modules.py   (exits 1 on the first failure)

Covers, for the kit's own modules: each module.json is valid and its version_from file has a
VERSION; module_hooks.py loads and defines only known hooks; core 1.0.0 matches hub/hub_release.py;
and the import rule: a module that runs on Windows imports only the standard library (less tkinter),
movekit, hud, webview and its own files, since the core exe can only give it what it bundled
(files module.json lists as standalone, such as an old window, are left out).
For the manager, against fixture modules alpha and beta (beta needs alpha) in a plain kit folder:
GitHub's list read once (drafts, pre-releases, releases with no module zip and other tools' tags
left out; the highest version wins), a fresh kit with nothing installed, install refused while a
needed module is missing, install, update (previous kept, install hook run again, stop and start
around it), roll back and back again, auto off by default and auto_update doing nothing until the
switch is on, a broken release (install hook fails: marked failed, the old version back, auto
skipping it), a release that needs a newer core (waits, nothing changed), a zip with a ../ path
refused, set_auto refusing a non-bool, uninstall refused while another module needs it, uninstall
(hook run, folder and previous gone, saved data kept or deleted as asked, the auto switch kept),
a swap that fails halfway (everything back, the server started again, the release marked failed),
update_all, and the core's card using the installer it was given; data entries outside the
module's own folders refused. In a git checkout: no downloads,
uninstall runs the hook and hides the module with its code left, install shows it again.
Strafe Review's real hooks from this checkout, with HOME, the data folders and its server port in
the temp folder: install puts the recorder, autoexec block and launch hook in, uninstall takes them
out, and uninstall still finishes when the game is gone.
The hub's Bridge over a manager: the Modules page's calls (cards, check, install, set_auto, an
error reply still carrying the cards, a call while busy, uninstall), and the sections and page
server following installs, with a core section's show_with hiding it until its module is in.
"""
import ast
import http.server
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
sys.path.insert(0, str(KIT))
TMP = Path(tempfile.mkdtemp(prefix="check-modules-"))
for var, sub in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"),
                 ("LOCALAPPDATA", "data"), ("APPDATA", "config")):
    os.environ[var] = str(TMP / sub)
os.environ["HOME"] = str(TMP / "home")  # ~/.local/bin links (launch.bin_link) and Steam's folders
(TMP / "home").mkdir()


def closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# the Strafe Review hooks' stop asks its server: never the real one on 8765
os.environ["STRAFE_REVIEW_PORT"] = str(closed_port())
os.environ.pop("MOMENTUM_DIR", None)
OUT = TMP / "hook-calls"
OUT.mkdir()
os.environ["MODCHECK_OUT"] = str(OUT)

from movekit import modules  # after the path and environment above

CORE = modules.CORE_VERSION
_major, _minor, *_ = CORE.split(".")
NEXT_CORE = f"{_major}.{int(_minor) + 1}.0"  # a hub-v* release newer than this core
HOOK_NAMES = {"install", "uninstall", "stop", "start", "launch"}
ALLOWED = (set(sys.stdlib_module_names) - {"tkinter", "turtle", "idlelib", "test", "ensurepip"}) \
    | {"movekit", "hud", "webview", "__future__"}
SKIP = {"build", "dist", "__pycache__", "probe"}  # build output, and tools that never ship


def fail(msg):
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def raises(fn, text, what):
    try:
        fn()
    except (OSError, RuntimeError, ValueError) as e:
        if text not in str(e):
            fail(f"{what}: error {e!r} doesn't say {text!r}")
        return
    fail(f"{what}: no error")


# the kit's own modules

def own_names(folder):
    """Module names a tool's own files can import: its .py files and folders, at any depth (the
    tools put their subfolders on the path)."""
    names = set()
    for p in folder.rglob("*"):
        if SKIP & set(p.relative_to(folder).parts):
            continue
        if p.suffix == ".py":
            names.add(p.stem)
        elif p.is_dir():
            names.add(p.name)
    return names


def shipped_files(folder):
    for p in sorted(folder.rglob("*.py")):
        rel = p.relative_to(folder)
        if SKIP & set(rel.parts) or rel.name.startswith("check_") \
                or rel.name in ("build.py", "smoke_test.py"):
            continue
        yield p


def optional(tree):
    """Import nodes inside a try that catches ImportError: the file runs without them."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
                isinstance(h.type, ast.Name) and h.type.id in ("ImportError", "ModuleNotFoundError")
                for h in node.handlers):
            out |= {id(n) for stmt in node.body for n in ast.walk(stmt)}
    return out


def imports(file):
    """(top-level name, line) of each import the file needs."""
    tree = ast.parse(file.read_text(encoding="utf-8"), str(file))
    skip = optional(tree)
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0], node.lineno
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0], node.lineno


def check_own_modules():
    hub_release = (KIT / "hub" / "hub_release.py").read_text()
    expect(modules.VERSION_RE.search(hub_release).group(1), modules.CORE_VERSION,
           "hub_release.VERSION against CORE_VERSION")
    found = []
    for folder in sorted(p for p in KIT.iterdir() if (p / modules.MANIFEST).is_file()):
        try:
            m = modules.read_manifest(folder)
        except ValueError as e:
            fail(f"{folder.name}/module.json: {e}")
        found.append(m["key"])
        if not modules.module_version(folder, m):
            fail(f"{folder.name}: no VERSION line in {m['version_from']}")
        if (folder / modules.HOOKS).is_file():
            hooks = modules.Manager(kit_root=KIT, data=TMP / "own-data")._hooks(folder.name)
            public = {n for n in vars(hooks) if callable(getattr(hooks, n)) and not n.startswith("_")
                      and getattr(getattr(hooks, n), "__module__", None) == hooks.__name__}
            if public - HOOK_NAMES:
                fail(f"{folder.name}/module_hooks.py defines {sorted(public - HOOK_NAMES)}")
        if "win32" in m["os"]:
            own = own_names(folder)
            for file in shipped_files(folder):
                if str(file.relative_to(folder)) in m["standalone"]:
                    continue
                for name, line in imports(file):
                    if name not in ALLOWED and name not in own:
                        fail(f"{file.relative_to(KIT)}:{line} imports {name}, which the core exe "
                             "doesn't carry")
    expect(sorted(found), ["first-jump", "gain-converter", "jhud", "sourceyaw", "strafe-histogram", "strafe-review", "trainer-height", "zone-exit"], "the kit's modules")
    # discovery from the checkout finds every module's folder (the manager itself, next)
    mgr = modules.Manager(kit_root=KIT, data=TMP / "own-data", platform="linux")
    expect(mgr.problems(), [], "problems in the kit's module.json files")
    expect(sorted(mgr.available()), sorted(found), "modules available on Linux")
    expect(sorted(modules.Manager(kit_root=KIT, data=TMP / "own-data", platform="win32").available()),
           sorted(found), "modules available on Windows (every one since Source Yaw's Phase 12)")
    bad = TMP / "bad" / "alpha"
    bad.mkdir(parents=True)
    (bad / "tool.py").write_text('VERSION = "1.0.0"\n')
    for data_entry in ("data:Steam", "config:alphabet", "data:alpha/../x"):
        (bad / "module.json").write_text(json.dumps({
            "key": "alpha", "title": "A", "os": ["linux"], "tag_prefix": "alpha-v",
            "version_from": "tool.py", "needs_core": "1.0.0", "data": [data_entry]}))
        raises(lambda: modules.read_manifest(bad), "data entries", f"data entry {data_entry}")
    base = {"key": "alpha", "title": "A", "os": ["linux"], "tag_prefix": "alpha-v",
            "version_from": "tool.py", "needs_core": "1.0.0"}
    for card in ("JHUD", {"title": "A"}, {"title": "A", "text": ""}, {"title": "A", "text": "t", "x": "y"},
                 {"title": 1, "text": "t"}):
        (bad / "module.json").write_text(json.dumps({**base, "hud_card": card}))
        raises(lambda: modules.read_manifest(bad), "hud_card", f"hud_card {card!r}")
    (bad / "module.json").write_text(json.dumps({**base, "hud_card": {"title": "A", "text": "t"}}))
    expect(modules.read_manifest(bad)["hud_card"], {"title": "A", "text": "t"}, "a good hud_card")


# fixture modules and a fake GitHub

HOOKS_SRC = '''import os
from pathlib import Path

from movekit.modules import module_version

BROKEN = {broken}


def _note(ctx, what):
    v = module_version(ctx.folder, ctx.manifest)
    (Path(os.environ["MODCHECK_OUT"]) / f"{{ctx.manifest['key']}}-{{what}}-{{v}}").write_text("")


def install(ctx):
    if BROKEN:
        raise RuntimeError("no game here")
    _note(ctx, "install")


def uninstall(ctx):
    _note(ctx, "uninstall")


def stop(ctx):
    _note(ctx, "stop")
    return True


def start(ctx):
    _note(ctx, "start")
'''


def module_zip(key, version, needs=(), needs_core="1.0.0", broken=False, evil=False):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{key}/module.json", json.dumps({
            "key": key, "title": key.title(), "summary": f"{key} module", "os": ["linux", "win32"],
            "tag_prefix": f"{key}-v", "version_from": "tool.py", "needs_core": needs_core,
            "needs": list(needs), "data": [f"data:{key}"]}))
        z.writestr(f"{key}/tool.py", f'VERSION = "{version}"\n')
        hook = zipfile.ZipInfo(f"{key}/launch-hook.sh")
        hook.external_attr = 0o100755 << 16
        z.writestr(hook, "#!/bin/sh\n")
        z.writestr(f"{key}/module_hooks.py", HOOKS_SRC.format(broken=broken))
        z.writestr(f"{key}/hub_section.py", f"SECTION = {{'key': '{key}', 'title': '{key.title()}', "
                   f"'os': ['linux', 'win32'], 'page': 'page.html', 'api': {{'hello': lambda: '{version}'}}}}\n")
        z.writestr(f"{key}/page.html", "<!DOCTYPE html><title>x</title>")
        if evil:
            z.writestr("../escaped.txt", "x")
    return buf.getvalue()


class GitHub:
    """Answers like GitHub's release list, and serves the zips it names."""

    def __init__(self):
        self.releases, self.files = [], {}
        gh = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/releases"):
                    body = json.dumps(gh.releases).encode()
                elif self.path in gh.files:
                    body = gh.files[self.path]
                else:
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
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def release(self, tag, asset=None, data=None, manifest=None, **extra):
        r = {"tag_name": tag, "html_url": f"https://example.invalid/{tag}", "body": f"notes {tag}",
             "assets": [], **extra}
        files = [(asset, data)] if asset else []
        if manifest is not None:
            files.append((tag.rsplit("-v", 1)[0] + "-module.json", json.dumps(manifest).encode()))
        for name, body in files:
            path = f"/files/{tag}/{name}"
            self.files[path] = body
            r["assets"].append({"name": name, "browser_download_url": self.base + path})
        self.releases.insert(0, r)


def calls():
    """The hook calls since the last look, sorted, and clears them."""
    out = sorted(p.name for p in OUT.iterdir())
    for p in OUT.iterdir():
        p.unlink()
    return out


def check_manager():
    gh = GitHub()
    kit, data = TMP / "kit", TMP / "mgr"
    core_installs = []
    mgr = modules.Manager(kit_root=kit, data=data, api=gh.base + "/releases?per_page=100",
                          core_installer=core_installs.append)

    # nothing on GitHub that the manager offers yet
    gh.release("alpha-v0.9.0")  # from before 3.7b: no module zip
    gh.release("gamma-v1.0.0", "gamma-windows.zip", b"")  # a tool exe, not a module
    gh.release("alpha-v2.0.0", "alpha-module.zip", module_zip("alpha", "2.0.0"), draft=True)
    gh.release("alpha-v3.0.0", "alpha-module.zip", module_zip("alpha", "3.0.0"), prerelease=True)
    expect(mgr.check(force=True), {}, "releases the manager offers before any module zip")
    expect([c["key"] for c in mgr.cards()], ["core"], "cards of a fresh kit")
    expect(mgr.installed(), {}, "a fresh kit installs nothing")

    gh.release("alpha-v1.0.0", "alpha-module.zip", module_zip("alpha", "1.0.0"))
    gh.release("beta-v1.0.0", "beta-module.zip", module_zip("beta", "1.0.0", needs=["alpha"]))
    gh.release(f"hub-v{CORE}")
    latest = mgr.check(force=True)
    expect(sorted(latest), ["alpha", "beta", "core"], "lines found")
    expect(latest["alpha"]["tag"], "alpha-v1.0.0", "alpha's newest release")
    expect(latest["alpha"]["notes"], "notes alpha-v1.0.0", "release notes kept")
    card = mgr.info("alpha")
    expect((card["installed"], card["can_install"], card["auto"]), (False, True, False),
           "alpha's card before install")
    expect(mgr.info("core")["update"], False, f"core {CORE} against hub-v{CORE}")

    raises(lambda: mgr.install("beta"), "needs alpha", "beta before alpha")
    expect((kit / "beta").exists(), False, "beta's folder after the refused install")
    mgr.install("alpha")
    expect(calls(), ["alpha-install-1.0.0"], "hooks on install (no stop on a first install)")
    if sys.platform != "win32":
        expect(os.access(kit / "alpha" / "launch-hook.sh", os.X_OK), True, "executable bit kept from the zip")
    expect(mgr.version("alpha"), "1.0.0", "alpha's version")
    expect(sorted(mgr.installed()), ["alpha"], "installed after alpha")
    expect([p.name for p in mgr.roots()], ["alpha"], "section roots")
    mgr.install("beta")
    calls()
    raises(lambda: mgr.install("alpha"), "already installed", "installing twice")

    # an update keeps the previous version and runs the hooks around the swap
    gh.release("alpha-v1.1.0", "alpha-module.zip", module_zip("alpha", "1.1.0"))
    mgr.check(force=True)
    card = mgr.info("alpha")
    expect((card["update"], card["can_update"], card["latest"]["tag"]), (True, True, "alpha-v1.1.0"),
           "alpha's card with an update")
    expect(mgr.auto_update(), {}, "auto_update with every switch off")
    expect(mgr.version("alpha"), "1.0.0", "alpha after auto_update with auto off")
    mgr.update("alpha")
    expect(calls(), ["alpha-install-1.1.0", "alpha-start-1.1.0", "alpha-stop-1.0.0"],
           "hooks on update")
    card = mgr.info("alpha")
    expect((card["version"], card["can_rollback"], card["previous"]), ("1.1.0", True, "alpha-v1.0.0"),
           "alpha after the update")
    raises(lambda: mgr.update("alpha"), "up to date", "updating an up-to-date module")

    mgr.rollback("alpha")
    expect(mgr.version("alpha"), "1.0.0", "alpha after roll back")
    expect(mgr.info("alpha")["previous"], "alpha-v1.1.0", "previous after roll back")
    expect("alpha-install-1.0.0" in calls(), True, "install hook after roll back")
    mgr.rollback("alpha")
    expect(mgr.version("alpha"), "1.1.0", "alpha after rolling back the roll back")
    calls()

    # auto on: auto_update installs; a broken release fails once and is skipped after
    raises(lambda: mgr.set_auto("alpha", "yes"), "true or false", "set_auto with a string")
    mgr.set_auto("alpha", True)
    gh.release("alpha-v1.2.0", "alpha-module.zip", module_zip("alpha", "1.2.0", broken=True))
    mgr.check(force=True)
    result = mgr.auto_update()
    expect(list(result), ["alpha"], "auto_update tried alpha")
    if "no game here" not in (result["alpha"] or ""):
        fail(f"auto_update's error for the broken release: {result['alpha']!r}")
    expect(mgr.version("alpha"), "1.1.0", "alpha after the broken update")
    expect(mgr.info("alpha")["failed"], "alpha-v1.2.0", "failed mark")
    calls()
    expect(mgr.auto_update(), {}, "auto_update skipping the failed release")

    # a release needing a newer core waits
    gh.release("alpha-v1.3.0", "alpha-module.zip", module_zip("alpha", "1.3.0", needs_core="9.0.0"))
    mgr.check(force=True)
    raises(lambda: mgr.update("alpha"), "needs core 9.0.0", "update needing a newer core")
    expect(mgr.version("alpha"), "1.1.0", "alpha after the refused update")
    expect(mgr.info("alpha")["waiting_for_core"], "9.0.0", "waiting_for_core on the card")
    expect(calls(), [], "no hooks for an update that waits for the core")

    gh.release("alpha-v1.4.0", "alpha-module.zip", module_zip("alpha", "1.4.0", evil=True))
    mgr.check(force=True)
    raises(lambda: mgr.update("alpha"), "Unexpected file", "a zip with ../")
    expect((TMP / "mgr" / "escaped.txt").exists() or (TMP / "escaped.txt").exists(), False,
           "file outside the staging folder")
    expect(mgr.version("alpha"), "1.1.0", "alpha after the refused zip")

    # update_all takes every module with an update, then the core
    gh.release("alpha-v1.5.0", "alpha-module.zip", module_zip("alpha", "1.5.0"))
    gh.release("beta-v1.1.0", "beta-module.zip", module_zip("beta", "1.1.0", needs=["alpha"]))
    gh.release(f"hub-v{NEXT_CORE}")
    mgr.check(force=True)
    expect(mgr.update_all(), {"alpha": None, "beta": None, "core": None}, "update_all")
    expect((mgr.version("alpha"), mgr.version("beta")), ("1.5.0", "1.1.0"), "versions after update_all")
    expect([c["tag"] for c in core_installs], [f"hub-v{NEXT_CORE}"], "core installer calls")
    calls()

    # a swap that fails halfway (Windows: a file still in use) puts everything back
    gh.release("alpha-v1.6.0", "alpha-module.zip", module_zip("alpha", "1.6.0"))
    mgr.check(force=True)
    real_rename = Path.rename

    def busy(self, target):
        if Path(target) == kit / "alpha" and "staging" in self.parts:
            raise PermissionError("in use")
        return real_rename(self, target)

    Path.rename = busy
    try:
        raises(lambda: mgr.update("alpha"), "in use", "update whose swap fails")
    finally:
        Path.rename = real_rename
    expect(mgr.version("alpha"), "1.5.0", "alpha after the failed swap")
    expect(modules.module_version(data / "previous" / "alpha", {"version_from": "tool.py"}), "1.1.0",
           "the kept previous version after the failed swap")
    expect((data / "previous" / "alpha.hold").exists(), False, "hold folder after the failed swap")
    expect(calls(), ["alpha-install-1.5.0", "alpha-start-1.5.0", "alpha-stop-1.5.0"],
           "hooks around the failed swap (old version reinstalled, started again)")
    expect(mgr.info("alpha")["failed"], "alpha-v1.6.0", "failed mark after the failed swap")

    # uninstall
    raises(lambda: mgr.uninstall("alpha"), "beta needs alpha", "uninstalling a needed module")
    raises(lambda: mgr.uninstall("core"), "can't be uninstalled", "uninstalling the core")
    for key in ("alpha", "beta"):
        d = modules.paths.data_dir(key)
        d.mkdir(parents=True)
        (d / "saved").write_text("x")
    mgr.uninstall("beta")
    expect(calls(), ["beta-stop-1.1.0", "beta-uninstall-1.1.0"], "hooks on uninstall")
    expect((kit / "beta").exists(), False, "beta's folder after uninstall")
    expect((modules.paths.data_dir("beta") / "saved").exists(), True, "data kept by default")
    mgr.uninstall("alpha", delete_data=True)
    expect(modules.paths.data_dir("alpha").exists(), False, "data deleted when asked")
    expect((data / "previous" / "alpha").exists(), False, "previous version after uninstall")
    expect(mgr.installed(), {}, "installed after both uninstalls")
    expect(mgr.info("alpha")["auto"], True, "alpha's auto switch kept for a reinstall")
    calls()


def check_checkout():
    root = TMP / "checkout"
    (root / ".git").mkdir(parents=True)
    alpha = root / "alpha"
    with zipfile.ZipFile(io.BytesIO(module_zip("alpha", "1.0.0"))) as z:
        z.extractall(root)
    mgr = modules.Manager(kit_root=root, data=TMP / "co-data", api="http://127.0.0.1:9/none")
    expect(sorted(mgr.installed()), ["alpha"], "a checkout's modules count as installed")
    card = mgr.info("alpha")
    expect((card["checkout"], card["can_update"], card["can_rollback"]), (True, False, False),
           "a checkout's card")
    raises(lambda: mgr.update("alpha"), "git pull", "update in a checkout")
    mgr.uninstall("alpha", delete_data=False)
    expect(calls(), ["alpha-stop-1.0.0", "alpha-uninstall-1.0.0"], "hooks on a checkout uninstall")
    expect(((alpha / "tool.py").is_file(), mgr.installed()), (True, {}), "checkout uninstall")
    expect(mgr.info("alpha")["can_install"], True, "a hidden checkout module can come back")
    mgr.install("alpha")
    expect(calls(), ["alpha-install-1.0.0"], "hooks on a checkout install")
    expect(sorted(mgr.installed()), ["alpha"], "installed again")


def check_groups():
    """The Modules page's order: tools, then HUD modules, installed first, by title; modules this OS
    can't run last, with no Install. group in module.json, LEGACY_GROUPS for releases without it, os and
    group kept from a release's module.json copy. games the same way: module.json, LEGACY_GAMES, a
    release's copy, bad values refused, and every real module saying its games."""
    root = TMP / "groups"
    (root / ".git").mkdir(parents=True)

    def mod(key, title, oses, group=None, games=None):
        m = {"key": key, "title": title, "os": oses, "tag_prefix": f"{key}-v", "version_from": "tool.py",
             "needs_core": "1.0.0"}
        if group:
            m["group"] = group
        if games:
            m["games"] = games
        (root / key).mkdir()
        (root / key / "module.json").write_text(json.dumps(m))
        (root / key / "tool.py").write_text('VERSION = "1.0.0"\n')

    mod("zeta", "Zeta", ["linux", "win32"])
    mod("alpha", "Alpha", ["linux", "win32"], games=["momentum", "css"])
    mod("hudb", "B Hud", ["linux", "win32"], "hud")
    mod("huda", "A Hud", ["linux", "win32"], "hud")
    mod("jhud", "JHUD", ["linux", "win32"])  # no group: LEGACY_GROUPS says hud
    mod("lin", "Linux Tool", ["linux"])
    mod("linhud", "Linux Hud", ["linux"], "hud")
    (root / "bad").mkdir()
    (root / "bad" / "module.json").write_text(json.dumps({"key": "bad", "title": "B", "os": ["linux"],
        "tag_prefix": "bad-v", "version_from": "tool.py", "needs_core": "1.0.0", "group": "fancy"}))
    (root / "bad" / "tool.py").write_text('VERSION = "1.0.0"\n')
    raises(lambda: modules.read_manifest(root / "bad"), "group must be", "an unknown group")
    for games in ([], ["tf2"], ["css", "css"], "css"):
        (root / "bad" / "module.json").write_text(json.dumps({"key": "bad", "title": "B", "os": ["linux"],
            "tag_prefix": "bad-v", "version_from": "tool.py", "needs_core": "1.0.0", "games": games}))
        raises(lambda: modules.read_manifest(root / "bad"), "games must", f"games {games!r}")
    for plat, want in [("linux", ["alpha", "lin", "zeta", "huda", "hudb", "jhud", "linhud"]),
                       ("win32", ["alpha", "zeta", "huda", "hudb", "jhud", "lin", "linhud"])]:
        mgr = modules.Manager(kit_root=root, data=TMP / f"groups-{plat}", api="http://127.0.0.1:9/none", platform=plat)
        cards = mgr.cards()
        expect([c["key"] for c in cards], ["core"] + want, f"card order on {plat}")
        expect({c["key"]: c["group"] for c in cards}["jhud"], "hud", "no group in an old JHUD: hud by LEGACY_GROUPS")
        expect({c["key"]: c["group"] for c in cards}["zeta"], "tool", "no group: a tool")
        games = {c["key"]: c["games"] for c in cards}
        expect((games["alpha"], games["zeta"], games["jhud"], games["core"]),
               (["css", "momentum"], [], ["momentum"], []),
               "games: module.json in GAMES order, none, LEGACY_GAMES, none for the core")
    expect([(c["key"], c["supported"], c["can_install"], c["os"]) for c in cards if c["key"] in ("lin", "alpha")],
           [("alpha", True, False, ["linux", "win32"]), ("lin", False, False, ["linux"])],
           "on Windows: the Linux tool unsupported, no Install (alpha is installed: a checkout)")
    raises(lambda: mgr.install("lin"), "doesn't run on this OS", "install of a Linux-only module on Windows")
    mgr.uninstall("alpha", delete_data=False)
    expect([c["key"] for c in mgr.cards()][:3], ["core", "zeta", "alpha"], "installed tools before the rest")
    expect(modules.LEGACY_GROUPS, {k: "hud" for k in ("jhud", "trainer-height", "strafe-histogram")}, "legacy groups")
    for key in modules.LEGACY_GROUPS:
        expect(modules.read_manifest(KIT / key).get("group"), "hud", f"{key}/module.json says hud itself")
    real = [f.parent.name for f in KIT.glob("*/module.json")]
    expect(set(modules.LEGACY_GAMES) <= set(real), True, "LEGACY_GAMES only names real modules")
    for key in real:
        games = modules.read_manifest(KIT / key).get("games")
        expect(bool(games), True, f"{key}/module.json says which games it works with")
        if key in modules.LEGACY_GAMES:
            expect(games, modules.LEGACY_GAMES[key], f"{key}: module.json and LEGACY_GAMES agree")
    # a release's module.json copy keeps os and group, so a card can say so before it is installed
    gh = GitHub()
    gh.release("omega-v1.0.0", "omega-module.zip", module_zip("omega", "1.0.0"),
               manifest={"title": "Omega", "summary": "s", "needs_core": "1.0.0", "os": ["linux"], "group": "hud",
                         "games": ["css"]})
    rmgr = modules.Manager(kit_root=TMP / "groups-rkit", data=TMP / "groups-rdata", api=gh.base + "/releases",
                           platform="win32")
    rmgr.check(force=True)
    c = rmgr.info("omega")
    expect((c["group"], c["supported"], c["can_install"], c["os"], c["games"]), ("hud", False, False, ["linux"], ["css"]),
           "a Linux-only release seen from Windows")
    raises(lambda: rmgr.install("omega"), "doesn't run on this OS", "install of a Linux-only release on Windows")


def fake_momentum(where):
    game = where / "momentum"
    (game / "cfg").mkdir(parents=True)
    (game / "panorama" / "layout" / "hud").mkdir(parents=True)
    (game / "panorama" / "layout" / "hud" / "timer.xml").write_text(
        "<root>\n\t<scripts>\n\t\t<include type=\"module\" src=\"file://{scripts}/hud/timer.ts\" />"
        "\n\t</scripts>\n</root>\n")
    (game / "cfg" / "autoexec.cfg").write_text("exec something\n")
    return game


def check_strafe_review_hooks():
    """Strafe Review's real hooks, from this checkout, against a fake Momentum: everything they
    write lands in the temp HOME and data folders."""
    game = fake_momentum(TMP / "sr")
    os.environ["MOMENTUM_DIR"] = str(game)
    mgr = modules.Manager(kit_root=KIT, data=TMP / "sr-data", api="http://127.0.0.1:9/none",
                          platform="linux")
    hook_link = modules.paths.data_dir("movekit") / "hooks" / "20-strafe-review"
    bin_link = TMP / "home" / ".local" / "bin" / "movekit-run"
    mgr.uninstall("strafe-review")  # nothing installed in this game yet: still fine
    expect("strafe-review" in mgr.installed(), False, "strafe-review hidden after uninstall")
    mgr.install("strafe-review")
    expect((game / "custom" / "0-strafe-review" / "panorama").is_dir(), True, "recorder installed")
    kit_timer = game / "custom" / "0-movekit" / "panorama" / "layout" / "hud" / "timer.xml"
    expect(kit_timer.is_file() and kit_timer.read_text().count("strafe-review.ts"), 1, "include in 0-movekit")
    expect((game / "custom" / "0-strafe-review" / "panorama" / "layout" / "hud" / "timer.xml").exists(), False,
           "no timer.xml in the recorder's folder")
    if "movekit:strafe-review begin" not in (game / "cfg" / "autoexec.cfg").read_text():
        fail("no autoexec block after the module install")
    if sys.platform.startswith("linux"):
        expect((hook_link.is_symlink(), bin_link.is_symlink()), (True, True), "launch hook and link")
    mgr.uninstall("strafe-review")
    expect((game / "custom" / "0-strafe-review").exists(), False, "recorder after uninstall")
    expect((game / "custom" / "0-movekit").exists(), False, "kit folder after uninstall")
    if "movekit:strafe-review" in (game / "cfg" / "autoexec.cfg").read_text():
        fail("autoexec block left after the module uninstall")
    expect(hook_link.is_symlink(), False, "launch hook after uninstall")
    # the game is gone: uninstall still finishes and takes the launch hook out
    mgr.install("strafe-review")
    shutil.rmtree(game)
    os.environ["MOMENTUM_DIR"] = str(TMP / "sr" / "gone")
    mgr.uninstall("strafe-review")
    expect(hook_link.is_symlink(), False, "launch hook after an uninstall with no game")
    expect("strafe-review" in mgr.installed(), False, "strafe-review after an uninstall with no game")
    os.environ.pop("MOMENTUM_DIR")


def check_bridge():
    """The hub's Bridge over a manager: the Modules page's calls, and the sections and page server
    following what is installed. A core section with show_with appears only with its module."""
    from movekit import hub

    gh = GitHub()
    gh.release("alpha-v1.0.0", "alpha-module.zip", module_zip("alpha", "1.0.0"))
    gh.release("alpha-v1.1.0", "alpha-module.zip", module_zip("alpha", "1.1.0"))
    core = TMP / "core"
    (core / "hud").mkdir(parents=True)
    (core / "hud" / "page.html").write_text("<!DOCTYPE html><title>x</title>")
    (core / "hud" / "hub_section.py").write_text(
        "SECTION = {'key': 'hud', 'title': 'HUD', 'os': ['linux', 'win32'], 'page': 'page.html', "
        "'api': {}, 'show_with': ['alpha']}\n")
    # show_if gets the installed modules' manifests; one that raises hides its section
    for key, test in (("extra", "lambda found: found.get('alpha', {}).get('key') == 'alpha'"),
                      ("boom", "lambda found: 1 / 0")):
        (core / key).mkdir()
        (core / key / "page.html").write_text("<!DOCTYPE html><title>x</title>")
        (core / key / "hub_section.py").write_text(
            f"SECTION = {{'key': '{key}', 'title': '{key}', 'os': ['linux', 'win32'], 'page': 'page.html', "
            f"'api': {{}}, 'show_if': {test}}}\n")
    mgr = modules.Manager(kit_root=TMP / "bkit", data=TMP / "bdata", api=gh.base + "/releases")
    served = {}
    bridge = hub.Bridge([], (), mgr, core, served)
    bridge._refresh()
    expect([s["key"] for s in bridge.sections()["sections"]], [], "sections before any module (HUD hidden)")
    r = bridge.modules("cards")
    expect((r["ok"], [c["key"] for c in r["result"]["cards"]]), (True, ["core"]), "cards before a check")
    expect(bridge.modules("check")["ok"], True, "check through the bridge")
    expect(bridge.modules("nope")["ok"], False, "an unknown module call")
    expect(bridge.modules("install", ["alpha"])["ok"], False, "args that aren't an object")
    r = bridge.modules("install", {"key": "alpha"})
    expect(r["ok"], True, f"install through the bridge: {r}")
    card = next(c for c in r["result"]["cards"] if c["key"] == "alpha")
    expect((card["installed"], card["version"], card["auto"]), (True, "1.1.0", False), "alpha's card after install")
    expect(sorted(s["key"] for s in bridge.sections()["sections"]), ["alpha", "extra", "hud"],
           "sections after install (HUD shown with alpha, extra by its show_if)")
    expect(sorted(served), ["alpha", "extra", "hud"], "the page server's sections after install")
    expect(bridge.call("alpha", "hello"), {"ok": True, "result": "1.1.0"}, "alpha's section call")
    r = bridge.modules("set_auto", {"key": "alpha", "value": True})
    expect(next(c for c in r["result"]["cards"] if c["key"] == "alpha")["auto"], True, "auto via the bridge")
    r = bridge.modules("update", {"key": "alpha"})
    expect((r["ok"], "up to date" in r["error"]), (False, True), "update with none newer: error, cards still sent")
    expect(r["result"] is not None, True, "cards in an error reply")
    bridge._mlock.acquire()
    bridge._busy = "Installing alpha"
    r = bridge.modules("check")
    expect((r["ok"], "Installing alpha" in r["error"]), (False, True), "a call while busy")
    expect(bridge.modules("cards")["result"]["busy"], "Installing alpha", "cards while busy")
    bridge._busy = None
    bridge._mlock.release()
    # a release's module.json copy names a module before it's installed, and says what core it needs
    gh.release("gamma-v1.0.0", "gamma-module.zip", module_zip("gamma", "1.0.0"),
               manifest={"title": "Gamma Tool", "summary": "does gamma things", "needs_core": "1.0.0"})
    gh.release("delta-v1.0.0", "delta-module.zip", module_zip("delta", "1.0.0", needs_core="9.0.0"),
               manifest={"title": "Delta", "needs_core": "9.0.0"})
    r = bridge.modules("check")
    cards = {c["key"]: c for c in r["result"]["cards"]}
    expect((cards["gamma"]["title"], cards["gamma"]["summary"], cards["gamma"]["can_install"]),
           ("Gamma Tool", "does gamma things", True), "gamma's card from its module.json copy")
    expect((cards["delta"]["waiting_for_core"], cards["delta"]["can_install"]), ("9.0.0", False),
           "delta needs a newer core: no install offered")
    expect(cards["alpha"]["title"], "Alpha", "alpha's card (no module.json copy) from its installed files")
    r = bridge.modules("uninstall", {"key": "alpha", "delete_data": False})
    expect(r["ok"], True, f"uninstall through the bridge: {r}")
    expect(([s["key"] for s in bridge.sections()["sections"]], sorted(served)), ([], []),
           "sections after uninstall")
    calls()


def main():
    check_own_modules()
    check_manager()
    check_checkout()
    check_groups()
    check_bridge()
    check_strafe_review_hooks()
    shutil.rmtree(TMP, ignore_errors=True)
    print("check_modules: all passed")


if __name__ == "__main__":
    main()
