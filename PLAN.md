# Soulmanyes's Movement Kit: plan

Status (2026-11-02): Phase 0 done locally (the three repos merged with full history, tags renamed `<tool>-v*`, privacy hooks in place; no GitHub repo yet). Phase 1 started: Steam/game discovery, Strafe Review's autoexec block and VPK reading are in `movekit` (see "Progress").

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
    games.py            the supported games as data (app ids, mod folder, install folder names)
    keyvalues.py        Valve KeyValues reader (flat pairs and nested)
    steam.py            Steam roots, libraryfolders.vdf, appmanifests (Linux, Flatpak, Windows registry)
    check_*.py          fixture checks, no game or Steam needed
    files.py            atomic file writes
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
2. **Game adapters.** `movekit/games.py` holds each game as data (`Game`: key, name, app ids, mod folder, install folder names, name hint, env override). It grows the rest (cfg dir, log path, tickrate for a map name, Panorama or not) as each concern moves in; it becomes a `games/` package only if a game needs code of its own. Tools ask it and never hard-code a game.
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
- Markers unchanged (`// strafe-review begin/end`). Moving to `// movekit:<tool>` is a behaviour change and waits for a release step with the owner.
- Verified unchanged: 36 fixture cases (missing, empty, LF, CRLF without a final newline, block in the middle, block only, stray end marker, non-UTF-8 byte, existing backup; add, add twice, add then remove, remove), comparing bytes, file mode and backup, identical before and after. Rebuilt exe bundles `movekit.cfgblock` and `movekit.files`; `smoke_test.py` passes all 5 steps.

### Phase 1.3: VPK reading (2026-11-02)

- `movekit/vpk.py`: `read_tree` (Strafe Review's parser: root-folder files, v1/v2 only), `files` (Strafe Review's `vpk_files`: empty set on any error) and `read_file` (Source Yaw's `_read_from_vpk`, tree cached per `_dir.vpk`). Reads only the header and tree, not the whole file.
- Strafe Review `install.base_timer` uses `vpk.files`; Source Yaw `sound_file` uses `vpk.read_file`.
- Two edge cases change for Source Yaw, neither reachable today: a file at a VPK's root is found at `name.ext` (was `" /name.ext"`), and a VPK whose version isn't 1 or 2 raises ValueError, which `sound_file` already skips. Sounds always sit under `sound/`, and Valve's VPKs are v1 or v2.
- Verified: synthetic VPKs (v1, v2, v3, preload bytes, data in the `_dir.vpk` and in `_000.vpk`, root file, bad signature, cut short, missing) and all 8 VPKs of the CS:S and Momentum installs on this PC (listing hash), plus every offered sound read from each game's sound VPKs: identical before and after apart from the two edge cases. A copy laid out like the installed app finds the same sounds. Rebuilt exe bundles `movekit.vpk`; `smoke_test.py` passes.

### Notes for later steps

- The tools' `.github/workflows` now sit in `strafe-review/.github` and `gain-converter/.github`, where GitHub ignores them. They move to the root in the release-CI step (with `working-directory` and `<tool>-v*` tag triggers).
- Pushing the renamed old tags would trigger the new tag-based CI for every old version. Push the branch first and decide about tags then.
- Source Yaw's updater installs from the release's source archive by running `install.sh` at the archive root; in the monorepo it is `sourceyaw/install.sh`. Fix in the updater step, before any monorepo release of Source Yaw.
- Found in Phase 1.2, unchanged so far, candidate fixes for the owner: Strafe Review's install crashes (UnicodeEncodeError) on an autoexec.cfg with a non-UTF-8 byte, because it reads with `surrogateescape` but writes strict UTF-8. `write_atomic` leaves files it writes at mode 0600 (`mkstemp`). Source Yaw turns a CRLF autoexec.cfg into LF and replaces non-UTF-8 bytes when it adds or removes its line.
