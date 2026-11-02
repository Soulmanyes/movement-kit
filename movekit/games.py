"""The games the movement tools support, as data. A new game is one more Game here.

Only what is the same for every tool lives here. Tool-specific details (Source Yaw's crosshair
method, sound packs...) stay in the tool and are looked up by the game's key.
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


CSS = Game("css", "Counter-Strike: Source", ("240",), "cstrike", folders=("Counter-Strike Source",))
MOMENTUM = Game("momentum", "Momentum Mod", ("1802710",), "momentum",
                folders=("Momentum Mod Playtest", "Momentum Mod"), name_hint="momentum", env="MOMENTUM_DIR")

GAMES = {g.key: g for g in (CSS, MOMENTUM)}
