"""Drei grobe Raumschiff-Konzepte (Massenmodelle) für Tonis Laterne. X = vorn, Y = links, Z = oben.
Jedes Konzept schreibt Teile nach render/<konzept>/<farbe>.stl (Farbe = Material im Renderer)."""
import math, sys
from pathlib import Path
import cadquery as cq


def section(x, w, h, zc=0.0, chamfer=0.3):
    """Flaches Sechseck/Achteck-Profil (Facettenlook) in der Ebene x = const."""
    c = min(w, h) * chamfer
    pts = [(-w / 2 + c, -h / 2), (w / 2 - c, -h / 2), (w / 2, -h / 2 + c), (w / 2, h / 2 - c),
           (w / 2 - c, h / 2), (-w / 2 + c, h / 2), (-w / 2, h / 2 - c), (-w / 2, -h / 2 + c)]
    return cq.Wire.makePolygon([cq.Vector(x, y, z + zc) for y, z in pts], close=True)


def loft(secs):
    return cq.Workplane().add(cq.Solid.makeLoft(secs, True))


def plate(pts_xy, t, z=0.0):
    return cq.Workplane("XY").workplane(offset=z - t / 2).polyline(pts_xy).close().extrude(t)


def mirror_y(wp):
    return wp.union(wp.mirror("XZ"))


def cylx(r, x0, x1, y=0, z=0):
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).circle(r).extrude(x1 - x0)


def conex(r0, r1, x0, x1, y=0, z=0):
    d = 1 if x1 > x0 else -1
    return cq.Workplane().add(cq.Solid.makeCone(r0, r1, abs(x1 - x0), cq.Vector(x0, y, z), cq.Vector(d, 0, 0)))


# ------------------------------------------------------------ A: Pfeiljäger „Falke“
def falke():
    hull = loft([section(-10, 70, 56), section(140, 84, 66), section(215, 56, 40, -6), section(300, 8, 6, -12)])
    canopy = loft([section(130, 40, 2, 32), section(170, 44, 30, 40, 0.35), section(225, 20, 4, 22)])
    wing = plate([(0, 30), (140, 30), (55, 150), (20, 150), (0, 110)], 5, -14)
    tipgun = cylx(4, 10, 150, 150, -14).union(cylx(7, 15, 70, 150, -14))
    eng = cylx(22, -30, 90, 52, 2).union(conex(22, 26, -40, -30, 52, 2))
    glow_eng = cylx(18, -41, -40, 52, 2)
    flame = conex(17, 1, -41, -130, 52, 2)
    fin = plate([(-10, 0), (40, 0), (5, 55), (-20, 55)], 4).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, 0, 28))
    strips = [plate([(x0, 0), (x0 + 60, 0), (x0 + 60, 3), (x0, 3)], 1).rotate((0, 0, 0), (1, 0, 0), 90)
              .translate((0, 42.6, z)) for x0, z in ((30, 8), (30, -2), (100, 8))]
    gl = strips[0]
    for s in strips[1:]:
        gl = gl.union(s)
    return {"rumpf": hull.union(fin), "hell": mirror_y(wing.union(tipgun)).union(mirror_y(eng)),
            "kanzel": canopy, "fenster": mirror_y(gl), "triebwerk": mirror_y(glow_eng), "flamme": mirror_y(flame)}


# ------------------------------------------------------------ B: Keil-Kreuzer „Pfeilspitze“
def keil():
    hull = loft([section(0, 190, 60, 0, 0.25), section(150, 120, 46, -4, 0.25), section(310, 14, 8, -16, 0.3)])
    deck = loft([section(20, 90, 4, 28), section(90, 70, 26, 38, 0.3), section(180, 20, 4, 22)])
    fins = mirror_y(plate([(0, 0), (40, 0), (10, 60), (-15, 60)], 4).rotate((0, 0, 0), (1, 0, 0), 70).translate((0, 80, 20)))
    eng = cylx(30, -25, 5, 0, 0).union(cylx(18, -18, 5, 60, -2)).union(cylx(18, -18, 5, -60, -2))
    glow = cylx(25, -26, -25).union(cylx(14, -19, -18, 60, -2)).union(cylx(14, -19, -18, -60, -2))
    flame = conex(24, 1, -26, -120).union(conex(13, 1, -19, -80, 60, -2)).union(conex(13, 1, -19, -80, -60, -2))
    # Fensterreihen schräg an den Flanken
    win = None
    for i in range(9):
        x = 20 + i * 24
        ww = 190 - (190 - 14) * x / 310
        s = plate([(x, 0), (x + 14, 0), (x + 14, 4), (x, 4)], 1).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, ww / 2 + 0.3, 2 - x * 0.04))
        win = s if win is None else win.union(s)
    spine = plate([(30, -3), (230, -2), (230, 2), (30, 3)], 1, 0).translate((0, 0, 30 - 0.0))
    return {"rumpf": hull.union(fins), "hell": deck.union(eng), "fenster": mirror_y(win), "kanzel": spine,
            "triebwerk": glow, "flamme": flame}


# ------------------------------------------------------------ C: Ringjäger „Komet“
def ring():
    hull = loft([section(-20, 70, 70, 0, 0.29), section(170, 70, 70, 0, 0.29), section(250, 36, 30, -6, 0.3), section(300, 6, 6, -10)])
    canopy = loft([section(150, 34, 2, 34), section(185, 38, 22, 40, 0.35), section(240, 14, 4, 16)])
    R, w = 115, 55
    ringo = cq.Workplane("YZ").workplane(offset=-30).circle(R).circle(R - 6).extrude(w)
    ringglow = cq.Workplane("YZ").workplane(offset=-28).circle(R - 6).circle(R - 7).extrude(w - 4)
    struts = None
    for k in range(4):
        a = 45 + 90 * k
        s = plate([(-25, 30), (40, 30), (20, R - 3), (-25, R - 3)], 4).rotate((0, 0, 0), (1, 0, 0), a)
        struts = s if struts is None else struts.union(s)
    glow = cylx(26, -31, -30)
    flame = conex(26, 1, -31, -140)
    stripes = None
    for k in range(4):
        a = 90 * k
        s = plate([(30, -2), (150, -2), (150, 2), (30, 2)], 1).translate((0, 0, 35.3)).rotate((0, 0, 0), (1, 0, 0), a)
        stripes = s if stripes is None else stripes.union(s)
    return {"rumpf": hull.union(cylx(30, -30, -20)), "hell": ringo.union(struts), "kanzel": canopy,
            "fenster": ringglow.union(stripes), "triebwerk": glow, "flamme": flame}


if __name__ == "__main__":
    out = Path(sys.argv[1])
    for name, fn in (("a", falke), ("b", keil), ("c", ring)):
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        for k, s in fn().items():
            cq.exporters.export(s, str(d / f"{k}.stl"), tolerance=0.1, angularTolerance=0.2)
        print(name, "ok")
