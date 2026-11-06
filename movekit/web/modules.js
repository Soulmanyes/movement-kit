// The Modules page (home.html): one card for the core and one per module, from hub.modules("cards").
// Every action goes through hub.modules(name, args) (Bridge.modules in movekit/hub.py), whose reply
// carries the cards as they are afterwards, so the page always redraws from Python's state.
"use strict";

(() => {
	const $ = (id) => document.getElementById(id);
	const errors = {}; // key -> the last action's error, shown on that card until the next action
	const confirming = new Set(); // keys whose uninstall panel is open
	let current = null;

	function el(tag, props = {}, ...kids) {
		const e = Object.assign(document.createElement(tag), props);
		e.append(...kids);
		return e;
	}

	function ver(tag) {
		return tag ? tag.replace(/^.*-v/, "v") : "";
	}

	function ago(seconds) {
		if (!seconds) return "Not checked yet";
		const mins = Math.round((Date.now() / 1000 - seconds) / 60);
		if (mins < 1) return "Checked just now";
		if (mins < 60) return `Checked ${mins} min ago`;
		const hours = Math.round(mins / 60);
		return hours < 48 ? `Checked ${hours} h ago` : `Checked ${Math.round(hours / 24)} days ago`;
	}

	async function act(name, args, card) {
		if (card) delete errors[card];
		draw(current, name, card);
		const reply = await hub.modules(name, args);
		if (!reply.ok) {
			if (card) errors[card] = reply.error;
			else showPageError(reply.error);
		} else if (!card) {
			showPageError(null);
		}
		if (["install", "uninstall", "update", "update_all", "rollback"].includes(name)) hub.drawSide();
		draw(reply.result || current);
	}

	function showPageError(text) {
		$("mod-page-error").hidden = !text;
		$("mod-page-error").textContent = text || "";
	}

	function status(c) {
		if (c.waiting_for_core) {
			return el("div", { className: "mod-status error",
				textContent: `${ver(c.latest.tag)} needs core v${c.waiting_for_core}: update the core first.` });
		}
		if (!c.installed) {
			return c.can_install ? null
				: el("div", { className: "mod-status muted", textContent: "No release of it on GitHub yet." });
		}
		if (c.update) {
			const text = c.checkout ? `${ver(c.latest.tag)} is out; git pull brings it.`
				: `Update available: ${ver(c.latest.tag)}`;
			return el("div", { className: "mod-status new", textContent: text });
		}
		return el("div", { className: "mod-status good", textContent: c.latest ? "Up to date" : "Installed" });
	}

	function card(c, busyName, busyKey) {
		const busy = busyKey === c.key;
		const anyBusy = !!busyName;
		const node = el("div", { className: "card" });
		const buttons = el("div", { className: "mod-buttons" });
		const button = (text, cls, fn, enabled = true) => {
			const b = el("button", { textContent: text, className: cls || "" });
			b.disabled = anyBusy || !enabled;
			b.addEventListener("click", fn);
			buttons.append(b);
			return b;
		};

		const head = el("div", { className: "mod-head" }, el("h2", { textContent: c.title }), ...gameBadges(c));
		if (c.installed && c.version) head.append(el("span", { className: "ver", textContent: "v" + c.version }));
		if (c.checkout && c.key !== "core") head.append(el("span", { className: "badge", textContent: "git checkout" }));
		head.append(buttons);
		node.append(head);
		if (c.summary) node.append(el("div", { className: "mod-summary", textContent: c.summary }));

		if (busy) {
			node.append(el("div", { className: "mod-status mod-busy", textContent: busyLabel(busyName) }));
		} else {
			const line = status(c);
			if (line) node.append(line);
		}

		if (!c.installed && c.can_install) {
			button("Install", "primary", () => act("install", { key: c.key }, c.key));
		}
		if (c.can_update) {
			button(`Update to ${ver(c.latest.tag)}`, "primary", () => act("update", { key: c.key }, c.key));
		}
		if (c.can_rollback) {
			button(c.previous ? `Roll back to ${ver(c.previous)}` : "Roll back", "",
				() => act("rollback", { key: c.key }, c.key));
		}
		if (c.installed && c.key !== "core") {
			const blocked = c.needed_by.length > 0;
			const b = button("Uninstall…", "danger", () => {
				confirming.add(c.key);
				draw(current);
			}, !blocked);
			if (blocked) b.title = `${c.needed_by.join(", ")} needs it; uninstall that first`;
		}

		if (c.update && c.latest && c.latest.notes) {
			const notes = el("details", { className: "mod-notes" },
				el("summary", { textContent: `What's new in ${ver(c.latest.tag)}` }),
				el("pre", { textContent: c.latest.notes }));
			node.append(notes);
		}
		if (c.failed && c.installed) {
			node.append(el("div", { className: "mod-error",
				textContent: `Installing ${ver(c.failed)} failed, so the version before it stays. Auto-update won't try it again; Update still can.` }));
		}

		// the auto switch, for installed copies that can update themselves
		if (c.installed && !c.checkout) {
			if (c.auto) {
				const row = el("div", { className: "mod-auto-on" }, "Auto-update on");
				const off = el("button", { textContent: "Turn off" });
				off.disabled = anyBusy;
				off.addEventListener("click", () => act("set_auto", { key: c.key, value: false }, c.key));
				row.append(off);
				node.append(row);
			} else {
				const row = el("div", { className: "mod-auto-off" }, "Auto-update off");
				const on = el("button", { textContent: "Turn on" });
				on.disabled = anyBusy;
				on.addEventListener("click", () => act("set_auto", { key: c.key, value: true }, c.key));
				row.append(on);
				node.append(row);
			}
		}

		if (confirming.has(c.key) && c.installed) {
			const box = el("input", { type: "checkbox" });
			const yes = el("button", { textContent: `Uninstall ${c.title}`, className: "danger" });
			const no = el("button", { textContent: "Cancel" });
			yes.disabled = no.disabled = anyBusy;
			yes.addEventListener("click", () => {
				confirming.delete(c.key);
				act("uninstall", { key: c.key, delete_data: box.checked }, c.key);
			});
			no.addEventListener("click", () => {
				confirming.delete(c.key);
				draw(current);
			});
			node.append(el("div", { className: "mod-confirm" },
				el("div", { textContent: c.checkout
					? `Takes ${c.title}'s game files, autoexec block and launch hooks out and hides it here. Its code stays in the checkout.`
					: `Takes ${c.title}'s game files, autoexec block and launch hooks out and deletes the module.` }),
				el("label", {}, box, "Also delete saved data (recordings, settings)"),
				el("div", { className: "row" }, yes, no)));
		}

		if (errors[c.key]) node.append(el("div", { className: "mod-error", textContent: errors[c.key] }));
		return node;
	}

	// the games a module works with (module.json "games"), one badge each
	const GAME_NAMES = { css: "CS:S", momentum: "Momentum Mod" };
	function gameBadges(c) {
		return (c.games || []).map((g) => el("span", { className: "badge mod-game",
			textContent: GAME_NAMES[g] || g, title: `Works with ${GAME_NAMES[g] || g}` }));
	}

	const OS_NAMES = { linux: "Linux", win32: "Windows", darwin: "macOS" };
	const osName = (p) => OS_NAMES[Object.keys(OS_NAMES).find((k) => (p || "").startsWith(k))] || p;

	function groupOf(c, platform) {
		if (!c.supported) return `Not available on ${osName(platform)}`;
		return c.group === "hud" ? "HUD" : "Tools";
	}

	// A module this OS can't run: its title and summary, greyed, with the OSes it runs on and no buttons
	function unavailable(c) {
		const only = c.os.map(osName).join(" and ");
		return el("div", { className: "card mod-unavailable" },
			el("div", { className: "mod-head" }, el("h2", { textContent: c.title }), ...gameBadges(c)),
			c.summary ? el("div", { className: "mod-summary", textContent: c.summary }) : "",
			el("div", { className: "mod-status muted", textContent: only ? `${only} only` : "Not for this OS" }));
	}

	function busyLabel(name) {
		return { install: "Installing…", update: "Updating…", rollback: "Rolling back…", uninstall: "Uninstalling…",
			set_auto: "Saving…", check: "Checking…", update_all: "Updating…" }[name] || "Working…";
	}

	let poll = null;

	function draw(state, busyName = null, busyKey = null) {
		if (!state) return;
		current = state;
		const working = busyName || state.busy;
		$("mod-busy").hidden = !state.busy || !!busyName;
		$("mod-busy").textContent = state.busy ? state.busy + "…" : "";
		$("mod-checkout").hidden = !state.checkout;
		$("mod-checked").textContent = state.checkout ? "" : ago(state.checked);
		$("mod-check").hidden = state.checkout;
		$("mod-check").disabled = !!working;
		const updatable = state.cards.filter((c) => c.can_update);
		$("mod-all").hidden = updatable.length === 0;
		$("mod-all").textContent = `Update all (${updatable.length})`;
		$("mod-all").disabled = !!working;

		const list = $("mod-cards");
		list.replaceChildren();
		const cards = state.cards;
		const installed = cards.filter((c) => c.installed && c.key !== "core");
		const core = cards.find((c) => c.key === "core");
		if (core) list.append(card(core, busyName, busyKey));
		if (!installed.length && cards.length > 1) {
			list.append(el("div", { className: "card muted",
				textContent: "No modules installed yet. Install the ones you use below; the rest never download." }));
		}
		// Python sends them in order (Manager.cards): tools, then HUD modules, installed first, then the ones
		// this OS can't run; a heading starts each group
		let shown = null;
		for (const c of cards) {
			if (c.key === "core") continue;
			const group = groupOf(c, state.platform);
			if (group !== shown) {
				list.append(el("h2", { className: "mod-group", textContent: group }));
				shown = group;
			}
			list.append(c.supported ? card(c, busyName, busyKey) : unavailable(c));
		}
		if (cards.length === 1 && !state.checkout) {
			list.append(el("div", { className: "card muted",
				textContent: "No modules found. Check for updates to see what you can install." }));
		}

		// while Python is busy by itself (the auto update at start), look again in a second
		clearTimeout(poll);
		if (state.busy && !busyName) poll = setTimeout(refresh, 1000);
	}

	async function refresh() {
		const reply = await hub.modules("cards");
		if (reply.ok) {
			const wasBusy = current && current.busy;
			draw(reply.result);
			if (wasBusy && !reply.result.busy) hub.drawSide();
		} else {
			showPageError(reply.error);
		}
	}

	$("mod-check").addEventListener("click", () => act("check", {}, null));
	$("mod-all").addEventListener("click", () => act("update_all", {}, null));

	hub.info.then((info) => {
		const probs = $("home-problems");
		if (info.problems.length) {
			probs.hidden = false;
			probs.replaceChildren(el("h2", { textContent: "Didn't load" }));
			for (const x of info.problems) probs.append(el("p", { textContent: `${x.folder}: ${x.error}` }));
		}
	});
	refresh();
})();
