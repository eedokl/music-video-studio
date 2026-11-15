# Runs inside Blender's Python (bpy) - started by stage_run.py, never with uv.
"""Ready-made sets. office(S): a warm office with a big table, whiteboard, shelf and plants (seats for four)."""
import math

import stage_props as P
from stage_core import FONT_SEMI, Node, V, area, box, cyl, mat, spot, text, tube, world

# x, y, heading: two places behind the table, one at each end, turned towards the others (left to right)
PLACES = [(-2.0, 0.6, 52), (-0.62, 1.22, 8), (0.62, 1.16, -8), (2.0, 0.6, -52)]
SEATS = {}                  # figure name -> place; filled by seat() (or set it yourself before calling seat())
TABLE_Z = 0.5

# Light moods: one room, five times of day. world = (top, bottom, strength); key / fill / rim / rim2 = (watts, colour);
# window = (watts, light colour, sky colour, sky strength); lamps = watts per pendant lamp; beam = low sun raking
# across the back wall through a window cross (watts, colour) or None. "day" is the bright, even office light;
# the others are lower key: darker room, one clear light direction, practical lamps doing real work.
LIGHT = {
    "day": {"world": ("#AFC3D6", "#E9D9C2", 0.22), "key": (1100, "#FFE2BF"), "fill": (260, "#CFE0FF"),
            "rim": (650, "#FFF4E0"), "rim2": (520, "#FFE9CC"), "window": (1100, "#FFE9C4", "#BFE0FF", 5.0),
            "lamps": 90, "beam": None},
    "golden": {"world": ("#D9A77E", "#EFD3B4", 0.035), "key": (300, "#FFC489"), "fill": (45, "#B9C8EE"),
               "rim": (210, "#FFD3A0"), "rim2": (150, "#FFC489"), "window": (250, "#FFC48A", "#FFCB96", 4.0),
               "lamps": 16, "beam": (3600, "#FFAE66")},
    "dusk": {"world": ("#4A4468", "#D98F86", 0.035), "key": (110, "#E8A6A6"), "fill": (45, "#8FA0D8"),
             "rim": (170, "#FFB890"), "rim2": (90, "#C8A0D0"), "window": (220, "#F0A090", "#E8968C", 2.6),
             "lamps": 130, "beam": None},
    "night": {"world": ("#0B1024", "#1A2238", 0.02), "key": (45, "#8FA8E8"), "fill": (18, "#6F86C8"),
              "rim": (100, "#A8C0FF"), "rim2": (45, "#8FA8E8"), "window": (80, "#9FB8FF", "#27365E", 1.0),
              "lamps": 160, "beam": None},
    "dawn": {"world": ("#9FB8E0", "#F2C4B0", 0.06), "key": (260, "#FFD8C8"), "fill": (90, "#C8D8FF"),
             "rim": (260, "#FFE0D0"), "rim2": (180, "#FFD0C0"), "window": (460, "#FFD8C0", "#F8D0D8", 4.5),
             "lamps": 15, "beam": (1300, "#FFC2A8")},
}
TABLE = (3.3, 1.1)          # table size (x, y), centred at (0, 0.45)


def office(S, lights=True, warm=1.0, props=True, name="office",
           poster=("GOOD IDEAS", "Take your time.\nThen make it\nsimple."), book="THE BIG\nBOOK OF\nPLANS",
           laptop_at=3, ceiling=False, mood="golden"):
    """Room 9 x 7 m, back wall at y=2.2. Walnut table (top at z=0.5) centred at (0, 0.45); characters stand
    around it at PLACES. poster = (headline, text) or None; book = title on the handbook; laptop_at = index of the
    place that gets the laptop; ceiling=True closes the room for low camera angles (it changes the light a little).
    mood = the light: "golden" (low warm sun, default), "day" (bright and even), "dusk", "night", "dawn" - see LIGHT;
    warm scales the warm lights of the mood.
    Returns dict with nodes: table, board, window, lamps, mugs, laptop ..."""
    P.palette()
    R = {}
    R["room"] = P.room(S, 9.0, 7.0, 3.3, wall="wall_warm", floor="floor_wood", y_back=2.2)
    box("wains", (9.0, 0.04, 1.0), (0, 2.18, 0.5), "wall_accent", bevel=0)
    box("wains_cap", (9.0, 0.07, 0.05), (0, 2.165, 1.02), "trim", bevel=0.01)
    for sx in (-1, 1):
        box(f"wains_s{sx}", (0.04, 9.0, 1.0), (sx * 4.48, 0, 0.5), "wall_accent", bevel=0)
    R["rug"] = Node(S, box("rug", (4.6, 2.9, 0.02), (0, 0.5, 0.01), "rug", bevel=0.008))
    R["table"] = P.desk(S, (0, 0.45, 0), w=TABLE[0], d=TABLE[1], h=TABLE_Z, name="table", thick=0.07)
    L = LIGHT[mood]
    R["window"] = P.window(S, (-2.9, 2.19, 2.0), 1.5, 1.5, light=L["window"][0] * warm, color=L["window"][1],
                           sky=L["window"][2], strength=L["window"][3], name="win")
    R["board"] = P.whiteboard(S, (0.25, 2.16, 2.0), 2.2, 1.2, name="board")
    # scribbles on the whiteboard: a chart, boxes and arrows
    b = R["board"]
    for i, hgt in enumerate((0.18, 0.3, 0.24, 0.42)):
        box(f"wb_bar{i}", (0.09, 0.004, hgt), (-0.85 + i * 0.14, -0.028, -0.4 + hgt / 2), "accent" if i < 3 else "accent_l",
            b, bevel=0)
    tube("wb_curve", [(-0.2, -0.03, -0.35), (0.05, -0.03, -0.2), (0.3, -0.03, -0.28), (0.55, -0.03, 0.05),
                      (0.85, -0.03, 0.3)], 0.008, "ink_t", b)
    for i, (x, z) in enumerate(((-0.7, 0.32), (-0.25, 0.32), (0.2, 0.32))):
        box(f"wb_box{i}", (0.3, 0.004, 0.16), (x, -0.028, z), "paper_a", b, bevel=0.0)
        text(f"wb_t{i}", ("IDEA", "BUILD", "TEST")[i], 0.06, "txt_dark", (x, -0.032, z), b, extrude=0.0005)
    R["shelf"] = P.shelf(S, (3.3, 2.0, 0), 1.7, 2.5, 0.32, rows=5, name="shelf")
    R["plant"] = P.plant(S, (-4.0, 1.7, 0), 2.2, name="plant1")
    R["plant2"] = P.plant(S, (2.05, 1.95, 0), 1.3, name="plant2", seed=4)
    if poster:
        box("poster_f", (0.9, 0.04, 1.15), (-1.6, 2.17, 2.05), "walnut", bevel=0.012)
        box("poster_p", (0.8, 0.02, 1.05), (-1.6, 2.15, 2.05), "paper", bevel=0)
        text("poster_t", poster[0], 0.085, "txt_accent", (-1.6, 2.135, 2.4), extrude=0.001)
        text("poster_t2", poster[1], 0.06, "txt_dark", (-1.6, 2.135, 2.08), extrude=0.001, font=FONT_SEMI)
        cyl("poster_gear", 0.11, 0.01, (-1.6, 2.135, 1.7), "accent", rot=(90, 0, 0), seg=10)
        cyl("poster_gear2", 0.045, 0.012, (-1.6, 2.13, 1.7), "paper", rot=(90, 0, 0), seg=24)
    if ceiling:
        box("ceiling", (9.0, 9.0, 0.04), (0, -1.3, 3.32), "wall_warm", bevel=0)
    R["lamps"] = [P.lamp(S, (x, 0.5, 3.3), 1.2, L["lamps"] * warm, name=f"lamp{i}") for i, x in enumerate((-1.1, 0, 1.1))]
    if props:
        z = TABLE_Z
        R["blueprint"] = P.blueprint(S, (-0.45, 0.5, z), 0.8, 0.55, rot_z=6)
        R["mug_h"] = P.mug(S, (-0.95, 0.78, z), "ceramic_a", rot_z=40, name="mug_h", steam=True)
        R["mug_x"] = P.mug(S, (0.95, 0.75, z), "ceramic_w", rot_z=-30, name="mug_x")
        R["book"] = P.book(S, (-1.25, 0.2, z), (0.26, 0.34, 0.05), "accent_d", rot_z=14, name="handbook",
                           title=book)
        R["papers"] = P.papers(S, (0.3, 0.3, z), 3, rot_z=-8, name="papers")
        fx, fy, fh = PLACES[laptop_at]
        a = math.radians(fh)
        R["laptop"] = P.laptop(S, (fx + math.sin(a) * 0.62, fy - math.cos(a) * 0.62, z), rot_z=fh + 180,
                               name="laptop", w=0.3, d=0.2, open_deg=112)
        box("cal1", (0.3, 0.02, 0.006), (0.55, 0.62, z + 0.004), "steel", rot=(0, 0, 20), bevel=0.002)
        box("cal2", (0.012, 0.07, 0.006), (0.45, 0.6, z + 0.005), "steel", rot=(0, 0, 20), bevel=0.002)
        box("cal3", (0.012, 0.07, 0.006), (0.52, 0.625, z + 0.005), "steel", rot=(0, 0, 20), bevel=0.002)
        box("calc", (0.1, 0.15, 0.015), (-1.4, 0.7, z + 0.008), "grey_d", rot=(0, 0, -50), bevel=0.006)
        box("calc_d", (0.08, 0.03, 0.004), (-1.37, 0.735, z + 0.017), "screen_a", rot=(0, 0, -50), bevel=0)
        cyl("cup", 0.04, 0.1, (1.2, 0.1, z + 0.05), "accent_d")
        for i, (dx, c) in enumerate(((-0.012, "brass"), (0.01, "red"), (0.0, "paper"))):
            cyl(f"pen{i}", 0.006, 0.16, (1.2 + dx, 0.1 + dx, z + 0.11), c, rot=(8 * (i - 1), 6, 0), bevel=0)
    if lights:
        world(*L["world"])
        R["key"] = area("key", (-3.4, -2.6, 3.3), (0, 0.8, 0.9), L["key"][0] * warm, 2.5, L["key"][1])
        R["fill"] = area("fill", (3.8, -3.5, 1.6), (0, 0.8, 0.9), L["fill"][0], 4.0, L["fill"][1])
        R["rim"] = area("rim", (2.2, 2.0, 3.1), (0.3, 0.9, 0.9), L["rim"][0], 1.0, L["rim"][1])
        R["rim2"] = area("rim2", (-2.6, 2.0, 3.0), (-0.8, 0.9, 0.9), L["rim2"][0], 1.0, L["rim2"][1])
        if L["beam"]:
            R["beam"] = sunbeam(L["beam"][0] * warm, L["beam"][1])
    return R


def sunbeam(power, color, loc=(-4.25, -1.6, 2.5), aim=(1.2, 2.2, 1.35), name="beam"):
    """low sun through a window that is out of the picture: a spot behind a window cross, raking over the figures
    and the back wall (the cross and its frame are invisible to the camera, only their shadow shows)"""
    li = spot(name, loc, aim, power, angle=42, blend=0.25, color=color, radius=0.02)
    mat("gobo", "#000000", rough=1.0)
    d = (V(aim) - V(loc)).normalized()
    c = V(loc) + d * 0.75
    g = P.grp(None, name + "_gobo", c)
    g.obj.rotation_euler = li.rotation_euler
    s = 0.62
    for nm, size, at in (("v", (0.03, s, 0.01), (0, 0, 0)), ("h", (s, 0.03, 0.01), (0, 0.04, 0)),
                         ("l", (0.5, s + 1.0, 0.01), (-s / 2 - 0.25, 0, 0)), ("r", (0.5, s + 1.0, 0.01), (s / 2 + 0.25, 0, 0)),
                         ("t", (s + 1.0, 0.5, 0.01), (0, s / 2 + 0.25, 0)), ("b", (s + 1.0, 0.5, 0.01), (0, -s / 2 - 0.25, 0))):
        o = box(f"{name}_gobo_{nm}", size, at, "gobo", g, bevel=0)
        o.visible_camera = False
        o.visible_glossy = False
    return li


def seat(cast, f=1, who=None, places=None):
    """place the figures at the table: in the order of the cast (left to right), or places = {name: index | (x, y,
    heading)}. Fewer than four figures take the middle places first. SEATS remembers who stands where."""
    order = {1: [1], 2: [1, 2], 3: [0, 1, 2]}.get(len(cast), list(range(len(PLACES))))
    for i, n in enumerate(cast):
        if n not in SEATS:
            pl = (places or {}).get(n, order[i % len(order)])
            SEATS[n] = PLACES[pl] if isinstance(pl, int) else tuple(pl)
    for n, c in cast.items():
        if who and n not in who:
            continue
        x, y, h = SEATS[n]
        c.at(f, x, y, h, ease="hold")
