"""Valve's text KeyValues format, as Steam writes it in libraryfolders.vdf, appmanifest_*.acf and
localconfig.vdf. Two readers: pairs() for flat lookups, parse() when nesting matters."""
import re
from pathlib import Path

# "key" "value" pairs; nesting is not needed for the keys pairs() is used for
_PAIR = re.compile(r'"((?:[^"\\]|\\.)*)"\s+"((?:[^"\\]|\\.)*)"')


def unescape(s):
    """KeyValues strings escape backslashes ("D:\\\\SteamLibrary" on Windows)."""
    return re.sub(r"\\(.)", r"\1", s)


def pairs(path):
    """(key, value) pairs of a KeyValues file, in file order, keys lower-cased; [] if it can't be read."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [(k.lower(), unescape(v)) for k, v in _PAIR.findall(text)]


def parse(text):
    """KeyValues text -> nested dicts (keys lower-cased)."""
    tokens = re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text)
    pos = 0

    def block():
        nonlocal pos
        out = {}
        while pos < len(tokens):
            text, brace = tokens[pos]
            pos += 1
            if brace == "}":
                return out
            if brace == "{":
                continue  # stray brace; skip
            key = text.lower()
            nxt_text, nxt_brace = tokens[pos] if pos < len(tokens) else ("", "")
            pos += 1
            if nxt_brace == "{":
                out[key] = block()
            else:
                out[key] = nxt_text.replace('\\"', '"').replace("\\\\", "\\")
        return out

    return block()
