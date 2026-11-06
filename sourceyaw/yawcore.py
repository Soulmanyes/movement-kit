"""Everything the app does that is not GUI: settings, yaws.cfg, crosshair images.

Two games are supported. Counter-Strike: Source shows the crosshair colour
through KROSSHAIR (below). Momentum Mod has its own crosshair colour cvar, so
each yawspeed's bind just runs a tiny cfg that sets it; nothing else is needed.

For CS:S the pieces fit together like this:
  - the game runs yaws.cfg (autoexec has `exec yaws.cfg`). Pressing the cycle
    key sets the next cl_yawspeed, plays its sound and echoes YAW_<speed>.
  - `con_logfile yaw.log` copies the console into cstrike/yaw.log.
  - crosshair_watch.py gets the YAW_<speed> echoes from the movekit session
    reading that log, and copies crosshairs/YAW_<speed>.png over
    ~/.config/sourceyaw/current.png. The game runs with KROSSHAIR_IMG pointing at
    that file, and the KROSSHAIR Vulkan layer reloads it inside the game's own
    frames (no compositor overlay, so no stutter).
  - launch-hook.sh, run by the Steam launch option movekit-run, runs `yawcore.py --apply`,
    sets KROSSHAIR=1 and KROSSHAIR_IMG for the game, and runs crosshair_watch.py for
    as long as the game runs. The app only edits settings.
"""

import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# movekit (code shared by the movement tools): next to this file in an installed copy (install.sh
# copies it), one folder up in the repo. Only that folder goes on the path, never ~/.local/share.
_HERE = Path(__file__).resolve().parent
if not (_HERE / "movekit").is_dir() and (_HERE.parent / "movekit").is_dir():
    sys.path.insert(1, str(_HERE.parent))
# after the path above
from movekit import binds, cfgblock, keyvalues, paths, steam, vpk
from movekit import games as kit_games

VERSION = "1.9.0"

HOME = Path.home()
# where the app is installed (or the source checkout it runs from)
HERE = Path(__file__).resolve().parent
XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
XDG_DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
# on Windows %APPDATA%\sourceyaw, the folder module.json's "config:sourceyaw" names (movekit/paths.py)
CONFIG_DIR = paths.config_dir("sourceyaw") if sys.platform == "win32" else XDG_CONFIG / "sourceyaw"
# the app was called CS:S Yaw before 1.2.0; its folders and markers are still recognised
OLD_CONFIG_DIR = XDG_CONFIG / "css-yaw"
SETTINGS = CONFIG_DIR / "settings.json"
CROSSHAIRS = CONFIG_DIR / "crosshairs"
# what the game shows: launch-hook.sh passes it to KROSSHAIR as KROSSHAIR_IMG
CURRENT = CONFIG_DIR / "current.png"
BUILTIN = CONFIG_DIR / "plain-cross.png"
WATCH_ENV = CONFIG_DIR / "watch.env"
# the launch option: movekit-run (movekit/launch.py), which install.sh links into ~/.local/bin
RUNNER = "movekit-run"
# names from before movekit-run that run Source Yaw too (install.sh keeps them as links, so old
# launch options work): sourceyaw-run, css-yaw-run (before 1.2.0), yaw-run (the full-path form)
OLD_RUNNERS = ("sourceyaw-run", "css-yaw-run", "yaw-run")
BIN_DIR = HOME / ".local/bin"

CM_DIR = XDG_CONFIG / "crosshair-maker"

# KROSSHAIR, offered as an opt-in download; pinned to the release this was tested with
KROSSHAIR_VERSION = "0.2.5"
KROSSHAIR_URL = ("https://github.com/noahlyk/krosshair/releases/download/"
                 f"v{KROSSHAIR_VERSION}/krosshair-linux-x86_64.tar.gz")
KROSSHAIR_SHA256 = "4f3c8258eb1abb6b6e4b15c55afddbba09296736473206c281e194f094617eef"
KROSSHAIR_LAYER = "VK_LAYER_KROSSHAIR_overlay"
# our own copy lives here; install.sh --uninstall removes both
KROSSHAIR_DIR = XDG_DATA / "sourceyaw/krosshair"
KROSSHAIR_JSON = XDG_DATA / "vulkan/implicit_layer.d/sourceyaw-krosshair.json"

# colors: "krosshair" = KROSSHAIR image swapped by the watcher (CS:S has no crosshair
# without a weapon); "cvar" = the game's own cl_crosshair_color, set from yaws.cfg.
# sound_vpks are relative to the game's install folder.
GAMES = {
    "css": {"name": "Counter-Strike: Source", "short": "CS:S", "colors": "krosshair",
            "process": "cstrike_linux64",
            "sound_vpks": ["cstrike/cstrike_pak_dir.vpk", "hl2/hl2_sound_misc_dir.vpk",
                           "hl2/hl2_misc_dir.vpk"]},
    "momentum": {"name": "Momentum Mod", "short": "Momentum Mod", "colors": "cvar",
                 "process": "momentum", "sound_vpks": ["mount/hl2_dir.vpk"]},
}
# no crosshair colour on Windows, for either game (Phase 12): KROSSHAIR is a Linux Vulkan layer,
# and the owner left Momentum's cvar colour out there too
WINDOWS = sys.platform == "win32"
if WINDOWS:
    for _game in GAMES.values():
        _game["colors"] = None
# first line of every yaws.cfg the app writes; anything else is the user's own file
YAWS_HEADER = "// Written by Source Yaw."
YAWS_HEADERS = (YAWS_HEADER, "// Written by CS:S Yaw.")
BACKUP = ".bak-sourceyaw"
BACKUPS = (BACKUP, ".bak-css-yaw")
# Momentum: one small cfg per yawspeed that sets the crosshair colour (an alias
# can't hold the quotes cl_crosshair_color "R G B A" needs, but a cfg can)
COLOR_DIR = "yaws_colors"
# the strafe trainer's in-game key: its alias echoes OFFSETS_TOKEN into yaw.log
OFFSETS_ALIAS = "sourceyaw_offsets"
OFFSETS_TOKEN = "SY_OFFSETS"
# bhop and surf lists (1.9.0). A profile with a "surf" list has two cycles. The mode key runs
# MODE_ALIAS, which switches to the other list at once. With auto_mode the cycle key runs
# PRESS_ALIAS: it first execs AUTO_CFG (normally empty), then cycles. When a map of the other mode
# loads, mode_watch.py writes that mode's arm alias into AUTO_CFG, so the next press starts that
# list. Every switch echoes MODE_TOKENS[mode]; the surf list echoes SURF_PREFIX tokens.
MODES = ("bhop", "surf")
MODE_TOKENS = {"bhop": "SY_MODE_BHOP", "surf": "SY_MODE_SURF"}
SURF_PREFIX = "YAWSURF_"
MODE_ALIAS = "sourceyaw_mode"
PRESS_ALIAS = "sourceyaw_press"
AUTO_CFG = "sourceyaw_auto"
DEFAULT_MAP_MODES = {"bhop_": "bhop", "surf_": "surf"}
# commands Source Yaw binds keys to; a key bound to one of them in config.cfg is ours
OWN_COMMANDS = ("yaw_cycle", PRESS_ALIAS, MODE_ALIAS, OFFSETS_ALIAS)

# short UI sounds to offer; the app only lists the ones this game install has
SOUNDS = ["buttons/blip1", "buttons/blip2", "buttons/button10", "buttons/button11",
          "buttons/button14", "buttons/button15", "buttons/button16", "buttons/button17",
          "buttons/button18", "buttons/button19"]

# key names the Source engine accepts in `bind`
VALID_KEYS = set(
    [chr(c) for c in range(ord("a"), ord("z") + 1)]
    + [str(d) for d in range(10)]
    + [f"f{n}" for n in range(1, 13)]
    + [f"mouse{n}" for n in range(1, 6)]
    + ["mwheelup", "mwheeldown", "space", "tab", "enter", "escape", "backspace",
       "capslock", "shift", "rshift", "ctrl", "rctrl", "alt", "ralt", "lwin",
       "rwin", "app", "ins", "del", "home", "end", "pgup", "pgdn", "uparrow",
       "downarrow", "leftarrow", "rightarrow", "pause", "scrolllock", "numlock",
       "kp_ins", "kp_end", "kp_downarrow", "kp_pgdn", "kp_leftarrow", "kp_5",
       "kp_rightarrow", "kp_home", "kp_uparrow", "kp_pgup", "kp_enter", "kp_del",
       "kp_slash", "kp_multiply", "kp_minus", "kp_plus", "semicolon", "'", "`",
       "-", "=", "[", "]", "\\", ",", ".", "/"]
)

DEFAULTS = {
    "key": "q",
    "crosshair": True,
    # "crosshair-maker", "builtin" or a path to a PNG
    "base": "crosshair-maker",
    # index into entries of the yawspeed the game starts on
    "start": 0,
    "entries": [
        {"speed": 90, "color": None, "sound": "buttons/blip1"},
        {"speed": 210, "color": "#ff00ff", "sound": "buttons/button17"},
    ],
}


def fmt_speed(value):
    """210.0 -> '210', 293.95350 -> '293.9535'. Used for both the cvar and the token."""
    text = f"{float(value):.4f}".rstrip("0").rstrip(".")
    return text or "0"


def token(value, surf=False):
    return f"{SURF_PREFIX if surf else 'YAW_'}{fmt_speed(value)}"


def prefix_value(name, table, default=None):
    """table[prefix] for the first prefix map `name` starts with (any case), else `default`.
    None for a name that isn't known (CS:S's "Connected to" line)."""
    if name is None:
        return None
    for prefix, value in table.items():
        if name.lower().startswith(prefix.lower()):
            return value
    return default


def surf_on(data):
    """Both lists in game: a surf list is saved and "separate" is on."""
    return bool(data.get("surf")) and bool(data.get("separate", True))


def active_mode(data):
    """With one list in game: the list it uses. The other one stays saved, unused."""
    return "surf" if data.get("active") == "surf" and data.get("surf") else "bhop"


def saved_lists(data):
    """Every saved {entries, start}: the bhop list (the profile's own entries), then the surf list."""
    return [data] + ([data["surf"]] if data.get("surf") else [])


def mode_lists(data):
    """[(mode, letter, {entries, start}, surf_tokens)] of the lists in game. Both: the bhop list,
    then the surf list; letter names their aliases and colour cfgs (yaw_b1, b1.cfg). One: the
    active list, as 1.8.0 wrote it (c1.cfg, YAW_ tokens)."""
    if surf_on(data):
        return [("bhop", "b", data, False), ("surf", "s", data["surf"], True)]
    mode = active_mode(data)
    return [(mode, "c", data if mode == "bhop" else data["surf"], False)]


def auto_on(data):
    return surf_on(data) and bool(data.get("auto_mode", True))


def mode_key_of(data):
    """The key that switches between the lists, or "" when there is none."""
    key = data.get("mode_key") or ""
    if not surf_on(data) or key.lower() == data["key"].lower():
        return ""
    return key


def map_mode(data, name):
    """"bhop" or "surf" for map `name` by its prefix, or None."""
    return prefix_value(name, data.get("map_modes") or DEFAULT_MAP_MODES)


# ---------------------------------------------------------------- locations

def find_game(game):
    """The game's mod folder (cstrike, momentum), or None. Flatpak Steam is left out:
    movekit-run can't run inside its sandbox (see flatpak_steam_only)."""
    return steam.game_dir(kit_games.GAMES[game], steam.steam_roots(flatpak=False))


def in_folder(path, root):
    """Whether `path` lies under folder `root` (case-insensitive, either slash, as on Windows)."""
    path, root = str(path).replace("/", "\\").lower(), str(root).replace("/", "\\").lower().rstrip("\\")
    return path.startswith(root + "\\")


def find_cstrike():
    return find_game("css")


def installed_games():
    return [g for g in GAMES if find_game(g)]


def game_running(game):
    """Whether the game is running (Linux; on Windows always False, as no caller needs it there)."""
    if WINDOWS:
        return False
    name = GAMES[game]["process"]
    for proc in Path("/proc").iterdir():
        try:
            if proc.name.isdigit() and (proc / "comm").read_text().strip() == name:
                return True
        except OSError:
            continue
    return False


def flatpak_steam_only(game="css"):
    """True when the game is only found in a Flatpak Steam, which isn't supported."""
    if find_game(game):
        return False
    return steam.game_dir(kit_games.GAMES[game], steam.flatpak_roots()) is not None


def crosshair_maker_png():
    """PNG of the crosshair picked in crosshair-maker, if it is installed."""
    try:
        project = json.loads((CM_DIR / "config.json").read_text())["current_crosshair"]
    except (OSError, ValueError, KeyError):
        return None
    png = Path(project).with_suffix(".png")
    return png if png.is_file() else None


def _image():
    """Pillow's Image, imported only by the crosshair colour code (Linux only), so this file
    imports on Windows, where the core exe has no Pillow."""
    try:
        from PIL import Image
    except ImportError as e:  # also what check_modules' import rule accepts in a Windows module
        raise RuntimeError("the crosshair colour needs Pillow (Linux only)") from e
    return Image


def plain_cross():
    """A simple 22x22 plus, for people without a crosshair of their own."""
    if not BUILTIN.exists():
        BUILTIN.parent.mkdir(parents=True, exist_ok=True)
        im = _image().new("RGBA", (22, 22), (0, 0, 0, 0))
        for i in range(1, 21):
            for j in (10, 11):
                im.putpixel((j, i), (255, 255, 255, 255))
                im.putpixel((i, j), (255, 255, 255, 255))
        im.save(BUILTIN)
    return BUILTIN


def resolve_base(data):
    """The crosshair image the colours are made from. Falls back to the plain cross."""
    base = data.get("base", "crosshair-maker")
    if base == "crosshair-maker":
        png = crosshair_maker_png()
    elif base == "builtin":
        png = None
    else:
        png = Path(base) if Path(base).is_file() else None
    return png or plain_cross()


def layer_dirs():
    """Where the Vulkan loader looks for implicit layers."""
    dirs = [XDG_CONFIG, Path("/etc/xdg"), Path("/etc"), XDG_DATA]
    dirs += [Path(d) for d in os.environ.get("XDG_DATA_DIRS",
                                             "/usr/local/share:/usr/share").split(":") if d]
    return [d / "vulkan/implicit_layer.d" for d in dirs]


def krosshair_installed():
    """Path of an installed KROSSHAIR layer manifest, or None."""
    for folder in layer_dirs():
        for manifest in folder.glob("*.json") if folder.is_dir() else ():
            try:
                if KROSSHAIR_LAYER in manifest.read_text(errors="replace"):
                    return manifest
            except OSError:
                continue
    return None


def krosshair_crosshairs():
    """Folder of the crosshairs that came with the user's KROSSHAIR, if any."""
    for folder in (Path("/usr/share/krosshair/crosshairs"), KROSSHAIR_DIR / "crosshairs"):
        if folder.is_dir():
            return folder
    return None


def can_install_krosshair():
    # upstream only publishes an x86_64 build
    return platform.machine() == "x86_64" and not krosshair_installed()


def install_krosshair(tarball=None):
    """Downloads the pinned KROSSHAIR release into the user's data folder (no root).
    `tarball` is for tests: a local copy of the release archive."""
    if krosshair_installed():
        raise RuntimeError("KROSSHAIR is already installed")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "krosshair.tar.gz"
        if tarball:
            shutil.copyfile(tarball, archive)
        else:
            with urllib.request.urlopen(KROSSHAIR_URL, timeout=30) as r:
                archive.write_bytes(r.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != KROSSHAIR_SHA256:
            raise RuntimeError("The download doesn't match the expected KROSSHAIR release")
        with tarfile.open(archive) as tar:
            wanted = [m for m in tar.getmembers()
                      if m.name.lstrip("./") in ("krosshair.so", "LICENSE", "krosshair.json")
                      or m.name.lstrip("./").startswith("crosshairs/")]
            try:
                tar.extractall(tmp, members=wanted, filter="data")
            except TypeError:
                # Python without extraction filters (e.g. Debian 12's 3.11.2): only plain
                # files and folders, with no absolute or ../ paths
                for m in wanted:
                    if not (m.isfile() or m.isdir()) or m.name.startswith("/") or ".." in m.name.split("/"):
                        raise RuntimeError(f"Unexpected file in the KROSSHAIR archive: {m.name}")
                tar.extractall(tmp, members=wanted)
        src = Path(tmp)
        manifest = json.loads((src / "krosshair.json").read_text())
        KROSSHAIR_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / "krosshair.so", KROSSHAIR_DIR / "krosshair.so")
        shutil.copyfile(src / "LICENSE", KROSSHAIR_DIR / "LICENSE")
        if (src / "crosshairs").is_dir():
            shutil.copytree(src / "crosshairs", KROSSHAIR_DIR / "crosshairs", dirs_exist_ok=True)
    manifest["layer"]["library_path"] = str(KROSSHAIR_DIR / "krosshair.so")
    KROSSHAIR_JSON.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(KROSSHAIR_JSON, json.dumps(manifest, indent=4) + "\n")


# ---------------------------------------------------------------- settings

def migrate_old_name():
    """Moves ~/.config/css-yaw (from before the rename) to ~/.config/sourceyaw."""
    if OLD_CONFIG_DIR.is_dir() and not CONFIG_DIR.exists():
        OLD_CONFIG_DIR.rename(CONFIG_DIR)


def _read_settings_file():
    """{"game": last used, "profiles": {game: settings}}. Before Momentum support the
    file held just the CS:S settings, which become the CS:S profile."""
    try:
        raw = json.loads(SETTINGS.read_text())
    except (OSError, ValueError):
        return {"game": "css", "profiles": {}}
    if "profiles" not in raw:
        return {"game": "css", "profiles": {"css": raw}}
    return raw


def has_profile(game):
    return game in _read_settings_file()["profiles"]


def last_game():
    return _read_settings_file().get("game", "css")


def set_last_game(game):
    whole = _read_settings_file()
    whole["game"] = game
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS.with_suffix(".tmp")
    tmp.write_text(json.dumps(whole, indent=2) + "\n")
    tmp.replace(SETTINGS)


def load_settings(game="css"):
    data = _read_settings_file()["profiles"].get(game)
    if data is None:
        data = json.loads(json.dumps(DEFAULTS))
        if GAMES[game]["colors"] == "cvar":
            # remember the user's own crosshair colour, to start from and to put back
            game_dir = find_game(game)
            data["original_color"] = game_crosshair_color(game_dir) if game_dir else None
    data.setdefault("crosshair", True)
    data.setdefault("base", "crosshair-maker")
    data["start"] = start_index(data)
    data.setdefault("mode_key", "")
    data.setdefault("auto_mode", True)
    data.setdefault("map_modes", dict(DEFAULT_MAP_MODES))
    if data.get("surf"):
        data["surf"]["start"] = start_index(data["surf"])
    for lst in saved_lists(data):
        for entry in lst["entries"]:
            if not entry.get("color"):
                original = data.get("original_color")
                entry["color"] = (rgba_to_hex(original) if original
                                  else main_color(resolve_base(data)))
    return data


def save_settings(data, game="css"):
    whole = _read_settings_file()
    whole["profiles"][game] = data
    whole["game"] = game
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS.with_suffix(".tmp")
    tmp.write_text(json.dumps(whole, indent=2) + "\n")
    tmp.replace(SETTINGS)


def start_index(data):
    start = data.get("start", 0)
    return start if isinstance(start, int) and 0 <= start < len(data["entries"]) else 0


def validate(data):
    """List of problems that block Apply; empty when fine."""
    problems = []
    if data["key"] not in VALID_KEYS:
        problems.append(f"'{data['key']}' is not a key name CS:S knows")
    for mode, _, lst, _ in mode_lists(data):
        what = " surf" if surf_on(data) and mode == "surf" else ""
        if not lst["entries"]:
            problems.append(f"Add at least one{what} yawspeed")
        tokens = [token(e["speed"]) for e in lst["entries"]]
        if len(set(tokens)) != len(tokens):
            problems.append(f"Each{what} yawspeed must be different")
    if surf_on(data):
        key = data.get("mode_key") or ""
        if key:
            if key not in VALID_KEYS:
                problems.append(f"'{key}' is not a key name the game knows")
            elif key.lower() == data["key"].lower():
                problems.append("The mode key must differ from the yaw key")
            elif key.lower() == ((data.get("trainer") or {}).get("offset_key") or "").lower() \
                    and trainer_on(data):
                problems.append("The mode key must differ from the offset key")
    return problems


# ---------------------------------------------------------------- crosshair images

def _pixels(im):
    # get_flattened_data is Pillow 12+; older Pillow (most stable distros) only has getdata
    return im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()


def main_color(png):
    """Most common visible colour of a crosshair, as #rrggbb."""
    im = _image().open(png).convert("RGBA")
    counts = {}
    for r, g, b, a in _pixels(im):
        if a:
            counts[(r, g, b)] = counts.get((r, g, b), 0) + 1
    if not counts:
        return "#ffffff"
    r, g, b = max(counts, key=counts.get)
    return f"#{r:02x}{g:02x}{b:02x}"


def recolor(png, color):
    """Every visible pixel becomes `color`, alpha kept. Outlines lose their own colour."""
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    im = _image().open(png).convert("RGBA")
    im.putdata([(*rgb, a) if a else (r, g, b, a) for r, g, b, a in _pixels(im)])
    return im


def write_crosshairs(data, reset_current):
    """One image per yawspeed. reset_current also puts the start yawspeed's image in
    current.png; done at launch (it must exist before the game's first frame), but
    not when applying mid-game, where it would show a different colour than the
    game is on."""
    base = resolve_base(data)
    CROSSHAIRS.mkdir(parents=True, exist_ok=True)
    for old in CROSSHAIRS.glob("*.png"):
        old.unlink()
    for n, (_, _, lst, surf_tokens) in enumerate(mode_lists(data)):
        for i, entry in enumerate(lst["entries"]):
            im = recolor(base, entry["color"])
            im.save(CROSSHAIRS / f"{token(entry['speed'], surf_tokens)}.png")
            # the game starts on the first list (bhop, or the one list in game)
            if n == 0 and i == start_index(lst) and (reset_current or not CURRENT.exists()):
                tmp = CURRENT.with_name(CURRENT.name + ".tmp.png")
                im.save(tmp)
                tmp.replace(CURRENT)


# ---------------------------------------------------------------- game config

def keys_bound_to_cycle(cstrike, command="yaw_cycle"):
    """Keys config.cfg binds to yaw_cycle (or `command`). It keeps binds across
    launches and the game rewrites it on exit, so a key that was changed away
    from stays bound there until yaws.cfg unbinds it."""
    return binds.keys_bound_to(binds.cfg_text(cstrike / "cfg/config.cfg"), command)


def key_conflicts(cstrike, key):
    """[(file name, command)] for binds of `key` to anything but Source Yaw's own
    commands in the configs that run before yaws.cfg would take the key over."""
    found = []
    for name in ("config.cfg", "autoexec.cfg"):
        for line in binds.cfg_text(cstrike / "cfg" / name).splitlines():
            bind = binds.parse_bind(binds.strip_comment(line))
            if not bind or bind[0].lower() != key.lower():
                continue
            command = bind[1].strip().strip('"')
            if command not in OWN_COMMANDS:
                found.append((name, command))
    return found


def trainer_on(data):
    return bool((data.get("trainer") or {}).get("enabled"))


def offsets_key_of(data):
    """The trainer's in-game offset toggle key, or "" when there is none."""
    key = (data.get("trainer") or {}).get("offset_key") or ""
    if not trainer_on(data) or key.lower() == data["key"].lower():
        return ""
    return key


def _set_alias(name, entry, nxt, surf, color_cfg):
    """`alias <name> "cl_yawspeed ..; echo ..; [exec colour cfg]; [play ..]; alias yaw_cycle <nxt>"`."""
    speed = fmt_speed(entry["speed"])
    parts = [f"cl_yawspeed {speed}", f"echo {token(speed, surf)}"]
    if color_cfg:
        parts.append(f"exec {COLOR_DIR}/{color_cfg}")
    if entry.get("sound"):
        parts.append(f"play {entry['sound']}")
    parts.append(f"alias yaw_cycle {nxt}")
    return f'alias {name} "{"; ".join(parts)}"'


def _key_lines(data, unbind, cycle_command):
    lines = [f'unbind "{key}"' for key in unbind]
    lines.append(f'bind "{data["key"]}" "{cycle_command}"')
    mode_key = mode_key_of(data)
    if mode_key:
        lines.append(f'bind "{mode_key}" "{MODE_ALIAS}"')
    offsets_key = offsets_key_of(data)
    if offsets_key:
        lines += [
            "",
            "// strafe trainer: each press shows or hides the offset (the trainer reads the echo)",
            f'alias {OFFSETS_ALIAS} "echo {OFFSETS_TOKEN}"',
            f'bind "{offsets_key}" "{OFFSETS_ALIAS}"',
        ]
    return lines


def _yaws_cfg_modes(data, unbind, game):
    """yaws.cfg with a bhop and a surf list (see MODE_ALIAS)."""
    cvar_colors = GAMES[game]["colors"] == "cvar" and data["crosshair"]
    lines = [f"{YAWS_HEADER} Change it in the app, edits here are overwritten."]
    if GAMES[game]["colors"] == "krosshair":
        lines += ["// echo goes to the console and yaw.log (read by the crosshair watcher and the",
                  "// list switcher); play is a local-only sound cue.",
                  "con_logfile yaw.log"]
    else:
        lines.append("// play is a local-only sound cue; the yaws_colors cfgs set the crosshair colour."
                     if GAMES[game]["colors"] == "cvar" else "// play is a local-only sound cue.")
        if trainer_on(data) or auto_on(data):
            lines += ["// the strafe trainer and the list switcher read map loads from yaw.log",
                      "con_logfile yaw.log"]
    starts = {}
    for mode, letter, lst, _ in mode_lists(data):
        entries = lst["entries"]
        starts[mode] = f"yaw_{letter}{start_index(lst) + 1}"
        lines += ["", f"// {mode} yawspeeds"]
        for i, entry in enumerate(entries):
            lines.append(_set_alias(f"yaw_{letter}{i + 1}", entry,
                                    f"yaw_{letter}{(i + 1) % len(entries) + 1}", mode == "surf",
                                    f"{letter}{i + 1}" if cvar_colors else None))
    lines += [
        "",
        f"// switching lists: sourceyaw_bhop/_surf switch at once ({MODE_ALIAS} runs the other one);",
        f"// an arm alias only makes the next yaw key press start its list. {PRESS_ALIAS} runs",
        f"// {AUTO_CFG}.cfg first, where the list switcher writes an arm alias when a map loads.",
        "// An arm works once: switching to a list turns its own arm off.",
        'alias sy_noop ""',
    ]
    for mode, other in (("bhop", "surf"), ("surf", "bhop")):
        lines.append(f'alias sy_{mode}_state "alias {MODE_ALIAS} sourceyaw_{other}; '
                     f'alias sourceyaw_arm_{mode} sy_noop; alias sourceyaw_arm_{other} sy_arm_{other}; '
                     f'echo {MODE_TOKENS[mode]}"')
    for mode in MODES:
        lines.append(f'alias sourceyaw_{mode} "sy_{mode}_state; {starts[mode]}"')
    for mode in MODES:
        lines.append(f'alias sy_arm_{mode} "sy_{mode}_state; alias yaw_cycle {starts[mode]}"')
    if auto_on(data):
        lines.append(f'alias {PRESS_ALIAS} "exec {AUTO_CFG}; yaw_cycle"')
    start = start_index(data)
    entries = data["entries"]
    first = fmt_speed(entries[start]["speed"])
    lines += [
        "",
        "// start on the bhop list's start yawspeed (no sound at launch); the next press goes to the one after it",
        f"cl_yawspeed {first}",
        f"echo {token(first)}",
    ]
    if cvar_colors:
        lines.append(f"exec {COLOR_DIR}/b{start + 1}")
    lines += [f"alias yaw_cycle yaw_b{(start + 1) % len(entries) + 1}", "sy_bhop_state", ""]
    lines += _key_lines(data, unbind, PRESS_ALIAS if auto_on(data) else "yaw_cycle")
    return "\n".join(lines) + "\n"


def yaws_cfg(data, unbind=(), game="css"):
    if surf_on(data):
        return _yaws_cfg_modes(data, unbind, game)
    lst = mode_lists(data)[0][2]  # the one list in game
    entries = lst["entries"]
    cvar_colors = GAMES[game]["colors"] == "cvar" and data["crosshair"]
    lines = [f"{YAWS_HEADER} Change it in the app, edits here are overwritten."]
    if GAMES[game]["colors"] == "krosshair":
        lines += [
            "// echo goes to the console and yaw.log (read by the crosshair watcher);",
            "// play is a local-only sound cue.",
            "con_logfile yaw.log",
        ]
    else:
        lines.append("// play is a local-only sound cue; the yaws_colors cfgs set the crosshair colour."
                     if GAMES[game]["colors"] == "cvar" else "// play is a local-only sound cue.")
        if trainer_on(data):
            lines += ["// the strafe trainer reads map loads from yaw.log to pick the tickrate",
                      "con_logfile yaw.log"]
    lines.append("")
    for i, entry in enumerate(entries):
        lines.append(_set_alias(f"yaw_set{i + 1}", entry, f"yaw_set{(i + 1) % len(entries) + 1}", False,
                                f"c{i + 1}" if cvar_colors else None))
    start = start_index(lst)
    first = fmt_speed(entries[start]["speed"])
    lines += [
        "",
        "// start on the chosen yawspeed (no sound at launch); the next press goes to the one after it",
        f"cl_yawspeed {first}",
        f"echo {token(first)}",
    ]
    if cvar_colors:
        lines.append(f"exec {COLOR_DIR}/c{start + 1}")
    lines += [
        f'alias yaw_cycle "yaw_set{(start + 1) % len(entries) + 1}"',
        "",
    ]
    lines += _key_lines(data, unbind, "yaw_cycle")
    return "\n".join(lines) + "\n"


# a line that runs yaws.cfg, e.g. `exec yaws`, `exec "yaws.cfg"  // comment`
_EXEC_YAWS = re.compile(r'^\s*exec\s+"?yaws(\.cfg)?"?\s*(//.*)?$', re.IGNORECASE)
# autoexec.cfg runs yaws.cfg from a `// movekit:sourceyaw begin` ... `end` block (cfgblock). Before
# 2026-11-02 it was this comment line with the exec line under it; set_autoexec replaces that in place.
_AUTOEXEC_TOOL = "sourceyaw"
_AUTOEXEC_COMMENTS = ("// added by Source Yaw", "// added by CS:S Yaw")


def autoexec_runs_yaws(cstrike):
    try:
        lines = (cstrike / "cfg/autoexec.cfg").read_text(errors="replace").splitlines()
    except OSError:
        return False
    return any(_EXEC_YAWS.match(line) for line in lines)


def _old_exec_lines(lines):
    """[(start, stop)] of each exec line under one of the old comments, with the comment."""
    return [(i - 1, i + 1) for i, line in enumerate(lines)
            if i and _EXEC_YAWS.match(line) and lines[i - 1].strip() in _AUTOEXEC_COMMENTS]


def _own_exec_lines(lines):
    """Exec lines the user wrote: not in our block and not under one of the old comments."""
    ours = {i for a, b in cfgblock.spans(lines, *cfgblock.markers(_AUTOEXEC_TOOL)) + _old_exec_lines(lines)
            for i in range(a, b)}
    return [(i, i + 1) for i, line in enumerate(lines) if i not in ours and _EXEC_YAWS.match(line)]


def set_autoexec(cstrike, on):
    """Adds or removes `exec yaws.cfg` in autoexec.cfg. Backs the file up the first time.
    Turning it on leaves an exec line the user wrote alone (and adds none); turning it off
    removes that one too."""
    path = cstrike / "cfg/autoexec.cfg"
    if on:
        lines, _ = cfgblock.read_cfg(path)
        if _own_exec_lines(lines):
            cfgblock.set_block(path, _AUTOEXEC_TOOL, [], False, BACKUPS, legacy=_old_exec_lines)
            return
        cfgblock.set_block(path, _AUTOEXEC_TOOL, ["exec yaws.cfg"], True, BACKUPS, legacy=_old_exec_lines)
    else:
        cfgblock.set_block(path, _AUTOEXEC_TOOL, [], False, BACKUPS,
                           legacy=lambda lines: _old_exec_lines(lines) + _own_exec_lines(lines))


# ---------------------------------------------------------------- Momentum crosshair colour

_CROSSHAIR_COLOR = re.compile(r'^(\s*cl_crosshair_color\s+)"([^"]*)"', re.MULTILINE)


def game_crosshair_color(game_dir):
    """The user's cl_crosshair_color ("R G B A") from config.cfg, or None."""
    try:
        m = _CROSSHAIR_COLOR.search((game_dir / "cfg/config.cfg").read_text(errors="replace"))
    except OSError:
        return None
    return m.group(2) if m else None


def rgba_to_hex(rgba):
    try:
        r, g, b = (max(0, min(255, int(float(v)))) for v in rgba.split()[:3])
    except ValueError:
        return "#00ff00"
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgba(color, alpha="255"):
    return " ".join(str(int(color[i:i + 2], 16)) for i in (1, 3, 5)) + f" {alpha}"


def write_color_cfgs(data, game_dir):
    folder = game_dir / "cfg" / COLOR_DIR
    if folder.is_dir():
        for old in folder.glob("[bcs]*.cfg"):
            old.unlink()
    if not data["crosshair"]:
        return
    folder.mkdir(exist_ok=True)
    original = data.get("original_color") or "0 255 0 255"
    alpha = original.split()[3] if len(original.split()) > 3 else "255"
    # c<i> with one list; b<i> and s<i> with a bhop and a surf list
    for _, letter, lst, _ in mode_lists(data):
        for i, entry in enumerate(lst["entries"]):
            write_text_atomic(folder / f"{letter}{i + 1}.cfg",
                              f'cl_crosshair_color "{hex_to_rgba(entry["color"], alpha)}"\n')


def restore_crosshair_color(data, game_dir, game):
    """Puts the user's own crosshair colour back in config.cfg. Returns a note when that
    can't be done now (the game rewrites config.cfg when it exits)."""
    original = data.get("original_color")
    if not original or game_crosshair_color(game_dir) in (None, original):
        return None
    if game_running(game):
        return f'Game is running: type cl_crosshair_color "{original}" in its console'
    path = game_dir / "cfg/config.cfg"
    text = path.read_text(errors="replace")
    write_text_atomic(path, _CROSSHAIR_COLOR.sub(lambda m: f'{m.group(1)}"{original}"', text, 1))
    return None


def write_text_atomic(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def apply(data, cstrike, reset_current=False, game="css"):
    """Write yaws.cfg plus the game's colour files (CS:S: crosshair images and watcher
    env; Momentum: colour cfgs). `cstrike` is the game's mod folder. Returns notes."""
    notes = []
    ours = {data["key"], offsets_key_of(data), mode_key_of(data)}
    unbind = [k for k in dict.fromkeys(key for command in OWN_COMMANDS
                                       for key in keys_bound_to_cycle(cstrike, command))
              if k not in ours]
    for key in unbind:
        notes.append(f"'{key}' gets unbound next time yaws.cfg runs")
    target = cstrike / "cfg/yaws.cfg"
    try:
        theirs = not target.read_text(errors="replace").startswith(YAWS_HEADERS)
    except FileNotFoundError:
        theirs = False
    backup = target.with_name("yaws.cfg" + BACKUP)
    if theirs and not any(target.with_name("yaws.cfg" + b).exists() for b in BACKUPS):
        # someone's own yaws.cfg: keep it rather than silently replace it
        shutil.copyfile(target, backup)
        notes.append(f"Your old yaws.cfg was saved as {backup.name}")
    write_text_atomic(target, yaws_cfg(data, unbind, game))
    # empty, so no arm left from the last game (a crash, a launch without the hook) fires
    auto = cstrike / "cfg" / f"{AUTO_CFG}.cfg"
    if auto_on(data):
        write_text_atomic(auto, "")
    else:
        auto.unlink(missing_ok=True)
    krosshair = GAMES[game]["colors"] == "krosshair"
    # read by launch-hook.sh (shell), so quote the path: it has spaces
    write_text_atomic(WATCH_ENV, f"LOG={shlex.quote(str(cstrike / 'yaw.log'))}\n"
                                 f"COLORS={1 if krosshair and data['crosshair'] else 0}\n"
                                 f"TRAINER={1 if trainer_on(data) else 0}\n"
                                 f"AUTO={1 if auto_on(data) else 0}\n")
    if krosshair:
        write_crosshairs(data, reset_current)
    elif GAMES[game]["colors"] == "cvar":
        write_color_cfgs(data, cstrike)
        if not data["crosshair"]:
            note = restore_crosshair_color(data, cstrike, game)
            if note:
                notes.append(note)
    save_settings(data, game)
    return notes


def remove_from_game(cstrike, game="css"):
    """For uninstalling: takes yaws.cfg out of autoexec.cfg and deletes it (if it is
    ours), putting back a yaws.cfg the user had before."""
    set_autoexec(cstrike, False)
    (cstrike / "cfg" / f"{AUTO_CFG}.cfg").unlink(missing_ok=True)
    if GAMES[game]["colors"] == "cvar":
        shutil.rmtree(cstrike / "cfg" / COLOR_DIR, ignore_errors=True)
        if has_profile(game):
            note = restore_crosshair_color(load_settings(game), cstrike, game)
            if note:
                print(note)
    target = cstrike / "cfg/yaws.cfg"
    try:
        if target.read_text(errors="replace").startswith(YAWS_HEADERS):
            target.unlink()
    except FileNotFoundError:
        pass
    for suffix in BACKUPS:
        backup = target.with_name("yaws.cfg" + suffix)
        if backup.exists() and not target.exists():
            backup.replace(target)


# ---------------------------------------------------------------- sound preview

SOUND_CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "sourceyaw/sounds"
def sound_file(cstrike, sound, game="css"):
    """Local file for a `play` sound name like buttons/blip1, extracting it if needed.
    `cstrike` is the game's mod folder; sound_vpks are where the game looks, in order."""
    install = cstrike.parent
    for ext in (".wav", ".mp3"):
        rel = f"sound/{sound}{ext}"
        loose = cstrike / rel
        if loose.is_file():
            return loose
        cached = SOUND_CACHE / game / f"{sound}{ext}"
        if cached.is_file():
            return cached
        for vpk_name in GAMES[game]["sound_vpks"]:
            try:
                data = vpk.read_file(install / vpk_name, rel)
            except (OSError, ValueError):
                continue
            if data:
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_bytes(data)
                return cached
    return None


def available_sounds(cstrike, game="css"):
    return [s for s in SOUNDS if sound_file(cstrike, s, game)]


def play_sound(cstrike, sound, game="css"):
    """Plays a game sound on the desktop. False if the game doesn't have it."""
    path = sound_file(cstrike, sound, game)
    if not path:
        return False
    if WINDOWS:
        import winsound  # async: a new sound cuts the last one short
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return True
    for player in (["pw-play"], ["paplay"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
        if shutil.which(player[0]):
            subprocess.Popen([*player, str(path)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
    return False


# ---------------------------------------------------------------- launch option

def current_launch_options(game="css"):
    """The game's launch options in the most recently used Steam account, or None."""
    roots = steam.steam_roots(flatpak=False) if WINDOWS else [HOME / ".local/share/Steam"]
    files = sorted((vdf for root in roots for vdf in Path(root).glob("userdata/*/config/localconfig.vdf")),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    for vdf in files:
        try:
            tree = keyvalues.parse(vdf.read_text(errors="replace"))
        except OSError:
            continue
        node = tree.get("userlocalconfigstore", {})
        for key in ("software", "valve", "steam", "apps"):
            node = node.get(key, {}) if isinstance(node, dict) else {}
        for appid in kit_games.GAMES[game].appids:
            app = node.get(appid) if isinstance(node, dict) else None
            if isinstance(app, dict):
                return app.get("launchoptions", "")
        if isinstance(node, dict):
            return ""
    return None


def steam_path():
    """PATH Steam runs with: from the running Steam if there is one, otherwise this
    session's (Steam started from the desktop gets the same)."""
    for proc in Path("/proc").iterdir():
        try:
            if proc.name.isdigit() and (proc / "comm").read_text().strip() == "steam":
                env = (proc / "environ").read_bytes().split(b"\0")
                for item in env:
                    if item.startswith(b"PATH="):
                        return item[5:].decode(errors="replace")
        except OSError:
            continue
    return os.environ.get("PATH", "")


def runner():
    """How the launch option should call the wrapper: the short name when Steam can
    find it in ~/.local/bin, otherwise the full path."""
    if str(BIN_DIR) in steam_path().split(":"):
        return RUNNER
    return shlex.quote(str(Path(kit_games.__file__).resolve().with_name(RUNNER)))


def launch_option(current=None, run=None):
    """The full launch options with the wrapper added, and whether it was there already."""
    run = run or runner()
    current = (current or "").strip()
    names = "|".join(re.escape(n) for n in (RUNNER, *OLD_RUNNERS))
    wrapper = rf"(?<![^\s/])(?:\S*/)?(?:{names})(?=\s|$)"
    found = re.search(wrapper, current)
    if found:
        # already there. A short old name still works (install.sh keeps them as links);
        # otherwise make it the form that works here (short name or full path)
        if "/" not in found.group(0) and run == RUNNER:
            return current, True
        fixed = re.sub(wrapper, lambda _: run, current)
        return fixed, fixed == current
    if "%command%" in current:
        return current.replace("%command%", f"{run} %command%", 1), False
    # options without %command% are passed to the game as arguments
    return " ".join(filter(None, [f"{run} %command%", current])), False


def set_up(game):
    """Whether a launch of `game` should apply Source Yaw: it has saved settings, or it is CS:S
    (a fresh install), so a game is never set up behind your back."""
    return has_profile(game) or game == "css"


def apply_at_launch(game):
    """Rewrites `game`'s files from its saved settings right before it starts (launch-hook.sh
    through --apply on Linux, launch_win.py on Windows), so the start yawspeed's colour is
    correct. Prints the notes, or why it couldn't; True when it applied."""
    game_dir = find_game(game)
    if not game_dir:
        print(f"{GAMES[game]['name']} not found in your Steam libraries")
        return False
    settings = load_settings(game)
    problems = validate(settings)
    if problems:
        print(f"{GAMES[game]['name']}: " + "; ".join(problems))
        return False
    for note in apply(settings, game_dir, reset_current=True, game=game):
        print(note)
    return True


if __name__ == "__main__":
    # `python3 yawcore.py --apply [game]`: rewrite a game's files from its saved settings
    #   (launch-hook.sh passes the game it is starting; without one: every game that has saved
    #   settings, or CS:S on a fresh install, so a game is never set up behind your back)
    # `python3 yawcore.py --remove-from-game`: undo the game side (install.sh --uninstall)
    import sys
    migrate_old_name()
    args = sys.argv[1:]
    if not args or args[0] not in ("--apply", "--remove-from-game") or len(args) > 2 \
            or (len(args) == 2 and args[1] not in GAMES):
        sys.exit(f"usage: yawcore.py --apply [{'|'.join(GAMES)}] | --remove-from-game")
    if args[0] == "--remove-from-game":
        for name in installed_games():
            remove_from_game(find_game(name), name)
        sys.exit(0)
    if len(args) == 2:
        games = [args[1]] if set_up(args[1]) else []
    else:
        games = [g for g in GAMES if has_profile(g)] or ["css"]
    for name in games:
        apply_at_launch(name)
