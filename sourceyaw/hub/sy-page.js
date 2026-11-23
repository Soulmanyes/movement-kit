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
	// the lists, each {profiles: [{name, maps, entries, start}], picked, open}: `picked` is the
	// profile in game at start, `open` the one on the page; entries/start above are the open tab's
	// open profile, put back by keepTab(). bhop and surf are in game with surfOn, single without.
	let lists = { bhop: null, surf: null, single: null };
	let tab = "bhop";    // the list on the page: "bhop" or "surf" with surfOn, else "single"
	let surfOn = false;  // both lists in game
	let active = "bhop"; // the saved "active": names the one list's mode in yaws.cfg, never changed here
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

	// Rows a switch shows or hides slide open or shut, and a shown one flashes the accent colour,
	// so it's clear which rows came and went. A button (not a row) slides in or out sideways.
	// Off while fill() sets up the page, and with reduced motion asked for.
	let animate = false;
	const running = new WeakMap();  // node -> {on, anims}: where it's going, cancelled by a change of mind
	function reveal(node, on) {
		const busy = running.get(node);
		if (busy ? busy.on === on : node.hidden === !on) return;  // already there or on its way
		if (busy) busy.anims.forEach((a) => a.cancel());
		running.delete(node);
		if (node.hidden === !on) return;
		if (!animate || matchMedia("(prefers-reduced-motion: reduce)").matches) { node.hidden = !on; return; }
		// a row slides open or shut downward; a button in a row sideways, its gap to the one before
		// it going too, so it moves in step with the rows
		const row = node.classList.contains("mk-row");
		node.hidden = false;
		const cs = getComputedStyle(node);
		const gap = getComputedStyle(node.parentElement).columnGap;
		// its own opacity, not 1: a disabled button is drawn at 0.5, and ending on 1 snapped back
		const opacity = Number(cs.opacity);
		const open = row
			? { height: `${node.offsetHeight}px`, paddingTop: cs.paddingTop, paddingBottom: cs.paddingBottom, opacity }
			: { width: `${node.offsetWidth}px`, paddingLeft: cs.paddingLeft, paddingRight: cs.paddingRight,
				borderLeftWidth: cs.borderLeftWidth, borderRightWidth: cs.borderRightWidth, marginLeft: "0px", opacity };
		const shut = row
			? { height: "0px", paddingTop: "0px", paddingBottom: "0px", opacity: 0 }
			: { width: "0px", paddingLeft: "0px", paddingRight: "0px", borderLeftWidth: "0px", borderRightWidth: "0px",
				marginLeft: gap === "normal" ? "0px" : `-${gap}`, opacity: 0 };
		const timing = { duration: 220, easing: "ease-out" };
		const anims = [];
		const keep = { overflow: node.style.overflow, whiteSpace: node.style.whiteSpace };
		node.style.overflow = "hidden";
		if (!row) node.style.whiteSpace = "nowrap";  // the label stays one line while the width shrinks
		const slide = node.animate(on ? [shut, open] : [open, shut], timing);
		const done = () => Object.assign(node.style, keep);
		slide.onfinish = () => { done(); if (!on) node.hidden = true; };
		slide.oncancel = done;
		anims.push(slide);
		if (on && row) {
			// a new row: the accent at 22%, fading out. A button gets none: its slide shows it, and a
			// flash on it outlasted the slide as an effect of its own. Worked out here: keyframes may
			// not resolve var()
			const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
			anims.push(node.animate([{ backgroundColor: accent + "38" }, { backgroundColor: accent + "00" }],
				{ duration: 1200, easing: "ease-in" }));
		}
		running.set(node, { on, anims });
		Promise.all(anims.map((a) => a.finished)).then(() => {
			if (running.get(node)?.anims === anims) running.delete(node);
		}, () => {});
	}

	// a number box keeps the last good value (mk.numberBox) within its data-limit range
	const numberBox = (input, value, onChange) =>
		mk.numberBox(input, value, st.limits[input.dataset.limit], onChange);

	// ------------------------------------------------------------ yawspeeds

	let previewTimer = null;
	function refreshPreviews() {
		if (st.windows || !st.colors) return;  // no previews on Windows (no Pillow) or without colours
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
				hidden: !st.colors });
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

			box.append(el("div", { className: "sy-entry" + (i === start ? " start" : "") + (!st.colors ? " sy-nocolor" : st.windows ? " sy-nopreview" : "") },
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

	const openProfile = (mode = tab) => lists[mode].profiles[lists[mode].open];
	const copyEntries = (list) => list.map((e) => ({ ...e }));

	function keepTab() {
		Object.assign(openProfile(), { entries, start });
	}

	// a first surf list starts as a copy of the bhop list's profile in game
	function ensureSurf() {
		keepTab();
		if (lists.surf) return;
		const p = lists.bhop.profiles[lists.bhop.picked];
		lists.surf = { profiles: [{ name: "surf", maps: "", entries: copyEntries(p.entries), start: p.start }],
			picked: 0, open: 0 };
	}

	function openTab(name) {
		if (name === "surf") ensureSurf();
		keepTab();
		tab = name;
		({ entries, start } = openProfile());
		showLists();
		drawEntries();
		refreshPreviews();
	}

	// ------------------------------------------------------------ profiles (yawcore.PROFILE_CMD)

	// the names of the profiles in game, which must differ
	const allNames = () => (surfOn ? ["bhop", "surf"] : ["single"])
		.flatMap((m) => (lists[m] ? lists[m].profiles.map((p) => p.name) : []));
	// what the console command allows (yawcore.PROFILE_NAME)
	const cleanName = (s) => s.toLowerCase().replace(/[^a-z0-9_]/g, "_").slice(0, 24);

	function showProfile() {
		const l = lists[tab];
		const sel = $("sy-prof");
		sel.replaceChildren(...l.profiles.map((p, i) =>
			el("option", { value: String(i) }, p.name + (i === l.picked ? " (in game)" : ""))));
		sel.value = String(l.open);
		const p = openProfile();
		$("sy-prof-name").value = p.name;
		$("sy-prof-maps").value = p.maps;
		$("sy-prof-cmd").textContent = st.profile_cmd + p.name;
		$("sy-prof-pick").disabled = l.open === l.picked;
		// profile by map on: the map picks the profile, so no button to pick one by hand; off: the
		// maps aren't used, so no maps field
		const byMap = $("sy-prof-auto").checked;
		reveal($("sy-prof-pick"), !byMap);
		reveal($("sy-prof-map"), byMap);
		reveal($("sy-prof-maps-row"), byMap);
		$("sy-prof-del").disabled = l.profiles.length < 2;
		$("sy-prof-note").textContent = l.profiles.length < 2
			? "Add a profile for another set of yawspeeds, picked by map or console"
			: l.open === l.picked
				? (byMap ? "In game on maps of no profile" : "In game when the game starts or this list is picked")
				: (byMap ? "Switched to on its maps or by its console command" : "Switched to by its console command");
	}

	function openProfileAt(i) {
		keepTab();
		lists[tab].open = i;
		({ entries, start } = openProfile());
		showProfile();
		drawEntries();
		refreshPreviews();
	}

	$("sy-prof").onchange = () => openProfileAt(Number($("sy-prof").value));
	// a copy of the open profile, under a name no profile has yet (stem, stem2, stem3, ...)
	function newProfile(stem, maps, numbered) {
		keepTab();
		const names = allNames();
		let n = 2;
		let name = numbered ? stem + n : stem;
		while (names.includes(name)) name = stem.slice(0, 22) + n++;
		lists[tab].profiles.push({ name, maps, entries: copyEntries(entries), start });
		openProfileAt(lists[tab].profiles.length - 1);
		changed();
	}

	$("sy-prof-new").onclick = () =>
		newProfile(openProfile().name.replace(/\d+$/, "").slice(0, 22) || "set", "", true);
	$("sy-prof-map").onclick = async () => {
		const got = await call("current_map", { game: st.game }, "Couldn't read the game's log");
		if (!got) return;
		if (!got.name) {
			$("sy-prof-note").textContent = "No map in the game's log yet: load a map, then try again";
			return;
		}
		// the map's own list when both are in game, so its gamemode cfg switches to it
		if (surfOn && got.mode && got.mode !== tab) openTab(got.mode);
		newProfile(cleanName(got.name), got.name, false);
	};
	$("sy-prof-del").onclick = () => {
		const l = lists[tab];
		if (l.profiles.length < 2) return;
		l.profiles.splice(l.open, 1);
		if (l.picked > l.open) l.picked--;
		else if (l.picked === l.open) l.picked = 0;
		l.open = Math.min(l.open, l.profiles.length - 1);
		({ entries, start } = openProfile());
		showProfile();
		drawEntries();
		refreshPreviews();
		changed();
	};
	$("sy-prof-pick").onclick = () => {
		lists[tab].picked = lists[tab].open;
		showProfile();
		changed();
	};
	$("sy-prof-name").oninput = () => {
		const input = $("sy-prof-name");
		const name = cleanName(input.value);
		if (name !== input.value) input.value = name;
		openProfile().name = name;
		$("sy-prof-cmd").textContent = st.profile_cmd + name;
		const sel = $("sy-prof");
		sel.options[sel.selectedIndex].textContent = name + (lists[tab].open === lists[tab].picked ? " (in game)" : "");
		changed();
	};
	$("sy-prof-maps").oninput = () => {
		openProfile().maps = $("sy-prof-maps").value;
		changed();
	};


	// the map-load switch rows: only for a game that runs gamemode cfgs (Momentum), with bhop or
	// surf by map prefix on (two lists) or profile by map on
	function showLoadRows() {
		const load = st.map_load && ((surfOn && $("sy-auto").checked) || $("sy-prof-auto").checked);
		reveal($("sy-load-row"), load);
		reveal($("sy-load-sound-row"), load && $("sy-load-switch").checked);
	}

	function showLists() {
		document.querySelectorAll("[data-surf]").forEach((n) => reveal(n, surfOn));
		showLoadRows();
		document.querySelectorAll("#sy-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
		showProfile();
		$("sy-surf-note").textContent = surfOn
			? "A bhop list and a surf list; the mode key or the map picks one"
			: "Off: one list for every map. The bhop and surf lists stay saved";
		$("sy-entries-note").textContent = !surfOn
			? "Cycled in this order. The ticked one is set when the game starts."
			: `${tab === "bhop" ? "Bhop" : "Surf"} list, cycled in this order. The ticked one is set when the list is picked.`;
	}

	$("sy-surf-on").onchange = () => {
		surfOn = $("sy-surf-on").checked;
		if (surfOn) ensureSurf();
		openTab(surfOn ? (st.last_list === "surf" ? "surf" : "bhop") : "single");
		changed();
	};
	document.querySelectorAll("#sy-tabs button").forEach((b) => { b.onclick = () => { if (b.dataset.tab !== tab) openTab(b.dataset.tab); }; });
	$("sy-auto").onchange = () => { showLoadRows(); changed(); };
	$("sy-prof-auto").onchange = () => { showLoadRows(); showProfile(); changed(); };
	$("sy-load-switch").onchange = () => { showLoadRows(); changed(); };
	$("sy-load-sound").onchange = changed;
	$("sy-null-turns").onchange = changed;

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
		// the picked profile is the list itself, the others its "sets" (hub_section.settings)
		const profile = (p) => ({ name: p.name, maps: p.maps, entries: copyEntries(p.entries), start: p.start });
		const copyList = (l) => ({ ...profile(l.profiles[l.picked]),
			sets: l.profiles.filter((_, i) => i !== l.picked).map(profile) });
		const bhop = copyList(lists.bhop);
		return { key, crosshair: $("sy-crosshair").checked, ...bhop, base,
			surf: lists.surf ? copyList(lists.surf) : null, single: copyList(lists.single), separate: surfOn, active,
			mode_key: modeKey, auto_mode: $("sy-auto").checked, profile_auto: $("sy-prof-auto").checked,
			load_switch: $("sy-load-switch").checked, load_sound: $("sy-load-sound").checked,
			null_turns: $("sy-null-turns").checked };
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
		animate = false;
		// the list itself is the picked profile, its "sets" the others
		const profile = (p, name) => ({ name: p.name || name, maps: (p.maps || []).join(", "),
			entries: copyEntries(p.entries), start: p.start });
		const toList = (d, name) => ({ profiles: [profile(d, name), ...(d.sets || []).map((s) => profile(s))],
			picked: 0, open: 0 });
		lists = { bhop: toList(st, "bhop"), surf: st.surf ? toList(st.surf, "surf") : null,
			single: toList(st.single, "main") };  // yawcore.SINGLE_NAME
		surfOn = st.separate;
		active = st.active;
		// both lists: open on the one last played in game
		tab = surfOn ? (st.last_list === "surf" ? "surf" : "bhop") : "single";
		({ entries, start } = openProfile());
		modeKey = st.mode_key;
		$("sy-surf-on").checked = surfOn;
		$("sy-auto").checked = st.auto_mode;
		$("sy-prof-auto").checked = st.profile_auto;
		$("sy-load-switch").checked = st.load_switch;
		$("sy-load-sound").checked = st.load_sound;
		$("sy-null-turns").checked = st.null_turns;
		const own = st.own_turns.map(([k, c]) => `${k} (${c})`).join(", ");
		$("sy-null-note").textContent = "Holding both turn keys turns toward the one pressed last. " + (st.turn_keys.length
			? `Your +left/+right keys: ${st.turn_keys.join(", ")}.`
			: own ? "" : "No +left/+right binds found in config.cfg.")
			+ (own ? ` On your own turn aliases, left as they are: ${own}.` : "");
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
		document.querySelectorAll("[data-colors]").forEach((n) => { n.hidden = !st.colors; });
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
		animate = true;
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
