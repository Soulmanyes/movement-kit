"""The kit's modules: each tool installs, updates, rolls back and uninstalls on its own (3.7b in PLAN.md).

A module is a tool folder with a module.json:

    {"key": "strafe-review", "title": "Strafe Review", "summary": "...",
     "os": ["linux", "win32"],                  sys.platform prefixes it runs on
     "tag_prefix": "strafe-review-v",           its release line in the monorepo
     "version_from": "collector/updater.py",    the file whose VERSION = "x.y.z" line is its version
     "needs_core": "1.0.0",                     the lowest core version it runs on
     "needs": [],                               keys of modules it can't run without
     "data": ["data:strafe-review/attempts"],   what "Also delete saved data" removes, under
                                                movekit.paths' data_dir (data:) or config_dir (config:)
     "standalone": ["gain_converter.py"]}       files that run on their own, never in the core (an
                                                old window), so check_modules' import rule skips them

and, if it changes anything outside its own folder, a module_hooks.py with any of:

    install(ctx)               after the folder is in place (first install, update, roll back);
                               puts the game files, autoexec block and launch hooks in. Run again
                               on every version, so it must be safe to repeat.
    uninstall(ctx)             before the folder goes; takes those out again
    stop(ctx) -> bool          stop what the module runs; True if something was running
    start(ctx)                 start it again after an update, when stop said it was running

ctx is a Context: the module's folder, the kit root, and script(), which runs one of the module's
scripts in a fresh process (python, or the core exe's --run-script). Hooks raise RuntimeError with
a message for the user.

Where modules live (kit_root): every module sits in a folder named after its key, next to movekit,
in the same layout as the repo, so a tool finds movekit the way it does in the repo.
  - git checkout (the owner's copy): the checkout itself. Updates come from git pull, so the
    manager doesn't download; uninstall runs the uninstall hook and hides the module, and install
    runs the install hook and shows it again. The code stays.
  - Windows exe: %LOCALAPPDATA%\\movekit\\kit (the core is the exe, which bundles movekit).
  - Linux copy: the core's own folder, ~/.local/share/movekit/kit (3.7b.4).
The previous version of each module is kept in <data>/previous/<key> for roll back.

State, in <data>/modules.json: per key {"auto", "installed" (tag), "previous" (tag), "failed"
(tag), "removed" (git checkout only)}, plus "checked" and "latest" (per key: tag, url, notes,
asset) from the last look at GitHub. The core is the entry "core" (line hub-v*); how it installs
an update is the caller's (see Manager.core_installer), since that differs by platform.

Standard library only.
"""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from movekit import paths, updater

CORE_VERSION = "1.0.0"  # the hub-v* line; hub/hub_release.py's VERSION must match (check_modules)
CORE = "core"
CORE_PREFIX = "hub-v"
REPO = "Soulmanyes/movement-kit"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=100"
AGENT = "movement-kit-modules"
CHECK_EVERY = 6 * 3600  # seconds between automatic looks at GitHub
MANIFEST = "module.json"
HOOKS = "module_hooks.py"
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATA_RE = re.compile(r"^(data|config):([A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*)$")
VERSION_RE = re.compile(r'^VERSION = "([0-9][0-9.]*)"', re.MULTILINE)
KIT = Path(__file__).resolve().parent.parent  # the repo root, or the folder the core runs from


def asset_name(key):
    return f"{key}-module.zip"


def manifest_asset(key):
    """The release's copy of module.json, so the hub can name a module and see what core it needs
    before downloading it."""
    return f"{key}-module.json"


def data_dir():
    """The kit's own folder, which movekit/launch.py's hooks/ already lives in."""
    return paths.data_dir("movekit")


def frozen():
    return bool(getattr(sys, "frozen", False))


def default_kit_root():
    return data_dir() / "kit" if frozen() else KIT


def is_checkout(root):
    return (Path(root) / ".git").exists()


def read_manifest(folder):
    """The folder's module.json as a dict. Raises ValueError saying what is wrong."""
    folder = Path(folder)
    try:
        m = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"no readable {MANIFEST}") from e
    if not isinstance(m, dict):
        raise ValueError(f"{MANIFEST} is not an object")  # noqa: TRY004 - callers catch ValueError
    for field, kind in (("key", str), ("title", str), ("os", list), ("tag_prefix", str),
                        ("version_from", str), ("needs_core", str)):
        if not isinstance(m.get(field), kind):
            raise ValueError(f"{MANIFEST} lacks {field}")  # noqa: TRY004
    if not KEY_RE.match(m["key"]) or m["key"] == CORE:
        raise ValueError(f"bad key {m['key']!r}")
    if m["key"] != folder.name:
        raise ValueError(f"key {m['key']!r} doesn't match the folder name {folder.name!r}")
    if not m["tag_prefix"].startswith(m["key"]) or m["tag_prefix"] == CORE_PREFIX:
        raise ValueError(f"tag_prefix {m['tag_prefix']!r} isn't the module's own line")
    if not updater.parse_version(m["needs_core"]):
        raise ValueError(f"needs_core {m['needs_core']!r} isn't a version")
    m.setdefault("summary", "")
    m.setdefault("needs", [])
    m.setdefault("data", [])
    m.setdefault("standalone", [])
    if not all(isinstance(k, str) and KEY_RE.match(k) for k in m["needs"]):
        raise ValueError("needs must list module keys")
    if not all(isinstance(d, str) and DATA_RE.match(d) and ".." not in d for d in m["data"]):
        raise ValueError("data entries look like data:<folder>/<path> or config:<folder>")
    # "Also delete saved data" deletes these, so they stay inside the module's own folders: a typo
    # such as data:Steam must not reach another program's files
    if not all(d.split(":", 1)[1].split("/")[0] == m["key"] for d in m["data"]):
        raise ValueError(f"data entries must be in the module's own folder ({m['key']})")
    if not all(isinstance(f, str) and (folder / f).is_file() for f in m["standalone"]):
        raise ValueError("standalone must list files in the module's folder")
    return m


def module_version(folder, manifest):
    """The VERSION in the module's version_from file, or None."""
    try:
        found = VERSION_RE.search((Path(folder) / manifest["version_from"]).read_text(encoding="utf-8"))
    except OSError:
        return None
    return found.group(1) if found else None


def data_paths(manifest):
    """The files and folders "Also delete saved data" removes, as Paths."""
    out = []
    for entry in manifest["data"]:
        where, rel = entry.split(":", 1)
        first, _, rest = rel.partition("/")
        base = paths.data_dir(first) if where == "data" else paths.config_dir(first)
        out.append(base / rest if rest else base)
    return out


def newer(tag, version):
    theirs, mine = updater.parse_version(tag), updater.parse_version(version)
    return bool(theirs and (not mine or theirs > mine))


def script_command(script, *args):
    """The command that runs a module's script in a fresh process: python from the repo or a Linux
    copy, the core exe's --run-script in the Windows exe (hub/movement_kit.py)."""
    if frozen():
        return [sys.executable, "--run-script", str(script), *map(str, args)]
    return [sys.executable, str(script), *map(str, args)]


class Context:
    """What a module's hooks get."""

    def __init__(self, folder, kit_root, manifest):
        self.folder = Path(folder)
        self.kit = Path(kit_root)
        self.manifest = manifest
        self.platform = sys.platform

    def script(self, name, *args, timeout=300):
        """Run the module's Python script name (path in its folder) with args; returns its output.
        Raises RuntimeError with the script's last line when it fails."""
        return self.run(script_command(self.folder / name, *args), name, timeout)

    def run(self, cmd, name=None, timeout=300):
        """Run cmd in the module's folder with no terminal (an installer that wants sudo fails
        instead of waiting); returns its output. Raises RuntimeError with its last line."""
        name = name or Path(str(cmd[0])).name
        try:
            run = subprocess.run([str(c) for c in cmd], cwd=self.folder, stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, timeout=timeout,
                                 start_new_session=True, check=False)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"{name} didn't finish in {timeout} s") from e
        if run.returncode != 0:
            last = (run.stderr.strip() or run.stdout.strip()).splitlines()[-1:]
            raise RuntimeError(f"{name} stopped" + (f": {last[0]}" if last else ""))
        return run.stdout


class Manager:
    """Every module's install, update, roll back, uninstall and auto switch.

    kit_root  where modules live (default_kit_root())
    data      the manager's own folder: state, previous versions, downloads (data_dir())
    api       GitHub's release list (tests point it at a local server)
    core_version, core_installer
              the running core's version, and a function(latest) that installs a core update
              (None: the core card offers no install, e.g. a git checkout)
    """

    def __init__(self, kit_root=None, data=None, api=API, core_version=CORE_VERSION,
                 core_installer=None, platform=sys.platform):
        self.kit = Path(kit_root) if kit_root else default_kit_root()
        self.data = Path(data) if data else data_dir()
        self.api = api
        self.core_version = core_version
        self.core_installer = core_installer
        self.platform = platform
        self.checkout = is_checkout(self.kit)
        self.state_file = self.data / "modules.json"
        self.state = self._load()

    # state

    def _load(self):
        try:
            state = json.loads(self.state_file.read_text())
            return state if isinstance(state, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        self.data.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2) + "\n")
        tmp.replace(self.state_file)

    def _entry(self, key):
        return self.state.setdefault("modules", {}).setdefault(key, {})

    def _forget(self, key):
        self.state.get("modules", {}).pop(key, None)

    # what is there

    def folder(self, key):
        return self.kit / key

    def available(self):
        """{key: manifest} of the modules in the kit root for this OS (installed or not, in a git
        checkout; installed ones elsewhere). Broken manifests are left out (see problems())."""
        out = {}
        for folder in sorted(p for p in self.kit.iterdir() if p.is_dir()) if self.kit.is_dir() else ():
            if not (folder / MANIFEST).is_file():
                continue
            try:
                m = read_manifest(folder)
            except ValueError:
                continue
            if any(self.platform.startswith(o) for o in m["os"]):
                out[m["key"]] = m
        return out

    def problems(self):
        """[(folder name, text)] for module folders whose module.json is broken."""
        out = []
        for folder in sorted(p for p in self.kit.iterdir() if p.is_dir()) if self.kit.is_dir() else ():
            if (folder / MANIFEST).is_file():
                try:
                    read_manifest(folder)
                except ValueError as e:
                    out.append((folder.name, str(e)))
        return out

    def installed(self):
        """{key: manifest} of the installed modules for this OS."""
        mods = self.available()
        if self.checkout:
            return {k: m for k, m in mods.items() if not self._entry(k).get("removed")}
        return mods

    def roots(self):
        """The module folders the hub should load sections from."""
        return [self.folder(k) for k in self.installed()]

    def known(self):
        """Keys the hub can offer: installed modules plus releases seen on GitHub."""
        keys = set(self.available())
        if not self.checkout:
            keys |= {k for k in self.state.get("latest", {}) if k != CORE}
        return sorted(keys)

    # GitHub

    def fetch(self):
        req = urllib.request.Request(self.api, headers={
            "Accept": "application/vnd.github+json", "User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=updater.TIMEOUT) as r:
            releases = json.load(r)
        if not isinstance(releases, list):
            raise ValueError("GitHub's answer isn't a release list")  # noqa: TRY004
        return releases

    def check(self, force=False):
        """Look at GitHub at most every CHECK_EVERY seconds (or now, when forced) and remember the
        newest release of the core and of each module line: {key: {tag, url, notes, asset}}.
        Module lines are found by the "<key>-module.zip" asset, so a tool's releases from before
        3.7b (no module zip) aren't offered. Raises OSError/ValueError when GitHub can't be read."""
        if not force and time.time() - self.state.get("checked", 0) < CHECK_EVERY \
                and "latest" in self.state:
            return self.state["latest"]
        latest = {}
        for r in self.fetch():
            if not isinstance(r, dict) or r.get("draft") or r.get("prerelease"):
                continue
            tag = r.get("tag_name")
            if not isinstance(tag, str) or not updater.parse_version(tag):
                continue
            assets = {a.get("name"): a.get("browser_download_url") for a in r.get("assets") or []
                      if isinstance(a, dict)}
            if tag.startswith(CORE_PREFIX):
                key = CORE
            else:
                key = next((n[:-len("-module.zip")] for n in assets
                            if isinstance(n, str) and n.endswith("-module.zip")
                            and tag.startswith(n[:-len("-module.zip")] + "-v")), None)
                if not key:
                    continue
            info = {"tag": tag, "url": r.get("html_url", ""), "notes": r.get("body") or "",
                    "asset": assets.get(asset_name(key)) if key != CORE else None,
                    "manifest_url": assets.get(manifest_asset(key)) if key != CORE else None}
            old = latest.get(key)
            if not old or updater.parse_version(tag) > updater.parse_version(old["tag"]):
                latest[key] = info
        for key, info in latest.items():
            url = info.pop("manifest_url", None)
            if url:
                info["manifest"] = self._fetch_manifest(url)
        self.state.update(latest=latest, checked=time.time())
        self._save()
        return latest

    def _fetch_manifest(self, url):
        """The title, summary and needs from a release's module.json copy; {} if it can't be read
        (the card then shows the key, and the download still checks the real one)."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=updater.TIMEOUT) as r:
                m = json.loads(r.read(64 * 1024))
        except (OSError, ValueError):
            return {}
        if not isinstance(m, dict):
            return {}
        out = {k: m[k] for k in ("title", "summary") if isinstance(m.get(k), str)}
        if isinstance(m.get("needs_core"), str) and updater.parse_version(m["needs_core"]):
            out["needs_core"] = m["needs_core"]
        if isinstance(m.get("needs"), list) and all(isinstance(k, str) for k in m["needs"]):
            out["needs"] = m["needs"]
        return out

    # one card's facts

    def version(self, key):
        if key == CORE:
            return self.core_version
        m = self.available().get(key)
        return module_version(self.folder(key), m) if m else None

    def info(self, key):
        """What the hub shows on a module's (or the core's) card."""
        latest = self.state.get("latest", {}).get(key)
        entry = self.state.get("modules", {}).get(key, {})
        if key == CORE:
            installed, manifest = True, {"title": "Movement Kit (core)", "summary":
                                         "The hub window, the HUD settings and the launch option."}
        else:
            remote = (latest or {}).get("manifest") or {}
            manifest = self.available().get(key) or {"title": remote.get("title", key),
                                                     "summary": remote.get("summary", ""),
                                                     "needs": remote.get("needs", [])}
            installed = key in self.installed()
        version = self.version(key) if installed else None
        update = bool(installed and latest and newer(latest["tag"], version))
        # a waiting mark counts only for the release that set it; a newer one may not need it
        waiting = (entry.get("waiting_for_core") if latest and entry.get("waiting_tag") == latest["tag"]
                   else None) or (self._too_new(latest) if key != CORE else None)
        if self.checkout or waiting:
            can_update = False
        elif key == CORE:
            can_update = update and self.core_installer is not None
        else:
            can_update = update and bool(latest.get("asset"))
        return {
            "key": key, "title": manifest["title"], "summary": manifest.get("summary", ""),
            "installed": installed, "version": version,
            "auto": bool(entry.get("auto")),
            "latest": latest, "update": update, "can_update": can_update,
            "can_install": not installed and (self.checkout and key in self.available()
                                              or bool(latest and latest.get("asset") and not waiting)),
            "can_rollback": (not self.checkout and installed and key != CORE
                             and (self.data / "previous" / key).is_dir()),
            "previous": entry.get("previous") if not self.checkout else None,
            "failed": entry.get("failed"),
            "waiting_for_core": waiting,
            "needed_by": [k for k, m in self.installed().items() if key in m["needs"]],
            "needs_missing": [k for k in manifest.get("needs", []) if k not in self.installed()],
            "checkout": self.checkout,
        }

    def _too_new(self, latest):
        """The core version a release says it needs, when that's newer than this core."""
        need = ((latest or {}).get("manifest") or {}).get("needs_core")
        if need and updater.parse_version(need) > updater.parse_version(self.core_version):
            return need
        return None

    def cards(self):
        """The core's card, then one per module the hub can offer."""
        return [self.info(CORE)] + [self.info(k) for k in self.known()]

    # switches

    def set_auto(self, key, value):
        if not isinstance(value, bool):
            raise ValueError("auto must be true or false")  # noqa: TRY004 - the bridge reports ValueError
        self._entry(key)["auto"] = value
        self._save()

    # hooks

    def _hooks(self, key, folder=None):
        folder = Path(folder or self.folder(key))
        file = folder / HOOKS
        if not file.is_file():
            return None
        name = f"movekit_module_{re.sub(r'\W', '_', key)}_hooks"
        # a fresh load every time: the code now on disk, after an update or roll back
        spec = importlib.util.spec_from_file_location(name, file)
        hooks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hooks)
        return hooks

    def _call(self, key, hook, folder=None):
        hooks = self._hooks(key, folder)
        fn = getattr(hooks, hook, None) if hooks else None
        if not fn:
            return None
        folder = Path(folder or self.folder(key))
        return fn(Context(folder, self.kit, read_manifest(folder)))

    def _stop(self, key):
        try:
            return bool(self._call(key, "stop"))
        except Exception:  # noqa: BLE001 - nothing running is fine; the swap goes on
            return False

    def _start(self, key):
        try:
            self._call(key, "start")
        except Exception:  # noqa: BLE001, S110 - the module starts by itself next time
            pass

    # changes

    def install(self, key):
        """Install a module that isn't installed: the newest release (or, in a git checkout, run
        its install hook from the checkout and show it again)."""
        if key in self.installed():
            raise RuntimeError(f"{key} is already installed")
        if self.checkout:
            if key not in self.available():
                raise RuntimeError(f"{key} isn't in this checkout")
            self._check_needs(key, self.available()[key])
            self._call(key, "install")
            self._entry(key).pop("removed", None)
            self._save()
            return
        latest = self.check().get(key)
        if not latest or not latest.get("asset"):
            raise RuntimeError(f"No {key} module release on GitHub yet")
        self._put(key, latest, first=True)

    def update(self, key):
        """Install the newest release of an installed module (or of the core)."""
        if self.checkout:
            raise RuntimeError("This copy is a git checkout: git pull updates it")
        latest = self.check().get(key)
        if key == CORE:
            if not latest or not newer(latest["tag"], self.core_version):
                raise RuntimeError("The core is up to date")
            if not self.core_installer:
                raise RuntimeError("This core can't update itself")
            self._mark(key, latest["tag"], lambda: self.core_installer(latest))
            return
        if key not in self.installed():
            raise RuntimeError(f"{key} isn't installed")
        if not latest or not newer(latest["tag"], self.version(key)):
            raise RuntimeError(f"{key} is up to date")
        if not latest.get("asset"):
            raise RuntimeError(f"The {latest['tag']} release has no {asset_name(key)}")
        self._put(key, latest, first=False)

    def update_all(self):
        """Update every module with a newer release, then the core. Returns {key: error or None}."""
        results = {}
        for card in self.cards()[1:] + self.cards()[:1]:
            if card["can_update"]:
                try:
                    self.update(card["key"])
                    results[card["key"]] = None
                except Exception as e:  # noqa: BLE001 - one module's failure mustn't stop the rest
                    results[card["key"]] = str(e)
        return results

    def auto_update(self):
        """What the hub runs at start: update each module (and the core) whose auto switch is on,
        unless that same release failed before. Returns {key: error or None}."""
        try:
            self.check()
        except (OSError, ValueError):
            return {}
        results = {}
        for card in self.cards()[1:] + self.cards()[:1]:
            if card["auto"] and card["can_update"] and card["failed"] != card["latest"]["tag"]:
                try:
                    self.update(card["key"])
                    results[card["key"]] = None
                except Exception as e:  # noqa: BLE001 - one module's failure mustn't stop the rest
                    results[card["key"]] = str(e)
        return results

    def rollback(self, key):
        """Swap the kept previous version back in (the current one becomes the previous)."""
        prev = self.data / "previous" / key
        if self.checkout or key == CORE or not prev.is_dir():
            raise RuntimeError(f"No earlier {key} version is kept")
        staged = self.data / "staging" / (key + "-rollback")
        shutil.rmtree(staged, ignore_errors=True)
        staged.parent.mkdir(parents=True, exist_ok=True)
        prev.rename(staged)
        try:
            self._swap(key, staged, first=False)
        except Exception:
            if staged.is_dir() and not prev.exists():
                staged.rename(prev)  # _swap put the rest back; this is the kept version's slot
            raise
        entry = self._entry(key)
        entry["installed"], entry["previous"] = entry.get("previous"), entry.get("installed")
        entry.pop("failed", None)
        self._save()

    def uninstall(self, key, delete_data=False):
        """Take a module out: its uninstall hook (game files, autoexec block, launch hooks), then
        its folder (not in a git checkout) and, when asked, its saved data."""
        if key == CORE:
            raise RuntimeError("The core can't be uninstalled from the hub")
        mods = self.installed()
        if key not in mods:
            raise RuntimeError(f"{key} isn't installed")
        users = [k for k, m in mods.items() if key in m["needs"]]
        if users:
            raise RuntimeError(f"{', '.join(users)} needs {key}; uninstall that first")
        manifest = mods[key]
        self._stop(key)
        self._call(key, "uninstall")
        if delete_data:
            for p in data_paths(manifest):
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
        if self.checkout:
            self._entry(key)["removed"] = True
        else:
            shutil.rmtree(self.folder(key), ignore_errors=True)
            shutil.rmtree(self.data / "previous" / key, ignore_errors=True)
            auto = self._entry(key).get("auto")
            self._forget(key)
            if auto:  # the switch is the person's choice; it stays for a reinstall
                self._entry(key)["auto"] = auto
        self._save()

    # internals

    def _check_needs(self, key, manifest):
        missing = [k for k in manifest["needs"] if k not in self.installed()]
        if missing:
            raise RuntimeError(f"{key} needs {', '.join(missing)}; install that first")

    def _mark(self, key, tag, action):
        entry = self._entry(key)
        try:
            action()
        except Exception:  # any failure, a hook's own bug too, marks the release
            entry["failed"] = tag
            self._save()
            raise
        entry["installed"] = tag
        entry.pop("failed", None)
        self._save()

    def _download(self, key, latest):
        """The release's module zip, unpacked to <data>/staging/<key>; returns that folder."""
        staging = self.data / "staging"
        dest = staging / key
        shutil.rmtree(dest, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=staging) as tmp:
            archive = Path(tmp) / asset_name(key)
            req = urllib.request.Request(latest["asset"], headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=120) as r, open(archive, "wb") as f:
                shutil.copyfileobj(r, f)
            unpacked = Path(tmp) / "unpacked"
            with zipfile.ZipFile(archive) as z:
                for name in z.namelist():
                    target = (unpacked / name).resolve()
                    if not target.is_relative_to(unpacked.resolve()):
                        raise RuntimeError(f"Unexpected file in the module zip: {name}")
                z.extractall(unpacked)
            top = unpacked / key
            if not (top / MANIFEST).is_file():
                raise RuntimeError(f"The module zip has no {key}/{MANIFEST}")
            top.rename(dest)
        return dest

    def _put(self, key, latest, first):
        entry = self._entry(key)

        def run():
            new = self._download(key, latest)
            try:
                manifest = read_manifest(new)
            except ValueError as e:
                raise RuntimeError(f"The {latest['tag']} module is broken: {e}") from e
            if updater.parse_version(manifest["needs_core"]) > updater.parse_version(self.core_version):
                entry["waiting_for_core"], entry["waiting_tag"] = manifest["needs_core"], latest["tag"]
                raise RuntimeError(f"{latest['tag']} needs core {manifest['needs_core']}; "
                                   "update the core first")
            entry.pop("waiting_for_core", None)
            entry.pop("waiting_tag", None)
            self._check_needs(key, manifest)
            self._swap(key, new, first)
            if not first:
                entry["previous"] = entry.get("installed")

        try:
            self._mark(key, latest["tag"], run)
        finally:
            shutil.rmtree(self.data / "staging" / key, ignore_errors=True)

    def _swap(self, key, incoming, first):
        """Put the folder incoming in as the module's current version, the current one becoming the
        previous (the older previous is dropped), and run the install hook. What the module runs is
        stopped first and started again after, whatever happens. On any failure every folder goes back
        where it was, incoming included, and the old version's install hook runs again; the first
        error is raised."""
        cur, prevs = self.folder(key), self.data / "previous"
        prev, hold = prevs / key, prevs / (key + ".hold")  # hold: the older previous, until it worked
        running = False if first else self._stop(key)
        done = []
        try:
            prevs.mkdir(parents=True, exist_ok=True)
            self.kit.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(hold, ignore_errors=True)
            if prev.exists():
                prev.rename(hold)
                done.append("hold")
            if cur.exists():
                cur.rename(prev)
                done.append("prev")
            incoming.rename(cur)
            done.append("cur")
            self._call(key, "install")
        except Exception:
            for step, src, dst in (("cur", cur, incoming), ("prev", prev, cur), ("hold", hold, prev)):
                if step in done:
                    try:
                        src.rename(dst)
                    except OSError:
                        pass  # best effort: the error below is what the card shows
            if "prev" in done:
                try:
                    self._call(key, "install")
                except Exception:  # noqa: BLE001, S110 - the first error is the one to report
                    pass
            raise
        finally:
            if running:
                self._start(key)
        shutil.rmtree(hold, ignore_errors=True)
