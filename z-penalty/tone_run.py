"""Z Penalty's tone beside the game: a constant tone on the desktop while the penalty is on.

The panel script (panorama/scripts/hud/movekit-z-penalty.ts) writes ZPEN_ON when a penalised stretch
starts and ZPEN_OFF when it ends into the game's console, which the autoexec block (install.py) logs
to yaw.log. This reads that log with a private movekit.session.Session (its own markers, polled every
POLL seconds; in game 2026-11-09 a marker reached the desktop 0-3 ms after it was written) and turns
the tone (movekit.tone) on and off.

The tone also stops on a map unload and after MAX_ON seconds without a ZPEN_OFF (the longest
stretch seen was 39 ticks, under 0.6 s), so a crash or alt-tab mid-climb can't leave it sounding.
The settings file is read again when it changes: switching the tone on or off, its pitch or its
volume applies at once.

Linux: launch-hook.sh runs `python3 tone_run.py` in the background while Momentum runs. Windows:
module_hooks.launch calls start() inside the core's launch process, which exits with the game.
"""
import atexit
import sys
import threading
import time
import traceback
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False) and (_HERE.parent / "movekit").is_dir() and str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))  # the kit root (repo or core copy); the core exe bundles movekit
from movekit import games, logfile, paths, session, tone  # after the path above
from movekit.hub import local_import

TOKENS = (r"ZPEN_ON", r"ZPEN_OFF")
POLL = 0.005  # seconds between log reads
MAX_ON = 2.0  # seconds the tone sounds at most without a ZPEN_OFF
SETTINGS_EVERY = 0.5  # seconds between looks at the settings file
LOG = paths.config_dir("movekit") / "z-penalty-run.log"
LOG_MAX = 200_000


class Runner:
    """The tone's state from the session's events. player: movekit.tone's player class (a fake in the
    checks); clock: seconds."""

    def __init__(self, settings, player, clock=time.monotonic):
        self.settings, self.player, self.clock = settings, player, clock
        self.cfg = None
        self.tone = None
        self.on_since = None
        self._stamp = None
        self._looked = -SETTINGS_EVERY

    def _make(self, cfg):
        """The tone for cfg, or None while it is off."""
        if self.tone:
            self.tone.close()
            self.tone = None
        if cfg["on"]:
            self.tone = self.player(tone.ToneSynth(cfg["volume"] / 100, {"on": cfg["pitch"]}))
            self.tone.start()
            if self.on_since is not None:
                self.tone.mode = "on"
        self.cfg = cfg

    def reload(self):
        """Read the settings again if the file changed (or on the first call)."""
        now = self.clock()
        if now - self._looked < SETTINGS_EVERY:
            return
        self._looked = now
        try:
            stamp = self.settings.file().stat().st_mtime_ns
        except OSError:
            stamp = None
        if self.cfg is None or stamp != self._stamp:
            self._stamp = stamp
            cfg = self.settings.load()
            if cfg != self.cfg:
                self._make(cfg)

    def handle(self, event):
        kind, data = event["type"], event["data"]
        if kind == "token" and data.get("name") == "ZPEN_ON":
            self.on_since = self.clock()
        elif (kind == "token" and data.get("name") == "ZPEN_OFF") or kind == "map_left":
            self.on_since = None
        self._apply()

    def tick(self):
        """Stop a tone that has sounded MAX_ON without a ZPEN_OFF."""
        if self.on_since is not None and self.clock() - self.on_since > MAX_ON:
            self.on_since = None
        self._apply()

    def _apply(self):
        if self.tone:
            self.tone.mode = "on" if self.on_since is not None else None

    def close(self):
        if self.tone:
            self.tone.close()
            self.tone = None


def run(log, stop=None, player=None, poll=POLL):
    """The tone for the game's console log `log` until `stop` (a threading.Event) is set."""
    sess = session.Session(log, tokens=TOKENS)
    runner = Runner(local_import(__file__, "settings"), player or tone.player())
    stop = stop or threading.Event()
    try:
        while not stop.wait(poll):
            runner.reload()
            for event in sess.poll():
                runner.handle(event)
            runner.tick()
    finally:
        runner.close()


def start(argv):
    """Windows: the tone as a thread of the core's launch process, for Momentum only. Returns the
    thread, or None."""
    if games.from_command(argv) != "momentum":
        return None
    game_dir = games.find("momentum")
    if game_dir is None:
        return None
    logfile.tee(LOG, LOG_MAX)
    stop = threading.Event()

    def body():
        try:
            run(game_dir / "yaw.log", stop)
        except Exception:  # noqa: BLE001 - logged, the game keeps running
            print(f"z-penalty: tone stopped by an error:\n{traceback.format_exc()}", flush=True)

    thread = threading.Thread(target=body, name="z-penalty-tone", daemon=True)
    thread.start()

    def finish():
        # at the exe's exit, after the game closed: the tone device closed
        stop.set()
        thread.join(2)
    atexit.register(finish)
    print("z-penalty: tone runner started", flush=True)
    return thread


def main():
    game_dir = games.find("momentum")
    if game_dir is None:
        sys.exit("Momentum Mod not found in any Steam library")
    try:
        run(game_dir / "yaw.log")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
