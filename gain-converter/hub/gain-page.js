// The Gain Converter section: the controls of the old tkinter window (retired in Phase 3.8), with the
// curve from movekit/web/gain.js.
"use strict";

(() => {
	const $ = (id) => document.getElementById(id);
	const SVG = "http://www.w3.org/2000/svg";
	const COL = { css: "#f0a63a", mom: "#4fb3ff", text: "#e6e9ef", grid: "#353b47", border: "#4a5468" };
	let fromCss = true; // true: type CS:S, get Momentum
	let value = 90;

	const clamp = (v) => Math.round(Math.min(100, Math.max(0, v)) * 10) / 10;
	const pair = () => (fromCss ? [value, gain.cssToMom(value)] : [gain.momToCss(value), value]); // [css, mom]

	function setValue(v) {
		if (Number.isFinite(v)) value = clamp(v);
		draw();
	}

	function typed() {
		setValue(parseFloat($("gc-box").value.replace("%", "").replace(",", ".")));
	}

	function setDirection(css) {
		// keep the same point on the curve: the old answer becomes the new input
		if (css !== fromCss) value = clamp(css ? gain.momToCss(value) : gain.cssToMom(value));
		fromCss = css;
		draw();
	}

	function draw() {
		const [css, mom] = pair();
		$("gc-from-css").classList.toggle("on", fromCss);
		$("gc-from-mom").classList.toggle("on", !fromCss);
		const label = $("gc-in-label");
		label.textContent = fromCss ? "Your CS:S gain" : "Your Momentum gain";
		label.style.color = fromCss ? COL.css : COL.mom;
		if (document.activeElement !== $("gc-box")) $("gc-box").value = String(value);
		$("gc-slider").value = value;
		$("gc-slider").style.accentColor = fromCss ? COL.css : COL.mom;
		const res = $("gc-result");
		res.textContent = fromCss ? `≈ ${mom.toFixed(1)} % Momentum` : `≈ ${css.toFixed(1)} % CS:S`;
		res.style.color = fromCss ? COL.mom : COL.css;
		$("gc-sub").textContent = fromCss ? `${value} % CS:S gain` : `${value} % Momentum gain`;
		graph(css, mom);
	}

	// Graph: x is always Momentum gain (the real share of speed gained), so Momentum is the straight
	// diagonal and CS:S the curve under it. The switch only changes which number you type.
	function geom(svg) {
		const w = svg.clientWidth, h = svg.clientHeight;
		return { w, h, l: 58, t: 14, r: w - 20, b: h - 44 };
	}

	function el(parent, tag, attrs, text) {
		const e = document.createElementNS(SVG, tag);
		for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
		if (text !== undefined) e.textContent = text;
		parent.append(e);
		return e;
	}

	function graph(css, mom) {
		const svg = $("gc-graph");
		const g = geom(svg);
		svg.replaceChildren();
		if (g.r - g.l < 50 || g.b - g.t < 50) return;
		const X = (p) => g.l + ((g.r - g.l) * p) / 100;
		const Y = (p) => g.b - ((g.b - g.t) * p) / 100;
		for (let p = 0; p <= 100; p += 10) {
			el(svg, "line", { x1: X(p), y1: g.t, x2: X(p), y2: g.b, stroke: COL.grid });
			el(svg, "line", { x1: g.l, y1: Y(p), x2: g.r, y2: Y(p), stroke: COL.grid });
			el(svg, "text", { x: X(p), y: g.b + 16, "text-anchor": "middle" }, p);
			el(svg, "text", { x: g.l - 8, y: Y(p) + 4, "text-anchor": "end" }, p);
		}
		el(svg, "rect", { x: g.l, y: g.t, width: g.r - g.l, height: g.b - g.t, fill: "none", stroke: COL.border, "stroke-width": 2 });
		el(svg, "text", { x: (g.l + g.r) / 2, y: g.b + 36, "text-anchor": "middle", class: "axis-title", style: `fill:${COL.mom}` },
			"Speed you actually gained (Momentum gain %)");
		const yt = (g.t + g.b) / 2;
		el(svg, "text", { x: 16, y: yt, "text-anchor": "middle", class: "axis-title", style: `fill:${COL.text}`, transform: `rotate(-90 16 ${yt})` },
			"Gain shown %");

		el(svg, "line", { x1: X(0), y1: Y(0), x2: X(100), y2: Y(100), stroke: COL.mom, "stroke-width": 3 });
		let d = "";
		for (let i = 0; i <= 200; i++) d += `${i ? "L" : "M"}${X(i / 2).toFixed(1)},${Y(gain.momToCss(i / 2)).toFixed(1)}`;
		el(svg, "path", { d, fill: "none", stroke: COL.css, "stroke-width": 3 });
		for (const [c, m] of gain.MEASURED) el(svg, "circle", { cx: X(m), cy: Y(c), r: 4, fill: COL.text });

		// legend
		[["Momentum", COL.mom], ["CS:S", COL.css]].forEach(([name, col], i) => {
			const lx = X(64), y = g.b - 40 + i * 20;
			el(svg, "line", { x1: lx, y1: y, x2: lx + 24, y2: y, stroke: col, "stroke-width": 3 });
			el(svg, "text", { x: lx + 30, y: y + 4, style: `fill:${col};font-weight:600` }, name);
		});

		// current value: one vertical line, a marker on each line, guides to the left axis
		const x = X(mom), ym = Y(mom), yc = Y(css);
		el(svg, "line", { x1: x, y1: g.b, x2: x, y2: ym, stroke: COL.text, "stroke-width": 2, "stroke-dasharray": "6 3" });
		const flip = x > g.r - 70; // labels go left of the markers near the right edge
		for (const [y, col, val, dy] of [[ym, COL.mom, mom, -10], [yc, COL.css, css, 14]]) {
			el(svg, "line", { x1: g.l, y1: y, x2: x, y2: y, stroke: col, "stroke-width": 2, "stroke-dasharray": "6 3" });
			el(svg, "circle", { cx: x, cy: y, r: 7, fill: COL.text, stroke: col, "stroke-width": 3 });
			el(svg, "text", { x: flip ? x - 12 : x + 12, y: y + dy, "text-anchor": flip ? "end" : "start", style: `fill:${col};font-weight:600` },
				`${val.toFixed(1)} %`);
		}
	}

	function picked(e) {
		const svg = $("gc-graph");
		const g = geom(svg);
		const px = e.clientX - svg.getBoundingClientRect().left;
		if (g.r <= g.l) return;
		const m = Math.min(100, Math.max(0, (100 * (px - g.l)) / (g.r - g.l)));
		setValue(fromCss ? gain.momToCss(m) : m);
	}

	$("gc-from-css").addEventListener("click", () => setDirection(true));
	$("gc-from-mom").addEventListener("click", () => setDirection(false));
	$("gc-minus").addEventListener("click", () => { typed(); setValue(value - 1); });
	$("gc-plus").addEventListener("click", () => { typed(); setValue(value + 1); });
	$("gc-box").addEventListener("keydown", (e) => { if (e.key === "Enter") typed(); });
	$("gc-box").addEventListener("blur", () => { typed(); draw(); });
	$("gc-slider").addEventListener("input", (e) => setValue(parseFloat(e.target.value)));
	const svg = $("gc-graph");
	svg.addEventListener("pointerdown", (e) => { svg.setPointerCapture(e.pointerId); picked(e); });
	svg.addEventListener("pointermove", (e) => { if (svg.hasPointerCapture(e.pointerId)) picked(e); });
	new ResizeObserver(() => draw()).observe(svg);
	draw();
})();
