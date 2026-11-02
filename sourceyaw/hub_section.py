"""The Source Yaw section (movekit/hub.py): the GTK window's settings as a hub page (Phase 3.6).

The logic is settings_api.py and yawcore.py, loaded by path (hub.local_import), so sourceyaw/ never
goes on sys.path. They need Pillow and the trainer's Linux modules, so the section is Linux-only.
hub.discover() loads this file on every OS before it looks at "os", so the top of the file imports
only the standard library and movekit.hub; settings_api loads on the first call.

What the GTK window keeps in its widgets, the page keeps in its own state and sends back whole:
`apply(game, form)` takes the form, clamps the numbers to the ranges the window's spin buttons
allow, and saves through the same settings_api.collect / yawcore.apply as the window. Texts the
window builds itself (key warnings, launch-option and KROSSHAIR notes) are built here, so the page
shows the same words and check_hub_section.py can test them.
"""
import base64
import io
import math
import re
import threading

from movekit.hub import local_import

# the GTK window's spin buttons: (lowest, highest). Speeds keep 4 decimals, as the window saves them.
LIMITS = {
    "speed": (1, 2000), "x": (0, 100), "y": (0, 100), "target": (-5, 5), "size": (10, 120),
    "wrong_ticks": (1, 20), "repeat": (0, 1), "tone_volume": (5, 100), "tone_pitch": (60, 1000),
    "tickrate": (16, 128),
}
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
PREVIEW_PX = 33  # the window's preview size; nearest-neighbour keeps the crosshair's pixels sharp

# KeyboardEvent.code -> Source bind name, for keys whose name isn't the key itself (the page also
# tries KeyboardEvent.key first, so letters follow the keyboard layout as the GTK window did).
# Super never reaches the page on Hyprland; lwin and rwin stay in the pick-from-list fallback.
KEY_CODES = {
    **{f"Key{c.upper()}": c for c in "abcdefghijklmnopqrstuvwxyz"},
    **{f"Digit{d}": str(d) for d in range(10)},
    **{f"F{n}": f"f{n}" for n in range(1, 13)},
    "Enter": "enter", "Escape": "escape", "Backspace": "backspace", "Tab": "tab", "Space": "space",
    "CapsLock": "capslock", "ShiftLeft": "shift", "ShiftRight": "rshift", "ControlLeft": "ctrl",
    "ControlRight": "rctrl", "AltLeft": "alt", "AltRight": "ralt", "MetaLeft": "lwin",
    "MetaRight": "rwin", "ContextMenu": "app", "Insert": "ins", "Delete": "del", "Home": "home",
    "End": "end", "PageUp": "pgup", "PageDown": "pgdn", "ArrowUp": "uparrow",
    "ArrowDown": "downarrow", "ArrowLeft": "leftarrow", "ArrowRight": "rightarrow",
    "Pause": "pause", "ScrollLock": "scrolllock", "NumLock": "numlock",
    "Numpad0": "kp_ins", "Numpad1": "kp_end", "Numpad2": "kp_downarrow", "Numpad3": "kp_pgdn",
    "Numpad4": "kp_leftarrow", "Numpad5": "kp_5", "Numpad6": "kp_rightarrow", "Numpad7": "kp_home",
    "Numpad8": "kp_uparrow", "Numpad9": "kp_pgup", "NumpadEnter": "kp_enter",
    "NumpadDecimal": "kp_del", "NumpadDivide": "kp_slash", "NumpadMultiply": "kp_multiply",
    "NumpadSubtract": "kp_minus", "NumpadAdd": "kp_plus", "Semicolon": "semicolon",
    "Quote": "'", "Backquote": "`", "Minus": "-", "Equal": "=", "BracketLeft": "[",
    "BracketRight": "]", "Backslash": "\\", "Comma": ",", "Period": ".", "Slash": "/",
}
# MouseEvent.button -> Source name (0 left, 1 middle, 2 right, 3/4 side)
MOUSE_BUTTONS = {0: "mouse1", 1: "mouse3", 2: "mouse2", 3: "mouse4", 4: "mouse5"}

_krosshair_job = {"running": False, "error": None, "done": False}
_overlay = None


def _api():
    return local_import(__file__, "settings_api")


def _core():
    return _api().core


def _trainer():
    return _api()._trainer_module()


def _number(form, name, low=None, high=None):
    """form[name] as a float kept inside the window's range; a blank box is refused."""
    value = form.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} needs a number")
    low, high = LIMITS[name] if low is None else (low, high)
    return float(min(max(value, low), high))


def _color(value, what):
    if not isinstance(value, str) or not COLOR.match(value):
        raise ValueError(f"{what} must be a colour like #00aaff")
    return value.lower()


def _cstrike(game):
    if game not in _core().GAMES:
        raise ValueError(f"unknown game {game!r}")
    return _core().find_game(game)


def _with_kept(choices, value):
    """A saved choice this install doesn't offer stays in the list rather than being dropped."""
    if value not in [v for v, _ in choices]:
        choices = [*choices, (value, value)]
    return [list(c) for c in choices]


# ---------------------------------------------------------------- texts (as app.py builds them)

def _bound_to(cstrike, key):
    return sorted({cmd for _, cmd in _core().key_conflicts(cstrike, key)}) if cstrike else []


def key_note(game, key):
    """The note under the cycle key (Window.show_key_conflicts)."""
    cstrike = _cstrike(game)
    conflicts = _core().key_conflicts(cstrike, key) if cstrike else []
    if not conflicts:
        return {"text": "Each press switches to the next yawspeed", "warn": False}
    text = f"⚠ {key} is bound to {', '.join(sorted({c for _, c in conflicts}))} now. Apply replaces that"
    if any(name == "autoexec.cfg" for name, _ in conflicts):
        text += ", but the bind in autoexec.cfg may still win if it comes after exec yaws.cfg"
    return {"text": text, "warn": True}


def offset_key_note(game, key, offset_key):
    """The note under the trainer's offset key (Window.show_offset_key)."""
    if offset_key and offset_key.lower() == key.lower():
        return {"text": f"⚠ {offset_key} is also the cycle key, so it stays the cycle key. Pick another key",
                "warn": True}
    commands = _bound_to(_cstrike(game), offset_key) if offset_key else []
    if commands:
        return {"text": f"⚠ {offset_key} is bound to {', '.join(commands)} now. Apply replaces that",
                "warn": True}
    return {"text": "In game, each press shows or hides the offset; Show offset sets how it "
                    "starts. Takes effect from the next game start", "warn": False}


def key_notes(game, key, offset_key):
    return {"key": key_note(game, key), "offset": offset_key_note(game, key, offset_key)}


def launch_option(game):
    """The launch options to paste into Steam and the note under them (Window.show_launch_option)."""
    core = _core()
    _cstrike(game)
    current = core.current_launch_options(game)
    run = core.runner()
    text, already = core.launch_option(current, run)
    if current is None:
        note = "Couldn't read your Steam launch options. Put movekit-run before %command%"
    elif already:
        note = "Already set up"
    elif current:
        note = "Your current launch options with movekit-run added. Replace them with this"
    else:
        note = "You have no launch options yet. Paste this in"
    if run != core.RUNNER:
        note += ". Steam can't find movekit-run by name here, so this uses the full path"
    return {"text": text, "note": note, "already": already}


def krosshair():
    """KROSSHAIR's state and note (Window.show_krosshair), and the install started by install_krosshair."""
    core = _core()
    manifest = core.krosshair_installed()
    can = core.can_install_krosshair()
    if manifest:
        note = f"Installed ({manifest})"
    elif can:
        note = (f"Not installed. Install downloads KROSSHAIR {core.KROSSHAIR_VERSION} (GPL-3.0) from "
                "github.com/noahlyk/krosshair into your user folder. No password needed.")
    else:
        note = "Not installed. Get it from github.com/noahlyk/krosshair"
    job = _krosshair_job
    return {"installed": bool(manifest), "can_install": bool(can and not manifest), "note": note,
            "installing": job["running"], "error": job["error"], "finished": job["done"]}


def install_krosshair():
    """Starts the download in the background (it can take a while, and the section's calls run one
    at a time); the page polls krosshair() until installing is false."""
    job = _krosshair_job
    if job["running"]:
        return krosshair()
    job.update(running=True, error=None, done=False)

    def work():
        try:
            _core().install_krosshair()
        except Exception as e:  # noqa: BLE001 - network, checksum, disk: all shown to the user
            job["error"] = str(e)
        finally:
            job.update(running=False, done=True)

    threading.Thread(target=work, daemon=True).start()
    return krosshair()


# ---------------------------------------------------------------- loading

def _trainer_form(cfg, game):
    """The trainer settings in the window's units (percent for position and tone volume)."""
    return {
        "enabled": cfg["enabled"], "show_offset": cfg["show_offset"], "offset_key": cfg["offset_key"],
        "x": round(cfg["x"] * 100, 4), "y": round(cfg["y"] * 100, 4), "size": cfg["size"], "colors": dict(cfg["colors"]),
        "sound": cfg["sound"], "wrong_ticks": cfg["wrong_ticks"], "repeat": cfg["repeat"],
        "tone_volume": round(cfg["tone_volume"] * 100, 4), "tone_pitch": cfg["tone_pitch"],
        "cue_wrong_key": cfg["cue_wrong_key"], "cue_no_key": cfg["cue_no_key"], "target": cfg["target"],
        "tickrate": None if game == "momentum" else cfg["tickrate"].get(game, 66),
    }


def load(game=None):
    """Everything the page shows for `game` (None: the last one used, as the window opens)."""
    api, core = _api(), _core()
    installed = core.installed_games()
    if game is None:
        game = core.last_game()
        if game not in installed and installed:
            game = installed[0]
    cstrike = _cstrike(game)
    info = core.GAMES[game]
    uses_krosshair = info["colors"] == "krosshair"
    data = core.load_settings(game)
    sounds = core.available_sounds(cstrike, game) if cstrike else core.SOUNDS
    sound_choices = [("", "None")] + [(s, s) for s in sounds]
    cfg = api.trainer_config(data.get("trainer"))
    rates = ", ".join(f"{p}* {r}" for p, r in cfg["map_tickrates"].items())
    tickrate_note = (f"From the map: {rates}, others {cfg['tickrate']['momentum']}" if game == "momentum"
                     else f"From the map: {rates}; on other maps the server's tickrate")
    entries = [{"speed": float(e["speed"]), "color": e["color"], "sound": e.get("sound") or ""}
               for e in data["entries"]]
    base_values = [v for v, _ in api.base_options(data["base"])]
    trainer = _trainer_form(cfg, game)
    return {
        "game": game, "version": core.VERSION, "name": info["name"], "short": info["short"],
        "games": [{"id": g, "name": core.GAMES[g]["name"], "short": core.GAMES[g]["short"]}
                  for g in installed],
        "found": bool(cstrike), "problem": api.setup_problem(game, cstrike),
        "uses_krosshair": uses_krosshair,
        "color_note": ("Shows a KROSSHAIR crosshair in the colour of the current yawspeed" if uses_krosshair
                       else f"Sets {info['name']}'s own crosshair to the colour of the current yawspeed"),
        "steam_note": ("CS:S Properties → Launch Options. movekit-run applies these settings and runs the "
                       "colour changer and strafe trainer while the game is open." if uses_krosshair
                       else f"{info['short']} Properties → Launch Options. Only needed for the strafe "
                            "trainer: movekit-run starts it while the game is open."),
        "autoexec": bool(cstrike) and core.autoexec_runs_yaws(cstrike),
        "key": data["key"], "crosshair": data["crosshair"], "start": data["start"],
        "base": data["base"], "base_options": [list(o) for o in api.base_options(data["base"])],
        # an unavailable choice (crosshair-maker gone) shows what is used instead
        "base_shown": data["base"] if data["base"] in base_values else "builtin",
        "entries": entries,
        "sounds": [list(c) for c in sound_choices],
        "cue_sounds": _with_kept([("tone", "Constant tone"), *sound_choices], cfg["sound"]),
        "trainer": trainer, "tickrate_note": tickrate_note,
        "trainer_status": api.trainer_status(cstrike, cfg["sound"]),
        "notes": key_notes(game, data["key"], trainer["offset_key"]),
        "krosshair": krosshair() if uses_krosshair else None,
        "launch": launch_option(game),
        "previews": previews(game, data["base"], [e["color"] for e in entries]),
        "limits": {k: list(v) for k, v in LIMITS.items()},
    }


def keys():
    """For key capture: the code and mouse-button maps, and every bind name for the list fallback."""
    valid = _core().VALID_KEYS
    return {"codes": KEY_CODES, "mouse": {str(k): v for k, v in MOUSE_BUTTONS.items()},
            "valid": sorted(valid, key=lambda k: (len(k) > 1, k))}


def set_game(game):
    """Remember `game` as the last one used, as the window does when it switches; returns load(game)."""
    _cstrike(game)
    _core().set_last_game(game)
    return load(game)


def trainer_status(game, sound):
    return _api().trainer_status(_cstrike(game), sound)


def new_entry(entries):
    """The yawspeed the + button adds (Window.add_entry): 60 above the last one, blue, no sound."""
    last = float(entries[-1]["speed"]) if entries else 90
    return {"speed": last + 60, "color": "#00aaff", "sound": ""}


# ---------------------------------------------------------------- crosshair

def _base_png(game, base):
    core = _core()
    return core.resolve_base({"base": base}) if core.GAMES[game]["colors"] == "krosshair" else core.plain_cross()


def previews(game, base, colors):
    """Data URLs of the crosshair recoloured for each colour, in one call for every row."""
    core = _core()
    png = _base_png(game, base)
    out = []
    for color in colors:
        im = core.recolor(png, _color(color, "colour")).resize((PREVIEW_PX, PREVIEW_PX), resample=0)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        out.append("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
    return out


def pick_image(base):
    """Asks for a PNG (pywebview's file dialog, real paths); returns the new base_options and the
    pick, or pick None when cancelled. The dialog is modal, so holding the section's lock is fine."""
    import webview
    folder = _core().krosshair_crosshairs()
    window = webview.windows[0] if webview.windows else None
    picked = window.create_file_dialog(webview.FileDialog.OPEN, directory=str(folder or ""),
                                       file_types=("PNG images (*.png)",)) if window else None
    path = str(picked[0]) if picked else None
    chosen = path or base
    return {"pick": path, "base_options": [list(o) for o in _api().base_options(chosen)]}


def base_options(base):
    return [list(o) for o in _api().base_options(base)]


# ---------------------------------------------------------------- game side

def set_autoexec(game, on):
    """Adds or removes exec yaws.cfg in autoexec.cfg at once, as the window's switch does."""
    if not isinstance(on, bool):
        raise TypeError("on must be true or false")
    cstrike = _cstrike(game)
    if not cstrike:
        return {"ok": False, "on": False, "message": f"{_core().GAMES[game]['name']} not found"}
    try:
        _core().set_autoexec(cstrike, on)
    except OSError as e:
        return {"ok": False, "on": not on, "message": f"Couldn't change autoexec.cfg: {e.strerror}"}
    return {"ok": True, "on": on, "message": "Added to autoexec.cfg" if on else "Removed from autoexec.cfg"}


def play_sound(game, sound):
    """Plays a game sound on the desktop (returns at once); False when the game doesn't have it."""
    if not sound:
        return True
    cstrike = _cstrike(game)
    return bool(cstrike and _core().play_sound(cstrike, sound, game))


def play_cue(game, sound, tone_volume, tone_pitch):
    """The trainer's wrong-key sound: both tones (other key, then no key), or the game sound."""
    if sound != "tone":
        return play_sound(game, sound)
    volume = _number({"v": tone_volume}, "v", *LIMITS["tone_volume"]) / 100
    pitch = _number({"v": tone_pitch}, "v", *LIMITS["tone_pitch"])
    tone = _trainer().Tone(volume, pitch)
    tone.start()
    tone.mode = "wrong"
    for delay, step in ((0.35, lambda: setattr(tone, "mode", "none")),
                        (0.7, lambda: setattr(tone, "mode", None)), (0.9, tone.close)):
        threading.Timer(delay, step).start()
    return True


def show_in_game(on, game, trainer):
    """Shows (or hides) a sample offset in a game started through movekit-run (Window.preview_overlay)."""
    global _overlay
    t = _trainer()
    if _overlay is None:
        _overlay = t.Overlay()
    if not on:
        _overlay.hide()
        return False
    cfg = _trainer_value(game, trainer)
    t.write_atlas(cfg)
    target = cfg["target"]
    _overlay.show(f"{target:+d}" if target else "0", 1, cfg["x"], cfg["y"])
    return True


# ---------------------------------------------------------------- saving

def _trainer_value(game, form, saved=None):
    """settings_api.trainer_value over the saved trainer settings, with the numbers kept in range."""
    api = _api()
    if saved is None:
        saved = _core().load_settings(game).get("trainer")
    clean = dict(form)
    for name in ("x", "y", "size", "wrong_ticks", "repeat", "tone_volume", "tone_pitch", "target"):
        clean[name] = _number(form, name)
    clean["tickrate"] = None if game == "momentum" or form.get("tickrate") is None else _number(form, "tickrate")
    clean["colors"] = {k: _color(form["colors"][k], f"the {k} colour") for k in ("early", "perfect", "late")}
    for name in ("enabled", "show_offset", "cue_wrong_key", "cue_no_key"):
        clean[name] = bool(form[name])
    clean["offset_key"] = form.get("offset_key") or ""
    clean["sound"] = form.get("sound") or ""
    return api.trainer_value(api.trainer_config(saved), clean, game)


def settings(game, form):
    """The settings dict Apply would save for the page's `form` (what Window.collect returns):
    form = {key, crosshair, start, base, entries: [{speed, color, sound}], trainer: {...}}."""
    data = _core().load_settings(game)
    entries = [{"speed": round(_number(e, "speed"), 4), "color": _color(e["color"], "a yawspeed's colour"),
                "sound": e.get("sound") or None} for e in form["entries"]]
    start = form.get("start", 0)
    if not isinstance(start, int) or not 0 <= start < len(entries):
        start = 0
    return _api().collect(str(form["key"]), bool(form["crosshair"]), start, str(form["base"]),
                          data.get("original_color"), _trainer_value(game, form["trainer"], data.get("trainer")),
                          entries)


def apply(game, form):
    """Validates and writes the game's files (Window.apply). saved False: `messages` says why."""
    core = _core()
    cstrike = _cstrike(game)
    if not cstrike:
        return {"saved": False, "messages": [_api().setup_problem(game, cstrike)]}
    try:
        data = settings(game, form)
    except (KeyError, ValueError) as e:
        return {"saved": False, "messages": [str(e).strip("'")]}
    problems = core.validate(data)
    if problems:
        return {"saved": False, "messages": problems[:1]}
    try:
        notes = core.apply(data, cstrike, game=game)
    except OSError as e:
        return {"saved": False, "messages": [f"Not saved: {e.strerror}"]}
    return {"saved": True, "messages": [*notes, "Saved. Game already open? Run: exec yaws"]}


SECTION = {
    "key": "sourceyaw",
    "title": "Source Yaw",
    "os": ["linux"],
    "page": "hub/index.html",
    "api": {
        "load": load, "keys": keys, "set_game": set_game, "key_notes": key_notes,
        "trainer_status": trainer_status, "new_entry": new_entry, "previews": previews,
        "base_options": base_options, "pick_image": pick_image, "krosshair": krosshair,
        "install_krosshair": install_krosshair, "set_autoexec": set_autoexec, "play_sound": play_sound,
        "play_cue": play_cue, "show_in_game": show_in_game, "launch_option": launch_option,
        "settings": settings, "apply": apply,
    },
    "order": 30,
}
