# Zone Exit Speed

When you leave the start zone in [Momentum Mod](https://momentum-mod.org/)'s surf mode, Zone Exit Speed shows how good your pre jump was:

- **Your speed** at the moment the timer starts, in x, y and z together. The start zone caps horizontal speed, so the vertical part of the pre jump is what tells a good exit from a bad one. The number is amber below 400 u/s, green from 400 to 420 u/s and blue above 420 u/s. Those speeds depend on the map, so set your own.
- **The difference** to the comparison run's exit speed, for example `+7` in green or `-29` in red. The comparison run is the one Momentum loads for its own split comparisons, normally your PB on that map. With none loaded, or one for another track, it doesn't show.

It stays for 3 seconds, then fades out. It shows only for your own runs on the main start, not at stage starts, on replays or while spectating.

Momentum has a "Zone Velocity" speedometer type for this, but the game no longer feeds it (its handler is commented out in `hud/speedometer.ts`), so it shows nothing.

Everything about it is set in the game's **HUD customizer**, where it is listed as **Zone Exit**: position (drag it), font, size and colours, whether the speed is coloured and the two speeds and three colours for it, whether the difference shows and its colours, and how long it stays and fades. The settings are saved with your HUD preset. The customizer's switch turns it off. While the customizer is open, it shows a sample (`418 +8`) so it can be placed.

## Install

Install [Soulmanyes's Movement Kit](../README.md#install) (Windows or Linux) and click **Install** on the Zone Exit Speed card of its Modules page. Then restart the game: Momentum mounts the folders in `custom/` only when it starts, so a game that was running doesn't see the new one. After an update, `panorama_reload` in the console is enough.

## What it changes in the game folder

- `custom/movekit-zone-exit`: its script, `movekit-zone-exit.ts`, and `movekit-panorama.json`, the two changes it makes to the game's files.
- `custom/0-movekit`: the kit's copies of `layout/hud/timer.xml` (one line added: the script's include) and `cfg/hud/hud_default.kv3` (its entry added, with its default settings; the customizer only takes a panel that has one). Each is made from the copy the game would use otherwise (another HUD mod's in `custom/`, or the game's own), again on every install and every game start, so a game update to either file carries over. If an update changes the line it looks for, that change is left out and the HUD section says so: without the include it doesn't load, without the entry it stays hidden.

Your own HUD presets in `cfg/hud` are not touched. The customizer saves its settings into them like any other panel's.

On Linux, starting the game through `movekit-run %command%` (the kit's launch option) makes the copies again at every start, unless a `[launch]` list in `~/.config/movekit/settings.toml` leaves `zone-exit` out for Momentum. On Windows the kit's exe as the launch option does the same.

**Uninstall** on the card takes them out again (`python install.py --uninstall` from a clone).

## Checks

- `node zone-exit/check_zone_exit.js`: the customizer settings against the kv3 entry, the drawn line, and the Panorama side with the numbers a probe logged in game.
- `python zone-exit/check_zone_exit.py`: install and uninstall on a fake game folder.
- `zone-exit/probe/`: the throwaway probe that logged those numbers (`python zone-exit/probe/probe.py [--mounted]`, `--uninstall`). Not part of the module.

### Licence

CC0 1.0 (see `LICENSE`).
