// Zone Exit Speed, part of Soulmanyes's Movement Kit (zone-exit/ in the repo). Loaded next to timer.ts
// through the kit's timer.xml patch (movekit/panorama.py).
//
// When a surf run starts (leaving the start zone): the 3D speed (x, y and z) at that moment, coloured in
// three bands, and how far it is above or below the loaded comparison run's exit speed (normally the PB);
// held for a moment, then faded out. 3D, not horizontal: the start zone caps horizontal speed (about 340
// u/s on surf_aura, probe 2026-11-04), so the pre jump's vertical speed is what tells exits apart.
//
// Momentum's own Zone Velocity speedometer would show this, but its handler is commented out in the game
// (hud/speedometer.ts, "TODO: replace with updates based on new timer events").
//
// The numbers (probe 10.1, 2026-11-04): OnObservedTimerSegmentEffectiveStart fires once on leaving the
// start zone, with the timer RUNNING and majorNum 1. The run's own segments[0].effectiveStartVelocity is
// still [0, 0, 0] then, so the player's velocity at the event is used, unless the split is already filled.
// The comparison run's split holds its exit velocity. Split velocities come as [x, y, z] arrays,
// MomentumPlayerAPI.GetVelocity() as {x, y, z}.
//
// Settings live in Momentum's HUD customizer. It loads a component only when hud_default.kv3 has an
// entry for its panel id; install.py hands the kit that entry (ENTRY there), whose dynamicStyles must
// list every setting in STYLES below with the value in DEFAULTS (check_zone_exit.js checks both).
//
// No imports, like the Strafe Review recorder. The plain functions (above "Panorama") are run in node
// by check_zone_exit.js.

const ID = 'MovekitZoneExit';
const GAMEMODES = [1]; // Gamemode.SURF (common/web/enums/gamemode.enum)
const TIMER_RUNNING = 2; // TimerState in common/timer.ts
const REPLAY_NONE = 0;
const MOVETYPE_OBSERVER = 10; // MomentumMovementAPI.MoveType.OBSERVER
// CustomizerPropertyType in common/hud-customizer.ts
const NONE = 0;
const NUMBER_ENTRY = 1;
const CHECKBOX = 2;
const COLOR_PICKER = 5;
const FONT_PICKER = 7;

type Vec = number[] | { x: number; y: number; z: number } | null | undefined;
type Part = { text: string; color: string | null }; // null: the font colour
type Settings = Record<string, any>;

// The customizer's values when nothing is saved yet. "$name" is one of the customizer's shared values
// (CustomizerSettings in hud_default.kv3); the customizer swaps in the real value before calling back.
// The speed bands are a first guess from the probe (surf_aura: exits 393-429, the PB's 422.5); they
// depend on the map, so they are set in the customizer.
const DEFAULTS: Settings = {
	font: '$fontPrimary',
	fontSize: 28,
	fontColor: '$fontColor',
	backgroundColor: 'rgba(0, 0, 0, 0)',
	colorBands: true,
	speedLow: 400,
	speedHigh: 420,
	lowColor: 'rgba(255, 176, 50, 1)',
	midColor: 'rgba(123, 216, 143, 1)',
	highColor: 'rgba(92, 160, 255, 1)',
	showDiff: true,
	fasterColor: 'rgba(123, 216, 143, 1)',
	slowerColor: 'rgba(255, 92, 92, 1)',
	holdMs: 3000,
	fadeMs: 300
};

// The customizer's rows: [id, name, type, children, extra]. Groups (NONE) only fold their children; a
// checkbox row shows a child only while it is ticked (extra.showWhen). extra.range: a number box's min and
// max. The min is 0: the NumberEntry clamps on every keystroke, so a higher min snaps a half-typed value
// back (owner, 2026-11-03). The real limits are applied where the value is used (font size 6+).
type Extra = { showWhen?: Record<string, unknown[]>; range?: { min: number; max: number } };
const SPEED_RANGE = { range: { min: 0, max: 10000 } };
const ON = [true, 1];
const STYLES: [string, string, number, string[]?, Extra?][] = [
	['fontStyling', 'Font', NONE, ['font', 'fontSize', 'fontColor', 'backgroundColor']],
	['font', 'Font', FONT_PICKER],
	['fontSize', 'Font size', NUMBER_ENTRY, undefined, { range: { min: 0, max: 99 } }],
	['fontColor', 'Font colour', COLOR_PICKER],
	['backgroundColor', 'Background colour', COLOR_PICKER],
	['bands', 'Speed colours', NONE, ['colorBands']],
	['colorBands', 'Colour the speed', CHECKBOX, ['speedLow', 'speedHigh', 'lowColor', 'midColor', 'highColor'],
		{ showWhen: { speedLow: ON, speedHigh: ON, lowColor: ON, midColor: ON, highColor: ON } }],
	['speedLow', 'Middle colour from (u/s)', NUMBER_ENTRY, undefined, SPEED_RANGE],
	['speedHigh', 'Top colour above (u/s)', NUMBER_ENTRY, undefined, SPEED_RANGE],
	['lowColor', 'Below the middle (amber)', COLOR_PICKER],
	['midColor', 'Middle (green)', COLOR_PICKER],
	['highColor', 'Top (blue)', COLOR_PICKER],
	['comparison', 'Comparison', NONE, ['showDiff']],
	['showDiff', 'Difference to the comparison run (PB)', CHECKBOX, ['fasterColor', 'slowerColor'],
		{ showWhen: { fasterColor: ON, slowerColor: ON } }],
	['fasterColor', 'Faster', COLOR_PICKER],
	['slowerColor', 'Slower', COLOR_PICKER],
	['timing', 'Timing', NONE, ['holdMs', 'fadeMs']],
	['holdMs', 'Shown for (ms)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 10000 } }],
	['fadeMs', 'Fade out (ms)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 5000 } }]
];

// Shown while the customizer is open, so there is something to drag
const SAMPLE = { speed: 418.4, comparison: 410.1 };

// A velocity's length (x, y and z), from either shape; NaN when there is none
function speed3(v: Vec): number {
	if (!v) return NaN;
	const [x, y, z] = Array.isArray(v) ? v : [v.x, v.y, v.z];
	return Math.sqrt(x * x + y * y + z * z);
}

// The speed in three bands, like JHUD's gain colours: lowColor under speedLow, midColor up to speedHigh,
// highColor above
function bandColor(speed: number, s: Settings): string {
	if (!(speed >= +s.speedLow)) return s.lowColor;
	return speed <= +s.speedHigh ? s.midColor : s.highColor;
}

const signed = (v: number) => (v >= 0 ? '+' : '') + v.toFixed(0);

// The line to draw: the speed (coloured by band, or the font colour), then the difference to the
// comparison's exit speed when there is one and showDiff is on. Rounded as shown, so 418.4 against 410.6
// reads 418 +8, not +7.
function rows(speed: number, comparison: number | null, s: Settings): Part[][] {
	if (!isFinite(speed)) return [];
	const shown = Math.round(speed);
	const line: Part[] = [{ text: String(shown), color: s.colorBands ? bandColor(speed, s) : null }];
	if (s.showDiff && comparison !== null && isFinite(comparison)) {
		const d = shown - Math.round(comparison);
		line.push({ text: signed(d), color: d >= 0 ? s.fasterColor : s.slowerColor });
	}
	return [line];
}

// ---- Panorama ----

// panorama_reload loads this file again, but the old copy's event handlers stay registered (seen with
// JHUD 2026-11-03). Each load takes a new number in Panorama's global object; a handler whose number
// isn't the latest does nothing.
const GLOBAL = UiToolkitAPI.GetGlobalObject() as Record<string, any>;
const GEN = (GLOBAL['MovekitZoneExitGen'] = (GLOBAL['MovekitZoneExitGen'] || 0) + 1);
const live = () => GLOBAL['MovekitZoneExitGen'] === GEN;

const settings: Settings = { ...DEFAULTS };
let panel: GenericPanel | null = null;
let editing = false;
let spectating = false; // MomentumSpectateStart/Stop; GetMoveType() covers a panorama_reload mid-spectate
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
	panel = $.CreatePanel('Panel', root, ID, { style: 'flow-children: down; width: 200px; transition-property: opacity;' });
	panel.visible = false;
	return panel;
}

// Whether the HUD customizer has this panel switched on: its own record (components[ID].enabled, what the
// preset saves), else the panel's flag for a customizer that hasn't taken the panel.
function switchedOn(): boolean {
	const c = GLOBAL['HudCustomizerHandler']?.components?.[ID];
	const on = c ? c.enabled !== false : getPanel().enabled;
	return on;
}

function draw(parts: Part[][]) {
	const p = getPanel();
	p.RemoveAndDeleteChildren();
	const font = String(settings.font || '').replace(/"/g, '');
	for (const row of parts) {
		const line = $.CreatePanel('Panel', p, '', { style: 'horizontal-align: center; max-width: 100%; flow-children: right;' });
		row.forEach((part, i) =>
			$.CreatePanel('Label', line, '', {
				text: part.text,
				style: `${font ? `font-family: "${font}";` : ''} font-size: ${Math.max(6, +settings.fontSize || 28)}px;
					font-weight: bold; color: ${part.color || settings.fontColor}; margin-left: ${i ? 10 : 0}px;
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

// An own run in surf: not a replay, not spectating
function ownRun(): boolean {
	if (MomentumReplayAPI.GetReplayState() !== REPLAY_NONE || MomentumTimerAPI.GetObservedRunMetadata()) return false;
	if (spectating || MomentumMovementAPI.GetMoveType() === MOVETYPE_OBSERVER) return false;
	return GAMEMODES.includes(GameModeAPI.GetCurrentGameMode());
}

const sameTrack = (a: any, b: any) => !!a && !!b && a.type === b.type && a.number === b.number;

// The comparison run's start zone exit speed on this track, or null
function comparisonSpeed(track: any): number | null {
	const run = RunComparisonsAPI.GetComparisonRun();
	if (!run || !sameTrack(run.trackId, track)) return null;
	const v = speed3(run.runSplits?.segments?.[0]?.effectiveStartVelocity as Vec);
	return v > 0 ? v : null;
}

function onSegmentStart() {
	if (editing || !ownRun()) return;
	const status = MomentumTimerAPI.GetObservedTimerStatus();
	if (status.state !== TIMER_RUNNING || status.majorNum !== 1) return; // the start zone only, not stages
	if (!switchedOn()) return; // switched off in the customizer
	const split = speed3(MomentumTimerAPI.GetObservedTimerRunSplits()?.segments?.[0]?.effectiveStartVelocity as Vec);
	const speed = split > 0 ? split : speed3(MomentumPlayerAPI.GetVelocity() as Vec);
	show(rows(speed, comparisonSpeed(status.trackId), settings), false);
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
				...(extra?.range ? { settingProps: { ...extra.range } } : {}),
				...(children ? { children: children.map((styleID) => ({ styleID, showWhen: extra?.showWhen?.[styleID] })) } : {}),
				callbackFunc: (_: unknown, value: unknown) => {
					settings[id] = value;
					if (editing) show(rows(SAMPLE.speed, SAMPLE.comparison, settings), true);
				}
			};
		}
	}
	return { name: 'Zone Exit', resizeX: true, resizeY: false, gamemode: GAMEMODES, dynamicStyles };
}

// The customizer draws a 3-digit value in its number boxes with the first digit under the minus button
// (JHUD, 2026-11-03): the box's text field is fit-children with a 24px min-width. While the customizer is
// open and this is the component being edited, its number boxes' text fields get a width that fits 5
// digits. The settings list is rebuilt whenever a component is picked, with no event for it, so this
// checks every BOX_FIX_S seconds.
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
// While the customizer is open: the sample hides when the switch is turned off and comes back when it's
// turned on (no event for the switch, so fixBoxes' loop checks)
function sampleFollowsSwitch() {
	const on = switchedOn();
	const p = getPanel();
	if (!on && p.visible) hide();
	else if (on && !p.visible) show(rows(SAMPLE.speed, SAMPLE.comparison, settings), true);
}
function fixBoxes() {
	if (!live() || !editing) return;
	const h = GLOBAL['HudCustomizerHandler'];
	const list = h?.panels?.activeComponentSettingsList as GenericPanel | undefined;
	if (h?.activeComponent?.id === ID && list && list.IsValid()) widenBoxes(list);
	sampleFollowsSwitch();
	$.Schedule(BOX_FIX_S, fixBoxes);
}

// The customizer throws when a setting has no value in the layout it loaded at the map start, and a throw
// here stops the whole script. After an update and a panorama_reload, the loaded layout is the old
// hud_default.kv3, without the new settings. So settings the layout has no value for are left out of the
// customizer until the next map load, where they keep their defaults. values: the loaded layout's
// dynamicStyles for this panel, or null (unknown: nothing left out).
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

$.RegisterForUnhandledEvent('HudCustomizer_Ready', () => {
	if (!live()) return;
	editing = false;
	hide();
	register();
});
$.RegisterForUnhandledEvent('HudCustomizer_Opened', () => {
	if (!live() || !GAMEMODES.includes(GameModeAPI.GetCurrentGameMode())) return;
	editing = true;
	if (switchedOn()) show(rows(SAMPLE.speed, SAMPLE.comparison, settings), true);
	fixBoxes();
});
$.RegisterForUnhandledEvent('HudCustomizer_Closed', () => {
	if (!live()) return;
	editing = false;
	hide();
});
$.RegisterForUnhandledEvent('OnObservedTimerSegmentEffectiveStart', () => {
	if (live()) onSegmentStart();
});
$.RegisterForUnhandledEvent('MomentumSpectateStart', () => {
	if (live()) spectating = true;
});
$.RegisterForUnhandledEvent('MomentumSpectateStop', () => {
	if (live()) spectating = false;
});
// HudCustomizer_Ready comes only at a map load; after panorama_reload in a map, register now, so the
// customizer hands this copy the saved settings
if (GLOBAL['HudCustomizerHandler']?.customizerReady) register();
