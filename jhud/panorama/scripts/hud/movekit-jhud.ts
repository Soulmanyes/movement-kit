// JHUD, part of Soulmanyes's Movement Kit (jhud/ in the repo). Loaded next to timer.ts through the kit's
// timer.xml patch (movekit/panorama.py).
//
// After every bhop jump: the jump's number, speed and speed change, gain % and sync on one line in the
// middle of the screen, in the font colour, coloured by gain, or by speed pace (colorBy); held for a moment,
// then faded out.
// The numbers are the game's own (MomentumMovementAPI.GetLastJumpStats(), as its Jump Stats panel shows them).
//
// Settings live in Momentum's HUD customizer. It loads a component only when hud_default.kv3 has an
// entry for its panel id; install.py hands the kit that entry (ENTRY there), whose dynamicStyles must
// list every setting in STYLES below with the value in DEFAULTS (check_jhud.js checks both).
//
// A line shows at every takeoff, labelled with the takeoff's number (jumpCount), like shavit-jhud. The
// event for takeoff N carries takeoff N's speed but the air time of jump N-1 (Phase 5.1), so gain, sync
// and the rest are the air time just before it. Takeoff 1 has no air time yet: its line is the number and
// speed only, in the font colour. jumpCount resets to 0 when the timer primes in the start zone.
//
// No imports, like the Strafe Review recorder. The plain functions (above "Panorama") are run in node
// by check_jhud.js.

const ID = 'MovekitJhud';
const GAMEMODES = [2, 3]; // Gamemode.BHOP, Gamemode.BHOP_HL1 (common/web/enums/gamemode.enum)
// CustomizerPropertyType in common/hud-customizer.ts
const NONE = 0;
const NUMBER_ENTRY = 1;
const CHECKBOX = 2;
const DROPDOWN = 4;
const COLOR_PICKER = 5;
const FONT_PICKER = 7;

type Stats = {
	jumpCount: number;
	takeoffSpeed: number;
	jumpSpeedDelta: number;
	speedGain: number;
	strafeSync: number;
	strafeCount: number;
	yawRatio: number;
	efficiency: number;
	heightDelta: number;
	distance: number;
	timeDelta: number;
};
type Part = { text: string; color: string | null }; // null: the font colour
type Settings = Record<string, any>;

// The customizer's values when nothing is saved yet. "$name" is one of the customizer's shared values
// (CustomizerSettings in hud_default.kv3); the customizer swaps in the real value before calling back.
const DEFAULTS: Settings = {
	font: '$fontPrimary',
	fontSize: 22,
	fontColor: '$fontColor',
	backgroundColor: 'rgba(0, 0, 0, 0)',
	showNumber: true,
	showSpeed: true,
	showDelta: true,
	showGain: true,
	showSync: true,
	showStrafes: false,
	showYawRatio: false,
	showEfficiency: false,
	showHeight: false,
	showDistance: false,
	showTime: false,
	gainRed: 60,
	gainGreen: 95,
	redColor: 'rgba(255, 92, 92, 1)',
	greenColor: 'rgba(123, 216, 143, 1)',
	colorBy: 'off',
	paceCut: '6',
	tier1Speed: 620,
	tier1Color: 'rgba(123, 216, 143, 1)',
	tier2Speed: 625,
	tier2Color: 'rgba(92, 160, 255, 1)',
	tier3Speed: 630,
	tier3Color: 'rgba(255, 255, 255, 1)',
	belowColor: 'rgba(255, 92, 92, 1)',
	gainAll: true,
	firstJump: 1,
	everyJump: 1,
	holdMs: 2000,
	fadeMs: 300
};

// How a line is coloured (colorBy): 'off' is the font colour. A new way is one more option here and one
// more case in lineColor().
const COLOR_BY = [
	{ label: 'Off (font colour)', value: 'off' },
	{ label: 'Gain %', value: 'gain' },
	{ label: 'Speed pace, then gain %', value: 'pace' }
];
const PACE_CUTS = [
	{ label: 'Jump 6', value: '6' },
	{ label: 'Jump 12', value: '12' }
];
// Speed pace: takeoff k's speed as a share of the cutoff jump's speed, PACE[cut][k - 2] for k = 2..cut. The
// median of the owner's saved runs that reached the cutoff (2026-11-03, bhop_glacial and bhop_ambience;
// 46 runs for 6, 14 for 12). Projected from jump 4 on, the cutoff speed is typically within 1.5 u/s at
// cutoff 6; jump 2 is only a rough guess (7 u/s). Jump 1 (prespeed or a zone reset) isn't judged.
const PACE: Record<string, number[]> = {
	'6': [0.601, 0.722, 0.827, 0.918, 1],
	'12': [0.432, 0.521, 0.596, 0.662, 0.72, 0.775, 0.824, 0.871, 0.915, 0.958, 1]
};

// The customizer's rows: [id, name, type, children, extra]. Groups (NONE) only fold their children; other
// rows show a child only while their value is one of extra.showWhen[child]. extra.options: a dropdown's choices.
// extra.range: a number box's min and max (the game's own boxes set one too). The min is 0: the NumberEntry
// clamps on every keystroke, so a higher min snaps a half-typed value back (owner, 2026-11-03, the histogram's
// rows box). The real limits are applied where the value is used (font size 6+, from jump 1+).
type Extra = {
	options?: { label: string; value: string }[];
	showWhen?: Record<string, string[]>;
	range?: { min: number; max: number };
};
const SPEED_RANGE = { range: { min: 0, max: 10000 } };
const GAIN_OR_PACE = ['gain', 'pace'];
const PACE_ONLY = ['pace'];
const STYLES: [string, string, number, string[]?, Extra?][] = [
	['fontStyling', 'Font', NONE, ['font', 'fontSize', 'fontColor', 'backgroundColor']],
	['font', 'Font', FONT_PICKER],
	['fontSize', 'Font size', NUMBER_ENTRY, undefined, { range: { min: 0, max: 99 } }],
	['fontColor', 'Font colour', COLOR_PICKER],
	['backgroundColor', 'Background colour', COLOR_PICKER],
	['fields', 'Fields', NONE, ['showNumber', 'showSpeed', 'showDelta', 'showGain', 'showSync', 'showStrafes',
		'showYawRatio', 'showEfficiency', 'showHeight', 'showDistance', 'showTime']],
	['showNumber', 'Jump number', CHECKBOX],
	['showSpeed', 'Speed', CHECKBOX],
	['showDelta', 'Speed change', CHECKBOX],
	['showGain', 'Gain %', CHECKBOX],
	['showSync', 'Sync %', CHECKBOX],
	['showStrafes', 'Strafes', CHECKBOX],
	['showYawRatio', 'Yaw ratio', CHECKBOX],
	['showEfficiency', 'Efficiency %', CHECKBOX],
	['showHeight', 'Height change', CHECKBOX],
	['showDistance', 'Distance', CHECKBOX],
	['showTime', 'Time since the last jump', CHECKBOX],
	['colours', 'Colours', NONE, ['colorBy']],
	['colorBy', 'Colour by', DROPDOWN, ['gainAll', 'paceCut', 'tier1Speed', 'tier1Color', 'tier2Speed', 'tier2Color',
		'tier3Speed', 'tier3Color', 'belowColor', 'gainRed', 'gainGreen', 'redColor', 'greenColor'],
		{ options: COLOR_BY, showWhen: {
			gainAll: GAIN_OR_PACE, paceCut: PACE_ONLY, tier1Speed: PACE_ONLY, tier1Color: PACE_ONLY, tier2Speed: PACE_ONLY,
			tier2Color: PACE_ONLY, tier3Speed: PACE_ONLY, tier3Color: PACE_ONLY, belowColor: PACE_ONLY,
			gainRed: GAIN_OR_PACE, gainGreen: GAIN_OR_PACE, redColor: GAIN_OR_PACE, greenColor: GAIN_OR_PACE } }],
	['gainAll', 'Colour the whole line', CHECKBOX],
	['paceCut', 'Speed pace up to', DROPDOWN, undefined, { options: PACE_CUTS }],
	['tier1Speed', 'On pace for this speed at the cutoff', NUMBER_ENTRY, undefined, SPEED_RANGE],
	['tier1Color', '... shown in', COLOR_PICKER],
	['tier2Speed', 'On pace for this speed', NUMBER_ENTRY, undefined, SPEED_RANGE],
	['tier2Color', '... shown in', COLOR_PICKER],
	['tier3Speed', 'On pace for this speed', NUMBER_ENTRY, undefined, SPEED_RANGE],
	['tier3Color', '... shown in', COLOR_PICKER],
	['belowColor', 'Below every pace speed', COLOR_PICKER],
	['gainRed', 'Gain % shown fully red at or below', NUMBER_ENTRY, undefined, { range: { min: 0, max: 200 } }],
	['gainGreen', 'Gain % shown fully green at or above', NUMBER_ENTRY, undefined, { range: { min: 0, max: 200 } }],
	['redColor', 'Red (bad gain)', COLOR_PICKER],
	['greenColor', 'Green (good gain)', COLOR_PICKER],
	['jumps', 'Which jumps', NONE, ['firstJump', 'everyJump']],
	['firstJump', 'From jump', NUMBER_ENTRY, undefined, { range: { min: 0, max: 999 } }],
	['everyJump', 'Every Nth jump (0: only the first)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 999 } }],
	['timing', 'Timing', NONE, ['holdMs', 'fadeMs']],
	['holdMs', 'Shown for (ms)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 10000 } }],
	['fadeMs', 'Fade out (ms)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 5000 } }]
];

// Shown while the customizer is open, so there is something to drag
const SAMPLE: Stats = {
	jumpCount: 7, takeoffSpeed: 642, jumpSpeedDelta: 48, speedGain: 0.874, strafeSync: 0.93, strafeCount: 2,
	yawRatio: 0.86, efficiency: 0.71, heightDelta: 0, distance: 470.2, timeDelta: 0.75
};

// "rgba(r, g, b, a)" or "#rrggbb" as [r, g, b, a], or null
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

// Gain % on a scale: red at or below gainRed, green at or above gainGreen, mixed between
function gainColor(pct: number, s: Settings): string {
	const lo = +s.gainRed;
	const hi = +s.gainGreen;
	const t = hi > lo ? (pct - lo) / (hi - lo) : pct >= hi ? 1 : 0;
	return mixColor(s.redColor, s.greenColor, t);
}

// The takeoff number a jump event is labelled with (1 = the first takeoff), or 0 when it has none
function jumpOf(st: Stats): number {
	return Math.max(0, Math.floor(st.jumpCount));
}

// Whether jump n shows: from firstJump on, every everyJump-th (0: only firstJump), like the game's Jump Stats
function shows(n: number, s: Settings): boolean {
	const first = Math.max(1, Math.floor(+s.firstJump) || 1);
	const every = Math.floor(+s.everyJump) || 0;
	if (n < first) return false;
	return every <= 0 ? n === first : (n - first) % every === 0;
}

const signed = (v: number, digits: number) => (v >= 0 ? '+' : '') + v.toFixed(digits);

// The colour of jump n's line by speed pace: the speed this takeoff is on pace for at the cutoff
// (speed / PACE share) against the tiers; the highest tier reached wins, none reached is belowColor.
// null when n isn't judged by pace (jump 1, past the cutoff).
function paceColor(speed: number, n: number, s: Settings): string | null {
	const curve = PACE[String(s.paceCut)] || PACE['6'];
	if (n < 2 || n > curve.length + 1) return null;
	const onPace = speed / curve[n - 2];
	const tiers = [1, 2, 3]
		.map((i) => ({ speed: +s[`tier${i}Speed`], color: s[`tier${i}Color`] }))
		.filter((t) => isFinite(t.speed))
		.sort((a, b) => b.speed - a.speed);
	const hit = tiers.find((t) => onPace >= t.speed);
	return hit ? hit.color : s.belowColor;
}

// The colour a jump's line is drawn in (null: the font colour), by colorBy, and the field it belongs to
// (what "only" colours when gainAll is off)
function lineColor(st: Stats, n: number, s: Settings): { color: string | null; field: 'speed' | 'gain' } {
	const gain = { color: gainColor(st.speedGain * 100, s), field: 'gain' as const };
	if (s.colorBy === 'gain') return gain;
	if (s.colorBy === 'pace') {
		const pace = paceColor(st.takeoffSpeed, n, s);
		return pace ? { color: pace, field: 'speed' } : gain;
	}
	return { color: null, field: 'gain' };
}

// The rows to draw for a jump: one line with every field switched on, in this order, in lineColor(): the
// whole line (gainAll) or only the gain %. Takeoff 1 (no air time yet): number and speed only, in
// the font colour. No fields: no rows. Kept as rows, so a layout with more lines can come back without
// changing draw().
function rows(st: Stats, n: number, s: Settings): Part[][] {
	if (n === 1) {
		const line: Part[] = [];
		if (s.showNumber) line.push({ text: '1:', color: null });
		if (s.showSpeed) line.push({ text: st.takeoffSpeed.toFixed(0), color: null });
		return line.length ? [line] : [];
	}
	const g = st.speedGain * 100;
	const lc = lineColor(st, n, s);
	const c = s.gainAll ? lc.color : null;
	const gc = s.gainAll || lc.field === 'gain' ? lc.color : null;
	const sc = s.gainAll || lc.field === 'speed' ? lc.color : null;
	const line: Part[] = [];
	if (s.showNumber) line.push({ text: `${n}:`, color: c });
	if (s.showSpeed) line.push({ text: st.takeoffSpeed.toFixed(0), color: sc });
	if (s.showDelta) line.push({ text: `(${signed(Math.round(st.jumpSpeedDelta), 0)})`, color: c });
	if (s.showGain) line.push({ text: `${g.toFixed(1)} %`, color: gc });
	if (s.showSync) line.push({ text: `sync ${(st.strafeSync * 100).toFixed(0)} %`, color: c });
	if (s.showStrafes) line.push({ text: `${st.strafeCount.toFixed(0)} strafes`, color: c });
	if (s.showYawRatio) line.push({ text: `ratio ${st.yawRatio.toFixed(2)}`, color: c });
	if (s.showEfficiency) line.push({ text: `eff ${(st.efficiency * 100).toFixed(0)} %`, color: c });
	if (s.showHeight) line.push({ text: `h ${signed(Math.abs(st.heightDelta) < 0.1 ? 0 : st.heightDelta, 1)}`, color: c });
	if (s.showDistance) line.push({ text: `${st.distance.toFixed(1)} u`, color: c });
	if (s.showTime) line.push({ text: `${st.timeDelta.toFixed(2)} s`, color: c });
	return line.length ? [line] : [];
}

// ---- Panorama ----

// panorama_reload loads this file again, but the old copy's event handlers stay registered (seen
// 2026-11-03: the two copies deleted each other's panel at every jump, so nothing showed). Each load
// takes a new number in Panorama's global object; a handler whose number isn't the latest does nothing.
const GLOBAL = UiToolkitAPI.GetGlobalObject() as Record<string, any>;
const GEN = (GLOBAL['MovekitJhudGen'] = (GLOBAL['MovekitJhudGen'] || 0) + 1);
const live = () => GLOBAL['MovekitJhudGen'] === GEN;

const settings: Settings = { ...DEFAULTS };
let panel: GenericPanel | null = null;
let editing = false;
let token = 0;

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
	panel = $.CreatePanel('Panel', root, ID, { style: 'flow-children: down; width: 400px; transition-property: opacity;' });
	panel.visible = false;
	return panel;
}

function draw(parts: Part[][]) {
	const p = getPanel();
	p.RemoveAndDeleteChildren();
	const font = String(settings.font || '').replace(/"/g, '');
	for (const row of parts) {
		const line = $.CreatePanel('Panel', p, '', { style: 'horizontal-align: center; max-width: 100%; flow-children: right-wrap;' });
		row.forEach((part, i) =>
			$.CreatePanel('Label', line, '', {
				text: part.text,
				style: `${font ? `font-family: "${font}";` : ''} font-size: ${Math.max(6, +settings.fontSize || 22)}px;
					font-weight: bold; color: ${part.color || settings.fontColor}; margin-left: ${i ? 8 : 0}px;
					text-shadow: 0px 1px 4px 2px rgba(0, 0, 0, 0.9);`
			})
		);
	}
}

function show(parts: Part[][], hold: boolean) {
	const p = getPanel();
	draw(parts);
	p.style.transitionDuration = '0s';
	p.style.opacity = '1';
	p.visible = parts.length > 0;
	const mine = ++token;
	if (hold) return;
	$.Schedule(Math.max(0, +settings.holdMs || 0) / 1000, () => {
		if (mine !== token || !live() || !p.IsValid()) return;
		p.style.transitionDuration = `${Math.max(0, +settings.fadeMs || 0) / 1000}s`;
		p.style.opacity = '0';
		$.Schedule(Math.max(0, +settings.fadeMs || 0) / 1000 + 0.05, () => {
			if (mine === token && live() && p.IsValid()) p.visible = false;
		});
	});
}

function hide() {
	++token;
	if (panel && panel.IsValid()) panel.visible = false;
}

function onJump() {
	if (editing || !GAMEMODES.includes(GameModeAPI.GetCurrentGameMode())) return;
	const p = getPanel();
	if (!p.enabled) return; // switched off in the customizer
	const st = MomentumMovementAPI.GetLastJumpStats() as unknown as Stats;
	const n = jumpOf(st);
	if (n < 1 || !shows(n, settings)) return;
	show(rows(st, n, settings), false);
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
					if (editing) show(rows(SAMPLE, jumpOf(SAMPLE), settings), true);
				}
			};
		}
	}
	return { name: 'JHUD', resizeX: true, resizeY: false, gamemode: GAMEMODES, dynamicStyles };
}

// The customizer draws a 3-digit value in its number boxes with the first digit under the minus button
// (seen 2026-11-03: 620 read "520"): the box's text field is fit-children with a 24px min-width and isn't
// widened after the settings are built. While the customizer is open and JHUD is the component being
// edited, its number boxes' text fields get a fixed width that fits 5 digits. The settings list is rebuilt
// whenever a component is picked, with no event for it, so this checks every BOX_FIX_S seconds.
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

$.RegisterForUnhandledEvent('HudCustomizer_Ready', () => {
	if (!live()) return;
	editing = false;
	hide();
	register();
});
$.RegisterForUnhandledEvent('HudCustomizer_Opened', () => {
	if (!live() || !GAMEMODES.includes(GameModeAPI.GetCurrentGameMode())) return;
	editing = true;
	show(rows(SAMPLE, jumpOf(SAMPLE), settings), true);
	fixBoxes();
});
$.RegisterForUnhandledEvent('HudCustomizer_Closed', () => {
	if (!live()) return;
	editing = false;
	hide();
});
$.RegisterForUnhandledEvent('OnJumpStarted', () => {
	if (live()) onJump();
});
// HudCustomizer_Ready comes only at a map load; after panorama_reload in a map, register now, so the
// customizer hands this copy the saved settings
if (GLOBAL['HudCustomizerHandler']?.customizerReady) register();
