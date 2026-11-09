"""Which recorded attempts are worth saving: surf replays and spectates are not.

Strafe Review's scope is bhop, including bhop bonuses on surf maps (PLAN.md, "Surf main tracks" under "Later / undecided").
Momentum reports surf mode for a whole map, bonuses included, so the map and track decide:

- Own runs are always saved.
- A replay or a spectated run on a surf_* map is skipped on the main track and on stages.
- On a bonus track it is saved only when it bhops: a chain of JUMP_CHAIN jumps or more,
  each within JUMP_GAP seconds of the last. Surf runs in the store never chain more than 2
  (one in ~500 reached 4, on a main track); bhop bonus replays chain 13 to 29.
"""

JUMP_CHAIN = 3
JUMP_GAP = 1.0  # seconds; a bhop jump lands in about 0.7 s at both 66 and 100 tick
JUMP_FROM = 50.0  # u/s: a jump is vz going from below this
JUMP_TO = 200.0  # to above this in one tick (Momentum's jump gives about +268 to +302)
BONUS = 2  # Momentum's TrackType: 0 main, 1 stage, 2 bonus


def jump_chain(attempt):
    """Longest run of jumps in the attempt where each follows the last within JUMP_GAP seconds."""
    cols = attempt.get("cols") or []
    if "tick" not in cols or "vz" not in cols:
        return 0
    it, iz = cols.index("tick"), cols.index("vz")
    interval = attempt.get("interval") or 0.01
    best = cur = 0
    last_jump = prev_vz = None
    for row in (attempt.get("rows") or "").split(";"):
        f = row.split(",")
        try:
            tick, vz = int(f[it]), float(f[iz])
        except (IndexError, ValueError):
            prev_vz = None
            continue
        if prev_vz is not None and prev_vz < JUMP_FROM and vz > JUMP_TO:
            t = tick * interval
            cur = cur + 1 if last_jump is not None and t - last_jump <= JUMP_GAP else 1
            best = max(best, cur)
            last_jump = t
        prev_vz = vz
    return best


def skip_reason(attempt):
    """Why the attempt should not be saved, or None to save it."""
    if attempt.get("label") not in ("replay", "spectate"):
        return None
    if not str(attempt.get("map") or "").lower().startswith("surf_"):
        return None
    track = attempt.get("track") or {}
    if track.get("type") != BONUS:
        return "surf main track or stage"
    if jump_chain(attempt) < JUMP_CHAIN:
        return "surf bonus without bhop"
    return None
