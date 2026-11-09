"""The Steam launch option every tool needs (movekit-run on Linux, the core exe on Windows): what the
game has now, and the text a settings page offers to paste, with a note saying what to do.

Each tool says which wrapper names already run it: movekit-run runs every tool, while the old
per-tool names (sourceyaw-run, strafe-review-run) run only their own tool (launch.py).
"""
import os
import re
import shlex
import sys
from pathlib import Path

from . import games, keyvalues, steam

RUNNER = "movekit-run"
BIN_DIR = Path.home() / ".local/bin"
# the core exe's names, now and before it was the hub (README: Steam launch option)
WINDOWS_EXES = ("movement-kit.exe", "strafe-review.exe")


def current(game):
    """The game's launch options in the most recently used Steam account ("" for none), or None
    when Steam's files can't be read."""
    roots = steam.steam_roots(flatpak=False) if sys.platform == "win32" else [Path.home() / ".local/share/Steam"]
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
        for appid in games.GAMES[game].appids:
            app = node.get(appid) if isinstance(node, dict) else None
            if isinstance(app, dict):
                return app.get("launchoptions", "")
        if isinstance(node, dict):
            return ""
    return None


def steam_path():
    """PATH Steam runs with: from the running Steam if there is one, otherwise this session's
    (Steam started from the desktop gets the same)."""
    for proc in Path("/proc").iterdir():
        try:
            if proc.name.isdigit() and (proc / "comm").read_text().strip() == "steam":
                for item in (proc / "environ").read_bytes().split(b"\0"):
                    if item.startswith(b"PATH="):
                        return item[5:].decode(errors="replace")
        except OSError:
            continue
    return os.environ.get("PATH", "")


def runner():
    """How the launch option should call the wrapper: the short name when Steam finds it in
    ~/.local/bin, otherwise the full path of the movekit-run next to this file."""
    if str(BIN_DIR) in steam_path().split(":"):
        return RUNNER
    return shlex.quote(str(Path(__file__).resolve().with_name(RUNNER)))


def with_runner(options=None, run=None, also=()):
    """(the launch options with the wrapper added, whether it was there already). Names in `also`
    count as the wrapper too (a tool's old names that still run it)."""
    run = run or runner()
    options = (options or "").strip()
    names = "|".join(re.escape(n) for n in (RUNNER, *also))
    wrapper = rf"(?<![^\s/])(?:\S*/)?(?:{names})(?=\s|$)"
    found = re.search(wrapper, options)
    if found:
        # already there. A short old name still works (the installers keep them as links);
        # otherwise make it the form that works here (short name or full path)
        if "/" not in found.group(0) and run == RUNNER:
            return options, True
        fixed = re.sub(wrapper, lambda _: run, options)
        return fixed, fixed == options
    if "%command%" in options:
        return options.replace("%command%", f"{run} %command%", 1), False
    # options without %command% are passed to the game as arguments
    return " ".join(filter(None, [f"{run} %command%", options])), False


def _windows(game):
    exe = sys.executable if getattr(sys, "frozen", False) else r"C:\path\to\movement-kit.exe"
    run = f'"{exe}"'
    now = current(game)
    if now and any(name in now.lower() for name in WINDOWS_EXES):
        return {"text": now, "note": "Already set up", "already": True}
    if now and "%command%" in now:
        text = now.replace("%command%", f"{run} %command%", 1)
    else:
        text = " ".join(filter(None, [f"{run} %command%", now]))
    if now is None:
        note = "Couldn't read your Steam launch options. Put this before %command%"
    elif now:
        note = "Your current launch options with movement-kit.exe added. Replace them with this"
    else:
        note = "You have no launch options yet. Paste this in"
    return {"text": text, "note": note + ". Every installed tool starts from this one launch option",
            "already": False}


def offer(game, also=()):
    """What a settings page shows: {text, note, already}. Linux: movekit-run before %command%
    (`also`: the tool's old names that still run it). Windows: the core exe."""
    if sys.platform == "win32":
        return _windows(game)
    now = current(game)
    run = runner()
    text, already = with_runner(now, run, also)
    if now is None:
        note = "Couldn't read your Steam launch options. Put movekit-run before %command%"
    elif already:
        note = "Already set up"
    elif now:
        note = "Your current launch options with movekit-run added. Replace them with this"
    else:
        note = "You have no launch options yet. Paste this in"
    if run != RUNNER:
        note += ". Steam can't find movekit-run by name here, so this uses the full path"
    return {"text": text, "note": note, "already": already}
