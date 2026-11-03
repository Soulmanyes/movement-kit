// Strafe Speed Histogram, part of Soulmanyes's Movement Kit (strafe-histogram/ in the repo). Loaded next to
// timer.ts through the kit's timer.xml patch (movekit/panorama.py).
//
// While bhopping: a histogram of how fast you turn against the optimal (the game's yawRatio, 1 = optimal)
// over the middle of your strafes in the last few seconds of strafing, plus the share in the optimal band.
// The bars stay as they are while you stand still; new strafing pushes the oldest ticks out.
//
// Which ticks count is Strafe Review's strafe-middle rule (viewer/static/checks.js strafesOf + interior,
// skip 2; data.js parse for ground, the 5-tick yaw average and the ideal key), worked out as the ticks come
// in. A tick is counted once nothing after it can change the answer, about 5 ticks later. So the in-band %
// is the viewer's "In optimal band" for the same strafing (check_strafe_histogram.js compares tick by tick).
//
// Settings live in Momentum's HUD customizer, as JHUD's do: install.py hands the kit the panel's
// hud_default.kv3 entry (ENTRY there), whose dynamicStyles must list every setting in STYLES below with the
// value in DEFAULTS (check_strafe_histogram.js checks both).
//
// No imports, like JHUD. The plain functions (above "Panorama") are run in node by check_strafe_histogram.js.
// The Panorama part copies JHUD's fixes (load number, panel take-over, register after a reload, number box
// width): Panorama scripts can't import, and a shared script would tie two modules that install alone.

const ID = 'MovekitStrafeHist';
const GAMEMODES = [2, 3]; // Gamemode.BHOP, Gamemode.BHOP_HL1 (common/web/enums/gamemode.enum)
// CustomizerPropertyType in common/hud-customizer.ts
const NONE = 0;
const NUMBER_ENTRY = 1;
const CHECKBOX = 2;
const DROPDOWN = 4;
const COLOR_PICKER = 5;
const FONT_PICKER = 7;

// ---- the strafe-middle rule (Strafe Review's viewer, see the top) ----

// Buttons (data.js BIT)
const MOVELEFT = 1 << 9;
const MOVERIGHT = 1 << 10;
const TURN_BTNS = (1 << 7) | (1 << 8); // +left, +right
const GROUND_VZ = 1; // data.js: a steady vz under this is ground
const COLLISION = 10; // checks.js: a tick losing more than this (u/s) is a wall or ramp hit
const MIN_SPEED = 100; // checks.js strafing(): judged at 100+ u/s
const KEY_YAW = 0.3; // data.js ideal_key: the 5-tick yaw average must turn more than this (degrees a tick)
const SKIP = 2; // stats.js: ticks skipped at each end of a strafe
const BAND_LO = 0.85; // stats.js BAND_LO / BAND_HI: the optimal band
const BAND_HI = 1.15;
const KEEP_ROWS = 2000; // rows kept at most while no jump finishes (a long fall)

// One tick: tick number, game yawRatio, speedGain, physical buttons, velocity, view yaw
type Row = { tick: number; ratio: number; gain: number; buttons: number; vx: number; vy: number; vz: number; yaw: number };

function wrap180(a: number): number {
	return ((((a + 180) % 360) + 360) % 360) - 180;
}

// The middle-of-strafe ticks of rows[0..n), as the viewer finds them in a whole recording, limited to what is
// already certain: ground needs the next row, the yaw average two rows ahead, a strafe's end two more.
// Returns the row indexes, and `keep`, the first row a later call still needs (rows before it can go).
function middles(rows: Row[]): { idx: number[]; keep: number } {
	const n = rows.length;
	const ground: boolean[] = [];
	for (let i = 0; i < n; i++) {
		const vz = rows[i].vz;
		const prev = i > 0 ? rows[i - 1].vz : 0;
		const next = i < n - 1 ? rows[i + 1].vz : 0;
		if (vz === 0) ground.push(!(prev > 0 && next < 0));
		else ground.push(Math.abs(vz) < GROUND_VZ && ((i > 0 && prev === vz) || (i < n - 1 && next === vz)));
	}
	const gap = (i: number) => (i > 0 ? rows[i].tick - rows[i - 1].tick - 1 : 0);
	const yawd = rows.map((r, i) => (i > 0 && gap(i) === 0 ? wrap180(r.yaw - rows[i - 1].yaw) : NaN));
	const keyEnd = n - 2; // ideal keys are certain for rows < keyEnd (the 5-tick average reaches 2 ahead)
	const key: number[] = [];
	for (let i = 0; i < keyEnd; i++) {
		let sum = 0;
		let cnt = 0;
		for (let j = i - 2; j <= i + 2; j++) {
			if (j < 0 || j >= n || Math.abs(rows[j].tick - rows[i].tick) > 2 || !isFinite(yawd[j])) continue;
			sum += yawd[j];
			cnt++;
		}
		const yaws = cnt ? sum / cnt : NaN;
		key.push(!ground[i] && Math.abs(yaws) > KEY_YAW ? Math.sign(yaws) : 0);
	}
	const strafing = (i: number) => {
		const r = rows[i];
		return !ground[i] && Math.hypot(r.vx, r.vy) > MIN_SPEED && !(r.gain < -COLLISION);
	};
	const takeoff = (i: number) => i > 0 && rows[i].vz > 100 && rows[i - 1].vz <= 0.5;

	const idx: number[] = [];
	let keep = -1; // the first jump not yet certain, less three rows: its takeoff row's yaw average reaches
	// two back, and the yaw change of the oldest of those needs the row before it
	for (let i = 1; i < n; i++) {
		if (!takeoff(i)) continue;
		const s = i;
		// the jump's air time: up to the first ground row or the next takeoff. The newest row's ground isn't
		// certain yet, so a jump that reaches it is still open.
		let e = s + 1;
		while (e < n - 1 && !ground[e] && !takeoff(e)) e++;
		const closed = e < n - 1 || (e === n - 1 && takeoff(e));
		const end = Math.min(e, keyEnd); // rows with certain keys inside the jump
		// strafes (checks.js strafesOf): a run of the same ideal key; rows with no key don't end one
		let cur: { dir: number; i0: number; i1: number } | null = null;
		const strafes: { dir: number; i0: number; i1: number }[] = [];
		for (let k = s; k < end; k++) {
			if (!key[k]) continue;
			if (!cur || cur.dir !== key[k]) {
				cur = { dir: key[k], i0: k, i1: k };
				strafes.push(cur);
			}
			cur.i1 = k;
		}
		for (const st of strafes) {
			// the last strafe of an open jump can still grow, but a tick SKIP rows before its known end stays inside
			for (let k = st.i0 + SKIP; k <= st.i1 - SKIP; k++) {
				if (strafing(k) && !(rows[k].buttons & TURN_BTNS) && gap(k) === 0 && isFinite(rows[k].ratio)) idx.push(k);
			}
		}
		if (keep < 0 && !(closed && e <= keyEnd)) keep = Math.max(0, s - 3);
		i = e - 1;
	}
	// every jump certain: only the last rows, for a takeoff on the next row
	if (keep < 0) keep = Math.max(0, n - 3);
	return { idx, keep };
}

// Rows in, counted ticks out, once each: push() returns the rows that just became certain.
class Middles {
	rows: Row[] = [];
	done = new Set<number>(); // tick numbers already counted, of rows still kept
	push(row: Row): Row[] {
		this.rows.push(row);
		const { idx, keep } = middles(this.rows);
		const out: Row[] = [];
		for (const i of idx) {
			const t = this.rows[i].tick;
			if (this.done.has(t)) continue;
			this.done.add(t);
			out.push(this.rows[i]);
		}
		const cut = Math.max(keep, this.rows.length - KEEP_ROWS);
		if (cut > 0) {
			const first = this.rows[cut].tick;
			this.rows = this.rows.slice(cut);
			for (const t of this.done) if (t < first) this.done.delete(t);
		}
		return out;
	}
	clear() {
		this.rows = [];
		this.done.clear();
	}
}

// ---- bars ----

type Settings = Record<string, any>;

// The bars: lowPct to highPct in steps of stepPct (all % of the optimal), and one bar each side for the rest
function edges(s: Settings): { lo: number; hi: number; step: number; bars: number } {
	const step = Math.max(1, Math.round(+s.stepPct) || 10) / 100;
	const lo = Math.max(0, Math.round(+s.lowPct) || 0) / 100;
	let hi = Math.round(+s.highPct) / 100;
	if (!(hi > lo)) hi = lo + step;
	const inner = Math.max(1, Math.min(60, Math.round((hi - lo) / step)));
	return { lo, hi: lo + inner * step, step, bars: inner + 2 };
}

// Which bar a ratio goes in: 0 under lo, bars - 1 at hi or over
function barOf(r: number, e: { lo: number; hi: number; step: number; bars: number }): number {
	if (r < e.lo) return 0;
	if (r >= e.hi - 1e-9) return e.bars - 1;
	return 1 + Math.min(e.bars - 3, Math.floor((r - e.lo) / e.step + 1e-9));
}

// The last `size` counted ticks (the window), with a count per bar and in the band
class Window {
	ratios: number[] = [];
	size: number;
	constructor(size: number) {
		this.size = Math.max(1, Math.floor(size));
	}
	add(r: number) {
		this.ratios.push(r);
		if (this.ratios.length > this.size) this.ratios.splice(0, this.ratios.length - this.size);
	}
	resize(size: number) {
		this.size = Math.max(1, Math.floor(size));
		if (this.ratios.length > this.size) this.ratios.splice(0, this.ratios.length - this.size);
	}
	counts(e: { lo: number; hi: number; step: number; bars: number }): number[] {
		const c = new Array(e.bars).fill(0);
		for (const r of this.ratios) c[barOf(r, e)]++;
		return c;
	}
	// share in the optimal band (stats.js: BAND_LO <= r <= BAND_HI), in %, or NaN with nothing counted
	band(): number {
		if (!this.ratios.length) return NaN;
		return (100 * this.ratios.filter((r) => r >= BAND_LO && r <= BAND_HI).length) / this.ratios.length;
	}
}

// Ticks a window of `seconds` holds at this tick interval
function windowTicks(seconds: number, interval: number): number {
	return Math.max(1, Math.round(Math.max(0.1, +seconds || 0) / (interval > 0 ? interval : 0.01)));
}

// "rgba(r, g, b, a)" or "#rrggbb" as [r, g, b, a], or null (as JHUD's)
function parseColor(s: string): number[] | null {
	const m = /^\s*rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)\s*$/i.exec(s || '');
	if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
	const h = /^\s*#([0-9a-f]{6})\s*$/i.exec(s || '');
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

// Each bar's colour: one colour (colorBy 'plain'), or by how far its middle is from 1 (colorBy 'good'):
// goodColor at 1, badColor at badPct % away or more, either side alike; the end bars count from their inner edge.
function barColors(s: Settings): string[] {
	const e = edges(s);
	const out: string[] = [];
	for (let b = 0; b < e.bars; b++) {
		if (s.colorBy !== 'good') {
			out.push(s.barColor);
			continue;
		}
		const mid = b === 0 ? e.lo : b === e.bars - 1 ? e.hi : e.lo + (b - 0.5) * e.step;
		const far = Math.max(1, +s.badPct || 50) / 100;
		out.push(mixColor(s.goodColor, s.badColor, Math.abs(mid - 1) / far));
	}
	return out;
}

// Bar heights in px: the tallest bar is barHeight, the rest by their share of it; nothing counted: all 0
function heights(counts: number[], s: Settings): number[] {
	const top = Math.max(0, ...counts);
	const h = Math.max(4, +s.barHeight || 60);
	return counts.map((c) => (top ? Math.round((h * c) / top) : 0));
}

// The line under the bars, or '' with it switched off or nothing counted
function bandText(pct: number, s: Settings): string {
	return s.showBand && isFinite(pct) ? `in band ${pct.toFixed(0)} %` : '';
}

const DEFAULTS: Settings = {
	font: '$fontPrimary',
	fontSize: 16,
	fontColor: '$fontColor',
	backgroundColor: 'rgba(0, 0, 0, 0)',
	windowS: 3,
	lowPct: 40,
	highPct: 160,
	stepPct: 10,
	barHeight: 60,
	colorBy: 'plain',
	barColor: 'rgba(255, 255, 255, 0.85)',
	goodColor: 'rgba(123, 216, 143, 1)',
	badColor: 'rgba(255, 92, 92, 1)',
	badPct: 50,
	showBand: true
};

const COLOR_BY = [
	{ label: 'Plain (one colour)', value: 'plain' },
	{ label: 'How good (by distance from optimal)', value: 'good' }
];
type Extra = {
	options?: { label: string; value: string }[];
	showWhen?: Record<string, string[]>;
	range?: { min: number; max: number };
};
const PLAIN = ['plain'];
const GOOD = ['good'];
const STYLES: [string, string, number, string[]?, Extra?][] = [
	['bars', 'Bars', NONE, ['windowS', 'lowPct', 'highPct', 'stepPct', 'barHeight']],
	['windowS', 'Last seconds of strafing counted', NUMBER_ENTRY, undefined, { range: { min: 1, max: 60 } }],
	['lowPct', 'From (% of optimal)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 1000 } }],
	['highPct', 'To (% of optimal)', NUMBER_ENTRY, undefined, { range: { min: 1, max: 1000 } }],
	['stepPct', 'Bar width (% of optimal)', NUMBER_ENTRY, undefined, { range: { min: 1, max: 100 } }],
	['barHeight', 'Tallest bar (px)', NUMBER_ENTRY, undefined, { range: { min: 4, max: 500 } }],
	['colours', 'Colours', NONE, ['colorBy', 'backgroundColor']],
	['colorBy', 'Colour by', DROPDOWN, ['barColor', 'goodColor', 'badColor', 'badPct'],
		{ options: COLOR_BY, showWhen: { barColor: PLAIN, goodColor: GOOD, badColor: GOOD, badPct: GOOD } }],
	['barColor', 'Bar colour', COLOR_PICKER],
	['goodColor', 'At optimal', COLOR_PICKER],
	['badColor', 'Far from optimal', COLOR_PICKER],
	['badPct', 'Fully "far" at (% away)', NUMBER_ENTRY, undefined, { range: { min: 1, max: 1000 } }],
	['backgroundColor', 'Background colour', COLOR_PICKER],
	['bandLine', 'In-band line', NONE, ['showBand', 'font', 'fontSize', 'fontColor']],
	['showBand', 'Show the share in the optimal band (85-115 %)', CHECKBOX],
	['font', 'Font', FONT_PICKER],
	['fontSize', 'Font size', NUMBER_ENTRY, undefined, { range: { min: 6, max: 72 } }],
	['fontColor', 'Font colour', COLOR_PICKER]
];

// Shown while the customizer is open, so there is something to drag: the store's shape (PLAN.md Phase 6)
const SAMPLE = [0.2, 0.55, 0.62, 0.7, 0.74, 0.78, 0.8, 0.82, 0.84, 0.86, 0.87, 0.88, 0.9, 0.9, 0.91, 0.92, 0.93, 0.94,
	0.95, 0.96, 0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.03, 1.05, 1.07, 1.1, 1.12, 1.18, 1.25, 1.4, 1.9];

// ---- Panorama ----

// panorama_reload loads this file again while the old copy's handlers and loop stay alive (JHUD,
// 2026-11-03). Each load takes a new number in Panorama's global object; an old copy does nothing.
const GLOBAL = UiToolkitAPI.GetGlobalObject() as Record<string, any>;
const GEN = (GLOBAL['MovekitStrafeHistGen'] = (GLOBAL['MovekitStrafeHistGen'] || 0) + 1);
const live = () => GLOBAL['MovekitStrafeHistGen'] === GEN;

const REPLAY_NONE = 0;
const MOVETYPE_OBSERVER = 10;
const REDRAW_MS = 50; // at most 20 redraws a second

const settings: Settings = { ...DEFAULTS };
const mids = new Middles();
let win = new Window(300);
let interval = 0.01;
let panel: GenericPanel | null = null;
let editing = false;
let spectating = false;
let lastKey = '';
let lastTick = -1;
let dirty = false;
let drawnAt = 0;

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
	panel = $.CreatePanel('Panel', root, ID, { style: 'flow-children: down; width: 300px;' });
	panel.visible = false;
	return panel;
}

function draw(counts: number[], band: number) {
	const p = getPanel();
	p.RemoveAndDeleteChildren();
	const colors = barColors(settings);
	const hs = heights(counts, settings);
	const h = Math.max(4, +settings.barHeight || 60);
	const bars = $.CreatePanel('Panel', p, '', { style: `width: 100%; height: ${h}px; flow-children: right;` });
	hs.forEach((bh, i) =>
		$.CreatePanel('Panel', bars, '', {
			style: `width: fill-parent-flow(1); height: ${bh}px; vertical-align: bottom; margin-left: 1px; margin-right: 1px;
				background-color: ${colors[i]};`
		})
	);
	const text = bandText(band, settings);
	if (text) {
		const font = String(settings.font || '').replace(/"/g, '');
		$.CreatePanel('Label', p, '', {
			text,
			style: `horizontal-align: center; margin-top: 4px; ${font ? `font-family: "${font}";` : ''}
				font-size: ${Math.max(6, +settings.fontSize || 16)}px; font-weight: bold; color: ${settings.fontColor};
				text-shadow: 0px 1px 4px 2px rgba(0, 0, 0, 0.9);`
		});
	}
}

function redraw() {
	const e = edges(settings);
	if (editing) {
		const sample = new Window(SAMPLE.length);
		SAMPLE.forEach((r) => sample.add(r));
		draw(sample.counts(e), sample.band());
		getPanel().visible = true;
		return;
	}
	draw(win.counts(e), win.band());
	getPanel().visible = win.ratios.length > 0;
}

function hide() {
	if (panel && panel.IsValid()) panel.visible = false;
}

// Own play in a bhop mode with the panel switched on in the customizer
function watching(): boolean {
	if (!GAMEMODES.includes(GameModeAPI.GetCurrentGameMode())) return false;
	if (spectating || MomentumMovementAPI.GetMoveType() === MOVETYPE_OBSERVER) return false;
	if (MomentumReplayAPI.GetReplayState() !== REPLAY_NONE) return false;
	return getPanel().enabled;
}

function reset() {
	mids.clear();
	win = new Window(windowTicks(settings.windowS, interval));
	lastKey = '';
	lastTick = -1;
	dirty = true;
}

// A new game tick, the recorder's way: the tick stats or velocity changed, numbered by game time
function sample() {
	const stats = MomentumMovementAPI.GetLastTickStats();
	const vel = MomentumPlayerAPI.GetVelocity();
	const key = `${stats.speedGain},${stats.idealGain},${stats.yawRatio},${stats.strafeRight},${vel.x},${vel.y},${vel.z}`;
	const floorTick = Math.floor(MomentumMovementAPI.GetCurrentTime() / interval);
	if (floorTick < lastTick - 1) reset(); // game time went back (map change, reload)
	if (key === lastKey) return;
	lastKey = key;
	const tick = Math.max(floorTick, lastTick + 1);
	lastTick = tick;
	const row: Row = {
		tick,
		ratio: stats.yawRatio,
		gain: stats.speedGain,
		buttons: MomentumInputAPI.GetButtons().physicalButtons,
		vx: vel.x,
		vy: vel.y,
		vz: vel.z,
		yaw: MomentumPlayerAPI.GetAngles().y
	};
	for (const r of mids.push(row)) {
		win.add(r.ratio);
		dirty = true;
	}
}

function loop() {
	if (!live()) return;
	if (!editing) {
		if (watching()) {
			sample();
			if (dirty && Date.now() - drawnAt >= REDRAW_MS) {
				dirty = false;
				drawnAt = Date.now();
				redraw();
			}
		} else {
			hide();
		}
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
					if (id === 'windowS') win.resize(windowTicks(settings.windowS, interval));
					if (editing) redraw();
					else dirty = true;
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
	const list = h?.panels?.activeComponentSettingsList as GenericPanel | undefined;
	if (h?.activeComponent?.id === ID && list && list.IsValid()) widenBoxes(list);
	$.Schedule(BOX_FIX_S, fixBoxes);
}

function register() {
	const h = GLOBAL['HudCustomizerHandler'];
	if (h) h.loadComponent(getPanel(), customizerProps());
}

function onLevelInit() {
	interval = MomentumMovementAPI.GetTickInterval() || 0.01;
	reset();
	hide();
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
	redraw();
	fixBoxes();
});
$.RegisterForUnhandledEvent('HudCustomizer_Closed', () => {
	if (!live()) return;
	editing = false;
	dirty = true;
	hide();
});
$.RegisterForUnhandledEvent('LevelInitPostEntity', () => {
	if (live()) onLevelInit();
});
$.RegisterForUnhandledEvent('MomentumSpectateStart', () => {
	if (!live()) return;
	spectating = true;
	reset();
});
$.RegisterForUnhandledEvent('MomentumSpectateStop', () => {
	if (!live()) return;
	spectating = false;
	reset();
});

onLevelInit();
// HudCustomizer_Ready comes only at a map load; after panorama_reload in a map, register now, so the
// customizer hands this copy the saved settings
if (GLOBAL['HudCustomizerHandler']?.customizerReady) register();
$.Schedule(0, loop);
