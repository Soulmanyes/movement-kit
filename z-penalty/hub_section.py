"""The Z Penalty section (movekit/hub.py): the desktop tone for the panel (hub/).

The panel itself is set up in Momentum's HUD customizer. The tone isn't: it plays on the desktop,
from the tone runner beside the game (tone_run.py), which reads the saved settings (settings.py)
again when they change. So Apply only saves, and a running game uses the change at once.

hub.discover() loads this file on every OS before it looks at "os", so the top imports only the
standard library and movekit; the siblings load on the first call through hub.local_import.
"""
from movekit.hub import local_import

TOOL = "z-penalty"


def _settings():
    return local_import(__file__, "settings")


def _install():
    return local_import(__file__, "install")


def load():
    """What the page shows: the saved tone, the limits, the version."""
    s = _settings()
    game = _install().find_game()
    return {
        "tone": s.load(), "pitch": list(s.PITCH), "volume": list(s.VOLUME), "version": _install().VERSION,
        "problem": None if game else "Momentum Mod not found in your Steam libraries",
    }


def apply(tone):
    """Save the tone. Returns load()'s data."""
    _settings().save(tone)
    return load()


def preview(pitch, volume):
    """Play the tone for 0.4 s on the desktop."""
    from movekit import tone

    cfg = _settings().check({"pitch": pitch, "volume": volume})
    return tone.play(cfg["volume"] / 100, cfg["pitch"])


SECTION = {
    "key": TOOL,
    "title": "Z Penalty",
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {"load": load, "apply": apply, "preview": preview},
    "order": 80,
}
