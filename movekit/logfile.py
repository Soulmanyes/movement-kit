"""Copy a program's output to a log file too (standard library only). A windowed exe has no console
and a background copy's output goes nowhere, so the file is all there is of it."""
import sys
import time

MAX = 1 << 20  # bytes; a longer log is started over


class Tee:
    """Writes to the console (if there is one) and to the log file."""

    def __init__(self, *streams):
        self.streams = [s for s in streams if s is not None]

    def write(self, text):
        for s in self.streams:
            try:
                s.write(text)
                s.flush()
            except (OSError, ValueError):
                pass
        return len(text)

    def flush(self):
        pass


def tee(path, max_bytes=MAX):
    """From now on, stdout and stderr also go to path (appended, started over past max_bytes)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > max_bytes:
            path.unlink()  # fails on Windows while another copy has it open; then it waits for the next start
    except OSError:
        pass
    try:
        f = open(path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - open for the program's life
    except OSError:
        return
    f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(sys.argv[1:]) or '(double-click)'}\n")
    sys.stdout = Tee(sys.stdout, f)
    sys.stderr = Tee(sys.stderr, f)
