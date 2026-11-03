"""First Jump HUD's hooks for the kit's module manager (movekit/modules.py, 3.7b in PLAN.md).

install / uninstall: install.py (--uninstall) in a fresh process, as Strafe Review does, so an update
or roll back always runs the install.py now on disk. It fails when Momentum Mod isn't found.
launch: install again before the game starts, when the kit's core exe is the launch option (Windows;
movekit/dispatch.py), so the kit's patched files follow a game update. That process is new at every
start, so loading install.py into it is safe. On Linux install.py registers launch-hook.sh with
movekit-run for that.
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
        inst.install(game, quiet=True)
