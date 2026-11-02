"""The hub exe's release line (3.7 in PLAN.md). Strafe Review's updater (collector/updater.py) reads
this module when hub/build.py has bundled it, so the server inside the hub exe offers hub-v* releases.

The installed file keeps its name: a copy that came from Strafe Review's line is still
strafe-review.exe, because Steam's launch option points at that path; swap_exe takes EXE from the
zip and puts it in under the running exe's name.
"""
VERSION = "1.0.0"  # bump in the same commit as the hub-v* tag
TAG_PREFIX = "hub-v"
ASSET = "hub-windows.zip"  # windows-release.yml names the zip <tool>-windows.zip
EXE = "movement-kit.exe"
STATE = "hub-updates.json"  # in Strafe Review's data folder, apart from the strafe-review-v* line's
