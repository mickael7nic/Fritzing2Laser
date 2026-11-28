#!/usr/bin/env python3
"""
fritzing2laser.py  -  Fritzing-Kupfer-SVG (+ optional Excellon-Drill) -> Laserdaten
für lackbeschichtete Platinen (Lack weglasern, danach ätzen).

Erzeugt je Platine 6 Dateien:
  <name>_Gang1_Flaeche.dxf / .svg   geschlossene Flächen = Lack weg (Fill, Even-Odd)
  <name>_Gang2_Kontur.dxf  / .svg   Konturen um das Kupfer (Line), um --offset versetzt
  <name>_Vektor.dxf        / .svg   ALTERNATIVE in einem Gang: Spalten mit parallelen
                                    Konturlinien (Abstand --step) gefüllt, nur Line/Cut

Installation (einmalig):
  pip install resvg-py opencv-python-headless numpy ezdxf

Aufruf:
  Oberfläche:     python fritzing2laser_gui.py
  Kommandozeile:  python fritzing2laser.py Platine_etch_copper_bottom_mirror.svg Platine_drill.txt
                  python fritzing2laser.py Platine.svg Platine_drill.txt --lines 3 --no-text

Hinweise:
  * Die Spiegelung wird aus der SVG erkannt (Fritzing "_mirror"-Export). Die Bohrungen
    werden automatisch passend gespiegelt; die Ausrichtung wird geprüft und gemeldet.
  * Für die Fritzing-Schrift die Datei OCR-Fritzing-mono.ttf neben das Script legen
    oder mit --font angeben (sonst Ersatzschrift):
    https://github.com/fritzing/fritzing-app/tree/develop/resources/fonts
"""
import argparse, os, re, sys
import xml.etree.ElementTree as ET
import numpy as np
import cv2
import ezdxf
import resvg_py

VERSION = "2026-11-28"

UNIT_MM = {"in": 25.4, "mm": 1.0, "cm": 10.0, "pt": 25.4 / 72, "px": 25.4 / 90, "": 25.4 / 90}


def dim_mm(s):
    m = re.match(r"\s*([0-9.]+)\s*([a-z]*)", s)
    return float(m.group(1)) * UNIT_MM[m.group(2)]


# ---------------------------------------------------------------- SVG laden
def load_svg(path, drop_text=False):
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    tree = ET.parse(path)
    root = tree.getroot()
    w_mm, h_mm = dim_mm(root.get("width")), dim_mm(root.get("height"))
    vb = root.get("viewBox")
    if vb:  # Renderer-freundliche Größe: Einheiten weg, x/y entfernen
        _, _, vw, vh = map(float, vb.replace(",", " ").split())
        root.set("width", repr(vw)); root.set("height", repr(vh))
    else:
        root.set("viewBox", f"0 0 {w_mm} {h_mm}")
        root.set("width", repr(w_mm)); root.set("height", repr(h_mm))
    for k in ("x", "y"):
        root.attrib.pop(k, None)
    # gespiegelt = die ganze Lage (oberste Gruppe), nicht ein einzelnes gespiegeltes Bauteil
    mirrored = False
    for g in root:
        t = g.get("transform", "")
        if t.replace(" ", "").startswith("matrix(-1,"):
            mirrored = True
            break
    # Platinenumriss (nur Linie) nicht als Kupfer rendern
    for parent in root.iter():
        for ch in list(parent):
            tag = ch.tag.split("}")[-1]
            if ch.get("id") == "boardoutline" or (drop_text and tag == "text"):
                parent.remove(ch)
    return ET.tostring(root, encoding="unicode"), w_mm, h_mm, mirrored


def render(svg_str, w_px, h_px, fonts):
    # Zielgröße direkt als (ganzzahlige) SVG-Größe setzen: resvg rundet eine krumme
    # Dokumentgröße (z.B. 309.543) sonst auf ganze Einheiten -> Maßstabsfehler ~0,15 %.
    m = re.search(r"<svg\b[^>]*>", svg_str)
    tag = re.sub(r'\s(width|height)="[^"]*"', "", m.group(0))
    tag = tag.replace("<svg", f'<svg width="{w_px}" height="{h_px}"', 1)
    svg_str = svg_str[:m.start()] + tag + svg_str[m.end():]
    png = resvg_py.svg_to_bytes(svg_string=svg_str,
                                background="#ffffff", font_files=fonts or None,
                                shape_rendering="geometric_precision",
                                text_rendering="geometric_precision")
    im = cv2.imdecode(np.frombuffer(bytes(png), np.uint8), cv2.IMREAD_GRAYSCALE)
    if im.shape != (h_px, w_px):
        im = cv2.resize(im, (w_px, h_px), interpolation=cv2.INTER_AREA)
    return im


# ---------------------------------------------------------------- Excellon
def load_drill(path, int_digits=None):
    unit, tools, holes, cur, metric_fmt = 25.4, {}, [], None, False
    lz = True
    for line in open(path, encoding="utf-8", errors="ignore"):
        s = line.strip().upper()
        if not s or s.startswith(";"):
            continue
        if s.startswith("INCH"):
            unit = 25.4; lz = "TZ" not in s
        elif s.startswith("METRIC"):
            unit = 1.0; metric_fmt = True; lz = "TZ" not in s
        m = re.match(r"^T(\d+)C([0-9.]+)", s)
        if m:
            tools[int(m.group(1))] = float(m.group(2)) * unit
            continue
        m = re.match(r"^T(\d+)$", s)
        if m:
            cur = int(m.group(1))
            continue
        m = re.match(r"^X([-+]?[0-9.]+)Y([-+]?[0-9.]+)", s)
        if m and cur in tools:
            def conv(v):
                if "." in v:
                    return float(v) * unit
                neg = v.startswith("-")
                v = v.lstrip("+-")
                nd = int_digits or (3 if metric_fmt else 2)
                dec = 3 if metric_fmt else 4
                if lz:
                    val = int(v) / 10 ** (len(v) - nd) if len(v) > nd else float(v)
                else:
                    val = int(v) / 10 ** dec
                return (-val if neg else val) * unit
            holes.append((conv(m.group(1)), conv(m.group(2)), tools[cur]))
    return holes


def hole_circle(pts):
    """Kreis-Fit (Kasa) auf die konvexe Hülle eines Lochs. Ein Leiterbahn-Ende, das ins Loch
    ragt, ist eine Einbuchtung und liegt nicht auf der Hülle -> verfälscht den Mittelpunkt nicht.
    Nur Hüllpunkte auf dem Kreisbogen verwenden (Sehne über die Einbuchtung iterativ entfernen)."""
    hull = cv2.convexHull(pts).reshape(-1, 2).astype(float)
    # Hülle verdichten, damit lange Sehnen nicht nur durch 2 Punkte vertreten sind
    dense = []
    for a, b in zip(hull, np.roll(hull, -1, axis=0)):
        n = max(1, int(np.hypot(*(b - a))))
        dense.append(a + (b - a) * np.linspace(0, 1, n, endpoint=False)[:, None])
    p = np.vstack(dense)
    if len(p) < 8:
        return None
    keep = np.ones(len(p), bool)
    for _ in range(5):
        x, y = p[keep, 0], p[keep, 1]
        A = np.column_stack([x, y, np.ones_like(x)])
        c, *_ = np.linalg.lstsq(A, x * x + y * y, rcond=None)
        cx, cy = c[0] / 2, c[1] / 2
        r = np.sqrt(c[2] + cx * cx + cy * cy)
        res = np.abs(np.hypot(p[:, 0] - cx, p[:, 1] - cy) - r)
        new = res < max(1.5, 0.04 * r)     # Sehnenpunkte liegen innerhalb -> fallen raus
        if new.sum() < 8 or (new == keep).all():
            break
        keep = new
    return cx, cy, r


def pad_centered(lmask, cx, cy, pxmm, d):
    h, w = lmask.shape
    if not (0 <= cx < w and 0 <= cy < h):
        return False
    rmax = (d / 2 + 2.5) * pxmm
    dist = []
    for ang in np.linspace(0, 2 * np.pi, 16, endpoint=False):
        dx, dy = np.cos(ang), np.sin(ang)
        r = 1.0
        while r < rmax:
            x, y = int(round(cx + dx * r)), int(round(cy + dy * r))
            if not (0 <= x < w and 0 <= y < h):
                break
            if lmask[y, x] != lmask[cy, cx]:
                dist.append(r)
                break
            r += 1
    if len(dist) < 10:
        return False
    dist = np.sort(dist)[len(dist) // 4: -len(dist) // 4 or None]  # Ausreißer (Leiterbahnen) weg
    return dist.std() / pxmm < 0.15


# ---------------------------------------------------------------- Konturen
def contours(mask, pxmm, h_px, w_mm, h_mm, eps):
    cs, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cs:
        if len(c) < 4:
            continue
        c = cv2.approxPolyDP(c, eps * pxmm, True).reshape(-1, 2).astype(float)
        if len(c) < 3:
            continue
        x = np.clip((c[:, 0] - 1 + 0.5) / pxmm, 0, w_mm)
        y = np.clip((h_px - (c[:, 1] - 1 + 0.5)) / pxmm, 0, h_mm)  # DXF: Y nach oben
        out.append(list(zip(x.round(4), y.round(4))))
    return out


def write_dxf(polys, fn, layer, color):
    doc = ezdxf.new("R2010", setup=False)
    doc.units = ezdxf.units.MM
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    doc.layers.add(layer, color=color)
    msp = doc.modelspace()
    for p in polys:
        msp.add_lwpolyline(p, close=True, dxfattribs={"layer": layer})
    doc.saveas(fn)


def write_svg(polys, fn, w_mm, h_mm, fill):
    d = []
    for p in polys:
        d.append("M" + " L".join(f"{x:.4f},{h_mm - y:.4f}" for x, y in p) + " Z")
    style = ('fill="#000000" fill-rule="evenodd" stroke="none"' if fill else
             'fill="none" stroke="#000000" stroke-width="0.01"')
    with open(fn, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.4f}mm" '
                f'height="{h_mm:.4f}mm" viewBox="0 0 {w_mm:.4f} {h_mm:.4f}">\n'
                f'<path {style} d="{" ".join(d)}"/>\n</svg>\n')


def analyze_holes(orig, holes, to_px, pxmm):
    """Findet zu jeder Bohrung das Fritzing-Loch in der gerenderten Maske (1 = kein Kupfer).
    Rückgabe: Liste von dicts (cx, cy, d, li, hx, hy, r, er, ex, ey) in px, Labelbild, Stats,
    Anzahl der Löcher mit eigener (zuverlässiger) SVG-Mitte.
      cx,cy = Bohrdatei   hx,hy,r = runde Lochmitte/-radius   ex,ey,er = Hüllkreis des Fritzing-Lochs"""
    n_lab, lab, st, _ = cv2.connectedComponentsWithStats(orig, connectivity=8)
    info = []
    for x, y, d in holes:
        cx, cy = to_px(x, y)
        R = int(round((d / 2 + 0.3) * pxmm))      # Suchfenster
        Rf = (d / 2 + 0.15) * pxmm                # Teilstücke eines Lochs liegen ganz darin
        x0, y0 = max(0, cx - R), max(0, cy - R)
        win = lab[y0:cy + R + 1, x0:cx + R + 1]
        lis, pts = [], []
        for li in np.unique(win[orig[y0:cy + R + 1, x0:cx + R + 1] > 0]):
            if st[li, cv2.CC_STAT_AREA] > np.pi * R * R * 1.3:   # kein Loch (zu groß)
                continue
            ys, xs = np.nonzero(lab[st[li, 1]:st[li, 1] + st[li, 3],
                                    st[li, 0]:st[li, 0] + st[li, 2]] == li)
            xs, ys = xs + st[li, 0], ys + st[li, 1]
            if np.hypot(xs - cx, ys - cy).max() > Rf:            # ragt aus dem Loch heraus
                continue
            lis.append(int(li)); pts.append(np.column_stack([xs, ys]))
        fit = enc = None
        if lis:   # alle Teilstücke (Leiterbahn-Ende kann das Loch zerschneiden) gemeinsam
            P = np.vstack(pts).astype(np.float32)
            fit = hole_circle(P)
            (ex, ey), er = cv2.minEnclosingCircle(P)
            enc = (ex, ey, er)
        info.append(dict(cx=cx, cy=cy, d=d, li=lis or None, fit=fit, enc=enc))
    # zuverlässig = Versatz (SVG-Mitte − Bohrposition) passt zum Versatz der Nachbarlöcher.
    # Der Versatz ist über die Platine glatt (Maßstab/Ursprung), Fehl-Fits durch große
    # Sicheln fallen dagegen heraus.
    cand = [(i, h["cx"], h["cy"], h["fit"][0] - h["cx"], h["fit"][1] - h["cy"])
            for i, h in enumerate(info)
            if h["fit"] and np.hypot(h["fit"][0] - h["cx"], h["fit"][1] - h["cy"]) < h["d"] / 2 * pxmm]
    cand = np.array(cand) if cand else np.zeros((0, 5))
    ok = set()
    for k in range(len(cand)):
        dist = np.hypot(cand[:, 1] - cand[k, 1], cand[:, 2] - cand[k, 2])
        dist[k] = np.inf
        nb = np.argsort(dist)[:6]
        nb = nb[np.isfinite(dist[nb])]
        if len(nb) == 0 or np.hypot(cand[k, 3] - np.median(cand[nb, 3]),
                                    cand[k, 4] - np.median(cand[nb, 4])) < 0.06 * pxmm:
            ok.add(int(cand[k, 0]))
    for i in ok:
        info[i]["hx"], info[i]["hy"], info[i]["r"] = info[i]["fit"]
    gd = np.array([[h["cx"], h["cy"], h["hx"] - h["cx"], h["hy"] - h["cy"], h["r"], h["d"]]
                   for i, h in enumerate(info) if i in ok]).reshape(-1, 6)
    for i, h in enumerate(info):
        if i in ok:
            continue
        # Versatz und Lochradius von den nächsten zuverlässigen Nachbarn übernehmen
        h["hx"], h["hy"] = h["cx"], h["cy"]
        h["r"] = h["enc"][2] if h["enc"] else h["d"] / 2 * pxmm
        if len(gd):
            dist = np.hypot(gd[:, 0] - h["cx"], gd[:, 1] - h["cy"])
            idx = np.argsort(dist)[:4]
            wgt = 1 / (dist[idx] + pxmm)
            h["hx"] = h["cx"] + np.sum(gd[idx, 2] * wgt) / wgt.sum()
            h["hy"] = h["cy"] + np.sum(gd[idx, 3] * wgt) / wgt.sum()
            same = gd[np.abs(gd[:, 5] - h["d"]) < 1e-3]
            if len(same):
                ds = np.hypot(same[:, 0] - h["cx"], same[:, 1] - h["cy"])
                h["r"] = float(np.median(same[np.argsort(ds)[:4], 4]))
    return info, lab, st, len(ok)


def round_holes_svg(o, log=print):
    """Schreibt eine Kopie der Fritzing-SVG, in der jedes Padloch als exakter Kreis neu
    gezeichnet ist (Sichel der Leiterbahn-Enden mit Kupfer überdeckt). Gibt Dateinamen zurück."""
    o = {**DEFAULTS, **o}
    if not o["drill"]:
        raise ValueError("Für runde Bohrlöcher wird die Bohrdatei benötigt.")
    svg_str, w_mm, h_mm, svg_mir = load_svg(o["svg"], False)
    pxmm = float(o["res"])
    w_px, h_px = int(round(w_mm * pxmm)), int(round(h_mm * pxmm))
    log("Rendere SVG …")
    orig = (render(svg_str, w_px, h_px, []) > 128).astype(np.uint8)
    mir = svg_mir if o["mirror"] == "auto" else (o["mirror"] == "ja")
    holes = load_drill(o["drill"])
    def to_px(x, y):
        if mir:
            x = w_mm - x
        return int(round(x * pxmm)), int(round((h_mm - y) * pxmm))
    res, _, _, n_fit = analyze_holes(orig, holes, to_px, pxmm)

    txt = open(o["svg"], encoding="utf-8").read()
    root = ET.fromstring(txt.encode("utf-8"))
    vb = root.get("viewBox")
    vx, vy, vw, vh = map(float, vb.replace(",", " ").split()) if vb else (0, 0, w_mm, h_mm)
    sx, sy = vw / w_px, vh / h_px                 # px -> SVG-Benutzereinheiten
    g = ['<g id="runde_bohrloecher">']
    for h in res:
        if h["enc"]:                              # altes Loch inkl. Sichel mit Kupfer abdecken
            ex, ey, er = h["enc"]
            g.append(f'<circle cx="{vx + (ex + .5) * sx:.4f}" cy="{vy + (ey + .5) * sy:.4f}" '
                     f'r="{(er + 2) * sx:.4f}" fill="black" stroke="none"/>')
    hole_d = float(o["hole"])                     # > 0: fester Lochdurchmesser in mm
    for h in res:                                 # neues rundes Loch
        r_px = hole_d / 2 * pxmm if hole_d > 0 else h["r"]
        g.append(f'<circle cx="{vx + (h["hx"] + .5) * sx:.4f}" cy="{vy + (h["hy"] + .5) * sy:.4f}" '
                 f'r="{r_px * sx:.4f}" fill="white" stroke="none"/>')
    g.append("</g>\n")
    i = txt.rfind("</svg>")
    out = txt[:i] + "\n".join(g) + txt[i:]
    outdir = o["outdir"] or os.path.dirname(os.path.abspath(o["svg"]))
    os.makedirs(outdir, exist_ok=True)
    fn = os.path.join(outdir, os.path.splitext(os.path.basename(o["svg"]))[0] + "_rund.svg")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(out)
    log(f"Runde Bohrlöcher: {len(res)} (Mitte aus SVG: {n_fit}, aus Nachbarn: {len(res) - n_fit}), "
        f"Ø {'wie SVG' if hole_d <= 0 else f'{hole_d:g} mm'}")
    log(f"  {fn}")
    return fn


def circle_poly(cx, cy, r, n=72):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return list(zip(np.round(cx + r * np.cos(a), 4), np.round(cy + r * np.sin(a), 4)))


def board_outline(path, w_px, h_px, pxmm, h_mm, w_mm, eps):
    """Platinenumriss aus dem Fritzing-Element id='boardoutline' (auch nicht rechteckig)."""
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root = ET.parse(path).getroot()
    keep = None
    for el in root.iter():
        if el.get("id") == "boardoutline":
            keep = el
            break
    if keep is None:                                    # Fallback: Rechteck = SVG-Größe
        return [[(0.0, 0.0), (w_mm, 0.0), (w_mm, h_mm), (0.0, h_mm)]]
    parents = {c: p for p in root.iter() for c in p}
    chain = set()
    el = keep
    while el is not None:
        chain.add(el)
        el = parents.get(el)
    for p in list(root.iter()):                         # alles außer dem Umriss entfernen
        for c in list(p):
            if c not in chain and not any(c is k for k in keep.iter()):
                p.remove(c)
    keep.set("fill", "black"); keep.set("fill-opacity", "1"); keep.set("stroke", "black")
    vb = root.get("viewBox")
    if vb:
        _, _, vw, vh = map(float, vb.replace(",", " ").split())
        root.set("width", repr(vw)); root.set("height", repr(vh))
    for k in ("x", "y"):
        root.attrib.pop(k, None)
    im = render(ET.tostring(root, encoding="unicode"), w_px, h_px, [])
    m = cv2.copyMakeBorder((im < 128).astype(np.uint8), 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cs:
        c = cv2.approxPolyDP(c, eps * pxmm, True).reshape(-1, 2).astype(float)
        if len(c) >= 3:
            out.append(list(zip(np.round((c[:, 0] - 0.5) / pxmm, 4),
                                np.round(h_mm - (c[:, 1] - 0.5) / pxmm, 4))))
    return out


# ---------------------------------------------------------------- Verarbeitung
DEFAULTS = dict(svg="", drill="", mask="", silk="", outdir="", prefix="", profile="CO2 + Lack", rotate=0,
                res=100.0, offset=0.05, mark=0.5, hole=0.0, step=0.06, lines=0, iso=0.0, kerf=0.1,
                eps=0.012, mirror="auto", font="", drop_text=False, mask_invert=False,
                gang1=True, gang2=True, vektor=True, bohren=False, kontur=False, loetstopp=False,
                bestueckung=False)

# Voreinstellungen je Laser. Faserlaser (xTool F1 Ultra): Spot 0,03 mm, Kupfer wird direkt
# abgetragen -> feinere Abstände, nur ein Isolationsstreifen um die Leiterbahnen.
PROFILES = {
    "CO2 + Lack":        dict(offset=0.05, step=0.06, eps=0.012, mark=0.5, iso=0.0, kerf=0.1),
    "Faserlaser direkt": dict(offset=0.015, step=0.025, eps=0.005, mark=0.4, iso=0.3, kerf=0.03),
}


def process(o, log=print):
    """o: dict mit Schlüsseln wie DEFAULTS. Gibt Liste der erzeugten Dateien zurück."""
    o = {**DEFAULTS, **o}
    log(f"fritzing2laser Version {VERSION}  ({os.path.abspath(__file__)})")
    log(f"Profil: {o['profile']}")
    nm = os.path.basename(o["svg"]).lower()
    if "_silk" in nm or "_mask" in nm or "copper" not in nm:
        log("WARNUNG: Die Kupfer-SVG heißt nicht '…_etch_copper_…' – ist das wirklich die Kupferlage?")
    svg_str, w_mm, h_mm, svg_mir = load_svg(o["svg"], o["drop_text"])
    pxmm = float(o["res"])
    w_px, h_px = int(round(w_mm * pxmm)), int(round(h_mm * pxmm))
    log(f"Platine: {w_mm:.2f} x {h_mm:.2f} mm, SVG gespiegelt: {'ja' if svg_mir else 'nein'}")

    fonts = [f for f in [o["font"]] if f and os.path.isfile(f)]
    here = os.path.dirname(os.path.abspath(__file__))
    for fn in ("OCR-Fritzing-mono.ttf", "OCRFritzing-mono.ttf", "OCRA.otf"):
        p = os.path.join(here, fn)
        if os.path.isfile(p) and p not in fonts:
            fonts.append(p)
    if not fonts and not o["drop_text"]:
        log("Hinweis: OCR-Fritzing-mono.ttf nicht gefunden – Kupferschrift mit Ersatzschrift.")

    log("Rendere SVG …")
    im = render(svg_str, w_px, h_px, fonts)
    laser = (im > 128).astype(np.uint8)          # weiß = kein Kupfer = Lack weg

    if o["drop_text"]:
        # Fritzing spart um Kupfertexte die Massefläche aus. Ohne Text bliebe diese Aussparung
        # als Text-Umriss stehen -> Aussparungen, die nur den Text umgeben, mit Kupfer füllen.
        full, _, _, _ = load_svg(o["svg"], False)
        txt = ((render(full, w_px, h_px, fonts) < 128) & (laser > 0)).astype(np.uint8)
        if txt.any():
            # Massefläche = größte Kupferfläche; alles übrige Kupfer (Bahnen, Pads) behält seinen Abstand
            n_c, lab_c, st_c, _ = cv2.connectedComponentsWithStats((laser == 0).astype(np.uint8), connectivity=8)
            filled = 0
            if n_c > 1:
                gnd_id = 1 + int(np.argmax(st_c[1:, cv2.CC_STAT_AREA]))
                gnd = (lab_c == gnd_id).astype(np.uint8)
                other = ((laser == 0) & (gnd == 0)).astype(np.uint8)
                dt_txt = cv2.distanceTransform((1 - txt).astype(np.uint8), cv2.DIST_L2, 5)
                dt_oth = cv2.distanceTransform((1 - other).astype(np.uint8), cv2.DIST_L2, 5)
                # Freistellabstand der Massefläche um den Text: Abstand Text -> Massefläche-Kante
                edge = (laser > 0) & (cv2.dilate(gnd, np.ones((3, 3), np.uint8)) > 0) & (dt_txt < 2.0 * pxmm)
                if edge.any():
                    c = float(np.median(dt_txt[edge]))
                    fill = (laser > 0) & (dt_txt <= c + 1.5) & (dt_oth > c)
                    filled = int(fill.sum())
                    laser[fill] = 0
                    # winzige, frei stehende Reste in der Nähe der Texte ebenfalls schließen
                    nr, lr, sr, _ = cv2.connectedComponentsWithStats(laser, connectivity=8)
                    nearby = dt_txt <= c + 0.3 * pxmm
                    for li in range(1, nr):
                        if sr[li, cv2.CC_STAT_AREA] < 0.02 * pxmm * pxmm:
                            sl = (slice(sr[li, 1], sr[li, 1] + sr[li, 3]),
                                  slice(sr[li, 0], sr[li, 0] + sr[li, 2]))
                            comp = lr[sl] == li
                            if nearby[sl][comp].all():
                                laser[sl][comp] = 0
                    log(f"Texte weggelassen: Aussparung um die Texte (Abstand {c / pxmm:.2f} mm) "
                        f"mit Kupfer gefüllt, Abstände zu Bahnen/Pads bleiben")
            if not filled:
                log("Texte weggelassen (keine Massefläche-Aussparung gefunden)")

    hole_res = []
    if o["drill"]:
        holes = load_drill(o["drill"])
        mir = svg_mir if o["mirror"] == "auto" else (o["mirror"] == "ja")
        def to_px(x, y, m):
            if m:
                x = w_mm - x
            return int(round(x * pxmm)), int(round((h_mm - y) * pxmm))
        orig = laser.copy()
        # Plausibilität: Bohrung sitzt mittig in einem runden Pad -> beide Spiegelungen vergleichen
        score = {m: sum(pad_centered(orig, *to_px(x, y, m), pxmm, d) for x, y, d in holes)
                 for m in (mir, not mir)}
        log(f"Bohrungen: {len(holes)} | passend zu Pads: {score[mir]} "
            f"(andere Spiegelung: {score[not mir]})")
        if score[not mir] > score[mir]:
            log("  WARNUNG: Die andere Spiegelung passt besser -> Spiegelung "
                f"'{'nein' if mir else 'ja'}' probieren!")
        # Fritzing-Padlöcher (von Leiterbahn-Enden angeschnitten) durch runde Zentrierpunkte
        # ersetzen. Mitte = Lochmitte aus der SVG (konzentrisch zum Pad).
        res, lab, st, n_fit = analyze_holes(orig, holes, lambda x, y: to_px(x, y, mir), pxmm)
        hole_res = res
        rr = int(round(float(o["mark"]) / 2 * pxmm))
        for h in res:                 # erst alle Fritzing-Löcher (inkl. Teilstücke) zu Kupfer …
            for li in h["li"] or []:
                sl = (slice(st[li, 1], st[li, 1] + st[li, 3]), slice(st[li, 0], st[li, 0] + st[li, 2]))
                laser[sl][lab[sl] == li] = 0
        if rr > 0:                    # … dann alle runden Zentrierpunkte setzen
            for h in res:
                cv2.circle(laser, (int(round(h["hx"])), int(round(h["hy"]))), rr, 1, -1)
        devs = [np.hypot(h["hx"] - h["cx"], h["hy"] - h["cy"]) / pxmm for h in res]
        log(f"Padlöcher rund ersetzt: {len(res)} (Mitte aus SVG: {n_fit}, aus Nachbarn: "
            f"{len(res) - n_fit}), Abweichung Bohrdatei↔SVG Ø {np.mean(devs):.3f} mm, "
            f"max {np.max(devs):.3f} mm")

    else:
        log("WARNUNG: Keine Bohrdatei angegeben – Fritzing-Löcher bleiben unverändert "
            "(angeschnitten, keine runden Zentrierpunkte)!")

    eps, off = float(o["eps"]), float(o["offset"])
    iso = float(o["iso"])
    if iso > 0:
        # Freie Bereiche am Platinenrand, die nur an EINE Kupferfläche grenzen (z.B. der Rand
        # zwischen Massefläche und Platinenkante), trennen nichts -> nicht isolieren, sonst
        # entsteht ein überflüssiger Rahmen entlang der Kante.
        nc, lab_cu, st_cu, _ = cv2.connectedComponentsWithStats((laser == 0).astype(np.uint8), connectivity=8)
        gnd_id = -1                   # Massefläche: größte Kupferfläche, wenn > 15 % der Platine
        if nc > 1:
            big = 1 + int(np.argmax(st_cu[1:, cv2.CC_STAT_AREA]))
            if st_cu[big, cv2.CC_STAT_AREA] > 0.15 * laser.size:
                gnd_id = big
        nw, lab_w, st_w, _ = cv2.connectedComponentsWithStats(laser, connectivity=8)
        border = set(np.unique(np.concatenate([lab_w[0], lab_w[-1], lab_w[:, 0], lab_w[:, -1]])))
        kept = 0
        for li in border - {0}:
            x0, y0 = max(0, st_w[li, 0] - 1), max(0, st_w[li, 1] - 1)
            sl = (slice(y0, st_w[li, 1] + st_w[li, 3] + 1), slice(x0, st_w[li, 0] + st_w[li, 2] + 1))
            comp = (lab_w[sl] == li).astype(np.uint8)
            ring = cv2.dilate(comp, np.ones((3, 3), np.uint8)) & (comp == 0)
            nets = set(np.unique(lab_cu[sl][ring > 0])) - {0}
            if len(nets) <= 1:
                laser[sl][comp > 0] = 0
                kept += 1
            elif gnd_id in nets:
                # grenzt an die Massefläche UND an weitere Kupferteile (z.B. Befestigungsringe):
                # nur um die anderen Teile isolieren, die Massefläche wächst bis dorthin
                oth = ((lab_cu > 0) & (lab_cu != gnd_id)).astype(np.uint8)
                d_oth = cv2.distanceTransform(1 - oth, cv2.DIST_L2, 5) / pxmm
                fill = (lab_w == li) & (d_oth > iso + 1.0 / pxmm)
                laser[fill] = 0
                kept += 1
        if kept:
            log(f"Randbereich ohne Trennfunktion bleibt Kupfer ({kept} Fläche(n)) – kein Rahmen an der Kante")
    # Abstand zum Kupfer. Mit Isolationsbreite zählt der Platinenrand NICHT als Kupfer
    # (kein Streifen entlang der Kante); ohne wird wie bisher bis an den Rand gefüllt.
    dsrc = cv2.copyMakeBorder(laser, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=1 if iso > 0 else 0)
    dist = cv2.distanceTransform(dsrc, cv2.DIST_L2, cv2.DIST_MASK_PRECISE) / pxmm
    laser = cv2.copyMakeBorder(laser, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    if iso > 0:                       # nur ein Isolationsstreifen um das Kupfer, Rest bleibt stehen
        laser = (laser & (dist <= iso + 0.5 / pxmm)).astype(np.uint8)
        log(f"Isolationsbreite {iso:g} mm: nur Streifen um die Leiterbahnen wird abgetragen")
    jobs = []
    if o["gang1"]:
        log("Gang 1 (Fläche) …")
        jobs.append((contours(laser, pxmm, h_px, w_mm, h_mm, eps), "Gang1_Flaeche", "FLAECHE", 1, True))
    if o["gang2"]:
        log("Gang 2 (Kontur) …")
        k = int(round(off * pxmm)) * 2 + 1
        er = cv2.erode(laser, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) if k > 1 else laser
        jobs.append((contours(er, pxmm, h_px, w_mm, h_mm, eps), "Gang2_Kontur", "KONTUR", 5, False))
    if o["vektor"]:
        # konzentrische Linien um das Kupfer, von der Kupferkante nach außen;
        # lines = 0 -> Spalt vollständig füllen, sonst max. 'lines' Linien
        log("Vektor-Füllung …")
        p3, r, n, nmax = [], off, 0, int(o["lines"])
        rmax = iso - float(o["step"]) / 2 if iso > 0 else np.inf
        while (dist > r).any() and (nmax <= 0 or n < nmax) and (r <= rmax or n == 0):
            if iso > 0:               # Kupfer um r aufgeweitet -> geschlossene Ringe, ohne Rand
                m = (dist <= r).astype(np.uint8)
                m[[0, -1], :] = 0; m[:, [0, -1]] = 0
            else:
                m = (dist > r).astype(np.uint8)
            p3 += contours(m, pxmm, h_px, w_mm, h_mm, eps)
            r += float(o["step"]); n += 1
        log(f"  {n} Linien je Kupferkante" + (f" (Streifen {iso:g} mm)" if iso > 0 else
            f" (alle Spalten vollständig gefüllt: {'ja' if not (dist > r).any() else 'nein'})"))
        jobs.append((p3, "Vektor", "VEKTOR", 5, False))

    kerf = float(o["kerf"])
    if o["bohren"]:
        if not hole_res:
            log("WARNUNG: Bohren gewählt, aber keine Bohrdatei – keine Bohrkonturen.")
        else:
            # Schnittlinie um halbe Schnittbreite nach innen, damit das Loch Nennmaß hat
            pb = [circle_poly((h["hx"] + 0.5) / pxmm, h_mm - (h["hy"] + 0.5) / pxmm,
                              max(h["d"] / 2 - kerf / 2, kerf)) for h in hole_res]
            jobs.append((pb, "Bohren", "BOHREN", 3, False))
            log(f"Bohren: {len(pb)} Kreise (Ø Bohrdatei − Schnittbreite {kerf:g} mm)")
    if o["kontur"]:
        po = board_outline(o["svg"], w_px, h_px, pxmm, h_mm, w_mm, eps)
        jobs.append((po, "Platinenkontur", "KONTUR_PLATINE", 6, False))
        log(f"Platinenkontur: {len(po)} Umriss(e)")
    if o["loetstopp"]:
        if not o["mask"] or not os.path.isfile(o["mask"]):
            log("WARNUNG: Lötstopp gewählt, aber keine Masken-SVG – übersprungen.")
        else:
            ms, mw, mh, mmir = load_svg(o["mask"])
            if abs(mw - w_mm) > 0.05 or abs(mh - h_mm) > 0.05:
                log(f"WARNUNG: Masken-SVG hat andere Größe ({mw:.2f} x {mh:.2f} mm)!")
            if mmir != svg_mir:
                log("WARNUNG: Masken-SVG und Kupfer-SVG sind unterschiedlich gespiegelt!")
            mk = (render(ms, w_px, h_px, fonts) < 128).astype(np.uint8)   # schwarz = Öffnung
            if o["mask_invert"]:
                mk = 1 - mk
            if mk.mean() > 0.5:
                log("WARNUNG: Über die Hälfte der Platine wäre freigelegt – "
                    "Polarität prüfen ('Maske invertieren').")
            mk = cv2.copyMakeBorder(mk, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
            pm = contours(mk, pxmm, h_px, w_mm, h_mm, eps)
            jobs.append((pm, "Loetstopp", "LOETSTOPP", 4, True))
            log(f"Lötstopp-Freistellung: {len(pm)} Öffnungen")

    jobs_top = []                     # Oberseite (nach dem Wenden der Platine)
    if o["bestueckung"]:
        if not o["silk"] or not os.path.isfile(o["silk"]):
            log("WARNUNG: Bestückungsdruck gewählt, aber keine Silk-SVG – übersprungen.")
        else:
            ss, sw_, sh_, smir = load_svg(o["silk"], False)
            if abs(sw_ - w_mm) > 0.05 or abs(sh_ - h_mm) > 0.05:
                log(f"WARNUNG: Silk-SVG hat andere Größe ({sw_:.2f} x {sh_:.2f} mm)!")
            if smir:
                log("WARNUNG: Silk-SVG ist gespiegelt – für die Oberseite die NICHT gespiegelte "
                    "'_etch_silk_top.svg' verwenden!")
            sk = (render(ss, w_px, h_px, fonts) < 128).astype(np.uint8)   # schwarz = Druck
            sk = cv2.copyMakeBorder(sk, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
            ps = contours(sk, pxmm, h_px, w_mm, h_mm, eps)
            jobs_top.append((ps, "Bestueckung", "BESTUECKUNG", 2, True))
            jobs_top.append((board_outline(o["silk"], w_px, h_px, pxmm, h_mm, w_mm, eps),
                             "Bestueckung_Umriss", "UMRISS_OBEN", 6, False))
            log(f"Bestückungsdruck Oberseite: {len(ps)} Flächen (+ Umriss zum Ausrichten)")

    # Drehung (gegen den Uhrzeigersinn positiv), Nullpunkt bleibt unten links
    rot = int(o["rotate"]) % 360
    def rp(p, r):
        if r == 90:  return [(round(h_mm - y, 4), x) for x, y in p]
        if r == 270: return [(y, round(w_mm - x, 4)) for x, y in p]
        if r == 180: return [(round(w_mm - x, 4), round(h_mm - y, 4)) for x, y in p]
        return p
    if rot:
        jobs = [([rp(p, rot) for p in polys], *rest) for polys, *rest in jobs]
        log(f"Gedreht um {int(o['rotate']):+d}°")
    # Oberseite: Platine wird links<->rechts gewendet -> Drehsinn kehrt sich um
    rot_top = (-rot) % 360
    jobs += [([rp(p, rot_top) for p in polys], *rest) for polys, *rest in jobs_top]
    ow, oh = (h_mm, w_mm) if rot in (90, 270) else (w_mm, h_mm)

    prefix = o["prefix"] or re.sub(r"_etch.*$", "", os.path.splitext(os.path.basename(o["svg"]))[0])
    outdir = o["outdir"] or os.path.dirname(os.path.abspath(o["svg"]))
    os.makedirs(outdir, exist_ok=True)
    files = []
    for polys, tag, layer, col, fill in jobs:
        base = os.path.join(outdir, f"{prefix}_{tag}")
        write_dxf(polys, base + ".dxf", layer, col)
        write_svg(polys, base + ".svg", ow, oh, fill)
        files += [base + ".dxf", base + ".svg"]
        log(f"  {base}.dxf/.svg  ({len(polys)} Konturen)")
    log("Fertig.")
    return files


# ---------------------------------------------------------------- Kommandozeile
def main():
    ap = argparse.ArgumentParser(description="Fritzing-Kupfer-SVG -> DXF/SVG für Laser (CO2+Lack oder Faser direkt)")
    ap.add_argument("svg", help="Fritzing Etch-Export, z.B. *_etch_copper_bottom_mirror.svg")
    ap.add_argument("drill", nargs="?", default="", help="Fritzing *_drill.txt (Excellon), optional")
    ap.add_argument("-d", "--outdir", default="", help="Ausgabeordner (Std.: Ordner der SVG)")
    ap.add_argument("-o", "--prefix", default="", help="Dateinamen-Präfix (Std.: Name der SVG ohne _etch...)")
    ap.add_argument("--profile", choices=["co2", "faser"], default="co2",
                    help="Voreinstellung: co2 = CO2-Laser + Lack, faser = Faserlaser trägt Kupfer direkt ab")
    ap.add_argument("--res", type=float, default=None, help="Rasterauflösung px/mm (Std. 100 = 0,01 mm)")
    ap.add_argument("--offset", type=float, default=None,
                    help="Abstand der 1. Linie zur Kupferkante in mm (≈ halber Spot; co2 0.05, faser 0.015)")
    ap.add_argument("--mark", type=float, default=None,
                    help="Durchmesser Zentrierpunkt je Bohrung in mm (0 = aus; co2 0.5, faser 0.4)")
    ap.add_argument("--step", type=float, default=None,
                    help="Linienabstand der Vektor-Füllung in mm (co2 0.06, faser 0.025)")
    ap.add_argument("--lines", type=int, default=None,
                    help="Vektor: max. Anzahl Linien um die Kupferbahnen (0 = unbegrenzt)")
    ap.add_argument("--iso", type=float, default=None,
                    help="Isolationsbreite in mm: nur dieser Streifen um das Kupfer wird gelasert "
                         "(0 = alles Freie; faser 0.3)")
    ap.add_argument("--kerf", type=float, default=None,
                    help="Schnittbreite für Bohren/Platinenkontur in mm (co2 0.1, faser 0.03)")
    ap.add_argument("--bohren", action="store_true", help="Bohrkonturen ausgeben (*_Bohren)")
    ap.add_argument("--kontur", action="store_true", help="Platinenumriss ausgeben (*_Platinenkontur)")
    ap.add_argument("--silk", default="",
                    help="Fritzing '_etch_silk_top.svg' -> *_Bestueckung (Druck auf der Oberseite)")
    ap.add_argument("--mask", default="", help="Fritzing-Lötstopp-SVG -> *_Loetstopp (Pads freilegen)")
    ap.add_argument("--mask-invert", dest="mask_invert", action="store_true",
                    help="Lötstoppmaske invertiert auswerten")
    ap.add_argument("--eps", type=float, default=None, help="Vereinfachungstoleranz mm (co2 0.012, faser 0.005)")
    ap.add_argument("--mirror", choices=["auto", "ja", "nein"], default="auto",
                    help="Bohrungen spiegeln (auto = wie SVG)")
    ap.add_argument("--font", default="", help="Schriftdatei .ttf, z.B. OCR-Fritzing-mono.ttf")
    ap.add_argument("--rotate", type=int, choices=[0, 90, -90, 180], default=0,
                    help="Ausgabe drehen in Grad (+ = gegen den Uhrzeigersinn)")
    ap.add_argument("--round-holes", action="store_true",
                    help="nur Kopie der SVG mit kreisrunden Bohrlöchern erzeugen (*_rund.svg)")
    ap.add_argument("--hole", type=float, default=0.0,
                    help="Lochdurchmesser für --round-holes in mm (0 = wie in der SVG)")
    ap.add_argument("--no-text", dest="drop_text", action="store_true", help="Texte im Kupfer weglassen")
    a = vars(ap.parse_args())
    prof = "Faserlaser direkt" if a.pop("profile") == "faser" else "CO2 + Lack"
    a = {**PROFILES[prof], **{k: v for k, v in a.items() if v is not None}, "profile": prof}
    a["loetstopp"] = bool(a["mask"])
    a["bestueckung"] = bool(a["silk"])
    if a.pop("round_holes"):
        round_holes_svg(a)
    else:
        process(a)


if __name__ == "__main__":
    main()
