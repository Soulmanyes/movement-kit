"""Update check against the app's GitHub releases. No GUI code, only the standard library.

check() asks GitHub for the latest release at most once a day and remembers the answer;
install() downloads that release's source archive and runs its install.sh, which copies
the app over the installed one. Settings stay where they are, and the new version runs
from the next start. A copy running from a git checkout never installs anything.
"""

from pathlib import Path

from movekit import updater as kit  # after yawcore, which puts movekit on the path

CHECK_EVERY = 24 * 3600  # seconds between automatic checks
TIMEOUT = kit.TIMEOUT
parse_version = kit.parse_version


class Updater(kit.Updater):
    """check() gives the latest release as {"tag", "url", "notes"} when it is newer, and
    raises OSError/ValueError when GitHub can't be reached, so callers can stay quiet.
    install() raises RuntimeError with a message for the user when it fails."""
    check_every = CHECK_EVERY

    def __init__(self, repo, version, app_dir, state_file):
        self.repo = repo                    # "Owner/name" on GitHub
        self.version = version              # the running version, "1.4.0"
        self.app_dir = Path(app_dir)
        # {"auto": bool, "checked": time, "latest": {...}, "installed": tag, "failed": tag}
        super().__init__(f"https://api.github.com/repos/{repo}/releases/latest",
                         repo.split("/")[-1], state_file)

    @property
    def dev_checkout(self):
        """Running from a git clone: installing over it would clobber local work."""
        return kit.in_git_checkout(self.app_dir)

    def installed(self, latest):
        """Already installed by an earlier update: waiting for a restart."""
        return self.state.get("installed") == latest["tag"]

    def release_info(self, data):
        return {**super().release_info(data), "notes": data.get("body") or ""}

    def _install(self, latest):
        if self.dev_checkout:
            raise RuntimeError(f"Running from a git checkout in {self.app_dir}. Use git pull")
        kit.install_source(
            f"https://github.com/{self.repo}/archive/refs/tags/{latest['tag']}.tar.gz", self.agent)
