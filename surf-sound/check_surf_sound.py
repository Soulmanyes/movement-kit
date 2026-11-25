"""Checks Surf Sound's install.py, module hooks, settings, noise synth and sound runner on a fake game folder.

- install: the script is in custom/movekit-surf-sound, the kit's timer.xml includes it once (no
  hud_default.kv3 copy: it needs no customizer entry), the autoexec block turns the console log on and
  hides MK_ markers, the Linux launch hook is registered; installing again changes nothing.
- another tool's timer.xml include is kept; uninstall takes everything of its own out, a failed sync
  keeps the script, with no game found it still removes the launch hook. The module hooks do the same.
- settings.py: bad values are refused, the volume clamped, its sound names = noise.SOUNDS; the hub
  section's apply saves them.
- noise.NoiseSynth: whole chunks at the player's size, silence when off, a seamless loop (the join is no
  louder a step than the rest), the ceiling variant brighter than the ramp one, fades with no jump.
- the sound runner (sound_run.py): RAMP/CEIL/OFF markers set the player's mode, the ramp/ceiling switches,
  map_left and QUIET silence it, the beat keeps it on, a settings change rebuilds or closes it, and run()
  reads the markers from a growing log.

The detection logic is checked by check_surf_sound.js.

Usage: python surf-sound/check_surf_sound.py   (exits 1 on a failure)
"""
import array
import math
import os
import re
import sys
import tempfile
import threading
import time
import wave
from itertools import pairwise
from pathlib import Path
from typing import ClassVar

HERE = Path(__file__).resolve().parent
KIT = HERE.parent

TIMER = "<root>\n\t<scripts>\n\t\t<include type=\"module\" src=\"file://{scripts}/hud/timer.ts\" />\n\t</scripts>\n</root>\n"
OTHER = [{"file": "panorama/layout/hud/timer.xml", "before": "</scripts>", "line": '<include src="other.ts" />'}]
INCLUDE = '<include type="module" src="file://{scripts}/hud/movekit-surf-sound.ts" />'


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def expect(got, want, what):
    if got != want:
        fail(f"{what}: got {got!r}, want {want!r}")


def fake_game(root):
    game = root / "momentum"
    (game / "panorama/layout/hud").mkdir(parents=True)
    (game / "panorama/layout/hud/timer.xml").write_text(TIMER)
    (game / "cfg/hud").mkdir(parents=True)
    return game


def check_settings(sett, hub, noise):
    expect(tuple(noise.SOUNDS), sett.SOUND_NAMES, "settings' sound names = noise.SOUNDS")
    expect(sett.DEFAULTS["sound"], next(iter(noise.SOUNDS)), "the default sound is the first")
    for bad in ({"on": 1}, {"ramp": None},
                {"sound": "beep"}, []):
        try:
            sett.check(bad)
            fail(f"settings.check took {bad!r}")
        except ValueError:
            pass
    expect(sett.check({"volume": 5})["levels"], dict.fromkeys(sett.SLOTS, 80),
           "a volume saved before 1.2.0 is dropped: every sound at 80")
    expect("volume" in sett.check({"volume": 50}), False, "no main volume saved")
    expect(sett.load(), sett.DEFAULTS, "no saved file: defaults")
    sett.file().parent.mkdir(parents=True, exist_ok=True)
    sett.file().write_text("{broken")
    expect(sett.load(), sett.DEFAULTS, "unreadable file: defaults")
    section = hub.local_import(HERE / "hub_section.py", "hub_section")
    for bad in ({"custom": []}, {"custom": {"door": {"file": "wall-0123456789ab.wav", "name": "x"}}},
                {"custom": {"wall": {"file": "../../evil.wav", "name": "x"}}},
                {"custom": {"wall": {"file": "bonk-0123456789ab.wav", "name": "x"}}},
                {"custom": {"wall": {"file": "wall-0123456789ab.wav"}}}, {"graze": "yes"}, {"levels": []},
                {"levels": {"door": 50}}, {"levels": {"wall": "50"}}, {"levels": {"bonk": True}}):
        try:
            sett.check(bad)
            fail(f"settings.check took {bad!r}")
        except ValueError:
            pass
    expect([sett.check({"bonk": False})["graze"], sett.check({"bonk": False, "graze": True})["graze"],
            sett.check({})["graze"]], [False, True, True],
           "light head hits: saved before their own switch, they follow head hits; their own switch wins")
    expect(sett.check({"levels": {"wall": 250, "bonk": -5, "ramp": 42.4}})["levels"],
           {"ramp": 42, "ceiling": 80, "wall": 100, "graze": 80, "bonk": 0, "jump": 80},
           "levels: each sound's own volume, clamped, the rest 80")
    expect(sett.levels(sett.check({"levels": {"graze": 50}}))["graze"], 0.5, "levels() as 0-1")
    expect([sett.DEFAULTS["jump"], sett.check({"bonk": True})["jump"]], [False, False],
           "jumps off by default and in settings saved before 1.4.0")
    expect(sett.check({"custom": {"jump": {"file": "jump-0123456789ab.wav", "name": "hop.wav"}}})["custom"],
           {"jump": {"file": "jump-0123456789ab.wav", "name": "hop.wav"}}, "a custom jump sound")
    want = {"on": True, "sound": "grind", "ramp": True, "ceiling": False, "wall": False, "graze": True,
            "bonk": True, "jump": True, "watch": False, "custom": {},
            "levels": {"ramp": 35, "ceiling": 60, "wall": 100, "graze": 80, "bonk": 40, "jump": 60}}
    data = section.apply(want)
    expect(data["sound"], want, "apply returns the saved settings")
    expect([k for k, _ in data["sounds"]], list(sett.SOUND_NAMES), "load lists the sounds")
    expect(sett.load(), want, "apply saved the settings")
    try:
        section.apply({"sound": "beep"})
        fail("apply took a bad sound")
    except ValueError:
        pass
    expect(sett.load(), want, "a refused apply keeps the saved settings")
    try:
        section.preview("wind", "floor")
        fail("preview took a bad kind")
    except ValueError:
        pass


def samples(b):
    return array.array("h", b).tolist()


def check_synth(noise):
    syn = noise.NoiseSynth(0.5, {"ramp": "wind", "ceiling": "wind"})
    expect(len(syn.next(None)), 2 * syn.CHUNK, "a chunk is CHUNK samples")
    expect(syn.next(None), syn.silence, "silence when off")
    for name in noise.SOUNDS:
        for kind in ("ramp", "ceiling"):
            loop = noise.render(name, kind)
            expect(len(loop) % noise.CHUNK, 0, f"{name}/{kind}: whole chunks")
            steps = [abs(b - a) for a, b in pairwise(loop)]
            join = abs(loop[0] - loop[-1])
            if join > 4 * max(steps):
                fail(f"{name}/{kind}: the loop's join jumps {join:.3f}, the largest step inside is {max(steps):.3f}")

    # constant loudness across the join: 50 ms windows around it within 1.5 dB of the loop's median
    # (the sounds without a designed swell or flutter)
    win = noise.RATE // 20
    for name in ("hiss", "rumble"):
        loop = noise.render(name, "ramp")
        twice = loop + loop

        def rms_db(xs):
            return 10 * math.log10(sum(x * x for x in xs) / len(xs))
        levels = sorted(rms_db(loop[i:i + win]) for i in range(0, len(loop) - win, win))
        median = levels[len(levels) // 2]
        seam = int(noise.RATE * noise.SEAM_S)
        for start in range(len(loop) - seam, len(loop) + seam, win // 2):
            db = rms_db(twice[start:start + win])
            if abs(db - median) > 1.5 + (3 if name == "rumble" else 0):
                fail(f"{name}: {db - median:+.1f} dB at the loop's join")

    # a sound from silence starts at the loop's loud start: wind's first 200 ms is louder than 3/4 of the loop
    # (grind's flutter is too fast to matter)
    for name in ("wind",):
        loop = noise.render(name, "ramp")
        w = 4 * win  # 200 ms: long enough that the noise itself evens out
        start = sum(x * x for x in loop[:w]) / w
        windows = sorted(sum(x * x for x in loop[i:i + w]) / w for i in range(0, len(loop) - w, w))
        if start < windows[len(windows) * 3 // 4]:
            fail(f"{name}: the loop starts in a quiet part")
    for name in noise.SOUNDS:
        peak = max(abs(x) for kind in ("ramp", "ceiling") for x in noise.render(name, kind))
        if peak > noise.PEAK + 1e-9:
            fail(f"{name}: peaks at {peak:.2f} of full scale, over PEAK")
    # the recording fills the loop and its seam without repeating
    expect(len(noise._recording("stone-dragging.wav")) >= int(noise.RATE * (noise.LOOP_S + noise.SEAM_S)), True,
           "stone-dragging.wav covers LOOP_S + SEAM_S")
    syn2 = noise.NoiseSynth(0.5, {"ramp": "wind"})
    for _ in range(123):
        syn2.next(None)
    for _ in range(40):
        syn2.next("ramp")
    for _ in range(60):
        syn2.next(None)
    syn2.next("ramp")
    expect(syn2.pos["ramp"], noise.CHUNK, "from silence the loop plays from its start")
    # hits: mixed on top of the loop, then gone; a synth with no loops plays them from silence
    syn3 = noise.NoiseSynth(0.5, {"ramp": "wind"})
    for _ in range(10):
        syn3.next("ramp")
    plain = samples(syn3.loop_bytes["ramp"])
    syn3.hit("wall3")
    start = syn3.pos["ramp"]
    mixed = samples(syn3.next("ramp"))
    expect(mixed != plain[start:start + noise.CHUNK], True, "a hit changes the chunk")
    for _ in range(200):
        syn3.next("ramp")
    expect(syn3.playing, [], "a hit ends")
    start = syn3.pos["ramp"]
    expect(samples(syn3.next("ramp")), plain[start:start + noise.CHUNK], "after a hit: the steady loop again")
    for name in noise.HITS:
        lone = noise.NoiseSynth(1.0, {})
        lone.hit(name)
        out = [x for _ in range(200) for x in samples(lone.next(None))]
        peak = max(map(abs, out))
        want = noise.HIT_PEAK * noise.HIT_SOUNDS[name][1] * 32767
        if not 0.97 * want < peak < min(1.03 * want, 32767):
            fail(f"{name} at volume 1 peaks at {peak}, not {want:.0f}")
        expect(out[-noise.CHUNK:], [0] * noise.CHUNK, f"{name} ends in silence")
    walls = []
    for name in ("wall1", "wall2", "wall3"):
        s = noise.NoiseSynth(1.0, {})
        s.hit(name)
        walls.append(max(abs(x) for _ in range(20) for x in samples(s.next(None))))
    expect(walls == sorted(walls) and walls[0] < walls[2] * 0.6, True, f"wall strengths get louder: {walls}")
    # levels: each sound scaled on its own, the product capped at full volume
    base = noise.NoiseSynth(0.4, {"ramp": "wind", "ceiling": "wind"})
    lv = noise.NoiseSynth(0.4, {"ramp": "wind", "ceiling": "wind"},
                          levels={"ramp": 0.5, "ceiling": 1.0, "wall": 2.0, "graze": 1.0, "bonk": 0.0})
    peak = lambda xs: max(map(abs, xs))
    expect([round(peak(lv.loops["ramp"]) / peak(base.loops["ramp"]), 3),
            round(peak(lv.loops["ceiling"]) / peak(base.loops["ceiling"]), 3),
            round(peak(lv.hit_sounds["wall3"]) / peak(base.hit_sounds["wall3"]), 3),
            round(peak(lv.hit_sounds["wall1"]) / peak(base.hit_sounds["wall1"]), 3),
            peak(lv.hit_sounds["bonk"]), lv.hit_sounds["graze"] == base.hit_sounds["graze"]],
           [0.5, 1.0, 2.0, 2.0, 0.0, True], "levels scale each loop and hit on their own")
    capped = noise.NoiseSynth(0.8, {"ramp": "wind"}, levels={"ramp": 2.0, "wall": 2.0})
    full = noise.NoiseSynth(1.0, {"ramp": "wind"})
    expect([capped.loops["ramp"] == full.loops["ramp"], capped.hit_sounds["wall3"] == full.hit_sounds["wall3"]],
           [True, True], "a level past full volume plays at full volume")
    # at full volume a hit on a loud loop (and two hits at once) stays under LIMIT: no samples cut flat
    top = int(noise.LIMIT * 32767) + 1
    for snd in noise.SOUNDS:
        loud = noise.NoiseSynth(1.0, {"ramp": snd})
        for _ in range(10):
            loud.next("ramp")
        loud.hit("wall3")
        loud.hit("bonk")
        out = [x for _ in range(200) for x in samples(loud.next("ramp"))]
        if max(map(abs, out)) > top:
            fail(f"{snd} with two hits at volume 1 peaks at {max(map(abs, out))}, over the limit {top}")
        expect(loud.limit_gain, 1.0, f"{snd}: the limiter's gain back to 1 after the hits")
        start = loud.pos["ramp"]
        loop = samples(loud.loop_bytes["ramp"])
        expect(samples(loud.next("ramp")), loop[start:start + noise.CHUNK], f"{snd}: after the limiter, the steady loop")
    try:
        lone.hit("door")
        fail("hit took a bad name")
    except ValueError:
        pass
    expect(noise.player_class().LEAD if sys.platform != "win32" else 0.005, 0.005, "the Linux player queues 5 ms")

    def brightness(xs):  # mean step size over RMS: higher for higher frequencies
        rms = (sum(x * x for x in xs) / len(xs)) ** 0.5
        return sum(abs(b - a) for a, b in pairwise(xs)) / len(xs) / rms
    for name in noise.SOUNDS:
        r, c = brightness(noise.render(name, "ramp")), brightness(noise.render(name, "ceiling"))
        if not c > r * 1.2:
            fail(f"{name}: the ceiling variant isn't brighter ({c:.3f} vs {r:.3f})")
    # fade in, steady, cross-fade, fade out: no sample jumps more than the sound itself does
    out = []
    for mode, n in ((None, 5), ("ramp", 40), ("ceiling", 40), (None, 40)):
        out += [x for _ in range(n) for x in samples(syn.next(mode))]
    biggest = max(abs(b - a) for kind in ("ramp", "ceiling") for a, b in pairwise(samples(syn.loop_bytes[kind])))
    worst = max(abs(b - a) for a, b in pairwise(out))
    if worst > 1.5 * biggest:
        fail(f"a switch clicks: a step of {worst} against {biggest} in the steady sound")
    expect(out[-syn.CHUNK:], [0] * syn.CHUNK, "faded out to silence")
    expect(any(out[5 * syn.CHUNK + 30 * syn.CHUNK:]), True, "sounds while on")


class FakePlayer:
    made: ClassVar[list] = []

    def __init__(self, synth):
        self.synth, self.mode, self.started, self.closed = synth, None, False, False
        FakePlayer.made.append(self)

    def start(self):
        self.started = True

    def close(self):
        self.closed = True


class FakeSynth:
    def __init__(self, volume, sounds, custom=None, levels=None):
        self.volume, self.sounds, self.custom, self.levels, self.hits = volume, sounds, custom, levels, []

    def hit(self, name):
        self.hits.append(name)


def check_runner(sett, hub, tmp):
    sr = hub.local_import(HERE / "sound_run.py", "sound_run")
    clock = [100.0]
    sett.save({"on": True, "sound": "wind", "ramp": True, "ceiling": True, "levels": {"wall": 50}})
    FakePlayer.made = []
    r = sr.Runner(sett, FakePlayer, FakeSynth, clock=lambda: clock[0])
    r.reload()
    p = FakePlayer.made[-1]
    expect([p.started, p.mode, p.synth.sounds, p.synth.volume], [True, None, {"ramp": "wind", "ceiling": "wind"}, 1.0],
           "player made from the settings, silent")
    expect(p.synth.levels, {**dict.fromkeys(sett.SLOTS, 0.8), "wall": 0.5}, "each sound's volume reaches the synth")

    def token(name):
        return {"type": "token", "data": {"name": name}}
    r.handle(token("MK_SURFSND_RAMP"))
    expect(p.mode, "ramp", "RAMP: ramp sound")
    r.handle(token("MK_SURFSND_CEIL"))
    expect(p.mode, "ceiling", "CEIL: ceiling sound")
    r.handle(token("MK_SURFSND_OFF"))
    expect(p.mode, None, "OFF: silent")
    r.handle(token("MK_SURFSND_RAMP"))
    r.handle({"type": "map_left", "data": {}})
    expect(p.mode, None, "map_left: silent")
    # a long surf: the beat keeps it on well past QUIET
    r.handle(token("MK_SURFSND_RAMP"))
    for _ in range(20):
        clock[0] += 0.5
        r.handle(token("MK_SURFSND_RAMP"))
        r.tick()
    expect(p.mode, "ramp", "a 10 s surf with the beat stays on")
    clock[0] += sr.QUIET - 0.1
    r.tick()
    expect(p.mode, "ramp", "still on before QUIET")
    clock[0] += 0.2
    r.tick()
    expect(p.mode, None, "silent after QUIET without a marker")
    # ceilings off: the player only has the ramp, CEIL is silent
    sett.save({"on": True, "sound": "hiss", "ramp": True, "ceiling": False})
    clock[0] += sr.SETTINGS_EVERY
    r.reload()
    p2 = FakePlayer.made[-1]
    expect([p.closed, p2.synth.sounds], [True, {"ramp": "hiss"}], "a settings change: old player closed, new one built")
    r.handle(token("MK_SURFSND_CEIL"))
    expect(p2.mode, None, "ceilings off: CEIL is silent")
    r.handle(token("MK_SURFSND_RAMP"))
    expect(p2.mode, "ramp", "ceilings off: RAMP still plays")
    # hits: one-shots on the synth, the constant sound and its timeout untouched
    heard = r.heard
    for name in ("MK_SURFSND_WALL1", "MK_SURFSND_WALL3", "MK_SURFSND_GRAZE", "MK_SURFSND_BONK"):
        clock[0] += 0.1
        r.handle(token(name))
    expect([p2.synth.hits, p2.mode, r.heard], [["wall1", "wall3", "graze", "bonk"], "ramp", heard],
           "hits played on top, the sound and its QUIET clock as they were")
    r.handle(token("MK_SURFSND_JUMP"))
    expect(p2.synth.hits[-1], "bonk", "jumps off (the default): JUMP is silent")
    unread = [m for name in sr.HITS for m in ("MK_" + name, "MK_" + name + "W")
              if not any(re.fullmatch(t, m) for t in sr.TOKENS)]
    expect(unread, [], "every hit marker, W too, is a token the session reads")
    r.handle(token("MK_SURFSND_OFF"))
    r.handle(token("MK_SURFSND_WALL2"))
    expect([p2.synth.hits[-1], p2.mode], ["wall2", None], "a hit plays with no constant sound")
    sett.save({"on": True, "sound": "hiss", "ramp": False, "ceiling": False, "wall": False, "bonk": True})
    clock[0] += sr.SETTINGS_EVERY
    r.reload()
    p3 = FakePlayer.made[-1]
    expect([p3.started, p3.synth.sounds], [True, {}], "only hits on: a player with no loops")
    r.handle(token("MK_SURFSND_WALL2"))
    r.handle(token("MK_SURFSND_GRAZE"))
    r.handle(token("MK_SURFSND_BONK"))
    expect(p3.synth.hits, ["graze", "bonk"], "wall hits off: only head hits play (a light one too)")
    sett.save({"on": True, "sound": "hiss", "ramp": False, "ceiling": False, "wall": False,
               "graze": False, "bonk": True,
               "custom": {"bonk": {"file": "bonk-0123456789ab.wav", "name": "mine.wav"}}})
    clock[0] += sr.SETTINGS_EVERY
    r.reload()
    p3 = FakePlayer.made[-1]
    r.handle(token("MK_SURFSND_GRAZE"))
    r.handle(token("MK_SURFSND_BONK"))
    expect([p3.synth.hits, p3.synth.custom], [["bonk"], {"bonk": sett.sounds_dir() / "bonk-0123456789ab.wav"}],
           "light head hits off: only hard ones; the custom sound reaches the synth")
    sett.save({"on": True, "sound": "hiss", "ramp": False, "ceiling": False, "wall": False,
               "graze": False, "bonk": False, "jump": True})
    clock[0] += sr.SETTINGS_EVERY
    r.reload()
    p3 = FakePlayer.made[-1]
    r.handle(token("MK_SURFSND_BONK"))
    r.handle(token("MK_SURFSND_JUMP"))
    r.handle(token("MK_SURFSND_JUMPW"))
    expect([r.sound is p3, p3.synth.hits], [True, ["jump", "jump"]], "only jumps on: a player, JUMP and JUMPW play")
    sett.save({"on": True, "sound": "hiss", "ramp": False, "ceiling": False, "wall": False,
               "graze": False, "bonk": False})
    clock[0] += sr.SETTINGS_EVERY
    r.reload()
    expect(r.sound, None, "every sound off: no player")
    # watching: the W markers play like the plain ones with "watch" on, and are muted with it off
    sett.save({"on": True, "sound": "hiss", "ramp": True, "ceiling": True})
    clock[0] += sr.SETTINGS_EVERY
    r.reload()
    p4 = FakePlayer.made[-1]
    r.handle(token("MK_SURFSND_CEILW"))
    r.handle(token("MK_SURFSND_BONKW"))
    expect([p4.mode, p4.synth.hits], ["ceiling", ["bonk"]], "watching, watch on: CEILW and BONKW play")
    sett.save({"on": True, "sound": "hiss", "ramp": True, "ceiling": True, "watch": False})
    clock[0] += sr.SETTINGS_EVERY
    r.reload()
    p5 = FakePlayer.made[-1]
    r.handle(token("MK_SURFSND_RAMP"))
    r.handle(token("MK_SURFSND_RAMPW"))
    r.handle(token("MK_SURFSND_WALL3W"))
    r.handle(token("MK_SURFSND_JUMPW"))
    expect([p5.mode, p5.synth.hits], [None, []], "watch off: RAMPW stops the sound, WALL3W and JUMPW are muted")
    r.handle(token("MK_SURFSND_RAMP"))
    r.handle(token("MK_SURFSND_WALL3"))
    expect([p5.mode, p5.synth.hits], ["ramp", ["wall3"]], "watch off: own play still plays")
    r.handle(token("MK_SURFSND_RAMP"))  # surfing again, for the checks below
    # a settings change mid-surf keeps sounding
    sett.save({"on": True, "sound": "rumble", "ramp": True, "ceiling": False})
    clock[0] += sr.SETTINGS_EVERY
    r.reload()
    expect(FakePlayer.made[-1].mode, "ramp", "a new sound mid-surf is on at once")
    sett.save({"on": False, "sound": "rumble", "ramp": True, "ceiling": True})
    clock[0] += sr.SETTINGS_EVERY
    r.reload()
    expect([FakePlayer.made[-1].closed, r.sound], [True, None], "switched off: the player closed")
    r.handle(token("MK_SURFSND_RAMP"))  # nothing to sound, no error
    r.tick()
    r.close()

    # run() on a log: markers as the game writes them, in a thread
    sett.save({"on": True, "sound": "wind", "ramp": True, "ceiling": True, "levels": {"wall": 50}})
    log = tmp / "yaw.log"
    log.write_text("old line MK_SURFSND_RAMP\n")  # an earlier game run: skipped
    FakePlayer.made = []
    stop = threading.Event()
    th = threading.Thread(target=sr.run, args=(log, stop, FakePlayer, 0.002))
    th.start()

    def wait_for(mode, what):
        end = time.monotonic() + 3
        while time.monotonic() < end:
            if FakePlayer.made and FakePlayer.made[-1].mode == mode:
                return
            time.sleep(0.005)
        fail(f"run: {what}")
    try:
        end = time.monotonic() + 5
        while not FakePlayer.made and time.monotonic() < end:  # the real synth renders first
            time.sleep(0.01)
        time.sleep(0.1)
        expect(FakePlayer.made[-1].mode, None, "run: the old log's marker is skipped")
        # RAMPW is a token of its own (TOKENS): it plays after an OFF
        for line, mode in (("MK_SURFSND_RAMP", "ramp"), ("MK_SURFSND_CEIL", "ceiling"), ("MK_SURFSND_OFF", None),
                           ("MK_SURFSND_RAMPW", "ramp"), ("MK_SURFSND_OFF", None)):
            with log.open("a") as f:
                f.write(f"[panorama] {line}\n")
            wait_for(mode, f"{line} in the log didn't set {mode}")
    finally:
        stop.set()
        th.join(3)
    expect([th.is_alive(), FakePlayer.made[-1].closed], [False, True], "run: stops and closes the player")


def write_wav(path, frames, channels=1, width=2, rate=48000):
    """A WAV of `frames` (a list of per-frame tuples of floats -1..1)."""
    out = bytearray()
    for frame in frames:
        for x in frame:
            v = round(x * (2 ** (8 * width - 1) - 1))
            out += bytes([v + 128]) if width == 1 else v.to_bytes(width, "little", signed=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(bytes(out))


def check_custom(sett, hub, noise, tmp):
    """Custom sounds: custom.py's conversion, the synth's use of them and its fallback, the hub's pick."""
    custom = hub.local_import(HERE / "custom.py", "custom")
    src = tmp / "picked"
    src.mkdir()
    # a 24-bit stereo 44.1 kHz WAV: mono, 48 kHz, 16-bit, its two channels averaged
    tone_s = 1.5
    frames = [(0.5 * math.sin(2 * math.pi * 440 * i / 44100), 0.1) for i in range(int(44100 * tone_s))]
    write_wav(src / "loop 24.wav", frames, channels=2, width=3, rate=44100)
    entry = custom.make(src / "loop 24.wav", "ramp")
    expect(entry["name"], "loop 24.wav", "the custom entry keeps the picked file's name")
    expect(bool(sett.FILE_RE.fullmatch(entry["file"])) and entry["file"].startswith("ramp-"), True,
           f"stored as ramp-<hash>.wav: {entry['file']}")
    with wave.open(str(sett.sounds_dir() / entry["file"])) as w:
        expect((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, noise.RATE), "converted to 16-bit mono 48 kHz")
        expect(abs(w.getnframes() - noise.RATE * tone_s) < 4, True, f"length kept through resampling: {w.getnframes()}")
        xs = array.array("h", w.readframes(w.getnframes()))
    expect(abs(sum(xs) / len(xs) / 32767 - 0.99 * 0.05 / 0.3) < 0.01, True, "channels averaged (the 0.1 offset halved)")
    expect(custom.make(src / "loop 24.wav", "ramp"), entry, "the same file again: the same stored file")
    # 8-bit (unsigned) reads too
    write_wav(src / "u8.wav", [(0.8 * math.sin(i / 7),) for i in range(48000 * 2)], width=1)
    custom.make(src / "u8.wav", "ceiling")
    # a hit: the silence before it trimmed, anything past HIT_MAX_S cut
    hit = [(0.0,)] * 4800 + [(0.9 * math.sin(i / 3),) for i in range(48000 * 3)]
    write_wav(src / "late hit.wav", hit)
    h = custom.make(src / "late hit.wav", "bonk")
    with wave.open(str(sett.sounds_dir() / h["file"])) as w:
        n = w.getnframes()
        head = array.array("h", w.readframes(200))
    expect(n, int(noise.RATE * custom.HIT_MAX_S), "a long hit is cut to HIT_MAX_S")
    expect(max(map(abs, head[:150])) > 1000, True, "the silence before a hit is trimmed (LEAD_S kept)")
    for name, frames, why in (("short.wav", [(0.5,)] * 24000, "a loop under LOOP_MIN_S"),
                              ("silent.wav", [(0.0,)] * 96000, "a silent file")):
        write_wav(src / name, frames)
        try:
            custom.make(src / name, "ramp")
            fail(f"custom.make took {why}")
        except ValueError:
            pass
    (src / "song.mp3").write_bytes(b"ID3 not really")
    which = custom.shutil.which
    custom.shutil.which = lambda _name: None
    try:
        custom.make(src / "song.mp3", "wall")
        fail("custom.make took an MP3 without ffmpeg")
    except ValueError as e:
        expect("ffmpeg" in str(e) and "WAV" in str(e), True, f"without ffmpeg the error asks for a WAV: {e}")
    finally:
        custom.shutil.which = which
    try:
        custom.make(src / "u8.wav", "door")
        fail("custom.make took a bad slot")
    except ValueError:
        pass
    # the synth: custom loops of their own lengths, a custom hit, and a bad file falls back
    files = {"ramp": sett.sounds_dir() / entry["file"], "bonk": sett.sounds_dir() / h["file"]}
    syn = noise.NoiseSynth(0.5, {"ramp": "wind", "ceiling": "wind"}, files)
    expect(syn.length["ramp"] != syn.length["ceiling"], True, "a custom loop keeps its own length")
    expect(len(syn.hit_sounds["bonk"]), int(noise.RATE * custom.HIT_MAX_S), "the custom hit replaces the goofy bonk")
    expect(syn.hit_sounds["graze"] == noise.NoiseSynth(0.5, {}).hit_sounds["graze"], True,
           "a light head hit without its own file or a custom wall stays the built-in one")
    out = [x for _ in range(2 * syn.length["ramp"] // noise.CHUNK) for x in samples(syn.next("ramp"))]
    steps = [abs(b - a) for a, b in pairwise(out)]
    expect(max(steps) < 6000, True, f"a custom loop repeats without a jump (largest step {max(steps)})")
    for _ in range(40):  # ramp to ceiling and back: both loops at their own positions, no jump
        out += samples(syn.next("ceiling"))
    for _ in range(40):
        out += samples(syn.next("ramp"))
    steps = [abs(b - a) for a, b in pairwise(out)]
    expect(max(steps) < 6000, True, f"switching between a custom and a built-in loop doesn't jump ({max(steps)})")
    walled = noise.NoiseSynth(0.5, {}, {"wall": files["bonk"]})
    expect(len(walled.hit_sounds["graze"]), len(walled.hit_sounds["wall1"]), "a light head hit follows a custom wall")
    broken = {"ramp": sett.sounds_dir() / "ramp-000000000000.wav", "wall": src / "song.mp3"}
    fallback = noise.NoiseSynth(0.5, {"ramp": "wind"}, broken)
    plain = noise.NoiseSynth(0.5, {"ramp": "wind"})
    expect([fallback.loop_bytes == plain.loop_bytes, fallback.hit_sounds == plain.hit_sounds], [True, True],
           "a missing or unreadable custom file plays the built-in sound")
    # a 2 s custom hit starts as fast as a built-in one: the synth scaled it once, the audio thread only adds
    syn = noise.NoiseSynth(1.0, {"ramp": "wind"}, files)
    syn.hit("bonk")
    syn.next("ramp")
    expect(syn.playing[0][0] is syn.hit_sounds["bonk"], True, "a hit starting copies no samples")
    own = noise.NoiseSynth(1.0, {}, {"graze": files["bonk"]})
    peak = max(map(abs, own.hit_sounds["graze"])) / 32767
    expect(abs(peak - noise.HIT_PEAK) < 0.01, True, f"a light head hit's own file plays at full strength ({peak:.2f})")
    # a long file: only the first READ_MAX_S is read, a loop cut to LOOP_MAX_S
    write_wav(src / "song.wav", [(0.3 * math.sin(i / 5),) for i in range(48000 * 40)])
    t = time.perf_counter()
    song = custom.make(src / "song.wav", "ceiling")
    took = time.perf_counter() - t
    with wave.open(str(sett.sounds_dir() / song["file"])) as w:
        expect(w.getnframes(), int(noise.RATE * custom.LOOP_MAX_S), "a long loop is cut to LOOP_MAX_S")
    expect(took < 10, True, f"a 40 s file reads only its start ({took:.1f} s)")
    # the hub: picking makes the file, cancelling keeps all, Apply saves and prunes what it doesn't name
    section = hub.local_import(HERE / "hub_section.py", "hub_section")
    picks = [[str(src / "late hit.wav")], None]

    class FakeWindow:
        def create_file_dialog(self, kind, file_types=()):
            return picks.pop(0)
    import types
    sys.modules["webview"] = types.SimpleNamespace(windows=[FakeWindow()], FileDialog=types.SimpleNamespace(OPEN=10))
    try:
        got = section.pick_sound("wall")
        expect([got["slot"], got["custom"]["name"]], ["wall", "late hit.wav"], "pick_sound makes the custom sound")
        expect(section.pick_sound("wall"), {"slot": "wall", "custom": None}, "a cancelled pick: nothing")
    finally:
        del sys.modules["webview"]
    data = section.apply({"custom": {"wall": got["custom"], "ramp": entry}})
    expect(data["sound"]["custom"], {"wall": got["custom"], "ramp": entry}, "apply saves the custom sounds")
    expect(sorted(f.name for f in sett.sounds_dir().iterdir()), sorted([got["custom"]["file"], entry["file"]]),
           "apply deletes the custom sound files no setting names")
    section.apply({})
    expect(list(sett.sounds_dir().iterdir()), [], "back to built-in sounds: no files left")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for var, sub in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("LOCALAPPDATA", "data"),
                         ("APPDATA", "config")):
            os.environ[var] = str(tmp / sub)
        os.environ["HOME"] = str(tmp / "home")  # ~/.local/bin/movekit-run
        game = fake_game(tmp)
        os.environ["MOMENTUM_DIR"] = str(game)
        sys.path.insert(0, str(KIT))
        from movekit import hub, launch, modules, panorama

        inst = hub.local_import(HERE / "install.py", "install")
        expect(modules.module_version(HERE, modules.read_manifest(HERE)), inst.VERSION, "module.json reads VERSION")
        kit = game / "custom" / panorama.KIT_FOLDER
        timer = kit / "panorama" / "layout" / "hud" / "timer.xml"
        own = game / "custom" / inst.FOLDER / inst.TS
        linux = sys.platform != "win32"

        panorama.install(game, "0-other", "other", OTHER)
        expect(inst.install(game), [], "install skips nothing")
        expect(own.read_bytes(), (HERE / inst.TS).read_bytes(), "script copied")
        autoexec = game / "cfg" / "autoexec.cfg"
        expect(autoexec.read_text().count("con_logfile yaw.log"), 1, "autoexec block: the console log on")
        expect(autoexec.read_text().count("con_filter_text_out MK_"), 1, "autoexec block: markers hidden in the console")
        expect(timer.read_text().count(INCLUDE), 1, "timer.xml includes Surf Sound once")
        expect(timer.read_text().count("other.ts"), 1, "the other tool's timer.xml include kept")
        expect((kit / "cfg" / "hud" / "hud_default.kv3").exists(), False, "no hud_default.kv3 copy")
        if linux:
            expect(launch.registered().get("surf-sound", (None,))[0], inst.HOOK_ORDER, "launch hook registered")
        before = {p: p.read_bytes() for p in kit.rglob("*") if p.is_file()}
        expect(inst.install(game, quiet=True), [], "second install skips nothing")
        expect({p: p.read_bytes() for p in kit.rglob("*") if p.is_file()}, before, "installing again changes nothing")

        inst.uninstall(game)
        expect((game / "custom" / inst.FOLDER).exists(), False, "own folder removed")
        expect("movekit:surf-sound" in autoexec.read_text(), False, "autoexec block removed")
        expect(INCLUDE in timer.read_text(), False, "timer.xml without its include")
        expect(timer.read_text().count("other.ts"), 1, "the other tool's include kept")
        if linux:
            expect("surf-sound" in launch.registered(), False, "launch hook removed")

        # a failed sync keeps the script, so the kit's timer.xml never includes a missing file
        inst.install(game, quiet=True)
        real = panorama.uninstall

        def broken(*_a, **_k):
            raise OSError("locked")
        panorama.uninstall = broken
        try:
            inst.uninstall(game)
        finally:
            panorama.uninstall = real
        expect(own.is_file(), True, "script kept when the sync fails")
        expect(INCLUDE in timer.read_text(), True, "include kept when the sync fails")
        inst.uninstall(game)
        panorama.uninstall(game, "0-other")
        expect(kit.exists(), False, "kit folder gone with no patches left")

        inst.install(game, quiet=True)
        inst.uninstall(None)
        if linux:
            expect("surf-sound" in launch.registered(), False, "launch hook removed with no game")
        inst.uninstall(game)

        # the module hooks, as the kit's module manager calls them (launch on Linux only syncs)
        hooks = modules.Manager(kit_root=KIT, data=tmp / "mgr")._hooks("surf-sound")
        ctx = modules.Context(HERE, KIT, modules.read_manifest(HERE))
        hooks.install(ctx)
        expect(INCLUDE in timer.read_text() and own.is_file(), True, "install hook")
        own.unlink()
        hooks.launch(ctx, ["game.exe"])
        expect(own.is_file(), True, "launch hook installs again")
        hooks.uninstall(ctx)
        expect(kit.exists() or own.exists(), False, "uninstall hook")
        os.environ["MOMENTUM_DIR"] = str(tmp / "nogame")
        try:
            hooks.install(ctx)
            fail("install hook with no game didn't raise")
        except RuntimeError:
            pass
        hooks.uninstall(ctx)
        hooks.launch(ctx, ["game.exe"])  # no game: nothing, no error
        os.environ["MOMENTUM_DIR"] = str(game)

        sett = hub.local_import(HERE / "settings.py", "settings")
        noise = hub.local_import(HERE / "noise.py", "noise")
        check_settings(sett, hub, noise)
        check_synth(noise)
        check_runner(sett, hub, tmp)
        check_custom(sett, hub, noise, tmp)
    print("check_surf_sound: all good")


if __name__ == "__main__":
    main()
