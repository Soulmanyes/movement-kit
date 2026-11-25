"""Surf Sound's custom sounds: a file the owner picks in the hub becomes a WAV the synth can play.

make(src, slot) reads the file, turns it into 16-bit mono at noise.RATE and saves it in
settings.sounds_dir() as <slot>-<hash>.wav, named by a hash of its samples: a new pick is a new name, so
the runner (which rebuilds its synth only when the settings change) and noise's file cache never play an
old one. The file is only used once the settings name it (the hub's Apply); prune() then deletes the ones
no setting names.

- WAV: 8, 16, 24 or 32-bit integer samples, any rate, any number of channels (read here, stdlib only).
- Anything else (MP3, OGG, FLAC, a float WAV): through ffmpeg when it is installed, else an error asking
  for a WAV.
- Only the first READ_MAX_S of a file is read (a 4-minute song read whole took 8 s and 1.3 GB).
- Loops (ramp, ceiling): LOOP_MIN_S to LOOP_MAX_S (longer is cut). Its end cross-fades into its start
  (noise.render_file), so it repeats without a click. 15 s, not more: the runner renders the loops again
  on every settings change (two 30 s loops took about 1 s).
- Hits (wall, graze, bonk, jump): the silence before the sound is trimmed so it plays at once (a gate GATE_DB
  under its peak, LEAD_S kept), and anything past HIT_MAX_S is faded out and cut: a long hit would make
  the chunk it starts in slow to mix (crackle on Windows).

Runs in the hub only, never in the runner beside the game.
"""
import array
import hashlib
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from movekit.hub import local_import

LOOPS = ("ramp", "ceiling")
LOOP_MAX_S = 15.0
READ_MAX_S = LOOP_MAX_S + 1  # a hit's leading silence comes out of this too
HIT_MAX_S = 2.0
HIT_FADE_S = 0.05  # the fade before a long hit's cut
GATE_DB = 40
LEAD_S = 0.002
FFMPEG_TIMEOUT = 30


def _noise():
    return local_import(__file__, "noise")


def _settings():
    return local_import(__file__, "settings")


def _wav(path):
    """(mono floats -1..1, rate) of an integer PCM WAV; wave.Error for one it can't read (a float WAV)."""
    with wave.open(str(path)) as w:
        ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(min(w.getnframes(), int(rate * READ_MAX_S)))
    if width == 1:  # unsigned
        xs = [(b - 128) / 128 for b in raw]
    else:
        if width == 3:  # spread to 32-bit, the low byte 0
            wide = bytearray(len(raw) // 3 * 4)
            for k in range(3):
                wide[k + 1::4] = raw[k::3]
            raw, width = bytes(wide), 4
        if width not in (2, 4):
            raise wave.Error(f"{width * 8}-bit samples")
        data = array.array("h" if width == 2 else "i", raw)
        if sys.byteorder == "big":
            data.byteswap()
        full = 2 ** (8 * width - 1)
        xs = [x / full for x in data]
    if ch > 1:
        xs = [sum(xs[i:i + ch]) / ch for i in range(0, len(xs) - ch + 1, ch)]
    return xs, rate


def _ffmpeg(path):
    """Mono floats at noise.RATE through ffmpeg, or None when it isn't installed."""
    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    rate = _noise().RATE
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        out = subprocess.run([exe, "-v", "error", "-i", str(path), "-t", str(READ_MAX_S), "-f", "s16le", "-ac", "1",
                              "-ar", str(rate), "-"],
                             capture_output=True, timeout=FFMPEG_TIMEOUT, creationflags=flags, check=False)
    except subprocess.TimeoutExpired:
        raise ValueError(f"{Path(path).name}: ffmpeg took too long") from None
    if out.returncode != 0 or not out.stdout:
        msg = out.stderr.decode(errors="replace").strip().splitlines()
        raise ValueError(f"{Path(path).name}: ffmpeg can't read it ({msg[-1] if msg else 'no sound'})")
    data = array.array("h", out.stdout[:len(out.stdout) // 2 * 2])
    if sys.byteorder == "big":
        data.byteswap()
    return [x / 32768 for x in data]


def _resample(xs, rate, to):
    """Linear resampling from rate to `to`."""
    if rate == to or not xs:
        return xs
    n = int(len(xs) * to / rate)
    step = rate / to
    out = []
    for i in range(n):
        p = i * step
        j = int(p)
        f = p - j
        b = xs[j + 1] if j + 1 < len(xs) else xs[j]
        out.append(xs[j] + (b - xs[j]) * f)
    return out


def decode(path):
    """Mono floats at noise.RATE from a sound file; ValueError if it can't be read."""
    path = Path(path)
    rate = _noise().RATE
    try:
        xs, src_rate = _wav(path)
        return _resample(xs, src_rate, rate)
    except (wave.Error, EOFError) as e:
        why = f"not a WAV it can read ({e})"
    except OSError as e:
        raise ValueError(f"{path.name}: {e.strerror or e}") from None
    xs = _ffmpeg(path)
    if xs is None:
        raise ValueError(f"{path.name}: {why}. Save it as a 16-bit WAV, or install ffmpeg for other formats")
    return xs


def shape(xs, slot):
    """The samples as the slot needs them (trimmed, cut, length checked), peaking at 0.99."""
    noise = _noise()
    rate = noise.RATE
    peak = max(map(abs, xs), default=0)
    if peak < 1e-4:
        raise ValueError("the file is silent")
    if slot in LOOPS:
        if len(xs) < rate * noise.LOOP_MIN_S:
            raise ValueError(f"a ramp or ceiling sound needs at least {noise.LOOP_MIN_S:g} s (it repeats)")
        xs = xs[:int(rate * LOOP_MAX_S)]
    else:
        gate = peak * 10 ** (-GATE_DB / 20)
        first = next(i for i, x in enumerate(xs) if abs(x) >= gate)
        xs = xs[max(0, first - int(rate * LEAD_S)):]
        end = int(rate * HIT_MAX_S)
        if len(xs) > end:
            fade = int(rate * HIT_FADE_S)
            xs = xs[:end - fade] + [x * (1 - i / fade) for i, x in enumerate(xs[end - fade:end])]
    k = 0.99 / peak
    return [x * k for x in xs]


def make(src, slot):
    """Turn the file `src` into the slot's custom sound; returns the settings entry {"file", "name"}."""
    if slot not in _settings().SLOTS:
        raise ValueError(f"no sound {slot!r}")
    xs = shape(decode(src), slot)
    data = array.array("h", (max(-32768, min(32767, round(x * 32767))) for x in xs))
    if sys.byteorder == "big":
        data.byteswap()
    raw = data.tobytes()
    name = f"{slot}-{hashlib.sha256(raw).hexdigest()[:12]}.wav"
    folder = _settings().sounds_dir()
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / name
    if not dest.exists():
        tmp = dest.with_suffix(".tmp")
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(_noise().RATE)
            w.writeframes(raw)
        os.replace(tmp, dest)
    return {"file": name, "name": Path(src).name}


def prune(cfg):
    """Delete the custom sounds cfg doesn't name (picks never applied, or replaced)."""
    folder = _settings().sounds_dir()
    keep = {c["file"] for c in cfg["custom"].values()}
    if not folder.is_dir():
        return
    for f in folder.iterdir():
        if f.name not in keep and (_settings().FILE_RE.fullmatch(f.name) or f.suffix == ".tmp"):
            f.unlink(missing_ok=True)

