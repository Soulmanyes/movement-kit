// Menu and timer marker, part of Soulmanyes's Movement Kit (strafe-trainer/panorama in the repo). Loaded
// next to timer.ts through the kit's timer.xml patch (movekit/panorama.py, strafe-trainer/install.py).
//
// Momentum's pause menu is its main menu over a loaded map: the map keeps running, so yaw.log gets no
// Host_ShutdownServer and the session can't tell from the map lines that the player is in a menu. The
// game tells the panels with ShowPauseMenu/HidePauseMenu (main-menu.ts); a HUD script gets them too
// (probe, 2026-11-13). This writes MK_MENU_ON/MK_MENU_OFF into the console, which the game logs to
// yaw.log; the kit's session (movekit/session.py) turns them into menu_shown/menu_hidden, and the
// Strafe Trainer stays silent in between (the wheel and space are jump keys, the cursor turns).
//
// MK_TIMER_ON/MK_TIMER_OFF: the timer runs on the player's own run (session: timer_started/
// timer_stopped), for the trainer's "Timer started" switch. A finish, reset or practice mode stops the
// timer; a replay or spectating shows someone else's timer, so those count as off. The own-run test is
// the Strafe Review recorder's (strafe-review.ts startAttempt), and it is checked again whenever
// spectating or the observed timer changes, since those can happen with the timer state unchanged.
//
// Both OFF on load: the HUD loads with each map, outside the menu and before a run, so a lost marker
// never keeps the trainer in the wrong state past the next map. No imports, like the other kit scripts.

// from common/timer.ts and the movement API (copied so this file has no imports)
const TIMER_RUNNING = 2;
const REPLAY_NONE = 0;
const MOVETYPE_OBSERVER = 10;

let timerOn = false;
let spectating = false; // MomentumSpectateStart/Stop; GetMoveType() covers a panorama_reload mid-spectate

function ownRunTiming() {
	return (
		MomentumTimerAPI.GetObservedTimerStatus().state === TIMER_RUNNING &&
		MomentumReplayAPI.GetReplayState() === REPLAY_NONE &&
		!MomentumTimerAPI.GetObservedRunMetadata() &&
		!spectating &&
		MomentumMovementAPI.GetMoveType() !== MOVETYPE_OBSERVER
	);
}

function onTimerState() {
	const on = ownRunTiming();
	if (on === timerOn) return;
	timerOn = on;
	$.Msg(on ? 'MK_TIMER_ON' : 'MK_TIMER_OFF');
}

$.RegisterForUnhandledEvent('ShowPauseMenu', () => $.Msg('MK_MENU_ON'));
$.RegisterForUnhandledEvent('HidePauseMenu', () => $.Msg('MK_MENU_OFF'));
$.RegisterForUnhandledEvent('OnObservedTimerStateChange', onTimerState);
$.RegisterForUnhandledEvent('OnObservedTimerReplaced', onTimerState);
$.RegisterForUnhandledEvent('ObserverTargetChanged', onTimerState);
$.RegisterForUnhandledEvent('MomentumSpectateStart', () => {
	spectating = true;
	onTimerState();
});
$.RegisterForUnhandledEvent('MomentumSpectateStop', () => {
	spectating = false;
	onTimerState();
});
$.Msg('MK_MENU_OFF');
$.Msg('MK_TIMER_OFF');
