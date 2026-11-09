// Movement Kit Z Penalty probe (Phase 14.1 in PLAN.md; throwaway, never released). Loaded next to
// timer.ts through the kit's timer.xml patch. Logs ZPPROBE lines to the console and yaw.log, and answers:
// 1. how many ticks per jump show z speed in (0, 140] (expect about 12 at 66.67 tick, gravity 800);
// 2. what the per-tick z change looks like in free fall (expect -12) and while climbing a surf ramp;
// 3. whether speedGain falls short of idealGain on penalised ticks (a sign the 0.25 friction shows);
// 4. whether GameInterfaceAPI.ConsoleCommand('playvol ...') plays a sound in game: a blip at load and on
//    each entry into the band (at most one per second).
// No imports, like the Strafe Review recorder.

const TAG = 'ZPPROBE';
const BAND = 140;

function log(what: string, data?: unknown) {
	$.Msg(`${TAG} ${what}${data === undefined ? '' : ' ' + JSON.stringify(data)}`);
}

const r = (x: number, d = 2) => +(+x).toFixed(d);
let lastKey = '';
let prevVz = 0;
let inBand = false;
let bandTicks = 0;
let lastBeep = 0;

function beep(why: string) {
	try {
		GameInterfaceAPI.ConsoleCommand('playvol buttons/blip1 0.6');
		log('beep', why);
	} catch (e) {
		log('beep failed', String(e));
	}
}

function sample() {
	const stats = MomentumMovementAPI.GetLastTickStats();
	const vel = MomentumPlayerAPI.GetVelocity();
	const key = `${stats.speedGain},${stats.idealGain},${vel.x},${vel.y},${vel.z}`;
	if (key === lastKey) return;
	lastKey = key;
	const vz = vel.z;
	const dz = vz - prevVz;
	const now = vz > 0 && vz <= BAND;
	// every airborne tick near the band, plus ground ticks right after it, so the log stays short
	if (vz !== 0 || prevVz !== 0) {
		log('t', {
			tick: Math.round(MomentumMovementAPI.GetCurrentTime() / MomentumMovementAPI.GetTickInterval()),
			vz: r(vz), dz: r(dz), h: r(Math.hypot(vel.x, vel.y)), gain: r(stats.speedGain, 3),
			ideal: r(stats.idealGain, 3), band: now ? 1 : 0, move: MomentumMovementAPI.GetMoveHudData().moveStatus
		});
	}
	if (now && !inBand) {
		bandTicks = 0;
		const t = Date.now();
		if (t - lastBeep > 1000) {
			lastBeep = t;
			beep('band entry');
		}
	}
	if (now) bandTicks++;
	if (!now && inBand) log('band left', { ticks: bandTicks });
	inBand = now;
	prevVz = vz;
}

function loop() {
	try {
		sample();
	} catch (e) {
		log('sample failed', String(e));
		return;
	}
	$.Schedule(0, loop);
}

log('loaded', { interval: MomentumMovementAPI.GetTickInterval() });
beep('load');
$.Schedule(0, loop);
