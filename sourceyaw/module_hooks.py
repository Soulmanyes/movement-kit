"""Source Yaw's hooks for the kit's module manager (movekit/modules.py, 3.7b in PLAN.md). Linux only.

install: install.sh, the same as running it by hand (the app to ~/.local/share/sourceyaw, its
launcher and launch hook). With no terminal it can't ask for a password, so missing system packages
make it stop with a message instead.
uninstall: first the game side (yaws.cfg and its autoexec line, which install.sh --uninstall only
asks about in a terminal), then install.sh --uninstall. Settings in ~/.config/sourceyaw stay unless
the uninstall asked to delete saved data (module.json "data").
"""


def install(ctx):
    ctx.run(["sh", "install.sh"], "install.sh", timeout=600)


def uninstall(ctx):
    ctx.script("yawcore.py", "--remove-from-game")
    ctx.run(["sh", "install.sh", "--uninstall"], "install.sh --uninstall")
