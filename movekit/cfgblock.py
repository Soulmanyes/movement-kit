"""A tool's marked block of lines in a game cfg (autoexec.cfg), added or taken out without touching
the rest of the file. The file keeps its line endings (CRLF or LF); the block uses the same ones.

    // <tool> begin
    ...
    // <tool> end
"""
import shutil

from .files import write_atomic


def read_cfg(path):
    """The file's lines with their endings kept, and the line ending it uses (\\r\\n or \\n)."""
    text = path.read_text(encoding="utf-8", errors="surrogateescape", newline="") if path.exists() else ""
    return text.splitlines(keepends=True), "\r\n" if "\r\n" in text else "\n"


def without_block(lines, begin, end):
    """lines (each with its line ending) minus the block from begin to end; markers match with or
    without \\r."""
    out, inside = [], False
    for line in lines:
        bare = line.rstrip("\r\n")
        if bare == begin:
            inside = True
        elif bare == end and inside:
            inside = False
        elif not inside:
            out.append(line)
    return out


def set_block(path, block, add, backup_suffix):
    """Put block (its lines, first and last are the markers) at the end of the cfg at path, replacing
    an older copy, or take it out (add=False). Adding creates a missing file and, the first time,
    keeps a copy of the file as <name><backup_suffix>. Returns False if there was nothing to take
    out of (no file), else True."""
    lines, nl = read_cfg(path)
    if add and not path.exists():
        path.touch()
    if add:
        backup = path.with_name(path.name + backup_suffix)
        if not backup.exists():
            shutil.copy2(path, backup)
    elif not path.exists():
        return False
    lines = without_block(lines, block[0], block[-1])
    if add:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += nl
        lines += [line + nl for line in block]
    write_atomic(path, "".join(lines))
    return True
