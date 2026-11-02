#!/usr/bin/env python3
"""Checks movekit.attempts on temp files; no game needed.

Usage: python movekit/check_attempts.py [--store DIR]   (exits 1 on the first failure)

Covers: a full recorder attempt, the minimal one css_demo.py writes, a missing optional field, an
unknown extra field, an unknown appended column (and columns() by name, NaN for a missing one),
format 2 refused by load() and flagged by problems(), broken rows, new labels and reasons allowed, the store
path, and files()/attempt_id(). With --store it also checks every file in that store (the real one:
--store ~/.local/share/strafe-review/attempts) and lists the ones with problems.
"""
import copy
import gzip
import json
import math
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from movekit import attempts  # after the path above

COLS = ["tick", "gain", "ideal", "ratio", "right", "vx", "vy", "vz", "yaw", "pitch", "buttons", "move", "duck",
        "rtick", "wx", "wy", "seek"]
FULL = {
    "format": 1, "id": "mh1abc12", "started": 1761600000000, "map": "bhop_test", "interval": 0.01, "style": 0,
    "track": {"type": 0, "number": 0}, "label": "own", "player": None, "replayFile": None, "practice": False,
    "version": "0.10.8", "mouse": {"sensitivity": 1.5, "m_yaw": 0.022, "cl_yawspeed": 210, "dpi": None},
    "cols": COLS, "preRows": 1, "postRows": 1,
    "rows": ";".join(",".join(str(v) for v in [t, 0, 0, 0, 0, 250 + t, 0, 0, 90, 0, 2, 0, 0, -1, 0, 0, 0])
                     for t in range(100, 104)),
    "events": [{"tick": 101, "kind": "jump", "n": 1}, {"tick": 103, "kind": "timer", "state": 0, "runTime": 0.02}],
    "reason": "zone", "runTime": 0.02, "gaps": 0, "ended": 1761600001000,
}
# What viewer/css_demo.py writes: required fields only, a column subset in another order
MINIMAL = {
    "format": 1, "id": "cssdemo", "map": "bhop_eazy", "interval": 0.01, "label": "own",
    "cols": ["tick", "gain", "ideal", "ratio", "right", "vx", "vy", "vz", "yaw", "buttons", "wx", "wy"],
    "preRows": 0, "postRows": 0, "events": [], "rows": "1,0,0,0,0,250,0,0,90,512,0,0;2,0,0,0,0,251,0,0,90,512,0,0",
}


def check(what, got, want):
    if got != want:
        sys.exit(f"FAIL {what}: got {got!r}, want {want!r}")
    print(f"ok   {what}")


def changed(base, **fields):
    out = copy.deepcopy(base)
    for k, v in fields.items():
        if v is None and k.startswith("drop_"):
            out.pop(k.removeprefix("drop_"))
        else:
            out[k] = v
    return out


def save(path, attempt):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(attempt, f)


def check_store(where):
    n = bad = 0
    for path in attempts.files(where):
        n += 1
        try:
            found = attempts.problems(attempts.load(path))
        except (OSError, EOFError, ValueError) as e:
            found = [str(e)]
        if found:
            bad += 1
            print(f"     {path}: {'; '.join(found)}")
    check(f"store {where}: {n} files, all format 1 without problems", bad, 0)


def main():
    check("full attempt", attempts.problems(FULL), [])
    check("minimal attempt (css_demo.py)", attempts.problems(MINIMAL), [])
    check("missing optional mouse", attempts.problems(changed(FULL, drop_mouse=None)), [])
    check("missing optional postRows", attempts.problems(changed(FULL, drop_postRows=None)), [])
    check("null mouse, int runTime", attempts.problems(changed(FULL, mouse=None, runTime=0)), [])
    check("unknown extra field", attempts.problems(changed(FULL, jhud={"x": 1})), [])
    extra = changed(MINIMAL, cols=[*MINIMAL["cols"], "future"], rows="1,0,0,0,0,250,0,0,90,512,0,0,7;2,0,0,0,0,251,0,0,90,512,0,0,8")
    check("unknown appended column", attempts.problems(extra), [])
    got = attempts.columns(extra, ["tick", "future", "pitch"])
    check("columns() by name", (got["tick"], got["future"]), ([1.0, 2.0], [7.0, 8.0]))
    check("columns() missing column is NaN", all(math.isnan(v) for v in got["pitch"]) and len(got["pitch"]), 2)
    check("columns() all", list(attempts.columns(MINIMAL)), MINIMAL["cols"])
    check("columns() no rows", attempts.columns(changed(MINIMAL, rows=""), ["tick"]), {"tick": []})

    check("format 2 flagged", attempts.problems(changed(FULL, format=2)), ["format 2 is not 1"])
    check("missing required", attempts.problems(changed(MINIMAL, drop_interval=None)), ["missing interval"])
    check("wrong type", attempts.problems(changed(MINIMAL, interval="0.01")), ["interval has type str"])
    check("bool is not an int", attempts.problems(changed(FULL, gaps=True)), ["gaps has type bool"])
    check("new label allowed", attempts.problems(changed(FULL, label="ghost")), [])
    check("new reason allowed", attempts.problems(changed(FULL, reason="boom")), [])
    check("short row", attempts.problems(changed(MINIMAL, rows="1,2")), ["row 0 has 2 values for 12 columns"])
    check("not a number", attempts.problems(changed(MINIMAL, rows=MINIMAL["rows"].replace("250", "x"))),
          ["row 0 has a value that is not a number"])
    check("preRows past the rows", attempts.problems(changed(MINIMAL, preRows=3)), ["preRows is outside the 2 rows"])
    check("event without kind", attempts.problems(changed(FULL, events=[{"tick": 1}])), ["event 0 has no kind or tick"])

    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "attempts"
        save(store / "bhop_test" / "mh1abc12.json.gz", FULL)
        save(store / "bhop_test" / "future.json.gz", changed(FULL, format=2, id="future"))
        (store / "meta.json").write_text("{}")
        check("files() finds attempts only", sorted(attempts.attempt_id(p) for p in attempts.files(store)),
              ["future", "mh1abc12"])
        check("load()", attempts.load(store / "bhop_test" / "mh1abc12.json.gz"), FULL)
        try:
            attempts.load(store / "bhop_test" / "future.json.gz")
            check("load() refuses format 2", "loaded", "refused")
        except attempts.UnsupportedFormat:
            check("load() refuses format 2", "refused", "refused")
        check("UnsupportedFormat is a ValueError", issubclass(attempts.UnsupportedFormat, ValueError), True)
        old = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = tmp
        try:
            if sys.platform != "win32":
                check("store() under XDG_DATA_HOME", attempts.store(), Path(tmp) / "strafe-review" / "attempts")
        finally:
            if old is None:
                os.environ.pop("XDG_DATA_HOME")
            else:
                os.environ["XDG_DATA_HOME"] = old

    if "--store" in sys.argv:
        check_store(Path(sys.argv[sys.argv.index("--store") + 1]).expanduser())
    print("all attempt checks passed")


if __name__ == "__main__":
    main()
