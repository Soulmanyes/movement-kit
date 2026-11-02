#!/usr/bin/env python3
"""Checks that the two copies of the gain curve agree: movekit/web/gain.js (the hub section, run
with node) and gain_converter.py (the tkinter window, kept until Phase 3.8).

Usage: python gain-converter/check_gain.py   (needs node; exits 1 on a mismatch)
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gain_converter as py  # after the path above

JS = HERE.parent / "movekit" / "web" / "gain.js"
POINTS = [i / 4 for i in range(401)]
script = f"""
const g = require({json.dumps(str(JS))});
const p = {json.dumps(POINTS)};
console.log(JSON.stringify({{K: g.K, MEASURED: g.MEASURED,
  c2m: p.map(g.cssToMom), m2c: p.map(g.momToCss)}}));
"""
js = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)

fails = []
if js["K"] != py.K:
    fails.append(f"K: js {js['K']} py {py.K}")
if [tuple(m) for m in js["MEASURED"]] != py.MEASURED:
    fails.append(f"MEASURED: js {js['MEASURED']} py {py.MEASURED}")
for name, fn in (("c2m", py.css_to_mom), ("m2c", py.mom_to_css)):
    worst = max(abs(a - fn(p)) for a, p in zip(js[name], POINTS, strict=True))
    if worst > 1e-9:
        fails.append(f"{name}: off by {worst}")
for f in fails:
    print("FAIL:", f)
if fails:
    sys.exit(1)
print(f"gain.js and gain_converter.py agree (K, measured points, {len(POINTS)} values each way)")
