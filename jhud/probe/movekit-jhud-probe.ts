// Movement Kit JHUD probe (Phase 5.1 in PLAN.md; throwaway, never released). Loaded next to timer.ts
// through the kit's timer.xml patch. Logs [panorama] JHUDPROBE lines to yaw.log and answers:
// 1. does a panel made here join the HUD customizer when hud_default.kv3 comes from a custom/ folder?
// 2. do OnJumpStarted + GetLastJumpStats() fire (bhop and surf), and when does jumpCount reset?
// No imports, like the Strafe Review recorder.

const TAG = 'JHUDPROBE';
const ID = 'MovekitJhud';
const COLOR_PICKER = 5; // CustomizerPropertyType in common/hud-customizer.ts
const NUMBER_ENTRY = 1;

function log(what: string, data?: unknown) {
	$.Msg(`${TAG} ${what}${data === undefined ? '' : ' ' + JSON.stringify(data)}`);
}

const ctx = $.GetContextPanel();
const root = ctx.GetParent() ?? ctx;
root.FindChildTraverse(ID)?.DeleteAsync(0);
const panel = $.CreatePanel('Panel', root, ID, { style: 'flow-children: down; width: 300px;' });
const label = $.CreatePanel('Label', panel, 'MovekitJhudText', {
	text: 'JHUD probe',
	style: 'horizontal-align: center; font-size: 22px; font-weight: bold; color: #ffffff; text-shadow: 0px 1px 4px 2px rgba(0, 0, 0, 0.9);'
});
let green = 95;

const props = {
	name: 'JHUD (probe)',
	resizeX: true,
	resizeY: false,
	dynamicStyles: {
		fontColor: { name: 'Font colour', type: COLOR_PICKER, targetPanel: '#MovekitJhudText', styleProperty: 'color' },
		gainGreen: {
			name: 'Green from gain %',
			type: NUMBER_ENTRY,
			callbackFunc: (_: unknown, v: number) => {
				green = v;
				log('setting', { gainGreen: v });
			}
		}
	}
};

log('load', { root: root.id, type: root.paneltype, handler: !!UiToolkitAPI.GetGlobalObject()['HudCustomizerHandler'] });

$.RegisterForUnhandledEvent('HudCustomizer_Ready', () => {
	try {
		const h = UiToolkitAPI.GetGlobalObject()['HudCustomizerHandler'] as any;
		h.loadComponent(panel, props);
		log('ready', {
			mode: GameModeAPI.GetCurrentGameMode(),
			joined: !!(h.components && h.components[ID]),
			enabled: panel.enabled,
			visible: panel.visible
		});
	} catch (e) {
		log('ready error', String(e));
	}
});

$.RegisterForUnhandledEvent('OnJumpStarted', () => {
	try {
		const s = MomentumMovementAPI.GetLastJumpStats() as any;
		const gain = s.speedGain * 100;
		label.text = `${s.jumpCount}: ${s.takeoffSpeed.toFixed(0)} (${s.jumpSpeedDelta >= 0 ? '+' : ''}${s.jumpSpeedDelta.toFixed(0)})  ${gain.toFixed(1)} %`;
		label.style.color = gain >= green ? '#7bd88f' : '#ffffff';
		log('jump', {
			mode: GameModeAPI.GetCurrentGameMode(),
			timer: MomentumTimerAPI.GetObservedTimerStatus().state,
			n: s.jumpCount,
			takeoff: s.takeoffSpeed,
			delta: s.jumpSpeedDelta,
			gain: s.speedGain,
			sync: s.strafeSync,
			strafes: s.strafeCount,
			ratio: s.yawRatio,
			eff: s.efficiency,
			height: s.heightDelta,
			dist: s.distance,
			dt: s.timeDelta
		});
	} catch (e) {
		log('jump error', String(e));
	}
});

$.RegisterForUnhandledEvent('OnObservedTimerStateChange', () => {
	try {
		log('timer', { state: MomentumTimerAPI.GetObservedTimerStatus().state, n: (MomentumMovementAPI.GetLastJumpStats() as any).jumpCount });
	} catch (e) {
		log('timer error', String(e));
	}
});
