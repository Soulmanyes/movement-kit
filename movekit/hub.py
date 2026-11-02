"""The hub: one settings window with a section per tool (Phase 3 in PLAN.md).

A section is a folder at the kit root (sourceyaw/, gain-converter/, hud/, ...) with a
hub_section.py that sets

  SECTION = {
      "key":   "gain",                  # unique, [a-z0-9-]; the page's URL is /s/<key>/
      "title": "Gain Converter",        # the sidebar label
      "os":    ["linux", "win32"],      # sys.platform prefixes it runs on
      "page":  "hub/index.html",        # relative to the folder; its folder is served at /s/<key>/
      "api":   {"convert": convert},    # plain functions: JSON-able keyword args in, JSON-able out
      "order": 20,                      # optional, sidebar position (then title)
      "show_with": ["strafe-review"],   # optional: shown only while one of these modules is installed
  }

Sections come from two places (3.7b in PLAN.md): the core's own folders (hud/; any folder at the kit
root without a module.json) and the installed modules (movekit/modules.py's Manager.roots()). The
home page is the Modules page, where each module is installed, updated, rolled back and uninstalled;
pages reach the manager through Bridge.modules(name, args).

The hub finds sections by folder and never imports tool internals; a new tool is a new folder.
A section that fails to load (syntax error, missing keys, a key another folder also uses) is skipped and
listed under problems(), so one broken tool doesn't take the window down.

Section pages call Python as  await hub.call(name, args)  (movekit/web/hub.js), which goes through
pywebview's bridge to Bridge.call(key, name, args). Every reply is {"ok": true, "result": ...} or
{"ok": false, "error": "..."}. pywebview runs each call on a worker thread; the hub holds one lock
per section, so a section's functions never run at the same time as each other.

Imports inside a section: hub_section.py is loaded under its own module name, and the section
folder is NOT put on sys.path, because tool folders share file names (updater.py is in sourceyaw/
and movekit/). A section imports its own helper modules with
  helper = local_import(__file__, "helper")
which loads <folder>/helper.py by path under a name of its own. The kit root is on sys.path, so
`movekit` and `hud` (packages with an __init__.py) are importable as usual.

Pages are served from 127.0.0.1 on a free port: /web/... is movekit/web/ (shared CSS and JS),
/s/<key>/... is the section page's folder. Live game events come from the session on 8766 over SSE,
which allows localhost origins.

This is the one movekit module that needs a third-party package, pywebview, and only for run():
discovery, the bridge and the page server are stdlib and run without a window (check_hub.py).
"""
import argparse
import importlib.util
import json
import mimetypes
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

KIT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))  # repo root or exe root
if str(KIT) not in sys.path:
    sys.path.insert(1, str(KIT))  # run as movekit/hub.py: sections import movekit and hud from the kit root
WEB = Path(__file__).resolve().parent / "web"
TITLE = "Soulmanyes's Movement Kit"
APP_ID = "io.github.soulmanyes.MovementKit"  # Linux app id; install-hub.sh names the launcher after it
REQUIRED = ("key", "title", "os", "page", "api")
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class Section:
    def __init__(self, folder, spec):
        self.folder = folder
        self.key = spec["key"]
        self.title = spec["title"]
        self.os = list(spec["os"])
        self.page = folder / spec["page"]
        self.api = dict(spec["api"])
        self.order = spec.get("order", 100)
        self.show_with = list(spec.get("show_with", []))
        self.lock = threading.Lock()

    def info(self):
        return {"key": self.key, "title": self.title, "url": f"/s/{self.key}/{self.page.name}"}


def _module_name(folder, name="hub_section"):
    return "movekit_section_" + re.sub(r"\W", "_", folder.name) + "." + name


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def local_import(section_file, name):
    """Load <folder of section_file>/<name>.py by path, under a module name only this folder uses."""
    folder = Path(section_file).resolve().parent
    full = _module_name(folder, name)
    if full in sys.modules:
        return sys.modules[full]
    return _load(folder / f"{name}.py", full)


def _check(spec, folder):
    if not isinstance(spec, dict):
        return "SECTION is not a dict"
    missing = [k for k in REQUIRED if k not in spec]
    if missing:
        return "SECTION lacks " + ", ".join(missing)
    if not isinstance(spec["key"], str) or not KEY_RE.match(spec["key"]):
        return f"bad key {spec['key']!r}"
    if not isinstance(spec["os"], (list, tuple)) or not all(isinstance(o, str) for o in spec["os"]):
        return "os must be a list of sys.platform prefixes"
    if not isinstance(spec["api"], dict) or not all(callable(f) for f in spec["api"].values()):
        return "api must map names to functions"
    show = spec.get("show_with", [])
    if not isinstance(show, (list, tuple)) or not all(isinstance(k, str) and KEY_RE.match(k) for k in show):
        return "show_with must list module keys"
    page = (folder / str(spec["page"])).resolve()
    if not page.is_relative_to(folder.resolve()) or not page.is_file():
        return f"page {spec['page']!r} is not a file in the folder"
    return None


def discover(root=KIT, platform=sys.platform, folders=None):
    """(sections for this OS in sidebar order, problems as [(folder name, text)]), from the
    subfolders of root, or from the given folders."""
    found, problems = [], []
    if folders is None:
        folders = sorted(p for p in Path(root).iterdir() if p.is_dir())
    for folder in folders:
        file = folder / "hub_section.py"
        if not file.is_file():
            continue
        try:
            spec = getattr(_load(file, _module_name(folder)), "SECTION", None)
        except Exception as e:  # noqa: BLE001 - a broken section must not stop the others
            problems.append((folder.name, f"{type(e).__name__}: {e}"))
            continue
        error = _check(spec, folder)
        if error:
            problems.append((folder.name, error))
        else:
            found.append((folder, spec))
    # two folders with one key: neither wins, so the clash shows instead of whichever sorts first
    owners = {}
    for folder, spec in found:
        owners.setdefault(spec["key"], []).append(folder.name)
    sections = []
    for folder, spec in found:
        names = owners[spec["key"]]
        if len(names) > 1:
            problems.append((folder.name, f"key {spec['key']!r} also used by "
                             + ", ".join(n for n in names if n != folder.name)))
        elif any(platform.startswith(o) for o in spec["os"]):
            sections.append(Section(folder, spec))
    sections.sort(key=lambda s: (s.order, s.title.lower()))
    return sections, problems


def core_folders(root=KIT):
    """The core's own section folders: those at root with no module.json (hud/)."""
    return [p for p in sorted(Path(root).iterdir())
            if p.is_dir() and not (p / "module.json").is_file()]


def kit_sections(manager, root=KIT, platform=sys.platform):
    """discover() over the core's folders and the installed modules, leaving out sections whose
    show_with names no installed module."""
    roots = manager.roots()
    folders = core_folders(root) + [f for f in roots if f.resolve() not in
                                    {c.resolve() for c in core_folders(root)}]
    sections, problems = discover(root, platform, folders)
    installed = set(manager.installed())
    sections = [s for s in sections if not s.show_with or installed & set(s.show_with)]
    problems += [(f, f"module.json: {e}") for f, e in manager.problems()]
    return sections, problems


class Bridge:
    """What pages reach as pywebview.api. Only call(), sections() and modules() are public;
    pywebview exposes every public attribute, so everything else here starts with an underscore.

    With a manager (movekit/modules.py), the sections follow what is installed: an install,
    uninstall, update or roll back rediscovers them, and the page server sees the change."""

    _MODULE_CALLS = ("cards", "check", "install", "update", "update_all", "rollback", "uninstall",
                    "set_auto")

    def __init__(self, sections, problems=(), manager=None, root=KIT, served=None):
        self._manager = manager
        self._root = root
        self._served = served if served is not None else {}  # key -> Section, read by the page server
        self._mlock = threading.Lock()
        self._busy = None  # what the manager is doing, shown on the Modules page
        self._last = {}    # the last auto update's results
        self._set(sections, problems)

    def _set(self, sections, problems):
        self._sections = {s.key: s for s in sections}
        self._order = list(sections)
        self._problems = list(problems)
        self._served.clear()
        self._served.update(self._sections)

    def _refresh(self):
        if self._manager is not None:
            self._set(*kit_sections(self._manager, self._root))

    def _cards(self):
        m = self._manager
        return {"cards": m.cards(), "busy": self._busy, "checked": m.state.get("checked"),
                "auto_results": self._last, "checkout": m.checkout}

    def _auto_update(self):
        """Run at start in a thread: the auto-update of every module whose switch is on."""
        if self._manager is None:
            return
        with self._mlock:
            self._busy = "Checking for updates"
            try:
                self._last = self._manager.auto_update()
                if self._last:
                    self._refresh()
            finally:
                self._busy = None

    def modules(self, name, args=None):
        """The Modules page's calls: cards, check, install(key), update(key), update_all,
        rollback(key), uninstall(key, delete_data), set_auto(key, value). Every reply carries the
        cards as they are after the call."""
        m = self._manager
        if m is None:
            return {"ok": False, "error": "no module manager"}
        if name not in self._MODULE_CALLS:
            return {"ok": False, "error": f"no module call {name!r}"}
        args = args or {}
        if not isinstance(args, dict):
            return {"ok": False, "error": "args must be an object"}
        if name == "cards":
            return {"ok": True, "result": self._cards()}
        if not self._mlock.acquire(blocking=False):
            return {"ok": False, "error": f"{self._busy or 'Busy'}; try again in a moment"}
        try:
            self._busy = {"check": "Checking for updates", "update_all": "Updating"}.get(
                name, f"{name.replace('_', ' ').capitalize()} {args.get('key', '')}".strip())
            if name == "check":
                m.check(force=True)
            elif name == "update_all":
                errors = {k: e for k, e in m.update_all().items() if e}
                self._refresh()
                if errors:
                    raise RuntimeError("; ".join(f"{k}: {e}" for k, e in errors.items()))
            else:
                getattr(m, name)(**args)
                if name != "set_auto":
                    self._refresh()
        except TypeError as e:
            return {"ok": False, "error": f"modules.{name}: {e}", "result": self._cards_safe()}
        except Exception as e:  # noqa: BLE001 - the card shows the error, the window stays up
            return {"ok": False, "error": str(e) or type(e).__name__, "result": self._cards_safe()}
        finally:
            self._busy = None
            self._mlock.release()
        return {"ok": True, "result": self._cards()}

    def _cards_safe(self):
        try:
            return self._cards()
        except Exception:  # noqa: BLE001 - the error reply is what matters
            return None

    def sections(self):
        return {"title": TITLE, "sections": [s.info() for s in self._order],
                "problems": [{"folder": f, "error": e} for f, e in self._problems]}

    def call(self, key, name, args=None):
        section = self._sections.get(key)
        if section is None:
            return {"ok": False, "error": f"no section {key!r}"}
        func = section.api.get(name)
        if func is None:
            return {"ok": False, "error": f"{key} has no function {name!r}"}
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return {"ok": False, "error": "args must be an object"}
        try:
            with section.lock:
                result = func(**args)
            json.dumps(result)
        except TypeError as e:  # wrong arguments, or a result JSON can't hold
            return {"ok": False, "error": f"{key}.{name}: {e}"}
        except Exception as e:  # noqa: BLE001 - the page shows the error, the window stays up
            return {"ok": False, "error": f"{key}.{name}: {type(e).__name__}: {e}"}
        return {"ok": True, "result": result}


def _local_hosts(port):
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


class _Pages(BaseHTTPRequestHandler):
    sections = None  # key -> Section, set by serve()

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        # a page on another site could reach localhost through a DNS name of its own; refuse those
        if self.headers.get("Host") not in _local_hosts(self.server.server_address[1]):
            return self._send(403, b"forbidden", "text/plain")
        path = unquote(urlsplit(self.path).path)
        if path == "/":
            return self._redirect("/web/home.html")
        parts = path.lstrip("/").split("/")
        if parts[0] == "web":
            base, rest = WEB, parts[1:]
        elif parts[0] == "s" and len(parts) > 2 and parts[1] in self.sections:
            base, rest = self.sections[parts[1]].page.parent, parts[2:]
        else:
            return self._send(404, b"not found", "text/plain")
        base = base.resolve()
        file = base.joinpath(*rest).resolve()
        if not file.is_relative_to(base) or not file.is_file():
            return self._send(404, b"not found", "text/plain")
        kind = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        self._send(200, file.read_bytes(), kind)

    def _redirect(self, to):
        self.send_response(302)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send(self, code, data, kind):
        self.send_response(code)
        self.send_header("Content-Type", kind + ("; charset=utf-8" if kind.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def serve(sections, port=0):
    """Serve the pages on 127.0.0.1 in a daemon thread; returns the server (.server_address[1]).
    sections is a list, or a key -> Section dict the caller keeps current (Bridge with a manager)."""
    if not isinstance(sections, dict):
        sections = {s.key: s for s in sections}
    handler = type("Pages", (_Pages,), {"sections": sections})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# GDK button -> MouseEvent.button for the mouse side buttons (back, forward)
SIDE_BUTTONS = {8: 3, 9: 4}
# a mousedown and mouseup with that button where the pointer is, as a page would have got them
SIDE_BUTTON_JS = """(function (x, y, b) {
    var t = document.elementFromPoint(x, y) || document.body;
    var o = {button: b, clientX: x, clientY: y, bubbles: true, cancelable: true, composed: true};
    t.dispatchEvent(new MouseEvent("mousedown", o));
    t.dispatchEvent(new MouseEvent("mouseup", o));
})(%d, %d, %d);"""


def _side_buttons(window):
    """WebKitGTK hands pages the mouse side buttons as button 0, the left button (Source Yaw's key
    capture read them as mouse1). Catch them on the GTK widget before WebKit does and send the page
    the mousedown with the right button instead; WebKit never sees them, so they don't go back or
    forward either. Runs on pywebview's shown event; the hookup itself runs on GTK's thread."""
    from gi.repository import Gdk, GLib, Gtk

    def find(widget):
        if type(widget).__name__ == "WebView":
            return widget
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                found = find(child)
                if found:
                    return found
        return None

    def press(view, event):
        button = SIDE_BUTTONS.get(event.button)
        if button is None:
            return False
        if event.type == Gdk.EventType.BUTTON_PRESS:  # not the extra double-click events
            view.run_javascript(SIDE_BUTTON_JS % (int(event.x), int(event.y), button), None, None, None)
        return True

    def hook():
        view = find(window.native) if window.native else None
        if view is None:
            print("hub: no WebKit view found; mouse side buttons reach pages as the left button", file=sys.stderr)
            return False
        view.connect("button-press-event", press)
        view.connect("button-release-event", lambda _view, event: event.button in SIDE_BUTTONS)
        return False

    GLib.idle_add(hook)


def check_sections(out, root=KIT, platform=sys.platform, calls=()):
    """Write {"sections": [keys], "problems": [[folder, text]], "calls": {...}} to the file out, with
    no window. For the hub exe's smoke test, which has no console to print to. calls are
    "key.name" or "key.name:{json args}", run through the Bridge as a page would; "calls" maps each
    to its reply. Returns the dict."""
    sections, problems = discover(root, platform)
    report = {"sections": [s.key for s in sections], "problems": [list(p) for p in problems]}
    if calls:
        bridge = Bridge(sections, problems)
        report["calls"] = {}
        for call in calls:
            target, _, args = call.partition(":")
            key, _, name = target.partition(".")
            report["calls"][call] = bridge.call(key, name, json.loads(args) if args else None)
    Path(out).write_text(json.dumps(report), encoding="utf-8")
    return report


def make_manager(root=KIT, kit_root=None, data=None):
    """The module manager the window uses. With --root (fixtures), modules live in that root too."""
    # here, not at the top: only a window needs the manager
    from movekit import modules

    api = os.environ.get("MOVEKIT_MODULES_API", modules.API)  # tests point it at a fake GitHub
    return modules.Manager(kit_root=kit_root or (root if root != KIT else None), data=data, api=api)


def run(root=KIT, app_class=None, debug=False, first=None, manager=None):
    """Open the hub window, on section `first` if given; returns when it closes."""
    try:
        import webview
    except ImportError:
        sys.exit("The hub needs pywebview: `sudo pacman -S python-pywebview` on Arch,"
                 " `pip install pywebview` elsewhere.")
    manager = manager or make_manager(root)
    served = {}
    bridge = Bridge([], (), manager, root, served)
    bridge._refresh()
    for folder, error in bridge._problems:
        print(f"hub: skipped {folder}: {error}", file=sys.stderr)
    sections = bridge._order
    server = serve(served)
    if sys.platform.startswith("linux"):
        # the Wayland app id / X11 class of the GTK window, which docks match to the launcher
        from gi.repository import GLib
        GLib.set_prgname(app_class or APP_ID)
    start = next((s.info()["url"] for s in sections if s.key == first), "/")
    window = webview.create_window(TITLE, f"http://127.0.0.1:{server.server_address[1]}{start}",
                                   js_api=bridge, width=1000, height=720,
                                   min_size=(640, 480), background_color="#15171c")
    if sys.platform.startswith("linux"):
        window.events.shown += lambda: _side_buttons(window)
    window.events.shown += lambda: threading.Thread(target=bridge._auto_update, daemon=True).start()
    webview.start(debug=debug)
    server.shutdown()


def main():
    ap = argparse.ArgumentParser(description=f"{TITLE}: the settings hub.")
    ap.add_argument("--root", type=Path, default=KIT, help="folder whose subfolders hold the sections")
    ap.add_argument("--class", dest="app_class", help=f"window class / app id, default {APP_ID} (tests use *-test)")
    ap.add_argument("--debug", action="store_true", help="allow the web inspector")
    ap.add_argument("--section", help="open on this section's page (screenshot checks)")
    ap.add_argument("--check-sections", metavar="FILE", type=Path,
                    help="write the sections found to FILE as JSON and exit, with no window")
    ap.add_argument("--call", action="append", default=[], metavar="KEY.NAME[:JSON]",
                    help="with --check-sections: also call this section function and write its reply")
    args = ap.parse_args()
    if args.check_sections:
        check_sections(args.check_sections, args.root, calls=args.call)
        return
    run(args.root, args.app_class, args.debug, args.section)


if __name__ == "__main__":
    main()
