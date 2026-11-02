"""Follow the game's console log (con_logfile, yaw.log) and read the lines the tools care about.

LogTail(path, start).lines() returns the complete lines written since the last call, or [] when
there is nothing new. It never sleeps or blocks, so a tool with its own wait loop (select on a
socket) can call it every turn. It waits while the file does not exist and starts over from the
top when the file is truncated or replaced (the game, or yaw-watch.sh's `: > "$LOG"`, empties it
on launch).

follow(path, once, poll) is the same as a generator for a tool that only reads the log: it yields
each line, and None on an idle tick (nothing new for `poll` seconds) so the caller can do timed
work such as dropping stale attempts.

Lines are decoded as UTF-8 with bad bytes replaced and keep a trailing "\\r" when the file has
CRLF line ends. Stdlib only; works on Linux and Windows.
"""
import os
import re
import time

POLL = 0.25  # seconds follow() sleeps when the log has nothing new
CHUNK = 1 << 16  # bytes read at a time


class LogTail:
    """Complete lines of a growing file, read without blocking.

    start="begin" reads the file from the top; start="end" skips what is in it when LogTail is
    made, if it exists then. A file that appears later, or replaces the first one, is always read
    from the top: everything in it is new."""

    def __init__(self, path, start="begin"):
        if start not in ("begin", "end"):
            raise ValueError(f"start must be 'begin' or 'end', not {start!r}")
        self.path = path
        self._f, self._ino, self._buf = None, None, b""
        if start == "end" and self._open():
            self._f.seek(0, os.SEEK_END)

    def _open(self):
        try:
            self._f = open(self.path, "rb")  # noqa: SIM115 - stays open across reads, closed on truncation
        except FileNotFoundError:
            return False
        self._ino = os.fstat(self._f.fileno()).st_ino
        return True

    def lines(self):
        """The complete lines available now ([] if none). A line still being written is kept
        until its line break arrives."""
        if self._f is None and not self._open():
            return []
        while True:
            data = self._f.read(CHUNK)
            if not data:
                break
            self._buf += data
            *done, self._buf = self._buf.split(b"\n")
            if done:
                return [line.decode("utf-8", "replace") for line in done]
        try:
            st = os.stat(self.path)
            replaced = st.st_ino != self._ino or st.st_size < self._f.tell()
        except FileNotFoundError:
            replaced = True
        if replaced:
            self.close()
            return self.lines()  # read the new file (or wait for it) at once
        return []

    @property
    def exists(self):
        """True while a file is open (it existed at the last read)."""
        return self._f is not None

    def close(self):
        if self._f is not None:
            self._f.close()
        self._f, self._ino, self._buf = None, None, b""


def follow(path, once=False, poll=POLL):
    """Yield complete lines of path as they are written, and None on an idle tick. Starts over
    when the file is truncated or replaced, and waits while it does not exist. With once=True,
    stop at the end of what is there now (at once if the file is missing)."""
    tail = LogTail(path)
    try:
        while True:
            got = tail.lines()
            if got:
                yield from got
                continue
            if once:
                return
            yield None
            time.sleep(poll)
    finally:
        tail.close()


# console lines that mean a map was entered or left; the game starts in its menu
_MAP_IN = re.compile(r"Host_NewGame on map |^Connected to |^Map: ")
_MAP_OUT = re.compile(r"Host_ShutdownServer|Host_Shutdown\b|^Disconnect")
# Momentum: "Host_NewGame on map <name>"; CS:S on joining a server: "Map: <name>"
_MAP_NAME = re.compile(r"on map (\S+)|^Map: (\S+)")


def map_state(line):
    """True when the line means a map was entered, False when left, else None."""
    if _MAP_IN.search(line):
        return True
    if _MAP_OUT.search(line):
        return False
    return None


def map_name(line):
    """The lower-case name of the map the line says is loading, or None."""
    m = _MAP_NAME.search(line)
    return (m.group(1) or m.group(2)).lower() if m else None
