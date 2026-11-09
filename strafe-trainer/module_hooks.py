"""The Strafe Trainer's hooks for the kit's module manager (movekit/modules.py).

install / uninstall: install.py (--uninstall) in a fresh process, so an update or roll back always
runs the install.py now on disk: the settings copied from Source Yaw once, the autoexec blocks, and
on Linux the overlay layer and the launch hook (launch-hook.sh, run by movekit-run).
launch (Windows): launch_win.start in the core's launch process, which exits with the game.
"""


def install(ctx):
    ctx.script("install.py")


def uninstall(ctx):
    ctx.script("install.py", "--uninstall")


def launch(ctx, argv):
    if ctx.platform != "win32":
        return
    from movekit.hub import local_import

    local_import(str(ctx.folder / "module_hooks.py"), "launch_win").start(list(argv), kit=ctx.kit)
