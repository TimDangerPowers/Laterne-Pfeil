"""Raketen-Laterne für Toni, Version 2 „Kapsel“ (CadQuery, parametrisch).

Achteckige Rakete: dunkler Gitterrahmen mit großen Fenstern, innen wird Transparentpapier eingeklebt.
Koordinaten: Z nach oben (Laterne hängt mit der Spitze nach oben), Ursprung = Unterkante Heck.
Achteck: Flächen zeigen in die Richtungen 0°, 45°, 90° ... (gemessen von +X), „Apothem“ = Abstand Mitte–Fläche.
Vorn (Bullaugen) = 270°, hinten (TONI) = 90°.

Teile
  spitze       achteckige Ogive mit 8 kleinen Fenstern, Loch für die Schnur, liegt lose auf dem Rumpf
  rumpf        Gitterrahmen: Bullaugen vorn, TONI als Schablonenschrift hinten, Fenster seitlich, Lichtschlitze
  heck         achteckiges Heck mit 4 Flossen (mit Aussparung) und Düse; die Rakete steht darauf
  flamme       gedrehte Flamme, steckt von unten in der Düse, nimmt die Funkel-Lichterkette auf
  akkuhalter   Ring + Steg + Platte: trägt die zwei Akkuboxen und ist der Aufhängepunkt

Kraftfluss: Stab -> Schnur -> durch die Spitze -> Knoten unter dem Steg des Akkuhalters -> Ring liegt auf der
Innenkante im Rumpf -> Rumpf -> Heck -> Flamme. Die Spitze liegt nur auf.

Aufruf: python raketen_laterne.py [ausgabeordner]
"""

import json
import math
import sys
from pathlib import Path

import cadquery as cq

NAME = "TONI"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CLEAR = 0.25                    # Spiel bei Steckverbindungen

# ---------------------------------------------------------------- Rumpf
A = 45.0                        # Apothem außen (Flächenbreite 37,3 mm)
TB = 1.2                        # Rahmenstärke (3 Bahnen à 0,4)
AI = A - TB
HB = 130.0
WIN_Z0, WIN_Z1 = 31.0, 111.0    # Fensterbereich (unten steckt der Rumpf 25 mm im Heck)
LEDGE_Z = HB - 14.0             # Oberkante der Innenkante für den Akkuhalter
LEDGE_W = 3.0
FRONT, BACK = 270, 90

# ---------------------------------------------------------------- Spitze
LN = 90.0
T_NOSE = 1.2
SPIGOT_H = 10.0
TIP_A = 4.5
CORD_D = 4.2
NOSE_WIN_D, NOSE_WIN_Z = 11.0, 16.0

# ---------------------------------------------------------------- Heck
T_TAIL = 1.2
SLEEVE_IN = A + CLEAR
SLEEVE_OUT = SLEEVE_IN + T_TAIL
SLEEVE_D = 25.0
EXIT_R = 31.2
THROAT_R = 26.6
Z_THROAT0, Z_THROAT1 = 10.0, 20.0
Z_CONE1 = 50.0
Z_BODY = Z_CONE1 + 3.0
Z_TOP = Z_BODY + SLEEVE_D
THROAT_IN = THROAT_R - T_TAIL
STOP_W = 1.6
N_FIN = 4
FIN_T = 2.4
FIN_PTS = [(18, 0), (68, 0), (80, 30), (SLEEVE_OUT - 0.3, Z_TOP - 2), (30, Z_TOP - 2), (18, 25)]
FIN_HOLE = [(52, 8), (65, 8), (71.5, 27), (55, 50)]

# ---------------------------------------------------------------- Flamme
FL_L = 90.0
FL_LOBES = 7
FL_TWIST = 110.0
FL_T = 1.2
FL_SPIGOT = 16.0
FL_SPIGOT_R = THROAT_IN - CLEAR

# ---------------------------------------------------------------- Akkuhalter
RING_OUT = AI - 0.4
RING_IN = AI - LEDGE_W - 3.0
RING_T = 3.0
BAR_W, BAR_T = 14.0, 5.0
PLATE_W, PLATE_H, PLATE_T = 56.0, 85.0, 3.0
STRAP_W, STRAP_H = 3.4, 22.0


# ================================================================ Hilfen
def cyl(r, h, z0=0.0):
    return cq.Workplane("XY").workplane(offset=z0).circle(r).extrude(h)


def octo(half):
    """Achteckiger Drehkörper: half = Umriss (Apothem a, z) von Achse unten über außen bis Achse oben.
    Schnitt von vier Scheiben |x'| <= a(z) in 45°-Schritten ergibt genau ein Achteck mit Apothem a(z)."""
    pts = [(a, z) for a, z in half]
    full = pts + [(-a, z) for a, z in reversed(pts) if a != 0]
    slab = cq.Workplane("XZ").polyline(full).close().extrude(150, both=True)
    s = slab
    for k in (1, 2, 3):
        s = s.intersect(slab.rotate((0, 0, 0), (0, 0, 1), 45 * k))
    return s


def oprism(a, h, z0=0.0):
    return octo([(0, z0), (a, z0), (a, z0 + h), (0, z0 + h)])


def on_face(sketch_fn, angle, a0, depth, z):
    """Skizze auf einer Ebene parallel zur Fläche in Richtung angle, ab Abstand a0 um depth nach außen extrudiert."""
    pl = cq.Plane(origin=(a0, 0, z), xDir=(0, 1, 0), normal=(1, 0, 0))
    return sketch_fn(cq.Workplane(pl)).extrude(depth).rotate((0, 0, 0), (0, 0, 1), angle)


def through(sketch_fn, angle, z, a=A):
    return on_face(sketch_fn, angle, a - 6, 12, z)


# ================================================================ Rumpf
def make_body():
    b = oprism(A, HB).cut(oprism(AI, HB + 2, -1))
    z1, z2 = LEDGE_Z - LEDGE_W, LEDGE_Z
    ledge = oprism(AI + 0.3, z2 - z1, z1).cut(octo([(0, z1 - 1), (AI + 1, z1 - 1), (AI - LEDGE_W, z2), (AI - LEDGE_W, z2 + 1), (0, z2 + 1)]))
    b = b.union(ledge)

    zc = (WIN_Z0 + WIN_Z1) / 2
    # vorn: Bullaugen mit erhabenem Rand
    for z, rw in ((89.0, 14.0), (52.0, 8.5)):
        b = b.cut(through(lambda w: w.circle(rw), FRONT, z))
        b = b.union(on_face(lambda w: w.circle(rw + 3.0).circle(rw), FRONT, A - 0.2, 1.4, z))
    # Seiten (0° und 180°): zwei große Fenster übereinander
    for ang in (0, 180):
        hgt = (WIN_Z1 - WIN_Z0 - 6) / 2
        for z in (WIN_Z0 + hgt / 2, WIN_Z1 - hgt / 2):
            b = b.cut(through(lambda w: w.sketch().rect(26, hgt).vertices().fillet(5).finalize(), ang, z))
    # Schrägflächen: lange Lichtschlitze
    for ang in (45, 135, 225, 315):
        b = b.cut(through(lambda w: w.slot2D(WIN_Z1 - WIN_Z0, 9, 90), ang, zc))
    # hinten: TONI als Schablonenschrift (ausgeschnitten, das O mit zwei Stegen)
    fs, pitch = 18.0, 20.0
    for i, ch in enumerate(NAME):
        z = WIN_Z1 - 10 - i * pitch
        pl = cq.Plane(origin=(A - 6, 0, z), xDir=(0, 1, 0), normal=(1, 0, 0))
        let = cq.Workplane(pl).text(ch, fs, 12, halign="center", valign="center", fontPath=FONT)\
            .rotate((0, 0, 0), (0, 0, 1), BACK)
        b = b.cut(let)
        if ch in "OADBPRQ0698":
            bridge = on_face(lambda w: w.rect(2.2, fs + 4), BACK, AI - 0.01, TB + 0.02, z)
            b = b.union(bridge)
    return b


# ================================================================ Spitze
def ogive_r(x):
    rho = (A * A + LN * LN) / (2 * A)
    return math.sqrt(max(rho * rho - x * x, 0)) + A - rho


def make_nose():
    n = 36
    xs = [LN * i / n for i in range(n + 1)]
    xs = [x for x in xs if ogive_r(x) >= TIP_A]
    x_tip = xs[-1]
    outer = octo([(0, 0)] + [(ogive_r(x), x) for x in xs] + [(0, x_tip)])
    solid_top = x_tip - 12.0
    inner = []
    for x in xs:
        if x > solid_top:
            break
        d = 0.5
        slope = (ogive_r(min(x + d, LN)) - ogive_r(max(x - d, 0))) / (2 * d)
        inner.append((ogive_r(x) - T_NOSE * math.sqrt(1 + slope * slope), x))
    inner = [p for p in inner if p[0] > 2]
    inner_half = [(0, -1), (inner[0][0], -1)] + inner + [(0, inner[-1][1])]
    nose = outer.cut(octo(inner_half))
    spa = AI - CLEAR
    nose = nose.union(oprism(spa, SPIGOT_H, -SPIGOT_H).cut(oprism(spa - T_NOSE, SPIGOT_H + 2, -SPIGOT_H - 1)))
    nose = nose.union(oprism(A - 0.3, 1.6, 0).cut(oprism(spa - T_NOSE, 4, -1)))     # Boden-Ring verbindet Kragen und Schale
    for k in range(8):
        nose = nose.cut(on_face(lambda w: w.circle(NOSE_WIN_D / 2), 45 * k, A - 12, 14, NOSE_WIN_Z))
    nose = nose.cut(cyl(CORD_D / 2, 40, x_tip - 30))
    return nose, inner_half


# ================================================================ Heck
def make_tail():
    ang = math.atan((SLEEVE_OUT - THROAT_R) / (Z_CONE1 - Z_THROAT1))
    off = T_TAIL / math.cos(ang)
    z_ri = Z_THROAT1 + (AI + off - THROAT_R) / (SLEEVE_OUT - THROAT_R) * (Z_CONE1 - Z_THROAT1)
    bell_in = EXIT_R - T_TAIL / math.cos(math.atan((EXIT_R - THROAT_R) / Z_THROAT0))
    outer = octo([(0, 0), (EXIT_R, 0), (THROAT_R, Z_THROAT0), (THROAT_R, Z_THROAT1), (SLEEVE_OUT, Z_CONE1),
                  (SLEEVE_OUT, Z_TOP), (0, Z_TOP)])
    bore = octo([(0, -1), (bell_in, -1), (bell_in, 0), (THROAT_IN, Z_THROAT0), (THROAT_IN - STOP_W, Z_THROAT1),
                 (THROAT_IN - STOP_W, Z_THROAT1 + 1.5), (THROAT_IN, Z_THROAT1 + 1.5 + STOP_W), (AI, z_ri),
                 (AI, Z_BODY), (SLEEVE_IN, Z_BODY), (SLEEVE_IN, Z_TOP + 1), (0, Z_TOP + 1)])
    # Anschlag: obere Kante (THROAT_IN - STOP_W) gerade, darüber 45° wieder auf
    tail = outer
    for k in range(N_FIN):
        fin = cq.Workplane("XZ").workplane(offset=FIN_T / 2).polyline(FIN_PTS).close().extrude(FIN_T)
        hole = cq.Workplane("XZ").workplane(offset=FIN_T).polyline(FIN_HOLE).close().extrude(2 * FIN_T)
        fin = fin.cut(hole)
        tail = tail.union(fin.rotate((0, 0, 0), (0, 0, 1), 45 + 90 * k), clean=False)
    return tail.cut(bore, clean=False)


# ================================================================ Flamme
def flame_section(z_local, scale, amp, twist_deg, n=8 * FL_LOBES, inset=0.0):
    pts = []
    for i in range(n):
        th = 2 * math.pi * i / n
        r = scale * (1 + amp * math.cos(FL_LOBES * th)) - inset
        r = max(r, 0.3)
        a = th + math.radians(twist_deg)
        pts.append(cq.Vector(r * math.cos(a), r * math.sin(a), z_local))
    e = cq.Edge.makeSpline(pts, periodic=True)
    return cq.Wire.assembleEdges([e])


# (z, Radius, Lappen-Amplitude); z=0 Oberkante der Flamme, Kragen (Rohr) darüber, Spitze unten
FLAME_PROFILE = [
    (0.0, FL_SPIGOT_R, 0.0),
    (-14.0, 27.5, 0.16),
    (-30.0, 27.0, 0.20),
    (-48.0, 21.0, 0.24),
    (-64.0, 13.0, 0.26),
    (-76.0, 6.5, 0.26),
    (-FL_L, 1.6, 0.15),
]


def loft(wires):
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    b = BRepOffsetAPI_ThruSections(True, False, 1e-4)
    b.SetMaxDegree(4)
    b.CheckCompatibility(False)
    for w in wires:
        b.AddWire(w.wrapped)
    b.Build()
    return cq.Solid(b.Shape())


def make_flame():
    def twist(z):
        return -FL_TWIST * z / FL_L

    outer = loft([flame_section(z, r, a, twist(z)) for z, r, a in FLAME_PROFILE])
    inner_prof = [(z, r, a) for z, r, a in FLAME_PROFILE if r - FL_T > 1.2]
    sec = [flame_section(z, r, a, twist(z), inset=FL_T) for z, r, a in inner_prof]
    # oben über den Kragen hinaus, damit die Öffnung sauber ist
    z0, r0, a0 = inner_prof[0]
    sec = [flame_section(z0 + 1.0, r0, a0, 0.0, inset=FL_T)] + sec
    inner = loft(sec)
    # Kragen als eigenes Rohr, stumpf auf die Oberkante gesetzt (überlappende Booleans scheitern am Loft)
    tube = cyl(FL_SPIGOT_R, FL_SPIGOT, 0).cut(cyl(FL_SPIGOT_R - FL_T, FL_SPIGOT + 2, -1)).val()
    return cq.Workplane("XY").add(outer.cut(inner).fuse(tube).clean())



# ================================================================ Akkuhalter
def make_holder():
    """Gebaut in Gebrauchslage: Ring oben (z=0 = Oberseite), Platte hängt nach unten."""
    h = oprism(RING_OUT, RING_T, -RING_T).cut(oprism(RING_IN, RING_T + 2, -RING_T - 1))
    h = h.union(cq.Workplane("XY").box(2 * RING_IN + 2, BAR_W, BAR_T).translate((0, 0, -BAR_T / 2)))
    h = h.union(cq.Workplane("XY").box(PLATE_W, PLATE_T, PLATE_H).translate((0, 0, -BAR_T - PLATE_H / 2 + 0.01)))
    gus = cq.Workplane("XZ").polyline([(-PLATE_W / 2, -BAR_T), (-RING_IN + 1, -BAR_T), (-PLATE_W / 2, -BAR_T - 14)]).close()\
        .extrude(PLATE_T / 2, both=True)
    h = h.union(gus).union(gus.mirror("YZ"))
    h = h.cut(cyl(2.2, 20, -10))                                                  # Schnurloch
    h = h.cut(cq.Workplane("XY").box(12, PLATE_T + 2, 14).translate((0, 0, -BAR_T - 7)))   # Platz für den Knoten
    for z in (-BAR_T - 22, -BAR_T - 66):                                          # Klettband-Schlitze
        for x in (-(PLATE_W / 2 - 6), PLATE_W / 2 - 6):
            h = h.cut(cq.Workplane("XY").box(STRAP_W, PLATE_T + 2, STRAP_H).translate((x, 0, z)))
    for z in (-BAR_T - 40, -BAR_T - 48, -BAR_T - 82):                             # Kerben für den Lichterdraht
        notch = cq.Workplane("XZ").polyline([(0, 1.5), (-3, 0), (0, -1.5)]).close().extrude(PLATE_T / 2 + 1, both=True)
        h = h.cut(notch.translate((PLATE_W / 2, 0, z))).cut(notch.mirror("YZ").translate((-PLATE_W / 2, 0, z)))
    return h


# ================================================================ Ausgabe
def placement():
    return {
        "heck": 0.0,
        "rumpf": Z_BODY,
        "spitze": Z_BODY + HB,
        "akkuhalter": Z_BODY + LEDGE_Z + RING_T,
        "flamme": Z_THROAT1 - FL_SPIGOT,
    }


def print_pose(name, shape):
    if name in ("flamme", "akkuhalter"):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 180)
    bb = shape.val().BoundingBox()
    return shape.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


def render_paper(nose_inner_half):
    """Nur für Vorschaubilder: Transparentpapier innen im Rumpf und hinter den Fenstern der Spitze."""
    body = oprism(AI - 0.05, WIN_Z1 - WIN_Z0 + 6, WIN_Z0 - 3).cut(oprism(AI - 0.5, 200, -10))
    shrink = [(max(a - 0.05, 0), z) for a, z in nose_inner_half]
    shrink2 = [(max(a - 0.5, 0), z) for a, z in nose_inner_half]
    band = octo(shrink).cut(octo(shrink2)).intersect(cyl(80, NOSE_WIN_D + 4, NOSE_WIN_Z - NOSE_WIN_D / 2 - 2))
    return body, band


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    for d in ("druck-k2", "onshape-step", "render"):
        (out / d).mkdir(parents=True, exist_ok=True)
    nose, nose_inner = make_nose()
    parts = {"spitze": nose, "rumpf": make_body(), "heck": make_tail(), "flamme": make_flame(), "akkuhalter": make_holder()}
    pl = placement()
    info = {}
    asm = cq.Assembly()
    for k, s in parts.items():
        v = s.val()
        p = print_pose(k, s)
        bb = p.val().BoundingBox()
        info[k] = {"volumen_cm3": round(v.Volume() / 1000, 1), "gewicht_pla_g": round(v.Volume() / 1000 * 1.24),
                   "groesse_mm": [round(bb.xlen), round(bb.ylen), round(bb.zlen)], "valid": v.isValid(),
                   "solids": len(v.Solids())}
        cq.exporters.export(p, str(out / "druck-k2" / f"druck-{k}.stl"), tolerance=0.03, angularTolerance=0.1)
        cq.exporters.export(s, str(out / "onshape-step" / f"{k}.step"))
        placed = s.translate((0, 0, pl[k]))
        cq.exporters.export(placed, str(out / "render" / f"{k}.stl"), tolerance=0.05, angularTolerance=0.15)
        asm.add(placed, name=k)
    pb, pn = render_paper(nose_inner)
    cq.exporters.export(pb.translate((0, 0, pl["rumpf"])), str(out / "render" / "papier.stl"), tolerance=0.05)
    cq.exporters.export(pn.translate((0, 0, pl["spitze"])), str(out / "render" / "papier-spitze.stl"), tolerance=0.05)
    asm.save(str(out / "onshape-step" / "raketen-laterne-komplett.step"))
    (out / "render" / "info.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info))
