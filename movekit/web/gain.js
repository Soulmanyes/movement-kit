// CS:S (SSJ) gain % <-> Momentum Mod gain %: the one copy of the curve for every web page (the hub's
// Gain Converter section, later the viewer). Momentum = 1 - (1 - CS:S) ** K, fitted to runs measured
// both ways with Strafe Review. gain-converter/gain_converter.py keeps a Python copy for the old
// tkinter window until Phase 3.8 retires it; gain-converter/check_gain.py keeps the two equal.
"use strict";

const gain = (() => {
	const K = 1.45; // each measured pair gives K between 1.41 and 1.54
	// [CS:S %, Momentum %]: ends of the measured ranges (finished bhop_ambience runs, top replays)
	const MEASURED = [[71, 83], [77, 88], [79, 91], [88, 95]];
	const cssToMom = (c) => 100 * (1 - (1 - c / 100) ** K);
	const momToCss = (m) => 100 * (1 - (1 - m / 100) ** (1 / K));
	return { K, MEASURED, cssToMom, momToCss };
})();

if (typeof module !== "undefined") module.exports = gain;
