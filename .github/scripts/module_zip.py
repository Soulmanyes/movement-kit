#!/usr/bin/env python3
"""Builds a tool's module release files (3.7b in PLAN.md): <key>-module.zip, the tool's folder as the
kit's core installs it (top folder <key>/), and <key>-module.json, a copy of its manifest that the
core reads before downloading.

Usage: python .github/scripts/module_zip.py TOOL OUT_DIR   (from the repo root, or with paths)

Left out of the zip: build output, caches, checks and smoke tests, screenshots (docs/), dev notes
(PLAN.md), and the exe-only files (WINDOWS.txt, THIRD-PARTY-NOTICES.txt, licenses/), which describe
what an exe bundles, not a folder of source.
"""
import json
import sys
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent.parent
SKIP_DIRS = {"build", "dist", "__pycache__", ".ruff_cache", "docs", "licenses", "probe"}
SKIP_FILES = {"PLAN.md", "WINDOWS.txt", "THIRD-PARTY-NOTICES.txt", "build.py", "smoke_test.py"}


def shipped(folder):
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder)
        if not p.is_file() or SKIP_DIRS & set(rel.parts[:-1]) or rel.name in SKIP_FILES \
                or rel.name.startswith("check_") or rel.suffix in (".spec", ".pyc"):
            continue
        yield p, rel


def build(tool, out):
    folder = KIT / tool
    manifest = json.loads((folder / "module.json").read_text(encoding="utf-8"))
    key = manifest["key"]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    zpath = out / f"{key}-module.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p, rel in shipped(folder):
            z.write(p, f"{key}/{rel.as_posix()}")
    (out / f"{key}-module.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return zpath


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__.split("\n\n")[1])
    print(build(sys.argv[1], sys.argv[2]))
