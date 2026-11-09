#!/usr/bin/env python3
"""Checks scope.py: which attempts the collector skips. Synthetic attempts, no game or store needed.

Usage: python3 check_scope.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import jump_chain, skip_reason

COLS = ["tick", "gain", "vz"]
INTERVAL = 1 / 66


def rows(jump_ticks, length):
    """vz per tick: +290 on a jump tick, falling 12 per tick after it, 0 on the tick before each jump (landed)."""
    vz, out = 0.0, []
    for t in range(length):
        if t in jump_ticks:
            vz = 290.0
        elif t + 1 in jump_ticks:
            vz = 0.0
        else:
            vz = max(vz - 12.0, -300.0)
        out.append(f"{t},0,{vz}")
    return ";".join(out)


def attempt(label, track_type, jump_ticks=(), length=400, map_name="surf_artois"):
    return {
        "map": map_name,
        "label": label,
        "track": {"type": track_type, "number": 1},
        "interval": INTERVAL,
        "cols": COLS,
        "rows": rows(set(jump_ticks), length),
    }


BHOP = range(10, 400, 46)  # a jump every 0.7 s
SURF = (10, 200)  # two jumps 2.9 s apart

CASES = [
    ("own surf main run", attempt("own", 0, SURF), None),
    ("own on a bonus without jumps", attempt("own", 2), None),
    ("bhop map replay", attempt("replay", 0, SURF, map_name="bhop_ambience"), None),
    ("bhop map spectate", attempt("spectate", 0, map_name="bhop_glacial"), None),
    ("surf main replay", attempt("replay", 0, SURF), "surf main track or stage"),
    ("surf main replay that bhops", attempt("replay", 0, BHOP), "surf main track or stage"),
    ("surf stage spectate", attempt("spectate", 1, SURF), "surf main track or stage"),
    ("SURF_ upper case", attempt("replay", 0, SURF, map_name="SURF_Mesa"), "surf main track or stage"),
    ("surf bonus replay that bhops", attempt("replay", 2, BHOP), None),
    ("surf bonus replay that surfs", attempt("replay", 2, SURF), "surf bonus without bhop"),
    ("surf bonus replay fragment", attempt("replay", 2, length=27), "surf bonus without bhop"),
    ("surf bonus spectate that bhops", attempt("spectate", 2, BHOP), None),
]


def main():
    bad = 0
    for name, a, want in CASES:
        got = skip_reason(a)
        ok = got == want
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {name}: {got!r}" + ("" if ok else f" (wanted {want!r})"))
    for name, ticks, want in [("bhop", BHOP, len(BHOP)), ("surf", SURF, 1), ("none", (), 0), ("pair", (10, 60), 2)]:
        got = jump_chain(attempt("replay", 2, ticks))
        ok = got == want
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} jump_chain {name}: {got}" + ("" if ok else f" (wanted {want})"))
    broken = attempt("replay", 2, BHOP)
    broken["rows"] += ";x,,;;5"
    ok = jump_chain(broken) == len(BHOP)
    bad += not ok
    print(f"{'ok ' if ok else 'BAD'} jump_chain skips broken rows")
    print("all passed" if not bad else f"{bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
