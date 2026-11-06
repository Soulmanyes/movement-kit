// The Source Yaw section (sourceyaw/hub_section.py): the GTK window's settings as a hub page.
// The page holds the form; Python loads it (load), checks it and saves it (apply), and builds
// every note the window shows, so both windows say the same thing.
"use strict";

(() => {
	const $ = (id) => document.getElementById(id);
	const el = (tag, props = {}, ...kids) => {
		const node = Object.assign(document.createElement(tag), props);
		node.append(...kids);
		return node;
	};

	let st = null;       // what load() returned for the current game
	let keyInfo = null;  // keys(): code map, mouse map, valid bind names
	let entries = [];    // [{speed, color, sound}] in cycle order: the list on the open tab
	let start = 0;       // index of the yawspeed that list starts on
	// both lists; entries/start above are the open tab's, put back by keepTab()
	let lists = { bhop: null, surf: null };
	let tab = "bhop";
	let surfOn = false;  // both lists in game
	let active = "bhop"; // with one list in game, the one it uses
	let modeKey = "";    // switches between the bhop and surf lists, "" for none
	let key = "";        // the cycle key
	let offsetKey = "";  // the trainer's offset key, "" for none
	let base = "";       // the crosshair base: "crosshair-maker", "builtin" or a path
	let dirty = false;

	// ------------------------------------------------------------ small helpers

	function toast(text, error = false, seconds = 4) {
		const t = el("div", { className: "sy-toast" + (error ? " error" : ""), textContent: text });
		$("sy-toasts").append(t);
		setTimeout(() => t.remove(), seconds * 1000);
	}

	async function call(name, args, what) {
		try {
			return await hub.call(name, args);
		} catch (e) {
			toast((what ? what + ": " : "") + e.message, true, 6);
			throw e;
		}
	}

	function setDirty(on) {
		dirty = on;
		const title = "Source Yaw" + (on ? " •" : "");
		$("sy-title").textContent = title;
	}
	const changed = () => setDirty(true);

	function fmtNumber(v) {
		return String(Number(Number(v).toFixed(4)));  // 210 not 210.0000, as the window shows it
	}

	async function copy(text) {
		try {
			await navigator.clipboard.writeText(text);
		} catch {
			const area = el("textarea", { value: text });
			document.body.append(area);
			area.select();
			document.execCommand("copy");
			area.remove();
		}
		toast("Copied", false, 2);
	}

	function note(id, n) {
		$(id).textContent = n.text;
		$(id).classList.toggle("warn", n.warn);
	}

	function options(select, choices, value) {
		select.replaceChildren(...choices.map(([v, label]) => el("option", { value: v, textContent: label })));
		select.value = value;
	}

	// a number box keeps the last good value: a blank or odd entry goes back, out of range is clamped
	function numberBox(input, value, onChange) {
		const [low, high] = st.limits[input.dataset.limit];
		input.min = low;
		input.max = high;
		input.value = fmtNumber(value);
		input.dataset.last = input.value;
		input.onchange = () => {
			let v = parseFloat(input.value);
			if (!Number.isFinite(v)) v = parseFloat(input.dataset.last);
			v = Math.min(Math.max(v, low), high);
			input.value = fmtNumber(v);
			input.dataset.last = input.value;
			onChange(v);
		};
	}

	// ------------------------------------------------------------ yawspeeds

	let previewTimer = null;
	function refreshPreviews() {
		clearTimeout(previewTimer);
		previewTimer = setTimeout(async () => {
			const urls = await call("previews", { game: st.game, base, colors: entries.map((e) => e.color) },
				"Couldn't draw the previews");
			document.querySelectorAll(".sy-preview").forEach((img, i) => { if (urls[i]) img.src = urls[i]; });
		}, 120);
	}

	function drawEntries(urls = null) {
		const box = $("sy-entries");
		box.replaceChildren();
		entries.forEach((entry, i) => {
			const up = el("button", { textContent: "▲", title: "Move up", disabled: i === 0 });
			const down = el("button", { textContent: "▼", title: "Move down", disabled: i === entries.length - 1 });
			up.onclick = () => move(i, i - 1);
			down.onclick = () => move(i, i + 1);

			const radio = el("input", { type: "radio", name: "sy-start", checked: i === start,
				title: "Start the game on this yawspeed" });
			radio.onchange = () => { start = i; drawEntries(currentUrls()); changed(); };

			const preview = el("img", { className: "sy-preview", alt: "", title: "Crosshair in this colour" });
			if (urls && urls[i]) preview.src = urls[i];

			const speed = el("input", { type: "number", step: "10", title: "cl_yawspeed" });
			speed.dataset.limit = "speed";
			numberBox(speed, entry.speed, (v) => { entry.speed = v; changed(); });

			const color = el("input", { type: "color", value: entry.color, title: "Crosshair colour" });
			color.oninput = () => { entry.color = color.value; refreshPreviews(); changed(); };

			const choices = st.sounds.some(([v]) => v === entry.sound) ? st.sounds
				: [...st.sounds, [entry.sound, entry.sound]];  // set by hand or missing here: kept
			const sound = el("select", { title: "Sound when switching to this yawspeed" });
			options(sound, choices, entry.sound);
			const play = el("button", { textContent: "▶", title: "Play this sound", disabled: !entry.sound });
			sound.onchange = () => { entry.sound = sound.value; play.disabled = !entry.sound; changed(); };
			play.onclick = async () => {
				if (!await call("play_sound", { game: st.game, sound: entry.sound }))
					toast(`Couldn't find ${entry.sound} in your game files`, true);
			};

			const remove = el("button", { textContent: "Remove", title: "Remove" });
			remove.onclick = () => {
				entries.splice(i, 1);
				// the start yawspeed goes with its row; removing it starts on the first
				if (i === start) start = 0;
				else if (i < start) start -= 1;
				drawEntries(currentUrls().filter((_, j) => j !== i));
				changed();
			};

			box.append(el("div", { className: "sy-entry" + (i === start ? " start" : "") },
				el("div", { className: "sy-move" }, up, down), radio,
				el("span", { className: "sy-num", textContent: String(i + 1) }), preview, speed, color,
				el("div", { className: "sy-sound-wrap" }, sound, play), remove));
		});
	}

	const currentUrls = () => [...document.querySelectorAll(".sy-preview")].map((img) => img.src);

	function move(from, to) {
		if (to < 0 || to >= entries.length) return;
		const urls = currentUrls();
		entries.splice(to, 0, entries.splice(from, 1)[0]);
		urls.splice(to, 0, urls.splice(from, 1)[0]);
		// the start choice stays with its yawspeed
		if (start === from) start = to;
		else if (from < start && to >= start) start -= 1;
		else if (from > start && to <= start) start += 1;
		drawEntries(urls);
		changed();
	}

	// ------------------------------------------------------------ bhop and surf lists

	function keepTab() {
		lists[tab] = { entries, start };
	}

	// a first surf list starts as a copy of the bhop list
	function ensureSurf() {
		keepTab();
		if (!lists.surf)
			lists.surf = { entries: lists.bhop.entries.map((e) => ({ ...e })), start: lists.bhop.start };
	}

	function openTab(name) {
		if (name === "surf") ensureSurf();
		keepTab();
		tab = name;
		({ entries, start } = lists[tab]);
		showLists();
		drawEntries();
		refreshPreviews();
	}

	const LIST_NAME = { bhop: "Bhop", surf: "Surf" };
	const other = (mode) => (mode === "bhop" ? "surf" : "bhop");

	function showLists() {
		document.querySelectorAll("[data-surf]").forEach((n) => { n.hidden = !surfOn; });
		document.querySelectorAll("#sy-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
		$("sy-surf-note").textContent = surfOn
			? "Both lists in game; the mode key or the map picks one"
			: "Off: only one list is used in game, the other stays saved";
		$("sy-active-note").textContent = surfOn ? "" : `In game: the ${LIST_NAME[active].toLowerCase()} list`;
		$("sy-swap").hidden = surfOn;
		$("sy-swap").textContent = `Use ${LIST_NAME[other(active)].toLowerCase()} instead`;
		const unused = !surfOn && tab !== active;
		$("sy-entries").classList.toggle("sy-inactive", unused);
		$("sy-entries-note").textContent = unused
			? `Not used in game. Press "Use ${tab} instead" to use this list.`
			: !surfOn
				? "Cycled in this order. The ticked one is set when the game starts."
				: tab === "bhop"
					? "Bhop list, cycled in this order. The ticked one is set when the game starts or the list is picked."
					: "Surf list, cycled in this order. The ticked one is set when the list is picked.";
	}

	$("sy-surf-on").onchange = () => {
		surfOn = $("sy-surf-on").checked;
		if (surfOn) ensureSurf();
		showLists();
		changed();
	};
	$("sy-swap").onclick = () => {
		active = other(active);
		if (active === "surf") ensureSurf();
		// show the list now in use
		if (tab !== active) openTab(active);
		else showLists();
		changed();
	};
	document.querySelectorAll("#sy-tabs button").forEach((b) => { b.onclick = () => { if (b.dataset.tab !== tab) openTab(b.dataset.tab); }; });
	$("sy-auto").onchange = changed;

	$("sy-add").onclick = async () => {
		entries.push(await call("new_entry", { entries }));
		drawEntries(currentUrls());
		refreshPreviews();
		changed();
	};

	// ------------------------------------------------------------ keys

	let captureDone = null;
	function capture(title, onKey) {
		$("sy-capture-title").textContent = title;
		const area = $("sy-capture-area");
		area.innerHTML = "Press a key, mouse button or scroll<br>inside this box";
		$("sy-capture-list").value = "";
		captureDone = onKey;
		$("sy-capture").hidden = false;
		area.focus();
	}

	function captureClose() {
		$("sy-capture").hidden = true;
		captureDone = null;
	}

	function captured(name) {
		if (!captureDone) return;
		if (!name) {
			$("sy-capture-area").innerHTML = "CS:S has no bind name for that key,<br>try another";
			return;
		}
		const done = captureDone;
		captureClose();
		done(name);
	}

	function keyName(ev) {
		// numpad keys by where they sit: with NumLock on, Numpad1 types "1" and would bind the main 1
		if (ev.code.startsWith("Numpad") && keyInfo.codes[ev.code]) return keyInfo.codes[ev.code];
		// the key as typed first (letters follow the layout, as in the GTK window), then where it sits
		if (ev.key.length === 1 && keyInfo.valid.includes(ev.key.toLowerCase())) return ev.key.toLowerCase();
		return keyInfo.codes[ev.code] || null;
	}

	document.addEventListener("keydown", (ev) => {
		if (!captureDone || ev.target === $("sy-capture-list")) return;
		ev.preventDefault();
		ev.stopPropagation();
		if (ev.key === "Escape") return captureClose();
		captured(keyName(ev));
	}, true);
	const area = $("sy-capture-area");
	area.addEventListener("mousedown", (ev) => {
		ev.preventDefault();
		captured(keyInfo.mouse[String(ev.button)] || null);
	});
	area.addEventListener("wheel", (ev) => {
		ev.preventDefault();
		if (ev.deltaY) captured(ev.deltaY < 0 ? "mwheelup" : "mwheeldown");
	}, { passive: false });
	// side buttons would otherwise go back or forward in the window
	for (const type of ["mouseup", "auxclick", "contextmenu"])
		document.addEventListener(type, (ev) => { if (captureDone || ev.button > 2) ev.preventDefault(); }, true);
	$("sy-capture-list").onchange = (ev) => { if (ev.target.value) captured(ev.target.value); };
	$("sy-capture-cancel").onclick = captureClose;

	let notesAsked = 0;
	async function showKeyNotes() {
		const asked = ++notesAsked;
		const notes = await call("key_notes", { game: st.game, key, offset_key: offsetKey, mode_key: modeKey });
		if (asked !== notesAsked) return;  // a newer key's notes are on the way
		showNotes(notes);
	}

	function showNotes(notes) {
		note("sy-key-note", notes.key);
		note("sy-offset-note", notes.offset);
		note("sy-mode-note", notes.mode);
	}

	function showKeys() {
		$("sy-key").textContent = key;
		$("sy-offset-key").textContent = offsetKey || "None";
		$("sy-offset-clear").hidden = !offsetKey;
		$("sy-mode-key").textContent = modeKey || "None";
		$("sy-mode-clear").hidden = !modeKey;
	}

	$("sy-key-change").onclick = () => capture("Cycle key", (name) => {
		key = name;
		showKeys();
		showKeyNotes();
		changed();
	});
	function setOffsetKey(name) {
		offsetKey = name;
		showKeys();
		showKeyNotes();
		trainerChanged();
	}
	$("sy-offset-change").onclick = () => capture("Offset key", setOffsetKey);
	function setModeKey(name) {
		modeKey = name;
		showKeys();
		showKeyNotes();
		changed();
	}
	$("sy-mode-change").onclick = () => capture("Mode key", setModeKey);
	$("sy-mode-clear").onclick = () => setModeKey("");
	$("sy-offset-clear").onclick = () => setOffsetKey("");

	// ------------------------------------------------------------ crosshair

	function showBase(choices, shown) {
		options($("sy-base"), choices, shown);
		$("sy-base").dataset.last = shown;
	}

	$("sy-base").onchange = async (ev) => {
		const value = ev.target.value;
		if (value !== "pick") {
			base = value;
			ev.target.dataset.last = value;
			refreshPreviews();
			changed();
			return;
		}
		const got = await call("pick_image", { base }, "Couldn't open the file dialog")
			.catch(() => ({ pick: null, base_options: null }));
		if (got.pick) {
			base = got.pick;
			refreshPreviews();
			changed();
		}
		if (got.base_options) showBase(got.base_options, base);
		else ev.target.value = ev.target.dataset.last;
	};

	function showKrosshair(k) {
		$("sy-krosshair-note").textContent = k.note;
		const btn = $("sy-krosshair-install");
		btn.hidden = !k.can_install && !k.installing;
		btn.disabled = k.installing;
		btn.textContent = k.installing ? "Installing…" : "Install";
	}

	$("sy-krosshair-install").onclick = async () => {
		let k = await call("install_krosshair", {});
		showKrosshair(k);
		while (k.installing) {
			await new Promise((r) => setTimeout(r, 500));
			k = await call("krosshair", {});
			showKrosshair(k);
		}
		toast(k.error ? `Couldn't install KROSSHAIR: ${k.error}`
			: "KROSSHAIR installed. It works the next time you start CS:S", !!k.error, 5);
	};

	// ------------------------------------------------------------ strafe trainer

	const T = (name) => $("sy-t-" + name);
	// each cue (trainer.CUES): its switch, then <cue>_sound, <cue>_pitch and <cue>_ticks
	const CUES = { wrong: "cue_wrong_key", none: "cue_no_key", overlap: "cue_overlap" };
	const NUMBERS = ["x", "y", "target", "size", "repeat", "tone_volume",
		...Object.keys(CUES).flatMap((c) => [c + "_pitch", c + "_ticks"])];
	const SWITCHES = ["enabled", "show_offset", ...Object.values(CUES)];

	function trainerForm() {
		const n = (name) => parseFloat(T(name).dataset.last);
		const form = { offset_key: offsetKey,
			colors: { early: T("early").value, perfect: T("perfect").value, late: T("late").value },
			tickrate: st.trainer.tickrate === null ? null : n("tickrate") };
		for (const name of NUMBERS) form[name] = n(name);
		for (const name of SWITCHES) form[name] = T(name).checked;
		for (const cue of Object.keys(CUES)) form[cue + "_sound"] = T(cue + "_sound").value;
		return form;
	}

	let statusAsked = 0;
	async function showTrainerStatus() {
		document.querySelectorAll(".sy-trainer").forEach((n) => n.classList.toggle("off", !T("enabled").checked));
		const asked = ++statusAsked;
		// the pitch only means something for the tone; the box keeps its place so the rows line up
		const cues = Object.keys(CUES);
		for (const cue of cues) {
			document.querySelector(`[data-tone-of="${cue}"]`).classList.toggle("sy-gone", T(cue + "_sound").value !== "tone");
		}
		$("sy-repeat-field").classList.toggle("sy-gone", cues.every((c) => T(c + "_sound").value === "tone"));
		const s = await call("trainer_status", { game: st.game });
		if (asked !== statusAsked) return;
		$("sy-service").textContent = s.service;
		$("sy-service-copy").hidden = s.installed;
		$("sy-service-copy").dataset.command = s.command;
		if (s.binds !== null) $("sy-binds").textContent = s.binds;
		$("sy-binds").classList.toggle("warn", (s.binds || "").startsWith("⚠"));
	}

	let showing = false;
	async function trainerChanged() {
		changed();
		await showTrainerStatus();
		if (showing) await call("show_in_game", { on: true, game: st.game, trainer: trainerForm() },
			"Couldn't show it in game");
	}

	function fillTrainer() {
		const t = st.trainer;
		for (const name of NUMBERS) numberBox(T(name), t[name], trainerChanged);
		for (const name of SWITCHES) {
			T(name).checked = t[name];
			T(name).onchange = trainerChanged;
		}
		for (const name of ["early", "perfect", "late"]) {
			T(name).value = t.colors[name];
			T(name).oninput = trainerChanged;
		}
		for (const cue of Object.keys(CUES)) {
			options(T(cue + "_sound"), st.cue_sounds, t[cue + "_sound"]);
			T(cue + "_sound").onchange = trainerChanged;
		}
		$("sy-tick-note").textContent = st.tickrate_note;
		$("sy-tick-field").hidden = t.tickrate === null;
		if (t.tickrate !== null) numberBox(T("tickrate"), t.tickrate, trainerChanged);
	}

	$("sy-service-copy").onclick = (ev) => copy(ev.target.dataset.command);
	document.querySelectorAll("[data-play]").forEach((b) => {
		b.onclick = async () => {
			const f = trainerForm();
			const cue = b.dataset.play, sound = f[cue + "_sound"];
			const ok = await call("play_cue", { game: st.game, sound, tone_volume: f.tone_volume,
				pitch: f[cue + "_pitch"] });
			if (!ok) toast(`Couldn't find ${sound} in your game files`, true);
		};
	});
	$("sy-show-in-game").onclick = async (ev) => {
		showing = !showing;
		ev.target.setAttribute("aria-pressed", String(showing));
		await call("show_in_game", { on: showing, game: st.game, trainer: trainerForm() },
			"Couldn't show it in game");
	};

	// ------------------------------------------------------------ game, launch option, apply

	function drawGames() {
		$("sy-game-row").hidden = st.games.length < 2;
		$("sy-games").replaceChildren(...st.games.map((g) => {
			const b = el("button", { textContent: g.short, title: g.name,
				className: g.id === st.game ? "active" : "" });
			b.onclick = async () => {
				if (g.id === st.game) return;
				// each game has its own settings; don't drop unapplied changes silently
				if (dirty) return toast("Apply your changes before switching game", true);
				fill(await call("set_game", { game: g.id }, "Couldn't switch game"));
			};
			return b;
		}));
	}

	$("sy-autoexec").onchange = async (ev) => {
		const box = ev.target;
		box.disabled = true;
		const got = await call("set_autoexec", { game: st.game, on: box.checked })
			.catch(() => ({ ok: false, on: !box.checked, message: "" }));
		box.checked = got.on;
		box.disabled = !st.found;
		if (got.message) toast(got.message, !got.ok, got.ok ? 3 : 5);
	};

	function showLaunch(l) {
		$("sy-launch").textContent = l.text;
		$("sy-launch-note").textContent = l.note;
	}
	$("sy-launch-refresh").onclick = async () => showLaunch(await call("launch_option", { game: st.game }));
	$("sy-launch-copy").onclick = () => copy($("sy-launch").textContent);

	function form() {
		keepTab();
		const copyList = (l) => ({ entries: l.entries.map((e) => ({ ...e })), start: l.start });
		const bhop = copyList(lists.bhop);
		return { key, crosshair: $("sy-crosshair").checked, start: bhop.start, base, entries: bhop.entries,
			trainer: trainerForm(), surf: lists.surf ? copyList(lists.surf) : null, separate: surfOn, active,
			mode_key: modeKey, auto_mode: $("sy-auto").checked };
	}

	$("sy-apply").onclick = async () => {
		const btn = $("sy-apply");
		btn.disabled = true;
		try {
			const got = await call("apply", { game: st.game, form: form() }, "Not saved");
			if (got.saved) setDirty(false);
			got.messages.forEach((m, i) => toast(m, !got.saved, i === got.messages.length - 1 && got.saved ? 6 : 4));
		} finally {
			btn.disabled = !st.found;
		}
	};
	$("sy-crosshair").onchange = changed;

	function fill(data) {
		st = data;
		lists = {
			bhop: { entries: st.entries.map((e) => ({ ...e })), start: st.start },
			surf: st.surf ? { entries: st.surf.entries.map((e) => ({ ...e })), start: st.surf.start } : null,
		};
		surfOn = st.separate;
		active = st.active;
		tab = surfOn ? "bhop" : active;
		({ entries, start } = lists[tab]);
		modeKey = st.mode_key;
		$("sy-surf-on").checked = surfOn;
		$("sy-auto").checked = st.auto_mode;
		$("sy-auto-note").textContent = st.mode_note;
		key = st.key;
		offsetKey = st.trainer.offset_key;
		base = st.base;
		$("sy-sub").textContent = `${st.name} · Version ${st.version}`;
		$("sy-problem").textContent = st.problem || "";
		$("sy-problem").hidden = !st.problem;
		$("sy-apply").disabled = !st.found;
		$("sy-autoexec").checked = st.autoexec;
		$("sy-autoexec").disabled = !st.found;
		$("sy-crosshair").checked = st.crosshair;
		$("sy-color-note").textContent = st.color_note;
		$("sy-steam-note").textContent = st.steam_note;
		document.querySelectorAll("[data-krosshair]").forEach((n) => { n.hidden = !st.uses_krosshair; });
		if (st.uses_krosshair) {
			showBase(st.base_options, st.base_shown);
			showKrosshair(st.krosshair);
		}
		drawGames();
		showKeys();
		showNotes(st.notes);
		showLists();
		// st.previews are the bhop list's
		if (tab === "bhop") drawEntries(st.previews);
		else { drawEntries(); refreshPreviews(); }
		fillTrainer();
		showTrainerStatus();
		showLaunch(st.launch);
		if (showing) $("sy-show-in-game").click();  // a sample from the other game's settings would mislead
		$("sy-loading").hidden = true;
		$("sy-form").hidden = false;
		setDirty(false);
	}

	// another section is another page: ask before unapplied changes go with this one
	$("hub-side").addEventListener("click", (ev) => {
		const link = ev.target.closest("a");
		if (!dirty || !link) return;
		ev.preventDefault();
		$("sy-leave-go").onclick = () => { location.href = link.href; };
		$("sy-leave").hidden = false;
		$("sy-leave-stay").focus();
	}, true);
	$("sy-leave-stay").onclick = () => { $("sy-leave").hidden = true; };

	(async () => {
		try {
			keyInfo = await hub.call("keys");
			options($("sy-capture-list"), [["", "Pick a key…"], ...keyInfo.valid.map((k) => [k, k])], "");
			fill(await hub.call("load"));
		} catch (e) {
			$("sy-loading").textContent = "Couldn't load the settings: " + e.message;
			$("sy-loading").className = "error";
		}
	})();
})();
