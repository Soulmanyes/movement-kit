// The Z Penalty section (z-penalty/hub_section.py): the in-game sound. Python loads it (load), checks
// and saves it and writes it into the game's copy of the panel (apply). Shared parts: movekit/web/section.js.
"use strict";

(() => {
	const { $, toast, call, options, numberBox } = mk;
	let dirty = false;

	function setDirty(on) {
		dirty = on;
		$("zp-title").textContent = "Z Penalty" + (on ? " •" : "");
		$("zp-apply").disabled = !on;
	}

	function form() {
		return { on: $("zp-on").checked, name: $("zp-name").value, volume: parseFloat($("zp-volume").dataset.last) };
	}

	function show(data) {
		$("zp-sub").textContent = "Version " + data.version;
		$("zp-problem").hidden = !data.problem;
		$("zp-problem").textContent = data.problem || "";
		$("zp-on").checked = data.sound.on;
		options($("zp-name"), data.sounds.map((s) => [s, s]), data.sound.name);
		numberBox($("zp-volume"), data.sound.volume, data.volume, () => setDirty(true));
		$("zp-loading").hidden = true;
		$("zp-form").hidden = false;
		setDirty(false);
	}

	$("zp-on").onchange = () => setDirty(true);
	$("zp-name").onchange = () => setDirty(true);
	$("zp-play").onclick = async () => {
		const ok = await call("preview", { name: $("zp-name").value }, "Can't play");
		if (!ok) toast("Couldn't play that sound here", true);
	};
	$("zp-apply").onclick = async () => {
		$("zp-apply").disabled = true;
		try {
			const got = await call("apply", { sound: form() }, "Not saved");
			show(got);
			toast(got.written ? "Saved. In a running game, type panorama_reload in the console." : "Saved");
		} catch {
			$("zp-apply").disabled = false;
		}
	};

	mk.leaveGuard(() => dirty, "Z Penalty");
	call("load", {}, "Couldn't load").then(show);
})();
