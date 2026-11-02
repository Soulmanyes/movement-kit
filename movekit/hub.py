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
  }

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
    page = (folder / str(spec["page"])).resolve()
    if not page.is_relative_to(folder.resolve()) or not page.is_file():
        return f"page {spec['page']!r} is not a file in the folder"
    return None


def discover(root=KIT, platform=sys.platform):
    """(sections for this OS in sidebar order, problems as [(folder name, text)])."""
    found, problems = [], []
    for folder in sorted(p for p in Path(root).iterdir() if p.is_dir()):
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


class Bridge:
    """What pages reach as pywebview.api. Only call() and sections() are public; pywebview exposes
    every public attribute, so everything else here starts with an underscore."""

    def __init__(self, sections, problems=()):
        self._sections = {s.key: s for s in sections}
        self._order = list(sections)
        self._problems = list(problems)

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
    """Serve the pages on 127.0.0.1 in a daemon thread; returns the server (.server_address[1])."""
    handler = type("Pages", (_Pages,), {"sections": {s.key: s for s in sections}})
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


def run(root=KIT, app_class=None, debug=False, first=None):
    """Open the hub window, on section `first` if given; returns when it closes."""
    try:
        import webview
    except ImportError:
        sys.exit("The hub needs pywebview: `sudo pacman -S python-pywebview` on Arch,"
                 " `pip install pywebview` elsewhere.")
    sections, problems = discover(root)
    for folder, error in problems:
        print(f"hub: skipped {folder}/hub_section.py: {error}", file=sys.stderr)
    server = serve(sections)
    if sys.platform.startswith("linux"):
        # the Wayland app id / X11 class of the GTK window, which docks match to the launcher
        from gi.repository import GLib
        GLib.set_prgname(app_class or APP_ID)
    start = next((s.info()["url"] for s in sections if s.key == first), "/")
    window = webview.create_window(TITLE, f"http://127.0.0.1:{server.server_address[1]}{start}",
                                   js_api=Bridge(sections, problems), width=1000, height=720,
                                   min_size=(640, 480), background_color="#15171c")
    if sys.platform.startswith("linux"):
        window.events.shown += lambda: _side_buttons(window)
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
