#!/usr/bin/env python3
"""Collects the recorder's attempts from Momentum's yaw.log and saves them.

Usage: collector.py [yaw.log] [--once] [--store DIR]

Reads the log from the start, then follows it. Once the log is past TRIM_AT and everything in it is
read, it empties the log (trim_ready has the conditions), since con_logfile only ever appends.
Each complete attempt is saved as
<store>/<map>/<id>.json.gz, where <store> defaults to
~/.local/share/strafe-review/attempts (%LOCALAPPDATA%\\strafe-review\\attempts on
Windows). An attempt already on disk, or deleted from the viewer (trash.py), is skipped, so
reading the same log again is safe.
--once reads to the end of the log and exits.
"""
import gzip  # noqa: I001 - steam must run before the movekit imports: it sets their path
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import steam  # sets the path to movekit
import trash
from scope import skip_reason
from srrec import Assembler, body

from movekit import attempts
from movekit.files import new_file_mode
from movekit.logtail import follow, map_state


def _bundled():
    """This file sits inside a one-file exe's unpacked bundle (Strafe Review's own exe until the bridge
    release, 3.7b in PLAN.md), whose layout is at sys._MEIPASS. A module loaded from disk by the kit's
    core exe is frozen too, but its files are its own folder."""
    bundle = getattr(sys, "_MEIPASS", None)
    return bool(bundle) and Path(__file__).resolve().is_relative_to(Path(bundle).resolve())


# Strafe Review's folder, or the old exe's unpacked bundle (it holds recorder/ and viewer/static/ the same way)
ROOT = Path(sys._MEIPASS) if _bundled() else Path(__file__).resolve().parent.parent
VERSION = "1.12.0"  # Strafe Review's (module.json reads it); bump in the same commit as the release tag
GAME = steam.find_game()  # None if Momentum isn't found; then the game folder must be given
STORE = attempts.store()
LOG = os.path.join(GAME, "yaw.log") if GAME else None  # con_logfile, shared with Source Yaw's yaws.cfg
NOT_FOUND = "Momentum Mod not found in any Steam library; set MOMENTUM_DIR to its momentum folder"
STALE = 600  # seconds after which an attempt without its end line is dropped
TRIM_AT = 64 << 20  # bytes: a log this big is emptied once trim_ready allows it
QUIET = 5.0  # seconds without a new line before the log may be emptied
TRIM_RETRY = 60.0  # seconds to wait after the log couldn't be emptied
# What run() has seen since it started, for the viewer's status box (/api/status)
STATS = {"lines": 0, "recorder": 0, "saved": 0, "dropped": 0, "skipped": 0, "lastLine": None, "lastRecorder": None, "lastSaved": None, "lastLoad": None}


def map_dir(name):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name or "") or "unknown"


def known_ids(store):
    """Ids on disk plus deleted ones (trash.py), so a deleted attempt still in yaw.log isn't saved again."""
    return {p.name.removesuffix(".json.gz") for p in store.glob("*/*.json.gz")} | trash.ids(store)


def save(store, attempt):
    """Write the attempt, or return None if it is already on disk (another collector may tail the same log)."""
    folder = store / map_dir(attempt.get("map"))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{attempt['id']}.json.gz"
    if path.exists():
        return None
    # write a tmp file of our own then rename, so a reader never sees a half-written file
    # and two collectors never write the same tmp file
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=f".{attempt['id']}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as raw, gzip.open(raw, "wt", encoding="utf-8") as f:
            json.dump(attempt, f, separators=(",", ":"))
        os.chmod(tmp, new_file_mode())  # mkstemp makes it 0600
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def trim_ready(log, asm, on_map, last_line, now):
    """Whether the log may be emptied now. Called when everything in it is read. It must be past TRIM_AT,
    with no attempt half read, the game off any map (Source Yaw's hub page reads the loaded map from the
    log's tail) and nothing new for QUIET seconds, so the other tools tailing it have read it all too."""
    if asm.chunks or on_map or now - last_line < QUIET:
        return False
    try:
        return os.path.getsize(log) >= TRIM_AT
    except OSError:
        return False


def trim(log):
    """Empty the log in place. The game opens it for appending, so its next line lands at the top; the
    tools tailing it see it shrink and read from the top again (movekit.logtail)."""
    try:
        with open(log, "r+b") as f:
            f.truncate(0)
    except OSError as e:
        print(f"collector: couldn't empty {log}: {e}", flush=True)
        return False
    print(f"collector: emptied {log}, everything in it was read", flush=True)
    return True


def run(log, store, once, on_saved=None, trim_log=False):
    """Collect from `log` into `store`. on_saved(path, attempt) is called for each attempt written
    (not for one already on disk); the viewer server uses it to announce attempts on the session.
    trim_log lets it empty `log` (see trim_ready): only for the game's own yaw.log, never a log
    someone passed in, which may be a saved copy."""
    known = known_ids(store)
    asm = Assembler()
    print(f"collector: reading {log}, saving to {store} ({len(known)} attempts already there)", flush=True)
    STATS.update(lines=0, recorder=0, saved=0, dropped=0, skipped=0, lastLine=None, lastRecorder=None, lastSaved=None, lastLoad=None)
    on_map = None  # True after a map load, False after leaving it (movekit.logtail.map_state)
    last_line = time.monotonic()
    trim_after = 0.0  # monotonic time before which no trim is tried (after one failed)
    for line in follow(log, once):
        if line is None:
            for b in asm.drop_stale(STALE):
                STATS["dropped"] += 1
                print(f"collector: dropped {b}", flush=True)
            now = time.monotonic()
            if trim_log and not once and now >= trim_after and trim_ready(log, asm, on_map, last_line, now) and not trim(log):
                trim_after = now + TRIM_RETRY
            continue
        STATS["lines"] += 1
        STATS["lastLine"] = time.time()
        last_line = time.monotonic()
        state = map_state(line)
        if state is not None:
            on_map = state
        text = body(line)
        if text is None:
            continue
        STATS["recorder"] += 1
        STATS["lastRecorder"] = time.time()
        if text.startswith("load "):  # the recorder's first line, written when the HUD loads it
            STATS["lastLoad"] = time.time()
        got = asm.feed(text)
        if got is None:
            continue
        kind, value = got
        if kind == "broken":
            STATS["dropped"] += 1
            print(f"collector: dropped {value}", flush=True)
        elif kind == "attempt" and value.get("id") not in known:
            known.add(value["id"])
            why = skip_reason(value)
            if why:  # surf runs that are not bhop bonuses (scope.py); the next start reads the log and skips them again
                STATS["skipped"] += 1
                print(f"collector: skipped {value.get('map')} {value.get('label')} {value['id']}: {why}", flush=True)
                continue
            path = save(store, value)
            if path:
                STATS["saved"] += 1
                STATS["lastSaved"] = time.time()
                print(f"collector: saved {path}", flush=True)
                if on_saved:
                    on_saved(path, value)
    for b in asm.leftover():
        print(f"collector: unfinished {b}", flush=True)


def main():
    args = sys.argv[1:]
    once = "--once" in args
    if once:
        args.remove("--once")
    store = STORE
    if "--store" in args:
        i = args.index("--store")
        store = Path(args[i + 1])
        del args[i:i + 2]
    log = args[0] if args else LOG
    if log is None:
        sys.exit(f"collector: {NOT_FOUND}, or pass the log")
    try:
        run(log, store, once, trim_log=not args)  # a log passed in is never emptied
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
