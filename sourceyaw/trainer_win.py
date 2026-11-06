"""The strafe trainer's Windows side (Phase 12 in PLAN.md): everything trainer.run needs from the
desktop, with the standard library only (the hub exe bundles no Pillow or pywin32).

  - keys and mouse from Raw Input: a hidden window registered with RIDEV_INPUTSINK, so input
    arrives while the game is in front, with no admin and nothing installed,
  - focus: the foreground window's program lives in the game's folder, cursor inside it,
  - the constant tone through winmm's waveOut, game sounds through winsound,
  - no offset number on screen: drawing over CS:S means hooking DirectX, which risks VAC.

`Windows` bundles them as trainer.run's `platform`. The Win32 calls are made inside functions
and classes only, so this file imports anywhere and its pure parts (key_event, mouse_events,
the struct layouts) are checked on Linux by check_trainer.py.
"""

import ctypes
import queue
import threading
import time
from ctypes import wintypes
from pathlib import Path

import yawcore

# ---------------------------------------------------------------- Raw Input -> evdev

EV_KEY, EV_REL = 1, 2
REL_X, REL_WHEEL = 0, 8
RI_KEY_BREAK, RI_KEY_E0 = 1, 2
# Raw Input's MakeCode is the scan code set 1 code, which equals the evdev code for the basic keys
# (the ones trainer.SOURCE_KEYS knows); keys sent with the E0 prefix have their own evdev codes
E0_KEYS = {0x38: 100, 0x1D: 97, 0x1C: 96, 0x35: 98, 0x47: 102, 0x48: 103, 0x49: 104, 0x4B: 105,
           0x4D: 106, 0x4F: 107, 0x50: 108, 0x51: 109, 0x52: 110, 0x53: 111}
# usButtonFlags: (down flag, up flag, evdev code)
MOUSE_BUTTONS = [(0x0001, 0x0002, 272), (0x0004, 0x0008, 273), (0x0010, 0x0020, 274),
                 (0x0040, 0x0080, 275), (0x0100, 0x0200, 276)]
RI_MOUSE_WHEEL = 0x0400
MOUSE_MOVE_ABSOLUTE = 0x01


def key_event(make_code, flags):
    """(EV_KEY, evdev code, 1 down / 0 up) for a RAWKEYBOARD, or None for a code with no evdev twin."""
    if flags & RI_KEY_E0:
        code = E0_KEYS.get(make_code)
        if code is None:
            return None
    else:
        code = make_code
    if not code:
        return None
    return EV_KEY, code, 0 if flags & RI_KEY_BREAK else 1


def mouse_events(us_flags, button_flags, button_data, last_x):
    """[(type, code, value)] for a RAWMOUSE: buttons, the wheel, relative X motion. Absolute
    motion (tablets, remote desktop) is left out: it isn't a turn."""
    events = []
    for down, up, code in MOUSE_BUTTONS:
        if button_flags & down:
            events.append((EV_KEY, code, 1))
        if button_flags & up:
            events.append((EV_KEY, code, 0))
    if button_flags & RI_MOUSE_WHEEL:
        delta = ctypes.c_short(button_data).value
        events.append((EV_REL, REL_WHEEL, 1 if delta > 0 else -1))
    if last_x and not us_flags & MOUSE_MOVE_ABSOLUTE:
        events.append((EV_REL, REL_X, last_x))
    return events


# ---------------------------------------------------------------- Win32 structs

# fixed widths: Windows' DWORD/ULONG/LONG are 32-bit, while wintypes' are 64-bit on Linux,
# where the layouts are checked
U32, I32 = ctypes.c_uint32, ctypes.c_int32


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                ("dwFlags", U32), ("hwndTarget", wintypes.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", U32), ("dwSize", U32), ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [("usFlags", wintypes.USHORT), ("_pad", wintypes.USHORT),
                ("usButtonFlags", wintypes.USHORT), ("usButtonData", wintypes.USHORT),
                ("ulRawButtons", U32), ("lLastX", I32), ("lLastY", I32), ("ulExtraInformation", U32)]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [("MakeCode", wintypes.USHORT), ("Flags", wintypes.USHORT),
                ("Reserved", wintypes.USHORT), ("VKey", wintypes.USHORT),
                ("Message", wintypes.UINT), ("ExtraInformation", U32)]


class RAWINPUT(ctypes.Structure):
    class _Data(ctypes.Union):
        _fields_ = [("mouse", RAWMOUSE), ("keyboard", RAWKEYBOARD)]
    _fields_ = [("header", RAWINPUTHEADER), ("data", _Data)]


LRESULT = ctypes.c_ssize_t
# WINFUNCTYPE exists only on Windows; CFUNCTYPE stands in so the file imports elsewhere
WNDPROC = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR)]


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", U32),
                ("nAvgBytesPerSec", U32), ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
                ("cbSize", wintypes.WORD)]


class WAVEHDR(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", U32), ("dwBytesRecorded", U32),
                ("dwUser", ctypes.c_size_t), ("dwFlags", U32), ("dwLoops", U32),
                ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]


WM_INPUT, WM_CLOSE = 0x00FF, 0x0010
RIM_TYPEMOUSE, RIM_TYPEKEYBOARD = 0, 1
RID_INPUT = 0x10000003
RIDEV_REMOVE, RIDEV_INPUTSINK = 0x00000001, 0x00000100
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WAVE_MAPPER, WAVE_FORMAT_PCM, WHDR_DONE = 0xFFFFFFFF, 1, 1

_dlls = {}


def _win32():
    """(user32, kernel32, winmm) with every call this file makes typed: ctypes' default int would
    cut 64-bit handles to 32 bits. Loaded once, on first use (Windows only)."""
    if not _dlls:
        w = wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        m = ctypes.WinDLL("winmm", use_last_error=True)
        p = ctypes.POINTER
        for fn, res, args in (
                (u.DefWindowProcW, LRESULT, [w.HWND, w.UINT, w.WPARAM, w.LPARAM]),
                (u.GetRawInputData, w.UINT, [w.HANDLE, w.UINT, ctypes.c_void_p, p(w.UINT), w.UINT]),
                (u.RegisterRawInputDevices, w.BOOL, [p(RAWINPUTDEVICE), w.UINT, w.UINT]),
                (u.RegisterClassW, w.ATOM, [p(WNDCLASSW)]),
                (u.UnregisterClassW, w.BOOL, [w.LPCWSTR, w.HINSTANCE]),
                (u.CreateWindowExW, w.HWND, [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                             ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]),
                (u.DestroyWindow, w.BOOL, [w.HWND]),
                (u.PostMessageW, w.BOOL, [w.HWND, w.UINT, w.WPARAM, w.LPARAM]),
                (u.GetMessageW, w.BOOL, [p(w.MSG), w.HWND, w.UINT, w.UINT]),
                (u.TranslateMessage, w.BOOL, [p(w.MSG)]),
                (u.DispatchMessageW, LRESULT, [p(w.MSG)]),
                (u.PostQuitMessage, None, [ctypes.c_int]),
                (u.GetForegroundWindow, w.HWND, []),
                (u.GetWindowThreadProcessId, w.DWORD, [w.HWND, p(w.DWORD)]),
                (u.GetWindowRect, w.BOOL, [w.HWND, p(w.RECT)]),
                (u.GetCursorPos, w.BOOL, [p(w.POINT)]),
                (k.GetModuleHandleW, w.HMODULE, [w.LPCWSTR]),
                (k.OpenProcess, w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]),
                (k.QueryFullProcessImageNameW, w.BOOL, [w.HANDLE, w.DWORD, w.LPWSTR, p(w.DWORD)]),
                (k.CloseHandle, w.BOOL, [w.HANDLE]),
                (m.waveOutOpen, w.UINT, [p(w.HANDLE), w.UINT, p(WAVEFORMATEX), ctypes.c_size_t,
                                         ctypes.c_size_t, w.DWORD]),
                (m.waveOutPrepareHeader, w.UINT, [w.HANDLE, p(WAVEHDR), w.UINT]),
                (m.waveOutUnprepareHeader, w.UINT, [w.HANDLE, p(WAVEHDR), w.UINT]),
                (m.waveOutWrite, w.UINT, [w.HANDLE, p(WAVEHDR), w.UINT]),
                (m.waveOutReset, w.UINT, [w.HANDLE]),
                (m.waveOutClose, w.UINT, [w.HANDLE])):
            fn.restype, fn.argtypes = res, args
        _dlls.update(user32=u, kernel32=k, winmm=m)
    return _dlls["user32"], _dlls["kernel32"], _dlls["winmm"]


# ---------------------------------------------------------------- input

class RawInput:
    """Keys and mouse from Raw Input, as trainer.run's event source: read(timeout) gives
    [(time, EV_KEY/EV_REL, evdev code, value)], time from perf_counter when WM_INPUT arrives
    (GetMessageTime ticks in ~15.6 ms steps, a whole game tick).

    A thread of its own owns a hidden window registered with RIDEV_INPUTSINK, and pumps its
    messages until close(). Raises OSError when Windows refuses the window or the registration."""
    _count = 0

    def __init__(self):
        self.events = queue.SimpleQueue()
        self.hwnd = None
        self.error = None
        ready = threading.Event()
        RawInput._count += 1
        # a class name per instance: a class outlives its window procedure otherwise
        self.class_name = f"SourceYawTrainer{RawInput._count}"
        self.thread = threading.Thread(target=self._run, args=(ready,), daemon=True)
        self.thread.start()
        ready.wait(5)
        if self.hwnd is None:
            raise OSError(self.error or "Raw Input didn't start")

    def _run(self, ready):
        user32, kernel32, _ = _win32()
        self.proc = WNDPROC(self._wndproc)  # kept referenced: Windows calls it
        hinst = kernel32.GetModuleHandleW(None)
        try:
            wc = WNDCLASSW(lpfnWndProc=self.proc, hInstance=hinst, lpszClassName=self.class_name)
            if not user32.RegisterClassW(ctypes.byref(wc)):
                raise OSError(f"RegisterClassW failed ({ctypes.get_last_error()})")
            # a top-level window that is never shown
            hwnd = user32.CreateWindowExW(0, self.class_name, "Source Yaw trainer", 0, 0, 0, 0, 0,
                                          None, None, hinst, None)
            if not hwnd:
                raise OSError(f"CreateWindowExW failed ({ctypes.get_last_error()})")
            devices = (RAWINPUTDEVICE * 2)(RAWINPUTDEVICE(1, 6, RIDEV_INPUTSINK, hwnd),   # keyboard
                                           RAWINPUTDEVICE(1, 2, RIDEV_INPUTSINK, hwnd))   # mouse
            if not user32.RegisterRawInputDevices(devices, 2, ctypes.sizeof(RAWINPUTDEVICE)):
                user32.DestroyWindow(hwnd)
                raise OSError(f"RegisterRawInputDevices failed ({ctypes.get_last_error()})")
        except OSError as e:
            self.error = str(e)
            user32.UnregisterClassW(self.class_name, hinst)
            ready.set()
            return
        self.hwnd = hwnd
        ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            gone = (RAWINPUTDEVICE * 2)(RAWINPUTDEVICE(1, 6, RIDEV_REMOVE, None),
                                        RAWINPUTDEVICE(1, 2, RIDEV_REMOVE, None))
            user32.RegisterRawInputDevices(gone, 2, ctypes.sizeof(RAWINPUTDEVICE))
            user32.DestroyWindow(hwnd)
            user32.UnregisterClassW(self.class_name, hinst)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        user32 = _dlls["user32"]
        if msg == WM_INPUT:
            now = time.perf_counter()
            raw = RAWINPUT()
            size = wintypes.UINT(ctypes.sizeof(raw))
            got = user32.GetRawInputData(lparam, RID_INPUT, ctypes.byref(raw), ctypes.byref(size),
                                         ctypes.sizeof(RAWINPUTHEADER))
            if got not in (0, 0xFFFFFFFF):
                if raw.header.dwType == RIM_TYPEKEYBOARD:
                    event = key_event(raw.data.keyboard.MakeCode, raw.data.keyboard.Flags)
                    if event:
                        self.events.put((now, *event))
                elif raw.header.dwType == RIM_TYPEMOUSE:
                    m = raw.data.mouse
                    for event in mouse_events(m.usFlags, m.usButtonFlags, m.usButtonData, m.lLastX):
                        self.events.put((now, *event))
        elif msg == WM_CLOSE:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def read(self, timeout):
        try:
            events = [self.events.get(timeout=timeout)]
        except queue.Empty:
            return [] if self.thread.is_alive() else None
        while True:
            try:
                events.append(self.events.get_nowait())
            except queue.Empty:
                return events

    def close(self):
        if self.hwnd and self.thread.is_alive():
            _dlls["user32"].PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
            self.thread.join(1)


# ---------------------------------------------------------------- focus

def in_folder(image, root):
    """Whether the program at path `image` lives under folder `root` (case-insensitive, as on Windows)."""
    image, root = str(image).replace("/", "\\").lower(), str(root).replace("/", "\\").lower().rstrip("\\")
    return image.startswith(root + "\\")


class Focus:
    """Whether the game's window has focus, asked every 0.25 s: the foreground window's program
    lives in the game's install folder (the mod folder's parent, so hl2.exe, cstrike_win64.exe or
    the Momentum exe all count without naming them), and the cursor is inside that window, so
    scrolling another window under the cursor doesn't count as jumping."""
    INTERVAL = 0.25

    def __init__(self, game_dir):
        self.root = Path(game_dir).parent
        self.focused = True
        self.stopped = threading.Event()
        threading.Thread(target=self._watch, daemon=True).start()

    def _check(self):
        user32, kernel32, _ = _win32()
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return False
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return False
        finally:
            kernel32.CloseHandle(handle)
        if not in_folder(buf.value, self.root):
            return False
        rect, point = wintypes.RECT(), wintypes.POINT()
        if not (user32.GetWindowRect(hwnd, ctypes.byref(rect)) and user32.GetCursorPos(ctypes.byref(point))):
            return True
        return rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom

    def _watch(self):
        while not self.stopped.is_set():
            try:
                self.focused = self._check()
            except OSError:
                self.focused = False
            self.stopped.wait(self.INTERVAL)


# ---------------------------------------------------------------- constant tone

class Tone:
    """A tone that sounds while `mode` is set (a cue, or None for silence), played through winmm's
    waveOut. `synth` is the trainer.ToneSynth giving 5 ms chunks.

    BUFFERS chunks are queued at most, so switching it on or off is heard within about
    BUFFERS x 5 ms; a buffer is refilled as soon as waveOut marks it done. Too few buffers
    would let the sound run dry (crackles) when Python is slow to refill."""
    BUFFERS = 4

    def __init__(self, synth):
        self.mode = None
        self.synth = synth
        self.closed = threading.Event()
        self.thread = None
        self.hwo = wintypes.HANDLE()
        _, _, winmm = _win32()
        rate = synth.RATE
        fmt = WAVEFORMATEX(WAVE_FORMAT_PCM, 1, rate, rate * 2, 2, 16, 0)
        if winmm.waveOutOpen(ctypes.byref(self.hwo), WAVE_MAPPER, ctypes.byref(fmt), 0, 0, 0):
            print("trainer: no sound device for the tone", flush=True)
            self.hwo = None

    def start(self):
        if self.hwo:
            self.thread = threading.Thread(target=self._feed, daemon=True)
            self.thread.start()

    def _feed(self):
        _, _, winmm = _win32()
        size = 2 * self.synth.CHUNK
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
                    time.sleep(0.001)
                    continue
                ctypes.memmove(data[i], self.synth.next(self.mode), size)
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

    def close(self):
        self.closed.set()
        if self.thread:
            self.thread.join(1)
        elif self.hwo:
            _win32()[2].waveOutClose(self.hwo)


# ---------------------------------------------------------------- the platform

class Windows:
    """trainer.run's `platform` on Windows."""
    FORWARDED_ONLY = False      # Raw Input sees every key; only keys with no evdev twin are missed
    UNSEEN = "keys Source Yaw can't read on Windows"
    GONE = "Raw Input stopped"
    Tone = Tone
    clock = staticmethod(time.perf_counter)  # RawInput stamps events with perf_counter

    def overlay(self, cfg):
        return None  # no offset number on Windows (VAC)

    def open_input(self):
        try:
            return RawInput()
        except OSError as e:
            print(f"trainer: no Raw Input ({e})", flush=True)
            return None

    def focus(self, game, game_dir):
        return Focus(game_dir)

    def play(self, game_dir, sound, game):
        """A game sound, through winsound (async: a new sound cuts the last one short)."""
        import winsound
        path = yawcore.sound_file(game_dir, sound, game)
        if not path:
            return False
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return True
