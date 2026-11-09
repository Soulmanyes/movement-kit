# Soulmanyes's Movement Kit: plan

Status (2026-11-02): Phase 0 done locally (the three repos merged with full history, tags renamed `<tool>-v*`, privacy hooks in place; no GitHub repo yet). Phase 1 nearly done locally: Steam/game discovery, autoexec blocks, VPK reading, bind parsing and the updater are in `movekit`, release CI sits at the root, and the root has a README and a CC0 LICENSE (see "Progress"). On GitHub since 2026-11-02, public since 2026-11-02 (via `/go-public`). The live installs run from the monorepo since 2026-11-02, and both tools write `// movekit:<tool>` blocks. Bridge releases out 2026-11-02 (Source Yaw v1.5.2, Strafe Review v1.4.1; the kit's first releases sourceyaw-v1.6.0, strafe-review-v1.5.0, gain-converter-v1.1.0). The old repos were archived 2026-11-03. Phase 2 started: 2.1 (yaw.log reading, `movekit/logtail.py`) 2.2 (session core, `movekit/session.py`) and 2.3 (the Strafe Review server hosts the session and announces saved attempts) and 2.4 (the trainer and the crosshair watcher on the session, live) done. 2.5 (`movekit-run`, one launch option) done and live. 2.6 (attempt format 1 documented in `strafe-review/FORMAT.md`, reader `movekit/attempts.py`) done. Phase 3 (hub app): toolkit decided (pywebview settings window, review page stays in the browser), steps 3.1–3.8 OK'd; 3.1 (shell), 3.2 (Gain Converter section), 3.3 (HUD section), 3.4 (Strafe Review section), 3.5 (Source Yaw logic out of the window) and 3.6 (Source Yaw section, awaiting the owner's click test) done 2026-11-02; 3.7 and 3.7b (modules) released 2026-11-02 (`hub-v1.0.0`, every tool as a module). 3.8 (retire the old windows) released 2026-11-02 (`sourceyaw-v1.8.0`, `gain-converter-v1.3.0`). 3.9 (the HUD's settings move to the kit's folder, the review page's jump-1 toggle goes) released 2026-11-02 (`hub-v1.1.0`, `strafe-review-v1.7.0`). Left: the Windows hand test. Phase 4 (Panorama module kit) planned and OK'd 2026-11-03; 4.1 (the kit) and 4.2 (Strafe Review on the kit) released 2026-11-03 (`hub-v1.2.0`, `strafe-review-v1.8.0`); 4.3 (Strafe Trainer Height as a module) released 2026-11-03 (`hub-v1.2.1`, `trainer-height-v1.0.0`).

## Goal

One home for every standalone surf, bhop and movement tool: Source Yaw, Strafe Review, Gain Converter and the ones still to come. Shared code lives in one place, so a fix or a new game reaches every tool at once and a new tool starts from working parts instead of copies.

## Names

- Display name: **Soulmanyes's Movement Kit**. It goes in the README title, the GitHub description and window titles.
- Repo `Soulmanyes/movement-kit`, folder `~/claude/movement-kit` (owner, 2026-11-02).
- Technical name: `movekit`. It's used for the Python package, the launch option `movekit-run`, data dirs and cfg block markers.

## Decisions so far (2026-11-02)

- **Monorepo**, not a core repo copied into each tool's repo by a sync script, and not a hub app straight away. A sync script would mean a sync plus one release per tool for every core fix.
- One folder per tool and a tag prefix per tool: `sourceyaw-v1.6.0`, `strafe-review-v1.5.0`, `gain-converter-v1.1.0`. Each tool keeps its own version and release.
- Phased: every phase ends with working, released tools.
- **End goal: one hub app**, one window with a section per tool (decided 2026-11-02). It comes last, as Phase 3, but every phase builds toward it: tool logic lives in `movekit` or the tool's own modules, not in its window code; tools talk through the Phase 2 session daemon and a local API rather than to each other; new UI is written so it can become a hub section.

## Layout (target)

```
movement-kit/
  movekit/              shared Python package, stdlib only
    games.py            the supported games as data (app ids, mod folder, install folder names)
    keyvalues.py        Valve KeyValues reader (flat pairs and nested)
    steam.py            Steam roots, libraryfolders.vdf, appmanifests (Linux, Flatpak, Windows registry)
    check_*.py          fixture checks, no game or Steam needed
    files.py            atomic file writes
    cfgblock.py         named autoexec blocks: // movekit:<module> begin/end, CRLF-safe, backup, uninstall
    vpk.py              read files out of VPKs
    binds.py            config.cfg binds and aliases
    logtail.py          follow con_logfile (yaw.log), CRLF, rotation, map load / tickrate lines
    launch.py           movekit-run's plan: the game, the registered launch hooks, settings.toml
    movekit-run         the one Steam launch option (bash), sources each tool's launch hook
    gain.py             CS:S SSJ <-> Momentum gain formula
    updater.py          GitHub releases filtered by tag prefix; source-install and frozen-exe modes
    paths.py            data/config dirs per OS, PyInstaller resource root
  sourceyaw/            the app as now, importing movekit
  strafe-review/        recorder, collector, viewer as now, importing movekit
  gain-converter/
  .github/workflows/    one reusable build-and-release workflow; one small caller per tool
```

Licences: own code CC0. `sourceyaw/overlay/` stays GPL-3 in its own folder with its own LICENSE, as now. Check third-party licences again before the first push.

## What is duplicated today (the Phase 1 work list)

| Concern | Source Yaw | Strafe Review | Other |
| --- | --- | --- | --- |
| Steam/game discovery | `yawcore.py` `find_game`, `_steam_libraries`, `_parse_vdf`, `steam_path` | `collector/steam.py` | |
| Updater | `updater.py` (source archive + install.sh, daily) | `collector/updater.py` (frozen exe swap, 6 h) | Gain Converter has none |
| autoexec blocks | `yawcore.set_autoexec` | `install.py` `set_autoexec`, `without_block`, `write_atomic` | |
| VPK reading | `yawcore._vpk_tree`, `_read_from_vpk` | `install.py vpk_files` | |
| Binds | `trainer.read_binds`, `yawcore.keys_bound_to_cycle` | `viewer/server.py game_mouse` | |
| yaw.log reading | `yaw-watch.sh`, `trainer.map_state`, `map_tickrate` | `collector.follow` | |
| Gain formula | | viewer CSS-SSJ JS | `gain_converter.py` |
| Launch wrapper | `yaw-run` | `strafe-review-run` (chained) | |

Strafe Review's version is usually the better tested one (CRLF, Windows, HUD-mod order). Start from it.

## Phase 0: the repo

1. Create `~/claude/movement-kit` as git. Merge the `sourceyaw`, `strafe-review` and `gain-converter` histories into their subfolders (`git subtree add` or `merge --allow-unrelated-histories` after moving each into its folder), so every old commit stays in `git log`.
2. Set up the privacy guards before the first push: hookify copies, git hooks, and the path regex in `.claude/hookify.public-repo-privacy-files.local.md`. Add it to the release-repo list.
3. Make the GitHub repo private first. Going public goes through `/go-public movement-kit`.

## Phase 1: `movekit` core, no change in behaviour

1. Extract one concern at a time into `movekit/`, in the order of the table. After each one, both tools still pass their checks (`strafe-review/smoke_test.py`, `viewer/check_*.js`, `recorder/check_recorder.py`, Source Yaw sandbox apply with HOME/XDG_CONFIG_HOME pointed at a sandbox).
2. **Game adapters.** `movekit/games.py` holds each game as data (`Game`: key, name, app ids, mod folder, install folder names, name hint, env override). It grows the rest (cfg dir, log path, tickrate for a map name, Panorama or not) as each concern moves in; it becomes a `games/` package only if a game needs code of its own. Tools ask it and never hard-code a game.
3. **cfg blocks.** Every tool writes its own `// movekit:<tool> begin/end` block. Migrate the old `// strafe-review begin` block and Source Yaw's `exec yaws.cfg` line on the next install.
4. **Updater.** One class, two install modes (source + install script on Linux, exe swap on Windows). It lists releases and picks the newest tag with its own prefix, not `releases/latest`. It keeps the state file, auto flag and `failed` loop guard from Strafe Review.
5. **Release CI.** One reusable workflow (PyInstaller one-file, smoke test on the Windows runner, licence zip), triggered by `<tool>-v*` tags. The current Strafe Review and Gain Converter workflows are the base.
6. **Bridge releases.** These are the last release in each old repo. Their updater points at `Soulmanyes/movement-kit` with that tool's tag prefix, and Source Yaw's `install.sh` (the `curl | sh` one) forwards to the new repo. Then the old repos get archived. This step must ship before archiving, or installed copies stop updating: the friend's Windows exe, and Source Yaw installs.

Done when: both tools are released from the monorepo, with no duplicated code from the table left, and an old install updates itself onto the new repo.

## Phase 2: one session, one launch option

- **Session daemon.** One reader of `yaw.log` per game session publishes events, and the trainer, the crosshair watcher and the Strafe Review collector listen instead of each tailing the log. Design (2026-11-02; Claude proposed it and chose the details, the owner left the internals to Claude since they change nothing in play):
  - `movekit/session.py`: `Session` reads the log through `logtail` and publishes on a `Bus`; served as server-sent events on `http://127.0.0.1:8766/events` (plus `/status`), localhost only, stdlib only, so it also runs in the Windows exe. Browsers (the future hub page), Python and Windows can all listen.
  - Hosted inside the Strafe Review server when that runs (it already runs the whole session and is the only process on Windows); otherwise `python -m movekit.session` runs it alone. Whoever binds port 8766 first serves; the rest listen. (Picked over "always its own process": no new program for the Windows exe.)
  - Events (`{"id", "type", "time", "data"}`): `map_loaded {name}`, `map_left`, `token {name}` (YAW_<speed>, SY_OFFSETS; sent before the line break arrives, chat ignored), `attempt_saved {dir, id}` from the collector, `game_exit` from the launch wrapper. Tickrate stays each tool's own setting, worked out from the map name.
  - The Strafe Review collector keeps its own `logtail.follow` (it needs every raw SRREC line, from the top of the log); the session in the same process reads the log for everything else. So "one reader" holds per process, not literally. Feeding the collector from the session would mean replaying the old log to every listener on start.
  - Joining (2.4, Claude's call): a tool calls `session.join(log)`. It hosts when 8766 is free, listens when the session there reads the same log (`os.path.samefile`), and otherwise runs a private `Session` for its own log without serving it. That last case is real: the Strafe Review server keeps serving Momentum's log for days after the game quits, so a CS:S launch finds 8766 busy with the wrong log. A listener takes the port over when the host goes away. The Strafe Review server retries hosting every 5 s, so a trainer that got the port first (it starts while the server's unit is still coming up) only holds it until its game exits. This refines "whoever binds first serves".
  - Changed from the first plan: key presses from `sourceyaw-inputd` stay a direct socket to the trainer. Routing them through the daemon only adds delay to strafe timing, and the trainer is their only user. `jump` events wait until a tool needs them.
- **`movekit-run %command%`.** One Steam launch option that starts whichever tools are turned on (one settings file), instead of chained `strafe-review-run sourceyaw-run`. The old wrapper names stay as links for a while.
- **Attempt format.** Version the srrec attempt format as a documented schema, so new tools (histograms, progress over time, JHUD) read attempts without touching the collector.

## Phase 3: hub app

Toolkit and split decided by the owner 2026-11-02; steps 3.1–3.8 OK'd the same day. Release line of its own, tag prefix `hub-v*`.

**Split (owner).** The hub is a real app window for **settings**. Strafe Review's review page stays in the browser, as now. Sections:
- **Source Yaw**: everything its GTK window does.
- **HUD**: in-game display settings, whichever tool draws them. Starts with the jump-1 line toggle. That toggle sits in the review page's sidebar today only by accident, because the recorder draws the line. Later the per-jump stat display (JHUD) and the Panorama module kit join it.
- **Gain Converter**: the converter and its graph.
- **Strafe Review**: collector and update status, and an "Open review" button. The button starts the server if it isn't running, then opens the browser.

**Toolkit (owner): pywebview.** A native window showing HTML pages, with WebKitGTK on Linux (installed here) and WebView2 on Windows (part of Windows 10/11).
- Licence BSD-3. On Arch it's `python-pywebview` in extra (6.2.1); the Windows exe bundles it.
- Section pages share CSS with the review page.
- Its file dialogs return real paths, so Source Yaw keeps "Choose an image…" as it is.
- Key capture uses a `KeyboardEvent.code` to Source-name map in place of `GDK_TO_SOURCE`. Super never arrives (Hyprland takes it), as in the GTK window. Keys that can't be caught get a pick-from-list fallback.
- Previews keep Pillow (`yawcore.recolor`), so the exe bundles Pillow.

**Shape.**
- `movekit/hub.py` opens the window and serves the shell page: a sidebar of sections, with shared CSS following `ui-visibility` (strong card fill and border, bar tracks, typeable number boxes).
- **Section contract.** Each section folder has a `hub_section.py` with `SECTION = {key, title, os, page, api}`. `api` holds plain functions taking and returning JSON-able data. The page calls them as `pywebview.api.call(key, name, args)`. The hub discovers sections by folder and never imports tool internals, so a new tool is a new folder. Pages that want live events read the session on 8766 over SSE.
- **Lifetime.** The hub is only the settings window, opened and closed by hand. The Strafe Review server keeps its current lifetime (launch hook on Linux, the exe on Windows), so collecting doesn't change.
- **HUD home.** A new top-level `hud/` folder owns in-game display settings. The jump-1 setting's code (`install.save_setting("inGameLine")`, `/api/settings` in `viewer/server.py`) moves there. The recorder install stays in Strafe Review, and `hud/` asks it to rewrite the setting.

**Prerequisite:** the Phase 1 bridge releases, shipped 2026-11-02 (see Phase 1.7). Archiving the old repos doesn't block the hub; the owner started 3.1 before it (2026-11-02). The Windows hub exe replacing the Strafe Review exe is a second migration for installed copies, so it waits until the first one has shipped.

**Steps** (the old windows keep working throughout; checks: the existing ones plus a screenshot check of each new section):
1. **3.1 Shell.** `movekit/hub.py`, section discovery, the `call` bridge, shared CSS, and `movekit/check_hub.py` (discovery, bridge and OS filter, run without a window). Install `python-pywebview`.
2. **3.2 Gain Converter section.** The simplest section, so it proves the contract. It settles "gain math in one language": one JS module `movekit/web/gain.js` for every page. (Found in 3.2: the viewer has no copy of the conversion curve; its CSS-SSJ code scores ticks, a different calculation. So `gain.js` serves the section, and `gain_converter.py` keeps its copy until 3.8, held equal by `gain-converter/check_gain.py`.)
3. **3.3 HUD section.** `hud/` takes over the jump-1 setting. The review page's sidebar toggle stays until the hub ships on Windows (3.7), then goes. (Done in 3.3: the settings file stays in Strafe Review's data folder until 3.7, because installed v1.5.0 exes read and write it there. Both moved in 3.9.)
4. **3.4 Strafe Review section.** Status, the updater, "Open review" (starts the server if it's down). (Done in 3.4: the viewer's colours come from `movekit/web/tokens.css`, the one copy.)
5. **3.5 Source Yaw logic out of the window.** Most of it is already in `yawcore` (`load_settings`, `validate`, `apply`, `key_conflicts`, `set_autoexec`, `install_krosshair`, `recolor`). Still in `app.py`: `check_setup`'s problem text, `base_options`, `collect`, `trainer_value` and the trainer status. They move to `sourceyaw/settings_api.py`, and the GTK app calls it, with no change in behaviour.
6. **3.6 Source Yaw section** over `settings_api`: key map with fallbacks, colours, sounds and previews. Linux-only for now; a Windows Source Yaw stays a later item.
7. **3.7 Hub release.** `hub-v*` CI (PyInstaller, pywebview and Pillow included) and a desktop entry on Linux. On Windows, one exe: no arguments opens the hub, `%command%` stays Strafe Review's launch option, and the last `strafe-review-v*` release updates itself into it.
7b. **3.7b Modules** (owner request 2026-11-02, see "Phase 3.7b"): per-tool install, update, auto-update switch, roll back and uninstall from the hub, on Windows and Linux. Comes before `hub-v1.0.0`.
8. **3.8 Retire the old windows** after the owner has used the hub for a while. The GTK app and the tkinter app go, or become thin launchers that open the hub. (Started 2026-11-02 at the owner's go-ahead, see "Phase 3.8".)

Done when: the hub window runs on Linux and Windows with every section, the review page opens from it, and installed copies have moved onto it.

## Phase 4: Panorama module kit (planned and OK'd 2026-11-03; done and released 2026-11-03: `hub-v1.2.0`, `strafe-review-v1.8.0`, `hub-v1.2.1`, `trainer-height-v1.0.0`)

The owner picked this from "Later" on 2026-11-03, as a phase of its own (not as the first step of JHUD).

**Problem.** Momentum mounts the folders in `custom/` in alphabetical order (any case), and the first copy of a file wins. Every tool that changes a game HUD file solves that alone:
- The Strafe Review recorder (`strafe-review/install.py`) writes `custom/0-strafe-review` with a `timer.xml` made on every install: the copy that would win otherwise, plus one `<include>`. That is the fix for the friend's `panoDev` (2026-10-28).
- `~/claude/mmod-trainer-height` (no git, outside the kit) copies three files into `custom/strafe-trainer-height` with `install.sh`. Linux only, a fixed game path, no sort-order fix, no hub card.
- A future JHUD would need the same thing a third time. Two tools patching the same file (both `timer.xml`) would hide each other's include.

**Found 2026-11-03.** Diffed against the game's own files, the trainer-height mod changes one line in each:
- `layout/hud/strafe-trainer.xml` adds `<include src="file://{resources}/styles/hud/strafe-trainer-height.scss" />` after the `main.scss` include.
- `scripts/hud/strafe-trainer.ts` changes `resizeY: false,` to `resizeY: true,` (line 89).

So both are patches, the same kind as the recorder's `timer.xml`. The game's file is patched on the player's machine. No Momentum file goes into this public repo, so there is no licence question, and a game update to those files carries over instead of being hidden by a stale copy.

**Shape.**
- `movekit/panorama.py`, stdlib only, Momentum only. It takes a game folder, so `games.py` doesn't need a `panorama` flag yet; that comes with the first second Panorama game.
- **A tool's own files** (new names: the recorder script, the scss) stay in the tool's own `custom/` folder, written by the tool as now. `0-strafe-review` keeps its name: `recorder_settings.recorder()` and the hub's HUD section find the recorder there, and the frozen hub carries its own copy of that file (3.7 note).
- **Patched game files** go in one kit folder, `custom/0-movekit`. It sorts before `0-strafe-review`, so its copies win. Each tool's own folder holds a `movekit-panorama.json` listing its patches. A patch is `{file, find, replace}`: `find` must occur exactly once in the base file. A patch whose `replace` text is already in the base does nothing. So an old copy (a stale `0-strafe-review/timer.xml`, or `custom/strafe-trainer-height`) chosen as the base never gets a second include.
- **`sync(game)`** reads every manifest in `custom/*/movekit-panorama.json` and rebuilds `0-movekit` from scratch. It builds in a temp folder and renames it into place, under a lock file, so a recorder install at game start and a hub install at the same moment don't lose each other's patches.
  - For each patched file it finds the base: the first `custom/` folder in mount order that has the file, skipping `0-movekit`, else the game's own.
  - A VPK in `custom/` that has the file gets a warning, as `install.py` prints now (VPKs aren't read).
  - It applies every tool's patches in tool-key order.
  - When a patch's `find` text is missing (the game changed the file), that tool's patches for that file are left out, the file falls back to the base, and `status` reports it. The game still loads.
  - No manifests left: `0-movekit` is removed.
- **`install(game, tool, patches)` / `uninstall(game, tool)`** write or remove the tool's manifest, then `sync`. `status(game)` lists each tool's patches as applied or skipped, plus warnings, for the hub.
- Strafe Review already reinstalls the recorder on every start (Windows exe, Linux launch hook). That start now also runs `sync`, so another mod's update to a patched file still carries over.

**Old and new versions together.** The kit is in the core, so core 1.2.0 and `needs_core` 1.2.0 for the modules that use it.
- An old Strafe Review module on the new core keeps writing its own `timer.xml` into `0-strafe-review`. When a kit tool also patches `timer.xml`, `sync` picks that file as the base (it is first after `0-movekit`), so both includes load. The old `base_timer` doesn't skip `0-movekit`, though: it copies the kit's merged `timer.xml` into `0-strafe-review`. An include of a kit tool uninstalled since then stays in that copy until the old module's next install (the next game start). So JHUD, the first other tool patching `timer.xml`, should need Strafe Review 1.8.0 or later.
- A new module on an old core is refused by `needs_core`.

**Steps** (each one ends released, checks as before plus the new ones):
1. **4.1 Kit.** `movekit/panorama.py` and `movekit/check_panorama.py`, with a fake game folder. The check covers:
   - the base from a foreign folder, from the game, and a VPK warning;
   - two fake tools patching the same file, both kept;
   - a patch already present, applied once;
   - a missing `find`, skipped and reported;
   - uninstalling one tool keeps the other;
   - `sync` run twice gives the same result;
   - nothing left, so `0-movekit` is gone.

   Mutations: drop one tool's include, ignore the "already present" rule, don't skip `0-movekit` in the base search. Each must make the check fail.
2. **4.2 Strafe Review on the kit.** `install.py` hands its `timer.xml` include to the kit as a patch and no longer writes `timer.xml` into `0-strafe-review`; uninstall removes the manifest and syncs. The `panoDev` smoke test (`smoke_test.py`) must still end with one include. Release: core 1.2.0 (`hub-v1.2.0`), Strafe Review 1.8.0 with the bridge zip.
3. **4.3 Strafe trainer height as a module.** New folder `trainer-height/`, copied from `~/claude/mmod-trainer-height` (copied, not moved; that folder stays until the owner says otherwise):
   - Contents: `module.json` (key `trainer-height`, Linux and Windows), `module_hooks.py`, and the scss in `custom/movekit-trainer-height`.
   - Two patches: the scss include after the `main.scss` include in `strafe-trainer.xml`, and `resizeY` in `strafe-trainer.ts`.
   - Install removes the old `custom/strafe-trainer-height`.
   - It shows as a card on the hub's Modules page. A switch in the HUD section can wait.
   - Release: `trainer-height-v1.0.0`, new CI caller. Then the wiki page for mmod-trainer-height says it moved.

**4.3 details (2026-11-03, OK'd by the owner the same day).**
- Files: `trainer-height/module.json` (key `trainer-height`, title "Strafe Trainer Height", Linux and Windows, `needs_core` 1.2.1), `install.py` (`VERSION = "1.0.0"`, `--game DIR`, `--uninstall`, runnable by hand like Strafe Review's; it replaces the old `install.sh`, which is Linux only), `module_hooks.py` (install and uninstall run `install.py` through `ctx.script`, so an update never runs a cached old copy; launch calls it in-process, in the launch's own new process), `launch-hook.sh`, `panorama/styles/hud/strafe-trainer-height.scss` (the only file copied from `~/claude/mmod-trainer-height`; its `.xml` and `.ts` are Momentum's and stay out of the repo), README and LICENSE.
- Patches: `before: "</styles>"` with the scss include in `strafe-trainer.xml` (the only include there is `main.scss`, so ours comes right after it), and `resizeY: false,` to `resizeY: true,` in `strafe-trainer.ts`. Both anchors occur once in the current game files.
- Install order: remove the old `custom/strafe-trainer-height`, copy the scss into `custom/movekit-trainer-height`, then `panorama.install`. The old folder goes first, or the kit would take it as the base. Uninstall: `panorama.uninstall` first, and the scss folder goes only when that sync worked, so `strafe-trainer.xml` never includes a missing file. No game found: install fails with a message, uninstall still finishes.
- Game start: without Strafe Review nothing else syncs the kit, and a stale `0-movekit` copy would hide a game update to either file. So Linux registers `launch-hook.sh` with `movekit-run` (order 30; runs `install.py --quiet` for Momentum), and on Windows `module_hooks.launch` installs again before the game starts. A patch that no longer fits is printed and shows on the HUD card; the install doesn't fail.
- HUD section (owner, 2026-11-03: "strafe review has nothing to do with strafe trainer height. they shouldnt require each other"): `show_with` is both modules, `needs` stays empty on both. The jump-1 line's card hides when Strafe Review isn't installed (`get` returns `strafeReview`); the patched files card shows with either. That HUD change ships in the core, so it needs a core release (1.2.1), and the module's `needs_core` is 1.2.1: on 1.2.0 a Trainer Height-only install would have no HUD section, so a left-out patch would show nowhere.
- Registration: `trainer-height-v*` in `module-release.yml`'s tags (no exe, so no Windows workflow), and the expected module lists in `check_modules.py`.
- Check: `trainer-height/check_trainer_height.py` on a fake game. Old folder removed, both files patched once, Strafe Review's and this module's patches kept together, uninstalling this one leaves Strafe Review's `timer.xml`. Mutations: no old-folder removal, uninstall order reversed. On a copy of the real game files, the kit's `strafe-trainer.xml` matches the old mod's byte for byte, and the `.ts` differs only by the old mod's trailing comment. The live game is never touched while building.
- The owner's checkout: a new module folder counts as installed there without its install hook running. To switch the live game from the old mod, use Uninstall and then Install on the module's card.

**Settled by the owner (2026-11-03).** The steps go ahead as written. The module is called "Strafe Trainer Height". The HUD section gets one small card listing the kit's `status` (each patch applied, present or skipped, with the reason), in 4.2.

## Phase 5: JHUD (planned and OK'd 2026-11-03; released 2026-11-03 as hub-v1.3.0 + jhud-v1.0.0)

The owner picked JHUD on 2026-11-03. Owner notes from 2026-10-29 are in `strafe-review/PLAN.md` ("JHUD-style HUD element").

**What it adds over the game's own Jump Stats.** Momentum's Jump Stats (`jump-stats.ts`) is a scrolling table, in bhop mode only, with no colours. JHUD is one jump at a time in the middle of the screen, coloured by thresholds, held for a moment and then faded out, in the style of the CS:S shavit-jhud.

**Settled by the owner (2026-11-03).**
- **Numbers.** The game's own `MomentumMovementAPI.GetLastJumpStats()`, with no Strafe Review maths. Its gain % is sum(`speedGain`) / sum(`idealGain`) over the air time, the same number Strafe Review shows (71.0 % both ways, Phase 2 notes). Two things can still differ from the jump-1 line. The game numbers jumps by its own `jumpCount`; when that resets is checked in 5.1. The stats also arrive when the next jump takes off (`OnJumpStarted`), not 3 ticks after landing.
- **Settings in the game's HUD customizer.** Position, size, font, colours, field tick boxes, colour thresholds and which jumps show all sit there, saved per gamemode preset like the built-in panels. The hub's HUD section only shows that JHUD is installed and the kit status. If 5.1 finds that a kit panel can't join the customizer, the fallback is every setting in the hub's HUD section, written into the installed script as `recorder_settings.py` does.

**Found in the game files (2026-11-03).**
- `OnJumpStarted` is a global event: `strafe-trainer.ts` uses it through `unhandledEvents`. So JHUD needs no `<MomHudJumpStats>` panel.
- `registerHUDCustomizerComponent(panel, props)` loads a component only when `defaultLayout[panel.id]` exists (`customizer.ts` `Component.register`). `defaultLayout` is `hud_default.kv3` merged with `<gamemode>_default.kv3`, both read with `loadLayout` from `/cfg/hud`. Presets merge over it, so one entry in `hud_default.kv3` covers every preset.
- `gameinfo.txt` mounts `momentum/custom/*` as `game+mod`. Whether `loadLayout` reads `cfg/hud/hud_default.kv3` from a `custom/` folder is not known yet (5.1).
- `movekit/panorama.py` allows only `panorama/` files today (`Patch` check).

**Default look** (all of it can be changed in the customizer):
- One line: `6: 1234 (+12) 85.3 % sync 92 %`, the jump number, takeoff speed, speed change, gain % and sync, all in the gain colour (drill page scale: red at 60 %, green at 95 %; both thresholds and both colours are customizer settings). A tick box (`gainAll`) colours only the gain %. (Owner after the first in-game test, 2026-11-03: fields on one line, not rows; the gain colour on all the text. The speed change's own up/down colours went.)
- Off by default, but can be ticked: strafes, yaw ratio, efficiency, height change, distance, time change.
- Which jumps show: from jump N, every Nth jump (the built-in panel's two settings). The default is every jump.
- Bhop modes only (`BHOP`, `BHOP_HL1`, through the customizer's `gamemode`), like the game's Jump Stats (owner, after 5.1: not in surf). Hidden until the first jump, no placeholder text.
- It holds for 2 s, then fades over 0.3 s. A new jump replaces it straight away. It sits in the middle of the screen, below the crosshair.
- On once the module is installed (installing it is the opt-in). The customizer's own switch turns it off.

**Shape.**
- New module folder `jhud/`, built like `trainer-height/`: `module.json` (key `jhud`, title "JHUD", Linux and Windows, `needs_core` 1.3.0), `install.py`, `module_hooks.py`, `launch-hook.sh` (syncs the kit at game start, order 30), README, LICENSE.
- Own files in `custom/movekit-jhud`: `panorama/scripts/hud/movekit-jhud.ts` and an scss. The script creates its panel (`MovekitJhud`) itself under the HUD root and registers it with the customizer.
- Kit patches:
  - `panorama/layout/hud/timer.xml`: `before: "</scripts>"`, the script include, the same host file as Strafe Review.
  - `cfg/hud/hud_default.kv3`: `find: "    CustomizerSettings = "`, which occurs once, and `replace` with the `MovekitJhud` block in front of it.
- The old-Strafe-Review caveat (Phase 4, "Old and new versions together") applies. A Strafe Review module older than 1.8.0 can keep a stale JHUD include for one game start after JHUD is uninstalled. Modules can't need each other (owner, 4.3), so that is left as is: the next start repairs it, and a missing include only logs an error.

**Steps** (each one ends released, unless it says otherwise):
1. **5.1 Probe (in game, not released).** A throwaway probe, installed into the live game through the kit as tool `jhud-probe` and removed afterwards. It needs the owner to start the game, so the files are built and checked on a copy first. It answers:
   - Does `hud_default.kv3` in a `custom/` folder reach the customizer, so `MovekitJhud` shows in its list and can be dragged, and a saved preset keeps it?
   - Does `OnJumpStarted` + `GetLastJumpStats()` fire in bhop and surf? When does `jumpCount` reset: at the start zone, at the timer start, or at a reset?
   - Logs to `yaw.log` as `[panorama] JHUDPROBE ...`.

   If the kv3 isn't read from `custom/`, stop and switch to the hub-settings fallback (ask the owner).
2. **5.2 Kit for `cfg/hud/`.** `panorama.py` also allows `cfg/hud/*.kv3`, with the base taken from the game's `cfg/hud` when no `custom/` folder has the file. `check_panorama.py` gets a kv3 case plus a mutation (the path check removed). The hub's HUD section gets JHUD in `show_with` and a JHUD card. Release: core 1.3.0 (`hub-v1.3.0`).
3. **5.3 JHUD module.** As in "Shape".
   - The display logic is plain functions: which jumps show, row text, colour for a value. `jhud/check_jhud.js` runs them in node with Panorama stubbed (as `check_line.js` does), on hand-made stats and on the `jump` events in saved attempts.
   - `jhud/check_jhud.py` checks a fake game: install and uninstall, both patches applied once, Strafe Review's and Trainer Height's patches kept, a changed kv3 left out and reported. Mutations: no kv3 patch, uninstall without sync.
   - Registration: `jhud-v*` in `module-release.yml`, plus the module lists in `check_modules.py`.
   - Release: `jhud-v1.0.0`. Then the owner tries it in the game and tunes the defaults.

### Phase 5.1: probe (2026-11-03, owner tested bhop_glacial and surf_ferros)

- **Customizer: works.** The `hud_default.kv3` copy in `custom/movekit-jhud-probe/cfg/hud` was read: `loadComponent` joined `MovekitJhud` (`joined: true`), the panel could be dragged, and the number setting reached the script (95, then 94-91). So the settings stay in the customizer, and 5.2 goes ahead.
- **Events.** `OnJumpStarted` + `GetLastJumpStats()` fire in bhop (mode 2) and surf (mode 1). The panel's parent from `timer.xml` is the `Hud` root.
- **`jumpCount`** resets to 0 when the timer primes (state 1, the start zone). The event for jump N carries the air time of jump N-1: `n` 1 has gain 0 and takeoff = speed, `n` 2 has jump 1's gain (82 %). So JHUD labelled a line with `n - 1` and skipped `n` 1. Changed after the owner's in-game test (2026-11-03, below): a line at every takeoff labelled `n`, like shavit-jhud, and `n` 1 shows its number and speed only. A reset in the zone can give an `n` 1 with takeoff about 55 and `dt` 0.01, which now shows as `1: 55`.
- **Owner:** the probe showed in surf and showed its text before any jump; JHUD should do neither (see "Default look").
- Probe removed from the live game afterwards (`probe.py --uninstall`).

### Phase 5.2: kit for `cfg/hud/` (2026-11-03, released in hub-v1.3.0)

- `movekit/panorama.py`: a patch's file may be `cfg/hud/*.kv3` as well as `panorama/...`. The base search is the same (a `custom/` folder in mount order, else the game's own). Only `*_default.kv3` should be patched, since the game writes its presets into `cfg/hud` itself.
- `check_panorama.py`: a kv3 patch from the game's file and from a mod's copy in `custom/` (entry once), gone with its tool; `cfg/hud/notes.txt` and `cfg/hud/../autoexec.kv3` refused. Mutation: allowing any `cfg/` path fails the check.
- HUD section: `show_with` adds `jhud`, `get` returns `jhud` (installed), and a JHUD card (shown only when installed) points at Momentum's HUD customizer. The jump-1 line's "off by default" note moved into its own card, since JHUD is on once installed. `check_hud` covers `jhud` and `show_with`.
- Every `check_*.py` and `hub/smoke_test.py --repo` pass (`strafe-review/check_hub_section.py` not run: it needs the live viewer stopped, and nothing it covers changed).

### Phase 5.3: JHUD module (2026-11-03, released as jhud-v1.0.0)

- `jhud/`: `module.json` (`needs_core` 1.3.0), `install.py` (VERSION 1.0.0, kv3 `ENTRY`), `module_hooks.py`, `launch-hook.sh` (order 40), `panorama/scripts/hud/movekit-jhud.ts`, README, LICENSE. Core bumped to 1.3.0 (`hub_release.py`, `modules.py`). `jhud-v*` in `module-release.yml`; `check_modules` lists it (both OSes). The release zip holds only the module files.
- The script registers its own events once (not through the customizer's `events`, which `loadComponent` would add again at every map load), shows nothing while the customizer has the panel switched off (`panel.enabled`) or outside bhop, and shows a held sample while the customizer is open.
- `check_jhud.js`: settings vs kv3 entry, colour scale, `jumpOf`/`shows`, rows, the Panorama flow with stubs, and 8621 saved jump events drawn with no NaN. Mutations caught (7/7): no mode check, `jumpOf` off by one, customizer switch ignored, an old timer fading a new jump, every 0 showing all, no sample redraw, a kv3 default drifting.
- `check_jhud.py`: fake game, both patches once, another tool's include kept, a mod's kv3 as the base, a changed kv3 left out and reported, failed sync keeps the script, hooks. Mutations caught (3/3): no kv3 patch, script removed on a failed sync, no hook unregister.
- On copies of the real `timer.xml` and `hud_default.kv3` (LF), the install applies both patches once.
- Every `check_*.py`, `check_jhud.js` and `hub/smoke_test.py --repo` pass. In-game test 2026-11-03 (installed from the repo): works; the owner asked for one line and the whole line in the gain colour, done the same day (`check_jhud.js` covers the owner's pick: number, speed, gain, yaw ratio on one line). After that change the owner's `panorama_reload` left JHUD invisible: the old copy's event handlers stay registered after a reload, and the two copies deleted each other's panel at every jump; also `HudCustomizer_Ready` comes only at a map load. Fixed: a load number in Panorama's global object (`MovekitJhudGen`) makes an old copy's handlers and timers do nothing, the placed panel is taken over instead of replaced, and a copy loaded while the customizer is ready registers at once. `check_jhud.js` loads the script twice in shared stubs (mutations caught: old copy still drawing, panel replaced, no register after reload, an old copy's timer hiding the new jump). Second in-game look (2026-11-03): JHUD still vanished after `panorama_reload`. Debug lines in yaw.log showed the reload re-ran the Timer layout without JHUD: a stale `custom/0-strafe-review/timer.xml` (from before Strafe Review moved onto the kit, 2026-11-02) wins on a reload, though `0-movekit` wins at game start. Rerunning `strafe-review/install.py` deleted it; after that the reload kept JHUD (load 3 and 4 took over the panel). The launch hook reinstalls JHUD from the repo at every game start, so a debug copy in the game folder is lost on restart: put debug lines in the repo file. The owner then asked for a line from the first takeoff (they had seen one in the probe): `jumpOf` is `jumpCount`, and takeoff 1 shows number and speed only, in the font colour (`check_jhud.js`; mutations caught: label `n - 1`, no takeoff-1 case). The owner checked the new numbering in game after a restart: good. CI test runs on the branch passed (hub-windows, module-release tool=jhud). Then the owner asked, before the release, for JHUD not to be coloured by default: a "Colour by" dropdown (`colorBy`, `COLOR_BY`), Off (the font colour, default) or Gain %; the gain settings (whole line, thresholds, red and green) sit under it and show only while it is Gain % (the customizer's `showWhen`, as in the game's ground-boost.ts). Saved presets without `colorBy` get Off: the customizer deep-merges a preset over hud_default.kv3. `check_jhud.js` covers it (mutations caught: default gain, colorBy ignored, no showWhen). Then the owner wanted speed colours after all, set per user, with a cutoff at 6 or 12 (CS:S servers colour by speed over the first 6 or 12 jumps), shown on every jump before the cutoff, not only at it. Owner's own wish: green when on track for 620 at jump 6, blue for 625, white for 630. Built as "Speed pace, then gain %" (`colorBy` 'pace'): `paceCut` 6 or 12, three tiers (`tierNSpeed`, `tierNColor`) and `belowColor` (own picker, owner's pick); takeoff k is on pace for speed / `PACE[cut][k - 2]` at the cutoff, the highest tier reached wins (tiers in any order); jump 1 isn't judged; after the cutoff, gain colours (owner's pick). `gainAll` off colours only the speed (pace) or the gain %. The pace curve is built in (owner's pick over editable or learned per user; learning can come later): the median share of the cutoff speed in the owner's runs that reached it, from the Strafe Review store (46 runs for 6, 14 for 12; bhop_glacial and bhop_ambience). Leave-one-out on those runs, the typical error of the projected cutoff speed: cutoff 6, jump 2 6.8 u/s, 3 3.4, 4 1.4, 5 1.2; cutoff 12, jump 2 10.0, 6 3.6, 10 1.4. The owner's tiers are 5 u/s apart, so jump 2 is a rough guess and jumps 4-5 are reliable. `check_jhud.js` covers it, and every saved jump is drawn in all three modes (mutations caught: lowest tier wins, no curve, no cutoff, no gain after the cutoff, no below colour, gainAll-off colouring the whole line). In-game look 1 (owner screenshot): the three 3-digit pace speeds were drawn with the first digit under the box's minus button once the customizer rebuilt the settings (620 read "520"); 2-digit boxes were fine, and the long tick-box label was cut off. Fix tried: every number box gets a min/max (`extra.range`, passed as `settingProps`, like the game's df-jump `maxDelay` 360 with max 1000; `check_jhud.js` checks each box has one around its default), and the label is now "Colour the whole line". In game: still cut off, so the range wasn't it (kept anyway). The customizer's number box text field is `width: fit-children; min-width: 24px` (customizer.scss) and isn't widened for 3 digits. Workaround: while the customizer is open and `HudCustomizerHandler.activeComponent` is JHUD, `fixBoxes()` sets every NumberEntry's TextEntry in `panels.activeComponentSettingsList` to width 44px (5 digits), checked every 0.25 s since the list is rebuilt on every pick with no event; it stops when the customizer closes (`check_jhud.js`; mutations caught: other components touched, never stops, never starts, wrong panel type). Owner, in game: "seems good". CI test runs passed on 9305e9e. Released 2026-11-03: main fast-forwarded to 9305e9e, tags hub-v1.3.0 (hub-windows.zip) and jhud-v1.0.0 (jhud-module.zip + .json), notes written. Open: a learned per-user (or per-map) pace curve, if the built-in one fits other players badly.

## Phase 6: Strafe Speed Histogram (planned and OK'd 2026-11-03; redesigned the same day, see 6.2b; released 2026-11-03 as hub-v1.4.0, jhud-v1.1.0, strafe-histogram-v1.0.0)

The owner asked on 2026-11-03 for an in-game HUD element: a histogram of strafe speed. Strafe speed here means yaw speed against the optimal, the game's `yawRatio` (1 = optimal). It is separate from the viewer idea "Strafe histograms, with snapshots" (Strafe Review, to-do `strafe-review-histograms`).

**Settled by the owner (2026-11-03).**
- **Value.** `yawRatio` per air tick, binned. It is not gain % per strafe or raw mouse speed.
- **Window.** It is rolling and stays current: only the most recent strafing counts, and older ticks drop out.

**Found in the Strafe Review store (2026-11-03).** There are 1418 attempts and 1.06 M air ticks at 100+ u/s.
- Quantiles: 1 % -1.95, 5 % -0.42, 10 % 0.22, 25 % 0.72, median 0.90, 75 % 1.01, 90 % 1.11, 95 % 1.23, 99 % 2.08.
- 7 % of ticks are negative (turning against the strafe, mostly at the swaps), and 2 % are exactly 0 (no turn).
- So the bars need ends that catch the rest. The bulk sits between 0.7 and 1.1.

**Default look** (all of it can be changed in the HUD customizer, as with JHUD):
- 12 bars of 0.1 from 0.4 to 1.6, plus one end bar each side ("< 0.4", "> 1.6"). That is 14 bars in all.
- Bar height is the bar's share of the ticks in the window, scaled to the tallest bar.
- Colours (owner, 2026-11-03): "Colour by" in the customizer, Plain (default, one colour to pick) or How good. How good shades each bar by its distance from 1.0: green at 1.0, red at the ends, both sides alike, with the two colours to pick.
- Under the bars, one line: the share of ticks in the optimal band (0.85-1.15, Strafe Review's `BAND_LO`/`BAND_HI`), e.g. `in band 62 %`. A tick box turns it off.
- Placement: bottom middle, about 300 x 90 in the customizer's 1920x1080 units.

**Which ticks count.** The viewer's strafe-middle rule (stats.js "angle"), so the HUD's in-band % means the same as the viewer's "In optimal band" for the same strafing:
- air (`moveStatus` 0), 100+ u/s, no collision;
- inside a strafe, with 2 ticks skipped at each end (the HUD is 2 ticks behind, which can't be seen);
- +left/+right ticks left out.

Each game tick counts once, whatever the frame rate. The `$.Schedule(0)` loop runs once per frame, so the recorder's new-tick test is used: a key over the tick stats and velocity, numbered by `floor(GetCurrentTime() / interval)`. The bars are redrawn at most 20 times a second.

**Window rule.** The last N seconds of counted ticks, 3 s by default, set in the customizer. Standing still or riding the start zone adds no ticks, so the last strafes stay on screen until new ones push them out. A map load clears it.

**Shape.** Built like `jhud/`:
- Folder `strafe-histogram/`, with `module.json` (key `strafe-histogram`, title "Strafe Speed Histogram", Linux and Windows, `needs_core` 1.4.0), `install.py`, `module_hooks.py`, `launch-hook.sh`, README and LICENSE.
- Script `panorama/scripts/hud/movekit-strafe-histogram.ts`, panel id `MovekitStrafeHist`, files in `custom/movekit-strafe-histogram`.
- Kit patches: the script include in `timer.xml`, and its `hud_default.kv3` entry, both as JHUD does. `HOOK_ORDER` 50.
- JHUD's Panorama fixes, copied:
  - the load number against old copies after `panorama_reload`;
  - the placed panel taken over, not replaced;
  - registering at once while the customizer is ready;
  - `fixBoxes()` for 3-digit number boxes;
  - a sample histogram while the customizer is open.
- **Copied, not shared.** Panorama scripts can't import. A shared helper script would add a load-order tie between two modules, and either one can be installed alone. When a third HUD component needs them, they move into a kit-owned helper include in `0-movekit`.

**Core 1.4.0: HUD cards come from `module.json`.** The HUD section's JHUD card is hard-coded today (`hud/hub_section.py` `_jhud`, `show_with`). Instead, a module lists a `hud_card` (title, one line of text) in its `module.json`, and the section shows one card per installed module that has one. JHUD's card moves there too. After that, a new HUD module needs no core release.

**Steps** (each one ends released, unless it says otherwise):
1. **6.1 Core 1.4.0.** HUD cards from `module.json`. Checks: `hud/check_hud.py` covers two fake modules with cards, one without, and none installed. JHUD's card looks the same as before. Release `hub-v1.4.0`. JHUD gets `hud_card` in `jhud-v1.0.1` (`needs_core` 1.4.0).
2. **6.2 Module.** `strafe-histogram/check_strafe_histogram.js` runs the plain functions in node, with Panorama stubbed:
   - tick filter, bins, window and in-band %;
   - the same tick seen over N frames counts once;
   - rows of stored attempts fed through the HUD code give the in-band % that `stats.js` reports for them;
   - kv3 entry against STYLES/DEFAULTS;
   - the reload guard.

   `check_strafe_histogram.py` covers a fake game, as `check_jhud.py` does. Mutations:
   - counting every frame;
   - no end skip;
   - no window drop;
   - band edges off by one bar.

   Then the owner tries it in game, before the release.
3. **6.3 Release** `strafe-histogram-v1.0.0`, with the CI caller and the `check_modules.py` lists.

**Modes (owner, 2026-11-03).** Bhop modes only (`BHOP`, `BHOP_HL1`), like JHUD. Own play only: it shows nothing while spectating or watching a replay. Whether `GetLastTickStats` follows a spectated player is untested.

### Phase 6.1: core 1.4.0, HUD cards from module.json (2026-11-03, branch `phase-6`)

- `module.json` may have `hud_card` (`title`, `text`, both non-empty; `read_manifest` refuses anything else). The HUD section's `get()` returns `cards` (by title) in place of `jhud`. The page draws one card per entry in `#hud-cards`.
- Hub sections may have `show_if(found)`, where `found` is `{key: manifest}` of the installed modules. A section shows while `show_with` names an installed module or `show_if` says True; an error counts as False. The HUD section keeps `show_with` for Strafe Review and Trainer Height, and shows while any installed module has a card.
- JHUD's card text moved into `jhud/module.json` (JHUD 1.0.1, still `needs_core` 1.3.0: an old core ignores the field and keeps its hard-coded card). A JHUD 1.0.0 on core 1.4.0 keeps its card through `LEGACY_CARDS` in `hud/hub_section.py`. `check_hud.py` checks that the legacy text equals the manifest's.
- Checks: `check_hud.py` (cards: own, legacy, none, sorted; when the section shows), `check_modules.py` (bad `hud_card` shapes refused, a good one kept; a core section with `show_if` given the manifests; one that raises stays hidden). Mutations caught (6/6): `show_if` ignored, `show_if`-less sections shown, `hud_card` unchecked, no legacy card, unsorted, no `show_if` on the HUD section. Every `check_*.py`, `check_jhud.js` and `hub/smoke_test.py --repo` pass. Test window: the HUD section looks the same as before.

### Phase 6.2: Strafe Speed Histogram module (2026-11-03, branch `phase-6`, waiting on the owner's in-game look)

- `strafe-histogram/`: `module.json` (key `strafe-histogram`, `needs_core` 1.4.0, `hud_card`), `install.py` (1.0.0, `HOOK_ORDER` 50), `module_hooks.py`, `launch-hook.sh`, README, LICENSE. Script `movekit-strafe-histogram.ts`, panel `MovekitStrafeHist`, kv3 entry at 810/880, width 300.
- The tick rule is `middles(rows)`, Strafe Review's viewer rule over the rows seen so far, limited to what is certain: ground one row behind, ideal keys two, a strafe's end two more. `Middles.push` gives each tick once. It keeps rows from 3 before the first open jump's takeoff: the takeoff row's 5-tick yaw average reaches 2 back, and the oldest one's yaw change needs the row before it (with 2, 1 tick in 1419 came out different). There is a cap of 2000 rows, so a surf ramp run (one long "jump") outgrows it. That doesn't matter, since surf modes don't show it.
- Bars are built once. A redraw (at most 20 a second) sets only the heights and the line's text. A setting that changes them (range, width, colours, font) builds them again. After `panorama_reload`, the new copy builds its own once.
- `check_strafe_histogram.js` covers: kv3 against DEFAULTS, ranges, bars, colours, the window, the tick rule on made-up jumps, and the Panorama side (sample, other mode, replay, spectating, switched off, reload take-over, one loop). On the store, the HUD's ticks equal the viewer's strafe-middle ticks on every own bhop attempt: 1146 attempts, 577754 ticks, in-band counts equal. Surf maps are skipped.
- Mutations caught (17): counting a tick again, counting every frame, no end skip, no window drop, band edges exclusive, band edge off, 2 rows kept before a takeoff, counting while spectating, counting in a replay, other modes, no reload guard, panel replaced on reload, bar edge off by one, rebuild on every draw, no rebuild on a layout change, old children kept on build, and in `check_strafe_histogram.py` no kv3 patch, script removed on a failed sync, no hook unregister.
- Two mutations were equivalent, not gaps: trusting the newest row's ground (keys stop 2 rows earlier), and skipping the rebuild after a take-over (`builtFor` is empty in a new copy).
- `check_strafe_histogram.py` covers the fake game as `check_jhud.py` does, plus JHUD installed alongside (both entries and includes, either uninstalls alone).
- Installed into the live game from the repo on 2026-11-03, with every patch applied.

### Phase 6.2b: redesign as a scrolling bar per tick (2026-11-03, owner)

The owner saw the first build and wanted something else: "a scrolling histogram with a bar for each tick. it should be vertical with the bars 'moving' up from the origin point as they scroll." The 14-bar summary, the window and the in-band line are gone, and so is the strafe-middle tick rule.

Settled by the owner:
- One horizontal bar per air tick. Ground ticks add no row ("every air tick, no gaps").
- The newest bar is at the bottom; older ones scroll up.
- Bars grow left to right by default. The optimal sits in the middle or at 3/4 of the width ("so you can see if you're going over").
- An option makes bars come in from the strafe's side, towards the middle.

Defaults picked by Claude: 100 rows of 2 px, optimal in the middle, a marker line at the optimal (two when coming from the sides at 3/4), Colour by Plain or How good (the earlier pick, kept), width 200 at 860/640.

How it works:
- Rows are built once. Each tick moves the top row to the bottom (`MoveChildAfter`) and restyles only that row. Rows with no bar yet are hidden, so the list is bottom-aligned and grows up.
- Each tick is drawn one tick late, so ground can use Strafe Review's exact rule, which needs the next tick. A rule using only the tick before differed on 429 of 1.04 M rows; the late one differs on 0 of 1040338 (1162 own bhop attempts).

`check_strafe_histogram.js` was rewritten. Mutations caught (19/19): counting every frame, ground ticks drawn, no move to the bottom, rebuild every tick, no rebuild on a layout change, sides always, 3/4 ignored, no cap at full width, negative widths, one marker from the sides, spectating, replay, other modes, switched off ignored, no reload guard, panel replaced on reload, how good ignored, apex as ground, one-sided steady vz.

A first install while the game is running fails to load the script (`Resource ... failed to load`, a parse error in `timer.xml`). The game mounts `custom/*` folders only at start, so a game restart is needed; the READMEs now say so. A possible core fix: tool scripts live in `0-movekit`, which is already mounted. Not done; the owner hasn't decided.

### Phase 6.2c: in-game fixes (2026-11-03, owner testing)

- **Number boxes:** a min over 0 snapped half-typed values back (couldn't type 200 ticks). Every box now has min 0, like the game's own, and the scripts clamp the value where it is used. Rows: max 9999 in the box, 1000 in use, step 10. JHUD's boxes changed the same way.
- **strafeRight** is 1, -1 or 0, not a bool, so `!!` sent every bar right. Now `> 0`; the test sends the game's values.
- **Sides:** by default right strafes come from the left and left strafes from the right. "Swap the sides" (`swapSides`) turns that round.
- **After an update and `panorama_reload` it vanished.** The customizer throws when a setting has no value in the layout loaded at map start (`customizer.ts`, Component constructor: "Could not load dynamic style value"), and the throw stopped the script before its loop started. Three changes, in JHUD too:
  - `fitLayout()` leaves out settings the loaded layout has no value for, until the next map load.
  - `register()` catches and logs.
  - The histogram's loop starts before registering.

  Tests copy the real throw. Mutations caught (6/6): no fit, throw passed on, no loop, group children kept, and JHUD's no fit and throw passed on.

- **Gain colours (owner, 2026-11-03).**
  - The histogram has a third mode, Gain %. The gain a tick's turn speed gives is `100 * (1 - (ratio - 1)^2)`, fitted to 1.0 M saved air ticks: within 0.5 % of the median gain at 86.5 % and 92 % on both sides.
  - Bands: amber below 86.5 %, green 86.5-92 % (both ends in), blue above. Thresholds are in tenths (865), since number boxes are int32.
  - JHUD's Gain % mode moved to the same bands and defaults (`gainLow`, `gainHigh`, `lowColor`, `midColor`, `highColor`), in place of the red-green fade (`gainRed` 60, `gainGreen` 95). `check_jhud.js` checks that its defaults equal the histogram's.
  - JHUD goes to 1.1.0 (it was 1.0.1), so the release order is `hub-v1.4.0`, `jhud-v1.1.0`, `strafe-histogram-v1.0.0`.

### Phase 6.3: release (2026-11-03)

- `strafe-review/check_hub_section.py` ran with `MOVEKIT_SESSION_PORT` on a free port, so the live viewer stayed up. It passed. Every other check, both node checks, `hub/smoke_test.py --repo` and the privacy scan passed too.
- CI test runs on `phase-6` were green: hub-windows (41689830317), and module-release for strafe-histogram (41689878910) and jhud (41689933069). The zips hold only the module's shipped files.
- `main` was fast-forwarded to 1f46ce7. The owner pushed the tags `hub-v1.4.0`, `jhud-v1.1.0` and `strafe-histogram-v1.0.0`. Each release has its files (hub-windows.zip; `<tool>-module.zip` + `.json`) and notes.
- The live game runs both modules from the checkout, as it did before the release.

### Modules page groups (2026-11-03, owner; released 2026-11-03 as hub-v1.5.0)

- **Order.** `Manager.cards()` sorts: core, tools, HUD modules (installed first in each, then by title), then modules this OS can't run. The page puts a heading at each group: Tools, HUD, "Not available on <OS>". Unavailable cards are greyed (opacity 0.5), have no buttons, and say "<OS> only".
- **`group`.** `module.json` may say `"group": "hud"`: JHUD, Strafe Speed Histogram and Strafe Trainer Height now do. Releases from before that use `LEGACY_GROUPS`, so those three modules need no new release. A release's `module.json` copy now keeps `os` and `group`.
- **Other OS.** `known()` also lists module folders for another OS (`local()`). `install()` refuses a module whose `os` leaves this platform out.
- **Sidebar.** The HUD section's order is 90, so it comes after the tools.
- **Checks.** `check_modules.check_groups` covers the order on Linux and Windows, the legacy group, an unknown group refused, install refused on the wrong OS, and a release seen from the other OS. Mutations caught (7/7): no HUD grouping, unsupported not last, install offered on the wrong OS, no install guard, other-OS modules hidden, release os dropped, no legacy groups. `check_hud.py` checks the HUD section is last in the sidebar (mutation caught). `smoke_test.py` SECTIONS order updated.
- **Test window.** Pretending to be win32, Source Yaw shows greyed under "Not available on Windows" at the bottom.

## Phase 7: First Jump HUD (owner, 2026-11-03; released 2026-11-03 as hub-v1.6.0, strafe-review-v1.9.0, first-jump-v1.0.0)

The owner asked for the jump-1 line to be "a separate hud element ... like jhud and histogram instead of being weird". Until now it was drawn by Strafe Review's recorder, at a fixed spot, and switched on in the hub's HUD section.

- **Look (owner's picks, 2026-11-03).** Same content as the old line: the landing speed and gain %, a box per strafe with its gain %, that strafe's top loss cause under it, and the biggest jump-1 mistake. Bhop modes only, like JHUD. The strafe boxes use the 3 gain bands of JHUD and the histogram (amber < 86.5, green to 92, blue above) instead of the old red-to-green fade.
- **Module `first-jump/`.** It has `module.json` (key `first-jump`, title "First Jump HUD", group `hud`, `hud_card`, both OSes, `needs_core` 1.5.0), plus `install.py` (1.0.0, `HOOK_ORDER` 60), `module_hooks.py`, `launch-hook.sh`, README and LICENSE. The script is `movekit-first-jump.ts`, with panel id `MovekitFirstJump`, files in `custom/movekit-first-jump`, and the customizer name "First Jump". The kv3 entry puts it at the top middle (offset 600/20, width 720).
- **Self-contained.** The script records its own rows: Strafe Review's sampler and columns, the 2 s ring before the timer start, own runs only, and a 0.5 s tail after the stop. The jump-1 maths moved over unchanged (`parseRows` to `jump1Mistakes`). It logs `FJLINE <started> <json>`, with the map in the JSON. It doesn't need Strafe Review, and Strafe Review doesn't need it.
- **Settings in the customizer.**
  - Font, font size, font colour and background.
  - Strafe boxes: font size, width and text colour.
  - The 5 row switches.
  - Gain thresholds and band colours, and the cause box colour.
  - Hold time (4000 ms) and fade time (300 ms).
  - Number boxes have min 0 and are clamped in code. `fitLayout` and the widened number boxes work as in JHUD.
- **Strafe Review 1.9.0.** The recorder loses the line: `SHOW_LINE`, `SHOW` and the analysis are gone. A small `showNote` keeps the replay rescan's "replay saved" note. `recorder_settings.py` and `install.apply_settings` are gone too. `needs_core` is 1.6.0, so an older core never gets a Strafe Review it can't show the toggle for.
- **HUD section (core 1.6.0).**
  - The jump-1 toggle is legacy. It shows only while an installed Strafe Review still has `recorder_settings.py` (before 1.9.0), so that old line can still be turned off. Otherwise it would show twice next to First Jump HUD.
  - `get()` returns `legacyLine` instead of `strafeReview`. `inGameLine` stays in `hud/settings.py` for the old `install.py`.
- **Checks.**
  - `first-jump/check_first_jump.js` covers the settings against the kv3 entry, the bands, the drawn parts and the Panorama side on a made-up run fed tick by tick. 10 mutations were tried and all 10 were caught: replay, spectating, the delay rows, the tail rule, once per run, the reload loop, the ring, the gamemode, switched off, and a dropped target.
  - `first-jump/check_parity.js` was `strafe-review/viewer/check_line.js`. It runs 1116 saved own attempts tick by tick (1118 at `--interval 0.015`) against the viewer: 0 differ. `--log` reads both `SRLINE` and `FJLINE`. Its 387 DIFFs on old SRLINE lines are the same with the old check_line.js, from viewer changes made after those lines were logged.
  - `first-jump/check_first_jump.py` covers the fake game install.
  - `hud/check_hud.py` covers the legacy toggle with a copy of the old `recorder_settings.py`. `hub/smoke_test.py --repo` expects no legacy toggle.
  - Every `check_*.py`, the node checks and the smoke test pass.
- **Released 2026-11-03.** The owner tested it in game and found it fine. `first-jump` was fast-forwarded into `main` (1a26cf8), and the tags `hub-v1.6.0`, `strafe-review-v1.9.0` and `first-jump-v1.0.0` were pushed by Claude (from now on Claude pushes the tags). All 4 CI runs passed. Each release has its files: hub-windows.zip; strafe-review module zip and json plus strafe-review-windows.zip; first-jump module zip and json.

## Phase 8: bhop and surf yaw lists in Source Yaw (owner, 2026-11-03; OK'd the same day; released 2026-11-04 as hub-v1.7.0 and sourceyaw-v1.9.0)

The owner wants separate bhop and surf yawspeeds in both games. They picked "both" for switching: automatic by map prefix, plus a mode key that overrides it.

- **Settings.** A profile keeps `entries` and `start` as the bhop list, which is also the only list while no surf list exists. New optional keys:
  - `surf: {entries, start}`, or missing. Missing means the feature is off, and the yaws.cfg is byte-identical to 1.8.0's.
  - `mode_key`: a key, or "".
  - `auto_mode`: bool, default true.
  - `map_modes`: `{"bhop_": "bhop", "surf_": "surf"}`, the same prefix style as the trainer's `map_tickrates`.
- **yaws.cfg with a surf list.**
  - Both cycles are aliases: `yaw_b1..N` and `yaw_s1..N`.
  - Each list has `sourceyaw_bhop` / `sourceyaw_surf`. These apply the list's start yaw at once (cvar, echo, colour, sound), point `yaw_cycle` at the next entry, point `sourceyaw_mode` at the other list, and echo `SY_MODE_BHOP` / `SY_MODE_SURF`. The mode key is bound to `sourceyaw_mode`.
  - Each list also has `sourceyaw_arm_bhop` / `sourceyaw_arm_surf`. These only point `yaw_cycle` at the list's start entry and echo the mode token, so the next press lands on the start yaw.
  - The cycle key is bound to `sourceyaw_press` = `exec sourceyaw_auto; yaw_cycle`. `cfg/sourceyaw_auto.cfg` is normally empty.
  - The game starts on the bhop list. `con_logfile yaw.log` is on whenever `auto_mode` is.
- **Surf tokens.** The surf list echoes `YAWSURF_<speed>`, so a speed in both lists can have its own crosshair image. `crosshair_watch.py` accepts both token forms. Momentum's colour cfgs become `b<i>.cfg` / `s<i>.cfg` (`c<i>.cfg` while there's no surf list).
- **Mode watcher.** A new `mode_watch.py` helper is started by `launch-hook.sh` when `watch.env` has `AUTO=1`. It joins the movekit session.
  - It tracks the current mode from the `SY_MODE_*` tokens, which covers the mode key too.
  - On `map_loaded`, if the prefix gives a mode other than the current one, it writes `sourceyaw_arm_<mode>` into `sourceyaw_auto.cfg`.
  - When it sees the matching token, it empties the file.
  - An unknown map (CS:S's "Connected to" line has no name) changes nothing.
  - The file is emptied at start and at exit.
- **Hub page.** A "Separate surf yaws" switch. When it's on, a Bhop / Surf tab pair sits above the yaw list (each tab with its own start radio), plus a mode key field (with conflict notes like the offset key) and an "Auto by map prefix" switch.
- **Unchanged.** The trainer, and the old `yaw_cycle` binds: `keys_bound_to_cycle` also looks for `sourceyaw_press`.
- **Step 1, probe in game before any code.** Write `cfg/sy_probe.cfg` with `echo PROBE_A`, run `bind p "exec sy_probe"` and press p. Then, with the game still running, change the file to `echo PROBE_B` and press p again. Do this in CS:S on a public server and in Momentum. If the second press doesn't print PROBE_B, auto switching can't work and only the mode key is built. Also note the console noise from the exec.
- **Arms are one-shot.** `sourceyaw_surf` turns `sourceyaw_arm_surf` into a no-op and puts `sourceyaw_arm_bhop` back, and the reverse for bhop. Alias bodies can't nest quotes, so the redefinitions point at single-word aliases (`alias sy_noop ""` at the top level). A press before the watcher empties the file, or a file left armed after a crash or after the hookless BHOP shortcut, can't reset the cycle. `apply()` also writes `sourceyaw_auto.cfg` empty.
- **Core 1.7.0.** The session publishes only the tokens in `movekit/session.py` `TOKENS`. This adds `YAWSURF_<speed>` and `SY_MODE_(BHOP|SURF)`. Source Yaw 1.9.0 then needs core 1.7.0.
- **Shared prefix lookup.** One helper in `yawcore` maps a map name to a value by prefix. Both `map_modes` and the trainer's `map_tickrate` use it.
- **Plumbing.** `settings_api.collect()`, and `hub_section.load()` / `settings()`, carry `surf`, `mode_key` and `auto_mode`. `validate()` adds three checks: the surf list isn't empty, its speeds are unique within the list, and the mode key is valid and differs from the cycle and offset keys. In `apply()` the mode key joins `ours`, and stale `sourceyaw_mode` binds are unbound. `write_color_cfgs` deletes `c*`, `b*` and `s*`. `write_crosshairs` also makes the surf PNGs. `remove_from_game` deletes `sourceyaw_auto.cfg`.
- **Checks.** A new `sourceyaw/check_modes.py`:
  - yaws.cfg is byte-identical to 1.8.0's without a surf list.
  - The alias chains, simulated: press order, mode key, arm then press lands on start.
  - The watcher, on fake session events: map to arm, token to clear, same mode does nothing, unknown map does nothing.
  - Settings round-trip through the real `hub_section.settings()` / `load()` path.
  - Cleanup of the colour cfgs and the auto file.
  - Mutations: the arm landing one past the start, the watcher writing on a same-mode map, a shared token for both lists.
- **Release.** hub-v1.7.0 (core 1.7.0) and sourceyaw-v1.9.0.
- **Probe (2026-11-03).** CS:S on a public server (bhop_bfur): `bind p "exec sy_probe"` printed PROBE_A, and after the file was changed with the game running, PROBE_B. So exec re-reads the file on every press. No "execing" line shows in the console or log. Order, same server: `alias sy_t "exec sy_probe; echo AFTER"` printed PROBE_B before AFTER on every press, so the exec'd file runs before the rest of the alias, as the console model in `check_modes.py` assumes. Momentum (2026-11-03): both pass too (PROBE_A then AFTER; after the file change, PROBE_B then AFTER). Its echoes reach yaw.log with a `[vstdlib] ` prefix, which the token scanner allows.
- **Built (2026-11-03).**
  - Everything as above. `_set_alias` and `_key_lines` are shared by the one-list and two-list yaws.cfg.
  - `mode_watch.py` is installed by `install.sh`.
  - The page has a "Separate surf yawspeeds" switch, Bhop / Surf tabs (a first surf list starts as a copy of the bhop list), the mode key with Change and Clear, and "Auto by map prefix".
  - Checked:
    - `sourceyaw/check_modes.py`: yaws.cfg without a surf list is identical to sourceyaw-v1.8.0's yawcore (24 cases from git); a console model runs yaws.cfg with exec inserted before the rest of the buffer; the watcher; validate; apply and cleanup; the hub's save and load. `--mutations`: 8 of 8 caught.
    - `movekit/check_session.py` covers the new tokens.
    - `check_settings_api.py` covers collect with a surf list.
    - Every `check_*.py` and `hub/smoke_test.py --repo` pass.
  - Owner (2026-11-03): turning "Separate surf yawspeeds" off must not delete the surf list. The other list is greyed out, with a button to swap which one is used.
    - Built as `separate` and `active` in the profile. `surf_on()` is a saved surf list plus `separate`. `active_mode()` gives the one list in game while not separate. `mode_lists()` gives that list as 1.8.0 wrote it (`c<i>.cfg`, `YAW_` tokens). `saved_lists()` covers every saved list, so colours get filled in for both.
    - The page always shows the Bhop / Surf tabs. While not separate, the unused list's rows are dimmed but still editable, and "Use <list> instead" swaps them.
    - `check_modes.py` checks that yaws.cfg with either list active matches 1.8.0's yawcore given that list (48 cases), plus validate, colour cfgs and the hub's save and load. `--mutations`: 11 of 11 caught.
  - `trainer.map_tickrate` now goes through `yawcore.prefix_value`, which lowercases the map name as well as the prefix (before, only the prefix was lowercased). This is a small behaviour change for map names with capitals.
  - The `I001` (import order) findings in trainer.py and crosshair_watch.py, deliberate because movekit must come after yawcore, now carry `noqa` (owner's OK).
  - Live (2026-11-04): the Strafe Review server was restarted on the new `session.py` and `sourceyaw/install.sh` was rerun. A window screenshot showed the new rows. In Momentum, the owner said it "seems to be working". run.log shows the watcher listening and arming on map loads (`surf_ferros -> arm surf`, `bhop_glacial -> arm bhop`). No mode key was set, so the mode key and CS:S weren't tried in game.
  - Released 2026-11-04: `sourceyaw-modes` fast-forwarded into `main`, and Claude pushed the tags hub-v1.7.0 (hub-windows.zip) and sourceyaw-v1.9.0 (module zip with `mode_watch.py`, and json). Both CI runs passed and the notes are written.
  - Earlier note, not yet checked then: the page in a window (CS:S was running), and the switch in game. The Strafe Review server hosts the session, so it must be restarted on the new `session.py` before the mode tokens reach the watcher.

## Phase 9: turn speed check, a Strafe Review page (owner, 2026-11-04; planned, not started)

The owner wants a check across all saved attempts: is the turn speed too slow or too fast at some speeds, and is the fix sens / yawspeed or technique? The Histogram shows it per tick and Strafe Review shows it per run; neither adds it up across runs and speeds.

- **Where.** A new `/turn` page in the Strafe Review viewer, next to `/drill` and `/compare` (owner's pick). It is not a hub section and not its own module.
- **Look (mockup shown to the owner).**

  ```
  speed band     your turn vs optimal    strafes
   300-700            98%                 4,210
   700-1100           96%                 6,880
  1100-1500           89%                 3,150
  1500+               81%   too slow        920

  -> You turn 19% too slow above 1500 u/s.
     Try a faster cl_yawspeed entry for high speed (now 120),
     or raise sens about 10%.
  ```

- **Numbers.** Per speed band, the median yawRatio of strafe middles, the same rule as the run stats' "Angle" (`static/stats.js`: 2 ticks skipped at each end, +left/+right ticks out). Speed from `vx`/`vy`. Own attempts only, bhop maps only.
- **Mouse and keys apart.** Ticks with +left/+right held (`buttons` 128/256) are turned by `cl_yawspeed`; they get their own rows, and their advice points at Source Yaw's list. Mouse ticks point at sens.
- **Per sens.** Each attempt saves `mouse` (`sensitivity`, `m_yaw`, `cl_yawspeed`, DPI), and the auto tags mark sens changes. Group by sens setting, so before and after a change can be compared, and the advice uses the current one.
- **The verdict.** Low only in the high bands means the hand can't keep up, so sens or yawspeed is the fix. Low in every band means technique. The page says which, not just the numbers. Band edges and thresholds come from the owner's saved runs.
- **Dropped in the same talk (2026-11-04).** Surf modules (landing quality, ramp smoothness, PB comparison by position, fail stats per stage, progress log, segment trainer: all either grade a style that has no single right way or repeat savelocs / KSF); weak-side finder (Strafe Review already shows it); key timing on every jump (the owner's offsets HUD has it, and more to watch next to JHUD is too much); a landing beep by gain band.

## Phase 10: Zone Exit Speed, a surf HUD module (owner, 2026-11-04; built on branch `zone-exit`, not released)

The owner wants to see how good a surf run's pre jump is: the speed leaving the start zone.

- **Why a module.** Momentum's Zone Velocity speedometer would show it, but its handler (`hud/speedometer.ts` `onZoneChange`) is commented out in the game ("TODO: replace with updates based on new timer events"). The owner added one and saw nothing.
- **Look (owner's picks).** One number, the 3D speed (x, y and z: "it should show xyz speed"), coloured in three bands like JHUD (amber below `speedLow`, green to `speedHigh`, blue above), and the difference to the comparison run's exit speed (normally the PB) in a faster or slower colour. Session best/average was offered and not picked. A HUD customizer component like the other HUD modules ("Zone Exit"), so it can be moved; surf only.
- **10.1 Probe (2026-11-04, surf_aura).** `zone-exit/probe/` logged `ZXPROBE` lines. `--mounted` put the script into the already mounted `custom/movekit-jhud`, so no game restart was needed.
  - `OnObservedTimerSegmentEffectiveStart` fires once on leaving the start zone, timer RUNNING, `majorNum` 1. The game's own scripts don't use it.
  - The run's own `segments[0].effectiveStartVelocity` is still `[0, 0, 0]` at that event, so the module uses `MomentumPlayerAPI.GetVelocity()` then (a filled split wins).
  - `RunComparisonsAPI.GetComparisonRun().runSplits.segments[0].effectiveStartVelocity` holds the comparison's exit velocity (`[327.4, -93.7, -250.0]`, 3D 422.5).
  - Split velocities are `[x, y, z]` arrays; `GetVelocity()` is `{x, y, z}`.
  - The start zone caps horizontal speed (`limitStartGroundSpeed`, about 340 u/s: exits 336-340 horizontal, 393-429 3D). So only the 3D number tells exits apart.
  - Stage starts weren't tried; the module filters on `majorNum === 1`.
- **10.2 Built.** `zone-exit/` (key `zone-exit`, tag `zone-exit-v*`, group hud, `HOOK_ORDER` 70, needs core 1.5.0), copied from JHUD's install, hooks and checks. Default bands 400 / 420 u/s from the probe; map dependent, set in the customizer. Checks: `node zone-exit/check_zone_exit.js` (with the probe's numbers; 4 of 4 mutations caught: no stage filter, a zero split used, another track's comparison, band edge) and `python zone-exit/check_zone_exit.py`; `movekit/check_modules.py` and `hud/check_hud.py` list it.
- **10.3 In game (2026-11-04).** The owner: "looks good". `ZXCHECK` lines over ~20 exits: the run's own split stayed `[0, 0, 0]` (later NaN) for at least 0.5 s after the exit, so the shown speed is the player's velocity at the event. No run was finished, so whether that matches the tick the PB's split was taken at is not checked; the diff may be off by a few u/s. The temporary lines are removed.
- **Switch fix (2026-11-04), wrong diagnosis.** The owner unticked First Jump and a jump-1 line still showed. All four HUD modules were changed to read the customizer's own record (`HudCustomizerHandler.components[ID].enabled`) before `panel.enabled`, and First Jump and Zone Exit hide or bring back the customizer sample when the switch changes; released that way. The real cause: the game's `custom/0-strafe-review` still held the recorder from 2026-11-03 (`SHOW_LINE = true`), which draws Strafe Review's old jump-1 line (`SRLINE` in yaw.log). Strafe Review's launch hook only starts the server and never copies the recorder, so a repo checkout keeps an old recorder until `strafe-review/install.py` runs. Rerun 2026-11-04. The switch change is harmless and stays.
- **10.4 Falling speed limit (owner, 2026-11-07).** A friend's 486 on surf_deadline led to in-game measurements (`getpos_exact` run from Panorama every tick, a stage replay's header). Jump +302 z (√(2·800·57)), gravity in half steps, 12 per tick. Crouching in the air lifts the origin 8.5 (half the hull difference; intended). The start zone counts as left on the first tick the box is fully outside it. On surf_deadline the zone ends at the floor's edge, and a crouched jump over the floor lands on the -322 tick; a box within about 1 unit of the edge on that tick neither lands nor leaves, and leaves on the next tick at -334 (480 in game; the replay's `effectiveStartVelocity` z -334.0066, so the game stores it too). Surfers count about 478 as the top. `MAX_FALL` = 322 in the script, a fixed limit (owner's pick over a setting): downward speed counted at most 322, for the player and the comparison. The start zone limits ground speed only: horizontal was 270-287 at takeoff, 318-351 at the exit after air strafing (the 10.1 note's ~340 was measured at the exit).

## Phase 11: Source Yaw section cleanup and the overlap cue (owner, 2026-11-06; branch `sy-cleanup`)

The owner wants the Source Yaw settings tidied before the Windows version (Phase 12), so the Windows step only has to hide whole cards.

- **Cards, one long page (owner's pick over tabs or sidebar entries).** One card per kind of option, in this order:
  1. Setup: game, Load from autoexec.cfg, Steam launch options.
  2. Yaw cycle: cycle key, mode key, auto by map prefix, the yawspeed lists.
  3. Crosshair: colour switch, base crosshair, KROSSHAIR.
  4. Strafe trainer: on/off, input service, keys, tickrate.
  5. Offset display: show offset, offset key, position, best offset, size and colours.
  6. Trainer sounds: sound or tone, pitch and volume, ticks and repeat, the cue switches.
- **Overlap cue (new).** Plays when both strafe keys are held at once while a jump key is held.
  - Own tick setting, `overlap_ticks` (default 1, 1-20).
  - Own tone pitch, `overlap_pitch` (default 110 Hz, low as the owner's friends need).
  - Switch `cue_overlap` (default on). With a game sound picked instead of the tone, the overlap plays that sound with the same repeat rule.
  - When an overlap and a wrong-key turn happen together, the overlap wins: it is the cause.
- No behaviour change otherwise. The checks (`sourceyaw/check_*.py`) still pass, and the page gets a screenshot check.
- **Built 2026-11-06 (branch `sy-cleanup`, not committed; waiting on the owner's look and in-game test).**
  - Page: the six cards, with the yawspeed list under a "Yawspeeds" sub-head in the Yaw cycle card, and the `+ Add` button there. The three trainer cards dim together while the trainer is off. Screenshot-checked on the owner's settings.
  - `trainer.py`: `TRAINER_DEFAULTS` gets `cue_overlap`, `overlap_ticks` and `overlap_pitch`, and `Tone` gets an "overlap" pitch. The overlap counts from the key press that made it (in `feed`), and the cue needs a jump key held. When it fires, the wrong-key wait restarts, so a wrong turn after a long overlap still waits its `wrong_ticks`. An overlap tone that ends while the wrong turn is still under `wrong_ticks` stops at once and doesn't linger.
  - `hub_section.play_cue(..., overlap_pitch, which)`: the overlap row has its own ▶ button.
  - Checks: new `sourceyaw/check_trainer.py` (synthetic key events). It catches four mutations: no jump needed, no tick wait, the lingering overlap tone, and the wrong-key wait not restarting. `check_settings_api` and `check_hub_section` cover the new fields, clamping and the overlap tone. Every `sourceyaw/check_*.py` passes.
  - The owner's game runs the installed copy in `~/.local/share/sourceyaw`, so the overlap cue is heard only after `sh sourceyaw/install.sh` from this branch.
- **Per-cue sounds (owner, 2026-11-06, after seeing the page).** The owner wanted each cue's sound customisable and asked what Ticks and Hz meant. Picked: one row per cue with its own sound (tone or a game sound), "Pitch (Hz)" and "Wait (ticks)", plus a ▶ button and a switch. Volume and "Repeat (s)" stay shared at the top of the card, and the card's description explains both terms.
  - Settings: `<cue>_sound`, `<cue>_pitch` and `<cue>_ticks` for `wrong`, `none` and `overlap` (`trainer.CUES`).
  - `trainer.migrate` maps 1.9.0's shared `sound` and `tone_pitch` (no-key at 2/3 of the pitch) and `wrong_ticks` onto them. An old `sound: ""` turns both wrong-key cues off.
  - `trainer_value` still writes `sound` and `tone_pitch` from the other-key cue, so a roll back to 1.9.0 reads sensible values.
  - `trainer.CueSounds` gives tone cues one shared `Tone` at their own pitches and plays game sounds for the rest. `Tone(volume, pitches)` now takes a dict. `play_cue(game, sound, tone_volume, pitch)` plays one cue.
  - Checks: per-cue waits, `CueSounds`, the migration and the roll-back keys. Mutations caught: one shared wait, the tone left on for a game-sound cue, no migration.
- **Game badges on the Modules page (owner, 2026-11-06; a core change on the same branch).** Each module card shows which games it works with, one badge per game ("CS:S", "Momentum Mod"), on supported and unsupported cards alike.
  - `module.json` gets `"games"` (keys from `movekit/games.py`). It is checked like `group`, and a release's module.json copy carries it.
  - `LEGACY_GAMES` covers releases from before the field. Gain Converter and Source Yaw say both games; every other module says Momentum.
  - `check_modules.check_groups` covers module.json, the legacy table, the release copy, bad values, and every real module naming its games. Screenshot-checked.
  - Ships with the next `hub-v*` release. Modules don't need a new `needs_core`, because an old core ignores the field.

## Phase 12: Source Yaw on Windows (owner, 2026-11-06; built on `sy-windows`, waits for a Windows test)

Replaces the 2026-10-26 plan for a separate Windows app. Source Yaw becomes a Windows module too, installed from the hub's Modules page, with its settings in the hub section.

- **Scope (owner).** The yaw cycle (binds, sounds) and the strafe trainer, for CS:S and Momentum. No crosshair colour on Windows for either game ("the colour can be left out"). The trainer gives the tone cue only, with no offset number on screen, because hooking DirectX in CS:S risks VAC.
- **What is known.** Windows launch hooks run inside the core exe's process (`movekit/dispatch.py`), so a trainer thread lives exactly as long as the game. The exe bundles the standard library only, with no Pillow, so Windows code uses ctypes, `winsound` and `winmm`.
- **Steps.**
  1. Split `trainer.py`. `Trainer`, `GameEvents`, `read_binds`, `settings` and `map_tickrate` go into a platform-neutral module. The input service socket, `FocusWatch`, the pw-cat `Tone`, `Overlay` and `write_atlas` stay Linux-only. Linux behaviour stays the same.
  2. Windows input: Raw Input with `RIDEV_INPUTSINK` on a hidden window, no admin. It gives the same `(time, EV_KEY/EV_REL, evdev code, value)` events: `MakeCode` equals the evdev code for the basic keys, E0 keys are mapped (right Alt 100, right Ctrl 97), mouse buttons are 272-276, the wheel is `REL_WHEEL` and `lLastX` is `REL_X`. Time comes from `perf_counter` when `WM_INPUT` arrives, not `GetMessageTime` (about 15.6 ms, a whole tick).
  3. Focus: `GetForegroundWindow`, then the process image name, plus the cursor inside `GetWindowRect`.
  4. Tone: a `winmm` `waveOut` backend with the same `mode`/`start`/`close` interface. Game sounds through `winsound`.
  5. Module: `win32` in `module.json`, Python install and launch hooks for Windows, the hub section hides the Crosshair and Offset display cards, KROSSHAIR, the input service and the launch-option text. `check_hub_section.py` expects the section on Windows from then on.
- **Step 1 built (2026-11-06).** `trainer.py` keeps the neutral parts under its old name, because `settings_api` and the checks load it by path. That covers the cue logic, binds, settings, `GameEvents`, `CueSounds` (its `tone_class` is now required) and the main loop `run(game, platform, stop=None)`. `trainer_linux.py` holds the input socket, `Overlay`/`write_atlas`, the pw-cat `Tone`, `FocusWatch` and `Linux`, the platform object that `run` takes. Its docstring lists what a platform gives. `trainer.platform()` imports `trainer_linux` only when it runs. `read_binds(game_dir, allowed)`: `None` passes every known key. `run` closes the tone, input and session on exit, and a set `stop` ends it, for the Windows thread. `yawcore` imports Pillow only inside the crosshair functions. `check_trainer.py` runs `run` with a fake platform, and imports `trainer`/`settings_api` with Pillow, fcntl and `trainer_linux` blocked. `install.sh` copies `trainer_linux.py`.
- **Steps 2-5 built (2026-11-06), not yet tested on Windows.** The owner couldn't test then and asked for everything first, tested in one go.
  - `trainer_win.py`: Raw Input on a hidden window in its own thread (`RIDEV_INPUTSINK`, perf_counter times, 1 ms timers while it runs). Focus is the foreground exe living under the game's install folder plus the cursor in its window, so no exe names are needed. The tone is a winmm waveOut ring of 5×10 ms buffers, refilled on its done event (4×5 ms polled ran dry and crackled), that logs how often it ran dry. Its samples come from `trainer.ToneSynth`, now shared with the Linux pw-cat player.
  - `launch_win.py`, called from `module_hooks.launch` on win32, does `launch-hook.sh`'s job. It finds the game from the exe path or `-game`, runs `yawcore.apply_at_launch` (shared with `--apply`), and starts `mode_watch.run` and `trainer.run` as threads. An atexit step sets their stop event. Output goes to `%APPDATA%\sourceyaw\run.log`.
  - `yawcore` on Windows keeps its config in `%APPDATA%\sourceyaw`, writes no crosshair colour for either game, plays game sounds through winsound and reads launch options from the Steam roots.
  - The hub section is listed on Windows. `data-linux` hides the Crosshair and Offset display cards and the input service row, and the yawspeed rows lose their colour and preview columns. The launch option is the core exe's. Screenshot-checked with Windows mode forced on Linux.
  - `module.json` lists win32. The two lazy Pillow imports sit in `try/except ImportError`, which `check_modules` accepts. The hub exe bundles `ctypes.wintypes`.
  - The step 1 split had broken two hub buttons on Linux, the tone ▶ preview and Show in game. Both are fixed, and the checks now catch them.
  - Tests:
    - `check_launch_win.py`, run on Linux.
    - `check_trainer.py`: struct layouts, key and mouse mapping, the folder test and ToneSynth fades.
    - `check_hub_section.py`: Windows mode faked on Linux.
    - The `sourceyaw-windows` CI job: `windows/check_windows.py` on windows-latest runs the real Win32 code. It covers SendInput into Raw Input, waveOut, `trainer.run`, the launch hook and the hub section.
  - `windows/rawinput_probe.py` is the standalone probe for the owner's game test.
- **Testing.** Claude covers the key table and the split trainer with synthetic events on Linux, and the Windows CI imports every Windows module. The owner or the friend hand-tests on Windows. To check there: whether Raw Input on a hidden window still gets input while CS:S (`m_rawinput 1`) is in front.

## Phase 13: Strafe Trainer as its own module (owner, 2026-11-09; branch `trainer-split`, planned and OK'd 2026-11-09)

The strafe trainer leaves Source Yaw and becomes its own module, so either can be installed, updated or removed without the other (the owner wants every tool modular, and the 4.3 rule: modules don't require each other).

- **Owner's choices (2026-11-09).**
  - Name "Strafe Trainer": folder `strafe-trainer/`, key `strafe-trainer`, tags `strafe-trainer-v*`. Picked over "Strafe Sync" and "Strafe Timing", though it sits next to Momentum's own strafe trainer HUD and Strafe Trainer Height.
  - Upgrade: when Source Yaw updates to the version without the trainer and the trainer was on, the update installs Strafe Trainer as well, with the same settings, and the Modules page shows a notice saying so.
- **What moves.** `trainer.py`, `trainer_linux.py`, `trainer_win.py`, `inputd/`, `overlay/` (GPL-3, with its LICENSE and credits), `check_trainer.py`, `windows/rawinput_probe.py`, the trainer parts of `settings_api.py` (`trainer_config`, `trainer_value`, `trainer_status`, `inputd_command`) and of `hub_section.py` and the page (the three trainer cards, the cue ▶ preview, Show in game). All by `git mv` or split commits, so history follows.
- **Helpers out of `yawcore` into `movekit`.** The trainer uses `find_game`, `GAMES` (process names), `prefix_value`, `play_sound`, `in_folder`, `load_settings`, `CONFIG_DIR` and `OFFSETS_TOKEN`. The neutral ones move into the core (`movekit/games.py` or a new `movekit/sounds.py` for `play_sound`), and `yawcore` keeps its names as thin calls into them. `load_settings`/`CONFIG_DIR` don't move: the trainer gets its own settings (below). The trainer's odd import dance (`import yawcore` before `movekit`, `settings_api` slipping yawcore into `sys.modules`) goes away. This is a core release, so both modules raise `needs_core`.
- **Settings.** Own config folder `paths.config_dir("strafe-trainer")` with one file per game, and `module.json` `data: ["config:strafe-trainer"]`, so deleting Source Yaw's data no longer wipes the trainer's. On first run with no file, it imports the game's old `"trainer"` dict from Source Yaw's settings through `trainer.migrate`. Source Yaw stops reading and writing that key but leaves it in its file, so rolling Source Yaw back still finds the trainer settings there.
- **Game cfg.** Today `yawcore` writes the offset key's alias and bind and `con_logfile yaw.log` into `yaws.cfg` when the trainer is on. These move into the trainer's own `// movekit:strafe-trainer` autoexec block through `cfgblock`, built like `strafe-review/install.py`. Uninstall removes the block. Several blocks each saying `con_logfile yaw.log` is fine (Strafe Review does it already). The token stays `SY_OFFSETS`, so the session core needs no change for it.
- **Key clashes across modules.** Source Yaw warns when the offset key equals the cycle or mode key. After the split neither module may import the other, so the core gets a small shared list: each module records the keys it binds (`paths.data_dir('movekit')/binds.json`, `{tool: [keys]}`), and each section warns about a key another tool holds. Claude's call; no change in what the owner sees.
- **Launch.** Linux: the trainer's part of `sourceyaw/launch-hook.sh` (start `trainer.py`, export `SOURCEYAW_OVERLAY*`) becomes `strafe-trainer/launch-hook.sh`, registered with its own order. Windows: the trainer thread in `launch_win.py` moves to `strafe-trainer/module_hooks.launch`, in the core's launch process like Source Yaw's. The yaw.log reset stays in Source Yaw's hook: it only happens for CS:S crosshair colours, and the trainer reads the log through the session, which copes with a reset.
- **Names on disk stay** (Claude's call): `sourceyaw-inputd` service and socket, `VK_LAYER_SOURCEYAW_overlay`, `sourceyaw-overlay.json`, `SOURCEYAW_OVERLAY*`. Renaming means a sudo reinstall of the service and risks two layers loading if an old manifest stays behind; nobody sees these names in play. The overlay library and its atlas/state move to the trainer's own folders, and the manifest is rewritten to point there. Source Yaw's uninstall stops removing the overlay manifest. `sourceyaw/inputd/install-inputd.sh` stays as a short forwarder, because older Source Yaw installs print that URL for removing the service.
- **Auto-install on upgrade (core).** A module may name modules split out of it: `module.json` `"split_out": ["strafe-trainer"]`, and a hook `module_hooks.split_out(ctx)` that returns the keys to install (Source Yaw: `strafe-trainer` when any game's saved trainer was on). After a successful update, the manager installs those that aren't installed, and stores a notice the Modules page shows as a strip ("Strafe Trainer was installed because it moved out of Source Yaw", with a dismiss button). A failed install shows the same strip with an Install button instead. Auto-update off changes nothing here: it runs when the owner clicks Update.
- **Hub.** New section "Strafe Trainer" (`strafe-trainer/hub_section.py` + `hub/`): the three trainer cards as they are today, with their on/off switch and dimming. Source Yaw's section loses those cards. `module.json`: group Tools, games css + momentum, os linux + win32.
- **Release wiring.** `strafe-trainer-v*` in `module-release.yml`; a Windows CI job for `strafe-trainer/` (or the `sourceyaw-windows` job's paths widened and its checks split); the expected lists in `check_modules.py`; README for the module and a line in the root README; the `release-repo` skill's Movement Kit section.
- **Steps.**
  1. 13.1 Core: helpers into `movekit`, the shared bind list, `split_out` + the Modules notice. Checks: `check_modules.py` (split-out install, failed install, notice dismissed), `check_hub.py`.
  2. 13.2 `strafe-trainer/` module: the moved files, own settings + import from Source Yaw, autoexec block, launch hooks for both OSes, hub section. Checks: `check_trainer.py`, a new `check_settings.py` (import, rollback key left), `check_hub_section.py`, Windows CI.
  3. 13.3 Source Yaw without the trainer: drop the files, cards, cfg lines and launch parts; `split_out` hook. Every `sourceyaw/check_*.py` passes with the trainer gone.
  4. 13.4 Test on the owner's PC: the live copy updated through the Modules page (core, then Source Yaw), Strafe Trainer appears with the same settings, cues and the offset number still work in Momentum. Windows hand test by the owner or the friend.
  5. 13.5 Release in order: core (`hub-v1.10.0`), then `strafe-trainer-v1.0.0` (needs that core), then `sourceyaw-v1.11.0` (needs that core). Source Yaw goes last, so its update always finds Strafe Trainer published.
- **Found while building 13.1, for 13.2/13.3.**
  - Rollback guard: Source Yaw rolled back to 1.10.x with Strafe Trainer installed would start two trainers (two tones, two input connections, two overlay writers, and its old `install.sh` repoints the layer manifest). Strafe Trainer's launch hook skips with a log line while the installed Source Yaw still ships `trainer.py` (Linux `~/.local/share/sourceyaw/`, Windows the kit's `sourceyaw/`), and rewrites its layer manifest on every launch. The check covers the guard.
  - The settings import runs in the install hook, not at first launch, so the new section shows the imported values at once.
  - Source Yaw 1.11's `install.sh` deletes the leftovers in `~/.local/share/sourceyaw` (`trainer.py`, `trainer_linux.py`, `overlay/`, `inputd/`): it installs file by file, so dropping them from its list leaves them. It removes the overlay manifest only while that still points into its own folder.
  - Keys are recorded when they reach the game, not only on Save: Source Yaw in `--apply` at launch, Strafe Trainer in its install hook (after the import) and on Save. Otherwise `binds.json` stays empty for settings saved before the split and the clash warning goes quiet.
- **13.1 built (2026-11-09, not committed).**
  - `movekit/games.py`: `Game.process` (Linux process name) and `Game.sound_vpks`, and `find(key)` (the mod folder, Flatpak left out; `steam` imported inside it so the file stays data only for old `launch.py` copies). `movekit/sounds.py`: `SOUNDS`, `sound_file`, `available`, `play` (cache now `~/.cache/movekit/sounds`, shared). `movekit/maps.py`: `prefix_value`. `movekit/files.py`: `in_folder`. `movekit/keys.py`: `record(tool, game, keys)`, `forget(tool)`, `held_by_others(tool, game)` over `data_dir('movekit')/binds.json`.
  - `yawcore` keeps its names as thin calls into these (`find_game` stays a function so the checks can swap it). No behaviour change; every `sourceyaw/check_*.py` passes.
  - `modules.py`: hook `split_out(ctx) -> [keys]`. `update()` is now the locked `_update()` plus `_split_out()` after the lock is let go (flock isn't re-entrant): it installs each named module that isn't installed and stores `split_from: {from, error}` in its entry. A broken hook or a failed install never fails the update. `install()` clears a failure note once it worked; `dismiss_split(key)` hides the note; uninstall forgets it with the entry. Bridge call `dismiss_split`.
  - Modules page: a strip on the new module's card, "Installed because it moved out of Source Yaw. " (accent border; generic, since any module may split) or "Strafe Trainer moved out of Source Yaw. Installing it failed: ..." (amber, the card's Install button does the rest), each with Dismiss. Screenshot-checked.
  - Checks: `check_modules.py` `check_split_out` (not released yet, install by hand clears the note, released, already installed, broken hook, uninstall) plus the bridge call; caught both mutations (no `_split_out` call, failure note not cleared). New `movekit/check_helpers.py`. `check_hub`, `check_steam`, `check_launch`, `check_panorama`, `check_linux_core`, `check_logtail`, `check_attempts` pass.
  - Left for 13.5: `CORE_VERSION` and `hub_release.VERSION` to 1.10.0.
- **13.1b built (2026-11-09).** What a Strafe Trainer-only install needs that only Source Yaw had, moved into the core as the one copy:
  - `movekit/launchopt.py`: `current(game)`, `steam_path`, `runner`, `with_runner(options, run, also)` (`also`: a tool's old wrapper names that still run it; `sourceyaw-run` runs only Source Yaw) and `offer(game, also)`, the page's `{text, note, already}` for Linux (movekit-run) and Windows (the core exe). `movekit/bindnames.py`: `VALID`, `CODES`, `MOUSE`, `capture_info()`. yawcore's `current_launch_options`, `runner`, `launch_option` and `VALID_KEYS` call these.
  - `movekit/web/form.css` (`mk-` rows, switches, segments, key chips, dialogs, toasts, launch box) and `movekit/web/section.js` (`mk.toast`, `call`, `copy`, `note`, `options`, `numberBox`, `keys.open` key capture with numpad-by-code, wheel and side-button blocking, `leaveGuard`).
  - `sourceyaw/module.json` `needs_core` 1.10.0 (yawcore imports the new core modules).
  - **13.3 must** move Source Yaw's page onto `form.css`/`section.js` and drop its `sy-` copies of those rules and helpers, and `hub_section.KEY_CODES`/`MOUSE_BUTTONS`/`_windows_launch_option`, so each exists once.
  - `check_helpers.py` covers `with_runner` (incl. `sourceyaw-run` not counting for another tool) and that every capture name is a bind name.
- **13.2 and 13.3 go together** (one commit when the checks are green): once the trainer files move, Source Yaw's section, `install.sh` and launch hook break until 13.3 is done.
- **13.2 + 13.3 built (2026-11-09, one commit).**
  - `strafe-trainer/`: the moved files plus `store.py` (settings per game, `import_from_sourceyaw`), `gamecfg.py` (the autoexec block), `settings_api.py`, `install.py` (import, blocks, overlay build into `~/.local/share/strafe-trainer/overlay`, manifest, launch hook order 55; `--apply GAME` at launch), `launch-hook.sh`, `launch_win.py` (rollback guard), `module_hooks.py`, `hub_section.py` + `hub/` on `form.css`/`section.js`. Siblings load through `local_import`. `movekit/games.from_command(argv)` picks the game from Steam's command for both modules.
  - Source Yaw 1.11.0: no trainer in `yawcore` (no offset alias/bind, `con_logfile` only for auto lists; a saved `"trainer"` dict kept untouched for a roll back), `kit_keys.record` in `apply`, page on `form.css`/`section.js`, `module_hooks.split_out`, `install.sh` deletes `trainer*.py`, `inputd/`, `overlay/` from its folder and the layer manifest only while it points there. `sourceyaw/inputd/install-inputd.sh` is the remove-only forwarder.
  - Checks moved with the code: `strafe-trainer/check_settings_api.py`, `check_hub_section.py`, `check_launch_win.py`, `check_game_events.py` (from `check_session_use.py`), `check_install.py` (import, block, section, guard), `windows/check_windows.py` (Raw Input, tone, trainer.run, launch, hub; CI `strafe-trainer-windows.yml`). Source Yaw's checks lost their trainer parts and assert it is gone; `check_modes.py` compares against 1.8.0 with the trainer off and catches all 11 mutations. `check_modules.py` lists `strafe-trainer`; `module-release.yml` takes `strafe-trainer-v*`.
  - READMEs: `strafe-trainer/README.md` (new, overlay GPL-3 credit), Source Yaw's without the trainer, the root list, layout and licence line. Both pages screenshot-checked.
  - Not run here: the Windows checks (CI on push).
  - Follow-ups (same day): `movekit/launch.py` `SPLIT_FROM` runs Strafe Trainer wherever Source Yaw runs (under `sourceyaw-run` and for a `[launch]` list naming `sourceyaw`), so old launch options keep the trainer; `check_launch.py` covers it. `sourceyaw/check_settings_api.py` calls the real `split_out` hook. `check_install.py` covers `install()` doing the import and `launch-hook.sh`'s guard; the guard and import mutations are caught. `sourceyaw/install.sh` ran in a sandbox HOME over a fake 1.10 copy: leftovers and its own manifest gone, Strafe Trainer's manifest kept through install and `--uninstall`.
  - For 13.5: retake `sourceyaw/docs/screenshot.png` (still shows the trainer cards).
- **Dev kit, for 13.4 (2026-11-09).** The owner's live kit is a release copy that updates only from GitHub releases, so unreleased work is tested in a second app: `movekit/movekit-dev` (Linux). It runs the hub and `movekit-run` from the checkout with `XDG_DATA_HOME`/`STATE`/`CACHE` in `~/.local/share/movekit-dev` and `MOVEKIT_BIN_DIR` (new `paths.bin_dir()`, used by `launch.bin_link`, `launchopt.runner`, Strafe Review's old link, `yawcore.BIN_DIR` and both `install*.sh`) in its `bin/`. Every module's installed copy, hook and Vulkan manifest lands there. `~/.config` and the game folders are shared on purpose. The hub shows "(dev)" and uses app id `...MovementKit.Dev`.
  - `movekit/devkit.py setup` keeps `~/.config/{movekit,sourceyaw,strafe-trainer}` from before the first dev run in `config-before-dev`, seeds the dev state from the live kit (no kit, hooks, locks, rollback copies), links the live Vulkan layers except `sourceyaw-*`, links fonts and themes, writes the app menu entry into the real applications folder, and installs the live kit's modules from the checkout (plus their `split_out`, so Strafe Trainer).
  - `movekit/devsteam.py`: `movekit-dev game <css|momentum>` starts the game like the owner's BHOP entry does (game folder, `SteamAppId`, sniper runtime, `<mod>.sh -steam`) under the dev `movekit-run`. `movekit-dev steam-entries` (Steam closed) adds "<game> (dev kit)" non-Steam entries with the game's own launch option prefix, backing up `shortcuts.vdf` first.
  - `launch.game_from_args` falls back to the game folder (`games.from_command`) when the app id is missing or unknown, since a non-Steam entry gets a made-up one.
  - Checks: new `movekit/check_devkit.py` (sandbox HOME: installed kit untouched, writes only in the dev root, layers, seeded state, hook and link in the dev tree, launch prefixes, shortcuts.vdf entries, backup, rerun), `check_launch.py` game-by-folder cases. Mutations caught: no folder fallback, `bin_dir()` ignoring the override.
  - Limits: Strafe Review's `systemd-run` unit name and port 8765 are fixed, so run one kit's game session at a time. Close the dev hub before updating the live kit from its Modules page: on 2026-11-09 the live update failed while the dev hub was open and worked once it was closed (cause not found; the error wasn't logged). Installing in the dev kit writes the checkout's game files, so reinstall in the live kit afterwards. The dev kit runs the checkout as it is; it doesn't test the update path from the 1.9.0 release (that would be a copy-mode kit in the dev tree pointed at a fake GitHub, not built).
  - 13.4 Linux result (2026-11-09): "Momentum Mod (dev kit)" Steam entry ran the checkout `movekit-run`, the game mapped the overlay from `~/.local/share/movekit-dev/data/strafe-trainer/overlay/`, the trainer logged the session (`bhop_glacial -> 100 tick`). Owner checked: cues and the offset number work, offset toggle bind works, Strafe Trainer section shows the old settings, Source Yaw page has no trainer cards. Open: Windows hand test; the update through the Modules page is tested after the 13.5 releases.
  - 13.5 released 2026-11-09 from main e9bdda1: `hub-v1.10.0`, `strafe-trainer-v1.0.0`, `sourceyaw-v1.11.0` in that order, CI green, notes from the tag messages. New `sourceyaw/docs/screenshot.png` taken with the dev XDG folders but without `MOVEKIT_DEV`/`MOVEKIT_BIN_DIR` (else the title says "(dev)" and the launch box shows the full checkout path). Open: the owner's live copy updated through the Modules page, and the Windows hand test.

## Phase 14: Z Penalty, a surf HUD module (owner, 2026-11-09; branch `z-penalty`)

The owner wants to see when the z velocity penalty hits on a ramp climb (the "z penalty" term in the owner's air acceleration graph): air acceleration x0.25 while airborne with z speed in (0, 140], so holding into the ramp can't keep speed.

- **Owner's picks (2026-11-09).** A HUD customizer panel like Zone Exit. All parts, each switchable: "Z PENALTY" label, z speed, ticks in the band, a vertical z bar with 0-140 shaded. A "Ramps only" switch, default on. Sound optional, set on the module's hub page. Momentum surf only.
- **Source.** `CategorizePosition` in Momentum's `mom_gamemovement.cpp`: any airborne tick with z in (0, 140] sets `m_surfaceFriction` 0.25. `Duck()` re-categorizes at tick start with the velocity `GetVelocity()` shows, so no gravity correction.
- **14.1 Probe (2026-11-09).** Free fall -12 per tick exactly; a jump's top is 12 ticks in the band; a ramp climb rises about +8 per tick (18 ticks), others +20 to +44. `GameInterfaceAPI.ConsoleCommand('playvol <sound> <vol>')` plays in game.
- **14.2 Built.** `z-penalty/` (key `z-penalty`, tag `z-penalty-v*`, group hud, `HOOK_ORDER` 80, needs core 1.10.0 for `movekit/sounds.py`). The hub page saves the sound to `~/.config/movekit/z-penalty.json`; `install.py` writes it into the installed script's SOUND line (`settings.py`), so Apply reinstalls. Checks: `node z-penalty/check_z_penalty.js`, `python z-penalty/check_z_penalty.py`; `movekit/check_modules.py` and `hud/check_hud.py` list it.
- **14.3 In game (2026-11-09).** First try: the first jump showed and ramps didn't. A debug log showed why: the tick number came from `GetCurrentTime()`, which moves per frame while the velocity moves per tick, so each tick was counted twice with a z change of 0, and the learned free fall step became 0. Fixed: a new tick is a changed velocity, free fall is a fixed `sv_gravity * GetTickInterval()` (-12), and any whole number of steps per sample is free fall (slow frames). Rerun: every jump top 12 ticks unflagged, every ramp climb flagged; owner: "seems good now". A regression check (every velocity on two frames) catches the old code.

## Later / undecided

- **Panorama module kit.** Planned as Phase 4 (2026-11-03).
- **JHUD**, a per-jump stat display. Planned as Phase 5 (2026-11-03).
- **Gain math in one language.** Done in 3.2: `movekit/web/gain.js`; the Python copy went with the tkinter window in 3.8.
- Windows strafe trainer, and the CS:S version of Strafe Review. Both get easier once the game adapters exist.
- **JHUD: pace colours on flat ground only** (owner, 2026-11-06). A setting under "Colour by: Speed pace" that shows the pace colours only for jumps on flat ground. On a slope, speed comes from the ground rather than the strafes, so the pace judgement would be wrong. Open: how JHUD knows the ground is flat. Panorama may not give the ground's surface normal. A possible fallback is takeoff height = landing height (unchecked). Also open: what a non-flat jump shows instead (font colour, or gain % colours).

## Progress

### Phase 1.1: Steam and game discovery (2026-11-02)

- `movekit/steam.py`, `keyvalues.py`, `games.py`, `paths.py`; `movekit/check_steam.py` covers the edge cases on fake Steam folders (Windows-style vdf, app id vs name match, folder fallback, symlinked roots, Flatpak on/off, env override).
- Source Yaw: `yawcore.find_game` / `flatpak_steam_only` / launch-option parsing call movekit; its own `_game_dir_in`, `_steam_libraries`, `_parse_vdf` and `FLATPAK_STEAM` are gone. Flatpak Steam stays excluded (`steam_roots(flatpak=False)`). The import is `games as kit_games`, because `yawcore`'s `__main__` block has a module-level `games` list.
- Strafe Review: `collector/steam.py` is now a thin wrapper (`find_game()`, `data_dir()`); every module imports it first, so it sets the path to movekit once. `build.py` adds `--paths` for the monorepo root; the exe bundles `movekit.*` (checked with `pyi-archive_viewer`).
- `sourceyaw/install.sh` copies `movekit/*.py` (not `check_*`) to `~/.local/share/sourceyaw/movekit/`; `yawcore` puts the repo root on `sys.path` only when `movekit/` sits next to it there, never `~/.local/share`.
- Small widenings, both only find more: Source Yaw now also reads `~/.steam/steam`'s own libraryfolders.vdf and matches Momentum builds by name; Strafe Review also tries the usual install folder names and `~/.local/share/Steam` when `XDG_DATA_HOME` points elsewhere.
- Verified unchanged: both tools find the same folders and launch options on this PC (probe script, before vs after), Source Yaw `--apply` in a sandbox writes byte-identical files, `install.sh` into a sandbox home works and the installed copy imports movekit, Strafe Review `smoke_test.py` on a rebuilt exe passes all 5 steps, `check_recorder.py` 1305 attempts 0 broken, viewer `check_*.js` pass (`check_css_ssj.js` needs a demo recording, not run).

### Phase 1.2: autoexec cfg blocks (2026-11-02)

- `movekit/files.py` (`write_atomic`) and `movekit/cfgblock.py` (`read_cfg`, `without_block(lines, begin, end)`, `set_block(path, block, add, backup_suffix)`), copied from Strafe Review's `install.py`. `set_block` doesn't print; `install.set_autoexec` keeps its messages. `install.py` imports `write_atomic` for settings.json too.
- Source Yaw's `exec yaws.cfg` line stays in `yawcore` for now. It works differently (one line, not a marked block; turns CRLF into LF; reads with `errors="replace"`; skips the backup for an empty file; checks legacy backup names) and would be its only user, so sharing it would change behaviour.
- Markers unchanged (`// strafe-review begin/end`) at this step; moved to `// movekit:<tool>` on 2026-11-02 (see "Markers and candidate fixes").
- Verified unchanged: 36 fixture cases (missing, empty, LF, CRLF without a final newline, block in the middle, block only, stray end marker, non-UTF-8 byte, existing backup; add, add twice, add then remove, remove), comparing bytes, file mode and backup, identical before and after. Rebuilt exe bundles `movekit.cfgblock` and `movekit.files`; `smoke_test.py` passes all 5 steps.

### Phase 1.3: VPK reading (2026-11-02)

- `movekit/vpk.py`: `read_tree` (Strafe Review's parser: root-folder files, v1/v2 only), `files` (Strafe Review's `vpk_files`: empty set on any error) and `read_file` (Source Yaw's `_read_from_vpk`, tree cached per `_dir.vpk`). Reads only the header and tree, not the whole file.
- Strafe Review `install.base_timer` uses `vpk.files`; Source Yaw `sound_file` uses `vpk.read_file`.
- Two edge cases change for Source Yaw, neither reachable today: a file at a VPK's root is found at `name.ext` (was `" /name.ext"`), and a VPK whose version isn't 1 or 2 raises ValueError, which `sound_file` already skips. Sounds always sit under `sound/`, and Valve's VPKs are v1 or v2.
- Verified: synthetic VPKs (v1, v2, v3, preload bytes, data in the `_dir.vpk` and in `_000.vpk`, root file, bad signature, cut short, missing) and all 8 VPKs of the CS:S and Momentum installs on this PC (listing hash), plus every offered sound read from each game's sound VPKs: identical before and after apart from the two edge cases. A copy laid out like the installed app finds the same sounds. Rebuilt exe bundles `movekit.vpk`; `smoke_test.py` passes.

### Phase 1.4: binds and aliases (2026-11-02)

- `movekit/binds.py`: `BIND` / `ALIAS` regexes, `cfg_text` (text or "" on a read error), `parse_bind` (raw key and rest), `keys_bound_to` (the strict `bind "KEY" "CMD"` form the game writes), `aliases(cfg_dir)`, `commands`, `resolve(command, wanted, alias_map)` (alias depth 6).
- Source Yaw: `trainer.read_binds`, `yawcore.keys_bound_to_cycle` and `key_conflicts` keep their names and signatures and call movekit. Each keeps its own pre-processing: `key_conflicts` cuts at `//` and strips quotes, `read_binds` doesn't. ROLES, SOURCE_KEYS, `forwarded()` and Source Yaw's own alias names stay in Source Yaw.
- Strafe Review's `game_mouse` stays in `viewer/server.py`. It reads cvars, not binds, and is the only cvar reader in the kit. It moves when a second tool needs cvars.
- Verified unchanged: `read_binds` (real, no and partial input-service config), `keys_bound_to_cycle` (both commands) and `key_conflicts` (16 keys) on 10 fixture game dirs (LF, CRLF, missing files, aliases in subfolders and loops, non-UTF-8 bytes, strict vs loose bind forms, unquoted, upper case, tabs, `//` inside quotes) and the real CS:S and Momentum cfgs: identical JSON. Source Yaw `apply` in a sandbox on LF, CRLF and a copy of the real CS:S cfgs writes identical files. A copy laid out like the installed app imports `movekit.binds`.

### Phase 1.5: updater, part 1 (2026-11-02)

- Fix first (`f28a8fc`): Source Yaw's `dev_checkout` only looked for `.git` in the app folder. In the monorepo `.git` sits one level up, so a dev copy with auto-update on would have run a release's installer over `~/.local/share/sourceyaw`. Now `movekit.updater.in_git_checkout` checks the folder and its parent, no further (a dotfiles repo in `~` would match).
- `movekit/updater.py`: `parse_version`, `in_git_checkout`, `frozen_exe`, class `Updater` (state file, `auto`, `newer`, `failed`, `check` every `check_every`, `install` marking installed/failed; subclasses set `release_info` and `_install`), and the install modes `install_source` (source archive + install script, no terminal, 3.11.2 tar fallback), `swap_exe` and `clean_old`.
- Each tool's `updater.py` subclasses it and keeps every name its callers use. Source Yaw keeps `installed()` (waiting for a restart), `dev_checkout` and a daily check. Strafe Review keeps the 6 h check, the `error` key, `info()`, `checkout_version`, the `STRAFE_REVIEW_UPDATE_API` override and the start-up step that turns an `installed` tag that didn't take into `failed`.
- Not changed yet: both still ask `releases/latest` of their old repos, with unprefixed tags, and Source Yaw still runs `install.sh` at the archive root.
- Verified unchanged: 41 cases on a faked GitHub (newer, same, older, prefixed and garbage tags, unreachable, bad JSON, missing tag, cached and stale state, installer failing, bad or cut tarball, no or nested install.sh, two top folders, git checkout; zip without exe, exe in a subfolder or upper case, renamed exe, no asset, repo mode, restart after install): identical JSON for calls, return values, exceptions, state files and files on disk. A copy laid out like the installed app imports `movekit.updater`. Rebuilt exe bundles `movekit.updater`; `smoke_test.py` passes all 5 steps, including the exe swap.

### Phase 1.5: updater, part 2 (2026-11-02)

- `0737234`: both tools ask `Soulmanyes/movement-kit`'s release list (`/releases?per_page=100`) instead of `releases/latest` of their old repos. `Updater.pick` keeps releases whose tag starts with the tool's `tag_prefix` (`sourceyaw-v`, `strafe-review-v`), leaves out drafts, pre-releases and tags that don't parse, and takes the highest version, not the first entry. A non-list answer or no matching release raises ValueError, which both callers catch.
- `parse_version` strips a `<name>-v` prefix; unprefixed tags (cached state, `v1.5.1`) parse as before.
- Source Yaw runs `sourceyaw/install.sh` from the release's source archive (it copies `movekit` from `$SRC/..`). Its User-Agent stays `sourceyaw`. `STRAFE_REVIEW_UPDATE_API` now points at a list endpoint; `smoke_test.py`'s fake GitHub lists another tool's newer release first.
- Verified: the 41 part-1 cases, with tags and URLs mapped back, are identical except the intended changes (prefixed tags count as newer; archives with only a root `install.sh` now fail with "no sourceyaw/install.sh", nested ones install; `nightly` is no release; a `[1]` answer used to crash Strafe Review's check with AttributeError and is now a check error). 13 new cases: mixed lists (other tools, drafts, pre-releases, junk entries, 1.10 vs 1.9), empty and non-list answers, old cached state with a new list, prefixed `installed` marks on restart. Installed-layout copy imports `movekit.updater` and picks the right tag. Rebuilt exe bundles `movekit.updater`; `smoke_test.py` passes all 5 steps.

### Phase 1.6: release CI (2026-11-02)

- `ba124b6`: `.github/workflows/windows-release.yml` is the shared Windows build (`workflow_call`): PyInstaller build, smoke test, zip with the tool's files and the bundled Python's licence, workflow artifact, and on a tag the GitHub release. Every run step runs in the tool's folder. Inputs: `tool` (folder and tag prefix), `title`, `build`, `smoke`, `files`, optional `version`.
- Callers: `strafe-review-windows.yml` (tags `strafe-review-v*`, VERSION check through `collector/updater.py`) and `gain-converter-windows.yml` (tags `gain-converter-v*`, no VERSION to check). Both can also be run by hand for a test zip.
- The release refuses a tag without the tool's prefix and, for Strafe Review, a tag that isn't `strafe-review-v<VERSION>`. Release notes start at the tool's own previous tag (`--notes-start-tag`), not at whichever tool released last. Title: "Strafe Review 1.5.0".
- Source Yaw has no Windows build and no workflow: its releases stay source archives, made by hand.
- First GitHub runs (2026-11-02, by hand on `main`): both workflows passed build, smoke test and zip (runs 41375437781 and 41375440502). The zips hold the same files as the old repos' zips.
- Before that, locally: YAML parses; the release step's bash run with a stub `gh` in a scratch clone (matching tag, wrong VERSION, another tool's tag, a tool's first tag, a later tag) does the right thing under `bash -e`. The Windows steps (PowerShell, `Compress-Archive`, the build) run on GitHub for the first time with the first push and a hand run.

### Phase 1.7: first kit releases and bridge releases (2026-11-02)

- Kit releases: `sourceyaw-v1.6.0` (by hand, source archive), `strafe-review-v1.5.0` and `gain-converter-v1.1.0` (tag CI built and smoke-tested the exes). `movekit.updater.pick` on the live release list picks each tool's own tag.
- `sourceyaw/install.sh` run through `curl | sh` fetches the kit at its newest `sourceyaw-v*` tag (GitHub's `matching-refs` API, `sort -V`) and runs `sourceyaw/install.sh`; READMEs link the kit and per-tool release lists (`releases?q=<tool>-v`).
- Bridges: `Soulmanyes/sourceyaw` v1.5.2 (updater reads the kit's release list, picks `sourceyaw-v*`, runs `sourceyaw/install.sh` from the kit archive; `install.sh` via `curl | sh` forwards to the kit's). `Soulmanyes/strafe-review` v1.4.1 (updater reads the kit's list, swaps in the newest `strafe-review-v*` exe). Both treat a cached answer from the old repo (tag without the prefix) as stale, so the second hop doesn't wait a day. Gain Converter had no updater: its old README points at the kit.
- Checked: the Source Yaw bridge installed `sourceyaw-v1.6.0` into a fake HOME (and the old `curl | sh` forwarded and installed there too; the real install untouched). The Strafe Review bridge's Windows smoke test passed on the old repo's CI with a fake list holding another tool's higher release and a pre-release; its `check()` against the live kit returns `strafe-review-v1.5.0` with the zip.
- Done 2026-11-03: the three old repos (`Soulmanyes/sourceyaw`, `strafe-review`, `gain-converter`) are archived. The owner chose not to wait for the friend's Windows exe to move first: an archived repo stays readable, so an old copy's updater still gets the bridge release (`releases/latest` on the old Strafe Review repo still answers `v1.4.1`). Was: archive them once a real old install has moved (the friend's Windows exe 1.4.0 → 1.4.1 → 1.5.0).

### GitHub repo (2026-11-02)

- `Soulmanyes/movement-kit` created private, `main` and all 21 `<tool>-v*` tags pushed. As expected, the tags started no runs and made no releases. The repo went public through `/go-public` the same day (privacy scan of files and history clean).
- Sandbox test (2026-11-02, owner): all three tools run from the monorepo with a fake HOME holding copies of the real cfg/ and custom/ folders, and symlinked VPKs and yaw.log. Strafe Review installed into the copy, served on 8799 and collected 1305 attempts from the live yaw.log. No real file changed. Owner: "looks good". Source Yaw was light mode only because the fake HOME has no dconf (`color-scheme` reads `default` there). Not tested yet: the game running the kit versions (needs the real install swap with the game closed).
- Real install swap (2026-11-02, owner): with Momentum closed, the live installs were backed up to `~/archive/movement-kit-swap-2026-11-02/` (both share folders, `~/.config/sourceyaw`, the `~/.local/bin` links, desktop file and icon, Vulkan layer json, Momentum and CS:S cfgs, `custom/0-strafe-review`), then `sourceyaw/install.sh` and `strafe-review/install.py` ran from the monorepo. `strafe-review-run` now links into `movement-kit/strafe-review/collector/`, and the 8765 server unit runs from the monorepo. autoexec.cfg and both yaws.cfg came out identical; the root-owned input service already matched (only the `@USER@` template differs). The installed recorder `.ts` was behind both repos (it lacked the per-strafe loss causes in the in-game line) and is now current. Owner played with the unchanged launch options: "everything works". Rollback: copy the backup back, or run the installers from the old folders.

### Markers and candidate fixes (2026-11-02, owner chose "1")

The first behaviour changes, one commit each:
- `c34f964` `write_atomic` writes bytes read with `surrogateescape` back unchanged (Strafe Review's install no longer crashes on a non-UTF-8 autoexec.cfg) and keeps a replaced file's mode; a new file gets `0666 & ~umask` instead of 0600.
- `ab3d45f` `binds.strip_comment` cuts a `//` comment only outside quotes. `read_binds` now sees `bind o "+moveleft" // x`, and `key_conflicts` reports `say http://x` whole.
- Both tools write `// movekit:<tool> begin` ... `end` blocks through `cfgblock.set_block(path, tool, body, add, backup_suffixes, legacy)`, with the tag prefix as the tool name (`sourceyaw`, `strafe-review`). An old block (`// strafe-review begin`, or Source Yaw's `// added by Source Yaw`/`CS:S Yaw` comment with its exec line) is replaced where it stands, so the cfg's order stays the same; a new block goes at the end after a blank line. The file keeps CRLF and non-UTF-8 bytes (Source Yaw used to turn it into LF and replace them). It is only written when it changes, and a tool backs up a non-empty file before its first change (either Source Yaw suffix counts). Source Yaw still leaves an `exec yaws` line the user wrote alone, and turning it off still removes that line too. Strafe Review's setup check accepts either marker.
- Checked: a harness ran the old and new code on 19 fixture autoexecs (missing, empty, LF, CRLF, no final newline, non-UTF-8, old and new blocks of both tools, the user's own exec line, trailing blanks, copies of the real Momentum and CS:S files) with 8 add/remove sequences, plus bind fixtures. Every difference was one of: the new markers, a blank line before an appended block, CRLF and bytes kept, mode 0644 instead of 0600, a blank-line-trimmed end after a removal, no backup of a missing or empty file or when nothing changes, a backup before a first removal, and the two bind fixes. No errors (the old code raised UnicodeEncodeError on 6 non-UTF-8 cases). Backups hold the original bytes (43 checked). The rebuilt exe passes `smoke_test.py` 5/5; a sandbox `install.sh` copy migrates a CRLF legacy line in place.
- Rollback note: older copies don't know the new markers. An old Strafe Review install adds a second block (a repeated `con_logfile`, harmless); an old Source Yaw sees the `exec yaws.cfg` line inside the new block, and turning it off removes that line and leaves the two marker comments.
- Live step (2026-11-02, Momentum closed): ran `sourceyaw/install.sh` and `strafe-review/install.py`. Strafe Review's block moved to the new markers in place. Source Yaw's install doesn't touch autoexec.cfg; its legacy block moved when `set_autoexec(on)` ran (what the app's toggle does). Result: both `// movekit:` blocks in the old order, no new `.bak` files. Off then on moves Source Yaw's block to the end, and removing a block from the middle leaves two blank lines once (5 more off/on cycles on a copy: no growth); the live file was tidied back to one. Restarted the `strafe-review` unit on the new code (`/api/status` autoexecBlock true, collecting) and set `chmod 644` on autoexec.cfg, `settings.json` and `strafe-review.ts`, which older code had left at 0600. The owner played on it the same day: works.
- Small fixes (2026-11-02, owner picked them before Phase 2): `3839bc3` taking a block out from between two blank lines drops the blank line before it too, so no double blank line is left (checked on LF and CRLF copies of the live file, 5 off/on cycles, Source Yaw's legacy line, the user's own blank lines kept). `e09335e` the collector's attempt files get the usual new-file mode (0644) instead of mkstemp's 0600, through the new `movekit.files.new_file_mode()`, which reads the umask once at import (no more brief umask 0 on every write). The rebuilt exe passes `smoke_test.py` 5/5. Live the same day, after Momentum closed: reran `sourceyaw/install.sh` (autoexec.cfg unchanged), restarted the `strafe-review` unit (`/api/status` fine), and set `chmod 644` on the 1002 old 0600 attempt files (of 1323).

### Phase 2.1: yaw.log reading (2026-11-02)

- `movekit/logtail.py`: `LogTail(path, start)` returns the complete lines written since the last call and never blocks, so a loop that waits on a socket can call it every turn. It waits while the file is missing, and reads from the top again when the file is truncated or replaced. `follow(path, once, poll)` is the collector's old generator, now built on `LogTail`; it still yields `None` on idle ticks for `drop_stale`. `map_state(line)` and `map_name(line)` are the trainer's map-line parsers. Lines keep a CRLF file's `\r`, as the collector's did.
- The collector uses `logtail.follow`; the trainer uses `logtail.map_state` and `map_name` (its per-map tickrate table stays a trainer setting). The trainer still reads yaw.log with its own `readlines()` loop, and `yaw-watch.sh` is left as is (the daemon step replaces it).
- Checked: `movekit/check_logtail.py` (missing file, appends, half lines, CRLF, bad bytes, `start="end"`, truncation, replacement, removal, long lines, `follow` once and idle ticks, Momentum and CS:S map lines). Old and new `follow(once=True)` give the same lines on the live Momentum log (208005 lines), the CS:S log and a random-byte file; old and new map parsers agree on all 445705 lines. Rebuilt exe passes `smoke_test.py` 5/5; viewer and recorder checks pass.
- Candidate change, not made: move the trainer onto `LogTail(start="end")`. That changes three things. (1) The trainer would notice yaw-watch.sh truncating the log on launch; today, with the log open past its new end, it misses lines until the file grows back past where it was. (2) It would see only complete lines; today `readlines()` also hands over a half line, so an offsets-toggle echo without its line break counts at once (with `LogTail` it waits for the break), while a map line split across two reads is missed. (3) Text mode turns CRLF into LF; `LogTail` keeps the `\r` (the parsers don't mind). Needs an in-game check of the offsets toggle. The daemon (Phase 2.2) reads the log for the trainer anyway, so this may fold into that step.

### Phase 2.2: session core (2026-11-02)

- `movekit/session.py` as designed above: `Bus` (ids, the last 500 events kept for reconnects; a Last-Event-ID above the newest id, from before a session restart, gets every kept event, a queue per listener), `TokenScanner` (yaw-watch.sh's rules: a token counts once something follows it or its line ends; chat cut at " : "; each token once per line, also while the line is half written), `Session` (log to events, `start="end"` by default; an emptied or replaced log starts over), `serve`/`start` (HTTP on 8766, `None` when the port is taken; Host header must be 127.0.0.1/localhost; CORS only for localhost pages), `listen()` (a client generator that reconnects with Last-Event-ID and yields `None` while there is no session), and `python -m movekit.session [--game] [--log] [--port]`.
- `LogTail` gained `pending` (the half-written line) and `opened` (counts files opened, so the session can tell the log started over).
- No tool uses it yet. Checked: `movekit/check_session.py` (bus, tokens, Momentum and CS:S map lines, emptied log, HTTP status/events/reconnect/Host/CORS/taken port). Replaying the live Momentum log gives 59 `map_loaded`, 58 `map_left`, 115 YAW tokens and 16 SY_OFFSETS, the same 16 the trainer's `in line` test finds. A short standalone run served `/status`, and a second copy reported the port taken.

### Phase 2.3: Strafe Review hosts the session (2026-11-02)

- `fc8290e`: `viewer/server.py` calls `movekit.session.start()` right after it binds 8765 and only while collecting, so a second copy exits before it touches 8766. `collector.run()` gained `on_saved(path, attempt)`, called only for an attempt it wrote (not one already on disk); the server's callback publishes `attempt_saved {dir, id}`, `dir` being the map folder `/api/attempt/<map>/<id>` uses. The collector itself knows nothing of the session, so `collector.py --once` is unchanged. After `serve_forever()` returns (Stop button, update, Ctrl+C) the server frees 8766 before `RESTART()` starts the new copy. `/api/status` gained `session` (the hosted session's status, or null).
- `MOVEKIT_SESSION_PORT` sets the session port (default 8766), for tests and for listeners alike.
- Checked: the rebuilt exe passes `smoke_test.py` 5/5, with new checks on port 8791: the attempt written to the log comes out as one `attempt_saved {dir: "bhop_smoke", id}`, Stop frees the session port, and the updated copy hosts the session again. Against the live log (game closed): 8766 `/status` and 8765 `/api/status` answered, 1323 attempts seen, then stopped. The unit starts with the game from the monorepo, so the next launch runs this.
- Open: when another process holds 8766 (a standalone `python -m movekit.session`), the server prints one line and its attempts go unannounced; listeners can't publish. Fix only if a tool ends up needing it (a POST endpoint, or the standalone session stepping aside).
- Next (2.4): the trainer and yaw-watch.sh listen. This is where the trainer's candidate change above is settled, with an in-game check of the offsets toggle and the CS:S crosshair swap.

### Phase 2.4: the trainer and the crosshair watcher on the session (2026-11-02)

- `b6ce625`: `movekit.session.join()` as described under Phase 2 (`Joined.mode` is `host`, `listen` or `private`; `events` is a queue). Event streams now end within a second of their session stopping, so a listener notices at once and can take the port (before, it waited for its 35 s timeout).
- Trainer: `GameEvents` turns `map_loaded`/`map_left`/`token` into `in_map`, the tickrate and the offsets toggle; its `readlines()` loop is gone. It joins after the input service check, so a trainer that gives up never holds the port. This settles the candidate change from 2.1, with one more difference: the toggle's echo now counts as soon as something follows it (session token rules) and is ignored in chat. Dropped: setting "in the menu" when the log first appears mid-run (the trainer counts everything until the first map event, as it did without a log).
- `yaw-watch.sh` is replaced by `sourceyaw/crosshair_watch.py`: each `YAW_<speed>` token with a `crosshairs/<token>.png` is copied to a temp file and renamed over `current.png`. In-order tokens end on the same image as the old "last token" rule. `sourceyaw-run` now empties the CS:S log (same condition as before: CS:S with colours on) before starting the helpers; `install.sh` removes the old `yaw-watch.sh`.
- Strafe Review: hosting moved into a thread that retries every 5 s; `announce()` looks up the hosted session per attempt.
- Checked: `movekit/check_session.py` adds join (host, listen, private on a port serving another log, takeover when the host closes, port freed). New `sourceyaw/check_session_use.py`: `GameEvents` (toggle, tickrate by prefix, CS:S's nameless map line, menu) and `crosshair_watch` on a live temp log while hosting and while the port serves another log (a token without its line break swaps, chat and unknown speeds don't, run-together echoes end on the last, no temp file left). The rebuilt exe passes `smoke_test.py` 5/5. A server started while another process held the session port hosted it within 5 s of the port coming free.
- Live (game closed): reran `sourceyaw/install.sh`; the installed copy has `crosshair_watch.py` and `movekit/session.py`, and its modules import the installed movekit. The Strafe Review unit runs from the repo, so it picks this up on the next launch.
- Done 2026-11-02: the owner checked in the game that (1) in Momentum the offsets toggle key hides and shows the number, and (2) in CS:S the cycle key swaps the crosshair colour. Both pass.
- Open: a listener reconnecting after its host left re-checks nothing; if a session for another log takes the port in that moment, it would listen to the wrong log. Not seen in practice; fix if it shows up.

### Phase 2.5: one launch option (2026-11-02)

- Design (Claude's call; the owner left the internals to Claude): `movekit/movekit-run` is the wrapper, bash as before (it has to strip and restore `LD_PRELOAD`/`LD_LIBRARY_PATH` and exec the game). `movekit/launch.py plan` works out the game from Steam's `AppId=` (`games.py`, no hardcoded id) and which hooks to run; the wrapper sources each tool's **launch hook** (`sourceyaw/launch-hook.sh`, `strafe-review/collector/launch-hook.sh`, the old wrappers' bodies) inside a function, so a hook keeps its variables `local`, exports reach the game, and every helper pid lands in one `HELPERS` list with one stop trap.
- Registration: each installer runs `launch.py register <tool> <order> <hook>`, which links the hook as `$XDG_DATA_HOME/movekit/hooks/<order>-<tool>` and `~/.local/bin/movekit-run` to its own movekit copy (the installed Source Yaw carries one; Strafe Review runs from the repo). Order: Strafe Review 20, Source Yaw 50 (today's order: the trainer then finds the server's session). `unregister` removes the hook; `movekit-run` goes with the last tool, or is relinked to a remaining tool's copy if it pointed into the one being removed.
- One settings file: `$XDG_CONFIG_HOME/movekit/settings.toml`, `[launch]` with a list of tools per game. Missing file or game = every registered hook, which gives today's behaviour (Strafe Review's hook skips anything but Momentum). A broken file, or Python 3.10 (no `tomllib`), is reported and ignored; `launch.py`'s notes go to `~/.local/state/movekit/launch.log`, rewritten each launch. Source Yaw's own settings and `watch.env` stay where they are.
- Old names: `sourceyaw-run`, `css-yaw-run`, `yaw-run` (the full-path form) and `strafe-review-run` are links to `movekit-run`, which then runs only that tool, so old launch options do exactly what they did. `MOVEKIT_RAN` (exported to the command) stops a tool running twice in a chain (`strafe-review-run sourceyaw-run`, `movekit-run sourceyaw-run`).
- Changed on the way: Strafe Review's hook now only starts the server for Momentum (the old wrapper started it for any game). Source Yaw's app suggests `movekit-run` and counts any of the old names as set up (`check_launch_option.py`). Windows is unchanged: the Strafe Review exe stays its own launch option.
- Not done: `game_exit` from the wrapper (listeners can't publish, the 2.3 gap).
- Checked: new `movekit/check_launch.py` (plan, settings, old names, `MOVEKIT_RAN`, register/unregister, and `movekit-run` with fake hooks and a fake game: arguments verbatim, `LD_*` back for the game only, exports, helpers stopped, exit code kept, failing hook skipped, chains run each tool once), `sourceyaw/check_launch_option.py`, the existing session/logtail/steam checks, the rebuilt exe's `smoke_test.py` 5/5, and a sandbox `sourceyaw/install.sh` plus both real hooks through `movekit-run` with stubbed `systemd-run` (Momentum: the unit and the page; CS:S: KROSSHAIR exported, log emptied, the crosshair watcher running for the game and stopped after).
- Cutover, with the games closed: back up `~/.local/bin` links and `~/.local/share/sourceyaw`, merge, rerun `sourceyaw/install.sh` and `strafe-review/install.py`. The current launch options keep working unchanged; then switch both games to `... movekit-run %command%` and play once.
- Done 2026-11-02: cut over with the games closed (backup in `~/archive/movement-kit-2.5-cutover-2026-11-02/`), `main` fast-forwarded, both installers rerun. Hooks `20-strafe-review` and `50-sourceyaw` registered; `launch.py plan` lists both for Momentum and CS:S. The owner played both games and both work.

### Phase 2.6: attempt format (2026-11-02)

- Design (Claude's call, as for the rest of Phase 2): `strafe-review/FORMAT.md` is the one reference for the wire lines and the saved file (`format` 1). The recorder's header comment, `srrec.py` and Strafe Review's PLAN entry point to it instead of describing it.
- Version rule: one number for wire and file (the file is the wire JSON as sent). New optional fields, event kinds, label/reason values and columns appended to `cols` keep 1; removing or changing the meaning of anything bumps it. Readers look columns up by name and ignore what they don't know.
- Required fields are the ones readers use unguarded: `format, id, map, interval, label, cols, rows`. Everything else is optional with a stated default, which matches the 1344 files on disk (8 lack `postRows`, 196 lack `mouse`) and the minimal object `viewer/css_demo.py` writes. Labels, reasons and event kinds come from the recorder source and the files (`level`, `target`, `restart` are real reasons no saved file has yet).
- Reader corrections (old spectated runs saved as `own`, replays that end `replaced`, rows before a replay's teleport, rebuilt gain/ideal, coarse speed) are documented in FORMAT.md and stay in `server.py`/`data.js`; no third copy.
- `movekit/attempts.py`: `FORMAT`, `store()`, `files()`, `attempt_id()`, `load()` (raises `UnsupportedFormat`, a `ValueError`, for another number), `columns()` by name (NaN for a missing column), `problems()`. The collector takes its store path from it, and the server's `head()` loads through it, so a file with an unknown format is skipped with a note on stderr.
- Checked: new `movekit/check_attempts.py` (full, minimal, missing optional, unknown field, unknown appended column, format 2, broken rows) and `--store` over the real store: 1344 files, no problems. Other movekit checks, the viewer's node checks, `check_recorder.py` on the real log (1344 attempts, 0 broken) and the rebuilt exe's `smoke_test.py` 5/5 pass.

### Phase 3.1: hub shell (2026-11-02)

- `movekit/hub.py`: `discover(root, platform)` finds `<folder>/hub_section.py` files, checks `SECTION` (key, title, os, page, api, optional order) and filters by `sys.platform` prefix. A broken section is skipped and listed in the problems, not fatal. Two folders with one key are both refused, so the clash shows instead of whichever folder sorts first.
- Imports: each `hub_section.py` loads under its own module name, and its folder is not put on `sys.path` (tool folders share file names, e.g. `updater.py`). A section loads its own helpers with `hub.local_import(__file__, "name")`.
- `Bridge` is the pywebview `js_api`: `sections()` and `call(key, name, args)`, replying `{ok, result}` or `{ok, error}`. pywebview runs calls on worker threads, so each section has a lock and its functions never overlap.
- Pages: no iframes, since pywebview injects `window.pywebview.api` per page and doesn't promise it inside frames. Each section is its own page at `/s/<key>/`, served with `movekit/web/` (`hub.css`, `hub.js`, `home.html`) by a stdlib server on 127.0.0.1 and a free port. The Host header is checked, and paths can't leave their folder. `hub.js` draws the sidebar and gives pages `hub.call(name, args)`.
- `python movekit/hub.py [--root DIR] [--class NAME] [--section KEY] [--debug]`. pywebview is imported only there, so the rest of `movekit` stays stdlib. `--class movekit-hub-test` makes the window float without focus (Hyprland rule for `*-test`), and `--section` opens on a section's page for screenshot checks.
- Window checked 2026-11-02 (pywebview 6.2.1, WebKitGTK) with fixture sections from a temp `--root`: home page with the section list and the broken one listed, the sidebar's active section, and a bridge call (`add`) returning into the page.
- Checked: new `movekit/check_hub.py` (43 checks: discovery, OS filter, every kind of broken section, same-named helpers kept apart, the bridge's errors, calls not overlapping, the page server's paths and Host check).

### Phase 3.2: Gain Converter section (2026-11-02)

- `gain-converter/hub_section.py` (key `gain-converter`, Linux and Windows, no Python functions) and `gain-converter/hub/` (`index.html`, `gain-page.js`, `gain.css`): the tkinter window's controls in the page. The direction switch, − / box / +, the slider, the result, and the SVG graph with the measured dots, the current-value guides and click or drag to pick.
- `movekit/web/gain.js` holds the curve (`K`, `MEASURED`, `cssToMom`, `momToCss`) for browsers and node. The viewer turned out to have no copy of it (see step 3.2 above), so the only other copy is `gain_converter.py`, kept for the old window until 3.8.
- Checked: new `gain-converter/check_gain.py` (node runs `gain.js`; K, the measured points and 401 values each way equal Python's). `check_hub.py` now also loads the kit's own sections on Linux and Windows with no problems. Window screenshot: 90 % CS:S gives ≈ 96.5 % Momentum, as in the tkinter window; all layers visible. Clicking and dragging tested by the owner 2026-11-02: works.

### Phase 3.3: HUD section (2026-11-02)

- New top-level `hud/` package. `hud/settings.py` is the store for in-game display settings (`load`, `get`, `save`, with `DEFAULTS` holding each key's type and default; unknown keys are kept, wrong types refused). Only `inGameLine` so far. The file is still `settings.json` in Strafe Review's data folder.
- `strafe-review/recorder_settings.py`: `FOLDER`, `RECORDER`, `SHOW_LINE` and `apply(game, show_line)`, which writes the value into the installed recorder. Standard library only at load (movekit is imported inside `apply`), so the hub loads it by path with no bare `steam` or `install` left in `sys.modules`.
- `install.py` keeps `apply_settings(game)` (used on install and by the server), now `recorder_settings.apply` with the value from `hud.settings`. Its own `settings`/`save_setting`/`SETTINGS` are gone. `viewer/server.py`'s `/api/settings` stays as it was for the review page's toggle, on top of `hud.settings`.
- `hud/hub_section.py` (key `hud`, order 20, Linux and Windows): `get()` returns the settings plus `recorder`: `installed`, `not installed` or `no game`. `set_line(on)` saves and applies, and returns `applied`. The game is `movekit.steam.game_dir(games.MOMENTUM)` (MOMENTUM_DIR first), counted only if the folder exists. `hud/hub/` is the page: one card with the toggle and the same notes as the review page.
- `movekit/hub.py` now puts the kit root on `sys.path`. Run as `movekit/hub.py`, sections could not import `movekit` before (no section did yet).
- The Strafe Review exe picks up `hud` through `build.py`'s `--paths` (the repo root), the same way it picks up `movekit`.
- Checked: new `hud/check_hud.py` (store, recorder rewrite, the section through discovery and the bridge with no game / not installed / installed, no bare modules left behind, `install.apply_settings` reading the same store; all in a temp folder). All `movekit/check_*.py` and `check_gain.py` pass. `recorder/check_recorder.py` passes. `smoke_test.py`, run against the script through a wrapper, passes steps 1–2 (these include `POST /api/settings`). Step 3 fails only because `stop_all` pkills by the exe path, so it misses the wrapper's python; the Windows CI build runs it in full. Window screenshot: the HUD section shows its card and its stored value. Toggle tested by the owner 2026-11-02: works.

### Phase 3.4: Strafe Review section (2026-11-02)

- `strafe-review/hub_section.py` (key `strafe-review`, order 15, Linux and Windows) talks to the running server over HTTP (127.0.0.1, 8765 or `STRAFE_REVIEW_PORT`, read on each call) from Python, never from the page: the server takes POSTs only from its own origin (`local_request`), and urllib sends no Origin. It imports none of Strafe Review's modules.
- API: `status()` (`{serving: false}`, or the server's `/api/status` and `/api/update`), `check_updates`, `set_auto`, `install_update`, `start`, `open_review`, `stop`. Every call returns fast, because the hub runs a section's calls one at a time: `start()` only spawns, and the page polls `status()` (up to 15 s, or until the version changes after an update).
- `start()` on Linux from the repo runs the same `systemd-run --user --unit=strafe-review` command as `collector/launch-hook.sh`, so `systemctl --user stop strafe-review` and the hook's `is-active` check stay true. If `systemd-run` is missing or fails, it falls back to a detached process. Windows from source: a detached `viewer/server.py`. Frozen (3.7): `[exe, "--collect"]` (install, then serve).
- `open_review()` opens the page with `webbrowser` from Python, so the review stays in the browser and not in the hub window.
- The page (`strafe-review/hub/`) shows Running or Not running, Open review, Stop, a short setup summary (game, recorder, autoexec block, collector, attempts saved, last error) and Updates (version, check, Update and auto mode only when `canInstall`, "git pull" text otherwise). The full setup check stays on the review page.
- One copy of the colour tokens: `movekit/web/tokens.css`. `hub.css` imports it. The viewer's `style.css` imports `/web/tokens.css`, which `viewer/server.py` serves from `movekit/web/` (through `session.__file__`, so it works from the repo and the exe). `build.py` bundles it at `movekit/web/`. `style.css` keeps `--own` and `--replay` as aliases of `--good` and `--warn`.
- `hub.css` has `[hidden] { display: none !important; }`: a page's own `display` rule showed hidden elements (found here: the auto-update box on a repo copy).
- Checked: new `strafe-review/check_hub_section.py` against a real `server.py` on a free port with temp folders (status with nothing running, status, check, auto through `local_request`, a non-bool refused, no second start, open with `webbrowser` patched, stop, `/web/tokens.css` served, start bringing it back through the detached fallback, no bare modules left behind). All `movekit/check_*.py`, `check_gain.py`, `check_hud.py`, `check_recorder.py` (1344 attempts, 0 broken) and the viewer's `check_*.js` pass (`check_css_ssj.js` needs a demo recording, not run). The review page, compare and drill screenshots match before and after the token move pixel for pixel; the main page varies between runs only by load timing. The rebuilt exe bundles `movekit/web/tokens.css` and serves it; `smoke_test.py` on it passes all 5 steps. Window screenshots: Running (live data from the owner's server) and Not running. Stop then Open review tested by the owner 2026-11-02: works. A server older than the change returned 404 for /web/tokens.css (dark text on dark), so the README now says to restart after `git pull`.

### Phase 3.5: Source Yaw logic out of the window (2026-11-02)

- New `sourceyaw/settings_api.py`, plain data in and out: `setup_problem(game, cstrike)`, `base_options(base_choice)`, `trainer_config(saved)`, `trainer_value(cfg, form, game)`, `inputd_command()`, `trainer_status(cstrike, sound)` and `collect(...)`. `app.py` calls it for the setup banner, the base picker, the trainer group's start values, notes and saved value, and Apply's settings dict. Widgets and `GLib.markup_escape_text` stay in `app.py`; the API returns raw text, so a web page can show it as is.
- `trainer_value` takes the form in the window's units (percent for position and tone volume, spin values as floats) and does the rounding, so the GTK app and the 3.6 page convert the same way. `tickrate: None` keeps the saved tickrate (Momentum, where the map sets it).
- Siblings: with `sourceyaw/` on `sys.path` (the app, an installed copy), it imports `yawcore` and `trainer` by name, so it shares the app's modules whatever the import order (ruff sorts `settings_api` first). Without it (the hub), it loads them by path under `hub.local_import`'s names (`movekit_section_sourceyaw.*`), so a section asking `local_import` for `yawcore` gets the same module, with a bare `yawcore` in `sys.modules` only while `trainer.py` (which does `import yawcore`) loads. `trainer` loads on first use: it's Linux-only (`fcntl`), and `setup_problem`, `base_options` and `collect` don't need it.
- `install.sh` copies `settings_api.py` (its file list is explicit; without it an installed app would fail to start).
- Checked: a driver calling the old and new `Window` methods on stub widgets (setup with and without a game, Flatpak-only; base options with and without crosshair-maker and a custom image; trainer status for both games, with and without a game folder, the input service, the tone or a game sound, on and off; `trainer_value` and `collect` for both games; `yawcore.apply` of the collected settings in a sandbox HOME): the JSON and the hashes of every written file are identical before and after. New `sourceyaw/check_settings_api.py` (the hub's way through `hub.local_import`, no bare modules left; the app's way in a child process, same modules). An installed-layout copy imports. All other checks pass; ruff shows only the 3 pre-existing findings. Window screenshot as a floating test window: banner, base, trainer notes and tone controls as before, title not marked changed.

### Phase 3.6: Source Yaw section (2026-11-02)

- `sourceyaw/hub_section.py` (key `sourceyaw`, order 30, Linux only). `hub.discover()` loads every `hub_section.py` before it checks `os`, so the top of the file imports only the standard library and `movekit.hub`. `settings_api` (and through it `yawcore`, Pillow and the trainer) loads on the first call, by `local_import`. On Windows the section is left out with no problem listed.
- The page holds the form; Python loads it (`load(game)`: settings, sound lists, base options, trainer values in the window's units, notes, KROSSHAIR, launch option, previews) and saves it (`apply(game, form)`, through `settings(game, form)` = `settings_api.collect` with `EntryRow.value`'s rounding). Numbers are clamped to the GTK spin buttons' ranges (`LIMITS`), and a blank box or a bad colour is refused. The page also puts a blank box back to its last value.
- Texts the GTK window builds itself (cycle-key and offset-key warnings, launch-option and KROSSHAIR notes) are built in `hub_section.py` in the same words, not moved out of `app.py`: moving them would mean redoing the 3.5 "unchanged" proof. 3.8 deletes the `app.py` copies.
- Key capture: numpad keys by `KeyboardEvent.code` (with NumLock on, Numpad1 types "1"), then `KeyboardEvent.key` when it is a bind name (letters follow the layout, as GTK's keyval did; Shift+1 gives "!" and falls through), then `KEY_CODES[KeyboardEvent.code]`, then `MOUSE_BUTTONS`, and the wheel. A pick-from-list fallback holds every `VALID_KEYS` name (Super never reaches the page on Hyprland). The maps live in Python, so the check holds every value to `VALID_KEYS`.
- Calls that take time don't hold the section's lock: KROSSHAIR's install runs in a thread and the page polls `krosshair()`, and the tone's steps run on timers. "Choose an image…" is pywebview's file dialog (modal, so it may hold the lock).
- Yawspeeds reorder with up and down buttons; HTML drag and drop in WebKitGTK on Wayland is unreliable. The start choice moves with its row and goes to the first when its row is removed, as in the window.
- Left out: the Updates group. Source Yaw's own updater stays in the GTK window; the hub's updates come with 3.7.
- Found in the owner's click test (2026-11-02): WebKitGTK hands pages the mouse side buttons as button 0, so key capture read them as mouse1 (synthetic page events had passed). `movekit/hub.py` now catches GDK buttons 8 and 9 on the WebKit widget before WebKit does and sends the page a mousedown/mouseup with button 3 or 4 where the pointer is. Checked in a floating test window by feeding GDK button events into the view: 0 without the fix, 3 and 4 with it, the left button unchanged.
- Leaving the section with unapplied changes asks first, in an in-page dialog (a sidebar click; WebKitGTK's `confirm()` works but titles itself "JavaScript - http://127.0.0.1:…"). Switching game with unapplied changes is refused, as in the window.
- Checked: new `sourceyaw/check_hub_section.py` (discovery on Linux and Windows, loading `hub_section.py` imports neither Pillow nor any sibling, no bare modules after the trainer loads, both games' `load`, key maps, every note, previews, ranges, `new_entry`, autoexec, sounds, tone, Show in game, KROSSHAIR install, file dialog with stubs; Apply for both games writes byte-identical files to the GTK way in a temp HOME). Mutations (no speed rounding; Pillow imported at the top) make it fail. All other checks pass; ruff shows only the 3 pre-existing findings. Window screenshots as a floating test window (both games, the key dialog, an added and moved yawspeed); synthetic key events give `1` for Shift+1, `kp_end` and `kp_minus` for the numpad, refuse F13, and catch space, the wheel and mouse5. The leave dialog stays or leaves; the CS:S tickrate box shows. Apply on the real game files and real mouse side buttons are left to the owner's click test.

### Phase 3.7: hub release (started 2026-11-02; branch `hub-release` merged into main 2026-11-02)

Built and checked on Linux and in Windows CI; the `hub-v1.0.0` release, the bridge and the HUD file move are still open (see "Left" below).

- **Linux launcher.** `movekit/install-hub.sh [--uninstall]` writes `io.github.soulmanyes.MovementKit.desktop` and its icon (`movekit/icons/`), running `movekit/hub.py` from the checkout, so `git pull` updates it. `hub.run()` now always sets that app id on Linux (`--class` still overrides it for test windows).
- **One Windows exe.** New top-level `hub/` (the CI's `tool` is both folder and tag prefix, so `hub-v*` means a `hub/` folder; it has no `hub_section.py`, so discovery skips it). `hub/movement_kit.py` is the entry: no arguments open the hub, `--check-sections FILE [KEY.NAME[:JSON] ...]` writes what discovery found as JSON (the exe has no console), with the replies of the section functions named, run through the Bridge as a page would, everything else goes to `strafe_review.main()` (`%command%`, `--serve`, `--restarted`, `--collect`). `hub/build.py` builds `movement-kit(.exe)`, `--windowed`: Strafe Review's layout at the bundle root as before (collector/, viewer/, recorder/), plus each Windows section's `hub_section.py` and `hub/` folder, `strafe-review/recorder_settings.py` and `movekit/web/` as data, and what they import as hidden imports. No Source Yaw and no Pillow: that section is Linux-only.
- **`--collect`** (new in `strafe_review.py`): install the recorder, then collect and serve with no page opened. The hub's "Open review" starts the exe this way, because `--serve` doesn't install and a Windows user without the launch option would get no recorder. A double-click of the plain Strafe Review exe is unchanged.
- **Release line.** `hub/hub_release.py` (VERSION 1.0.0, `hub-v`, `hub-windows.zip`, `movement-kit.exe`, state file `hub-updates.json`). `collector/updater.py` follows it when the module is bundled, else Strafe Review's line as before; from the repo `hub/` is never on the path. `swap_exe` takes `movement-kit.exe` from the zip and puts it in under the running exe's name, so a copy installed as `strafe-review.exe` keeps that name for Steam's launch option.
- **CI.** `.github/workflows/hub-windows.yml` calls `windows-release.yml`, which got three optional inputs: `exe` (the exe's name when it isn't the tool's), `packages` (pip packages next to PyInstaller) and `licenses_of`. The last runs `.github/scripts/collect_licenses.py`, which copies the licence files of pywebview and everything it requires on the build machine into `third-party-licenses/` in the zip and prints each package with its licence, failing if one has no licence file. Smoke: `strafe-review/smoke_test.py --hub`, then the exe with no arguments must keep its window up for 15 s.
- **Smoke test `--hub`:** step 0 checks the bundled sections (strafe-review, hud, gain-converter, no problems); step 1 uses `--collect` and expects no page opened, then calls `strafe-review.status`, `hud.get` and `hud.set_line` inside the exe (sections load what they import lazily, past PyInstaller's analysis): the server is seen, the recorder found installed, the setting written into it; the second double-click is left out; the update follows the hub's line into a copy named `strafe-review`.
- Checked 2026-11-02 on a Linux build (venv with PyInstaller 6.22.3 and the system's pywebview 6.2.1, test ports 8790/8791): `smoke_test.py --hub` passes all steps, the plain Strafe Review build still passes its smoke test, `check_hub.py` (now also `check_sections`), `check_launch`, `check_steam`, `check_attempts`, `check_hud`, `check_gain` pass. `strafe-review/check_hub_section.py` (its server takes the session port 8766) passed later the same day, with the live viewer stopped for the run. No window was opened.
- `hub/WINDOWS.txt` and `hub/THIRD-PARTY-NOTICES.txt` written; on Windows a double-click now opens the hub instead of Strafe Review's console window (a change in play for Windows users).

Left:
1. Done 2026-11-02: first Windows test builds passed (hub-windows on branch pushes, strafe-review-windows by hand on the branch: the shared workflow didn't regress). The licence step caught proxy_tools 0.1.0 with no licence file in its wheel; `hub/licenses/proxy-tools-LICENSE.txt` is its upstream LICENSE.txt (BSD), and the collector falls back to such kept copies. The exe also bundles the WebView2 SDK (Core/WinForms wrappers, WebView2Loader.dll; BSD-3, LICENSE and NOTICE from the NuGet package now in `hub/licenses/` and the zip), pywebview's own WebBrowserInterop DLLs, ClrLoader.dll and Python.Runtime.dll (covered by their packages), and the VC++ runtime (covered by PYTHON-LICENSE.txt). The step-2 stderr worry didn't happen. Was: a first test build: push the branch, run Actions > hub-windows by hand. From its log, check the licence list and what's under `webview/lib` (the WebView2 SDK DLLs, whose licence is Microsoft's and not in any package metadata), and fix `THIRD-PARTY-NOTICES.txt` to match. License check before any tag. Also run `strafe-review-windows` by hand, since `windows-release.yml` changed. Only Windows can show: a `--windowed` exe may have no stderr even when piped, so step 2's `"in use" in r.stderr` may fail there (then read `strafe-review.log` instead).
2. The bridge: the last `strafe-review-v*` release ships the hub exe as `strafe-review.exe` in `strafe-review-windows.zip`, so installed 1.5.0 copies update into the hub. Then `strafe-review-windows.yml` builds with `hub/build.py` and renames the exe. Waits until the first migration (old repo to kit) is confirmed on a real install, as in Phase 1.
3. Done in 3.9: after the bridge, move `settings.json` out of Strafe Review's data folder (`hud/settings.py` reads the old file once as a fallback) and take the jump-1 toggle out of the review page's sidebar (3.3).
4. Done 2026-11-02: `strafe-review/check_hub_section.py` passed on the branch. At the merge the temporary `branches: ["hub-release"]` push trigger came out of `hub-windows.yml`; test builds now go through Actions > hub-windows > Run workflow.
5. The `hub-v1.0.0` release (ask the owner first). Nobody has tested the hub exe by hand on Windows yet.

### Phase 3.7b: modules (planned and OK'd 2026-11-02; 3.7b.1 and 3.7b.2 done on branch `modules`)

The owner asked for this on 2026-11-02, before `hub-v1.0.0`: each tool updates on its own, so someone who doesn't use a tool never downloads it; each tool can be uninstalled on its own; and each has its own auto-update switch. `hub-v1.0.0` stays untagged until 3.7b ships. This replaces 3.7's "one Windows exe with everything inside": the exe stays one program, but the tools become modules it downloads.

**Owner's answers (2026-11-02):**
- Both Windows and Linux, with the same module cards in the hub.
- Modules: Strafe Review, Gain Converter, Source Yaw (Linux only). The HUD is part of the core. It shows only when a module that draws in game is installed.
- Uninstall always removes the module's game files, autoexec block and launch hooks. Saved data (attempts, settings) goes only if the uninstall dialog's "Also delete saved data" box is ticked, which is off by default.
- A fresh install starts with no modules; each is installed from its card.
- Auto-update starts off for each module and for the core. The card must show plainly that it's off, with a one-click way to turn it on: no popup.
- Extras: release notes for an available update, roll back to the previous version, and one "Update all" button.

**Shape.**
- **Core:** the hub window, `movekit`, `hud/` and the launch dispatcher. Line `hub-v*`. On Windows it's `movement-kit.exe` (PyInstaller); on Linux it's the hub from a source archive. The core never imports tool code, so it runs with no modules installed.
- **Module:** a tool folder with a `module.json`: `key`, `title`, `os`, `tag_prefix`, `version`, `needs_core` (the lowest core version it runs on), `needs` (other modules), `data` (the folders "Also delete saved data" removes), and its hooks file. The hooks file is `module_hooks.py`, with `install(ctx)`, `uninstall(ctx, delete_data)` and `launch(ctx, argv)` if the module has a launch step. Each module ships on its existing tag line as `<tool>-module.zip`, the tool folder only.
- **`movekit/modules.py`, one manager for every module.** It does no per-tool work: everything tool-specific is in `module.json` and the hooks.
  - Its state file is `modules.json` in the kit's data folder (`%LOCALAPPDATA%\movekit`, `~/.local/share/movekit`, where `movekit/launch.py` already keeps `hooks/`). Per module it keeps installed version, `auto` (default false), previous version and the `failed` mark.
  - Modules sit in `modules/<key>/current`, with `modules/<key>/previous` kept for roll back.
  - Calls: `list`, `check` (one GitHub release list for every line, at most every 6 h), `notes(key)` (the release body), `install`, `update`, `update_all`, `rollback`, `uninstall(key, delete_data)` and `set_auto`.
  - It reuses `movekit/updater.py`: `parse_version`, the download code, the `failed` mark, and `in_git_checkout`.
  - An update that needs a newer core than the one running waits and says so on the card. It never installs halfway.
  - Before an update, roll back or uninstall it stops what the module runs (Strafe Review's server), then swaps the folder and starts it again.
  - `needs` blocks uninstalling a module another installed module needs, and the card names the dependent module.
- **Git checkout (the owner's copy):** modules come from the checkout and the cards say "updated by git pull", as Strafe Review's section does now. Uninstall still runs the hooks, so game files and launch hooks come out, and hides the section; it never deletes code from the checkout.
- **Discovery:** `hub.discover()` takes the installed module folders (or the checkout's tool folders) as roots, so sections are only those of installed modules. Section loading by path stays as it is.

**Hub page.** A "Modules" page sits at the top of the sidebar, part of the core, not a section. The hub opens on it while no module is installed. Every module, and the core, gets a card:
- Name, installed version, and Install, or Update when one is available. Update has a "What's new" fold with the release notes.
- Roll back, shown only when a previous version is kept.
- Uninstall, with the "Also delete saved data" box.
- The auto-update switch. While it's off the card shows an amber "Auto-update off" strip with a **Turn on** button, so it stands out with no popup.

"Update all" sits at the top, shown when at least one update is waiting. The cards follow `ui-visibility`.

**Launch option (must never break the game).** `%command%` goes to the core's dispatcher: `movement-kit.exe %command%` on Windows, `movekit-run %command%` on Linux. It calls each installed module's `launch` hook. A hook that is missing, raises or is mid-update is skipped and logged. The game always starts with its own arguments, even with no modules installed. `movekit-run` already does this on Linux (`movekit/launch.py`); the Windows exe gets the same rule.

**Windows core and downloaded code.** A frozen exe can only import what PyInstaller bundled, and modules arrive later.
- The core bundles the whole standard library except `tkinter`, `test`, `idlelib` and `ensurepip`, plus `movekit`, `hud` and pywebview.
- A check (`movekit/check_modules.py`) reads every module's imports (AST) and fails on anything outside stdlib, `movekit`, `hud`, `webview` and the module's own files. Today all three tools pass: stdlib plus `movekit`.
- The Windows smoke test starts the core with an empty modules folder. It installs each `<tool>-module.zip` from a local fake GitHub, then runs the sections and the launch from the downloaded folder, not from the bundle.

**Linux core.**
- `movekit/install-hub.sh` gets a copy mode for other users: core files into `~/.local/share/movekit/kit` (the kit root, so modules sit next to them), with `movekit-run` linked from there.
- From a git checkout it keeps running in place (the owner's case).
- Source Yaw's module hooks wrap what exists: `install_source` and `sourceyaw/install.sh` (it still installs to `~/.local/share/sourceyaw`), plus a non-interactive `--uninstall` that takes a keep-or-delete-data flag. Its GTK window and the manager share one auto-update state.

**Migration.**
- **Windows:** the bridge release (the last `strafe-review-v*`) ships the core exe as `strafe-review.exe`. On first start the core sees Strafe Review's old data folder. It installs the Strafe Review module (download) and carries over the old `auto` value, so the friend's copy keeps working and keeps its Steam launch option. The rule from 3.7 stands: this waits until the first migration is confirmed.
- **Linux:** the manager adopts an existing `~/.local/share/sourceyaw` as an installed Source Yaw module.
- **HUD:** because the HUD is part of the core, its `settings.json` moves to the kit's data folder here (was 3.7 Left #3), reading the old file once. It writes the recorder through the Strafe Review module's hooks; with no Strafe Review installed, the HUD section says the line needs Strafe Review.

**Steps** (checks after each: the existing ones plus the new ones named):
1. **3.7b.1 Manager.** `module.json` for the three tools, `module_hooks.py` that wrap what exists (`install.py`, Source Yaw's `install.sh`), and `movekit/modules.py`. New checks: `movekit/check_modules.py` (manifests, the import rule, install, update, roll back and uninstall against a fake GitHub in a temp data folder, the needs block, a core-too-old wait) and the launch pass-through with no modules or a broken one.
   Done 2026-11-02 on branch `modules`. Found while building it:
   - **One layout everywhere.** Modules sit in a folder named after their key next to `movekit`, as in the repo, so each tool keeps finding `movekit` the way it does now (`steam.py`'s "two folders up"). The kit root is the checkout itself in a git checkout, `<data>/kit` in the Windows exe, and the core's own folder in a Linux copy (3.7b.4). Previous versions sit in `<data>/previous/<key>`, downloads in `<data>/staging`.
   - **Versions aren't copied into module.json.** `version_from` names the file with the tool's `VERSION = "x.y.z"` line. Gain Converter got one (`1.1.0`, its last tag).
   - **`standalone`** (optional) lists files that never run in the core, such as Gain Converter's tkinter window, and the import rule skips them. The rule also skips imports inside `try/except ImportError`.
   - Module lines are found by their `<key>-module.zip` asset, so tool releases from before 3.7b aren't offered as modules.
   - Hooks run module scripts in a fresh process (`Context.script`): python from the repo, `movement-kit.exe --run-script FILE` in the exe (added to `hub/movement_kit.py`). In-process, `install.py` would leave bare `steam`/`install` modules behind, which `check_hub_section.py` forbids.
   - Strafe Review's `install` hook fails when Momentum Mod isn't found, so the module doesn't install without its game. Source Yaw's `uninstall` runs `yawcore.py --remove-from-game` first, since `install.sh --uninstall` only asks about that in a terminal. Its settings (`~/.config/sourceyaw`) go only with "Also delete saved data". Strafe Review's data entry leaves `settings.json` alone (the HUD's, part of the core).
   - **Folders.** The kit keeps its state in `paths.data_dir("movekit")`, the folder `movekit/launch.py`'s `hooks/` already uses: one name for the kit. `data:`/`config:` entries must start with the module's own key, so a typo can't make "Also delete saved data" reach another program's folder.
   - **Swaps put everything back.** Stop, the folder swap and the install hook run as one step. If any part fails (on Windows a file still in use), every folder returns to where it was, the old version's install hook runs again, the server is started again and the release is marked failed. Strafe Review's `stop` hook waits up to 10 s for its server to end, because `api/stop` only asks.
   - `strafe-review/install.py --uninstall` now finishes when Momentum Mod is gone or moved: it still removes the launch hook and the link. Before, it stopped with "Momentum Mod not found", so the module could never be uninstalled. `check_modules.py` runs Strafe Review's real hooks against a fake Momentum, with `HOME`, the data folders and its server port in a temp folder.
   - The launch pass-through check moves to 3.7b.3, with the Windows dispatcher it checks. Linux already passes through (`movekit-run`, `check_launch.py`).
   - For 3.7b.3: `strafe-review/install.py` takes `ROOT` from `sys._MEIPASS` in the exe. A module loaded from disk needs it from `__file__` (which PyInstaller also sets inside the bundle, so the old exe keeps working). The same applies to every `_MEIPASS` use in module code.
   - For 3.7b.2: Strafe Review's own updater (`collector/updater.py`, including the hub line it follows in the exe) gives way to the module card. The core line moves to the manager's "core" entry.
2. **3.7b.2 Hub page.** The Modules page and cards, `discover()` over installed modules, and Strafe Review's section losing its own update UI to its card. Then a screenshot check, and an owner click test.
   Done 2026-11-02 on branch `modules`; the owner click-tested the demo window (notes, auto switch, update, roll back, install, uninstall):
   - The home page is the Modules page (`movekit/web/home.html` + `modules.js`), with a "Modules" entry at the top of the sidebar. Pages reach the manager through `Bridge.modules(name, args)`. Every reply carries the cards as they are afterwards, also after an error, so the page always redraws from Python's state. One call at a time; a second one while busy gets "<what it's doing>; try again". The auto update runs in a thread once the window shows, and the page polls while it works.
   - Sections follow what is installed: `hub.kit_sections()` = the core's folders (no `module.json`) plus `Manager.roots()`. An install, update, roll back or uninstall rediscovers them, and the page server reads the same dict. New optional `SECTION["show_with"]`: the HUD shows only with `strafe-review` installed.
   - Each module release also carries `<key>-module.json`, a copy of its manifest. `check()` reads it, so a card can name a module that isn't installed and see that a release needs a newer core before downloading. CI must upload it in 3.7b.3. A "waiting for core" mark counts only for the release that set it.
   - Strafe Review's section lost its Updates card and its `check_updates`, `set_auto` and `install_update` calls; `status()` no longer reads `/api/update`. The review page's own updater and the server's update API stay until 3.7b.3.
   - A test window with fake modules from a fake GitHub (nothing real touched) is a scratch script: Manager on a temp kit and data folder, `hub.run(KIT, app_class="movekit-hub-test", manager=mgr)`. `MOVEKIT_MODULES_API` points a normal hub at a fake GitHub.
3. **3.7b.3 Windows core.** The `hub/build.py` split (core only, whole stdlib), the core dispatcher in `hub/movement_kit.py`, and `<tool>-module.zip` CI from one script reading `module.json`. Also the smoke test described above.
   Built 2026-11-02 on branch `modules`. Windows CI green the same day (hub-windows and strafe-review-windows on the branch: all 8 smoke steps, window stays up; exe 14.7 MB). Licence recheck from the build: same packages as 3.7; the whole stdlib adds sqlite3.dll (public domain) and expat in pyexpat (MIT, now `hub/licenses/expat-LICENSE.txt` and in the notices); libffi is in PYTHON-LICENSE.txt.
   - **Core entry** (`hub/movement_kit.py`): no arguments open the hub; a game command goes to `movekit/dispatch.py` (each installed module's `launch` hook, logged and skipped on any failure, then the game with PyInstaller's library path restored); `--run-script FILE` runs module scripts inside the exe; `--modules OUT CMD [KEY]` drives the manager with no window; `--check-sections` uses the installed modules. Output also goes to `movement-kit.log` (`movekit/logfile.py`, shared with Strafe Review).
   - **Bridge pieces in the core:** `migrate()` installs the Strafe Review module once when Strafe Review's old data folder exists, keeping its auto switch (offline: tried again next start, the game runs anyway). The old exe's `--serve`/`--restarted`/`--collect` go to the module's `strafe_review.py`, so an old copy that updates itself into the core gets its server back.
   - **Strafe Review as a module:** `ROOT` comes from the file's own folder unless the file sits inside a one-file bundle (the old exe); `me()` and the section's start run `strafe_review.py` through `--run-script` in the core; its launch step is `prepare_launch()`, called by its `launch` hook. Its own updater is gone (`collector/updater.py`, the server's `/api/update*` and update loop, the review page's banner); `VERSION` lives in `collector/collector.py`. `strafe-review/build.py` (the standalone exe) is gone.
   - **HUD:** finds the recorder through `modules.default_kit_root()` (which also takes `MOVEKIT_KIT_ROOT`, for tests).
   - **Build:** `hub/build.py [--name strafe-review]` bundles the core only, with every public stdlib module as a hidden import except `EXCLUDE` (tkinter, tests, bz2/lzma/_decimal, which would each ship a native library); `movekit/check_modules.py` forbids modules those. Linux build: 153 MB (GTK and WebKit come along).
   - **CI:** `module-release.yml` attaches `<tool>-module.zip` and `<tool>-module.json` (`.github/scripts/module_zip.py`) on `strafe-review-v*`, `gain-converter-v*` and `sourceyaw-v*` tags. `strafe-review-windows.yml` now builds the bridge: the core exe as `strafe-review.exe`, in `hub/` (new `folder` input in `windows-release.yml`). `.github/scripts/version.py` reads a tool's VERSION for the tag checks. The module zip keeps executable bits; the manager restores them on install.
   - **Smoke test** moved to `hub/smoke_test.py` (`EXE` or `--repo`): modules installed from a fake GitHub and run from the download folder, Open review, a second server, the launch option, Stop, uninstall (game still runs with no modules), the bridge's first launch, and (built exe) the core update. `hub/check_core.py` checks the entry point from the repo.
4. **3.7b.4 Linux core.** The copy mode in `install-hub.sh`, the Source Yaw adoption and the shared auto state.
   Built 2026-11-02 on branch `modules`:
   - **Copy mode** (`movekit/install-hub.sh`): outside a git checkout (a release download, `curl | sh`, the core's own update) or with `--copy`, it copies `movekit/` and `hud/` (no `check_*`, no caches) and `LICENSE` to `~/.local/share/movekit/kit` (`modules.core_kit()`, the folder the 3.7b.1 notes chose, not the `movement-kit/core` named above). The launcher runs the copy's `hub.py` and `~/.local/bin/movekit-run` links to the copy. The copy is staged next to the old one and swapped in folder by folder, so `movekit-run` is never half copied. Other folders there are modules and stay. From a checkout it still runs in place. `--uninstall` removes the launcher; the core goes too only when no module is left, else it says to uninstall them in the hub first.
   - **`movekit-run` stays on the core.** `launch.py register` links it to the core copy whenever there is one, and `unregister` keeps it there after the last tool, so the launch option starts the game with no modules. Without a core copy nothing changes.
   - **Core update on Linux:** `Manager.linux_core_installer` runs the `hub-v*` release's source archive's `install-hub.sh` (copy mode, since the archive isn't a checkout). The hub gives it to a copy's manager only, so a checkout's core card still says git pull.
   - **Adoption:** `Manager.adopt(key, marker, auto_files, flag)`, once per flag: when the old install exists and the module isn't installed, it downloads the module and takes the auto switch from the old updater's state. A failure (offline, no module release yet) leaves the flag unset, so the next start tries again; never in a checkout. The hub runs it for Source Yaw (`~/.local/share/sourceyaw/yawcore.py`, `~/.config/sourceyaw/updates.json`) at window start, before the auto update, never in the launch path. The Windows bridge's `migrate()` now goes through the same call.
   - **Shared auto state:** a Manager takes every auto switch from `modules.json` on each save and each `cards()`, except the ones it set itself since its last save, so a switch flipped in another program survives the hub's next save. `python3 -m movekit.modules CMD [KEY]` is the manager with no window (the exe's `--modules` uses the same `cli()`). Source Yaw's GTK updater, once `kit/sourceyaw/module.json` exists, reads and writes its switch and installs its update through that command in the core copy, never through its own `install_source` or its own movekit copy, so the module folder and `~/.local/share/sourceyaw` stay one version. Its check takes the newest release from the manager's card (the manager asks GitHub then), so a tag without a module zip isn't offered and a stale manager cache can't answer "up to date" to an update the window offered; when the hub already put the version in, the window says restart. Its switch's subtitle says it is the Modules page's. The window's calls to the manager time out after 15 s (a check after 60 s, an update after 15 min).
   - **One change at a time:** install, update, roll back and uninstall hold `<data>/modules.lock` (flock, Linux) and read the state file afresh, so the hub and the GTK window never swap a module's folders at once.
   - Checked: new `movekit/check_linux_core.py` (temp HOME and data folders, fake GitHub: copy contents, launcher and link, a fresh copy with no modules or sections, a module folder surviving a re-copy, `movekit-run` with no modules and through register/unregister from another copy, uninstall kept then done, the core update from a source archive, adoption once/offline/no release/checkout, switches from another program, the GTK updater managed and not, and with the real manager command: a release after the hub's last look, the hub updating while the window runs, a tag with no module zip). Mutations (no core link on unregister, no merge in `cards()` or `_save`, the GTK update installing itself, the window's restart test, `cli()` ignoring the test API, a tool folder in the copy) make it fail. All other `check_*.py` pass, `strafe-review/check_hub_section.py` and `hub/smoke_test.py --repo` included (run with the live server stopped, then started again). Windows CI green on `ca4e8b4` (hub-windows and strafe-review-windows, 2026-11-02).
5. **3.7b.5 Docs and release.** README, WINDOWS.txt and the per-tool READMEs. Then `hub-v1.0.0` and the first `<tool>-module.zip` releases, after the owner's OK. The bridge follows later, as above.
   Docs done 2026-11-02 on branch `modules`; the release waits for the owner's OK:
   - The root README has an Install section (Windows `hub-windows.zip`, Linux `curl … install-hub.sh | sh`, then each tool from its card), the card buttons, the launch option for both systems (the `[launch]` filter in `settings.toml` is Linux only; `movekit/dispatch.py` doesn't read it) and the module releases.
   - `hub/WINDOWS.txt` (in both the hub zip and the bridge zip) starts from an empty Modules page, says what the bridge's first start does, and names both logs: the core's `%LOCALAPPDATA%\movekit\movement-kit.log` and the server's `%LOCALAPPDATA%\strafe-review\strafe-review.log`. Its checklist adds install, uninstall, update and roll back.
   - Tool READMEs install through the card, with the clone way kept. Strafe Review's lost its standalone exe and banner text. Gain Converter keeps its own tkinter exe as the standalone way. Source Yaw's says the card can't ask for a password, so missing packages stop it, and a standalone install is adopted at the hub's next start.
   - Removed `strafe-review/WINDOWS.txt` and `THIRD-PARTY-NOTICES.txt`: they described the standalone exe, which is gone; the bridge zip takes `hub/`'s. `hub/THIRD-PARTY-NOTICES.txt` names both exe names.
   - Module zips checked: each keeps every licence file git tracks for its tool (Source Yaw's overlay GPL text and Vulkan header licences included); only the exe-only files are left out.
   Released 2026-11-02 (`modules` merged into `main`): `gain-converter-v1.2.0`, `sourceyaw-v1.7.0`, then `hub-v1.0.0` and `strafe-review-v1.6.0` (module zip and the bridge). CI green on all; notes written by hand. The owner chose to ship the bridge without the Windows hand test or a confirmed first migration ("if its broken then i will hear about it"). Checked from outside: the `curl | sh` line in a temp HOME installs the core from `hub-v1.0.0`, and its manager sees all four releases; a temp kit installed Gain Converter from the real zip.

Risks: Windows Defender may flag a downloaded zip; it has the same signing status as the exe now. The bridge is the one moment both Strafe Review lines must work, so it gets its own smoke step (old exe, update to bridge, module installed, launch works).

### Phase 3.8: retire the old windows (2026-11-02; branch `retire-windows` merged into main and released the same day)

The owner said go ahead on 2026-11-02, the same day the hub shipped, without the "used it a while" wait.

- **Source Yaw: thin launcher.** `sourceyaw/app.py` is now a stdlib launcher. It runs the hub with `--section sourceyaw`, finding `hub.py` from the hub's app menu entry (`io.github.soulmanyes.MovementKit.desktop`, so a git checkout works) or else the installed core (`~/.local/share/movekit/kit/movekit/hub.py`). With no hub, it prints the `install-hub.sh` line, and notify-sends it when there's no terminal. Keeping the name `app.py` keeps three old paths working: the "Source Yaw" app menu entry, `~/.local/bin/sourceyaw`, and an old window's `restart()` after an update (`os.execv` on its own path, which is now the launcher).
- `sourceyaw/updater.py` is gone, along with the GTK window's update group. The Modules page updates Source Yaw. `install.sh` removes `updater.py` and `icons/` from an installed copy, and needs only Python and Pillow (no GTK 4, libadwaita or PyGObject; the hub's own installer brings what its window needs). The drag-handle icon is gone; the app icon stays for the menu entry. The `app.py` copies of the notes are gone with the window; `hub_section.py` holds the only ones.
- `check_linux_core.py` dropped `check_gtk_updater`. `check_settings_api.py` no longer looks for a bare `updater`. `check_hub_section.py` still compares Apply against the window's collect-and-round path, so the files Apply writes can't change.
- **Gain Converter: deleted.** `gain_converter.py` (the tkinter window and the Python curve), `gain-converter-windows.yml`, its `THIRD-PARTY-NOTICES.txt` and its Tcl/Tk licences are gone. VERSION moved to `gain-converter/hub_section.py` (`module.json` `version_from`), and the `standalone` key is gone. `check_gain.py` now checks `gain.js` against K, the measured points and 41 values each way, taken from the Python copy before it was deleted; a changed K fails it. The old 1.2.0 exe has no updater, so installed copies just stay as they are.
- Also fixed: 3.7b.5 had left Gain Converter's README Install section empty. It now installs through the Modules page.
- Versions: Source Yaw 1.8.0, Gain Converter 1.3.0. No Strafe Review or hub change, so no bridge release is needed.
- Checked: every `check_*.py` and `check_gain.py` passes. A temp HOME with a `sourceyaw-v1.7.0` install, updated by the new `install.sh`: `updater.py` and `icons/` gone, `app.py` is the launcher, the menu entry and `~/.local/bin/sourceyaw` point at it, and `--uninstall` cleans up. The launcher finds both a checkout hub (from the menu entry, with a space in the path) and an installed core. Both module zips built locally: `read_manifest` and `module_version` give 1.8.0 and 1.3.0, and `hub.discover` finds both sections with no problems. Screenshots for both READMEs were retaken from the hub, as floating test windows with a temp HOME and a fake CS:S install.
- Released 2026-11-02: `sourceyaw-v1.8.0` and `gain-converter-v1.3.0` (module zips only, CI green, notes written by hand); the module manager sees both. A Windows test build of the hub on the branch passed first. The live Source Yaw was reinstalled from main, so its menu entry opens the hub.
- Left: the jump-1 toggle in the review page's sidebar (PLAN 3.3: goes once the hub ships on Windows), which needs a Strafe Review release with the bridge. Done in 3.9.

### Phase 3.9: the HUD settings move, the review page's toggle goes (2026-11-02; branch `hud-move` merged into main and released the same day)

The owner picked both on 2026-11-02, before the Windows hand test. The hub shipped on Windows as `hub-v1.0.0`, the condition 3.3 named.

- **HUD settings file.** `hud/settings.py` keeps the values in `hud.json` in the kit's data folder (`paths.data_dir("movekit")`, next to `modules.json`). While `hud.json` doesn't exist, it reads Strafe Review's old `settings.json`, unknown keys included; the first save writes `hud.json`, and from then on the old file is ignored. The old file is never changed or deleted, because a strafe-review v1.5.0 exe that hasn't updated yet still reads it. Saving no longer creates Strafe Review's data folder. That matters on Windows, where `migrate()` installs the Strafe Review module when that folder exists.
- **Review page.** `static/ingame.js`, the sidebar foot (`#ingame`, `.side-foot`, `.upd-auto`) and `GET/POST /api/settings` are gone. The hub's HUD section is the only place to set the line. `server.py` no longer imports `install` or `hud.settings`. `install.apply_settings` stays: the install and the HUD section use it.
- **Versions.** Core 1.1.0 (`hub/hub_release.py`, `modules.CORE_VERSION`), Strafe Review 1.7.0. `needs_core` stays 1.0.0. Both mixes work: an old Strafe Review server on the new core reads `hud.settings` from the core, and the new module on the old core has nothing that needs it. The Strafe Review tag must carry the bridge zip (`strafe-review-windows.yml`).
- `check_modules.py` and `check_linux_core.py` take the core version from `modules.CORE_VERSION` instead of a fixed 1.0.0, so a core bump doesn't break them.
- Checked: `check_hud.py` covers the old file only (and broken), the first save carrying the old keys while the old file stays, the old file ignored once `hud.json` exists, and a save not creating Strafe Review's folder. Mutations (always the old file, never the old file, the old file first, saving to the old file) make it fail. Every other `check_*.py` and the viewer's JS checks pass, and so does `hub/smoke_test.py --repo` (run with the live server stopped). The README screenshot was retaken from the live server through a WebKit2GTK snapshot.
- Live: the server was restarted on the new code through the section's `start()`. It's a transient `systemd-run` unit, so `systemctl --user start` can't bring it back. It reads `inGameLine: true` from the old file until the next save.
- Released 2026-11-02: `hub-v1.1.0` (hub-windows.zip) and `strafe-review-v1.7.0` (module zip and json, and the bridge zip). Windows test builds of both passed on the branch first, CI was green on the tags, notes were written by hand, and the module manager sees both.

### Phase 4.1: the kit (2026-11-03, branch `panorama-kit`)

- `movekit/panorama.py`: `install(game, folder, tool, patches)`, `uninstall(game, folder)`, `sync(game)` and `status(game)`, as in "Phase 4". Two patch forms: `before` + `line` (a line put in front of the one line starting with `before`, one indent step deeper, the file's line endings kept; the recorder's `timer_with_recorder` logic) and `find` + `replace` (exactly once).
- A tool's patches to one file fit all or none: when one doesn't fit, its earlier ones to that file are taken out too, and the other tools' stay.
- A tool name listed by two manifests, or a manifest that doesn't parse, is left out with a warning. `install` refuses a bad patch (not under `panorama/`, `..`, a missing field, find equal to replace, a line with a newline) before writing anything.
- The new kit folder is built in the game folder (`.movekit-new-*`), not in `custom/`: the game mounts every folder in `custom/`, and a name starting with `.` sorts before `0-movekit`, so a leftover would win. Leftovers from a crash are removed on the next sync. When the swap fails halfway (a file locked on Windows), the last good folder is put back before the error is raised. The lock is `panorama.lock` in the kit's data folder: `fcntl` on Linux, `msvcrt.locking` on Windows, because there the hub window and the game's launch can sync at the same time. The Windows lock first ran in 4.2's Windows CI build (smoke test), and passed.
- `sync` writes nothing when the folder already holds the same files. When only `present` patches are left (the base already has them), no copy is needed and no file is written.
- `movekit/check_panorama.py` covers the list in "Phase 4" step 1, plus CRLF and tab indents, a find/replace patch, the all-or-none rule, bad and duplicate manifests, and `status` writing nothing. Also a leftover temp folder removed, and a swap failing halfway (`Path.rename` made to fail) keeping the last good folder, with both temp folders in the game folder. Mutations caught: one tool's include dropped, the "already present" rule ignored, the kit folder allowed as the base, a failed tool's earlier patch kept, no rollback, either temp folder in `custom/`, no leftover cleanup. Every other core check passes.
- Nothing uses it yet, so it ships with 4.2 (core 1.2.0) instead of a release of its own. The hub build bundles every `movekit/*.py` as a hidden import (`hub/build.py` `kit_modules`), so the frozen core carries it.

### Phase 4.2: Strafe Review on the kit (2026-11-03, released 2026-11-03)

- `strafe-review/install.py` lists its include as `PATCHES` (`before: </scripts>`) and calls `panorama.install` after copying the recorder, so the kit's `timer.xml` never includes a script that isn't there yet. `base_timer` and `timer_with_recorder` are gone. The old `0-strafe-review` folder is deleted on install as before, so a stale `timer.xml` from an older version goes with it.
- Uninstall calls `panorama.uninstall` first, then deletes the recorder. When that sync fails (OSError), the recorder folder stays and a warning is printed. The autoexec block and the launch hook are still removed.
- A skipped patch no longer fails the install (the old code raised on a `timer.xml` without `</scripts>`). Instead it prints "the recorder won't load" to stderr, and the HUD card shows it. The review page's "Recorder installed" (`viewer/server.py`) still only checks the `.ts` file.
- Before deleting the old code: on the real game's `timer.xml` the kit's patch gives the same text as `timer_with_recorder`, and on the live `0-strafe-review/timer.xml` it reports `present`.
- HUD section: `panorama_status` (`game: false` when Momentum isn't found), and a "Patched game files" card listing each patch as applied, already in the file, or left out with the reason, plus the kit's warnings. Screenshot taken on a fake game with one applied and one skipped patch.
- Versions: `CORE_VERSION` and `hub_release.VERSION` 1.2.0, Strafe Review 1.8.0 with `needs_core` 1.2.0.
- Checks: `check_modules` (include once in `0-movekit`, none in `0-strafe-review`, `0-movekit` gone after uninstall), `hub/smoke_test.py --repo` (panoDev's `timer.xml` with one include, now in `0-movekit`; `0-movekit` gone after uninstall), `check_hud` (`panorama_status` with no patches, applied, skipped, no game). Mutations caught: no `panorama.install` call, no `panorama.uninstall` call, `panorama_status` returning nothing. Every `check_*.py`, `check_recorder.py` (1344 attempts, 0 broken) and the viewer's `check_*.js` pass. `check_css_ssj.js` needs a demo recording, so it wasn't run.
- Released 2026-11-03: the Windows CI builds on `panorama-kit` passed first (the smoke test's install is the first run of the `msvcrt` lock), then main was fast-forwarded and the owner pushed `hub-v1.2.0` and `strafe-review-v1.8.0`. Both releases carry their Windows zip, Strafe Review's also the module zip and json (`needs_core` 1.2.0).
- The owner's live game runs this working tree (`strafe-review-run` links into it). Its next start writes `custom/0-movekit` and removes the old `timer.xml` from `0-strafe-review`.

### Phase 4.3: Strafe Trainer Height as a module (2026-11-03, released 2026-11-03)

- `trainer-height/` as in "4.3 details": `install.py` (VERSION 1.0.0), `module_hooks.py`, `launch-hook.sh`, the scss. Only the scss came from `~/claude/mmod-trainer-height`, which stays as it is.
- On copies of the real game files the kit's `strafe-trainer.xml` matches the old mod's byte for byte; the `.ts` differs only by the old mod's comment after `resizeY: true,`.
- HUD: shows with either module; the jump-1 card hides without Strafe Review (screenshot on a fake game with only Trainer Height: the patched files card lists both patches as applied). Core 1.2.1 for that, and the module's `needs_core`.
- Checks: `trainer-height/check_trainer_height.py` (old folder removed, both files patched once, another tool's patches to the same files kept, a changed `.ts` left out and reported, a failed sync keeps the scss, launch hook registered and removed, the module hooks; mutations caught: no old-folder removal, old folder removed after the sync, the scss removed when the sync fails, no `panorama.install`, no hook unregister). `check_hud` (`strafeReview` false once Strafe Review is uninstalled, `show_with`), `check_modules` (four modules, three on Windows), every other `check_*.py` and `hub/smoke_test.py --repo` pass.
- Released 2026-11-03: test runs of `hub-windows` and `module-release` (`tool=trainer-height`, no `check_*` in the zip) passed on the branch, main was fast-forwarded, and the owner pushed `hub-v1.2.1` and `trainer-height-v1.0.0`. A core copy made like `install-hub.sh`'s (no `.git`) in a sandbox installed the module from the real release: both files patched once, the hook registered in the sandbox. The owner said a git checkout isn't a way users run the kit, so its quirk below stays as a note. The live game still has the hand-installed `custom/strafe-trainer-height`. In the owner's checkout the module counts as installed without its install hook having run, so use Uninstall and then Install on its card to switch.

### Notes for later steps

- Releases: tag `<tool>-v<VERSION>` (a plain `v1.5.0` starts no CI and the updaters ignore it). The `release-repo` skill has a Movement Kit section for this since 2026-11-02.
- Pushing the renamed old tags triggers no CI: none of their commits has a workflow at the repo root (checked 2026-11-02, all 21 tags). They also make no releases, so the updaters don't see them.
- `sourceyaw/install.sh`'s `curl | sh` branch has the same root-path problem (`sh "$tmp/install.sh"`), and on the monorepo `releases/latest` gives whichever tool released last. Fix in the bridge step: pick the newest `sourceyaw-v*` tag and run `sourceyaw/install.sh`.
- `failed()` and Source Yaw's `installed()` compare tag strings. A `failed` or `installed` mark from an old unprefixed tag (`v1.5.0`) doesn't match the same version's new tag (`strafe-review-v1.5.0`), so auto mode would retry it once. No such release exists (both tools are on their newest old tag), so it stays as is.
- Until a tool has its first `<tool>-v*` release, a copy running the new updater gets "No <tool>-v* release on GitHub yet": Source Yaw stays quiet, Strafe Review's page shows it as the check error. Only dev copies run that code before then.
- Fixed 2026-11-02 (see "Markers and candidate fixes"), found in Phase 1.2: Strafe Review's install crashes (UnicodeEncodeError) on an autoexec.cfg with a non-UTF-8 byte, because it reads with `surrogateescape` but writes strict UTF-8. `write_atomic` leaves files it writes at mode 0600 (`mkstemp`). Source Yaw turns a CRLF autoexec.cfg into LF and replaces non-UTF-8 bytes when it adds or removes its line.
- Fixed 2026-11-02, found in Phase 1.4: `read_binds` matches the raw line, so a bind with a trailing `// comment` gets a command ending in `"` and its role is missed (`bind o "+moveleft" // x`). `key_conflicts` cuts at the first `//` even inside quotes, so `bind "h" "say http://x"` reports `say http:`.
- Hub (3.1): colour tokens were copied between `hub.css` and the viewer's `style.css`. Done in 3.4: one copy in `movekit/web/tokens.css`.
- Hub (3.1): hub pages come from their own localhost port. The session on 8766 already sends `Access-Control-Allow-Origin` for localhost origins, so SSE from a section page works as is.
- Hub (3.1): `local_import` loads one file by path. A helper that imports a sibling with a plain `import x` still fails, so 3.5's `settings_api.py` must load its siblings the same way (or through `movekit`).
- HUD (3.3, done in 3.9): moving `settings.json` out of Strafe Review's data folder (to a kit or hud folder) waits for 3.7, when installed exes become the hub. Then `hud/settings.py` reads the old file once as a fallback.
- Source Yaw (3.5): `settings_api.trainer_config` merges the saved `tickrate` per game over the defaults, as the window always did; `trainer.settings()` (the in-game trainer) doesn't. Left as is, since changing it would change the trainer.
- Source Yaw (3.8, done): the `app.py` copies of the notes and Source Yaw's own updater went with the GTK window.
- Source Yaw section (3.6): load the API with `local_import(__file__, "settings_api")`. It needs Pillow and the trainer's Linux modules, so keep the section Linux-only.
- Hub exe (3.7): sections are loaded by path (`hub_section.py`, and the HUD section's `strafe-review/recorder_settings.py`), so PyInstaller won't follow them. Bundle them as data, or the HUD section reports the recorder as "not installed". The same goes for `strafe-review/hub_section.py` and `hub/`. In the frozen hub, the Strafe Review section's `start()` runs `[exe, "--collect"]` (done in 3.7, see there).
