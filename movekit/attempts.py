"""Reads Strafe Review's saved attempts (attempt format 1, see strafe-review/FORMAT.md).

The collector writes each attempt as <store>/<map dir>/<id>.json.gz: the recorder's JSON exactly as
sent. This module is the reading side for any tool: find the files, load one, check its format number,
get its columns by name and list what a file breaks in the format. It changes nothing on disk.

Files are stored as recorded. The corrections the viewer makes when reading (FORMAT.md, "Reader
corrections") stay in the viewer; a tool that needs them has to apply them itself.
"""
import gzip
import json
import math
from pathlib import Path

from . import paths

FORMAT = 1  # the attempt format this module reads; FORMAT.md says when it goes up
SUFFIX = ".json.gz"

# Fields every attempt has (format 1). Everything else is optional; FORMAT.md gives each one's default.
REQUIRED = {"format": int, "id": str, "map": str, "interval": (int, float), "label": str, "cols": list, "rows": str}
OPTIONAL = {
    "started": int, "style": int, "track": dict, "player": (str, type(None)), "replayFile": (str, type(None)),
    "practice": bool, "version": str, "mouse": (dict, type(None)), "preRows": int, "postRows": int,
    "events": list, "reason": str, "runTime": (int, float), "gaps": int, "ended": int,
}
LABELS = {"own", "replay", "spectate"}  # known so far; new values keep format 1, so problems() allows them
REASONS = {"finish", "zone", "reset", "stop", "practice", "savestate", "replaced", "target", "level", "restart"}


class UnsupportedFormat(ValueError):
    """The file's format number is not one this module reads."""


def store():
    """The default attempt store: ~/.local/share/strafe-review/attempts, %LOCALAPPDATA% on Windows."""
    return paths.data_dir("strafe-review") / "attempts"


def files(where=None):
    """Every attempt file in the store, in no particular order."""
    return Path(where or store()).glob(f"*/*{SUFFIX}")


def attempt_id(path):
    """The attempt id a file holds, from its name."""
    return Path(path).name.removesuffix(SUFFIX)


def supported(attempt):
    """True when this module can read the attempt's format number."""
    return attempt.get("format") == FORMAT


def load(path):
    """The attempt in `path` as a dict. Raises UnsupportedFormat for another format number, and
    OSError, EOFError or ValueError for a file that can't be read."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        attempt = json.load(f)
    if not isinstance(attempt, dict):
        raise ValueError(f"{path}: not a JSON object")  # noqa: TRY004 - a bad file, like bad JSON: callers catch ValueError
    if not supported(attempt):
        raise UnsupportedFormat(f"attempt format {attempt.get('format')!r}, this reader knows {FORMAT}")
    return attempt


def columns(attempt, names=None):
    """{name: [float per row]} for the named columns, or all of them. A column the attempt doesn't have
    reads NaN on every row, so old files work with new column names."""
    cols = attempt.get("cols") or []
    rows = [r.split(",") for r in attempt["rows"].split(";")] if attempt.get("rows") else []
    out = {}
    for name in names or cols:
        if name in cols:
            i = cols.index(name)
            out[name] = [float(r[i]) for r in rows]
        else:
            out[name] = [math.nan] * len(rows)
    return out


def problems(attempt):
    """What the attempt breaks in format 1, as texts; [] for a good one. Unknown fields, columns,
    event kinds, labels and reasons are allowed (later additions)."""
    out = []
    if not supported(attempt):
        return [f"format {attempt.get('format')!r} is not {FORMAT}"]
    for name, kind in REQUIRED.items():
        if name not in attempt:
            out.append(f"missing {name}")
        elif not isinstance(attempt[name], kind) or isinstance(attempt[name], bool) and kind is not bool:
            out.append(f"{name} has type {type(attempt[name]).__name__}")
    for name, kind in OPTIONAL.items():
        value = attempt.get(name)
        if name in attempt and (not isinstance(value, kind) or isinstance(value, bool) and kind is not bool):
            out.append(f"{name} has type {type(value).__name__}")
    if out:
        return out
    if attempt["interval"] <= 0:
        out.append("interval is not above 0")
    cols = attempt["cols"]
    if "tick" not in cols:
        out.append("no tick column")
    if len(set(cols)) != len(cols):
        out.append("a column name appears twice")
    rows = attempt["rows"].split(";") if attempt["rows"] else []
    for i, row in enumerate(rows):
        values = row.split(",")
        if len(values) != len(cols):
            out.append(f"row {i} has {len(values)} values for {len(cols)} columns")
            break
        try:
            [float(v) for v in values]
        except ValueError:
            out.append(f"row {i} has a value that is not a number")
            break
    for name in ("preRows", "postRows"):
        if attempt.get(name, 0) > len(rows) or attempt.get(name, 0) < 0:
            out.append(f"{name} is outside the {len(rows)} rows")
    for i, event in enumerate(attempt.get("events", [])):
        if not isinstance(event, dict) or not isinstance(event.get("kind"), str) or "tick" not in event:
            out.append(f"event {i} has no kind or tick")
            break
    return out
