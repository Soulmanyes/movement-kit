"""The Strafe Trainer's lines in the game: a `// movekit:strafe-trainer` block in autoexec.cfg
(movekit.cfgblock) that turns the console log on and binds the offset key.

    con_logfile yaw.log                         map loads (tickrate) and the offset key's echo
    unbind "<old key>"                          a key config.cfg still binds to the alias
    alias sourceyaw_offsets "echo SY_OFFSETS"   each press shows or hides the offset
    bind "<offset key>" "sourceyaw_offsets"

Until Phase 13 Source Yaw wrote these into yaws.cfg; the alias and token keep their names, so a
bind config.cfg saved back then still toggles, and the session (movekit/session.py) needs no change.
The offset key is left unbound while another tool binds the same key (movekit.keys), as Source Yaw
did when it was the cycle key. The block goes when the trainer is off or uninstalled.
"""
from pathlib import Path

from movekit import binds, cfgblock, games, keys

TOOL = "strafe-trainer"
BACKUP = ".bak-strafe-trainer"
OFFSETS_ALIAS = "sourceyaw_offsets"
OFFSETS_TOKEN = "SY_OFFSETS"


def _autoexec(game_dir):
    return Path(game_dir) / "cfg" / "autoexec.cfg"


def stale_keys(game_dir, key):
    """Keys config.cfg binds to the offset alias, other than `key`."""
    text = binds.cfg_text(Path(game_dir) / "cfg" / "config.cfg")
    return sorted(k for k in binds.keys_bound_to(text, OFFSETS_ALIAS) if k.lower() != (key or "").lower())


def conflicts(game_dir, key):
    """[(file name, command)] for binds of `key` to anything but the offset alias in the configs
    that run before the block would take the key over."""
    found = []
    for name in ("config.cfg", "autoexec.cfg"):
        for line in binds.cfg_text(Path(game_dir) / "cfg" / name).splitlines():
            bind = binds.parse_bind(binds.strip_comment(line))
            if not bind or bind[0].lower() != key.lower():
                continue
            command = bind[1].strip().strip('"')
            if command != OFFSETS_ALIAS:
                found.append((name, command))
    return found


def offset_key(cfg, game):
    """The key to bind: the saved one, "" when there is none or another tool binds it."""
    key = (cfg.get("offset_key") or "").lower()
    if not key or key in keys.held_by_others(TOOL, game):
        return ""
    return key


def block(cfg, game, game_dir):
    """The block's body lines for the saved settings `cfg`."""
    key = offset_key(cfg, game)
    lines = ["// the strafe trainer reads map loads and the offset key's echo from yaw.log",
             "con_logfile yaw.log"]
    lines += [f'unbind "{k}"' for k in stale_keys(game_dir, key)]
    if key:
        lines += [f'alias {OFFSETS_ALIAS} "echo {OFFSETS_TOKEN}"', f'bind "{key}" "{OFFSETS_ALIAS}"']
    return lines


def apply(game, cfg, game_dir=None):
    """Write (trainer on) or remove (off) the block for `game`, and record the offset key for the
    other tools' clash warnings. Returns the autoexec.cfg path, or None when the game isn't found."""
    game_dir = game_dir or games.find(game)
    keys.record(TOOL, game, [cfg.get("offset_key") or ""] if cfg.get("enabled") else [])
    if not game_dir:
        return None
    path = _autoexec(game_dir)
    if cfg.get("enabled"):
        cfgblock.set_block(path, TOOL, block(cfg, game, game_dir), True, BACKUP)
    else:
        cfgblock.set_block(path, TOOL, [], False, BACKUP)
    return path


def remove(game_dir):
    """Take the block out of the game's autoexec.cfg."""
    cfgblock.set_block(_autoexec(game_dir), TOOL, [], False, BACKUP)
