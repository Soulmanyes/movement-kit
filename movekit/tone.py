"""A constant tone on the desktop: ToneSynth makes the samples, LinuxTone (PipeWire's pw-cat) or
WindowsTone (winmm's waveOut) plays them. player() gives this OS's player class.

A player is built as player()(ToneSynth(volume, {mode: Hz})) and has `mode` (the mode sounding, or
None for silence), start() and close(). Switching takes effect within about 20 ms on Linux and 50 ms
on Windows.

Copied unchanged from the Strafe Trainer (trainer.py, trainer_linux.py, trainer_win.py), so Z Penalty
can use it too: modules don't import each other. The trainer moves to this copy in a later release. The Windows player keeps the trainer's
fix for crackle (Phase 12): a ring of 5 x 10 ms buffers refilled on waveOut's done event.

play(volume, hz, seconds) plays one short tone and returns at once (a settings page's preview).

Stdlib only. The Win32 calls happen inside WindowsTone, so this file imports on every OS.
"""
import array
import ctypes
import math
import shutil
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from fractions import Fraction

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

U32 = ctypes.c_uint32


class ToneSynth:
    """The constant tone's samples, for each platform's tone player (LinuxTone, WindowsTone): next(mode) gives the next CHUNK of 16-bit mono samples at RATE, for the
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


# ---------------------------------------------------------------- Linux

class LinuxTone:
    """A tone that sounds while `mode` is set (a cue: "wrong", "none", "overlap"; None for
    silence), streamed to PipeWire through pw-cat. `synth` is the ToneSynth giving the samples.

    Audio is written in 5 ms chunks paced by the clock, keeping only LEAD
    seconds queued, so switching it on or off is heard within ~20 ms (a plain
    pipe would buffer most of a second)."""
    LEAD = 0.015

    def __init__(self, synth):
        self.mode = None
        self.proc = None
        self.synth = synth
        player = shutil.which("pw-cat")
        if not player:
            return
        self.proc = subprocess.Popen(
            [player, "--playback", "--raw", "--rate", str(self.synth.RATE), "--channels", "1",
             "--format", "s16", "--latency", "10ms", "-"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            fcntl.fcntl(self.proc.stdin, 1031, 4096)  # F_SETPIPE_SZ: the smallest pipe
        except (OSError, AttributeError):
            pass

    def start(self):
        if self.proc:
            threading.Thread(target=self._feed, daemon=True).start()

    def _feed(self):
        rate, chunk = self.synth.RATE, self.synth.CHUNK
        start = time.monotonic()
        written = 0
        while True:
            due = (time.monotonic() - start + self.LEAD) * rate
            if written >= due:
                time.sleep(0.002)
                continue
            try:
                self.proc.stdin.write(self.synth.next(self.mode))
                self.proc.stdin.flush()
            except (BrokenPipeError, ValueError, OSError):
                return
            written += chunk
            if written + rate < due:  # fell far behind (suspend): don't catch up
                written = int(due)

    def close(self):
        if self.proc:
            self.proc.kill()


# ---------------------------------------------------------------- Windows

class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", U32),
                ("nAvgBytesPerSec", U32), ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
                ("cbSize", wintypes.WORD)]


class WAVEHDR(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", U32), ("dwBytesRecorded", U32),
                ("dwUser", ctypes.c_size_t), ("dwFlags", U32), ("dwLoops", U32),
                ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]


WAVE_MAPPER, WAVE_FORMAT_PCM, WHDR_DONE = 0xFFFFFFFF, 1, 1
CALLBACK_EVENT = 0x00050000

_dlls = {}


def _win32():
    """(kernel32, winmm) with every call this file makes typed: ctypes' default int would cut
    64-bit handles to 32 bits. Loaded once, on first use (Windows only)."""
    if not _dlls:
        w = wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        m = ctypes.WinDLL("winmm", use_last_error=True)
        p = ctypes.POINTER
        for fn, res, args in (
                (k.CloseHandle, w.BOOL, [w.HANDLE]),
                (k.CreateEventW, w.HANDLE, [w.LPVOID, w.BOOL, w.BOOL, w.LPCWSTR]),
                (k.WaitForSingleObject, w.DWORD, [w.HANDLE, w.DWORD]),
                (m.waveOutOpen, w.UINT, [p(w.HANDLE), w.UINT, p(WAVEFORMATEX), ctypes.c_size_t,
                                         ctypes.c_size_t, w.DWORD]),
                (m.waveOutPrepareHeader, w.UINT, [w.HANDLE, p(WAVEHDR), w.UINT]),
                (m.waveOutUnprepareHeader, w.UINT, [w.HANDLE, p(WAVEHDR), w.UINT]),
                (m.waveOutWrite, w.UINT, [w.HANDLE, p(WAVEHDR), w.UINT]),
                (m.waveOutReset, w.UINT, [w.HANDLE]),
                (m.waveOutClose, w.UINT, [w.HANDLE])):
            fn.restype, fn.argtypes = res, args
        _dlls.update(kernel32=k, winmm=m)
    return _dlls["kernel32"], _dlls["winmm"]


class WindowsTone:
    """A tone that sounds while `mode` is set (a cue, or None for silence), played through winmm's
    waveOut. `synth` is the ToneSynth giving 5 ms chunks.

    Each waveOut buffer holds CHUNKS chunks (10 ms) and BUFFERS of them are queued at most, so
    up to 50 ms is queued and switching it on or off is heard within about that. The Windows
    audio engine mixes in ~10 ms periods: with 5 ms buffers and only 20 ms queued, refilled by
    a 1 ms sleep poll, the queue ran dry and every gap was heard as a click (loud, crackly,
    distorted). So a buffer is now refilled as soon as waveOut signals its done event
    (CALLBACK_EVENT, auto-reset). `dry` counts the times every buffer had finished before the
    next was written, logged at close."""
    BUFFERS = 5
    CHUNKS = 2

    def __init__(self, synth):
        self.mode = None
        self.synth = synth
        self.closed = threading.Event()
        self.thread = None
        self.dry = 0
        self.hwo = wintypes.HANDLE()
        kernel32, winmm = _win32()
        rate = synth.RATE
        fmt = WAVEFORMATEX(WAVE_FORMAT_PCM, 1, rate, rate * 2, 2, 16, 0)
        self.event = kernel32.CreateEventW(None, False, False, None)  # auto-reset
        if not self.event or winmm.waveOutOpen(ctypes.byref(self.hwo), WAVE_MAPPER, ctypes.byref(fmt),
                                               self.event, 0, CALLBACK_EVENT):
            print("tone: no sound device", flush=True)
            if self.event:
                kernel32.CloseHandle(self.event)
                self.event = None
            self.hwo = None

    def start(self):
        if self.hwo:
            self.thread = threading.Thread(target=self._feed, daemon=True)
            self.thread.start()

    def _feed(self):
        kernel32, winmm = _win32()
        size = 2 * self.synth.CHUNK * self.CHUNKS
        data = [ctypes.create_string_buffer(size) for _ in range(self.BUFFERS)]
        headers = [WAVEHDR(ctypes.cast(d, ctypes.c_void_p), size) for d in data]
        hsize = ctypes.sizeof(WAVEHDR)
        for h in headers:
            winmm.waveOutPrepareHeader(self.hwo, ctypes.byref(h), hsize)
        queued = [False] * self.BUFFERS
        i = 0
        try:
            while not self.closed.is_set():
                h = headers[i]
                if queued[i] and not h.dwFlags & WHDR_DONE:
                    kernel32.WaitForSingleObject(self.event, 20)
                    continue
                if all(queued) and all(x.dwFlags & WHDR_DONE for x in headers):
                    self.dry += 1
                ctypes.memmove(data[i], b"".join(self.synth.next(self.mode) for _ in range(self.CHUNKS)), size)
                h.dwFlags &= ~WHDR_DONE
                if winmm.waveOutWrite(self.hwo, ctypes.byref(h), hsize):
                    return
                queued[i] = True
                i = (i + 1) % self.BUFFERS
        finally:
            winmm.waveOutReset(self.hwo)  # hands back every queued buffer
            for h in headers:
                winmm.waveOutUnprepareHeader(self.hwo, ctypes.byref(h), hsize)
            winmm.waveOutClose(self.hwo)
            kernel32.CloseHandle(self.event)

    def close(self):
        self.closed.set()
        if self.thread:
            self.thread.join(1)
            print(f"tone: ran dry {self.dry} times", flush=True)
        elif self.hwo:
            kernel32, winmm = _win32()
            winmm.waveOutClose(self.hwo)
            kernel32.CloseHandle(self.event)


def player():
    """This OS's tone player class."""
    return WindowsTone if sys.platform == "win32" else LinuxTone


def play(volume, hz, seconds=0.4):
    """One tone of `seconds` at `hz`, volume 0-1; returns at once."""
    tone = player()(ToneSynth(volume, {"on": hz}))
    tone.start()
    tone.mode = "on"
    for delay, step in ((seconds, lambda: setattr(tone, "mode", None)), (seconds + 0.2, tone.close)):
        threading.Timer(delay, step).start()
    return True
