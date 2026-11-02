# Soulmanyes's Movement Kit: plan

Status (2026-11-02): Phase 0 done locally (the three repos merged with full history, tags renamed `<tool>-v*`, privacy hooks in place; no GitHub repo yet). Phase 1 nearly done locally: Steam/game discovery, autoexec blocks, VPK reading, bind parsing and the updater are in `movekit`, release CI sits at the root, and the root has a README and a CC0 LICENSE (see "Progress"). On GitHub as a private repo since 2026-11-02. The live installs run from the monorepo since 2026-11-02. Left: the marker decision and the bridge releases.

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

## Phase 3: hub app

- One window with a section per tool, on Linux and Windows. Open question: the UI toolkit. Source Yaw is GTK (Linux only), Strafe Review is a web page that already runs on Windows, Gain Converter is tkinter. A web UI served by the session daemon is the likely fit.

## Later / undecided

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

### GitHub repo (2026-11-02)

- `Soulmanyes/movement-kit` created private, `main` and all 21 `<tool>-v*` tags pushed. As expected, the tags started no runs and made no releases. The repo goes public through `/go-public`.
- Sandbox test (2026-11-02, owner): all three tools run from the monorepo with a fake HOME holding copies of the real cfg/ and custom/ folders, and symlinked VPKs and yaw.log. Strafe Review installed into the copy, served on 8799 and collected 1305 attempts from the live yaw.log. No real file changed. Owner: "looks good". Source Yaw was light mode only because the fake HOME has no dconf (`color-scheme` reads `default` there). Not tested yet: the game running the kit versions (needs the real install swap with the game closed).
- Real install swap (2026-11-02, owner): with Momentum closed, the live installs were backed up to `~/archive/movement-kit-swap-2026-11-02/` (both share folders, `~/.config/sourceyaw`, the `~/.local/bin` links, desktop file and icon, Vulkan layer json, Momentum and CS:S cfgs, `custom/0-strafe-review`), then `sourceyaw/install.sh` and `strafe-review/install.py` ran from the monorepo. `strafe-review-run` now links into `movement-kit/strafe-review/collector/`, and the 8765 server unit runs from the monorepo. autoexec.cfg and both yaws.cfg came out identical; the root-owned input service already matched (only the `@USER@` template differs). The installed recorder `.ts` was behind both repos (it lacked the per-strafe loss causes in the in-game line) and is now current. Owner played with the unchanged launch options: "everything works". Rollback: copy the backup back, or run the installers from the old folders.

### Notes for later steps

- Releases: tag `<tool>-v<VERSION>` (a plain `v1.5.0` starts no CI and the updaters ignore it). The `release-repo` skill has a Movement Kit section for this since 2026-11-02.
- Pushing the renamed old tags triggers no CI: none of their commits has a workflow at the repo root (checked 2026-11-02, all 21 tags). They also make no releases, so the updaters don't see them.
- `sourceyaw/install.sh`'s `curl | sh` branch has the same root-path problem (`sh "$tmp/install.sh"`), and on the monorepo `releases/latest` gives whichever tool released last. Fix in the bridge step: pick the newest `sourceyaw-v*` tag and run `sourceyaw/install.sh`.
- `failed()` and Source Yaw's `installed()` compare tag strings. A `failed` or `installed` mark from an old unprefixed tag (`v1.5.0`) doesn't match the same version's new tag (`strafe-review-v1.5.0`), so auto mode would retry it once. No such release exists (both tools are on their newest old tag), so it stays as is.
- Until a tool has its first `<tool>-v*` release, a copy running the new updater gets "No <tool>-v* release on GitHub yet": Source Yaw stays quiet, Strafe Review's page shows it as the check error. Only dev copies run that code before then.
- Found in Phase 1.2, unchanged so far, candidate fixes for the owner: Strafe Review's install crashes (UnicodeEncodeError) on an autoexec.cfg with a non-UTF-8 byte, because it reads with `surrogateescape` but writes strict UTF-8. `write_atomic` leaves files it writes at mode 0600 (`mkstemp`). Source Yaw turns a CRLF autoexec.cfg into LF and replaces non-UTF-8 bytes when it adds or removes its line.
- Found in Phase 1.4, unchanged, candidate fixes for the owner: `read_binds` matches the raw line, so a bind with a trailing `// comment` gets a command ending in `"` and its role is missed (`bind o "+moveleft" // x`). `key_conflicts` cuts at the first `//` even inside quotes, so `bind "h" "say http://x"` reports `say http:`.
