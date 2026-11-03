#!/usr/bin/env python3
"""Collects the recorder's attempts from Momentum's yaw.log and saves them.

Usage: collector.py [yaw.log] [--once] [--store DIR]

Reads the log from the start, then follows it. Each complete attempt is saved as
<store>/<map>/<id>.json.gz, where <store> defaults to
~/.local/share/strafe-review/attempts (%LOCALAPPDATA%\\strafe-review\\attempts on
Windows). An attempt already on disk is skipped, so reading the same log again is safe.
--once reads to the end of the log and exits.
"""
import gzip
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import steam  # sets the path to movekit
from srrec import Assembler, body

from movekit import attempts
from movekit.files import new_file_mode
from movekit.logtail import follow


def _bundled():
    """This file sits inside a one-file exe's unpacked bundle (Strafe Review's own exe until the bridge
    release, 3.7b in PLAN.md), whose layout is at sys._MEIPASS. A module loaded from disk by the kit's
    core exe is frozen too, but its files are its own folder."""
    bundle = getattr(sys, "_MEIPASS", None)
    return bool(bundle) and Path(__file__).resolve().is_relative_to(Path(bundle).resolve())


# Strafe Review's folder, or the old exe's unpacked bundle (it holds recorder/ and viewer/static/ the same way)
ROOT = Path(sys._MEIPASS) if _bundled() else Path(__file__).resolve().parent.parent
VERSION = "1.8.0"  # Strafe Review's (module.json reads it); bump in the same commit as the release tag
GAME = steam.find_game()  # None if Momentum isn't found; then the game folder must be given
STORE = attempts.store()
LOG = os.path.join(GAME, "yaw.log") if GAME else None  # con_logfile, shared with Source Yaw's yaws.cfg
NOT_FOUND = "Momentum Mod not found in any Steam library; set MOMENTUM_DIR to its momentum folder"
STALE = 600  # seconds after which an attempt without its end line is dropped
# What run() has seen since it started, for the viewer's status box (/api/status)
STATS = {"lines": 0, "recorder": 0, "saved": 0, "dropped": 0, "lastLine": None, "lastRecorder": None, "lastSaved": None, "lastLoad": None}


def map_dir(name):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name or "") or "unknown"


def known_ids(store):
    return {p.name.removesuffix(".json.gz") for p in store.glob("*/*.json.gz")}


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


def run(log, store, once, on_saved=None):
    """Collect from `log` into `store`. on_saved(path, attempt) is called for each attempt written
    (not for one already on disk); the viewer server uses it to announce attempts on the session."""
    known = known_ids(store)
    asm = Assembler()
    print(f"collector: reading {log}, saving to {store} ({len(known)} attempts already there)", flush=True)
    STATS.update(lines=0, recorder=0, saved=0, dropped=0, lastLine=None, lastRecorder=None, lastSaved=None, lastLoad=None)
    for line in follow(log, once):
        if line is None:
            for b in asm.drop_stale(STALE):
                STATS["dropped"] += 1
                print(f"collector: dropped {b}", flush=True)
            continue
        STATS["lines"] += 1
        STATS["lastLine"] = time.time()
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
            path = save(store, value)
            known.add(value["id"])
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
        run(log, store, once)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
