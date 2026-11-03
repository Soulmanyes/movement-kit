# Strafe Speed Histogram

While you bhop in [Momentum Mod](https://momentum-mod.org/), this HUD element shows how fast you turn your mouse compared with the optimal turn speed, as a histogram. It covers the middle of your strafes in the last few seconds of strafing. The value is the game's yaw ratio, where 1.0 is optimal, below is too slow and above is too fast.

- **Bars:** by default 14 bars. There are 12 of width 0.1 from 0.4 to 1.6, plus one bar for everything under 0.4 and one for 1.6 and over. Each bar's height is its share of the ticks counted, so the tallest bar is always full height.
- **In band:** a line under the bars gives the share of ticks inside the optimal band, 0.85 to 1.15. A tick box turns it off.
- **Window:** the last 3 seconds of strafing by default. Standing still adds nothing, so the bars stay as they are until new strafing pushes the oldest ticks out. A map load clears them.
- **Colours:** "Colour by" is **Plain** by default: every bar in one colour you pick. **How good** colours each bar by how far it is from 1.0, from green at 1.0 to red at 50 % away or more, the same on both sides. Both colours and the distance can be set.

Which ticks count is Strafe Review's own rule for the middle of a strafe, the same one behind its "In optimal band" number. The ticks must be in the air after a jump, at 100 u/s or more, with no wall or ramp hit, not on +left/+right, and not the first or last 2 ticks of a strafe. So the HUD is about 5 ticks behind, which can't be seen. On 1132 saved bhop runs it counts exactly the ticks Strafe Review does (`check_strafe_histogram.js`).

It shows in the bhop modes only, and only for your own play: not while spectating or watching a replay.

Everything about it is set in the game's **HUD customizer**, where it is listed as **Strafe Speed Histogram**:

- position and width (drag it), and the height of the tallest bar;
- the range and the bar width, in % of the optimal;
- the window length in seconds;
- the colours, and the font of the in-band line.

The settings are saved with your HUD preset. The customizer's switch turns it off. While the customizer is open, it shows a sample histogram so it can be placed.

## Install

Install [Soulmanyes's Movement Kit](../README.md#install) (Windows or Linux) and click **Install** on the Strafe Speed Histogram card of its Modules page. Then restart the game: Momentum mounts the folders in `custom/` only when it starts, so a game that was running doesn't see the new one. After an update, `panorama_reload` in the console is enough.

It doesn't need Strafe Review or JHUD, and they don't need it. The hub's HUD section has a card for it, and lists its changes under **Patched game files**.

## What it changes in the game folder

- `custom/movekit-strafe-histogram`: its script, `movekit-strafe-histogram.ts`, and `movekit-panorama.json`, the two changes it makes to the game's files.
- `custom/0-movekit`: the kit's copies of two game files:
  - `layout/hud/timer.xml`, with one line added: the script's include;
  - `cfg/hud/hud_default.kv3`, with the histogram's entry and its default settings added (the customizer only takes a panel that has one).

  Each copy is made from the one the game would use otherwise: another HUD mod's in `custom/`, or the game's own. This happens again on every install and every game start, so a game update to either file carries over. If an update changes the line the kit looks for, that change is left out and the HUD section says so. Without the include the histogram doesn't load; without the entry it stays hidden.

Your own HUD presets in `cfg/hud` are not touched. The customizer saves the histogram's settings into them like any other panel's.

On Linux, starting the game through `movekit-run %command%` (the kit's launch option) makes the copies again at every start. A `[launch]` list in `~/.config/movekit/settings.toml` that leaves `strafe-histogram` out for Momentum stops that. On Windows the kit's exe as the launch option does the same.

**Uninstall** on the card takes them out again (`python install.py --uninstall` from a clone).

### Licence

CC0 1.0 (see `LICENSE`).
