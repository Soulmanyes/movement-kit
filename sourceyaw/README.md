# Source Yaw

*Formerly CS:S Yaw. If you had it installed, the installer moves your settings, and launch
options that still say `css-yaw-run` keep working.*

A surf and bhop helper for Counter-Strike: Source and Momentum Mod on Linux. It cycles
`cl_yawspeed` with one key and tells you which yawspeed is active, and it can train your
strafes.

- **Yawspeed cycle:** one key steps through your yawspeeds. A short game sound plays when
  you switch, and only you hear it.
- **Crosshair colour:** your crosshair changes colour for each yawspeed. In Momentum Mod
  that's the game's own crosshair. CS:S has no crosshair without a weapon, so there it's a
  [KROSSHAIR](https://github.com/noahlyk/krosshair) crosshair.
- **Strafe trainer** (optional): a tone while you turn without the matching strafe key, and
  each strafe's offset in ticks on screen, with a key to show or hide it. See
  [Strafe trainer](#strafe-trainer).
- **Settings in the hub:** its settings are a section of
  [Soulmanyes's Movement Kit](../README.md), whose Modules page also installs its updates.

https://github.com/user-attachments/assets/40f99c9d-ba8a-4a52-8c9c-d5cf06575f16

![Source Yaw's settings in the Movement Kit hub](docs/screenshot.png)

## What you need

- Linux, and the native Linux version of CS:S or Momentum Mod on Steam. Steam from your
  distro's packages works. Flatpak Steam doesn't, because `movekit-run` can't run inside
  its sandbox.
- Python 3 and Pillow. `install.sh` installs them with pacman, apt or dnf if they are missing.
- [Soulmanyes's Movement Kit](../README.md#install) for the settings. Its installer brings what
  its window needs.
- For the crosshair colours in CS:S: KROSSHAIR. If it isn't installed, the app can install
  it for you (see below). crosshair-maker is optional. Momentum Mod needs neither.
- For the strafe trainer: a C compiler and `make` (to build its overlay), PipeWire's
  `pw-cat` (for the tone, part of PipeWire) and a one-time `sudo` to install its input
  service.

Tested on CachyOS (Arch), Debian 12 and Ubuntu 22.04, so newer releases of these and
distros based on them (Mint 21 and newer, Pop!_OS, Manjaro, EndeavourOS) should work too.
Fedora and openSUSE Tumbleweed have new enough packages but are untested. On openSUSE,
install the dependencies yourself.

## Install

Two ways, and they end up the same:

- **In the hub:** install [Soulmanyes's Movement Kit](../README.md#install) and click **Install**
  on the Source Yaw card of its Modules page. The card runs the same `install.sh`, but it has no
  terminal to ask for your password: if Python or Pillow is missing, it stops
  with an error. Install them (or run `install.sh` once in a terminal), then press Install again.
- **On its own:**

  ```sh
  curl -fsSL https://raw.githubusercontent.com/Soulmanyes/movement-kit/main/sourceyaw/install.sh | sh
  ```

  It installs the latest release. Or clone the repository and run `./install.sh` from it. Run the
  same command again to update. The settings still open in the hub, so install it too: the first
  time it starts, it takes this copy over as its Source Yaw module, and its Modules page updates
  it from then on.

Then:

1. Open **Source Yaw** (from the app menu, or `sourceyaw`); it opens the hub on Source Yaw's
   section. If you have both games, pick one at the top; each has its own
   settings. Pick your key, yawspeeds, colours and sounds, and press **Apply**.
2. Turn on **Load from autoexec.cfg**, or add `exec yaws.cfg` to your `autoexec.cfg` yourself.

That's all Momentum Mod needs. For CS:S's crosshair colours, also:

3. Add `movekit-run` right before `%command%` in the CS:S launch options. The app shows
   your current launch options with it added, ready to copy. With no other options:

   ```
   movekit-run %command%
   ```

   If Steam can't find `movekit-run` (it lives in `~/.local/bin`), the app shows the full
   path instead. `movekit-run` is the launch option all of the movement tools share: it
   starts each one that is installed (see the repository's README to turn one off per game).
   `sourceyaw-run`, its name before, still works and starts only Source Yaw.

To remove the app, press **Uninstall** on its card in the hub, or run the install command with
`--uninstall`. Then take `movekit-run` (or `sourceyaw-run`) out of the launch options, unless
another movement tool still uses it:

```sh
curl -fsSL https://raw.githubusercontent.com/Soulmanyes/movement-kit/main/sourceyaw/install.sh | sh -s -- --uninstall
# or, from a clone:
./install.sh --uninstall
```

The command asks whether to remove `yaws.cfg` and its `autoexec.cfg` line too; the card always
removes them, and keeps your settings unless you tick **Also delete saved data**. If you installed the strafe
trainer's input service, the uninstall prints the command that removes it.

If you already had a `yaws.cfg` of your own, the app saves it as `yaws.cfg.bak-sourceyaw`
before writing its own, and uninstalling puts it back.

## Settings

- **Cycle key:** press any key, mouse button or wheel direction to bind it. If that key is
  already bound to something else, the app tells you what.
- **Yawspeeds:** add, remove or drag them into order. Each one has a crosshair colour and a
  sound, which you can preview from the dropdown. The ticked one is set when the game starts.
- **Change crosshair colour:** turn the colour changing off if you only want the sounds.
  In Momentum Mod, turning it off puts your own crosshair colour back.
- **Crosshair** (CS:S): the image that gets recoloured. Choose your crosshair-maker crosshair if
  you use it, the built-in plain cross, or any PNG. The crosshairs that come with KROSSHAIR
  are offered in the file picker.
- **KROSSHAIR** (CS:S): if it isn't installed, **Install** downloads KROSSHAIR 0.2.5 (GPL-3.0,
  x86_64 only) from its GitHub releases into your user folder. No password is needed, and
  nothing is downloaded unless you press it.
- **Updates:** the Source Yaw card on the hub's Modules page shows new releases, with **Update**,
  an auto-update switch and roll back. Source Yaw's own window and its update banner retired in
  Movement Kit 3.8; a copy that still has the old window turns into the launcher at its next
  update.

If the game is already running when you press Apply, run `exec yaws` in the console.

## Strafe trainer

While a jump key is held, the trainer listens to your strafe keys, turn keys and mouse:

- **Tone:** while you turn one way without that way's strafe key held, a constant tone plays
  until you press the right key. Holding the other strafe key and holding none have their
  own switches and their own pitch (the no-key tone is lower). You can pick a game sound
  instead, which repeats while the key stays wrong.
- **Offset:** for each strafe, the ticks between turning the other way and switching
  strafe keys: minus is early, plus is late. Your best offset (-1 by default) shows in the
  on-time colour. Position, size and colours are settings, and **Show in game** previews
  them in the running game. An optional **Offset key** shows or hides the number in game
  with one press.

It only counts while the game's window has focus and the cursor is inside it (on Hyprland;
other desktops can't be asked, so there it always counts) and while a map is loaded, so
scrolling in the main menu or another window stays quiet.

It reads your binds from the game's `config.cfg`, following aliases, so null binds and turn
binds (`+left`/`+right`) work as they are. The tickrate is picked from the map (`surf_` maps
66, `bhop_` maps 100); on other CS:S maps it uses the tickrate you set in the app.

Setup:

1. Install the input service once, in a terminal (the app shows the command):

   ```
   sudo sh ~/.local/share/sourceyaw/inputd/install-inputd.sh
   ```

2. Turn on **Strafe trainer** in the app and press **Apply**.
3. Add `movekit-run` before `%command%` in the game's launch options (Momentum Mod needs
   it too for the trainer).

**About the input service.** Under Wayland a game holds the pointer, so the trainer reads
keys and mouse from `/dev/input`, which needs root. A small root service does that and
passes on only the keys listed in `/etc/sourceyaw-inputd.conf` (by default A, D, Space, left
Alt, L, O, P, the two main mouse buttons, mouse X and the wheel), and only to your user.
Nothing else you type reaches the trainer or any other program. The list is root-owned so
programs running as you can't widen it; add keys there if your binds use others (the app
tells you which). The service starts when the trainer connects and stops 30 seconds after
it leaves.

Offsets are measured from your keyboard and mouse at the OS, not from the game's own input
ticks, so they can differ from a server's offset display by about one tick.

## How it works

- The app writes `cfg/yaws.cfg`. In it, each press sets the next `cl_yawspeed` and plays its
  sound with `play`.
- **Momentum Mod:** each press also runs a small cfg in `cfg/yaws_colors/` that sets
  `cl_crosshair_color` to that yawspeed's colour.
- **CS:S:** each press also runs `echo YAW_<speed>`, and `con_logfile yaw.log` copies the
  console to a file. `movekit-run` wraps the game. It rebuilds `yaws.cfg` and the coloured crosshairs from
  your settings, then starts the game with `KROSSHAIR=1` and
  `KROSSHAIR_IMG=~/.config/sourceyaw/current.png`. While the game runs, it watches
  `yaw.log` and copies the matching colour over that file on each `YAW_<speed>` line.
  KROSSHAIR reloads the file whenever it changes.

- **Strafe trainer:** `movekit-run` starts `trainer.py` beside the game and turns on the
  Source Yaw overlay, a small Vulkan layer (in `overlay/`, a fork of KROSSHAIR) that draws
  the offset. The trainer passes the number through a tiny shared file the layer reads each
  frame, so nothing is reloaded while you play, and the layer does no work while the number
  is hidden. In Momentum Mod, `yaws.cfg` also turns on `con_logfile yaw.log` so the trainer
  can see which map loads.

Settings and generated images are stored in `~/.config/sourceyaw`.

## Limits

- Recolouring is flat: every visible pixel of the crosshair gets the chosen colour, so
  outlines lose their own colour.
- If another config changes `cl_yawspeed` directly, the colour isn't updated until the
  next press of the cycle key.
- The strafe trainer can't see in-game menus: with a map loaded, scrolling in the pause
  menu or console still counts as jumping.

## License

[CC0 1.0](LICENSE). Public domain, do what you like. Source Yaw plays sounds straight from
your own game install, and KROSSHAIR is only downloaded from its own releases if you ask for
it. The only other connection is the hub's update check to GitHub.

The one exception is the strafe trainer's overlay in [`overlay/`](overlay/): it is a fork
of KROSSHAIR and stays under the [GPL-3.0](overlay/LICENSE), with the Vulkan headers it
builds against (Apache-2.0 or MIT) and stb_image (public domain or MIT). See
[overlay/README.md](overlay/README.md).
