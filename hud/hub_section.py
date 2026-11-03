"""The HUD section (movekit/hub.py): in-game display settings, whichever tool draws them.

The store is hud/settings.py. Each setting is written into the game by the tool that draws it:
the jump-1 line by Strafe Review's recorder (recorder_settings.py in the Strafe Review module, loaded
by path so its folder never goes on sys.path). The HUD is part of the core; the module may be
installed or not (movekit/modules.py), so the file is looked up on each call. Modules whose settings
live in Momentum's own HUD customizer get a card from their module.json's hud_card.
"""
from hud import settings
from movekit import games, modules, panorama, steam
from movekit.hub import local_import


def _recorder():
    """Strafe Review's recorder_settings module, or None when Strafe Review isn't installed."""
    file = modules.default_kit_root() / "strafe-review" / "recorder_settings.py"
    return local_import(file, "recorder_settings") if file.is_file() else None


def _installed():
    """{key: manifest} of the installed modules, or None when the state file can't be read."""
    try:
        return modules.Manager().installed()
    except Exception:  # noqa: BLE001 - an unreadable state file: callers fall back on the folders
        return None


def _manifests():
    """{key: manifest} of the installed modules; when the state file can't be read, every module
    folder in the kit root with a readable module.json."""
    found = _installed()
    if found is not None:
        return found
    root, found = modules.default_kit_root(), {}
    for folder in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else ():
        try:
            m = modules.read_manifest(folder)
        except ValueError:
            continue
        found[m["key"]] = m
    return found


def _line_tool(found):
    """True when Strafe Review, which draws the jump-1 line, is installed (the HUD section also shows
    for the other HUD modules alone, and then the line's card is hidden)."""
    return "strafe-review" in found


# Cards for modules released before module.json had hud_card (JHUD 1.0.0), so they keep theirs
LEGACY_CARDS = {
    "jhud": {"title": "JHUD",
             "text": "After every jump in bhop: the jump's number, speed, speed change, gain % and sync, in the "
                     "middle of the screen, in one colour, coloured by gain, or by speed pace. Its position, size, "
                     "font, colours, fields and thresholds are set in Momentum Mod's own HUD customizer, where it "
                     "is listed as JHUD, and saved with your HUD preset. Turn it off there too."},
}


def cards(found):
    """[{key, title, text}] for the installed modules set up in the game's HUD customizer, by title.
    found: {key: manifest}."""
    out = []
    for key, m in found.items():
        card = m.get("hud_card") or LEGACY_CARDS.get(key)
        if card:
            out.append({"key": key, "title": card["title"], "text": card["text"]})
    return sorted(out, key=lambda c: (c["title"].lower(), c["key"]))


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
    found = _manifests()
    return {**settings.load(), "recorder": _status(), "strafeReview": _line_tool(found), "cards": cards(found)}


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
    "order": 90,  # after the tools (owner, 2026-11-03: HUD below the other things)
    # the jump-1 line is drawn by Strafe Review's recorder; a module's hud_card (JHUD, ...) only points
    # at the game's HUD customizer; the patched files card is for every tool that patches a game file.
    # The modules don't need each other.
    "show_with": ["strafe-review", "trainer-height"],
    "show_if": lambda found: bool(cards(found)),
}
