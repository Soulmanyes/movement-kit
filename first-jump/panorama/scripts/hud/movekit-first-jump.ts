// First Jump HUD, part of Soulmanyes's Movement Kit (first-jump/ in the repo). Loaded next to timer.ts
// through the kit's timer.xml patch (movekit/panorama.py).
//
// Shortly after jump 1 of a bhop run lands, a panel shows the landing speed and gain %, one box per strafe
// with its gain % (coloured in the same 3 bands as JHUD and the Strafe Speed Histogram), what lost each
// strafe most of its gain under it, and the biggest jump-1 mistake; held for a moment, then faded out.
// Own runs only (tick stats read 0 on replays and while spectating), bhop modes only.
//
// It records its own rows, so it needs no other tool: one row per physics tick (the same columns as Strafe
// Review's recorder, so saved attempts can be fed through it), the last 2 s before the timer starts, and the
// run until jump 1 has landed. The numbers are a port of Strafe Review's viewer (data.js parse/findJumps,
// drill.js strafeStats, checks.js strafeCause and runChecks with the jump-1 checks at their default
// thresholds); check_parity.js diffs the two. Each line also goes to the console (and yaw.log, when Strafe
// Review has con_logfile on) as "FJLINE <started> <json>".
//
// Settings live in Momentum's HUD customizer. It loads a component only when hud_default.kv3 has an entry for
// its panel id; install.py hands the kit that entry (ENTRY there), whose dynamicStyles must list every setting
// in STYLES below with the value in DEFAULTS (check_first_jump.js checks both).
//
// No imports, like the other kit HUD scripts. The plain functions (above "Panorama") are run in node by
// check_first_jump.js and check_parity.js.

const ID = 'MovekitFirstJump';
const LINE_TAG = 'FJLINE';
const GAMEMODES = [1, 2, 3]; // Gamemode.SURF, Gamemode.BHOP, Gamemode.BHOP_HL1 (common/web/enums/gamemode.enum)
// CustomizerPropertyType in common/hud-customizer.ts
const NONE = 0;
const NUMBER_ENTRY = 1;
const CHECKBOX = 2;
const COLOR_PICKER = 5;
const FONT_PICKER = 7;

type Settings = Record<string, any>;

// The customizer's values when nothing is saved yet. "$name" is one of the customizer's shared values
// (CustomizerSettings in hud_default.kv3); the customizer swaps in the real value before calling back.
const DEFAULTS: Settings = {
	font: '$fontPrimary',
	fontSize: 22,
	fontColor: '$fontColor',
	backgroundColor: 'rgba(0, 0, 0, 0)',
	boxSize: 20,
	boxWidth: 116,
	boxTextColor: 'rgba(17, 17, 17, 1)',
	showLanding: true,
	showGain: true,
	showStrafes: true,
	showCauses: true,
	showMistake: true,
	gainLow: 865,
	gainHigh: 920,
	lowColor: 'rgba(255, 176, 50, 1)',
	midColor: 'rgba(123, 216, 143, 1)',
	highColor: 'rgba(92, 160, 255, 1)',
	causeColor: 'rgba(200, 200, 210, 1)',
	holdMs: 4000,
	fadeMs: 300
};

// The customizer's rows: [id, name, type, children, extra]. Groups (NONE) only fold their children.
// extra.range: a number box's min and max. The min is 0: the NumberEntry clamps on every keystroke, so a
// higher min snaps a half-typed value back (PLAN.md Phase 6). The real limits are applied where the value
// is used (sizes 6+, box width 20+).
type Extra = { range?: { min: number; max: number } };
const STYLES: [string, string, number, string[]?, Extra?][] = [
	['fontStyling', 'Font', NONE, ['font', 'fontSize', 'fontColor', 'backgroundColor']],
	['font', 'Font', FONT_PICKER],
	['fontSize', 'Font size (top line; the mistake 3 smaller)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 99 } }],
	['fontColor', 'Font colour', COLOR_PICKER],
	['backgroundColor', 'Background colour', COLOR_PICKER],
	['boxes', 'Strafe boxes', NONE, ['boxSize', 'boxWidth', 'boxTextColor']],
	['boxSize', 'Font size (the cause row 3 smaller)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 99 } }],
	['boxWidth', 'Box width', NUMBER_ENTRY, undefined, { range: { min: 0, max: 999 } }],
	['boxTextColor', 'Text colour in the boxes', COLOR_PICKER],
	['fields', 'Rows', NONE, ['showLanding', 'showGain', 'showStrafes', 'showCauses', 'showMistake']],
	['showLanding', 'Landing speed', CHECKBOX],
	['showGain', 'Gain % of the jump', CHECKBOX],
	['showStrafes', 'Gain % per strafe', CHECKBOX],
	['showCauses', 'What lost each strafe the most', CHECKBOX],
	['showMistake', 'Biggest mistake', CHECKBOX],
	['colours', 'Colours', NONE, ['gainLow', 'gainHigh', 'lowColor', 'midColor', 'highColor', 'causeColor']],
	['gainLow', 'Middle colour from (gain %, tenths: 865 = 86.5 %)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 2000 } }],
	['gainHigh', 'Top colour above (gain %, tenths: 920 = 92 %)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 2000 } }],
	['lowColor', 'Below the middle (amber)', COLOR_PICKER],
	['midColor', 'Middle (green; also a strafe that lost nothing)', COLOR_PICKER],
	['highColor', 'Top (blue)', COLOR_PICKER],
	['causeColor', 'Cause boxes', COLOR_PICKER],
	['timing', 'Timing', NONE, ['holdMs', 'fadeMs']],
	['holdMs', 'Shown for (ms)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 20000 } }],
	['fadeMs', 'Fade out (ms)', NUMBER_ENTRY, undefined, { range: { min: 0, max: 5000 } }]
];

// ---- Recording ----

const TIMER_RUNNING = 2; // TimerState in common/timer.ts
const REPLAY_NONE = 0;
const MOVETYPE_OBSERVER = 10; // MomentumMovementAPI.MoveType.OBSERVER
const PRESTART_SECONDS = 2;
// After the timer stops, rows are still taken this long (a jump 1 landing on the stop tick); then the
// attempt is dropped
const TAIL_SECONDS = 0.5;
const TAIL_WALL_MS = 2000; // give up waiting for tail ticks (game paused, menu)
// The 5-tick turn average reads 2 rows ahead, so the strafes are split a few rows past the landing
const LINE_DELAY_ROWS = 3;

interface Attempt {
	started: number; // Date.now() at the timer start; Strafe Review's recording of the run has the same
	rows: string[];
	preRows: number;
	endRows: number; // rows up to and including the tick the timer stopped on, -1 while it runs
	untilTick: number;
	untilMs: number;
	seen: number; // rows already scanned for a landing
	at: number; // row count at which to work the line out, -1 while waiting for a landing
}

let interval = MomentumMovementAPI.GetTickInterval();
let ringSize = Math.ceil(PRESTART_SECONDS / interval);
let ring: string[] = [];
let attempt: Attempt | null = null;
let lastTick = -1;
let lastKey = '';
let lastState = MomentumTimerAPI.GetObservedTimerStatus().state;
let spectating = false; // MomentumSpectateStart/Stop; GetMoveType() covers a panorama_reload mid-spectate

function r(value: number, digits: number) {
	return Number.isFinite(value) ? value.toFixed(digits) : 'nan';
}

// One row of what the APIs read now: Strafe Review's COLS (tick, gain, ideal, ratio, right, vx, vy, vz,
// yaw, pitch, buttons, move, duck, rtick, wx, wy, seek), rtick -1 and seek 0
function rowNow(tick: number) {
	const stats = MomentumMovementAPI.GetLastTickStats();
	const vel = MomentumPlayerAPI.GetVelocity();
	const ang = MomentumPlayerAPI.GetAngles();
	const move = MomentumMovementAPI.GetMoveHudData();
	return [
		tick,
		r(stats.speedGain, 3),
		r(stats.idealGain, 3),
		r(stats.yawRatio, 3),
		stats.strafeRight,
		r(vel.x, 2),
		r(vel.y, 2),
		r(vel.z, 2),
		r(ang.y, 3),
		r(ang.x, 3),
		MomentumInputAPI.GetButtons().physicalButtons,
		move.moveStatus,
		MomentumPlayerAPI.IsDucking() ? 1 : 0,
		-1,
		r(move.wishVel.x, 2),
		r(move.wishVel.y, 2),
		0
	].join(',');
}

// Strafe Review's sample(): a row when the tick stats or velocity change (a new tick), or each tick of game
// time while standing still
function sample() {
	const stats = MomentumMovementAPI.GetLastTickStats();
	const vel = MomentumPlayerAPI.GetVelocity();
	const key = `${stats.speedGain},${stats.idealGain},${stats.yawRatio},${stats.strafeRight},${vel.x},${vel.y},${vel.z}`;
	const floorTick = Math.floor(MomentumMovementAPI.GetCurrentTime() / interval);
	if (floorTick < lastTick - 1) lastTick = -1; // game time went back (map change, reload)
	let tick: number;
	if (key !== lastKey) tick = Math.max(floorTick, lastTick + 1);
	else if (floorTick > lastTick && vel.x === 0 && vel.y === 0 && vel.z === 0) tick = floorTick;
	else return;
	lastKey = key;
	lastTick = tick;
	const row = rowNow(tick);
	ring.push(row);
	if (ring.length > ringSize) ring.shift();
	if (attempt) attempt.rows.push(row);
}

// An own run in a bhop mode: replays and spectated players have no tick stats
function ownRun() {
	if (MomentumReplayAPI.GetReplayState() !== REPLAY_NONE || MomentumTimerAPI.GetObservedRunMetadata()) return false;
	if (spectating || MomentumMovementAPI.GetMoveType() === MOVETYPE_OBSERVER) return false;
	return GAMEMODES.includes(GameModeAPI.GetCurrentGameMode());
}

function onTimerState() {
	const status = MomentumTimerAPI.GetObservedTimerStatus();
	if (status.state === TIMER_RUNNING && lastState !== TIMER_RUNNING) {
		attempt = ownRun()
			? { started: Date.now(), rows: ring.slice(), preRows: ring.length, endRows: -1, untilTick: 0, untilMs: 0, seen: 0, at: -1 }
			: null;
	} else if (lastState === TIMER_RUNNING && status.state !== TIMER_RUNNING && attempt && attempt.endRows < 0) {
		attempt.endRows = attempt.rows.length;
		attempt.untilTick = lastTick + Math.ceil(TAIL_SECONDS / interval);
		attempt.untilMs = Date.now() + TAIL_WALL_MS;
	}
	lastState = status.state;
}

// New map: the tickrate may differ. An attempt still open is dropped.
function onLevelInit() {
	attempt = null;
	lastState = MomentumTimerAPI.GetObservedTimerStatus().state;
	interval = MomentumMovementAPI.GetTickInterval();
	ringSize = Math.ceil(PRESTART_SECONDS / interval);
	ring = [];
	lastTick = -1;
}

// ---- Jump 1 (a port of the viewer's code; check_parity.js diffs it) ----

// checks.js defaults (CHECKS), jump-1 checks only
const CFG = {
	early: { minTicks: 18 },
	lateFirst: { maxTicks: 3 },
	wide: { ratio: 1.2, skip: 3 },
	narrow: { ratio: 0.4, skip: 3 },
	uneven: { spread: 0.9, skip: 3 },
	wrongKey: { minTicks: 2 },
	noKey: { minTicks: 3 },
	switch: { early: 4, late: 2 }
};
// checks.js TIMED: tick counts at 100 tick, scaled to the same time at this tickrate (rounded up)
const atRate = (ticks: number) => Math.ceil((ticks * 0.01) / interval - 1e-6);
const SWITCH_WINDOW = 8;
const COLLISION = 10;
const B_LEFT = 1 << 7;
const B_RIGHT = 1 << 8;
const B_MOVELEFT = 1 << 9;
const B_MOVERIGHT = 1 << 10;
const B_FORWARD = 1 << 3;
const B_BACK = 1 << 4;
const EXACT_YAW_MAX = 10; // data.js: a wish-velocity yaw further than this from the recorded one isn't used

interface Rows {
	n: number;
	tick: number[];
	gain: number[];
	ideal: number[];
	ratio: number[];
	vz: number[];
	buttons: number[];
	speed: number[];
	gap: number[];
	ground: number[];
	yaws: number[];
	key: number[]; // ideal key: +1 turning left (A), -1 right (D), 0 no clear turn
}

interface Jump {
	s: number;
	e: number;
	pct: number;
	land: number;
}

interface Strafe {
	dir: number;
	i0: number;
	i1: number;
	n: number;
	gap: boolean;
	btn: number;
}

interface Mistake {
	check: string;
	i0: number;
	lost: number;
	text: string;
}

function wrap180(a: number) {
	return ((((a + 180) % 360) + 360) % 360) - 180;
}

function median(vs: number[]) {
	if (!vs.length) return NaN;
	const s = [...vs].sort((a, b) => a - b);
	const m = s.length >> 1;
	return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function pctile(vs: number[], q: number) {
	if (!vs.length) return NaN;
	const s = [...vs].sort((a, b) => a - b);
	return s[Math.min(s.length - 1, Math.floor(q * s.length))];
}

function keyDir(b: number) {
	const a = (b & B_MOVELEFT) !== 0;
	const d = (b & B_MOVERIGHT) !== 0;
	return a && !d ? 1 : d && !a ? -1 : 0;
}

// data.js parse(), own-run columns only
function parseRows(rows: string[]): Rows {
	const n = rows.length;
	const d: Rows = { n, tick: [], gain: [], ideal: [], ratio: [], vz: [], buttons: [], speed: [], gap: [], ground: [], yaws: [], key: [] };
	const yaw: number[] = [];
	const yawd: number[] = [];
	const wx: number[] = [];
	const wy: number[] = [];
	for (let i = 0; i < n; i++) {
		const v = rows[i].split(',');
		d.tick.push(+v[0]);
		d.gain.push(+v[1]);
		d.ideal.push(+v[2]);
		d.ratio.push(+v[3]);
		d.vz.push(+v[7]);
		yaw.push(+v[8]);
		d.buttons.push(+v[10]);
		d.speed.push(Math.hypot(+v[5], +v[6]));
		d.gap.push(i > 0 ? d.tick[i] - d.tick[i - 1] - 1 : 0);
		wx.push(+v[14]);
		wy.push(+v[15]);
	}
	exactYaw(d, yaw, wx, wy);
	// Ground: vz exactly 0, except an apex between rising and falling
	for (let i = 0; i < n; i++) {
		const prev = i > 0 ? d.vz[i - 1] : 0;
		const next = i < n - 1 ? d.vz[i + 1] : 0;
		d.ground.push(d.vz[i] !== 0 ? 0 : prev > 0 && next < 0 ? 0 : 1);
		yawd.push(i > 0 && d.gap[i] === 0 ? wrap180(yaw[i] - yaw[i - 1]) : NaN);
	}
	for (let i = 0; i < n; i++) {
		let sum = 0;
		let cnt = 0;
		for (let j = i - 2; j <= i + 2; j++) {
			if (j < 0 || j >= n || Math.abs(d.tick[j] - d.tick[i]) > 2 || !Number.isFinite(yawd[j])) continue;
			sum += yawd[j];
			cnt++;
		}
		d.yaws.push(cnt ? sum / cnt : NaN);
		d.key.push(!d.ground[i] && Math.abs(d.yaws[i]) > 0.3 ? Math.sign(d.yaws[i]) : 0);
	}
	return d;
}

// data.js parse(): the exact yaw from the wish velocity on ticks with a strafe key, the recorded yaw moved by
// the offset to it (linear between exact ticks) elsewhere. Needs wish velocity on some air row.
function exactYaw(d: Rows, yaw: number[], wx: number[], wy: number[]) {
	const n = d.n;
	let has = false;
	for (let i = 0; i < n && !has; i++) {
		const v = d.vz[i];
		const air = v !== 0 || (i > 0 && i < n - 1 && d.vz[i - 1] > 0 && d.vz[i + 1] < 0);
		if (air && Math.hypot(wx[i], wy[i]) > 0.1) has = true;
	}
	if (!has) return;
	const corr: number[] = [];
	for (let i = 0; i < n; i++) {
		const b = d.buttons[i];
		const f = (b & B_FORWARD ? 1 : 0) - (b & B_BACK ? 1 : 0);
		const sd = (b & B_MOVERIGHT ? 1 : 0) - (b & B_MOVELEFT ? 1 : 0);
		corr.push(NaN);
		if ((!f && !sd) || !(Math.hypot(wx[i], wy[i]) >= 1)) continue;
		const c = wrap180(((Math.atan2(wy[i], wx[i]) - Math.atan2(-sd, f)) * 180) / Math.PI - yaw[i]);
		if (Math.abs(c) <= EXACT_YAW_MAX) corr[i] = c;
	}
	let prev = -1;
	for (let i = 0; i <= n; i++) {
		if (i < n && !Number.isFinite(corr[i])) continue;
		for (let k = prev + 1; k < i; k++) {
			const c = prev < 0 ? (i < n ? corr[i] : 0) : i >= n ? corr[prev] : corr[prev] + ((corr[i] - corr[prev]) * (k - prev)) / (i - prev);
			yaw[k] = wrap180(yaw[k] + c);
		}
		if (i < n) yaw[i] = wrap180(yaw[i] + corr[i]);
		prev = i;
	}
}

// data.js findJumps(): jump 1 is the air segment in progress at the timer start, else the next one
function findJump1(d: Rows, preRows: number): Jump | null {
	const takeoffs: number[] = [];
	for (let i = 1; i < d.n; i++) if (d.vz[i] > 100 && d.vz[i - 1] <= 0.5) takeoffs.push(i);
	let jumps = takeoffs.map((s, k) => {
		const stop = k + 1 < takeoffs.length ? takeoffs[k + 1] : d.n;
		let e = s + 1;
		while (e < stop && !d.ground[e]) e++;
		let g = 0;
		let id = 0;
		for (let j = s; j < e; j++) {
			if (!Number.isFinite(d.gain[j]) || !Number.isFinite(d.ideal[j])) continue;
			g += d.gain[j];
			id += d.ideal[j];
		}
		return { s, e, pct: id > 0 ? (100 * g) / id : NaN, land: d.speed[e - 1] };
	});
	const p = Math.min(preRows, d.n - 1);
	let tp = -1;
	for (let i = 1; i <= p; i++) {
		if (d.gap[i] > 0) continue;
		const a = d.speed[i - 1];
		const b = d.speed[i];
		if ((a > 100 && b < 1) || (a < 1 && b > 100)) tp = i;
	}
	if (tp > 0) jumps = jumps.filter((j) => j.e > tp);
	let j1 = jumps.findIndex((j) => j.s <= p && j.e > p);
	if (j1 < 0) j1 = jumps.findIndex((j) => j.s >= p);
	return j1 < 0 ? null : jumps[j1];
}

const strafing = (d: Rows, i: number) => !d.ground[i] && d.speed[i] > 100 && !(d.gain[i] < -COLLISION);
const turnBtn = (d: Rows, i: number) => (d.buttons[i] & (B_LEFT | B_RIGHT)) !== 0;

function strafesOf(d: Rows, s: number, e: number): Strafe[] {
	const out: Strafe[] = [];
	let cur: Strafe | null = null;
	for (let i = s; i < e; i++) {
		const k = d.key[i];
		if (!k) continue;
		if (!cur || cur.dir !== k) {
			cur = { dir: k, i0: i, i1: i, n: 0, gap: false, btn: 0 };
			out.push(cur);
		}
		cur.i1 = i;
	}
	for (const st of out) {
		st.n = d.tick[st.i1] - d.tick[st.i0] + 1;
		for (let i = st.i0; i <= st.i1; i++) {
			if (i > st.i0 && d.gap[i] > 0) st.gap = true;
			if (turnBtn(d, i)) st.btn++;
		}
	}
	return out;
}

function switchesOf(d: Rows, s: number, e: number) {
	const out: { i: number; dir: number }[] = [];
	let last = 0;
	for (let i = Math.max(s - SWITCH_WINDOW, 0); i < e; i++) {
		const k = keyDir(d.buttons[i]);
		if (!k) continue;
		if (last && k !== last) out.push({ i, dir: k });
		last = k;
	}
	return out;
}

function lostOver(d: Rows, i0: number, i1: number) {
	let s = 0;
	for (let i = i0; i <= i1; i++) if (strafing(d, i) && Number.isFinite(d.gain[i]) && Number.isFinite(d.ideal[i])) s += d.ideal[i] - d.gain[i];
	return Math.max(s, 0);
}

function turnStart(d: Rows, s: number, dir: number) {
	let from = s;
	let still = 0;
	for (let i = s - 1; i >= 0 && d.gap[i + 1] === 0; i--) {
		const k = d.key[i];
		if (k === dir) {
			from = i;
			still = 0;
		} else if (k || ++still > 3) break;
	}
	return from;
}

function interior(d: Rows, st: Strafe, skip: number) {
	const out: number[] = [];
	for (let i = st.i0 + skip; i <= st.i1 - skip; i++) if (strafing(d, i) && !turnBtn(d, i) && d.gap[i] === 0) out.push(i);
	return out;
}

function runsOf(d: Rows, from: number, to: number, bad: (i: number) => boolean, min: number) {
	const out: { i0: number; i1: number }[] = [];
	let r: { i0: number; i1: number } | null = null;
	for (let i = from; i < to; i++) {
		if (bad(i) && !(r && d.gap[i] > 0)) {
			if (!r) r = { i0: i, i1: i };
			r.i1 = i;
			continue;
		}
		if (r && r.i1 - r.i0 + 1 >= min) out.push(r);
		r = bad(i) ? { i0: i, i1: i } : null;
	}
	if (r && r.i1 - r.i0 + 1 >= min) out.push(r);
	return out;
}

// Loss causes per strafe, a port of checks.js strafeCause(): a tick gaining under CAUSE_LOSS of ideal is a
// lost tick, put down to keys (no key, or the other one, held while turning), slow (angle under CAUSE_LO of
// optimal, or turning the wrong way) or fast (over CAUSE_HI). +left/+right ticks count by their angle like
// mouse turning. Lost ticks inside the band, or with no angle known, are left out.
const CAUSE_LOSS = 0.75;
const CAUSE_LO = 0.85;
const CAUSE_HI = 1.15;
type Cause = 'keys' | 'slow' | 'fast';

// drill.js strafeStats(): gain % per strafe over the rows the checks judge, plus the cause that lost the
// strafe the most u/s and its tick count (null: no lost ticks with a cause)
function strafePcts(d: Rows, sts: Strafe[]) {
	return sts.map((st) => {
		let g = 0;
		let id = 0;
		const by: Record<Cause, { lost: number; ticks: number }> = { keys: { lost: 0, ticks: 0 }, slow: { lost: 0, ticks: 0 }, fast: { lost: 0, ticks: 0 } };
		for (let i = st.i0; i <= st.i1; i++) {
			if (!strafing(d, i) || !Number.isFinite(d.gain[i]) || !Number.isFinite(d.ideal[i])) continue;
			g += d.gain[i];
			id += d.ideal[i];
			if (!(d.gain[i] < CAUSE_LOSS * d.ideal[i])) continue;
			const r = d.ratio[i];
			const cause: Cause | null =
				keyDir(d.buttons[i]) !== st.dir ? 'keys' : !Number.isFinite(r) ? null : r < CAUSE_LO ? 'slow' : r > CAUSE_HI ? 'fast' : null;
			if (!cause) continue;
			by[cause].lost += d.ideal[i] - d.gain[i];
			by[cause].ticks++;
		}
		let top: { cause: Cause; ticks: number } | null = null;
		let most = 0;
		for (const c of ['keys', 'slow', 'fast'] as Cause[])
			if (by[c].lost > most) {
				most = by[c].lost;
				top = { cause: c, ticks: by[c].ticks };
			}
		return { dir: st.dir, pct: id > 0 ? (100 * g) / id : NaN, top };
	});
}

const KEY = (dir: number) => (dir > 0 ? 'A' : 'D');

// checks.js runChecks() for jump 1 (weak takeoff needs other attempts, imbalance the whole run)
function jump1Mistakes(d: Rows, j: Jump, e: number, sts: Strafe[]): Mistake[] {
	const s = j.s;
	const out: Mistake[] = [];
	const add = (check: string, i0: number, i1: number, text: string, lost?: number) =>
		out.push({ check, i0, lost: lost === undefined ? lostOver(d, i0, i1) : lost, text });
	const reversals = sts.slice(1).map((st) => st.i0);
	const nearReversal = (i: number) => reversals.some((r) => Math.abs(d.tick[i] - d.tick[r]) <= SWITCH_WINDOW / 2);

	const first = sts[0];
	if (first && sts.length > 1 && !first.gap) {
		const len = d.tick[first.i1] - d.tick[turnStart(d, s, first.dir)] + 1;
		if (len < atRate(CFG.early.minTicks)) add('early', s, first.i1, `reversed after ${len} ticks`);
	}

	let at = -1;
	for (let i = s; i < e; i++) {
		if (d.key[i] && keyDir(d.buttons[i]) === d.key[i]) {
			at = i;
			break;
		}
	}
	const delay = at < 0 ? NaN : d.tick[at] - d.tick[s];
	if (delay > atRate(CFG.lateFirst.maxTicks)) add('lateFirst', s, at - 1, `first key ${delay} ticks late`);

	sts.forEach((st, k) => {
		if (st.gap || st.n < 8) return;
		const name = `${KEY(st.dir)}${k + 1}`;
		const inW = interior(d, st, CFG.wide.skip).filter((i) => Number.isFinite(d.ratio[i]));
		const mW = median(inW.map((i) => d.ratio[i]));
		if (inW.length >= 4 && mW > CFG.wide.ratio) add('wide', st.i0, st.i1, `${name} too wide (${mW.toFixed(2)})`, lostOver(d, inW[0], inW[inW.length - 1]));
		const inN = interior(d, st, CFG.narrow.skip).filter((i) => Number.isFinite(d.ratio[i]));
		const mN = median(inN.map((i) => d.ratio[i]));
		if (inN.length >= 4 && mN < CFG.narrow.ratio) add('narrow', st.i0, st.i1, `${name} too narrow (${mN.toFixed(2)})`, lostOver(d, inN[0], inN[inN.length - 1]));
		const inU = interior(d, st, CFG.uneven.skip)
			.map((i) => Math.abs(d.yaws[i]))
			.filter(Number.isFinite);
		const mid = median(inU);
		const spread = mid > 0 ? (pctile(inU, 0.9) - pctile(inU, 0.1)) / mid : NaN;
		if (inU.length >= 6 && spread > CFG.uneven.spread) add('uneven', st.i0, st.i1, `${name} uneven turn`);
	});

	const judged = (i: number) => d.key[i] !== 0 && !turnBtn(d, i) && !nearReversal(i);
	for (const r of runsOf(d, s, e, (i) => judged(i) && keyDir(d.buttons[i]) === -d.key[i], atRate(CFG.wrongKey.minTicks)))
		add('wrongKey', r.i0, r.i1, `wrong key ${r.i1 - r.i0 + 1} ticks`);
	for (const r of runsOf(d, s, e, (i) => judged(i) && !(d.buttons[i] & (B_MOVELEFT | B_MOVERIGHT)), atRate(CFG.noKey.minTicks)))
		add('noKey', r.i0, r.i1, `no key ${r.i1 - r.i0 + 1} ticks`);

	const sw = switchesOf(d, s, e);
	for (let k = 1; k < sts.length; k++) {
		const st = sts[k];
		if (st.gap || sts[k - 1].gap) continue;
		let best: { off: number; i: number } | null = null;
		for (const w of sw) {
			if (w.dir !== st.dir) continue;
			const off = d.tick[w.i] - d.tick[st.i0];
			if (Math.abs(off) <= SWITCH_WINDOW && (!best || Math.abs(off + 1) < Math.abs(best.off + 1))) best = { off, i: w.i };
		}
		if (!best) continue;
		const lo = Math.min(best.i, st.i0);
		const hi = Math.max(best.i, st.i0);
		if (best.off <= -CFG.switch.early) add('switch', lo, hi, `${KEY(st.dir)} switch ${-best.off} ticks early`);
		else if (best.off >= CFG.switch.late) add('switch', lo, hi, `${KEY(st.dir)} switch ${best.off} ticks late`);
	}

	out.sort((a, b) => b.lost - a.lost);
	return out;
}

interface StrafeLine {
	dir: number;
	pct: number;
	top: { cause: string; ticks: number } | null;
}
interface Line {
	s: number;
	e: number;
	land: number;
	pct: number;
	strafes: StrafeLine[];
	mistakes: Mistake[];
}

// Jump 1 of an attempt once it has landed, or null (not landed yet: the landing seen was a hop before
// jump 1, or the run ended in the air)
function workOut(a: Attempt): Line | null {
	const d = parseRows(a.rows);
	const endIdx = a.endRows >= 0 ? a.endRows - 1 : d.n - 1;
	const j = findJump1(d, a.preRows);
	if (!j || j.e >= d.n || j.e - 1 > endIdx) return null;
	const e = Math.min(j.e, endIdx + 1);
	const sts = strafesOf(d, j.s, e);
	return { s: j.s, e: j.e, land: j.land, pct: j.pct, strafes: strafePcts(d, sts), mistakes: jump1Mistakes(d, j, e, sts) };
}

// The console line for check_parity.js --log (rounded as the viewer's numbers are compared)
function logLine(a: Attempt, L: Line) {
	$.Msg(
		`${LINE_TAG} ${a.started} ${JSON.stringify({
			map: MapCacheAPI.GetMapName(),
			s: L.s,
			e: L.e,
			land: +L.land.toFixed(3),
			pct: +L.pct.toFixed(3),
			strafes: L.strafes.map((p) => [p.dir, +p.pct.toFixed(3)]),
			causes: L.strafes.map((p) => (p.top ? [p.top.cause, p.top.ticks] : null)),
			mistakes: L.mistakes.map((m) => [m.check, m.i0, +m.lost.toFixed(3)])
		})}`
	);
}

// Scans new rows for a landing (vz from falling to exactly 0, or a takeoff); works the line out a few rows
// later. Returns the line once jump 1 has landed; the attempt is then done.
function lineStep(): Line | null {
	const a = attempt;
	if (!a) return null;
	for (; a.seen < a.rows.length; a.seen++) {
		if (a.seen === 0 || a.at >= 0) continue;
		const vz = Number(a.rows[a.seen].split(',')[7]);
		const prev = Number(a.rows[a.seen - 1].split(',')[7]);
		// A missed landing tick goes straight from falling to the next takeoff, which also ends a jump in findJumps
		if ((vz === 0 && prev < 0) || (vz > 100 && prev <= 0.5)) a.at = a.seen + 1 + LINE_DELAY_ROWS;
	}
	if (a.at < 0 || a.rows.length < a.at) return null;
	a.at = -1;
	const L = workOut(a);
	if (!L) return null; // keep scanning for the next landing
	attempt = null;
	logLine(a, L);
	return L;
}

// ---- Display ----

type Box = { text: string; color: string };
type Parts = { head: string; boxes: Box[]; causes: Box[]; mistake: string };

const NO_VALUE = 'rgba(140, 140, 150, 1)';

// Gain % in three bands, the same as JHUD and the Strafe Speed Histogram (owner, 2026-11-03): lowColor
// under gainLow, midColor up to gainHigh, highColor above. Thresholds in tenths of a % (865 = 86.5 %).
function gainColor(pct: number, s: Settings): string {
	if (!Number.isFinite(pct)) return NO_VALUE;
	if (!(pct >= +s.gainLow / 10)) return s.lowColor;
	return pct <= +s.gainHigh / 10 ? s.midColor : s.highColor;
}

const fmt = (v: number, n: number) => (Number.isFinite(v) ? v.toFixed(n) : '-');

// What to draw for a line, with the rows switched on: the top line (landing, gain), a box per strafe, the
// strafe's top loss cause under each, the biggest mistake. Nothing switched on: every part empty.
function parts(L: Line, s: Settings): Parts {
	const head = [s.showLanding ? `J1 ${fmt(L.land, 0)} u/s` : '', s.showGain ? `${fmt(L.pct, 2)} %` : '']
		.filter(Boolean)
		.join('  ·  ');
	const boxes = s.showStrafes ? L.strafes.map((st) => ({ text: `${KEY(st.dir)} ${fmt(st.pct, 1)} %`, color: gainColor(st.pct, s) })) : [];
	const causes =
		s.showStrafes && s.showCauses
			? L.strafes.map((st) => (st.top ? { text: `${st.top.cause} ${st.top.ticks}t`, color: s.causeColor } : { text: 'ok', color: s.midColor }))
			: [];
	const top = L.mistakes[0];
	const mistake = s.showMistake && top ? `${top.text} (-${top.lost.toFixed(1)} u/s)` : '';
	return { head, boxes, causes, mistake };
}

const empty = (p: Parts) => !p.head && !p.boxes.length && !p.mistake;

// Shown while the customizer is open, so there is something to drag
const SAMPLE: Line = {
	s: 0,
	e: 0,
	land: 291,
	pct: 89.62,
	strafes: [
		{ dir: 1, pct: 93.4, top: null },
		{ dir: -1, pct: 88.1, top: { cause: 'fast', ticks: 4 } },
		{ dir: 1, pct: 84.7, top: { cause: 'keys', ticks: 3 } }
	],
	mistakes: [{ check: 'switch', i0: 0, lost: 5.6, text: 'A switch 4 ticks early' }]
};

// ---- Panorama ----

// panorama_reload loads this file again, but the old copy's event handlers and loop stay (PLAN.md Phase 5).
// Each load takes a new number in Panorama's global object; a copy whose number isn't the latest does nothing.
const GLOBAL = UiToolkitAPI.GetGlobalObject() as Record<string, any>;
const GEN = (GLOBAL['MovekitFirstJumpGen'] = (GLOBAL['MovekitFirstJumpGen'] || 0) + 1);
const live = () => GLOBAL['MovekitFirstJumpGen'] === GEN;

const settings: Settings = { ...DEFAULTS };
let panel: GenericPanel | null = null;
let editing = false;
let token = 0;

const SHADOW = 'text-shadow: 0px 1px 4px 2px rgba(0, 0, 0, 0.9);';

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
	panel = $.CreatePanel('Panel', root, ID, { style: 'flow-children: down; width: 720px; transition-property: opacity;' });
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

const size = (v: unknown, fallback: number, min: number) => Math.max(min, +(v as number) || fallback);

function draw(p: Parts) {
	const root = getPanel();
	root.RemoveAndDeleteChildren();
	const font = String(settings.font || '').replace(/"/g, '');
	const family = font ? `font-family: "${font}";` : '';
	const fontSize = size(settings.fontSize, 22, 6);
	const text = (t: string, px: number) =>
		$.CreatePanel('Label', root, '', {
			text: t,
			style: `horizontal-align: center; ${family} font-size: ${px}px; font-weight: bold; color: ${settings.fontColor}; ${SHADOW}`
		});
	// fixed box width, so each cause box sits under its gain box
	const row = (boxes: Box[], px: number) => {
		if (!boxes.length) return;
		const line = $.CreatePanel('Panel', root, '', { style: 'horizontal-align: center; flow-children: right; margin: 4px 0px 0px 0px;' });
		for (const b of boxes)
			$.CreatePanel('Label', line, '', {
				text: b.text,
				style: `width: ${size(settings.boxWidth, 116, 20)}px; text-align: center; ${family} font-size: ${px}px; font-weight: bold;
					color: ${settings.boxTextColor}; background-color: ${b.color}; padding: 2px 0px; margin: 0px 3px; border-radius: 4px;`
			});
	};
	const boxSize = size(settings.boxSize, 20, 6);
	if (p.head) text(p.head, fontSize);
	row(p.boxes, boxSize);
	row(p.causes, Math.max(6, boxSize - 3));
	if (p.mistake) text(p.mistake, Math.max(6, fontSize - 3));
}

function show(p: Parts, hold: boolean) {
	const root = getPanel();
	draw(p);
	root.style.transitionDuration = '0s';
	root.style.opacity = '1';
	root.visible = !empty(p);
	const mine = ++token;
	if (hold) return;
	const fade = Math.max(0, +settings.fadeMs || 0) / 1000;
	$.Schedule(Math.max(0, +settings.holdMs || 0) / 1000, () => {
		if (mine !== token || !live() || !root.IsValid()) return;
		root.style.transitionDuration = `${fade}s`;
		root.style.opacity = '0';
		$.Schedule(fade + 0.05, () => {
			if (mine === token && live() && root.IsValid()) root.visible = false;
		});
	});
}

function hide() {
	++token;
	if (panel && panel.IsValid()) panel.visible = false;
}

// Once per frame: a row when a new tick shows up, then the line once jump 1 has landed
function loop() {
	if (!live()) return; // a newer load runs its own loop
	guard('sample', sample);
	guard('line', () => {
		const L = lineStep();
		if (L && !editing && switchedOn()) {
			const p = parts(L, settings);
			if (!empty(p)) show(p, false);
		}
		const a = attempt;
		if (a && a.endRows >= 0 && (lastTick >= a.untilTick || Date.now() > a.untilMs)) attempt = null;
	});
	$.Schedule(0, loop);
}

const reported = new Set<string>();
// Runs fn and logs its first exception only, so a throw every frame can't flood the console
function guard(where: string, fn: () => void) {
	try {
		fn();
	} catch (e) {
		if (reported.has(where)) return;
		reported.add(where);
		$.Msg(`${ID}: error in ${where}: ${e}`);
	}
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
				callbackFunc: (_: unknown, value: unknown) => {
					settings[id] = value;
					if (editing) show(parts(SAMPLE, settings), true);
				}
			};
		}
	}
	return { name: 'First Jump', resizeX: true, resizeY: false, gamemode: GAMEMODES, dynamicStyles };
}

// The customizer draws a 3-digit value in its number boxes with the first digit under the minus button (JHUD,
// 2026-11-03). While the customizer is open and this is the component being edited, its number boxes' text
// fields get a width that fits 5 digits. The list is rebuilt whenever a component is picked, with no event
// for it, so this checks every BOX_FIX_S seconds.
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
	else if (on && !p.visible) show(parts(SAMPLE, settings), true);
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
// here stops the whole script. After an update and a panorama_reload the loaded layout may be the old
// hud_default.kv3, so settings it has no value for are left out until the next map load (as in JHUD).
// values: the loaded layout's dynamicStyles for this panel, or null (unknown: nothing left out).
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
	if (switchedOn()) show(parts(SAMPLE, settings), true);
	fixBoxes();
});
$.RegisterForUnhandledEvent('HudCustomizer_Closed', () => {
	if (!live()) return;
	editing = false;
	hide();
});
$.RegisterForUnhandledEvent('OnObservedTimerStateChange', () => {
	if (live()) guard('timer', onTimerState);
});
$.RegisterForUnhandledEvent('LevelInitPostEntity', () => {
	if (live()) guard('level', onLevelInit);
});
// a new observed target or timer must never be glued onto the run that was going
const dropRun = () => {
	if (!live()) return;
	attempt = null;
	lastState = MomentumTimerAPI.GetObservedTimerStatus().state;
	lastKey = '';
};
$.RegisterForUnhandledEvent('ObserverTargetChanged', dropRun);
$.RegisterForUnhandledEvent('OnObservedTimerReplaced', dropRun);
$.RegisterForUnhandledEvent('MomentumSpectateStart', () => (spectating = true));
$.RegisterForUnhandledEvent('MomentumSpectateStop', () => (spectating = false));
$.Schedule(0, loop);
// HudCustomizer_Ready comes only at a map load; after panorama_reload in a map, register now, so the
// customizer hands this copy the saved settings
if (GLOBAL['HudCustomizerHandler']?.customizerReady) register();
