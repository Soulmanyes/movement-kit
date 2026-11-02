"""A tool's marked block of lines in a game cfg (autoexec.cfg), added or taken out without touching
the rest of the file. The file keeps its line endings (CRLF or LF) and any bytes that aren't UTF-8;
the block uses the same line endings.

    // movekit:<tool> begin
    ...
    // movekit:<tool> end

<tool> is the tool's folder and tag prefix (sourceyaw, strafe-review). A block a tool wrote under
older markers (see `legacy` in set_block) is replaced where it stands, so the cfg's order stays
the same.
"""
import shutil

from .files import write_atomic


def markers(tool):
    """The begin and end marker lines of a tool's block."""
    return f"// movekit:{tool} begin", f"// movekit:{tool} end"


def read_cfg(path):
    """The file's lines with their endings kept, and the line ending it uses (\\r\\n or \\n)."""
    text = path.read_text(encoding="utf-8", errors="surrogateescape", newline="") if path.exists() else ""
    return text.splitlines(keepends=True), "\r\n" if "\r\n" in text else "\n"


def spans(lines, begin, end):
    """[(start, stop)] slices of lines (each with its line ending) holding a block from begin to end;
    markers match with or without \\r. A begin with no end runs to the end of the file."""
    found, start = [], None
    for i, line in enumerate(lines):
        bare = line.rstrip("\r\n")
        if start is None and bare == begin:
            start = i
        elif start is not None and bare == end:
            found.append((start, i + 1))
            start = None
    if start is not None:
        found.append((start, len(lines)))
    return found


def without_block(lines, begin, end):
    """lines minus every block from begin to end."""
    drop = {i for a, b in spans(lines, begin, end) for i in range(a, b)}
    return [line for i, line in enumerate(lines) if i not in drop]


def _backup(path, suffixes):
    """Keep a copy of a non-empty cfg as <name><suffixes[0]>, unless a copy under any of the
    suffixes exists already."""
    if path.exists() and path.stat().st_size and not any(
            path.with_name(path.name + s).exists() for s in suffixes):
        shutil.copy2(path, path.with_name(path.name + suffixes[0]))


def set_block(path, tool, body, add, backup_suffixes, legacy=None):
    """Put the tool's block (markers around the body lines) into the cfg at path, or take it out
    (add=False).

    An existing block, or one found by legacy(lines) (a function returning [(start, stop)] slices of
    the tool's older lines), is replaced where the first one stands and the others are dropped;
    with none, the block goes at the end after a blank line. Taking it out drops all of them and
    blank lines left at the end of the file. Adding creates a missing file. The file is only written
    when it changes, and the first change keeps a copy of a non-empty file (see _backup;
    backup_suffixes is a str or a tuple, the first is the one written). Returns False if there was
    nothing to take out of (no file), else True."""
    suffixes = (backup_suffixes,) if isinstance(backup_suffixes, str) else tuple(backup_suffixes)
    if not add and not path.exists():
        return False
    lines, nl = read_cfg(path)
    begin, end = markers(tool)
    found = sorted(set(spans(lines, begin, end) + (legacy(lines) if legacy else [])))
    drop = {i for a, b in found for i in range(a, b)}
    out = []
    for i, line in enumerate(lines):
        if add and found and i == found[0][0]:
            out += [line + nl for line in (begin, *body, end)]
        if i not in drop:
            out.append(line)
    if add and not found:
        if out and not out[-1].endswith("\n"):
            out[-1] += nl
        if out and out[-1].strip():
            out.append(nl)
        out += [line + nl for line in (begin, *body, end)]
    if not add and found:
        while out and not out[-1].strip():
            out.pop()
    text = "".join(out)
    if not path.exists() or text != "".join(lines):
        _backup(path, suffixes)
        write_atomic(path, text)
    return True
