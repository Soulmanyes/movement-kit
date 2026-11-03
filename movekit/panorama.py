"""Momentum Mod's Panorama HUD files, shared by every tool that changes one (Phase 4 in PLAN.md).

The game mounts the folders in custom/ in alphabetical order (any case), and the first copy of a file
wins. A tool's own files (new names, such as the Strafe Review recorder script) stay in the tool's own
custom/ folder. A game file that tools change goes in one kit folder, custom/0-movekit, which sorts
first. It is made again on every sync from small patches on the copy that would win without it, so
two tools changing the same file (timer.xml) keep both changes, and another mod's update to that file
carries over.

A tool lists its patches in custom/<its folder>/movekit-panorama.json:

    {"tool": "strafe-review", "patches": [
        {"file": "panorama/layout/hud/timer.xml", "before": "</scripts>", "line": "<include ... />"},
        {"file": "panorama/scripts/hud/strafe-trainer.ts", "find": "resizeY: false,", "replace": "resizeY: true,"}]}

- "before"/"line": put line on its own line in front of the one line that starts with "before"
  (leading space ignored), one indent step deeper, with the file's own line endings.
- "find"/"replace": swap the text, which must occur exactly once.

A patch whose result is already in the base (its line, or its replace text with no find text left)
does nothing, so an old copy of a patched file picked as the base never gets a second include. A patch
that doesn't fit (its anchor isn't there exactly once, because the game changed the file) is skipped,
and so are that tool's other patches for the file; status() and sync() report it, and the game loads
the file as it would without us.

Stdlib only, and nothing happens on import.
"""
import contextlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from movekit import vpk

KIT_FOLDER = "0-movekit"  # sorts before every tool's folder, "0-strafe-review" included
MANIFEST = "movekit-panorama.json"
NOTE = "README.txt"
NOTE_TEXT = (f"Made by Soulmanyes's Movement Kit from the patches its tools list in custom/*/{MANIFEST}.\n"
             "It is made again on every install, so edits here are lost.\n")


class Patch:
    def __init__(self, tool, folder, raw):
        if not isinstance(raw, dict) or not isinstance(raw.get("file"), str):
            raise TypeError("a patch needs a file")
        self.tool, self.folder, self.file = tool, folder, raw["file"].replace("\\", "/").strip("/")
        if ".." in self.file.split("/") or not self.file.lower().startswith("panorama/"):
            raise ValueError(f"not a Panorama file: {raw['file']!r}")
        if isinstance(raw.get("before"), str) and isinstance(raw.get("line"), str):
            self.before, self.line = raw["before"].strip(), raw["line"].strip()
            self.find = self.replace = None
            if not self.before or not self.line or "\n" in self.line:
                raise ValueError("before and line must be one non-empty line each")
        elif isinstance(raw.get("find"), str) and isinstance(raw.get("replace"), str):
            self.find, self.replace = raw["find"], raw["replace"]
            self.before = self.line = None
            if not self.find or self.find == self.replace:
                raise ValueError("find must be non-empty and differ from replace")
        else:
            raise TypeError("a patch needs before and line, or find and replace")

    def describe(self):
        return f"add {self.line}" if self.line else f"{self.find} -> {self.replace}"

    def apply(self, text):
        """(new text, "applied" | "present"), or raises ValueError when it doesn't fit."""
        if self.line is not None:
            if self.line in text:
                return text, "present"
            hits = [m for m in re.finditer(r"^([ \t]*)(\S[^\r\n]*)", text, re.MULTILINE)
                    if m.group(2).startswith(self.before)]
            if len(hits) != 1:
                raise ValueError(f"{len(hits)} lines start with {self.before!r}, want 1")
            m = hits[0]
            indent = m.group(1) + ("\t" if "\t" in m.group(1) or not m.group(1) else "    ")
            nl = "\r\n" if "\r\n" in text else "\n"
            return text[:m.start()] + indent + self.line + nl + text[m.start():], "applied"
        count = text.count(self.find)
        if count == 0 and self.replace in text:
            return text, "present"
        if count != 1:
            raise ValueError(f"{self.find!r} found {count} times, want 1")
        return text.replace(self.find, self.replace), "applied"


def _read(path):
    """Text with its own line endings; bytes that aren't UTF-8 come back unchanged when written."""
    with open(path, encoding="utf-8", errors="surrogateescape", newline="") as f:
        return f.read()


def _entries(custom):
    """custom/'s entries in mount order."""
    try:
        return sorted(custom.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []


def manifests(game):
    """(patches, warnings) from every custom/*/movekit-panorama.json, ordered by tool key."""
    patches, warnings, tools = [], [], {}
    for entry in _entries(Path(game) / "custom"):
        path = entry / MANIFEST
        if entry.name.lower() == KIT_FOLDER or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            tool = data["tool"]
            if not isinstance(tool, str) or not tool:
                raise ValueError("no tool name")
            if tool in tools:
                raise ValueError(f"tool {tool} is listed by {tools[tool]} already")
            found = [Patch(tool, entry.name, p) for p in data.get("patches", [])]
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            warnings.append(f"{path}: {e}; its patches are left out")
            continue
        tools[tool] = entry.name
        patches += found
    patches.sort(key=lambda p: p.tool)  # stable: a tool's own patches keep their order
    return patches, warnings


def base(game, rel):
    """(path of the copy the game loads without the kit folder or None, warnings): the first custom/
    folder in mount order that has the file, else the game's own. A VPK that has it can't be read
    from, so it gets a warning and the search goes on."""
    warnings = []
    for entry in _entries(Path(game) / "custom"):
        if entry.name.lower() == KIT_FOLDER:
            continue
        if entry.is_dir() and (entry / rel).is_file():
            return entry / rel, warnings
        if entry.suffix.lower() == ".vpk" and rel.lower() in vpk.files(entry):
            warnings.append(f"{entry} has its own {rel}, which the kit's copy replaces; that mod's "
                            "version may look different")
    own = Path(game) / rel
    return (own if own.is_file() else None), warnings


def build(game):
    """What custom/0-movekit should hold, without writing anything: ({rel: text}, report). The report
    has "patches" (tool, folder, file, patch, state "applied" | "present" | "skipped", reason, base)
    and "warnings"."""
    patches, warnings = manifests(game)
    files, rows = {}, []
    by_file = {}
    for p in patches:
        by_file.setdefault(p.file.lower(), []).append(p)
    for group in by_file.values():
        rel = group[0].file
        path, found = base(game, rel)
        warnings += found
        text = None
        if path is not None:
            try:
                text = _read(path)
            except OSError as e:
                warnings.append(f"{path}: {e}")
        if text is None:
            rows += [_row(p, "skipped", "the game has no such file", None) for p in group]
            continue
        for tool in dict.fromkeys(p.tool for p in group):  # a tool's patches to a file fit all or none
            mine, trial, states = [p for p in group if p.tool == tool], text, []
            try:
                for p in mine:
                    trial, state = p.apply(trial)
                    states.append(state)
            except ValueError as e:
                rows += [_row(p, "skipped", str(e) if i == len(states) else "another patch of this tool "
                              "to the file doesn't fit", path) for i, p in enumerate(mine)]
                continue
            text = trial
            rows += [_row(p, state, "", path) for p, state in zip(mine, states)]
        if any(r["state"] == "applied" and r["file"] == rel for r in rows):
            files[rel] = text
    return files, {"patches": rows, "warnings": warnings}


def _row(p, state, reason, path):
    return {"tool": p.tool, "folder": p.folder, "file": p.file, "patch": p.describe(), "state": state,
            "reason": reason, "base": str(path) if path else None}


def status(game):
    """The report sync() would give, writing nothing."""
    return build(game)[1]


def _current(folder):
    """{rel: text} of the kit folder now, or None when it has files that didn't come from build()."""
    if not folder.is_dir():
        return {}
    out = {}
    for f in folder.rglob("*"):
        if f.is_file():
            rel = f.relative_to(folder).as_posix()
            if rel != NOTE:
                out[rel] = _read(f)
    return out


@contextlib.contextmanager
def _lock():
    try:
        import fcntl
    except ImportError:  # Windows: installs run one at a time from the core exe
        yield
        return
    from movekit import paths
    data = paths.data_dir("movekit")
    data.mkdir(parents=True, exist_ok=True)
    with open(data / "panorama.lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def sync(game):
    """Make custom/0-movekit from every tool's patches, or remove it when no patch applies. Returns the
    report (see build). The new folder is built in the game folder and swapped in, so the game never
    sees half of it. Raises OSError when custom/ can't be written."""
    custom = Path(game) / "custom"
    with _lock():
        files, report = build(game)
        dest = custom / KIT_FOLDER
        if _current(dest) == files and (dest / NOTE).is_file() == bool(files):
            return report
        if not files:
            shutil.rmtree(dest, ignore_errors=True)
            return report
        # built in the game folder, not in custom/: the game mounts every folder in custom/, and a
        # name starting with "." would sort before ours and win
        for stale in Path(game).glob(".movekit-*"):
            shutil.rmtree(stale, ignore_errors=True)
        new = Path(tempfile.mkdtemp(dir=game, prefix=".movekit-new-"))
        try:
            for rel, text in files.items():
                (new / rel).parent.mkdir(parents=True, exist_ok=True)
                with open(new / rel, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
                    f.write(text)
            (new / NOTE).write_text(NOTE_TEXT, encoding="utf-8")
            old = None
            if dest.exists():
                old = Path(game) / f".movekit-old-{os.getpid()}"
                shutil.rmtree(old, ignore_errors=True)
                dest.rename(old)
            new.rename(dest)
        except BaseException:
            shutil.rmtree(new, ignore_errors=True)
            raise
        if old is not None:
            shutil.rmtree(old, ignore_errors=True)
        return report


def install(game, folder, tool, patches):
    """Write the tool's manifest into custom/<folder> (made if missing) and sync. Raises ValueError or
    TypeError for a bad patch, before anything is written."""
    for p in patches:
        Patch(tool, folder, p)
    dest = Path(game) / "custom" / folder
    dest.mkdir(parents=True, exist_ok=True)
    from movekit.files import write_atomic
    write_atomic(dest / MANIFEST, json.dumps({"tool": tool, "patches": list(patches)}, indent=1) + "\n")
    return sync(game)


def uninstall(game, folder):
    """Remove the tool's manifest from custom/<folder> and sync. The folder itself is the tool's."""
    with contextlib.suppress(FileNotFoundError):
        (Path(game) / "custom" / folder / MANIFEST).unlink()
    return sync(game)
