#!/usr/bin/env python3
"""Checks movekit.hub without a window or pywebview: fixture sections in a temp folder.

Usage: python movekit/check_hub.py   (exits 1 on the first failure)

Covers: discovery (sidebar order, the OS filter, folders without hub_section.py ignored), broken
sections skipped and listed (syntax error, an import that fails, no SECTION, missing keys, a bad
key, two folders with one key (both refused), a page outside the folder or missing, api not
functions), two sections with a same-named helper each getting their own through local_import,
the bridge (a result, no
args, an unknown section or function, args that aren't an object, wrong arguments, a function
that raises, a result JSON can't hold, one section's calls never overlapping), and the page server
(home redirect, /web/ files, a section's page and its neighbours, path traversal and unknown
sections refused, a foreign Host header refused), and the kit's own sections loading on both OSes.
"""
import http.client
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from movekit import hub  # after the path above

PAGE = "<!DOCTYPE html><title>x</title>"


def section(root, folder, body, page="hub/index.html", files=None):
    d = root / folder
    (d / Path(page).parent).mkdir(parents=True, exist_ok=True)
    (d / page).write_text(PAGE)
    (d / "hub_section.py").write_text(body)
    for name, text in (files or {}).items():
        (d / name).write_text(text)


def spec(key, title, os='["linux", "win32"]', api="{}", page="hub/index.html", extra=""):
    return f'SECTION = {{"key": "{key}", "title": "{title}", "os": {os}, "page": "{page}", "api": {api}{extra}}}\n'


def check(cond, what):
    if not cond:
        print("FAIL:", what)
        sys.exit(1)
    print("ok  ", what)


def build(root):
    # good ones
    section(root, "gain", """\
import time
from movekit.hub import local_import
helper = local_import(__file__, "helper")
state = {"busy": 0, "overlap": False}

def add(a, b):
    return a + b

def hello():
    return {"from": helper.NAME}

def boom():
    raise ValueError("nope")

def badresult():
    return {1, 2}

def slow():
    state["busy"] += 1
    if state["busy"] > 1:
        state["overlap"] = True
    time.sleep(0.05)
    state["busy"] -= 1
    return state["overlap"]

""" + spec("gain", "Gain Converter", api='{"add": add, "hello": hello, "boom": boom, '
           '"badresult": badresult, "slow": slow}', extra=', "order": 20'),
            files={"helper.py": 'NAME = "gain"\n'})
    (root / "gain" / "hub" / "app.js").write_text("// js")
    (root / "gain" / "secret.txt").write_text("outside the page folder")
    section(root, "yaw", "from movekit.hub import local_import\nhelper = local_import(__file__, 'helper')\n"
            "def hello():\n    return {'from': helper.NAME}\n"
            + spec("yaw", "Source Yaw", os='["linux"]', api='{"hello": hello}', extra=', "order": 10'),
            files={"helper.py": 'NAME = "yaw"\n'})
    section(root, "zz-alpha", spec("alpha", "Alpha", extra=', "order": 20'))  # same order as gain: title decides
    section(root, "hud", spec("hud", "HUD"))
    section(root, "winonly", spec("winonly", "Windows thing", os='["win32"]'))
    (root / "plainfolder").mkdir()
    # broken ones
    section(root, "b-syntax", "SECTION = {\n")
    section(root, "b-import", "import no_such_module_here\n")
    section(root, "b-nosection", "X = 1\n")
    section(root, "b-missing", 'SECTION = {"key": "m", "title": "M"}\n')
    section(root, "b-badkey", spec("Bad Key", "B"))
    section(root, "b-dupe", spec("hud", "Second HUD"))
    section(root, "b-escape", spec("esc", "E", page="../gain/hub/index.html"))
    section(root, "b-nopage", spec("nop", "N", page="hub/missing.html"))
    section(root, "b-api", spec("api", "A", api='{"x": 1}'))


def get(port, path, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path, headers={"Host": host or f"127.0.0.1:{port}"})
    r = conn.getresponse()
    return r.status, r.read(), r.getheader("Location")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build(root)

        sections, problems = hub.discover(root, platform="linux")
        keys = [s.key for s in sections]
        check(keys == ["yaw", "alpha", "gain"], f"linux sections in order, Windows-only left out ({keys})")
        win, _ = hub.discover(root, platform="win32")
        check([s.key for s in win] == ["alpha", "gain", "winonly"], "win32 gets its own and no Linux-only")
        bad = dict(problems)
        expect = {"b-syntax": "SyntaxError", "b-import": "ModuleNotFoundError", "b-nosection": "not a dict",
                  "b-missing": "lacks os, page, api", "b-badkey": "bad key", "b-dupe": "also used by hud", "hud": "also used by b-dupe",
                  "b-escape": "not a file in the folder", "b-nopage": "not a file in the folder",
                  "b-api": "api must map"}
        for folder, text in expect.items():
            check(text in bad.get(folder, ""), f"{folder} skipped: {bad.get(folder)}")
        check(set(bad) == set(expect), "nothing else listed as broken (plainfolder ignored)")
        report = hub.check_sections(root / "report.json", root, platform="win32")
        check(json.loads((root / "report.json").read_text()) == report
              and report["sections"] == ["alpha", "gain", "winonly"] and len(report["problems"]) == len(expect),
              "check_sections writes the keys and problems as JSON")
        report = hub.check_sections(root / "report.json", root, platform="linux",
                                    calls=["gain.hello", 'gain.add:{"a": 2, "b": 3}', "gain.boom", "nope.x"])
        check(report["calls"]["gain.hello"] == {"ok": True, "result": {"from": "gain"}}
              and report["calls"]['gain.add:{"a": 2, "b": 3}'] == {"ok": True, "result": 5}
              and not report["calls"]["gain.boom"]["ok"] and not report["calls"]["nope.x"]["ok"],
              f"check_sections calls section functions through the bridge: {report['calls']}")

        bridge = hub.Bridge(sections, problems)
        info = bridge.sections()
        check(info["sections"][0] == {"key": "yaw", "title": "Source Yaw", "url": "/s/yaw/index.html"},
              "sections() gives key, title and page URL")
        check(len(info["problems"]) == len(expect), "sections() lists the problems")
        check(bridge.call("gain", "hello") == {"ok": True, "result": {"from": "gain"}}
              and bridge.call("yaw", "hello") == {"ok": True, "result": {"from": "yaw"}},
              "same-named helpers stay apart (local_import)")
        check("helper" not in sys.modules, "no bare 'helper' module leaked")
        check(bridge.call("gain", "add", {"a": 2, "b": 3}) == {"ok": True, "result": 5}, "call with args")
        for args, what in (([1, 2], "args that aren't an object"), ({"a": 1}, "missing argument"),
                           ({"a": 1, "b": 2, "c": 3}, "extra argument")):
            r = bridge.call("gain", "add", args)
            check(r["ok"] is False and r["error"], f"{what}: {r}")
        for k, n, text in (("nope", "add", "no section"), ("gain", "nope", "no function"),
                           ("gain", "boom", "ValueError: nope"), ("gain", "badresult", "not JSON serializable"),
                           ("winonly", "x", "no section")):
            r = bridge.call(k, n)
            check(r["ok"] is False and text in r["error"], f"{k}.{n} refused: {r['error']}")
        public = [a for a in dir(bridge) if not a.startswith("_")]
        check(sorted(public) == ["call", "modules", "sections"],
              f"only call(), sections() and modules() are public: {public}")
        r = bridge.modules("cards")
        check(r == {"ok": False, "error": "no module manager"}, f"modules() with no manager: {r}")

        results = []
        threads = [threading.Thread(target=lambda: results.append(bridge.call("gain", "slow"))) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        check(all(r == {"ok": True, "result": False} for r in results), "one section's calls never overlap")

        server = hub.serve(sections)
        port = server.server_address[1]
        try:
            time.sleep(0.05)
            status, _, loc = get(port, "/")
            check(status == 302 and loc == "/web/home.html", "/ goes to the home page")
            status, body, _ = get(port, "/web/hub.js")
            check(status == 200 and b"hub.call" in body, "/web/hub.js served")
            check(get(port, "/web/home.html")[0] == 200 and get(port, "/web/hub.css")[0] == 200, "home and CSS served")
            status, body, _ = get(port, "/s/gain/index.html")
            check(status == 200 and body.decode() == PAGE, "section page served")
            check(get(port, "/s/gain/app.js")[0] == 200, "files next to the page served")
            for path in ("/s/gain/../secret.txt", "/s/gain/%2e%2e/secret.txt", "/s/gain/..%2fsecret.txt",
                         "/s/gain/../hub_section.py", "/web/../hub.py", "/s/winonly/index.html",
                         "/s/nope/index.html", "/elsewhere", "/s/gain/"):
                check(get(port, path)[0] == 404, f"{path} refused")
            check(get(port, "/web/hub.js", host=f"evil.example:{port}")[0] == 403, "foreign Host refused")
        finally:
            server.shutdown()
    # the real kit: every section loads, on both OSes
    for plat in ("linux", "win32"):
        real, probs = hub.discover(hub.KIT, platform=plat)
        check(not probs and "gain-converter" in [s.key for s in real], f"the kit's own sections load on {plat}: "
              f"{[s.key for s in real]} {probs}")
    print("all hub checks passed")


if __name__ == "__main__":
    main()
