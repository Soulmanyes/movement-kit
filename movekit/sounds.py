"""Short game sounds (buttons/blip1...) played on the desktop: a tool's cue or a settings preview.

A sound is looked up as a loose file in the mod folder first, then in the game's sound VPKs
(games.Game.sound_vpks), and a file found in a VPK is extracted once into the cache.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import games, vpk

# short UI sounds to offer; a settings page lists only the ones this game install has
SOUNDS = ["buttons/blip1", "buttons/blip2", "buttons/button10", "buttons/button11",
          "buttons/button14", "buttons/button15", "buttons/button16", "buttons/button17",
          "buttons/button18", "buttons/button19"]

CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "movekit/sounds"


def sound_file(mod_dir, sound, game="css", cache=None):
    """Local file for a `play` sound name like buttons/blip1, extracting it if needed, or None.
    `mod_dir` is the game's mod folder (cstrike, momentum)."""
    cache = Path(cache) if cache else CACHE
    install = Path(mod_dir).parent
    for ext in (".wav", ".mp3"):
        rel = f"sound/{sound}{ext}"
        loose = Path(mod_dir) / rel
        if loose.is_file():
            return loose
        cached = cache / game / f"{sound}{ext}"
        if cached.is_file():
            return cached
        for vpk_name in games.GAMES[game].sound_vpks:
            try:
                data = vpk.read_file(install / vpk_name, rel)
            except (OSError, ValueError):
                continue
            if data:
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_bytes(data)
                return cached
    return None


def available(mod_dir, game="css", cache=None):
    return [s for s in SOUNDS if sound_file(mod_dir, s, game, cache)]


def play(mod_dir, sound, game="css", cache=None):
    """Plays a game sound on the desktop. False if the game doesn't have it or nothing can play it."""
    path = sound_file(mod_dir, sound, game, cache)
    if not path:
        return False
    if sys.platform == "win32":
        import winsound  # async: a new sound cuts the last one short
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return True
    for player in (["pw-play"], ["paplay"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
        if shutil.which(player[0]):
            subprocess.Popen([*player, str(path)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
    return False
