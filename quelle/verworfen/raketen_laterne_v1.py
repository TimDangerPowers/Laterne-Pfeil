"""Raketen-Laterne für Toni (CadQuery, parametrisch).

Koordinaten: Z nach oben (Laterne hängt mit der Spitze nach oben), Ursprung = Unterkante Heck (Düse/Flossenfüße).

Teile
  spitze       Nasenkegel (Ogive) mit Loch für die Schnur, steckt lose oben auf dem Rumpf
  rumpf        leuchtender Rumpf, dünnwandig, mit Bullaugen und „TONI“, das von innen hell durchscheint
  heck         Heck mit 3 Flossen und Düse; die Rakete steht darauf, wenn die Flamme ab ist
  flamme       Flamme (drehte Sterne), steckt von unten in der Düse; hier hinein kommt die Funkel-Lichterkette
  akkuhalter   Ring mit Steg und Platte: trägt die zwei Akkuboxen und ist der Aufhängepunkt (Schnur)

Kraftfluss beim Tragen: Stab -> Schnur -> Loch in der Spitze (nur durchgeführt) -> Knoten unter dem Steg des
Akkuhalters -> Ring liegt auf der Innenkante im Rumpf -> Rumpf -> Heck -> Flamme. Die Spitze liegt nur auf.

Aufruf: python raketen_laterne.py [ausgabeordner]
"""

import json
import math
import sys
from pathlib import Path

import cadquery as cq

NAME = "TONI"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ---------------------------------------------------------------- Rumpf
R = 45.0            # Außenradius Rumpf (Ø 90)
T = 1.2             # Wand (3 Bahnen à 0,4) – dünn, damit er leuchtet
SKIN = 0.45         # Restwand hinter Schrift und Bullaugen (1 Bahn), leuchtet heller
HB = 120.0          # Rumpfhöhe
RI = R - T
CLEAR = 0.25        # Spiel bei Steckverbindungen

LEDGE_W = 3.0       # Innenkante oben, auf der der Akkuhalter liegt
LEDGE_Z = HB - 14.0

# ---------------------------------------------------------------- Spitze
LN = 85.0           # Länge der Ogive
T_NOSE = 1.2
SPIGOT_H = 10.0     # Kragen, der in den Rumpf greift
TIP_R = 4.5         # Spitze abgeflacht
CORD_D = 4.2        # Schnurloch

# ---------------------------------------------------------------- Heck
T_TAIL = 1.2
SLEEVE_IN = R + CLEAR
SLEEVE_OUT = SLEEVE_IN + T_TAIL
SLEEVE_D = 25.0     # so weit steckt der Rumpf im Heck
EXIT_R = 31.2       # Düsenaustritt außen
THROAT_R = 26.6     # Düsenhals außen
Z_THROAT0, Z_THROAT1 = 10.0, 20.0
Z_CONE1 = 50.0      # Kegel endet, Hülse beginnt
Z_BODY = Z_CONE1 + 3.0          # Unterkante Rumpf (liegt auf der Stufe)
Z_TOP = Z_BODY + SLEEVE_D
N_FIN = 3
FIN_T = 2.4
FIN_R = 76.0        # Flossenspitze (Spannweite 152)
FIN_TIP_H = 18.0    # senkrechte Außenkante
FIN_ROOT_Z = 68.0   # wo die Flosse oben in die Hülse läuft

# ---------------------------------------------------------------- Flamme
FL_L = 85.0         # sichtbare Länge
FL_LOBES = 7
FL_TWIST = 110.0    # Grad Verdrehung über die Länge
FL_T = 1.2
FL_SPIGOT = 16.0
THROAT_IN = THROAT_R - T_TAIL
FL_SPIGOT_R = THROAT_IN - CLEAR
STOP_W = 1.6        # Anschlag oben im Düsenhals, die Flamme stößt dort an

# ---------------------------------------------------------------- Akkuhalter
RING_OUT = RI - 0.4
RING_IN = RI - LEDGE_W - 3.0
RING_T = 3.0
BAR_W, BAR_T = 14.0, 5.0
PLATE_W, PLATE_H, PLATE_T = 56.0, 85.0, 3.0
STRAP_W, STRAP_H = 3.4, 22.0     # Schlitze für 20 mm Klettband


def revolve(pts):
    """Profil (r, z) in der XZ-Ebene um die Z-Achse drehen."""
    return cq.Workplane("XZ").polyline(pts).close().revolve(360, (0, 0, 0), (0, 1, 0))


def cyl(r, h, z0=0.0):
    return cq.Workplane("XY").workplane(offset=z0).circle(r).extrude(h)


def radial_prism(sketch_fn, angle, x0, depth, z):
    """Etwas in einer Ebene senkrecht zur Radiusrichtung zeichnen und nach außen extrudieren."""
    pl = cq.Plane(origin=(x0, 0, z), xDir=(0, 1, 0), normal=(1, 0, 0))
    s = sketch_fn(cq.Workplane(pl)).extrude(depth)
    return s.rotate((0, 0, 0), (0, 0, 1), angle)


# ================================================================ Rumpf
def make_body():
    b = cyl(R, HB).cut(cyl(RI, HB + 2, -1))
    # Innenkante oben (unten 45° -> stützenfrei)
    ledge = revolve([(RI + 0.01, LEDGE_Z - LEDGE_W), (RI + 0.01, LEDGE_Z), (RI - LEDGE_W, LEDGE_Z)])
    b = b.union(ledge)

    thin = cyl(R - SKIN, HB, 0)      # alles innerhalb davon darf weg
    shell_out = cyl(R + 1.6, HB, 0).cut(cyl(R - 0.1, HB, 0))

    # Bullaugen vorn (Winkel 270°): groß oben, klein darunter, mit erhabenem Rand
    for z, rw in ((86.0, 13.0), (52.0, 8.0)):
        win = radial_prism(lambda w: w.circle(rw), 270, 30, 30, z).intersect(thin)
        b = b.cut(win)
        rim = radial_prism(lambda w: w.circle(rw + 3.0).circle(rw), 270, 30, 30, z).intersect(shell_out)
        b = b.union(rim)

    # Name senkrecht, Buchstabe unter Buchstabe, auf der Rückseite (90°), von innen ausgedünnt
    fs, pitch = 15.0, 18.5
    z0 = 30.0 + (len(NAME) - 1) * pitch + fs / 2
    for i, ch in enumerate(NAME):
        z = z0 - i * pitch - fs / 2
        b = b.cut(letter_solid(ch, fs, z, 90).intersect(thin))
    return b


def letter_solid(ch, fs, z, angle):
    pl = cq.Plane(origin=(30, 0, z), xDir=(0, 1, 0), normal=(1, 0, 0))
    s = cq.Workplane(pl).text(ch, fs, 30, halign="center", valign="center", fontPath=FONT)
    return s.rotate((0, 0, 0), (0, 0, 1), angle)


# ================================================================ Spitze
def ogive_r(x):
    """x = Abstand von der Basis (0..LN)."""
    rho = (R * R + LN * LN) / (2 * R)
    return math.sqrt(max(rho * rho - x * x, 0)) + R - rho


def make_nose():
    n = 40
    xs = [LN * i / n for i in range(n + 1)]
    xs = [x for x in xs if ogive_r(x) >= TIP_R] + []
    x_tip = xs[-1]
    out = [(ogive_r(x), x) for x in xs]
    pts = [(0, 0)] + out + [(0, x_tip)]
    solid = cq.Workplane("XZ").moveTo(0, 0)
    prof = cq.Workplane("XZ").polyline([(0, 0), (R, 0)]).spline([(r, z) for r, z in out[1:]], includeCurrent=True)\
        .lineTo(0, x_tip).close()
    nose = prof.revolve(360, (0, 0, 0), (0, 1, 0))
    # innen hohl: gleiche Kurve, um T_NOSE/cos nach innen, oben bleibt ein massiver Kopf
    solid_top = x_tip - 12.0
    inner = []
    for x in xs:
        if x > solid_top:
            break
        # Normalenabstand annähern
        dx = 0.5
        slope = (ogive_r(min(x + dx, LN)) - ogive_r(max(x - dx, 0))) / (2 * dx)
        inner.append((ogive_r(x) - T_NOSE * math.sqrt(1 + slope * slope), x))
    inner = [p for p in inner if p[0] > 2]
    iprof = cq.Workplane("XZ").polyline([(0, -1), (inner[0][0], -1), inner[0]]).spline(inner[1:], includeCurrent=True)\
        .lineTo(0, inner[-1][1]).close()
    nose = nose.cut(iprof.revolve(360, (0, -1, 0), (0, 1, 0)) if False else iprof.revolve(360, (0, 0, 0), (0, 1, 0)))
    # Kragen nach unten
    spig_out = RI - CLEAR
    spig = cyl(spig_out, SPIGOT_H, -SPIGOT_H).cut(cyl(spig_out - T_NOSE, SPIGOT_H + 2, -SPIGOT_H - 1))
    nose = nose.union(spig)
    # Schnurloch
    nose = nose.cut(cyl(CORD_D / 2, 40, x_tip - 30))
    # Spitze leicht verrunden
    try:
        nose = nose.faces(">Z").edges("not %LINE").fillet(1.2)
    except Exception:
        pass
    return nose


# ================================================================ Heck
def tail_outer_r(z):
    if z <= Z_THROAT0:
        return EXIT_R + (THROAT_R - EXIT_R) * z / Z_THROAT0
    if z <= Z_THROAT1:
        return THROAT_R
    if z <= Z_CONE1:
        return THROAT_R + (SLEEVE_OUT - THROAT_R) * (z - Z_THROAT1) / (Z_CONE1 - Z_THROAT1)
    return SLEEVE_OUT


def make_tail():
    ang = math.atan((SLEEVE_OUT - THROAT_R) / (Z_CONE1 - Z_THROAT1))
    off = T_TAIL / math.cos(ang)
    # Kegel innen: r = außen - off; wo erreicht er RI (Stufe für den Rumpf)?
    z_ri = Z_THROAT1 + (RI + off - THROAT_R) / (SLEEVE_OUT - THROAT_R) * (Z_CONE1 - Z_THROAT1)
    bell_off = T_TAIL / math.cos(math.atan((EXIT_R - THROAT_R) / Z_THROAT0))
    prof = [
        (EXIT_R, 0), (THROAT_R, Z_THROAT0), (THROAT_R, Z_THROAT1), (SLEEVE_OUT, Z_CONE1), (SLEEVE_OUT, Z_TOP),
        (SLEEVE_IN, Z_TOP), (SLEEVE_IN, Z_BODY), (RI, Z_BODY), (RI, z_ri),
        (THROAT_IN, Z_THROAT1 + 1.5 + STOP_W), (THROAT_IN - STOP_W, Z_THROAT1 + 1.5), (THROAT_IN - STOP_W, Z_THROAT1),
        (THROAT_IN, Z_THROAT1), (THROAT_IN, Z_THROAT0), (EXIT_R - bell_off, 0),
    ]
    tail = revolve(prof)
    bore = revolve([(0, -1), (EXIT_R - bell_off, -1), (EXIT_R - bell_off, 0), (THROAT_IN, Z_THROAT0),
                    (THROAT_IN - STOP_W, Z_THROAT1), (THROAT_IN - STOP_W, Z_THROAT1 + 1.5),
                    (THROAT_IN, Z_THROAT1 + 1.5 + STOP_W), (RI, z_ri), (RI, Z_BODY), (SLEEVE_IN, Z_BODY), (SLEEVE_IN, Z_TOP + 1),
                    (0, Z_TOP + 1)])
    fin_pts = [(20, 0), (FIN_R, 0), (FIN_R, FIN_TIP_H), (SLEEVE_OUT - 0.5, FIN_ROOT_Z), (30, FIN_ROOT_Z), (20, 30)]
    for k in range(N_FIN):
        fin = (cq.Workplane("XZ").workplane(offset=FIN_T / 2).polyline(fin_pts).close().extrude(FIN_T))
        try:
            fin = fin.edges("|Y").fillet(1.0)
        except Exception:
            pass
        tail = tail.union(fin.rotate((0, 0, 0), (0, 0, 1), 90 + k * 360 / N_FIN), clean=False)
    tail = tail.cut(bore, clean=False)
    return tail


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
    ring = cyl(RING_OUT, RING_T, -RING_T).cut(cyl(RING_IN, RING_T + 2, -RING_T - 1))
    # Unterkante des Rings 45° wie die Kante im Rumpf
    ring = ring.cut(revolve([(RING_OUT + 1, -RING_T - 0.01), (RING_OUT - 1.2, -RING_T - 0.01), (RING_OUT + 1, -RING_T + 2.2)]))
    bar = cq.Workplane("XY").box(2 * RING_IN + 2, BAR_W, BAR_T).translate((0, 0, -BAR_T / 2))
    h = ring.union(bar)
    plate = cq.Workplane("XY").box(PLATE_W, PLATE_T, PLATE_H).translate((0, 0, -BAR_T - PLATE_H / 2 + 0.01))
    # obere Ecken der Platte schräg in den Steg (stabil, stützenfrei)
    h = h.union(plate)
    gus = cq.Workplane("XZ").polyline([(-PLATE_W / 2, -BAR_T), (-RING_IN + 1, -BAR_T), (-PLATE_W / 2, -BAR_T - 14)]).close()\
        .extrude(PLATE_T / 2, both=True)
    h = h.union(gus).union(gus.mirror("YZ"))
    # Schnurloch durch den Steg und Aussparung darunter für den Knoten
    h = h.cut(cyl(2.2, 20, -10))
    h = h.cut(cq.Workplane("XY").box(12, PLATE_T + 2, 14).translate((0, 0, -BAR_T - 7)))
    # Schlitze für Klettband (2 Höhen, links/rechts)
    for z in (-BAR_T - 22, -BAR_T - 66):
        for x in (-(PLATE_W / 2 - 6), PLATE_W / 2 - 6):
            h = h.cut(cq.Workplane("XY").box(STRAP_W, PLATE_T + 2, STRAP_H).translate((x, 0, z)))
    # Kerben am Rand zum Einhängen des Lichterketten-Drahts
    for z in (-BAR_T - 40, -BAR_T - 48, -BAR_T - 82):
        for s in (-1, 1):
            notch = cq.Workplane("XZ").polyline([(0, 1.5), (-3, 0), (0, -1.5)]).close().extrude(PLATE_T / 2 + 1, both=True)
            h = h.cut(notch.translate((s * PLATE_W / 2, 0, z)) if s > 0 else notch.mirror("YZ").translate((-PLATE_W / 2, 0, z)))
    # Griffmulde: zwei Fingerlöcher im Ring zum Herausheben
    return h


# ================================================================ Ausgabe
def build():
    parts = {
        "spitze": make_nose(),
        "rumpf": make_body(),
        "heck": make_tail(),
        "flamme": make_flame(),
        "akkuhalter": make_holder(),
    }
    return parts


def placement():
    """Lage der Teile in der zusammengebauten Rakete (Verschiebung in z)."""
    flame_top = Z_THROAT1 - FL_SPIGOT     # Kragen stößt oben an den Anschlag
    return {
        "heck": 0.0,
        "rumpf": Z_BODY,
        "spitze": Z_BODY + HB,
        "akkuhalter": Z_BODY + LEDGE_Z + RING_T,
        "flamme": flame_top,
    }


def print_pose(name, shape):
    """Für den Druck drehen und aufs Bett legen."""
    if name in ("flamme", "akkuhalter"):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 180)
    if name == "spitze":
        pass
    bb = shape.val().BoundingBox()
    return shape.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    for d in ("druck-k2", "onshape-step", "render"):
        (out / d).mkdir(parents=True, exist_ok=True)
    parts = build()
    pl = placement()
    info = {}
    asm = cq.Assembly()
    for k, s in parts.items():
        v = s.val()
        vol = v.Volume()
        p = print_pose(k, s)
        bb = p.val().BoundingBox()
        info[k] = {"volumen_cm3": round(vol / 1000, 1), "gewicht_pla_g": round(vol / 1000 * 1.24, 0),
                   "groesse_mm": [round(bb.xlen), round(bb.ylen), round(bb.zlen)], "valid": v.isValid()}
        cq.exporters.export(p, str(out / "druck-k2" / f"druck-{k}.stl"), tolerance=0.03, angularTolerance=0.1)
        cq.exporters.export(s, str(out / "onshape-step" / f"{k}.step"))
        placed = s.translate((0, 0, pl[k]))
        cq.exporters.export(placed, str(out / "render" / f"{k}.stl"), tolerance=0.05, angularTolerance=0.15)
        asm.add(placed, name=k)
    # nur für Vorschaubilder: die ausgedünnten Stellen (leuchten heller)
    glow = cyl(R - SKIN - 0.02, HB - 2, 1).cut(cyl(RI + 0.05, HB + 2, -1)).cut(parts["rumpf"])
    cq.exporters.export(glow.translate((0, 0, pl["rumpf"])), str(out / "render" / "glow.stl"), tolerance=0.05)
    asm.save(str(out / "onshape-step" / "raketen-laterne-komplett.step"))
    (out / "render" / "info.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))
