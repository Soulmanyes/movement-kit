// Z Penalty, part of Soulmanyes's Movement Kit (z-penalty/ in the repo). Loaded next to timer.ts through
// the kit's timer.xml patch (movekit/panorama.py).
//
// Shows when air acceleration is cut to a quarter by the engine's z velocity penalty, so a ramp climb
// that bleeds speed can be told apart from bad strafing. The rule (CategorizePosition in Momentum's
// mom_gamemovement.cpp): a tick that starts airborne (no walkable ground under the player) with z speed
// above 0 and at most 140 u/s sets m_surfaceFriction to 0.25, and AirAccelerate multiplies by it. The
// value that decides a tick is the z speed at the end of the tick before, which is what GetVelocity()
// reads, so the band needs no gravity correction.
//
// That band also covers the top of every normal jump (probe 14.1, 2026-11-09: exactly 12 ticks per jump,
// z speed falling 12 per tick in free fall). Ramps only, the default, counts a stretch in the band only
// once a tick in it changes z speed by something other than the free fall step: on a ramp climb the
// probe saw z speed rise by about 8 per tick through the whole band (18 ticks). The free fall step is
// sv_gravity times the tick interval (-12 at 800 and 66.67 tick, which the logs show exactly).
//
// A new tick is told by the velocity changing, not by the game time: GetCurrentTime() moves per frame
// while the velocity moves per tick, so a tick number from the time counts one tick twice (in game
// 2026-11-09: that gave a z change of 0 on every other sample and broke the ramp test). A frame slower
// than a tick shows several free fall steps at once, so free fall is any whole number of steps.
//
// What it shows (each part switchable in Momentum's HUD customizer, listed as Z Penalty): a "Z PENALTY"
// label while penalised, the z speed (in the penalty colour while penalised), the ticks spent in the band
// on this stretch, and a vertical z speed bar with the 0-140 band shaded. A sound on entering a penalised
// stretch is set in the hub (Z Penalty page), which writes the SOUND line below through install.py.
//
// Settings live in Momentum's HUD customizer. It loads a component only when hud_default.kv3 has an
// entry for its panel id; install.py hands the kit that entry (ENTRY there), whose dynamicStyles must
// list every setting in STYLES below with the value in DEFAULTS (check_z_penalty.js checks both).
//
// No imports, like the Strafe Review recorder. The plain functions (above "Panorama") are run in node
// by check_z_penalty.js.

const ID = 'MovekitZPenalty';
const GAMEMODES = [1]; // Gamemode.SURF (common/web/enums/gamemode.enum)
const REPLAY_NONE = 0;
const MOVETYPE_OBSERVER = 10; // MomentumMovementAPI.MoveType.OBSERVER
// CustomizerPropertyType in common/hud-customizer.ts
const NONE = 0;
const NUMBER_ENTRY = 1;
const CHECKBOX = 2;
const COLOR_PICKER = 5;
const FONT_PICKER = 7;

// The hub's sound setting. install.py replaces this whole line with the saved one (z-penalty/settings.py).
const SOUND = { on: false, name: 'buttons/blip1', volume: 60 }; // movekit:sound
const SOUND_GAP_MS = 500; // at most one sound per this long, so a flickering contact doesn't stutter

type Settings = Record<string, any>;

// The customizer's values when nothing is saved yet. "$name" is one of the customizer's shared values
// (CustomizerSettings in hud_default.kv3); the customizer swaps in the real value before calling back.
const DEFAULTS: Settings = {
	font: '$fontPrimary',
	fontSize: 22,
	fontColor: '$fontColor',
	backgroundColor: 'rgba(0, 0, 0, 0)',
	rampsOnly: true,
	alwaysShow: false,
	showLabel: true,
	showNumber: true,
	showTicks: true,
	showBar: true,
	barHeight: 120,
	barWidth: 12,
	barMax: 300,
	trackColor: 'rgba(255, 255, 255, 0.15)',
	bandColor: 'rgba(255, 176, 50, 0.35)',
	markerColor: 'rgba(255, 255, 255, 0.9)',
	penaltyColor: 'rgba(255, 176, 50, 1)',
	holdMs: 1500,
	fadeMs: 300
};

// The customizer's rows: [id, name, type, children, extra]. Groups (NONE) only fold their children; a
// checkbox row shows a child only while it is ticked (extra.showWhen). extra.range: a number box's min and
// max. The min is 0: the NumberEntry clamps on every keystroke, so a higher min snaps a half-typed value
// back (owner, 2026-11-03). The real limits are applied where the value is used.
type Extra = { showWhen?: Record<string, unknown[]>; range?: { min: number; max: number } };
const ON = [true, 1];
const OFF = [false, 0];
const STYLES: [string, string, number, string[]?, Extra?][] = [
	['fontStyling', 'Font', NONE, ['font', 'fontSize', 'fontColor', 'backgroundColor']],
	['font', 'Font', FONT_PICKER],
	['fontSize', 'Font size', NUMBER_ENTRY, undefined, { range: { min: 0, max: 99 } }],
	['fontColor', 'Font colour', COLOR_PICKER],
	['backgroundColor', 'Background colour', COLOR_PICKER],
	['when', 'When', NONE, ['rampsOnly', 'alwaysShow']],
	['rampsOnly', 'Ramps only (off: also the top of every jump)', CHECKBOX],
	['alwaysShow', 'Always shown (off: only while penalised)', CHECKBOX, ['holdMs', 'fadeMs'],
		{ showWhen: { holdMs: OFF, fadeMs: OFF } }],
	['holdMs', 'Kept after the penalty (ms)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 10000 } }],
	['fadeMs', 'Fade out (ms)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 5000 } }],
	['parts', 'Parts', NONE, ['showLabel', 'showNumber', 'showTicks', 'showBar', 'penaltyColor']],
	['showLabel', '"Z PENALTY" label', CHECKBOX],
	['showNumber', 'Z speed', CHECKBOX],
	['showTicks', 'Ticks in the band', CHECKBOX],
	['showBar', 'Z speed bar', CHECKBOX, ['barHeight', 'barWidth', 'barMax', 'trackColor', 'bandColor', 'markerColor'],
		{ showWhen: { barHeight: ON, barWidth: ON, barMax: ON, trackColor: ON, bandColor: ON, markerColor: ON } }],
	['barHeight', 'Bar height', NUMBER_ENTRY, undefined, { range: { min: 0, max: 1000 } }],
	['barWidth', 'Bar width', NUMBER_ENTRY, undefined, { range: { min: 0, max: 200 } }],
	['barMax', 'Bar top (u/s)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 5000 } }],
	['trackColor', 'Bar background', COLOR_PICKER],
	['bandColor', '0-140 band', COLOR_PICKER],
	['markerColor', 'Marker', COLOR_PICKER],
	['penaltyColor', 'Penalty colour (label, z speed, marker)', COLOR_PICKER]
];

const BAND = 140; // NON_JUMP_VELOCITY outside the TF2 modes
const FALL_EPS = 0.05; // u/s off a whole number of free fall steps that still counts as free fall
const MAX_DZ = 300; // a bigger z change between two samples is a teleport or a reset: it tells nothing

// What the customizer shows while it is open, so there is something to drag
const SAMPLE = { vz: 96, ticks: 12, penalised: true };

type Tracker = {
	has: boolean; // lastVz is a sample
	lastVz: number;
	inBand: boolean;
	ramp: boolean;
	ticks: number;
	penalised: boolean;
};
type Step = { vz: number; ticks: number; penalised: boolean; entered: boolean; left: boolean };

function newTracker(): Tracker {
	return { has: false, lastVz: 0, inBand: false, ramp: false, ticks: 0, penalised: false };
}

// How many free fall steps a z change is: a whole number of at least 1, or 0 when it isn't free fall
function fallSteps(dz: number, step: number): number {
	if (!(step < 0)) return 0;
	const k = Math.round(dz / step);
	return k >= 1 && Math.abs(dz - k * step) <= FALL_EPS * k ? k : 0;
}

// One new sample's z speed (the velocity changed: one tick, or a few when a frame was slow) into the
// tracker. step: the free fall change per tick (negative). rampsOnly: a stretch in the band counts once
// a tick in it wasn't free fall. Returns the state after the sample.
function track(t: Tracker, vz: number, step: number, rampsOnly: boolean): Step {
	const dz = vz - t.lastVz;
	const known = t.has && Math.abs(dz) <= MAX_DZ;
	const fall = known ? fallSteps(dz, step) : 0;
	const was = t.penalised;
	const inBand = vz > 0 && vz <= BAND;
	if (inBand) {
		if (!t.inBand) {
			t.ticks = 0;
			t.ramp = false;
		}
		t.ticks += Math.max(1, fall);
		// not free fall: on a ramp, or off the ground into the band without a jump (a jump starts near 300)
		if (known && fall === 0) t.ramp = true;
		t.penalised = !rampsOnly || t.ramp;
	} else {
		t.penalised = false;
		t.ramp = false;
	}
	t.inBand = inBand;
	t.has = true;
	t.lastVz = vz;
	return { vz, ticks: t.ticks, penalised: t.penalised, entered: t.penalised && !was, left: was && !t.penalised };
}

// The bar's numbers in pixels: the band's height from the bottom and the marker's offset from the top
function barGeometry(vz: number, s: Settings) {
	const h = Math.max(10, +s.barHeight || 0);
	const top = Math.max(BAND, +s.barMax || 0);
	const band = Math.round((BAND / top) * h);
	const at = Math.min(top, Math.max(0, vz));
	const marker = Math.round(h - (at / top) * h);
	return { h, w: Math.max(2, +s.barWidth || 0), band, marker: Math.min(h - 3, Math.max(0, marker - 1)) };
}

// The text lines: [text, colour, shown] (null colour: the font colour). A line not shown keeps its space
// (opacity 0), so the panel doesn't jump as the label comes and goes.
type Line = [string, string | null, boolean];
function lines(state: { vz: number; ticks: number; penalised: boolean }, s: Settings): Line[] {
	const out: Line[] = [];
	if (s.showLabel) out.push(['Z PENALTY', s.penaltyColor, state.penalised]);
	if (s.showNumber) out.push([`z ${Math.round(state.vz)}`, state.penalised ? s.penaltyColor : null, true]);
	if (s.showTicks) out.push([`${state.ticks} tick${state.ticks === 1 ? '' : 's'}`, null, state.ticks > 0]);
	return out;
}

// ---- Panorama ----

// panorama_reload loads this file again, but the old copy's event handlers stay registered (seen with
// JHUD 2026-11-03). Each load takes a new number in Panorama's global object; a handler whose number
// isn't the latest does nothing.
const GLOBAL = UiToolkitAPI.GetGlobalObject() as Record<string, any>;
const GEN = (GLOBAL['MovekitZPenaltyGen'] = (GLOBAL['MovekitZPenaltyGen'] || 0) + 1);
const live = () => GLOBAL['MovekitZPenaltyGen'] === GEN;

const settings: Settings = { ...DEFAULTS };
let panel: GenericPanel | null = null;
let editing = false;
let spectating = false; // MomentumSpectateStart/Stop; GetMoveType() covers a panorama_reload mid-spectate
let token = 0;
let lastKey = '';
let lastSound = -Infinity;
let lastTicks = 0; // the last penalised stretch's ticks in the band, what the tick count shows

// The free fall change in z speed per tick
function fallStep(): number {
	let g = NaN;
	try {
		g = GameInterfaceAPI.GetSettingFloat('sv_gravity');
	} catch {
		// keep NaN
	}
	return -(g > 0 ? g : 800) * MomentumMovementAPI.GetTickInterval();
}
let tracker = newTracker();
let lastTime = -Infinity;

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
	panel = $.CreatePanel('Panel', root, ID, { style: 'flow-children: right; width: 200px; transition-property: opacity;' });
	panel.visible = false;
	return panel;
}

// Whether the HUD customizer has this panel switched on: its own record (components[ID].enabled, what the
// preset saves), else the panel's flag for a customizer that hasn't taken the panel.
function switchedOn(): boolean {
	const c = GLOBAL['HudCustomizerHandler']?.components?.[ID];
	return c ? c.enabled !== false : getPanel().enabled;
}

// The panel's children are built once per settings change (built.key), then only updated per tick: a
// tick comes up to 100 times a second
let built: { key: string; marker: GenericPanel | null; labels: Label[] } | null = null;

function build(p: GenericPanel) {
	const key = JSON.stringify(settings);
	if (built && built.key === key && p.GetChildCount() > 0) return built;
	p.RemoveAndDeleteChildren();
	built = { key, marker: null, labels: [] };
	if (settings.showBar) {
		const g = barGeometry(0, settings);
		const bar = $.CreatePanel('Panel', p, 'ZPenaltyBar', {
			style: `width: ${g.w}px; height: ${g.h}px; background-color: ${settings.trackColor}; margin-right: 8px; vertical-align: center;`
		});
		$.CreatePanel('Panel', bar, 'ZPenaltyBand', {
			style: `width: 100%; height: ${g.band}px; position: 0px ${g.h - g.band}px 0px; background-color: ${settings.bandColor};`
		});
		built.marker = $.CreatePanel('Panel', bar, 'ZPenaltyMarker', { style: 'width: 100%; height: 3px;' });
	}
	const rows = lines(SAMPLE, settings);
	if (rows.length) {
		const col = $.CreatePanel('Panel', p, '', { style: 'flow-children: down; vertical-align: center;' });
		const font = String(settings.font || '').replace(/"/g, '');
		for (let i = 0; i < rows.length; i++) {
			built.labels.push($.CreatePanel('Label', col, '', {
				text: '',
				style: `${font ? `font-family: "${font}";` : ''} font-size: ${Math.max(6, +settings.fontSize || 22)}px;
					font-weight: bold; text-shadow: 0px 1px 4px 2px rgba(0, 0, 0, 0.9);`
			}) as Label);
		}
	}
	return built;
}

function draw(state: { vz: number; ticks: number; penalised: boolean }) {
	const b = build(getPanel());
	if (b.marker) {
		const g = barGeometry(state.vz, settings);
		b.marker.style.position = `0px ${g.marker}px 0px`;
		b.marker.style.backgroundColor = state.penalised ? settings.penaltyColor : settings.markerColor;
	}
	lines(state, settings).forEach(([text, color, on], i) => {
		const l = b.labels[i];
		if (!l) return;
		l.text = text;
		l.style.color = color || settings.fontColor;
		l.style.opacity = on ? '1' : '0';
	});
}

function showNow() {
	const p = getPanel();
	++token;
	p.style.transitionDuration = '0s';
	p.style.opacity = '1';
	p.visible = true;
}

function fadeLater() {
	const p = getPanel();
	const mine = ++token;
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

// Own play in surf: not a replay, not a watched run, not spectating
function ownPlay(): boolean {
	if (MomentumReplayAPI.GetReplayState() !== REPLAY_NONE || MomentumTimerAPI.GetObservedRunMetadata()) return false;
	if (spectating || MomentumMovementAPI.GetMoveType() === MOVETYPE_OBSERVER) return false;
	return GAMEMODES.includes(GameModeAPI.GetCurrentGameMode());
}

function playSound() {
	if (!SOUND.on) return;
	const now = Date.now();
	if (now - lastSound < SOUND_GAP_MS) return;
	lastSound = now;
	const volume = Math.min(1, Math.max(0, SOUND.volume / 100));
	GameInterfaceAPI.ConsoleCommand(`playvol ${SOUND.name} ${volume}`);
}

// A new tick, if there is one: tracked, drawn, sounded
function sample() {
	const vel = MomentumPlayerAPI.GetVelocity();
	const time = MomentumMovementAPI.GetCurrentTime();
	if (time < lastTime) tracker = newTracker(); // game time went back (map change, reload)
	lastTime = time;
	const key = `${vel.x},${vel.y},${vel.z}`; // a new tick changes the velocity (see the top)
	if (key === lastKey) return;
	lastKey = key;
	const st = track(tracker, vel.z, fallStep(), !!settings.rampsOnly);
	if (st.penalised) lastTicks = st.ticks;
	if (editing) return;
	if (!ownPlay() || !switchedOn()) {
		hide();
		return;
	}
	if (st.entered) playSound();
	const view = { vz: st.vz, ticks: lastTicks, penalised: st.penalised };
	if (settings.alwaysShow || st.penalised) {
		draw(view);
		showNow();
	} else if (st.left) {
		draw(view);
		fadeLater();
	} else if (getPanel().visible) {
		draw(view); // held after the penalty, until the fade
	}
}

function loop() {
	if (!live()) return;
	try {
		sample();
	} catch (e) {
		$.Msg(`${ID}: ${e}`);
	}
	$.Schedule(0, loop);
}

function showSample() {
	draw(SAMPLE);
	showNow();
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
					if (editing) showSample();
				}
			};
		}
	}
	return { name: 'Z Penalty', resizeX: true, resizeY: false, gamemode: GAMEMODES, dynamicStyles };
}

// The customizer draws a 3-digit value in its number boxes with the first digit under the minus button
// (JHUD, 2026-11-03). While the customizer is open and this is the component being edited, its number
// boxes' text fields get a width that fits 5 digits. The settings list is rebuilt whenever a component
// is picked, with no event for it, so this checks every BOX_FIX_S seconds.
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
	else if (on && !p.visible) showSample();
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
	tracker = newTracker(); // a new map
	register();
});
$.RegisterForUnhandledEvent('HudCustomizer_Opened', () => {
	if (!live() || !GAMEMODES.includes(GameModeAPI.GetCurrentGameMode())) return;
	editing = true;
	if (switchedOn()) showSample();
	fixBoxes();
});
$.RegisterForUnhandledEvent('HudCustomizer_Closed', () => {
	if (!live()) return;
	editing = false;
	hide();
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
$.Schedule(0, loop);
