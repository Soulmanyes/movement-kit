#!/usr/bin/env node
// Checks strafe-histogram/panorama/scripts/hud/movekit-strafe-histogram.ts in node, with Panorama stubbed
// (types stripped, as jhud/check_jhud.js does).
//
// Usage: node strafe-histogram/check_strafe_histogram.js [--store DIR] [--max N]   (exits 1 on the first failure)
//
// Covers: the customizer settings (every STYLES row has a DEFAULTS value and sits in one group) against
// install.py's hud_default.kv3 entry; bars (edges, which bar a ratio goes in, heights, colours, the band
// line); the window (keeps the last N counted ticks, band share inclusive at 0.85 and 1.15); the tick rule
// on made-up rows (strafe ends skipped, +left/+right, gaps, collisions, slow ticks, ground, a tick seen over
// several frames counted once); the Panorama side (customizer component for bhop modes only, sample while
// it is open, nothing while spectating, a replay or in another mode, the panel taken over after
// panorama_reload and the old copy's loop stopping); then every own attempt in Strafe Review's store (--store,
// default ~/.local/share/strafe-review/attempts; skipped when missing): the ticks the HUD counts, fed one at a
// time, are exactly the viewer's strafe-middle ticks (checks.js strafesOf + interior, skip 2), and the in-band
// share is the same. Surf maps are skipped (surf modes don't show it).
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const zlib = require('zlib');
const { stripTypeScriptTypes } = require('module');

const TS = path.join(__dirname, 'panorama/scripts/hud/movekit-strafe-histogram.ts');
const INSTALL = path.join(__dirname, 'install.py');
const VIEWER = path.join(__dirname, '..', 'strafe-review', 'viewer', 'static');
const args = process.argv.slice(2);
const opt = (name, dflt) => (args.indexOf(name) >= 0 ? args[args.indexOf(name) + 1] : dflt);
const store = opt('--store', path.join(process.env.HOME || '', '.local/share/strafe-review/attempts'));
const maxFiles = +opt('--max', 'Infinity');

function fail(msg) {
	console.error('FAIL: ' + msg);
	process.exit(1);
}
function expect(got, want, what) {
	const g = JSON.stringify(got);
	const w = JSON.stringify(want);
	if (g !== w) fail(`${what}:\n got  ${g}\n want ${w}`);
}

// ---- Panorama stubs ----
class FakePanel {
	constructor(type, parent, id, props) {
		this.type = type;
		this.paneltype = type;
		this.id = id;
		this.text = props && props.text;
		this.styleText = (props && props.style) || '';
		this.style = {};
		this.children = [];
		this.visible = true;
		this.enabled = true;
		this.valid = true;
		this.parent = parent;
		if (parent) parent.children.push(this);
	}
	IsValid() { return this.valid; }
	GetChildCount() { return this.children.length; }
	GetChild(i) { return this.children[i] || null; }
	GetParent() { return this.parent; }
	FindChildTraverse(id) {
		for (const c of this.children) {
			if (c.id === id) return c;
			const f = c.FindChildTraverse(id);
			if (f) return f;
		}
		return null;
	}
	RemoveAndDeleteChildren() { this.children = []; }
}
const hud = new FakePanel('Hud', null, 'Hud');
const timer = new FakePanel('MomHudTimer', hud, 'Timer');
const handlers = {};
let schedules = [];
let mode = 2;
let moveType = 2;
let replayState = 0;
let time = 0;
let tickStats = { speedGain: 0, idealGain: 0, yawRatio: 0, strafeRight: 0 };
let vel = { x: 0, y: 0, z: 0 };
let yaw = 0;
let buttons = 0;
let loaded = null;
let loads = 0;
const GLOBAL = { HudCustomizerHandler: { customizerReady: false, loadComponent: (p, props) => { loaded = { p, props }; loads++; } } };
const stubs = {
	$: {
		GetContextPanel: () => timer,
		CreatePanel: (type, parent, id, props) => new FakePanel(type, parent, id, props),
		RegisterForUnhandledEvent: (ev, fn) => { (handlers[ev] = handlers[ev] || []).push(fn); },
		Schedule: (s, fn) => { schedules.push({ s, fn }); },
		Msg: () => {}
	},
	GameModeAPI: { GetCurrentGameMode: () => mode },
	MomentumMovementAPI: {
		GetLastTickStats: () => tickStats,
		GetCurrentTime: () => time,
		GetTickInterval: () => 0.01,
		GetMoveType: () => moveType
	},
	MomentumPlayerAPI: { GetVelocity: () => vel, GetAngles: () => ({ x: 0, y: yaw, z: 0 }) },
	MomentumInputAPI: { GetButtons: () => ({ physicalButtons: buttons }) },
	MomentumReplayAPI: { GetReplayState: () => replayState },
	UiToolkitAPI: { GetGlobalObject: () => GLOBAL },
	Date: { now: () => time * 1000 },
	console
};
const src = stripTypeScriptTypes(fs.readFileSync(TS, 'utf8'), { mode: 'strip' });
function loadScript() {
	const ctx = { ...stubs };
	vm.createContext(ctx);
	vm.runInContext(`${src}
globalThis.__api = { DEFAULTS, STYLES, SAMPLE, NONE, BAND_LO, BAND_HI, middles, Middles, Window, edges, barOf, windowTicks,
	barColors, heights, bandText, mixColor, settings, getWin: () => win };`, ctx);
	return ctx.__api;
}
const api = loadScript();
const fire = (ev) => (handlers[ev] || []).forEach((fn) => fn());
// runs the scheduled callbacks once (one frame); returns the delays they were scheduled with
const frame = () => { const s = schedules; schedules = []; s.forEach((x) => x.fn()); return s.map((x) => x.s); };

// ---- settings against install.py's kv3 entry ----
const ids = api.STYLES.filter((r) => r[2] !== api.NONE).map((r) => r[0]);
expect([...ids].sort(), Object.keys(api.DEFAULTS).sort(), 'every setting row has a default and back');
const grouped = api.STYLES.flatMap((r) => r[3] || []);
expect([...grouped].sort(), [...ids].sort(), 'every setting sits under exactly one row');
const py = fs.readFileSync(INSTALL, 'utf8');
const entry = /ENTRY = """([\s\S]*?)"""/.exec(py);
if (!entry) fail('ENTRY not found in install.py');
const dyn = /dynamicStyles = \s*\{([\s\S]*?)\}/.exec(entry[1]);
const kv = {};
for (const m of dyn[1].matchAll(/^\s*(\w+) = (.+?)\s*$/gm)) {
	const v = m[2];
	kv[m[1]] = v === 'true' ? true : v === 'false' ? false : /^"/.test(v) ? v.slice(1, -1) : Number(v);
}
expect(kv, Object.fromEntries(Object.keys(kv).map((k) => [k, api.DEFAULTS[k]])), 'kv3 values = DEFAULTS');
expect(Object.keys(kv).sort(), Object.keys(api.DEFAULTS).sort(), 'kv3 keys = DEFAULTS keys');
if (!/^    MovekitStrafeHist = \n/.test(entry[1])) fail('kv3 entry is not for the panel id MovekitStrafeHist');
for (const [id, , type, , extra] of api.STYLES) {
	if (type !== 1) continue;
	if (!extra || !extra.range) fail(`number box ${id} has no range`);
	if (!(extra.range.min <= api.DEFAULTS[id] && api.DEFAULTS[id] <= extra.range.max)) fail(`${id}'s default is outside its range`);
}

// ---- bars ----
const S = { ...api.DEFAULTS, fontColor: 'rgba(255, 255, 255, 1)' };
const E = api.edges(S);
expect([E.lo, E.hi, E.bars], [0.4, 1.6, 14], 'default bars: 0.4 to 1.6, 12 inner + 2 ends');
expect([-2, 0, 0.39, 0.4, 0.49, 0.5, 0.85, 0.99, 1.0, 1.59, 1.6, 9].map((r) => api.barOf(r, E)),
	[0, 0, 0, 1, 1, 2, 5, 6, 7, 12, 13, 13], 'which bar a ratio goes in');
expect(api.barOf(0.7, E), 4, 'a ratio on an inner edge goes in the bar above it (0.7: 0.7-0.8)');
expect(api.edges({ ...S, lowPct: 160, highPct: 40 }).bars, 3, 'from above to: one inner bar');
expect(api.edges({ ...S, stepPct: 0 }).bars, 14, 'bar width 0 counts as 10');
expect(api.heights([0, 5, 10, 2], S), [0, 30, 60, 12], 'heights: the tallest bar is barHeight');
expect(api.heights([0, 0], S), [0, 0], 'heights with nothing counted');
expect(new Set(api.barColors(S)).size, 1, 'plain: one colour');
expect(api.barColors(S)[0], S.barColor, 'plain: the bar colour');
const good = api.barColors({ ...S, colorBy: 'good' });
expect(good.length, 14, 'one colour per bar');
expect([good[6], good[7]], [api.mixColor(S.goodColor, S.badColor, 0.1), api.mixColor(S.goodColor, S.badColor, 0.1)],
	'how good: the two bars next to 1.0 alike, near good');
expect([good[0], good[13], good[1]], [S.badColor, S.badColor, api.mixColor(S.goodColor, S.badColor, 0.55 / 0.5)],
	'how good: far bars fully bad');
expect(good[3] === good[10], true, 'how good: both sides alike');
expect(api.bandText(61.6, S), 'in band 62 %', 'band line');
expect(api.bandText(NaN, S), '', 'no band line with nothing counted');
expect(api.bandText(50, { ...S, showBand: false }), '', 'band line off');

// ---- window ----
const w = new api.Window(4);
[0.1, 0.85, 1.15, 1.16, 0.849, 1].forEach((r) => w.add(r));
expect(w.ratios, [1.15, 1.16, 0.849, 1], 'the window keeps the last ticks');
expect(w.band(), 50, 'band: 0.85 to 1.15, both ends in');
const wb = new api.Window(10);
[0.85, 1.15].forEach((r) => wb.add(r));
expect(wb.band(), 100, 'band edges count as in band');
w.resize(2);
expect(w.ratios, [0.849, 1], 'a smaller window drops the oldest');
expect(new api.Window(4).band(), NaN, 'empty window: no band');
expect(api.windowTicks(3, 0.01), 300, '3 s at 100 tick');
expect(api.windowTicks(3, 1 / 66), 198, '3 s at 66 tick');
const cnt = new api.Window(10);
[0.3, 0.95, 0.95, 2].forEach((r) => cnt.add(r));
expect(cnt.counts(E), [1, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 1], 'counts per bar');

// ---- the tick rule on made-up rows ----
// A jump: takeoff vz 290, then air falling by 8 a tick, turning `turn` degrees a tick (left, then right)
function jump(t0, n, opts = {}) {
	const out = [{ tick: t0 - 1, ratio: 0, gain: 0, buttons: 0, vx: 300, vy: 0, vz: 0, yaw: 0 }];
	let y = 0;
	for (let i = 0; i < n; i++) {
		const left = i < n / 2;
		y += left ? 1 : -1;
		out.push({ tick: t0 + i, ratio: 0.9 + i / 1000, gain: 1, buttons: left ? 1 << 9 : 1 << 10, vx: 300 + i, vy: 0, vz: 290 - 8 * i, yaw: y });
	}
	out.push({ tick: t0 + n, ratio: 0, gain: 0, buttons: 0, vx: 300, vy: 0, vz: 0, yaw: y }); // ground
	out.push({ tick: t0 + n + 1, ratio: 0, gain: 0, buttons: 0, vx: 300, vy: 0, vz: 0, yaw: y });
	out.push({ tick: t0 + n + 2, ratio: 0, gain: 0, buttons: 0, vx: 300, vy: 0, vz: 0, yaw: y });
	return out;
}
const counted = (rows) => {
	const m = new api.Middles();
	const got = [];
	for (const r of rows) got.push(...m.push(r).map((x) => x.ratio));
	return got;
};
const j = jump(100, 20);
const all = counted(j).map((r) => Math.round((r - 0.9) * 1000)); // back to the air row number
// Keys turn left on rows 0-9, right on 10-19. The 5-tick yaw average is under 0.3 on rows 9 and 10 (0.2 and
// -0.2), so the strafes are rows 0-8 and 11-19, and their middles (2 skipped at each end) 2-6 and 13-17.
expect(all, [2, 3, 4, 5, 6, 13, 14, 15, 16, 17], 'a two-strafe jump: ends skipped');
const batch = api.middles(j).idx.map((i) => j[i].tick - 100);
expect(batch, all, 'the stream counts what the whole rows give');
const lr = j.map((r, i) => (i === 5 ? { ...r, buttons: r.buttons | (1 << 7) } : r));
expect(counted(lr).length, 9, '+left tick left out');
const hit = j.map((r, i) => (i === 6 ? { ...r, gain: -12 } : r));
expect(counted(hit).length, 9, 'a wall hit (gain under -10) left out');
const slow = j.map((r, i) => (i === 4 ? { ...r, vx: 90 } : r));
expect(counted(slow).length, 9, 'a tick under 100 u/s left out');
const gapped = j.filter((r, i) => i !== 5);
expect(counted(gapped).includes(j[6].ratio), false, 'the row after a missed tick left out');
const noTake = j.map((r) => ({ ...r, vz: r.vz > 100 ? 99 : r.vz }));
expect(counted(noTake), [], 'no takeoff: no jump, nothing counted');
const twice = counted([...jump(100, 20), ...jump(200, 20)]);
expect(twice.length, 20, 'two jumps');
// the stream on the jump with the end not seen yet: the last strafe's ticks wait for two more rows
const m = new api.Middles();
let got = [];
for (const r of j.slice(0, 16)) got.push(...m.push(r));
expect(got.length < 10, true, 'not everything counted before the jump ends');
for (const r of j.slice(16)) got.push(...m.push(r));
expect(got.length, 10, 'the rest once it ends');

// ---- Panorama ----
expect(loaded, null, 'not registered before the customizer is ready');
fire('HudCustomizer_Ready');
expect(loads, 1, 'registered at HudCustomizer_Ready');
expect(loaded.props.gamemode, [2, 3], 'bhop modes only');
expect(loaded.props.name, 'Strafe Speed Histogram', 'component name');
const P = loaded.p;
expect(P.id, 'MovekitStrafeHist', 'panel id');
expect(P.visible, false, 'hidden before any strafing');
fire('HudCustomizer_Opened');
expect(P.visible, true, 'sample while the customizer is open');
expect(P.children[0].children.length, 14, 'sample: 14 bars');
expect(P.children[1].text.startsWith('in band '), true, 'sample: band line');
fire('HudCustomizer_Closed');
expect(P.visible, false, 'hidden when the customizer closes, with nothing counted');
// play the made-up jump through the stubs: three frames per tick, the same values each time
function play(rows, frames = 3) {
	for (const r of rows) {
		time = r.tick * 0.01 + 0.001;
		tickStats = { speedGain: r.gain, idealGain: 1, yawRatio: r.ratio, strafeRight: 0 };
		vel = { x: r.vx, y: r.vy, z: r.vz };
		yaw = r.yaw;
		buttons = r.buttons;
		for (let f = 0; f < frames; f++) {
			frame();
			time += 0.002;
		}
	}
}
// a distinct row before the jump, so its first row is a new key (the ground rows repeat)
play([{ tick: 98, ratio: 0, gain: 0, buttons: 0, vx: 1, vy: 0, vz: 0, yaw: 0 }, ...jump(100, 20), { tick: 124, ratio: 0, gain: 0, buttons: 0, vx: 2, vy: 0, vz: 0, yaw: 0 }]);
expect(api.getWin().ratios.length, 10, 'in game: each tick counted once over three frames');
for (let f = 0; f < 5; f++) { time += 0.06; frame(); }
expect(P.visible, true, 'shown after strafing');
expect(P.children[0].children.length, 14, '14 bars');
expect(P.children[1].text, 'in band 100 %', 'band line in game');
// standing still: nothing new, the bars stay
for (let f = 0; f < 20; f++) { time += 0.01; frame(); }
expect([P.visible, api.getWin().ratios.length], [true, 10], 'standing still: the bars stay');
mode = 1;
frame();
expect(P.visible, false, 'another mode: hidden');
mode = 2;
replayState = 1;
frame();
expect(P.visible, false, 'watching a replay: hidden');
play([{ tick: 198, ratio: 0, gain: 0, buttons: 0, vx: 1, vy: 0, vz: 0, yaw: 0 }, ...jump(200, 20), { tick: 224, ratio: 0, gain: 0, buttons: 0, vx: 2, vy: 0, vz: 0, yaw: 0 }]);
expect(api.getWin().ratios.length, 10, 'watching a replay: its strafing not counted');
replayState = 0;
fire('MomentumSpectateStart');
frame();
expect([P.visible, api.getWin().ratios.length], [false, 0], 'spectating: hidden and cleared');
play([{ tick: 248, ratio: 0, gain: 0, buttons: 0, vx: 1, vy: 0, vz: 0, yaw: 0 }, ...jump(250, 20), { tick: 274, ratio: 0, gain: 0, buttons: 0, vx: 2, vy: 0, vz: 0, yaw: 0 }]);
expect([P.visible, api.getWin().ratios.length], [false, 0], 'spectating: strafing not counted');
fire('MomentumSpectateStop');
P.enabled = false;
play(jump(300, 20));
expect(api.getWin().ratios.length, 0, 'switched off in the customizer: nothing counted');
P.enabled = true;
// panorama_reload: a second load takes the panel over, the old loop stops (its schedule is still pending)
GLOBAL.HudCustomizerHandler.customizerReady = true;
expect(schedules.length, 1, 'one loop running before the reload');
const api2 = loadScript();
expect(loads, 2, 'a reload registers at once while the customizer is ready');
expect(loaded.p === P, true, 'a reload takes the placed panel over');
expect(timer.parent.children.filter((c) => c.id === 'MovekitStrafeHist').length, 1, 'still one panel');
play([{ tick: 498, ratio: 0, gain: 0, buttons: 0, vx: 1, vy: 0, vz: 0, yaw: 0 }, ...jump(500, 20), { tick: 524, ratio: 0, gain: 0, buttons: 0, vx: 2, vy: 0, vz: 0, yaw: 0 }]);
expect([api.getWin().ratios.length, api2.getWin().ratios.length], [0, 10], 'only the new copy counts');
expect(schedules.length, 1, 'one loop running after the reload');

// ---- the store: HUD ticks = viewer strafe-middle ticks ----
if (!fs.existsSync(store)) {
	console.log(`check_strafe_histogram: all good (no store at ${store}, attempts skipped)`);
	process.exit(0);
}
const data = require(path.join(VIEWER, 'data.js'));
Object.assign(globalThis, data);
const checks = require(path.join(VIEWER, 'checks.js'));
let files = 0;
let ticks = 0;
let outside = 0;
let hudIn = 0;
let viewIn = 0;
for (const mapDir of fs.readdirSync(store).sort()) {
	const dir = path.join(store, mapDir);
	// surf maps play in surf modes, where the histogram is hidden; a ramp run there is one long "jump" that
	// outgrows the HUD's KEEP_ROWS
	if (mapDir.startsWith('surf_') || !fs.statSync(dir).isDirectory()) continue;
	for (const file of fs.readdirSync(dir).sort()) {
		if (!file.endsWith('.json.gz') || files >= maxFiles) continue;
		const a = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(dir, file))).toString());
		const d = data.parse(a);
		if (data.isOther(a) || d.derived || d.n < 10) continue;
		files++;
		const { jumps } = data.findJumps(d, a.preRows);
		// the viewer: every jump's strafes, their middles (stats.js), with a known ratio; the last 5 rows left out
		// (the HUD waits for rows after them)
		const last = d.n - 5;
		const want = new Set();
		const inJump = new Set();
		for (const jj of jumps) {
			for (let i = jj.s; i < jj.e; i++) inJump.add(i);
			for (const st of checks.strafesOf(d, jj, d.n - 1)) {
				for (const i of checks.interior(d, st, 2)) if (Number.isFinite(d.ratio[i]) && i < last) want.add(i);
			}
		}
		// the HUD, fed one row at a time
		const byTick = new Map();
		for (let i = 0; i < d.n; i++) byTick.set(d.tick[i], i);
		const stream = new api.Middles();
		const got = new Set();
		for (let i = 0; i < d.n; i++) {
			const row = { tick: d.tick[i], ratio: d.ratio[i], gain: d.gain[i], buttons: d.buttons[i], vx: d.vx[i], vy: d.vy[i], vz: d.vz[i], yaw: d.yaw[i] };
			for (const r of stream.push(row)) {
				const k = byTick.get(r.tick);
				if (got.has(k)) fail(`${mapDir}/${file}: row ${k} counted twice`);
				got.add(k);
			}
		}
		const hudJ = [...got].filter((i) => inJump.has(i) && i < last);
		outside += [...got].filter((i) => !inJump.has(i)).length;
		const miss = [...want].filter((i) => !got.has(i));
		const extra = hudJ.filter((i) => !want.has(i));
		if (miss.length || extra.length) {
			fail(`${mapDir}/${file}: HUD vs viewer middles differ: ${miss.length} missed (first row ${miss[0]}), ` +
				`${extra.length} extra (first row ${extra[0]}) of ${want.size}`);
		}
		ticks += want.size;
		hudIn += hudJ.filter((i) => d.ratio[i] >= api.BAND_LO && d.ratio[i] <= api.BAND_HI).length;
		viewIn += [...want].filter((i) => d.ratio[i] >= 0.85 && d.ratio[i] <= 1.15).length;
	}
}
expect(hudIn, viewIn, 'in-band ticks, HUD vs viewer');
console.log(`check_strafe_histogram: all good (${files} own attempts, ${ticks} strafe-middle ticks match the viewer; ` +
	`${outside} more in hops the viewer drops before a teleport)`);
