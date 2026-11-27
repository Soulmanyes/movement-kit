"""Paint Saver's hooks for the kit's module manager (movekit/modules.py, 3.7b in PLAN.md).

install / uninstall: install.py (--uninstall) in a fresh process, as Z Penalty does.
launch: install with launch=True before the game starts, when the kit's core exe is the launch option
(Windows; movekit/dispatch.py): reads the saved paint from yaw.log and writes savedlocs.txt while the
game is still closed. On Linux install.py registers launch-hook.sh with movekit-run for it.
"""
from movekit.hub import local_import


def install(ctx):
    ctx.script("install.py")


def uninstall(ctx):
    ctx.script("install.py", "--uninstall")


def launch(ctx, argv):
    inst = local_import(__file__, "install")
    game = inst.find_game()
    if game is not None:
        inst.install(game, quiet=True, launch=True)
