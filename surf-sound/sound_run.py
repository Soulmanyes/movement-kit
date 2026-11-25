"""Surf Sound's runner beside the game: a constant noise sound on the desktop while you ride a ramp or a
ceiling.

The HUD script (panorama/scripts/hud/movekit-surf-sound.ts) writes MK_SURFSND_RAMP, MK_SURFSND_CEIL and
MK_SURFSND_OFF into the game's console, which the autoexec block (install.py) logs to yaw.log. This
reads that log with a private movekit.session.Session (its own markers, polled every POLL seconds) and
plays the matching sound (noise.NoiseSynth through noise.player_class()). MK_SURFSND_WALL1-3 and
MK_SURFSND_GRAZE, MK_SURFSND_BONK and MK_SURFSND_JUMP (a jump's takeoff) are one-shot hits, mixed in on
top (NoiseSynth.hit). Custom sounds
(settings "custom") go to the synth, which falls back to a built-in sound for a file it can't read. While you
watch a replay or spectate, every marker but OFF ends in W; the "watch" setting mutes those.

A surf can last many seconds, so there is no cap on how long a sound plays. Instead the script writes
the sounding marker again every half second, and the sound stops after QUIET seconds without one (a
crash or a dead script can't leave it on), and on a map unload. The settings file is read again every
half second: on/off, sound, each sound's volume and the switches apply at once.

Linux: launch-hook.sh runs `python3 sound_run.py` in the background while Momentum runs. Windows:
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
from movekit import games, logfile, paths, session  # after the path above
from movekit.hub import local_import

TOKENS = (r"MK_SURFSND_RAMPW?", r"MK_SURFSND_CEILW?", r"MK_SURFSND_OFF", r"MK_SURFSND_WALL[123]W?",
          r"MK_SURFSND_GRAZEW?", r"MK_SURFSND_BONKW?", r"MK_SURFSND_JUMPW?")
MODES = {"SURFSND_RAMP": "ramp", "SURFSND_CEIL": "ceiling"}
# a hit's marker: (its noise.HITS name, the settings switch)
HITS = {"SURFSND_WALL1": ("wall1", "wall"), "SURFSND_WALL2": ("wall2", "wall"), "SURFSND_WALL3": ("wall3", "wall"),
        "SURFSND_GRAZE": ("graze", "graze"), "SURFSND_BONK": ("bonk", "bonk"), "SURFSND_JUMP": ("jump", "jump")}
POLL = 0.005  # seconds between log reads
QUIET = 1.5  # seconds without a marker after which a sound stops (the script beats every 0.5 s)
SETTINGS_EVERY = 0.5  # seconds between looks at the settings file
LOG = paths.config_dir("movekit") / "surf-sound-run.log"
LOG_MAX = 200_000


class Runner:
    """The sound's state from the session's events. player: movekit.tone's player class (a fake in the
    checks); synth: the synth class (noise.NoiseSynth); clock: seconds."""

    def __init__(self, settings, player, synth, clock=time.monotonic):
        self.settings, self.player, self.synth, self.clock = settings, player, synth, clock
        self.cfg = None
        self.sound = None
        self.voice = None  # the sound's synth, for hits
        self.mode = None  # what the script last said: "ramp", "ceiling" or None
        self.heard = None  # clock() of that marker
        self._looked = -SETTINGS_EVERY

    def _make(self, cfg):
        """The player for cfg, or None while it is off. The new synth is built before the old player
        closes, so the sound plays on while custom loops render (up to about half a second)."""
        old = self.sound
        self.sound = self.voice = None
        kinds = [k for k in ("ramp", "ceiling") if cfg[k]]
        if cfg["on"] and (kinds or any(cfg[k] for k in ("wall", "graze", "bonk", "jump"))):
            loops = self.settings.loop_sounds(cfg)
            voice = self.synth(1.0, {k: loops[k] for k in kinds}, self.settings.custom_files(cfg),
                               self.settings.levels(cfg),  # each sound's own volume
                               self.settings.loop_variants(cfg), random_start=cfg["random_start"])
            if old:
                old.close()
                old = None
            self.voice, self.sound = voice, self.player(voice)
            self.sound.start()
        if old:
            old.close()
        self.cfg = cfg
        self._apply()

    def reload(self):
        """Read the settings again every SETTINGS_EVERY seconds; a change rebuilds the player."""
        now = self.clock()
        if now - self._looked < SETTINGS_EVERY:
            return
        self._looked = now
        cfg = self.settings.load()
        if cfg != self.cfg:
            self._make(cfg)

    def handle(self, event):
        kind, data = event["type"], event["data"]
        name = (data.get("name") or "").removeprefix("MK_") if kind == "token" else None
        if name and name.endswith("W"):  # a replay's or a spectated player's (no plain name ends in W)
            name = name[:-1]
            if not (self.cfg and self.cfg["watch"]):
                if name in HITS:
                    return
                name = "SURFSND_OFF"
        if name in HITS:
            hit, switch = HITS[name]
            if self.voice and self.cfg[switch]:
                self.voice.hit(hit)
            return  # a one-shot: the constant sound and its timeout stay as they are
        if name in MODES:
            self.mode, self.heard = MODES[name], self.clock()
        elif name == "SURFSND_OFF" or kind == "map_left":
            self.mode = None
        self._apply()

    def tick(self):
        """Stop a sound whose script went quiet for QUIET seconds."""
        if self.mode and self.clock() - self.heard > QUIET:
            self.mode = None
        self._apply()

    def _apply(self):
        if self.sound:
            on = self.mode and self.cfg and self.cfg[self.mode]
            self.sound.mode = self.mode if on else None

    def close(self):
        if self.sound:
            self.sound.close()
            self.sound = self.voice = None


def run(log, stop=None, player=None, poll=POLL):
    """The sound for the game's console log `log` until `stop` (a threading.Event) is set."""
    sess = session.Session(log, tokens=TOKENS)
    noise = local_import(__file__, "noise")
    runner = Runner(local_import(__file__, "settings"), player or noise.player_class(), noise.NoiseSynth)
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
    """Windows: the sound as a thread of the core's launch process, for Momentum only. Returns the
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
            print(f"surf-sound: sound stopped by an error:\n{traceback.format_exc()}", flush=True)

    thread = threading.Thread(target=body, name="surf-sound", daemon=True)
    thread.start()

    def finish():
        # at the exe's exit, after the game closed: the sound device closed
        stop.set()
        thread.join(2)
    atexit.register(finish)
    print("surf-sound: sound runner started", flush=True)
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
