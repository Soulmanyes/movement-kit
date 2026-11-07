#!/usr/bin/env node
// Checks zone-exit/panorama/scripts/hud/movekit-zone-exit.ts in node, with Panorama stubbed (types
// stripped, as jhud/check_jhud.js does).
//
// Usage: node zone-exit/check_zone_exit.js   (exits 1 on the first failure)
//
// Covers: the customizer settings (every STYLES row has a DEFAULTS value and sits in one group) against
// install.py's hud_default.kv3 entry (same keys, same values); speed3 on both velocity shapes, the band
// colours and the line text; the Panorama side, with the probe's numbers (2026-11-04, surf_aura): the
// customizer gets the component for surf only, a start zone exit shows the player's 3D speed and the
// difference to the comparison run's split, a filled split wins over the player's velocity, falling
// speed counted up to 322, stages,
// replays, spectating, other modes, another track's comparison and a panel switched off show nothing or
// no diff, the fade, the customizer's sample, panorama_reload.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { stripTypeScriptTypes } = require('module');

const TS = path.join(__dirname, 'panorama/scripts/hud/movekit-zone-exit.ts');
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
const TRACK = { type: 2, number: 1 }; // the probe's main track
// the game's state, as the probe logged it at a start zone exit on surf_aura
const G = {
	mode: 1, replay: 0, observed: null, moveType: 2,
	status: { state: 2, majorNum: 1, minorNum: 1, trackId: TRACK },
	splits: { segments: [{ effectiveStartVelocity: [0, 0, 0] }] },
	velocity: { x: 300, y: -120, z: 140 }, // 3D 352.1
	comparison: { trackId: TRACK, runSplits: { segments: [{ effectiveStartVelocity: [327.41912841796875, -93.68795776367188, -250.00662231445312] }] } }
};
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
	GameModeAPI: { GetCurrentGameMode: () => G.mode },
	MomentumReplayAPI: { GetReplayState: () => G.replay },
	MomentumMovementAPI: { GetMoveType: () => G.moveType },
	MomentumPlayerAPI: { GetVelocity: () => G.velocity },
	MomentumTimerAPI: {
		GetObservedTimerStatus: () => G.status,
		GetObservedTimerRunSplits: () => G.splits,
		GetObservedRunMetadata: () => G.observed
	},
	RunComparisonsAPI: { GetComparisonRun: () => G.comparison },
	UiToolkitAPI: { GetGlobalObject: () => GLOBAL },
	console
};
const src = stripTypeScriptTypes(fs.readFileSync(TS, 'utf8'), { mode: 'strip' });
function loadScript() {
	const ctx = { ...stubs };
	vm.createContext(ctx);
	vm.runInContext(`${src}
globalThis.__api = { DEFAULTS, STYLES, SAMPLE, fitLayout, speed3, bandColor, rows, settings, NONE };`, ctx);
	return ctx.__api;
}
const api = loadScript();
const fire = (ev) => (handlers[ev] || []).forEach((fn) => fn());
const texts = (p) => p.children.map((line) => line.children.map((l) => l.text));
const colours = (p) => p.children[0].children.map((l) => /color: ([^;]+);/.exec(l.styleText)[1]);
const runSchedules = () => { const s = schedules; schedules = []; s.forEach((x) => x.fn()); return s.map((x) => x.s); };

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
if (!/^    MovekitZoneExit = \n/.test(entry[1])) fail('kv3 entry is not for the panel id MovekitZoneExit');

// ---- plain functions ----
const S = { ...api.DEFAULTS, fontColor: 'rgba(255, 255, 255, 1)' };
const [LOW, MID, HIGH, FAST, SLOW] = [S.lowColor, S.midColor, S.highColor, S.fasterColor, S.slowerColor];
const CMP = 422.4737; // the probe's PB split, 3D
expect(+api.speed3(G.comparison.runSplits.segments[0].effectiveStartVelocity).toFixed(4), CMP, 'speed3 of a split array');
expect(+api.speed3({ x: 3, y: 4, z: 12 }).toFixed(4), 13, 'speed3 of {x, y, z}, z counts');
expect([null, undefined].map((v) => isNaN(api.speed3(v))), [true, true], 'speed3 of nothing is NaN');
expect(+api.speed3([0, 0, -334]).toFixed(4), 322, 'speed3 counts falling speed up to 322');
expect(+api.speed3({ x: 0, y: 0, z: 400 }).toFixed(4), 400, 'speed3 doesn\'t limit rising speed');
expect([300, 399.9, 400, 410, 420, 420.1, 500, NaN].map((v) => api.bandColor(v, S)), [LOW, LOW, MID, MID, MID, HIGH, HIGH, LOW],
	'bands: amber under 400, green 400-420 (both in), blue above');
expect(api.bandColor(350, { ...S, speedLow: 300, speedHigh: 340 }), HIGH, 'band speeds can be set');
for (const k of ['lowColor', 'midColor', 'highColor']) {
	const jhud = fs.readFileSync(path.join(__dirname, '..', 'jhud', 'panorama', 'scripts', 'hud', 'movekit-jhud.ts'), 'utf8');
	const m = new RegExp(`^\\t${k}: (.+),$`, 'm').exec(jhud);
	if (!m || eval(m[1]) !== S[k]) fail(`${k}: ${S[k]} isn't JHUD's ${m && m[1]}`);
}
const line = (sp, cmp, s = S) => api.rows(sp, cmp, s).map((r) => r.map((p) => [p.text, p.color]));
expect(line(429.4, CMP), [[['429', HIGH], ['+7', FAST]]], 'faster than the PB: blue, +7');
expect(line(392.9, CMP), [[['393', LOW], ['-29', SLOW]]], 'slower: amber, -29');
expect(line(418.4, 410.6), [[['418', MID], ['+7', FAST]]], 'diff from the shown (rounded) numbers');
expect(line(422.4, CMP), [[['422', HIGH], ['+0', FAST]]], 'level with the PB: +0');
expect(line(412, null), [[['412', MID]]], 'no comparison: no diff');
expect(line(412, CMP, { ...S, showDiff: false }), [[['412', MID]]], 'diff switched off');
expect(line(412, CMP, { ...S, colorBands: false }), [[['412', null], ['-10', SLOW]]], 'bands off: the font colour');
expect(api.rows(NaN, CMP, S), [], 'no speed: no rows');

// ---- Panorama side ----
expect(loads, 0, 'no registration before the customizer is ready');
fire('HudCustomizer_Ready');
GLOBAL.HudCustomizerHandler.customizerReady = true;
if (!loaded) fail('the customizer got no component');
expect(loaded.p.id, 'MovekitZoneExit', 'component panel id');
expect([loaded.props.name, loaded.props.gamemode], ['Zone Exit', [1]], 'listed as Zone Exit, surf only');
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
const cb = loaded.props.dynamicStyles.colorBands;
expect(cb.children.map((c) => [c.styleID, c.showWhen]), ['speedLow', 'speedHigh', 'lowColor', 'midColor', 'highColor'].map((id) => [id, [true, 1]]),
	'band settings show while Colour the speed is ticked');
expect(loaded.props.dynamicStyles.showDiff.children.map((c) => [c.styleID, c.showWhen]), [['fasterColor', [true, 1]], ['slowerColor', [true, 1]]],
	'diff colours show while the diff is ticked');
expect(loaded.props.dynamicStyles.backgroundColor.styleProperty, 'backgroundColor', 'background on the panel itself');
const panel = hud.FindChildTraverse('MovekitZoneExit');
expect(panel && panel.visible, false, 'hidden until a zone exit');

const exit = () => fire('OnObservedTimerSegmentEffectiveStart');
const quiet = (what, undo) => {
	exit();
	expect(panel.visible, false, what);
	undo();
};
exit();
expect(panel.visible, true, 'a start zone exit shows');
expect(texts(panel), [['352', '-70']], 'the player\'s 3D speed (the split is still 0) and the diff to the PB\'s split');
expect(colours(panel), [LOW, SLOW], 'amber, slower');
expect(panel.style.opacity, '1', 'shown fully');
expect(runSchedules(), [3], 'held for holdMs');
expect([panel.style.opacity, panel.style.transitionDuration], ['0', '0.3s'], 'fading over fadeMs');
runSchedules();
expect(panel.visible, false, 'hidden after the fade');
G.splits = { segments: [{ effectiveStartVelocity: [330, -90, 260] }] };
exit();
expect(texts(panel)[0][0], '430', 'a filled split wins over the player\'s velocity');
G.splits = { segments: [{ effectiveStartVelocity: [0, 0, 0] }] };
runSchedules();
runSchedules();
// the -334 exit on surf_deadline (stage replay, 2026-11-07): 484.0 counted in full, 475.8 with falling speed
// counted up to 322
const plain = G.velocity;
G.velocity = { x: 331.2524719238281, y: 113.99437713623047, z: -334.0066223144531 };
exit();
expect(texts(panel), [['476', '+54']], 'falling speed counted up to 322');
runSchedules();
runSchedules();
const pb = G.comparison;
G.comparison = { trackId: TRACK, runSplits: { segments: [{ effectiveStartVelocity: [331.2524719238281, 113.99437713623047, -334.0066223144531] }] } };
exit();
expect(texts(panel), [['476', '+0']], 'the comparison\'s falling speed is counted up to 322 too');
runSchedules();
runSchedules();
G.comparison = pb;
G.velocity = plain;
G.status = { ...G.status, majorNum: 2 };
quiet('a stage start shows nothing', () => (G.status = { ...G.status, majorNum: 1 }));
G.status = { ...G.status, state: 1 };
quiet('a timer that isn\'t running shows nothing', () => (G.status = { ...G.status, state: 2 }));
G.mode = 2;
quiet('bhop shows nothing', () => (G.mode = 1));
G.replay = 1;
quiet('a replay shows nothing', () => (G.replay = 0));
G.observed = { tempId: 3 };
quiet('a watched run shows nothing', () => (G.observed = null));
fire('MomentumSpectateStart');
quiet('spectating shows nothing', () => fire('MomentumSpectateStop'));
G.moveType = 10;
quiet('observer move type shows nothing', () => (G.moveType = 2));
panel.enabled = false;
quiet('switched off in the customizer shows nothing', () => (panel.enabled = true));
// the customizer's own record wins over the panel's flag
GLOBAL.HudCustomizerHandler.components = { MovekitZoneExit: { enabled: false } };
quiet('switched off in the customizer\'s record, panel flag on: nothing', () => (GLOBAL.HudCustomizerHandler.components.MovekitZoneExit.enabled = true));
panel.enabled = false;
exit();
expect(panel.visible, true, 'switched on in the customizer\'s record wins over a stale panel flag');
panel.enabled = true;
delete GLOBAL.HudCustomizerHandler.components;
runSchedules();
runSchedules();
G.comparison = { ...G.comparison, trackId: { type: 1, number: 1 } };
exit();
expect(texts(panel), [['352']], 'another track\'s comparison: no diff');
G.comparison = null;
exit();
expect(texts(panel), [['352']], 'no comparison loaded: no diff');
G.comparison = { trackId: TRACK, runSplits: null };
exit();
expect(texts(panel), [['352']], 'a comparison without splits: no diff');
G.comparison = { trackId: TRACK, runSplits: { segments: [{ effectiveStartVelocity: [327.41912841796875, -93.68795776367188, -250.00662231445312] }] } };
// a new exit while one is held replaces it, and the old timer doesn't hide the new one
schedules = [];
exit();
G.velocity = { x: 330, y: -90, z: 250 };
exit();
const first = schedules[0];
schedules = [schedules[1]];
first.fn();
expect(panel.style.opacity, '1', 'an old exit\'s timer leaves the new one');
expect(texts(panel)[0][0], '424', 'the newer exit drawn');
schedules = [];

// the customizer: a sample to drag while it is open, hidden when it closes
const settingsList = new FakePanel('Panel', null, 'ActiveComponentSettingsList');
const row = new FakePanel('Panel', new FakePanel('Panel', settingsList, 'ParentWrapper'), '');
const box = new FakePanel('TextEntry', new FakePanel('NumberEntry', row, 'NumberEntry'), '');
GLOBAL.HudCustomizerHandler.panels = { activeComponentSettingsList: settingsList };
GLOBAL.HudCustomizerHandler.activeComponent = { id: 'MovekitZoneExit' };
fire('HudCustomizer_Opened');
expect(panel.visible, true, 'sample shown in the customizer');
expect(texts(panel), [['418', '+8']], 'sample line');
runSchedules();
expect(box.style.width, '44px', 'number boxes widened');
exit();
expect(texts(panel)[0][0], '418', 'exits don\'t replace the sample while editing');
loaded.props.dynamicStyles.showDiff.callbackFunc(loaded.p, false);
expect(texts(panel), [['418']], 'a changed setting redraws the sample');
loaded.props.dynamicStyles.showDiff.callbackFunc(loaded.p, true);
GLOBAL.HudCustomizerHandler.components = { MovekitZoneExit: { enabled: false } };
runSchedules();
expect(panel.visible, false, 'the sample hides when the switch goes off');
GLOBAL.HudCustomizerHandler.components.MovekitZoneExit.enabled = true;
runSchedules();
expect([panel.visible, texts(panel)], [true, [['418', '+8']]], 'and comes back when it goes on');
delete GLOBAL.HudCustomizerHandler.components;
fire('HudCustomizer_Closed');
expect(panel.visible, false, 'hidden when the customizer closes');
runSchedules();
expect(schedules.length, 0, 'number box check stops when the customizer closes');
G.mode = 2;
fire('HudCustomizer_Opened');
expect(panel.visible, false, 'no sample outside surf');
fire('HudCustomizer_Closed');
G.mode = 1;

// panorama_reload in a map: the new copy takes over the placed panel and registers at once, the old
// copy's handlers do nothing
const before = loads;
const api2 = loadScript();
expect(loads, before + 1, 'registered at load after a reload');
expect(loaded.p === panel, true, 'the placed panel taken over, not replaced');
for (const [id, value] of Object.entries({ ...S, showDiff: false })) {
	const d = loaded.props.dynamicStyles[id];
	if (d.callbackFunc) d.callbackFunc(loaded.p, value);
}
expect(api2.settings.showDiff, false, 'the new copy gets the saved settings');
exit();
expect(texts(panel), [['424']], 'drawn once, by the new copy with its settings');
expect(schedules.length, 1, 'only the new copy schedules a fade');
expect(hud.children.filter((c) => c.id === 'MovekitZoneExit').length, 1, 'one panel');

const fp = { dynamicStyles: { g: { type: 0, children: [{ styleID: 'a' }, { styleID: 'b' }] }, a: { type: 1 }, b: { type: 2 } } };
const fit = api.fitLayout(fp, { a: 1 });
expect([Object.keys(fit.dynamicStyles), fit.dynamicStyles.g.children.map((c) => c.styleID)], [['g', 'a'], ['a']],
	'stale layout: the missing setting left out, and out of its group');
GLOBAL.HudCustomizerHandler.loadComponent = () => { throw new Error('Could not load dynamic style value for x'); };
loadScript();
console.log('check_zone_exit: all good');
