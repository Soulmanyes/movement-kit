#!/usr/bin/env python3
"""Checks movekit.steam and movekit.keyvalues on fake Steam folders; no Steam needed.

Usage: python movekit/check_steam.py   (exits 1 on the first failure)

Covers: a Windows-style libraryfolders.vdf (CRLF, escaped backslashes, a second library), a game
found by app id, a Momentum build found by name under another app id, the install folder fallback,
a folder without cfg/ skipped, libraries listed twice searched once, the environment override,
Flatpak left out on request, and nested KeyValues for localconfig.vdf.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from movekit import games, keyvalues, steam  # after the path above


def check(what, got, want):
    if got != want:
        sys.exit(f"FAIL {what}: got {got!r}, want {want!r}")
    print(f"ok   {what}")


def mod(lib, folder, name):
    """A game's mod folder with cfg/ in it."""
    path = lib / "steamapps" / "common" / folder / name
    (path / "cfg").mkdir(parents=True)
    return path


def manifest(lib, appid, name, installdir):
    (lib / "steamapps").mkdir(parents=True, exist_ok=True)
    (lib / "steamapps" / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{name}"\n\t"installdir"\t\t"{installdir}"\n}}\n')


def main():
    tmp = Path(tempfile.mkdtemp(prefix="movekit-check-"))
    root = tmp / "Steam"
    second = tmp / "D drive" / "SteamLibrary"
    (root / "steamapps").mkdir(parents=True)
    second.mkdir(parents=True)
    escaped = str(second).replace("\\", "\\\\")
    vdf = (f'"libraryfolders"\r\n{{\r\n\t"0"\r\n\t{{\r\n\t\t"path"\t\t"{root}"\r\n\t}}\r\n'
           f'\t"1"\r\n\t{{\r\n\t\t"path"\t\t"{escaped}"\r\n\t}}\r\n}}\r\n')
    (root / "steamapps" / "libraryfolders.vdf").write_bytes(vdf.encode())

    check("unescape", keyvalues.unescape(r"D:\\SteamLibrary"), r"D:\SteamLibrary")
    check("libraries: root first, then each path (root listed again)", steam.libraries(root), [root, root, second])

    # CS:S by app id in the second library, with a renamed install folder
    manifest(second, "240", "Counter-Strike: Source", "CSS custom")
    css = mod(second, "CSS custom", "cstrike")
    check("CS:S by app id in the second library", steam.game_dir(games.CSS, [root]), css)

    # Momentum: a build with another app id, found by its name
    manifest(root, "999999", "Momentum Mod Something", "Momentum Something")
    mom = mod(root, "Momentum Something", "momentum")
    os.environ.pop("MOMENTUM_DIR", None)
    check("Momentum by name under another app id", steam.game_dir(games.MOMENTUM, [root]), mom)

    # the environment variable wins, but only when the roots aren't given
    os.environ["MOMENTUM_DIR"] = str(tmp / "elsewhere")
    check("MOMENTUM_DIR overrides the search", steam.game_dir(games.MOMENTUM), tmp / "elsewhere")
    check("MOMENTUM_DIR ignored for given roots", steam.game_dir(games.MOMENTUM, [root]), mom)
    os.environ.pop("MOMENTUM_DIR")

    # install folder fallback without a manifest; a folder without cfg/ is skipped
    lone = tmp / "lone"
    (lone / "steamapps" / "common" / "Momentum Mod Playtest" / "momentum").mkdir(parents=True)
    check("folder without cfg/ skipped", steam.game_in(lone, games.MOMENTUM), None)
    fallback = mod(lone, "Momentum Mod", "momentum")
    check("usual folder name when no manifest names one", steam.game_in(lone, games.MOMENTUM), fallback)
    check("not installed", steam.game_in(lone, games.CSS), None)

    # system roots under a fake home: Flatpak only on request
    home = tmp / "home"
    flat = home / ".var/app/com.valvesoftware.Steam/.local/share/Steam"
    (home / ".local/share/Steam").mkdir(parents=True)
    flat.mkdir(parents=True)
    (home / ".steam").mkdir()
    (home / ".steam" / "steam").symlink_to(home / ".local/share/Steam")  # as Steam makes it
    os.environ["HOME"] = str(home)
    os.environ.pop("XDG_DATA_HOME", None)
    steam.FLATPAK_DATA = flat.parent  # computed from the real home at import
    check("roots: symlinked ~/.steam/steam counted once, Flatpak last",
          steam.steam_roots(), [home / ".local/share/Steam", flat])
    check("roots without Flatpak", steam.steam_roots(flatpak=False), [home / ".local/share/Steam"])
    check("flatpak_roots", steam.flatpak_roots(), [flat])

    tree = keyvalues.parse('"Store"\n{\n "Apps"\n {\n  "240"\n  {\n   "LaunchOptions" "a \\"b\\" c"\n  }\n }\n}\n')
    check("nested KeyValues", tree["store"]["apps"]["240"]["launchoptions"], 'a "b" c')
    print("all passed")


if __name__ == "__main__":
    main()
