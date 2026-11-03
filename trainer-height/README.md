# Strafe Trainer Height

Lets you make [Momentum Mod](https://momentum-mod.org/)'s strafe trainer taller. In the HUD editor its height can be dragged like its width, and the bar fills the new height. At the stock height of 80 px it looks the same as the game's own.

## Install

Install [Soulmanyes's Movement Kit](../README.md#install) (Windows or Linux) and click **Install** on the Strafe Trainer Height card of its Modules page. Then type `panorama_reload` in the game console, or restart the game, and drag the trainer's height in the HUD editor.

It doesn't need Strafe Review, and Strafe Review doesn't need it. The hub's HUD section lists its changes under **Patched game files**.

## What it changes in the game folder

- `custom/movekit-trainer-height`: its stylesheet, `strafe-trainer-height.scss`, and `movekit-panorama.json`, the two changes it makes to the game's files.
- `custom/0-movekit`: the kit's copies of `layout/hud/strafe-trainer.xml` (one line added: the stylesheet's include) and `scripts/hud/strafe-trainer.ts` (`resizeY: false,` becomes `resizeY: true,`). Each is made from the copy the game would use otherwise (another HUD mod's in `custom/`, or the game's own), again on every install and every game start, so a game update to either file carries over. If an update changes the line it looks for, that change is left out and the HUD section says so; the game then shows the stock trainer.
- `custom/strafe-trainer-height`, the same mod installed by hand before it was a module, is removed.

On Linux, starting the game through `movekit-run %command%` (the kit's launch option) makes the copies again at every start, unless a `[launch]` list in `~/.config/movekit/settings.toml` leaves `trainer-height` out for Momentum. On Windows the kit's exe as the launch option does the same.

**Uninstall** on the card takes them out again (`python install.py --uninstall` from a clone).

### Licence

CC0 1.0 (see `LICENSE`).
