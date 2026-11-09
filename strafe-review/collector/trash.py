"""Deleted attempts: moved to a trash folder, kept 30 days, then removed for good.

A delete moves <store>/<map>/<id>.json.gz to <store>/.trash/<map>/<id>.json.gz, three folders deep, so the
store's */*.json.gz globs and the checks' two-level walks never see it. The attempt's note and tags move
out of meta.json into the deleted list, so a restore brings them back.

The deleted list, <store>/deleted.json, is {"version": 1, "deleted": {"<map>/<id>": {"at": seconds,
"meta": {"note", "tags"} or absent, "purged": true once the file is gone}}}. Entries stay after the purge:
the collector re-reads yaw.log on start and would save a deleted attempt again, so it treats every id
listed here as already known (ids()).
"""
import json
import os
import threading
import time

TRASH = ".trash"
LIST_FILE = "deleted.json"
KEEP_DAYS = 30
SUFFIX = ".json.gz"
_lock = threading.Lock()  # one writer per process; the viewer server is the only one that writes


def _read(store):
    try:
        with open(store / LIST_FILE) as f:
            got = json.load(f).get("deleted")
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def _write(store, deleted):
    tmp = store / f".{LIST_FILE}.tmp"
    with open(tmp, "w") as f:
        json.dump({"version": 1, "deleted": deleted}, f, indent=1, sort_keys=True)
    os.replace(tmp, store / LIST_FILE)


def ids(store):
    """Every deleted attempt's id, purged ones included, for the collector's known set."""
    return {key.rsplit("/", 1)[-1] for key in _read(store)}


def trash_path(store, key):
    folder, attempt = key.split("/")
    return store / TRASH / folder / f"{attempt}{SUFFIX}"


def delete(store, keys, take_meta):
    """Move each "<map>/<id>" in keys to the trash. take_meta(key) removes the attempt's note and tags
    from meta.json and returns them (or None). Returns the keys moved; ones with no file are left out."""
    done = []
    with _lock:
        deleted = _read(store)
        for key in keys:
            src = store / f"{key}{SUFFIX}"
            if not src.is_file():
                continue
            dst = trash_path(store, key)
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
            entry = {"at": int(time.time())}
            meta = take_meta(key)
            if meta:
                entry["meta"] = meta
            deleted[key] = entry
            done.append(key)
        if done:
            _write(store, deleted)
    return done


def restore(store, keys, put_meta):
    """Move each key back from the trash and off the deleted list. put_meta(key, meta) stores its note
    and tags again. Returns the keys restored; purged ones and ones not in the trash are left out."""
    done = []
    with _lock:
        deleted = _read(store)
        for key in keys:
            src = trash_path(store, key)
            entry = deleted.get(key)
            if entry is None or not src.is_file():
                continue
            dst = store / f"{key}{SUFFIX}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
            if entry.get("meta"):
                put_meta(key, entry["meta"])
            del deleted[key]
            done.append(key)
        if done:
            _write(store, deleted)
    return done


def purge(store, now=None):
    """Remove trashed files deleted more than KEEP_DAYS ago (by the list's time, not the file's: a move
    keeps the old mtime). Their entries stay, marked purged, without the note and tags. Returns the keys."""
    cutoff = (now or time.time()) - KEEP_DAYS * 86400
    done = []
    with _lock:
        deleted = _read(store)
        for key, entry in deleted.items():
            if entry.get("purged") or entry.get("at", 0) > cutoff:
                continue
            trash_path(store, key).unlink(missing_ok=True)
            entry.pop("meta", None)
            entry["purged"] = True
            done.append(key)
        if done:
            _write(store, deleted)
            for folder in (store / TRASH).glob("*"):
                if folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
    return done
