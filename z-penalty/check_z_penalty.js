#!/usr/bin/env node
// Checks z-penalty/panorama/scripts/hud/movekit-z-penalty.ts in node, with Panorama stubbed (types
// stripped, as zone-exit/check_zone_exit.js does).
//
// Usage: node z-penalty/check_z_penalty.js   (exits 1 on the first failure)
//
// Covers: the customizer settings (every STYLES row has a DEFAULTS value and sits in one group) against
// install.py's hud_default.kv3 entry (same keys, same values); the tracker on the probe's shapes
// (2026-11-09: a jump's top is 12 ticks in the band at -12 per tick, a ramp climb rises about 8 per tick
// through it): ramps only skips the jump and takes the climb, any air takes both, the learned free fall
// step, landings and long gaps; the bar's numbers and the text lines; the Panorama side: surf only,
// shown while penalised then held and faded, always shown, the sound once per stretch and at most every
// half second, nothing for replays, spectating, other modes or a panel switched off, the customizer's
// sample, panorama_reload.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { stripTypeScriptTypes } = require('module');

const TS = path.join(__dirname, 'panorama/scripts/hud/movekit-z-penalty.ts');
const INSTALL = path.join(__dirname, 'install.py');

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
let commands = [];
let now = 1e6;
const G = { mode: 1, replay: 0, observed: null, moveType: 2, time: 0, velocity: { x: 900, y: 0, z: 0 }, gravity: 1200 };
let loaded = null;
let loads = 0;
const GLOBAL = { HudCustomizerHandler: { customizerReady: false, loadComponent: (p, props) => { loaded = { p, props }; loads++; } } };
const stubs = {
	$: {
		GetContextPanel: () => timer,
		CreatePanel: (type, parent, id, props) => new FakePanel(type, parent, id, props),
		RegisterForUnhandledEvent: (ev, fn) => { (handlers[ev] = handlers[ev] || []).push(fn); },
		Schedule: (s, fn) => { schedules.push({ s, fn }); },
		Msg: (m) => fail('Msg: ' + m)
	},
	GameModeAPI: { GetCurrentGameMode: () => G.mode },
	GameInterfaceAPI: { GetSettingFloat: (k) => (k === 'sv_gravity' ? G.gravity : 0), ConsoleCommand: (c) => commands.push(c) },
	MomentumReplayAPI: { GetReplayState: () => G.replay },
	MomentumMovementAPI: { GetMoveType: () => G.moveType, GetTickInterval: () => 0.01, GetCurrentTime: () => G.time },
	MomentumPlayerAPI: { GetVelocity: () => G.velocity },
	MomentumTimerAPI: { GetObservedRunMetadata: () => G.observed },
	UiToolkitAPI: { GetGlobalObject: () => GLOBAL },
	Date: { now: () => now },
	console
};
const raw = fs.readFileSync(TS, 'utf8');
function loadScript(text = raw) {
	const ctx = { ...stubs };
	vm.createContext(ctx);
	vm.runInContext(`${stripTypeScriptTypes(text, { mode: 'strip' })}
globalThis.__api = { DEFAULTS, STYLES, SAMPLE, SOUND, fitLayout, newTracker, freeStep, track, barGeometry, lines, settings, NONE };`, ctx);
	return ctx.__api;
}
const api = loadScript();
const fire = (ev) => (handlers[ev] || []).forEach((fn) => fn());

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
if (!/^    MovekitZPenalty = \n/.test(entry[1])) fail('kv3 entry is not for the panel id MovekitZPenalty');
expect(api.SOUND, { on: false, name: 'buttons/blip1', volume: 60 }, 'the repo script\'s SOUND is the default');
if ((raw.match(/^const SOUND = .*\/\/ movekit:sound$/gm) || []).length !== 1) fail('one SOUND line for install.py to replace');

// ---- the tracker ----
// a jump from the ground: +290, then -12 per tick to the ground; the probe's 12 ticks in the band
function jump(t, tick, rampsOnly) {
	const out = [];
	out.push(api.track(t, tick++, 0, rampsOnly));
	for (let vz = 290; vz > -290; vz -= 12) out.push(api.track(t, tick++, vz, rampsOnly));
	out.push(api.track(t, tick++, 0, rampsOnly));
	return { out, tick };
}
// a ramp climb like the probe's: z speed from -21.5 rising about 8 per tick to 162
function climb(t, tick, rampsOnly) {
	const out = [];
	out.push(api.track(t, tick++, -40, rampsOnly));
	for (let vz = -21.53; vz < 165; vz += 7.9) out.push(api.track(t, tick++, vz, rampsOnly));
	return { out, tick };
}
const penalisedTicks = (out) => out.filter((s) => s.penalised).length;
const entries = (out) => out.filter((s) => s.entered).length;

let t = api.newTracker(-12);
let r = jump(t, 100, false);
expect([penalisedTicks(r.out), entries(r.out), r.out.filter((s) => s.left).length], [12, 1, 1], 'any air: a jump\'s top is 12 penalised ticks, one stretch');
expect(Math.max(...r.out.map((s) => s.ticks)), 12, 'ticks counts the stretch');
t = api.newTracker(-12);
r = jump(t, 100, true);
expect(penalisedTicks(r.out), 0, 'ramps only: a jump\'s top doesn\'t count');
r = climb(t, r.tick + 10, true);
expect([penalisedTicks(r.out), entries(r.out)], [18, 1], 'ramps only: the climb\'s 18 ticks in the band count');
t = api.newTracker(-8); // a wrong guess (sv_gravity 800 at 100 tick) ...
for (let i = 0, tick = 0; i < 3; i++) tick = jump(t, tick, true).tick + 5;
expect(api.freeStep(t), -12, '... is replaced by the learned step after a few jumps');
r = jump(t, 1000, true);
expect(penalisedTicks(r.out), 0, 'and then a jump\'s top doesn\'t count');
t = api.newTracker(-12);
api.track(t, 10, 0, true);
expect(api.track(t, 11, 60, true).penalised, true, 'off the ground straight into the band (no jump): a ramp');
t = api.newTracker(-12);
api.track(t, 10, 200, true);
expect(api.track(t, 30, 100, true).penalised, false, 'a long gap tells nothing: no ramp');
expect(api.track(t, 31, 0, true), { vz: 0, ticks: 1, penalised: false, entered: false, left: false }, 'landing ends the stretch');

// ---- bar and lines ----
const S = { ...api.DEFAULTS, fontColor: 'rgba(255, 255, 255, 1)' };
expect(api.barGeometry(0, S), { h: 120, w: 12, band: 56, marker: 117 }, 'bar at 0: band 140/300 of 120, marker at the bottom');
expect(api.barGeometry(140, S).marker, 63, 'marker at the band\'s top edge');
expect(api.barGeometry(9000, S).marker, 0, 'marker clamps at the top');
expect(api.barGeometry(-500, S).marker, 117, 'and at the bottom');
expect(api.barGeometry(0, { ...S, barMax: 50 }).band, 120, 'a bar top under 140 still holds the band');
const P = S.penaltyColor;
expect(api.lines({ vz: 96.4, ticks: 12, penalised: true }, S), [['Z PENALTY', P, true], ['z 96', P, true], ['12 ticks', null, true]], 'penalised lines');
expect(api.lines({ vz: 180, ticks: 0, penalised: false }, S), [['Z PENALTY', P, false], ['z 180', null, true], ['0 ticks', null, false]], 'not penalised: label and ticks keep their space');
expect(api.lines({ vz: 1, ticks: 1, penalised: true }, { ...S, showLabel: false, showTicks: false }), [['z 1', P, true]], 'parts switched off');

// ---- Panorama side ----
fire('HudCustomizer_Ready');
GLOBAL.HudCustomizerHandler.customizerReady = true;
if (!loaded) fail('the customizer got no component');
expect([loaded.p.id, loaded.props.name, loaded.props.gamemode], ['MovekitZPenalty', 'Z Penalty', [1]], 'listed as Z Penalty, surf only');
expect(Object.keys(loaded.props.dynamicStyles).sort(), api.STYLES.map((x) => x[0]).sort(), 'every row in the customizer');
for (const [id, value] of Object.entries(S)) {
	const d = loaded.props.dynamicStyles[id];
	if (d.callbackFunc) d.callbackFunc(loaded.p, value);
}
for (const [id, , type] of api.STYLES) {
	if (type !== 1) continue;
	const sp = loaded.props.dynamicStyles[id].settingProps;
	if (!sp || !(sp.min <= S[id] && S[id] <= sp.max)) fail(`number box ${id}: no min/max around its default`);
	if (sp.min !== 0) fail(`number box ${id}: min ${sp.min}, not 0`);
}
expect(loaded.props.dynamicStyles.alwaysShow.children.map((c) => [c.styleID, c.showWhen]), [['holdMs', [false, 0]], ['fadeMs', [false, 0]]],
	'hold and fade show while Always shown is off');
const panel = hud.FindChildTraverse('MovekitZPenalty');
expect(panel.visible, false, 'hidden at the start');

// the frame loop: one scheduled loop() runs a sample, then schedules itself again
const loopFn = () => {
	const i = schedules.findIndex((x) => x.s === 0 && x.fn.name === 'loop');
	if (i < 0) fail('no loop scheduled');
	const [x] = schedules.splice(i, 1);
	x.fn();
};
let tick = 5000;
function frame(vz) {
	G.time = ++tick * 0.01;
	G.velocity = { x: 900, y: 0, z: vz };
	loopFn();
	now += 10;
}
const labelTexts = () => {
	const col = panel.children.find((c) => c.id === '');
	return col ? col.children.filter((l) => l.style.opacity === '1').map((l) => l.text) : [];
};
// learn the step (ramps only is on), then a jump: nothing
for (let i = 0; i < 2; i++) {
	frame(0);
	for (let vz = 290; vz > -290; vz -= 12) frame(vz);
	frame(0);
}
expect([panel.visible, commands], [false, []], 'jumps: nothing shown, no sound (sound off)');
// a ramp climb with the sound on
const zp = loadScript(raw.replace(/^const SOUND = .*$/m, 'const SOUND = {"on": true, "name": "buttons/blip2", "volume": 45}; // movekit:sound'));
for (const [id, value] of Object.entries(S)) loaded.props.dynamicStyles[id].callbackFunc?.(loaded.p, value);
schedules = schedules.filter((x) => x.fn.name === 'loop').slice(-1); // the new copy's loop; the old one stops (live())
for (let i = 0; i < 2; i++) {
	frame(0);
	for (let vz = 290; vz > -290; vz -= 12) frame(vz);
	frame(0);
}
frame(-40);
for (let vz = -21.53; vz < 100; vz += 7.9) frame(vz);
expect(panel.visible, true, 'a ramp climb shows');
expect(labelTexts(), ['Z PENALTY', 'z 97', '13 ticks'], 'label, z speed, ticks so far');
expect(commands, ['playvol buttons/blip2 0.45'], 'the baked sound, once per stretch');
const marker = panel.FindChildTraverse('ZPenaltyMarker');
expect([marker.style.position, marker.style.backgroundColor], [`0px ${api.barGeometry(96.69, S).marker}px 0px`, S.penaltyColor], 'marker placed and in the penalty colour');
const fades = schedules.length;
for (let vz = 100; vz < 170; vz += 7.9) frame(vz);
expect(labelTexts(), ['z 163', '19 ticks'], 'out of the band: held, label gone, the stretch\'s count stays');
expect(schedules.length, fades + 1, 'a fade scheduled');
const fade = schedules.find((x) => x.s === 1.5);
schedules = schedules.filter((x) => x !== fade);
fade.fn();
expect([panel.style.opacity, panel.style.transitionDuration], ['0', '0.3s'], 'fading after holdMs');
schedules.find((x) => x.s > 0.3 && x.s < 0.4).fn();
expect(panel.visible, false, 'hidden after the fade');
schedules = schedules.filter((x) => x.fn.name === 'loop');
// a second stretch right after: no second sound within half a second
now -= 0;
frame(0);
frame(60);
expect(commands.length, 1, 'no second sound inside half a second');
frame(0);
now += 600;
frame(60);
expect(commands.length, 2, 'a new stretch after half a second sounds again');
frame(0);
// not own play
const quiet = (what, set, undo) => {
	set();
	frame(0);
	frame(60);
	expect(panel.visible, false, what);
	frame(0);
	undo();
};
schedules = schedules.filter((x) => x.fn.name === 'loop');
quiet('a replay shows nothing', () => (G.replay = 1), () => (G.replay = 0));
quiet('a watched run shows nothing', () => (G.observed = { tempId: 1 }), () => (G.observed = null));
quiet('spectating shows nothing', () => fire('MomentumSpectateStart'), () => fire('MomentumSpectateStop'));
quiet('observer move type shows nothing', () => (G.moveType = 10), () => (G.moveType = 2));
quiet('bhop shows nothing', () => (G.mode = 2), () => (G.mode = 1));
quiet('switched off shows nothing', () => (GLOBAL.HudCustomizerHandler.components = { MovekitZPenalty: { enabled: false } }),
	() => delete GLOBAL.HudCustomizerHandler.components);
// always shown
loaded.props.dynamicStyles.alwaysShow.callbackFunc(loaded.p, true);
frame(0);
expect([panel.visible, labelTexts()], [true, ['z 0', '1 tick']], 'always shown: there with nothing penalised, the last stretch\'s count');
loaded.props.dynamicStyles.alwaysShow.callbackFunc(loaded.p, false);
// the customizer's sample
const settingsList = new FakePanel('Panel', null, 'ActiveComponentSettingsList');
const box = new FakePanel('TextEntry', new FakePanel('NumberEntry', settingsList, 'NumberEntry'), '');
GLOBAL.HudCustomizerHandler.panels = { activeComponentSettingsList: settingsList };
GLOBAL.HudCustomizerHandler.activeComponent = { id: 'MovekitZPenalty' };
fire('HudCustomizer_Opened');
expect([panel.visible, labelTexts()], [true, ['Z PENALTY', 'z 96', '12 ticks']], 'sample in the customizer');
schedules.filter((x) => x.fn.name === 'fixBoxes').forEach((x) => x.fn());
expect(box.style.width, '44px', 'number boxes widened');
frame(0);
expect(labelTexts(), ['Z PENALTY', 'z 96', '12 ticks'], 'play doesn\'t replace the sample while editing');
loaded.props.dynamicStyles.showTicks.callbackFunc(loaded.p, false);
expect(labelTexts(), ['Z PENALTY', 'z 96'], 'a changed setting redraws the sample');
fire('HudCustomizer_Closed');
expect(panel.visible, false, 'hidden when the customizer closes');
expect(hud.children.filter((c) => c.id === 'MovekitZPenalty').length, 1, 'one panel after a reload');

const fp = { dynamicStyles: { g: { type: 0, children: [{ styleID: 'a' }, { styleID: 'b' }] }, a: { type: 1 }, b: { type: 2 } } };
const fit = api.fitLayout(fp, { a: 1 });
expect([Object.keys(fit.dynamicStyles), fit.dynamicStyles.g.children.map((c) => c.styleID)], [['g', 'a'], ['a']],
	'stale layout: the missing setting left out, and out of its group');
console.log('check_z_penalty: all good');
