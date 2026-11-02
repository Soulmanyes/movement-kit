"""Strafe Review's game and data folders, found through movekit (the movement tools' shared code).

find_game(): MOMENTUM_DIR, else Momentum in any Steam library on this system (see movekit.steam).
data_dir(): %LOCALAPPDATA%\\strafe-review on Windows, $XDG_DATA_HOME/strafe-review elsewhere.

Every Strafe Review module imports this one before movekit, so the path to movekit is set here once:
from the repo it is two folders up; a PyInstaller exe has it bundled (build.py).
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
if not getattr(sys, "frozen", False) and (_REPO / "movekit").is_dir() and str(_REPO) not in sys.path:
    sys.path.insert(1, str(_REPO))
from movekit import games, paths  # after the path above
from movekit import steam as _steam


def find_game():
    """Momentum's game folder as a str, or None if it isn't installed where Steam keeps games."""
    game = _steam.game_dir(games.MOMENTUM)
    return str(game) if game else None


def data_dir():
    return paths.data_dir("strafe-review")


if __name__ == "__main__":
    print(find_game())
