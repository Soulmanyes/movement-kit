// The Surf Sound section (surf-sound/hub_section.py): the desktop sound. Python loads it (load), checks
// and saves it (apply); the sound runner beside the game picks the change up. Shared parts:
// movekit/web/section.js.
"use strict";

(() => {
	const { $, toast, call, numberBox } = mk;
	const SLOTS = ["ramp", "ceiling", "wall", "graze", "bonk"];
	let dirty = false;
	let custom = {}; // the page's custom sounds, {slot: {file, name}}: saved by Apply

	function setDirty(on) {
		dirty = on;
		$("ss-title").textContent = "Surf Sound" + (on ? " •" : "");
		$("ss-apply").disabled = !on;
	}

	function form() {
		return {
			on: $("ss-on").checked, sound: $("ss-sound").value, volume: parseFloat($("ss-volume").dataset.last),
			ramp: $("ss-ramp").checked, ceiling: $("ss-ceiling").checked,
			wall: $("ss-wall").checked, graze: $("ss-graze").checked, bonk: $("ss-bonk").checked,
			watch: $("ss-watch").checked, custom
		};
	}

	function showCustom() {
		for (const slot of SLOTS) {
			const c = custom[slot];
			$("ss-file-" + slot).textContent = c ? c.name : "Built-in";
			$("ss-file-" + slot).title = c ? c.name : "";
			$("ss-clear-" + slot).hidden = !c;
		}
	}

	function show(data) {
		$("ss-sub").textContent = "Version " + data.version;
		$("ss-problem").hidden = !data.problem;
		$("ss-problem").textContent = data.problem || "";
		const sel = $("ss-sound");
		sel.replaceChildren(...data.sounds.map(([key, label]) => new Option(label, key)));
		sel.value = data.sound.sound;
		$("ss-on").checked = data.sound.on;
		$("ss-ramp").checked = data.sound.ramp;
		$("ss-ceiling").checked = data.sound.ceiling;
		$("ss-wall").checked = data.sound.wall;
		$("ss-graze").checked = data.sound.graze;
		$("ss-bonk").checked = data.sound.bonk;
		custom = { ...data.sound.custom };
		showCustom();
		$("ss-watch").checked = data.sound.watch;
		numberBox($("ss-volume"), data.sound.volume, data.volume, () => setDirty(true));
		$("ss-loading").hidden = true;
		$("ss-form").hidden = false;
		setDirty(false);
	}

	for (const id of ["ss-on", "ss-sound", "ss-ramp", "ss-ceiling", "ss-wall", "ss-graze", "ss-bonk", "ss-watch"]) $(id).onchange = () => setDirty(true);
	for (const slot of SLOTS) {
		$("ss-pick-" + slot).onclick = async () => {
			$("ss-pick-" + slot).disabled = true;
			try {
				const got = await call("pick_sound", { slot }, "Can't use that file");
				if (got && got.custom) {
					custom = { ...custom, [slot]: got.custom };
					showCustom();
					setDirty(true);
				}
			} catch {
				// call() showed the error
			} finally {
				$("ss-pick-" + slot).disabled = false;
			}
		};
		$("ss-clear-" + slot).onclick = () => {
			const { [slot]: _gone, ...rest } = custom;
			custom = rest;
			showCustom();
			setDirty(true);
		};
	}
	async function play(kind) {
		const f = form();
		const ok = await call("preview", { sound: f.sound, volume: f.volume, kind, custom }, "Can't play");
		if (!ok) toast("Couldn't play the sound here", true);
	}
	$("ss-play").onclick = () => play("ramp");
	$("ss-play-ceil").onclick = () => play("ceiling");
	$("ss-play-wall").onclick = () => play("wall3");
	$("ss-play-bonk").onclick = () => play("bonk");
	$("ss-play-graze").onclick = () => play("graze");
	$("ss-apply").onclick = async () => {
		$("ss-apply").disabled = true;
		try {
			show(await call("apply", { sound: form() }, "Not saved"));
			toast("Saved");
		} catch {
			$("ss-apply").disabled = false;
		}
	};

	mk.leaveGuard(() => dirty, "Surf Sound");
	call("load", {}, "Couldn't load").then(show);
})();
