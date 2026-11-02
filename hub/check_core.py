#!/usr/bin/env python3
"""Checks the core's entry point (hub/movement_kit.py, 3.7b in PLAN.md) from the repo, each case in a
fresh process as Steam or the hub would start it, against a temp kit and a fake GitHub.

Usage: python hub/check_core.py   (exits 1 on the first failure)

Covers: the launch option passing through: with no modules the game runs with its own arguments
and its exit code comes back; a module whose launch hook raises is skipped and logged and the game
still runs; a working launch hook runs before the game. --run-script runs a script by path with its
folder on the path. --modules: cards, install, auto-on and uninstall with the reply in a file. The
bridge's migration: with Strafe Review's old data folder and no module, the first start installs
the Strafe Review module and keeps the old auto switch, once; a start with no old folder only
marks it done; offline, it's left for the next start and the game still runs.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "movekit"))
import check_modules as cm  # its temp folder and environment (HOME, XDG, LOCALAPPDATA), fake GitHub

CORE = HERE / "movement_kit.py"
LOG_HOOK = '''
import os
from pathlib import Path


def launch(ctx, argv):
    {body}
'''


def run_core(*args, kit, api="http://127.0.0.1:9/none"):
    env = {**os.environ, "MOVEKIT_KIT_ROOT": str(kit), "MOVEKIT_MODULES_API": api}
    return subprocess.run([sys.executable, str(CORE), *map(str, args)], env=env, capture_output=True,
                          text=True, timeout=60, check=False)


def game(marker, code=0):
    """A stand-in game: writes its arguments to marker, exits with code."""
    script = f"import sys, pathlib; pathlib.Path({str(marker)!r}).write_text(' '.join(sys.argv[1:])); sys.exit({code})"
    return [sys.executable, "-c", script]


def fixture(kit, key, body):
    folder = kit / key
    folder.mkdir(parents=True)
    (folder / "module.json").write_text(json.dumps({
        "key": key, "title": key, "os": ["linux", "win32"], "tag_prefix": f"{key}-v",
        "version_from": "tool.py", "needs_core": "1.0.0"}))
    (folder / "tool.py").write_text('VERSION = "1.0.0"\n')
    (folder / "module_hooks.py").write_text(LOG_HOOK.format(body=body))


def check_launch():
    kit = cm.TMP / "core-kit"
    kit.mkdir()
    marker = cm.TMP / "played"
    r = run_core(*game(marker, 7), "-novid", "+map", "x", kit=kit)
    cm.expect((r.returncode, marker.read_text()), (7, "-novid +map x"), "game with no modules")
    marker.unlink()
    fixture(kit, "broken", 'raise RuntimeError("hook broke")')
    fixture(kit, "good", f'Path({str(cm.TMP / "hooked")!r}).write_text(" ".join(argv[-2:]))')
    r = run_core(*game(marker), "-x", kit=kit)
    cm.expect((r.returncode, marker.read_text()), (0, "-x"), "game with a broken module")
    if "broken's launch step failed: RuntimeError: hook broke" not in r.stdout + r.stderr:
        cm.fail(f"the broken hook isn't logged: {r.stdout!r} {r.stderr!r}")
    cm.expect((cm.TMP / "hooked").read_text().endswith("-x"), True, "the good hook ran with the game's command")
    log = (cm.modules.data_dir() / "movement-kit.log").read_text()
    if "hook broke" not in log:
        cm.fail("movement-kit.log lacks the broken hook")


def check_run_script():
    folder = cm.TMP / "script"
    folder.mkdir()
    (folder / "helper.py").write_text("X = 5\n")
    (folder / "main.py").write_text("import sys, helper\nprint(sys.argv[1:], helper.X, __name__)\n")
    r = run_core("--run-script", folder / "main.py", "a", "b", kit=cm.TMP / "core-kit")
    cm.expect(r.stdout.strip(), "['a', 'b'] 5 __main__", "--run-script")


def check_modules_cli_and_migration():
    gh = cm.GitHub()
    gh.release("strafe-review-v9.0.0", "strafe-review-module.zip", cm.module_zip("strafe-review", "9.0.0"))
    api = gh.base + "/releases"
    kit = cm.TMP / "mig-kit"
    out = cm.TMP / "reply.json"
    state = cm.modules.data_dir() / "modules.json"
    state.unlink(missing_ok=True)

    # offline with an old Strafe Review folder: nothing installed, the game still runs, tried again later
    old = cm.modules.paths.data_dir("strafe-review")
    old.mkdir(parents=True)
    (old / "updates.json").write_text(json.dumps({"auto": True}))
    marker = cm.TMP / "mig-played"
    r = run_core(*game(marker), kit=kit)
    cm.expect((r.returncode, marker.exists()), (0, True), "game while the migration can't download")
    cm.expect((kit / "strafe-review").exists(), False, "no module installed offline")
    st = json.loads(state.read_text()) if state.is_file() else {}
    cm.expect(st.get("migrated-from-strafe-review"), None, "not marked done offline")

    r = run_core(*game(marker), kit=kit, api=api)
    cm.expect(r.returncode, 0, "game on the migrating start")
    cm.expect((kit / "strafe-review" / "module.json").is_file(), True, "Strafe Review module installed")
    st = json.loads(state.read_text())
    cm.expect((st["migrated-from-strafe-review"], st["modules"]["strafe-review"]["auto"]), (True, True),
              "marked done, old auto switch kept")
    calls = cm.calls()
    if "strafe-review-install-9.0.0" not in calls:
        cm.fail(f"the module's install hook didn't run: {calls}")

    # --modules: cards, auto-off, uninstall (data kept), and the migration doesn't come back
    r = run_core("--modules", out, "cards", kit=kit, api=api)
    reply = json.loads(out.read_text())
    cm.expect((r.returncode, reply["ok"]), (0, True), "--modules cards")
    cm.expect([c["key"] for c in reply["cards"] if c["installed"]], ["core", "strafe-review"], "installed cards")
    run_core("--modules", out, "auto-off", "strafe-review", kit=kit, api=api)
    cm.expect(json.loads(out.read_text())["cards"][1]["auto"], False, "--modules auto-off")
    r = run_core("--modules", out, "uninstall", "strafe-review", kit=kit, api=api)
    cm.expect((r.returncode, json.loads(out.read_text())["ok"]), (0, True), "--modules uninstall")
    run_core(*game(marker), kit=kit, api=api)
    cm.expect((kit / "strafe-review").exists(), False, "no second migration after an uninstall")
    r = run_core("--modules", out, "install", "nope", kit=kit, api=api)
    cm.expect((r.returncode, json.loads(out.read_text())["ok"]), (1, False), "--modules with a bad key")
    cm.calls()

    # no old folder: only marked done
    import shutil

    shutil.rmtree(old)
    state.unlink()
    run_core(*game(marker), kit=cm.TMP / "fresh-kit", api=api)
    st = json.loads(state.read_text())
    cm.expect((st.get("migrated-from-strafe-review"), st.get("modules", {})), (True, {}),
              "a fresh copy: marked done, nothing installed")


def main():
    check_launch()
    check_run_script()
    check_modules_cli_and_migration()
    import shutil

    shutil.rmtree(cm.TMP, ignore_errors=True)
    print("check_core: all passed")


if __name__ == "__main__":
    main()
