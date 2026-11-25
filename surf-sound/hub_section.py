"""The Surf Sound section (movekit/hub.py): the desktop sound while you ride a ramp or a ceiling (hub/).

The sound plays on the desktop, from the sound runner beside the game (sound_run.py), which reads the
saved settings (settings.py) again when they change. So Apply only saves, and a running game uses the
change at once.

hub.discover() loads this file on every OS before it looks at "os", so the top imports only the
standard library and movekit; the siblings load on the first call through hub.local_import.
"""
import sys
import time

from movekit import launchopt
from movekit.hub import local_import

TOOL = "surf-sound"
WINDOWS = sys.platform == "win32"


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
        "steam_note": ("Momentum Mod Properties → Launch Options. movement-kit.exe plays the sound while the "
                       "game is open." if WINDOWS
                       else "Momentum Mod Properties → Launch Options. movekit-run plays the sound while the "
                            "game is open."),
        "launch": launch_option(),
        "rec": local_import(__file__, "custom").rec_rules(), "mics": mics(),
    }


def mics():
    """The microphones Rec can record from: {"list": [[id, name]], "default": the default input's
    name or None}."""
    mic = local_import(__file__, "mic")
    try:
        return {"list": mic.inputs(), "default": mic.input_name()}
    except Exception:  # noqa: BLE001 - listing mics must never break the page (Windows' is untested)
        return {"list": [], "default": None}


def launch_option():
    """The launch options to paste into Steam and the note under them (movekit.launchopt)."""
    return launchopt.offer("momentum")


def apply(sound):
    """Save the settings, then delete the custom sound files they no longer name. Returns load()'s data."""
    cfg = _settings().save(sound)
    local_import(__file__, "custom").prune(cfg)
    return load()


def preview(sound, kind="ramp", custom=None, levels=None, split=True):
    """Play the sound (its ramp or ceiling variant) for a moment on the desktop, or a hit (kind wall1-3,
    graze, bonk or jump). custom: the page's custom sounds, saved or not ({slot: {"file", "name"}}); levels: the
    page's volume per sound ({slot: %}); split: the page's split_ceiling (off: a headsurf plays as a ramp,
    the ramp's file too)."""
    s = _settings()
    cfg = s.check({"sound": sound, "custom": custom or {}, "levels": levels or {}, "split_ceiling": bool(split)})
    files, lv = s.custom_files(cfg), s.levels(cfg)
    noise = local_import(__file__, "noise")
    if kind in noise.HITS:
        return noise.play_hit(1.0, kind, files, lv)
    if kind not in ("ramp", "ceiling"):
        raise ValueError("kind must be ramp, ceiling, wall1-3, graze, bonk or jump")
    return noise.play(1.0, cfg["sound"], kind, custom=files, levels=lv, variant=s.loop_variants(cfg)[kind])


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


_rec = {}  # the recording between record_start and record_stop: {"slot", "recorder"}


def record_start(slot, device="", recorder=None, inputs=None):
    """Start recording the slot's sound from the microphone `device` (mic.inputs()'s id, "" for the
    default input), for at most custom.REC_S[slot] seconds; it stops by itself then. Returns {"slot",
    "seconds"} at once: record_stop ends it. recorder, inputs: the recorder class and the device list
    (fakes in the checks)."""
    custom = local_import(__file__, "custom")
    mic = local_import(__file__, "mic")
    if slot not in custom.REC_S:
        raise ValueError(f"no sound {slot!r}")
    old = _rec.get("recorder")
    if old and old.recording:
        raise ValueError("already recording")
    if device and device not in [i for i, _ in (inputs if inputs is not None else mic.inputs())]:
        # pw-cat would record the default input instead, without a word
        raise ValueError("that microphone isn't connected; pick another (↻ lists them again)")
    r = (recorder or mic.recorder_class())(custom.REC_S[slot], device or None)
    r.start()
    _rec.update(slot=slot, recorder=r)
    return {"slot": slot, "seconds": custom.REC_S[slot]}


def record_stop():
    """End the recording (or take the one that stopped by itself) and make it the slot's custom sound
    (custom.record). Returns {"slot", "custom": {"file", "name"}, "seconds": its length}; nothing is
    saved: Apply saves it."""
    r, slot = _rec.pop("recorder", None), _rec.pop("slot", None)
    if r is None:
        raise ValueError("not recording")
    xs = r.stop()
    entry, seconds = local_import(__file__, "custom").record(xs, slot, time.strftime("Recording %H:%M"))
    return {"slot": slot, "custom": entry, "seconds": round(seconds, 2)}


def saved(slot):
    """The slot's saved recordings (custom.saved)."""
    return local_import(__file__, "custom").saved(slot)


def save_recording(slot, custom, name=""):
    """Keep a take ({"file", "name"}) among the saved recordings; returns the slot's list."""
    return local_import(__file__, "custom").save_recording(slot, custom, name)


def use_saved(slot, file):
    """A saved recording as the slot's custom sound: {"slot", "custom"}; Apply saves it."""
    return {"slot": slot, "custom": local_import(__file__, "custom").use_saved(slot, file)}


def rename_saved(slot, file, name):
    """Rename a saved recording; returns the slot's list."""
    return local_import(__file__, "custom").rename_saved(slot, file, name)


def delete_saved(slot, file):
    """Delete a saved recording; returns the slot's list."""
    return local_import(__file__, "custom").delete_saved(slot, file)


SECTION = {
    "key": TOOL,
    "title": "Surf Sound",
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {"load": load, "apply": apply, "preview": preview, "pick_sound": pick_sound,
            "record_start": record_start, "record_stop": record_stop, "mics": mics,
            "saved": saved, "save_recording": save_recording, "use_saved": use_saved, "delete_saved": delete_saved,
            "rename_saved": rename_saved,
            "launch_option": launch_option},
    "order": 85,
}
