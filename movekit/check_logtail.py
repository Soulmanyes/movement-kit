#!/usr/bin/env python3
"""Checks movekit.logtail on temp files; no game needed.

Usage: python movekit/check_logtail.py   (exits 1 on the first failure)

Covers: a missing file that appears later, appended lines, a line finished by a later write, CRLF
kept, non-UTF-8 bytes replaced, start="end" on an existing file and on one that appears later,
truncation (yaw-watch.sh's `: > "$LOG"`), replacement by a new file, removal, a line longer than
one read, follow() with once and its idle ticks, and the map lines of Momentum and CS:S.
"""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from movekit import logtail  # after the path above


def check(what, got, want):
    if got != want:
        sys.exit(f"FAIL {what}: got {got!r}, want {want!r}")
    print(f"ok   {what}")


def write(path, data, mode="ab"):
    with open(path, mode) as f:
        f.write(data)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "yaw.log"

        tail = logtail.LogTail(log)
        check("missing file: nothing", tail.lines(), [])
        check("missing file: not open", tail.exists, False)
        write(log, b"one\ntwo\n")
        check("file appears: read from the top", tail.lines(), ["one", "two"])
        check("nothing new", tail.lines(), [])
        write(log, b"thr")
        check("half a line is kept back", tail.lines(), [])
        write(log, b"ee\r\nfour\n")
        check("line finished later, CRLF kept", tail.lines(), ["three\r", "four"])
        write(log, b"caf\xe9 \xff\n")
        check("bad bytes replaced", tail.lines(), ["caf� �"])
        write(log, b"", "wb")
        write(log, b"fresh\n")
        check("truncated then written: read from the top", tail.lines(), ["fresh"])
        new = Path(tmp) / "new.log"
        write(new, b"replaced\n", "wb")
        os.replace(new, log)
        check("replaced: the new file from the top", tail.lines(), ["replaced"])
        log.unlink()
        check("removed: nothing", tail.lines(), [])
        check("removed: closed", tail.exists, False)
        write(log, b"back\n", "wb")
        check("back again", tail.lines(), ["back"])
        long = b"x" * (logtail.CHUNK * 2 + 5)
        write(log, long + b"\nafter\n")
        check("line longer than one read", tail.lines(), [long.decode(), "after"])
        tail.close()

        write(log, b"old\nstuff\n", "wb")
        tail = logtail.LogTail(log, start="end")
        check("start=end: skips what is there", tail.lines(), [])
        write(log, b"new\n")
        check("start=end: then new lines", tail.lines(), ["new"])
        tail.close()
        log.unlink()
        tail = logtail.LogTail(log, start="end")
        write(log, b"first\n", "wb")
        check("start=end, file appears later: from the top", tail.lines(), ["first"])
        tail.close()
        try:
            logtail.LogTail(log, start="middle")
            sys.exit("FAIL bad start: no ValueError")
        except ValueError:
            print("ok   bad start raises ValueError")

        write(log, b"a\nb\nhalf", "wb")
        check("follow once: complete lines, then stop", list(logtail.follow(log, once=True)), ["a", "b"])
        check("follow once, missing file: nothing", list(logtail.follow(Path(tmp) / "none", once=True)), [])
        gen = logtail.follow(log, poll=0.01)
        got = [next(gen), next(gen), next(gen)]
        check("follow: lines then an idle tick", got, ["a", "b", None])
        threading.Timer(0.05, write, (log, b"done\n")).start()
        deadline, seen = time.monotonic() + 2, []
        for line in gen:
            if line is not None:
                seen.append(line)
                break
            if time.monotonic() > deadline:
                break
        check("follow: line written later", seen, ["halfdone"])
        gen.close()

    momentum = "Host_NewGame on map surf_Utopia_V3\r"
    css = "Map: bhop_eazy\r"
    check("Momentum map name", logtail.map_name(momentum), "surf_utopia_v3")
    check("CS:S map name", logtail.map_name(css), "bhop_eazy")
    check("no map name", logtail.map_name("Connected to 1.2.3.4:27015"), None)
    check("map in: Momentum", logtail.map_state(momentum), True)
    check("map in: CS:S", logtail.map_state(css), True)
    check("map in: connected", logtail.map_state("Connected to 1.2.3.4:27015"), True)
    check("map out: shutdown server", logtail.map_state("Host_ShutdownServer\r"), False)
    check("map out: shutdown", logtail.map_state("Host_Shutdown"), False)
    check("map out: disconnect", logtail.map_state("Disconnect: Server shutting down"), False)
    check("not Host_ShutdownX", logtail.map_state("Host_ShutdownX"), None)
    check("other line", logtail.map_state("say Map: x"), None)
    print("all logtail checks passed")


if __name__ == "__main__":
    main()
