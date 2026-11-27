// Movement Kit Paint Saver: brings back paint saved on a map, on mk_loadpaint after the next game start.
// Loaded next to timer.ts through the kit's timer.xml patch (install.py). No imports, like the Strafe
// Review recorder. Found with the probe (paint-saver/probe, 2026-11-27):
// - The paint key isn't visible to Panorama, so install.py binds it to +mkpaint, which sets the hostname
//   cvar to mkpaint1/mkpaint0; mk_savepaint / mk_clearpaint / mk_loadpaint set it to mkpaintsave /
//   mkpaintclear / mkpaintrestore.
// - Recording: while held, every SAMPLE_MS, log MK_PAINT_S then run getpos; its "setpos ...;setang ..."
//   answer lands in yaw.log right after the marker. paintlog.py reads it at the next game start.
// - Restore: install.py writes the saved samples into savedlocs.txt as the block zzpaint_<map> while the
//   game is closed, and the PLAN below. On mk_loadpaint, on a map with a plan: import the block, hold
//   +paint while going to each imported savestate (goto is 1-based), delete them again from the top,
//   mom_restart_track. Only on the command, not on map load: the mouse moving during the replay moves the
//   marks, so the player starts it with hands off (owner, 2026-11-27).
// - Each point's spot after the goto is logged (MK_PAINT_R + getpos), a step later: paintlog.py finds the
//   missed ones at the next game start and writes them again higher, lower or back along the aim (paint
//   drawn in noclip near or inside a brush; going to a savestate turns noclip off). STUCK: per map, points
//   nothing placed.

const PLAN: Record<string, [string, string, number, number?][]> = /*MK_PLAN*/ {};
const STUCK: Record<string, number> = /*MK_STUCK*/ {};
const SAMPLE_MS = 15;
const STEP_MS = 15;
const RETRY_MS = 2000; // before importing again after an import that added nothing
const PREFIX = 'zzpaint_';
// before the first point paints: right after the first goto (from far away) getpos read up to 14 high,
// coming down over 6 steps (probe, 2026-11-27), which would count those points as blocked
const SETTLE_MS = 250;

function log(what: string, data?: unknown) {
	$.Msg(`MK_PAINT_${what}${data === undefined ? '' : ' ' + JSON.stringify(data)}`);
}

function cmd(c: string) {
	try {
		GameInterfaceAPI.ConsoleCommand(c);
	} catch (e) {
		$.Msg(`MK_PAINT_ERR ${JSON.stringify({ c, e: String(e) })}`);
	}
}

function say(text: string) {
	cmd(`echo "Paint Saver: ${text}"`);
}

function setting(name: string) {
	try {
		return GameInterfaceAPI.GetSettingString(name);
	} catch {
		return '';
	}
}

function mapName() {
	try {
		return (MapCacheAPI.GetMapName() || '').toLowerCase();
	} catch {
		return '';
	}
}

let count = -1;
let current = -1;
let countMap = ''; // the map count belongs to: it carries over from the last map until the new one's event
let events = 0;
$.RegisterForUnhandledEvent('OnSaveStateUpdate', (c: number, cur: number) => {
	count = c;
	current = cur;
	countMap = mapName();
	events++;
});

// ---- recording -------------------------------------------------------------------------------------

let busy = false; // a restore runs: nothing is recorded
let held = false;
let lastSample = 0;

function ducking() {
	try {
		return MomentumPlayerAPI.IsDucking() ? 1 : 0;
	} catch {
		return 0;
	}
}

function watch() {
	const host = setting('hostname');
	if (host === 'mkpaintsave' || host === 'mkpaintclear' || host === 'mkpaintrestore') {
		cmd('hostname mkpaint0');
		const map = mapName();
		if (!map) {
			say('load a map first');
		} else if (host === 'mkpaintrestore') {
			if (busy) say('a restore is already running');
			else if (!PLAN[map] || !PLAN[map].length) say(`no saved paint on ${map} (paint saved this session comes back after a game restart)`);
			else {
				tries = 0;
				say("restoring the saved paint; don't move the mouse until it's done");
				restore(map);
			}
		} else if (host === 'mkpaintsave') {
			log('SAVE');
			say(`saved the paint on ${map}; after the next game start (through movekit-run), mk_loadpaint paints it again`);
		} else {
			log('CLEAR');
			say(`cleared the saved paint on ${map} (paint on screen stays until the map reloads)`);
		}
	}
	const down = host === 'mkpaint1' && !busy;
	if (down !== held) {
		held = down;
		if (down) {
			log('DOWN', { c: setting('mom_paint_color'), s: setting('mom_paint_size') });
			lastSample = 0;
		} else {
			log('UP');
		}
	}
	const now = Date.now();
	if (held && now - lastSample >= SAMPLE_MS) {
		lastSample = now;
		log('S', { d: ducking() });
		cmd('getpos');
	}
	$.Schedule(0, watch);
}

// ---- restore ---------------------------------------------------------------------------------------

// where the n-th replayed point (1-based) put the player, for paintlog.py
function where(n: number) {
	log('R', { k: n });
	cmd('getpos');
}

function later(ms: number, f: () => void) {
	$.Schedule(ms / 1000, f);
}

function restore(map: string) {
	const strokes = PLAN[map];
	if (!strokes || !strokes.length || busy) return;
	busy = true;
	if (countMap === map) {
		importAndPaint(map, strokes, count);
		return;
	}
	// the list's length on this map isn't known yet (no event since the map loaded): going to the last
	// savestate sends one; none means an empty list
	const seen = events;
	cmd('mom_savestate_last');
	later(300, () => importAndPaint(map, strokes, events !== seen && countMap === map ? count : -1));
}

// before: the list's length before the import, -1 when the game sent nothing (taken as empty, but then a
// mismatch deletes nothing anyway)
function importAndPaint(map: string, strokes: [string, string, number, number?][], before: number) {
	const total = strokes.reduce((n, s) => n + s[2], 0);
	const seen = events;
	const t0 = Date.now();
	log('RESTORE', { map, strokes: strokes.length, total, before, v: 2 }); // v 2: reads each point (paintlog.py)
	cmd(`mom_saveloc_import ${PREFIX}${map}`);
	later(500, () => {
		const nothing = events === seen || (before >= 0 && count === before);
		if (nothing && tries < MAX_TRIES) {
			// the first import after a game start can add nothing (seen in game twice, 2026-11-27): again a
			// little later
			tries++;
			log('RESTORE_RETRY', { before, count, tries });
			busy = false;
			later(RETRY_MS, () => restore(map));
			return;
		}
		if (nothing || count !== Math.max(before, 0) + total) {
			log('RESTORE_FAIL', { why: 'import', before, count, total });
			// install.py bakes the plan from the block it last wrote, so a count that doesn't match means the
			// list changed meanwhile (a savestate made right after the command): delete nothing, as which
			// entries are the imported ones isn't known. A cut-short restore's leftovers go at the next
			// game start (savedlocs.py).
			say(`the paint savestates didn't import as expected, so none were removed; ${count - Math.max(before, 0)} new ones are at the end of the list until the next game start`);
			busy = false;
			return;
		}
		tries = 0;
		const base = count - total;
		const color = setting('mom_paint_color');
		const size = setting('mom_paint_size');
		const sound = setting('mom_paint_sound_enable');
		const putBack = () => {
			cmd(`mom_paint_color "${color}"`);
			cmd(`mom_paint_size ${size}`);
			cmd(`mom_paint_sound_enable ${sound}`);
		};
		cmd('mom_paint_sound_enable 0');
		let s = 0; // stroke
		let i = 0; // sample within it
		let at = base; // last savestate gone to, 1-based
		const step = () => {
			if (at > base) where(at - base);
			at++;
			if (i === 0) {
				// a stroke's first entry: there first, then the key, so no dot of its colour lands where the
				// last stroke ended
				cmd('-paint');
				// a crouched savestate gone to without +duck stands up over the next steps (probe, 2026-11-27)
				cmd(strokes[s][3] ? '+duck' : '-duck');
				cmd(`mom_paint_color "${strokes[s][0]}"`);
				cmd(`mom_paint_size ${strokes[s][1]}`);
				cmd(`mom_savestate_goto ${at}`);
				later(at === base + 1 ? SETTLE_MS : STEP_MS, () => {
					cmd('+paint');
					next();
				});
				return;
			}
			cmd(`mom_savestate_goto ${at}`);
			next();
		};
		const next = () => {
			i++;
			if (i >= strokes[s][2]) {
				s++;
				i = 0;
			}
			if (s < strokes.length) {
				later(STEP_MS, step);
				return;
			}
			later(STEP_MS, () => {
				where(total);
				cmd('-paint');
				cmd('-duck');
				putBack();
				removeFrom(base, base + total, t0, map, true);
			});
		};
		step();
	});
}

// Deletes the imported savestates (base+1 .. top) from the top, each only once the event says it is the
// current one (current is 0-based) and the list is as long as expected, so the player's own savestates are
// never touched: one made during the restore stops it. painted: the replay ran, so the track restarts
// (the replay teleported the player).
function removeFrom(base: number, top: number, t0: number, map: string, painted: boolean) {
	let k = top;
	const done = (ok: boolean) => {
		busy = false;
		log(ok ? 'RESTORE_END' : 'RESTORE_FAIL', { map, base, count, current, ms: Date.now() - t0 });
		if (ok && painted) {
			const n = STUCK[map] || 0;
			say(n ? `paint restored; ${n} points drawn inside walls (noclip) couldn't be placed and are off` : 'paint restored');
		}
		if (!ok) say(`stopped removing the imported paint savestates (${k - base} left, numbers ${base + 1}-${k}); they go at the next game start`);
		if (painted) cmd('mom_restart_track');
	};
	const del = () => {
		if (k <= base || count <= base) {
			done(true);
			return;
		}
		const go = current !== k - 1;
		if (go) cmd(`mom_savestate_goto ${k}`);
		later(go ? STEP_MS : 0, () => {
			if (current !== k - 1 || count !== k) {
				done(false);
				return;
			}
			cmd('mom_savestate_delete');
			k--;
			later(STEP_MS, del);
		});
	};
	del();
}

let tries = 0; // imports that added nothing since mk_loadpaint
const MAX_TRIES = 3;

log('LOADED', { map: mapName(), maps: Object.keys(PLAN).length });
$.Schedule(0, watch);
