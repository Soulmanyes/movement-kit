"""The Z Penalty section (movekit/hub.py): the in-game sound for the panel (hub/).

The panel itself is set up in Momentum's HUD customizer. The sound can't be: the game can't read the
kit's files, so Apply saves it (settings.py) and runs install.py's install again, which writes it into
the panel script's copy in the game. A running game picks the new copy up after panorama_reload in its console.

hub.discover() loads this file on every OS before it looks at "os", so the top imports only the
standard library and movekit; the siblings load on the first call through hub.local_import.
"""
from movekit import sounds
from movekit.hub import local_import

TOOL = "z-penalty"


def _settings():
    return local_import(__file__, "settings")


def _install():
    return local_import(__file__, "install")


def load():
    """What the page shows: the saved sound, the sounds this Momentum install has, the version."""
    s = _settings()
    cfg = s.load()
    game = _install().find_game()
    found = sounds.available(game, "momentum") if game else list(sounds.SOUNDS)
    if cfg["name"] not in found:
        found.append(cfg["name"])
    return {
        "sound": cfg, "sounds": found, "found": bool(game), "version": _install().VERSION,
        "volume": list(s.VOLUME),
        "problem": None if game else "Momentum Mod not found in your Steam libraries, so Apply only saves",
    }


def apply(sound):
    """Save the sound and write it into the game's copy of the panel. Returns load()'s data plus
    `written`: whether the game's copy was updated."""
    cfg = _settings().save(sound)
    inst = _install()
    game = inst.find_game()
    skipped = inst.install(game, quiet=True) if game else None
    out = load()
    out["sound"] = cfg
    out["written"] = bool(game) and not skipped
    return out


def preview(name):
    """Play the sound on the desktop (the game plays it at the volume set; this can't)."""
    _settings().check({"name": name})
    game = _install().find_game()
    return bool(game and sounds.play(game, name, "momentum"))


SECTION = {
    "key": TOOL,
    "title": "Z Penalty",
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {"load": load, "apply": apply, "preview": preview},
    "order": 80,
}
