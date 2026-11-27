#!/usr/bin/env node
// Checks paint-saver/panorama/scripts/hud/movekit-paint-saver.ts in node, with Panorama and the game's
// savestate list stubbed (types stripped, as z-penalty/check_z_penalty.js does), on a virtual clock.
//
// Usage: node paint-saver/check_paint_saver.js   (exits 1 on the first failure)
//
// Covers: recording (MK_PAINT_DOWN with colour and size, one MK_PAINT_S per SAMPLE_MS each followed by its
// getpos, MK_PAINT_UP); mk_savepaint / mk_clearpaint (the marker, hostname reset); mk_loadpaint on a map
// with a plan (never by itself on load): import, each stroke painted with its colour and size at its entries in order, nothing
// recorded meanwhile, the imported entries deleted and the player's own kept, settings put back, the
// track restarted; once per map load, again after a reload; a missing block deletes nothing, nor does a block that
// doesn't match the plan; a map without a plan does nothing.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { stripTypeScriptTypes } = require('module');

const TS = path.join(__dirname, 'panorama/scripts/hud/movekit-paint-saver.ts');
const PLAN = { surf_a: [['1 0 0 255', '2', 3, 0], ['0 0 1 255', '4', 2, 1]] };

function fail(msg) {
	console.error('FAIL: ' + msg);
	process.exit(1);
}
function expect(got, want, what) {
	const g = JSON.stringify(got);
	const w = JSON.stringify(want);
	if (g !== w) fail(`${what}:\n got  ${g}\n want ${w}`);
}

function world(blocks, map) {
	const w = {
		now: 0, timers: [], handlers: {}, msgs: [], cmds: [], painted: [], where: [],
		settings: { hostname: 'Momentum', mom_paint_color: '9 9 9 255', mom_paint_size: '1', mom_paint_sound_enable: '1' },
		list: ['own1', 'own2'], cur: 1, map, paint: false, restarts: 0,
	};
	const fire = () => w.timers.push({ at: w.now + 5, f: () => (w.handlers.OnSaveStateUpdate || []).forEach((h) => h(w.list.length, w.cur, false)) });
	w.command = (c) => {
		w.cmds.push(c);
		let m;
		if ((m = c.match(/^hostname (\S+)$/))) w.settings.hostname = m[1];
		else if ((m = c.match(/^(mom_paint_\w+) "?([^"]*)"?$/))) w.settings[m[1]] = m[2];
		else if (c === '+paint') {
			// the key paints every tick while held; the check counts a mark per position reached with it held
			w.paint = true;
			w.painted.push([w.list[w.cur], w.settings.mom_paint_color, w.settings.mom_paint_size, w.settings.mom_paint_sound_enable]);
		}
		else if (c === '-paint') w.paint = false;
		else if (c === 'getpos') {
			w.msgs.push('setpos 1 2 3;setang 4 5 0');
			w.where.push(w.list[w.cur]); // the savestate the player is at when getpos answers
		}
		else if (c === 'mom_restart_track') w.restarts++;
		else if ((m = c.match(/^mom_saveloc_import (\S+)$/))) {
			if (blocks[m[1]]) {
				w.list.push(...blocks[m[1]]);
				fire();
			}
		} else if ((m = c.match(/^mom_savestate_goto (\d+)$/))) {
			const k = Number(m[1]);
			if (k < 1 || k > w.list.length) return;
			w.cur = k - 1;
			if (w.paint) w.painted.push([w.list[w.cur], w.settings.mom_paint_color, w.settings.mom_paint_size, w.settings.mom_paint_sound_enable]);
			fire();
		} else if (c === 'mom_savestate_last') {
			if (!w.list.length) return; // assumed: nothing to go to, no event
			w.cur = w.list.length - 1;
			fire();
		} else if (c === 'mom_savestate_delete') {
			w.list.splice(w.cur, 1);
			w.cur = Math.min(w.cur, w.list.length - 1);
			fire();
		}
	};
	const ctx = {
		$: {
			Msg: (s) => w.msgs.push(s),
			Schedule: (sec, f) => w.timers.push({ at: w.now + Math.max(sec * 1000, 1), f }),
			RegisterForUnhandledEvent: (name, h) => (w.handlers[name] = w.handlers[name] || []).push(h),
		},
		GameInterfaceAPI: { ConsoleCommand: (c) => w.command(c), GetSettingString: (n) => w.settings[n] ?? '' },
		MapCacheAPI: { GetMapName: () => w.map },
		MomentumPlayerAPI: { IsDucking: () => false },
		Date: { now: () => w.now },
		JSON, Object, String, Number,
	};
	w.run = (ms) => {
		const end = w.now + ms;
		for (;;) {
			w.timers.sort((a, b) => a.at - b.at);
			if (!w.timers.length || w.timers[0].at > end) break;
			const t = w.timers.shift();
			w.now = t.at;
			t.f();
		}
		w.now = end;
	};
	w.event = (name) => (w.handlers[name] || []).forEach((h) => h());
	w.create = (id) => {
		w.list.push(id);
		w.cur = w.list.length - 1;
		fire();
	};
	w.fire = fire;
	const src = fs.readFileSync(TS, 'utf8').replace('/*MK_PLAN*/ {}', JSON.stringify(PLAN));
	vm.runInNewContext(stripTypeScriptTypes(src), ctx);
	if (map) fire(); // the game's event on map load
	return w;
}

// the player loads `map` with `list` as its savestates; the game's load event only when `event`
function travel(w, map, list, event) {
	w.map = map;
	w.list = list;
	w.cur = list.length - 1;
	w.event('LevelInitPostEntity');
	if (event) w.fire();
}

const marks = (w) => w.msgs.filter((m) => m.startsWith('MK_PAINT_')).map((m) => m.split(' ')[0].slice(9));
const block = ['p1', 'p2', 'p3', 'p4', 'p5'];
const go = (w) => (w.settings.hostname = 'mkpaintrestore'); // mk_loadpaint
const said = (w) => w.cmds.filter((c) => c.startsWith('echo'));

// mk_loadpaint, then recording and the commands
{
	const w = world({ zzpaint_surf_a: block }, 'surf_a');
	w.run(10000);
	expect(w.cmds.filter((c) => c.startsWith('mom_')), [], 'no restore without the command');
	go(w);
	w.run(510); // the import is checked 500 ms after it, then the replay starts
	w.settings.hostname = 'mkpaint1'; // the key held during the replay: nothing recorded
	w.run(90);
	expect(marks(w).filter((m) => ['DOWN', 'S', 'UP'].includes(m)), [], 'nothing recorded during the restore');
	w.settings.hostname = 'mkpaint0';
	w.run(3400);
	expect(w.painted, [
		['p1', '1 0 0 255', '2', '0'], ['p2', '1 0 0 255', '2', '0'], ['p3', '1 0 0 255', '2', '0'],
		['p4', '0 0 1 255', '4', '0'], ['p5', '0 0 1 255', '4', '0']], 'strokes painted in order with their colour and size, sound off');
	const rs = w.msgs.filter((m) => m.startsWith('MK_PAINT_R ')).map((m) => JSON.parse(m.slice(11)).k);
	expect(rs, [1, 2, 3, 4, 5], 'every replayed point read once, the last one too');
	expect(w.where, block, 'each read at its own point');
	const ducks = w.cmds.filter((c) => /^[+-]duck$|^mom_savestate_goto/.test(c)).slice(0, 8);
	expect(ducks, ['-duck', 'mom_savestate_goto 3', 'mom_savestate_goto 4', 'mom_savestate_goto 5', '+duck',
		'mom_savestate_goto 6', 'mom_savestate_goto 7', '-duck'], 'duck held through the crouched stroke only');
	w.run(30000);
	expect(w.list, ['own1', 'own2'], 'imported entries deleted, own kept');
	expect([w.settings.mom_paint_color, w.settings.mom_paint_size, w.settings.mom_paint_sound_enable], ['9 9 9 255', '1', '1'], 'settings put back');
	expect(w.restarts, 1, 'track restarted once');
	expect(marks(w).includes('RESTORE_END'), true, 'restore end logged');
	expect(w.settings.hostname, 'mkpaint0', 'hostname reset after restore');
	expect(said(w).some((c) => c.includes('paint restored')), true, 'done message');

	w.msgs.length = 0;
	w.settings.hostname = 'mkpaint1';
	w.settings.mom_paint_color = '5 5 5 255';
	w.run(100);
	w.settings.hostname = 'mkpaint0';
	w.run(50);
	const m = w.msgs.filter((x) => !x.startsWith('MK_PAINT_LOADED'));
	expect(m[0], 'MK_PAINT_DOWN {"c":"5 5 5 255","s":"1"}', 'stroke start with colour and size');
	expect(m[m.length - 1], 'MK_PAINT_UP', 'stroke end');
	const samples = m.slice(1, -1);
	if (samples.length < 10) fail(`too few samples: ${samples.length}`);
	for (let i = 0; i < samples.length; i += 2) {
		expect([samples[i], samples[i + 1]], ['MK_PAINT_S {"d":0}', 'setpos 1 2 3;setang 4 5 0'], `sample ${i / 2}: marker then getpos`);
	}
	w.msgs.length = 0;
	w.settings.hostname = 'mkpaintsave';
	w.run(50);
	expect(marks(w), ['SAVE'], 'save marker');
	expect(w.settings.hostname, 'mkpaint0', 'hostname reset');
	w.settings.hostname = 'mkpaintclear';
	w.run(50);
	expect(marks(w), ['SAVE', 'CLEAR'], 'clear marker');

	// a reload doesn't restore; the command again does
	w.event('LevelInitPostEntity');
	w.run(10000);
	expect(w.painted.length, 5, 'no restore on a reload');
	go(w);
	w.run(40000);
	expect(w.painted.length, 10, 'restored again on the command');
	expect(w.list, ['own1', 'own2'], 'own kept after the second restore');
	expect(w.restarts, 2, 'track restarted again');
}

// the first import adds nothing (as in game after a start): tried again quietly, then restored
{
	const w = world({ zzpaint_surf_a: block }, 'surf_a');
	const real = w.command;
	let ignored = 0;
	w.command = (c) => (c.startsWith('mom_saveloc_import') && !ignored++ ? w.cmds.push(c) : real(c));
	go(w);
	w.run(40000);
	expect(w.painted.length, 5, 'a first import that adds nothing: retried and painted');
	expect(w.list, ['own1', 'own2'], 'retry: own kept');
	expect(said(w).filter((c) => c.includes('could not')), [], 'retry: no error message');
}

// no block in savedlocs.txt: tried MAX_TRIES times more, then reported; nothing deleted
{
	const w = world({}, 'surf_a');
	go(w);
	w.run(30000);
	expect(w.cmds.filter((c) => c.startsWith('mom_saveloc_import')).length, 4, 'missing block: 1 try + 3 retries');
	expect(w.list, ['own1', 'own2'], 'missing block: list unchanged');
	expect(w.cmds.filter((c) => c.includes('delete') || c === '+paint'), [], 'missing block: no paint, no delete');
	expect(marks(w).includes('RESTORE_FAIL'), true, 'missing block logged');
}

// a block that doesn't match the plan: nothing deleted, nothing painted
{
	const w = world({ zzpaint_surf_a: ['p1', 'p2', 'p3'] }, 'surf_a');
	go(w);
	w.run(20000);
	expect(w.list, ['own1', 'own2', 'p1', 'p2', 'p3'], 'mismatched block: nothing deleted');
	expect(w.painted, [], 'mismatched block not painted');
	expect(w.restarts, 0, 'no restart without a replay');
}

// a savestate made during the replay stops the deletes: it and the player's others stay
{
	const w = world({ zzpaint_surf_a: block }, 'surf_a');
	w.run(100);
	go(w);
	w.run(550);
	w.create('mine');
	w.run(30000);
	for (const id of ['own1', 'own2', 'mine']) expect(w.list.includes(id), true, `${id} kept after a savestate made mid-replay`);
	expect(marks(w).includes('RESTORE_FAIL'), true, 'mid-replay savestate: deletes stopped');
}

// a savestate made right after the command, before the import is checked: kept
{
	const w = world({ zzpaint_surf_a: block }, 'surf_a');
	w.run(100);
	go(w);
	w.run(200);
	w.create('mine');
	w.run(30000);
	for (const id of ['own1', 'own2', 'mine']) expect(w.list.includes(id), true, `${id} kept after a savestate made during the import`);
}

// a count from the previous map, no load event on this one: the script asks (mom_savestate_last) first
for (const [name, blocks, list, want] of [
	['matching block', { zzpaint_surf_a: block }, ['a1', 'a2', 'a3'], 5],
	['matching block, empty list (no event for last)', { zzpaint_surf_a: block }, [], 5],
	['mismatched block', { zzpaint_surf_a: ['p1', 'p2'] }, ['a1', 'a2', 'a3'], 0],
	['mismatched block, empty list', { zzpaint_surf_a: ['p1', 'p2', 'p3', 'p4', 'p5', 'p6'] }, [], 0],
]) {
	const w = world(blocks, 'surf_x'); // own1, own2 on surf_x: count 2 there
	w.run(5000);
	travel(w, 'surf_a', list, false);
	w.run(5000);
	go(w);
	w.run(30000);
	expect(w.painted.length, want, `stale count, ${name}: marks`);
	for (const id of list) expect(w.list.includes(id), true, `stale count, ${name}: ${id} kept`);
	if (want) expect(w.list, list, `stale count, ${name}: imported entries gone`);
}

// a map without a plan
{
	const w = world({ zzpaint_surf_a: block }, 'surf_b');
	go(w);
	w.run(10000);
	expect(w.cmds.filter((c) => c.startsWith('mom_')), [], 'no plan: no commands');
	expect(said(w).some((c) => c.includes('no saved paint')), true, 'no plan: said so');
}

console.log('check_paint_saver.js: all passed');
