"""Writing files so a crash or a full disk never leaves a half-written one behind."""
import os
import stat
import tempfile


def _umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


def write_atomic(path, text):
    """Write text (UTF-8, line endings as given) to path through a temporary file in the same folder.
    Bytes read with errors="surrogateescape" are written back unchanged. A replaced file keeps its
    mode; a new one gets the usual mode for a new file (0644 with the common umask 022)."""
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except FileNotFoundError:
        mode = 0o666 & ~_umask()
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
