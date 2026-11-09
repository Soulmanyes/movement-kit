"""The dev kit's Steam side (movekit/movekit-dev, Linux): starting a game with the dev launch
wrapper, and the Steam library entries that do it.

`movekit-dev game <css|momentum> [args]` starts the game the way Steam would, but outside its own
library entry, so its Steam launch option (and the installed kit's movekit-run) stays out of it:
in the game folder, with SteamAppId set so the game still talks to Steam as itself, through the
Steam Linux Runtime (sniper) when it is there, all under the dev kit's movekit-run. launch.py then
finds the game by its folder (the entry's app id is one Steam made up).

`movekit-dev steam-entries` adds "<game> (dev kit)" to the Steam library for each installed game
(non-Steam games in userdata/<account>/config/shortcuts.vdf), running `movekit-dev game <key>`
with the prefix of the game's own launch options (game-performance, env variables), minus
movekit-run. Steam rewrites that file while it runs, so it refuses while Steam is open, and keeps
a copy of the file from before as shortcuts.vdf.bak-<date>. Run again, it updates its own entries.
"""
import binascii
import datetime
import os
import shlex
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movekit import games, launchopt, steam

CHECKOUT = Path(__file__).resolve().parent.parent
DEV = CHECKOUT / "movekit" / "movekit-dev"
WRAPPER = CHECKOUT / "movekit" / "movekit-run"
SNIPER = Path("steamapps/common/SteamLinuxRuntime_sniper/_v2-entry-point")
SUFFIX = " (dev kit)"


# -- starting a game

def game_argv(key, args=(), roots=None):
    """(game folder, env additions, argv) that start the game under the dev movekit-run."""
    game = games.GAMES[key]
    mod_dir = games.find(key)
    if not mod_dir:
        raise RuntimeError(f"{game.name} isn't installed in a Steam library")
    root = Path(mod_dir).parent
    script = root / f"{game.mod}.sh"
    if not script.is_file():
        raise RuntimeError(f"{script} is missing")
    argv = [str(WRAPPER)]
    for steam_root in roots or steam.steam_roots(flatpak=False):
        if (Path(steam_root) / SNIPER).is_file():
            argv += [str(Path(steam_root) / SNIPER), "--verb=waitforexitandrun", "--"]
            break
    argv += [str(script), "-steam", *args]
    env = {"SteamAppId": game.appids[0], "SteamGameId": game.appids[0]}
    return root, env, argv


def run_game(key, args):
    root, env, argv = game_argv(key, args)
    os.chdir(root)  # the game's start script finds its 64-bit server relative to here
    os.environ.update(env)
    os.execv(argv[0], argv)


# -- shortcuts.vdf: Valve's binary KeyValues (0 = subtree, 1 = string, 2 = int32, 7 = uint64, 8 = end)

def read_kv(data, i=0):
    out = {}
    while True:
        kind = data[i]
        i += 1
        if kind == 8:
            return out, i
        end = data.index(0, i)
        name = data[i:end].decode("utf-8", "surrogateescape")
        i = end + 1
        if kind == 0:
            value, i = read_kv(data, i)
        elif kind == 1:
            end = data.index(0, i)
            value = data[i:end].decode("utf-8", "surrogateescape")
            i = end + 1
        elif kind == 2:
            value = (2, int.from_bytes(data[i:i + 4], "little"))
            i += 4
        elif kind == 7:
            value = (7, int.from_bytes(data[i:i + 8], "little"))
            i += 8
        else:
            raise ValueError(f"unknown KeyValues type {kind} at byte {i - 1}")
        out[name] = value


def write_kv(tree):
    out = bytearray()
    for name, value in tree.items():
        key = name.encode("utf-8", "surrogateescape") + b"\0"
        if isinstance(value, dict):
            out += b"\0" + key + write_kv(value)
        elif isinstance(value, str):
            out += b"\1" + key + value.encode("utf-8", "surrogateescape") + b"\0"
        else:
            kind, number = value
            out += bytes([kind]) + key + number.to_bytes(4 if kind == 2 else 8, "little")
    return bytes(out + b"\x08")


def shortcut_id(exe, name):
    """A non-Steam game id (top bit set) that stays the same for the same entry: crc32 of exe + name."""
    return (binascii.crc32((exe + name).encode()) & 0xFFFFFFFF) | 0x80000000


def launch_prefix(options):
    """What runs before %command% in a game's launch options, with movekit-run (and its old
    names) taken out, and what comes after it. ("", "") for none."""
    options = (options or "").strip()
    before, sep, after = options.partition("%command%")
    if not sep:
        before, after = "", options
    runners = {launchopt.RUNNER, "sourceyaw-run", "css-yaw-run", "yaw-run", "strafe-review-run"}
    words = [w for w in shlex.split(before) if os.path.basename(w) not in runners]
    return shlex.join(words), after.strip()


def entry(key, options):
    game = games.GAMES[key]
    name = game.name + SUFFIX
    exe = f'"{DEV}"'
    before, after = launch_prefix(options)
    launch = " ".join(filter(None, [before, "%command%", "game", key, after]))
    return {
        "appid": (2, shortcut_id(exe, name)), "AppName": name, "Exe": exe,
        "StartDir": str(CHECKOUT), "icon": "", "ShortcutPath": "", "LaunchOptions": launch,
        "IsHidden": (2, 0), "AllowDesktopConfig": (2, 1), "AllowOverlay": (2, 1), "OpenVR": (2, 0),
        "Devkit": (2, 0), "DevkitGameID": "", "DevkitOverrideAppID": (2, 0), "LastPlayTime": (2, 0),
        "FlatpakAppID": "", "sortas": "", "tags": {},
    }


def steam_running():
    for proc in Path("/proc").iterdir():
        try:
            if proc.name.isdigit() and (proc / "comm").read_text().strip() == "steam":
                return True
        except OSError:
            continue
    return False


def add_entries(config_dirs, wanted, today=None, log=print):
    """Add or update the dev entries in each account's shortcuts.vdf. wanted: {key: options}."""
    today = today or datetime.date.today().isoformat()
    for config in config_dirs:
        vdf = Path(config) / "shortcuts.vdf"
        tree = read_kv(vdf.read_bytes())[0] if vdf.is_file() else {"shortcuts": {}}
        items = [v for v in tree.get("shortcuts", {}).values()
                 if not (isinstance(v, dict) and str(v.get("AppName", "")).endswith(SUFFIX)
                         and v.get("Exe") == f'"{DEV}"')]
        items += [entry(key, options) for key, options in wanted.items()]
        new = write_kv({"shortcuts": {str(i): item for i, item in enumerate(items)}})
        if vdf.is_file():
            if vdf.read_bytes() == new:
                log(f"{vdf}: up to date")
                continue
            backup = vdf.with_name(f"shortcuts.vdf.bak-{today}")
            if not backup.exists():
                shutil.copy2(vdf, backup)
                log(f"kept {backup}")
        vdf.write_bytes(new)
        log(f"{vdf}: " + ", ".join(games.GAMES[k].name + SUFFIX for k in wanted))


def steam_entries():
    if steam_running():
        sys.exit("devkit: close Steam first (it rewrites shortcuts.vdf while it runs), then run this again")
    root = Path.home() / ".local/share/Steam"
    configs = sorted(p.parent for p in root.glob("userdata/*/config/localconfig.vdf"))
    if not configs:
        sys.exit(f"devkit: no Steam account found under {root}/userdata")
    wanted = {key: launchopt.current(key) or "" for key in games.GAMES if games.find(key)}
    if not wanted:
        sys.exit("devkit: neither CS:S nor Momentum Mod is installed")
    add_entries(configs, wanted)
    print("Start Steam: the entries are in the library. Their launch options are the games' own,")
    print("with movekit-dev in place of movekit-run; change them in the entry's Properties.")
