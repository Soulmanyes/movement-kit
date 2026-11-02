#!/usr/bin/env python3
"""Prints a tool's VERSION, for the release workflows' tag check (3.7b in PLAN.md).

Usage: python .github/scripts/version.py TOOL   (hub: hub/hub_release.py; a module: the file its
module.json names in version_from)
"""
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent.parent


def version(tool):
    if tool == "hub":
        file = KIT / "hub" / "hub_release.py"
    else:
        file = KIT / tool / json.loads((KIT / tool / "module.json").read_text(encoding="utf-8"))["version_from"]
    found = re.search(r'^VERSION = "([^"]+)"', file.read_text(encoding="utf-8"), re.MULTILINE)
    if not found:
        sys.exit(f"no VERSION line in {file}")
    return found.group(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__.split("\n\n")[1])
    print(version(sys.argv[1]))
