#!/usr/bin/env node
// Checks strafe-histogram/panorama/scripts/hud/movekit-strafe-histogram.ts in node, with Panorama stubbed
// (types stripped, as jhud/check_jhud.js does).
//
// Usage: node strafe-histogram/check_strafe_histogram.js [--store DIR]   (exits 1 on the first failure)
//
// Covers: the customizer settings (every STYLES row has a DEFAULTS value and sits in one group, number boxes
// have a range around their default) against install.py's hud_default.kv3 entry; bar length, side, colour
// and marker lines; ground from vz; the Panorama side: the customizer component for bhop modes only, the
// sample while it is open, one row per air tick (each tick once over several frames, none for ground ticks),
// newest at the bottom and the top row reused (no panel made or deleted per tick), a setting that changes the
// rows building them again, nothing while spectating, in a replay, in another mode or switched off, and after
// panorama_reload the panel taken over and the old copy's loop stopping. Then every own bhop attempt in
// Strafe Review's store (--store, default ~/.local/share/strafe-review/attempts; skipped when missing): the
// HUD's ground rule against the viewer's, row by row.
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
const at = args.indexOf('--store');
const store = at >= 0 ? args[at + 1] : path.join(process.env.HOME || '', '.local/share/strafe-review/attempts');

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
let made = 0;
class FakePanel {
	constructor(type, parent, id, props) {
		made++;
		this.type = type;
		this.paneltype = type;
		this.id = id;
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
	MoveChildAfter(child, after) {
		const i = this.children.indexOf(child);
		if (i < 0 || this.children.indexOf(after) < 0) throw new Error('MoveChildAfter: not my children');
		this.children.splice(i, 1);
		this.children.splice(this.children.indexOf(after) + 1, 0, child);
	}
	RemoveAndDeleteChildren() {
		for (const c of this.children) c.valid = false;
		this.children = [];
	}
}
const hud = new FakePanel('Hud', null, 'Hud');
const timer = new FakePanel('MomHudTimer', hud, 'Timer');
const handlers = {};
let schedules = [];
let mode = 2;
let replayState = 0;
let time = 0;
let tickStats = { speedGain: 0, idealGain: 0, yawRatio: 0, strafeRight: 0 };
let vel = { x: 0, y: 0, z: 0 };
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
		GetMoveType: () => 2
	},
	MomentumPlayerAPI: { GetVelocity: () => vel },
	MomentumReplayAPI: { GetReplayState: () => replayState },
	UiToolkitAPI: { GetGlobalObject: () => GLOBAL },
	console
};
const src = stripTypeScriptTypes(fs.readFileSync(TS, 'utf8'), { mode: 'strip' });
function loadScript() {
	const ctx = { ...stubs };
	vm.createContext(ctx);
	vm.runInContext(`${src}
globalThis.__api = { DEFAULTS, STYLES, SAMPLE, NONE, onGround, optimalAt, barLength, barSide, barColor, mixColor, markers,
	rowStyle, settings };`, ctx);
	return ctx.__api;
}
const api = loadScript();
const fire = (ev) => (handlers[ev] || []).forEach((fn) => fn());
const frame = () => { const s = schedules; schedules = []; s.forEach((x) => x.fn()); };

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
	// the NumberEntry clamps on every keystroke, so a min over 0 snaps a half-typed value back (2 on the way to 200)
	if (extra.range.min !== 0) fail(`number box ${id}: min ${extra.range.min}, not 0`);
}

// ---- plain functions ----
const S = { ...api.DEFAULTS };
const S3 = { ...S, optimalAt: 'three' };
expect([api.optimalAt(S), api.optimalAt(S3)], [0.5, 0.75], 'optimal in the middle by default, or at 3/4');
expect([0, -0.5, NaN, 0.5, 1, 1.5, 2, 3].map((r) => api.barLength(r, S)), [0, 0, 0, 0.25, 0.5, 0.75, 1, 1], 'length, optimal in the middle');
expect([1, 1.2, 4 / 3, 2].map((r) => +api.barLength(r, S3).toFixed(4)), [0.75, 0.9, 1, 1], 'length, optimal at 3/4');
expect([api.barSide(true, S), api.barSide(false, S)], ['left', 'left'], 'from the left by default');
const SS = { ...S, fromSides: true };
expect([api.barSide(true, SS), api.barSide(false, SS)], ['right', 'left'], 'from the strafe side');
expect(api.markers(S), [0.5], 'one marker in the middle');
expect(api.markers(S3), [0.75], 'one marker at 3/4');
expect(api.markers({ ...S3, fromSides: true }), [0.75, 0.25], 'from the sides at 3/4: both markers');
expect(api.markers({ ...S, fromSides: true }), [0.5], 'from the sides in the middle: one marker');
expect(api.barColor(0.3, S), S.barColor, 'plain: one colour');
const G = { ...S, colorBy: 'good' };
expect([api.barColor(1, G), api.barColor(1.5, G), api.barColor(0.5, G), api.barColor(3, G)],
	[api.mixColor(G.goodColor, G.badColor, 0), G.badColor, G.badColor, G.badColor], 'how good: good at 1, bad at 50 % away');
expect(api.barColor(0.75, G), api.barColor(1.25, G), 'how good: slow and fast alike');
expect(api.rowStyle(1.5, true, SS), { width: 75, side: 'right', color: S.barColor }, 'a row');
expect(api.rowStyle(0.333, false, S).width, 16.7, 'width rounded to 0.1 %');
expect([api.onGround(0, -290, 290), api.onGround(0, 3, -5), api.onGround(0, 3, 0), api.onGround(-8, 0, -16), api.onGround(0.42, 0.42, 0),
	api.onGround(0.42, 0, 0.42), api.onGround(0.42, 0.5, 0)], [true, false, true, false, true, true, false],
	'ground: vz 0 unless an apex, a small vz the same as a neighbour');

// ---- Panorama ----
const rowsOf = (p) => p.children[0].children;
const shownRows = (p) => rowsOf(p).filter((r) => r.visible);
expect(loaded, null, 'not registered before the customizer is ready');
fire('HudCustomizer_Ready');
expect(loads, 1, 'registered at HudCustomizer_Ready');
expect(loaded.props.gamemode, [2, 3], 'bhop modes only');
expect(loaded.props.name, 'Strafe Speed Histogram', 'component name');
const P = loaded.p;
expect(P.id, 'MovekitStrafeHist', 'panel id');
expect(P.visible, false, 'hidden before any tick');
fire('HudCustomizer_Opened');
expect([P.visible, rowsOf(P).length, shownRows(P).length], [true, 100, 100], 'sample while the customizer is open');
expect(P.children.length, 2, 'sample: the rows and one marker line');
fire('HudCustomizer_Closed');
expect(P.visible, false, 'hidden when the customizer closes');

// one game tick, seen over `frames` frames with the same values
function tick(t, ratio, right, vz, frames = 3) {
	time = t * 0.01 + 0.001;
	tickStats = { speedGain: 1, idealGain: 1, yawRatio: ratio, strafeRight: right ? 1 : -1 }; // the game's: 1, -1 or 0
	vel = { x: 300 + t, y: 0, z: vz };
	for (let f = 0; f < frames; f++) {
		frame();
		time += 0.002;
	}
}
// a jump: `n` air ticks, left then right, then two ground ticks
function jump(t0, n, ratio = (i) => 0.9 + i / 100) {
	for (let i = 0; i < n; i++) tick(t0 + i, ratio(i), i >= n / 2, 290 - (580 * i) / Math.max(1, n - 1));
	tick(t0 + n, 0, false, 0);
	tick(t0 + n + 1, 0, false, 0);
}
jump(100, 20);
expect(shownRows(P).length, 20, 'one row per air tick, each tick once over three frames, none for ground ticks');
expect(shownRows(P).map((r) => r.style.width), Array.from({ length: 20 }, (_, i) => `${Math.round((0.9 + i / 100) * 500) / 10}%`),
	'oldest on top, newest at the bottom');
expect(rowsOf(P).slice(80).every((r) => r.visible) && rowsOf(P).slice(0, 80).every((r) => !r.visible), true,
	'the shown rows sit at the end of the list (the bottom)');
const before = rowsOf(P).slice();
const madeBefore = made;
jump(200, 30, () => 1.2);
expect(made, madeBefore, 'no panel made per tick');
expect(new Set(rowsOf(P)).size === 100 && rowsOf(P).every((r) => before.includes(r)), true, 'the same 100 rows, reused');
expect(shownRows(P).length, 50, 'rows pile up across jumps');
expect(rowsOf(P)[99].style.width, '60%', 'the newest row is the last tick');
jump(300, 80, () => 0.6);
expect([shownRows(P).length, rowsOf(P)[0].style.width], [100, '60%'], 'full: the oldest scroll out the top');
// standing still: nothing new, the rows stay
for (let f = 0; f < 20; f++) { time += 0.01; frame(); }
expect([P.visible, shownRows(P).length], [true, 100], 'standing still: the bars stay');
// a setting that changes the rows builds them again (empty); one that doesn't keeps them
const cb = (id, v) => loaded.props.dynamicStyles[id].callbackFunc(null, v);
cb('barColor', 'rgba(1, 2, 3, 1)');
jump(400, 4);
expect([rowsOf(P).length, shownRows(P).length, rowsOf(P)[99].style.backgroundColor], [100, 100, 'rgba(1, 2, 3, 1)'],
	'a new bar colour: rows kept, new rows in it');
for (const v of [0, 2, 20, 200, 5000]) cb('rows', v);
jump(450, 4);
expect(rowsOf(P).length, 1000, 'rows typed past 1000: capped at 1000');
cb('rows', 2);
jump(460, 4);
expect(rowsOf(P).length, 10, 'a half-typed 2: 10 rows, no error');
cb('rowHeight', 0);
jump(470, 4);
expect(P.style.height, '10px', 'bar height 0: 1 px');
cb('rowHeight', 2);
cb('rows', 50);
jump(500, 4);
expect([rowsOf(P).length, shownRows(P).length], [50, 4], 'fewer ticks shown: built again, empty');
cb('optimalAt', 'three');
cb('fromSides', true);
jump(600, 4, () => 1);
expect(P.children.length, 3, 'from the sides at 3/4: two marker lines');
expect(rowsOf(P).slice(-4).map((r) => [r.style.width, r.style.horizontalAlign]),
	[['75%', 'left'], ['75%', 'left'], ['75%', 'right'], ['75%', 'right']], 'from the sides: right strafes from the right');
for (const [k, v] of [['rows', 100], ['optimalAt', 'middle'], ['fromSides', false], ['barColor', api.DEFAULTS.barColor]]) cb(k, v);
jump(700, 4);
const n0 = shownRows(P).length;
mode = 1;
jump(800, 10);
expect([P.visible, shownRows(P).length], [false, n0], 'another mode: hidden, nothing added');
mode = 2;
replayState = 1;
jump(900, 10);
expect([P.visible, shownRows(P).length], [false, n0], 'watching a replay: hidden, nothing added');
replayState = 0;
fire('MomentumSpectateStart');
jump(1000, 10);
expect(P.visible, false, 'spectating: hidden');
fire('MomentumSpectateStop');
jump(1100, 6);
expect(shownRows(P).length, 6, 'after spectating: a fresh start');
P.enabled = false;
jump(1200, 10);
expect([P.visible, shownRows(P).length], [false, 6], 'switched off in the customizer: nothing added');
P.enabled = true;
// panorama_reload: a second load takes the panel over, the old loop stops (its schedule is still pending)
GLOBAL.HudCustomizerHandler.customizerReady = true;
expect(schedules.length, 1, 'one loop running before the reload');
loadScript();
expect(loads, 2, 'a reload registers at once while the customizer is ready');
expect(loaded.p === P, true, 'a reload takes the placed panel over');
expect(timer.parent.children.filter((c) => c.id === 'MovekitStrafeHist').length, 1, 'still one panel');
jump(1300, 10);
expect([shownRows(P).length, P.children.length], [10, 2], 'after the reload: the new copy built its own rows, once');
expect(schedules.length, 1, 'one loop running after the reload');

// ---- the store: the HUD's ground rule against the viewer's ----
if (!fs.existsSync(store)) {
	console.log(`check_strafe_histogram: all good (no store at ${store}, ground rule not compared)`);
	process.exit(0);
}
const data = require(path.join(VIEWER, 'data.js'));
let files = 0;
let rowsN = 0;
let differ = 0;
for (const mapDir of fs.readdirSync(store).sort()) {
	const dir = path.join(store, mapDir);
	if (mapDir.startsWith('surf_') || !fs.statSync(dir).isDirectory()) continue;
	for (const file of fs.readdirSync(dir).sort()) {
		if (!file.endsWith('.json.gz')) continue;
		const a = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(dir, file))).toString());
		const d = data.parse(a);
		if (data.isOther(a) || d.derived) continue;
		files++;
		for (let i = 1; i < d.n - 1; i++) {
			if (d.gap[i] > 0) continue;
			rowsN++;
			if (api.onGround(d.vz[i], d.vz[i - 1], d.vz[i + 1]) !== !!d.ground[i]) differ++;
		}
	}
}
if (differ) fail(`ground rule: ${differ} of ${rowsN} rows differ from the viewer's`);
console.log(`check_strafe_histogram: all good (ground rule on ${files} own bhop attempts: ${differ} of ${rowsN} rows differ from the viewer's)`);
