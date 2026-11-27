"""Paint Saver's saved paint (paint.json) and the yaw.log reader that adds to it.

The HUD script (movekit-paint-saver.ts) logs, while the paint key is held:
  MK_PAINT_DOWN {"c": "<mom_paint_color>", "s": "<mom_paint_size>"}   a stroke starts
  MK_PAINT_S {"d": 0|1}                                                then a getpos line, once a tick
  MK_PAINT_UP                                                          the stroke ends
and on the player's commands MK_PAINT_SAVE (mk_savepaint) and MK_PAINT_CLEAR (mk_clearpaint).
The map comes from the engine's "Host_NewGame on map <name>".
A replay (mk_loadpaint) logs MK_PAINT_RESTORE {"map", "total"} and then, for each point it went to,
MK_PAINT_R {"k": n} and a getpos line: where the game put the player at the n-th point (1-based, replay
order). A point that landed somewhere else is written differently next time: higher or lower when it only
missed up or down, else moved back along its aim (shift(), _adjust()).

A stroke is pending until MK_PAINT_SAVE on its map adds every pending stroke of that map (this session,
reloads included) to the saved paint. MK_PAINT_CLEAR drops the map's saved paint and pending strokes.
Strokes the replay paints are not logged, so saving after a restore adds only the new ones.

paint.json: {"version": 1, "maps": {map: [stroke, ...]}, "log": {"offset": n, "head": sha1, "map": last map},
             "plan": replay_plan(maps) as last written to savedlocs.txt (install.py)}
stroke: {"c": "r g b a", "s": "size", "p": [[x, y, z, pitch, yaw, duck(, slide, tries, lift)], ...]}
slide: how far the point is moved along its aim (negative: back); tries: how many replays found it
off, -1 once given up (all 0 again); lift: how much higher than usual its savestate is written.
Standard library only.
"""
import hashlib
import json
import math
import re
from pathlib import Path

VERSION = 1
HEAD = 4096  # bytes of the log hashed to tell a new log file from the one the offset belongs to
_MAP = re.compile(r"Host_NewGame on map (\S+)")
_MARK = re.compile(r"\bMK_PAINT_(DOWN|S|UP|SAVE|CLEAR|RESTORE|R)\b ?(\{.*\})?")
# getpos's answer; the engine sometimes glues it to the line before ("...save/restore.setpos ...")
_POS = re.compile(r"setpos (-?[\d.]+) (-?[\d.]+) (-?[\d.]+);setang (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)")


def empty():
    return {"version": VERSION, "maps": {}, "log": {}}


def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty()
    if not isinstance(data, dict) or not isinstance(data.get("maps"), dict):
        return empty()
    data.setdefault("log", {})
    return data


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(path)


def _json(text):
    try:
        v = json.loads(text) if text else {}
    except ValueError:
        return {}
    return v if isinstance(v, dict) else {}


def apply_lines(lines, maps, current=""):
    """Reads log lines into maps ({map: [stroke]}, changed in place); current is the map loaded before the
    first line. Returns {"strokes": n new pending, "saved": [maps saved], "cleared": [maps cleared],
    "dropped": n strokes never saved, "map": the map loaded after the last line}."""
    pending = {}
    stroke = None
    want = None  # duck flag of the sample whose getpos line comes next
    # the replay order of the paint as last written (before this log's saves and clears change it): what
    # the replay's k counts in
    order = {m: [p for r in replay_runs(s) for p in r["p"]] for m, s in maps.items()}
    replay = None  # the points of the replay running in the log, or None
    point = None  # the replayed point whose getpos line comes next
    seen = {}  # id(point): (point, landed where it should) from the last replay that reached it
    report = {"saved": [], "cleared": [], "strokes": 0}
    for line in lines:
        m = _MAP.search(line)
        if m:
            current = m.group(1).lower()
            stroke, want, replay, point = None, None, None, None
            continue
        if want is not None or point is not None:
            p = _POS.search(line)
            if p:
                v = [float(x) for x in p.groups()]
                if want is not None and stroke is not None:
                    stroke["p"].append([*v[:3], v[3], v[4], want])
                if point is not None:
                    seen[id(point)] = (point, None if _landed(point, v[:3]) else v[:3])
                want, point = None, None
                continue
            # a line between the marker and its getpos answer (another script's output): keep waiting
            # for one line only, so a lost answer can't pull in a later manual getpos
            want, point = None, None
        k = _MARK.search(line)
        if not k:
            continue
        kind, data = k.group(1), _json(k.group(2))
        if kind == "RESTORE":
            pts = order.get(str(data.get("map", "")).lower())
            # another plan's replay, or one from before the settle wait (v 2), whose first reads ran high
            replay = pts if pts and data.get("total") == len(pts) and data.get("v") == 2 else None
        elif kind == "R":
            n = data.get("k")
            ok = replay is not None and isinstance(n, int) and 1 <= n <= len(replay)
            point = replay[n - 1] if ok else None
        elif kind == "DOWN":
            stroke = {"c": str(data.get("c", "")), "s": str(data.get("s", "")), "p": []}
        elif kind == "S":
            want = 1 if data.get("d") else 0
        elif kind == "UP":
            if stroke and stroke["p"] and current:
                pending.setdefault(current, []).append(stroke)
                report["strokes"] += 1
            stroke = None
        elif kind == "SAVE" and current:
            maps.setdefault(current, []).extend(pending.pop(current, []))
            if not maps[current]:
                maps.pop(current)
            report["saved"].append(current)
        elif kind == "CLEAR" and current:
            maps.pop(current, None)
            pending.pop(current, None)
            report["cleared"].append(current)
    report["dropped"] = sum(len(v) for v in pending.values())
    report["map"] = current
    report["moved"], report["stuck"] = 0, 0
    for p, got in seen.values():
        if got is None or (len(p) > 7 and p[7] < 0):
            continue
        p[6:] = _adjust(p, got)
        report["moved" if p[7] > 0 else "stuck"] += 1
    return report


def _head(path, n):
    """sha1 of the log's first n bytes (n at most HEAD: a short log grows, so the bookmark hashes only what
    it had)."""
    with open(path, "rb") as f:
        return hashlib.sha1(f.read(min(n, HEAD))).hexdigest()


def read_log(log_path, data):
    """Adds the log's new part (since data["log"]) to data. The first run only bookmarks the end, so a
    log from before the install adds nothing. Returns apply_lines' report, or None when nothing was read."""
    log_path = Path(log_path)
    try:
        size = log_path.stat().st_size
        mark = data.get("log") or {}
        if "offset" not in mark:
            data["log"] = {"offset": size, "head": _head(log_path, size)}
            return None
        start = mark.get("offset", 0)
        if start > size or mark.get("head") != _head(log_path, start):
            start = 0  # a new or emptied log
    except OSError:
        return None
    with open(log_path, "rb") as f:
        f.seek(start)
        raw = f.read()
    end = raw.rfind(b"\n") + 1  # a cut last line waits for the next run
    text = raw[:end].decode("utf-8", errors="replace")
    report = apply_lines(text.splitlines(), data["maps"], mark.get("map", "") if start else "")
    data["log"] = {"offset": start + end, "head": _head(log_path, start + end), "map": report["map"]}
    return report


def replay_runs(strokes):
    """The strokes cut into runs of standing or crouched samples, every standing run first. Going from a
    crouched savestate to a standing one un-crouches the player in the air, which lifts them, so marks
    painted after a crouched one landed too high (owner, 2026-11-27); standing to crouched is fine."""
    runs = []
    for s in strokes:
        for p in s["p"]:
            if runs and runs[-1]["src"] is s and runs[-1]["p"][-1][5] == p[5]:
                runs[-1]["p"].append(p)
            else:
                runs.append({"c": s["c"], "s": s["s"], "p": [p], "src": s})
    return [{"c": r["c"], "s": r["s"], "p": r["p"]} for r in sorted(runs, key=lambda r: r["p"][0][5])]


# getpos gives the eye minus the standing eye height (64), not the feet: crouched on flat ground it read
# 17.00 lower than standing there (owner's paint.json, 2026-11-27). Paint comes from the eye, so a replay
# step is right when getpos there reads what it read while painting, whatever duck state the game leaves.
# Going to an imported savestate puts the player its eye height above its pos (Momentum 0.10.x; the
# player's own savestates don't do this). Probe on surf_ruse, 2026-11-27, getpos one tick after each goto:
# standing entries read pos z + 64 (63.91 when in the air: one tick of fall), crouched ones written at the
# floor's height or lower + 47 and stayed crouched. (Crouched ones written 17 above the floor came out
# standing, 55.5 up.) So each sample is written that much lower.
LIFT_STANDING = 64.0
LIFT_CROUCHED = 47.0


# A point that lands off its spot straight up or down is written that much the other way, up to
# _LIFT_TRIES times. Seen on surf_ruse (stage 1 start, 2026-11-27): a line painted in noclip just above
# a playerclip spawn tube landed 12 low. Its spots were free, but their savestates, written 64 below,
# were inside the tube, and from inside a brush the import's lift is 52, not 64. Points written in the
# clear landed right. A point that still misses, or that moved sideways, is blocked where it is (the body
# in a wall), and moves back along its aim. A mark lands where the eye's line along the aim first hits a
# surface, so further back on that line paints the same mark (unless the eye was inside something behind
# it). Never forward: that goes past the marked surface.
_LAND_XY = 1.0  # how far a replayed point may land from its own spot and still count as placed
_LAND_Z = 2.0  # the replay reads getpos a tick after the goto: up to a few frames of fall in the air
_MARGIN = 4.0
_STEP = 16.0  # the least a slide back moves
_MAX_SLIDE = 512.0
_LIFT_TRIES = 2
MAX_TRIES = 5


def _aim(p):
    pitch, yaw = math.radians(p[3]), math.radians(p[4])
    return [math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), -math.sin(pitch)]


def _state(p):
    """[slide, tries, lift] of a point."""
    s = [0.0, 0, 0.0]
    s[:len(p[6:9])] = p[6:9]
    return s


def shift(p):
    """The point's spot (getpos's x, y, z) moved by its slide along the aim."""
    d = _state(p)[0]
    return [v + d * a for v, a in zip(p[:3], _aim(p), strict=True)]


def _landed(p, got):
    want = shift(p)
    return (abs(got[0] - want[0]) <= _LAND_XY and abs(got[1] - want[1]) <= _LAND_XY
            and abs(got[2] - want[2]) <= _LAND_Z)


def _adjust(p, got):
    """[slide, tries, lift] for a point a replay found off its spot, at got (getpos's x, y, z)."""
    slide, tries, lift = _state(p)
    if tries + 1 >= MAX_TRIES:
        return [0.0, -1, 0.0]
    push = [g - w for g, w in zip(got, shift(p), strict=True)]
    if not slide and tries < _LIFT_TRIES and abs(push[0]) <= _LAND_XY and abs(push[1]) <= _LAND_XY:
        return [0.0, tries + 1, lift - push[2]]
    size = math.sqrt(sum(v * v for v in push))
    return [max(-_MAX_SLIDE, slide - max(_STEP, size + _MARGIN)), tries + 1, 0.0]


def stuck(strokes):
    """How many points nothing placed."""
    return sum(1 for s in strokes for p in s["p"] if len(p) > 7 and p[7] < 0)


def samples(strokes):
    """The strokes' samples as savedlocs.py takes them, in replay order (replay_runs)."""
    out = []
    for r in replay_runs(strokes):
        for p in r["p"]:
            x, y, z = shift(p)
            z += _state(p)[2] - (LIFT_CROUCHED if p[5] else LIFT_STANDING)
            out.append({"pos": [x, y, z], "ang": [p[3], p[4], 0.0], "duck": p[5]})
    return out


def replay_plan(maps):
    """{map: [[color, size, sample count, crouched 0|1], ...]} for the HUD script, one per replay run
    (replay_runs). The script holds +duck through a crouched run: a crouched savestate gone to without it
    stands up over the next ten steps, 17 higher (probe, 2026-11-27)."""
    return {m: [[r["c"], r["s"], len(r["p"]), r["p"][0][5]] for r in replay_runs(strokes)]
            for m, strokes in sorted(maps.items()) if strokes}
