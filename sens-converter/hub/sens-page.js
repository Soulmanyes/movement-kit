// The Sens Converter section (sens-converter/hub_section.py). The two sensitivities follow each other
// as you type: a change to the bottom one works the top one out, any other change the bottom one.
// Apply sends the boxes and Python sets the bottom row's sensitivity and m_yaw.
// Shared parts: movekit/web/section.js.
"use strict";

(() => {
	const { $, el, call, copy, toast } = mk;
	const IDS = { old_dpi: "sc-old-dpi", old_m_yaw: "sc-old-yaw", old_sens: "sc-old-sens",
		new_dpi: "sc-new-dpi", new_m_yaw: "sc-new-yaw", new_sens: "sc-new-sens" };
	// [min, max, step] of each box's slider. A typed value may be outside it or between steps: the
	// box keeps it, the slider shows the nearest it can.
	const DPI = [50, 6400, 50], SENS = [0.05, 10, 0.05], YAW = [0.001, 0.088, 0.001];
	const RANGES = { "sc-old-dpi": DPI, "sc-old-yaw": YAW, "sc-old-sens": SENS, "sc-new-dpi": DPI, "sc-new-yaw": YAW, "sc-new-sens": SENS };
	const sliders = {};
	let current = {};
	let loaded = false; // no saving until load() has filled the boxes

	const num = (id) => {
		const v = parseFloat($(id).value.trim().replace(",", "."));
		return Number.isFinite(v) && v > 0 ? v : null;
	};
	// up to d decimals, trailing zeros after the point dropped (1600 stays 1600)
	const fmt = (v, d = 6) => v.toFixed(d).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
	const cm360 = (dpi, sens, yaw) => (360 / (dpi * sens * yaw)) * 2.54;

	function form() {
		return Object.fromEntries(Object.entries(IDS).map(([k, id]) => [k, $(id).value.trim()]));
	}

	// the slider under each box: moving it writes its value into the box
	for (const [id, [min, max, step]] of Object.entries(RANGES)) {
		const box = $(id), label = box.closest("label");
		const slider = el("input", { type: "range", min, max, step, className: "sc-slider" });
		const decimals = (String(step).split(".")[1] || "").length;
		slider.addEventListener("input", () => {
			box.value = fmt(parseFloat(slider.value), decimals);
			update(id);
		});
		const wrap = el("div", { className: "sc-field" });
		label.replaceWith(wrap);
		wrap.append(label, slider);
		sliders[id] = slider;
	}

	function syncSliders() {
		for (const [id, slider] of Object.entries(sliders)) {
			const v = num(id);
			if (v !== null && document.activeElement !== slider) slider.value = v;
		}
	}

	// the boxes are saved (hub_section.save) a moment after the last change, for the next start
	let saveTimer = null;
	function saveSoon() {
		clearTimeout(saveTimer);
		saveTimer = setTimeout(() => hub.call("save", { form: form() }).catch(() => {}), 400);
	}

	// changed: the box (or its slider) the change came from; none works the bottom sens out
	function update(changed) {
		const v = Object.fromEntries(Object.entries(IDS).map(([k, id]) => [k, num(id)]));
		const rows = v.old_dpi && v.old_m_yaw && v.new_dpi && v.new_m_yaw;
		if (rows && changed === "sc-new-sens" && v.new_sens) {
			v.old_sens = (v.new_sens * v.new_dpi * v.new_m_yaw) / (v.old_dpi * v.old_m_yaw);
			$("sc-old-sens").value = fmt(v.old_sens);
		} else if (rows && changed !== "sc-new-sens" && v.old_sens) {
			v.new_sens = (v.old_sens * v.old_dpi * v.old_m_yaw) / (v.new_dpi * v.new_m_yaw);
			$("sc-new-sens").value = fmt(v.new_sens);
		}
		syncSliders();
		if (loaded) saveSoon();
		const ok = Object.values(v).every((x) => x !== null);
		$("sc-apply").disabled = !ok;
		if (!ok) {
			$("sc-result").textContent = "";
			$("sc-detail").textContent = "Fill in every box";
			return;
		}
		$("sc-result").textContent = `${cm360(v.new_dpi, v.new_sens, v.new_m_yaw).toFixed(2)} cm/360`;
		$("sc-detail").textContent = "the same in both rows";
	}

	function messages(list, saved) {
		$("sc-messages").replaceChildren(...list.map((m, i) => {
			// a console line (the last message when the game is open) can be clicked to copy it
			if (!saved && i === list.length - 1 && /^sensitivity /.test(m)) {
				const code = el("code", { textContent: m, title: "Click to copy" });
				code.onclick = () => copy(m);
				return el("div", {}, code);
			}
			return el("div", { textContent: m });
		}));
	}

	function show(data) {
		$("sc-sub").textContent = "Version " + data.version;
		$("sc-problem").hidden = !data.problem;
		$("sc-problem").textContent = data.problem || "";
		current = data.current || {};
		// on opening: the DPIs and the old m_yaw as saved, the new m_yaw from the game, and the old sens
		// as the game's sens turned into the top row's DPI and m_yaw
		if (!loaded) {
			for (const [k, id] of Object.entries(IDS)) if (data.inputs && data.inputs[k]) $(id).value = data.inputs[k];
			if (!$("sc-old-yaw").value) $("sc-old-yaw").value = "0.022";
			if (current.m_yaw) $("sc-new-yaw").value = String(current.m_yaw);
			fillGameSens();
			loaded = true;
		}
		const have = current.sensitivity && current.m_yaw;
		$("sc-now-row").hidden = !have;
		if (have) $("sc-now").textContent = `Now in Momentum's config.cfg: sensitivity ${current.sensitivity}, m_yaw ${current.m_yaw}`;

		update();
	}

	// The game's sens at the top row's DPI and m_yaw: the game runs at the bottom DPI (your mouse's),
	// so sens * that DPI * game m_yaw is the speed to keep. Without a bottom DPI, the game's sens as is.
	function fillGameSens() {
		if (!(current.sensitivity && current.m_yaw)) return;
		const now = num("sc-new-dpi"), dpi = num("sc-old-dpi"), yaw = num("sc-old-yaw");
		const sens = now && dpi && yaw ? (current.sensitivity * now * current.m_yaw) / (dpi * yaw) : current.sensitivity;
		$("sc-old-sens").value = fmt(sens);
	}

	for (const id of Object.values(IDS)) $(id).addEventListener("input", () => update(id));
	$("sc-use-now").onclick = () => {
		fillGameSens();
		update();
	};
	$("sc-apply").onclick = async () => {
		$("sc-apply").disabled = true;
		try {
			const r = await call("apply", { form: form() }, "Not saved");
			messages(r.messages, r.saved);
			toast(r.saved ? "Applied" : r.messages[0], !r.saved);
			if (r.saved) show(await call("load", {}, "Couldn't load"));
		} finally {
			update();
		}
	};

	call("load", {}, "Couldn't load").then(show);
})();
