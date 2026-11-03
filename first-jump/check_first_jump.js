#!/usr/bin/env node
// Checks first-jump/panorama/scripts/hud/movekit-first-jump.ts in node, with Panorama stubbed (types stripped,
// as jhud/check_jhud.js does). The jump-1 numbers against Strafe Review's viewer are check_parity.js's job.
//
// Usage: node first-jump/check_first_jump.js   (exits 1 on the first failure)
//
// Covers: the customizer settings (every STYLES row has a DEFAULTS value and sits in one group, number boxes
// min 0) against install.py's hud_default.kv3 entry (same keys, same values); the gain bands (the same
// defaults as JHUD's); the drawn parts and the row switches; the Panorama side on a made-up run fed tick by
// tick: hidden until jump 1 lands, shown LINE_DELAY_ROWS rows after the landing and logged as FJLINE, held
// for holdMs then faded, once per run, the pre-timer rows used, nothing in surf, on a replay, while
// spectating, with the panel switched off in the customizer or with every row off; a run stopped in the air
// dropped; the customizer's sample and number boxes; panorama_reload (the old copy's loop stops).
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { stripTypeScriptTypes } = require('module');

const TS = path.join(__dirname, 'panorama/scripts/hud/movekit-first-jump.ts');
const INSTALL = path.join(__dirname, 'install.py');
const JHUD = path.join(__dirname, '..', 'jhud', 'panorama', 'scripts', 'hud', 'movekit-jhud.ts');

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
let msgs = [];
let loaded = null;
let loads = 0;
const IV = 0.01;
// What the game APIs read now; tick() moves it on
const G = { mode: 2, state: 0, replay: 0, meta: null, moveType: 2, time: 0, gain: 0, ideal: 0, ratio: 0, right: 0,
	vx: 0, vy: 0, vz: 0, yaw: 0, buttons: 0, wx: 0, wy: 0 };
const GLOBAL = { HudCustomizerHandler: { customizerReady: false, loadComponent: (p, props) => { loaded = { p, props }; loads++; } } };
const stubs = {
	$: {
		GetContextPanel: () => timer,
		CreatePanel: (type, parent, id, props) => new FakePanel(type, parent, id, props),
		RegisterForUnhandledEvent: (ev, fn) => { (handlers[ev] = handlers[ev] || []).push(fn); },
		Schedule: (s, fn) => { schedules.push({ s, fn }); },
		Msg: (t) => msgs.push(t)
	},
	GameModeAPI: { GetCurrentGameMode: () => G.mode },
	MomentumMovementAPI: {
		GetTickInterval: () => IV,
		GetCurrentTime: () => G.time,
		GetLastTickStats: () => ({ speedGain: G.gain, idealGain: G.ideal, yawRatio: G.ratio, strafeRight: G.right }),
		GetMoveHudData: () => ({ moveStatus: G.vz ? 0 : 1, wishVel: { x: G.wx, y: G.wy } }),
		GetMoveType: () => G.moveType
	},
	MomentumTimerAPI: { GetObservedTimerStatus: () => ({ state: G.state }), GetObservedRunMetadata: () => G.meta },
	MomentumPlayerAPI: {
		GetVelocity: () => ({ x: G.vx, y: G.vy, z: G.vz }),
		GetAngles: () => ({ x: 0, y: G.yaw }),
		IsDucking: () => false
	},
	MomentumInputAPI: { GetButtons: () => ({ physicalButtons: G.buttons }) },
	MomentumReplayAPI: { GetReplayState: () => G.replay },
	MapCacheAPI: { GetMapName: () => 'bhop_check' },
	UiToolkitAPI: { GetGlobalObject: () => GLOBAL },
	console
};
const src = stripTypeScriptTypes(fs.readFileSync(TS, 'utf8'), { mode: 'strip' });
// One load of the script in a fresh context; the panels, handlers and global object are shared, so a second
// load is panorama_reload: the first load's handlers and loop stay.
function loadScript() {
	const ctx = { ...stubs };
	vm.createContext(ctx);
	vm.runInContext(`${src}
globalThis.__api = { DEFAULTS, STYLES, SAMPLE, NONE, LINE_DELAY_ROWS, gainColor, parts, empty, fitLayout, settings, get attempt() { return attempt; } };`, ctx);
	return ctx.__api;
}
const api = loadScript();
const fire = (ev, ...a) => (handlers[ev] || []).forEach((fn) => fn(...a));
// One frame: every loop scheduled for it runs (other timers stay)
function frame() {
	const loops = schedules.filter((x) => x.fn.name === 'loop');
	schedules = schedules.filter((x) => x.fn.name !== 'loop');
	loops.forEach((x) => x.fn());
}
const runTimers = () => {
	const t = schedules.filter((x) => x.fn.name !== 'loop');
	schedules = schedules.filter((x) => x.fn.name === 'loop');
	t.forEach((x) => x.fn());
	return t.map((x) => x.s);
};
let tickNo = 1000;
// One physics tick with these values, then a frame
function tick(v) {
	Object.assign(G, v);
	tickNo++;
	G.time = tickNo * IV + 1e-6;
	frame();
}
const A = 1 << 9;
const D = 1 << 10;
const W = 1 << 3;
// A made-up jump-1 run: ground at 280 u/s, the timer starts (onRun), a takeoff, 60 air ticks strafing A then D
// (turning left then right), the landing, then ground. onRun runs at the timer start.
function run({ landing = true, onRun = () => {}, stopInAir = false } = {}) {
	const speed = 280;
	for (let i = 0; i < 30; i++) tick({ vx: speed + i * 0.001, vy: 0, vz: 0, gain: 0, ideal: 0, ratio: 0, buttons: W, yaw: 0 });
	G.state = 2;
	fire('OnObservedTimerStateChange');
	onRun();
	let yaw = 0;
	for (let i = 0; i < 60; i++) {
		const left = i < 30;
		yaw += left ? 1.2 : -1.2;
		const rad = (yaw * Math.PI) / 180;
		tick({ vz: 290 - i * 8 || 0.01, vx: (speed + i) * Math.cos(rad), vy: (speed + i) * Math.sin(rad), gain: 0.9, ideal: 1, ratio: 1,
			right: left ? -1 : 1, buttons: left ? A : D, yaw, wx: 0, wy: 0 });
		if (stopInAir && i === 40) {
			G.state = 0;
			fire('OnObservedTimerStateChange');
		}
	}
	if (!landing) return;
	for (let i = 0; i < 10; i++) tick({ vz: 0, vx: 340 + i * 0.001, vy: 0, gain: 0, ideal: 0, buttons: W });
}
const panelOf = () => hud.FindChildTraverse('MovekitFirstJump');
const texts = (p) => p.children.map((c) => (c.children.length ? c.children.map((l) => l.text) : c.text));
const lines = () => msgs.filter((t) => t.startsWith('FJLINE '));
function reset() {
	G.state = 0;
	fire('OnObservedTimerStateChange');
	runTimers();
	runTimers();
	msgs = [];
}

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
if (!/^    MovekitFirstJump = \n/.test(entry[1])) fail('kv3 entry is not for the panel id MovekitFirstJump');
const pos = Object.fromEntries([...entry[1].matchAll(/^        (offsetX|offsetY|width) = (\d+)$/gm)].map((m) => [m[1], +m[2]]));
expect(pos.offsetX * 2 + pos.width, 1920, 'placed in the middle of the 1920 wide screen');

// ---- plain functions ----
const S = { ...api.DEFAULTS, fontColor: 'rgba(255, 255, 255, 1)' };
const [LOW, MID, HIGH] = [S.lowColor, S.midColor, S.highColor];
expect([40, 86.4, 86.5, 90, 92, 92.1, 120].map((g) => api.gainColor(g, S)), [LOW, LOW, MID, MID, MID, HIGH, HIGH],
	'gain bands: amber under 86.5, green 86.5-92 (both in), blue above');
expect(api.gainColor(NaN, S), 'rgba(140, 140, 150, 1)', 'no gain known: grey');
expect(api.gainColor(70, { ...S, gainLow: 600, gainHigh: 650 }), HIGH, 'thresholds can be set (tenths of a %)');
const jhud = fs.readFileSync(JHUD, 'utf8');
for (const k of ['gainLow', 'gainHigh', 'lowColor', 'midColor', 'highColor']) {
	const m = new RegExp(`^\\t${k}: (.+),$`, 'm').exec(jhud);
	if (!m || eval(m[1]) !== S[k]) fail(`${k}: the default ${S[k]} isn't JHUD's ${m && m[1]}`);
}
const p = api.parts(api.SAMPLE, S);
expect(p.head, 'J1 291 u/s  ·  89.62 %', 'top line');
expect(p.boxes.map((b) => b.text), ['A 93.4 %', 'D 88.1 %', 'A 84.7 %'], 'a box per strafe');
expect(p.boxes.map((b) => b.color), [HIGH, MID, LOW], 'boxes in the gain bands');
expect(p.causes, [{ text: 'ok', color: MID }, { text: 'fast 4t', color: S.causeColor }, { text: 'keys 3t', color: S.causeColor }],
	'a cause under each box');
expect(p.mistake, 'A switch 4 ticks early (-5.6 u/s)', 'the biggest mistake');
expect(api.parts(api.SAMPLE, { ...S, showLanding: false }).head, '89.62 %', 'landing off');
expect(api.parts(api.SAMPLE, { ...S, showGain: false }).head, 'J1 291 u/s', 'gain off');
expect(api.parts(api.SAMPLE, { ...S, showCauses: false }).causes, [], 'causes off');
expect([api.parts(api.SAMPLE, { ...S, showStrafes: false }).boxes, api.parts(api.SAMPLE, { ...S, showStrafes: false }).causes], [[], []],
	'strafes off: no causes either');
expect(api.parts({ ...api.SAMPLE, mistakes: [] }, S).mistake, '', 'no mistake found');
const none = Object.fromEntries(Object.keys(S).map((k) => [k, k.startsWith('show') ? false : S[k]]));
expect(api.empty(api.parts(api.SAMPLE, none)), true, 'every row off: nothing');
expect(api.parts({ ...api.SAMPLE, strafes: [{ dir: -1, pct: NaN, top: null }] }, S).boxes[0].text, 'D - %', 'no gain known');

// ---- Panorama side ----
expect(loads, 0, 'no registration before the customizer is ready');
fire('HudCustomizer_Ready');
GLOBAL.HudCustomizerHandler.customizerReady = true;
if (!loaded) fail('the customizer got no component');
expect(loaded.p.id, 'MovekitFirstJump', 'component panel id');
expect([loaded.props.name, loaded.props.gamemode], ['First Jump', [2, 3]], 'listed as First Jump, bhop modes only');
expect(Object.keys(loaded.props.dynamicStyles).sort(), api.STYLES.map((x) => x[0]).sort(), 'every row in the customizer');
for (const [id, value] of Object.entries(S)) {
	const d = loaded.props.dynamicStyles[id];
	if (d.callbackFunc) d.callbackFunc(loaded.p, value);
}
expect(api.settings.fontColor, S.fontColor, 'callback stores the setting');
for (const [id, , type] of api.STYLES) {
	if (type !== 1) continue;
	const sp = loaded.props.dynamicStyles[id].settingProps;
	if (!sp || !(sp.min <= S[id] && S[id] <= sp.max)) fail(`number box ${id}: no min/max around its default (${JSON.stringify(sp)})`);
	if (sp.min !== 0) fail(`number box ${id}: min ${sp.min}, not 0`);
}
expect(loaded.props.dynamicStyles.backgroundColor.styleProperty, 'backgroundColor', 'background on the panel itself');
const panel = panelOf();
expect(panel.visible, false, 'hidden until jump 1 lands');

// a bhop run: shown a few rows after the landing
let shownAt = -1;
run({ landing: false });
expect([panel.visible, lines().length], [false, 0], 'nothing while in the air');
for (let i = 0; i < 10 && shownAt < 0; i++) {
	tick({ vz: 0, vx: 340 + i * 0.001, vy: 0, gain: 0, ideal: 0, buttons: W });
	if (panel.visible) shownAt = i;
}
expect(shownAt, api.LINE_DELAY_ROWS, 'shown LINE_DELAY_ROWS rows after the landing row');
expect(lines().length, 1, 'logged once');
const logged = JSON.parse(lines()[0].slice(lines()[0].indexOf('{')));
expect([logged.map, logged.strafes.map((s) => s[0]), logged.s], ['bhop_check', [1, -1], 30], 'logged: map, two strafes (A, D), takeoff after the 30 pre rows');
const t = texts(panel);
if (!/^J1 \d+ u\/s {2}· {2}90\.00 %$/.test(t[0])) fail(`top line ${t[0]}`);
expect(t[1], ['A 90.0 %', 'D 90.0 %'], 'strafe boxes drawn');
if (!panel.children[1].children.every((l) => l.styleText.includes(`background-color: ${MID};`))) fail('90 % boxes not green');
expect(api.attempt, null, 'the run is done once jump 1 is shown');
expect(runTimers(), [4], 'held for holdMs');
expect([panel.style.opacity, panel.style.transitionDuration], ['0', '0.3s'], 'fading over fadeMs');
runTimers();
expect(panel.visible, false, 'hidden after the fade');
for (let i = 0; i < 80; i++) tick({ vz: i % 40 === 0 ? 290 : i % 40 < 30 ? 100 : 0, vx: 350 + i, gain: 0.9, ideal: 1 });
expect([panel.visible, lines().length], [false, 1], 'later jumps of the run show nothing');
reset();

const quiet = (what, opts, undo) => {
	run(opts);
	expect([panel.visible, lines().length], [false, 0], what);
	undo && undo();
	reset();
};
G.mode = 1;
quiet('surf shows nothing', {}, () => (G.mode = 2));
G.replay = 1;
quiet('a replay shows nothing', {}, () => (G.replay = 0));
fire('MomentumSpectateStart');
quiet('spectating shows nothing', {}, () => fire('MomentumSpectateStop'));
quiet('a new observed target drops the run', { onRun: () => fire('OnObservedTimerReplaced') });
quiet('a run stopped in the air is dropped (jump 1 landed after the stop)', { stopInAir: true });
panel.enabled = false;
run();
expect([panel.visible, lines().length], [false, 1], 'switched off in the customizer: not shown, still logged');
panel.enabled = true;
reset();
for (const [id, v] of Object.entries(none)) if (id.startsWith('show')) loaded.props.dynamicStyles[id].callbackFunc(loaded.p, v);
run();
expect(panel.visible, false, 'every row off: nothing shown');
for (const [id, v] of Object.entries(S)) if (id.startsWith('show')) loaded.props.dynamicStyles[id].callbackFunc(loaded.p, v);
reset();
run();
expect(panel.visible, true, 'a second run shows again');
reset();

// the customizer: a sample to drag while it is open, hidden when it closes
const settingsList = new FakePanel('Panel', null, 'ActiveComponentSettingsList');
const row = new FakePanel('Panel', new FakePanel('Panel', settingsList, 'ParentWrapper'), '');
const box = new FakePanel('TextEntry', new FakePanel('NumberEntry', row, 'NumberEntry'), '');
GLOBAL.HudCustomizerHandler.panels = { activeComponentSettingsList: settingsList };
GLOBAL.HudCustomizerHandler.activeComponent = { id: 'MovekitFirstJump' };
fire('HudCustomizer_Opened');
expect([panel.visible, texts(panel)[0]], [true, 'J1 291 u/s  ·  89.62 %'], 'sample shown in the customizer');
runTimers();
expect(box.style.width, '44px', 'number boxes widened');
loaded.props.dynamicStyles.showLanding.callbackFunc(loaded.p, false);
expect(texts(panel)[0], '89.62 %', 'a changed setting redraws the sample');
loaded.props.dynamicStyles.showLanding.callbackFunc(loaded.p, true);
run();
expect(texts(panel)[0], 'J1 291 u/s  ·  89.62 %', 'a run doesn\'t replace the sample while editing');
fire('HudCustomizer_Closed');
expect(panel.visible, false, 'hidden when the customizer closes');
reset();

// panorama_reload: the new copy takes over the placed panel and registers at once; the old copy's loop stops
const before = loads;
loadScript();
expect(loads, before + 1, 'registered at load after a reload');
expect(loaded.p === panel, true, 'the placed panel taken over, not replaced');
for (const [id, value] of Object.entries(S)) {
	const d = loaded.props.dynamicStyles[id];
	if (d.callbackFunc) d.callbackFunc(loaded.p, value);
}
frame();
expect(schedules.filter((x) => x.fn.name === 'loop').length, 1, 'one loop after a reload');
run();
expect([panel.visible, lines().length], [true, 1], 'shown once after a reload');
expect(hud.children.filter((c) => c.id === 'MovekitFirstJump').length, 1, 'one panel');
// a stale layout after an update + panorama_reload: a setting with no value is left out of the customizer
const fp = { dynamicStyles: { g: { type: 0, children: [{ styleID: 'a' }, { styleID: 'b' }] }, a: { type: 1 }, b: { type: 2 } } };
const fit = api.fitLayout(fp, { a: 1 });
expect([Object.keys(fit.dynamicStyles), fit.dynamicStyles.g.children.map((c) => c.styleID)], [['g', 'a'], ['a']], 'stale layout');
GLOBAL.HudCustomizerHandler.loadComponent = () => { throw new Error('Could not load dynamic style value for x'); };
loadScript();
console.log('check_first_jump: all good');
