// JHUD, part of Soulmanyes's Movement Kit (jhud/ in the repo). Loaded next to timer.ts through the kit's
// timer.xml patch (movekit/panorama.py).
//
// After every bhop jump: the jump's number, speed and speed change, gain % and sync on one line in the
// middle of the screen, the whole line coloured by gain; held for a moment, then faded out. The numbers are the
// game's own (MomentumMovementAPI.GetLastJumpStats(), as its Jump Stats panel shows them).
//
// Settings live in Momentum's HUD customizer. It loads a component only when hud_default.kv3 has an
// entry for its panel id; install.py hands the kit that entry (ENTRY there), whose dynamicStyles must
// list every setting in STYLES below with the value in DEFAULTS (check_jhud.js checks both).
//
// The event for takeoff N carries the air time of jump N-1 (Phase 5.1): jumpCount 1 is a takeoff with
// no air time yet, so it is skipped, and a line is labelled jumpCount - 1. jumpCount resets to 0 when
// the timer primes in the start zone.
//
// No imports, like the Strafe Review recorder. The plain functions (above "Panorama") are run in node
// by check_jhud.js.

const ID = 'MovekitJhud';
const GAMEMODES = [2, 3]; // Gamemode.BHOP, Gamemode.BHOP_HL1 (common/web/enums/gamemode.enum)
// CustomizerPropertyType in common/hud-customizer.ts
const NONE = 0;
const NUMBER_ENTRY = 1;
const CHECKBOX = 2;
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
	gainAll: true,
	firstJump: 1,
	everyJump: 1,
	holdMs: 2000,
	fadeMs: 300
};

// The customizer's rows: [id, name, type, children]. Groups (NONE) only fold their children.
const STYLES: [string, string, number, string[]?][] = [
	['fontStyling', 'Font', NONE, ['font', 'fontSize', 'fontColor', 'backgroundColor']],
	['font', 'Font', FONT_PICKER],
	['fontSize', 'Font size', NUMBER_ENTRY],
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
	['colours', 'Colours', NONE, ['gainAll', 'gainRed', 'gainGreen', 'redColor', 'greenColor']],
	['gainAll', 'Colour the whole line by gain (off: only the gain %)', CHECKBOX],
	['gainRed', 'Gain % shown fully red at or below', NUMBER_ENTRY],
	['gainGreen', 'Gain % shown fully green at or above', NUMBER_ENTRY],
	['redColor', 'Red (bad gain)', COLOR_PICKER],
	['greenColor', 'Green (good gain)', COLOR_PICKER],
	['jumps', 'Which jumps', NONE, ['firstJump', 'everyJump']],
	['firstJump', 'From jump', NUMBER_ENTRY],
	['everyJump', 'Every Nth jump (0: only the first)', NUMBER_ENTRY],
	['timing', 'Timing', NONE, ['holdMs', 'fadeMs']],
	['holdMs', 'Shown for (ms)', NUMBER_ENTRY],
	['fadeMs', 'Fade out (ms)', NUMBER_ENTRY]
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

// The jump a takeoff event describes (1 = jump 1), or 0 when it describes none
function jumpOf(st: Stats): number {
	return Math.max(0, Math.floor(st.jumpCount) - 1);
}

// Whether jump n shows: from firstJump on, every everyJump-th (0: only firstJump), like the game's Jump Stats
function shows(n: number, s: Settings): boolean {
	const first = Math.max(1, Math.floor(+s.firstJump) || 1);
	const every = Math.floor(+s.everyJump) || 0;
	if (n < first) return false;
	return every <= 0 ? n === first : (n - first) % every === 0;
}

const signed = (v: number, digits: number) => (v >= 0 ? '+' : '') + v.toFixed(digits);

// The rows to draw for a jump: one line with every field switched on, in this order, the whole line in
// the gain colour (gainAll) or only the gain %. No fields: no rows. Kept as rows, so a layout with more
// lines can come back without changing draw().
function rows(st: Stats, n: number, s: Settings): Part[][] {
	const g = st.speedGain * 100;
	const gc = gainColor(g, s);
	const c = s.gainAll ? gc : null;
	const line: Part[] = [];
	if (s.showNumber) line.push({ text: `${n}:`, color: c });
	if (s.showSpeed) line.push({ text: st.takeoffSpeed.toFixed(0), color: c });
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

const settings: Settings = { ...DEFAULTS };
let panel: GenericPanel | null = null;
let editing = false;
let token = 0;

function getPanel(): GenericPanel {
	if (panel && panel.IsValid()) return panel;
	const ctx = $.GetContextPanel();
	const root = ctx.GetParent() ?? ctx;
	root.FindChildTraverse(ID)?.DeleteAsync(0);
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
		if (mine !== token || !p.IsValid()) return;
		p.style.transitionDuration = `${Math.max(0, +settings.fadeMs || 0) / 1000}s`;
		p.style.opacity = '0';
		$.Schedule(Math.max(0, +settings.fadeMs || 0) / 1000 + 0.05, () => {
			if (mine === token && p.IsValid()) p.visible = false;
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
	for (const [id, name, type, children] of STYLES) {
		if (type === NONE) {
			dynamicStyles[id] = { name, type, expandable: true, children: (children || []).map((styleID) => ({ styleID })) };
		} else if (id === 'backgroundColor') {
			dynamicStyles[id] = { name, type, styleProperty: 'backgroundColor' };
		} else {
			dynamicStyles[id] = {
				name,
				type,
				callbackFunc: (_: unknown, value: unknown) => {
					settings[id] = value;
					if (editing) show(rows(SAMPLE, jumpOf(SAMPLE), settings), true);
				}
			};
		}
	}
	return { name: 'JHUD', resizeX: true, resizeY: false, gamemode: GAMEMODES, dynamicStyles };
}

$.RegisterForUnhandledEvent('HudCustomizer_Ready', () => {
	editing = false;
	hide();
	const h = UiToolkitAPI.GetGlobalObject()['HudCustomizerHandler'] as any;
	if (h) h.loadComponent(getPanel(), customizerProps());
});
$.RegisterForUnhandledEvent('HudCustomizer_Opened', () => {
	if (!GAMEMODES.includes(GameModeAPI.GetCurrentGameMode())) return;
	editing = true;
	show(rows(SAMPLE, jumpOf(SAMPLE), settings), true);
});
$.RegisterForUnhandledEvent('HudCustomizer_Closed', () => {
	editing = false;
	hide();
});
$.RegisterForUnhandledEvent('OnJumpStarted', onJump);
