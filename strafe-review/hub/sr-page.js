// The Strafe Review section (strafe-review/hub_section.py): whether the server runs, a short setup
// summary and "Open review", which starts the server first if it's down. The full setup check stays
// on the review page; updates are the Modules page's (movekit/web/modules.js, 3.7b in PLAN.md).
// Every request goes through Python: the server takes POSTs only from its own page's origin.
"use strict";

(() => {
	const $ = (id) => document.getElementById(id);
	const POLL = 3000; // ms between status reads
	const START_WAIT = 15000; // ms "Open review" waits for a server it started
	let last = null, busy = false, timer = null;

	function note(text, error = false) {
		$("sr-note").textContent = text;
		$("sr-note").className = "sr-note " + (error ? "error" : "muted");
	}

	function el(tag, props = {}, ...kids) {
		const e = Object.assign(document.createElement(tag), props);
		e.append(...kids);
		return e;
	}

	function rows(st) {
		const out = [];
		const add = (ok, label, text) => out.push([ok, label, text]);
		add(!!st.game, "Game folder", st.game || "Momentum Mod not found in any Steam library");
		add(st.recorder, "Recorder", st.recorder ? "installed" : "not installed: start the game once with the launch option");
		add(st.autoexecBlock, "autoexec.cfg", st.autoexecBlock ? "has the strafe-review block" : "block missing");
		add(st.collecting, "Collector", st.collecting ? "reading the game's log" : "off");
		add(st.saved > 0, "Attempts saved", String(st.saved));
		if (st.error) add(false, "Last error", st.error.text);
		return out;
	}

	function drawRows(st) {
		const box = $("sr-rows");
		box.replaceChildren();
		if (!st) return;
		for (const [ok, label, text] of rows(st)) {
			box.append(el("b", { className: ok ? "ok" : "bad", textContent: `${ok ? "✓" : "✗"} ${label}` }),
				el("span", { className: "val", textContent: text }));
		}
	}

	function draw(got) {
		last = got;
		const on = got.serving;
		$("sr-state").textContent = on ? "Running" : "Not running";
		$("sr-state").className = "sr-state " + (on ? "ok" : "off");
		$("sr-open").disabled = busy;
		$("sr-open").title = on ? got.url : "Starts Strafe Review, then opens the page";
		$("sr-stop").hidden = !on;
		if (!busy) note(on ? "" : "It starts with the game, or here with Open review. Attempts played while it was off are picked up from the game's log.");
		drawRows(on ? got.status : null);
	}

	async function refresh() {
		clearTimeout(timer);
		try {
			draw(await hub.call("status"));
		} catch (e) {
			note("Couldn't read the status: " + e.message, true);
		}
		timer = setTimeout(refresh, POLL);
	}

	async function waitServing(ms, ok = (got) => got.serving) {
		for (let t = 0; t < ms; t += 500) {
			const got = await hub.call("status");
			if (ok(got)) return got;
			await new Promise((r) => setTimeout(r, 500));
		}
		return null;
	}

	$("sr-open").addEventListener("click", async () => {
		busy = true;
		$("sr-open").disabled = true;
		try {
			if (!last || !last.serving) {
				note("Starting Strafe Review…");
				await hub.call("start");
				if (!(await waitServing(START_WAIT))) throw new Error("it didn't start within 15 s");
			}
			await hub.call("open_review");
			note("Opened in the browser.");
		} catch (e) {
			note("Couldn't open the review: " + e.message, true);
		}
		busy = false;
		refresh();
	});

	$("sr-stop").addEventListener("click", async () => {
		if (!confirm("Stop Strafe Review? It starts again with the game, or with Open review.")) return;
		try {
			await hub.call("stop");
		} catch (e) {
			note("Couldn't stop it: " + e.message, true);
		}
		setTimeout(refresh, 500);
	});

	refresh();
})();
