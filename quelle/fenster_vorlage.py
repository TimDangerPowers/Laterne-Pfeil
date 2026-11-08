"""Druckvorlage (PDF, 1:1) für das Transparentpapier hinter den Fenstern.

Die Innenflächen von Kanzel, Deck, Bauch, Seitenwänden und Heck werden aus den Maßen in pfeil_jaeger.py
abgewickelt (Falze dort, wo Deck in Fase und Fase in Wand übergeht). Alle Teile sind rundum 0,5 mm kleiner
als der Innenraum, damit sich das Papier nicht wellt.

    python3 -I quelle/fenster_vorlage.py vorlagen/fenster-vorlage.pdf
"""
import sys
from collections import deque
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Polygon, Rectangle

# ---- Maße aus pfeil_jaeger.py (dort bleibt die Quelle der Wahrheit)
T = 1.2
Z_TOP, Z_BOT = 28.0, -30.0
SECTIONS = [(0.0, 88.0, Z_TOP, Z_BOT, 16.0, 12.0), (100.0, 92.0, Z_TOP, Z_BOT, 18.0, 14.0),
            (170.0, 70.0, Z_TOP, Z_BOT, 14.0, 10.0), (245.0, 14.0, -18.0, Z_BOT, 3.0, 3.0)]
CANOPY = [(92.0, 40.0, 31.0, 4.0), (120.0, 46.0, 49.0, 14.0), (150.0, 40.0, 49.0, 13.0), (170.0, 16.0, 31.5, 4.0)]
CAN_SILL = 31.0
Z_SPLIT = -8.0
FIT = 0.5          # Rand, den jedes Teil kleiner ist als der Innenraum


def inner_hull(x):
    """Innenquerschnitt des Rumpfs bei x: (halbe Breite, Oberkante, Unterkante, Fase oben, Fase unten)."""
    for (xa, wa, zta, zba, cta, cba), (xb, wb, ztb, zbb, ctb, cbb) in zip(SECTIONS, SECTIONS[1:]):
        if xa <= x <= xb:
            f = (x - xa) / (xb - xa)
            w, zt, zb, ct, cb = [a + (b - a) * f for a, b in ((wa, wb), (zta, ztb), (zba, zbb), (cta, ctb), (cba, cbb))]
            return (w - 2 * T) / 2, zt - T, zb + T, max(ct - 0.41 * T, 0.01), max(cb - 0.41 * T, 0.01)
    raise ValueError(x)


def inner_canopy(i):
    x, w, zt, ct = CANOPY[i]
    return x, (w - 2 * T) / 2, zt - T, max(ct - 0.5, 0.01)


# ---- Abwicklung eines Streifennetzes (Punkte[i][k] in 3D, Reihen i entlang x, Spalten k rund um das Profil).
# Alle Vierecke sind eben (Wände senkrecht, Fasen 45°, Deck waagerecht), also wird jedes Viereck starr in die Ebene
# gelegt: die Mittelbahn Stück für Stück entlang x, die Nachbarbahnen jeweils an die Falzkante der Mittelbahn.
def quad_local(Q):
    """Ebene 2D-Koordinaten der vier Ecken eines (fast) ebenen Vierecks."""
    Q = np.asarray(Q, float)
    u = Q[3] - Q[0]
    if np.linalg.norm(u) < 1e-6:
        u = Q[2] - Q[1]
    u /= np.linalg.norm(u)
    w = Q[1] - Q[0] if np.linalg.norm(Q[1] - Q[0]) > 1e-6 else Q[2] - Q[3]
    nrm = np.cross(u, w)
    if np.linalg.norm(nrm) < 1e-9:
        nrm = np.cross(u, Q[2] - Q[0])
    nrm /= np.linalg.norm(nrm)
    v = np.cross(nrm, u)
    return np.array([(np.dot(q - Q[0], u), np.dot(q - Q[0], v)) for q in Q])


def fit_edge(loc, ia, ib, a2, b2, far_local, far_known):
    """Starre Abbildung (Drehung/Spiegelung + Verschiebung), die loc[ia]->a2 und loc[ib]->b2 bringt und die
    übrigen Ecken auf die andere Seite der Kante legt als far_known."""
    best = None
    for refl in (1, -1):
        L = loc * np.array([1, refl])
        d_src, d_dst = L[ib] - L[ia], b2 - a2
        ang = np.arctan2(d_dst[1], d_dst[0]) - np.arctan2(d_src[1], d_src[0])
        R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
        M = (R @ L.T).T
        M += a2 - M[ia]
        e = b2 - a2
        nn = np.array([-e[1], e[0]])
        side = np.dot(M[far_local] - a2, nn)
        ok = far_known is None or side * np.dot(far_known - a2, nn) <= 0
        if ok and (best is None or abs(side) > best[0]):
            best = (abs(side), M)
    return best[1]


def unfold(P):
    P = np.asarray(P, float)
    n, m = P.shape[:2]
    pos = {}
    k0 = (m - 1) // 2

    def corners(i, k):
        return [(i, k), (i, k + 1), (i + 1, k + 1), (i + 1, k)]

    # Mittelbahn entlang x
    for i in range(n - 1):
        idx = corners(i, k0)
        loc = quad_local([P[v] for v in idx])
        if i == 0:
            M = loc.copy()
            # Ausrichtung: Falzkante (0,k0)->(1,k0) entlang +x
            d = M[3] - M[0]
            ang = -np.arctan2(d[1], d[0])
            R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
            M = (R @ M.T).T
        else:
            M = fit_edge(loc, 0, 1, pos[(i, k0)], pos[(i, k0 + 1)], 3, pos[(i - 1, k0)])
        for v, q in zip(idx, M):
            pos.setdefault(v, q)
    # Nachbarbahnen nach außen, jeweils an die Falzkante zur schon gelegten Bahn
    for k in list(range(k0 + 1, m - 1)) + list(range(k0 - 1, -1, -1)):
        for i in range(n - 1):
            idx = corners(i, k)
            loc = quad_local([P[v] for v in idx])
            if k > k0:   # geteilte Kante: Spalte k = Ecken 0 und 3; Referenz: Bahn k-1, Ecke (i, k-1)
                M = fit_edge(loc, 0, 3, pos[(i, k)], pos[(i + 1, k)], 1, pos[(i, k - 1)])
            else:        # geteilte Kante: Spalte k+1 = Ecken 1 und 2; Referenz: Bahn k+1, Ecke (i, k+2)
                M = fit_edge(loc, 1, 2, pos[(i, k + 1)], pos[(i + 1, k + 1)], 0, pos[(i, k + 2)])
            for v, q in zip(idx, M):
                pos.setdefault(v, q)
    return pos


def strip_mesh(xs, profile):
    """P[i][k] = 3D-Punkt des Profilpunkts k bei xs[i]; profile(x) liefert Liste von (y, z)."""
    return [[(x, y, z) for y, z in profile(x)] for x in xs]


def outline(pos, n, m):
    ring = [(0, k) for k in range(m)] + [(i, m - 1) for i in range(1, n)] + \
           [(n - 1, k) for k in range(m - 2, -1, -1)] + [(i, 0) for i in range(n - 2, 0, -1)]
    return np.array([pos[v] for v in ring])


def shrink_poly(poly, d):
    """Polygon um d nach innen versetzen."""
    from shapely.geometry import Polygon as SPoly
    g = SPoly(np.asarray(poly)).buffer(0).buffer(-d, join_style=2)
    return np.array(g.exterior.coords)[:-1]


def map_point(pos, P, pt):
    """Punkt auf der 3D-Fläche in die Abwicklung übertragen (baryzentrisch im nächsten Dreieck)."""
    P = np.asarray(P, float)
    n, m = P.shape[:2]
    best = None
    for i in range(n - 1):
        for k in range(m - 1):
            for tri in (((i, k), (i, k + 1), (i + 1, k + 1)), ((i, k), (i + 1, k + 1), (i + 1, k))):
                a, b, c = (P[v] for v in tri)
                nrm = np.cross(b - a, c - a)
                nn = np.linalg.norm(nrm)
                if nn < 1e-9:
                    continue
                nrm /= nn
                q = pt - np.dot(pt - a, nrm) * nrm           # Projektion in die Dreiecksebene
                v0, v1, v2 = b - a, c - a, q - a
                d00, d01, d11, d20, d21 = (np.dot(v0, v0), np.dot(v0, v1), np.dot(v1, v1), np.dot(v2, v0), np.dot(v2, v1))
                den = d00 * d11 - d01 * d01
                v = (d11 * d20 - d01 * d21) / den
                w = (d00 * d21 - d01 * d20) / den
                u = 1 - v - w
                err = -min(u, v, w, 0) + abs(np.dot(pt - a, nrm)) * 0.01
                if best is None or err < best[0]:
                    best = (err, u * pos[tri[0]] + v * pos[tri[1]] + w * pos[tri[2]])
    return best[1]


# ---- Teile
def can_sec(x):
    """Innenprofil der Kanzel bei x: (halbe Breite, Oberkante, Fase)."""
    for (xa, wa, zta, cta), (xb, wb, ztb, ctb) in zip(CANOPY, CANOPY[1:]):
        if xa <= x <= xb:
            f = (x - xa) / (xb - xa)
            w, zt, ct = wa + (wb - wa) * f, zta + (ztb - zta) * f, cta + (ctb - cta) * f
            return (w - 2 * T) / 2, zt - T, max(ct - 0.5, 0.01)
    raise ValueError(x)


def teil_kanzel(xa, xb, fenster, name):
    """Ein Papierstück zwischen zwei Querstreben. Die Kanzel ist zwischen den Streben nicht abwickelbar,
    deshalb drei Stücke (vorn, Mitte, hinten) statt eines langen."""
    zb = Z_TOP + 0.3

    def prof(x):
        hw, zt, ct = can_sec(x)
        if zt - ct < zb:   # an den Enden liegt der Fasenansatz unter dem Papierrand: Rand liegt auf der Fase
            d = zb - (zt - ct)
            return [(hw - d, zb), (hw - d, zb + 0.01), (hw - ct, zt), (-hw + ct, zt), (-hw + d, zb + 0.01), (-hw + d, zb)]
        return [(hw, zb), (hw, zt - ct), (hw - ct, zt), (-hw + ct, zt), (-hw, zt - ct), (-hw, zb)]
    xs = [xa, xb]
    P = strip_mesh(xs, prof)
    pos = unfold(P)
    folds = [[pos[(i, k)] for i in range(len(xs))] for k in (1, 2, 3, 4)]
    marks = []
    for a, b in fenster:
        for s in (1, -1):
            pts3 = []
            for x in (a, b):
                hw, zt, ct = can_sec(x)
                col = [(hw, CAN_SILL), (hw, max(zt - ct, CAN_SILL)), (hw - ct, zt), (1.6, zt)]
                if zt - ct < CAN_SILL:
                    col = [(hw - (CAN_SILL - (zt - ct)), CAN_SILL), (hw - ct, zt), (1.6, zt)]
                pts3.append([(x, s * y, z) for y, z in col])
            poly3 = pts3[0] + pts3[1][::-1]
            marks.append(("Scheibe", [[map_point(pos, P, np.array(q)) for q in poly3]]))
    return dict(name=name, P=P, pos=pos, folds=folds, marks=marks,
                labels=[("hinten", pos[(0, 2)], pos[(0, 3)]), ("vorn", pos[(1, 2)], pos[(1, 3)])])


def teile_kanzel():
    return [teil_kanzel(92.0, 118.5, [(95.0, 116.5)], "Kanzel hinten (Hellblau)"),
            teil_kanzel(117.5, 148.5, [(119.5, 146.5)], "Kanzel Mitte (Hellblau)"),
            teil_kanzel(147.5, 170.0, [(151.5, 166.0)], "Kanzel vorn (Hellblau)")]


def teil_deck():
    xs = [2.0, 50.0, 96.0]
    def prof(x):
        hw, zt, zb, ct, cb = inner_hull(x)
        zw = Z_SPLIT + 0.5                 # bis an die Trennebene (Kragen der Oberschale)
        return [(hw, zw), (hw, zt - ct), (hw - ct, zt), (-hw + ct, zt), (-hw, zt - ct), (-hw, zw)]
    P = strip_mesh(xs, prof)
    pos = unfold(P)
    folds = [[pos[(i, k)] for i in range(len(xs))] for k in (1, 2, 3, 4)]
    marks = []
    zt0 = inner_hull(50)[1]
    for x in (14, 30, 46):
        for y in (-14, 14):
            marks.append(("Fenster", [[map_point(pos, P, np.array((px, py, zt0))) for px, py in
                                       ((x, y - 4), (x + 11, y - 4), (x + 11, y + 4), (x, y + 4))]]))
    for s in (1, -1):
        y0, y1 = (28, 34) if s > 0 else (-34, -28)
        pts = []
        for px, py in ((12, y0), (88, y0), (88, y1), (12, y1)):
            hw, zt, zb, ct, cb = inner_hull(px)
            z = zt - (abs(py) - (hw - ct))              # auf der 45°-Fase
            pts.append(map_point(pos, P, np.array((px, py, z))))
        marks.append(("Schlitz", [pts]))
    return dict(name="Deck der Oberschale (Orange/Gelb), hinten x = 0 bis 96 mm", P=P, pos=pos, folds=folds, marks=marks,
                labels=[("Heck", pos[(0, 2)], pos[(0, 3)]), ("nach vorn", pos[(2, 2)], pos[(2, 3)])])


def teil_bauch():
    xs = [2.0, 60.0, 125.0]
    def prof(x):
        hw, zt, zb, ct, cb = inner_hull(x)
        return [(hw - cb, zb), (-hw + cb, zb)]
    P = strip_mesh(xs, prof)
    pos = unfold(P)
    zb = inner_hull(60)[2]
    marks = [("Fenster", [[map_point(pos, P, np.array((px, py, zb))) for px, py in
                           ((24, y - 3.5), (120, y - 3.5), (120, y + 3.5), (24, y + 3.5))]]) for y in (-23, 23)]
    return dict(name="Bauch der Unterschale (Orange/Gelb)", P=P, pos=pos, folds=[], marks=marks,
                labels=[("Heck", pos[(0, 0)], pos[(0, 1)]), ("nach vorn", pos[(2, 0)], pos[(2, 1)])])


def teil_seite():
    xs = [100.0, 168.0]
    def prof(x):
        hw, zt, zb, ct, cb = inner_hull(x)
        return [(hw, Z_SPLIT + 0.5), (hw, zt - ct)]
    P = strip_mesh(xs, prof)
    pos = unfold(P)
    # TONI-Bereich: x 103..153, z -4,5..8,5 (Schrift 13 mm um z = 2)
    pts = []
    for px, pz in ((103, -4.5), (153, -4.5), (153, 8.5), (103, 8.5)):
        hw = inner_hull(px)[0]
        pts.append(map_point(pos, P, np.array((px, hw, pz))))
    return dict(name="Seitenwand mit TONI (2 Stück, Orange/Gelb)", P=P, pos=pos, folds=[],
                marks=[("TONI", [pts])], labels=[("hinten", pos[(0, 0)], pos[(0, 1)]), ("vorn", pos[(1, 0)], pos[(1, 1)])])


def teil_heck():
    hw, zt, zb, ct, cb = inner_hull(0.5)
    poly = np.array([(-hw + cb, zb), (hw - cb, zb), (hw, zb + cb), (hw, zt - ct), (hw - ct, zt), (-hw + ct, zt),
                     (-hw, zt - ct), (-hw, zb + cb)])
    marks = [("Gitter", [np.array([(y - 3, -22), (y + 3, -22), (y + 3, 18), (y - 3, 18)])]) for y in (-12, 0, 12)]
    marks.append(("Trennebene Ober-/Unterschale: hier durchschneiden", [np.array([(-hw, Z_SPLIT), (hw, Z_SPLIT)])]))
    return dict(name="Heckwand (Orange/Gelb)", poly=poly, folds=[], marks=marks, labels=[("oben", poly[4], poly[5])])


def draw(ax, teil, origin):
    ox, oy = origin
    if "poly" in teil:
        poly = teil["poly"]
    else:
        P = np.asarray(teil["P"])
        poly = outline(teil["pos"], P.shape[0], P.shape[1])
    poly = shrink_poly(poly, FIT) + (ox, oy)
    ax.add_patch(Polygon(poly, closed=True, fill=False, lw=0.8, ec="black"))
    for f in teil["folds"]:
        f = np.array(f) + (ox, oy)
        ax.plot(f[:, 0], f[:, 1], ls=(0, (4, 2)), lw=0.5, color="0.35")
    for label, polys in teil["marks"]:
        for pts in polys:
            pts = np.array(pts) + (ox, oy)
            if len(pts) > 2:
                ax.add_patch(Polygon(pts, closed=True, fill=True, fc="0.85", ec="0.5", lw=0.3))
            else:
                ax.plot(pts[:, 0], pts[:, 1], lw=0.5, color="0.5", ls=":")
                ax.text(pts[:, 0].mean(), pts[:, 1].mean() + 1.2, label, fontsize=5, ha="center", color="0.35")
    for label, a, b in teil["labels"]:
        a, b = np.array(a) + (ox, oy), np.array(b) + (ox, oy)
        ax.text(*((a + b) / 2), label, fontsize=5.5, ha="center", va="center", color="0.3")
    bb = poly.min(axis=0), poly.max(axis=0)
    ax.text(bb[0][0], bb[1][1] + 2.5, teil["name"], fontsize=7, weight="bold")
    return bb


def seite(pdf, teile, titel, hinweis=""):
    fig = plt.figure(figsize=(210 / 25.4, 297 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 210)
    ax.set_ylim(0, 297)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.text(15, 283, "Laterne „Pfeil“ – Schnittvorlage Fensterpapier · " + titel, fontsize=9, weight="bold")
    import textwrap
    txt = ("Mit 100 % drucken (keine Anpassung an die Seite). Kontrollmaß unten muss genau 100 mm sein. Durchgezogen = schneiden, "
           "gestrichelt = falzen (alle Falze zur selben Seite, Papier wird zur Rinne), grau = Fenster dahinter. " + hinweis)
    ax.text(15, 279, "\n".join(textwrap.wrap(txt, 150)), fontsize=6, color="0.3", va="top", linespacing=1.4)
    ax.plot([15, 115], [14, 14], color="black", lw=0.8)
    for x in (15, 115):
        ax.plot([x, x], [12.5, 15.5], color="black", lw=0.8)
    ax.text(65, 16, "Kontrollmaß 100 mm", fontsize=6, ha="center")
    for teil, origin in teile:
        draw(ax, teil, origin)
    pdf.savefig(fig)
    plt.close(fig)


def main(out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    k1, k2, k3 = teile_kanzel()
    dk, ba, se, he = teil_deck(), teil_bauch(), teil_seite(), teil_heck()
    with PdfPages(out) as pdf:
        seite(pdf, [(k1, (25, 225)), (k2, (80, 225)), (k3, (140, 225)), (he, (105, 125)), (se, (20, 55)), (se, (120, 55))],
              "Seite 1: Kanzel, Heck, Seiten",
              "Kanzel: drei Stücke, sie stoßen auf den beiden Querstreben aneinander (Papier erst falzen, dann von unten "
              "in die Kanzel schieben und am Sims festkleben). Seitenwand: eine für links, eine für rechts.")
        seite(pdf, [(dk, (40, 190)), (ba, (40, 70))], "Seite 2: Deck und Bauch")
    print("geschrieben:", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "vorlagen/fenster-vorlage.pdf")
