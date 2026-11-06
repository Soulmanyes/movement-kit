#!/usr/bin/env python3
"""Checks the strafe trainer's cue logic (trainer.Trainer) with synthetic key events, no game,
input service or sound. HOME and the XDG folders point into a temp folder.

Usage: python sourceyaw/check_trainer.py   (exits 1 on the first failure)

Covers the overlap cue (Phase 11 in PLAN.md): it waits overlap_ticks, needs a jump key held,
obeys cue_overlap, outranks a wrong-key turn, and hands back without the overlap tone lingering
while the wrong-key turn is still under wrong_ticks. Also the wrong-key and no-key cues, each
cue's own wait (<cue>_ticks), and CueSounds: tone cues share one Tone at their own pitches, game-sound
cues play their own sound on every cue.
"""
import os
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
            def __init__(self, volume, pitches):
                made.append((volume, pitches))
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
    print("check_trainer: all passed")


if __name__ == "__main__":
    main()
