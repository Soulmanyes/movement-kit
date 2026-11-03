// Strafe Review recorder. Loaded next to timer.ts (see layout/hud/timer.xml).
// Records one row per physics tick, keeps the last 2 s before the timer starts, and dumps
// each attempt to yaw.log as [panorama] SRREC lines when it ends. Reads only and sends no inputs, except
// on a replay paused at its end: it steps the paused replay through the ticks it missed (see "Replay rescan").
//
// Wire format (format 1), all lines start with "SRREC <id> ":
//   <id> <i>/<n> <text>        chunk i of n; joined in order they form one JSON object
//   <id> end n=<n> chars=<c>   the last line of an attempt
// The JSON object holds head fields, "cols" (names of the comma-separated row fields),
// "rows" (rows joined by ';'), "events" and the end fields. FORMAT.md is the reference; keep it in step.

const TAG = 'SRREC';
const FORMAT = 1;

// TimerState from common/timer.ts (copied so this file has no imports)
const TIMER_PRIMED = 1;
const TIMER_RUNNING = 2;
const TIMER_FINISHED = 3;
const REPLAY_NONE = 0;
const REPLAY_PAUSED = 2;
const MOVETYPE_OBSERVER = 10; // MomentumMovementAPI.MoveType.OBSERVER

const PRESTART_SECONDS = 2;
// Rows kept after a non-finish end. mom_restart_stage ends the timer as DISABLED, the same
// state as practice mode, so the reason is judged from what happens in these rows.
const TAIL_SECONDS = 0.5;
const TAIL_WALL_MS = 2000; // give up waiting for tail ticks (game paused, menu)
// A reset teleports: horizontal speed falls to about 0 on the first tick after the end
// (361 to 0 in the 2026-10-27 test). Bhopping back into the start zone also primes the
// timer, but speed only bleeds off over several ticks (42, 39, 21, 3, 0).
const TELEPORT_SPEED = 5;
const TELEPORT_FROM = 30; // only judge a teleport when the run was moving at least this fast
const CHUNK_CHARS = 900; // $.Msg cuts at 2047 chars (probe v1); stay well under
const CHUNKS_PER_FRAME = 200; // long runs are spread over frames so a dump never hitches

const COLS = [
	'tick', // floor(game time / interval), raised to last + 1 when a new tick shows up inside the same number
	'gain', // GetLastTickStats().speedGain
	'ideal', // idealGain
	'ratio', // yawRatio
	'right', // strafeRight
	'vx',
	'vy',
	'vz',
	'yaw', // view angles, 3 decimals since yaw speed is a difference
	'pitch',
	'buttons', // physicalButtons (local player's keys, also while spectating)
	'move', // moveStatus: 0 air, 1 walk, 2 water, 3 waterjump
	'duck',
	'rtick', // replay curtick while a replay plays, else -1
	'wx', // GetMoveHudData().wishVel x/y: the game's own wish velocity, to check the viewer's CS:S gain
	'wy',
	'seek' // 1: read by the replay rescan after playback (a tick missed while playing), else 0
];

interface Attempt {
	id: string;
	head: Record<string, unknown>;
	rows: string[];
	events: unknown[];
	preRows: number;
	gaps: number;
	runTime: number; // last runTime seen while running; reset and stop read 0 after the state change
	tail: Tail | null; // set once the timer stopped running; the attempt is dumped when it is over
}

interface Tail {
	state: number; // timer state the run ended in
	endRows: number; // rows up to and including the end tick
	endTick: number;
	endSpeed: number;
	untilTick: number;
	untilMs: number;
}

let interval = MomentumMovementAPI.GetTickInterval();
let ringSize = Math.ceil(PRESTART_SECONDS / interval);
let ring: string[] = [];
let attempt: Attempt | null = null;
let lastTick = -1;
let lastKey = '';
let lastState = MomentumTimerAPI.GetObservedTimerStatus().state;
const queue: string[] = [];
const reported = new Set<string>();
let spectating = false; // MomentumSpectateStart/Stop; GetMoveType() covers a panorama_reload mid-spectate

function msg(text: string) {
	$.Msg(`${TAG} ${text}`);
}

function r(value: number, digits: number) {
	return Number.isFinite(value) ? value.toFixed(digits) : 'nan';
}

// Mouse settings for turning degrees into mouse distance in the viewer. Read per attempt, so a
// sens change shows up between attempts. dpi is what Momentum's mouse settings page stored, or null.
function mouse() {
	const dpi = Number.parseFloat($.persistentStorage.getItem<string>('settings.mouseDPI') ?? '');
	return {
		sensitivity: GameInterfaceAPI.GetSettingFloat('sensitivity'),
		m_yaw: GameInterfaceAPI.GetSettingFloat('m_yaw'),
		cl_yawspeed: GameInterfaceAPI.GetSettingFloat('cl_yawspeed'),
		dpi: Number.isFinite(dpi) && dpi > 0 ? dpi : null
	};
}

// mouse(), or null if the HUD can't read the settings; the attempt is recorded either way
function mouseOrNull() {
	let out = null;
	guard('mouse', () => (out = mouse()));
	return out;
}

// Runs fn and logs its first exception only, so a throw every frame can't flood yaw.log
function guard(where: string, fn: () => void) {
	try {
		fn();
	} catch (e) {
		if (reported.has(where)) return;
		reported.add(where);
		msg(`err ${where} ${e}`);
	}
}

// New map: the tickrate may differ (surf 66, bhop 100). An attempt still open is cut here.
function onLevelInit() {
	endAttempt('level');
	lastState = MomentumTimerAPI.GetObservedTimerStatus().state;
	interval = MomentumMovementAPI.GetTickInterval();
	ringSize = Math.ceil(PRESTART_SECONDS / interval);
	ring = [];
	lastTick = -1;
}

function sample() {
	const stats = MomentumMovementAPI.GetLastTickStats();
	const vel = MomentumPlayerAPI.GetVelocity();
	// View angles change every frame, so they are not part of the new-tick key
	const key = `${stats.speedGain},${stats.idealGain},${stats.yawRatio},${stats.strafeRight},${vel.x},${vel.y},${vel.z}`;
	const floorTick = Math.floor(MomentumMovementAPI.GetCurrentTime() / interval);
	// Game time went back (map change, reload): start counting again
	if (floorTick < lastTick - 1) lastTick = -1;

	let tick: number;
	if (key !== lastKey) {
		tick = Math.max(floorTick, lastTick + 1);
	} else if (floorTick > lastTick && vel.x === 0 && vel.y === 0 && vel.z === 0) {
		tick = floorTick; // standing still: nothing changes, so time is the only tick signal
	} else {
		return;
	}
	lastKey = key;
	if (attempt && lastTick >= 0 && tick > lastTick + 1) attempt.gaps += tick - lastTick - 1;
	lastTick = tick;

	const replaying = MomentumReplayAPI.GetReplayState() !== REPLAY_NONE;
	const row = rowNow(tick, replaying ? MomentumReplayAPI.GetReplayProgress().curtick : -1, 0);

	ring.push(row);
	if (ring.length > ringSize) ring.shift();
	if (attempt) {
		attempt.rows.push(row);
		const status = MomentumTimerAPI.GetObservedTimerStatus();
		if (status.state === TIMER_RUNNING) attempt.runTime = status.runTime;
		if (attempt.tail && tick >= attempt.tail.untilTick) finishTail();
	}
}

// One row (COLS) of what the APIs read now
function rowNow(tick: number, rtick: number, seek: number) {
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
		rtick,
		r(move.wishVel.x, 2),
		r(move.wishVel.y, 2),
		seek
	].join(',');
}

function hspeed() {
	const vel = MomentumPlayerAPI.GetVelocity();
	return Math.hypot(vel.x, vel.y);
}

// The run stopped without finishing: keep recording a short tail, then judge the reason
function startTail(state: number) {
	if (!attempt) return;
	attempt.tail = {
		state,
		endRows: attempt.rows.length,
		endTick: lastTick,
		endSpeed: hspeed(),
		untilTick: lastTick + Math.ceil(TAIL_SECONDS / interval),
		untilMs: Date.now() + TAIL_WALL_MS
	};
}

function finishTail() {
	const tail = attempt?.tail;
	if (!attempt || !tail) return;
	const timers = attempt.events.filter(
		(e) => (e as { kind: string }).kind === 'timer'
	) as { state: number }[];
	// IsInPracticeMode() read false half a second after practice mode stopped a run
	// (play test 2026-10-27), so the event decides
	const practice = attempt.events.some((e) => (e as { kind: string; on?: boolean }).kind === 'practice' && (e as { on: boolean }).on);
	// Loading a savestate stops the timer as DISABLED; its event comes on the same tick, just
	// before the timer's. Creating one mid-run fires the same event, but earlier.
	const savestate = attempt.events.some(
		(e) => (e as { kind: string; tick: number }).kind === 'savestate' && (e as { tick: number }).tick >= tail.endTick - 1
	);
	const primed = tail.state === TIMER_PRIMED || timers.some((e) => e.state === TIMER_PRIMED);
	const speeds = attempt.rows.slice(tail.endRows).map((row) => {
		const f = row.split(',');
		return Math.hypot(Number(f[5]), Number(f[6]));
	});
	const teleported = tail.endSpeed >= TELEPORT_FROM && speeds.length > 0 && speeds[0] < TELEPORT_SPEED;
	let reason = 'stop';
	if (practice || MomentumPlayerAPI.IsInPracticeMode()) reason = 'practice';
	else if (savestate) reason = 'savestate';
	else if (teleported) reason = 'reset';
	else if (primed) reason = 'zone'; // back in the start zone without a teleport
	endAttempt(reason);
}

function startAttempt() {
	const status = MomentumTimerAPI.GetObservedTimerStatus();
	const meta = MomentumTimerAPI.GetObservedRunMetadata();
	const replaying = MomentumReplayAPI.GetReplayState() !== REPLAY_NONE;
	// Spectating a live player: the player API follows the target, tick stats read 0 like on replays
	const spec = !replaying && !meta && (spectating || MomentumMovementAPI.GetMoveType() === MOVETYPE_OBSERVER);
	const now = Date.now();
	const id = `${now.toString(36)}${Math.floor(Math.random() * 1296)
		.toString(36)
		.padStart(2, '0')}`;
	attempt = {
		id,
		head: {
			format: FORMAT,
			id,
			started: now,
			map: MapCacheAPI.GetMapName(),
			interval,
			style: status.style,
			track: status.trackId,
			label: replaying || meta ? 'replay' : spec ? 'spectate' : 'own',
			player: meta ? meta.playerName : spec ? specName() : null,
			replayFile: meta ? meta.filePath : null,
			practice: MomentumPlayerAPI.IsInPracticeMode(),
			version: MomentumAPI.GetVersionInfo(),
			mouse: mouseOrNull()
		},
		rows: ring.slice(),
		events: [],
		preRows: ring.length,
		gaps: 0,
		runTime: 0,
		tail: null
	};
}

// Name of the spectated player, from the built-in spectate HUD panel (#Spectator in hud.xml)
function specName(): string | null {
	let root = $.GetContextPanel();
	while (root.GetParent()) root = root.GetParent()!;
	const p = root.FindChildTraverse<MomHudSpectate>('Spectator');
	return p && p.name ? p.name : null;
}

// runTime: the run time to save; by default the timer's (finish) or the last one seen while running
function endAttempt(reason: string, runTime?: number) {
	if (!attempt) return;
	const status = MomentumTimerAPI.GetObservedTimerStatus();
	const data = JSON.stringify({
		...attempt.head,
		cols: COLS,
		preRows: attempt.preRows,
		postRows: attempt.tail ? attempt.rows.length - attempt.tail.endRows : 0,
		rows: attempt.rows.join(';'),
		events: attempt.events,
		reason,
		runTime: runTime ?? (attempt.tail ? attempt.runTime : status.state === TIMER_FINISHED ? status.runTime : attempt.runTime),
		gaps: attempt.gaps,
		ended: Date.now()
	});
	const count = Math.ceil(data.length / CHUNK_CHARS);
	for (let i = 0; i < count; i++) {
		queue.push(`${attempt.id} ${i + 1}/${count} ${data.slice(i * CHUNK_CHARS, (i + 1) * CHUNK_CHARS)}`);
	}
	queue.push(`${attempt.id} end n=${count} chars=${data.length}`);
	attempt = null;
}

function flush() {
	for (let i = 0; i < CHUNKS_PER_FRAME && queue.length > 0; i++) msg(queue.shift()!);
}

function event(kind: string, fields: Record<string, unknown>) {
	if (rescanBusy()) return;
	attempt?.events.push({ tick: lastTick, kind, ...fields });
}

function onTimerState() {
	if (rescanBusy()) return; // its seeks move the observed timer
	const status = MomentumTimerAPI.GetObservedTimerStatus();
	if (status.state === TIMER_RUNNING && lastState !== TIMER_RUNNING) {
		if (attempt?.tail) finishTail(); // started again inside the tail
		endAttempt('restart'); // only if one was still open, e.g. a missed state change
		startAttempt();
	} else if (lastState === TIMER_RUNNING && status.state !== TIMER_RUNNING) {
		event('timer', { state: status.state, runTime: status.runTime });
		if (status.state === TIMER_FINISHED) endAttempt('finish');
		else startTail(status.state);
	} else if (attempt?.tail) {
		event('timer', { state: status.state, runTime: status.runTime });
	}
	lastState = status.state;
}

function onJump() {
	if (rescanBusy()) return;
	const s = MomentumMovementAPI.GetLastJumpStats();
	event('jump', {
		n: s.jumpCount,
		takeoff: s.takeoffSpeed,
		delta: s.jumpSpeedDelta,
		takeoffTime: s.takeoffTime,
		sync: s.strafeSync,
		strafes: s.strafeCount,
		gain: s.speedGain,
		ratio: s.yawRatio,
		height: s.heightDelta,
		distance: s.distance,
		eff: s.efficiency
	});
}

// A new observed target or timer must never be glued onto the attempt that was running
function onTargetChange(why: string) {
	if (rescanBusy()) return; // every rescan seek fires OnObservedTimerReplaced
	endAttempt(why);
	lastState = MomentumTimerAPI.GetObservedTimerStatus().state;
	lastKey = '';
}

// ---------------------------------------------------------------------------------------------
// A short note at the top middle of the screen (the replay rescan's "replay saved"), on screen for
// NOTE_SECONDS. The jump-1 line that used to share this spot is First Jump HUD now (first-jump/ in the kit).

const NOTE_SECONDS = 4;
const SHADOW = 'text-shadow: 0px 1px 4px 2px rgba(0, 0, 0, 0.9);';
let notePanel: Panel | null = null;
let noteToken = 0;

function showNote(head: string, sub: string) {
	if (!notePanel || !notePanel.IsValid()) {
		const ctx = $.GetContextPanel();
		const root = ctx.GetParent() ?? ctx;
		root.FindChildTraverse('StrafeReviewLine')?.DeleteAsync(0);
		// Top middle of the screen (Panorama px are 1080p units)
		notePanel = $.CreatePanel('Panel', root, 'StrafeReviewLine', {
			style: 'horizontal-align: center; vertical-align: top; margin-top: 20px; flow-children: down;'
		});
	}
	const panel = notePanel;
	panel.RemoveAndDeleteChildren();
	for (const [text, size] of [[head, 22], [sub, 19]] as [string, number][])
		if (text)
			$.CreatePanel('Label', panel, '', {
				text,
				style: `horizontal-align: center; font-size: ${size}px; font-weight: bold; color: #ffffff; ${SHADOW}`
			});
	panel.visible = true;
	const token = ++noteToken;
	$.Schedule(NOTE_SECONDS, () => {
		if (token === noteToken && notePanel?.IsValid()) notePanel.visible = false;
	});
}

// ---------------------------------------------------------------------------------------------
// Replay rescan. The recorder reads once per frame, so a frame longer than a tick loses that tick's row
// (5 of 2368 rows on one replay). When a recorded replay is paused at its end, the replay is still
// loaded: the rescan steps it to each missed tick, reads the row, goes back to the end and dumps the
// attempt with the rows put in place ('seek' 1). Seek probe 2026-10-28 (recorder/probe/
// strafe-review-seek-probe.ts, PLAN.md "Replay rescan"): after a seek to curtick c the APIs read what
// playback recorded as rtick c + 1, speed, keys and wishVel exactly. Yaw reads playback's value at
// once after GoTo() or GoToPreviousTick(), but drifts for ~17 frames after GoToNextTick(), so every
// tick is reached from above with GoToPreviousTick(). Each seek fires OnObservedTimerReplaced, so the
// other handlers do nothing while it runs. Unpausing stops it and dumps what it has.

const RESCAN_MAX = 600; // missed rows rescanned per attempt (about 4 frames each)
const RESCAN_SETTLE = 2; // frames after a seek before curtick is checked
const RESCAN_TRIES = 8; // seeks allowed to reach one tick, then it stays missed
const RESCAN_QUIET = 10; // frames after the rescan in which its last seeks' events are still ignored
const COL_TICK = 0;
const COL_RTICK = COLS.indexOf('rtick');

interface Rescan {
	todo: number[]; // rticks to read, highest first
	wanted: number; // todo's length at the start
	offset: number; // tick - rtick while the replay played
	total: number;
	target: number; // curtick to seek to (rtick - 1), -1 between rows, -2 going back to the end
	seen: boolean; // target reached; read on the next frame
	wait: number;
	tries: number;
	rows: string[];
}

let rescan: Rescan | null = null;
let rescanQuiet = 0;
const rescanBusy = () => rescan !== null || rescanQuiet > 0;

// A replay attempt whose replay sits paused at its last tick: rescan its missed rows, then dump it
function replayEnd() {
	const a = attempt;
	if (!a || a.tail || a.head.label !== 'replay' || MomentumReplayAPI.GetReplayState() !== REPLAY_PAUSED) return;
	const p = MomentumReplayAPI.GetReplayProgress();
	if (p.totalticks <= 0 || p.curtick < p.totalticks) return;
	const have = new Set<number>();
	const offsets = new Map<number, number>();
	for (const row of a.rows) {
		const f = row.split(',');
		const rt = Number(f[COL_RTICK]);
		if (rt < 0) continue;
		have.add(rt);
		const off = Number(f[COL_TICK]) - rt;
		offsets.set(off, (offsets.get(off) || 0) + 1);
	}
	// the run time seen while it played: the rescan's seeks move the timer (one read 0.005 s after them)
	if (have.size < 2) {
		endAttempt('finish', a.runTime);
		return rescanNote(0, 0, true);
	}
	let offset = 0;
	let most = 0;
	for (const [off, n] of offsets) if (n > most) [offset, most] = [off, n];
	const lo = Math.min(...have);
	const hi = Math.max(...have);
	const todo: number[] = [];
	for (let rt = hi - 1; rt > lo && todo.length < RESCAN_MAX; rt--) if (!have.has(rt)) todo.push(rt);
	if (!todo.length) {
		endAttempt('finish', a.runTime);
		return rescanNote(0, 0, true);
	}
	rescan = { todo, wanted: todo.length, offset, total: p.totalticks, target: -1, seen: false, wait: 0, tries: 0, rows: [] };
}

function rescanStep() {
	const s = rescan!;
	if (MomentumReplayAPI.GetReplayState() !== REPLAY_PAUSED) return endRescan(false);
	if (s.wait > 0) {
		s.wait--;
		return;
	}
	const cur = MomentumReplayAPI.GetReplayProgress().curtick;
	if (s.target === -2) {
		if (cur >= s.total || s.tries++ >= RESCAN_TRIES) return endRescan(true);
		MomentumReplayAPI.GoToEnd();
		s.wait = RESCAN_SETTLE;
		return;
	}
	if (s.target === -1) {
		const next = s.todo.shift();
		if (next === undefined) {
			s.target = -2;
			s.tries = 0;
			return;
		}
		s.target = next - 1;
		s.seen = false;
		s.tries = 0;
	}
	if (cur === s.target) {
		if (!s.seen) {
			s.seen = true; // values follow curtick within a frame (probe): read on the next one
			return;
		}
		const rt = s.target + 1;
		s.rows.push(rowNow(rt + s.offset, rt, 1));
		s.target = -1;
		return;
	}
	s.seen = false;
	if (s.tries++ >= RESCAN_TRIES) {
		s.target = -1; // couldn't land on it: it stays a missed tick
		return;
	}
	// from above only: a step forward leaves the view angles drifting
	if (cur > s.target && cur - s.target <= 3) MomentumReplayAPI.GoToPreviousTick();
	else MomentumReplayAPI.GoTo(Math.min(s.target + 2, s.total) / s.total);
	s.wait = RESCAN_SETTLE;
}

// Put the rescanned rows in tick order and dump the attempt (at the end, or unpaused midway)
function endRescan(atEnd: boolean) {
	const s = rescan;
	const a = attempt;
	rescan = null;
	rescanQuiet = RESCAN_QUIET;
	lastKey = '';
	if (!s || !a) return;
	const tickOf = (row: string) => Number(row.slice(0, row.indexOf(',')));
	const startTick = a.preRows < a.rows.length ? tickOf(a.rows[a.preRows]) : Infinity;
	a.rows = a.rows.concat(s.rows).sort((x, y) => tickOf(x) - tickOf(y));
	a.preRows = a.rows.findIndex((row) => tickOf(row) >= startTick);
	if (a.preRows < 0) a.preRows = a.rows.length;
	a.gaps = Math.max(0, a.gaps - s.rows.length);
	a.events.push({ tick: lastTick, kind: 'rescan', rows: s.rows.length, wanted: s.wanted, atEnd });
	endAttempt('finish', a.runTime);
	rescanNote(s.rows.length, s.wanted, atEnd);
}

// On screen for NOTE_SECONDS: the replay is saved and how many of its missed ticks the rescan filled
function rescanNote(filled: number, wanted: number, atEnd: boolean) {
	const sub = !wanted
		? 'no missed ticks'
		: filled === wanted
			? `${filled} missed tick${filled === 1 ? '' : 's'} filled`
			: `${filled} of ${wanted} missed ticks filled${atEnd ? '' : ' (unpaused, rescan stopped)'}`;
	showNote('Strafe Review: replay saved', sub);
}

function loop() {
	if (rescanQuiet > 0) rescanQuiet--;
	if (rescan) guard('rescan', rescanStep);
	else {
		guard('sample', sample);
		guard('replay end', replayEnd);
	}
	if (attempt?.tail && Date.now() > attempt.tail.untilMs) guard('tail', finishTail);
	guard('flush', flush);
	$.Schedule(0, loop);
}

$.Schedule(0, loop);
$.RegisterForUnhandledEvent('OnObservedTimerStateChange', () => guard('timer', onTimerState));
$.RegisterForUnhandledEvent('OnMomentumPlayerPracticeModeStateChange', (on) =>
	guard('practice', () => event('practice', { on }))
);
$.RegisterForUnhandledEvent('OnSaveStateUpdate', (count, current, usingMenu) =>
	guard('savestate', () => event('savestate', { count, current, usingMenu }))
);
$.RegisterForUnhandledEvent('OnJumpStarted', () => guard('jump', onJump));
$.RegisterForUnhandledEvent('ObserverTargetChanged', () => guard('target', () => onTargetChange('target')));
$.RegisterForUnhandledEvent('OnObservedTimerReplaced', () => guard('replaced', () => onTargetChange('replaced')));
$.RegisterForUnhandledEvent('MomentumSpectateStart', () => (spectating = true));
$.RegisterForUnhandledEvent('MomentumSpectateStop', () => (spectating = false));
$.RegisterForUnhandledEvent('LevelInitPostEntity', () => guard('level', onLevelInit));

guard('mouse', () => msg(`mouse ${JSON.stringify(mouse())}`));
msg(`load format=${FORMAT} interval=${interval}`);
