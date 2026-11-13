// Menu marker, part of Soulmanyes's Movement Kit (strafe-trainer/panorama in the repo). Loaded next to
// timer.ts through the kit's timer.xml patch (movekit/panorama.py, strafe-trainer/install.py).
//
// Momentum's pause menu is its main menu over a loaded map: the map keeps running, so yaw.log gets no
// Host_ShutdownServer and the session can't tell from the map lines that the player is in a menu. The
// game tells the panels with ShowPauseMenu/HidePauseMenu (main-menu.ts); a HUD script gets them too
// (probe, 2026-11-13). This writes MK_MENU_ON/MK_MENU_OFF into the console, which the game logs to
// yaw.log; the kit's session (movekit/session.py) turns them into menu_shown/menu_hidden, and the
// Strafe Trainer stays silent in between (the wheel and space are jump keys, the cursor turns).
//
// MK_MENU_OFF on load: the HUD loads with each map, outside the menu, so a lost marker never keeps the
// trainer quiet past the next map. No imports, like the other kit scripts.

$.RegisterForUnhandledEvent('ShowPauseMenu', () => $.Msg('MK_MENU_ON'));
$.RegisterForUnhandledEvent('HidePauseMenu', () => $.Msg('MK_MENU_OFF'));
$.Msg('MK_MENU_OFF');
