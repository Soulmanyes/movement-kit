// Checks the viewer's CS:S gain against a real server's SSJ: runs the shipped findJumps() / ssjJump() on a
// recording made from a CS:S demo (viewer/css_demo.py) and compares each jump with the [SSJ] chat line.
// Jumps are paired by takeoff speed (SSJ's "Speed:"), and a jump's gain is on the line after its own.
// Each jump is scored twice: with the demo's wish velocity (wx/wy) and without it (velocity + angles, as
// for Momentum recordings made before wishVel was saved).
//
//   node viewer/check_css_ssj.js OUT.json CONSOLE.txt
const fs = require('fs');
const data = require('./static/data.js');

const [file, consoleFile] = process.argv.slice(2);
if (!file || !consoleFile) {
	console.log('usage: node viewer/check_css_ssj.js OUT.json CONSOLE.txt');
	process.exit(1);
}
const lines = fs
	.readFileSync(consoleFile, 'utf8')
	.split('\n')
	.filter((l) => l.startsWith('[SSJ]'))
	.map((l) => {
		const g = (k) => {
			const m = l.match(new RegExp(`${k}: (-?[\\d.]+)`));
			return m ? +m[1] : null;
		};
		return { j: g('Jump'), speed: g('Speed'), gain: g('Gain') };
	});

function score(withWish) {
	const a = JSON.parse(fs.readFileSync(file));
	if (!withWish) {
		const keep = a.cols.indexOf('wx');
		a.cols = a.cols.slice(0, keep);
		a.rows = a.rows
			.split(';')
			.map((r) => r.split(',').slice(0, keep).join(','))
			.join(';');
	}
	const d = data.parse(a);
	return { d, jumps: data.findJumps(d, a.preRows).jumps };
}
const W = score(true);
const O = score(false);
// The console text can hold runs from before the demo started, and the demo can open while spectating
// someone else, so pairing is tried from every SSJ line and every jump; after the first pair a jump only
// pairs with one of the next 3 lines. The start that matches the most jumps wins.
function pair(start, first) {
	let used = start;
	const out = [];
	W.jumps.forEach((j, k) => {
		if (k < first) return;
		const sp = W.d.speed[j.s];
		const li = lines.findIndex((s, i) => i >= used && (!out.length || i <= used + 2) && s.speed !== null && Math.abs(s.speed - sp) <= 3);
		if (li < 0) return;
		used = li + 1;
		const nx = lines[li + 1];
		if (!nx || nx.j !== lines[li].j + 1 || nx.gain === null) return;
		const w = j.ssj;
		const o = O.jumps[k] ? O.jumps[k].ssj : NaN;
		// SSJ prints 2 decimals cut off, so 0.01 either way is a match
		out.push({ nx, sp, w, o, hitW: Math.abs(w - nx.gain) < 0.015, hitO: Math.abs(o - nx.gain) < 0.015 });
	});
	return out;
}
let best = [];
const hits = (q) => q.filter((r) => r.hitW).length * 1000 + q.length;
for (let s = 0; s < lines.length; s++) {
	for (let f = 0; f < W.jumps.length; f++) {
		const p = pair(s, f);
		if (hits(p) > hits(best)) best = p;
	}
}
const n = best.length;
let okW = 0;
let okO = 0;
for (const { nx, sp, w, o, hitW, hitO } of best) {
	okW += hitW;
	okO += hitO;
	console.log(
		`J:${nx.j} takeoff ${sp.toFixed(0)}  SSJ ${nx.gain.toFixed(2)}  wish ${w.toFixed(2)}${hitW ? '' : ' *'}  old ${o.toFixed(2)}${hitO ? '' : ' *'}`
	);
}
const fit = data.angleFit(O.d);
console.log(`matched to 0.01: wish ${okW}/${n}, old ${okO}/${n} (angle fit lag ${fit.lag}, err ${fit.err.toFixed(3)})`);
