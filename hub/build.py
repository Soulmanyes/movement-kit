#!/usr/bin/env python3
"""Builds the hub exe with PyInstaller: dist/movement-kit(.exe) (3.7 in PLAN.md).

Usage: python build.py   (needs: pip install pyinstaller pywebview)

PyInstaller builds for the system it runs on, so the Windows exe is built on Windows
(.github/workflows/hub-windows.yml). The exe is Strafe Review's program (strafe_review.py) with the
hub in front of it, so the bundle has two layouts in one:
- Strafe Review's, as its own build.py has it: collector/ and viewer/ modules, viewer/static/ and
  recorder/panorama/ at the bundle root, found through sys._MEIPASS.
- The kit's, for the hub: <tool>/hub_section.py and <tool>/hub/ per section, movekit/web/. The hub
  loads these by path, so PyInstaller can't follow them: they go in as data, and what they import
  goes in as hidden imports.
Source Yaw's section is Linux-only, so it isn't bundled (and neither is Pillow).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
SR = KIT / "strafe-review"
SECTIONS = ("strafe-review", "hud", "gain-converter")  # the sections that run on Windows
# what the section files import: modules loaded by path are invisible to PyInstaller's analysis
HIDDEN = ("hub_release", "hud.settings", "movekit.hub", "movekit.games", "movekit.steam", "movekit.files",
          "movekit.paths", "webbrowser", "urllib.request", "urllib.error")


def data(src, dest):
    return ["--add-data", f"{src}{os.pathsep}{dest}"]


def clean():
    """Tool caches inside the bundled folders would be shipped too."""
    for folder in (SR, KIT / "movekit", KIT / "hud", KIT / "gain-converter"):
        for cache in [*folder.glob("**/.ruff_cache"), *folder.glob("**/__pycache__")]:
            shutil.rmtree(cache, ignore_errors=True)


def sections():
    args = []
    for tool in SECTIONS:
        args += data(KIT / tool / "hub_section.py", tool) + data(KIT / tool / "hub", f"{tool}/hub")
    return args + data(SR / "recorder_settings.py", "strafe-review")  # the HUD section loads it by path


def main():
    clean()
    cmd = [
        sys.executable, "-m", "PyInstaller", "--onefile", "--windowed", "--noconfirm", "--clean",
        "--name", "movement-kit",
        "--paths", str(SR), "--paths", str(SR / "collector"), "--paths", str(SR / "viewer"),
        "--paths", str(KIT), "--paths", str(HERE),
        # as in Strafe Review's build: unused, and each would ship one more library and licence
        "--exclude-module", "_decimal", "--exclude-module", "_bz2", "--exclude-module", "_lzma",
        *[a for m in HIDDEN for a in ("--hidden-import", m)],
        *data(SR / "viewer" / "static", "viewer/static"),
        *data(SR / "recorder" / "panorama", "recorder/panorama"),
        *data(KIT / "movekit" / "web", "movekit/web"),  # the hub's shell and the viewer's tokens.css
        *sections(),
        str(HERE / "movement_kit.py"),
    ]
    sys.exit(subprocess.call(cmd, cwd=HERE))


if __name__ == "__main__":
    main()
