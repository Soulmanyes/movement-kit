"""Source Yaw's hooks for the kit's module manager (movekit/modules.py, 3.7b in PLAN.md).

Linux:
install: install.sh, the same as running it by hand (the app to ~/.local/share/sourceyaw, its
launcher and launch hook). With no terminal it can't ask for a password, so missing system packages
make it stop with a message instead.
uninstall: first the game side (yaws.cfg and its autoexec line, which install.sh --uninstall only
asks about in a terminal), then install.sh --uninstall. Settings in ~/.config/sourceyaw stay unless
the uninstall asked to delete saved data (module.json "data").
launch: nothing here; movekit-run sources launch-hook.sh, which install.sh registered.

Windows (Phase 12): the module folder itself is the install, so install does nothing.
uninstall: the game side only. launch: launch_win.start, in the core's launch process.
"""
import sys


def install(ctx):
    if ctx.platform == "win32":
        return
    ctx.run(["sh", "install.sh"], "install.sh", timeout=600)


def uninstall(ctx):
    ctx.script("yawcore.py", "--remove-from-game")
    if ctx.platform != "win32":
        ctx.run(["sh", "install.sh", "--uninstall"], "install.sh --uninstall")


def launch(ctx, argv):
    if ctx.platform != "win32":
        return
    # in the core's launch process only, which exits with the game: the bare module names
    # (yawcore, trainer, mode_watch) don't reach the hub
    if str(ctx.folder) not in sys.path:
        sys.path.insert(0, str(ctx.folder))
    import launch_win

    launch_win.start(list(argv))
