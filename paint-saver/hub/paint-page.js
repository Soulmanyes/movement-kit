// The Paint Saver section (paint-saver/hub_section.py): its two switches, saved as soon as they change
// (set_options), the saved paint per map and the Steam launch option. Shared parts: movekit/web/section.js.
"use strict";

(() => {
	const { $, el, call, copy, toast } = mk;
	let loadOn = false; // mk_loadpaint works: saving on, or loading while it's off

	function showLaunch(l) {
		$("ps-launch").textContent = l.text;
		$("ps-launch-note").textContent = l.note;
	}

	function showSaved(maps) {
		const box = $("ps-saved");
		box.replaceChildren();
		if (!maps.length) {
			box.textContent = "None yet.";
			return;
		}
		box.classList.remove("muted");
		for (const m of maps) {
			const parts = [`${m.strokes} stroke${m.strokes === 1 ? "" : "s"}, ${m.points} points`,
				!loadOn ? "loading is off" : m.ready ? "mk_loadpaint brings it back" : "comes back after the next game start"];
			if (m.stuck) parts.push(`${m.stuck} points couldn't be placed`);
			box.append(el("div", { className: "ps-map" }, el("b", { textContent: m.map }),
				el("span", { className: "muted", textContent: parts.join(" · ") })));
		}
	}

	function show(data) {
		$("ps-sub").textContent = "Version " + data.version;
		$("ps-problem").hidden = !data.problem;
		$("ps-problem").textContent = data.problem || "";
		$("ps-save").checked = data.settings.save;
		$("ps-load-off").checked = data.settings.load_off;
		loadOn = data.settings.save || data.settings.load_off;
		showSaved(data.saved);
		showLaunch(data.launch);
	}

	async function setOptions() {
		const box = [$("ps-save"), $("ps-load-off")];
		box.forEach((b) => (b.disabled = true));
		try {
			show(await call("set_options", { save: $("ps-save").checked, load_off: $("ps-load-off").checked }, "Not saved"));
			toast("Saved. It takes effect at the next game start");
		} catch {
			call("load", {}, "Couldn't load").then(show);
		} finally {
			box.forEach((b) => (b.disabled = false));
		}
	}
	// the three buttons: Python sends the command to the open game and reads its answer from yaw.log
	async function run(what) {
		if (what === "clear" && !confirm("Delete the saved paint of the map you are on? Paint on screen stays until the map reloads."))
			return;
		const out = $("ps-run-out");
		const buttons = ["save", "load", "clear"].map((w) => $("ps-run-" + w));
		buttons.forEach((b) => (b.disabled = true));
		out.replaceChildren();
		try {
			const r = await call("run", { what }, "Not sent");
			for (const [i, m] of r.messages.entries()) {
				// not sent: the last line is the command to type, click to copy
				out.append(!r.sent && i === r.messages.length - 1
					? el("div", {}, el("code", { textContent: m, title: "Copy", onclick: () => copy(m) }))
					: el("div", { textContent: m }));
			}
			if (r.sent) call("load", {}, "Couldn't load").then(show);
		} finally {
			buttons.forEach((b) => (b.disabled = false));
		}
	}
	for (const w of ["save", "load", "clear"]) $("ps-run-" + w).onclick = () => run(w);

	$("ps-save").onchange = setOptions;
	$("ps-load-off").onchange = setOptions;

	$("ps-launch-refresh").onclick = async () => showLaunch(await call("launch_option", {}, "Couldn't read Steam"));
	$("ps-launch-copy").onclick = () => copy($("ps-launch").textContent);
	call("load", {}, "Couldn't load").then(show);
})();
