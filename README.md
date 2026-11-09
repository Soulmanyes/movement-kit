# Soulmanyes's Movement Kit

Standalone surf, bhop and movement tools for Counter-Strike: Source and [Momentum Mod](https://momentum-mod.org/), in one repo with shared code.

| Tool | What it does | Runs on |
| --- | --- | --- |
| [Source Yaw](sourceyaw/) | Cycles `cl_yawspeed` with one key (bhop and surf lists), colours the crosshair per yawspeed (Linux) | Windows, Linux |
| [Strafe Trainer](strafe-trainer/) | Sounds when you turn without the matching strafe key or hold both, and each strafe's key timing in ticks on screen (Linux) | Windows, Linux |
| [Strafe Review](strafe-review/) | Records every attempt per tick and reviews it in the browser | Windows, Linux |
| [Gain Converter](gain-converter/) | Converts CS:S SSJ gain % to Momentum gain % and back | Windows, Linux |
| [Strafe Trainer Height](trainer-height/) | Lets Momentum's strafe trainer be dragged taller in the HUD editor | Windows, Linux |
| [JHUD](jhud/) | Shows each bhop or surf jump's speed, gain % and sync in the middle of the screen in Momentum, in one colour or coloured by gain or speed pace, set up in its HUD editor | Windows, Linux |
| [Strafe Speed Histogram](strafe-histogram/) | Shows a bar per air tick for how fast you turn against the optimal, scrolling up, while you bhop or surf in Momentum, set up in its HUD editor | Windows, Linux |
| [First Jump HUD](first-jump/) | Shows how jump 1 of a bhop or surf run went in Momentum: landing speed, gain %, gain per strafe, what lost each strafe the most and the biggest mistake, set up in its HUD editor | Windows, Linux |
| [Zone Exit Speed](zone-exit/) | Shows your 3D speed leaving the start zone in Momentum's surf, coloured by how good the pre jump was, and the difference to your PB's, set up in its HUD editor | Windows, Linux |

The kit is one program, the hub, and the tools are modules it installs. A fresh hub has none; each tool is installed, updated, rolled back and uninstalled from its card on the hub's Modules page, so a tool you don't use is never downloaded. Each tool's folder has its own README with what it needs and how it works.

| Source Yaw | Strafe Review | Gain Converter |
| --- | --- | --- |
| ![Source Yaw](sourceyaw/docs/screenshot.png) | ![Strafe Review](strafe-review/docs/screenshot.png) | ![Gain Converter](gain-converter/docs/screenshot.png) |

## Install

**Windows:** download `hub-windows.zip` from the [latest hub release](https://github.com/Soulmanyes/movement-kit/releases?q=hub-v&expanded=true), unzip it to a folder you keep and double-click `movement-kit.exe`. Windows Defender or SmartScreen may warn, because the exe isn't signed. `WINDOWS.txt` in the zip has the steps.

**Linux:** needs Python 3.10 or newer and [pywebview](https://pywebview.flowrl.com/) (`python-pywebview` on Arch).

```sh
curl -fsSL https://raw.githubusercontent.com/Soulmanyes/movement-kit/main/movekit/install-hub.sh | sh
```

It downloads the newest hub release, copies the core (`movekit/` and `hud/`) to `~/.local/share/movekit/kit`, adds **Soulmanyes's Movement Kit** to the app launcher and links `movekit-run` into `~/.local/bin`. Run it again with `sh -s -- --uninstall` to remove the launcher; the core goes too once no module is left.

Then open the hub. It starts on the Modules page:

- The cards come in groups: the core, the tools, then the HUD modules (the ones set up in Momentum's HUD editor), installed ones first. Tools that don't run on your OS are listed greyed out at the bottom, with no Install button.

- **Install** on a tool's card downloads it and runs its installer (Strafe Review needs Momentum Mod installed; Source Yaw on Linux needs its system packages, see its README). Each card says which games the tool works with.
- **Update** shows when a new version is out, with **What's new** for its release notes. **Update all** at the top updates every card that has one.
- After the hub or a tool updates, a **What's new** window shows the release notes once, including those of any versions skipped.
- **Roll back** returns to the version before the last update.
- **Uninstall** removes the tool, its game files, its `autoexec.cfg` block and its launch hook. Saved data (attempts, settings) stays unless you tick **Also delete saved data**.
- Auto-update is off for every tool and for the hub itself. A card with it off shows an amber **Auto-update off** strip; **Turn on** turns it on.

A copy of this repository (`git clone`) runs as it is: `./movekit/install-hub.sh` adds the launcher running from the clone, the cards use the tools in it and say they are updated by `git pull`, and uninstalling a tool takes it out of the game and the hub but leaves its folder.

To test changes next to an installed kit, a clone has a dev kit (Linux): `./movekit/movekit-dev` opens the hub from the clone as **Movement Kit (dev)**, a separate app with its own files in `~/.local/share/movekit-dev`. Its first start copies the installed kit's state and installs the same tools there, from the clone. It never changes the installed kit's files, hooks or `movekit-run`. Settings in `~/.config` and the game folders are shared, and a copy of the settings from before the first dev start is kept in `~/.local/share/movekit-dev/config-before-dev`. Installing a tool in the dev kit writes the clone's version of its game files, so reinstall that tool in the installed kit afterwards. The game runs with the dev kit through `movekit-dev run %command%` instead of `movekit-run %command%`. `movekit/devkit.py` describes the setup.

## Layout

```
movekit/          the shared Python package (standard library only)
sourceyaw/        Source Yaw
strafe-trainer/   Strafe Trainer
strafe-review/    Strafe Review
gain-converter/   Gain Converter
trainer-height/   Strafe Trainer Height
jhud/             JHUD
strafe-histogram/ Strafe Speed Histogram
first-jump/       First Jump HUD
zone-exit/        Zone Exit Speed
hud/              in-game display settings, shared by the tools that draw in game (hub section)
hub/              the hub's Windows exe: entry point, build script and release line
.github/          the Windows builds and the module releases
```

`movekit` holds what the tools used to copy between them: Steam and game discovery, autoexec cfg blocks, VPK reading, bind and alias parsing, and the GitHub release updater. It also has the game session (`session.py`), the patched Momentum HUD files several tools share (`panorama.py`, which writes them into the game's `custom/0-movekit`), the launch wrapper (`movekit-run`) and a reader for Strafe Review's saved attempts (`attempts.py`, format in [strafe-review/FORMAT.md](strafe-review/FORMAT.md)). A tool imports it from the folder above its own: the repo root in a clone, the core's folder when the hub installed it (modules sit next to the core's `movekit`).

`movekit/hub.py` is the hub: the Modules page (`movekit/modules.py` is the manager behind it) and one section per installed tool. Strafe Review (status, Open review and Stop), Gain Converter, Source Yaw (the same settings as its old window; on Windows without the crosshair parts) and Strafe Trainer (on Windows without the offset display) have sections, and the HUD settings (`hud/`, part of the core) show while Strafe Review, Strafe Trainer Height or a tool set up in the game's HUD editor (JHUD, Strafe Speed Histogram) is installed. It is the one part of `movekit` that needs a package outside the standard library: [pywebview](https://pywebview.flowrl.com/). A tool is a module through its `module.json` (key, release line, the core version it needs, its saved data, and a card for the HUD section if it has one) and `module_hooks.py` (install, uninstall, launch).

## Launch option

One Steam launch option starts every installed tool that needs to run beside the game. The game always starts with its own arguments, also with no tool installed or one that fails.

- **Linux:** put `movekit-run` right before `%command%`, for example `movekit-run %command%`. Each tool's installer registers its part with it (a launch hook, linked into `~/.local/share/movekit/hooks`).
- **Windows:** `"C:\full\path\to\movement-kit.exe" %command%`, with the quotes and your real path.

Tools that don't fit the game skip themselves: Strafe Review only runs for Momentum Mod. On Linux, to turn a tool off for one game, list the ones you want in `~/.config/movekit/settings.toml`; a game it leaves out runs every installed tool:

```toml
[launch]
momentum = ["strafe-review", "sourceyaw"]
css = ["sourceyaw"]
```

The older per-tool options still work and start only their own tool: `sourceyaw-run %command%`, `strafe-review-run sourceyaw-run %command%`. Strafe Trainer, which was part of Source Yaw until 1.11.0, runs wherever Source Yaw does: under `sourceyaw-run`, and for a game whose `[launch]` list names `sourceyaw`. On Windows, a launch option that still names `strafe-review.exe` keeps working (see Releases).

## Releases

Each tool keeps its own version and its own tags: `sourceyaw-v1.8.0`, `strafe-review-v1.6.0`, `gain-converter-v1.3.0`. A pushed tool tag attaches `<tool>-module.zip` (the tool's folder) and `<tool>-module.json` (its manifest) to that release; the hub only offers releases that have them. The hub itself, the core, has the line `hub-v*`: the Windows exe (`hub-windows.zip`) and, on Linux, the source archive that `install-hub.sh` installs. Its card on the Modules page updates it like a tool.

A `strafe-review-v*` tag also builds `strafe-review-windows.zip`, the hub exe under Strafe Review's old name, so a copy of the old standalone exe that updates itself turns into the hub, installs the Strafe Review module on its first start, and keeps its Steam launch option.

The tools used to live in their own repos (`Soulmanyes/sourceyaw`, `Soulmanyes/strafe-review`, `Soulmanyes/gain-converter`), and their history and tags came along. Each old repo's last release points its tool's updater here.

## Licence

CC0 1.0 (see [LICENSE](LICENSE)), except `strafe-trainer/overlay/` (in `sourceyaw/overlay/` before Source Yaw 1.11.0), which is GPL-3.0 (see [its LICENSE](strafe-trainer/overlay/LICENSE)) and includes the Vulkan headers and stb_image under their own licences. The Windows exes also bundle Python and other parts under their own licences; [hub/THIRD-PARTY-NOTICES.txt](hub/THIRD-PARTY-NOTICES.txt) lists them. (Gain Converter's own small exe, which bundled Tcl/Tk, was last built for `gain-converter-v1.2.0`; it is the hub's Gain Converter section now.)
