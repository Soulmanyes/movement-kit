"""The game session: yaw.log read once, turned into events, sent to every tool that listens.

Session(log).poll() reads what the game wrote since the last call (movekit.logtail) and publishes
events on its Bus:
  map_loaded {name}  a map started loading (name is None for CS:S's "Connected to" line)
  map_left           the game went back to its menu
  token {name}       a marker a tool's bind echoes (YAW_<speed>, SY_OFFSETS). It counts as soon as
                     something follows it, without waiting for the line break, which the console
                     sometimes leaves out for a while. Chat ("Name :  text") is ignored.
Tools add their own with Bus.publish(): the Strafe Review collector sends attempt_saved {dir, id}
and the launch wrapper game_exit.

serve(session) offers the events on http://127.0.0.1:8766 (localhost only):
  GET /events   server-sent events: "id: <n>", "event: <type>", "data: <json>". A client that
                reconnects with Last-Event-ID (or ?after=<n>) gets the ones it missed, if still kept.
  GET /status   {log, inMap, map, lastId, listeners}
A process that wants the session calls start(log). It gets (session, server), or None when the port
is taken: another process (the Strafe Review server, or `python -m movekit.session`) already has one,
and this one only listens with listen().

Stdlib only; works on Linux and Windows.
"""
import argparse
import json
import queue
import re
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

if __package__ in (None, ""):  # run as a script: python movekit/session.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from movekit import logtail  # after the path above

HOST = "127.0.0.1"
PORT = 8766
URL = f"http://{HOST}:{PORT}"
POLL = 0.05  # seconds between log reads; tokens should show within a frame or so
HISTORY = 500  # events kept for clients that reconnect
PING = 15  # seconds between keep-alive comments on /events
LISTEN_TIMEOUT = 2 * PING + 5  # a client gives up on a stream this quiet and reconnects
# markers the tools' binds echo into the console: Source Yaw's yaw_cycle and the trainer's toggle
TOKENS = (r"YAW_\d+(?:\.\d+)?", r"SY_OFFSETS")


class Bus:
    """Events in order: {"id": 1, 2, ..., "type", "time", "data": {...}}. Every subscriber gets its
    own queue; the last HISTORY events are kept for late or reconnecting subscribers."""

    def __init__(self, history=HISTORY):
        self._lock = threading.Lock()
        self._subs = set()
        self._history = deque(maxlen=history)
        self.last_id = 0

    def publish(self, kind, **data):
        """Send an event of type `kind` with `data` (JSON-able) to every subscriber; returns it."""
        with self._lock:
            self.last_id += 1
            event = {"id": self.last_id, "type": kind, "time": time.time(), "data": data}
            self._history.append(event)
            for q in self._subs:
                q.put(event)
        return event

    def subscribe(self, after=None):
        """A queue of every event from now on, plus the kept ones after id `after` if given."""
        q = queue.SimpleQueue()
        with self._lock:
            if after is not None and after > self.last_id:
                after = 0  # an id from before the session restarted: everything kept is new
            if after is not None:
                for event in self._history:
                    if event["id"] > after:
                        q.put(event)
            self._subs.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._subs.discard(q)

    @property
    def listeners(self):
        return len(self._subs)


class TokenScanner:
    """Finds the tokens in one console line at a time, also while the line is still being written.
    A token counts once a character that can't be part of it follows (echo writes "YAW_210 "), or
    the line ends. Each token is reported once per line."""

    def __init__(self, tokens=TOKENS):
        body = r"(?<![A-Za-z0-9_])(" + "|".join(tokens) + r")"
        self._partial = re.compile(body + r"(?=[^0-9A-Za-z_.])")
        self._complete = re.compile(body + r"(?=[^0-9A-Za-z_.]|\Z)")
        self._done = 0  # where the tokens already reported end, in the current line

    def scan(self, text, complete):
        """The new tokens in the current line `text` (all of it so far). complete: the line ended."""
        text = text.split(" : ", 1)[0]  # chat looks like "Name :  text"; ignore what players type
        if len(text) < self._done:  # not the line seen so far (the log started over)
            self._done = 0
        found = []
        for m in (self._complete if complete else self._partial).finditer(text, self._done):
            found.append(m.group(1))
            self._done = m.end()
        if complete:
            self._done = 0
        return found

    def reset(self):
        self._done = 0


class Session:
    """yaw.log as events. start="end" skips what the log already holds (an earlier game run)."""

    def __init__(self, log, bus=None, tokens=TOKENS, start="end"):
        self.log = Path(log)
        self.bus = bus or Bus()
        self.in_map = None  # unknown until the log says
        self.map = None
        self._tail = logtail.LogTail(self.log, start)
        self._tokens = TokenScanner(tokens)
        self._opened = self._tail.opened

    def poll(self):
        """Read the log once and publish what it says. Returns the events published."""
        out = []
        while True:
            got = self._tail.lines()
            if self._tail.opened != self._opened:  # a new or emptied log: no half line carried over
                self._opened = self._tail.opened
                self._tokens.reset()
            if not got:
                break
            for line in got:
                out += self._line(line)
        for name in self._tokens.scan(self._tail.pending, complete=False):
            out.append(self.bus.publish("token", name=name))
        return out

    def _line(self, line):
        out = [self.bus.publish("token", name=name) for name in self._tokens.scan(line, complete=True)]
        state = logtail.map_state(line)
        if state:
            name = logtail.map_name(line)
            if not self.in_map or name:
                self.in_map = True
                self.map = name or self.map
                out.append(self.bus.publish("map_loaded", name=name))
        elif state is False and self.in_map is not False:
            self.in_map = False
            self.map = None
            out.append(self.bus.publish("map_left"))
        return out

    def run(self, stop=None, poll=POLL):
        """poll() until `stop` (a threading.Event) is set."""
        stop = stop or threading.Event()
        while not stop.wait(poll):
            self.poll()

    def status(self):
        return {"log": str(self.log), "inMap": self.in_map, "map": self.map,
                "lastId": self.bus.last_id, "listeners": self.bus.listeners}


def _local_hosts(port):
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


class Handler(BaseHTTPRequestHandler):
    session = None  # set by serve()

    def log_message(self, fmt, *args):  # no line per request on stderr
        pass

    def do_GET(self):
        # a page on another site could reach localhost through a DNS name of its own; refuse those
        if self.headers.get("Host") not in _local_hosts(self.server.server_address[1]):
            return self._send(403, {"error": "forbidden"})
        url = urlsplit(self.path)
        if url.path == "/status":
            return self._send(200, self.session.status())
        if url.path == "/events":
            return self._events(parse_qs(url.query))
        return self._send(404, {"error": "not found"})

    def _cors(self):
        # pages of the other movekit tools (another localhost port) may listen too
        origin = self.headers.get("Origin") or ""
        host = origin.removeprefix("http://").rsplit(":", 1)[0]
        if host in ("127.0.0.1", "localhost"):
            self.send_header("Access-Control-Allow-Origin", origin)

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _events(self, query):
        after = self.headers.get("Last-Event-ID") or (query.get("after") or [None])[0]
        try:
            after = int(after) if after is not None else None
        except ValueError:
            after = None
        bus = self.session.bus
        q = bus.subscribe(after)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self._cors()
            self.end_headers()
            self.wfile.write(b": movekit session\n\n")
            self.wfile.flush()
            while True:
                try:
                    event = q.get(timeout=PING)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                else:
                    data = json.dumps(event, separators=(",", ":"))
                    self.wfile.write(f"id: {event['id']}\nevent: {event['type']}\ndata: {data}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            bus.unsubscribe(q)


class Server(ThreadingHTTPServer):
    daemon_threads = True  # open /events streams don't keep the process alive
    # On Windows SO_REUSEADDR lets a second session bind the same port, so start() would never see
    # it taken; leave it off there (as the Strafe Review server does)
    allow_reuse_address = sys.platform != "win32"


def serve(session, host=HOST, port=PORT):
    """Serve the session's events in a background thread. Returns the server (shutdown() stops
    it); raises OSError when the port is taken."""
    handler = type("SessionHandler", (Handler,), {"session": session})
    server = Server((host, port), handler)
    threading.Thread(target=server.serve_forever, name="movekit-session-http", daemon=True).start()
    return server


def start(log, host=HOST, port=PORT, poll=POLL):
    """Run a session for `log` in this process: (session, server), or None when another process
    already serves one on the port. Stop it with server.shutdown() and session_stop.set()."""
    session = Session(log)
    try:
        server = serve(session, host, port)
    except OSError:
        return None
    session.stop = threading.Event()
    threading.Thread(target=session.run, args=(session.stop, poll), name="movekit-session", daemon=True).start()
    return session, server


def listen(url=URL, after=None, retry=1.0, stop=None):
    """Yield the session's events (dicts) for good, reconnecting when the stream drops; events
    missed meanwhile come again if the session still keeps them. Yields None each time the
    connection is lost or can't be made, so the caller can tell. Ends when `stop` is set."""
    last = after
    while stop is None or not stop.is_set():
        headers = {"Accept": "text/event-stream"}
        if last is not None:
            headers["Last-Event-ID"] = str(last)
        try:
            with urlopen(Request(url.rstrip("/") + "/events", headers=headers), timeout=LISTEN_TIMEOUT) as resp:
                data = []
                for raw in resp:
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    if line.startswith("data:"):
                        data.append(line[5:].lstrip())
                    elif not line and data:
                        event = json.loads("\n".join(data))
                        data = []
                        last = event.get("id", last)
                        yield event
                    if stop is not None and stop.is_set():
                        return
        except (OSError, ValueError):
            pass
        yield None
        if stop is not None:
            if stop.wait(retry):
                return
        else:
            time.sleep(retry)


def main():
    from movekit import games, steam

    ap = argparse.ArgumentParser(description="Serve a game's console log (yaw.log) as movekit session events.")
    ap.add_argument("--game", choices=sorted(games.GAMES), default="momentum")
    ap.add_argument("--log", help="the log file; default: yaw.log in the game's folder")
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()
    log = args.log
    if log is None:
        folder = steam.game_dir(games.GAMES[args.game])
        if folder is None:
            sys.exit(f"movekit session: {games.GAMES[args.game].name} not found; pass --log")
        log = folder / "yaw.log"
    got = start(log, port=args.port)
    if got is None:
        sys.exit(f"movekit session: port {args.port} is taken (a session already runs)")
    session, _server = got
    print(f"movekit session: reading {log}, serving http://{HOST}:{args.port}/events", flush=True)
    try:
        session.stop.wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
