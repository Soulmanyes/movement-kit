// The HUD section: in-game display settings (hud/hub_section.py). The jump-1 line is drawn by
// Strafe Review's recorder; saving it also writes it into the installed recorder.
"use strict";

(() => {
	const $ = (id) => document.getElementById(id);
	const RECORDER = {
		"not installed": "Strafe Review's recorder isn't installed yet; the setting applies once it is.",
		"no game": "Momentum Mod wasn't found; the setting applies once the recorder is installed.",
	};

	function note(text, error = false) {
		const el = $("hud-line-note");
		el.textContent = text;
		el.className = "hud-note " + (error ? "error" : "muted");
	}

	async function load() {
		const box = $("hud-line");
		try {
			const st = await hub.call("get");
			$("hud-line-card").hidden = !st.strafeReview;
			box.checked = st.inGameLine;
			box.disabled = false;
			note(RECORDER[st.recorder] || "");
		} catch (e) {
			note("Couldn't read the settings: " + e.message, true);
		}
	}

	const STATE = { applied: "applied", present: "already in the file", skipped: "left out" };

	async function patches() {
		const list = $("hud-patches");
		const out = $("hud-patches-note");
		try {
			const st = await hub.call("panorama_status");
			list.replaceChildren(...st.patches.map((p) => {
				const li = document.createElement("li");
				const name = document.createElement("span");
				name.textContent = `${p.tool}: ${p.file.split("/").pop()}`;
				const state = document.createElement("span");
				state.className = "hud-state " + p.state;
				state.textContent = STATE[p.state] || p.state;
				li.append(name, state);
				if (p.reason) {
					const why = document.createElement("div");
					why.className = "muted";
					why.textContent = p.reason;
					li.append(why);
				}
				return li;
			}));
			out.textContent = !st.game ? "Momentum Mod wasn't found."
				: st.warnings.length ? st.warnings.join("\n")
				: st.patches.length ? "" : "No installed tool changes a game file.";
			out.className = "hud-note " + (st.game && st.warnings.length ? "error" : "muted");
		} catch (e) {
			out.textContent = "Couldn't read the patched files: " + e.message;
			out.className = "hud-note error";
		}
	}

	$("hud-line").addEventListener("change", async (ev) => {
		const box = ev.target;
		box.disabled = true;
		try {
			const got = await hub.call("set_line", { on: box.checked });
			box.checked = got.inGameLine;
			note(got.applied ? "Saved. Type panorama_reload in the game console, or restart the game, to apply it."
				: "Saved. The recorder isn't installed yet; it applies once it is.");
		} catch (e) {
			box.checked = !box.checked;
			note("Couldn't save it: " + e.message, true);
		}
		box.disabled = false;
	});

	load();
	patches();
})();
