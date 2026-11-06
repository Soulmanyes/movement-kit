"""Source Yaw on Windows, probe (Phase 12 in PLAN.md): does Raw Input reach a background program
while CS:S or Momentum Mod is in front?

The Windows strafe trainer will read keys and mouse movement the way this script does: a hidden
window registered for Raw Input with RIDEV_INPUTSINK (no admin needed). This script prints
what arrives, so we know it works before the trainer is built on it.

Run it (needs Python 3.10+ from python.org, nothing else):

    py rawinput_probe.py

Then start the game, load a map and play for a minute: strafe (A/D), jump, turn with the mouse,
use the scroll wheel, and your turn keys if you have any. Alt-tab out once and back. Close
this window, or press Ctrl+C, to stop. It writes rawinput_probe.log next to itself; send
that file back.

What to look for, every 2 seconds:
    front: hl2.exe (in window)   keys 14   mouse 812 moves, gap med 1.0 ms max 8.1 ms   wheel 3
If the counts stay at 0 while the game is in front, Raw Input doesn't get through and the
trainer needs another way to read input.
"""

import ctypes
import statistics
import sys
import time
from ctypes import wintypes
from pathlib import Path

LOG = Path(__file__).with_suffix(".log")

# ---------------------------------------------------------------- input -> evdev (pure, testable anywhere)

RI_KEY_BREAK, RI_KEY_E0 = 1, 2
# Raw Input's MakeCode is the scan code set 1 code, which equals the evdev code for the basic keys;
# keys sent with the E0 prefix have their own evdev codes
E0_KEYS = {0x38: 100, 0x1D: 97, 0x1C: 96, 0x35: 98, 0x47: 102, 0x48: 103, 0x49: 104, 0x4B: 105,
           0x4D: 106, 0x4F: 107, 0x50: 108, 0x51: 109, 0x52: 110, 0x53: 111}
EVDEV_NAMES = {**{c: k for k, c in zip("qwertyuiop", range(16, 26))},
               **{c: k for k, c in zip("asdfghjkl", range(30, 39))},
               **{c: k for k, c in zip("zxcvbnm", range(44, 51))},
               **{c: d for d, c in zip("1234567890", range(2, 12))},
               57: "space", 56: "alt", 100: "ralt", 29: "ctrl", 97: "rctrl", 42: "shift", 54: "rshift",
               15: "tab", 58: "capslock", 14: "backspace", 1: "escape",
               272: "mouse1", 273: "mouse2", 274: "mouse3", 275: "mouse4", 276: "mouse5"}
EV_KEY, EV_REL = 1, 2
REL_X, REL_WHEEL = 0, 8
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
    """[(type, code, value)] for a RAWMOUSE: buttons, the wheel, relative X motion."""
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


# ---------------------------------------------------------------- Win32 (Windows only)

WM_INPUT, WM_DESTROY, WM_CLOSE = 0x00FF, 0x0002, 0x0010
RIM_TYPEMOUSE, RIM_TYPEKEYBOARD = 0, 1
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


# fixed widths: Windows' DWORD/ULONG/LONG are 32-bit, while wintypes' are 64-bit on Linux,
# where the parsing is checked
U32, I32 = ctypes.c_uint32, ctypes.c_int32


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                ("dwFlags", U32), ("hwndTarget", wintypes.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", U32), ("dwSize", U32),
                ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [("usFlags", wintypes.USHORT), ("_pad", wintypes.USHORT),
                ("usButtonFlags", wintypes.USHORT), ("usButtonData", wintypes.USHORT),
                ("ulRawButtons", U32), ("lLastX", I32),
                ("lLastY", I32), ("ulExtraInformation", U32)]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [("MakeCode", wintypes.USHORT), ("Flags", wintypes.USHORT),
                ("Reserved", wintypes.USHORT), ("VKey", wintypes.USHORT),
                ("Message", wintypes.UINT), ("ExtraInformation", U32)]


class RAWINPUT(ctypes.Structure):
    class _Data(ctypes.Union):
        _fields_ = [("mouse", RAWMOUSE), ("keyboard", RAWKEYBOARD)]
    _fields_ = [("header", RAWINPUTHEADER), ("data", _Data)]


LRESULT = ctypes.c_ssize_t
# WINFUNCTYPE exists only on Windows; CFUNCTYPE stands in so the pure parts import elsewhere
WNDPROC = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR)]


class Probe:
    def __init__(self):
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # every handle typed: ctypes' default int would cut 64-bit handles to 32 bits
        w, u, k = wintypes, self.user32, self.kernel32
        for fn, res, args in (
                (u.DefWindowProcW, LRESULT, [w.HWND, w.UINT, w.WPARAM, w.LPARAM]),
                (u.GetRawInputData, w.UINT, [w.HANDLE, w.UINT, ctypes.c_void_p, ctypes.POINTER(w.UINT), w.UINT]),
                (u.RegisterRawInputDevices, w.BOOL, [ctypes.POINTER(RAWINPUTDEVICE), w.UINT, w.UINT]),
                (u.RegisterClassW, w.ATOM, [ctypes.POINTER(WNDCLASSW)]),
                (u.CreateWindowExW, w.HWND, [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                             ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]),
                (u.SetTimer, ctypes.c_size_t, [w.HWND, ctypes.c_size_t, w.UINT, ctypes.c_void_p]),
                (u.GetMessageW, w.BOOL, [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]),
                (u.TranslateMessage, w.BOOL, [ctypes.POINTER(w.MSG)]),
                (u.DispatchMessageW, LRESULT, [ctypes.POINTER(w.MSG)]),
                (u.PostQuitMessage, None, [ctypes.c_int]),
                (u.GetForegroundWindow, w.HWND, []),
                (u.GetWindowThreadProcessId, w.DWORD, [w.HWND, ctypes.POINTER(w.DWORD)]),
                (u.GetWindowRect, w.BOOL, [w.HWND, ctypes.POINTER(w.RECT)]),
                (u.GetCursorPos, w.BOOL, [ctypes.POINTER(w.POINT)]),
                (k.GetModuleHandleW, w.HMODULE, [w.LPCWSTR]),
                (k.OpenProcess, w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]),
                (k.QueryFullProcessImageNameW, w.BOOL, [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]),
                (k.CloseHandle, w.BOOL, [w.HANDLE])):
            fn.restype, fn.argtypes = res, args
        self.log = open(LOG, "w", encoding="utf-8")  # noqa: SIM115 - open for the whole run
        self.reset()
        self.last_report = time.perf_counter()
        self.proc = WNDPROC(self.wndproc)  # kept referenced: Windows calls it

    def say(self, line):
        print(line, flush=True)
        self.log.write(line + "\n")
        self.log.flush()

    def reset(self):
        self.keys = 0
        self.moves = []      # perf_counter of each mouse move
        self.wheel = 0
        self.fronts = set()

    # ------------------------------------------------ foreground

    def front(self):
        """(process image name, cursor inside its window) for the foreground window."""
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return "-", False
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = "?"
        handle = self.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if handle:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if self.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                name = buf.value.rsplit("\\", 1)[-1]
            self.kernel32.CloseHandle(handle)
        rect, point = wintypes.RECT(), wintypes.POINT()
        self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        self.user32.GetCursorPos(ctypes.byref(point))
        inside = rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom
        return name, inside

    # ------------------------------------------------ window and input

    def start(self):
        hinst = self.kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW(lpfnWndProc=self.proc, hInstance=hinst, lpszClassName="SourceYawProbe")
        if not self.user32.RegisterClassW(ctypes.byref(wc)):
            sys.exit(f"RegisterClassW failed: {ctypes.get_last_error()}")
        # a plain top-level window that is never shown (not HWND_MESSAGE, to rule that out)
        self.hwnd = self.user32.CreateWindowExW(0, "SourceYawProbe", "Source Yaw probe", 0,
                                                0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            sys.exit(f"CreateWindowExW failed: {ctypes.get_last_error()}")
        devices = (RAWINPUTDEVICE * 2)(RAWINPUTDEVICE(1, 6, RIDEV_INPUTSINK, self.hwnd),   # keyboard
                                       RAWINPUTDEVICE(1, 2, RIDEV_INPUTSINK, self.hwnd))   # mouse
        if not self.user32.RegisterRawInputDevices(devices, 2, ctypes.sizeof(RAWINPUTDEVICE)):
            sys.exit(f"RegisterRawInputDevices failed: {ctypes.get_last_error()}")
        self.say(f"probe: listening (Python {sys.version.split()[0]}, Windows {sys.getwindowsversion().build}); "
                 f"log: {LOG}")
        self.user32.SetTimer(self.hwnd, 1, 250, None)  # wakes the loop for the 2 s report when idle

    def wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            now = time.perf_counter()
            try:
                self.on_input(lparam, now)
            except Exception as e:  # noqa: BLE001 - a probe must keep running and say what broke
                self.say(f"probe: error reading input: {e!r}")
        elif msg in (WM_CLOSE, WM_DESTROY):
            self.user32.PostQuitMessage(0)
            return 0
        return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def on_input(self, lparam, now):
        raw = RAWINPUT()
        size = wintypes.UINT(ctypes.sizeof(raw))
        got = self.user32.GetRawInputData(lparam, RID_INPUT, ctypes.byref(raw), ctypes.byref(size),
                                          ctypes.sizeof(RAWINPUTHEADER))
        if got in (0, 0xFFFFFFFF):
            return
        if raw.header.dwType == RIM_TYPEKEYBOARD:
            kb = raw.data.keyboard
            event = key_event(kb.MakeCode, kb.Flags)
            if event:
                self.keys += 1
                if event[2]:  # print presses only; releases are counted
                    name = EVDEV_NAMES.get(event[1], "?")
                    self.say(f"{now:12.4f}  key  {name:9} evdev {event[1]:3}  (scan 0x{kb.MakeCode:02X}"
                             f"{' E0' if kb.Flags & RI_KEY_E0 else ''}, vk 0x{kb.VKey:02X})")
        elif raw.header.dwType == RIM_TYPEMOUSE:
            m = raw.data.mouse
            for etype, code, value in mouse_events(m.usFlags, m.usButtonFlags, m.usButtonData, m.lLastX):
                if etype == EV_REL and code == REL_X:
                    self.moves.append(now)
                elif etype == EV_REL:
                    self.wheel += 1
                    self.say(f"{now:12.4f}  wheel {'up' if value > 0 else 'down'}")
                else:
                    self.keys += 1
                    if value:
                        self.say(f"{now:12.4f}  key  {EVDEV_NAMES[code]:9} evdev {code}")

    def report(self):
        now = time.perf_counter()
        name, inside = self.front()
        self.fronts.add(name)
        if now - self.last_report < 2:
            return
        gaps = [b - a for a, b in zip(self.moves, self.moves[1:])]
        gap = (f"gap med {statistics.median(gaps) * 1000:.1f} ms max {max(gaps) * 1000:.1f} ms"
               if gaps else "gap -")
        self.say(f"front: {name} ({'in window' if inside else 'cursor outside'})   keys {self.keys}   "
                 f"mouse {len(self.moves)} moves, {gap}   wheel {self.wheel}")
        self.reset()
        self.last_report = now

    def loop(self):
        msg = wintypes.MSG()
        while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            self.user32.TranslateMessage(ctypes.byref(msg))
            self.user32.DispatchMessageW(ctypes.byref(msg))
            self.report()


def main():
    if sys.platform != "win32":
        sys.exit("This probe is for Windows.")
    probe = Probe()
    probe.start()
    try:
        probe.loop()
    except KeyboardInterrupt:
        pass
    probe.say("probe: stopped")


if __name__ == "__main__":
    main()
