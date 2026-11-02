#!/usr/bin/env python3
"""Gain Converter: turns a CS:S (SSJ) gain % into a Momentum Mod gain % and back, with a graph.

The two don't measure the same thing, so this is an estimate. The curve momentum = 1 - (1 - css) ** K
is fitted to measured pairs from Strafe Review (https://github.com/Soulmanyes/strafe-review).
Runs on Linux and Windows with the standard library only.
"""
import sys
import tkinter as tk

K = 1.45  # fitted to the measured pairs below (each one gives K between 1.41 and 1.54)
# (CS:S %, Momentum %) ends of the measured ranges: finished bhop_ambience runs, top replays
MEASURED = [(71, 83), (77, 88), (79, 91), (88, 95)]

BG = "#16181d"
CARD = "#262a33"
BORDER = "#4a5263"
TEXT = "#e8eaf0"
MUTED = "#9aa3b5"
CSS_COL = "#f0a63a"
MOM_COL = "#4fb3ff"
GRID = "#353b47"
FONT = "Segoe UI" if sys.platform == "win32" else "Sans"
SLIDER_PAD = 14


def css_to_mom(c):
    return 100 * (1 - (1 - c / 100) ** K)


def mom_to_css(m):
    return 100 * (1 - (1 - m / 100) ** (1 / K))


class App:
    def __init__(self, root):
        self.root = root
        self.from_css = True  # True: type CS:S, get Momentum
        self.value = tk.DoubleVar(value=90.0)
        self.box_text = tk.StringVar(value="90")

        root.title("Gain Converter")
        root.configure(bg=BG)
        root.minsize(620, 640)

        # Direction switch: two big buttons, the active one filled
        sw = tk.Frame(root, bg=BG)
        sw.pack(pady=(18, 10))
        self.btn_css = self.switch_button(sw, "CS:S  →  Momentum", True)
        self.btn_mom = self.switch_button(sw, "Momentum  →  CS:S", False)
        self.btn_css.pack(side="left", padx=4)
        self.btn_mom.pack(side="left", padx=4)

        # Input card: label, − [box] +, slider
        card = tk.Frame(root, bg=CARD, highlightbackground=BORDER, highlightthickness=2)
        card.pack(fill="x", padx=20, pady=6)
        self.in_label = tk.Label(card, bg=CARD, fg=TEXT, font=(FONT, 13, "bold"))
        self.in_label.pack(pady=(12, 6))
        row = tk.Frame(card, bg=CARD)
        row.pack()
        self.step_button(row, "−", -1).pack(side="left", padx=8)
        box = tk.Entry(row, textvariable=self.box_text, width=6, justify="center", font=(FONT, 20, "bold"),
                       bg="#0e1014", fg=TEXT, insertbackground=TEXT, relief="flat",
                       highlightthickness=2, highlightbackground=BORDER, highlightcolor=MOM_COL)
        box.pack(side="left", ipady=4)
        box.bind("<Return>", self.typed)
        box.bind("<FocusOut>", self.typed)
        tk.Label(row, text="%", bg=CARD, fg=TEXT, font=(FONT, 18)).pack(side="left", padx=(4, 0))
        self.step_button(row, "+", 1).pack(side="left", padx=8)
        # Slider: drawn so the track, the filled part and the knob all stand out
        self.slider = tk.Canvas(card, height=34, bg=CARD, highlightthickness=0, cursor="hand2")
        self.slider.pack(fill="x", padx=24, pady=(10, 14))
        self.slider.bind("<Configure>", lambda _e: self.draw_slider())
        self.slider.bind("<Button-1>", self.slid)
        self.slider.bind("<B1-Motion>", self.slid)

        # Result
        self.result = tk.Label(root, bg=BG, font=(FONT, 26, "bold"))
        self.result.pack(pady=(10, 0))
        self.result_sub = tk.Label(root, bg=BG, fg=MUTED, font=(FONT, 11))
        self.result_sub.pack()

        # Graph (click or drag on it to pick a value)
        self.canvas = tk.Canvas(root, bg=CARD, highlightthickness=2, highlightbackground=BORDER, height=300)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=12)
        self.canvas.bind("<Configure>", lambda _e: self.update())
        self.canvas.bind("<Button-1>", self.clicked)
        self.canvas.bind("<B1-Motion>", self.clicked)

        tk.Label(root, bg=BG, fg=MUTED, font=(FONT, 9), justify="center",
                 text="An estimate: the two games score gain differently, so no exact conversion exists.\n"
                      "Curve fitted to measured runs (dots). Click or drag on the graph to pick a value.").pack(pady=(0, 12))

        self.set_direction(True)

    def switch_button(self, parent, text, css):
        return tk.Button(parent, text=text, font=(FONT, 12, "bold"), relief="flat", bd=0, padx=16, pady=8,
                         highlightthickness=2, cursor="hand2", command=lambda: self.set_direction(css))

    def step_button(self, parent, text, step):
        return tk.Button(parent, text=text, width=3, font=(FONT, 16, "bold"), bg=CARD, fg=TEXT,
                         activebackground=BORDER, activeforeground=TEXT, relief="flat",
                         highlightthickness=2, highlightbackground=BORDER, cursor="hand2",
                         command=lambda: self.step(step))

    def step(self, step):
        self.typed()  # a number typed without Enter counts first
        self.set_value(self.value.get() + step)

    def set_direction(self, from_css):
        # Keep the same point on the curve: the old answer becomes the new input
        if from_css != self.from_css:
            v = self.value.get()
            self.value.set(round(mom_to_css(v) if from_css else css_to_mom(v), 1))
        self.from_css = from_css
        for btn, on, col in ((self.btn_css, from_css, CSS_COL), (self.btn_mom, not from_css, MOM_COL)):
            btn.configure(bg=col if on else CARD, fg="#101216" if on else MUTED, activebackground=col,
                          highlightbackground=col if on else BORDER)
        self.in_label.configure(text="Your CS:S gain" if from_css else "Your Momentum gain",
                                fg=CSS_COL if from_css else MOM_COL)
        self.update()

    def set_value(self, v):
        self.value.set(round(min(100.0, max(0.0, v)), 1))
        self.update()

    def typed(self, _e=None):
        try:
            self.set_value(float(self.box_text.get().replace("%", "").replace(",", ".")))
        except ValueError:
            self.update()  # puts the current value back in the box

    def pair(self):
        """(css, mom) for the current input."""
        v = self.value.get()
        return (v, css_to_mom(v)) if self.from_css else (mom_to_css(v), v)

    def update(self):
        v = self.value.get()
        self.box_text.set(f"{v:g}")
        css, mom = self.pair()
        if self.from_css:
            self.result.configure(text=f"≈ {mom:.1f} % Momentum", fg=MOM_COL)
            self.result_sub.configure(text=f"{css:g} % CS:S gain")
        else:
            self.result.configure(text=f"≈ {css:.1f} % CS:S", fg=CSS_COL)
            self.result_sub.configure(text=f"{mom:g} % Momentum gain")
        self.draw_slider()
        self.draw()

    # Graph: x is always Momentum gain (the real share of speed gained), so Momentum is the straight
    # diagonal and CS:S the curve under it. The switch only changes which number you type.
    def geom(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        return 58, 16, w - 20, h - 44  # left, top, right, bottom

    def to_px(self, x, y):
        l, t, r, b = self.geom()
        return l + (r - l) * x / 100, b - (b - t) * y / 100

    def slid(self, e):
        w = self.slider.winfo_width() - 2 * SLIDER_PAD
        if w > 0:
            self.set_value(100 * (e.x - SLIDER_PAD) / w)

    def draw_slider(self):
        c = self.slider
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        col = CSS_COL if self.from_css else MOM_COL
        x = SLIDER_PAD + (w - 2 * SLIDER_PAD) * self.value.get() / 100
        y = h / 2
        c.create_line(SLIDER_PAD, y, w - SLIDER_PAD, y, fill="#4d5566", width=8, capstyle="round")
        c.create_line(SLIDER_PAD, y, x, y, fill=col, width=8, capstyle="round")
        c.create_oval(x - 11, y - 11, x + 11, y + 11, fill=TEXT, outline=col, width=3)

    def clicked(self, e):
        l, _t, r, _b = self.geom()
        if r > l:
            m = min(100.0, max(0.0, 100 * (e.x - l) / (r - l)))
            self.set_value(mom_to_css(m) if self.from_css else m)

    def draw(self):
        c = self.canvas
        c.delete("all")
        l, t, r, b = self.geom()
        if r - l < 50 or b - t < 50:
            return
        for p in range(0, 101, 10):
            x, _ = self.to_px(p, 0)
            _, y = self.to_px(0, p)
            c.create_line(x, t, x, b, fill=GRID)
            c.create_line(l, y, r, y, fill=GRID)
            c.create_text(x, b + 12, text=str(p), fill=MUTED, font=(FONT, 9))
            c.create_text(l - 8, y, text=str(p), fill=MUTED, font=(FONT, 9), anchor="e")
        c.create_rectangle(l, t, r, b, outline=BORDER, width=2)
        c.create_text((l + r) / 2, b + 30, text="Speed you actually gained (Momentum gain %)",
                      fill=MOM_COL, font=(FONT, 10, "bold"))
        c.create_text(16, (t + b) / 2, text="Gain shown %", fill=TEXT, font=(FONT, 10, "bold"), angle=90)

        c.create_line(*self.to_px(0, 0), *self.to_px(100, 100), fill=MOM_COL, width=3)
        pts = []
        for i in range(201):
            pts += self.to_px(i / 2, mom_to_css(i / 2))
        c.create_line(*pts, fill=CSS_COL, width=3, smooth=True)
        for cs, mo in MEASURED:
            x, y = self.to_px(mo, cs)
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=TEXT, outline="")

        # Legend
        for i, (name, col) in enumerate((("Momentum", MOM_COL), ("CS:S", CSS_COL))):
            lx, y = self.to_px(64, 0)[0], b - 40 + i * 20
            c.create_line(lx, y, lx + 24, y, fill=col, width=3)
            c.create_text(lx + 30, y, text=name, fill=col, font=(FONT, 10, "bold"), anchor="w")

        # Current value: one vertical line, a marker on each line, guides to the left axis
        css, mom = self.pair()
        x, ym = self.to_px(mom, mom)
        _, yc = self.to_px(mom, css)
        c.create_line(x, b, x, ym, fill=TEXT, width=2, dash=(6, 3))
        flip = x > r - 70  # labels go left of the markers near the right edge
        for y, col, val in ((ym, MOM_COL, mom), (yc, CSS_COL, css)):
            c.create_line(l, y, x, y, fill=col, width=2, dash=(6, 3))
            c.create_oval(x - 7, y - 7, x + 7, y + 7, fill=TEXT, outline=col, width=3)
            dy = -10 if y == ym else 10  # Momentum's label above its line, CS:S's below
            c.create_text(x - 12 if flip else x + 12, y + dy, text=f"{val:.1f} %", fill=col,
                          font=(FONT, 10, "bold"), anchor="e" if flip else "w")


if __name__ == "__main__":
    root = tk.Tk(className="gain-converter")
    App(root)
    root.mainloop()
