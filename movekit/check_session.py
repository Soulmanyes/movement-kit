#!/usr/bin/env python3
"""Checks movekit.session on temp logs and a local port; no game needed.

Usage: python movekit/check_session.py   (exits 1 on the first failure)

Covers: the bus (ids, history for late subscribers, its limit, unsubscribe), tokens (run-together
echoes, a token cut off mid-write, one at the line end, chat ignored, look-alikes), the session's
map and token events for Momentum and CS:S lines, start="end", an emptied log, and over HTTP:
/status, /events, a reconnect with Last-Event-ID, a foreign Host refused, CORS for localhost pages
only, and a second start() on a taken port. join(): hosting on a free port, listening to a session
of the same log, a private session when the port serves another log, and a listener taking over
when the host closes.
"""
import json
import queue
import socket
import sys
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from movekit import session  # after the path above


def check(what, got, want):
    if got != want:
        sys.exit(f"FAIL {what}: got {got!r}, want {want!r}")
    print(f"ok   {what}")


def kinds(events):
    return [(e["type"], e["data"]["name"]) if "name" in e["data"] else (e["type"],) for e in events]


def write(path, data, mode="ab"):
    with open(path, mode) as f:
        f.write(data)


def check_bus():
    bus = session.Bus(history=3)
    early = bus.subscribe()
    for i in range(5):
        bus.publish("n", i=i)
    check("bus ids", bus.last_id, 5)
    check("early subscriber gets all", [early.get_nowait()["data"]["i"] for _ in range(5)], [0, 1, 2, 3, 4])
    late = bus.subscribe(after=1)
    check("late subscriber: only kept ones after its id", [late.get_nowait()["id"] for _ in range(3)], [3, 4, 5])
    stale = bus.subscribe(after=137)
    check("id from before a restart: all kept ones", [stale.get_nowait()["id"] for _ in range(3)], [3, 4, 5])
    bus.unsubscribe(stale)
    check("listeners", bus.listeners, 2)
    bus.unsubscribe(early)
    bus.publish("n", i=5)
    check("unsubscribed queue gets nothing", early.empty(), True)
    check("listeners after unsubscribe", bus.listeners, 1)


def check_tokens():
    t = session.TokenScanner()
    check("run together", t.scan("YAW_60 YAW_90", True), ["YAW_60", "YAW_90"])
    check("then other text", t.scan("YAW_60 [Timer] go", True), ["YAW_60"])
    check("cut off: not yet", t.scan("YAW_21", False), [])
    check("cut off: once followed", t.scan("YAW_210 ", False), ["YAW_210"])
    check("same line ends: not twice", t.scan("YAW_210 \r", True), [])
    check("at line end", t.scan("YAW_45", True), ["YAW_45"])
    check("decimal speed", t.scan("YAW_62.5 ", True), ["YAW_62.5"])
    check("offsets toggle", t.scan("SY_OFFSETS\r", True), ["SY_OFFSETS"])
    check("surf list and mode switch", t.scan("SY_MODE_SURF YAWSURF_30.5 SY_MODE_BHOP", True),
          ["SY_MODE_SURF", "YAWSURF_30.5", "SY_MODE_BHOP"])
    check("mode look-alikes", t.scan("SY_MODE_KZ YAWSURF_ xSY_MODE_SURF", True), [])
    check("chat ignored", t.scan("Bob :  YAW_60 SY_OFFSETS", True), [])
    check("name before chat counts", t.scan("YAW_60 : x", True), ["YAW_60"])
    check("look-alikes", t.scan("xYAW_60 YAW_60abc SY_OFFSETSX MY_SY_OFFSETS", True), [])
    t.scan("YAW_90 YAW", False)
    check("grows from a half line", t.scan("YAW_90 YAW_120\r", True), ["YAW_120"])


def check_session(tmp):
    log = Path(tmp) / "yaw.log"
    write(log, b"Host_NewGame on map old_map\nYAW_60\n", "wb")
    s = session.Session(log)
    check("start=end: old lines skipped", s.poll(), [])
    check("state unknown", (s.in_map, s.map), (None, None))
    write(log, b"Host_NewGame on map surf_Utopia\r\nYAW_9")
    check("Momentum map", kinds(s.poll()), [("map_loaded", "surf_utopia")])
    check("in a map", (s.in_map, s.map), (True, "surf_utopia"))
    write(log, b"0 ")
    check("token before its line break", kinds(s.poll()), [("token", "YAW_90")])
    write(log, b"\r\nHost_ShutdownServer\r\nDisconnect: bye\r\n")
    check("left once", kinds(s.poll()), [("map_left",)])
    check("in the menu", (s.in_map, s.map), (False, None))
    write(log, b"Connected to 1.2.3.4:27015\nMap: bhop_eazy\nConnected to 1.2.3.4:27015\n")
    check("CS:S join: connect then map name", kinds(s.poll()),
          [("map_loaded", None), ("map_loaded", "bhop_eazy")])
    write(log, b"YAW", "wb")  # emptied by the launch, then a new half line
    s.poll()
    write(log, b"_30 SY_OFFSETS\n")
    check("emptied log: read from the top", kinds(s.poll()), [("token", "YAW_30"), ("token", "SY_OFFSETS")])
    s2 = session.Session(log, start="begin")
    check("start=begin reads it all", kinds(s2.poll()), [("token", "YAW_30"), ("token", "SY_OFFSETS")])
    check("status", (s.status()["inMap"], s.status()["map"]), (True, "bhop_eazy"))
    return log


def get(url, headers=None):
    with urlopen(Request(url, headers=headers or {}), timeout=5) as resp:
        return resp.status, dict(resp.headers), resp.read()


def check_http(log):
    got = session.start(log, port=0, poll=0.01)
    check("start: serves", got is not None, True)
    s, server = got
    port = server.server_address[1]
    base = f"http://127.0.0.1:{port}"
    code, _, body = get(base + "/status")
    check("/status", (code, json.loads(body)["log"]), (200, str(log)))
    try:
        get(base + "/status", {"Host": "evil.example:80"})
        sys.exit("FAIL foreign Host: no 403")
    except HTTPError as e:
        check("foreign Host refused", e.code, 403)
    _, h, _ = get(base + "/status", {"Origin": f"http://127.0.0.1:{port - 1}"})
    check("CORS for a localhost page", h.get("Access-Control-Allow-Origin"), f"http://127.0.0.1:{port - 1}")
    _, h, _ = get(base + "/status", {"Origin": "http://evil.example"})
    check("no CORS for other pages", h.get("Access-Control-Allow-Origin"), None)

    stop = threading.Event()
    stream = session.listen(base, stop=stop)
    first = []
    reader = threading.Thread(target=lambda: first.extend(e for _, e in zip(range(2), stream)))
    reader.start()
    while s.bus.listeners == 0:
        threading.Event().wait(0.01)
    write(log, b"Host_NewGame on map bhop_a\nSY_OFFSETS\n")
    reader.join(5)
    check("events over HTTP", kinds(first), [("map_loaded", "bhop_a"), ("token", "SY_OFFSETS")])
    stop.set()
    stream.close()

    last = first[-1]["id"]
    s.bus.publish("attempt_saved", dir="bhop_a", id="x1")
    s.bus.publish("game_exit")
    again = session.listen(base, after=last)
    missed = [next(again), next(again)]
    again.close()
    check("reconnect gets what it missed", [e["type"] for e in missed], ["attempt_saved", "game_exit"])
    check("event id kept, data apart", (missed[0]["id"] - last, missed[0]["data"]), (1, {"dir": "bhop_a", "id": "x1"}))

    check("second start on the same port: None", session.start(log, port=port), None)
    down = session.listen("http://127.0.0.1:9", retry=0.01)
    check("no session: listen yields None", next(down), None)
    down.close()
    server.shutdown()
    s.stop.set()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def take(joined, timeout=5):
    try:
        return kinds([joined.events.get(timeout=timeout)])[0]
    except queue.Empty:
        return None


def wait_for(cond, timeout=5):
    end = threading.Event()
    for _ in range(int(timeout / 0.01)):
        if cond():
            return True
        end.wait(0.01)
    return False


def check_join(tmp):
    port = free_port()
    log_a, log_b = Path(tmp) / "a.log", Path(tmp) / "b.log"
    write(log_a, b"old\n", "wb")
    write(log_b, b"", "wb")
    a = session.join(log_a, port=port, poll=0.01, retry=0.05)
    check("join on a free port: host", a.mode, "host")
    b = session.join(log_a, port=port, poll=0.01, retry=0.05)
    check("join, same log served: listen", b.mode, "listen")
    c = session.join(log_b, port=port, poll=0.01, retry=0.05)
    check("join, another log served: private", c.mode, "private")
    wait_for(lambda: a.session.bus.listeners >= 2)  # a's own pump and b's stream
    write(log_a, b"YAW_210\n")
    write(log_b, b"SY_OFFSETS\n")
    check("host gets its log's events", take(a), ("token", "YAW_210"))
    check("listener gets them too", take(b), ("token", "YAW_210"))
    check("private gets its own log's", take(c), ("token", "SY_OFFSETS"))
    check("private gets nothing of the other log", take(c, 0.3), None)
    a.close()
    check("listener takes over when the host closes", wait_for(lambda: b.mode == "host"), True)
    write(log_a, b"Host_NewGame on map bhop_b\n")
    check("and reads the log itself", take(b), ("map_loaded", "bhop_b"))
    b.close()
    c.close()
    check("closed host frees the port", session.status(f"http://127.0.0.1:{port}", timeout=0.5), None)


def main():
    check_bus()
    check_tokens()
    with tempfile.TemporaryDirectory() as tmp:
        check_http(check_session(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        check_join(tmp)
    print("all session checks passed")


if __name__ == "__main__":
    main()
