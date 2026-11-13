// The Source Yaw section (sourceyaw/hub_section.py): the GTK window's settings as a hub page.
// The page holds the form; Python loads it (load), checks it and saves it (apply), and builds
// every note the window shows, so both windows say the same thing. Shared parts (toasts, number
// boxes, key capture, the leave dialog): movekit/web/section.js. The strafe trainer has its own
// section since Phase 13.
"use strict";

(() => {
	const { $, el, toast, call, copy, note, options, fmtNumber } = mk;

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
	let base = "";       // the crosshair base: "crosshair-maker", "builtin" or a path
	let dirty = false;

	// ------------------------------------------------------------ small helpers

	function setDirty(on) {
		dirty = on;
		const title = "Source Yaw" + (on ? " •" : "");
		$("sy-title").textContent = title;
	}
	const changed = () => setDirty(true);

	// a number box keeps the last good value (mk.numberBox) within its data-limit range
	const numberBox = (input, value, onChange) =>
		mk.numberBox(input, value, st.limits[input.dataset.limit], onChange);

	// ------------------------------------------------------------ yawspeeds

	let previewTimer = null;
	function refreshPreviews() {
		if (st.windows) return;  // no crosshair colour on Windows
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

			const preview = el("img", { className: "sy-preview", alt: "", title: "Crosshair in this colour",
				hidden: st.windows });
			if (urls && urls[i]) preview.src = urls[i];

			const speed = el("input", { type: "number", step: "10", title: "cl_yawspeed" });
			speed.dataset.limit = "speed";
			numberBox(speed, entry.speed, (v) => { entry.speed = v; changed(); });

			const color = el("input", { type: "color", value: entry.color, title: "Crosshair colour",
				hidden: st.windows });
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

			box.append(el("div", { className: "sy-entry" + (i === start ? " start" : "") + (st.windows ? " sy-nocolor" : "") },
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

	// the map-load switch rows: only for a game that runs gamemode cfgs (Momentum), with auto on
	function showLoadRows() {
		const load = surfOn && st.map_load && $("sy-auto").checked;
		$("sy-load-row").hidden = !load;
		$("sy-load-sound-row").hidden = !load || !$("sy-load-switch").checked;
	}

	function showLists() {
		document.querySelectorAll("[data-surf]").forEach((n) => { n.hidden = !surfOn; });
		showLoadRows();
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
	$("sy-auto").onchange = () => { showLoadRows(); changed(); };
	$("sy-load-switch").onchange = () => { showLoadRows(); changed(); };
	$("sy-load-sound").onchange = changed;

	$("sy-add").onclick = async () => {
		entries.push(await call("new_entry", { entries }));
		drawEntries(currentUrls());
		refreshPreviews();
		changed();
	};

	// ------------------------------------------------------------ keys

	let notesAsked = 0;
	async function showKeyNotes() {
		const asked = ++notesAsked;
		const notes = await call("key_notes", { game: st.game, key, mode_key: modeKey });
		if (asked !== notesAsked) return;  // a newer key's notes are on the way
		showNotes(notes);
	}

	function showNotes(notes) {
		note("sy-key-note", notes.key);
		note("sy-mode-note", notes.mode);
	}

	function showKeys() {
		$("sy-key").textContent = key;
		$("sy-mode-key").textContent = modeKey || "None";
		$("sy-mode-clear").hidden = !modeKey;
	}

	$("sy-key-change").onclick = () => mk.keys.open("Cycle key", keyInfo, (name) => {
		key = name;
		showKeys();
		showKeyNotes();
		changed();
	});
	function setModeKey(name) {
		modeKey = name;
		showKeys();
		showKeyNotes();
		changed();
	}
	$("sy-mode-change").onclick = () => mk.keys.open("Mode key", keyInfo, setModeKey);
	$("sy-mode-clear").onclick = () => setModeKey("");

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
			surf: lists.surf ? copyList(lists.surf) : null, separate: surfOn, active,
			mode_key: modeKey, auto_mode: $("sy-auto").checked,
			load_switch: $("sy-load-switch").checked, load_sound: $("sy-load-sound").checked };
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
		$("sy-load-switch").checked = st.load_switch;
		$("sy-load-sound").checked = st.load_sound;
		$("sy-auto-note").textContent = st.mode_note;
		key = st.key;
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
		document.querySelectorAll("[data-linux]").forEach((n) => { n.hidden = st.windows; });
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
		showLaunch(st.launch);
		$("sy-loading").hidden = true;
		$("sy-form").hidden = false;
		setDirty(false);
	}

	mk.leaveGuard(() => dirty, "Source Yaw");

	(async () => {
		try {
			keyInfo = await hub.call("keys");
			fill(await hub.call("load"));
		} catch (e) {
			$("sy-loading").textContent = "Couldn't load the settings: " + e.message;
			$("sy-loading").className = "error";
		}
	})();
})();
