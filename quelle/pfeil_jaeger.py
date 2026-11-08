"""Laterne für Toni: Raumjäger „Pfeil“ (CadQuery, parametrisch).

Die Laterne hängt waagerecht am Stab, als würde der Jäger vorbeifliegen.
Koordinaten: X nach vorn (Nase), Y nach links, Z nach oben. Ursprung: Heckwand, Rumpfmitte.

Teile
  rumpf-unten     Unterschale mit Nase, Flügelschlitzen, Bauchfenstern, Aufhängepfosten und Klettschlitzen für die Akkus
  rumpf-oben      Oberschale (Deck) mit Fenstern, TONI-Schriftzug an beiden Seiten, Kanzel- und Leitwerksöffnung;
                  liegt lose auf der Unterschale (Kragen) und wird zum Einschalten abgehoben
  kanzel          Cockpitrahmen, innen blaues Transparentpapier
  leitwerk        Seitenleitwerk, steckt im Deck
  fluegel-links/-rechts   Flügel mit Kanone, Laschen werden in die Rumpfschlitze geklebt
  triebwerk (2x)  Triebwerksgondel, sitzt auf dem Flügel, hinten steckt die Flamme
  flamme (2x)     gedrehte Flamme, nimmt die Funkel-Lichterkette auf
  flammengitter (2x) dünne Gitterscheibe auf dem Kragenende der Flamme, trägt die zwei LEDs

Kraftfluss: Stab -> Schnur -> Schlitz im Deck (nur durchgeführt) -> Knoten am Pfosten der Unterschale.
Die Oberschale liegt nur auf; die Schnur hält sie mittig.

Aufruf: python pfeil_jaeger.py [ausgabeordner]
"""

import json
import math
import sys
from pathlib import Path

import cadquery as cq

NAME = "TONI"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CLEAR = 0.25
T = 1.2                         # Wandstärke (3 Bahnen à 0,4)

# ---------------------------------------------------------------- Rumpf
# Querschnitte (x, Breite, Oberkante, Unterkante, Fase oben, Fase unten). Deck und Boden sind flach (druckt ohne Stützen).
Z_TOP, Z_BOT = 28.0, -30.0
SECTIONS = [
    (0.0, 88.0, Z_TOP, Z_BOT, 16.0, 12.0),
    (100.0, 92.0, Z_TOP, Z_BOT, 18.0, 14.0),
    (170.0, 70.0, Z_TOP, Z_BOT, 14.0, 10.0),
    (245.0, 14.0, -18.0, Z_BOT, 3.0, 3.0),
]
X_DECK = 170.0                  # bis hier reicht die Oberschale, davor gehört die Nase zur Unterschale
Z_SPLIT = -8.0                  # Trennebene Ober-/Unterschale
LIP_H = 5.0                     # Kragen der Oberschale, greift in die Unterschale

# ---------------------------------------------------------------- Kanzel
CANOPY = [  # (x, Breite, Oberkante, Fase oben)
    (92.0, 40.0, 31.0, 4.0),
    (120.0, 46.0, 49.0, 14.0),
    (150.0, 40.0, 49.0, 13.0),
    (170.0, 16.0, 31.5, 4.0),
]
CAN_RIM = 1.0                   # Kragen der Kanzel steht 1 mm innerhalb der Außenhaut (druckt ohne Stütze)
CAN_FRAMES = (118.0, 148.0)     # Querstreben der Kanzel
CAN_SILL = 31.0                 # bis hierhin bleibt die Kanzel geschlossen (Sims)

# ---------------------------------------------------------------- Flügel und Triebwerke
Z_WING = -14.0
WING_T = 3.0
WING = None   # wird unten aus den Rumpfquerschnitten gebaut (Wurzel folgt der Rumpfseite)
WING_HOLES = [[(14, 60), (14, 100), (26, 124), (42, 124), (74, 70), (70, 60)]]
TABS = [(14, 28), (50, 64), (84, 98)]   # x-Bereiche der Laschen
TAB_IN = 7.0
GUN_Y = 144.5                   # Mitte des Kanonenfußes (Block bündig mit der Flügelspitze)
GUN_W, GUN_H = 11.0, 11.5       # Kanonenfuß: Block auf dem Flügel, Breite und Höhe über dem Flügel
GUN_X0, GUN_X1 = 4.0, 64.0
GUN_SLOT_W = 7.0                # offener Schacht im Fuß (Kette hin und zurück), Deckel obendrauf
TUNNEL_R = 3.3                  # Durchlass für die LED-Kapseln (5,4 mm) durch Fuß und Zapfen
BARREL_R, BARREL_X1 = 6.7, 140.0  # Rohr aus grau-transparentem Filament, innen eine LED der Lichterkette
BARREL_BORE = 7.2
SPIGOT_R, SPIGOT_L = 4.5, 8.0
DUCT = ((98.8, 47.0), (42.2, 139.0))   # Kabelkanal auf dem Flügel, parallel zur Vorderkante
DUCT_W, DUCT_H = 7.0, 6.2       # Kabelkanal innen (offen nach oben, Deckel wird eingelegt)
COVER_T = 1.2                   # Deckel von Kanal und Fuß
CABLE_R = 3.2                   # Kabellöcher in der Rumpfseite (LED-Kapseln müssen durch)
CABLE_X = (40.0, 102.0)         # Kabellöcher in der Rumpfseite: Triebwerk, Kanone
CABLE_Z = Z_WING + WING_T / 2 + 2.5   # knapp über dem Flügel (ragt 0,7 mm in die Oberschale)
HEAD_Y, HEAD_Z, HEAD_D = 3.4, -24.0, 5.6   # Scheinwerfer in der Nasenspitze

ENG_R = 18.0
ENG_Y = 65.5          # 2 mm Luft zur Oberschale, damit sie sich abheben lässt
ENG_X0, ENG_L = -38.0, 118.0    # Austritt hinten, Länge bis zur Spitze
ENG_Z = Z_WING + WING_T / 2 + ENG_R
THROAT_R, THROAT_U0, THROAT_U1 = 15.6, 7.0, 15.0
STOP_W = 1.4

# ---------------------------------------------------------------- Flamme
FL_L = 70.0
FL_LOBES = 6
FL_TWIST = 110.0
FL_T = 1.6
FL_SPIGOT = 14.0
FL_SPIGOT_R = THROAT_R - T - CLEAR
FLAME_PROFILE = [
    (0.0, FL_SPIGOT_R, 0.0),
    (-10.0, 17.5, 0.16),
    (-24.0, 17.0, 0.20),
    (-38.0, 13.0, 0.24),
    (-50.0, 8.5, 0.26),
    (-60.0, 4.5, 0.24),
    (-FL_L, 1.2, 0.12),
]

# ---------------------------------------------------------------- Griff am Stab
# Im Griff sitzen der ESP32-C3 und zwei Arcade-Taster. Strom kommt über ein magnetisches USB-C-Kabel von der
# Powerbank im Rucksack (löst sich, wenn jemand daran zieht). Zum Schiff geht nur ein 3-adriges Kabel.
GRIP_T, GRIP_TOP, GRIP_LID = 2.4, 3.0, 2.4
GRIP_IN_L, GRIP_IN_W, GRIP_IN_H = 96.0, 34.0, 34.0
GRIP_L = GRIP_IN_L + 2 * GRIP_T
GRIP_W = GRIP_IN_W + 2 * GRIP_T
GRIP_H = GRIP_IN_H + GRIP_TOP
GRIP_BTN_D = 24.2               # Arcade-Taster 24 mm (Feuer rot, Turbo blau)
GRIP_BTN_X = (22.0, 51.0)
GRIP_BTN_PANEL = 1.6             # Deckenstärke am Taster (Sanwa-artige Schnapp-Taster sind für 1,6 mm gebaut)
GRIP_BTN_RECESS = 28.0           # Mulde innen um jeden Taster       # ab Innenkante hinten (Kabelseite zum Schiff)
ESP_X = (70.0, 92.5)            # ESP32-C3 SuperMini liegt auf einem Bock, USB-C zeigt zur Stirnwand
BLOCK_POCKET = 1.0              # Tiefe der Tasche für den Bock im Griffboden
ESP_BLOCK_H = 16.0              # Platz für die Dupont-Stecker unter der Platine
USB_Z = GRIP_LID * 0 + ESP_BLOCK_H + 3.0
STICK_D = 20.0                  # V-Kerbe für den Bambusstab (passt für ca. 8-22 mm)

# ---------------------------------------------------------------- Aufhängung
POST_X = (40.0, 76.0)           # Pfosten in der Unterschale, 3 Löcher zum Ausbalancieren (Schwerpunkt bei ca. 55 mm)
POST_HOLES = (47.0, 55.0, 63.0)
POST_T = 4.0
HANG_SLOT = (42.0, 70.0)        # Schlitz im Deck darüber (10 mm breit, der JST-Stecker muss durch)


# ================================================================ Hilfen
def sec_wire(x, w, zt, zb, ct, cb, grow=0.0):
    w, zt, zb = w + 2 * grow, zt + grow, zb - grow
    ct, cb = max(ct + grow * 0.41, 0.01), max(cb + grow * 0.41, 0.01)
    pts = [(-w / 2 + cb, zb), (w / 2 - cb, zb), (w / 2, zb + cb), (w / 2, zt - ct),
           (w / 2 - ct, zt), (-w / 2 + ct, zt), (-w / 2, zt - ct), (-w / 2, zb + cb)]
    return cq.Wire.makePolygon([cq.Vector(x, y, z) for y, z in pts], close=True)


def ruled(wires):
    return cq.Workplane().add(cq.Solid.makeLoft(wires, True))


def hull(grow=0.0, x0=None, x1=None, secs=SECTIONS):
    """Rumpf als Facettenkörper; grow < 0 schrumpft ihn (Innenraum)."""
    ws = []
    for x, w, zt, zb, ct, cb in secs:
        ws.append(sec_wire(x, w, zt, zb, ct, cb, grow))
    s = ruled(ws)
    if x0 is not None or x1 is not None:
        a, b = (x0 if x0 is not None else -50), (x1 if x1 is not None else 300)
        s = s.intersect(box(a, b, -200, 200, -100, 100))
    return s


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def half_w(x):
    """Halbe Rumpfbreite bei x (linear zwischen den Querschnitten)."""
    for (xa, wa, *_), (xb, wb, *_) in zip(SECTIONS, SECTIONS[1:]):
        if xa <= x <= xb:
            return (wa + (wb - wa) * (x - xa) / (xb - xa)) / 2
    return SECTIONS[-1][1] / 2


# Draufsicht linker Flügel (y > 0): Wurzelkante folgt der Rumpfseite (+0,3 mm Luft), Spitze bei y = 150
WING = [(0, half_w(0) + 0.3), (0, 112.0), (16, 150.0), (46, 150.0), (110, half_w(110) + 0.3), (100, half_w(100) + 0.3)]


def cylx(r, x0, x1, y=0.0, z=0.0):
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).circle(r).extrude(x1 - x0)


def side_cut(sketch_fn, y_side, x, z):
    """Ausschnitt durch die linke (y_side=1) oder rechte (-1) Seitenwand, Skizze in Weltkoordinaten (x nach vorn, z hoch)
    so, dass sie von außen richtig lesbar ist."""
    if y_side > 0:
        pl = cq.Plane(origin=(x, 30, z), xDir=(-1, 0, 0), normal=(0, 1, 0))
    else:
        pl = cq.Plane(origin=(x, -30, z), xDir=(1, 0, 0), normal=(0, -1, 0))
    return sketch_fn(cq.Workplane(pl))


# ================================================================ Rumpf
def shell_solid():
    outer = hull()
    inner = hull(-T, x0=T, x1=SECTIONS[-1][0] - 12)
    return outer.cut(inner), inner


def make_hull_parts():
    sh, inner = shell_solid()
    top_zone = box(-1, X_DECK, -100, 100, Z_SPLIT, 100)
    top = sh.intersect(top_zone)
    bot = sh.cut(top_zone)

    # Kragen der Oberschale nach unten, mit Spiel innen an der Unterschale
    lip = hull(-T - CLEAR, x0=T + CLEAR, x1=X_DECK - 1).cut(hull(-2 * T - CLEAR, x0=-10, x1=400))\
        .intersect(box(-5, X_DECK, -100, 100, Z_SPLIT - LIP_H, Z_SPLIT + 0.5))
    # Steg zur Wand als Treppe (je 0,5 mm Höhe, 0,29 mm Versatz = ca. 30°), damit der Kragen ohne Stütze druckt
    for k in range(4):
        o = -2 * T - CLEAR + (k + 1) * (T + CLEAR) / 5
        lip = lip.union(hull(-T + 0.05, x0=T + CLEAR, x1=X_DECK - 1).cut(hull(o, x0=-10, x1=400))
                        .intersect(box(-5, X_DECK, -100, 100, Z_SPLIT + 0.5 * k, Z_SPLIT + 0.5 * (k + 1) + 0.01)))
    for xc in CABLE_X:                # Aussparungen im Kragen vor den Kabellöchern
        lip = lip.cut(box(xc - 5, xc + 5, -100, 100, Z_SPLIT - LIP_H - 1, Z_SPLIT + 3))
    for a, b in TABS:                 # Kragen über den Flügellaschen 1 mm kürzer (Laschen reichen bis z = -12,5)
        lip = lip.cut(box(a - 1, b + 1, -100, 100, Z_SPLIT - LIP_H - 1, Z_SPLIT - LIP_H + 1.0))
    top = top.union(lip)
    # Anschlag vorn: Nase bekommt innen eine Leiste, an der die Oberschale vorn anliegt
    stop = hull(-T + 0.01, x0=X_DECK, x1=X_DECK + 2).cut(hull(-T - 3, x0=-10, x1=400))
    bot = bot.union(stop.intersect(box(X_DECK - 1, X_DECK + 3, -100, 100, -100, 100)))

    # ---------- Fenster (innen kommt Transparentpapier dahinter)
    # Deck: zwei Reihen kleiner Fenster und ein Mittelstreifen
    for x in (14, 30, 46):
        for y in (-14, 14):
            top = top.cut(box(x, x + 11, y - 4, y + 4, 0, 40))
    # Fasen oben: lange Lichtschlitze
    for s in (1, -1):
        top = top.cut(box(12, 88, s * 31 - 3 if s > 0 else -34, s * 31 + 3 if s > 0 else -28, 10, 40))
    # Seiten: TONI als Schablonenschrift vor den Triebwerken, von außen lesbar (links von hinten nach vorn gelesen)
    fs, pitch, x_mid, z_mid = 13.0, 12.5, 128.0, 2.0
    for side in (1, -1):
        xdir = -side                       # Leserichtung von außen gesehen
        for i, ch in enumerate(NAME):
            xc = x_mid + (i - (len(NAME) - 1) / 2) * pitch * xdir
            pl = cq.Plane(origin=(xc, side * 30, z_mid), xDir=(xdir, 0, 0), normal=(0, side, 0))
            top = top.cut(cq.Workplane(pl).text(ch, fs, 30, halign="center", valign="center", fontPath=FONT))
            if ch in "OADBPRQ0698":        # Stege, damit der Innenteil nicht herausfällt
                yw = half_w(xc)
                y0, y1 = (yw - T - 0.05, yw) if side > 0 else (-yw, -yw + T + 0.05)
                top = top.union(box(xc - 1.1, xc + 1.1, y0, y1, z_mid - 9, z_mid + 9))
    # Heckwand: Reaktorgitter (3 senkrechte Schlitze)
    for y in (-12, 0, 12):
        g = box(-2, 3, y - 3, y + 3, -22, 18)
        top, bot = top.cut(g), bot.cut(g)
    # Bauch: zwei lange Fenster. Sie bleiben in der flachen Bodenplatte (außen mindestens 3,5 mm Rand bis zur Fase),
    # sonst bricht das Fenster vorn durch die Fase und lässt einen freistehenden Splitter stehen (Druckabbruch 2026-11-08).
    for y in (-23, 23):
        bot = bot.cut(box(24, 120, y - 3.5, y + 3.5, -40, -20))
    # Nase: zwei Lüftungsschlitze oben, zwei Scheinwerfer in der Spitze
    for y in (-10, 10):
        bot = bot.cut(box(182, 205, y - 2.5, y + 2.5, -10, 40))
    for y in (-HEAD_Y, HEAD_Y):
        bot = bot.cut(cylx(HEAD_D / 2, SECTIONS[-1][0] - 20, SECTIONS[-1][0] + 5, y, HEAD_Z))

    # ---------- Kanzel- und Leitwerksöffnung im Deck, Schnurschlitz
    top = top.cut(canopy_opening(CAN_RIM - CLEAR).extrude(40))
    for x in FIN_TABS:
        top = top.cut(box(x[0] - CLEAR, x[1] + CLEAR, -FIN_T / 2 - CLEAR, FIN_T / 2 + CLEAR, 10, 40))
    top = top.cut(box(HANG_SLOT[0], HANG_SLOT[1], -5, 5, 10, 40))

    # ---------- Unterschale: Flügelschlitze, Pfosten, Klettschlitze, Kabellöcher
    for s in (1, -1):
        for a, b in TABS:
            bot = bot.cut(box(a - CLEAR, b + CLEAR, -100 if s < 0 else 0, 0 if s < 0 else 100,
                              Z_WING - WING_T / 2 - CLEAR, Z_WING + WING_T / 2 + CLEAR).intersect(side_band(s)))
        for xc in CABLE_X:
            bot = bot.cut(side_hole(s, xc, CABLE_Z, CABLE_R))
            top = top.cut(side_hole(s, xc, CABLE_Z, CABLE_R))
    post = box(POST_X[0], POST_X[1], -POST_T / 2, POST_T / 2, Z_BOT + 0.5, Z_SPLIT - 3)
    for xh in POST_HOLES:
        post = post.cut(cq.Workplane("XZ").workplane(offset=-5).center(xh, Z_SPLIT - 8).circle(2.6).extrude(10))
    rib = cq.Workplane("YZ").polyline([(-14, Z_BOT + 0.5), (14, Z_BOT + 0.5), (POST_T / 2, Z_BOT + 14), (-POST_T / 2, Z_BOT + 14)]).close().extrude(2.4)
    for x in (POST_X[0], 49.8, 57.8, POST_X[1] - 2.4):      # Streben zwischen den Löchern, nicht darin
        post = post.union(rib.translate((x, 0, 0)))
    bot = bot.union(post)
    return top, bot


def side_band(s):
    """Zone, die nur die Seitenwand einer Seite trifft."""
    return box(-10, 300, 20, 120, -100, 100) if s > 0 else box(-10, 300, -120, -20, -100, 100)


def side_hole(s, x, z, r):
    return cq.Workplane("YZ").workplane(offset=x).center(0, z).circle(r).extrude(1).translate((0, 0, 0))\
        .union(cylx(r, x - r, x + r)).intersect(box(-10, 300, -1, 1, -100, 100)) if False else \
        cq.Workplane("XZ").center(x, z).circle(r).extrude(-120 if s > 0 else 120).intersect(side_band(s))


# ================================================================ Kanzel
def canopy_opening(shrink):
    """Umriss der Kanzel auf Deckhöhe, um shrink nach innen versetzt (als Workplane-Sketch auf z = 0)."""
    pts = []
    xs = [CANOPY[0][0] + shrink] + [x for x, *_ in CANOPY[1:-1]] + [CANOPY[-1][0] - shrink]
    hws = [w / 2 - shrink for _, w, *_ in CANOPY]
    for x, hw in zip(xs, hws):
        pts.append((x, hw))
    for x, hw in zip(reversed(xs), reversed(hws)):
        pts.append((x, -hw))
    return cq.Workplane("XY").polyline(pts).close()


def make_canopy():
    ws = [sec_wire(x, w, zt, Z_TOP - 3, ct, 0.01) for x, w, zt, ct in CANOPY]
    outer = ruled(ws)
    inner = ruled([sec_wire(x, w - 2 * T, zt - T, Z_TOP - 5, max(ct - 0.5, 0.01), 0.01) for x, w, zt, ct in CANOPY])
    c = outer.cut(inner).intersect(box(-10, 300, -100, 100, Z_TOP, 100))
    # Scheiben ausschneiden: übrig bleiben Sims, Mittelsteg, zwei Querstreben, Front- und Heckrahmen
    xs = [CANOPY[0][0] + 3, CAN_FRAMES[0] - 1.5, CAN_FRAMES[0] + 1.5, CAN_FRAMES[1] - 1.5, CAN_FRAMES[1] + 1.5, CANOPY[-1][0] - 4]
    for a, b in ((xs[0], xs[1]), (xs[2], xs[3]), (xs[4], xs[5])):
        for s in (1, -1):
            c = c.cut(box(a, b, 1.6 if s > 0 else -40, 40 if s > 0 else -1.6, CAN_SILL, 80))
    # Kragen nach unten in die Deck-Öffnung: gleiche Form wie die Kanzel, 1 mm nach innen versetzt
    outer_ring = canopy_opening(CAN_RIM).extrude(3 + T + 0.5).translate((0, 0, Z_TOP - T - 3))
    inner_ring = canopy_opening(CAN_RIM + T).extrude(3 + T + 2).translate((0, 0, Z_TOP - T - 4))
    return c.union(outer_ring.cut(inner_ring))


# ================================================================ Leitwerk
FIN_T = 3.0
FIN_TABS = [(6.0, 18.0), (32.0, 44.0)]


def make_fin():
    prof = [(0, Z_TOP), (50, Z_TOP), (16, Z_TOP + 46), (-6, Z_TOP + 50), (-6, Z_TOP + 44)]
    fin = cq.Workplane("XZ").polyline(prof).close().extrude(FIN_T / 2, both=True)
    hole = cq.Workplane("XZ").polyline([(12, Z_TOP + 7), (34, Z_TOP + 7), (14, Z_TOP + 30), (6, Z_TOP + 30)]).close().extrude(5, both=True)
    fin = fin.cut(hole)
    for a, b in FIN_TABS:
        fin = fin.union(box(a, b, -FIN_T / 2, FIN_T / 2, Z_TOP - T - 3, Z_TOP + 0.5))
    return fin


# ================================================================ Flügel
def make_wing():
    """Linker Flügel (y > 0). Der rechte ist gespiegelt."""
    w = cq.Workplane("XY").workplane(offset=Z_WING - WING_T / 2).polyline(WING).close().extrude(WING_T)
    for h in WING_HOLES:
        w = w.cut(cq.Workplane("XY").workplane(offset=Z_WING - 5).polyline(h).close().extrude(10))
    for a, b in TABS:
        w = w.union(box(a, b, half_w((a + b) / 2) - TAB_IN, half_w((a + b) / 2) + 1, Z_WING - WING_T / 2, Z_WING + WING_T / 2))
    # Kanonenfuß an der Flügelspitze: Block von der Flügelunterseite bis GUN_H über dem Flügel (steht auf dem Bett,
    # auch wo der Flügel schmaler ist), vorn ein Zapfen für das Rohr mit Sockel bis aufs Bett
    zg, zb = Z_WING + WING_T / 2, Z_WING - WING_T / 2
    blk = box(GUN_X0, GUN_X1, GUN_Y - GUN_W / 2, GUN_Y + GUN_W / 2, zb, zg + GUN_H)
    w = w.union(blk)
    w = w.union(box(GUN_X1 - 0.5, GUN_X1 + SPIGOT_L, GUN_Y - 3.5, GUN_Y + 3.5, zb, GUN_Z))
    w = w.union(cylx(SPIGOT_R, GUN_X1 - 0.5, GUN_X1 + SPIGOT_L, GUN_Y, GUN_Z))
    # Kabelkanal auf dem Flügel: von der Flügelwurzel (Rumpfloch) bis an den Kanonenfuß, offen nach oben
    (xa, ya), (xb, yb) = DUCT
    L = math.hypot(xb - xa, yb - ya)
    ang = math.degrees(math.atan2(yb - ya, xb - xa))
    def along(width, h, z0, extra):
        return cq.Workplane("XY").box(L + extra, width, h).translate((0, 0, z0 + h / 2))\
            .rotate((0, 0, 0), (0, 0, 1), ang).translate(((xa + xb) / 2, (ya + yb) / 2, 0))
    # Kanalkörper endet 0,3 mm vor der Rumpfwand (sonst stößt seine Ecke in die Wand, Fehler bis 2026-11-08)
    w = w.union(along(DUCT_W + 3.0, 0.9 + DUCT_H + COVER_T, zg - 0.01, 2).cut(hull(0.3, x0=-10, x1=400)))
    w = w.cut(along(DUCT_W, DUCT_H + COVER_T + 2, zg + 0.9, 8))                      # Kanal, läuft 4 mm in den Fuß
    blk_grow = box(GUN_X0 - 0.3, GUN_X1 + 0.3, GUN_Y - GUN_W / 2 - 0.3, GUN_Y + GUN_W / 2 + 0.3, zb - 1, zg + GUN_H + 1)
    w = w.cut(along(DUCT_W + 1.0, COVER_T + 2, zg + 0.9 + DUCT_H, 8).cut(blk_grow))  # Absatz für den Kanaldeckel
    # Schacht im Fuß (offen nach oben) vom Kanalende bis kurz vor den Zapfen, Tunnel durch den Zapfen
    reg, ledge, cover = foot_cover_shapes()
    w = w.cut(reg.extrude(GUN_H + 2).translate((0, 0, zg + 0.9)))
    w = w.cut(ledge.extrude(COVER_T + 2).translate((0, 0, zg + GUN_H - COVER_T)))
    w = w.cut(cylx(TUNNEL_R, GUN_X1 - 6, GUN_X1 + SPIGOT_L + 1, GUN_Y, GUN_Z))
    return w


def foot_cover_shapes():
    """Grundriss von Schacht + Kanalmündung im Kanonenfuß: (Schacht, Absatz, Deckel) als Workplane-Skizzen auf z = 0."""
    from shapely.geometry import box as sbox, LineString
    (xa, ya), (xb, yb) = DUCT
    dx, dy = xb - xa, yb - ya
    L = math.hypot(dx, dy)
    ex, ey = dx / L, dy / L
    slot = sbox(xb - 6.0, GUN_Y - GUN_SLOT_W / 2, GUN_X1 - 3.0, GUN_Y + GUN_SLOT_W / 2)
    chan = LineString([(xa, ya), (xb + 4 * ex, yb + 4 * ey)]).buffer(DUCT_W / 2, cap_style=2)
    blk = sbox(GUN_X0, GUN_Y - GUN_W / 2, GUN_X1, GUN_Y + GUN_W / 2)
    reg = slot.union(chan).intersection(blk)
    def wp(poly):
        pts = list(poly.exterior.coords)[:-1]
        return cq.Workplane("XY").polyline(pts).close()
    return wp(reg), wp(reg.buffer(0.5, join_style=2)), wp(reg.buffer(0.4, join_style=2))


def make_covers():
    """Deckel für Kabelkanal und Kanonenfuß (linker Flügel), flach gedruckt."""
    (xa, ya), (xb, yb) = DUCT
    L = math.hypot(xb - xa, yb - ya)
    ang = math.degrees(math.atan2(yb - ya, xb - xa))
    zg = Z_WING + WING_T / 2
    duct_cover = cq.Workplane("XY").box(L - 2.0, DUCT_W + 0.8, COVER_T).translate((0, 0, zg + 0.9 + DUCT_H + COVER_T / 2))\
        .rotate((0, 0, 0), (0, 0, 1), ang).translate(((xa + xb) / 2, (ya + yb) / 2, 0))
    _, _, cover = foot_cover_shapes()
    foot_cover = cover.extrude(COVER_T).translate((0, 0, zg + GUN_H - COVER_T))
    return duct_cover, foot_cover


def hexx(r, x0, x1, y, z):
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).polygon(6, 2 * r).extrude(x1 - x0)


GUN_Z = Z_WING + WING_T / 2 + 6.7    # Achse von Zapfen und Rohr: Rohrunterkante 0,9 mm über dem Flügel


def make_cannon():
    """Laserrohr (linke Seite, Einbaulage). Grau-transparent drucken, innen 2-3 LEDs der Lichterkette."""
    c = hexx(BARREL_R, GUN_X1, BARREL_X1, GUN_Y, GUN_Z)
    c = c.union(hexx(BARREL_R + 1.2, BARREL_X1 - 7, BARREL_X1, GUN_Y, GUN_Z))        # Mündung
    c = c.union(hexx(BARREL_R + 0.5, GUN_X1, GUN_X1 + 5, GUN_Y, GUN_Z))             # Ring am Fuß
    c = c.cut(cylx(SPIGOT_R + CLEAR, GUN_X1 - 1, GUN_X1 + SPIGOT_L + 0.3, GUN_Y, GUN_Z))
    # Schlitz unten für den Sockel unter dem Zapfen (7 mm breit, bis zur Achse): ohne ihn passt das Rohr nicht
    # über den Zapfen (Fehler bis 2026-11-08). Das Rohr greift so von oben über den Zapfen und wird geklebt.
    c = c.cut(box(GUN_X1 - 1, GUN_X1 + SPIGOT_L + 0.3, GUN_Y - 3.5 - CLEAR, GUN_Y + 3.5 + CLEAR, GUN_Z - 12, GUN_Z))
    c = c.cut(cylx(BARREL_BORE / 2, GUN_X1 + SPIGOT_L, BARREL_X1 - 0.8, GUN_Y, GUN_Z))
    for x in (90.0, 110.0):                                                          # Kühlrippen
        c = c.cut(hexx(BARREL_R + 1, x, x + 1.2, GUN_Y, GUN_Z).cut(hexx(BARREL_R - 0.5, x - 1, x + 3, GUN_Y, GUN_Z)))
    return c


def grip_x(xi):
    """Innenmaß ab Innenkante (Kabelseite) -> Koordinate."""
    return -GRIP_IN_L / 2 + xi


def grip_screws():
    return [(grip_x(x), y) for x in (3.5, GRIP_IN_L - 3.5) for y in (-GRIP_IN_W / 2 + 3.5, GRIP_IN_W / 2 - 3.5)]


def cyl_z(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def make_grip():
    """Steuergriff, Gebrauchslage: Taster oben, Boden (eigenes Teil) unten. -x: Kabel zum Schiff, +x: USB-C (Strom)."""
    g = box(-GRIP_L / 2, GRIP_L / 2, -GRIP_W / 2, GRIP_W / 2, 0, GRIP_H)
    try:
        g = g.edges("|X and >Z").fillet(5.0)          # nur die oberen Längskanten rund, unten sitzt der Boden bündig
    except Exception:
        pass
    g = g.cut(box(-GRIP_IN_L / 2, GRIP_IN_L / 2, -GRIP_IN_W / 2, GRIP_IN_W / 2, -1, GRIP_IN_H))
    for x in GRIP_BTN_X:
        g = g.cut(cyl_z(GRIP_BTN_D / 2, GRIP_IN_H - 1, GRIP_H + 1, grip_x(x), 0))
        # innen eine Mulde, damit die Decke am Taster nur GRIP_BTN_PANEL dick ist (Schnapp-Taster rasten sonst nicht)
        g = g.cut(cyl_z(GRIP_BTN_RECESS / 2, GRIP_IN_H - 1, GRIP_H - GRIP_BTN_PANEL, grip_x(x), 0))
    for sx, sy in grip_screws():                    # Schraubdome für den Boden (M3 x 10, selbstschneidend)
        # Dome beginnen erst über dem Boden (sonst stößt die Bodenplatte an, Fehler bis 2026-11-08)
        g = g.union(cyl_z(4.0, GRIP_LID, GRIP_IN_H + 0.5, sx, sy)).cut(cyl_z(1.3, -1, GRIP_IN_H - 4, sx, sy))
    g = g.cut(box(-GRIP_L / 2 - 1, -GRIP_IN_L / 2 + 1, -5, 5, 4, 12))                    # Kabel zum Schiff
    g = g.cut(box(GRIP_IN_L / 2 - 1, GRIP_L / 2 + 1, -6.5, 6.5, USB_Z - 4, USB_Z + 4))     # USB-C / Magnetstecker
    # kleine Pfeil-Markierung oben zwischen den Tastern (Schmuck)
    g = g.cut(cq.Workplane("XY").workplane(offset=GRIP_H - 0.8)
              .polyline([(grip_x(76), -6), (grip_x(88), 0), (grip_x(76), 6), (grip_x(79), 0)]).close().extrude(1))
    return g


def make_grip_lid():
    """Boden des Griffs: Bock für den ESP32, zwei Sättel für den Bambusstab mit Kabelbinder-Schlitzen."""
    # Platte sitzt innerhalb der Wände und schließt unten bündig ab (so druckt sie flach ohne Überhang)
    lw = GRIP_IN_W / 2 - CLEAR
    lid = box(-GRIP_IN_L / 2 + CLEAR, GRIP_IN_L / 2 - CLEAR, -lw, lw, 0, GRIP_LID)
    for sx, sy in grip_screws():
        lid = lid.cut(cyl_z(1.7, -1, GRIP_LID + 1, sx, sy)).cut(cyl_z(3.1, -1, 1.2, sx, sy))
    # Bock ist ein eigenes Teil (sonst nicht ohne Stützen druckbar). Eine flache Tasche zeigt, wo er hingeklebt wird.
    lid = lid.cut(box(grip_x(ESP_X[0] + 2) - 0.2, grip_x(ESP_X[1] - 2) + 0.2, -4.7, 4.7, GRIP_LID - BLOCK_POCKET, GRIP_LID + 1))
    for xi in (18.0, 78.0):
        sx = grip_x(xi)
        blk = box(sx - 8, sx + 8, -lw, lw, -11, 0.01)
        v = cq.Workplane("YZ").polyline([(-STICK_D / 2 - 2, -11.01), (STICK_D / 2 + 2, -11.01),
                                          (0, -1.0)]).close().extrude(20).translate((sx - 10, 0, 0))
        blk = blk.cut(v).cut(box(sx - 2.6, sx + 2.6, -30, 30, -4.2, -1.0))   # Kabelbinder 5 mm
        lid = lid.union(blk)
    return lid


def make_grip_block():
    """Bock für den ESP32 im Griff: wird in die Tasche im Griffboden geklebt."""
    return box(grip_x(ESP_X[0] + 2), grip_x(ESP_X[1] - 2), -4.5, 4.5, GRIP_LID - BLOCK_POCKET, ESP_BLOCK_H)


# ================================================================ Triebwerk
def eng_profile_outer():
    return [(0, ENG_R), (THROAT_U0, THROAT_R + T), (THROAT_U1, THROAT_R + T), (24, ENG_R), (ENG_L - 26, ENG_R),
            (ENG_L - 22, ENG_R - 3), (ENG_L, 5.0)]


def make_engine():
    """Gebaut entlang +u (= +x), Austritt bei u = 0, Achse auf y = z = 0."""
    po = eng_profile_outer()
    outer = cq.Workplane("XY").polyline([(0, 0)] + [(u, r) for u, r in po] + [(ENG_L, 0)]).close()\
        .revolve(360, (0, 0, 0), (1, 0, 0))
    bore = [(-1, 0), (-1, ENG_R - T - 0.4), (0, ENG_R - T - 0.4), (THROAT_U0, THROAT_R), (THROAT_U1, THROAT_R),
            (THROAT_U1, THROAT_R - STOP_W), (THROAT_U1 + 1.5, THROAT_R - STOP_W), (THROAT_U1 + 1.5 + STOP_W, THROAT_R),
            (24, ENG_R - T), (ENG_L - 26, ENG_R - T), (ENG_L - 22, ENG_R - 3 - T), (ENG_L - 10, 3.5), (ENG_L - 10, 0)]
    inner = cq.Workplane("XY").polyline(bore).close().revolve(360, (0, 0, 0), (1, 0, 0))
    e = outer.cut(inner)
    # Zierringe (Rillen) und Ansaugring
    for u in (34, 40, 80):
        e = e.cut(cq.Workplane("YZ").workplane(offset=u).circle(ENG_R + 1).circle(ENG_R - 0.5).extrude(1.2))
    # Sockel unten (flach auf den Flügel geklebt), Anfang 45° für den Druck
    pad_z0 = -ENG_R
    pad = cq.Workplane("XZ").polyline([(30, pad_z0), (ENG_L - 30, pad_z0), (ENG_L - 30, pad_z0 + 9), (39, pad_z0 + 9)]).close()\
        .extrude(6, both=True)
    e = e.union(pad.cut(cq.Workplane("YZ").workplane(offset=0).circle(ENG_R - T).extrude(ENG_L - 26)))
    # Kabelloch zur Rumpfseite, knapp über dem Flügel
    # durchgehend, damit dasselbe Teil links und rechts passt (das äußere Loch sitzt verdeckt knapp über dem Flügel)
    e = e.cut(cq.Workplane("XZ").center(ENG_X_HOLE, pad_z0 + 4.0).circle(TUNNEL_R).extrude(30, both=True))
    return e


ENG_X_HOLE = 40.0 - ENG_X0      # Kabelloch auf Höhe des Rumpflochs (x = 40)


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
    """Gebaut entlang -z (Spitze unten), Kragen oben. Für den Einbau gedreht."""
    def twist(z):
        return -FL_TWIST * z / FL_L
    z0, r0, a0 = FLAME_PROFILE[0]
    outer = loft([flame_section(z0 + 1.0, r0, a0, 0.0)] + [flame_section(z, r, a, twist(z)) for z, r, a in FLAME_PROFILE])
    ip = [(z, r, a) for z, r, a in FLAME_PROFILE if r - FL_T > 1.0]
    # Innen- und Außenform haben dieselben Schnitte (auch den Zusatzschnitt bei z = +1), sonst schwingen die Splines
    # verschieden und die Innenform stößt an den Flanken durch die Wand (gab Löcher beim Slicen).
    inner = loft([flame_section(z0 + 1.0, r0, a0, 0.0, inset=FL_T)] + [flame_section(z, r, a, twist(z), inset=FL_T) for z, r, a in ip])
    tube = cq.Workplane("XY").circle(FL_SPIGOT_R + 0.05).circle(FL_SPIGOT_R - FL_T - 0.05).extrude(FL_SPIGOT).val()   # 0,05 mm Übermaß, sonst verschmilzt OCC die Teile nicht
    return cq.Workplane("XY").add(outer.cut(inner).fuse(tube).clean())


# ================================================================ Flammengitter
# Dünne Gitterscheibe, wird auf das offene Ende des Flammenkragens geklebt (verschwindet im Triebwerk).
# Die zwei LEDs werden auf das Gitter gelegt und festgeklebt, ihr Licht scheint durch die Maschen in die Flamme.
FG_R = FL_SPIGOT_R - 0.1      # gleicher Außenradius wie der Kragen, passt mit ihm in die Düse
FG_T = 1.0                    # Dicke
FG_RIM = 1.6                  # Ring außen = Klebefläche auf dem Kragen (Kragenwand 1,6 mm)
FG_BAR, FG_PITCH = 1.0, 6.0   # Stege 1 mm, Maschen 5 × 5 mm


def make_flame_grid():
    disc = cq.Workplane("XY").circle(FG_R).extrude(FG_T)
    hole = cq.Workplane("XY").workplane(offset=-1).circle(FG_R - FG_RIM).extrude(FG_T + 2)
    g = disc.cut(hole)
    lattice = None
    n = int(FG_R / FG_PITCH) + 1
    for i in range(-n, n + 1):
        for bar in (box(i * FG_PITCH - FG_BAR / 2, i * FG_PITCH + FG_BAR / 2, -FG_R, FG_R, 0, FG_T),
                    box(-FG_R, FG_R, i * FG_PITCH - FG_BAR / 2, i * FG_PITCH + FG_BAR / 2, 0, FG_T)):
            lattice = bar if lattice is None else lattice.union(bar)
    return g.union(lattice.intersect(cq.Workplane("XY").circle(FG_R - FG_RIM + 0.05).extrude(FG_T)))


# ================================================================ Zusammenbau
def assembly_pose(name, s):
    if name in ("triebwerk-links", "triebwerk-rechts"):
        y = ENG_Y if name.endswith("links") else -ENG_Y
        if name.endswith("rechts"):
            s = s.mirror("XZ")
        return s.translate((ENG_X0, y, ENG_Z))
    if name in ("flamme-links", "flamme-rechts"):
        y = ENG_Y if name.endswith("links") else -ENG_Y
        # Kragen (z 0..FL_SPIGOT) zeigt nach +x in die Düse, Spitze nach -x
        s = s.rotate((0, 0, 0), (0, 1, 0), 90)
        return s.translate((ENG_X0 + THROAT_U1 - FL_SPIGOT, y, ENG_Z))
    if name in ("flammengitter-links", "flammengitter-rechts"):
        y = ENG_Y if name.endswith("links") else -ENG_Y
        s = s.translate((0, 0, FL_SPIGOT)).rotate((0, 0, 0), (0, 1, 0), 90)   # auf dem Kragenende der Flamme
        return s.translate((ENG_X0 + THROAT_U1 - FL_SPIGOT, y, ENG_Z))
    if name in ("fluegel-rechts", "kanone-rechts", "kanaldeckel-rechts", "fussdeckel-rechts"):
        return s.mirror("XZ")
    if name in ("griff", "griff-boden", "griff-bock"):
        return s
    return s


def print_pose(name, s):
    if name == "rumpf-oben":
        s = s.rotate((0, 0, 0), (1, 0, 0), 180)                    # Deck aufs Bett
    elif name.startswith("triebwerk"):
        s = s.rotate((0, 0, 0), (0, 1, 0), -90)                    # Düse aufs Bett, Spitze nach oben
    elif name.startswith("flamme-"):
        s = s.rotate((0, 0, 0), (1, 0, 0), 180)                    # Kragen aufs Bett
    elif name.startswith("flammengitter"):
        pass                                                        # flach
    elif name.startswith("kanone"):
        s = s.rotate((0, 0, 0), (0, 1, 0), -90)                    # Mündung nach oben
    elif name == "griff":
        s = s.rotate((0, 0, 0), (1, 0, 0), 180)                    # Oberseite aufs Bett
    elif name == "griff-boden":
        s = s.rotate((0, 0, 0), (1, 0, 0), 180)                    # Platte aufs Bett, Sättel nach oben
    elif name == "leitwerk":
        s = s.rotate((0, 0, 0), (1, 0, 0), 90)                     # flach hinlegen
    elif name == "rumpf-unten":
        s = s.rotate((0, 0, 0), (0, 0, 1), 45)                     # diagonal, damit 245 mm sicher passen
    bb = s.val().BoundingBox()
    return s.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


def render_paper():
    """Nur für Vorschaubilder: Transparentpapier innen."""
    inner = hull(-T - 0.05, x0=T + 0.1, x1=SECTIONS[-1][0] - 13)
    body = inner.cut(hull(-T - 0.6, x0=-10, x1=400))
    ws = [sec_wire(x, w - 2 * T - 0.1, zt - T - 0.05, Z_TOP + 0.5, max(ct - 0.5, 0.01), 0.01) for x, w, zt, ct in CANOPY]
    ws2 = [sec_wire(x, w - 2 * T - 1.0, zt - T - 0.5, Z_TOP - 2, max(ct - 0.7, 0.01), 0.01) for x, w, zt, ct in CANOPY]
    canopy = ruled(ws).cut(ruled(ws2))
    return body, canopy


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    for d in ("druck-k2", "onshape-step", "render"):
        (out / d).mkdir(parents=True, exist_ok=True)
    top, bot = make_hull_parts()
    covers = make_covers()
    wing = make_wing()
    eng = make_engine()
    flame = make_flame()
    parts = {"rumpf-unten": bot, "rumpf-oben": top, "kanzel": make_canopy(), "leitwerk": make_fin(),
             "fluegel-links": wing, "fluegel-rechts": wing, "triebwerk-links": eng, "triebwerk-rechts": eng,
             "flamme-links": flame, "flamme-rechts": flame,
             "flammengitter-links": make_flame_grid(), "flammengitter-rechts": make_flame_grid(),
             "kanone-links": make_cannon(), "kanone-rechts": make_cannon(), "griff": make_grip(),
             "griff-boden": make_grip_lid(), "griff-bock": make_grip_block(),
             "kanaldeckel-links": covers[0], "kanaldeckel-rechts": covers[0],
             "fussdeckel-links": covers[1], "fussdeckel-rechts": covers[1]}
    info, asm = {}, cq.Assembly()
    cg = [0.0, 0.0, 0.0]
    mass = 0.0
    for k, s in parts.items():
        placed = assembly_pose(k, s)
        v = placed.val()
        if k.startswith("griff"):
            v = s.val()
        vol = v.Volume()
        c = cq.Shape.centerOfMass(v)
        m = vol / 1000 * 1.24
        if not k.startswith("griff"):
            mass += m
            cg = [cg[0] + c.x * m, cg[1] + c.y * m, cg[2] + c.z * m]
        info[k] = {"gewicht_g": round(m), "valid": v.isValid(), "solids": len(v.Solids())}
        cq.exporters.export(placed, str(out / "render" / f"{k}.stl"), tolerance=0.12, angularTolerance=0.35)
        if not k.startswith("griff"):
            asm.add(placed, name=k)
        mirrored = k.startswith(("fluegel", "kanaldeckel", "fussdeckel"))   # links/rechts sind Spiegelbilder
        if k.endswith("rechts") and not mirrored:
            continue                                                 # gleiches Teil, nur einmal ausgeben
        name = k if mirrored else k.replace("-links", "")
        p = print_pose(k, placed if (mirrored and k.endswith("rechts")) else s)
        bb = p.val().BoundingBox()
        info[k]["druckgroesse_mm"] = [round(bb.xlen), round(bb.ylen), round(bb.zlen)]
        cq.exporters.export(p, str(out / "druck-k2" / f"druck-{name}.stl"), tolerance=0.03, angularTolerance=0.1)
        cq.exporters.export(placed if (mirrored and k.endswith("rechts")) else s, str(out / "onshape-step" / f"{name}.step"))
    heads = cylx(HEAD_D / 2 - 0.3, SECTIONS[-1][0] - 1, SECTIONS[-1][0] + 0.4, HEAD_Y, HEAD_Z)\
        .union(cylx(HEAD_D / 2 - 0.3, SECTIONS[-1][0] - 1, SECTIONS[-1][0] + 0.4, -HEAD_Y, HEAD_Z))
    cq.exporters.export(heads, str(out / "render" / "scheinwerfer.stl"), tolerance=0.05)
    pb, pc = render_paper()
    cq.exporters.export(pb, str(out / "render" / "papier.stl"), tolerance=0.05)
    cq.exporters.export(pc, str(out / "render" / "papier-kanzel.stl"), tolerance=0.05)
    asm.save(str(out / "onshape-step" / "pfeil-jaeger-komplett.step"))
    info["_summe_g"] = round(mass)
    info["_schwerpunkt_mm"] = [round(c / mass, 1) for c in cg]
    (out / "render" / "info.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info))
