// The Strafe Trainer section (strafe-trainer/hub_section.py). The page holds the form; Python loads it
// (load), checks it and saves it (apply), and builds every note. Shared parts: movekit/web/section.js.
"use strict";

(() => {
	const { $, el, toast, call, copy, note, options, numberBox } = mk;
	const T = (name) => $("st-t-" + name);
	// each cue (store.CUES): its switch, then <cue>_sound, <cue>_pitch and <cue>_ticks
	const CUES = { wrong: "cue_wrong_key", none: "cue_no_key", overlap: "cue_overlap" };
	const NUMBERS = ["x", "y", "target", "size", "repeat", "tone_volume",
		...Object.keys(CUES).flatMap((c) => [c + "_pitch", c + "_ticks"])];
	const SWITCHES = ["enabled", "when_jump", "when_timer", "show_offset", ...Object.values(CUES)];

	let st = null;       // what load() returned for the current game
	let keyInfo = null;  // keys(): code map, mouse map, valid bind names
	let offsetKey = "";  // "" for none
	let dirty = false;
	let showing = false; // the sample number in game

	function setDirty(on) {
		dirty = on;
		$("st-title").textContent = "Strafe Trainer" + (on ? " •" : "");
	}
	const box = (name) => numberBox(T(name), st.trainer[name], st.limits[T(name).dataset.limit], changed);

	function form() {
		const n = (name) => parseFloat(T(name).dataset.last);
		const f = { offset_key: offsetKey,
			colors: { early: T("early").value, perfect: T("perfect").value, late: T("late").value },
			tickrate: st.trainer.tickrate === null ? null : n("tickrate") };
		for (const name of NUMBERS) f[name] = n(name);
		for (const name of SWITCHES) f[name] = T(name).checked;
		for (const cue of Object.keys(CUES)) f[cue + "_sound"] = T(cue + "_sound").value;
		return f;
	}

	// Momentum only: CS:S has no timer marker, so its trainer always waits for a jump key
	function showWhen() {
		const mom = st.game === "momentum";
		$("st-when-timer-field").hidden = !mom;
		const jump = T("when_jump").checked, timer = mom && T("when_timer").checked;
		const text = !mom ? "While a jump key is held"
			: jump && timer ? "While a jump key is held or the run timer is running (either one)"
			: timer ? "While the run timer is running; not in practice mode or replays"
			: jump ? "While a jump key is held"
			: "⚠ Pick at least one";
		note("st-when-note", { text, warn: !jump && !timer });
	}

	let statusAsked = 0;
	async function showStatus() {
		document.querySelectorAll(".mk-dims").forEach((n) => n.classList.toggle("off", !T("enabled").checked));
		showWhen();
		// the pitch only means something for the tone; the box keeps its place so the rows line up
		const cues = Object.keys(CUES);
		for (const cue of cues) {
			document.querySelector(`[data-tone-of="${cue}"]`).classList.toggle("mk-gone", T(cue + "_sound").value !== "tone");
		}
		$("st-repeat-field").classList.toggle("mk-gone", cues.every((c) => T(c + "_sound").value === "tone"));
		const asked = ++statusAsked;
		const s = await call("trainer_status", { game: st.game });
		if (asked !== statusAsked) return;
		$("st-service").textContent = s.service;
		$("st-service-copy").hidden = s.installed;
		$("st-service-copy").dataset.command = s.command;
		if (s.binds !== null) $("st-binds").textContent = s.binds;
		$("st-binds").classList.toggle("warn", (s.binds || "").startsWith("⚠"));
	}

	async function changed() {
		setDirty(true);
		await showStatus();
		if (showing) await call("show_in_game", { on: true, game: st.game, trainer: form() }, "Couldn't show it in game");
	}

	// ------------------------------------------------------------ offset key

	function showKey() {
		$("st-offset-key").textContent = offsetKey || "None";
		$("st-offset-clear").hidden = !offsetKey;
	}
	let notesAsked = 0;
	async function setOffsetKey(name) {
		offsetKey = name;
		showKey();
		changed();
		const asked = ++notesAsked;
		const n = await call("offset_key_note", { game: st.game, offset_key: offsetKey });
		if (asked === notesAsked) note("st-offset-note", n);
	}
	$("st-offset-change").onclick = () => mk.keys.open("Offset key", keyInfo, setOffsetKey);
	$("st-offset-clear").onclick = () => setOffsetKey("");

	// ------------------------------------------------------------ sounds, the sample number

	$("st-service-copy").onclick = (ev) => copy(ev.target.dataset.command);
	document.querySelectorAll("[data-play]").forEach((b) => {
		b.onclick = async () => {
			const f = form();
			const cue = b.dataset.play, sound = f[cue + "_sound"];
			const ok = await call("play_cue", { game: st.game, sound, tone_volume: f.tone_volume, pitch: f[cue + "_pitch"] });
			if (!ok) toast(`Couldn't find ${sound} in your game files`, true);
		};
	});
	$("st-show-in-game").onclick = async (ev) => {
		showing = !showing;
		ev.target.setAttribute("aria-pressed", String(showing));
		await call("show_in_game", { on: showing, game: st.game, trainer: form() }, "Couldn't show it in game");
	};

	// ------------------------------------------------------------ game, launch option, apply

	function drawGames() {
		$("st-game-row").hidden = st.games.length < 2;
		$("st-games").replaceChildren(...st.games.map((g) => {
			const b = el("button", { textContent: g.short, title: g.name, className: g.id === st.game ? "active" : "" });
			b.onclick = async () => {
				if (g.id === st.game) return;
				// each game has its own settings; don't drop unapplied changes silently
				if (dirty) return toast("Apply your changes before switching game", true);
				fill(await call("set_game", { game: g.id }, "Couldn't switch game"));
			};
			return b;
		}));
	}

	function showLaunch(l) {
		$("st-launch").textContent = l.text;
		$("st-launch-note").textContent = l.note;
	}
	$("st-launch-refresh").onclick = async () => showLaunch(await call("launch_option", { game: st.game }));
	$("st-launch-copy").onclick = () => copy($("st-launch").textContent);

	$("st-apply").onclick = async () => {
		const btn = $("st-apply");
		btn.disabled = true;
		try {
			const got = await call("apply", { game: st.game, form: form() }, "Not saved");
			if (got.saved) setDirty(false);
			got.messages.forEach((m, i) => toast(m, !got.saved, i === got.messages.length - 1 && got.saved ? 6 : 4));
		} finally {
			btn.disabled = false;
		}
	};

	function fill(data) {
		st = data;
		const t = st.trainer;
		for (const name of NUMBERS) box(name);
		for (const name of SWITCHES) {
			T(name).checked = t[name];
			T(name).onchange = changed;
		}
		for (const name of ["early", "perfect", "late"]) {
			T(name).value = t.colors[name];
			T(name).oninput = changed;
		}
		for (const cue of Object.keys(CUES)) {
			options(T(cue + "_sound"), st.cue_sounds, t[cue + "_sound"]);
			T(cue + "_sound").onchange = changed;
		}
		$("st-tick-note").textContent = st.tickrate_note;
		$("st-tick-field").hidden = t.tickrate === null;
		if (t.tickrate !== null) box("tickrate");
		offsetKey = t.offset_key;
		showKey();
		note("st-offset-note", st.offset_note);
		$("st-sub").textContent = `${st.name} · Version ${st.version}`;
		$("st-problem").textContent = st.problem || "";
		$("st-problem").hidden = !st.problem;
		$("st-apply").disabled = false;
		$("st-steam-note").textContent = st.steam_note;
		document.querySelectorAll("[data-linux]").forEach((n) => { n.hidden = st.windows; });
		drawGames();
		showLaunch(st.launch);
		showStatus();
		if (showing) $("st-show-in-game").click();  // a sample from the other game's settings would mislead
		$("st-loading").hidden = true;
		$("st-form").hidden = false;
		setDirty(false);
	}

	mk.leaveGuard(() => dirty, "the Strafe Trainer");

	(async () => {
		try {
			keyInfo = await hub.call("keys");
			fill(await hub.call("load"));
		} catch (e) {
			$("st-loading").textContent = "Couldn't load the settings: " + e.message;
			$("st-loading").className = "error";
		}
	})();
})();
