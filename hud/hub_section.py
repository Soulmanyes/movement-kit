"""The HUD section (movekit/hub.py): in-game display settings, whichever tool draws them.

Modules whose settings live in Momentum's own HUD customizer (JHUD, First Jump HUD, ...) get a card
from their module.json's hud_card.

Legacy: Strafe Review before 1.9.0 draws the jump-1 line itself, switched by a setting in
hud/settings.py that its recorder_settings.py writes into the installed recorder (loaded by path, so
its folder never goes on sys.path). While such a Strafe Review is installed the section keeps that
toggle, so the old line can still be turned off (it would show twice next to First Jump HUD, the module
that draws it now). The module may be installed or not (movekit/modules.py), so the file is looked up
on each call.
"""
from hud import settings
from movekit import games, modules, panorama, steam
from movekit.hub import local_import


def _recorder_file():
    return modules.default_kit_root() / "strafe-review" / "recorder_settings.py"


def _recorder():
    """The recorder_settings module of a Strafe Review from before 1.9.0, or None (not installed, or
    a newer one: its recorder has no jump-1 line any more)."""
    file = _recorder_file()
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


def _legacy_line(found):
    """True when a Strafe Review from before 1.9.0, which draws the jump-1 line itself, is installed."""
    return "strafe-review" in found and _recorder_file().is_file()


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
    """The legacy recorder: "installed", "not installed" (not in the game, or no legacy Strafe Review)
    or "no game" (Momentum not found)."""
    game, rec = _game(), _recorder()
    if game is None:
        return "no game"
    return "installed" if rec and rec.recorder(game).is_file() else "not installed"


def get():
    found = _manifests()
    return {**settings.load(), "recorder": _status(), "legacyLine": _legacy_line(found), "cards": cards(found)}


def set_line(on):
    """Legacy (Strafe Review before 1.9.0): save the jump-1 line setting and write it into the
    installed recorder. applied: False when the recorder or the game isn't there."""
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
    # a module's hud_card (JHUD, First Jump HUD, ...) only points at the game's HUD customizer; the
    # patched files card is for every tool that patches a game file; an old Strafe Review keeps its
    # jump-1 line toggle. The modules don't need each other.
    "show_with": ["strafe-review", "trainer-height"],
    "show_if": lambda found: bool(cards(found)),
}
