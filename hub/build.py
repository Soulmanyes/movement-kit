#!/usr/bin/env python3
"""Builds the core exe with PyInstaller: dist/movement-kit(.exe) (3.7b in PLAN.md).

Usage: python build.py [--name strafe-review]   (needs: pip install pyinstaller pywebview)

PyInstaller builds for the system it runs on, so the Windows exe is built on Windows
(.github/workflows/hub-windows.yml; strafe-review-windows.yml builds the same exe as
strafe-review.exe for the bridge release). The exe is the core only: the hub, movekit and the HUD
section. The tools are modules it downloads (movekit/modules.py) and runs from disk, so it must carry
everything a module may import: the whole standard library (less the parts named in EXCLUDE, which
movekit/check_modules.py keeps modules away from), pywebview, movekit and hud.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
CORE_SECTIONS = ("hud",)  # the core's own sections; loaded by path, so bundled as data
# Left out: no window toolkit but WebView2, no tests or tooling, and three compression/decimal
# libraries that would each ship one more native library and licence (decimal falls back to Python)
EXCLUDE = {"tkinter", "turtle", "turtledemo", "idlelib", "test", "ensurepip", "lib2to3", "venv",
           "pydoc_data", "_decimal", "_bz2", "_lzma", "bz2", "lzma", "this", "antigravity"}


def data(src, dest):
    return ["--add-data", f"{src}{os.pathsep}{dest}"]


def clean():
    """Tool caches inside the bundled folders would be shipped too."""
    for folder in (KIT / "movekit", KIT / "hud", HERE):
        for cache in [*folder.glob("**/.ruff_cache"), *folder.glob("**/__pycache__")]:
            shutil.rmtree(cache, ignore_errors=True)


def stdlib():
    """Every public standard library module this Python has (on the build machine's OS)."""
    names = []
    for name in sorted(sys.stdlib_module_names):
        if name.startswith("_") or name in EXCLUDE:
            continue
        try:
            if importlib.util.find_spec(name) is not None:
                names.append(name)
        except (ImportError, ValueError):
            pass
    return names


def kit_modules():
    """movekit's and hud's own modules: sections and modules import them by name at run time."""
    out = []
    for pkg in ("movekit", "hud"):
        out += [f"{pkg}.{p.stem}" for p in sorted((KIT / pkg).glob("*.py"))
                if p.stem != "__init__" and not p.stem.startswith("check_")]
    return out


def main():
    name = sys.argv[sys.argv.index("--name") + 1] if "--name" in sys.argv else "movement-kit"
    clean()
    # ctypes.wintypes: a submodule, so stdlib() doesn't name it; Source Yaw's Windows trainer needs it
    hidden = [*stdlib(), "ctypes.wintypes", *kit_modules(), "webview", "hub_release"]
    cmd = [
        sys.executable, "-m", "PyInstaller", "--onefile", "--windowed", "--noconfirm", "--clean",
        "--name", name, "--paths", str(KIT), "--paths", str(HERE),
        *[a for m in sorted(EXCLUDE) for a in ("--exclude-module", m)],
        *[a for m in hidden for a in ("--hidden-import", m)],
        *data(KIT / "movekit" / "web", "movekit/web"),  # the hub's shell, cards and tokens.css
        *[a for s in CORE_SECTIONS for a in data(KIT / s / "hub_section.py", s) + data(KIT / s / "hub", f"{s}/hub")],
        str(HERE / "movement_kit.py"),
    ]
    sys.exit(subprocess.call(cmd, cwd=HERE))


if __name__ == "__main__":
    main()
