# Surf Sound

Part of [Movement Kit](../README.md). For Momentum Mod, on Windows and Linux.

A constant sound on your desktop for as long as you ride a surface in the air:

- **Ramps:** surfing a ramp, or sliding down a slope.
- **Ceilings:** headsurfing a sloped ceiling. By default it sounds just like a ramp. Separate on its row gives
  it a sound of its own; Same as ramps joins them again. (Up to 1.5.0 a separated headsurf played a
  brighter version of a built-in sound; since 1.6.0 it plays it as it is.)

The sound is a recorded loop, not a tone. Pick one of four on the Surf Sound page in the hub:

| Sound | What it is like |
| --- | --- |
| Whoosh | A whoosh, a 1.3 s recording (`sounds/whoosh.wav`, the default) |
| Rumble | A low rumble, a 2.35 s recording (`sounds/rumble.wav`) |
| Stone | Stone dragged over stone, a recording (`sounds/stone-dragging.wav`) |
| Long squeak | A long squeak, a 2.5 s recording (`sounds/long-squeak.wav`) |

Whoosh, Rumble and Long squeak repeat at their own length. 1.7.0 replaced the generated sounds with
recordings: Hiss became Whoosh, Rumble is a recording now, and Wind and Grind are gone (settings that
used them play Whoosh).

▶ plays each one there. The page also has a switch and a Volume % for each sound (ramps, ceilings,
wall hits, light and hard head hits, jumps), and "Also when watching" for replays and spectating. A change
applies at once, also while the game runs. Each sound starts at 80 %; settings from before 1.2.0 had one
volume for all, which is dropped, so they start there too.

Hits play once, on top of the constant sound, each with its own switch and ▶:

- **Wall hits:** a bonk (`sounds/bonk-wall.wav`) when a wall takes your speed. It gets louder the more
  speed you lose (from 100, 300 and 800 u/s).
- **Head hits:** rising at 400 u/s or more into a ceiling, the trick to drop down faster, plays a goofy
  bonk (`sounds/bonk-goofy.wav`). So does hitting a sloped ceiling nearly head-on at any speed, when it
  costs you 100 u/s or more and throws you down at 300 u/s or faster. Just clipping a flat ceiling near the top of a jump (a jump that
  missed) plays the wall's bonk instead, and so does a head hit that costs you speed without that throw
  (a bhop that lands wrong and hits the curve above). These light head hits have their own switch.
- **Jumps:** a cartoon boing (`sounds/jump.wav`) at every takeoff,
  bhops and surf alike, as the game counts jumps. Off by default, since a bhop map jumps every half
  second or so.

### Your own sounds

Each of the six (ramps, ceilings, wall hits, light and hard head hits, jumps) can play a sound file of your
own: File… on its row, × goes back to the built-in one, and Apply saves it. Or record one: ● Rec on its
row opens a recording window that says what that sound needs (a steady sound for ramps and ceilings, at
least 1 s; one short sound for hits). Pick the microphone there (the system's default input unless you
pick another; ↻ lists them again), click ● Record, make the sound and click ■ Stop, or it stops by itself
after 8 s for ramps and ceilings and 3 s for hits. ▶ Play lets you hear it; Use it puts it on the row. Save (with a name) keeps a recording for later,
and Use it saves it too: the window lists that sound's saved recordings to play, use again, rename (✎ or click the name) or delete, so
one you replaced isn't lost. Save next to "On the row now" keeps the sound the row already has. The quiet before and after the sound is cut, so a loop
doesn't repeat a gap and a hit plays at once; a jump keeps at most 1 s. Linux records through PipeWire
(`pw-cat`), Windows through the system's recording device.

- A WAV of any rate and channels, 8 to 32-bit. MP3, OGG, FLAC and others work when ffmpeg is installed.
- The silence before and after the sound is cut, for every sound (since 1.6.0; before, only a hit's leading silence).
- Ramps and ceilings repeat it: 1 to 15 s of sound (a longer file is cut), its end blended into its start so it loops without a click and without a silent gap.
  A ceiling with no file of its own plays the built-in sound's ceiling version.
- A hit plays it once, at once, cut at 2 s. A light head hit
  with no file of its own plays the wall hit's sound, a bit quieter; with its own file it plays that at
  full strength. Wall hits play your file louder the more speed you lose, as the built-in one.
- The hub keeps a converted copy in `surf-sound-sounds/` in the kit's config folder (`~/.config/movekit`,
  `%APPDATA%\movekit` on Windows), so moving or deleting the original changes nothing. A copy that goes
  missing plays the built-in sound.

## Install

From the hub's Modules page. Then type `panorama_reload` in the game's console, or load a map.

On Linux the sound runner starts with the game through `movekit-run`, so the Steam launch options need
`movekit-run %command%`. On Windows the kit's core exe is the launch option and starts it.

## How it works

Momentum counts a ramp as air, so there is no "surfing" flag to read. The HUD script
(`panorama/scripts/hud/movekit-surf-sound.ts`) watches your z speed instead. In free fall it changes by
exactly `sv_gravity` × the tick interval each tick. A surface under you makes it fall slower or rise;
a ceiling pressing down makes it fall faster.

- The sound starts on the first tick of that, so a brief headsurf is heard, and stops after 3 ticks of
  free fall, so a ride doesn't stutter. On the ground your z speed is exactly 0, which counts as ground.
- It stops at once on the ground, in water, below 150 u/s, on a teleport, while paused or stuck, in
  noclip, in a paused replay and while the HUD customizer is open.
- At the speed cap (`sv_maxvelocity`, 3500 u/s per axis) a fall no longer speeds up, so a fall at
  -3500 counts as free fall, not as a ramp. A ramp ridden at the cap can read the same speed every
  tick; that keeps the sound on as long as the game (or replay) clock runs.
- Replays and spectating play too, for the player you watch (switch: "Also when watching"). A replay
  counts its own ticks, so it works at any playback speed. A spectated player's speed arrives every
  3 or 5 of their ticks, so there the sound and hits come in steps of about 50 ms.
- A wall hit is a horizontal speed drop of 100 u/s or more in one tick while your z speed stays plain
  free fall. A key against your motion in the air (S while going forward, A right after
  D) can lose far more, but it leaves exactly 30 u/s of your new speed along the change, where a wall
  leaves none, so it never bonks. A glancing hit counts from 40 u/s lost: a wall removes the part of your
  velocity along its normal, so the change is at a right angle to your new velocity, while a strafe
  that slows you pushes against it. Sliding along a curved wall loses a little more speed each tick, so
  while you slide (two updates in a row losing speed that way), a wall hit needs 300 u/s or more lost. Riding a ramp onto the flat top of a spine at 300 u/s or more falling
  (z speed exactly 0, horizontal speed kept) is a wall hit too. So is falling straight onto a spine
  top from free fall at 300 u/s or more, with 600 u/s or more across: it plays one tick (15 ms) after
  the landing, unless you jumped by then (a bhop). A hard landing on the floor that you don't jump out
  of plays it too. Landing on a spine top and dropping off within the same tick plays at once, with or
  without a ramp ride. A head hit is losing at least half your upward speed to a ceiling in one tick.
  A light one also has to leave your z speed at -30 u/s or above: a sloped ceiling that throws you
  down near the top of a jump is a headsurf starting, and plays the ceiling sound instead, unless
  it cost 100 u/s or more of your whole speed: a head hit after all, a bonk if it throws you down at
  300 u/s or faster, else a light one. Each hit
  waits 250 ms before it can play again, so scraping along a wall bonks once. A reset or teleport,
  which sets all your speed to 0 at once, is never a hit.
- Crashing nearly head-on into a slope that faces up, which changes your z speed too, is a hard wall
  hit when it costs 800 u/s or more of your whole speed in one tick. Ordinary ramp landings, even
  steep ones on a map's route, lose far less.
- Known gaps: trigger pushes and gravity zones can sound like a ramp for a moment. Hitting a wall
  (not a spine top) while you ride a ramp plays no thud, since the ramp changes your z speed too.

The script writes `MK_SURFSND_RAMP`, `MK_SURFSND_CEIL` and `MK_SURFSND_OFF` into the console, again every
half second while a sound plays. Hits write `MK_SURFSND_WALL1`/`2`/`3`, `MK_SURFSND_GRAZE` or
`MK_SURFSND_BONK` once. While you watch a replay or spectate, each of these but OFF ends in `W`
(`MK_SURFSND_RAMPW`), so the runner can mute them. The autoexec block logs the console to `yaw.log` and hides `MK_` lines
from the console. The sound runner (`sound_run.py`) reads them and plays the sound
(`noise.py`, through the kit's `movekit/tone.py` players). It stops a sound after 1.5 s without a marker.
On Linux its PipeWire stream is named "Surf Sound", so OBS's Application Audio Capture (PipeWire) can
record it on its own. On Windows the player keeps the kit's fix for crackle (a ring of 10 ms buffers, refilled as each one
finishes). A hit on top of a loud sound goes through a limiter, so it never clips at any volume.

## Checks

```sh
node surf-sound/check_surf_sound.js
python surf-sound/check_surf_sound.py
```
