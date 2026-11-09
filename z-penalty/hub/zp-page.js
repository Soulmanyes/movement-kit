// The Z Penalty section (z-penalty/hub_section.py): the desktop tone. Python loads it (load), checks and
// saves it (apply); the tone runner beside the game picks the change up. Shared parts: movekit/web/section.js.
"use strict";

(() => {
	const { $, toast, call, numberBox } = mk;
	let dirty = false;

	function setDirty(on) {
		dirty = on;
		$("zp-title").textContent = "Z Penalty" + (on ? " •" : "");
		$("zp-apply").disabled = !on;
	}

	function form() {
		return { on: $("zp-on").checked, pitch: parseFloat($("zp-pitch").dataset.last), volume: parseFloat($("zp-volume").dataset.last) };
	}

	function show(data) {
		$("zp-sub").textContent = "Version " + data.version;
		$("zp-problem").hidden = !data.problem;
		$("zp-problem").textContent = data.problem || "";
		$("zp-on").checked = data.tone.on;
		numberBox($("zp-pitch"), data.tone.pitch, data.pitch, () => setDirty(true));
		numberBox($("zp-volume"), data.tone.volume, data.volume, () => setDirty(true));
		$("zp-loading").hidden = true;
		$("zp-form").hidden = false;
		setDirty(false);
	}

	$("zp-on").onchange = () => setDirty(true);
	$("zp-play").onclick = async () => {
		const f = form();
		const ok = await call("preview", { pitch: f.pitch, volume: f.volume }, "Can't play");
		if (!ok) toast("Couldn't play the tone here", true);
	};
	$("zp-apply").onclick = async () => {
		$("zp-apply").disabled = true;
		try {
			show(await call("apply", { tone: form() }, "Not saved"));
			toast("Saved");
		} catch {
			$("zp-apply").disabled = false;
		}
	};

	mk.leaveGuard(() => dirty, "Z Penalty");
	call("load", {}, "Couldn't load").then(show);
})();
