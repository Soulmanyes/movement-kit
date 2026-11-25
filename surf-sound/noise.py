"""Surf Sound's sounds: shaped noise or a recorded loop, not a tone. NoiseSynth makes the samples for movekit.tone's
players (LinuxTone through pw-cat, WindowsTone through waveOut), which only call next(mode) and read
RATE and CHUNK, so it stands in for ToneSynth.

Up to 1.6.0 most sounds were a loop of LOOP_S seconds of filtered random noise (Wind, Rumble, Hiss, Grind);
since 1.7.0 every built-in sound is a recording (owner, 2026-11-25), its seam cross-faded so it repeats
without a click or a dip. render() still takes a noise function with an optional gain shape, for a
sound made that way again. Every sound has two
variants: "ramp" (a surface under you) and "ceiling" (a headsurf). Up to 1.5.0 the ceiling one was brighter, so the two
could be told apart by ear; since 1.6.0 (owner, 2026-11-25) both are the same, BRIGHT 1.0. Switching fades the gain over FADE_IN_S / FADE_OUT_S, so it never clicks.

Stone (sounds/stone-dragging.wav: 16-bit mono at RATE, LOOP_S + SEAM_S long) goes through render's
seam as noise did. Whoosh (sounds/whoosh.wav, 1.3 s), Rumble (sounds/rumble.wav, 2.35 s; both the
owner's hub recordings, 1.7.0) and Long squeak (sounds/long-squeak.wav, 2.5 s, made by the owner, 1.6.0)
loop at their own length, as a custom loop does (render_file): LOOP_FILES.

Hits are one-shots on top (owner, 2026-11-24), recordings in sounds/: bonk-wall.wav for a wall (three
strengths, by the speed lost) and a light ceiling hit, bonk-goofy.wav for a hard head hit. A jump's
takeoff plays jump.wav (1.4.0), a cartoon boing (0.55 s, the owner's pick, 2026-11-25), quieter than the
hits as bhops jump every half second or so. hit(name)
queues one from any thread; next() mixes it in, through a limiter (LIMIT) so a hit on a loud loop is
never cut flat (crackle).

Custom sounds (custom.py converts them in the hub) replace any of these: a ramp or ceiling loop
(render_file: any length, so each loop keeps its own position) or a hit's recording. One that won't load
plays the built-in sound instead.

player_class() gives this OS's player, with less sound queued on Linux than the core's tone.
play(volume, sound, kind, seconds) plays a short burst and returns at once (the hub's ▶); play_hit
plays a hit.

Stdlib only, so the Windows core exe can run it.
"""
import array
import collections
import functools
import itertools
import math
import random
import sys
import threading
import wave
from pathlib import Path

from movekit import tone

SOUNDS = {}  # filled below the sounds

RATE = 48000
CHUNK = 240  # 5 ms, as ToneSynth
LOOP_S = 4.0
SEAM_S = 0.3
LOOP_MIN_S = 1.0  # a custom loop's shortest (custom.py)
FADE_IN_S = 0.005  # one chunk: as fast as it goes without a click (owner, 2026-11-24: it felt late)
FADE_OUT_S = 0.12
RMS = 0.22  # of full scale at volume 1; noise peaks about 3x its RMS
PEAK = 0.95  # a loop's peak at volume 1, at most: a recording can peak higher than noise
SOUND_DIR = Path(__file__).resolve().parent / "sounds"


def _lowpass(xs, hz):
    """One-pole low-pass."""
    a = 1 - math.exp(-2 * math.pi * hz / RATE)
    y, out = 0.0, []
    for x in xs:
        y += a * (x - y)
        out.append(y)
    return out


def _highpass(xs, hz):
    lo = _lowpass(xs, hz)
    return [x - y for x, y in zip(xs, lo)]


@functools.cache
def _recording(name):
    """A recorded sound in SOUND_DIR as floats -1..1 (16-bit mono at RATE), cached."""
    return _read(str(SOUND_DIR / name))


def _read(path):
    """A 16-bit mono WAV at RATE as floats -1..1. Not cached: a custom sound is read again on each
    settings change, so every pick of a game session doesn't stay in memory."""
    with wave.open(path) as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, RATE):
            raise ValueError(f"{Path(path).name}: needs 16-bit mono at {RATE} Hz")
        data = array.array("h", w.readframes(w.getnframes()))
    if sys.byteorder == "big":
        data.byteswap()
    return [x / 32768 for x in data]


def _stone(n, rng, bright):
    """Stone dragged over stone: a recording (repeated if shorter than n), high-passed on a ceiling."""
    rec = _recording("stone-dragging.wav")
    xs = (rec * (n // len(rec) + 1))[:n]
    return _highpass(xs, 25 if bright <= 1 else 600)


# name: (label, noise(n, rng, bright), gain(phase 0-1 over the loop, bright) or None); the first is the default
SOUNDS.update({
    "whoosh": ("Whoosh", None, None),  # whole recordings, LOOP_FILES
    "rumble": ("Rumble", None, None),
    "stone": ("Stone", _stone, None),
    "squeak": ("Long squeak", None, None),  # a whole recording, LOOP_FILES
})
LOOP_FILES = {"whoosh": "whoosh.wav", "rumble": "rumble.wav", "squeak": "long-squeak.wav"}  # built-in sounds that loop at their recording's own length
BRIGHT = {"ramp": 1.0, "ceiling": 1.0}  # filter scale per surface; a headsurf no longer plays brighter (1.6.0)

HIT_PEAK = 0.8  # a hit's peak at volume 1 and gain 1
# the mix's limiter: a hit on a loud loop (volume over about 57%, or two hits at once) would sum past full
# scale and be cut flat, heard as crackle; instead a chunk that would pass LIMIT of full scale is turned
# down as a whole, and the gain comes back over LIMIT_RELEASE_S
LIMIT = 0.95
LIMIT_RELEASE_S = 0.1
# a hit's name: (its recording in SOUND_DIR, its gain). Walls get louder the more speed they took; a
# light ceiling hit plays the wall's sound (owner, 2026-11-24: grazing the ceiling on a jump is a miss,
# hitting it hard to drop faster is the goofy bonk)
HIT_SOUNDS = {
    "wall1": ("bonk-wall.wav", 0.45), "wall2": ("bonk-wall.wav", 0.7), "wall3": ("bonk-wall.wav", 1.0),
    "graze": ("bonk-wall.wav", 0.7), "bonk": ("bonk-goofy.wav", 1.0), "jump": ("jump.wav", 0.5),
}


def _hit_file(name, custom):
    """The file a hit plays: its custom sound (custom: {slot: path}), else the built-in one. A light
    head hit with no sound of its own follows the wall's."""
    slot = _slot(name)
    if custom.get(slot):
        return str(custom[slot])
    if name == "graze" and custom.get("wall"):
        return str(custom["wall"])
    return str(SOUND_DIR / HIT_SOUNDS[name][0])


def _slot(name):
    """The settings slot of a hit name (wall1-3 are "wall")."""
    return "wall" if name.startswith("wall") else name


def render_hits(scale=1.0, custom=None, scales=None):
    """Each hit's samples ready to mix, by hit name: peaking at HIT_PEAK x its gain x scale, or x
    scales[its slot] when given. A custom file that can't be read falls back to the built-in sound, with a
    log line."""
    custom = custom or {}
    scales = scales or {}
    out, peaks, files = {}, {}, {}
    for name, (builtin, gain) in HIT_SOUNDS.items():
        path = _hit_file(name, custom)
        if name == "graze" and custom.get("graze"):
            gain = 1.0  # its own sound: as picked, not as the wall's light version
        try:
            xs = _recording(Path(path).name) if Path(path).parent == SOUND_DIR else files.get(path) or _read(path)
        except (OSError, EOFError, ValueError, wave.Error) as e:
            print(f"surf-sound: {name} plays the built-in sound, {Path(path).name} didn't load: {e}", flush=True)
            path = str(SOUND_DIR / builtin)
            xs = _recording(builtin)
        files[path] = xs
        if path not in peaks:
            peaks[path] = max(map(abs, xs)) or 1
        k = HIT_PEAK * gain * scales.get(_slot(name), scale) / peaks[path]
        out[name] = [x * k for x in xs]
    return out


HITS = tuple(HIT_SOUNDS)


def render(sound, kind, seed=1):
    """One seamless loop of `sound` for `kind` ("ramp" or "ceiling"), as floats near RMS.

    The noise past the loop's end cross-fades into its start at equal power (noise segments don't
    correlate, so a linear fade would dip about 3 dB at the join). The sound's gain shape is applied
    after that, over the closed loop, so it repeats exactly."""
    if sound in LOOP_FILES:
        return render_file(SOUND_DIR / LOOP_FILES[sound])
    n, seam = int(RATE * LOOP_S), int(RATE * SEAM_S)
    n -= n % CHUNK
    _, make, gain = SOUNDS[sound]
    bright = BRIGHT[kind]
    xs = make(n + seam, random.Random(seed), bright)
    head = [xs[i] * math.sin(math.pi / 2 * i / seam) + xs[n + i] * math.cos(math.pi / 2 * i / seam)
            for i in range(seam)]
    xs = head + xs[seam:n]
    if gain:
        xs = [x * gain(i / n, bright) for i, x in enumerate(xs)]
        # start the loop at its loudest chunk: a sound starting from silence plays from there (NoiseSynth),
        # so a brief touch never lands in a swell's quiet part
        loud = max(range(n // CHUNK), key=lambda k: gain((k * CHUNK + CHUNK / 2) / n, bright))
        xs = xs[loud * CHUNK:] + xs[:loud * CHUNK]
    return _level(xs)


def _level(xs):
    """A loop scaled to RMS, its peak at most PEAK."""
    rms = math.sqrt(sum(x * x for x in xs) / len(xs)) or 1
    scale = min(RMS / rms, PEAK / (max(map(abs, xs)) or 1))
    return [x * scale for x in xs]


def render_file(path):
    """A custom loop (custom.py's WAV, LOOP_MIN_S or longer) as floats near RMS: its last SEAM_S
    cross-faded into its start at equal power, cut to whole chunks, played as it is on a ceiling too."""
    xs = _read(str(path))
    seam = int(RATE * SEAM_S)
    n = len(xs) - seam
    n -= n % CHUNK
    if n < RATE * LOOP_MIN_S - seam:
        raise ValueError(f"{Path(path).name}: a loop needs at least {LOOP_MIN_S:g} s")
    head = [xs[i] * math.sin(math.pi / 2 * i / seam) + xs[n + i] * math.cos(math.pi / 2 * i / seam)
            for i in range(seam)]
    return _level(head + xs[seam:n])


class NoiseSynth:
    """The sound's samples: next(mode) gives the next CHUNK of 16-bit mono samples at RATE, for mode
    "ramp", "ceiling" or None (silence). sounds: {mode: sound name}; custom: {slot: path of a custom
    sound (custom.py)}, slots "ramp", "ceiling", "wall", "graze", "bonk" and "jump", each replacing that built-in
    sound. A custom file that doesn't load falls back to the built-in sound (a log line), so a bad file
    never stops the sound. levels: {slot: factor} on volume per sound (settings "levels"), the product
    capped at 1."""
    RATE = RATE
    CHUNK = CHUNK

    def __init__(self, volume, sounds, custom=None, levels=None, variants=None, random_start=False):
        """variants: {mode: the variant ("ramp" or "ceiling") its built-in sound renders as}; each mode's
        own by default. A headsurf that sounds like a ramp (settings "split_ceiling" off) is
        {"ceiling": "ramp"}. random_start (settings "random_start", 1.8.0): a loop starting from silence
        starts at a random point of it instead of its start, so rides don't all open the same way."""
        self.random_start = random_start
        custom = custom or {}
        levels = levels or {}
        variants = variants or {}
        vol = max(0.0, min(1.0, volume)) * 32767
        scales = {slot: min(vol * max(0.0, level), 32767.0) for slot, level in levels.items()}
        self.loops = {mode: [x * scales.get(mode, vol)
                             for x in self._loop(mode, name, custom.get(mode), variants.get(mode, mode))]
                      for mode, name in sounds.items()}
        # the steady sound ready to write; only fades are computed on the fly
        self.loop_bytes = {mode: array.array("h", (max(-32768, min(32767, int(x))) for x in loop)).tobytes()
                           for mode, loop in self.loops.items()}
        # each loop has its own length (a custom one) and position
        self.length = {mode: len(loop) for mode, loop in self.loops.items()}
        self.pos = dict.fromkeys(self.loops, 0)
        self.gain = dict.fromkeys(self.loops, 0.0)
        self.up = CHUNK / (RATE * FADE_IN_S)
        self.down = CHUNK / (RATE * FADE_OUT_S)
        self.silence = bytes(2 * CHUNK)
        self.vol = vol
        self.hit_sounds = render_hits(vol, custom, scales)  # scaled once here: the audio thread only adds them
        self.queued = collections.deque()  # hit names from hit(), any thread
        self.playing = []  # [samples, position] of the hits sounding
        self.limit_gain = 1.0  # the limiter's gain (LIMIT)
        self.release = CHUNK / (RATE * LIMIT_RELEASE_S)

    @staticmethod
    def _loop(mode, name, path, variant):
        if path:
            try:
                return render_file(path)
            except (OSError, EOFError, ValueError, wave.Error) as e:
                print(f"surf-sound: the {mode} plays {name}, {Path(path).name} didn't load: {e}", flush=True)
        return render(name, variant)

    def hit(self, name):
        """Play a hit (HITS) on top of the sound, from the next chunk on."""
        if name not in HITS:
            raise ValueError(f"no hit {name!r}")
        self.queued.append(name)

    def _hits(self):
        """This chunk of the sounding hits, as floats, or None."""
        while self.queued:
            self.playing.append([self.hit_sounds[self.queued.popleft()], 0])
        if not self.playing:
            return None
        out = [0.0] * CHUNK
        for item in self.playing:
            xs, at = item
            for i, x in enumerate(xs[at:at + CHUNK]):
                out[i] += x
            item[1] = at + CHUNK
        self.playing = [p for p in self.playing if p[1] < len(p[0])]
        return out

    def next(self, mode):
        hits = self._hits()
        loop = self._loops(mode)
        if hits is None and self.limit_gain == 1.0:
            return loop
        mixed = array.array("h", loop)
        if hits is not None:
            mixed = [a + b for a, b in zip(mixed, hits)]
        peak = max(map(abs, mixed)) or 1
        g0 = self.limit_gain
        g1 = min(1.0, g0 + self.release, LIMIT * 32767 / peak)
        self.limit_gain = g1
        if g1 < g0:  # down at once for the whole chunk: a ramp would let its first samples clip
            gains = itertools.repeat(g1)
        else:  # back up gradually; every gain is at most g1, so still under LIMIT
            step = (g1 - g0) / CHUNK
            gains = (g0 + step * (i + 1) for i in range(CHUNK))
        return array.array("h", (max(-32768, min(32767, int(x * g))) for x, g in zip(mixed, gains))).tobytes()

    def _loops(self, mode):
        if mode in self.loops and not any(self.gain.values()):
            # from silence: the loop's loud start (render), or a random chunk of it (random_start);
            # a loop's length is whole chunks, so a chunk never runs past its end
            self.pos[mode] = random.randrange(self.length[mode] // CHUNK) * CHUNK if self.random_start else 0
        starts = dict(self.pos)
        for m, at in starts.items():
            self.pos[m] = (at + CHUNK) % self.length[m]
        if mode in self.loops and self.gain[mode] == 1 and all(g == 0 for m, g in self.gain.items() if m != mode):
            return self.loop_bytes[mode][2 * starts[mode]:2 * (starts[mode] + CHUNK)]
        out = None
        for m, loop in self.loops.items():
            g0 = self.gain[m]
            g1 = min(1.0, g0 + self.up) if m == mode else max(0.0, g0 - self.down)
            self.gain[m] = g1
            if g0 == g1 == 0:
                continue
            part = loop[starts[m]:starts[m] + CHUNK]
            step = (g1 - g0) / CHUNK
            part = [x * (g0 + step * i) for i, x in enumerate(part)]
            out = part if out is None else [a + b for a, b in zip(out, part)]
        if out is None:
            return self.silence
        return array.array("h", (max(-32768, min(32767, int(x))) for x in out)).tobytes()


class LinuxNoise(tone.LinuxTone):
    """The kit's pw-cat player with less queued ahead: 5 ms instead of 15 (owner, 2026-11-24: the sound
    felt late). PipeWire's own buffer still covers a late write; the core's tone keeps 15 ms. Its stream is
    named Surf Sound (owner, 2026-11-24: to pick it in OBS's Application Audio Capture); a core older than
    hub 1.17.0 ignores NAME and the stream stays pw-cat."""
    LEAD = 0.005
    NAME = "Surf Sound"


def player_class():
    """This OS's player class for NoiseSynth."""
    return tone.WindowsTone if sys.platform == "win32" else LinuxNoise


def play(volume, sound, kind="ramp", seconds=1.2, custom=None, levels=None, variant=None):
    """A burst of `sound` (its `variant` variant, kind's by default, or custom's file for kind) for
    `seconds`, volume 0-1; returns at once."""
    player = player_class()(NoiseSynth(volume, {kind: sound}, custom, levels, {kind: variant or kind}))
    player.start()
    player.mode = kind
    for delay, step in ((seconds, lambda: setattr(player, "mode", None)), (seconds + 0.4, player.close)):
        threading.Timer(delay, step).start()
    return True


def play_hit(volume, name, custom=None, levels=None):
    """One hit (HITS, custom's file for its slot if any) at volume 0-1; returns at once."""
    synth = NoiseSynth(volume, {}, custom, levels)
    synth.hit(name)
    player = player_class()(synth)
    player.start()
    threading.Timer(len(synth.hit_sounds[name]) / RATE + 0.3, player.close).start()
    return True
