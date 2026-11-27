"""Paint Saver's hub section (movekit/hub.py): what it does, its two switches (install.read_settings),
how to use it, the Steam launch option it needs, and the paint saved per map (paint.json, written at each
game start by install.py --launch).

The Save, Load and Delete buttons run mk_savepaint, mk_loadpaint and mk_clearpaint in the open game
through Source Yaw's net console (sourceyaw/netcon.py, as Sens Converter does), which is there only when
the game was started through the kit with Source Yaw installed. The game's answer (its "Paint Saver: ..."
echo) is read back from yaw.log.

hub.discover() loads this file on every OS before it looks at "os", so the top imports only the
standard library and movekit; the siblings load on the first call through hub.local_import.
"""
import time
from pathlib import Path

from movekit import launchopt, paths
from movekit.hub import local_import

TOOL = "paint-saver"
GAME = "momentum"
SOURCEYAW = Path(__file__).resolve().parent.parent / "sourceyaw"  # a sibling module at the kit root
COMMANDS = {"save": "mk_savepaint", "load": "mk_loadpaint", "clear": "mk_clearpaint"}
SAY = "Paint Saver: "  # the HUD script's and the aliases' echo prefix
REPLY_S = 1.5  # how long to wait for the game's answer in yaw.log
NOT_OPEN = ("The game isn't open through the kit with Source Yaw installed, so the hub can't reach its console. "
            "Type this in the console instead:")


def _install():
    return local_import(__file__, "install")


def _paintlog():
    return local_import(__file__, "paintlog")


def launch_option():
    """The launch options to paste into Steam and the note under them (movekit.launchopt)."""
    return launchopt.offer("momentum")


def saved():
    """[{map, strokes, points, ready, stuck}] from paint.json, by map name. ready: written into the game
    at the last game start, so mk_loadpaint has it; else it comes after the next one."""
    pl = _paintlog()
    data = pl.load(_install().data_file())
    plan = data.get("plan") or {}
    return [{"map": m, "strokes": len(s), "points": sum(len(x["p"]) for x in s), "ready": bool(plan.get(m)),
             "stuck": pl.stuck(s)}
            for m, s in sorted(data.get("maps", {}).items()) if s]


def _netcon():
    """Source Yaw's netcon.py and its settings folder, or None when Source Yaw isn't here."""
    if not (SOURCEYAW / "netcon.py").exists():
        return None
    try:
        return local_import(SOURCEYAW / "hub_section.py", "netcon"), paths.config_dir("sourceyaw")
    except Exception:  # noqa: BLE001 - an old or broken Source Yaw only costs the buttons
        return None


def _replies(log, start):
    """The "Paint Saver: ..." lines yaw.log got after byte `start`."""
    try:
        with open(log, "rb") as f:
            f.seek(start)
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return []
    return [line.split(SAY, 1)[1].strip() for line in text.splitlines()
            if SAY in line and "echo " not in line]


def run(what):
    """Run mk_savepaint / mk_loadpaint / mk_clearpaint (what: save, load, clear) in the open game.
    Returns {"sent": bool, "messages": [...]}: the game's answer, or why it wasn't sent and the command."""
    command = COMMANDS[what]
    game = _install().find_game()
    net = _netcon()
    if game is None or net is None or not net[0].is_open(GAME, net[1]):
        return {"sent": False, "messages": [NOT_OPEN, command]}
    log = Path(game) / "yaw.log"
    try:
        start = log.stat().st_size
    except OSError:
        start = 0
    if not net[0].send(GAME, command, net[1]):
        return {"sent": False, "messages": [NOT_OPEN, command]}
    end = time.monotonic() + REPLY_S
    while time.monotonic() < end:
        time.sleep(0.1)
        found = _replies(log, start)
        if found:
            return {"sent": True, "messages": found}
    return {"sent": True, "messages": [f"Sent {command}"]}


def load():
    """What the page shows."""
    inst = _install()
    return {"version": inst.VERSION, "launch": launch_option(), "saved": saved(), "settings": inst.read_settings(),
            "problem": None if inst.find_game() else "Momentum Mod not found in your Steam libraries"}


def set_options(save, load_off):
    """Save the switches and install again, so the autoexec block and the script follow them. They take
    effect at the next game start: the game runs its autoexec only then. Returns load()'s data."""
    inst = _install()
    inst.write_settings({"save": bool(save), "load_off": bool(load_off)})
    game = inst.find_game()
    if game is not None:
        inst.install(game, quiet=True)
    return load()


SECTION = {
    "key": TOOL,
    "title": "Paint Saver",
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {"load": load, "set_options": set_options, "launch_option": launch_option, "run": run},
    "order": 40,
}
