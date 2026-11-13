// Shared by every hub page: draws the sidebar and offers hub.call(name, args), which runs one of
// this section's Python functions (SECTION["api"] in its hub_section.py) and returns its result.
// Load it with <script src="/web/hub.js"></script> and put <nav id="hub-side"></nav> in the page.
// The Modules page (home.html) also uses hub.modules(name, args), the module manager's calls, and
// hub.drawSide() to redraw the sidebar after an install or uninstall changes the sections, and
// hub.restart() to start the hub again after a core update, and hub.releaseNotes(key, title) for a
// card's Release notes popup.
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

	// {ok, result, error}: the Modules page shows the error on the card and redraws from result
	async function modules(name, args = {}) {
		const api = await ready;
		return api.modules(name, args);
	}

	// {ok, error}: starts a new hub and closes this window, so a reply means it failed
	async function restart() {
		const api = await ready;
		return api.restart();
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
		const mods = document.createElement("a");
		mods.href = "/web/home.html";
		mods.textContent = "Modules";
		if (!key) mods.className = "active";
		side.append(mods);
		const line = document.createElement("div");
		line.className = "hub-sep";
		side.append(line);
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

	// Release notes (GitHub Markdown) as elements: headings and **bold** in bold, `code` as code,
	// list items as a list, links as their text. Built with text nodes, so notes can't inject HTML.
	function notesElement(text) {
		const box = document.createElement("div");
		let list = null;
		const inline = (parent, line) => {
			line = line.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
			for (const part of line.split(/(\*\*[^*]+\*\*|`[^`]+`)/)) {
				if (!part) continue;
				const tag = part.startsWith("**") ? "strong" : part.startsWith("`") ? "code" : null;
				const el = tag ? document.createElement(tag) : document.createTextNode(part);
				if (tag) el.textContent = part.slice(tag === "strong" ? 2 : 1, tag === "strong" ? -2 : -1);
				parent.append(el);
			}
		};
		for (const raw of text.split("\n")) {
			const line = raw.trimEnd();
			const item = line.match(/^\s*[-*+]\s+(.*)/);
			if (item) {
				if (!list) box.append((list = document.createElement("ul")));
				const li = document.createElement("li");
				inline(li, item[1]);
				list.append(li);
				continue;
			}
			list = null;
			if (!line.trim()) continue;
			const head = line.match(/^#+\s+(.*)/);
			const p = document.createElement("p");
			if (head) {
				const b = document.createElement("strong");
				inline(b, head[1]);
				p.append(b);
			} else inline(p, line);
			box.append(p);
		}
		return box;
	}

	// A notes dialog in the "What's new" look, open at once: {setTitle(text), show(sections), message(text)}.
	// sections: [{heading, notes}], notes as GitHub Markdown or "" for none written. Only one is open
	// at a time: null when another is.
	let notesOpen = false;
	function notesDialog(title) {
		if (notesOpen) return null;
		notesOpen = true;
		const dlg = document.createElement("dialog");
		dlg.className = "hub-notes";
		const h = document.createElement("h2");
		h.textContent = title;
		const body = document.createElement("div");
		body.className = "hub-notes-body";
		const close = document.createElement("button");
		close.className = "primary";
		close.textContent = "Close";
		close.addEventListener("click", () => dlg.close());
		const row = document.createElement("div");
		row.className = "hub-notes-buttons";
		row.append(close);
		dlg.append(h, body, row);
		dlg.addEventListener("close", () => { dlg.remove(); notesOpen = false; });
		document.body.append(dlg);
		dlg.showModal();
		close.focus();
		const message = (text) => {
			const p = document.createElement("p");
			p.className = "hub-notes-empty";
			p.textContent = text;
			body.replaceChildren(p);
		};
		return {
			setTitle(text) { h.textContent = text; },
			message,
			show(sections) {
				body.replaceChildren();
				for (const s of sections) {
					const head = document.createElement("h3");
					head.textContent = s.heading;
					const notes = s.notes ? notesElement(s.notes) : document.createElement("p");
					if (!s.notes) {
						notes.className = "hub-notes-empty";
						notes.textContent = "No notes were written for this release.";
					}
					body.append(head, notes);
				}
				if (!sections.length) message("No releases on GitHub yet.");
			},
		};
	}

	const version = (tag) => tag.replace(/^.*-v/, "v");

	// The notes of what updated since they were last shown, once (Bridge.whats_new). Runs on every
	// page load and after an update on the Modules page; the bridge waits for the start's auto update.
	async function whatsNew() {
		if (notesOpen) return;
		const api = await ready;
		if (!api.whats_new) return;
		const items = await api.whats_new();
		if (!items || !items.length) return;
		const view = notesDialog("What's new");
		if (!view) return;
		view.show(items.flatMap((it) => it.releases.map((r) => ({
			heading: `${it.title} ${version(r.tag)}`, notes: r.notes }))));
		api.notes_seen(items.map((it) => it.key));
	}

	// Every release's notes for one Modules card, newest first (Bridge.release_notes); the
	// installed version is marked.
	async function releaseNotes(key, title) {
		const view = notesDialog(`${title}: release notes`);
		if (!view) return;
		view.message("Reading the releases from GitHub…");
		let reply;
		try {
			reply = await (await ready).release_notes(key);
		} catch (e) {
			reply = { ok: false, error: String(e) };
		}
		if (!reply.ok) return view.message(reply.error);
		const r = reply.result;
		view.setTitle(`${r.title}: release notes`);
		view.show(r.releases.map((rel) => {
			const v = version(rel.tag);
			return { heading: v === "v" + r.version ? `${v} (installed)` : v, notes: rel.notes };
		}));
	}

	const info = new Promise((resolve) => {
		const go = () => drawSide().then(resolve);
		if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go);
		else go();
	});
	info.then(() => whatsNew()).catch(() => {});

	return { ready, call, key, info, modules, drawSide, whatsNew, releaseNotes, restart };
})();
