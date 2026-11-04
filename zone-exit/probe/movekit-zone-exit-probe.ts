// Movement Kit Zone Exit Speed probe (Phase 10.1 in PLAN.md; throwaway, never released). Loaded next to
// timer.ts through the kit's timer.xml patch. Logs ZXPROBE lines to the console and yaw.log, and answers:
// 1. does OnObservedTimerSegmentEffectiveStart fire when leaving the start zone (the game's own scripts
//    never use it), with which majorNum, and also at stage starts?
// 2. does GetObservedTimerRunSplits().segments[n].effectiveStartVelocity hold the exit velocity then?
// 3. does the loaded comparison run (RunComparisonsAPI.GetComparisonRun()) carry its own exit velocity?
// 4. the start zone's speed limit (GetActiveZoneDefs()), for the colour bands' defaults.
// No imports, like the Strafe Review recorder.

const TAG = 'ZXPROBE';

function log(what: string, data?: unknown) {
	$.Msg(`${TAG} ${what}${data === undefined ? '' : ' ' + JSON.stringify(data)}`);
}

type V = { x: number; y: number; z: number } | null | undefined;
const mag = (v: V) => (v ? +Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z).toFixed(2) : null);
const hor = (v: V) => (v ? +Math.sqrt(v.x * v.x + v.y * v.y).toFixed(2) : null);

function splitsInfo(where: string) {
	const st = MomentumTimerAPI.GetObservedTimerStatus();
	const sp = MomentumTimerAPI.GetObservedTimerRunSplits();
	const segs = sp?.segments ?? [];
	const v = segs.length ? segs[Math.max(0, st.majorNum - 1)]?.effectiveStartVelocity : null;
	const now = MomentumPlayerAPI.GetVelocity();
	log(where, {
		mode: GameModeAPI.GetCurrentGameMode(),
		state: st.state, major: st.majorNum, minor: st.minorNum, track: st.trackId, segs: segs.length,
		v, v3d: mag(v), vh: hor(v), seg0: segs[0]?.effectiveStartVelocity ?? null,
		now3d: mag(now), nowh: hor(now),
		replay: MomentumReplayAPI.GetReplayState(), observed: !!MomentumTimerAPI.GetObservedRunMetadata()
	});
	const cmp = RunComparisonsAPI.GetComparisonRun();
	const cs = cmp?.runSplits?.segments ?? [];
	log(`${where} comparison`, cmp ? {
		file: cmp.filePath, time: cmp.runTime, track: cmp.trackId, segs: cs.length,
		seg0: cs[0]?.effectiveStartVelocity ?? null, seg0_3d: mag(cs[0]?.effectiveStartVelocity)
	} : null);
}

function zoneInfo(where: string) {
	try {
		const z = MomentumTimerAPI.GetActiveZoneDefs() as any;
		const text = JSON.stringify(z);
		const hits = text.match(/"(maxVelocity|limitStartGroundSpeed|startSpeed\w*)":[^,}]+/g);
		log(`${where} zones`, { size: text.length, hits });
		const main = z?.tracks?.main;
		log(`${where} main track`, JSON.stringify(main).slice(0, 1500));
	} catch (e) {
		log(`${where} zones failed`, String(e));
	}
}

$.RegisterForUnhandledEvent('OnObservedTimerSegmentEffectiveStart', () => splitsInfo('segment start'));
$.RegisterForUnhandledEvent('OnObservedTimerStateChange', () => splitsInfo('state change'));
$.RegisterForUnhandledEvent('ComparisonRunUpdated', () => splitsInfo('comparison updated'));
$.RegisterForUnhandledEvent('ActiveZoneDefsChanged', () => zoneInfo('zone defs changed'));
log('loaded');
zoneInfo('load');
