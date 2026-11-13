"""The Source Yaw section (movekit/hub.py): the GTK window's settings as a hub page (Phase 3.6).

The logic is settings_api.py and yawcore.py, loaded by path (hub.local_import), so sourceyaw/ never
goes on sys.path. hub.discover() loads this file on every OS before it looks at "os", so the top of
the file imports only the standard library and movekit; settings_api loads on the first call.

On Windows (Phase 12) the page hides what Windows doesn't have (data-linux in hub/index.html: the
crosshair colour), load() says so with "windows", and the launch option is the core exe's
(movekit/launchopt.py). Pillow is only needed for the crosshair previews, which Windows doesn't draw.
The strafe trainer has its own section since Phase 13 (strafe-trainer/hub_section.py).

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

from movekit import bindnames, launchopt
from movekit.hub import local_import

# the GTK window's spin buttons: (lowest, highest). Speeds keep 4 decimals, as the window saves them.
LIMITS = {"speed": (1, 2000)}
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
PREVIEW_PX = 33  # the window's preview size; nearest-neighbour keeps the crosshair's pixels sharp

_krosshair_job = {"running": False, "error": None, "done": False}


def _api():
    return local_import(__file__, "settings_api")


def _core():
    return _api().core


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


# ---------------------------------------------------------------- texts (in the GTK window's words, before 3.8)

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


def mode_key_note(game, key, mode_key):
    """The note under the bhop/surf mode key."""
    if not mode_key:
        return {"text": "No key: only the map's prefix picks the list", "warn": False}
    if key and mode_key.lower() == key.lower():
        return {"text": f"⚠ {mode_key} is also the cycle key. Pick another key", "warn": True}
    commands = _bound_to(_cstrike(game), mode_key)
    if commands:
        return {"text": f"⚠ {mode_key} is bound to {', '.join(commands)} now. Apply replaces that",
                "warn": True}
    return {"text": "Each press switches to the other list's start yawspeed", "warn": False}


def key_notes(game, key, mode_key=""):
    return {"key": key_note(game, key), "mode": mode_key_note(game, key, mode_key)}


def launch_option(game):
    """The launch options to paste into Steam and the note under them (movekit.launchopt; Source
    Yaw's old wrapper names still count on Linux)."""
    if not _core().WINDOWS:
        _cstrike(game)
    return launchopt.offer(game, _core().OLD_RUNNERS)


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

def _entries_form(entries):
    return [{"speed": float(e["speed"]), "color": e["color"], "sound": e.get("sound") or ""} for e in entries]


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
    entries = _entries_form(data["entries"])
    surf = ({"entries": _entries_form(data["surf"]["entries"]), "start": data["surf"]["start"]}
            if data.get("surf") else None)
    modes = ", ".join(f"{p}* {m}" for p, m in data["map_modes"].items())
    base_values = [v for v, _ in api.base_options(data["base"])]
    return {
        "game": game, "version": core.VERSION, "name": info["name"], "short": info["short"],
        "games": [{"id": g, "name": core.GAMES[g]["name"], "short": core.GAMES[g]["short"]}
                  for g in installed],
        "found": bool(cstrike), "problem": api.setup_problem(game, cstrike),
        "uses_krosshair": uses_krosshair,
        "color_note": ("Shows a KROSSHAIR crosshair in the colour of the current yawspeed" if uses_krosshair
                       else f"Sets {info['name']}'s own crosshair to the colour of the current yawspeed"),
        "windows": core.WINDOWS,
        "steam_note": (f"{info['short']} Properties → Launch Options. movement-kit.exe applies these settings "
                       "and runs the list switcher while the game is open." if core.WINDOWS
                       else "CS:S Properties → Launch Options. movekit-run applies these settings and runs the "
                            "colour changer while the game is open." if uses_krosshair
                       else f"{info['short']} Properties → Launch Options. movekit-run applies these settings "
                            "when the game starts."),
        "autoexec": bool(cstrike) and core.autoexec_runs_yaws(cstrike),
        "key": data["key"], "crosshair": data["crosshair"], "start": data["start"],
        "base": data["base"], "base_options": [list(o) for o in api.base_options(data["base"])],
        # an unavailable choice (crosshair-maker gone) shows what is used instead
        "base_shown": data["base"] if data["base"] in base_values else "builtin",
        "entries": entries,
        "surf": surf, "separate": core.surf_on(data), "active": core.active_mode(data),
        "mode_key": data["mode_key"], "auto_mode": data["auto_mode"],
        # Momentum runs a cfg per gamemode on map load, so it can switch then; CS:S on the next press
        "map_load": core.runs_mode_cfgs(game),
        "load_switch": data["load_switch"], "load_sound": data["load_sound"],
        "mode_note": f"From the map: {modes}; other maps keep the current list",
        "sounds": [list(c) for c in sound_choices],
        "notes": key_notes(game, data["key"], data["mode_key"]),
        "krosshair": krosshair() if uses_krosshair else None,
        "launch": launch_option(game),
        "previews": [] if core.WINDOWS else previews(game, data["base"], [e["color"] for e in entries]),
        "limits": {k: list(v) for k, v in LIMITS.items()},
    }


def keys():
    """For key capture (movekit/web/section.js): the code and mouse-button maps, every bind name."""
    return bindnames.capture_info()


def set_game(game):
    """Remember `game` as the last one used, as the window does when it switches; returns load(game)."""
    _cstrike(game)
    _core().set_last_game(game)
    return load(game)


def new_entry(entries):
    """The yawspeed the + button adds (Window.add_entry): 60 above the last one, blue, no sound."""
    last = float(entries[-1]["speed"]) if entries else 90
    return {"speed": last + 60, "color": "#00aaff", "sound": ""}


# ---------------------------------------------------------------- crosshair

def _base_png(game, base):
    core = _core()
    return core.resolve_base({"base": base}) if core.GAMES[game]["colors"] == "krosshair" else core.plain_cross()


def previews(game, base, colors):
    """Data URLs of the crosshair recoloured for each colour, in one call for every row (none on
    Windows, which has no crosshair colour and no Pillow)."""
    core = _core()
    if core.WINDOWS:
        return []
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


# ---------------------------------------------------------------- saving

def settings(game, form):
    """The settings dict Apply would save for the page's `form` (what Window.collect returns):
    form = {key, crosshair, start, base, entries: [{speed, color, sound}],
            surf: {entries, start} or null, separate, active, mode_key, auto_mode,
            load_switch, load_sound}.
    The saved "trainer" dict (from before Phase 13) is kept as it was, for a roll back to 1.10."""
    data = _core().load_settings(game)
    entries, start = _list_value(form["entries"], form.get("start", 0))
    surf = None
    if form.get("surf"):
        surf_entries, surf_start = _list_value(form["surf"]["entries"], form["surf"].get("start", 0))
        surf = {"entries": surf_entries, "start": surf_start}
    return _api().collect(str(form["key"]), bool(form["crosshair"]), start, str(form["base"]),
                          data.get("original_color"), data.get("trainer"),
                          entries, surf=surf, mode_key=str(form.get("mode_key") or ""),
                          auto_mode=bool(form.get("auto_mode", True)), map_modes=data.get("map_modes"),
                          separate=bool(form.get("separate")) and surf is not None,
                          active=str(form.get("active") or "bhop"),
                          load_switch=bool(form.get("load_switch", True)),
                          load_sound=bool(form.get("load_sound", True)))


def _list_value(form_entries, start):
    """One yaw list from the form: [{speed, color, sound}] and its start index (0 when out of range)."""
    entries = [{"speed": round(_number(e, "speed"), 4), "color": _color(e["color"], "a yawspeed's colour"),
                "sound": e.get("sound") or None} for e in form_entries]
    if not isinstance(start, int) or not 0 <= start < len(entries):
        start = 0
    return entries, start


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
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {
        "load": load, "keys": keys, "set_game": set_game, "key_notes": key_notes,
        "new_entry": new_entry, "previews": previews,
        "base_options": base_options, "pick_image": pick_image, "krosshair": krosshair,
        "install_krosshair": install_krosshair, "set_autoexec": set_autoexec, "play_sound": play_sound,
        "launch_option": launch_option, "settings": settings, "apply": apply,
    },
    "order": 30,
}
