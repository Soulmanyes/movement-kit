// Surf Sound, part of Soulmanyes's Movement Kit (surf-sound/ in the repo). Loaded next to timer.ts through
// the kit's timer.xml patch (movekit/panorama.py). It draws nothing: it only tells the sound runner
// beside the game (sound_run.py) when to play.
//
// Momentum has no "surfing" flag: the engine counts a ramp as air (moveStatus AIR), as Source does. So
// contact with a surface is read from the z speed. In free fall it changes by exactly one free fall step
// per tick (-sv_gravity * tick interval: -12 at 800 and 66.67 tick, Z Penalty's probe 2026-11-09). A
// surface that pushes back (a ramp under you, a slide down a slope) makes the z speed fall slower or rise:
// "ramp". A sloped ceiling pressing down (a headsurf) makes it fall faster: "ceiling". The sign comes from
// the z change minus the free fall steps the elapsed game time accounts for.
//
// A new tick is told by the velocity changing, not by the game time (see Z Penalty's script): the time
// moves per frame, the velocity per tick. A frame slower than a tick shows several steps at once, so
// free fall is any whole number of steps.
//
// The sound turns on after ON_SAMPLES contact samples in a row (1: a brief headsurf is heard; a head hit
// plays its own sound instead, see Hits) and off after OFF_SAMPLES free fall samples, so a ride with a free fall tick in it
// doesn't stutter. A jump and a landing tell nothing: the ground's sample has no history. It is
// off at once on the ground, in water, below MIN_SPEED, on a teleport, when the velocity
// stops changing for STALL_MS (stuck, paused), in noclip, in a paused replay and while the HUD customizer
// is open.
//
// The ground: the engine sets the z speed to exactly 0 on every tick on the ground, and an airborne z
// speed is never exactly 0 two ticks running. GetMoveHudData().moveStatus can't tell: only the defrag
// movement fills it, and in surf it read AIR while walking (in game 2026-11-24: walking played RAMP).
// It is still checked, for the modes that fill it.
//
// Hits (owner, 2026-11-24): one-shot sounds on top of the constant one.
// - A wall: the horizontal speed drops by WALL_MIN or more in one sample while the z change stays exact
//   free fall (a vertical wall's normal has no z; a ramp or ceiling contact changes z, so it isn't a wall).
//   An axis-aligned wall zeroes a velocity component exactly, so a drop to 0 counts too. A wrong-way air
//   strafe loses at most sv_airaccelerate * 30 * tick per tick (67.5 at surf's 150), under WALL_MIN. In
//   21 recorded runs on surf_phantasia (2026-11-24) this found 6 hits, each flying into a wall. The
//   strength is the speed lost (WALL_LEVELS).
// - A glancing wall loses less than WALL_MIN, so it is told from a strafe by shape: a wall removes the
//   velocity's part along its normal, so the change is at a right angle to the new velocity (|cos| at
//   most GLANCE_COS). An air strafe that slows you pushes against your speed (recorded: cos -0.2 to
//   -0.38, or -1); one at a right angle only adds speed. Recorded glances (surf_tequila, owner
//   2026-11-24): losses 43-100 with changes of 410-610 at cos +0.02 to +0.05. GLANCE_MIN or more lost.
// - A spine: riding a ramp (its sound on), then landing on the flat top of a spine, a ramp's edge or
//   the floor at SLAM_MIN or more falling: z speed exactly 0 (ground) while you keep at least half your
//   horizontal speed (a teleport zeroes it). Recorded 3 times on surf_tequila (owner, 2026-11-24):
//   -1183, -1163, -1156 to 0, horizontal 1122 -> 1128, then 1-4 ticks of ground friction. Plays a wall
//   hit with the fall speed lost as its strength. Sliding gently off a slope onto the floor stays quiet.
// - Sliding along a curved wall while falling loses a little more speed each tick, at a right angle to
//   the velocity, until it passes WALL_MIN (a leaderboard replay on surf_tequila, 2026-11-24: losses
//   1, 5, 14, 27, 46, 73, 99, 125 per tick at cos +0.01 to +0.02, the velocity turning 5-15 degrees a
//   tick; and one ride ending on a flat wall, 1515 -> 1374, three false bonks). So right after a sample
//   that already lost SLIDE_MIN or more at a right angle, after one before it that lost at a right angle
//   too (t.sliding), a wall hit needs SLIDE_HIT lost. One such sample alone is no slide: glancing off a
//   pillar while spectating (surf_fiellu, 2026-11-24, 3-tick updates) lost 34 then 46, a hit split over
//   two updates.
//   Real slams out of such a slide lose far more: 427 to 2319 in 25 recorded on surf_tequila.
// - A head hit: rising, then at least half the upward speed gone, CEIL_MIN or more of it beyond free fall.
//   Rising at BONK_HARD or more (raised from 200 by the owner, 2026-11-24) is a hard hit ("bonk": hitting the ceiling on purpose to drop faster;
//   recorded 560 -> 60, 375 -> 97). Slower is a light one ("graze": clipping a ceiling near the top of a
//   jump, a miss), which plays the wall's sound (owner, 2026-11-24), but only when the ceiling stops you
//   (z speed GRAZE_VZ or more after): a sloped ceiling throwing you down near the top of a jump (recorded
//   0.67 -> -190, 117 -> -91, 18 -> -60: about 20 u/s of speed lost, the ceiling still pressing the next
//   ticks) is a headsurf starting, and plays the ceiling sound instead. One that costs WALL_MIN or more
//   of your whole speed is a head hit after all (owner, 2026-11-24). Thrown down to THROW_VZ or faster,
//   it is hitting a sloped ceiling nearly head-on to drop, the same trick as a hard hit, and plays the
//   bonk at any rising speed (owner's PB on surf_tequila: 324 -> -863, horizontal 2112 -> 1319, silent
//   before; recorded 35 -> -375, 243 -> -340, 239 -> -865 likewise). Slower is a miss, the graze: on
//   surf_imaginarium bonus 1 a bhop inside a donut that lands wrong hits the top curve instead of the
//   bottom one (122 -> -32, horizontal 893 -> 644; 7 failed runs, -31 to -148).
//   Exactly 0 counts only from above NON_JUMP_VZ, as the engine can't put a player that fast on the
//   ground. A ceiling often clips a second tick too; that one doesn't start the ceiling sound, the
//   contact after it does (a sloped ceiling you keep riding).
// Walls and ceilings each wait HIT_GAP_MS after their last hit (scraping a wall clips the speed for a few
// ticks).
//
// Markers (written with $.Msg; the autoexec block logs the console to yaw.log and hides MK_ lines from the
// console): MK_SURFSND_RAMP, MK_SURFSND_CEIL, MK_SURFSND_OFF. Each is written on a change, and the one
// sounding again every BEAT_MS, so the runner can stop a sound whose script died (it waits a few beats).
// Hits: MK_SURFSND_WALL1, _WALL2, _WALL3 (by strength), MK_SURFSND_GRAZE and MK_SURFSND_BONK, once each,
// never beaten. While watching, every marker but OFF ends in W (MK_SURFSND_RAMPW, MK_SURFSND_BONKW...),
// so the runner can mute them with its "also when watching" switch, which this script can't read.
//
// Watching (owner, 2026-11-24): replays and spectating play too. GetVelocity() reads the watched
// player; the local player is an observer, and moveStatus reads AIR (0) for every watched tick (132
// recorded replay and spectate runs), so the ground is the z speed of exactly 0 alone.
// - A replay changes the velocity once per replay tick, in exact free fall steps, as own play (55
//   recorded). Its time is its curtick, so a slow or fast replay counts its own ticks. A paused replay
//   plays nothing: Strafe Review's rescan seeks one, tick by tick.
// - Spectating updates the velocity every 3 (66 tick) or 5 (100 tick) of the spectated player's ticks,
//   always whole free fall steps (77 recorded), while the local game time doesn't follow them. So a
//   sample's ticks are its free fall steps, kept from the last free fall update for contact updates
//   (watchTicks), and its time is the wall clock. Ramps, ceilings and hits come in steps of 45-50 ms.
// - A switch between own play, a replay and spectating starts the tracker again.
//
// No imports, like the Strafe Review recorder. The plain functions (above "Panorama") are run in node by
// check_surf_sound.js.

const FALL_EPS = 0.05; // u/s off a whole number of free fall steps that still counts as free fall
const MAX_DZ = 300; // a bigger z change between two samples is a jump, a teleport or a push: it tells nothing
const MIN_SPEED = 150; // u/s; slower is a crawl or being stuck on a ramp, not surfing
const ON_SAMPLES = 1; // owner, 2026-11-24: 2 missed brief headsurfs
const OFF_SAMPLES = 3;
const STALL_MS = 250;
const BEAT_MS = 500;
const WALL_MIN = 100; // u/s of horizontal speed lost in one sample
const WALL_LEVELS = [300, 800]; // lost at least this much: strength 2, 3
const GLANCE_MIN = 40; // u/s of horizontal speed lost by a glancing wall hit

const GLANCE_COS = 0.15; // at most this |cos| between that change and the new velocity
const SLIDE_MIN = 2; // u/s lost at a right angle in one sample: already sliding along a wall
const TOUCH_MIN = 0.5; // u/s lost at a right angle in one sample: touching a wall (a slide needs two)
const SLIDE_HIT = 300; // u/s lost: the least wall hit while sliding
const SLAM_MIN = 300; // u/s falling onto a flat top from a ramp ride: a spine hit
const CEIL_MIN = 5; // u/s of upward speed a ceiling takes beyond free fall for a head hit
const BONK_HARD = 400; // u/s rising into the ceiling: a hard head hit (slower: a light one)
const THROW_VZ = -300; // u/s: a head hit that costs speed and throws you down this fast or faster is on purpose
const GRAZE_VZ = -30; // u/s: a light head hit leaves the z speed at least this (a flat ceiling: about -6)
const NON_JUMP_VZ = 150; // above this the engine never puts you on the ground (Source: 140)
const HIT_GAP_MS = 250;
const GAP_S = 0.2; // seconds between two samples after which the last one is no history (a replay seek, a hitch)
const MOVESTATUS_AIR = 0; // MomentumMovementAPI.PlayerMoveStatus.AIR
const MOVETYPE_WALK = 2; // MomentumMovementAPI.MoveType.WALK (normal movement; not noclip, ladder or observer)
const MOVETYPE_OBSERVER = 10;
const REPLAY_NONE = 0;
const REPLAY_PAUSED = 2; // as Strafe Review's recorder; its rescan seeks a paused replay tick by tick

type Kind = 'ramp' | 'ceiling' | null;
type Hit = 'wall1' | 'wall2' | 'wall3' | 'graze' | 'bonk' | null;
// spectate: the velocity comes from a spectated player, in updates of several of their ticks (see Watching)
type Sample = { play: boolean; fast: boolean; vx: number; vy: number; vz: number; time: number; spectate?: boolean };
type Tracker = {
	has: boolean; // lastVx, lastVy, lastVz and lastTime are a sample
	lastVx: number;
	lastVy: number;
	lastVz: number;
	lastTime: number;
	hit: Hit; // the last sample's hit
	hitAt: Record<string, number>; // game time of the last wall and ceiling hit
	touched: boolean; // the last sample lost TOUCH_MIN or more at a right angle
	sliding: boolean; // that, SLIDE_MIN or more, after a sample that touched too (along a wall)
	hold: number; // contact samples after a head hit that don't start the sound yet
	run: number; // contact samples in a row (of kind runKind), or free fall samples in a row when negative
	runKind: Kind;
	sounding: Kind;
	watchTicks: number; // spectating: the spectated player's ticks per update, from the last free fall one
};

function newTracker(): Tracker {
	return { has: false, lastVx: 0, lastVy: 0, lastVz: 0, lastTime: 0, hit: null, hitAt: {}, touched: false, sliding: false, hold: 0, run: 0, runKind: null, sounding: null, watchTicks: 0 };
}

// How many free fall steps a z change is: a whole number of at least 1, or 0 when it isn't free fall
function fallSteps(dz: number, step: number): number {
	if (!(step < 0)) return 0;
	const k = Math.round(dz / step);
	return k >= 1 && Math.abs(dz - k * step) <= FALL_EPS * k ? k : 0;
}

// What one sample says: 'ramp', 'ceiling', 'fall' (free fall) or null (tells nothing). dz: the z change
// since the last sample, dt: the game time since then, step: the free fall change per tick (negative),
// tick: the tick interval in seconds.
function classify(dz: number, dt: number, step: number, tick: number): Kind | 'fall' {
	if (Math.abs(dz) > MAX_DZ) return null;
	if (fallSteps(dz, step) > 0) return 'fall';
	const ticks = Math.max(1, Math.round(dt / tick));
	return dz - ticks * step > 0 ? 'ramp' : 'ceiling';
}

// The ticks a sample covers since the tracker's last one. Own play and replays: from the time (a
// replay's is its curtick). Spectating: the update's free fall steps, kept for the contact updates
// between them (see Watching).
function sampleTicks(t: Tracker, s: Sample, dz: number, step: number, tick: number): number {
	const byTime = Math.max(1, Math.round((s.time - t.lastTime) / tick));
	if (!s.spectate) return byTime;
	const k = Math.abs(dz) <= MAX_DZ ? fallSteps(dz, step) : 0;
	if (k > 0) t.watchTicks = k;
	return t.watchTicks || byTime;
}

// The hit one sample makes after the tracker's last one (which was airborne), or null.
/** The velocity's change since the tracker's last sample is at a right angle to the new velocity
 * (|cos| at most GLANCE_COS), as a wall makes it. */
function square(t: Tracker, s: Sample): boolean {
	const dx = s.vx - t.lastVx;
	const dy = s.vy - t.lastVy;
	return Math.abs(dx * s.vx + dy * s.vy) <= GLANCE_COS * Math.hypot(dx, dy) * Math.hypot(s.vx, s.vy);
}

/** A glancing wall: GLANCE_MIN lost, the change at a right angle to the new velocity. */
function glancing(t: Tracker, s: Sample, lost: number): boolean {
	return lost >= GLANCE_MIN && square(t, s);
}

function hitOf(t: Tracker, s: Sample, step: number, tick: number): Hit {
	const dz = s.vz - t.lastVz;
	const ticks = sampleTicks(t, s, dz, step, tick);
	const taken = ticks * step - dz; // upward speed taken beyond free fall
	// a reset to the start or a teleport zeroes the whole velocity; any hit keeps some (spectating
	// surf_fiellu, 2026-11-24: a reset while rising at 582 played a head hit)
	if (s.vx === 0 && s.vy === 0 && s.vz === 0) return null;
	if (t.lastVz > 0 && s.vz <= t.lastVz / 2 && taken >= CEIL_MIN && (s.vz !== 0 || t.lastVz > NON_JUMP_VZ)) {
		if (t.lastVz >= BONK_HARD) return 'bonk';
		if (s.vz >= GRAZE_VZ) return 'graze';
		const lost3 = Math.hypot(t.lastVx, t.lastVy, t.lastVz) - Math.hypot(s.vx, s.vy, s.vz);
		if (lost3 < WALL_MIN) return null;
		return s.vz <= THROW_VZ ? 'bonk' : 'graze';
	}
	const lost = Math.hypot(t.lastVx, t.lastVy) - Math.hypot(s.vx, s.vy);
	if (s.vz === 0 && t.sounding === 'ramp' && -t.lastVz >= SLAM_MIN && lost <= Math.hypot(t.lastVx, t.lastVy) / 2)
		return -t.lastVz >= WALL_LEVELS[1] ? 'wall3' : 'wall2';
	if ((lost >= WALL_MIN || glancing(t, s, lost)) && (lost >= SLIDE_HIT || !t.sliding) && s.vz !== 0 && fallSteps(dz, step) === ticks)
		return wallHit(lost);
	return null;
}

function wallHit(lost: number): Hit {
	return lost >= WALL_LEVELS[1] ? 'wall3' : lost >= WALL_LEVELS[0] ? 'wall2' : 'wall1';
}

// One new sample into the tracker. s.play: own play under normal movement, airborne as far as the game
// tells (moveStatus); s.fast: at MIN_SPEED or more. Off the ground, fast and in play is "air"; otherwise the
// sound stops at once and the history is dropped. Returns the kind sounding after it; t.hit is the
// sample's hit.
function track(t: Tracker, s: Sample, step: number, tick: number): Kind {
	const had = t.has && s.time - t.lastTime <= GAP_S;
	let hit = had && s.play ? hitOf(t, s, step, tick) : null;
	const gapKey = hit === 'bonk' || hit === 'graze' ? 'ceiling' : 'wall';
	if (hit && s.time - (t.hitAt[gapKey] ?? -Infinity) < HIT_GAP_MS / 1000) {
		t.hitAt[gapKey] = s.time;
		hit = null;
	} else if (hit) {
		t.hitAt[gapKey] = s.time;
	}
	t.hit = hit;
	const ceiling = hit === 'bonk' || hit === 'graze'; // a second clip in the gap is a plain contact
	const grounded = s.vz === 0 && !ceiling; // see the top
	const air = s.play && s.fast && !grounded;
	const vz = s.vz;
	const dz = vz - t.lastVz;
	const dt = had ? sampleTicks(t, s, dz, step, tick) * tick : 0;
	t.has = air;
	const lostH = had ? Math.hypot(t.lastVx, t.lastVy) - Math.hypot(s.vx, s.vy) : 0;
	const touching = lostH >= TOUCH_MIN && square(t, s);
	t.sliding = touching && t.touched && lostH >= SLIDE_MIN;
	t.touched = touching;
	t.lastVx = s.vx;
	t.lastVy = s.vy;
	t.lastVz = vz;
	t.lastTime = s.time;
	if (ceiling) {
		// a contact, but the ceiling sound waits (see the top)
		t.run = 0;
		t.runKind = null;
		t.hold = 1;
		return t.sounding;
	}
	if (!air || !had) {
		t.run = 0;
		t.runKind = null;
		t.hold = 0;
		t.sounding = null;
		return null;
	}
	const kind = classify(dz, dt, step, tick);
	if (kind === null) {
		t.run = 0;
		t.runKind = null;
		t.hold = 0;
		t.sounding = null;
	} else if (kind === 'fall') {
		t.run = Math.min(0, t.run) - 1;
		t.runKind = null;
		t.hold = 0;
		if (-t.run >= OFF_SAMPLES) t.sounding = null;
	} else {
		t.run = kind === t.runKind && t.run > 0 ? t.run + 1 : 1;
		t.runKind = kind;
		if (t.hold > 0) t.hold--;
		else if (t.run >= ON_SAMPLES) t.sounding = kind;
	}
	return t.sounding;
}

const MARKERS: Record<string, string> = {
	ramp: 'MK_SURFSND_RAMP', ceiling: 'MK_SURFSND_CEIL', off: 'MK_SURFSND_OFF', rampW: 'MK_SURFSND_RAMPW',
	ceilingW: 'MK_SURFSND_CEILW'
};
const HIT_MARKERS: Record<string, string> = {
	wall1: 'MK_SURFSND_WALL1', wall2: 'MK_SURFSND_WALL2', wall3: 'MK_SURFSND_WALL3', graze: 'MK_SURFSND_GRAZE',
	bonk: 'MK_SURFSND_BONK'
};

// ---- Panorama ----

// panorama_reload loads this file again, but the old copy's handlers and loop stay alive (seen with JHUD
// 2026-11-03). Each load takes a new number in Panorama's global object; a copy whose number isn't the
// latest stops.
const GLOBAL = UiToolkitAPI.GetGlobalObject() as Record<string, any>;
const GEN = (GLOBAL['MovekitSurfSoundGen'] = (GLOBAL['MovekitSurfSoundGen'] || 0) + 1);
const live = () => GLOBAL['MovekitSurfSoundGen'] === GEN;

let editing = false;
let watchMode = ''; // 'own', 'replay' or 'spectate': the last sample's
let spectating = false; // MomentumSpectateStart/Stop; GetMoveType() covers a panorama_reload mid-spectate
let tracker = newTracker();
let lastKey = '';
let lastChange = 0; // Date.now() of the last new velocity
let sent = 'none'; // so the first send('off'), at load, writes MK_SURFSND_OFF
let sentAt = 0;

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

// The runner's marker: on a change, and the sounding one again every BEAT_MS
function send(state: string) {
	const now = Date.now();
	if (state === sent && (state === 'off' || now - sentAt < BEAT_MS)) return;
	sent = state;
	sentAt = now;
	$.Msg(MARKERS[state]);
}

// What the velocity is: own play, a replay or a spectated player's
function watching(replay: number): string {
	if (replay !== REPLAY_NONE) return 'replay';
	if (MomentumTimerAPI.GetObservedRunMetadata() || spectating) return 'spectate';
	return MomentumMovementAPI.GetMoveType() === MOVETYPE_OBSERVER ? 'spectate' : 'own';
}

function airborne(): boolean {
	if (MomentumMovementAPI.GetMoveType() !== MOVETYPE_WALK) return false;
	try {
		return MomentumMovementAPI.GetMoveHudData().moveStatus === MOVESTATUS_AIR;
	} catch {
		return false;
	}
}

function sample() {
	const vel = MomentumPlayerAPI.GetVelocity();
	const replay = MomentumReplayAPI.GetReplayState();
	const mode = watching(replay);
	const tick = MomentumMovementAPI.GetTickInterval();
	const time =
		mode === 'replay' ? MomentumReplayAPI.GetReplayProgress().curtick * tick
		: mode === 'spectate' ? Date.now() / 1000
		: MomentumMovementAPI.GetCurrentTime();
	if (mode !== watchMode) {
		watchMode = mode;
		tracker = newTracker();
		send('off');
	}
	if (time < tracker.lastTime) tracker = newTracker(); // time went back (map change, reload, replay seek)
	const key = `${vel.x},${vel.y},${vel.z}`; // a new tick changes the velocity (see the top)
	const now = Date.now();
	if (key === lastKey) {
		if (now - lastChange > STALL_MS) {
			tracker = newTracker();
			send('off');
		} else if (tracker.sounding) {
			send(tracker.sounding + (mode === 'own' ? '' : 'W')); // the beat
		}
		return;
	}
	lastKey = key;
	lastChange = now;
	const fast = Math.hypot(vel.x, vel.y, vel.z) >= MIN_SPEED;
	const play = !editing && (mode === 'own' ? airborne() : replay !== REPLAY_PAUSED);
	const s = { play, fast, vx: vel.x, vy: vel.y, vz: vel.z, time, spectate: mode === 'spectate' };
	const kind = track(tracker, s, fallStep(), tick);
	const w = mode === 'own' ? '' : 'W';
	if (tracker.hit) $.Msg(HIT_MARKERS[tracker.hit] + w); // a one-shot, outside send()'s state
	send(kind ? kind + w : 'off');
}

function loop() {
	if (!live()) return;
	try {
		sample();
	} catch (e) {
		$.Msg(`MovekitSurfSound: ${e}`);
	}
	$.Schedule(0, loop);
}

$.RegisterForUnhandledEvent('HudCustomizer_Opened', () => {
	if (!live()) return;
	editing = true;
	send('off');
});
$.RegisterForUnhandledEvent('HudCustomizer_Closed', () => {
	if (live()) editing = false;
});
$.RegisterForUnhandledEvent('MomentumSpectateStart', () => {
	if (live()) spectating = true;
});
$.RegisterForUnhandledEvent('MomentumSpectateStop', () => {
	if (live()) spectating = false;
});
send('off'); // an earlier copy's sound may still be on (panorama_reload mid-ramp)
$.Schedule(0, loop);
