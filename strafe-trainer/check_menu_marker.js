#!/usr/bin/env node
// Checks strafe-trainer/panorama/scripts/hud/movekit-menu.ts in node, with Panorama stubbed (types
// stripped, as z-penalty/check_z_penalty.js does).
//
// Usage: node strafe-trainer/check_menu_marker.js   (exits 1 on the first failure)
//
// Covers: both markers OFF on load; the pause menu markers; MK_TIMER_ON only for the player's own
// running timer, once per change; OFF on a finish or reset, a replay (replay state or run metadata),
// spectating (the spectate events or the observer move type), and each rechecked when spectating or
// the observed timer changes with the timer state the same.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { stripTypeScriptTypes } = require('module');

const TS = path.join(__dirname, 'panorama/scripts/hud/movekit-menu.ts');

function fail(msg) {
	console.error('FAIL: ' + msg);
	process.exit(1);
}
function expect(got, want, what) {
	const g = JSON.stringify(got);
	const w = JSON.stringify(want);
	if (g !== w) fail(`${what}:\n got  ${g}\n want ${w}`);
	console.log('ok   ' + what);
}

const game = { state: 0, replay: 0, meta: null, moveType: 2 };
const handlers = {};
const msgs = [];
const sandbox = {
	$: {
		Msg: (m) => msgs.push(m),
		RegisterForUnhandledEvent: (name, fn) => (handlers[name] = handlers[name] || []).push(fn)
	},
	MomentumTimerAPI: {
		GetObservedTimerStatus: () => ({ state: game.state }),
		GetObservedRunMetadata: () => game.meta
	},
	MomentumReplayAPI: { GetReplayState: () => game.replay },
	MomentumMovementAPI: { GetMoveType: () => game.moveType }
};
function fire(name) {
	if (!handlers[name]) fail(`no handler for ${name}`);
	handlers[name].forEach((fn) => fn());
}
function take() {
	return msgs.splice(0);
}

vm.runInNewContext(stripTypeScriptTypes(fs.readFileSync(TS, 'utf8')), sandbox, { filename: TS });
expect(take(), ['MK_MENU_OFF', 'MK_TIMER_OFF'], 'both OFF on load');

fire('ShowPauseMenu');
fire('HidePauseMenu');
expect(take(), ['MK_MENU_ON', 'MK_MENU_OFF'], 'pause menu markers');

game.state = 1; // primed in the start zone
fire('OnObservedTimerStateChange');
expect(take(), [], 'primed: still off');
game.state = 2;
fire('OnObservedTimerStateChange');
expect(take(), ['MK_TIMER_ON'], 'own timer running: ON');
fire('OnObservedTimerStateChange');
expect(take(), [], 'no second ON');
game.state = 3;
fire('OnObservedTimerStateChange');
expect(take(), ['MK_TIMER_OFF'], 'finish: OFF');
game.state = 0;
fire('OnObservedTimerStateChange');
expect(take(), [], 'reset after a finish: no second OFF');

game.state = 2;
fire('OnObservedTimerStateChange');
take();
fire('MomentumSpectateStart');
expect(take(), ['MK_TIMER_OFF'], 'spectating a running player: OFF without a timer change');
fire('ObserverTargetChanged');
expect(take(), [], 'another target, still spectating: nothing');
fire('MomentumSpectateStop');
expect(take(), ['MK_TIMER_ON'], 'back to an own running timer: ON');

game.moveType = 10;
fire('ObserverTargetChanged');
expect(take(), ['MK_TIMER_OFF'], 'observer move type (reload mid-spectate): OFF');
game.moveType = 2;
fire('ObserverTargetChanged');
take();

game.meta = { filePath: 'x.mtv' };
fire('OnObservedTimerReplaced');
expect(take(), ['MK_TIMER_OFF'], 'observed timer replaced by a replay run: OFF');
game.meta = null;
game.replay = 1;
fire('OnObservedTimerStateChange');
expect(take(), [], 'replay playing: stays off');
game.replay = 0;
fire('OnObservedTimerStateChange');
expect(take(), ['MK_TIMER_ON'], 'replay closed, own timer running: ON');

console.log('check_menu_marker: all passed');
