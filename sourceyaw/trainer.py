#!/usr/bin/env python3
"""Strafe trainer: runs beside the game (started by launch-hook.sh through movekit-run on Linux).

Reads the strafe, turn and jump keys plus mouse movement, and while a jump key is held:
  - plays a sound when you turn one way for a few ticks without holding that
    way's strafe key (no key, or the other one), and one when both strafe
    keys are held at once,
  - works out each strafe's offset: the ticks between turning the other way
    and switching strafe keys. Negative means the key came early, positive
    late, 0 on the same tick. The number is drawn over the game where the
    platform can (Linux: the Source Yaw overlay layer).

This file is platform-neutral (it imports on Windows, with no Pillow): the cue logic, binds,
settings and the main loop. Where keys come from, how sounds play, focus and the overlay are
the platform's (trainer_linux.Linux; Windows is Phase 12 in PLAN.md), handed to run().

Keys come from the game's own binds (config.cfg plus aliases from every cfg),
so rebinding in the game just works. On Linux the input service must forward
that key too (see /etc/sourceyaw-inputd.conf).

  trainer.py GAME            run until the game exits (launch-hook.sh does this)
  trainer.py GAME --binds    print which keys do what, then exit
"""

import array  # noqa: I001, RUF100 - movekit must come after yawcore (see below)
import math
import sys
import time
from fractions import Fraction
from pathlib import Path

import yawcore

from movekit import binds, session  # after yawcore, which puts movekit on the path

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

TRAINER_DEFAULTS = {
    "enabled": False,
    "tone_volume": 0.3,            # 0-1, for the constant tone
    "repeat": 0.2,                 # game sound: seconds between plays while wrong; 0 = once
    # the cues (CUES): on/off, sound ("tone" or a game sound), the tone's Hz, and the
    # ticks the mistake must last before it sounds
    "cue_wrong_key": True, "wrong_sound": "tone", "wrong_pitch": 220, "wrong_ticks": 3,
    "cue_no_key": True, "none_sound": "tone", "none_pitch": 147, "none_ticks": 3,
    "cue_overlap": True, "overlap_sound": "tone", "overlap_pitch": 110, "overlap_ticks": 1,
    "target": -1,                  # the offset counted as best (shown green)
    "show_offset": True,           # at launch; offset_key flips it in game
    "offset_key": "",              # key bound in yaws.cfg to show or hide the offset
    "x": 0.5, "y": 0.56,           # number's centre, as a fraction of the screen
    "size": 36,                    # font size in pixels
    "colors": {"early": "#ff5a5a", "perfect": "#5aff78", "late": "#ffc83c"},
    "hide_after": 2.0,             # seconds the last offset stays up
    "window": 0.25,                # seconds a key switch may be from a turn to count
    "mouse_threshold": 4,          # mouse counts the other way that make a turn
    # CS:S servers pick their own tickrate; Momentum's follows the map's game mode
    "tickrate": {"css": 66, "momentum": 100},
    "map_tickrates": {"surf_": 66, "bhop_": 100},
}


# cue -> its on/off setting: "wrong" turning with the other strafe key held, "none" turning with
# no strafe key held, "overlap" both strafe keys held. Its other settings are <cue>_sound,
# <cue>_pitch and <cue>_ticks.
CUES = {"wrong": "cue_wrong_key", "none": "cue_no_key", "overlap": "cue_overlap"}


def migrate(saved):
    """Trainer settings saved before each cue had its own sound (1.9.0 and older: one `sound` and
    `tone_pitch` for both wrong-key cues, the no-key tone at 2/3 of that pitch, one `wrong_ticks`)
    in today's keys. The old keys stay, so a rolled-back version still reads them."""
    saved = dict(saved or {})
    if "wrong_sound" not in saved and "sound" in saved:
        if not saved["sound"]:  # "" played nothing
            saved["cue_wrong_key"] = saved["cue_no_key"] = False
        saved["wrong_sound"] = saved["none_sound"] = saved["sound"] or "tone"
    if "wrong_pitch" not in saved and "tone_pitch" in saved:
        saved["wrong_pitch"] = int(saved["tone_pitch"])
        saved["none_pitch"] = max(40, round(int(saved["tone_pitch"]) * 2 / 3))
    if "none_ticks" not in saved and "wrong_ticks" in saved:
        saved["none_ticks"] = saved["wrong_ticks"]
    return saved


def settings(game):
    data = migrate(yawcore.load_settings(game).get("trainer"))
    merged = {**TRAINER_DEFAULTS, **data}
    merged["colors"] = {**TRAINER_DEFAULTS["colors"], **data.get("colors", {})}
    return merged


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

    # False while another window has focus or the game is in its menu (no map
    # loaded): keys and mouse are still tracked, so nothing sticks when you come
    # back, but nothing counts or sounds
    focused = True

    def jumping(self, now):
        if not self.focused:
            return False
        return (any(c in self.roles["jump"] for c in self.held)
                or ("wheel" in self.roles["jump"] and now - self.last_wheel < 0.1))

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
        if not self.jumping(t):
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
        if (self.cfg["cue_overlap"] and self.overlap_since is not None and self.jumping(now)
                and now - self.overlap_since >= self.cfg["overlap_ticks"] / self.tickrate):
            self._cue("overlap", now)
            self.wrong_since = None  # a wrong-key turn waits its ticks again after the overlap
            return
        turning = self._button_turn() or (self.mouse_dir if now - self.last_motion < 0.03 else 0)
        reason = None
        if turning and self.jumping(now) and self.strafe_dir != turning:
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

def map_tickrate(cfg, game, name):
    """The tickrate for map `name`, or None when the name isn't known (CS:S's "Connected to" line)."""
    return yawcore.prefix_value(name, cfg["map_tickrates"], cfg["tickrate"].get(game, 66))


class GameEvents:
    """What the movekit session's events (map loads, the offsets toggle's echo) mean for the trainer."""

    def __init__(self, cfg, game, tickrate, in_map, showing):
        self.cfg, self.game = cfg, game
        self.tickrate = tickrate
        self.in_map = in_map
        self.showing = showing

    def handle(self, event):
        kind, data = event["type"], event["data"]
        if kind == "token" and data.get("name") == yawcore.OFFSETS_TOKEN:
            self.showing = not self.showing
            print(f"trainer: offset {'shown' if self.showing else 'hidden'}", flush=True)
        elif kind == "map_loaded":
            if not self.in_map:
                print("trainer: in a map", flush=True)
            self.in_map = True
            rate = map_tickrate(self.cfg, self.game, data.get("name"))
            if rate:
                self.tickrate = rate
                print(f"trainer: map {data['name']} -> {rate} tick", flush=True)
        elif kind == "map_left":
            if self.in_map:
                print("trainer: in the menu", flush=True)
            self.in_map = False


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
    game_dir = yawcore.find_game(game)
    if not cfg["enabled"] or game_dir is None:
        return 0
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

    sounds = CueSounds(cfg, lambda sound: platform.play(game_dir, sound, game), platform.Tone)
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
            trainer.focused = focus.focused and game_events.in_map
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
    """trainer_linux or trainer_win, loaded from this file's folder under this module's naming:
    the hub loads trainer by path under a prefixed name (settings_api), with sourceyaw/ not on
    sys.path. Their `import yawcore` gets this file's yawcore."""
    import importlib.util
    prefix = __name__.rpartition(".")[0]
    full = f"{prefix}.{name}" if prefix else name
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, Path(__file__).with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    before = sys.modules.get("yawcore")
    sys.modules["yawcore"] = yawcore
    sys.modules[full] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules[full]
        raise
    finally:
        if before is None:
            sys.modules.pop("yawcore", None)
        else:
            sys.modules["yawcore"] = before
    return mod


def platform():
    """This OS's platform for run(): trainer_win.Windows or trainer_linux.Linux, loaded only here
    so neither OS loads the other's code."""
    if sys.platform == "win32":
        return _sibling("trainer_win").Windows()
    return _sibling("trainer_linux").Linux()


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in yawcore.GAMES:
        print(__doc__)
        return 2
    game = sys.argv[1]
    if "--binds" in sys.argv:
        game_dir = yawcore.find_game(game)
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
