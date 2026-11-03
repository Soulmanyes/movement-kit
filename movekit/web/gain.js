// CS:S (SSJ) gain % <-> Momentum Mod gain %: the one copy of the curve for every web page (the hub's
// Gain Converter section, later the viewer). Momentum = 1 - (1 - CS:S) ** K, fitted to jumps measured
// both ways with Strafe Review (about 10,000 single jumps, 2026-11-03). The tkinter window's Python
// copy went with it in Phase 3.8; gain-converter/check_gain.py checks this one against values taken from it.
"use strict";

const gain = (() => {
	const K = 1.45; // each measured pair gives K between 1.41 and 1.54
	const cssToMom = (c) => 100 * (1 - (1 - c / 100) ** K);
	const momToCss = (m) => 100 * (1 - (1 - m / 100) ** (1 / K));
	return { K, cssToMom, momToCss };
})();

if (typeof module !== "undefined") module.exports = gain;
