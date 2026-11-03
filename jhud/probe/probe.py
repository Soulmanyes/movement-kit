#!/usr/bin/env python3
"""Installs the JHUD probe (Phase 5.1, throwaway) into Momentum Mod, or takes it out.

Usage: probe.py [--game DIR] [--uninstall]

- custom/movekit-jhud-probe/panorama/scripts/hud/movekit-jhud-probe.ts, included from timer.xml through
  the kit (tool "jhud-probe").
- custom/movekit-jhud-probe/cfg/hud/hud_default.kv3: a copy of the game's file with a MovekitJhud entry,
  to see whether the HUD customizer reads it from custom/. The kit can't patch cfg/ yet (5.2).
"""
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from movekit import games, panorama, steam  # after the path above

FOLDER = "movekit-jhud-probe"
TOOL = "jhud-probe"
TS = "movekit-jhud-probe.ts"
PATCHES = [{"file": "panorama/layout/hud/timer.xml", "before": "</scripts>",
            "line": f'<include type="module" src="file://{{scripts}}/hud/{TS}" />'}]
ANCHOR = "    CustomizerSettings = "
ENTRY = """    MovekitJhud = 
    {
        enabled = true
        offsetX = 810
        offsetY = 620
        width = 300
        dynamicStyles = 
        {
            fontColor = "$fontColor"
            gainGreen = 95
        }
    }
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    game = Path(a.game) if a.game else steam.game_dir(games.MOMENTUM)
    if not game or not (game / "cfg" / "hud" / "hud_default.kv3").is_file():
        sys.exit("Momentum's game folder not found")
    own = game / "custom" / FOLDER
    if a.uninstall:
        print(panorama.uninstall(game, FOLDER)["patches"])
        shutil.rmtree(own, ignore_errors=True)
        return
    kv3 = (game / "cfg" / "hud" / "hud_default.kv3").read_text(encoding="utf-8")
    if kv3.count(ANCHOR) != 1:
        sys.exit("hud_default.kv3: anchor not found once")
    ts = own / "panorama" / "scripts" / "hud" / TS
    ts.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / TS, ts)
    out = own / "cfg" / "hud" / "hud_default.kv3"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(kv3.replace(ANCHOR, ENTRY + ANCHOR), encoding="utf-8")
    result = panorama.install(game, FOLDER, TOOL, PATCHES)
    print(result["patches"], result["warnings"])


if __name__ == "__main__":
    main()
