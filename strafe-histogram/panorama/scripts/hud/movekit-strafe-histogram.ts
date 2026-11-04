// Strafe Speed Histogram, part of Soulmanyes's Movement Kit (strafe-histogram/ in the repo). Loaded next to
// timer.ts through the kit's timer.xml patch (movekit/panorama.py).
//
// While bhopping: one horizontal bar per air tick, the newest at the bottom, the older ones scrolling up.
// A bar's length is how fast you turned that tick against the optimal (the game's yawRatio, 1 = optimal);
// a marker line shows where the optimal is (the middle, or 3/4 of the width). Bars grow from the left, or
// from the sides by strafe (right strafes from the left edge, left strafes from the right; swapSides flips it).
// Ground ticks add no row, so the bars run on across jumps; standing still adds nothing, so they stay.
//
// Settings live in Momentum's HUD customizer, as JHUD's do: install.py hands the kit the panel's
// hud_default.kv3 entry (ENTRY there), whose dynamicStyles must list every setting in STYLES below with the
// value in DEFAULTS (check_strafe_histogram.js checks both).
//
// No imports, like JHUD. The plain functions (above "Panorama") are run in node by check_strafe_histogram.js.
// The Panorama part copies JHUD's fixes (load number, panel take-over, register after a reload, number box
// width): Panorama scripts can't import, and a shared script would tie two modules that install alone.

const ID = 'MovekitStrafeHist';
const GAMEMODES = [1, 2, 3]; // Gamemode.SURF, Gamemode.BHOP, Gamemode.BHOP_HL1 (common/web/enums/gamemode.enum)
// CustomizerPropertyType in common/hud-customizer.ts
const NONE = 0;
const NUMBER_ENTRY = 1;
const CHECKBOX = 2;
const DROPDOWN = 4;
const COLOR_PICKER = 5;

const GROUND_VZ = 1; // Strafe Review's data.js: a steady vz under this is ground

type Settings = Record<string, any>;

// Whether a tick is on the ground, from its vz and the ticks before and after (Strafe Review's rule, data.js
// parse): vz 0 is ground unless it sits between rising and falling (an apex), and a small vz the same as a
// neighbour's is ground too (a replay's steady start-zone vz; gravity changes it every air tick). So each
// tick is drawn one tick late, once the next one is known.
function onGround(vz: number, prevVz: number, nextVz: number): boolean {
	if (vz === 0) return !(prevVz > 0 && nextVz < 0);
	return Math.abs(vz) < GROUND_VZ && (prevVz === vz || nextVz === vz);
}

// Where the optimal sits, as a share of the width: the middle (the bars reach 2x the optimal) or 3/4 (1.33x)
function optimalAt(s: Settings): number {
	return s.optimalAt === 'three' ? 0.75 : 0.5;
}

// A bar's length as a share of the width: the ratio scaled so 1 lands on optimalAt, cut at 0 (turning
// against the strafe) and at the full width
function barLength(ratio: number, s: Settings): number {
	if (!isFinite(ratio) || ratio <= 0) return 0;
	return Math.min(1, ratio * optimalAt(s));
}

// The side a bar grows from: 'left', or with fromSides on, by the strafe (strafeRight: the game's tick stat):
// right strafes from the left edge and left strafes from the right (owner, 2026-11-03), swapSides the other way
function barSide(strafeRight: boolean, s: Settings): 'left' | 'right' {
	if (!s.fromSides) return 'left';
	return strafeRight !== !!s.swapSides ? 'left' : 'right';
}

// "rgba(r, g, b, a)" or "#rrggbb" as [r, g, b, a], or null (as JHUD's)
function parseColor(c: string): number[] | null {
	const m = /^\s*rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)\s*$/i.exec(c || '');
	if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
	const h = /^\s*#([0-9a-f]{6})\s*$/i.exec(c || '');
	if (h) return [0, 2, 4].map((i) => parseInt(h[1].slice(i, i + 2), 16)).concat(1);
	return null;
}

// a to b at t (0-1); a when either colour can't be read
function mixColor(a: string, b: string, t: number): string {
	const x = parseColor(a);
	const y = parseColor(b);
	if (!x || !y) return a;
	const k = Math.max(0, Math.min(1, t));
	const c = x.map((v, i) => v + (y[i] - v) * k);
	return `rgba(${Math.round(c[0])}, ${Math.round(c[1])}, ${Math.round(c[2])}, ${+c[3].toFixed(3)})`;
}

// The gain % a tick gets at this yaw ratio: 100 * (1 - (ratio - 1)^2), too slow and too fast alike. Fitted
// to the owner's saved bhop runs (2026-11-03, 1.0 M air ticks, median gain per 0.05 of ratio): 92 % at 0.718
// and 1.288 measured against 1 -/+ 0.283 from the curve, 86.5 % at 0.634 and 1.372 against 1 -/+ 0.367.
// Turning against the strafe (ratio 0 or below) gets 0 or less.
function gainOf(ratio: number): number {
	return isFinite(ratio) ? 100 * (1 - (ratio - 1) ** 2) : 0;
}

// colorBy 'gain': lowColor under gainLow, midColor up to gainHigh, highColor above (thresholds in tenths of
// a %, as the customizer's number boxes take whole numbers: 865 = 86.5 %)
function gainBand(ratio: number, s: Settings): string {
	const g = gainOf(ratio);
	if (g < +s.gainLow / 10) return s.lowColor;
	return g <= +s.gainHigh / 10 ? s.midColor : s.highColor;
}

// A bar's colour: one colour (colorBy 'plain'; growing from the sides, one per screen side, leftColor and
// rightColor, so a colour stays with its edge when the sides are swapped), or by how far the ratio is from 1
// (colorBy 'good'): goodColor at 1, badColor at badPct % away or more, too slow and too fast alike, or by
// the gain its turn speed gives (colorBy 'gain', gainBand)
function barColor(ratio: number, side: 'left' | 'right', s: Settings): string {
	if (s.colorBy === 'gain') return gainBand(ratio, s);
	if (s.colorBy !== 'good') return s.fromSides ? (side === 'left' ? s.leftColor : s.rightColor) : s.barColor;
	const far = Math.max(1, +s.badPct || 50) / 100;
	return mixColor(s.goodColor, s.badColor, isFinite(ratio) ? Math.abs(ratio - 1) / far : 1);
}

// The marker lines' positions (share of the width from the left): one at optimalAt, and with fromSides on and
// the optimal off the middle, the right strafes' one mirrored
function markers(s: Settings): number[] {
	const at = optimalAt(s);
	return s.fromSides && at !== 0.5 ? [at, 1 - at] : [at];
}

// How one row is drawn: width in % of the panel, the side it grows from, its colour
function rowStyle(ratio: number, strafeRight: boolean, s: Settings): { width: number; side: 'left' | 'right'; color: string } {
	const side = barSide(strafeRight, s);
	return { width: Math.round(barLength(ratio, s) * 1000) / 10, side, color: barColor(ratio, side, s) };
}

const DEFAULTS: Settings = {
	backgroundColor: 'rgba(0, 0, 0, 0.25)',
	rows: 100,
	rowHeight: 2,
	optimalAt: 'middle',
	fromSides: false,
	swapSides: false,
	leftColor: 'rgba(92, 160, 255, 0.9)',
	rightColor: 'rgba(255, 170, 80, 0.9)',
	colorBy: 'plain',
	barColor: 'rgba(255, 255, 255, 0.85)',
	goodColor: 'rgba(123, 216, 143, 1)',
	badColor: 'rgba(255, 92, 92, 1)',
	badPct: 50,
	gainLow: 865,
	gainHigh: 920,
	lowColor: 'rgba(255, 176, 50, 1)',
	midColor: 'rgba(123, 216, 143, 1)',
	highColor: 'rgba(92, 160, 255, 1)',
	showMarker: true,
	markerColor: 'rgba(255, 220, 90, 0.9)'
};

const OPTIMAL_AT = [
	{ label: 'Middle', value: 'middle' },
	{ label: '3/4 of the width', value: 'three' }
];
const COLOR_BY = [
	{ label: 'Plain (one colour)', value: 'plain' },
	{ label: 'How good (by distance from optimal)', value: 'good' },
	{ label: 'Gain % (what the turn speed gains)', value: 'gain' }
];
type Extra = {
	options?: { label: string; value: string }[];
	showWhen?: Record<string, (string | boolean)[]>;
	range?: { min: number; max: number; increment?: number };
};
// A box's min is 0 and its max roomy: the NumberEntry clamps on every keystroke, so a min of 10 snaps "2"
// (on the way to 200) back to 10 (owner, 2026-11-03). The real limits are applied here (rowCount, rowPx).
const PLAIN = ['plain'];
const SIDES = [true]; // a tick box hands showWhen its checked state
const GOOD = ['good'];
const GAIN = ['gain'];
const STYLES: [string, string, number, string[]?, Extra?][] = [
	['bars', 'Bars', NONE, ['rows', 'rowHeight', 'optimalAt', 'fromSides']],
	['rows', 'Ticks shown (10-1000)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 9999, increment: 10 } }],
	['rowHeight', 'Bar height (px, 1-20)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 99 } }],
	['optimalAt', 'Optimal at', DROPDOWN, undefined, { options: OPTIMAL_AT }],
	['fromSides', 'Grow from the sides (right strafes from the left)', CHECKBOX, ['swapSides', 'leftColor', 'rightColor'],
		{ showWhen: { swapSides: SIDES, leftColor: SIDES, rightColor: SIDES } }],
	['swapSides', 'Swap the sides (right strafes from the right)', CHECKBOX],
	['leftColor', 'Bars from the left edge (Plain)', COLOR_PICKER],
	['rightColor', 'Bars from the right edge (Plain)', COLOR_PICKER],
	['colours', 'Colours', NONE, ['colorBy', 'showMarker', 'markerColor', 'backgroundColor']],
	['colorBy', 'Colour by', DROPDOWN, ['barColor', 'goodColor', 'badColor', 'badPct', 'gainLow', 'gainHigh', 'lowColor', 'midColor', 'highColor'],
		{ options: COLOR_BY, showWhen: { barColor: PLAIN, goodColor: GOOD, badColor: GOOD, badPct: GOOD,
			gainLow: GAIN, gainHigh: GAIN, lowColor: GAIN, midColor: GAIN, highColor: GAIN } }],
	['barColor', 'Bar colour', COLOR_PICKER],
	['goodColor', 'At optimal', COLOR_PICKER],
	['badColor', 'Far from optimal', COLOR_PICKER],
	['badPct', 'Fully "far" at (% away)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 1000 } }],
	['gainLow', 'Middle colour from (gain %, tenths: 865 = 86.5 %)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 1000 } }],
	['gainHigh', 'Top colour above (gain %, tenths: 920 = 92 %)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 1000 } }],
	['lowColor', 'Below the middle (amber)', COLOR_PICKER],
	['midColor', 'Middle (green)', COLOR_PICKER],
	['highColor', 'Top (blue)', COLOR_PICKER],
	['showMarker', 'Line at the optimal', CHECKBOX],
	['markerColor', 'Line colour', COLOR_PICKER],
	['backgroundColor', 'Background colour', COLOR_PICKER]
];

// Shown while the customizer is open, so there is something to drag: [ratio, strafeRight], four strafes
const SAMPLE: [number, boolean][] = [];
for (let i = 0; i < 100; i++) {
	const k = i % 25;
	const r = k < 3 ? 0.4 + 0.2 * k : k > 21 ? 1.3 - 0.1 * (k - 21) : 0.85 + 0.3 * Math.abs(Math.sin(i * 1.7));
	SAMPLE.push([r, Math.floor(i / 25) % 2 === 1]);
}

// ---- Panorama ----

// panorama_reload loads this file again while the old copy's handlers and loop stay alive (JHUD,
// 2026-11-03). Each load takes a new number in Panorama's global object; an old copy does nothing.
const GLOBAL = UiToolkitAPI.GetGlobalObject() as Record<string, any>;
const GEN = (GLOBAL['MovekitStrafeHistGen'] = (GLOBAL['MovekitStrafeHistGen'] || 0) + 1);
const live = () => GLOBAL['MovekitStrafeHistGen'] === GEN;

const REPLAY_NONE = 0;
const MOVETYPE_OBSERVER = 10; // MomentumMovementAPI.MoveType.OBSERVER, as the recorder has it

const settings: Settings = { ...DEFAULTS };
let interval = 0.01;
let panel: GenericPanel | null = null;
let editing = false;
let spectating = false;
let lastKey = '';
let lastTick = -1;
let prevVz = 0; // the vz of the tick before the pending one
let pending: { ratio: number; right: boolean; vz: number } | null = null; // the last tick, drawn when the next comes
// The rows are built once; each new tick moves the top row to the bottom and restyles only that one, so
// a tick costs one panel move, not a redraw. Rows with no bar yet are hidden, so the list (aligned to the
// bottom) starts at the bottom and grows up. Built again when a setting changes them (layoutKey).
let list: GenericPanel | null = null;
let rows: GenericPanel[] = [];
let builtFor = '';

function getPanel(): GenericPanel {
	if (panel && panel.IsValid()) return panel;
	const ctx = $.GetContextPanel();
	const root = ctx.GetParent() ?? ctx;
	// an earlier load's panel is taken over, not replaced: the customizer has placed that one
	const old = root.FindChildTraverse(ID);
	if (old && old.IsValid()) {
		panel = old;
		return panel;
	}
	panel = $.CreatePanel('Panel', root, ID, { style: 'width: 200px;' });
	panel.visible = false;
	return panel;
}

function rowCount(s: Settings): number {
	const n = Math.round(+s.rows);
	return isFinite(n) ? Math.max(10, Math.min(1000, n)) : 100;
}
function rowPx(s: Settings): number {
	const h = Math.round(+s.rowHeight);
	return isFinite(h) ? Math.max(1, Math.min(20, h)) : 2;
}

// What the built rows depend on (each row's width, side and colour are set when it is painted)
function layoutKey(s: Settings): string {
	return JSON.stringify([rowCount(s), rowPx(s), markers(s), !!s.showMarker, s.markerColor]);
}

function build() {
	const p = getPanel();
	p.RemoveAndDeleteChildren();
	const n = rowCount(settings);
	const h = rowPx(settings);
	p.style.height = `${n * h}px`;
	list = $.CreatePanel('Panel', p, '', { style: 'width: 100%; height: fit-children; vertical-align: bottom; flow-children: down;' });
	rows = [];
	for (let i = 0; i < n; i++) {
		const row = $.CreatePanel('Panel', list, '', { style: `width: 0%; height: ${h}px;` });
		row.visible = false;
		rows.push(row);
	}
	if (settings.showMarker) {
		for (const at of markers(settings)) {
			$.CreatePanel('Panel', p, '', {
				style: `width: 2px; height: 100%; margin-left: ${(at * 100).toFixed(1)}%; background-color: ${settings.markerColor};`
			});
		}
	}
	builtFor = layoutKey(settings);
}

function ensureBuilt() {
	const stale = !list || !list.IsValid() || rows.length !== rowCount(settings) || rows.some((r) => !r.IsValid());
	if (stale || builtFor !== layoutKey(settings)) build();
}

// One new tick at the bottom: the top row moves to the bottom and is painted
function addRow(ratio: number, strafeRight: boolean) {
	ensureBuilt();
	const row = rows.shift()!;
	list!.MoveChildAfter(row, rows[rows.length - 1]);
	rows.push(row);
	const st = rowStyle(ratio, strafeRight, settings);
	row.style.width = `${st.width}%`;
	row.style.horizontalAlign = st.side;
	row.style.backgroundColor = st.color;
	row.visible = true;
	getPanel().visible = true;
}

function showSample() {
	build();
	for (const [r, right] of SAMPLE.slice(-rows.length)) addRow(r, right);
}

function hide() {
	if (panel && panel.IsValid()) panel.visible = false;
}

// Whether the HUD customizer has this panel switched on: its own record (components[ID].enabled, what the
// preset saves), else the panel's flag for a customizer that hasn't taken the panel.
function switchedOn(): boolean {
	const c = GLOBAL['HudCustomizerHandler']?.components?.[ID];
	return c ? c.enabled !== false : getPanel().enabled;
}

// Own play in a bhop mode with the panel switched on in the customizer
function watching(): boolean {
	if (!GAMEMODES.includes(GameModeAPI.GetCurrentGameMode())) return false;
	if (spectating || MomentumMovementAPI.GetMoveType() === MOVETYPE_OBSERVER) return false;
	if (MomentumReplayAPI.GetReplayState() !== REPLAY_NONE) return false;
	return switchedOn();
}

// Empty rows from the next tick on (a map load, spectating, the customizer closing)
function clearRows() {
	builtFor = '';
	lastKey = '';
	lastTick = -1;
	prevVz = 0;
	pending = null;
	hide();
}

// A new game tick, the recorder's way: the tick stats or velocity changed, numbered by game time. The tick
// before it is now judged: in the air it adds a row, on the ground none.
function sample() {
	const stats = MomentumMovementAPI.GetLastTickStats();
	const vel = MomentumPlayerAPI.GetVelocity();
	const key = `${stats.speedGain},${stats.idealGain},${stats.yawRatio},${stats.strafeRight},${vel.x},${vel.y},${vel.z}`;
	const floorTick = Math.floor(MomentumMovementAPI.GetCurrentTime() / interval);
	if (floorTick < lastTick - 1) clearRows(); // game time went back (map change, reload)
	if (key === lastKey) return;
	lastKey = key;
	lastTick = Math.max(floorTick, lastTick + 1);
	if (pending) {
		if (!onGround(pending.vz, prevVz, vel.z)) addRow(pending.ratio, pending.right);
		prevVz = pending.vz;
	}
	// strafeRight is 1 (right), -1 (left) or 0 (no key), not a bool (the recorder's 'right' column)
	pending = { ratio: stats.yawRatio, right: stats.strafeRight > 0, vz: vel.z };
}

function loop() {
	if (!live()) return;
	if (!editing) {
		if (watching()) sample();
		else hide();
	}
	$.Schedule(0, loop);
}

function customizerProps() {
	const dynamicStyles: Record<string, any> = {};
	for (const [id, name, type, children, extra] of STYLES) {
		if (type === NONE) {
			dynamicStyles[id] = { name, type, expandable: true, children: (children || []).map((styleID) => ({ styleID })) };
		} else if (id === 'backgroundColor') {
			dynamicStyles[id] = { name, type, styleProperty: 'backgroundColor' };
		} else {
			dynamicStyles[id] = {
				name,
				type,
				...(extra?.options ? { options: extra.options } : {}),
				...(extra?.range ? { settingProps: { ...extra.range } } : {}),
				...(children ? { children: children.map((styleID) => ({ styleID, showWhen: extra?.showWhen?.[styleID] })) } : {}),
				callbackFunc: (_: unknown, value: unknown) => {
					settings[id] = value;
					if (editing) showSample();
				}
			};
		}
	}
	return { name: 'Strafe Speed Histogram', resizeX: true, resizeY: false, gamemode: GAMEMODES, dynamicStyles };
}

// The customizer's number boxes clip 3 digits (JHUD, 2026-11-03): while this component is being edited,
// its boxes' text fields get a width that fits 5 digits, checked every BOX_FIX_S seconds since the list is
// rebuilt with no event.
const BOX_WIDTH = '44px';
const BOX_FIX_S = 0.25;
function widenBoxes(p: GenericPanel) {
	for (let i = 0; i < p.GetChildCount(); i++) {
		const c = p.GetChild(i);
		if (!c) continue;
		if (c.paneltype === 'NumberEntry') {
			for (let j = 0; j < c.GetChildCount(); j++) {
				const t = c.GetChild(j);
				if (t && t.paneltype === 'TextEntry' && t.style.width !== BOX_WIDTH) t.style.width = BOX_WIDTH;
			}
		} else {
			widenBoxes(c);
		}
	}
}
function fixBoxes() {
	if (!live() || !editing) return;
	const h = GLOBAL['HudCustomizerHandler'];
	const lst = h?.panels?.activeComponentSettingsList as GenericPanel | undefined;
	if (h?.activeComponent?.id === ID && lst && lst.IsValid()) widenBoxes(lst);
	$.Schedule(BOX_FIX_S, fixBoxes);
}

// The customizer throws when a setting has no value in the layout it loaded at the map start
// (customizer.ts Component constructor), and a throw here stops the whole script. After an update and a
// panorama_reload, the loaded layout is the old hud_default.kv3, without the new settings (seen 2026-11-03:
// swapSides). So settings the layout has no value for are left out of the customizer until the next map load,
// where they keep their defaults. values: the loaded layout's dynamicStyles for this panel, or null (unknown:
// nothing left out).
function fitLayout(props: Record<string, any>, values: Record<string, unknown> | null): Record<string, any> {
	if (!values) return props;
	const keep = (id: string) => props.dynamicStyles[id].type === NONE || values[id] !== undefined;
	const dynamicStyles: Record<string, any> = {};
	for (const [id, style] of Object.entries(props.dynamicStyles as Record<string, any>)) {
		if (!keep(id)) continue;
		dynamicStyles[id] = style.children ? { ...style, children: style.children.filter((c: any) => props.dynamicStyles[c.styleID] && keep(c.styleID)) } : style;
	}
	return { ...props, dynamicStyles };
}

function register() {
	const h = GLOBAL['HudCustomizerHandler'];
	if (!h) return;
	const layout = h.constructor?.presetLayout ?? h.presetLayout;
	const values = layout ? (layout[ID]?.dynamicStyles ?? {}) : null;
	try {
		h.loadComponent(getPanel(), fitLayout(customizerProps(), values));
	} catch (e) {
		$.Msg(`${ID}: the HUD customizer refused the panel (${e}); it shows with its defaults`);
	}
}

function onLevelInit() {
	interval = MomentumMovementAPI.GetTickInterval() || 0.01;
	clearRows();
}

$.RegisterForUnhandledEvent('HudCustomizer_Ready', () => {
	if (!live()) return;
	editing = false;
	hide();
	register();
});
$.RegisterForUnhandledEvent('HudCustomizer_Opened', () => {
	if (!live() || !GAMEMODES.includes(GameModeAPI.GetCurrentGameMode())) return;
	editing = true;
	showSample();
	fixBoxes();
});
$.RegisterForUnhandledEvent('HudCustomizer_Closed', () => {
	if (!live()) return;
	editing = false;
	clearRows();
});
$.RegisterForUnhandledEvent('LevelInitPostEntity', () => {
	if (live()) onLevelInit();
});
$.RegisterForUnhandledEvent('MomentumSpectateStart', () => {
	if (!live()) return;
	spectating = true;
	clearRows();
});
$.RegisterForUnhandledEvent('MomentumSpectateStop', () => {
	if (!live()) return;
	spectating = false;
	clearRows();
});

onLevelInit();
$.Schedule(0, loop); // before registering, so nothing the customizer does can keep the bars from drawing
// HudCustomizer_Ready comes only at a map load; after panorama_reload in a map, register now, so the
// customizer hands this copy the saved settings
if (GLOBAL['HudCustomizerHandler']?.customizerReady) register();
