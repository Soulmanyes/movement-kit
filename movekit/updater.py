"""Updates from a tool's GitHub releases. Standard library only.

Updater keeps what the tools share: the state file (auto, checked, latest, installed, failed),
asking GitHub at most every check_every seconds, and the "failed" mark that stops auto mode
from retrying a broken release on every start. Each tool subclasses it, sets what it shows
for a release (release_info) and how it installs one (_install), usually with one of the two
install modes below:

  install_source  download the release's source archive and run its install script (Linux)
  swap_exe        download the release zip and swap in its exe next to the running one (Windows)
"""
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

TIMEOUT = 10  # seconds for the release check


def parse_version(text):
    """"v1.4.0" or "1.4" -> (1, 4, 0); None if it isn't a plain version number."""
    parts = (text or "").strip().lstrip("vV").split(".")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    return tuple(nums + [0] * (3 - len(nums)))


def in_git_checkout(folder):
    """The folder is a git clone, or a tool folder one level below the monorepo clone's root.
    No further up, where a dotfiles repo in the home folder would count too."""
    folder = Path(folder)
    return any((d / ".git").exists() for d in (folder, folder.parent))


def frozen_exe():
    """The running program when it is a PyInstaller build, else None."""
    return Path(sys.executable) if getattr(sys, "frozen", False) else None


class Updater:
    check_every = 24 * 3600  # seconds between automatic checks; a tool sets its own

    def __init__(self, api_url, agent, state_file):
        self.api_url = api_url              # GitHub's releases/latest for the tool
        self.agent = agent                  # User-Agent for GitHub
        self.state_file = Path(state_file)
        self.state = self._load()

    def _load(self):
        try:
            state = json.loads(self.state_file.read_text())
            return state if isinstance(state, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2) + "\n")
        tmp.replace(self.state_file)

    @property
    def auto(self):
        return bool(self.state.get("auto"))

    @auto.setter
    def auto(self, value):
        self.state["auto"] = bool(value)
        self._save()

    def newer(self, latest):
        mine, theirs = parse_version(self.version), parse_version(latest and latest.get("tag"))
        return bool(mine and theirs and theirs > mine)

    def failed(self, latest):
        """Its install failed before. Auto mode doesn't retry it on every start."""
        return self.state.get("failed") == latest["tag"]

    def release_info(self, data):
        """What the tool keeps of GitHub's answer for a release. Subclasses add their keys."""
        return {"tag": data["tag_name"], "url": data.get("html_url", "")}

    def fetch(self):
        """GitHub's answer for the latest release, parsed. Raises OSError/ValueError."""
        req = urllib.request.Request(self.api_url, headers={
            "Accept": "application/vnd.github+json", "User-Agent": self.agent})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)

    def _refresh(self):
        return self._store(self.release_info(self.fetch()))

    def _store(self, latest):
        self.state.update(latest=latest, checked=time.time())
        self._save()
        return latest

    def check(self, force=False):
        """The latest release (release_info) if it is newer than this version, else None. Asks
        GitHub only when forced or check_every after the last check."""
        latest = self.state.get("latest")
        if force or not latest or time.time() - self.state.get("checked", 0) > self.check_every:
            latest = self._refresh()
        return latest if self.newer(latest) else None

    def install(self, latest):
        """Installs the release with _install, marking it installed or failed. Raises what
        _install raised; its RuntimeErrors carry a message for the user."""
        try:
            self._install(latest)
        except (OSError, RuntimeError, zipfile.BadZipFile):
            self.state["failed"] = latest["tag"]
            self._save()
            raise
        self.state["installed"] = latest["tag"]
        self.state.pop("failed", None)
        self._save()

    def _install(self, latest):
        raise NotImplementedError


def install_source(url, agent, script="install.sh"):
    """Download the source archive at url and run the script in its top folder, with no
    terminal: an installer that needs sudo fails instead of waiting for a password nobody
    can type. Raises RuntimeError with a message for the user."""
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "release.tar.gz"
        req = urllib.request.Request(url, headers={"User-Agent": agent})
        with urllib.request.urlopen(req, timeout=60) as r:
            archive.write_bytes(r.read())
        src = Path(tmp) / "src"
        src.mkdir()
        _extract(archive, src)
        tops = list(src.iterdir())
        if len(tops) != 1 or not (tops[0] / script).is_file():
            raise RuntimeError(f"The release download has no {script}")
        run = subprocess.run(["sh", str(tops[0] / script)], cwd=tops[0],
                             stdin=subprocess.DEVNULL, capture_output=True, text=True,
                             start_new_session=True, check=False)
        if run.returncode != 0:
            last = (run.stderr.strip() or run.stdout.strip()).splitlines()[-1:]
            raise RuntimeError("The installer stopped" + (f": {last[0]}" if last else "")
                               + f". Run {script} in a terminal")


def _extract(archive, dest):
    try:
        _extract_tar(archive, dest)
    except tarfile.TarError as e:  # a cut-off download, or a file the filter refuses
        raise RuntimeError(f"Couldn't unpack the release: {str(e).splitlines()[0]}") from e


def _extract_tar(archive, dest):
    with tarfile.open(archive) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            # Python without extraction filters (e.g. Debian 12's 3.11.2): only plain
            # files and folders, with no absolute or ../ paths
            for m in tar.getmembers():
                if not (m.isfile() or m.isdir()) or m.name.startswith("/") \
                        or ".." in m.name.split("/"):
                    raise RuntimeError(f"Unexpected file in the release archive: {m.name}")
            tar.extractall(dest)


def swap_exe(exe, url, agent, asset, exe_name):
    """Download the release zip at url and swap its exe (exe_name, or the running exe's own
    name, in any folder of the zip) in for exe. The new version runs from the next start.
    Raises RuntimeError, OSError or zipfile.BadZipFile."""
    new, old = exe.with_name(exe.name + ".new"), exe.with_name(exe.name + ".old")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / asset
        req = urllib.request.Request(url, headers={"User-Agent": agent})
        with urllib.request.urlopen(req, timeout=120) as r, open(archive, "wb") as f:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(archive) as z:
            names = {exe_name, exe.name.lower()}
            name = next((n for n in z.namelist() if n.rsplit("/", 1)[-1].lower() in names), None)
            if not name:
                raise RuntimeError(f"The release zip has no {exe_name}")
            with z.open(name) as src, open(new, "wb") as dst:
                shutil.copyfileobj(src, dst)
    old.unlink(missing_ok=True)
    new.chmod(exe.stat().st_mode)
    exe.rename(old)  # Windows lets a running exe be renamed, not replaced
    try:
        new.rename(exe)
    except OSError:
        old.rename(exe)
        raise


def clean_old(exe):
    """Delete the exe an earlier swap_exe left behind. The old copy may still be ending when
    the new one starts, so this keeps trying for a while in the background."""
    def run():
        old = exe.with_name(exe.name + ".old")
        for _ in range(60):
            try:
                old.unlink(missing_ok=True)
                return
            except OSError:
                time.sleep(1)

    threading.Thread(target=run, daemon=True).start()
