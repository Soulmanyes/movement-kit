// Helpers the settings sections share (Source Yaw, Strafe Trainer), with form.css for their look.
// Load after hub.js: <script src="/web/section.js"></script>. Everything is on `mk`:
//   mk.$(id), mk.el(tag, props, ...kids)
//   mk.toast(text, error, seconds)       a note in the corner
//   mk.call(name, args, what)            hub.call that toasts "what: error" and rethrows
//   mk.copy(text)                        to the clipboard, with a toast
//   mk.note(id, {text, warn})            a note under a label, amber when warn
//   mk.options(select, [[value, label]], value)
//   mk.fmtNumber(v), mk.numberBox(input, value, [low, high], onChange)
//   mk.keys.open(title, info, onKey)     the key-capture dialog; info = movekit.bindnames.capture_info()
//   mk.leaveGuard(isDirty, what)         asks before a sidebar link leaves unapplied changes
"use strict";

const mk = (() => {
	const $ = (id) => document.getElementById(id);
	const el = (tag, props = {}, ...kids) => {
		const node = Object.assign(document.createElement(tag), props);
		node.append(...kids);
		return node;
	};

	let toasts = null;
	function toast(text, error = false, seconds = 4) {
		if (!toasts) document.body.append(toasts = el("div", { className: "mk-toasts" }));
		const t = el("div", { className: "mk-toast" + (error ? " error" : ""), textContent: text });
		toasts.append(t);
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

	function fmtNumber(v) {
		return String(Number(Number(v).toFixed(4)));  // 210 not 210.0000
	}

	// a number box keeps the last good value: a blank or odd entry goes back, out of range is clamped.
	// Its value for the form is parseFloat(input.dataset.last).
	function numberBox(input, value, [low, high], onChange) {
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

	// ------------------------------------------------------------ key capture

	const keys = (() => {
		let dialog = null, area = null, list = null, titleNode = null;
		let info = null, done = null;

		function build() {
			titleNode = el("h2");
			area = el("div", { className: "mk-capture-area", tabIndex: 0 });
			list = el("select");
			const cancel = el("button", { textContent: "Cancel", onclick: close });
			dialog = el("div", { className: "mk-modal", hidden: true },
				el("div", { className: "mk-dialog" }, titleNode, area,
					el("div", { className: "mk-row" },
						el("label", { className: "mk-label" }, "Or pick it from the list",
							el("div", { className: "muted", textContent: "For keys this window can't catch, like the Windows key" })),
						list),
					el("div", { className: "mk-dialog-buttons" }, cancel)));
			document.body.append(dialog);
			// capture phase, and only while the dialog is open; the list's own keys stay its own
			document.addEventListener("keydown", (ev) => {
				if (!done || ev.target === list) return;
				ev.preventDefault();
				ev.stopPropagation();
				if (ev.key === "Escape") return close();
				captured(keyName(ev));
			}, true);
			area.addEventListener("mousedown", (ev) => {
				ev.preventDefault();
				captured(info.mouse[String(ev.button)] || null);
			});
			area.addEventListener("wheel", (ev) => {
				ev.preventDefault();
				if (ev.deltaY) captured(ev.deltaY < 0 ? "mwheelup" : "mwheeldown");
			}, { passive: false });
			// side buttons would otherwise go back or forward in the window
			for (const type of ["mouseup", "auxclick", "contextmenu"])
				document.addEventListener(type, (ev) => { if (done || ev.button > 2) ev.preventDefault(); }, true);
			list.onchange = () => { if (list.value) captured(list.value); };
		}

		function keyName(ev) {
			// numpad keys by where they sit: with NumLock on, Numpad1 types "1" and would bind the main 1
			if (ev.code.startsWith("Numpad") && info.codes[ev.code]) return info.codes[ev.code];
			// the key as typed first (letters follow the layout), then where it sits
			if (ev.key.length === 1 && info.valid.includes(ev.key.toLowerCase())) return ev.key.toLowerCase();
			return info.codes[ev.code] || null;
		}

		function close() {
			dialog.hidden = true;
			done = null;
		}

		function captured(name) {
			if (!done) return;
			if (!name) {
				area.innerHTML = "The game has no bind name for that key,<br>try another";
				return;
			}
			const fn = done;
			close();
			fn(name);
		}

		function open(title, keyInfo, onKey) {
			if (!dialog) build();
			if (info !== keyInfo) {
				info = keyInfo;
				options(list, [["", "Pick a key…"], ...info.valid.map((k) => [k, k])], "");
			}
			titleNode.textContent = title;
			area.innerHTML = "Press a key, mouse button or scroll<br>inside this box";
			list.value = "";
			done = onKey;
			dialog.hidden = false;
			area.focus();
		}

		return { open, close, keyName: (ev) => keyName(ev) };
	})();

	// ------------------------------------------------------------ leaving with unapplied changes

	function leaveGuard(isDirty, what) {
		const stay = el("button", { textContent: "Stay" });
		const go = el("button", { textContent: "Leave without applying" });
		const dialog = el("div", { className: "mk-modal", hidden: true },
			el("div", { className: "mk-dialog" }, el("h2", { textContent: "Unapplied changes" }),
				el("p", { textContent: `Leave ${what} without applying your changes? They are lost.` }),
				el("div", { className: "mk-dialog-buttons" }, stay, go)));
		document.body.append(dialog);
		stay.onclick = () => { dialog.hidden = true; };
		// another section is another page: ask before unapplied changes go with this one
		$("hub-side").addEventListener("click", (ev) => {
			const link = ev.target.closest("a");
			if (!isDirty() || !link) return;
			ev.preventDefault();
			go.onclick = () => { location.href = link.href; };
			dialog.hidden = false;
			stay.focus();
		}, true);
	}

	return { $, el, toast, call, copy, note, options, fmtNumber, numberBox, keys, leaveGuard };
})();
