#!/usr/bin/env python3
"""Checks the Strafe Trainer's cue logic (trainer.Trainer) with synthetic key events, no game,
input service or sound. HOME and the XDG folders point into a temp folder.

Usage: python strafe-trainer/check_trainer.py   (exits 1 on the first failure)

Covers the overlap cue (Phase 11 in PLAN.md): it waits overlap_ticks, needs a jump key held,
obeys cue_overlap, outranks a wrong-key turn, and hands back without the overlap tone lingering
while the wrong-key turn is still under wrong_ticks. Also the wrong-key and no-key cues, each
cue's own wait (<cue>_ticks), and CueSounds: tone cues share one Tone at their own pitches, game-sound
cues play their own sound on every cue. Phase 12's split: trainer.run with a fake platform, and
trainer.py, store and settings_api importing without Pillow or fcntl (as in the Windows exe).
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

A, D, SPACE, TURN_L, TURN_R = 30, 32, 57, 272, 273
EV_KEY = 1
TICK = 0.01  # 100 tick


def fail(msg):
    sys.exit(f"FAIL: {msg}")


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def make(trainer, **cfg):
    roles = {"jump": {SPACE}, "strafe_left": {A}, "strafe_right": {D},
             "turn_left": {TURN_L}, "turn_right": {TURN_R}}
    states, cues = [], []
    t = trainer.Trainer({**trainer.TRAINER_DEFAULTS, **cfg}, roles, 100, lambda ticks: None,
                        lambda: cues.append(t.wrong_active), states.append)
    return t, states, cues


def press(t, when, *codes):
    for code in codes:
        t.feed(when, EV_KEY, code, 1)


def release(t, when, *codes):
    for code in codes:
        t.feed(when, EV_KEY, code, 0)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ.update(HOME=tmp, XDG_CONFIG_HOME=f"{tmp}/config", XDG_DATA_HOME=f"{tmp}/data",
                          XDG_CACHE_HOME=f"{tmp}/cache")
        sys.path.insert(0, str(HERE))
        import trainer

        expect({k: trainer.TRAINER_DEFAULTS[k] for k in ("cue_overlap", "overlap_ticks", "overlap_pitch",
                                                         "wrong_pitch", "none_pitch", "none_ticks")},
               {"cue_overlap": True, "overlap_ticks": 1, "overlap_pitch": 110, "wrong_pitch": 220,
                "none_pitch": 147, "none_ticks": 3}, "cue defaults")

        # overlap while jumping: cue after one tick, then off once a key is let go
        t, states, cues = make(trainer)
        press(t, 0.0, SPACE, A)
        press(t, 0.001, D)
        t.check(0.005)
        expect(states, [], "no cue before overlap_ticks")
        t.check(0.0015 + TICK)
        expect((states, cues), (["overlap"], ["overlap"]), "overlap cue after one tick")
        t.check(0.02)
        expect(cues, ["overlap"], "tone mode: one cue, no repeat")
        release(t, 0.03, A)
        t.check(0.031)
        expect(states, ["overlap", None], "overlap ends")

        # no jump key: no overlap cue
        t, states, cues = make(trainer)
        press(t, 0.0, A, D)
        t.check(0.5)
        expect(states, [], "overlap without a jump key")

        expect((trainer.TRAINER_DEFAULTS["when_jump"], trainer.TRAINER_DEFAULTS["when_timer"]), (True, True),
               "When defaults: both on")

        # when_timer: the running timer is enough, no jump key needed
        t, states, cues = make(trainer, when_timer=True)
        t.timer = True
        press(t, 0.0, A, D)
        t.check(0.5)
        expect(states, ["overlap"], "timer running: overlap without a jump key")
        t, states, cues = make(trainer, when_timer=True)
        press(t, 0.0, SPACE, A, D)
        t.check(0.5)
        expect(states, ["overlap"], "both on, timer off (saveloc): the jump key still counts")
        t, states, cues = make(trainer, when_jump=False, when_timer=True)
        press(t, 0.0, SPACE, A, D)
        t.check(0.5)
        expect(states, [], "timer only, timer off: a jump key alone is silent")
        t, states, cues = make(trainer, when_timer=True)
        t.timer, t.focused = True, False
        press(t, 0.0, A, D)
        t.check(0.5)
        expect(states, [], "timer running but in the pause menu: silent")

        # switched off
        t, states, cues = make(trainer, cue_overlap=False)
        press(t, 0.0, SPACE, A, D)
        t.check(0.5)
        expect(states, [], "cue_overlap off")

        # its own tick count
        t, states, cues = make(trainer, overlap_ticks=3)
        press(t, 0.0, SPACE, A, D)
        t.check(0.025)
        expect(states, [], "under overlap_ticks 3")
        t.check(0.031)
        expect(states, ["overlap"], "after overlap_ticks 3")

        # overlap outranks a wrong-key turn (turning left, D the newest strafe key)
        t, states, cues = make(trainer)
        press(t, 0.0, SPACE, TURN_L, A)
        press(t, 0.001, D)
        t.check(0.002)
        t.check(0.05)
        expect(states, ["overlap"], "overlap over wrong key")

        # hand-off: D let go while turning right with A held; the turn is wrong but under
        # wrong_ticks, so the overlap tone stops instead of lingering, then the wrong cue comes
        t, states, cues = make(trainer)
        press(t, 0.0, SPACE, TURN_R, D)
        press(t, 0.001, A)
        t.check(0.002)
        t.check(0.02)
        expect(states, ["overlap"], "hand-off: overlap first")
        release(t, 0.03, A, TURN_R)
        press(t, 0.03, TURN_L)
        release(t, 0.031, TURN_L)
        press(t, 0.031, TURN_R)
        t.check(0.032)
        # D still held, turning right: no cue at all
        expect(states, ["overlap", None], "hand-off: overlap ends cleanly")

        t, states, cues = make(trainer)
        press(t, 0.0, SPACE, TURN_R, D)
        press(t, 0.001, A)  # newest strafe key is A (left) while turning right
        t.check(0.002)
        t.check(0.02)
        release(t, 0.03, D)  # A alone: still wrong for the right turn, overlap over
        t.check(0.031)
        expect(states, ["overlap", None], "hand-off: tone off while under wrong_ticks")
        t.check(0.031 + 3 * TICK + 0.001)
        expect(states, ["overlap", None, "wrong"], "hand-off: wrong cue after wrong_ticks")

        # a long overlap: the wrong-key turn after it still waits its wrong_ticks
        t, states, cues = make(trainer)
        press(t, 0.0, SPACE, TURN_R, D)
        press(t, 0.001, A)
        for k in range(1, 100):
            t.check(0.002 * k)
        release(t, 0.2, D)
        t.check(0.201)
        expect(states, ["overlap", None], "long overlap: no wrong cue at once")
        t.check(0.201 + 3 * TICK + 0.001)
        expect(states, ["overlap", None, "wrong"], "long overlap: wrong cue after wrong_ticks")

        # wrong-key and no-key cues unchanged
        t, states, cues = make(trainer)
        press(t, 0.0, SPACE, TURN_L, D)
        t.check(0.0)
        t.check(0.025)
        expect(states, [], "wrong key under wrong_ticks")
        t.check(0.031)
        expect(states, ["wrong"], "wrong key")
        t, states, cues = make(trainer)
        press(t, 0.0, SPACE, TURN_L)
        t.check(0.0)
        t.check(0.031)
        expect(states, ["none"], "no key")
        # each cue waits its own ticks
        t, states, cues = make(trainer, wrong_ticks=1, none_ticks=6)
        press(t, 0.0, SPACE, TURN_L)
        t.check(0.0)
        t.check(0.031)
        expect(states, [], "no key under none_ticks 6")
        t.check(0.061)
        expect(states, ["none"], "no key after none_ticks 6")
        t, states, cues = make(trainer, wrong_ticks=1, none_ticks=6)
        press(t, 0.0, SPACE, TURN_L, D)
        t.check(0.0)
        t.check(0.011)
        expect(states, ["wrong"], "wrong key after wrong_ticks 1")

        # CueSounds: two tone cues at their pitches, one game sound
        made, played = [], []

        class FakeTone:
            def __init__(self, synth):
                made.append((synth.volume, synth.pitches))
                self.mode = None

            def start(self):
                pass

        cfg = {**trainer.TRAINER_DEFAULTS, "wrong_pitch": 300, "none_sound": "buttons/blip1.wav"}
        sounds = trainer.CueSounds(cfg, played.append, FakeTone)
        expect(made, [(0.3, {"wrong": 300, "overlap": 110})], "one tone for the tone cues")
        sounds.state("wrong")
        sounds.cue("wrong")
        expect((sounds.tone.mode, played), ("wrong", []), "tone cue: tone on, no game sound")
        sounds.state("none")
        sounds.cue("none")
        expect((sounds.tone.mode, played), (None, ["buttons/blip1.wav"]), "game-sound cue: tone off, sound plays")
        sounds.state(None)
        expect(sounds.tone.mode, None, "no cue: tone off")
        made.clear()
        quiet = trainer.CueSounds({**cfg, **{f"{c}_sound": "buttons/blip2.wav" for c in trainer.CUES}},
                                  played.append, FakeTone)
        expect((made, quiet.tone), ([], None), "no tone when no cue uses it")
        quiet.state("overlap")  # nothing to switch, nothing raised

        check_run(trainer, Path(tmp))
        check_neutral_import()
        check_tone_synth(trainer)
        check_windows_parts()
    print("check_trainer: all passed")


def check_tone_synth(trainer):
    """ToneSynth (shared by the Linux and Windows tone players): 5 ms chunks, silence when off,
    fades in, holds, cross-fades between cues and fades out without a jump at a chunk's edge, also
    when it comes back on mid-cycle."""
    import array
    import itertools
    synth = trainer.ToneSynth(0.5, {"wrong": 220, "none": 147})
    expect((synth.volume, synth.pitches), (0.5, {"wrong": 220, "none": 147}), "synth settings")
    chunks = [synth.next(m) for m in (None, "wrong", "wrong", "none", "none", None, "wrong", "wrong", None, None)]
    expect({len(c) for c in chunks}, {2 * synth.CHUNK}, "chunk size")
    expect((chunks[0], chunks[-1]), (synth.silence, synth.silence), "silence when off")
    samples = array.array("h", b"".join(chunks))
    biggest = max(abs(b - a) for a, b in itertools.pairwise(samples))
    expect(biggest < 0.5 * 32767 * 2 * 3.1416 * 220 / synth.RATE * 1.5, True,
           f"no click between chunks (largest step {biggest})")
    expect(max(samples) > 0.45 * 32767, True, "tone at its volume")


def check_windows_parts():
    """trainer_win's pure parts, checked on Linux: struct layouts as on 64-bit Windows, Raw Input
    key and mouse data to evdev events, and the focus check's folder test."""
    import ctypes

    import trainer_win as w
    sizes = {s.__name__: ctypes.sizeof(s) for s in (w.RAWINPUTHEADER, w.RAWMOUSE, w.RAWKEYBOARD,
                                                     w.RAWINPUT, w.RAWINPUTDEVICE, w.WAVEHDR, w.WAVEFORMATEX)}
    expect(sizes, {"RAWINPUTHEADER": 24, "RAWMOUSE": 24, "RAWKEYBOARD": 16, "RAWINPUT": 48,
                   "RAWINPUTDEVICE": 16, "WAVEHDR": 48, "WAVEFORMATEX": 20}, "Win64 struct sizes")
    expect((w.RAWMOUSE.usButtonFlags.offset, w.RAWMOUSE.lLastX.offset), (4, 12), "RAWMOUSE offsets")
    expect([w.key_event(0x1E, 0), w.key_event(0x20, 1), w.key_event(0x39, 0), w.key_event(0x38, 2),
            w.key_event(0x1D, 3), w.key_event(0x2A, 2)],
           [(1, A, 1), (1, D, 0), (1, SPACE, 1), (1, 100, 1), (1, 97, 0), None], "keys")
    expect([w.mouse_events(0, 0x0001, 0, 0), w.mouse_events(0, 0x0008, 0, 0), w.mouse_events(0, 0x0200, 0, 0),
            w.mouse_events(0, 0x0400, 0xFF88, 0), w.mouse_events(0, 0x0400, 120, -5), w.mouse_events(1, 0, 0, 9)],
           [[(1, TURN_L, 1)], [(1, TURN_R, 0)], [(1, 276, 0)], [(2, 8, -1)], [(2, 8, 1), (2, 0, -5)], []],
           "mouse")
    game = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Source"
    expect([w.files.in_folder(game + r"\cstrike_win64.exe", game.replace("\\", "/")),
            w.files.in_folder(game.upper() + r"\BIN\WIN64\X.EXE", game),
            w.files.in_folder(game + r" Beta\hl2.exe", game)], [True, True, False], "focus folder test")


def check_neutral_import():
    """The Windows exe has no Pillow and no fcntl/termios: the platform-neutral files must import
    without them (trainer_linux, which needs them, only loads on Linux)."""
    code = ("import sys\n"
            "for m in ('PIL', 'fcntl', 'termios', 'trainer_linux'):\n"
            "    sys.modules[m] = None\n"
            f"sys.path[:0] = [{str(HERE)!r}]\n"
            "import trainer, settings_api, trainer_win\n")
    done = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True)
    expect(done.stderr.strip().splitlines()[-1:], [], "trainer.py and trainer_win import without Pillow, fcntl or trainer_linux")


def check_run(trainer, tmp):
    """trainer.run with a fake platform (the Phase 12 split): binds read without the input service's
    filter, events fed in order, the overlap tone on, an offset drawn, everything closed at the end."""
    game_dir = tmp / "game"
    (game_dir / "cfg").mkdir(parents=True)
    (game_dir / "cfg" / "config.cfg").write_text(
        'bind "SPACE" "+jump"\nbind "a" "+moveleft"\nbind "d" "+moveright"\n'
        'bind "MOUSE1" "+left"\nbind "MOUSE2" "+right"\nbind "F13" "+jump"\n')
    trainer.settings = lambda game: {**trainer.TRAINER_DEFAULTS, "enabled": True}
    trainer.games.find = lambda game: game_dir
    log = []

    class FakeJoined:
        mode = "fake"

        def __init__(self, path):
            import queue
            self.events = queue.Queue()

        def close(self):
            log.append("session closed")

    trainer.session.join = FakeJoined

    class Tone:
        def __init__(self, synth):
            self._mode = None

        @property
        def mode(self):
            return self._mode

        @mode.setter
        def mode(self, value):
            if value != self._mode:
                log.append(f"tone {value}")
            self._mode = value

        def start(self):
            pass

        def close(self):
            log.append("tone closed")

    class Overlay:
        def show(self, text, row, x, y):
            log.append(f"offset {text} row {row}")

        def hide(self):
            pass

    # (clock, events) per read; 66 tick in CS:S, so overlap_ticks 1 is ~0.015 s
    script = [(1.000, [(1.000, EV_KEY, SPACE, 1), (1.000, EV_KEY, A, 1), (1.000, EV_KEY, D, 1)]),
              (1.010, []), (1.020, []),
              (1.100, [(1.100, EV_KEY, D, 0)]),
              (1.200, [(1.200, EV_KEY, TURN_R, 1)]),
              (1.230, [(1.230, EV_KEY, D, 1), (1.230, EV_KEY, A, 0)])]

    class Source:
        def read(self, timeout):
            if not script:
                return None
            platform.now, events = script.pop(0)
            return events

        def close(self):
            log.append("input closed")

    class Platform:
        FORWARDED_ONLY = False
        UNSEEN, GONE = "keys with no code", "input gone"
        now = 0.0

        def __init__(self):
            self.Tone = Tone

        def clock(self):
            return self.now

        def overlay(self, cfg):
            return Overlay()

        def open_input(self):
            return Source()

        def focus(self, game, game_dir):
            return type("Focus", (), {"focused": True})()

        def play(self, game_dir, sound, game):
            log.append(f"play {sound}")

    platform = Platform()
    expect(trainer.run("css", platform), 1, "run ends with 1 when the input is gone")
    expect(log, ["tone overlap", "tone None", "offset +2 row 2",
                 "tone closed", "input closed", "session closed"], "run with a fake platform")

    # stop set: returns 0 at once, still closes everything
    import threading
    stop = threading.Event()
    stop.set()
    log.clear()
    expect(trainer.run("css", platform, stop), 0, "run returns 0 when stopped")
    expect(log, ["tone closed", "input closed", "session closed"], "stopped run closes everything")

    # settings saved while it runs (the hub's Apply): a new pitch gives a new tone, which takes up
    # the cue still sounding; switched off it goes quiet without ending; switched on it sounds again
    saved = {"stamp": 0, "over": {}}
    trainer.settings = lambda game: {**trainer.TRAINER_DEFAULTS, "enabled": True, **saved["over"]}
    trainer.SettingsWatch.INTERVAL = 0
    trainer.SettingsWatch._stamp = staticmethod(lambda: saved["stamp"])

    def save(**over):
        saved["over"].update(over)
        saved["stamp"] += 1

    steps = [(1.000, [(1.000, EV_KEY, SPACE, 1), (1.000, EV_KEY, A, 1), (1.000, EV_KEY, TURN_R, 1)], None),
             (1.100, [], None),
             (1.200, [], lambda: save(wrong_pitch=300)),
             (1.300, [], lambda: save(enabled=False)),
             (1.400, [], lambda: save(enabled=True)),
             (1.500, [], lambda: save(hide_after=5.0))]

    class LiveSource(Source):
        def read(self, timeout):
            if not steps:
                return None
            platform.now, events, change = steps.pop(0)
            if change:
                change()
            return events

    # off at the game's start: waits without opening anything, then runs once it is switched on
    saved["over"] = {"enabled": False}
    stop = threading.Event()
    stop.set()
    log.clear()
    expect((trainer.run("css", platform, stop), log), (0, []), "off at the start and stopped: nothing opened")
    waits = []
    trainer.time.sleep = lambda seconds: (waits.append(seconds), save(enabled=True))
    platform.open_input = lambda: None
    expect((trainer.run("css", platform), len(waits)), (1, 1), "off at the start: runs once switched on")
    saved["over"] = {}

    platform.open_input = LiveSource
    log.clear()
    expect(trainer.run("css", platform), 1, "run with settings saved meanwhile ends when the input is gone")
    expect(log, ["tone wrong", "tone closed", "tone wrong", "tone None", "tone wrong",
                 "tone closed", "input closed", "session closed"],
           "saved settings apply while it runs: new tone, off, on; other settings keep the tone")


if __name__ == "__main__":
    main()
