"""Strafe Trainer Height's hooks for the kit's module manager (movekit/modules.py, 3.7b in PLAN.md).

install / uninstall: install.py's, in this process. launch: install again before the game starts,
when the kit's core exe is the launch option (Windows; movekit/dispatch.py), so the kit's patched files
follow a game update. On Linux install.py registers launch-hook.sh with movekit-run for that.
"""
from movekit.hub import local_import


def _installer():
    return local_import(__file__, "install")


def install(ctx):
    inst = _installer()
    game = inst.find_game()
    if game is None:
        raise RuntimeError("Momentum Mod wasn't found, so Strafe Trainer Height can't go in")
    inst.install(game)  # a patch that no longer fits is left out and shows on the HUD page's card


def uninstall(ctx):
    inst = _installer()
    inst.uninstall(inst.find_game())


def launch(ctx, argv):
    inst = _installer()
    game = inst.find_game()
    if game is not None:
        inst.install(game, quiet=True)
