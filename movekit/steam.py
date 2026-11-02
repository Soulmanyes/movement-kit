"""Steam installs on this system, their game libraries, and a game's folder in them.

A Steam root is an install folder (it holds steamapps/libraryfolders.vdf). Each root lists its
libraries; a library holds a game when one of its steamapps/appmanifest_*.acf files is the game's
(by app id, or by name for builds with other ids), and the manifest's installdir names the folder.
All Windows and Flatpak specifics are in this file.
"""
import os
import sys
from pathlib import Path

from . import keyvalues

FLATPAK_DATA = Path.home() / ".var/app/com.valvesoftware.Steam/.local/share"


def _existing(roots):
    """The folders that exist, without duplicates (by real path), in order."""
    seen, out = set(), []
    for r in roots:
        if os.path.isdir(r):
            real = os.path.realpath(r)
            if real not in seen:
                seen.add(real)
                out.append(Path(r))
    return out


def flatpak_roots():
    """Flatpak Steam's root, if it is installed. Helpers started from its launch options run inside
    its sandbox, so a tool that needs them may want to leave it out (steam_roots(flatpak=False))."""
    return [] if sys.platform == "win32" else _existing([FLATPAK_DATA / "Steam"])


def steam_roots(flatpak=True):
    """Steam install folders on this system that exist, without duplicates."""
    if sys.platform == "win32":
        roots = []
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                roots.append(winreg.QueryValueEx(key, "SteamPath")[0])
        except OSError:
            pass
        roots.append(os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Steam"))
        return _existing(roots)
    home = Path.home()
    roots = [
        Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share") / "Steam",
        home / ".local/share/Steam",  # Steam's own default, also when XDG_DATA_HOME points elsewhere
        home / ".steam/steam",
    ]
    if flatpak:
        roots.append(FLATPAK_DATA / "Steam")
    return _existing(roots)


def libraries(root):
    """The library folders of one Steam root, the root itself first."""
    libs = [Path(root)]
    for key, value in keyvalues.pairs(Path(root) / "steamapps" / "libraryfolders.vdf"):
        if key == "path":
            libs.append(Path(value))
    return libs


def _install_dirs(library, game):
    """Folder names under steamapps/common that may hold the game, best guess first."""
    names = []
    for appid in game.appids:
        kv = dict(keyvalues.pairs(library / "steamapps" / f"appmanifest_{appid}.acf"))
        if kv.get("installdir"):
            names.append(kv["installdir"])
    if game.name_hint:
        for acf in sorted((library / "steamapps").glob("appmanifest_*.acf")):
            kv = dict(keyvalues.pairs(acf))
            if game.name_hint in kv.get("name", "").lower() and kv.get("installdir"):
                names.append(kv["installdir"])
    return names + list(game.folders)


def game_in(library, game):
    """The game's mod folder (the one holding cfg/) in one library, or None."""
    for name in _install_dirs(Path(library), game):
        mod = Path(library) / "steamapps" / "common" / name / game.mod
        if (mod / "cfg").is_dir():
            return mod
    return None


def game_dir(game, roots=None):
    """The game's mod folder as a Path, or None if it isn't installed where Steam keeps games.

    roots: the Steam roots to search, steam_roots() if not given. Only then does the game's
    environment variable (Game.env) override the search.
    """
    if roots is None:
        if game.env and os.environ.get(game.env):
            return Path(os.environ[game.env])
        roots = steam_roots()
    seen = set()
    for root in roots:
        for lib in libraries(root):
            real = os.path.realpath(lib)
            if real in seen:
                continue
            seen.add(real)
            mod = game_in(lib, game)
            if mod:
                return mod
    return None
