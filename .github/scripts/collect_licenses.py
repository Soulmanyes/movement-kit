#!/usr/bin/env python3
"""Copy the licence files of the given packages and everything they require into a folder, and
print what was found, for the zip next to an exe (windows-release.yml, input `licenses_of`).

Usage: python collect_licenses.py OUT_FOLDER pywebview [more packages...]

Reads the installed distributions' metadata (importlib.metadata), so the list is what the build
machine had, not what someone remembers. A package with no licence file in its metadata is an error:
its terms would be missing from the zip.
"""
import re
import sys
from importlib import metadata
from pathlib import Path

# installed with PyInstaller, which needs it
from packaging.requirements import Requirement

LICENSE_NAME = re.compile(r"(^|/)(LICEN[CS]E|COPYING|NOTICE|AUTHORS)[^/]*$", re.IGNORECASE)


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def requirements(dist):
    """The names this distribution needs on this machine (environment markers evaluated)."""
    names = []
    for line in dist.requires or ():
        req = Requirement(line)
        if req.marker is None or req.marker.evaluate({"extra": ""}):
            names.append(req.name)
    return names


def main():
    out, wanted = Path(sys.argv[1]), sys.argv[2:]
    out.mkdir(parents=True, exist_ok=True)
    seen, todo, missing = set(), list(wanted), []
    while todo:
        name = norm(todo.pop())
        if name in seen:
            continue
        seen.add(name)
        dist = metadata.distribution(name)
        files = [f for f in dist.files or () if LICENSE_NAME.search(str(f))]
        licence = dist.metadata.get("License-Expression") or dist.metadata.get("License") or ""
        print(f"{dist.metadata['Name']} {dist.version}: {licence.splitlines()[0] if licence else '?'}"
              f" ({', '.join(str(f) for f in files) or 'no licence file'})")
        if not files:
            missing.append(dist.metadata["Name"])
        for i, f in enumerate(files):
            stem = f"{norm(dist.metadata['Name'])}-{Path(str(f)).name}" + (f"-{i}" if i else "")
            (out / (stem if stem.endswith(".txt") else stem + ".txt")).write_bytes(Path(f.locate()).read_bytes())
        todo += requirements(dist)
    if missing:
        sys.exit(f"no licence file in the metadata of: {', '.join(missing)}")


if __name__ == "__main__":
    main()
