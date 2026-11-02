"""Update check against the app's GitHub releases. No GUI code; yawcore is imported only to put movekit on the path.

check() asks GitHub for the latest sourceyaw-v* release at most once a day and remembers the
answer; install() downloads that release's source archive and runs its sourceyaw/install.sh,
which copies the app over the installed one. Settings stay where they are, and the new version
runs from the next start. A copy running from a git checkout never installs anything.

When Source Yaw is a module of the Linux core (~/.local/share/movekit/kit/sourceyaw, 3.7b in
PLAN.md), the core's module manager owns it: the auto switch is the one on its Modules card, and an
update goes through the manager, so the module folder and this copy stay the same version. Both go
through the core's own copy of movekit (`python3 -m movekit.modules`), never this copy's.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import yawcore  # noqa: F401 - puts movekit on the path

from movekit import paths  # after yawcore, which puts movekit on the path
from movekit import updater as kit

KEY = "sourceyaw"  # the module's key

CHECK_EVERY = 24 * 3600  # seconds between automatic checks
TIMEOUT = kit.TIMEOUT
parse_version = kit.parse_version


class Updater(kit.Updater):
    """check() gives the latest release as {"tag", "url", "notes"} when it is newer, and
    raises OSError/ValueError when GitHub can't be reached, so callers can stay quiet.
    install() raises RuntimeError with a message for the user when it fails."""
    check_every = CHECK_EVERY
    tag_prefix = "sourceyaw-v"

    def __init__(self, repo, version, app_dir, state_file):
        self.repo = repo                    # "Owner/movement-kit" on GitHub
        self.version = version              # the running version, "1.4.0"
        self.app_dir = Path(app_dir)
        # {"auto": bool, "checked": time, "latest": {...}, "installed": tag, "failed": tag}
        super().__init__(f"https://api.github.com/repos/{repo}/releases?per_page=100",
                         "sourceyaw", state_file)

    @property
    def dev_checkout(self):
        """Running from a git clone: installing over it would clobber local work."""
        return kit.in_git_checkout(self.app_dir)

    @property
    def core_kit(self):
        return paths.data_dir("movekit") / "kit"

    @property
    def managed(self):
        """Installed as a module of the core: the core's manager updates it."""
        return not self.dev_checkout and (self.core_kit / KEY / "module.json").is_file()

    def _manager(self, *args):
        """One call to the core's module manager; its reply. Raises RuntimeError with its error."""
        try:
            run = subprocess.run([sys.executable, "-m", "movekit.modules", *args], cwd=self.core_kit,
                                 env={**os.environ, "PYTHONPATH": str(self.core_kit)},
                                 stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                 timeout=900, check=False)
            reply = json.loads(run.stdout.strip().splitlines()[-1])
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(f"The Movement Kit's module manager didn't answer: {e}") from e
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error", "the module manager failed").partition(": ")[2]
                               or reply.get("error"))
        return reply

    @property
    def auto(self):
        if not self.managed:
            return super().auto
        try:
            card = next(c for c in self._manager("cards")["cards"] if c["key"] == KEY)
        except (RuntimeError, StopIteration, KeyError, TypeError):
            return False
        return bool(card.get("auto"))

    @auto.setter
    def auto(self, value):
        if not self.managed:
            kit.Updater.auto.fset(self, value)
            return
        try:
            self._manager("auto-on" if value else "auto-off", KEY)
        except RuntimeError:
            kit.Updater.auto.fset(self, value)  # the core is broken: keep it here at least

    def installed(self, latest):
        """Already installed by an earlier update: waiting for a restart."""
        return self.state.get("installed") == latest["tag"]

    def release_info(self, data):
        return {**super().release_info(data), "notes": data.get("body") or ""}

    def _install(self, latest):
        if self.managed:
            self._manager("update", KEY)
            return
        if self.dev_checkout:
            raise RuntimeError(f"Running from a git checkout in {self.app_dir}. Use git pull")
        kit.install_source(
            f"https://github.com/{self.repo}/archive/refs/tags/{latest['tag']}.tar.gz", self.agent,
            script="sourceyaw/install.sh")
