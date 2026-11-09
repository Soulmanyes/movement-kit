"""Which game keys each tool binds, so a tool can warn about a key another tool already uses
without importing that tool (modules don't require each other).

One file, paths.data_dir("movekit")/binds.json: {tool: {game: [key, ...]}}. Each tool records its
own keys when it writes its binds, and forgets them when it is uninstalled. Keys are compared
without case, as the Source engine does.
"""
import json

from . import files, paths


def _file():
    return paths.data_dir("movekit") / "binds.json"


def _load():
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(data):
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    files.write_atomic(path, json.dumps(data, indent=1, sort_keys=True) + "\n")


def record(tool, game, keys):
    """Store the keys `tool` binds in `game` (replacing what it stored before). Empty keys drop out."""
    data = _load()
    keys = sorted({k.lower() for k in keys if k})
    per_tool = data.get(tool) if isinstance(data.get(tool), dict) else {}
    if keys:
        per_tool[game] = keys
    else:
        per_tool.pop(game, None)
    if per_tool:
        data[tool] = per_tool
    else:
        data.pop(tool, None)
    try:
        _save(data)
    except OSError:
        pass  # only the warning is lost


def forget(tool):
    """Drop every key `tool` recorded (its uninstall)."""
    data = _load()
    if data.pop(tool, None) is not None:
        try:
            _save(data)
        except OSError:
            pass


def held_by_others(tool, game):
    """{key: other tool} for the keys other tools bind in `game`."""
    out = {}
    for other, per_game in sorted(_load().items()):
        if other == tool or not isinstance(per_game, dict):
            continue
        for key in per_game.get(game) or []:
            if isinstance(key, str):
                out.setdefault(key.lower(), other)
    return out
