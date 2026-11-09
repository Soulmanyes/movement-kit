#!/usr/bin/env python3
"""Checks deleting and restoring attempts (trash.py, the viewer's /api/delete and /api/restore) on a temp
store: notes and tags move with the attempt, the collector doesn't save a deleted attempt again from
yaw.log, and the 30-day purge removes the file but keeps the id.

Usage: python3 check_trash.py
"""
import gzip
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "viewer")]
import collector
import server
import trash

failed = 0


def check(what, ok):
    global failed
    print(f"{'ok  ' if ok else 'FAIL'} {what}")
    failed += not ok


def fake_attempt(store, folder, attempt_id):
    path = store / folder / f"{attempt_id}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as f:
        json.dump({"format": 1, "id": attempt_id, "map": folder}, f)
    return path


with tempfile.TemporaryDirectory() as tmp:
    store = Path(tmp)
    a = fake_attempt(store, "bhop_a", "aaa111")
    fake_attempt(store, "bhop_a", "bbb222")
    c = fake_attempt(store, "bhop_c", "ccc333")
    server.write_meta(store, "bhop_a/aaa111", {"note": "new sens", "tags": ["pb"]})
    server.write_meta(store, "bhop_a/bbb222", {"note": "keep", "tags": []})

    try:
        server.clean_keys({"keys": ["../x/aaa111"]})
        check("'..' key refused", False)
    except TypeError:
        check("'..' key refused", True)
    check("keys deduped", server.clean_keys({"keys": ["bhop_a/aaa111", "bhop_a/aaa111"]}) == ["bhop_a/aaa111"])

    done = server.delete_attempts(store, ["bhop_a/aaa111", "bhop_c/ccc333", "bhop_a/nope99"])
    check("delete moves the two that exist", done == ["bhop_a/aaa111", "bhop_c/ccc333"])
    check("files gone from the store", not a.exists() and not c.exists())
    check("files in the trash", trash.trash_path(store, "bhop_a/aaa111").is_file())
    check("store glob doesn't see the trash", {p.name for p in store.glob("*/*.json.gz")} == {"bbb222.json.gz"})
    meta = server.read_meta(store)
    check("note moved out of meta.json", "bhop_a/aaa111" not in meta and meta.get("bhop_a/bbb222", {}).get("note") == "keep")
    check("collector knows deleted ids", {"aaa111", "ccc333", "bbb222"} <= collector.known_ids(store))

    # the collector reads yaw.log again: a deleted attempt in it must not come back
    saved = []
    known = collector.known_ids(store)
    for attempt in ({"id": "aaa111", "map": "bhop_a"}, {"id": "ddd444", "map": "bhop_a"}):
        if attempt["id"] not in known:
            saved.append(collector.save(store, {"format": 1, **attempt}))
    check("re-read saves only the new one", [p.name for p in saved] == ["ddd444.json.gz"])

    done = server.restore_attempts(store, ["bhop_a/aaa111", "bhop_a/zzz000"])
    check("restore brings back the trashed one", done == ["bhop_a/aaa111"] and a.is_file())
    check("note and tags back", server.read_meta(store).get("bhop_a/aaa111") == {"note": "new sens", "tags": ["pb"]})
    check("off the deleted list", "aaa111" not in trash.ids(store) and "ccc333" in trash.ids(store))

    check("fresh trash not purged", trash.purge(store) == [])
    gone = trash.purge(store, now=time.time() + 31 * 86400)
    check("old trash purged", gone == ["bhop_c/ccc333"] and not trash.trash_path(store, "bhop_c/ccc333").exists())
    check("purged id still known", "ccc333" in collector.known_ids(store))
    check("empty trash map folder removed", not (store / trash.TRASH / "bhop_c").exists())
    check("purged one can't be restored", server.restore_attempts(store, ["bhop_c/ccc333"]) == [])

print("all ok" if not failed else f"{failed} failed")
sys.exit(1 if failed else 0)
