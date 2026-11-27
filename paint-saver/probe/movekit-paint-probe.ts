// Movement Kit Paint Saver probe (throwaway, never released). Loaded next to timer.ts through the kit's
// timer.xml patch. Logs MK_PPROBE lines to the console and yaw.log.
// Run 1 (2026-11-27): mom_savestate_goto is 1-based; holding +paint while going through savestates paints
//   at each; GetButtons() never shows the PAINT bit.
// Run 2: a bind setting hostname mkpaint1/mkpaint0 signals paint held; ConsoleCommand('getpos') once a
//   tick lands a "setpos ...;setang ..." line right after each marker (movekit-paint-probe.ts.run2).
// Run 3 (this one): savedlocs.txt holds a zzpaint_surf_ruse block (EXPECT entries, written while the game
//   was closed). On surf_ruse, 3 s after load: import it, check the count rises by EXPECT, replay every
//   entry with +paint held (STEP_MS each, paint sound off), delete the imported entries from the top down
//   (never below the count from before the import), then mom_restart_track.
// No imports, like the Strafe Review recorder.

const TAG = 'MK_PPROBE';
const EXPECT = 359;
const STEP_MS = 15;
const BLOCK = 'zzpaint_surf_ruse';

function log(what: string, data?: unknown) {
	$.Msg(`${TAG} ${what}${data === undefined ? '' : ' ' + JSON.stringify(data)}`);
}

function cmd(c: string) {
	try {
		GameInterfaceAPI.ConsoleCommand(c);
	} catch (e) {
		log('cmd failed', { c, e: String(e) });
	}
}

let count = -1;
let current = -1;
let events = 0;
$.RegisterForUnhandledEvent('OnSaveStateUpdate', (c: number, cur: number, menu: boolean) => {
	count = c;
	current = cur;
	events++;
	if (events <= 3 || events % 100 === 0) log('ss', { count: c, current: cur, menu, events });
});

function later(ms: number, f: () => void) {
	$.Schedule(ms / 1000, f);
}

function run() {
	const map = MapCacheAPI.GetMapName();
	if (map !== 'surf_ruse') {
		log('skip', { map });
		return;
	}
	const seen = events;
	const t0 = Date.now();
	log('import start', { count, events });
	cmd(`mom_saveloc_import ${BLOCK}`);
	later(500, () => {
		log('import result', { count, current, newEvents: events - seen });
		if (events === seen || count < EXPECT) {
			log('import failed: nothing to replay');
			return;
		}
		const base = count - EXPECT;
		const sound = GameInterfaceAPI.GetSettingString('mom_paint_sound_enable');
		cmd('mom_paint_sound_enable 0');
		cmd('+paint');
		let i = 1;
		const t1 = Date.now();
		const step = () => {
			cmd(`mom_savestate_goto ${base + i}`);
			i++;
			if (i <= EXPECT) {
				later(STEP_MS, step);
				return;
			}
			later(STEP_MS, () => {
				cmd('-paint');
				log('replay end', { base, count, current, ms: Date.now() - t1 });
				let k = base + EXPECT;
				const del = () => {
					if (k <= base || count <= base) {
						log('delete end', { base, count, current, ms: Date.now() - t0 });
						cmd(`mom_paint_sound_enable ${sound}`);
						cmd('mom_restart_track');
						return;
					}
					cmd(`mom_savestate_goto ${k}`);
					// delete only once the event says the imported entry is current (current is 0-based)
					later(STEP_MS, () => {
						if (current !== k - 1) {
							log('delete aborted: wrong current', { k, current, count });
							cmd(`mom_paint_sound_enable ${sound}`);
							return;
						}
						cmd('mom_savestate_delete');
						k--;
						later(STEP_MS, del);
					});
				};
				del();
			});
		};
		step();
	});
}

// The HUD script loads in the main menu and lives across maps (run 3, first try: the import ran during the
// map load), so poll until surf_ruse is the map, then wait 3 s for the spawn and run once.
let started = false;
function waitForMap() {
	if (!started && MapCacheAPI.GetMapName() === 'surf_ruse') {
		started = true;
		log('map ready', { count, events });
		later(3000, run);
		return;
	}
	later(1000, waitForMap);
}

log('loaded', { map: MapCacheAPI.GetMapName() });
waitForMap();
