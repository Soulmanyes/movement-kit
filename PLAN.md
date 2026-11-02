# Soulmanyes's Movement Kit: plan

Status (2026-11-02): Phase 0 done locally (the three repos merged with full history, tags renamed `<tool>-v*`, privacy hooks in place; no GitHub repo yet). Phase 1 nearly done locally: Steam/game discovery, autoexec blocks, VPK reading, bind parsing and the updater are in `movekit`, release CI sits at the root, and the root has a README and a CC0 LICENSE (see "Progress"). On GitHub as a private repo since 2026-11-02. The live installs run from the monorepo since 2026-11-02, and both tools write `// movekit:<tool>` blocks. Left: the bridge releases. Phase 2 started: 2.1 (yaw.log reading, `movekit/logtail.py`) 2.2 (session core, `movekit/session.py`) and 2.3 (the Strafe Review server hosts the session and announces saved attempts) and 2.4 (the trainer and the crosshair watcher on the session, live) done. 2.5 (`movekit-run`, one launch option) done and live. 2.6 (attempt format 1 documented in `strafe-review/FORMAT.md`, reader `movekit/attempts.py`) done.

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

### GitHub repo (2026-11-02)

- `Soulmanyes/movement-kit` created private, `main` and all 21 `<tool>-v*` tags pushed. As expected, the tags started no runs and made no releases. The repo goes public through `/go-public`.
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

### Notes for later steps

- Releases: tag `<tool>-v<VERSION>` (a plain `v1.5.0` starts no CI and the updaters ignore it). The `release-repo` skill has a Movement Kit section for this since 2026-11-02.
- Pushing the renamed old tags triggers no CI: none of their commits has a workflow at the repo root (checked 2026-11-02, all 21 tags). They also make no releases, so the updaters don't see them.
- `sourceyaw/install.sh`'s `curl | sh` branch has the same root-path problem (`sh "$tmp/install.sh"`), and on the monorepo `releases/latest` gives whichever tool released last. Fix in the bridge step: pick the newest `sourceyaw-v*` tag and run `sourceyaw/install.sh`.
- `failed()` and Source Yaw's `installed()` compare tag strings. A `failed` or `installed` mark from an old unprefixed tag (`v1.5.0`) doesn't match the same version's new tag (`strafe-review-v1.5.0`), so auto mode would retry it once. No such release exists (both tools are on their newest old tag), so it stays as is.
- Until a tool has its first `<tool>-v*` release, a copy running the new updater gets "No <tool>-v* release on GitHub yet": Source Yaw stays quiet, Strafe Review's page shows it as the check error. Only dev copies run that code before then.
- Fixed 2026-11-02 (see "Markers and candidate fixes"), found in Phase 1.2: Strafe Review's install crashes (UnicodeEncodeError) on an autoexec.cfg with a non-UTF-8 byte, because it reads with `surrogateescape` but writes strict UTF-8. `write_atomic` leaves files it writes at mode 0600 (`mkstemp`). Source Yaw turns a CRLF autoexec.cfg into LF and replaces non-UTF-8 bytes when it adds or removes its line.
- Fixed 2026-11-02, found in Phase 1.4: `read_binds` matches the raw line, so a bind with a trailing `// comment` gets a command ending in `"` and its role is missed (`bind o "+moveleft" // x`). `key_conflicts` cuts at the first `//` even inside quotes, so `bind "h" "say http://x"` reports `say http:`.
