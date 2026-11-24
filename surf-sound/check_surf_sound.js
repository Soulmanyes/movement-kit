#!/usr/bin/env node
// Checks surf-sound/panorama/scripts/hud/movekit-surf-sound.ts in node, with Panorama stubbed (types
// stripped, as z-penalty/check_z_penalty.js does).
//
// Usage: node surf-sound/check_surf_sound.js   (exits 1 on the first failure)
//
// Covers: the classifier and tracker on synthetic shapes (free fall at -12 per tick, a jump, a ramp climb
// rising about 8 per tick, a slide down a ramp, a headsurf falling faster than gravity, a flat ceiling
// bonk, a slow frame with two ticks per sample, a teleport, landing); the Panorama side: OFF at load,
// RAMP/CEIL on a change and again every half second, OFF on the ground, below the speed floor, when the
// velocity stalls, in replays, spectating, noclip and with the HUD customizer open, panorama_reload; hits:
// wall strengths, the hit gap, ramp landings and wrong-way strafes, head hits (hard, light, a headsurf
// starting at a jump's top, flat, sloped, reading 0, slow rising onto ground), the ceiling sound held one contact after a head hit, WALL/BONK markers.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { stripTypeScriptTypes } = require('module');

const TS = path.join(__dirname, 'panorama/scripts/hud/movekit-surf-sound.ts');

function fail(msg) {
	console.log(`FAIL: ${msg}`);
	process.exit(1);
}
function expect(got, want, what) {
	if (JSON.stringify(got) !== JSON.stringify(want)) fail(`${what}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
}

const TICK = 0.015;
const STEP = -800 * TICK; // -12
const handlers = {};
let schedules = [];
let markers = [];
let now = 1e6;
const G = { replay: 0, curtick: 0, observed: null, moveType: 2, status: 0, time: 0, velocity: { x: 900, y: 0, z: 0 } };
const GLOBAL = {};
const stubs = {
	$: {
		RegisterForUnhandledEvent: (ev, fn) => { (handlers[ev] = handlers[ev] || []).push(fn); },
		Schedule: (s, fn) => { schedules.push({ s, fn }); },
		Msg: (m) => (/^MK_SURFSND_((RAMP|CEIL|WALL[123]|GRAZE|BONK)W?|OFF)$/.test(m) ? markers.push(m.slice(11)) : fail('Msg: ' + m))
	},
	GameInterfaceAPI: { GetSettingFloat: (k) => (k === 'sv_gravity' ? 800 : 0) },
	MomentumReplayAPI: { GetReplayState: () => G.replay, GetReplayProgress: () => ({ curtick: G.curtick }) },
	MomentumMovementAPI: {
		GetMoveType: () => G.moveType, GetTickInterval: () => TICK, GetCurrentTime: () => G.time,
		GetMoveHudData: () => ({ moveStatus: G.status })
	},
	MomentumPlayerAPI: { GetVelocity: () => G.velocity },
	MomentumTimerAPI: { GetObservedRunMetadata: () => G.observed },
	UiToolkitAPI: { GetGlobalObject: () => GLOBAL },
	Date: { now: () => now },
	Math,
	JSON,
	console
};
const raw = fs.readFileSync(TS, 'utf8');
function loadScript() {
	const ctx = { ...stubs };
	vm.createContext(ctx);
	vm.runInContext(`${stripTypeScriptTypes(raw, { mode: 'strip' })}
globalThis.__api = { newTracker, fallSteps, classify, track, ON_SAMPLES, OFF_SAMPLES, HIT_GAP_MS };`, ctx);
	return ctx.__api;
}
const api = loadScript();
expect(markers, ['OFF'], 'a load turns an earlier copy\'s sound off');
markers = [];

// ---- the classifier ----
expect(api.classify(STEP, TICK, STEP, TICK), 'fall', 'one free fall step');
expect(api.classify(2 * STEP, 2 * TICK, STEP, TICK), 'fall', 'two steps in a slow frame');
expect(api.classify(8, TICK, STEP, TICK), 'ramp', 'z rising on a ramp climb');
expect(api.classify(-5, TICK, STEP, TICK), 'ramp', 'falling slower than gravity: a slide');
expect(api.classify(0, TICK, STEP, TICK), 'ramp', 'z level in the air: a surface carries you');
expect(api.classify(-20, TICK, STEP, TICK), 'ceiling', 'falling faster than gravity: a headsurf');
expect(api.classify(-20, 2 * TICK, STEP, TICK), 'ramp', 'two ticks of -10: slower than two steps');
expect(api.classify(-30, 2 * TICK, STEP, TICK), 'ceiling', 'two ticks of -15');
expect(api.classify(290, TICK, STEP, TICK), 'ramp', 'a jump-sized change is still under MAX_DZ');
expect(api.classify(-900, TICK, STEP, TICK), null, 'a teleport tells nothing');

// ---- the tracker ----
// samples: [air, vz, ticks = 1, vx = 900]; air false: on the ground (z speed 0) or out of play
let clock = 1;
function run(t, samples, hits) {
	const out = [];
	for (const [air, vz, ticks = 1, vx = 900, vy = 0] of samples) {
		clock += ticks * TICK;
		out.push(api.track(t, { play: air, fast: true, vx, vy, vz: air ? vz : 0, time: clock }, STEP, TICK));
		if (hits) hits.push(t.hit);
	}
	return out;
}
const fall = (from, n) => Array.from({ length: n }, (_, i) => [true, from + (i + 1) * STEP]);
const along = (from, by, n, ticks = 1) => Array.from({ length: n }, (_, i) => [true, from + (i + 1) * by * ticks, ticks]);

let t = api.newTracker();
// a jump: first air sample (no history), then free fall to the ground
let got = run(t, [[true, 290], ...fall(290, 40), [false, 0]]);
expect(got.every((k) => k === null), true, 'a jump plays nothing');

t = api.newTracker();
got = run(t, [[true, -21], ...along(-21, 8, 20)]);
expect(got.slice(0, api.ON_SAMPLES + 1), [null, 'ramp'], 'a climb plays from its first contact sample');
expect(got.slice(api.ON_SAMPLES + 1).every((k) => k === 'ramp'), true, 'a climb plays ramp');
// off the ramp: free fall for OFF_SAMPLES samples
got = run(t, fall(139, 5));
expect(got, [ 'ramp', 'ramp', null, null, null ], 'leaving the ramp stops after OFF_SAMPLES fall samples');

t = api.newTracker();
got = run(t, [[true, 0], ...along(0, -5, 10)]);
expect(got.at(-1), 'ramp', 'a slide down a ramp plays ramp');
t = api.newTracker();
got = run(t, [[true, 0], ...along(0, -20, 10)]);
expect(got.at(-1), 'ceiling', 'a headsurf plays ceiling');
t = api.newTracker();
got = run(t, [[true, 0], ...along(0, -5, 10, 2)]);
expect(got.at(-1), 'ramp', 'a slide at two ticks per sample');

t = api.newTracker();
got = run(t, [[true, 200], [true, 180], ...fall(180, 10)]);
expect(got.slice(0, 5), [null, 'ceiling', 'ceiling', 'ceiling', null], 'a one-tick headsurf plays, then OFF_SAMPLES more');

t = api.newTracker();
got = run(t, [[true, 1], ...along(1, 8, 5), [true, 41 + STEP], [true, 41 + 2 * STEP], [true, 41 + 2 * STEP + 8]]);
expect(got.slice(-3), ['ramp', 'ramp', 'ramp'], 'two free fall samples mid-ride keep it on');

t = api.newTracker();
run(t, [[true, 0], ...along(0, 8, 5)]);
expect(run(t, [[false, 0]]), [null], 'landing stops it at once');
run(t, [[true, 0], ...along(0, 8, 5)]);
expect(run(t, [[true, -2000]]), [null], 'a teleport stops it at once');

t = api.newTracker();
run(t, [[true, 0], ...along(0, 8, 5)]);
got = run(t, along(41, -20, 3));
expect(got, ['ceiling', 'ceiling', 'ceiling'], 'ramp to ceiling switches at once');

// ---- hits ----
let hits = [];
t = api.newTracker();
// a wall in free fall: 900 -> 500 horizontal, z still free fall
run(t, [[true, -100], [true, -112], [true, -124, 1, 500], [true, -136, 1, 300], [true, -148, 1, 300]], hits);
expect(hits, [null, null, 'wall2', null, null], 'a wall hit: once, strength by the speed lost (second clip in the gap)');
hits = [];
run(t, [[true, -160, 1, 300], ...Array.from({ length: 20 }, (_, i) => [true, -172 - 12 * i, 1, 300]), [true, -500, 1, 100]], hits);
expect(hits.filter(Boolean), [], 'a drop of 200 with z off free fall (a ramp landing) is no wall');
hits = [];
t = api.newTracker();
run(t, [[true, -100, 1, 2000], [true, -112, 1, 2000], [true, -124, 1, 0], [true, -136, 1, 0]], hits);
expect(hits, [null, null, 'wall3', null], 'an axis-aligned wall zeroing the speed: wall3');
hits = [];
t = api.newTracker();
run(t, [[true, -100, 1, 1000], [true, -112, 1, 1000], [true, -124, 1, 950]], hits);
expect(hits, [null, null, null], 'losing 50 (a wrong-way strafe) is no wall');
hits = [];
t = api.newTracker();
run(t, [[true, -100, 1, 1500], [true, -112, 1, 1500], [true, -124, 1, 1324.5, 482.1]], hits);
expect(hits, [null, null, 'wall1'], 'a glancing wall at 20 degrees (1500 -> 1410, the change at a right angle): wall1');
// riding a curved wall while falling (a leaderboard replay on surf_tequila): the velocity turns, losing more each tick
const curve = (rows) => rows.map(([vx, vy], i) => [true, -100 + i * STEP, 1, vx, vy]);
hits = [];
t = api.newTracker();
run(t, curve([[1612.3, 1590.6], [1397.2, 1756.4], [1156.3, 1906.9], [807.4, 2049.9], [336.8, 2131.0], [-245.0, 2069.7], [-777.2, 1826.7], [-1199.4, 1421.8]]), hits);
expect(hits, [null, null, null, null, null, null, null, null], 'a curved wall ride losing 5, 14, 27, 46, 73, 99, 125: no wall');
hits = [];
t = api.newTracker();
run(t, curve([[-1155.6, -1007.0], [-1041.0, -1115.5], [-912.5, -1215.9], [-774.2, -1301.9], [0, -1374.2], [0, -1374.2]]), hits);
expect(hits, [null, null, null, null, null, null], 'a curved ride ending on a flat wall (1515 -> 1374): no wall');
hits = [];
t = api.newTracker();
const slide = Array.from({ length: 4 }, (_, i) => [(1500 - 2.5 * i) * Math.cos(i * 0.05), (1500 - 2.5 * i) * Math.sin(i * 0.05)]);
run(t, curve([...slide, [0, 300]]), hits);
expect(hits, [null, null, null, null, 'wall3'], 'a slam out of a slow slide (2.5 lost a tick, then 1490 -> 300): wall3');

hits = [];
t = api.newTracker();
run(t, curve([...slide, [1420 * Math.cos(0.25), 1420 * Math.sin(0.25)]]), hits);
expect(hits, [null, null, null, null, null], 'a slide losing 72 at once, at a right angle: no glancing hit');
hits = [];
t = api.newTracker();
run(t, curve([[1622.4, 1690.6], [1462.3, 1788.5], [1696.9, 1500.4]]), hits);
expect(hits, [null, null, 'wall1'], 'glancing off a pillar, spectated: 34 then 46 lost at a right angle is a hit, not a slide');
hits = [];
t = api.newTracker();
run(t, [[true, -100, 1, 1500], [true, -112, 1, 1500], [true, -124, 1, 1400, 120]], hits);
expect(hits, [null, null, null], 'a strafe slowing you by 95 (a change of 156) is no wall');
hits = [];
t = api.newTracker();
run(t, [[true, -100, 1, 1500], [true, -112, 1, 1500], [true, -124, 1, 1396.6, 194.3]], hits);
expect(hits, [null, null, null], 'losing 90 with a change of 220 partly against the speed (cos -0.34) is no wall');
const ride = (vz, n = 4) => Array.from({ length: n }, (_, i) => [true, vz - 6 * i, 1, 1100]);
hits = [];
t = api.newTracker();
got = run(t, [...ride(-1160), [true, 0, 1, 1110], [true, 0, 1, 1040], [true, -6, 1, 1000]], hits);
expect([hits.slice(4), got.slice(3, 5)], [['wall3', null, null], ['ramp', null]], 'riding a ramp onto a spine top (-1178 -> 0, recorded): wall3');
hits = [];
t = api.newTracker();
run(t, [...ride(-500), [true, 0, 1, 1100]], hits);
expect(hits.slice(4), ['wall2'], 'riding a ramp onto a flat top at -518: wall2');
hits = [];
t = api.newTracker();
run(t, [...ride(-200), [true, 0, 1, 1100]], hits);
expect(hits.filter(Boolean), [], 'sliding off a slope onto the floor at -218 is no hit');
hits = [];
t = api.newTracker();
run(t, [...ride(-1160), [true, 0, 1, 0]], hits);
expect(hits.filter(Boolean), [], 'a teleport out of a ramp ride (speed zeroed) is no hit');
hits = [];
t = api.newTracker();
run(t, [[true, -1100, 1, 1100], [true, -1112, 1, 1100], [true, -1124, 1, 1100], [true, 0, 1, 1100]], hits);
expect(hits.filter(Boolean), [], 'free fall onto the ground (no ramp ride) is no hit');
// a free fall onto a spine top, no ramp ride before it: plays on dropping off (recorded, surf_fiellu)
const drop = (h, after) => [[true, -1397, 1, h], [true, -1409, 1, h], [true, -1421, 1, h], [true, 0, 1, h], ...after];
hits = [];
t = api.newTracker();
run(t, drop(2382, [[true, 0, 1, 2239], [true, -6, 1, 2105]]), hits);
expect(hits, [null, null, null, null, null, 'wall3'], 'free fall onto a spine top (-1421 -> 0, recorded), then off it: wall3');
hits = [];
t = api.newTracker();
run(t, [[true, -300, 1, 1800], [true, -312, 1, 1800], [true, -324, 1, 1800], [true, 0, 1, 1800], [true, -6, 1, 1750]], hits);
expect(hits, [null, null, null, null, 'wall2'], 'free fall onto a spine top at -324, then off it: wall2');
hits = [];
t = api.newTracker();
run(t, drop(2382, [[true, 0, 1, 2300], [true, 0, 1, 2250], [true, 0, 1, 2200], [true, 0, 1, 2150], [true, -6, 1, 2100]]), hits);
expect(hits.filter(Boolean), [], 'staying on a flat top for 75 ms before dropping off is no hit');
hits = [];
t = api.newTracker();
run(t, drop(2382, [[false, 0, 1, 2300], [true, -12, 1, 2300]]), hits);
expect(hits.filter(Boolean), [], 'landing on the ground (not airborne) is no hit');
hits = [];
t = api.newTracker();
run(t, drop(2382, [[true, 290, 1, 2300], [true, 278, 1, 2300]]), hits);
expect(hits.filter(Boolean), [], 'a jump off the landing is no hit');
hits = [];
t = api.newTracker();
run(t, drop(400, [[true, -6, 1, 400]]), hits);
expect(hits.filter(Boolean), [], 'stepping off a ledge at 400 u/s is no hit');
hits = [];
t = api.newTracker();
run(t, [[true, -1397, 1, 2382], [true, -1409, 1, 2382], [true, 0, 1, 0], [true, -12, 1, 0]], hits);
expect(hits.filter(Boolean), [], 'a teleport out of a free fall is no hit');
hits = [];
t = api.newTracker();
run(t, [[true, 0, 1, 1000], [true, 0, 1, 600]], hits);
expect(hits, [null, null], 'on the ground nothing hits');

// head hits: rising, the ceiling takes the speed
hits = [];
t = api.newTracker();
got = run(t, [[true, 600], [true, 588], [true, 576], [true, 97], [true, 18], [true, -60], [true, -72], [true, -84]], hits);
expect(hits, [null, null, null, 'bonk', null, null, null, null], 'a head hit (576 -> 97), the second clip in the gap');
expect(got, [null, null, null, null, null, 'ceiling', 'ceiling', 'ceiling'], 'a head hit holds the ceiling sound one contact');
hits = [];
t = api.newTracker();
run(t, [[true, 500], [true, 488], [true, -6]], hits);
expect(hits, [null, null, 'bonk'], 'a flat ceiling: 488 -> -6');
hits = [];
t = api.newTracker();
got = run(t, [[true, 500], [true, 488], [true, 0], [true, -12]], hits);
expect([hits, got], [[null, null, 'bonk', null], [null, null, null, null]], 'a head hit reading exactly 0 from fast rising is no landing');
hits = [];
t = api.newTracker();
run(t, [[true, 618, 3, 86, -417], [true, 582, 3, 86, -417], [true, 0, 3, 0, 0]], hits);
expect(hits, [null, null, null], 'a reset to the start while rising (582, all speed to 0) is no head hit');
hits = [];
t = api.newTracker();
run(t, [[true, 500], [true, 488], [true, 0], [true, -12, 1, 300]], hits);
expect(hits, [null, null, 'bonk', 'wall2'], 'the sample after a head hit reading 0 keeps its history (a wall right after)');
hits = [];
t = api.newTracker();
run(t, [[true, 120], [true, 108], [true, 0]], hits);
expect(hits, [null, null, null], 'slow rising onto flat ground (z speed 0) is a landing');
hits = [];
t = api.newTracker();
run(t, [[true, 900], [true, 888], [true, 800], [true, 700]], hits);
expect(hits, [null, null, null, null], 'a sloped ceiling slowing a fast rise is no head hit');
hits = [];
t = api.newTracker();
got = run(t, [[true, 140], [true, 128], [true, -6], [true, -18]], hits);
expect([hits, got], [[null, null, 'graze', null], [null, null, null, null]], 'clipping a flat ceiling near the top of a jump: a light hit');
hits = [];
t = api.newTracker();
run(t, [[true, 412], [true, 400], [true, -6]], hits);
expect(hits, [null, null, 'bonk'], 'rising at BONK_HARD into a ceiling: a hard hit');
hits = [];
t = api.newTracker();
run(t, [[true, 400], [true, 388], [true, -6]], hits);
expect(hits, [null, null, 'graze'], 'rising just under BONK_HARD into a flat ceiling: a light hit');
hits = [];
t = api.newTracker();
got = run(t, [[true, 47], [true, 35], [true, -190], [true, -290]], hits);
expect([hits, got.slice(2)], [[null, null, null, null], ['ceiling', 'ceiling']], 'a sloped ceiling throwing you down at the top of a jump: a headsurf, no hit');
hits = [];
t = api.newTracker();
run(t, [[true, 336, 1, 2112], [true, 324, 1, 2112], [true, -863, 1, 1319], [true, -875, 1, 1319]], hits);
expect(hits, [null, null, 'bonk', null], 'a sloped ceiling hit nearly head-on, thrown down at a big speed cost: a bonk (owner\'s PB, 560 lost)');
hits = [];
t = api.newTracker();
run(t, [[true, 336, 1, 1000], [true, 324, 1, 1000], [true, -300, 1, 915]], hits);
expect(hits, [null, null, null], 'a deflection costing under WALL_MIN of speed: no hit');
hits = [];
t = api.newTracker();
run(t, [[true, 336, 1, 1000], [true, 324, 1, 1000], [true, -300, 1, 900]], hits);
expect(hits, [null, null, 'bonk'], 'a deflection costing WALL_MIN or more, thrown down to THROW_VZ: a bonk');
hits = [];
t = api.newTracker();
run(t, [[true, 134, 1, 893], [true, 122, 1, 893], [true, -32, 1, 644], [true, -44, 1, 644]], hits);
expect(hits, [null, null, 'graze', null], 'a head hit costing speed without a throw (imaginarium donut): a graze');
hits = [];
t = api.newTracker();
run(t, [[true, 336, 1, 1000], [true, 324, 1, 1000], [true, -299, 1, 880]], hits);
expect(hits, [null, null, 'graze'], 'a deflection just short of THROW_VZ: a graze');
hits = [];
t = api.newTracker();
run(t, [[true, 30], [true, 18], [true, 6]], hits);
expect(hits, [null, null, null], 'free fall near the top of a jump is no hit');
hits = [];
t = api.newTracker();
run(t, [[true, 500], [true, 488], [true, -6], [true, -18], ...fall(-18, 20), [true, 500], [true, 488], [true, -6]], hits);
expect(hits.filter(Boolean), ['bonk', 'bonk'], 'two head hits apart both play');

// ---- Panorama ----
const tickLoop = () => {
	const due = schedules;
	schedules = [];
	due.forEach(({ fn }) => fn());
};
const fire = (ev) => (handlers[ev] || []).forEach((fn) => fn());
// one new tick: z changes by dz, the frame takes ms
function tick(dz, ms = 15) {
	G.time += TICK;
	G.curtick++;
	G.velocity = { x: G.velocity.x + 1, y: 0, z: G.velocity.z + dz };
	now += ms;
	tickLoop();
}
function frame(ms) {
	now += ms;
	tickLoop();
}
tickLoop();
G.velocity = { x: 900, y: 0, z: 0 };
for (let i = 0; i < 5; i++) tick(8);
expect(markers, ['RAMP'], 'surfing writes RAMP once');
for (let i = 0; i < 40; i++) tick(8);
expect(markers.filter((m) => m === 'RAMP').length, 2, 'RAMP again after half a second (the beat)');
for (let i = 0; i < 5; i++) tick(STEP);
expect(markers.at(-1), 'OFF', 'free fall writes OFF');
markers = [];

for (let i = 0; i < 5; i++) tick(8);
frame(100);
frame(200);
expect(markers, ['RAMP', 'OFF'], 'a stalled velocity (paused, stuck) writes OFF');
markers = [];

for (let i = 0; i < 5; i++) tick(8);
G.status = 1;
tick(0);
expect(markers, ['RAMP', 'OFF'], 'on the ground: OFF');
G.status = 0;
markers = [];

// walking: moveStatus stays AIR (surf doesn't fill it), z speed exactly 0, the speed changing
markers = [];
G.velocity = { x: 260, y: 0, z: 0 };
for (let i = 0; i < 30; i++) tick(0);
expect(markers, [], 'walking on the ground (z speed 0, moveStatus still AIR) plays nothing');
G.velocity = { x: 260, y: 0, z: 0 };
tick(290);
for (let i = 0; i < 48; i++) tick(STEP);
G.velocity = { x: 300, y: 0, z: 0 };
tick(0);
tick(0);
expect(markers, [], 'a jump from the ground and its landing play nothing');

G.velocity = { x: 50, y: 0, z: 0 };
for (let i = 0; i < 5; i++) tick(1);
expect(markers, [], 'below the speed floor nothing plays');
G.velocity = { x: 900, y: 0, z: 0 };

for (const [what, set, unset] of [
	['noclip', () => { G.moveType = 8; }, () => { G.moveType = 2; }],
	['the customizer', () => fire('HudCustomizer_Opened'), () => fire('HudCustomizer_Closed')],
	['a paused replay', () => { G.replay = 2; G.moveType = 10; }, () => { G.replay = 0; G.moveType = 2; }]
]) {
	markers = [];
	set();
	for (let i = 0; i < 5; i++) tick(8);
	expect(markers.filter((m) => m !== 'OFF'), [], `${what} plays nothing`);
	unset();
	for (let i = 0; i < 5; i++) tick(8);
	expect(markers.at(-1), 'RAMP', `back from ${what}`);
	for (let i = 0; i < 5; i++) tick(STEP);
}

// watching: a playing replay and spectating play, with W markers (the local player an observer, moveStatus
// AIR throughout); leaving starts own play again
for (const [what, set, unset] of [
	['a replay', () => { G.replay = 1; G.moveType = 10; }, () => { G.replay = 0; G.moveType = 2; }],
	['a watched run', () => { G.observed = {}; G.moveType = 10; }, () => { G.observed = null; G.moveType = 2; }],
	['spectating', () => { fire('MomentumSpectateStart'); G.moveType = 10; }, () => { fire('MomentumSpectateStop'); G.moveType = 2; }]
]) {
	markers = [];
	G.velocity = { x: 900, y: 0, z: -500 }; // clear of exactly 0 (the ground) throughout
	set();
	for (let i = 0; i < 5; i++) tick(8);
	expect(markers, ['RAMPW'], `${what} plays, marked W`);
	for (let i = 0; i < 5; i++) tick(STEP);
	expect(markers.at(-1), 'OFF', `${what}: free fall writes OFF`);
	unset();
	for (let i = 0; i < 5; i++) tick(8);
	expect(markers.at(-1), 'RAMP', `back from ${what}: own play, no W`);
	for (let i = 0; i < 5; i++) tick(STEP);
}

// a replay counts its own ticks (curtick): at half speed a replay tick takes two game ticks, and a wall
// hit (its z change one free fall step for one replay tick) still counts
markers = [];
G.replay = 1;
G.moveType = 10;
const halfTick = (dz) => {
	tick(dz);
	G.time += TICK; // a game tick with no replay tick: the velocity doesn't change
	frame(15);
};
for (let i = 0; i < 4; i++) halfTick(STEP);
G.velocity = { x: 900, y: 0, z: G.velocity.z };
halfTick(STEP);
G.velocity = { x: 50, y: 0, z: G.velocity.z };
halfTick(STEP);
expect(markers.filter((m) => m !== 'OFF'), ['WALL3W'], 'a half-speed replay: a wall hit by replay ticks');
G.replay = 0;
G.moveType = 2;
for (let i = 0; i < 5; i++) tick(STEP);

// spectating: updates of 5 spectated ticks, the local clock not following them
markers = [];
fire('MomentumSpectateStart');
G.moveType = 10;
for (let i = 0; i < 4; i++) tick(5 * STEP, 50); // free fall: 5 steps an update
tick(-40, 50); // a slide: -40 over 5 ticks is slower than the -60 of free fall
tick(-40, 50);
expect(markers.filter((m) => m !== 'OFF'), ['RAMPW'], 'spectating: a slide between 5-step updates is a ramp');
for (let i = 0; i < 5; i++) tick(5 * STEP, 50);
markers = [];
G.velocity = { x: 900, y: 0, z: G.velocity.z };
tick(5 * STEP, 50);
G.velocity = { x: 50, y: 0, z: G.velocity.z };
tick(5 * STEP, 50);
expect(markers, ['WALL3W'], 'spectating: a wall hit in a 5-step update writes WALL3W');
fire('MomentumSpectateStop');
G.moveType = 2;
for (let i = 0; i < 5; i++) tick(STEP);

// hits through Panorama: one marker each, the constant sound's state untouched
markers = [];
for (let i = 0; i < 5; i++) tick(STEP);
G.velocity = { x: 900, y: 0, z: G.velocity.z };
tick(STEP);
G.velocity = { x: 50, y: 0, z: G.velocity.z };
tick(STEP);
expect(markers, ['WALL3'], 'a wall hit writes WALL3 once, no OFF repeated');
G.velocity = { x: 900, y: 0, z: 500 };
markers = [];
tick(-12);
tick(-300);
expect(markers, ['BONK'], 'a head hit writes BONK');
for (let i = 0; i < 5; i++) tick(STEP);

// panorama_reload: the new copy writes OFF, the old copy's loop stops
markers = [];
for (let i = 0; i < 5; i++) tick(8);
loadScript();
expect(markers, ['RAMP', 'OFF'], 'a reload writes OFF');
const before = schedules.length;
tickLoop();
expect(schedules.length, 1, `only the new copy keeps looping (had ${before})`);

console.log('surf-sound: all JS checks passed');
