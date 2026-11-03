# JHUD

After every jump in [Momentum Mod](https://momentum-mod.org/)'s bhop modes, JHUD shows that jump in the middle of the screen: its number, your speed and how much it changed, gain % and sync, on one line. By default the line is in the font colour, which you can set. "Colour by" can instead colour it:

- **Gain %:** amber below 86.5 %, green from 86.5 to 92 %, blue above 92 %, the same as the Strafe Speed Histogram's Gain % mode. The thresholds are set in tenths of a percent (865 = 86.5 %), as the HUD customizer's number boxes take whole numbers.
- **Speed pace, then gain %:** up to jump 6 or 12 (you pick), by the speed you are on pace for at that jump. You set three target speeds and their colours (by default 620 green, 625 blue, 630 white) and a colour for below all three. Jump 4, say, shows blue when its speed is what usually leads to 625 or more at jump 6. After the cutoff the line goes by gain %. The pace curve comes from one player's runs; from jump 4 on it usually predicts jump 6 within 1.5 u/s, but jump 2 is only a rough guess. Jump 1 isn't judged.

A tick box colours only the speed or gain % instead of the whole line. It shows at every takeoff, labelled with the takeoff's number; gain, sync and the rest are from the air time just before it, so the first takeoff shows only its number and speed. It stays for 2 seconds, then fades out. The numbers are the game's own, the same as its Jump Stats panel.

Everything about it is set in the game's **HUD customizer**, where it is listed as **JHUD**: position and width (drag it), font, size and colours, which fields show (strafes, yaw ratio, efficiency, height change, distance and time are off by default), the gain thresholds and their colours, which jumps show (from jump N, every Nth), and how long it stays and fades. The settings are saved with your HUD preset. The customizer's switch turns it off. While the customizer is open, JHUD shows a sample jump so it can be placed.

Jump numbers start again when the timer is primed in the start zone. Jump 1 is the first jump that leaves it.

## Install

Install [Soulmanyes's Movement Kit](../README.md#install) (Windows or Linux) and click **Install** on the JHUD card of its Modules page. Then restart the game: Momentum mounts the folders in `custom/` only when it starts, so a game that was running doesn't see the new one. After an update, `panorama_reload` in the console is enough.

It doesn't need Strafe Review, and Strafe Review doesn't need it. The hub's HUD section has a JHUD card, and lists its changes under **Patched game files**.

## What it changes in the game folder

- `custom/movekit-jhud`: its script, `movekit-jhud.ts`, and `movekit-panorama.json`, the two changes it makes to the game's files.
- `custom/0-movekit`: the kit's copies of `layout/hud/timer.xml` (one line added: the script's include) and `cfg/hud/hud_default.kv3` (JHUD's entry added, with its default settings; the customizer only takes a panel that has one). Each is made from the copy the game would use otherwise (another HUD mod's in `custom/`, or the game's own), again on every install and every game start, so a game update to either file carries over. If an update changes the line it looks for, that change is left out and the HUD section says so: without the include JHUD doesn't load, without the entry it stays hidden.

Your own HUD presets in `cfg/hud` are not touched. The customizer saves JHUD's settings into them like any other panel's.

On Linux, starting the game through `movekit-run %command%` (the kit's launch option) makes the copies again at every start, unless a `[launch]` list in `~/.config/movekit/settings.toml` leaves `jhud` out for Momentum. On Windows the kit's exe as the launch option does the same.

**Uninstall** on the card takes them out again (`python install.py --uninstall` from a clone).

### Licence

CC0 1.0 (see `LICENSE`).
