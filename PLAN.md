# Soulmanyes's Movement Kit: plan

Status: planning (2026-11-02). Nothing is built yet, and there's no GitHub repo yet.

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

## Layout (target)

```
movement-kit/
  movekit/              shared Python package, stdlib only
    games/              one adapter per game: momentum.py, css.py
    steam.py            Steam roots, libraryfolders.vdf, appmanifests (Linux, Flatpak, Windows registry)
    cfgblock.py         named autoexec blocks: // movekit:<module> begin/end, CRLF-safe, backup, uninstall
    vpk.py              read files out of VPKs
    binds.py            config.cfg binds and aliases
    logtail.py          follow con_logfile (yaw.log), CRLF, rotation, map load / tickrate lines
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
2. **Game adapters.** `games/momentum.py` and `games/css.py`, each with the same small interface: app id, game folder, cfg dir, log path, tickrate for a map name, whether it has Panorama. Tools ask the adapter and never hard-code a game.
3. **cfg blocks.** Every tool writes its own `// movekit:<tool> begin/end` block. Migrate the old `// strafe-review begin` block and Source Yaw's `exec yaws.cfg` line on the next install.
4. **Updater.** One class, two install modes (source + install script on Linux, exe swap on Windows). It lists releases and picks the newest tag with its own prefix, not `releases/latest`. It keeps the state file, auto flag and `failed` loop guard from Strafe Review.
5. **Release CI.** One reusable workflow (PyInstaller one-file, smoke test on the Windows runner, licence zip), triggered by `<tool>-v*` tags. The current Strafe Review and Gain Converter workflows are the base.
6. **Bridge releases.** These are the last release in each old repo. Their updater points at `Soulmanyes/movement-kit` with that tool's tag prefix, and Source Yaw's `install.sh` (the `curl | sh` one) forwards to the new repo. Then the old repos get archived. This step must ship before archiving, or installed copies stop updating: the friend's Windows exe, and Source Yaw installs.

Done when: both tools are released from the monorepo, with no duplicated code from the table left, and an old install updates itself onto the new repo.

## Phase 2: one session, one launch option

- **Session daemon.** One process per game session tails `yaw.log` once, reads `sourceyaw-inputd` when the trainer is on, and publishes events over a local socket/SSE: `map_loaded`, `tickrate`, `attempt_saved`, `jump`, `game_exit`. The trainer, the crosshair watcher and the Strafe Review collector become subscribers.
- **`movekit-run %command%`.** One Steam launch option that starts whichever tools are turned on (one settings file), instead of chained `strafe-review-run sourceyaw-run`. The old wrapper names stay as links for a while.
- **Attempt format.** Version the srrec attempt format as a documented schema, so new tools (histograms, progress over time, JHUD) read attempts without touching the collector.

## Later / undecided

- **Hub app.** One window with a tab per tool. Open question: the UI toolkit. Source Yaw is GTK (Linux only), while Strafe Review is a web page that already runs on Windows.
- **Panorama module kit.** One installer for `custom/0-*` folders and `timer.xml` includes, shared by the recorder, `mmod-trainer-height` and a future JHUD.
- **Gain math in one language.** Either Python serves it over the API, or one shared JS module serves both the viewer and Gain Converter.
- Windows strafe trainer, and the CS:S version of Strafe Review. Both get easier once the game adapters exist.
