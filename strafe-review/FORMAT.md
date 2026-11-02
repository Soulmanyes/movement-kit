# Strafe Review attempt format 1

This page is the reference for what the recorder sends and the collector saves. Other tools (histograms, progress over time, a JHUD) read attempts from it without touching the collector. Python tools can use `movekit/attempts.py`, which follows this page; `movekit/check_attempts.py` checks it (`--store DIR` also checks every saved file).

## Version rule

- One number, `format`, covers the wire format and the file, because the file is the wire JSON as it was sent.
- **No bump:** a new optional field, a new event kind, a new `label` or `reason` value, a new column added at the end of `cols`.
- **Bump:** removing a field or column, changing a field's type or unit, or giving a value a new meaning.
- Readers look columns up by name in `cols`, never by position (`css_demo.py` writes a subset in another order). They ignore fields, columns and event kinds they don't know, and use the defaults below for missing optional fields.
- Readers skip a file whose `format` they don't know. The viewer's server leaves it out of the list and says so on stderr.

## Wire

Every line in Momentum's console log (`yaw.log`) is `[panorama] SRREC <id> ...`:

- `<id> <i>/<n> <text>`: chunk `i` of `n`, at most 900 characters. The chunks of one id, joined in order, are one JSON object (the attempt).
- `<id> end n=<n> chars=<c>`: the last line. An attempt with missing chunks, or a joined length other than `c`, is dropped.
- Other `SRREC` lines are recorder messages, not data.

`collector/srrec.py` reads this.

## Storage

- `<store>/<map dir>/<id>.json.gz`: one gzip-compressed JSON object per attempt, UTF-8, exactly as the recorder sent it. Files are never rewritten.
- `<store>` is `~/.local/share/strafe-review/attempts` (`$XDG_DATA_HOME`), or `%LOCALAPPDATA%\strafe-review\attempts` on Windows.
- `<map dir>` is the `map` field with every character outside `A-Z a-z 0-9 _ . -` replaced by `_` (`unknown` if empty).
- The collector writes a temporary file and renames it, so a reader never sees half a file. An id already on disk is not saved again.
- `<store>/meta.json` is the viewer's own file: `{"version": 1, "attempts": {"<map dir>/<id>": {"note": str, "tags": [str]}}}`. It is not part of an attempt.

## Fields

Required in every attempt:

| field | type | meaning |
|---|---|---|
| `format` | int | `1` |
| `id` | string | `Date.now()` in base 36 plus 2 random base-36 characters; unique, also the file name |
| `map` | string | map name as the game gives it |
| `interval` | number | seconds per tick (0.01 = 100 tick, 0.015 = 66 tick) |
| `label` | string | whose movement: `own`, `replay` (a replay file playing), `spectate` (a live player spectated); treat any other value as someone else's |
| `cols` | array of strings | names of the row values, in order |
| `rows` | string | rows joined by `;`, each row the values named in `cols` joined by `,`; `""` for none |

Optional (missing in some files; default in brackets):

| field | type | meaning |
|---|---|---|
| `started` | int | ms since 1970 when the attempt began [none] |
| `ended` | int | ms since 1970 when it was sent [none] |
| `style` | int | Momentum style id [0] |
| `track` | object | `{type, number}`; type 0 main, 1 stage, 2 bonus (Momentum's TrackType) [main] |
| `player` | string or null | replay or spectated player's name; null for own runs or when unknown [null] |
| `replayFile` | string or null | replay file path relative to the game's `momentum` folder [null] |
| `practice` | bool | practice mode was on at the start [false] |
| `version` | string | Momentum version, e.g. `0.10.8` [none] |
| `mouse` | object or null | `{sensitivity, m_yaw, cl_yawspeed, dpi}` read at the start; `dpi` from Momentum's own settings page or null; null if the HUD couldn't read them. Added 2026-10-27 [none: use the game's current settings] |
| `preRows` | int | rows before the timer started (up to 2 s); row `preRows` is the first run row [0] |
| `postRows` | int | rows kept after a non-finish end (up to 0.5 s) [0] |
| `events` | array | see below [[]] |
| `reason` | string | how it ended, see below [none] |
| `runTime` | number | seconds on the timer at the end; the last time seen while running for non-finish ends [0] |
| `gaps` | int | ticks missed while recording [0] |

## Columns

Format 1 recorder files carry these, in this order; older files stop after `rtick` or `wy`. Values are numbers. `tick` is required; any other column may be missing (`css_demo.py` writes no `pitch`, `move`, `duck`, `rtick` or `seek`).

| column | meaning |
|---|---|
| `tick` | tick number: floor(game time / interval), raised to last + 1 when a new tick shows up inside the same number. A jump of more than 1 is a missed tick |
| `gain` | `GetLastTickStats().speedGain`, u/s. Reads 0 on replays and spectated players |
| `ideal` | `idealGain`, u/s. Reads 0 on replays and spectated players |
| `ratio` | `yawRatio` |
| `right` | `strafeRight` |
| `vx`, `vy`, `vz` | velocity, u/s |
| `yaw`, `pitch` | view angles, degrees (3 decimals) |
| `buttons` | `physicalButtons` bits (jump 2, forward 8, back 16, left 128, right 256, moveleft 512, moveright 1024). The local player's keys, also while spectating |
| `move` | `moveStatus`: 0 air, 1 walk, 2 water, 3 waterjump |
| `duck` | ducking |
| `rtick` | replay's current tick while a replay plays, else -1 |
| `wx`, `wy` | `GetMoveHudData().wishVel` x and y, the game's wish velocity |
| `seek` | 1 when the row was read by the replay rescan after playback (a tick missed while playing), else 0 |

## Events

Each event is `{"tick": <tick column value>, "kind": <string>, ...}`. Kinds so far:

| kind | fields |
|---|---|
| `timer` | `state` (Momentum TimerState), `runTime` |
| `jump` | `n`, `takeoff`, `delta`, `takeoffTime`, `sync`, `strafes`, `gain`, `ratio`, `height`, `distance`, `eff` (`GetLastJumpStats()`) |
| `practice` | `on` |
| `savestate` | `count`, `current`, `usingMenu` |
| `rescan` | `rows`, `wanted`, `atEnd` (replay rescan finished) |

## End reasons

| reason | meaning |
|---|---|
| `finish` | timer finished (also a replay rescanned to its end) |
| `zone` | back in the start zone without a teleport (bhopped back) |
| `reset` | teleported to the start (horizontal speed fell to about 0 right after the end) |
| `stop` | timer stopped for another reason |
| `practice` | practice mode turned on |
| `savestate` | a savestate was loaded |
| `replaced` | Momentum swapped the observed timer (a replay looping or changed) |
| `target` | the spectated target changed |
| `level` | the map changed mid-attempt |
| `restart` | a new run started while one was still open (a missed state change) |

## Reader corrections

Files keep what the recorder sent, including its old mistakes. The viewer fixes these when reading (`viewer/server.py` `head()`, `viewer/static/data.js` `parse()`); a tool that needs the same answers has to do the same:

- **Old spectated runs.** Recorders before the `spectate` label saved a spectated live player as `own`. An `own` attempt with 20 or more air rows where no air row has a non-zero `ideal` is `spectate`. Ground is a row with `vz` exactly 0 that isn't an apex.
- **Replays played to the end** end as `replaced` (Momentum swaps the timer a tick before FINISHED) or as `finish` with a run time a tick short. When the replay file's header run time is within a few ticks, the attempt counts as a finish with the file's run time.
- **Rows before a teleport.** A replay opens with the end of the player's previous run, then a teleport into the start zone. Rows before the last teleport ahead of the timer start are not part of this run.
- **No tick stats.** Replays and spectated players read 0 for `gain` and `ideal`. The viewer rebuilds them from speed: gain = change in horizontal speed, ideal = sqrt(v² + 30²) - v.
- **Coarse speed.** A spectated player's velocity only changes every 5th tick or so, so per-tick gain means nothing there; only per-jump sums do.
