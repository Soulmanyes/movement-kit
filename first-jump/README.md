# First Jump HUD

Shortly after jump 1 of a run in [Momentum Mod](https://momentum-mod.org/)'s bhop or surf modes lands, First Jump HUD shows how that jump went, at the top middle of the screen:

- **Top line:** the landing speed and the jump's gain %.
- **One box per strafe** with its gain %, coloured like JHUD and the Strafe Speed Histogram: amber below 86.5 %, green from 86.5 to 92 %, blue above 92 %. The thresholds are set in tenths of a percent (865 = 86.5 %), as the HUD customizer's number boxes take whole numbers.
- **Under each box:** what lost that strafe the most gain, with its tick count. `keys` means no key or the wrong one was held while turning, `slow` means turning under 85 % of the optimal angle, `fast` means over 115 %. `ok` means nothing lost much.
- **The biggest jump-1 mistake** and the speed it cost, for example `D switch 4 ticks early (-5.6 u/s)`.

It stays for 4 seconds, then fades out. It shows only for your own runs, not on replays or while spectating.

The numbers are the same as [Strafe Review](../strafe-review/)'s review page shows for jump 1, with its mistake checks at their default thresholds. First Jump HUD works them out in the game from its own recording of the jump, so it doesn't need Strafe Review, and Strafe Review doesn't need it.

Everything about it is set in the game's **HUD customizer**, where it is listed as **First Jump**: position and width (drag it), font, sizes and colours, the strafe boxes' width and text colour, which rows show, the gain thresholds and their colours, and how long it stays and fades. The settings are saved with your HUD preset. The customizer's switch turns it off. While the customizer is open, it shows a sample jump so it can be placed.

Jump 1 is the jump in the air when the timer starts, or else the first jump after it.

## Install

Install [Soulmanyes's Movement Kit](../README.md#install) (Windows or Linux) and click **Install** on the First Jump HUD card of its Modules page. Then restart the game: Momentum mounts the folders in `custom/` only when it starts, so a game that was running doesn't see the new one. After an update, `panorama_reload` in the console is enough.

Before Strafe Review 1.9.0, Strafe Review's recorder drew this line itself, switched on in the hub's HUD section. Update Strafe Review too, or the old line shows as well; until then the HUD section keeps the old switch.

## What it changes in the game folder

- `custom/movekit-first-jump`: its script, `movekit-first-jump.ts`, and `movekit-panorama.json`, the two changes it makes to the game's files.
- `custom/0-movekit`: the kit's copies of `layout/hud/timer.xml` (one line added: the script's include) and `cfg/hud/hud_default.kv3` (its entry added, with its default settings; the customizer only takes a panel that has one). Each is made from the copy the game would use otherwise (another HUD mod's in `custom/`, or the game's own), again on every install and every game start, so a game update to either file carries over. If an update changes the line it looks for, that change is left out and the HUD section says so: without the include it doesn't load, without the entry it stays hidden.

Your own HUD presets in `cfg/hud` are not touched. The customizer saves its settings into them like any other panel's.

On Linux, starting the game through `movekit-run %command%` (the kit's launch option) makes the copies again at every start, unless a `[launch]` list in `~/.config/movekit/settings.toml` leaves `first-jump` out for Momentum. On Windows the kit's exe as the launch option does the same.

**Uninstall** on the card takes them out again (`python install.py --uninstall` from a clone).

## Checks

- `node first-jump/check_first_jump.js`: the customizer settings against the kv3 entry, the drawn rows, and the Panorama side on a made-up run.
- `node first-jump/check_parity.js`: every own attempt Strafe Review saved, fed tick by tick through the script, against the review page's own code (`--interval 0.015` as if at 66 tick, `--log` for the lines the game logged).
- `python first-jump/check_first_jump.py`: install and uninstall on a fake game folder.

### Licence

CC0 1.0 (see `LICENSE`).
