# Strafe Trainer

A strafe trainer for Counter-Strike: Source and Momentum Mod on Linux and Windows. It plays a sound
when you turn without the matching strafe key or hold both, and on Linux it shows each strafe's
key timing in ticks on screen. It was part of [Source Yaw](../sourceyaw/) until Source Yaw 1.11.0.
If you had the trainer on in Source Yaw, updating Source Yaw installs it, with your trainer
settings copied over.

- **Sounds:** three cues, each with its own switch, sound, pitch and wait (see [Cues](#cues)).
- **Offset** (Linux): for each strafe, the ticks between turning the other way and switching
  strafe keys, drawn over the game, with a key to show or hide it.
- **Settings in the hub:** its settings are a section of
  [Soulmanyes's Movement Kit](../README.md), whose Modules page also installs its updates.

## What you need

On Windows, only the hub. On Linux:

- The native Linux version of CS:S or Momentum Mod on Steam (not Flatpak Steam: `movekit-run`
  can't run inside its sandbox).
- [Soulmanyes's Movement Kit](../README.md#install).
- PipeWire's `pw-cat` for the tone (part of PipeWire).
- A C compiler and `make`, to build the offset display when the module installs. Without them
  the trainer still plays its sounds.
- A one-time `sudo` to install the input service (see below).

## Install

Click **Install** on the Strafe Trainer card of the hub's Modules page. Then:

1. Open **Strafe Trainer** in the hub. If you have both games, pick one at the top; each has its
   own settings.
2. Turn on **Strafe trainer** and press **Apply**. Apply writes a short block into the game's
   `autoexec.cfg` (the console log the trainer reads, and the offset key's bind). If the game is
   already open, run `exec autoexec` in its console.
3. Add `movekit-run` before `%command%` in the game's launch options (Linux), or
   `"C:\full\path\to\movement-kit.exe" %command%` (Windows). The section shows yours with it
   added. Both games need it: the launch option starts the trainer beside the game.
4. On Linux, install the input service once, in a terminal. The section shows the command; with
   the hub installed the usual way it is:

   ```
   sudo sh ~/.local/share/movekit/kit/strafe-trainer/inputd/install-inputd.sh
   ```

**Uninstall** on its card takes the block out of `autoexec.cfg`, removes the offset display and
the launch hook, and keeps your settings unless you tick **Also delete saved data**. The input
service stays; remove it with the same command plus `remove`:

```
sudo sh ~/.local/share/movekit/kit/strafe-trainer/inputd/install-inputd.sh remove
```

## Cues

While a jump key is held, the trainer listens to your strafe keys, turn keys and mouse. Three cues:

- turning one way while holding the other strafe key,
- turning with no strafe key held,
- holding both strafe keys at once (it outranks the other two, as it causes them).

Each cue plays a constant tone at its own pitch until you fix the keys, or a game sound that
repeats while they stay wrong. The wait is how many ticks the mistake must last before it sounds,
and ▶ previews it.

**Offset** (Linux): minus is early, plus is late. Your best offset (-1 by default) shows in the
on-time colour. Position, size and colours are settings, and **Show in game** previews them in the
running game. An optional **Offset key** shows or hides the number in game with one press.

It only counts while the game's window has focus and the cursor is inside it (on Hyprland and
Windows; other Linux desktops can't be asked, so there it always counts) and while a map is
loaded, so scrolling in the main menu or another window stays quiet.

It reads your binds from the game's `config.cfg`, following aliases, so null binds and turn binds
(`+left`/`+right`) work as they are. The tickrate is picked from the map (`surf_` maps 66, `bhop_`
maps 100); on other CS:S maps it uses the tickrate you set.

Offsets are measured from your keyboard and mouse at the OS, not from the game's own input ticks,
so they can differ from a server's offset display by about one tick.

## On Windows

- No offset number: drawing over CS:S would mean hooking DirectX, which risks a VAC ban. The
  offset cards are hidden.
- It reads your keys through Windows' Raw Input, the same way games do. No service, no admin.
- Settings are in `%APPDATA%\strafe-trainer`, and what the launch did goes to `run.log` there. If
  something doesn't work, `run.log` says why.

## The input service (Linux)

Under Wayland a game holds the pointer, so the trainer reads keys and mouse from `/dev/input`,
which needs root. A small root service does that and passes on only the keys listed in
`/etc/sourceyaw-inputd.conf` (by default A, D, Space, left Alt, L, O, P, the two main mouse
buttons, mouse X and the wheel), and only to your user. Nothing else you type reaches the trainer
or any other program. The list is root-owned so programs running as you can't widen it; add keys
there if your binds use others (the section tells you which). The service starts when the trainer
connects and stops 30 seconds after it leaves. It kept its name from Source Yaw, so an input
service installed for Source Yaw keeps working.

## How it works

- **Linux:** `movekit-run` starts `trainer.py` beside the game and turns on a small Vulkan layer
  (in `overlay/`, a fork of KROSSHAIR) that draws the offset. The trainer passes the number through
  a tiny shared file the layer reads each frame, so nothing is reloaded while you play, and the
  layer does no work while the number is hidden. The layer lives in
  `~/.local/share/strafe-trainer/overlay`.
- **Windows:** the hub exe's launch step (`launch_win.py`) runs the trainer as a thread of that
  process, which ends with the game. It reads keys and mouse through Raw Input on a hidden window
  and plays its tone through `waveOut`.
- **Both:** the `autoexec.cfg` block turns on `con_logfile yaw.log`, so the trainer sees which map
  loads (the tickrate) and the offset key's echo.

Settings are stored in `~/.config/strafe-trainer` (`%APPDATA%\strafe-trainer` on Windows). The
first install copies them from Source Yaw's settings, once per game; Source Yaw keeps its copy, so
rolling Source Yaw back to 1.10 keeps the trainer it had. While such an older Source Yaw is
installed, this module stays off, so no cue plays twice.

## Limits

- The trainer can't see in-game menus: with a map loaded, scrolling in the pause menu or console
  still counts as jumping.

## License

[CC0 1.0](LICENSE). Public domain, do what you like. The trainer plays sounds straight from your
own game install and makes no connections of its own; the hub checks GitHub for updates.

The one exception is the overlay in [`overlay/`](overlay/): it is a fork of KROSSHAIR and stays
under the [GPL-3.0](overlay/LICENSE), with the Vulkan headers it builds against (Apache-2.0 or MIT)
and stb_image (public domain or MIT). See [overlay/README.md](overlay/README.md).
