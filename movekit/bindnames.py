"""Source engine key names (what `bind` takes), and how a settings page's key capture maps browser
key events onto them. The page tries KeyboardEvent.key first (letters follow the keyboard layout),
then KeyboardEvent.code through CODES; mouse buttons go through MOUSE (movekit/web/keycapture.js).
"""

VALID = set(
    [chr(c) for c in range(ord("a"), ord("z") + 1)]
    + [str(d) for d in range(10)]
    + [f"f{n}" for n in range(1, 13)]
    + [f"mouse{n}" for n in range(1, 6)]
    + ["mwheelup", "mwheeldown", "space", "tab", "enter", "escape", "backspace",
       "capslock", "shift", "rshift", "ctrl", "rctrl", "alt", "ralt", "lwin",
       "rwin", "app", "ins", "del", "home", "end", "pgup", "pgdn", "uparrow",
       "downarrow", "leftarrow", "rightarrow", "pause", "scrolllock", "numlock",
       "kp_ins", "kp_end", "kp_downarrow", "kp_pgdn", "kp_leftarrow", "kp_5",
       "kp_rightarrow", "kp_home", "kp_uparrow", "kp_pgup", "kp_enter", "kp_del",
       "kp_slash", "kp_multiply", "kp_minus", "kp_plus", "semicolon", "'", "`",
       "-", "=", "[", "]", "\\", ",", ".", "/"]
)

# KeyboardEvent.code -> bind name, for keys whose name isn't the key itself.
# Super never reaches the page on Hyprland; lwin and rwin stay in the pick-from-list fallback.
CODES = {
    **{f"Key{c.upper()}": c for c in "abcdefghijklmnopqrstuvwxyz"},
    **{f"Digit{d}": str(d) for d in range(10)},
    **{f"F{n}": f"f{n}" for n in range(1, 13)},
    "Enter": "enter", "Escape": "escape", "Backspace": "backspace", "Tab": "tab", "Space": "space",
    "CapsLock": "capslock", "ShiftLeft": "shift", "ShiftRight": "rshift", "ControlLeft": "ctrl",
    "ControlRight": "rctrl", "AltLeft": "alt", "AltRight": "ralt", "MetaLeft": "lwin",
    "MetaRight": "rwin", "ContextMenu": "app", "Insert": "ins", "Delete": "del", "Home": "home",
    "End": "end", "PageUp": "pgup", "PageDown": "pgdn", "ArrowUp": "uparrow",
    "ArrowDown": "downarrow", "ArrowLeft": "leftarrow", "ArrowRight": "rightarrow",
    "Pause": "pause", "ScrollLock": "scrolllock", "NumLock": "numlock",
    "Numpad0": "kp_ins", "Numpad1": "kp_end", "Numpad2": "kp_downarrow", "Numpad3": "kp_pgdn",
    "Numpad4": "kp_leftarrow", "Numpad5": "kp_5", "Numpad6": "kp_rightarrow", "Numpad7": "kp_home",
    "Numpad8": "kp_uparrow", "Numpad9": "kp_pgup", "NumpadEnter": "kp_enter",
    "NumpadDecimal": "kp_del", "NumpadDivide": "kp_slash", "NumpadMultiply": "kp_multiply",
    "NumpadSubtract": "kp_minus", "NumpadAdd": "kp_plus", "Semicolon": "semicolon",
    "Quote": "'", "Backquote": "`", "Minus": "-", "Equal": "=", "BracketLeft": "[",
    "BracketRight": "]", "Backslash": "\\", "Comma": ",", "Period": ".", "Slash": "/",
}
# MouseEvent.button -> bind name (0 left, 1 middle, 2 right, 3/4 side)
MOUSE = {0: "mouse1", 1: "mouse3", 2: "mouse2", 3: "mouse4", 4: "mouse5"}


def capture_info():
    """What keycapture.js needs, JSON-able: {codes, mouse, valid}."""
    return {"codes": CODES, "mouse": {str(k): v for k, v in MOUSE.items()},
            "valid": sorted(VALID, key=lambda k: (len(k) > 1, k))}
