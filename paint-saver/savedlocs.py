"""Momentum's savedlocs.txt: the savestate file, one block per map. Paint Saver keeps each map's saved paint
in a block of its own, "zzpaint_<map>", that the HUD script imports with mom_saveloc_import, replays and
deletes again, so the player's own savestates never change.

The game reads the file once, at launch, and writes all of it back from memory on every map change, so
this only edits it while the game is closed (the launch hook, before the game starts). Edits are textual:
everything but the zzpaint_ blocks and leftover paint entries keeps its exact bytes. Standard library only.
"""
import os
import re
import shutil
import time
from pathlib import Path

PREFIX = "zzpaint_"
# a top-level block: \t"name"\n\t{ ... \n\t}\n (the game writes tabs and \n)
_TOP = re.compile(r'^\t"([^"]*)"\n\t\{\n(.*?)^\t\}\n', re.MULTILINE | re.DOTALL)
# one savestate inside a map block's "cps" list
_CPS = re.compile(r'(^\t\t"cps"\n\t\t\{\n)(.*?)(^\t\t\}\n)', re.MULTILINE | re.DOTALL)
_ENTRY = re.compile(r'^\t\t\t"(\d+)"\n\t\t\t\{\n(.*?)^\t\t\t\}\n', re.MULTILINE | re.DOTALL)
_FIELD = re.compile(r'^\t\t\t\t"([^"]+)"\t\t"([^"]*)"$', re.MULTILINE)

# a savestate's fields as the game writes them (Momentum 0.10.x, savedlocs.txt), zero velocity: a moving
# savestate shifts the paint by its first tick of movement (owner, probe run 1)
_FIELDS = ("ang", "canBounce", "components", "crouched", "dfDoubleJumping", "dfJumpTime",
           "dfRemainingDamageBoost", "dfRemainingFlight", "dfRemainingHaste", "dfRemainingSlick", "dfTimer",
           "dfTimerFlags", "disabledButtons", "duckAmount", "gravityScale", "groundPosZ", "movementLagScale",
           "pos", "predictedOrigin", "predictedVel", "stamina", "targetClassName", "time", "toggledButtons",
           "track", "vel", "zone")
_FIXED = {"canBounce": "1", "components": "-1", "dfDoubleJumping": "0", "dfJumpTime": "0",
          "dfRemainingDamageBoost": "0", "dfRemainingFlight": "0", "dfRemainingHaste": "0",
          "dfRemainingSlick": "0", "dfTimer": "160", "dfTimerFlags": "2", "disabledButtons": "0",
          "gravityScale": "1.000000", "movementLagScale": "1.000000", "predictedVel": "0.000000 0.000000 0.000000",
          "stamina": "0.000000", "targetClassName": "player", "time": "-1", "toggledButtons": "0", "track": "0",
          "vel": "0.000000 0.000000 0.000000", "zone": "0"}


def block_name(map_name):
    return PREFIX + map_name.lower()


def _vec(v):
    return " ".join(f"{float(x):.6f}" for x in v)


def entry(index, sample):
    """One cps entry. sample: {"pos": [x, y, z], "ang": [pitch, yaw, roll], "duck": 0|1}."""
    duck = 1 if sample.get("duck") else 0
    values = dict(_FIXED)
    values.update({"ang": _vec(sample["ang"]), "pos": _vec(sample["pos"]), "predictedOrigin": _vec(sample["pos"]),
                   "groundPosZ": f"{float(sample['pos'][2]):.6f}", "crouched": str(duck),
                   # duckAmount 0 even when crouched, as the game writes it: 1 left the duck mid-transition and
                   # a crouched line replayed wobbly (probe run 3)
                   "duckAmount": "0.000000"})
    body = "".join(f'\t\t\t\t"{k}"\t\t"{values[k]}"\n' for k in _FIELDS)
    return f'\t\t\t"{index:09d}"\n\t\t\t{{\n{body}\t\t\t}}\n'


def block(map_name, samples):
    entries = "".join(entry(i, s) for i, s in enumerate(samples))
    return (f'\t"{block_name(map_name)}"\n\t{{\n\t\t"cur"\t\t"-1"\n\t\t"cps"\n\t\t{{\n{entries}\t\t}}\n\t}}\n')


def _close(a, b, tol=0.01):
    try:
        xs = [float(x) for x in a.split()]
        ys = [float(y) for y in b.split()]
    except ValueError:
        return False
    return len(xs) == len(ys) and all(abs(x - y) <= tol for x, y in zip(xs, ys, strict=True))


def _is_sample(fields, sample):
    """True when a savestate's pos and ang match the paint sample's."""
    pos, ang = fields.get("pos"), fields.get("ang")
    return (pos is not None and ang is not None and _close(pos, _vec(sample["pos"]))
            and _close(ang, _vec(sample["ang"])))


def _leftover_run(fields, i, paint):
    """How many entries from i on are a cut-short restore's leftovers: a run matching the paint samples
    from the first on, in order (the HUD script deletes the imported entries from the top, so what a quit
    leaves is the start of the sequence). At least 2 long, or the whole sequence when it is shorter, so a
    savestate the player made where they painted a dot is never taken for one. 0 when it isn't."""
    n = 0
    while i + n < len(fields) and n < len(paint) and _is_sample(fields[i + n], paint[n]):
        n += 1
    return n if n >= min(2, len(paint)) else 0


def _clean_map_block(body, paint):
    """A map block's text without leftover paint entries, the rest renumbered in order. (text, removed)."""
    m = _CPS.search(body)
    if not m or not paint:
        return body, 0
    bodies = [e.group(2) for e in _ENTRY.finditer(m.group(2))]
    fields = [dict(_FIELD.findall(b)) for b in bodies]
    kept, removed, i = [], 0, 0
    while i < len(bodies):
        n = _leftover_run(fields, i, paint)
        if n:
            removed += n
            i += n
        else:
            kept.append(bodies[i])
            i += 1
    if not removed:
        return body, 0
    entries = "".join(f'\t\t\t"{i:09d}"\n\t\t\t{{\n{b}\t\t\t}}\n' for i, b in enumerate(kept))
    return body[:m.start(2)] + entries + body[m.end(2):], removed


def rewrite_text(text, paint_by_map, leftovers=None):
    """The file's text with every zzpaint_ block replaced by paint_by_map ({map: [samples]}, empty lists
    dropped) and leftover paint entries removed from the maps' own blocks: entries of leftovers ({map:
    [samples]} as the last write had them, as a slid point moves; default paint_by_map). (text, report)."""
    if leftovers is None:
        leftovers = paint_by_map
    if not text.strip():
        text = '"MOMSavelocSystem"\n{\n}\n'
    out, pos, removed = [], 0, {}
    for m in _TOP.finditer(text):
        name, body = m.group(1), m.group(2)
        out.append(text[pos:m.start()])
        pos = m.end()
        if name.lower().startswith(PREFIX):
            continue
        paint = leftovers.get(name.lower()) or []
        new_body, n = _clean_map_block(body, paint)
        if n:
            removed[name] = n
        out.append(f'\t"{name}"\n\t{{\n{new_body}\t}}\n' if n else m.group(0))
    rest = text[pos:]
    end = rest.rstrip().rfind("}")
    if end < 0:
        raise ValueError("savedlocs.txt has no closing brace")
    blocks = "".join(block(name, s) for name, s in sorted(paint_by_map.items()) if s)
    out.append(rest[:end] + blocks + rest[end:])
    return "".join(out), {"removed": removed, "maps": sorted(k for k, v in paint_by_map.items() if v)}


def rewrite(path, paint_by_map, backup=True, leftovers=None):
    """Rewrites savedlocs.txt in place (temp file + rename). A first backup per day goes next to it."""
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    new, report = rewrite_text(text, paint_by_map, leftovers)
    if new == text:
        return report
    if backup and path.exists():
        bak = path.with_name(f"{path.name}.bak-paint-saver-{time.strftime('%Y-%m-%d')}")
        if not bak.exists():
            shutil.copy2(path, bak)
    tmp = path.with_name(path.name + ".tmp-paint-saver")
    tmp.write_text(new, encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return report
