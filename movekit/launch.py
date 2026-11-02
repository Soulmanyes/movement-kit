"""What `movekit-run` starts: the game from Steam's command line, and the launch hooks of the
tools that are installed and turned on for it. Linux only (Windows runs the Strafe Review exe
as its own launch option).

Each tool's installer registers a launch hook, a bash snippet the wrapper sources before it
starts the game (see movekit-run for what a hook may do):

    python3 launch.py register <tool> <order> <hook>   # also links ~/.local/bin/movekit-run here
    python3 launch.py unregister <tool>

Hooks run in order, lowest first; the links live in $XDG_DATA_HOME/movekit/hooks as
<order>-<tool>. Which tools run for which game is the [launch] table of the one settings file,
$XDG_CONFIG_HOME/movekit/settings.toml; a game it leaves out runs every registered hook:

    [launch]
    momentum = ["strafe-review", "sourceyaw"]
    css = ["sourceyaw"]

`python3 launch.py plan <name> <steam command...>` prints `game <key>`, then `hook <tool> <path>`
per hook to run, for movekit-run to read. <name> is the name the wrapper was called by: the old
per-tool names (sourceyaw-run, strafe-review-run) run only their own tool, so launch options
written before movekit-run keep doing exactly what they did.
"""
import os
import sys
import tomllib
from pathlib import Path

if __package__ in (None, ""):  # run as a script (movekit-run does): import movekit next to us
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from movekit import games, paths

WRAPPER = "movekit-run"
# names from before movekit-run, each limited to its own tool
OLD_NAMES = {"sourceyaw-run": "sourceyaw", "css-yaw-run": "sourceyaw", "yaw-run": "sourceyaw",
             "strafe-review-run": "strafe-review"}
# tools a wrapper further out already ran (an old name chained after movekit-run, or two old
# names chained); set by movekit-run for the command it starts
RAN_ENV = "MOVEKIT_RAN"


def hooks_dir():
    return paths.data_dir("movekit") / "hooks"


def settings_file():
    return paths.config_dir("movekit") / "settings.toml"


def bin_link():
    return Path.home() / ".local" / "bin" / WRAPPER


def game_from_args(args):
    """The game Steam is starting: its command line carries AppId=<id> (the reaper wrapper)."""
    for arg in args:
        if arg.startswith("AppId="):
            appid = arg[len("AppId="):]
            for game in games.GAMES.values():
                if appid in game.appids:
                    return game.key
    return "css"  # what sourceyaw-run assumed before: CS:S has no reaper line on older Steam


def registered():
    """{tool: (order, hook path)} for every hook link that still points at a file."""
    found = {}
    folder = hooks_dir()
    if not folder.is_dir():
        return found
    for link in folder.iterdir():
        order, _, tool = link.name.partition("-")
        if order.isdigit() and tool and link.is_file():
            found[tool] = (int(order), link)
    return found


def enabled(game, settings=None):
    """The tools turned on for a game, or None when the settings don't say (then: all)."""
    path = settings or settings_file()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        print(f"{WRAPPER}: ignoring {path}: {e}", file=sys.stderr)
        return None
    tools = data.get("launch", {}).get(game)
    if tools is None:
        return None
    if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
        print(f"{WRAPPER}: ignoring launch.{game} in {path}: not a list of tool names",
              file=sys.stderr)
        return None
    return tools


def plan(name, args, env=None):
    """(game, [(tool, hook path)]) for one launch."""
    env = os.environ if env is None else env
    game = game_from_args(args)
    hooks = registered()
    only = OLD_NAMES.get(name)
    ran = set(env.get(RAN_ENV, "").split())
    wanted = enabled(game)
    run = []
    for tool, (order, hook) in sorted(hooks.items(), key=lambda kv: (kv[1][0], kv[0])):
        if (only and tool != only) or tool in ran or (wanted is not None and tool not in wanted):
            continue
        run.append((tool, hook))
    return game, run


def register(tool, order, hook):
    """Link a tool's hook into the hooks folder, and ~/.local/bin/movekit-run to this copy."""
    if not tool or tool.startswith("-") or "/" in tool or not str(order).isdigit():
        raise SystemExit(f"bad tool name or order: {tool!r} {order!r}")
    folder = hooks_dir()
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob(f"*-{tool}"):
        if old.name.partition("-")[2] == tool:
            old.unlink()
    (folder / f"{int(order):02d}-{tool}").symlink_to(Path(hook).resolve())
    link_wrapper(Path(__file__).resolve().with_name(WRAPPER))


def unregister(tool):
    """Remove a tool's hook. ~/.local/bin/movekit-run goes with the last tool; while others are
    left, it is relinked to one of their copies if it pointed into this one (being removed)."""
    folder = hooks_dir()
    if folder.is_dir():
        for old in folder.glob(f"*-{tool}"):
            if old.name.partition("-")[2] == tool:
                old.unlink()
    link = bin_link()
    if not link.is_symlink():
        return
    left = registered()
    if not left:
        link.unlink()
        return
    if link.exists() and link.resolve() != Path(__file__).resolve().with_name(WRAPPER):
        return  # another tool's copy: leave it
    for _, hook in sorted(left.values()):
        wrapper = find_wrapper(hook.resolve().parent)
        if wrapper:
            link_wrapper(wrapper)
            return
    link.unlink()


def find_wrapper(start):
    """movekit/movekit-run in a tool's folder or up to two folders above it."""
    for folder in (start, start.parent, start.parent.parent):
        candidate = folder / "movekit" / WRAPPER
        if candidate.is_file():
            return candidate
    return None


def link_wrapper(target):
    link = bin_link()
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)


def main(argv):
    if argv[:1] == ["plan"] and len(argv) >= 2:
        game, run = plan(Path(argv[1]).name, argv[2:])
        print(f"game {game}")
        for tool, hook in run:
            print(f"hook {tool} {hook}")
    elif argv[:1] == ["register"] and len(argv) == 4:
        register(*argv[1:])
    elif argv[:1] == ["unregister"] and len(argv) == 2:
        unregister(argv[1])
    else:
        raise SystemExit("usage: launch.py plan <name> <command...> | register <tool> <order> <hook>"
                         " | unregister <tool>")


if __name__ == "__main__":
    main(sys.argv[1:])
