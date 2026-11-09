"""The games the movement tools support, as data. A new game is one more Game here.

Only what is the same for every tool lives here. Tool-specific details (Source Yaw's crosshair
method...) stay in the tool and are looked up by the game's key.
"""
from dataclasses import dataclass


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


CSS = Game("css", "Counter-Strike: Source", ("240",), "cstrike", folders=("Counter-Strike Source",),
           process="cstrike_linux64",
           sound_vpks=("cstrike/cstrike_pak_dir.vpk", "hl2/hl2_sound_misc_dir.vpk", "hl2/hl2_misc_dir.vpk"))
MOMENTUM = Game("momentum", "Momentum Mod", ("1802710",), "momentum",
                folders=("Momentum Mod Playtest", "Momentum Mod"), name_hint="momentum", env="MOMENTUM_DIR",
                process="momentum", sound_vpks=("mount/hl2_dir.vpk",))

GAMES = {g.key: g for g in (CSS, MOMENTUM)}


def find(key):
    """The game's mod folder (cstrike, momentum) as a Path, or None. Flatpak Steam is left out:
    movekit-run can't run inside its sandbox. steam is imported here, so this file stays data only
    (launch.py's copies in older tool installs carry games.py without steam.py)."""
    from . import steam

    return steam.game_dir(GAMES[key], steam.steam_roots(flatpak=False))
