"""The Surf Sound section (movekit/hub.py): the desktop sound while you ride a ramp or a ceiling (hub/).

The sound plays on the desktop, from the sound runner beside the game (sound_run.py), which reads the
saved settings (settings.py) again when they change. So Apply only saves, and a running game uses the
change at once.

hub.discover() loads this file on every OS before it looks at "os", so the top imports only the
standard library and movekit; the siblings load on the first call through hub.local_import.
"""
from movekit.hub import local_import

TOOL = "surf-sound"


def _settings():
    return local_import(__file__, "settings")


def _install():
    return local_import(__file__, "install")


def load():
    """What the page shows: the saved settings, the sounds, the limits, the version."""
    s = _settings()
    game = _install().find_game()
    sounds = local_import(__file__, "noise").SOUNDS
    return {
        "sound": s.load(), "sounds": [[k, label] for k, (label, *_) in sounds.items()],
        "volume": list(s.VOLUME), "version": _install().VERSION,
        "problem": None if game else "Momentum Mod not found in your Steam libraries",
    }


def apply(sound):
    """Save the settings, then delete the custom sound files they no longer name. Returns load()'s data."""
    cfg = _settings().save(sound)
    local_import(__file__, "custom").prune(cfg)
    return load()


def preview(sound, volume, kind="ramp", custom=None):
    """Play the sound (its ramp or ceiling variant) for a moment on the desktop, or a hit (kind wall1-3,
    graze or bonk). custom: the page's custom sounds, saved or not ({slot: {"file", "name"}})."""
    s = _settings()
    cfg = s.check({"sound": sound, "volume": volume, "custom": custom or {}})
    files = s.custom_files(cfg)
    noise = local_import(__file__, "noise")
    if kind in noise.HITS:
        return noise.play_hit(cfg["volume"] / 100, kind, files)
    if kind not in ("ramp", "ceiling"):
        raise ValueError("kind must be ramp, ceiling, wall1-3, graze or bonk")
    return noise.play(cfg["volume"] / 100, cfg["sound"], kind, custom=files)


def pick_sound(slot):
    """Ask for a sound file (pywebview's file dialog) and make it the slot's custom sound (custom.make).
    Returns {"slot", "custom": {"file", "name"}}, or custom None when cancelled. Nothing is saved: the
    page's Apply saves it. The dialog is modal, so holding the section's lock is fine."""
    import webview
    window = webview.windows[0] if webview.windows else None
    picked = window.create_file_dialog(
        webview.FileDialog.OPEN,
        file_types=("Sound files (*.wav;*.mp3;*.ogg;*.flac;*.m4a)", "All files (*.*)")) if window else None
    if not picked:
        return {"slot": slot, "custom": None}
    return {"slot": slot, "custom": local_import(__file__, "custom").make(str(picked[0]), slot)}


SECTION = {
    "key": TOOL,
    "title": "Surf Sound",
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {"load": load, "apply": apply, "preview": preview, "pick_sound": pick_sound},
    "order": 85,
}
