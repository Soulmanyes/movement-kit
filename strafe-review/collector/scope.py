"""Which recorded attempts are worth saving: on surf maps, only bonuses that bhop.

Strafe Review's scope is bhop, including bhop bonuses on surf maps; surfing itself is out (owner, 2026-11-23).
Momentum reports surf mode for a whole map, bonuses included, so the map and track decide,
the same for own runs, replays and spectated runs:

- Anything on a map that isn't surf_* is saved.
- On a surf_* map the main track and stages are skipped.
- A bonus is saved only when it bhops: a chain of JUMP_CHAIN jumps or more, each JUMP_GAP_MIN to
  JUMP_GAP seconds after the last. Bhop jumps on bhop maps land 0.6-0.9 s apart (13,000 gaps in the
  store); surf bonuses chained 3-6 jumps through boosters and ramps (surf_nova b2, surf_ofrenda b2,
  0.2-0.5 s or 1.4 s apart), while bhop bonuses (surf_aura b1, surf_tequila b4) chain 6 to 30+.
"""

JUMP_CHAIN = 6
JUMP_GAP_MIN = 0.55  # seconds: closer jumps are boosters or ramps, not bhop
JUMP_GAP = 1.0  # seconds; a bhop jump lands in about 0.7 s at both 66 and 100 tick
JUMP_FROM = 50.0  # u/s: a jump is vz going from below this
JUMP_TO = 200.0  # to above this in one tick (Momentum's jump gives about +268 to +302)
BONUS = 2  # Momentum's TrackType: 0 main, 1 stage, 2 bonus


def jump_chain(attempt):
    """Longest run of jumps in the attempt where each follows the last by JUMP_GAP_MIN to JUMP_GAP seconds."""
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
            cur = cur + 1 if last_jump is not None and JUMP_GAP_MIN <= t - last_jump <= JUMP_GAP else 1
            best = max(best, cur)
            last_jump = t
        prev_vz = vz
    return best


def skip_reason(attempt):
    """Why the attempt should not be saved, or None to save it."""
    if not str(attempt.get("map") or "").lower().startswith("surf_"):
        return None
    track = attempt.get("track") or {}
    if track.get("type") != BONUS:
        return "surf main track or stage"
    if jump_chain(attempt) < JUMP_CHAIN:
        return "surf bonus without bhop"
    return None
