"""Binds and aliases in a Source game's cfg files.

Only parsing lives here. What a command means to a tool (Source Yaw's roles, its own aliases)
stays in the tool. Callers strip comments (strip_comment) or quotes themselves.
"""

import glob
import re
from pathlib import Path

# bind KEY COMMAND, with the key quoted or not and any case or spacing
BIND = re.compile(r'^\s*bind\s+(?:"([^"]+)"|(\S+))\s+(.*?)\s*$', re.IGNORECASE)
ALIAS = re.compile(r'^\s*alias\s+"?([^\s"]+)"?\s+"?(.*?)"?\s*(//.*)?$', re.IGNORECASE)
ALIAS_DEPTH = 6  # how deep resolve() follows aliases into aliases


def cfg_text(path):
    """The file's text, or "" if it can't be read."""
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


def strip_comment(line):
    """line up to a `//` comment; a `//` inside quotes (`say "http://x"`) is not one."""
    quoted = False
    for i, c in enumerate(line):
        if c == '"':
            quoted = not quoted
        elif not quoted and line.startswith("//", i):
            return line[:i]
    return line


def parse_bind(line):
    """(key, rest of the line) for a bind line, or None. Neither is lowercased or stripped of
    quotes or comments."""
    m = BIND.match(line)
    return (m.group(1) or m.group(2), m.group(3)) if m else None


def keys_bound_to(text, command):
    """Keys bound to exactly `command`, in the strict form the game writes config.cfg in:
    `bind "KEY" "COMMAND"` at the start of a line."""
    return re.findall(rf'^bind "([^"]+)" "{re.escape(command)}"', text, re.MULTILINE)


def aliases(cfg_dir):
    """{lowercased alias name: [bodies, in file order]} from every cfg under cfg_dir."""
    found = {}
    for path in sorted(glob.glob(str(Path(cfg_dir) / "**/*.cfg"), recursive=True)):
        try:
            text = Path(path).read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            m = ALIAS.match(line)
            if m:
                found.setdefault(m.group(1).lower(), []).append(m.group(2))
    return found


def commands(text):
    """The lowercased first word of each ;-separated command in text."""
    return [c.strip().strip('"').split()[0].lower() for c in text.split(";") if c.strip().strip('"')]


def resolve(command, wanted, alias_map, depth=0):
    """{wanted[cmd]} for each command in `command` found in `wanted`, following aliases from
    alias_map up to ALIAS_DEPTH levels deep."""
    found = set()
    for cmd in commands(command):
        if cmd in wanted:
            found.add(wanted[cmd])
        elif depth < ALIAS_DEPTH and cmd in alias_map:
            for body in alias_map[cmd]:
                found |= resolve(body, wanted, alias_map, depth + 1)
    return found
