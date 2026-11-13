"""The games the movement tools support, as data. A new game is one more Game here.

Only what is the same for every tool lives here. Tool-specific details (Source Yaw's crosshair
method...) stay in the tool and are looked up by the game's key.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Game:
    key: str  # short id the tools use in settings and on the command line
    name: str  # full name for people
    appids: tuple  # Steam app ids, as strings
    mod: str  # the mod folder inside the install folder, the one holding cfg/
    folders: tuple = ()  # usual install folder names, tried when no app manifest names one
    name_hint: str = ""  # an app manifest whose "name" contains this (any case) is this game, whatever its app id
    env: str = ""  # environment variable that overrides the game folder (the mod folder)
    process: str = ""  # the game's process name on Linux (/proc/<pid>/comm), to tell when it has focus
    sound_vpks: tuple = ()  # VPKs that hold its sounds, relative to the install folder, in search order
    # gamemodes whose cfg/<gamemode>.cfg the game runs by itself each time a map of that gamemode
    # loads (Momentum Mod: the names engine.so holds; surf and bhop probed in game 2026-11-13). The game
    # ships none of these files, so a tool may write them.
    mode_cfgs: tuple = ()


CSS = Game("css", "Counter-Strike: Source", ("240",), "cstrike", folders=("Counter-Strike Source",),
           process="cstrike_linux64",
           sound_vpks=("cstrike/cstrike_pak_dir.vpk", "hl2/hl2_sound_misc_dir.vpk", "hl2/hl2_misc_dir.vpk"))
MOMENTUM = Game("momentum", "Momentum Mod", ("1802710",), "momentum",
                folders=("Momentum Mod Playtest", "Momentum Mod"), name_hint="momentum", env="MOMENTUM_DIR",
                process="momentum", sound_vpks=("mount/hl2_dir.vpk",),
                mode_cfgs=("surf", "bhop", "bhophl", "ahop", "kz", "rj", "sj", "conc",
                           "df_vq3", "df_cpm", "df_vtg"))

GAMES = {g.key: g for g in (CSS, MOMENTUM)}


def find(key):
    """The game's mod folder (cstrike, momentum) as a Path, or None. Flatpak Steam is left out:
    movekit-run can't run inside its sandbox. steam is imported here, so this file stays data only
    (launch.py's copies in older tool installs carry games.py without steam.py)."""
    from . import steam

    return steam.game_dir(GAMES[key], steam.steam_roots(flatpak=False))


# the mod folder name Steam's command gives with -game, per game
_GAME_ARGS = {g.mod: g.key for g in GAMES.values()}


def from_command(argv, finder=None):
    """The game Steam is starting with the command argv: the one whose install folder holds the exe
    (argv[0]), else the one named by -game, else None (another game). `finder` is find() by default."""
    from .files import in_folder

    finder = finder or find
    exe = argv[0] if argv else ""
    for key in GAMES:
        game_dir = finder(key)
        if game_dir and in_folder(exe, Path(game_dir).parent):
            return key
    args = [a.lower() for a in argv]
    if "-game" in args[:-1]:
        folder = args[args.index("-game") + 1].replace("\\", "/").rstrip("/")
        return _GAME_ARGS.get(folder.rsplit("/", 1)[-1])
    return None
