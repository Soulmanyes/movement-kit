// Deleting attempts from the main page: Select mode for the list, the server calls, and the Undo toast.
// Deleted attempts go to the store's trash for 30 days (collector/trash.py); Undo brings them back.

const UNDO_SECONDS = 10;

async function postKeys(route, keys) {
	const res = await fetch(`/api/${route}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ keys })
	});
	if (!res.ok) throw new Error(res.status === 404 ? 'restart the viewer (new route)' : await res.text());
	return (await res.json()).keys;
}

const deleteAttempts = (keys) => postKeys('delete', keys);
const restoreAttempts = (keys) => postKeys('restore', keys);

// The toast at the bottom of the page: "<text> · Undo" for UNDO_SECONDS, or a plain message.
// A new toast replaces the old one (its Undo is gone then; the files stay in the trash).
let toastTimer = null;
function showToast(el, text, onUndo) {
	clearTimeout(toastTimer);
	el.replaceChildren();
	const msg = document.createElement('span');
	msg.textContent = text;
	el.append(msg);
	if (onUndo) {
		const b = document.createElement('button');
		b.textContent = 'Undo';
		b.onclick = () => {
			el.hidden = true;
			clearTimeout(toastTimer);
			onUndo();
		};
		el.append(b);
	}
	el.hidden = false;
	toastTimer = setTimeout(() => (el.hidden = true), UNDO_SECONDS * 1000);
}

// Select mode for the list. els: { mode, all, del, cancel } buttons; onChange() redraws the list;
// onDelete(keys) deletes. Picks are "<dir>/<id>" keys, kept outside the DOM since the list is rebuilt often.
function initPicker(els, onChange, onDelete) {
	const picked = new Set();
	let active = false;
	let shownKeys = []; // what the list shows now; picks it hides don't count
	const sync = () => {
		els.mode.hidden = active;
		els.all.hidden = els.del.hidden = els.cancel.hidden = !active;
		const n = picked.size;
		els.del.textContent = `Delete ${n}`;
		els.del.disabled = !n;
		els.all.textContent = n && n === shownKeys.length ? 'Untick all' : 'Tick all shown';
	};
	const set = (on) => {
		active = on;
		picked.clear();
		sync();
		onChange();
	};
	els.mode.onclick = () => set(true);
	els.cancel.onclick = () => set(false);
	els.all.onclick = () => {
		const all = picked.size === shownKeys.length;
		picked.clear();
		if (!all) for (const k of shownKeys) picked.add(k);
		sync();
		onChange();
	};
	els.del.onclick = () => {
		const keys = [...picked];
		if (keys.length) onDelete(keys).then((ok) => ok && set(false));
	};
	sync();
	return {
		get active() {
			return active;
		},
		has: (key) => picked.has(key),
		toggle(key) {
			if (!picked.delete(key)) picked.add(key);
			sync();
		},
		// called by each list render with the keys it shows: drops picks the filters now hide
		shown(keys) {
			shownKeys = keys;
			const now = new Set(keys);
			for (const k of picked) if (!now.has(k)) picked.delete(k);
			sync();
		},
		off: () => active && set(false)
	};
}
