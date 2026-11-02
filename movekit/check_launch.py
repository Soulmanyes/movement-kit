#!/usr/bin/env python3
"""Checks movekit.launch and movekit-run in a temp home with fake hooks and a fake game; no Steam,
game or tool install needed, and nothing outside the temp folder is touched.

Usage: python movekit/check_launch.py   (exits 1 on the first failure)

Covers: the game from Steam's AppId= argument, hook order, the settings file (a game listed,
a game left out, a broken file), the old names running only their own tool, MOVEKIT_RAN,
no tomllib (Python 3.10), register/unregister (the ~/.local/bin link, relinked to another tool's copy, removed with the
last one), and movekit-run itself: arguments passed on as they are, LD_PRELOAD and
LD_LIBRARY_PATH kept from the helpers and given back to the game, exports reaching the game,
helpers stopped when the game exits, the game's exit code kept, a failing hook skipped, and
the chained old names (strafe-review-run sourceyaw-run, movekit-run sourceyaw-run) running each
tool once.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from movekit import launch  # after the path above

MOMENTUM = ["/steam/reaper", "SteamLaunch", "AppId=1802710", "--", "/game/hl2.sh", "-game", "momentum"]
CSS = ["/steam/reaper", "SteamLaunch", "AppId=240", "--", "/game/hl2.sh"]

# a hook that notes it ran (tool, game, its folder), exports a variable for the game and starts a
# helper; FAIL_<tool>=1 makes it fail before starting anything
HOOK = """\
local note="$HOOK_DIR/../../ran"
[ "${{FAIL_{var}:-0}}" = 1 ] && return 1
echo "{tool} $GAME $HOOK_DIR LD_PRELOAD=${{LD_PRELOAD-unset}}" >> "$note"
export FROM_{var}=yes
sleep 300 &
echo "$!" > "$HOOK_DIR/../../helper-{tool}"
HELPERS="$HELPERS $!"
"""
GAME = """\
#!/bin/sh
{
  for a in "$@"; do printf 'arg=%s\\n' "$a"; done
  echo "LD_PRELOAD=${LD_PRELOAD-unset}"
  echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH-unset}"
  echo "FROM_SY=${FROM_SY-unset}"
  echo "FROM_SR=${FROM_SR-unset}"
} > "$OUT"
exit 7
"""


def check(what, got, want):
    if got != want:
        sys.exit(f"FAIL {what}: got {got!r}, want {want!r}")
    print(f"ok   {what}")


def tool_copy(root, tool, var):
    """A tool folder with its own movekit copy and a hook, like an installed Source Yaw."""
    folder = root / tool
    (folder / "movekit").mkdir(parents=True)
    for f in ("launch.py", "games.py", "paths.py", "__init__.py", "movekit-run"):
        shutil.copy2(HERE / f, folder / "movekit" / f)
    hook = folder / "hook" / "launch-hook.sh"
    hook.parent.mkdir()
    hook.write_text(HOOK.format(tool=tool, var=var))
    return folder, hook


def run_wrapper(names, args, home, env_extra=None):
    """Runs the chain of wrapper names (links in home/bin) before a fake game; returns the
    game's exit code and output lines."""
    out = home / "game.out"
    out.unlink(missing_ok=True)
    env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / "data"),
               XDG_CONFIG_HOME=str(home / "config"), OUT=str(out),
               LD_PRELOAD="libc.so.6", LD_LIBRARY_PATH="/steam/runtime")
    env.pop(launch.RAN_ENV, None)
    env.update(env_extra or {})
    cmd = [str(home / "bin" / n) for n in names] + [str(home / "game.sh"), *args]
    code = subprocess.run(cmd, env=env, timeout=20, check=False).returncode
    return code, out.read_text().splitlines() if out.exists() else []


def ran(home):
    note = home / "tools" / "ran"
    lines = note.read_text().splitlines() if note.exists() else []
    note.unlink(missing_ok=True)
    return lines


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # a stopped child may linger as a zombie until its parent's parent reaps it
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ")[1][0] != "Z"
    except (OSError, IndexError):
        return False


def main():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        os.environ.update(HOME=str(home), XDG_DATA_HOME=str(home / "data"),
                          XDG_CONFIG_HOME=str(home / "config"))
        os.environ.pop(launch.RAN_ENV, None)

        # -- plan, without the shell
        check("game: Momentum by app id", launch.game_from_args(MOMENTUM), "momentum")
        check("game: CS:S by app id", launch.game_from_args(CSS), "css")
        check("game: no AppId means CS:S", launch.game_from_args(["/game/hl2.sh"]), "css")
        check("nothing registered", launch.plan("movekit-run", MOMENTUM), ("momentum", []))

        tools = home / "tools"
        sy_dir, sy_hook = tool_copy(tools, "sourceyaw", "SY")
        sr_dir, sr_hook = tool_copy(tools, "strafe-review", "SR")
        # loaded from the copies, so register() links ~/.local/bin/movekit-run to that copy
        sy = subprocess.run([sys.executable, sy_dir / "movekit" / "launch.py", "register",
                             "sourceyaw", "50", sy_hook], env=os.environ, check=False)
        check("register sourceyaw", sy.returncode, 0)
        bin_link = home / ".local" / "bin" / "movekit-run"
        check("movekit-run linked to the first copy", bin_link.resolve(),
              (sy_dir / "movekit" / "movekit-run").resolve())
        sr = subprocess.run([sys.executable, sr_dir / "movekit" / "launch.py", "register",
                             "strafe-review", "20", sr_hook], env=os.environ, check=False)
        check("register strafe-review", sr.returncode, 0)
        check("movekit-run linked to the last copy", bin_link.resolve(),
              (sr_dir / "movekit" / "movekit-run").resolve())
        check("hook links", sorted(p.name for p in launch.hooks_dir().iterdir()),
              ["20-strafe-review", "50-sourceyaw"])

        def tools_of(name, args, env=None):
            game, run = launch.plan(name, args, env or {})
            return game, [t for t, _ in run]

        check("all tools, lowest order first", tools_of("movekit-run", MOMENTUM),
              ("momentum", ["strafe-review", "sourceyaw"]))
        check("old name: only its tool", tools_of("sourceyaw-run", MOMENTUM),
              ("momentum", ["sourceyaw"]))
        check("old name: css-yaw-run", tools_of("css-yaw-run", CSS), ("css", ["sourceyaw"]))
        check("old name: strafe-review-run", tools_of("strafe-review-run", MOMENTUM),
              ("momentum", ["strafe-review"]))
        check("already ran further out", tools_of("movekit-run", MOMENTUM,
                                                  {launch.RAN_ENV: "strafe-review"}),
              ("momentum", ["sourceyaw"]))

        settings = launch.settings_file()
        settings.parent.mkdir(parents=True)
        settings.write_text('[launch]\nmomentum = ["sourceyaw"]\n')
        check("settings: game listed", tools_of("movekit-run", MOMENTUM), ("momentum", ["sourceyaw"]))
        check("settings: game left out runs all", tools_of("movekit-run", CSS),
              ("css", ["strafe-review", "sourceyaw"]))
        check("settings: old name still obeys them", tools_of("strafe-review-run", MOMENTUM),
              ("momentum", []))
        settings.write_text('[launch\nmomentum = "x"\n')
        check("settings: broken file runs all", tools_of("movekit-run", MOMENTUM),
              ("momentum", ["strafe-review", "sourceyaw"]))
        settings.write_text('[launch]\nmomentum = "sourceyaw"\n')
        check("settings: not a list runs all", tools_of("movekit-run", MOMENTUM),
              ("momentum", ["strafe-review", "sourceyaw"]))
        # Python 3.10 has no tomllib: the settings are ignored with a note, every tool runs
        no_toml = subprocess.run(
            [sys.executable, "-c", ("import sys; sys.modules['tomllib'] = None; "
             f"sys.path.insert(0, {str(HERE.parent)!r}); from movekit import launch; "
             "print([t for t, _ in launch.plan('movekit-run', sys.argv[1:], {})[1]])"), *MOMENTUM],
            env=os.environ, capture_output=True, text=True, check=False)
        check("no tomllib: every tool runs", no_toml.stdout.strip(), "['strafe-review', 'sourceyaw']")
        check("no tomllib: says why", "needs Python 3.11" in no_toml.stderr, True)
        settings.unlink()

        # -- movekit-run itself
        game = home / "game.sh"
        game.write_text(GAME)
        game.chmod(0o755)
        for name in ("sourceyaw-run", "strafe-review-run"):
            (home / "bin").mkdir(exist_ok=True)
            (home / "bin" / name).symlink_to(sy_dir / "movekit" / "movekit-run")
        (home / "bin" / "movekit-run").symlink_to(bin_link)
        args = [*MOMENTUM[:3], "--", "has space", "", "-novid"]

        code, out = run_wrapper(["movekit-run"], args, home)
        check("game exit code kept", code, 7)
        check("arguments passed on as they are", [x for x in out if x.startswith("arg=")],
              [f"arg={a}" for a in args])
        check("game gets LD_PRELOAD back", "LD_PRELOAD=libc.so.6" in out, True)
        check("game gets LD_LIBRARY_PATH back", "LD_LIBRARY_PATH=/steam/runtime" in out, True)
        check("hook exports reach the game", ["FROM_SY=yes", "FROM_SR=yes"],
              [x for x in out if x.startswith("FROM_")])
        check("hooks ran in order, without LD_PRELOAD", ran(home),
              [f"strafe-review momentum {sr_hook.parent} LD_PRELOAD=unset",
               f"sourceyaw momentum {sy_hook.parent} LD_PRELOAD=unset"])
        for tool in ("sourceyaw", "strafe-review"):
            pid = int((tools / f"helper-{tool}").read_text())
            deadline = time.time() + 3
            while alive(pid) and time.time() < deadline:
                time.sleep(0.05)
            check(f"{tool} helper stopped with the game", alive(pid), False)

        run_wrapper(["strafe-review-run", "sourceyaw-run"], args, home)
        check("old chain: each tool once", [r.split()[0] for r in ran(home)],
              ["strafe-review", "sourceyaw"])
        run_wrapper(["movekit-run", "sourceyaw-run"], args, home)
        check("movekit-run then an old name: each tool once", [r.split()[0] for r in ran(home)],
              ["strafe-review", "sourceyaw"])
        code, out = run_wrapper(["sourceyaw-run"], CSS, home)
        check("old name alone: its tool", [r.split()[:2] for r in ran(home)], [["sourceyaw", "css"]])
        check("old name alone: game still runs", code, 7)

        code, out = run_wrapper(["movekit-run"], args, home, {"FAIL_SR": "1"})
        check("failing hook: the others still run", [r.split()[0] for r in ran(home)], ["sourceyaw"])
        check("failing hook: game still runs", (code, "FROM_SR=unset" in out), (7, True))

        settings.write_text("[launch\n")
        run_wrapper(["movekit-run"], args, home)
        ran(home)
        check("launch.py's notes go to launch.log",
              "ignoring" in (home / ".local" / "state" / "movekit" / "launch.log").read_text(), True)
        settings.unlink()

        (home / "nohooks").mkdir()
        code, out = run_wrapper(["movekit-run"], args, home,
                                {"XDG_DATA_HOME": str(home / "nohooks")})
        check("no hooks: game runs alone", (code, ran(home), "LD_PRELOAD=libc.so.6" in out),
              (7, [], True))

        # -- unregister
        un = subprocess.run([sys.executable, sr_dir / "movekit" / "launch.py", "unregister",
                             "strafe-review"], env=os.environ, check=False)
        check("unregister strafe-review", un.returncode, 0)
        check("its hook gone", sorted(p.name for p in launch.hooks_dir().iterdir()), ["50-sourceyaw"])
        check("movekit-run relinked to the copy left", bin_link.resolve(),
              (sy_dir / "movekit" / "movekit-run").resolve())
        un = subprocess.run([sys.executable, sr_dir / "movekit" / "launch.py", "unregister",
                             "sourceyaw"], env=os.environ, check=False)
        check("unregister a tool from another copy", un.returncode, 0)
        check("movekit-run gone with the last tool", bin_link.is_symlink(), False)

    print("all launch checks passed")


if __name__ == "__main__":
    main()
