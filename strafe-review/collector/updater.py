"""Update check against Strafe Review's GitHub releases. Only the standard library.

check() asks GitHub for the latest strafe-review-v* release (hub-v* in the hub exe, see
hub_release) at most every CHECK_EVERY seconds and remembers the answer in <data_dir>/updates.json
(hub-updates.json in the hub exe; the same keys as the owner's other apps: auto, checked, latest,
installed, failed). install() is for the Windows exe only: it downloads the
release zip, puts the new exe next to the running one and swaps them (a running exe can be renamed,
not overwritten); the new version runs from the next start, which the server does right away. A
copy running from the repo (Linux, or Python on Windows) only reports updates: git pull brings them.
"""
import os
import re
import time
import zipfile
from pathlib import Path

import steam

from movekit import updater as kit  # after steam, which puts movekit on the path

try:
    # only in the hub exe (hub/build.py bundles it, 3.7 in PLAN.md): there this updater follows the
    # hub's release line, since the exe is the hub
    import hub_release
except ImportError:
    hub_release = None

VERSION = "1.5.0"  # Strafe Review's; bump in the same commit as the release tag
REPO = "Soulmanyes/movement-kit"
if hub_release:
    LINE_VERSION, TAG_PREFIX = hub_release.VERSION, hub_release.TAG_PREFIX
    ASSET, EXE, STATE_NAME = hub_release.ASSET, hub_release.EXE, hub_release.STATE
else:
    LINE_VERSION, TAG_PREFIX = VERSION, "strafe-review-v"
    ASSET, EXE, STATE_NAME = "strafe-review-windows.zip", "strafe-review.exe", "updates.json"
CHECK_EVERY = 6 * 3600  # seconds between automatic checks
TIMEOUT = kit.TIMEOUT
# Tests point this at a local server; it answers like GitHub's release list
API = os.environ.get("STRAFE_REVIEW_UPDATE_API", f"https://api.github.com/repos/{REPO}/releases?per_page=100")
STATE_FILE = steam.data_dir() / STATE_NAME

parse_version = kit.parse_version
frozen_exe = kit.frozen_exe  # the Windows exe; a Linux build only in tests


def checkout_version():
    """VERSION as this file on disk has it now. A copy running from the repo keeps the VERSION it
    started with, so after a git pull (or the owner's own release commit) it would report its own
    checkout as an update. None for the exe or when the file can't be read."""
    if frozen_exe():
        return None
    try:
        m = re.search(r'^VERSION = "([^"]+)"', Path(__file__).read_text(), re.MULTILINE)
    except OSError:
        return None
    return m.group(1) if m else None


class Updater(kit.Updater):
    check_every = CHECK_EVERY
    tag_prefix = TAG_PREFIX

    def __init__(self, state_file=STATE_FILE, version=None):
        self._version = version
        super().__init__(API, "strafe-review", state_file)
        # an update that was installed but isn't what runs now didn't take: don't retry it on its own
        tag = self.state.get("installed")
        if tag and parse_version(tag) != parse_version(self.version):
            self.state.update(failed=tag)
            self.state.pop("installed", None)
            self._save()
        elif tag:
            self.state.pop("installed", None)
            self._save()

    @property
    def version(self):
        """The version given, else the checkout's on disk (repo copy), else the one this process loaded."""
        return self._version or (None if hub_release else checkout_version()) or LINE_VERSION

    @property
    def can_install(self):
        return frozen_exe() is not None

    def info(self):
        """What the page shows: this version, the latest release if newer, and whether it can install."""
        latest = self.state.get("latest")
        return {
            "version": self.version,
            "latest": latest if self.newer(latest) else None,
            "checked": self.state.get("checked"),
            "auto": self.auto,
            "canInstall": self.can_install,
            "failed": self.state.get("failed"),
            "error": self.state.get("error"),
        }

    def release_info(self, data):
        asset = next((a["browser_download_url"] for a in data.get("assets", []) if a.get("name") == ASSET), None)
        return {**super().release_info(data), "asset": asset}

    def _refresh(self):
        """Asks GitHub; the error is kept for the page too, and raised as OSError."""
        try:
            latest = self.release_info(self.fetch())
        except (OSError, ValueError, KeyError, TypeError) as e:
            self.state.update(error=f"{type(e).__name__}: {e}", checked=time.time())
            self._save()
            raise OSError(str(e)) from e
        self.state.pop("error", None)
        return self._store(latest)

    def install(self, latest):
        """Swap in the release's exe. Raises RuntimeError with a message for the page when that fails."""
        try:
            super().install(latest)
        except (OSError, RuntimeError, zipfile.BadZipFile) as e:
            raise RuntimeError(str(e)) from e

    def _install(self, latest):
        exe = frozen_exe()
        if exe is None:
            raise RuntimeError("This copy runs from the repo: update it with git pull")
        if not latest.get("asset"):
            raise RuntimeError(f"Release {latest['tag']} has no {ASSET}")
        kit.swap_exe(exe, latest["asset"], "strafe-review", ASSET, EXE)


def clean_old():
    """Delete the exe an earlier update left behind (the exe only)."""
    exe = frozen_exe()
    if exe:
        kit.clean_old(exe)
