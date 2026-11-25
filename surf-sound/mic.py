"""Surf Sound's microphone recorder (1.5.0): the hub's Rec button records a sound of your own.

Recorder(seconds, device) captures 16-bit mono at noise.RATE from `device` (an id from inputs(); None
or "" for the system's default input): Linux through PipeWire's
pw-cat (--record, raw samples to stdout, the binary the sound already plays through), Windows through
winmm's waveIn (typed as movekit.tone types waveOut). start() returns at once; the recording stops by
itself after `seconds`, so a closed page or a dead timer can't leave the microphone open. stop() ends
it early and returns the samples as floats -1..1; it can be called again and returns the same.

The hub calls start and stop as two calls (its section lock runs one call at a time), so the recorder
lives between them in hub_section.py.

Runs in the hub only, never in the runner beside the game. Stdlib only.
"""
import array
import json
import shutil
import subprocess
import sys
import threading

RATE = 48000  # noise.RATE; checked equal in check_surf_sound.py


def inputs():
    """The microphones to pick from, [[id, name]]: Linux PipeWire's sources (pw-dump; id the node.name,
    which pw-cat --target takes), Windows waveIn's devices (id the device's name: its number can change
    as devices come and go). Empty when they can't be listed."""
    if sys.platform == "win32":
        return [[n, n] for n in _win_inputs()]
    exe = shutil.which("pw-dump")
    if not exe:
        return []
    try:
        out = subprocess.run([exe], capture_output=True, text=True, timeout=5, check=False).stdout
        objs = json.loads(out or "[]")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    found = []
    for o in objs if isinstance(objs, list) else []:
        p = ((o or {}).get("info") or {}).get("props") or {}
        if str(p.get("media.class", "")).startswith("Audio/Source") and p.get("node.name"):
            found.append([str(p["node.name"]), str(p.get("node.description") or p["node.name"])])
    return found


class Recorder:
    """One recording of at most `seconds` from `device` (inputs()'s id; None: the default input)."""

    def __init__(self, seconds, device=None):
        self.device = device or None
        self.limit = int(RATE * seconds) * 2  # bytes
        self.data = bytearray()
        self.lock = threading.Lock()
        self.done = threading.Event()
        self.error = None
        self.thread = None

    def start(self):
        self._open()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _open(self):
        """Open the device; ValueError when there is none."""
        raise NotImplementedError

    def _run(self):
        raise NotImplementedError

    def _add(self, chunk):
        """Keep a chunk; True once the limit is reached."""
        with self.lock:
            self.data += chunk[:self.limit - len(self.data)]
            return len(self.data) >= self.limit

    @property
    def seconds(self):
        return len(self.data) / 2 / RATE

    @property
    def recording(self):
        return self.thread is not None and self.thread.is_alive()

    def stop(self):
        """End the recording (if it still runs) and return its samples as floats -1..1."""
        self.done.set()
        if self.thread:
            self.thread.join(3)
        if self.error and not self.data:
            raise ValueError(self.error)
        with self.lock:
            raw = bytes(self.data[:len(self.data) // 2 * 2])
        data = array.array("h", raw)
        if sys.byteorder == "big":
            data.byteswap()
        return [x / 32768 for x in data]


class LinuxRecorder(Recorder):
    """pw-cat --record, its stdout read all the time (a full pipe would stall it and lose sound)."""

    def _open(self):
        exe = shutil.which("pw-cat")
        if not exe:
            raise ValueError("recording needs pw-cat (PipeWire)")
        target = ["--target", self.device] if self.device else []
        self.proc = subprocess.Popen(
            [exe, "--record", "--raw", "--format", "s16", "--rate", str(RATE), "--channels", "1", *target,
             "-P", '{ application.name = "Surf Sound", media.name = "Surf Sound recording" }', "-"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        # a pw-cat that gives no bytes never reaches the limit: end it by the clock too
        self.backstop = threading.Timer(self.limit / 2 / RATE + 1, self._end)
        self.backstop.daemon = True
        self.backstop.start()

    def _end(self):
        """End pw-cat; its stdout's end wakes the reader."""
        if self.proc.poll() is None:
            self.proc.terminate()

    def stop(self):
        self.done.set()
        self.backstop.cancel()
        self._end()
        return super().stop()

    def _run(self):
        try:
            while not self.done.is_set():
                chunk = self.proc.stdout.read1(4800)
                if not chunk:
                    if not self.data and not self.done.is_set():
                        self.error = "the microphone gave no sound (pw-cat stopped)"
                    break
                if self._add(chunk):
                    break
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc.stdout.close()


class WindowsRecorder(Recorder):
    """winmm's waveIn: a ring of BUFFERS buffers of BUFFER_S each, added again as each fills (its done
    event, auto-reset). waveInReset hands back the partly filled one, whose dwBytesRecorded counts."""
    BUFFERS = 4
    BUFFER_S = 0.05

    def _open(self):
        import ctypes
        from ctypes import wintypes

        from movekit import tone
        self.ct, self.tone = ctypes, tone
        kernel32, winmm = _win32()
        self.hwi = wintypes.HANDLE()
        fmt = tone.WAVEFORMATEX(tone.WAVE_FORMAT_PCM, 1, RATE, RATE * 2, 2, 16, 0)
        self.event = kernel32.CreateEventW(None, False, False, None)
        dev = tone.WAVE_MAPPER
        if self.device:
            names = _win_inputs()
            if self.device not in names:
                if self.event:
                    kernel32.CloseHandle(self.event)
                raise ValueError(f"{self.device} isn't connected")
            dev = names.index(self.device)
        if not self.event or winmm.waveInOpen(ctypes.byref(self.hwi), dev, ctypes.byref(fmt),
                                              self.event, 0, tone.CALLBACK_EVENT):
            if self.event:
                kernel32.CloseHandle(self.event)
            raise ValueError("no microphone found (or Windows doesn't let desktop apps use it: Settings → "
                             "Privacy → Microphone)")

    def _run(self):
        ctypes, tone = self.ct, self.tone
        kernel32, winmm = _win32()
        size = int(RATE * self.BUFFER_S) * 2
        bufs = [ctypes.create_string_buffer(size) for _ in range(self.BUFFERS)]
        headers = [tone.WAVEHDR(ctypes.cast(b, ctypes.c_void_p), size) for b in bufs]
        hsize = ctypes.sizeof(tone.WAVEHDR)
        i, full = 0, False
        try:
            for h in headers:
                winmm.waveInPrepareHeader(self.hwi, ctypes.byref(h), hsize)
                winmm.waveInAddBuffer(self.hwi, ctypes.byref(h), hsize)
            if winmm.waveInStart(self.hwi):
                self.error = "the microphone didn't start"
                return
            while not self.done.is_set():
                h = headers[i]
                if not h.dwFlags & tone.WHDR_DONE:
                    kernel32.WaitForSingleObject(self.event, 20)
                    continue
                full = self._add(ctypes.string_at(bufs[i], h.dwBytesRecorded))
                if full:
                    break
                h.dwFlags &= ~tone.WHDR_DONE
                winmm.waveInAddBuffer(self.hwi, ctypes.byref(h), hsize)
                i = (i + 1) % self.BUFFERS
        finally:
            winmm.waveInReset(self.hwi)  # hands back every buffer: the one being filled (i) partly full
            h = headers[i]
            if not full and h.dwBytesRecorded:
                self._add(ctypes.string_at(bufs[i], h.dwBytesRecorded))
            for h in headers:
                winmm.waveInUnprepareHeader(self.hwi, ctypes.byref(h), hsize)
            winmm.waveInClose(self.hwi)
            kernel32.CloseHandle(self.event)


_dlls = {}


def _win_inputs():
    """waveIn's device names, by device number."""
    import ctypes
    from ctypes import wintypes as w

    class CAPS(ctypes.Structure):  # WAVEINCAPSW
        _fields_ = [("wMid", w.WORD), ("wPid", w.WORD), ("vDriverVersion", w.UINT),
                    ("szPname", w.WCHAR * 32), ("dwFormats", w.DWORD), ("wChannels", w.WORD),
                    ("wReserved1", w.WORD)]
    _, winmm = _win32()
    names = []
    for i in range(winmm.waveInGetNumDevs()):
        caps = CAPS()
        if winmm.waveInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
            names.append(caps.szPname)
        else:
            names.append(f"Device {i + 1}")
    return names


def _win32():
    """(kernel32, winmm) with the waveIn calls typed (64-bit handles; ctypes' default int would cut
    them)."""
    if not _dlls:
        import ctypes
        from ctypes import wintypes as w

        from movekit import tone
        k, _ = tone._win32()
        m = ctypes.WinDLL("winmm", use_last_error=True)
        p = ctypes.POINTER
        for fn, res, args in (
                (m.waveInOpen, w.UINT, [p(w.HANDLE), w.UINT, p(tone.WAVEFORMATEX), ctypes.c_size_t,
                                        ctypes.c_size_t, w.DWORD]),
                (m.waveInPrepareHeader, w.UINT, [w.HANDLE, p(tone.WAVEHDR), w.UINT]),
                (m.waveInUnprepareHeader, w.UINT, [w.HANDLE, p(tone.WAVEHDR), w.UINT]),
                (m.waveInAddBuffer, w.UINT, [w.HANDLE, p(tone.WAVEHDR), w.UINT]),
                (m.waveInStart, w.UINT, [w.HANDLE]),
                (m.waveInReset, w.UINT, [w.HANDLE]),
                (m.waveInClose, w.UINT, [w.HANDLE]),
                (m.waveInGetNumDevs, w.UINT, []),
                (m.waveInGetDevCapsW, w.UINT, [ctypes.c_size_t, ctypes.c_void_p, w.UINT])):
            fn.restype, fn.argtypes = res, args
        _dlls.update(kernel32=k, winmm=m)
    return _dlls["kernel32"], _dlls["winmm"]


def input_name():
    """The system's default input device's name, for messages; None when unknown."""
    if sys.platform == "win32":
        return None
    exe = shutil.which("wpctl")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "inspect", "@DEFAULT_AUDIO_SOURCE@"], capture_output=True, text=True,
                             timeout=3, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    for key in ("node.description", "node.nick", "node.name"):
        for line in out.splitlines():
            k, _, v = line.strip().lstrip("*").strip().partition(" = ")
            if k == key and v:
                return v.strip('"')
    return None


def recorder_class():
    """This OS's recorder."""
    return WindowsRecorder if sys.platform == "win32" else LinuxRecorder
