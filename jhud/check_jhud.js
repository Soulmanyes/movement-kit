#!/usr/bin/env node
// Checks jhud/panorama/scripts/hud/movekit-jhud.ts in node, with Panorama stubbed (types stripped, as
// strafe-review/viewer/check_line.js does).
//
// Usage: node jhud/check_jhud.js [--store DIR]   (exits 1 on the first failure)
//
// Covers: the customizer settings (every STYLES row has a DEFAULTS value and sits in one group) against
// install.py's hud_default.kv3 entry (same keys, same values); jumpOf, shows, the gain colour scale and
// the row text; the Panorama side: the customizer gets the component for bhop modes only, the first
// takeoff shows its number and speed, other modes and a panel switched off in the customizer show
// nothing, a jump shows its rows and
// fades after holdMs, the customizer's sample while it is open; then every saved jump event in Strafe
// Review's store (--store, default ~/.local/share/strafe-review/attempts; skipped when missing) gives
// rows with no NaN or undefined.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const zlib = require('zlib');
const { stripTypeScriptTypes } = require('module');

const TS = path.join(__dirname, 'panorama/scripts/hud/movekit-jhud.ts');
const INSTALL = path.join(__dirname, 'install.py');
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
	DeleteAsync() { this.valid = false; this.parent.children = this.parent.children.filter((c) => c !== this); }
	RemoveAndDeleteChildren() { this.children = []; }
}
const hud = new FakePanel('Hud', null, 'Hud');
const timer = new FakePanel('MomHudTimer', hud, 'Timer');
const handlers = {};
let schedules = [];
let mode = 2;
let stats = null;
let loaded = null;
let loads = 0;
// one global object for every load, as Panorama keeps it across panorama_reload
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
	MomentumMovementAPI: { GetLastJumpStats: () => stats },
	UiToolkitAPI: { GetGlobalObject: () => GLOBAL },
	console
};
const src = stripTypeScriptTypes(fs.readFileSync(TS, 'utf8'), { mode: 'strip' });
// One load of the script in a fresh context; the panels, event handlers and global object are shared,
// so a second load is panorama_reload: the first load's handlers stay registered.
function loadScript() {
	const ctx = { ...stubs };
	vm.createContext(ctx);
	vm.runInContext(`${src}
globalThis.__api = { DEFAULTS, STYLES, SAMPLE, PACE, parseColor, mixColor, gainColor, paceColor, lineColor, jumpOf, shows, rows, settings, NONE };`, ctx);
	return ctx.__api;
}
const api = loadScript();
const fire = (ev) => (handlers[ev] || []).forEach((fn) => fn());
const texts = (p) => p.children.map((line) => line.children.map((l) => l.text));
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
if (!/^    MovekitJhud = \n/.test(entry[1])) fail('kv3 entry is not for the panel id MovekitJhud');

// ---- plain functions ----
const S = { ...api.DEFAULTS, fontColor: 'rgba(255, 255, 255, 1)' };
expect(api.parseColor('rgba(1, 2, 3, 0.5)'), [1, 2, 3, 0.5], 'parse rgba');
expect(api.parseColor('#ff8000'), [255, 128, 0, 1], 'parse hex');
expect(api.parseColor('blue'), null, 'parse junk');
expect(api.gainColor(40, S), 'rgba(255, 92, 92, 1)', 'gain under red: red');
expect(api.gainColor(60, S), 'rgba(255, 92, 92, 1)', 'gain at red: red');
expect(api.gainColor(95, S), 'rgba(123, 216, 143, 1)', 'gain at green: green');
expect(api.gainColor(120, S), 'rgba(123, 216, 143, 1)', 'gain over green: green');
expect(api.gainColor(77.5, S), 'rgba(189, 154, 118, 1)', 'gain half way: mixed');
expect(api.gainColor(70, { ...S, gainRed: 90, gainGreen: 80 }), 'rgba(255, 92, 92, 1)', 'thresholds the wrong way round');
expect([0, 1, 2, 3].map((c) => api.jumpOf({ jumpCount: c })), [0, 1, 2, 3], 'jumpOf: labelled with the takeoff number');
const pick = (first, every) => [1, 2, 3, 4, 5, 6, 7].filter((n) => api.shows(n, { firstJump: first, everyJump: every }));
expect(pick(1, 1), [1, 2, 3, 4, 5, 6, 7], 'shows every jump');
expect(pick(2, 2), [2, 4, 6], 'shows from 2, every 2nd');
expect(pick(3, 0), [3], 'every 0: only the first');
expect(pick(0, 1), [1, 2, 3, 4, 5, 6, 7], 'first 0 counts as 1');
const st = { jumpCount: 4, takeoffSpeed: 508.81, jumpSpeedDelta: 65.28, speedGain: 0.92076, strafeSync: 1, strafeCount: 2,
	yawRatio: 0.9319, efficiency: 0.5817, heightDelta: -0.04, distance: 357.89, timeDelta: 0.75 };
expect(S.colorBy, 'off', 'not coloured by default');
expect([...new Set(api.rows(st, 3, S)[0].map((p) => p.color))], [null], 'colorBy off: the whole line in the font colour');
expect([...new Set(api.rows(st, 3, { ...S, gainAll: false })[0].map((p) => p.color))], [null], 'colorBy off, gainAll off: font colour too');
const SG = { ...S, colorBy: 'gain' };
const r = api.rows(st, 3, SG);
const GC = api.gainColor(92.076, S);
expect(r.map((row) => row.map((p) => p.text)), [['3:', '509', '(+65)', '92.1 %', 'sync 100 %']], 'default: one line');
expect([...new Set(r[0].map((p) => p.color))], [GC], 'gainAll: the whole line in the gain colour');
const own = api.rows(st, 3, { ...SG, gainAll: false })[0];
expect(own.map((p) => p.color), [null, null, null, GC, null], 'gainAll off: only the gain % coloured');
expect(api.rows({ ...st, jumpSpeedDelta: -3.4 }, 3, S)[0][2].text, '(-3)', 'speed down');
const all = Object.fromEntries(Object.keys(S).map((k) => [k, k.startsWith('show') ? true : S[k]]));
expect(api.rows(st, 3, all).map((row) => row.map((p) => p.text)),
	[['3:', '509', '(+65)', '92.1 %', 'sync 100 %', '2 strafes', 'ratio 0.93', 'eff 58 %', 'h +0.0', '357.9 u', '0.75 s']], 'every field: still one line');
const none = Object.fromEntries(Object.keys(S).map((k) => [k, k.startsWith('show') ? false : S[k]]));
expect(api.rows(st, 3, none), [], 'no fields: no rows');
// speed pace: on pace for speed / PACE share at the cutoff, the highest tier reached
const SP = { ...S, colorBy: 'pace' };
const T1 = S.tier1Color, T2 = S.tier2Color, T3 = S.tier3Color, BELOW = S.belowColor;
expect(api.PACE['6'].length, 5, 'cutoff 6: jumps 2-6');
expect(api.PACE['12'].length, 11, 'cutoff 12: jumps 2-12');
expect([api.PACE['6'][4], api.PACE['12'][10]], [1, 1], 'the cutoff jump is its own speed');
const paceAt = (n, onPace, cut = '6') => api.paceColor(api.PACE[cut][n - 2] * onPace, n, { ...SP, paceCut: cut });
expect([paceAt(4, 600), paceAt(4, 620.5), paceAt(4, 627), paceAt(4, 640)], [BELOW, T1, T2, T3], 'jump 4: below, tier 1, 2, 3');
expect([paceAt(6, 619.9), paceAt(6, 625), paceAt(6, 630)], [BELOW, T2, T3], 'the cutoff jump by its own speed');
expect(api.paceColor(290, 1, SP), null, 'jump 1 not judged');
expect(api.paceColor(700, 7, SP), null, 'past cutoff 6 not judged');
expect(paceAt(7, 626, '12'), T2, 'cutoff 12 judges jump 7');
expect(api.paceColor(api.PACE['6'][2] * 627, 4, { ...SP, tier1Speed: 630, tier3Speed: 620 }), T2, 'tiers in any order');
const pst = { ...st, jumpCount: 4, takeoffSpeed: api.PACE['6'][2] * 626 };
const pl = api.rows(pst, 4, SP)[0];
expect([...new Set(pl.map((p) => p.color))], [T2], 'pace: the whole line in the tier colour');
expect(api.rows(pst, 4, { ...SP, gainAll: false })[0].map((p) => p.color), [null, T2, null, null, null], 'pace, gainAll off: only the speed');
expect(api.rows({ ...st, jumpCount: 7 }, 7, { ...SP, gainAll: false })[0].map((p) => p.color), [null, null, null, GC, null],
	'past the cutoff: gain colour on the gain %');
expect(api.rows({ ...st, jumpCount: 1 }, 1, SP)[0].map((p) => p.color), [null, null], 'pace: jump 1 in the font colour');
const one = api.rows({ ...st, jumpCount: 1, speedGain: 0 }, 1, SG);
expect(one.map((row) => row.map((p) => p.text)), [['1:', '509']], 'takeoff 1: number and speed only');
expect(one[0].map((p) => p.color), [null, null], 'takeoff 1: font colour, no gain yet');
expect(api.rows(st, 1, { ...none, showGain: true }), [], 'takeoff 1 with only gain on: no rows');
// the owner's pick on 2026-11-03 (number, speed, gain, yaw ratio) came out on three lines before
expect(api.rows(st, 3, { ...none, showNumber: true, showSpeed: true, showGain: true, showYawRatio: true }).map((row) => row.map((p) => p.text)),
	[['3:', '509', '92.1 %', 'ratio 0.93']], 'a few fields: one line');

// ---- Panorama side ----
expect(loads, 0, 'no registration before the customizer is ready');
fire('HudCustomizer_Ready');
GLOBAL.HudCustomizerHandler.customizerReady = true;
if (!loaded) fail('the customizer got no component');
expect(loaded.p.id, 'MovekitJhud', 'component panel id');
expect(loaded.props.gamemode, [2, 3], 'bhop modes only');
expect(Object.keys(loaded.props.dynamicStyles).sort(), api.STYLES.map((x) => x[0]).sort(), 'every row in the customizer');
// the customizer calls back each setting with its saved value (shared "$" values come resolved)
for (const [id, value] of Object.entries(S)) {
	const d = loaded.props.dynamicStyles[id];
	if (d.callbackFunc) d.callbackFunc(loaded.p, value);
}
expect(api.settings.fontColor, S.fontColor, 'callback stores the setting');
const cb = loaded.props.dynamicStyles.colorBy;
expect([cb.type, cb.options.map((o) => o.value)], [4, ['off', 'gain', 'pace']], 'colorBy: a dropdown, off, gain and pace');
const PACE_IDS = ['paceCut', 'tier1Speed', 'tier1Color', 'tier2Speed', 'tier2Color', 'tier3Speed', 'tier3Color', 'belowColor'];
const GAIN_IDS = ['gainAll', 'gainRed', 'gainGreen', 'redColor', 'greenColor'];
expect(Object.fromEntries(cb.children.map((c) => [c.styleID, c.showWhen])),
	Object.fromEntries(cb.children.map((c) => [c.styleID, PACE_IDS.includes(c.styleID) ? ['pace'] : ['gain', 'pace']])),
	'pace settings show only for pace, gain settings for gain and pace (gain after the cutoff)');
expect([...cb.children.map((c) => c.styleID)].sort(), [...PACE_IDS, ...GAIN_IDS].sort(), 'colorBy holds the pace and gain settings');
for (const [id, , type] of api.STYLES) {
	if (type !== 1) continue;
	const sp = loaded.props.dynamicStyles[id].settingProps;
	if (!sp || !(sp.min <= S[id] && S[id] <= sp.max)) fail(`number box ${id}: no min/max around its default (${JSON.stringify(sp)})`);
}
expect(loaded.props.dynamicStyles.paceCut.options.map((o) => o.value), ['6', '12'], 'cutoff 6 or 12');
expect(loaded.props.dynamicStyles.colours.children.map((c) => c.styleID), ['colorBy'], 'the colours group holds colorBy');
expect(loaded.props.dynamicStyles.backgroundColor.styleProperty, 'backgroundColor', 'background on the panel itself');
const panel = hud.FindChildTraverse('MovekitJhud');
expect(panel && panel.visible, false, 'hidden until a jump');

stats = { ...st, jumpCount: 1, speedGain: 0 };
fire('OnJumpStarted');
expect(panel.visible, true, 'the first takeoff shows');
expect(texts(panel), [['1:', '509']], 'the first takeoff: number and speed');
if (!panel.children[0].children.every((l) => l.styleText.includes(`color: ${S.fontColor};`))) fail('the first takeoff not in the font colour');
runSchedules();
runSchedules();
expect(panel.visible, false, 'the first takeoff fades');
stats = st;
mode = 1;
fire('OnJumpStarted');
expect(panel.visible, false, 'surf shows nothing');
mode = 2;
panel.enabled = false;
fire('OnJumpStarted');
expect(panel.visible, false, 'switched off in the customizer shows nothing');
panel.enabled = true;
fire('OnJumpStarted');
expect(panel.visible, true, 'a bhop jump shows');
expect(texts(panel), [['4:', '509', '(+65)', '92.1 %', 'sync 100 %']], 'drawn line');
if (!panel.children[0].children.every((l) => l.styleText.includes(`color: ${S.fontColor};`))) fail('drawn line not in the font colour (colorBy off)');
expect(panel.style.opacity, '1', 'shown fully');
expect(runSchedules(), [2], 'held for holdMs');
expect([panel.style.opacity, panel.style.transitionDuration], ['0', '0.3s'], 'fading over fadeMs');
runSchedules();
expect(panel.visible, false, 'hidden after the fade');
cb.callbackFunc(loaded.p, 'gain');
fire('OnJumpStarted');
if (!panel.children[0].children.every((l) => l.styleText.includes(`color: ${GC};`))) fail('drawn line not all in the gain colour (colorBy gain)');
cb.callbackFunc(loaded.p, 'off');
runSchedules();
runSchedules();
expect(panel.visible, false, 'colorBy gain line faded');
// a new jump while one is held replaces it, and the old timer doesn't hide the new one
fire('OnJumpStarted');
stats = { ...st, jumpCount: 5 };
fire('OnJumpStarted');
const first = schedules[0];
schedules = [schedules[1]];
first.fn();
expect(panel.style.opacity, '1', 'an old jump\'s timer leaves the new one');
expect(texts(panel)[0][0], '5:', 'the newer jump drawn');
schedules = [];

// the customizer: a sample to drag while it is open, hidden when it closes
// the customizer's settings list, as it builds it: rows with a NumberEntry holding a TextEntry
const settingsList = new FakePanel('Panel', null, 'ActiveComponentSettingsList');
const row = new FakePanel('Panel', new FakePanel('Panel', settingsList, 'ParentWrapper'), '');
const box = new FakePanel('TextEntry', new FakePanel('NumberEntry', row, 'NumberEntry'), '');
const colour = new FakePanel('TextEntry', row, '');
GLOBAL.HudCustomizerHandler.panels = { activeComponentSettingsList: settingsList };
GLOBAL.HudCustomizerHandler.activeComponent = { id: 'Timer' };
fire('HudCustomizer_Opened');
expect(panel.visible, true, 'sample shown in the customizer');
expect(texts(panel)[0], ['7:', '642', '(+48)', '87.4 %', 'sync 93 %'], 'sample line');
expect(schedules.map((x) => x.s), [0.25], 'sample is held (only the number box check is scheduled)');
expect(box.style.width, undefined, 'another component\'s number boxes are left alone');
GLOBAL.HudCustomizerHandler.activeComponent = { id: 'MovekitJhud' };
runSchedules();
expect([box.style.width, colour.style.width], ['44px', undefined], 'JHUD\'s number boxes widened, other text fields not');
expect(schedules.length, 1, 'still checking while the customizer is open');
fire('OnJumpStarted');
expect(texts(panel)[0][0], '7:', 'jumps don\'t replace the sample while editing');
loaded.props.dynamicStyles.showSpeed.callbackFunc(loaded.p, false);
expect(texts(panel)[0], ['7:', '(+48)', '87.4 %', 'sync 93 %'], 'a changed setting redraws the sample');
loaded.props.dynamicStyles.showSpeed.callbackFunc(loaded.p, true);
fire('HudCustomizer_Closed');
expect(panel.visible, false, 'hidden when the customizer closes');
runSchedules();
expect(schedules.length, 0, 'number box check stops when the customizer closes');
mode = 1;
fire('HudCustomizer_Opened');
expect(panel.visible, false, 'no sample outside bhop');
expect(schedules.length, 0, 'no number box check outside bhop');
fire('HudCustomizer_Closed');
mode = 2;

// panorama_reload in a map: the new copy takes over the placed panel and registers at once (no
// HudCustomizer_Ready until the next map), the old copy's handlers do nothing
stats = st;
fire('OnJumpStarted');
const oldTimers = schedules; // the old copy's hold timer, still pending at the reload
schedules = [];
const before = loads;
const api2 = loadScript();
expect(loads, before + 1, 'registered at load after a reload');
expect(loaded.p === panel, true, 'the placed panel taken over, not replaced');
expect(panel.valid, true, 'the panel survives the reload');
for (const [id, value] of Object.entries({ ...S, showSpeed: false })) {
	const d = loaded.props.dynamicStyles[id];
	if (d.callbackFunc) d.callbackFunc(loaded.p, value);
}
expect(api2.settings.showSpeed, false, 'the new copy gets the saved settings');
stats = { ...st, jumpCount: 6 };
fire('OnJumpStarted');
expect(panel.visible, true, 'shows after a reload');
expect(texts(panel), [['6:', '(+65)', '92.1 %', 'sync 100 %']], 'drawn once, by the new copy with its settings');
expect(schedules.length, 1, 'only the new copy schedules a fade');
oldTimers.forEach((x) => x.fn());
expect([panel.visible, panel.style.opacity], [true, '1'], 'the old copy\'s pending timer leaves the new jump');
runSchedules();
runSchedules();
expect(panel.visible, false, 'the new copy fades it');
expect(hud.children.filter((c) => c.id === 'MovekitJhud').length, 1, 'one JHUD panel');

// ---- saved jump events ----
let n = 0;
if (fs.existsSync(store)) {
	const allOn = { ...all };
	for (const m of fs.readdirSync(store)) {
		const dir = path.join(store, m);
		if (!fs.statSync(dir).isDirectory()) continue;
		for (const f of fs.readdirSync(dir)) {
			if (!f.endsWith('.json.gz')) continue;
			const a = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(dir, f))).toString());
			for (const e of a.events || []) {
				if (e.kind !== 'jump') continue;
				const s = { jumpCount: e.n, takeoffSpeed: e.takeoff, jumpSpeedDelta: e.delta, speedGain: e.gain,
					strafeSync: e.sync, strafeCount: e.strafes, yawRatio: e.ratio, efficiency: e.eff,
					heightDelta: e.height, distance: e.distance, timeDelta: e.timeDelta ?? 0 };
				const j = api.jumpOf(s);
				if (j < 1) continue;
				const out = JSON.stringify(['off', 'gain', 'pace'].map((colorBy) => api.rows(s, j, { ...allOn, colorBy })));
				if (/NaN|undefined|Infinity/.test(out)) fail(`${f} jump ${e.n}: ${out}`);
				n++;
			}
		}
	}
}
console.log(`check_jhud: all good (${n} saved jumps drawn${n ? '' : '; no store'})`);
