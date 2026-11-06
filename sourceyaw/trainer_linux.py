"""The strafe trainer's Linux side: everything trainer.run needs from the desktop (Phase 12 split).

  - keys and mouse from the Source Yaw input service (/run/sourceyaw-inputd.sock),
  - the offset number drawn by the Source Yaw overlay layer (overlay/), through a small
    shared state file and a digit atlas,
  - the constant tone through PipeWire (pw-cat), game sounds through yawcore.play_sound,
  - focus from Hyprland.

`Linux` bundles them as trainer.run's `platform`. trainer.py (platform-neutral) imports this
file only when it runs on Linux, so nothing here has to import on Windows.
"""

import fcntl
import glob
import json
import mmap
import os
import select
import shutil
import socket
import struct
import subprocess
import threading
import time

import yawcore

SOCKET = "/run/sourceyaw-inputd.sock"
OVERLAY_DIR = yawcore.CONFIG_DIR / "overlay"
ATLAS = OVERLAY_DIR / "atlas.png"
STATE = OVERLAY_DIR / "state"
EVENT = struct.Struct("<qIHHi")


# ---------------------------------------------------------------- overlay

def write_atlas(cfg):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:  # Linux only; check_modules' import rule accepts it this way
        raise RuntimeError("the offset display needs Pillow") from e
    fonts = (glob.glob("/usr/share/fonts/**/DejaVuSansMono-Bold.ttf", recursive=True)
             or glob.glob("/usr/share/fonts/**/*Mono*Bold*.ttf", recursive=True))
    px = max(8, int(cfg["size"]))
    font = ImageFont.truetype(fonts[0], px) if fonts else ImageFont.load_default()
    stroke = max(2, px // 16)
    _, top, _, bottom = font.getbbox("0123456789+-", stroke_width=stroke)
    cell_w = int(font.getlength("0")) + 2 * stroke + 2
    cell_h = int(bottom - top) + 2 * stroke + 2
    colours = [cfg["colors"][k] for k in ("early", "perfect", "late")]
    im = Image.new("RGBA", (cell_w * 12, cell_h * len(colours)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    for row, colour in enumerate(colours):
        for i, c in enumerate("0123456789+-"):
            draw.text((i * cell_w + cell_w / 2, row * cell_h + cell_h / 2), c, font=font,
                      fill=colour, anchor="mm", stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ATLAS.with_suffix(".tmp.png")
    im.save(tmp)
    tmp.replace(ATLAS)


class Overlay:
    """Writes the state the overlay layer reads every frame (see overlay/src/layer.c)."""
    FMT = struct.Struct("<IIIIIfff16s")

    def __init__(self):
        OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
        if not STATE.exists() or STATE.stat().st_size < self.FMT.size:
            STATE.write_bytes(b"\0" * self.FMT.size)
        self.file = open(STATE, "r+b")  # noqa: SIM115 - mapped for the overlay's whole life
        self.map = mmap.mmap(self.file.fileno(), self.FMT.size)
        self.seq = struct.unpack_from("<I", self.map, 4)[0] & ~1

    def show(self, text, row, x, y, visible=True):
        self.seq += 1
        struct.pack_into("<I", self.map, 4, self.seq)  # odd: being written
        self.map[:self.FMT.size] = self.FMT.pack(0x314F5953, self.seq, int(visible), row, 3,
                                                 x, y, 1.0, text.encode()[:15])
        self.seq += 1
        struct.pack_into("<I", self.map, 4, self.seq)

    def hide(self):
        self.show("", 0, 0.5, 0.5, visible=False)


# ---------------------------------------------------------------- constant tone

class Tone:
    """A tone that sounds while `mode` is set (a cue: "wrong", "none", "overlap"; None for
    silence), streamed to PipeWire through pw-cat. `synth` is the trainer.ToneSynth giving the samples.

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
        except OSError:
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


# ---------------------------------------------------------------- focus

class FocusWatch:
    """Whether the game's window has focus, asked from Hyprland every 0.25 s.

    The input service sees every key and mouse movement on the desktop, so
    without this, scrolling in a browser while the game runs in the background
    would count as jumping. With follow_mouse = 2 the game keeps keyboard focus
    while the wheel scrolls the window under the cursor, so the cursor must be
    inside the game's window too. Other desktops have no common way to ask, so
    there the game counts as focused."""
    INTERVAL = 0.25

    def __init__(self, process):
        self.process = process
        self.focused = True
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        self.path = os.path.join(runtime, "hypr", sig, ".socket.sock") if runtime and sig else None
        if self.path and os.path.exists(self.path):
            threading.Thread(target=self._watch, daemon=True).start()

    def _ask(self, command):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(self.path)
            s.sendall(command)
            data = b""
            while chunk := s.recv(65536):
                data += chunk
        return json.loads(data or b"{}") or {}

    def _check(self):
        window = self._ask(b"j/activewindow")
        with open(f"/proc/{window.get('pid')}/comm") as f:
            if f.read().strip() != self.process:
                return False
        cursor = self._ask(b"j/cursorpos")
        (x, y), (w, h) = window["at"], window["size"]
        return x <= cursor["x"] < x + w and y <= cursor["y"] < y + h

    def _watch(self):
        while True:
            try:
                self.focused = self._check()
            except (OSError, ValueError, TypeError, KeyError):
                self.focused = False
            time.sleep(self.INTERVAL)


# ---------------------------------------------------------------- input

class InputSocket:
    """The input service's event stream: evdev's (time, type, code, value), time in wall-clock seconds."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(SOCKET)
        self.buf = b""

    def read(self, timeout):
        """The events that came within `timeout` seconds (maybe none), or None once the service is gone."""
        ready, _, _ = select.select([self.sock], [], [], timeout)
        if not ready:
            return []
        data = self.sock.recv(4096)
        if not data:
            return None
        self.buf += data
        events = []
        while len(self.buf) >= EVENT.size:
            sec, usec, etype, code, value = EVENT.unpack_from(self.buf)
            self.buf = self.buf[EVENT.size:]
            events.append((sec + usec / 1e6, etype, code, value))
        return events

    def close(self):
        self.sock.close()


# ---------------------------------------------------------------- the platform

class Linux:
    """trainer.run's `platform` on Linux."""
    FORWARDED_ONLY = True       # only keys in the input service's config reach the trainer
    UNSEEN = "keys the input service does not forward"
    GONE = "input service went away"
    Tone = Tone
    clock = staticmethod(time.time)  # the input service stamps events with the wall clock

    def overlay(self, cfg):
        """Where the offset is drawn: an object with show(text, row, x, y) and hide()."""
        write_atlas(cfg)
        overlay = Overlay()
        overlay.hide()
        return overlay

    def open_input(self):
        """The event source (read(timeout), close()), or None after printing why there isn't one."""
        try:
            return InputSocket()
        except OSError as e:
            print(f"trainer: no input service ({e}); install it from Source Yaw", flush=True)
            return None

    def focus(self, game, game_dir):
        return FocusWatch(yawcore.GAMES[game]["process"])

    def play(self, game_dir, sound, game):
        return yawcore.play_sound(game_dir, sound, game)
