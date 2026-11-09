"""Checks the dev kit (movekit/movekit-dev, movekit/devkit.py) in a temporary HOME: setup seeds
from a fake installed kit, links the Vulkan layers but the kit's own, writes only inside the dev
root (plus its app menu entry), and installing a module registers its hook there, never in the
installed kit's hooks or ~/.local/bin. Linux only. Run: python3 movekit/check_devkit.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parent.parent
DEV = CHECKOUT / "movekit" / "movekit-dev"
failed = False


def check(name, got, want):
    global failed
    if got == want:
        print(f"ok   {name}")
    else:
        failed = True
        print(f"FAIL {name}: got {got!r}, want {want!r}")


def files(top):
    return sorted(str(p.relative_to(top)) for p in top.rglob("*") if not p.is_dir() or p.is_symlink())


def check_steam(tmp):
    """devsteam: launch prefixes, and the library entries in a shortcuts.vdf that has another game."""
    sys.path.insert(0, str(CHECKOUT))
    from movekit import devsteam

    check("prefix: movekit-run taken out",
          devsteam.launch_prefix("A=1 game-performance movekit-run %command% -novid"), ("A=1 game-performance", "-novid"))
    check("prefix: full-path and old wrapper names too",
          devsteam.launch_prefix("/x/movekit-run sourceyaw-run %command%"), ("", ""))
    check("prefix: no %command% means game arguments", devsteam.launch_prefix("-novid"), ("", "-novid"))
    other = {"appid": (2, 2585635855), "AppName": "BHOP", "Exe": '"/g/BHOP"', "LaunchOptions": "x %command%",
             "LastPlayTime": (2, 5), "tags": {"0": "fav"}}
    config = tmp / "steam" / "config"
    config.mkdir(parents=True)
    vdf = config / "shortcuts.vdf"
    original = devsteam.write_kv({"shortcuts": {"0": other}})
    vdf.write_bytes(original)
    check("binary KeyValues round trip", devsteam.write_kv(devsteam.read_kv(original)[0]), original)
    wanted = {"css": "A=1 movekit-run %command%", "momentum": ""}
    devsteam.add_entries([config], wanted, today="2026-01-01", log=lambda _: None)
    items = list(devsteam.read_kv(vdf.read_bytes())[0]["shortcuts"].values())
    check("other entries kept, dev entries added", [i["AppName"] for i in items],
          ["BHOP", "Counter-Strike: Source (dev kit)", "Momentum Mod (dev kit)"])
    check("other entry unchanged", items[0], other)
    check("dev entry runs movekit-dev game", items[1]["LaunchOptions"], "A=1 %command% game css")
    check("dev entry id in the non-Steam range", items[1]["appid"][1] >= 0x80000000, True)
    check("backup of the file before", (config / "shortcuts.vdf.bak-2026-01-01").read_bytes(), original)
    first = vdf.read_bytes()
    devsteam.add_entries([config], wanted, today="2026-01-02", log=lambda _: None)
    check("second run: same file, no new backup",
          (vdf.read_bytes() == first, (config / "shortcuts.vdf.bak-2026-01-02").exists()), (True, False))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        home, live = Path(tmp) / "home", Path(tmp) / "live"
        (home / ".config").mkdir(parents=True)
        # the installed kit: state, one hook, a module with no game side, Vulkan layers
        (live / "movekit" / "hooks").mkdir(parents=True)
        (live / "movekit" / "hooks" / "20-x").symlink_to("/nowhere")
        (live / "movekit" / "modules.json").write_text(json.dumps({"modules": {"gain-converter": {"seen": "1.0.0"}}}))
        (live / "movekit" / "binds.json").write_text("{}")
        (live / "movekit" / "modules.lock").write_text("")
        kit_mod = live / "movekit" / "kit" / "gain-converter"
        kit_mod.mkdir(parents=True)
        (kit_mod / "module.json").write_text((CHECKOUT / "gain-converter" / "module.json").read_text())
        layers = live / "vulkan" / "implicit_layer.d"
        layers.mkdir(parents=True)
        for name in ("steamoverlay_x86_64.json", "sourceyaw-overlay.json"):
            (layers / name).write_text("{}")
        before = files(live)

        env = {"PATH": os.environ["PATH"], "HOME": str(home), "MOVEKIT_LIVE_DATA": str(live),
               "XDG_CONFIG_HOME": str(home / ".config")}
        run = subprocess.run([DEV, "setup"], env=env, capture_output=True, text=True, check=False)
        check("setup runs", (run.returncode, run.stderr.strip()), (0, ""))
        root = home / ".local/share/movekit-dev"
        data = root / "data"
        check("installed kit untouched but the app entry",
              sorted(set(files(live)) - set(before)), ["applications/io.github.soulmanyes.MovementKit.Dev.desktop"])
        check("nothing outside the dev root and the shared settings",
              sorted({p.split("/")[0] + "/" + p.split("/")[1] for p in files(home) if p.count("/") >= 1}
                     - {".local/share"}), [])
        # the dev manager makes its own modules.lock; hooks/ only once something registers
        check("state seeded without kit, rollback copies or the installed kit's files",
              sorted({p.name for p in (data / "movekit").iterdir()} - {"modules.lock", "hooks"}),
              ["binds.json", "modules.json"])
        check("live hook not copied", (data / "movekit" / "hooks" / "20-x").exists(), False)
        check("Vulkan: Steam's layer linked, the kit's own left out",
              sorted(p.name for p in (data / "vulkan" / "implicit_layer.d").iterdir()), ["steamoverlay_x86_64.json"])
        state = json.loads((data / "movekit" / "modules.json").read_text())["modules"]
        check("gain-converter installed in the dev state", state.get("gain-converter", {}).get("removed"), None)
        check("other checkout modules hidden", state.get("sourceyaw", {}).get("removed"), True)
        check("seen kept from the installed kit", state["gain-converter"].get("seen"), "1.0.0")
        envout = subprocess.run([DEV, "env"], env=env, capture_output=True, text=True, check=False).stdout
        check("env: dev data home", f"XDG_DATA_HOME={data}" in envout, True)
        check("env: dev bin dir", f"MOVEKIT_BIN_DIR={root / 'bin'}" in envout, True)

        # the launch wrapper's link and a hook go to the dev tree, through launch.py in dev env
        denv = dict(env, MOVEKIT_DEV="1", MOVEKIT_DEV_ROOT=str(root), MOVEKIT_BIN_DIR=str(root / "bin"),
                    XDG_DATA_HOME=str(data), XDG_STATE_HOME=str(root / "state"), XDG_CACHE_HOME=str(root / "cache"))
        hook = Path(tmp) / "hook.sh"
        hook.write_text("true\n")
        subprocess.run([sys.executable, CHECKOUT / "movekit" / "launch.py", "register", "devcheck", "90", hook],
                       env=denv, check=True, capture_output=True)
        check("hook registered in the dev tree", (data / "movekit" / "hooks" / "90-devcheck").is_symlink(), True)
        check("movekit-run linked in the dev bin", (root / "bin" / "movekit-run").resolve(),
              CHECKOUT / "movekit" / "movekit-run")
        check("no ~/.local/bin", (home / ".local/bin").exists(), False)
        check("installed kit still untouched", sorted(set(files(live)) - set(before)),
              ["applications/io.github.soulmanyes.MovementKit.Dev.desktop"])
        check_steam(Path(tmp))
    print("dev kit checks failed" if failed else "all dev kit checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
