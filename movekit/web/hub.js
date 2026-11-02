// Shared by every hub page: draws the sidebar and offers hub.call(name, args), which runs one of
// this section's Python functions (SECTION["api"] in its hub_section.py) and returns its result.
// Load it with <script src="/web/hub.js"></script> and put <nav id="hub-side"></nav> in the page.
"use strict";

const hub = (() => {
	// pywebview injects window.pywebview.api on each page, not always before onload
	const ready = new Promise((resolve) => {
		if (window.pywebview && window.pywebview.api) return resolve(window.pywebview.api);
		window.addEventListener("pywebviewready", () => resolve(window.pywebview.api), { once: true });
	});

	// /s/<key>/... is a section's page; anything else (the home page) has no section
	const match = location.pathname.match(/^\/s\/([^/]+)\//);
	const key = match ? decodeURIComponent(match[1]) : null;

	async function call(name, args = {}) {
		if (!key) throw new Error("this page belongs to no section");
		const api = await ready;
		const reply = await api.call(key, name, args);
		if (!reply.ok) throw new Error(reply.error);
		return reply.result;
	}

	async function drawSide() {
		const side = document.getElementById("hub-side");
		if (!side) return null;
		const info = await (await ready).sections();
		document.title = info.title;
		side.replaceChildren();
		const title = document.createElement("a");
		title.className = "hub-title";
		title.href = "/web/home.html";
		title.textContent = info.title;
		side.append(title);
		for (const s of info.sections) {
			const a = document.createElement("a");
			a.href = s.url;
			a.textContent = s.title;
			if (s.key === key) a.className = "active";
			side.append(a);
		}
		if (info.problems.length) {
			const p = document.createElement("div");
			p.className = "hub-problems";
			p.textContent = "Not loaded: " + info.problems.map((x) => x.folder).join(", ");
			p.title = info.problems.map((x) => `${x.folder}: ${x.error}`).join("\n");
			side.append(p);
		}
		return info;
	}

	const info = new Promise((resolve) => {
		const go = () => drawSide().then(resolve);
		if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go);
		else go();
	});

	return { ready, call, key, info };
})();
