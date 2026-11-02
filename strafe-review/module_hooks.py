"""Strafe Review's hooks for the kit's module manager (movekit/modules.py, 3.7b in PLAN.md).

launch: the launch option's part before the game (strafe_review.prepare_launch: install the recorder,
start the server, open the page), when the kit's core exe is the launch option (movekit/dispatch.py).
install: install.py, the same as running it by hand: the recorder into Momentum Mod, the autoexec
block, and on Linux the launch hook with movekit-run. It fails when Momentum Mod isn't found.
uninstall: install.py --uninstall. stop/start: the review server, through the hub section's own
calls, so an update never swaps files under a running server: stop waits until it has ended.
"""
import sys
import time

from movekit.hub import local_import

STOP_WAIT = 10  # seconds to wait for the server to end, so its files are free to swap (Windows)


def _section():
    return local_import(__file__, "hub_section")


def install(ctx):
    ctx.script("install.py")


def uninstall(ctx):
    ctx.script("install.py", "--uninstall")


def stop(ctx):
    section = _section()
    if not section.status()["serving"]:
        return False
    try:
        section.stop()  # only asks; the server ends a moment later
    except OSError:
        return False  # it ended by itself in between
    end = time.monotonic() + STOP_WAIT
    while time.monotonic() < end and section.status()["serving"]:
        time.sleep(0.2)
    return True


def start(ctx):
    _section().start()


def launch(ctx, argv):
    # in the core's launch process only, which exits with the game: the bare module names that
    # strafe_review.py puts on the path don't reach the hub
    if str(ctx.folder) not in sys.path:
        sys.path.insert(0, str(ctx.folder))
    import strafe_review

    strafe_review.log_to_file()
    strafe_review.prepare_launch()
