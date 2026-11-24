#!/usr/bin/env python3
"""
fritzing2laser_gui.py  -  Oberfläche für fritzing2laser.py
Benötigt fritzing2laser.py im selben Ordner.  Start:  python fritzing2laser_gui.py
Historie der letzten 10 Projekte: ~/.fritzing2laser_history.json
Logo in Dock/Taskleiste (Linux): fritzing2laser.desktop nach ~/.local/share/applications kopieren
"""
import json, os, sys, threading, queue, time, subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fritzing2laser as core

HIST_FILE = os.path.join(os.path.expanduser("~"), ".fritzing2laser_history.json")
HIST_MAX = 10

# (Schlüssel, Beschriftung, Typ, Hilfetext)
NUM_OPTS = [
    ("offset", "Abstand 1. Linie zur Kupferkante [mm]", float, "≈ halber Spotdurchmesser"),
    ("step",   "Linienabstand Vektor [mm]",             float, "kleiner als Spotdurchmesser"),
    ("lines",  "Anzahl Linien um Kupferbahnen",          int,   "0 = Spalt vollständig füllen"),
    ("mark",   "Zentrierpunkt Bohrung Ø [mm]",           float, "0 = aus"),
    ("hole",   "Lochdurchmesser runde Löcher [mm]",      float, "0 = wie SVG (Button ◯)"),
    ("res",    "Rasterauflösung [px/mm]",                float, "100 = 0,01 mm"),
    ("eps",    "Vereinfachungstoleranz [mm]",            float, "größer = weniger Punkte"),
]


def load_hist():
    try:
        with open(HIST_FILE, encoding="utf-8") as f:
            h = json.load(f)
        return h if isinstance(h, list) else []
    except Exception:
        return []


def save_hist(h):
    try:
        with open(HIST_FILE, "w", encoding="utf-8") as f:
            json.dump(h[:HIST_MAX], f, indent=1, ensure_ascii=False)
    except Exception as e:
        print("Historie nicht gespeichert:", e)


# ---------------------------------------------------------------- Logo (PNG, base64)
ICONS = {
    256: (
        "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"
    ),
    64: (
        "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"
        "RU5ErkJggg=="
    ),
    32: (
        "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"
    ),
}


def install_icon():
    """Linux: Logo für .desktop-Starter/Dock nach ~/.local/share/icons kopieren (einmalig)."""
    if not sys.platform.startswith("linux"):
        return
    import base64
    d = os.path.join(os.path.expanduser("~"), ".local/share/icons/hicolor/256x256/apps")
    f = os.path.join(d, "fritzing2laser.png")
    if not os.path.isfile(f):
        try:
            os.makedirs(d, exist_ok=True)
            with open(f, "wb") as fh:
                fh.write(base64.b64decode(ICONS[256]))
        except Exception:
            pass


class App(tk.Tk):
    def __init__(self):
        super().__init__(className="fritzing2laser")     # WM_CLASS für Dock/Taskleiste
        self.title("Fritzing → Laser (Lack-Ablation)")
        self._icons = [tk.PhotoImage(data=ICONS[n]) for n in (256, 64, 32)]
        self.iconphoto(True, *self._icons)
        install_icon()
        self.minsize(820, 640)
        self.q = queue.Queue()
        self.hist = load_hist()
        self.v = {}
        self._build()
        self.apply(self.hist[0]["opts"] if self.hist else core.DEFAULTS)
        self.after(100, self._poll)

    # ------------------------------------------------------------ Aufbau
    def _build(self):
        pad = dict(padx=6, pady=3)
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        # Dateien
        f = ttk.LabelFrame(main, text="Dateien", padding=6)
        f.grid(row=0, column=0, sticky="ew")
        f.columnconfigure(1, weight=1)
        files = [("svg", "Kupfer-SVG (Fritzing Etch)", "file", [("SVG", "*.svg")]),
                 ("drill", "Bohrdatei (optional)", "file", [("Excellon", "*.txt *.drl *.xln"), ("Alle", "*.*")]),
                 ("font", "Schrift .ttf (optional)", "file", [("Schrift", "*.ttf *.otf")]),
                 ("outdir", "Ausgabeordner (leer = wie SVG)", "dir", None)]
        for r, (k, lbl, kind, ft) in enumerate(files):
            ttk.Label(f, text=lbl).grid(row=r, column=0, sticky="w", **pad)
            self.v[k] = tk.StringVar()
            ttk.Entry(f, textvariable=self.v[k]).grid(row=r, column=1, sticky="ew", **pad)
            ttk.Button(f, text="…", width=3,
                       command=lambda k=k, kind=kind, ft=ft: self.browse(k, kind, ft)
                       ).grid(row=r, column=2, **pad)
        ttk.Label(f, text="Dateinamen-Präfix (leer = auto)").grid(row=4, column=0, sticky="w", **pad)
        self.v["prefix"] = tk.StringVar()
        ttk.Entry(f, textvariable=self.v["prefix"]).grid(row=4, column=1, sticky="ew", **pad)

        # Einstellungen
        mid = ttk.Frame(main)
        mid.grid(row=1, column=0, sticky="ew", pady=6)
        mid.columnconfigure(0, weight=1); mid.columnconfigure(1, weight=1)

        s = ttk.LabelFrame(mid, text="Einstellungen", padding=6)
        s.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        for r, (k, lbl, typ, hint) in enumerate(NUM_OPTS):
            ttk.Label(s, text=lbl).grid(row=r, column=0, sticky="w", **pad)
            self.v[k] = tk.StringVar()
            if k == "lines":
                w = ttk.Spinbox(s, from_=0, to=50, increment=1, width=8, textvariable=self.v[k])
            else:
                w = ttk.Entry(s, width=10, textvariable=self.v[k])
            w.grid(row=r, column=1, sticky="w", **pad)
            ttk.Label(s, text=hint, foreground="gray").grid(row=r, column=2, sticky="w", **pad)
        r = len(NUM_OPTS) + 1
        ttk.Label(s, text="Drehung [°]").grid(row=r - 1, column=0, sticky="w", **pad)
        self.v["rotate"] = tk.StringVar()
        ttk.Combobox(s, textvariable=self.v["rotate"], values=["0", "90", "-90", "180"],
                     state="readonly", width=8).grid(row=r - 1, column=1, sticky="w", **pad)
        ttk.Label(s, text="+ = gegen Uhrzeigersinn", foreground="gray").grid(row=r - 1, column=2,
                                                                             sticky="w", **pad)
        ttk.Label(s, text="Bohrungen spiegeln").grid(row=r, column=0, sticky="w", **pad)
        self.v["mirror"] = tk.StringVar()
        ttk.Combobox(s, textvariable=self.v["mirror"], values=["auto", "ja", "nein"],
                     state="readonly", width=8).grid(row=r, column=1, sticky="w", **pad)
        ttk.Label(s, text="auto = wie SVG", foreground="gray").grid(row=r, column=2, sticky="w", **pad)

        o = ttk.LabelFrame(mid, text="Ausgabe", padding=6)
        o.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        for r, (k, lbl) in enumerate([("vektor", "Vektor (nur Linie/Cut, 1 Gang)"),
                                       ("gang1", "Gang 1 Fläche (Fill)"),
                                       ("gang2", "Gang 2 Kontur (Linie)"),
                                       ("drop_text", "Texte im Kupfer weglassen")]):
            self.v[k] = tk.BooleanVar()
            ttk.Checkbutton(o, text=lbl, variable=self.v[k]).grid(row=r, column=0, sticky="w", **pad)
        ttk.Button(o, text="Standardwerte", command=lambda: self.apply(core.DEFAULTS, files=False)
                   ).grid(row=5, column=0, sticky="w", padx=6, pady=(12, 3))

        # Start
        b = ttk.Frame(main)
        b.grid(row=2, column=0, sticky="ew")
        self.btn = ttk.Button(b, text="▶  Erzeugen", command=self.run)
        self.btn.pack(side="left")
        self.btn2 = ttk.Button(b, text="◯  Bohrlöcher rund (SVG)", command=lambda: self.run(True))
        self.btn2.pack(side="left", padx=(8, 0))
        ttk.Button(b, text="Ausgabeordner öffnen", command=self.open_out).pack(side="left", padx=8)
        self.pb = ttk.Progressbar(b, mode="indeterminate", length=180)
        self.pb.pack(side="right")

        # Historie + Log
        low = ttk.PanedWindow(main, orient="vertical")
        low.grid(row=3, column=0, sticky="nsew", pady=(6, 0))
        hf = ttk.LabelFrame(low, text="Letzte Projekte (Doppelklick = laden)", padding=4)
        cols = ("zeit", "svg", "einst")
        self.tree = ttk.Treeview(hf, columns=cols, show="headings", height=6)
        for c, t, w in zip(cols, ("Zeit", "Platine", "Einstellungen"), (120, 220, 420)):
            self.tree.heading(c, text=t); self.tree.column(c, width=w, stretch=(c != "zeit"))
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", self.load_sel)
        hb = ttk.Frame(hf); hb.pack(side="right", fill="y", padx=4)
        ttk.Button(hb, text="Laden", command=self.load_sel).pack(fill="x", pady=2)
        ttk.Button(hb, text="Entfernen", command=self.del_sel).pack(fill="x", pady=2)
        low.add(hf, weight=1)
        lf = ttk.LabelFrame(low, text="Protokoll", padding=4)
        self.log = tk.Text(lf, height=8, wrap="word", state="disabled")
        sb = ttk.Scrollbar(lf, command=self.log.yview); self.log["yscrollcommand"] = sb.set
        self.log.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        low.add(lf, weight=1)
        self.fill_tree()

    # ------------------------------------------------------------ Werte
    def apply(self, opts, files=True):
        for k, d in core.DEFAULTS.items():
            if not files and k in ("svg", "drill", "outdir", "prefix", "font"):
                continue
            val = opts.get(k, d)
            if k in self.v:
                self.v[k].set(val)

    def collect(self):
        o = {}
        for k, d in core.DEFAULTS.items():
            val = self.v[k].get()
            if isinstance(d, bool):
                o[k] = bool(val)
            elif isinstance(d, (int, float)):
                typ = int if k in ("lines", "rotate") else float
                try:
                    o[k] = typ(str(val).replace(",", "."))
                except ValueError:
                    raise ValueError(f"Ungültiger Wert für '{k}': {val}")
            else:
                o[k] = str(val).strip()
        return o

    def browse(self, k, kind, ft):
        start = os.path.dirname(self.v["svg"].get()) or os.getcwd()
        if kind == "dir":
            p = filedialog.askdirectory(initialdir=start)
        else:
            p = filedialog.askopenfilename(initialdir=start, filetypes=ft)
        if p:
            self.v[k].set(p)
            if k == "svg":                # Bohrdatei immer zur neuen SVG passend setzen
                d = os.path.dirname(p)
                stem = os.path.basename(p).split("_etch")[0]
                cand = os.path.join(d, stem + "_drill.txt")
                if os.path.isfile(cand):
                    self.v["drill"].set(cand)
                    self.write(f"Bohrdatei automatisch gesetzt: {cand}\n")
                elif self.v["drill"].get():
                    self.v["drill"].set("")
                    self.write("Keine passende Bohrdatei neben der SVG gefunden – Feld geleert, "
                               "bitte Bohrdatei wählen.\n")

    # ------------------------------------------------------------ Historie
    @staticmethod
    def summary(o):
        parts = []
        if o.get("vektor"):
            parts.append(f"Vektor {'voll' if not o.get('lines') else str(o['lines']) + ' Linien'}"
                         f" / {o.get('step')} mm")
        if o.get("gang1"): parts.append("G1")
        if o.get("gang2"): parts.append("G2")
        parts.append(f"Offset {o.get('offset')} mm")
        parts.append(f"Punkt {o.get('mark')} mm")
        if o.get("rotate"): parts.append(f"Drehung {int(o['rotate']):+d}°")
        if o.get("hole"): parts.append(f"Loch Ø {o['hole']} mm")
        if o.get("drop_text"): parts.append("ohne Text")
        if o.get("mirror") != "auto": parts.append(f"Spiegeln {o.get('mirror')}")
        return ", ".join(parts)

    def fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, h in enumerate(self.hist):
            self.tree.insert("", "end", iid=str(i), values=(
                h.get("time", ""), os.path.basename(h["opts"].get("svg", "")), self.summary(h["opts"])))

    def add_hist(self, o):
        self.hist = [h for h in self.hist if h["opts"].get("svg") != o["svg"]]
        self.hist.insert(0, {"time": time.strftime("%d.%m.%Y %H:%M"), "opts": o})
        self.hist = self.hist[:HIST_MAX]
        save_hist(self.hist)
        self.fill_tree()

    def load_sel(self, *_):
        sel = self.tree.selection()
        if sel:
            self.apply(self.hist[int(sel[0])]["opts"])
            self.write(f"Projekt geladen: {self.hist[int(sel[0])]['opts'].get('svg')}\n")

    def del_sel(self):
        sel = self.tree.selection()
        if sel:
            del self.hist[int(sel[0])]
            save_hist(self.hist)
            self.fill_tree()

    # ------------------------------------------------------------ Ausführen
    def write(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", s)
        self.log.see("end")
        self.log.configure(state="disabled")

    def run(self, round_only=False):
        try:
            o = self.collect()
        except ValueError as e:
            messagebox.showerror("Eingabe", str(e)); return
        if not os.path.isfile(o["svg"]):
            messagebox.showerror("Eingabe", "Bitte eine Kupfer-SVG wählen."); return
        if o["drill"] and not os.path.isfile(o["drill"]):
            messagebox.showerror("Eingabe", "Bohrdatei nicht gefunden."); return
        if o["drill"] and os.path.dirname(os.path.abspath(o["drill"])) != \
                os.path.dirname(os.path.abspath(o["svg"])):
            if not messagebox.askyesno(
                    "Bohrdatei prüfen",
                    "Bohrdatei und SVG liegen in verschiedenen Ordnern:\n\n"
                    f"SVG:  {o['svg']}\nBohr: {o['drill']}\n\nTrotzdem verwenden?"):
                return
        if not o["drill"] and not messagebox.askyesno(
                "Keine Bohrdatei",
                "Ohne Bohrdatei bleiben die Fritzing-Löcher unverändert (angeschnitten, "
                "keine runden Zentrierpunkte).\n\nTrotzdem fortfahren?"):
            return
        if round_only and not o["drill"]:
            messagebox.showerror("Eingabe", "Für runde Bohrlöcher wird die Bohrdatei benötigt."); return
        if not round_only and not (o["vektor"] or o["gang1"] or o["gang2"]):
            messagebox.showerror("Eingabe", "Mindestens eine Ausgabe wählen."); return
        self.btn.configure(state="disabled"); self.btn2.configure(state="disabled"); self.pb.start(12)
        self.write(f"\n=== {os.path.basename(o['svg'])} ===\n")

        def worker():
            try:
                lg = lambda m: self.q.put(("log", m + "\n"))
                if round_only:
                    core.round_holes_svg(o, log=lg)
                    self.q.put(("done_round", o))
                else:
                    core.process(o, log=lg)
                    self.q.put(("done", o))
            except Exception as e:
                self.q.put(("err", f"{type(e).__name__}: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self.write(data)
                else:
                    self.btn.configure(state="normal"); self.btn2.configure(state="normal")
                    self.pb.stop()
                    if kind == "done":
                        self.add_hist(data)
                    elif kind == "done_round":
                        pass
                    else:
                        self.write("FEHLER: " + data + "\n")
                        messagebox.showerror("Fehler", data)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def open_out(self):
        d = self.v["outdir"].get() or os.path.dirname(self.v["svg"].get())
        if not d or not os.path.isdir(d):
            return
        if sys.platform.startswith("win"):
            os.startfile(d)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", d])
        else:
            subprocess.Popen(["xdg-open", d])


if __name__ == "__main__":
    App().mainloop()
