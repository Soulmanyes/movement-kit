"""The HUD section (movekit/hub.py): in-game display settings, whichever tool draws them.

The store is hud/settings.py. Each setting is written into the game by the tool that draws it:
the jump-1 line by Strafe Review's recorder (recorder_settings.py in the Strafe Review module, loaded
by path so its folder never goes on sys.path). The HUD is part of the core; the module may be
installed or not (movekit/modules.py), so the file is looked up on each call.
"""
from hud import settings
from movekit import games, modules, panorama, steam
from movekit.hub import local_import


def _recorder():
    """Strafe Review's recorder_settings module, or None when Strafe Review isn't installed."""
    file = modules.default_kit_root() / "strafe-review" / "recorder_settings.py"
    return local_import(file, "recorder_settings") if file.is_file() else None


def _installed():
    """Keys of the installed modules, or None when the state file can't be read."""
    try:
        return modules.Manager().installed()
    except Exception:  # noqa: BLE001 - an unreadable state file: callers fall back on the folders
        return None


def _line_tool(keys):
    """True when Strafe Review, which draws the jump-1 line, is installed (the HUD section also shows
    for the other HUD modules alone, and then the line's card is hidden)."""
    return "strafe-review" in keys if keys is not None else _recorder() is not None


def _jhud(keys):
    """True when JHUD is installed. Its settings live in Momentum's own HUD customizer, so the section
    only says so."""
    if keys is not None:
        return "jhud" in keys
    return (modules.default_kit_root() / "jhud" / "module.json").is_file()


def _game():
    """Momentum's game folder, or None; MOMENTUM_DIR is taken as given, so check it's there."""
    game = steam.game_dir(games.MOMENTUM)
    return game if game and game.is_dir() else None


def _status():
    """"installed", "not installed" (the recorder isn't in the game) or "no game" (Momentum not found)."""
    game, rec = _game(), _recorder()
    if game is None:
        return "no game"
    return "installed" if rec and rec.recorder(game).is_file() else "not installed"


def get():
    keys = _installed()
    return {**settings.load(), "recorder": _status(), "strafeReview": _line_tool(keys), "jhud": _jhud(keys)}


def set_line(on):
    """Save the jump-1 line setting and write it into the installed recorder.
    applied: False when the recorder or the game isn't there; it applies once the recorder is installed."""
    if not isinstance(on, bool):
        raise TypeError("on must be true or false")
    settings.save("inGameLine", on)
    game, rec = _game(), _recorder()
    applied = bool(game and rec and rec.apply(game, on))
    return {**settings.load(), "applied": applied}


def panorama_status():
    """The kit's patched HUD files (movekit/panorama.py): each tool's patches as applied, present or
    skipped, plus warnings. game: False when Momentum isn't found."""
    game = _game()
    if game is None:
        return {"game": False, "patches": [], "warnings": []}
    return {"game": True, **panorama.status(game)}


SECTION = {
    "key": "hud",
    "title": "HUD",
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {"get": get, "set_line": set_line, "panorama_status": panorama_status},
    "order": 20,
    # the jump-1 line is drawn by Strafe Review's recorder, JHUD's card only points at the game's HUD
    # customizer; the patched files card is for every tool that patches a game file. The modules
    # don't need each other.
    "show_with": ["strafe-review", "trainer-height", "jhud"],
}
