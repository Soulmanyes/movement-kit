#!/usr/bin/env python3
"""Checks movekit/web/gain.js, the one copy of the gain curve (run with node), against values taken
from gain_converter.py, the tkinter window's Python copy, before Phase 3.8 retired it. A change to
the curve has to change these on purpose.

Usage: python gain-converter/check_gain.py   (needs node; exits 1 on a mismatch)
"""
import json
import subprocess
import sys
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "movekit" / "web" / "gain.js"
K = 1.45
MEASURED = [[71, 83], [77, 88], [79, 91], [88, 95]]
POINTS = [i * 2.5 for i in range(41)]  # 0, 2.5, ..., 100
# css_to_mom and mom_to_css at POINTS, rounded to 10 decimals
CSS_TO_MOM = [
    0.0, 3.6045150009, 7.1676749772, 10.6888847647, 14.1675244079, 17.6029474145, 20.9944788329,
    24.3414131307, 27.6430118459, 30.89850098, 34.1070680929, 37.2678590579, 40.3799744214,
    43.4424653039, 46.4543287663, 49.4145025485, 52.3218590656, 55.1751985237, 57.9732409817,
    60.7146171425, 63.3978576014, 66.0213802032, 68.5834750595, 71.0822866396, 73.5157921605,
    75.8817752327, 78.1777933396, 80.4011371667, 82.5487789622, 84.6173058186, 86.6028317183,
    88.5008788046, 90.3062125334, 92.0126048436, 93.6124792254, 95.0963493881, 96.4518661077,
    97.6620305503, 98.7013069802, 99.5246505316, 100.0,
]
MOM_TO_CSS = [
    0.0, 1.7309005045, 3.4756314593, 5.2346718391, 7.0085306621, 8.7977497669, 10.6029069309,
    12.4246193883, 14.263547808, 16.1204008121, 17.9959401249, 19.890986467, 21.8064263309,
    23.7432198054, 25.702409659, 27.6851319386, 29.6926284097, 31.7262612477, 33.787530505,
    35.8780950299, 37.9997977169, 40.1546962523, 42.3451009045, 44.5736214619, 46.8432262106,
    49.157316997, 51.5198261527, 53.9353436971, 56.4092873941, 58.9481349765, 61.5597491685,
    64.2538459346, 67.0426927234, 69.9421941475, 72.9736700077, 76.1669667263, 79.5664028214,
    83.243620735, 87.3311284156, 92.1452739907, 100.0,
]

script = f"""
const g = require({json.dumps(str(JS))});
const p = {json.dumps(POINTS)};
console.log(JSON.stringify({{K: g.K, MEASURED: g.MEASURED,
  c2m: p.map(g.cssToMom), m2c: p.map(g.momToCss)}}));
"""
js = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)

fails = []
if js["K"] != K:
    fails.append(f"K: js {js['K']}, expected {K}")
if js["MEASURED"] != MEASURED:
    fails.append(f"MEASURED: js {js['MEASURED']}, expected {MEASURED}")
for name, want in (("c2m", CSS_TO_MOM), ("m2c", MOM_TO_CSS)):
    worst = max(abs(a - b) for a, b in zip(js[name], want, strict=True))
    if worst > 1e-9:
        fails.append(f"{name}: off by {worst}")
for f in fails:
    print("FAIL:", f)
if fails:
    sys.exit(1)
print(f"gain.js matches the curve (K, measured points, {len(POINTS)} values each way)")
