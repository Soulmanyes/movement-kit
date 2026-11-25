// The Surf Sound section (surf-sound/hub_section.py): the desktop sound. Python loads it (load), checks
// and saves it (apply); the sound runner beside the game picks the change up. Shared parts:
// movekit/web/section.js.
"use strict";

(() => {
	const { $, toast, call, copy, numberBox } = mk;
	const SLOTS = ["ramp", "ceiling", "wall", "graze", "bonk", "jump"];
	let dirty = false;
	let custom = {}; // the page's custom sounds, {slot: {file, name}}: saved by Apply


	function setDirty(on) {
		dirty = on;
		$("ss-title").textContent = "Surf Sound" + (on ? " •" : "");
		$("ss-apply").disabled = !on;
	}

	function form() {
		return {
			on: $("ss-on").checked, sound: loopBuiltin.ramp, ceiling_sound: loopBuiltin.ceiling, split_ceiling: split,
			ramp: $("ss-ramp").checked, ceiling: $("ss-ceiling").checked,
			wall: $("ss-wall").checked, graze: $("ss-graze").checked, bonk: $("ss-bonk").checked,
			jump: $("ss-jump").checked, watch: $("ss-watch").checked, custom, levels: levels(), mic: $("ss-mic").value
		};
	}

	function levels() {
		return Object.fromEntries(SLOTS.map((slot) => [slot, parseFloat($("ss-level-" + slot).dataset.last)]));
	}

	// ramps and ceilings pick in one list: the built-in sounds, then the row's own sound (a file or a
	// recording) as "Your sound". Picking a built-in keeps the own sound in the list until the page reloads.
	let builtins = []; // [[key, label]]
	const loopBuiltin = { ramp: "whoosh", ceiling: "whoosh" };
	let kept = {}; // {slot: custom entry} an own sound swapped for a built-in, to pick again
	let split = false; // headsurfs have their own sound (split_ceiling); else they play the ramp's
	function showSplit() {
		$("ss-ceil-same").hidden = split;
		$("ss-ceil-own").hidden = !split;
		$("ss-split").textContent = split ? "Same as ramps" : "Separate";
		$("ss-split").title = split ? "Play the ramp's sound on headsurfs too" : "Give headsurfs a sound of their own";
	}
	$("ss-split").onclick = () => {
		split = !split;
		showSplit();
		setDirty(true);
	};
	function showLoop(slot) {
		const sel = $("ss-sound-" + slot);
		const own = custom[slot] || kept[slot];
		const opts = builtins.map(([key, label]) => new Option(label, key));
		if (own) {
			const group = document.createElement("optgroup");
			group.label = "Your sound";
			group.append(new Option(own.name, "own"));
			opts.push(group);
		}
		sel.replaceChildren(...opts);
		sel.value = custom[slot] ? "own" : loopBuiltin[slot];
		sel.title = custom[slot] ? custom[slot].name : "Built-in sound";
	}
	for (const slot of ["ramp", "ceiling"]) {
		$("ss-sound-" + slot).addEventListener("change", (e) => {
			const v = e.target.value;
			if (v === "own") {
				custom = { ...custom, [slot]: kept[slot] };
				delete kept[slot];
			} else {
				loopBuiltin[slot] = v;
				if (custom[slot]) {
					kept[slot] = custom[slot];
					const { [slot]: _gone, ...rest } = custom;
					custom = rest;
				}
			}
			showCustom();
			setDirty(true);
		});
	}

	function showCustom() {
		for (const slot of SLOTS) {
			const c = custom[slot];
			$("ss-file-" + slot).textContent = c ? c.name : "Built-in";
			if ($("ss-sound-" + slot)) {
				$("ss-file-" + slot).hidden = true;
				showLoop(slot);
			}
			$("ss-file-" + slot).title = c ? c.name : "";
			$("ss-clear-" + slot).hidden = !c;
		}
	}

	function showLaunch(l) {
		$("ss-launch").textContent = l.text;
		$("ss-launch-note").textContent = l.note;
	}
	$("ss-launch-refresh").onclick = async () => showLaunch(await call("launch_option", {}));
	$("ss-launch-copy").onclick = () => copy($("ss-launch").textContent);

	// the microphones: "" is the system's default input; a saved one that's gone stays, marked
	function showMics(m, want) {
		const sel = $("ss-mic");
		const opts = [new Option(m.default ? `Default input (${m.default})` : "Default input", "")];
		for (const [id, name] of m.list) opts.push(new Option(name, id));
		if (want && !m.list.some(([id]) => id === want)) opts.push(new Option(`${want} (not connected)`, want));
		sel.replaceChildren(...opts);
		sel.value = want || "";
	}
	$("ss-mic-refresh").onclick = async () => showMics(await call("mics", {}, "Can't list the microphones"), $("ss-mic").value);

	function show(data) {
		$("ss-sub").textContent = "Version " + data.version;
		recRules = data.rec;
		$("ss-steam-note").textContent = data.steam_note;
		showLaunch(data.launch);
		$("ss-problem").hidden = !data.problem;
		$("ss-problem").textContent = data.problem || "";
		builtins = data.sounds;
		loopBuiltin.ramp = data.sound.sound;
		loopBuiltin.ceiling = data.sound.ceiling_sound || data.sound.sound;
		kept = {};
		split = data.sound.split_ceiling;
		showSplit();
		$("ss-on").checked = data.sound.on;
		showOn();
		$("ss-ramp").checked = data.sound.ramp;
		$("ss-ceiling").checked = data.sound.ceiling;
		$("ss-wall").checked = data.sound.wall;
		$("ss-graze").checked = data.sound.graze;
		$("ss-bonk").checked = data.sound.bonk;
		$("ss-jump").checked = data.sound.jump;
		custom = { ...data.sound.custom };
		showCustom();
		$("ss-watch").checked = data.sound.watch;
		showMics(data.mics, data.sound.mic);
		for (const slot of SLOTS) numberBox($("ss-level-" + slot), data.sound.levels[slot], data.volume, () => setDirty(true));
		$("ss-loading").hidden = true;
		$("ss-form").hidden = false;
		setDirty(false);
	}

	// the card's on switch: the rows fade while it's off (they keep their own settings)
	function showOn() {
		const on = $("ss-on").checked;
		$("ss-on-text").textContent = on ? "On" : "Off";
		$("ss-rows").classList.toggle("off", !on);
	}
	$("ss-on").addEventListener("change", showOn);
	for (const id of ["ss-on", "ss-ramp", "ss-ceiling", "ss-wall", "ss-graze", "ss-bonk", "ss-jump", "ss-watch", "ss-mic"]) $(id).onchange = () => setDirty(true);
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
			delete kept[slot];
			showCustom();
			setDirty(true);
		};
	}
	// the recording dialog: ● Rec opens it for one sound. Python stops the recording by itself at the
	// window's end; the page stops it then too, on ■ Stop, or when the dialog closes.
	const REC_WHAT = {
		ramp: ["Ramps", "It plays over and over while you surf, so record a steady sound: a hiss, a hum, a whoosh. " +
			"Keep it going the whole time; its end blends into its start."],
		ceiling: ["Headsurfs", "It plays over and over while you headsurf, so record a steady sound: a hiss, a hum, a " +
			"scrape. Keep it going the whole time; its end blends into its start."],
		wall: ["Wall hits", "It plays once when a wall takes your speed (louder the more you lose). Make one short, " +
			"sharp sound."],
		graze: ["Light head hits", "It plays once when you clip a ceiling. Make one short sound."],
		bonk: ["Hard head hits", "It plays once when you slam into a ceiling. Make one short sound."],
		jump: ["Jumps", "It plays at every takeoff, and bhops jump about every 0.6 s, so make it quick: a hop, a " +
			"boing, a click."],
	};
	const PLAY_KIND = { wall: "wall3" };
	let recRules = {}; // {slot: {seconds, min, keep}} from Python
	let dlg = null; // the open dialog: {slot, take (the recording's custom entry), rec: {start, timer, seconds}}

	function recInfo(slot) {
		const r = recRules[slot];
		const [title, what] = REC_WHAT[slot];
		const len = r.min
			? `It must be at least ${r.min} s long once the quiet at the start and end is cut; up to ${r.keep} s is kept.`
			: `Up to ${r.keep} s is kept; the quiet before and after it is cut.`;
		return [`Record the ${title.toLowerCase()} sound`,
			`${what} ${len} Recording stops by itself after ${r.seconds} s, or click ■ Stop.`];
	}
	function recStatus(text, warn = false) {
		$("ss-rec-status").textContent = text;
		$("ss-rec-status").classList.toggle("warn", warn);
	}
	function recBusy(on) {
		// while recording or waiting on Python: only ■ Stop and Cancel stay
		$("ss-mic").disabled = $("ss-mic-refresh").disabled = on;
		$("ss-rec-play").disabled = $("ss-rec-use").disabled = on || !dlg?.take;
	}
	function recOpen(slot) {
		const [title, info] = recInfo(slot);
		dlg = { slot, take: null, rec: null };
		$("ss-rec-title").textContent = title;
		$("ss-rec-info").textContent = info;
		$("ss-rec-go").textContent = "● Record";
		$("ss-rec-go").classList.remove("on");
		$("ss-rec-go").disabled = false;
		$("ss-rec-fill").style.width = "0";
		recStatus("");
		recBusy(false);
		$("ss-rec-take").hidden = true;
		showSaved(slot, null);
		hub.call("saved", { slot }).then((list) => showSaved(slot, list), () => showSaved(slot, []));
		$("ss-rec-dlg").hidden = false;
		$("ss-rec-go").focus();
	}
	async function recClose() {
		if (!dlg) return;
		const { rec } = dlg;
		dlg = null;
		$("ss-rec-dlg").hidden = true;
		if (rec) {
			clearInterval(rec.timer);
			try { await hub.call("record_stop", {}); } catch { /* thrown away anyway */ }
		}
	}
	async function recStart() {
		const d = dlg;
		$("ss-rec-go").disabled = true;
		d.take = null;
		$("ss-rec-take").hidden = true;
		recBusy(true);
		recStatus("Starting…");
		try {
			const got = await hub.call("record_start", { slot: d.slot, device: $("ss-mic").value });
			if (dlg !== d) { // closed meanwhile
				await hub.call("record_stop", {}).catch(() => {});
				return;
			}
			d.rec = { start: Date.now(), timer: 0, seconds: got.seconds };
			$("ss-rec-go").textContent = "■ Stop";
			$("ss-rec-go").classList.add("on");
			const tick = () => {
				const s = Math.min((Date.now() - d.rec.start) / 1000, d.rec.seconds);
				$("ss-rec-fill").style.width = `${(100 * s) / d.rec.seconds}%`;
				recStatus(`Recording… ${s.toFixed(1)} / ${d.rec.seconds} s`);
				if (s >= d.rec.seconds) recStop();
			};
			tick();
			d.rec.timer = setInterval(tick, 100);
		} catch (e) {
			recStatus(e.message, true);
			recBusy(false);
		} finally {
			$("ss-rec-go").disabled = false;
		}
	}
	async function recStop() {
		const d = dlg;
		if (!d?.rec) return;
		clearInterval(d.rec.timer);
		d.rec = null;
		$("ss-rec-go").disabled = true;
		recStatus("…");
		try {
			const got = await hub.call("record_stop", {});
			if (dlg !== d) return;
			d.take = got.custom;
			recStatus(`Got ${got.seconds.toFixed(1)} s. ▶ Play to hear it, Use it to put it on the row, or Save it for later.`);
			$("ss-rec-name").value = got.custom.name;
			$("ss-rec-save").disabled = false;
			$("ss-rec-take").hidden = false;
		} catch (e) {
			if (dlg === d) recStatus(e.message, true);
		} finally {
			if (dlg === d) {
				$("ss-rec-go").textContent = d.take ? "● Record again" : "● Record";
				$("ss-rec-go").classList.remove("on");
				$("ss-rec-go").disabled = false;
				recBusy(false);
			}
		}
	}
	$("ss-rec-go").onclick = () => (dlg?.rec ? recStop() : recStart());
	$("ss-rec-cancel").onclick = recClose;
	// saved recordings: list = [{file, name, seconds, date}], null while loading
	function showSaved(slot, list) {
		const box = $("ss-rec-saved");
		if (!dlg || dlg.slot !== slot) return;
		if (!list || !list.length) {
			box.replaceChildren(mk.el("div", { className: "muted", textContent: list ? "None yet." : "…" }));
			showCurrent(slot, list || []);
			return;
		}
		showCurrent(slot, list);
		box.replaceChildren(...list.map((s) => {
			const play = mk.el("button", { textContent: "▶", title: "Play it" });
			const use = mk.el("button", { textContent: "Use", title: "Put it on the row (Apply saves it)" });
			const del = mk.el("button", { textContent: "×", title: "Delete it" });
			play.onclick = async () => {
				try {
					const got = await call("use_saved", { slot, file: s.file }, "Can't play");
					await previewWith(slot, got.custom);
				} catch { /* call() showed it */ }
			};
			use.onclick = async () => {
				try {
					useTake(slot, (await call("use_saved", { slot, file: s.file }, "Can't use it")).custom);
				} catch { /* call() showed it */ }
			};
			del.onclick = async () => {
				if (del.textContent === "×") { // a second click deletes
					del.textContent = "Delete?";
					setTimeout(() => { del.textContent = "×"; }, 3000);
					return;
				}
				try {
					showSaved(slot, await call("delete_saved", { slot, file: s.file }, "Can't delete it"));
				} catch { /* call() showed it */ }
			};
			const label = mk.el("span", { className: "ss-saved-name", textContent: s.name, title: "Click to rename" });
			const edit = mk.el("button", { textContent: "✎", title: "Rename it" });
			const info = mk.el("span", { className: "muted", textContent: `${s.seconds} s · ${s.date}` });
			const row = mk.el("div", { className: "ss-saved-row" }, label, info, play, use, edit, del);
			label.onclick = edit.onclick = () => renameSaved(slot, s, row, label);
			return row;
		}));
	}
	// rename: the name turns into a text box; Enter or leaving it saves, Esc keeps the old name
	function renameSaved(slot, s, row, label) {
		if (row.querySelector("input")) return;
		const box = mk.el("input", { type: "text", value: s.name, maxLength: 200, className: "ss-saved-name" });
		box.setAttribute("aria-label", "New name");
		label.replaceWith(box);
		box.focus();
		box.select();
		let done = false;
		const finish = async (keep) => {
			if (done) return;
			done = true;
			const name = box.value.trim();
			if (!keep || !name || name === s.name) {
				box.replaceWith(label);
				return;
			}
			try {
				const list = await call("rename_saved", { slot, file: s.file, name }, "Can't rename it");
				if (custom[slot]?.file === s.file) { // the row uses it: its name follows
					custom = { ...custom, [slot]: { ...custom[slot], name } };
					showCustom();
					setDirty(true);
				}
				showSaved(slot, list);
			} catch {
				box.replaceWith(label);
			}
		};
		box.addEventListener("keydown", (e) => {
			if (e.key === "Enter") finish(true);
			else if (e.key === "Escape") {
				e.stopPropagation(); // Esc here cancels the rename, not the whole window
				finish(false);
			}
		});
		box.addEventListener("blur", () => finish(true));
	}
	// the row's own custom sound (a recording or a file, applied or not): Save keeps it too
	function showCurrent(slot, list) {
		const cur = custom[slot];
		$("ss-rec-cur").hidden = !cur;
		if (!cur) return;
		const kept = list.some((s) => s.file === cur.file);
		$("ss-rec-cur-name").textContent = cur.name;
		$("ss-rec-cur-name").title = cur.name;
		$("ss-rec-cur-save").textContent = kept ? "Saved" : "Save";
		$("ss-rec-cur-save").disabled = kept;
	}
	$("ss-rec-cur-save").onclick = async () => {
		const { slot } = dlg;
		$("ss-rec-cur-save").disabled = true;
		try {
			showSaved(slot, await call("save_recording", { slot, custom: custom[slot], name: custom[slot].name }, "Can't save it"));
		} catch {
			$("ss-rec-cur-save").disabled = false;
		}
	};
	async function saveTake() {
		const { slot, take } = dlg;
		const list = await call("save_recording", { slot, custom: take, name: $("ss-rec-name").value }, "Can't save it");
		showSaved(slot, list);
		return list;
	}
	function useTake(slot, entry) {
		custom = { ...custom, [slot]: entry };
		showCustom();
		setDirty(true);
		recClose();
	}
	$("ss-rec-save").onclick = async () => {
		$("ss-rec-save").disabled = true;
		try {
			await saveTake();
			recStatus("Saved. Use it puts it on the row.");
		} catch {
			$("ss-rec-save").disabled = false;
		}
	};
	$("ss-rec-use").onclick = async () => {
		const { slot, take } = dlg;
		try { await saveTake(); } catch { /* still used; call() said why it wasn't saved */ }
		useTake(slot, { ...take, name: $("ss-rec-name").value.trim() || take.name });
	};
	// the built-in sound a preview plays: the ceiling's own for a ceiling, else the ramp's (hits ignore it)
	function rowSound(kind, f) {
		return kind === "ceiling" && f.split_ceiling ? f.ceiling_sound : f.sound;
	}
	async function previewWith(slot, entry) {
		const f = form();
		const ok = await call("preview", { sound: rowSound(slot, f), kind: PLAY_KIND[slot] || slot, custom: { ...custom, [slot]: entry },
			levels: f.levels, split: f.split_ceiling }, "Can't play");
		if (!ok) toast("Couldn't play the sound here", true);
	}
	$("ss-rec-play").onclick = () => previewWith(dlg.slot, dlg.take);
	$("ss-rec-dlg").addEventListener("keydown", (e) => {
		if (e.key === "Escape") recClose();
	});
	for (const slot of SLOTS) $("ss-rec-" + slot).onclick = () => recOpen(slot);

	async function play(kind) {
		const f = form();
		const ok = await call("preview", { sound: rowSound(kind, f), kind, custom, levels: f.levels, split: f.split_ceiling }, "Can't play");
		if (!ok) toast("Couldn't play the sound here", true);
	}
	$("ss-play-ramp").onclick = () => play("ramp");
	$("ss-play-ceiling").onclick = () => play("ceiling");
	$("ss-play-wall").onclick = () => play("wall3");
	$("ss-play-bonk").onclick = () => play("bonk");
	$("ss-play-graze").onclick = () => play("graze");
	$("ss-play-jump").onclick = () => play("jump");
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
