#!/usr/bin/env python3
"""Checks the collector on a temp log and store: it reads the recorder's lines with the MK_ prefix (1.12.0)
and without it (older recorders), and empties the log (trim) only when it is past TRIM_AT, read to the
end, quiet, off any map and with no attempt half read.

Usage: python3 check_collector.py
"""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import collector  # noqa: I001 - after the sys.path line above, which makes it importable
from srrec import body

failed = 0


def check(what, ok):
    global failed
    print(f"{'ok  ' if ok else 'FAIL'} {what}")
    failed += not ok


def lines(tag, aid, attempt, n=2):
    data = json.dumps(attempt, separators=(",", ":"))
    size = -(-len(data) // n)
    parts = [data[i * size:(i + 1) * size] for i in range(n)]
    out = [f"[panorama] {tag} {aid} {i}/{n} {p}\r\n" for i, p in enumerate(parts, 1)]
    return out + [f"[panorama] {tag} {aid} end n={n} chars={len(data)}\r\n"]


def attempt(aid):
    return {"format": 1, "id": aid, "map": "bhop_check", "label": "run", "cols": [], "rows": "", "events": []}


def wait(cond, secs=3.0):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def main():
    check("body: new tag", body("[panorama] MK_SRREC a 1/1 x\r\n") == "a 1/1 x")
    check("body: old tag", body("[panorama] SRREC a 1/1 x") == "a 1/1 x")
    check("body: other line", body("[panorama] MK_TIMER_ON") is None)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        log, store = tmp / "yaw.log", tmp / "store"
        # both tags, read once
        log.write_text("".join(lines("MK_SRREC", "new1", attempt("new1")) + lines("SRREC", "old1", attempt("old1"))))
        collector.run(str(log), store, once=True)
        check("--once: both tags saved", collector.known_ids(store) == {"new1", "old1"})
        check("--once: the log isn't emptied", log.stat().st_size > 0)

        # following: a small TRIM_AT and QUIET so the check is quick
        collector.TRIM_AT, collector.QUIET = 600, 0.3
        log.write_text("[engine] Host_NewGame on map bhop_check\n" + "x" * 700 + "\n")
        th = threading.Thread(target=collector.run, args=(str(log), store, False, None, True), daemon=True)
        th.start()
        time.sleep(1.0)
        check("on a map: not emptied", log.stat().st_size > 700)
        with log.open("a") as f:
            f.write("[engine] Host_ShutdownServer\n")
            f.writelines(lines("MK_SRREC", "new2", attempt("new2"))[:1])  # half an attempt
        time.sleep(1.0)
        check("an attempt half read: not emptied", log.stat().st_size > 700)
        with log.open("a") as f:
            f.writelines(lines("MK_SRREC", "new2", attempt("new2"))[1:])
        check("off the map, all read, quiet: emptied", wait(lambda: log.stat().st_size == 0))
        check("the attempt finished first was saved", "new2" in collector.known_ids(store))
        with log.open("a") as f:  # the game appends at the top of the emptied log
            f.writelines(lines("MK_SRREC", "new3", attempt("new3")))
        check("lines after emptying are read", wait(lambda: "new3" in collector.known_ids(store)))
        check("a small log stays", log.stat().st_size > 0 and not wait(lambda: log.stat().st_size == 0, 1.0))

        # a log passed in (trim_log off, the default) is never emptied, however big
        other = tmp / "saved.log"
        other.write_text("[engine] Host_ShutdownServer\n" + "x" * 700 + "\n")
        threading.Thread(target=collector.run, args=(str(other), tmp / "store2", False), daemon=True).start()
        check("trim_log off: a big log stays", not wait(lambda: other.stat().st_size == 0, 1.0))

    print("check_collector: " + ("all passed" if not failed else f"{failed} failed"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
