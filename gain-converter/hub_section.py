"""Gain Converter's hub section (movekit/hub.py). All of it runs in the page: the curve is
movekit/web/gain.js, so the section needs no Python functions. Since Phase 3.8 retired the tkinter
window (gain_converter.py), this is the whole tool, and it holds the version."""

VERSION = "1.3.1"  # bump in the same commit as the gain-converter-v* tag

SECTION = {
    "key": "gain-converter",
    "title": "Gain Converter",
    "os": ["linux", "win32"],
    "page": "hub/index.html",
    "api": {},
    "order": 30,
}
