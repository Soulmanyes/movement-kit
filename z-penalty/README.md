# Z Penalty

In [Momentum Mod](https://momentum-mod.org/)'s surf mode, Z Penalty shows when the game cuts your air acceleration to a quarter.

The rule is in the game's movement code: on every tick you are in the air with an upward (z) speed above 0 and at most 140 u/s, air acceleration counts only a quarter. On a ramp climb that is the part where holding into the ramp can't keep your speed any more, so you lose speed. It doesn't matter where on the ramp you are, only how fast you move up.

What it shows, each part switchable:

- a **Z PENALTY** label while the penalty is on
- your **z speed**, in the penalty colour while the penalty is on
- the **ticks** spent in the band on the last penalised stretch
- a **vertical z speed bar** with the 0-140 band shaded and a marker for your z speed

**Ramps only** (the default) counts a stretch only when it happens on a ramp, not at the top of a normal jump, which passes through the band too (12 ticks per jump). It tells the two apart by the z speed per tick: in free fall it changes by exactly sv_gravity times the tick interval (12 u/s at 800 and 66.67 tick); on a ramp it doesn't. Untick it to see the top of every jump as well.

It shows only in your own surf runs, not on replays or while spectating.

Everything about the panel is set in the game's **HUD customizer**, where it is listed as **Z Penalty**: position (drag it), font, size and colours, Ramps only, whether it is always shown or only while penalised (and then how long it stays and fades), the parts, and the bar's size, top speed and colours. The settings are saved with your HUD preset. While the customizer is open, it shows a sample so it can be placed.

## Sound

The **Z Penalty** page in the hub sets an optional sound played in game when a penalised stretch starts: on or off, the sound (one of the game's, with a preview) and its volume. The game can't read the kit's settings, so Apply writes the sound into the installed script. In a running game, type `panorama_reload` in the console afterwards. The setting is saved in `~/.config/movekit/z-penalty.json` (Windows: `%APPDATA%\movekit\z-penalty.json`).

## Install

Install [Soulmanyes's Movement Kit](../README.md#install) (Windows or Linux) and click **Install** on the Z Penalty card of its Modules page. It needs hub 1.10.0 or newer. Then restart the game: Momentum mounts the folders in `custom/` only when it starts, so a game that was running doesn't see the new one. After an update, `panorama_reload` in the console is enough.

## What it changes in the game folder

- `custom/movekit-z-penalty`: its script, `movekit-z-penalty.ts` (with your sound setting in it), and `movekit-panorama.json`, the two changes it makes to the game's files.
- `custom/0-movekit`: the kit's copies of `layout/hud/timer.xml` (one line added: the script's include) and `cfg/hud/hud_default.kv3` (its entry added, with its default settings; the customizer only takes a panel that has one). Each is made from the copy the game would use otherwise (another HUD mod's in `custom/`, or the game's own), again on every install and every game start, so a game update to either file carries over. If an update changes the line it looks for, that change is left out and the HUD section says so: without the include it doesn't load, without the entry it stays hidden.

Your own HUD presets in `cfg/hud` are not touched. The customizer saves its settings into them like any other panel's.

On Linux, starting the game through `movekit-run %command%` (the kit's launch option) makes the copies again at every start, unless a `[launch]` list in `~/.config/movekit/settings.toml` leaves `z-penalty` out for Momentum. On Windows the kit's exe as the launch option does the same.

**Uninstall** on the card takes them out again (`python install.py --uninstall` from a clone).

## Checks

- `node z-penalty/check_z_penalty.js`: the customizer settings against the kv3 entry, the tracker on jump and ramp shapes from in-game logs (also with every tick seen on two frames), the bar and text, and the Panorama side.
- `python z-penalty/check_z_penalty.py`: install and uninstall on a fake game folder, the sound setting and the hub page's Apply.
- `z-penalty/probe/`: the throwaway probe that logged the jump and ramp numbers (`python z-penalty/probe/probe.py`, `--uninstall`). Not part of the module.

### Licence

CC0 1.0 (see `LICENSE`).
