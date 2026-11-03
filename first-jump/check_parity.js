#!/usr/bin/env node
'use strict';
// Checks First Jump HUD's numbers (its TS port of the jump-1 stats) against Strafe Review's viewer code
// (strafe-review/viewer/static/data.js, checks.js, the drill page's per-strafe gain %), on the attempts
// Strafe Review saved. Needs the repo (both folders); a dev check, not shipped with either module.
//
//   node first-jump/check_parity.js [--store DIR]      feed every saved own attempt row by row through
//                                                     the HUD's code
//   node first-jump/check_parity.js --interval 0.015  the same, with every attempt taken as recorded at
//                                                     this tick interval (tickrate-scaled checks)
//   node first-jump/check_parity.js --log [yaw.log]    compare the lines the game logged: FJLINE (matched
//                                                     to a saved attempt by map and start time), and
//                                                     SRLINE from Strafe Review's recorder before 1.9.0
//
// Prints one line per attempt and a mismatch count; exits 1 if anything differs.

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const vm = require('vm');
const { stripTypeScriptTypes } = require('module');

const data = require('../strafe-review/viewer/static/data.js');
Object.assign(globalThis, data);
const { runChecks, strafesOf, strafeCause, strafing } = require('../strafe-review/viewer/static/checks.js');

const args = process.argv.slice(2);
const at = args.indexOf('--store');
const store = at >= 0 ? args[at + 1] : path.join(process.env.HOME, '.local/share/strafe-review/attempts');
const iv = args.indexOf('--interval');
const forceInterval = iv >= 0 ? +args[iv + 1] : null;
const GAME = path.join(process.env.HOME, '.local/share/Steam/steamapps/common/Momentum Mod Playtest/momentum');
const HUD = path.join(__dirname, 'panorama/scripts/hud/movekit-first-jump.ts');
const DELAY = 3; // LINE_DELAY_ROWS in the HUD script

const files = new Map();
for (const m of fs.readdirSync(store)) {
	const dir = path.join(store, m);
	if (!fs.statSync(dir).isDirectory()) continue;
	for (const f of fs.readdirSync(dir)) if (f.endsWith('.json.gz')) files.set(f.slice(0, -8), path.join(dir, f));
}
const load = (f) => JSON.parse(zlib.gunzipSync(fs.readFileSync(f)).toString());

// The viewer's numbers for jump 1, rounded as the HUD logs them
function viewer(a) {
	const d = data.parse(a);
	const { jumps } = data.findJumps(d, a.preRows);
	const endIdx = a.postRows ? d.n - 1 - a.postRows : d.n - 1;
	const j = jumps.find((x) => x.num === 1);
	if (!j || j.e > endIdx || j.e >= d.n) return null;
	const sts = strafesOf(d, j, endIdx);
	const causes = sts.map((st) => {
		const c = strafeCause(d, st);
		return c ? [c.cause, c.ticks] : null;
	});
	const strafes = sts.map((st) => {
		let g = 0;
		let id = 0;
		for (let i = st.i0; i <= st.i1; i++) {
			if (strafing(d, i) && Number.isFinite(d.gain[i]) && Number.isFinite(d.ideal[i])) {
				g += d.gain[i];
				id += d.ideal[i];
			}
		}
		return [st.dir, id > 0 ? +((100 * g) / id).toFixed(3) : null];
	});
	const off = { takeoff: { on: false }, balance: { on: false } };
	const mistakes = runChecks(d, jumps, endIdx, off, null, false)
		.filter((m) => m.jump === 1)
		.map((m) => [m.check, m.i0, +m.lost.toFixed(3)]);
	return { s: j.s, e: j.e, land: +j.land.toFixed(3), pct: +j.pct.toFixed(3), strafes, causes, mistakes };
}

// The HUD script run with stub Panorama APIs; returns a function working out one attempt's line
function hudLine() {
	const msgs = [];
	const stub = new Proxy({}, { get: () => () => ({ state: 0, x: 0, y: 0, z: 0 }) });
	const ctx = {
		$: {
			Msg: (t) => msgs.push(t),
			Schedule: () => 0,
			RegisterForUnhandledEvent: () => 0,
			GetContextPanel: () => ({ GetParent: () => null, FindChildTraverse: () => null }),
			// any panel method is a no-op that answers true
			CreatePanel: () => new Proxy({}, { get: (_, k) => (k === 'visible' ? true : () => true) })
		},
		MomentumMovementAPI: { GetTickInterval: () => 0.01 },
		MomentumTimerAPI: stub,
		MomentumPlayerAPI: stub,
		MomentumInputAPI: stub,
		MomentumReplayAPI: stub,
		MapCacheAPI: stub,
		GameModeAPI: stub,
		UiToolkitAPI: { GetGlobalObject: () => ({}) },
		Math,
		JSON,
		Number,
		Date
	};
	vm.createContext(ctx);
	const src = stripTypeScriptTypes(fs.readFileSync(HUD, 'utf8'), { mode: 'strip' });
	// Rows go in one at a time through lineStep(), as in the game, so the landing trigger is tested too
	vm.runInContext(`${src}\nglobalThis.__step = (a, row) => { attempt = a; a.rows.push(row); lineStep(); };\nglobalThis.__interval = (v) => { interval = v; };`, ctx);
	return (id, rows, preRows, iv) => {
		msgs.length = 0;
		ctx.__interval(iv);
		const a = { started: 0, rows: [], preRows, endRows: -1, untilTick: 0, untilMs: 0, seen: 0, at: -1 };
		for (const row of rows) {
			ctx.__step(a, row);
			if (msgs.length) break;
		}
		const m = msgs.find((t) => t.startsWith('FJLINE '));
		return m ? { at: a.rows.length, ...JSON.parse(m.slice(m.indexOf('{'))) } : null;
	};
}

// Round-trips through JSON so NaN reads as null on both sides
const same = (x, y) => JSON.stringify(x) === JSON.stringify(y);

function diff(id, got, want) {
	const bad = [];
	// causes: SRLINE lines logged before the recorder had them don't carry the field
	for (const k of ['s', 'e', 'land', 'pct', 'strafes', 'causes', 'mistakes']) if ((k !== 'causes' || k in got) && !same(got[k], want[k])) bad.push(`${k}: game ${JSON.stringify(got[k])} viewer ${JSON.stringify(want[k])}`);
	const top = want.mistakes[0];
	console.log(
		`${bad.length ? 'DIFF' : 'ok  '} ${id} land ${want.land.toFixed(1)} gain ${want.pct.toFixed(2)} % strafes ${want.strafes.length} top ${top ? `${top[0]} -${top[2].toFixed(1)}` : '-'}`
	);
	for (const b of bad) console.log(`     ${b}`);
	return bad.length > 0;
}

// The saved own attempt on this map that started within START_MS of an FJLINE's start time (the HUD and
// Strafe Review's recorder both take Date.now() at the timer start), or undefined
const START_MS = 1000;
let starts = null;
function byStart(started, map) {
	if (!starts) {
		starts = [];
		for (const f of files.values()) {
			const a = load(f);
			if (a.label === 'own') starts.push({ started: a.started, map: a.map, f });
		}
	}
	const hit = starts.find((s) => s.map === map && Math.abs(s.started - started) <= START_MS);
	return hit && hit.f;
}

let checked = 0;
let bad = 0;
if (args.includes('--log')) {
	const li = args.indexOf('--log');
	const log = args[li + 1] && !args[li + 1].startsWith('--') ? args[li + 1] : path.join(GAME, 'yaw.log');
	for (const ln of fs.readFileSync(log, 'latin1').split('\n')) {
		const m = ln.match(/(SRLINE|FJLINE) (\S+) (\{.*\})/);
		if (!m) continue;
		const got = JSON.parse(m[3]);
		const f = m[1] === 'SRLINE' ? files.get(m[2]) : byStart(+m[2], got.map);
		if (!f) {
			console.log(`skip ${m[2]}: not saved (yet)`);
			continue;
		}
		const want = viewer(load(f));
		if (!want) {
			console.log(`skip ${m[2]}: viewer finds no landed jump 1`);
			continue;
		}
		checked++;
		if (diff(m[2], got, want)) bad++;
	}
} else {
	const work = hudLine();
	for (const [id, f] of files) {
		const a = load(f);
		if (a.label !== 'own') continue;
		if (forceInterval) a.interval = forceInterval;
		const want = viewer(a);
		// parse() relabels old spectated recordings as 'spectate'
		if (!want || a.label !== 'own') continue;
		const got = work(id, a.rows.split(';'), a.preRows, a.interval);
		checked++;
		if (!got) {
			console.log(`DIFF ${id}: the HUD shows no line`);
			bad++;
		} else if (diff(id, got, want)) bad++;
		else if (got.at !== want.e + 1 + DELAY) {
			console.log(`     shown at row ${got.at}, landing row ${want.e} (expected ${want.e + 1 + DELAY})`);
			bad++;
		}
	}
}
console.log(`${checked} checked, ${bad} differ`);
process.exit(bad ? 1 : 0);
