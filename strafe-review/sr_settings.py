"""Strafe Review's own settings: paths.config_dir("strafe-review")/settings.json, set on the hub page.

open_on_launch: open the review page in the browser when the game starts (the launch option,
strafe_review.prepare_launch, and on Linux collector/launch-hook.sh). The server starts either way.
Opening it by hand (double-click, the hub's Open review) is not affected.

The file is read on every call, so a change on the hub page counts at the next game start. A missing
or broken file means the defaults.

Loaded three ways: by strafe_review.py as a bare module, by the hub section through local_import, and
run by the launch hook (`python3 sr_settings.py open_on_launch`: exit 0 when on, OFF (10) when off,
so a crash (1) isn't read as off; the hook puts the kit's folder on PYTHONPATH so movekit imports).
"""
import json
import sys

from movekit import files, paths

DEFAULTS = {"open_on_launch": True}
OFF = 10  # exit code for a setting that is off (see the module docstring)


def path():
    """Read on each call, so a check can point it at a temp folder through XDG_CONFIG_HOME/APPDATA."""
    return paths.config_dir("strafe-review") / "settings.json"


def load():
    try:
        saved = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    if not isinstance(saved, dict):
        saved = {}
    return {k: saved[k] if isinstance(saved.get(k), type(v)) else v for k, v in DEFAULTS.items()}


def save(changes):
    """Merge the known keys of changes into the file and return all settings. Unknown keys raise."""
    unknown = set(changes) - set(DEFAULTS)
    if unknown:
        raise ValueError("unknown setting: " + ", ".join(sorted(unknown)))
    now = load()
    for k, v in changes.items():
        if not isinstance(v, type(DEFAULTS[k])):
            raise TypeError(f"{k} must be {type(DEFAULTS[k]).__name__}")
        now[k] = v
    path().parent.mkdir(parents=True, exist_ok=True)
    files.write_atomic(path(), json.dumps(now, indent=2) + "\n")
    return now


if __name__ == "__main__":
    sys.exit(0 if load().get(sys.argv[1] if len(sys.argv) > 1 else "") else OFF)
