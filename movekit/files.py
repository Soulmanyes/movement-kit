"""Writing files so a crash or a full disk never leaves a half-written one behind."""
import os
import tempfile


def write_atomic(path, text):
    """Write text (UTF-8, line endings as given) to path through a temporary file in the same folder.
    A file it creates gets the temporary file's mode (0600 on Linux), and a replaced file takes it too."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
