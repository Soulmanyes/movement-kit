#!/usr/bin/env python3
"""Strafe Trainer: runs beside the game (launch-hook.sh through movekit-run on Linux; on Windows a
thread in the core exe's launch process, module_hooks.launch).

Reads the strafe, turn and jump keys plus mouse movement, and while it listens (a jump key held,
the timer running in Momentum, or either: the when_jump and when_timer settings):
  - plays a sound when you turn one way for a few ticks without holding that
    way's strafe key (no key, or the other one), and one when both strafe
    keys are held at once,
  - works out each strafe's offset: the ticks between turning the other way
    and switching strafe keys. Negative means the key came early, positive
    late, 0 on the same tick. The number is drawn over the game where the
    platform can (Linux: the Vulkan layer in overlay/).

This file is platform-neutral (it imports on Windows, with no Pillow): the cue logic, binds,
settings and the main loop. Where keys come from, how sounds play, focus and the overlay are
the platform's (trainer_linux.Linux, trainer_win.Windows), handed to run(). Settings are store.py's.
Part of Source Yaw until Phase 13 (PLAN.md).

Settings saved while the game runs (the hub's Apply) are picked up within half a second
(SettingsWatch): switched off, the trainer goes quiet but keeps running, so switching it on again
works too. A trainer that is off when the game starts waits (no input read, nothing opened) until
it is switched on. Two things wait for the next game start: the offset's font size and colours (the
overlay layer loads its atlas once), and on Linux the offset number itself when the trainer was off
at the game's start (launch-hook.sh loads the layer only for a trainer that is on).

Siblings (store, gamecfg, trainer_linux, trainer_win) load through movekit.hub.local_import, also
when this runs as a script, so the hub section and a script get one module object per file.

Keys come from the game's own binds (config.cfg plus aliases from every cfg),
so rebinding in the game just works. On Linux the input service must forward
that key too (see /etc/sourceyaw-inputd.conf; the service kept Source Yaw's name).

  trainer.py GAME            run until the game exits (launch-hook.sh does this)
  trainer.py GAME --binds    print which keys do what, then exit
  trainer.py GAME --enabled  exit 0 when the trainer is on for GAME, else 1
"""

import array
import math
import sys
import time
from fractions import Fraction
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False) and (_HERE.parent / "movekit").is_dir() and str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))  # the kit root (repo or core copy); the core exe bundles movekit
from movekit import binds, games, maps, session  # after the path above
from movekit.hub import local_import

VERSION = "1.1.0"  # the Strafe Trainer's (module.json reads it); bump in the same commit as the release tag

store = local_import(__file__, "store")
gamecfg = local_import(__file__, "gamecfg")

# the Linux input service's config: which keys it forwards (read here, not in trainer_linux,
# because the hub's settings ask too)
INPUTD_CONFIG = "/etc/sourceyaw-inputd.conf"
EV_KEY, EV_REL = 1, 2
REL_X, REL_WHEEL = 0, 8

# Source key names -> evdev codes the input service can forward
SOURCE_KEYS = {c: code for c, code in zip("qwertyuiop", range(16, 26))}
SOURCE_KEYS.update({c: code for c, code in zip("asdfghjkl", range(30, 39))})
SOURCE_KEYS.update({c: code for c, code in zip("zxcvbnm", range(44, 51))})
SOURCE_KEYS.update({d: code for d, code in zip("1234567890", range(2, 12))})
SOURCE_KEYS.update({"space": 57, "alt": 56, "ralt": 100, "ctrl": 29, "rctrl": 97, "shift": 42,
                    "rshift": 54, "tab": 15, "capslock": 58, "backspace": 14,
                    "mouse1": 272, "mouse2": 273, "mouse3": 274, "mouse4": 275, "mouse5": 276,
                    "mwheelup": "wheel", "mwheeldown": "wheel"})

# evdev names in the input service's config -> codes, for the keys above
EVDEV_NAMES = {**{f"KEY_{k.upper()}": c for k, c in SOURCE_KEYS.items() if len(k) == 1},
               "KEY_SPACE": 57, "KEY_LEFTALT": 56, "KEY_RIGHTALT": 100, "KEY_LEFTCTRL": 29,
               "KEY_RIGHTCTRL": 97, "KEY_LEFTSHIFT": 42, "KEY_RIGHTSHIFT": 54, "KEY_TAB": 15,
               "KEY_CAPSLOCK": 58, "KEY_BACKSPACE": 14, "BTN_LEFT": 272, "BTN_RIGHT": 273,
               "BTN_MIDDLE": 274, "BTN_SIDE": 275, "BTN_EXTRA": 276}


def forwarded():
    """Codes the input service passes on ("wheel" included), or None if it isn't installed."""
    try:
        text = Path(INPUTD_CONFIG).read_text()
    except OSError:
        return None
    codes = set()
    for line in text.splitlines():
        name, _, value = line.split("#", 1)[0].partition("=")
        if name.strip() == "keys":
            codes |= {EVDEV_NAMES[k] for k in value.split() if k in EVDEV_NAMES}
        elif name.strip() == "axes" and "REL_WHEEL" in value.split():
            codes.add("wheel")
    return codes


ROLES = {"+jump": "jump", "+moveleft": "strafe_left", "+moveright": "strafe_right",
         "+left": "turn_left", "+right": "turn_right"}

# the settings' defaults and cues live in store.py; these names stay for the checks and the section
TRAINER_DEFAULTS = store.DEFAULTS
CUES = store.CUES
migrate = store.migrate


def settings(game):
    return store.config(game)


# ---------------------------------------------------------------- binds

_FORWARDED = object()


def read_binds(game_dir, allowed=_FORWARDED):
    """{role: set of evdev codes or "wheel"}, plus Source key names with a role that won't reach
    the trainer: no code known, or not in `allowed` (a set of codes; None = every known key).
    By default `allowed` is what the Linux input service forwards (forwarded())."""
    cfg = Path(game_dir) / "cfg"
    alias_map = binds.aliases(cfg)
    roles = {r: set() for r in ROLES.values()}
    unseen = []
    if allowed is _FORWARDED:
        allowed = forwarded()
    for line in binds.cfg_text(cfg / "config.cfg").splitlines():
        bind = binds.parse_bind(binds.strip_comment(line))
        if not bind:
            continue
        key = bind[0].lower()
        for role in binds.resolve(bind[1].strip(), ROLES, alias_map):
            code = SOURCE_KEYS.get(key)
            if code is None or (allowed is not None and code not in allowed):
                unseen.append(f"{key} ({role.replace('_', ' ')})")
            else:
                roles[role].add(code)
    return roles, sorted(set(unseen))


class ToneSynth:
    """The constant tone's samples, for each platform's tone player (trainer_linux.Tone,
    trainer_win.Tone): next(mode) gives the next CHUNK of 16-bit mono samples at RATE, for the
    cue `mode` sounding (None: silence).

    Each pitch is pre-rendered as a loop of chunks that holds a whole number of cycles, so the
    chunks join without clicks; switching on, off or between pitches fades over one chunk."""
    RATE = 48000
    CHUNK = 240     # 5 ms

    def __init__(self, volume, pitches):
        self.volume = max(0.0, min(1.0, volume))
        self.pitches = pitches = {mode: max(40, int(hz)) for mode, hz in pitches.items()}
        amp = 32767 * self.volume
        self.silence = bytes(2 * self.CHUNK)
        # per mode: the loop of chunks (whole cycles overall) as float samples
        self.loops = {}
        for mode, hz in pitches.items():
            count = Fraction(hz * self.CHUNK, self.RATE).denominator
            samples = [amp * math.sin(2 * math.pi * hz * i / self.RATE)
                       for i in range(count * self.CHUNK)]
            self.loops[mode] = [samples[k * self.CHUNK:(k + 1) * self.CHUNK] for k in range(count)]
        # steady chunks ready to write; only fades are computed on the fly
        self.loop_bytes = {mode: [array.array("h", (int(x) for x in c)).tobytes() for c in loop]
                           for mode, loop in self.loops.items()}
        self.pos = {mode: 0 for mode in pitches}
        self.ramp = [i / self.CHUNK for i in range(self.CHUNK)]
        self.was = None

    def _chunk(self, mode, envelope=None):
        k = self.pos[mode] % len(self.loops[mode])
        self.pos[mode] += 1
        if envelope is None:
            return self.loop_bytes[mode][k]
        return array.array("h", (int(s * e) for s, e in zip(self.loops[mode][k], envelope))).tobytes()

    def next(self, mode):
        was, self.was = self.was, mode
        if mode == was:
            return self._chunk(mode) if mode else self.silence
        if mode is None:
            return self._chunk(was, [1 - r for r in self.ramp])
        if was is None:
            return self._chunk(mode, self.ramp)
        # other pitch: cross-fade so neither tone cuts off mid-wave
        a = self._chunk(was, [1 - r for r in self.ramp])
        b = self._chunk(mode, self.ramp)
        return array.array("h", (x + y for x, y in zip(array.array("h", a), array.array("h", b)))).tobytes()


class CueSounds:
    """Each cue's own sound: cues set to "tone" share one tone (a mode per cue, at the cue's pitch),
    the rest play their game sound through `play` on every cue (Trainer's on_wrong).

    `tone_class` is the platform's tone player (trainer_linux.Tone, trainer_win.Tone): built as
    tone_class(ToneSynth(volume, {cue: Hz})), with `mode` (the cue sounding, or None), start()
    and close(). The synth comes from here so the platform files never import trainer."""

    def __init__(self, cfg, play, tone_class):
        self.cfg, self.play = cfg, play
        self.pitches = {cue: cfg[f"{cue}_pitch"] for cue in CUES if cfg[f"{cue}_sound"] == "tone"}
        self.tone = tone_class(ToneSynth(cfg["tone_volume"], self.pitches)) if self.pitches else None
        if self.tone:
            self.tone.start()

    def state(self, reason):
        """Trainer's on_wrong_state: the cue now sounding, or None."""
        if self.tone:
            self.tone.mode = reason if reason in self.pitches else None

    def cue(self, reason):
        sound = self.cfg.get(f"{reason}_sound")
        if sound and sound != "tone":
            self.play(sound)

    def close(self):
        if self.tone:
            self.tone.close()


# ---------------------------------------------------------------- the trainer

class Trainer:
    def __init__(self, cfg, roles, tickrate, on_offset, on_wrong, on_wrong_state=None):
        self.cfg = cfg
        self.on_wrong_state = on_wrong_state
        self.wrong_active = None   # None, "wrong", "none" or "overlap"
        self.roles = roles
        self.tickrate = tickrate
        self.on_offset = on_offset
        self.on_wrong = on_wrong
        self.held = {}             # code -> press time
        self.last_wheel = 0.0
        self.strafe_dir = 0        # -1 left, 1 right, 0 none
        self.strafe_changes = []   # (time, new strafe_dir)
        self.turn_dir = 0
        self.mouse_dir = 0
        self.run_sum = 0
        self.run_start = 0.0
        self.last_motion = 0.0
        self.pending = None        # (turn time, direction) waiting for its key switch
        self.wrong_since = None
        self.overlap_since = None
        self.last_cue = None

    def has(self, role, code):
        return code in self.roles[role]

    # False while another window has focus or the game is in a menu (no map
    # loaded, or Momentum's pause menu over one): keys and mouse are still tracked, so nothing sticks when you come
    # back, but nothing counts or sounds
    focused = True
    # Momentum's timer runs on the player's own run (GameEvents.timer)
    timer = False

    def jumping(self, now):
        return (any(c in self.roles["jump"] for c in self.held)
                or ("wheel" in self.roles["jump"] and now - self.last_wheel < 0.1))

    def listening(self, now):
        """Whether turns and keys count now: focused, and a jump key held (when_jump) or the timer
        running (when_timer)."""
        if not self.focused:
            return False
        return ((self.cfg["when_timer"] and self.timer)
                or (self.cfg["when_jump"] and self.jumping(now)))

    def _strafe(self):
        """Direction of the most recently pressed strafe key still held."""
        best, when = 0, -1.0
        for code, t in self.held.items():
            for role, d in (("strafe_left", -1), ("strafe_right", 1)):
                if code in self.roles[role] and t > when:
                    best, when = d, t
        return best

    def _overlapping(self):
        """Both strafe keys held at once."""
        return (any(c in self.roles["strafe_left"] for c in self.held)
                and any(c in self.roles["strafe_right"] for c in self.held))

    def _button_turn(self):
        best, when = 0, -1.0
        for code, t in self.held.items():
            for role, d in (("turn_left", -1), ("turn_right", 1)):
                if code in self.roles[role] and t > when:
                    best, when = d, t
        return best

    def _set_turn(self, direction, t):
        if direction == self.turn_dir or direction == 0:
            return
        self.turn_dir = direction
        if not self.listening(t):
            self.pending = None
            return
        window = self.cfg["window"]
        if self.strafe_dir == direction:
            # key already switched: early (or same tick)
            for when, d in reversed(self.strafe_changes):
                if d == direction:
                    if t - when <= window:
                        self._offset(when - t)
                    break
            self.pending = None
        else:
            self.pending = (t, direction)

    def _offset(self, seconds):
        self.on_offset(round(seconds * self.tickrate))

    def feed(self, t, etype, code, value):
        if etype == EV_KEY:
            if value:
                self.held[code] = t
            else:
                self.held.pop(code, None)
            # the overlap counts from the key press that made it
            if not self._overlapping():
                self.overlap_since = None
            elif self.overlap_since is None:
                self.overlap_since = t
            new = self._strafe()
            if new != self.strafe_dir:
                self.strafe_dir = new
                self.strafe_changes = self.strafe_changes[-15:] + [(t, new)]
                if self.pending and new == self.pending[1]:
                    if t - self.pending[0] <= self.cfg["window"]:
                        self._offset(t - self.pending[0])
                    self.pending = None
            button = self._button_turn()
            if button:
                self._set_turn(button, t)
            elif self.mouse_dir:
                self._set_turn(self.mouse_dir, t)
        elif etype == EV_REL and code == REL_WHEEL:
            self.last_wheel = t
        elif etype == EV_REL and code == REL_X and value:
            sign = 1 if value > 0 else -1
            self.last_motion = t
            if sign == self.mouse_dir:
                self.run_sum = 0
                return
            # a turn the other way counts from its first count, once it is more
            # than jitter: mouse_threshold counts without a long pause
            if self.run_sum == 0 or t - self.last_run_t > 0.05:
                self.run_sum, self.run_start = 0, t
            self.last_run_t = t
            self.run_sum += abs(value)
            if self.run_sum >= self.cfg["mouse_threshold"] or self.mouse_dir == 0:
                self.mouse_dir = sign
                self.run_sum = 0
                if not self._button_turn():
                    self._set_turn(sign, self.run_start)

    last_run_t = 0.0

    def _wrong_state(self, reason):
        if reason != self.wrong_active:
            self.wrong_active = reason
            if self.on_wrong_state:
                self.on_wrong_state(reason)

    def check(self, now):
        """Wrong-key and overlap cues; called often between events."""
        if self.pending and now - self.pending[0] > self.cfg["window"]:
            self.pending = None
        # an overlap outranks a wrong-key turn: it is the cause of it
        if (self.cfg["cue_overlap"] and self.overlap_since is not None and self.listening(now)
                and now - self.overlap_since >= self.cfg["overlap_ticks"] / self.tickrate):
            self._cue("overlap", now)
            self.wrong_since = None  # a wrong-key turn waits its ticks again after the overlap
            return
        turning = self._button_turn() or (self.mouse_dir if now - self.last_motion < 0.03 else 0)
        reason = None
        if turning and self.listening(now) and self.strafe_dir != turning:
            reason = "none" if self.strafe_dir == 0 else "wrong"
            if not self.cfg["cue_no_key" if reason == "none" else "cue_wrong_key"]:
                reason = None
        if reason is None:
            self.wrong_since, self.last_cue = None, None
            self._wrong_state(None)
            return
        if self.wrong_since is None:
            self.wrong_since = now
        if now - self.wrong_since < self.cfg[f"{reason}_ticks"] / self.tickrate:
            if self.wrong_active == "overlap":  # the overlap ended; the turn isn't wrong for long enough yet
                self._wrong_state(None)
            return
        self._cue(reason, now)

    def _cue(self, reason, now):
        self._wrong_state(reason)
        # first cue once it has lasted <reason>_ticks, then every `repeat`
        # seconds for as long as it stays wrong
        repeat = self.cfg["repeat"]
        if self.last_cue is None or (repeat > 0 and now - self.last_cue >= repeat):
            self.last_cue = now
            self.on_wrong()


# ---------------------------------------------------------------- running

# the settings CueSounds builds its tone from: a change in one needs a new tone
SOUND_KEYS = ("tone_volume", *(f"{cue}_{part}" for cue in CUES for part in ("sound", "pitch")))


class SettingsWatch:
    """Notices the game's settings being saved while the trainer runs (the hub's Apply rewrites
    settings.json): changed() gives the new settings once, when they differ from `cfg`."""
    INTERVAL = 0.5  # seconds between looks at the file

    def __init__(self, game, cfg):
        self.game, self.cfg = game, cfg
        self.stamp = self._stamp()
        self.next = 0.0

    @staticmethod
    def _stamp():
        try:
            stat = store.SETTINGS.stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def changed(self):
        now = time.monotonic()
        if now < self.next:
            return None
        self.next = now + self.INTERVAL
        stamp = self._stamp()
        if stamp == self.stamp:
            return None
        self.stamp = stamp
        new = settings(self.game)
        return new if new != self.cfg else None


def map_tickrate(cfg, game, name):
    """The tickrate for map `name`, or None when the name isn't known (CS:S's "Connected to" line)."""
    return maps.prefix_value(name, cfg["map_tickrates"], cfg["tickrate"].get(game, 66))


class GameEvents:
    """What the movekit session's events (map loads, Momentum's pause menu and run timer, the offsets
    toggle's echo) mean for the trainer."""

    def __init__(self, cfg, game, tickrate, in_map, showing):
        self.cfg, self.game = cfg, game
        self.tickrate = tickrate
        self.map = None  # the loaded map's name, when the log gave one
        self.in_map = in_map
        self.showing = showing
        self.menu = False  # Momentum's pause menu is open (the map stays loaded under it)
        self.timer = False  # Momentum's timer runs on the player's own run

    @property
    def playing(self):
        """In a map and not in its pause menu: the only time the keys and the mouse are play."""
        return self.in_map and not self.menu

    def retune(self):
        """The tickrate again, after the settings changed (cfg is the same dict, updated)."""
        self.tickrate = ((self.map and map_tickrate(self.cfg, self.game, self.map))
                         or self.cfg["tickrate"].get(self.game, 66))

    def handle(self, event):
        kind, data = event["type"], event["data"]
        if kind == "token" and data.get("name") == gamecfg.OFFSETS_TOKEN:
            self.showing = not self.showing
            print(f"trainer: offset {'shown' if self.showing else 'hidden'}", flush=True)
        elif kind in ("menu_shown", "menu_hidden"):
            menu = kind == "menu_shown"
            if menu != self.menu:
                print(f"trainer: pause menu {'open' if menu else 'closed'}", flush=True)
            self.menu = menu
        elif kind in ("timer_started", "timer_stopped"):
            timer = kind == "timer_started"
            if timer != self.timer:
                print(f"trainer: timer {'started' if timer else 'stopped'}", flush=True)
            self.timer = timer
        elif kind == "map_loaded":
            if not self.in_map:
                print("trainer: in a map", flush=True)
            self.in_map = True
            self.menu = False  # a lost menu_hidden never keeps the trainer quiet past a map load
            self.timer = False  # nor a lost timer_stopped listening
            rate = map_tickrate(self.cfg, self.game, data.get("name"))
            if rate:
                self.map = data["name"]
                self.tickrate = rate
                print(f"trainer: map {data['name']} -> {rate} tick", flush=True)
        elif kind == "map_left":
            if self.in_map:
                print("trainer: in the menu", flush=True)
            self.in_map = False
            self.menu = False
            self.timer = False


def run(game, platform, stop=None):
    """The trainer for `game` until the input ends or `stop` (a threading.Event) is set; returns
    the exit code. `platform` is everything that differs per OS (trainer_linux.Linux):
      FORWARDED_ONLY  whether only the input service's forwarded keys arrive (read_binds)
      UNSEEN, GONE    log text: keys that won't arrive, the input ending
      Tone            CueSounds' tone_class
      clock()         the clock the input's event times use
      overlay(cfg)    where the offset is drawn (show(text, row, x, y), hide()), or None
      open_input()    read(timeout) -> [(time, EV_KEY/EV_REL, evdev code, value)], or None
                      once the input is gone; close(). None after printing why there's none.
      focus(game, game_dir)  an object whose `focused` says the game's window has focus
      play(game_dir, sound, game)  a game sound"""
    cfg = settings(game)
    game_dir = games.find(game)
    if game_dir is None:
        return 0
    if not cfg["enabled"]:
        # off at the game's start: wait for it to be switched on, holding nothing meanwhile
        print("trainer: switched off, waiting", flush=True)
        while not cfg["enabled"]:
            if stop is None:
                time.sleep(SettingsWatch.INTERVAL)
            elif stop.wait(SettingsWatch.INTERVAL):
                return 0
            cfg = settings(game)
        print("trainer: switched on", flush=True)
    roles, unseen = read_binds(game_dir) if platform.FORWARDED_ONLY else read_binds(game_dir, None)
    if unseen:
        print(f"trainer: {platform.UNSEEN}: {', '.join(unseen)}", flush=True)
    overlay = platform.overlay(cfg)
    source = platform.open_input()
    if source is None:
        return 1

    shown_until = 0.0
    log_path = game_dir / "yaw.log"
    # without a console log there is no way to tell, so everything counts until it shows up
    game_events = GameEvents(cfg, game, cfg["tickrate"].get(game, 66), not log_path.exists(), cfg["show_offset"])

    def offset(ticks):
        nonlocal shown_until
        if overlay is None or not game_events.showing:
            return
        target = cfg["target"]
        row = 0 if ticks < target else 1 if ticks == target else 2
        overlay.show(f"{ticks:+d}" if ticks else "0", row, cfg["x"], cfg["y"])
        shown_until = time.monotonic() + cfg["hide_after"]

    def play(sound):
        platform.play(game_dir, sound, game)

    sounds = CueSounds(cfg, play, platform.Tone)
    watch = SettingsWatch(game, cfg)
    trainer = Trainer(cfg, roles, game_events.tickrate, offset,
                      lambda: sounds.cue(trainer.wrong_active), sounds.state)
    focus = platform.focus(game, game_dir)
    # map loads and the offsets toggle come from the movekit session (after the input
    # check above, so a trainer that gives up never holds the session's port)
    joined = session.join(log_path)
    print(f"trainer: session events ({joined.mode})", flush=True)
    try:
        while stop is None or not stop.is_set():
            events = source.read(0.002)
            if events is None:
                print(f"trainer: {platform.GONE}", flush=True)
                return 1
            for event in events:
                trainer.feed(*event)
            while not joined.events.empty():
                was_showing = game_events.showing
                game_events.handle(joined.events.get())
                trainer.tickrate = game_events.tickrate
                if overlay and was_showing and not game_events.showing:
                    overlay.hide()
                    shown_until = 0.0
            new = watch.changed()
            if new is not None:
                # cfg is the one dict the trainer, the game events and the sounds read: updated in place
                was = dict(cfg)
                cfg.clear()
                cfg.update(new)
                print(f"trainer: settings reloaded{'' if cfg['enabled'] else ' (switched off)'}", flush=True)
                if any(was.get(key) != cfg.get(key) for key in SOUND_KEYS):
                    sounds.close()
                    sounds = CueSounds(cfg, play, platform.Tone)
                    trainer.on_wrong_state = sounds.state
                    trainer.wrong_active = None  # the new tone hears a cue still sounding at the next check
                if was.get("show_offset") != cfg["show_offset"]:
                    game_events.showing = cfg["show_offset"]
                game_events.retune()
                trainer.tickrate = game_events.tickrate
                if overlay and not (cfg["enabled"] and game_events.showing):
                    overlay.hide()
                    shown_until = 0.0
            trainer.focused = cfg["enabled"] and focus.focused and game_events.playing
            trainer.timer = game_events.timer
            trainer.check(platform.clock())
            if shown_until and time.monotonic() > shown_until:
                overlay.hide()
                shown_until = 0.0
        return 0
    finally:
        sounds.close()
        source.close()
        joined.close()


def _sibling(name):
    """trainer_linux or trainer_win (movekit.hub.local_import)."""
    return local_import(__file__, name)


def platform():
    """This OS's platform for run(): trainer_win.Windows or trainer_linux.Linux, loaded only here
    so neither OS loads the other's code."""
    if sys.platform == "win32":
        return _sibling("trainer_win").Windows()
    return _sibling("trainer_linux").Linux()


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in store.GAMES:
        print(__doc__)
        return 2
    game = sys.argv[1]
    if "--enabled" in sys.argv:  # launch-hook.sh asks before it sets the overlay up
        return 0 if settings(game)["enabled"] else 1
    if "--binds" in sys.argv:
        game_dir = games.find(game)
        roles, unseen = read_binds(game_dir)
        for role, codes in roles.items():
            print(f"{role:13} {sorted(codes, key=str)}")
        if unseen:
            print("not forwarded by the input service:", ", ".join(unseen))
        return 0
    try:
        return run(game, platform())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
