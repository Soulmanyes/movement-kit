#!/usr/bin/env python3
"""Installs the Zone Exit Speed probe (Phase 10.1, throwaway) into Momentum Mod, or takes it out.

Usage: probe.py [--game DIR] [--uninstall]

custom/movekit-zone-exit-probe/panorama/scripts/hud/movekit-zone-exit-probe.ts, included from timer.xml
through the kit (tool "zone-exit-probe"). Type panorama_reload in game after installing.
--mounted puts the script into custom/movekit-jhud instead, which a running game has mounted already
(a new custom/ folder only mounts at game start). JHUD's launch hook wipes it at the next start.
"""
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from movekit import games, panorama, steam  # after the path above

FOLDER = "movekit-zone-exit-probe"
TOOL = "zone-exit-probe"
TS = "movekit-zone-exit-probe.ts"
PATCHES = [{"file": "panorama/layout/hud/timer.xml", "before": "</scripts>",
            "line": f'<include type="module" src="file://{{scripts}}/hud/{TS}" />'}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--mounted", action="store_true")
    a = ap.parse_args()
    game = Path(a.game) if a.game else steam.game_dir(games.MOMENTUM)
    if not game or not (game / "cfg").is_dir():
        sys.exit("Momentum's game folder not found")
    own = game / "custom" / FOLDER
    host = game / "custom" / "movekit-jhud"
    if a.uninstall:
        print(panorama.uninstall(game, FOLDER)["patches"])
        shutil.rmtree(own, ignore_errors=True)
        (host / "panorama" / "scripts" / "hud" / TS).unlink(missing_ok=True)
        return
    ts = (host if a.mounted else own) / "panorama" / "scripts" / "hud" / TS
    ts.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / TS, ts)
    result = panorama.install(game, FOLDER, TOOL, PATCHES)
    print(result["patches"], result["warnings"])


if __name__ == "__main__":
    main()
