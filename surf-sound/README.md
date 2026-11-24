# Surf Sound

Part of [Movement Kit](../README.md). For Momentum Mod, on Windows and Linux.

A constant sound on your desktop for as long as you ride a surface in the air:

- **Ramps:** surfing a ramp, or sliding down a slope.
- **Ceilings:** headsurfing a sloped ceiling. This plays a brighter version of the same sound, so you can
  hear which one you are on.

The sound is shaped noise or a recorded loop, not a tone. Pick one of five on the Surf Sound page in the hub:

| Sound | What it is like |
| --- | --- |
| Wind | Rushing air with a slow swell (the default) |
| Rumble | A deep, low rumble |
| Hiss | Sand or spray |
| Grind | A board on a rail: mid noise with a fast flutter |
| Stone | Stone dragged over stone, a recording (`sounds/stone-dragging.wav`) |

▶ plays each one there. The page also has a switch and a Volume % for each sound (ramps, ceilings,
wall hits, light and hard head hits), and "Also when watching" for replays and spectating. A change
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

### Your own sounds

Each of the five (ramps, ceilings, wall hits, light and hard head hits) can play a sound file of your
own: File… on its row, × goes back to the built-in one, and Apply saves it.

- A WAV of any rate and channels, 8 to 32-bit. MP3, OGG, FLAC and others work when ffmpeg is installed.
- Ramps and ceilings repeat it: 1 to 15 s (a longer file is cut), its end blended into its start so it loops without a click.
  A ceiling with no file of its own plays the built-in sound's ceiling version.
- A hit plays it once, the silence before it trimmed so it plays at once, cut at 2 s. A light head hit
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
- Replays and spectating play too, for the player you watch (switch: "Also when watching"). A replay
  counts its own ticks, so it works at any playback speed. A spectated player's speed arrives every
  3 or 5 of their ticks, so there the sound and hits come in steps of about 50 ms.
- A wall hit is a horizontal speed drop of 100 u/s or more in one tick while your z speed stays plain
  free fall. A wrong-way air strafe loses less than that (67.5 u/s per tick at surf's
  `sv_airaccelerate` 150). A glancing hit counts from 40 u/s lost: a wall removes the part of your
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
