"""The core exe's release line (3.7b in PLAN.md): hub-v* tags, read by hub/movement_kit.py and
hub/build.py. movekit/modules.py's CORE_VERSION must equal VERSION (movekit/check_modules.py).

The installed file keeps its name: a copy that came from Strafe Review's line is still
strafe-review.exe, because Steam's launch option points at that path; the core update takes EXE from
the zip and puts it in under the running exe's name.
"""
VERSION = "1.11.1"  # bump in the same commit as the hub-v* tag
ASSET = "hub-windows.zip"  # windows-release.yml names the zip <tool>-windows.zip
EXE = "movement-kit.exe"
