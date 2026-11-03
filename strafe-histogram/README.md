# Strafe Speed Histogram

While you bhop in [Momentum Mod](https://momentum-mod.org/), this HUD element draws one bar for every tick you are in the air. The newest bar appears at the bottom and the older ones scroll up. A bar's length is how fast you turned your mouse that tick compared with the optimal turn speed (the game's yaw ratio, where 1.0 is optimal).

- **Optimal line:** a line marks the optimal. It sits in the middle by default, so a bar reaching the right edge is twice the optimal. It can sit at 3/4 of the width instead, so the bars have room up to 1.33 times the optimal.
- **Direction:** bars grow from the left by default. "Grow from the sides" makes right strafes grow from the left edge and left strafes from the right, towards the middle. "Swap the sides" turns that round.
- **Ticks shown:** 100 by default, 1 second at 100 tick. Ground ticks add no bar, so the bars run on across jumps. Standing still adds nothing, so the bars stay until you jump again. A map load clears them.
- **Colours:** "Colour by" is **Plain** by default: every bar in one colour you pick. **How good** colours each bar by how far its tick was from the optimal, from green at 1.0 to red at 50 % away or more, the same for too slow and too fast.
- Turning against the strafe (a negative ratio) gives an empty bar. Anything past the right edge is cut at the edge.

Each tick is drawn one tick (10 ms) late, once the next tick says whether it was on the ground: the same rule Strafe Review uses (`check_strafe_histogram.js` compares the two on saved runs).

It shows in the bhop modes only, and only for your own play: not while spectating or watching a replay.

Everything about it is set in the game's **HUD customizer**, where it is listed as **Strafe Speed Histogram**:

- position and width (drag it);
- the ticks shown and the bar height (together they give the height);
- where the optimal sits, and the sides the bars grow from;
- the colours, the optimal line and the background.

The settings are saved with your HUD preset. The customizer's switch turns it off. While the customizer is open, it shows a sample so it can be placed.

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
