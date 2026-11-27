# Paint Saver

Saves the paint you put on a map in [Momentum Mod](https://momentum-mod.org/) and paints it again after a map reload or a game restart.

## How it works

1. **Recording.** While you hold the paint key, a HUD script notes where you stand and where you look, every 15 ms, with the paint's colour and size. Install binds your paint keys to an alias that also tells the script about the key, as the game's HUD can't see it. `mk_savepaint` keeps the strokes of the map you are on.
2. **Making savestates.** At the next game start through the kit, before the game opens, Paint Saver writes each spot of the saved paint into `momentum/savedlocs.txt` as a savestate, in a list of its own named `zzpaint_<map>`. The game reads that file only when it starts, which is why saved paint comes back only after a restart.
3. **Painting.** `mk_loadpaint` imports that list to the end of your savestates and goes to each of them in turn with paint held, so each one paints where you looked from that spot, in its stroke's colour and size.
4. **Cleaning up.** It then deletes those savestates again from the end of the list and restarts the track. Your own savestates are never touched: if one changes during a load, it stops there and says so, and the leftovers go at the next game start. Your paint colour, size and paint sound settings are put back after a load (the paint sound is off during it).

## Switches

The Paint Saver section of the hub has two switches. Both are off after install, so your paint key stays as it is until you turn saving on. A change takes effect at the next game start.

- **Save paint.** On: your paint key is bound to Paint Saver's alias, which paints as before and also notes each stroke, and `mk_savepaint` saves them. Off: your paint key goes back to plain paint, and nothing is noted or saved. Paint already saved stays.
- **Load paint while saving is off.** With saving on, `mk_loadpaint` always works. With saving off, it works only while this is on, for paint you saved before.

## How to use it

The hub's Paint Saver section also has **Save paint**, **Load paint** and **Delete saved paint** buttons that run these commands in the open game, on the map you are on. They reach the game only when it was started through the kit with [Source Yaw](../sourceyaw/) installed; otherwise they show the command to type.

1. Turn on **Save paint**, and start the game with the kit's Steam launch option (the Paint Saver section shows it, with a Copy button). A key you bind to paint later is picked up at the next game start.
2. `mk_savepaint` saves all paint you made on this map since the game started, map reloads included. Save before you quit the game: paint you didn't save is gone after it.
3. After the next game start, on that map, type `mk_loadpaint`. Keep the mouse still until the console says `paint restored`: moving it moves the marks.
4. `mk_clearpaint` drops this map's saved paint. What is on screen stays until the map reloads.

## For paint that comes back right

- **Don't paint from inside walls, floors or clip brushes** (in noclip). Loading paint can't use noclip, so it can't stand where you stood, and that paint comes back in the wrong place.
- If some paint still comes back off, load it once, restart the game and load it again. Each load notes where each spot ended up, and the next game start corrects the ones that were off: it writes them higher or lower, or moves them back along your aim, which paints the same mark. Spots it can't place after a few tries are counted in the console message.
- Don't paint from inside teleports, boosters or other triggers that move you, or from moving platforms and doors.

The Paint Saver section in the hub lists the maps with saved paint.

## What it changes in the game folder

- `custom/movekit-paint-saver`: its HUD script, with the saved paint's plan written in.
- `custom/0-movekit`: the kit's copy of `layout/hud/timer.xml`, with one line added (the script's include).
- `cfg/autoexec.cfg`: a `// movekit:paint-saver` block with the console log, the commands, and, while saving is on, your paint keys bound to its alias.
- `cfg/config.cfg`: with saving off, your paint keys bound back to `+paint` at the next game start.
- `savedlocs.txt`: the `zzpaint_<map>` lists.

Uninstall takes all of these out and binds your paint keys back to `+paint`. The saved paint stays unless you tick **Also delete saved data**.

## Install

Install [Soulmanyes's Movement Kit](../README.md#install) (Windows or Linux) and click **Install** on the Paint Saver card of its Modules page. Then restart the game through the kit's launch option.

### Licence

CC0 1.0 (see `LICENSE`).
