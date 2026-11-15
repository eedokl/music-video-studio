# Runs inside Blender's Python (bpy) - started by stage_run.py, never with uv.
"""Sets and props for 3D films: rooms, furniture, screens, signs, speech bubbles, mini robots, confetti, coins.

Everything is built from soft bevelled primitives in the film palette (warm wood, cream, brass and one accent family - stage_core.PAL)
so that the white characters stand out. Functions return a Node (animatable) unless noted.
"""
import math

from stage_core import (BLUE, FONT_BOLD, FONT_COMIC, FONT_SEMI, INK, PAL, WHITE, _MATS, Node, V, area, box,
                   capsule, cyl, ell, emit, empty, felt, lathe, mat, plane, point, smooth, text, torus, tube, wood)


LEGACY = {"green": "accent", "green_d": "accent_d", "green_l": "accent_l", "wall_green": "wall_accent",
          "wall_sage": "wall_soft", "paper_g": "paper_a", "ceramic_g": "ceramic_a", "gold_coin": "coin",
          "screen_g": "screen_a", "glow_green": "glow_a", "txt_green": "txt_accent", "txt_mint": "txt_soft"}


def palette():
    """create the shared materials from stage_core.PAL (call it once per clip, before building props)"""
    wood("oak", PAL["oak"], PAL["oak2"], scale=5.0)
    wood("walnut", PAL["walnut"], PAL["walnut2"], scale=7.0, rough=0.38, coat=0.4)
    wood("floor_wood", PAL["floor"], PAL["floor2"], scale=3.0, rough=0.45, coat=0.2)
    mat("wall", PAL["wall"], rough=0.9)
    mat("wall_warm", PAL["wall_warm"], rough=0.9)
    mat("wall_soft", PAL["wall_soft"], rough=0.9)
    mat("wall_accent", PAL["wall_accent"], rough=0.85)
    mat("wall_blue", "#243B55", rough=0.85)
    mat("wall_night", "#1A2036", rough=0.8)
    mat("trim", "#F7F2E8", rough=0.6)
    mat("paper", "#FBF8F1", rough=0.75)
    mat("paper_a", PAL["paper_a"], rough=0.75)
    mat("ink_t", INK, rough=0.6)
    mat("accent", PAL["accent"], rough=0.55)
    mat("accent_d", PAL["accent_d"], rough=0.55)
    mat("accent_l", PAL["accent_l"], rough=0.55)
    mat("cream", "#F1E7D3", rough=0.7)
    mat("grey", "#9AA1A8", rough=0.6)
    mat("grey_d", "#3A3F46", rough=0.5)
    mat("black", "#17191C", rough=0.35)
    mat("plastic_w", "#F4F4F2", rough=0.3, coat=0.3)
    mat("brass", "#D9B36A", rough=0.3, metal=1.0)
    mat("steel", "#C9CED4", rough=0.3, metal=1.0)
    mat("ceramic_a", PAL["ceramic"], rough=0.15, coat=0.6)
    mat("ceramic_w", "#F6F4EE", rough=0.15, coat=0.6)
    mat("leaf", "#3F8A5B", rough=0.5, sss=0.2)
    mat("leaf_d", "#2C6B45", rough=0.5, sss=0.2)
    mat("terracotta", "#C97B55", rough=0.7)
    mat("red", "#D7443E", rough=0.5)
    mat("blue", BLUE, rough=0.6)
    mat("slide_blue", "#2B66AA", rough=0.7)
    mat("coin", PAL["coin"], rough=0.25, metal=0.9)
    mat("glass_w", "#DCE9F2", rough=0.05, alpha=0.25)
    felt("rug", PAL["rug"], fuzz=1.0, scale=120.0, bump=0.5)
    emit("screen_w", "#F2F7FF", 1.6)
    emit("screen_a", PAL["screen"], 2.0)
    emit("screen_b", "#6FB6FF", 2.0)
    emit("glow_warm", "#FFD9A0", 6.0)
    emit("glow_gold", "#FFAE00", 2.2)
    emit("glow_a", PAL["glow"], 6.0)
    emit("glow_pink", "#FF4FB0", 8.0)
    emit("glow_cyan", "#46E6FF", 8.0)
    emit("glow_white", "#FFFFFF", 5.0)
    emit("txt_dark", "#101418", 0.0)
    emit("txt_white", "#FFFFFF", 1.2)
    emit("txt_accent", PAL["txt_accent"], 0.6)
    mat("txt_soft", PAL["txt_soft"], rough=0.6)
    for old, new in LEGACY.items():                  # older scenes name the accent materials by their first colour
        _MATS[old] = _MATS[new]
    emit("txt_red", "#E0352F", 1.5)


def grp(S, name, loc=(0, 0, 0), parent=None, rot=None):
    return Node(S, empty(name, loc, parent, rot))


# ------------------------------------------------------------------ architecture
def room(S, w=8.0, d=6.0, h=3.2, wall="wall", floor="floor_wood", y_back=2.0, sides=True, ceiling=False, base=True,
         name="room"):
    """box room: back wall at y=y_back, open towards -Y (camera side). Returns the group node."""
    g = grp(S, name)
    box(name + "_floor", (w + 4, d + 4, 0.1), (0, y_back - d / 2, -0.05), floor, g, bevel=0)
    box(name + "_back", (w + 0.4, 0.2, h), (0, y_back + 0.1, h / 2), wall, g, bevel=0)
    if sides:
        for sx in (-1, 1):
            box(name + f"_side{sx}", (0.2, d + 4, h), (sx * (w / 2 + 0.1), y_back - d / 2, h / 2), wall, g, bevel=0)
    if base:
        box(name + "_base", (w, 0.03, 0.12), (0, y_back - 0.015, 0.06), "trim", g, bevel=0.006)
    if ceiling:
        box(name + "_ceil", (w + 0.4, d + 4, 0.1), (0, y_back - d / 2, h + 0.05), "trim", g, bevel=0)
    return g


def window(S, loc, w=1.4, h=1.3, light=600, color="#FFE9C4", parent=None, name="window", sky="#BFE0FF", strength=5.0):
    """window on the back wall (faces -Y) with a glowing sky pane and a soft light into the room"""
    g = grp(S, name, loc, parent)
    emit(name + "_sky", sky, strength)
    box(name + "_pane", (w, 0.02, h), (0, 0.0, 0), name + "_sky", g, bevel=0)
    t = 0.07
    for dx, dz, sw, sh in ((0, h / 2, w + t, t), (0, -h / 2, w + t, t), (-w / 2, 0, t, h + t), (w / 2, 0, t, h + t),
                           (0, 0, t * 0.6, h), (0, 0, w, t * 0.6)):
        box(name + "_f", (sw, 0.08, sh), (dx, -0.03, dz), "trim", g, bevel=0.01)
    box(name + "_sill", (w + 0.3, 0.2, 0.05), (0, -0.1, -h / 2 - 0.03), "trim", g, bevel=0.01)
    if light:
        a = area(name + "_light", (0, -0.2, 0), (0, -3, -1.2), light, w, color, size_y=h, parent=g)
        a.location = (0, -0.15, 0)
    return g


def desk(S, loc, w=2.4, d=1.0, h=0.52, top="walnut", leg="black", parent=None, name="desk", thick=0.06):
    g = grp(S, name, loc, parent)
    box(name + "_top", (w, d, thick), (0, 0, h - thick / 2), top, g, bevel=0.015)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(name + "_leg", (0.06, 0.06, h - thick), (sx * (w / 2 - 0.1), sy * (d / 2 - 0.1), (h - thick) / 2), leg, g,
                bevel=0.01)
    return g


def shelf(S, loc, w=1.6, h=1.8, d=0.3, rows=4, parent=None, name="shelf", fill=True, seed=3):
    """bookshelf with binders and books in the film palette"""
    import random
    r = random.Random(seed)
    g = grp(S, name, loc, parent)
    box(name + "_back", (w, 0.03, h), (0, d / 2, h / 2), "walnut", g, bevel=0.004)
    for sx in (-1, 1):
        box(name + "_s", (0.04, d, h), (sx * w / 2, 0, h / 2), "walnut", g, bevel=0.006)
    for i in range(rows + 1):
        z = i * (h - 0.04) / rows + 0.02
        box(name + "_b", (w, d, 0.035), (0, 0, z), "walnut", g, bevel=0.006)
    if fill:
        cols = ["accent", "accent_d", "cream", "grey", "accent_l", "paper", "grey_d", "terracotta"]
        for i in range(rows):
            z0 = i * (h - 0.04) / rows + 0.04
            x = -w / 2 + 0.06
            rh = (h - 0.04) / rows - 0.06
            while x < w / 2 - 0.12:
                bw = r.uniform(0.04, 0.085)
                bh = rh * r.uniform(0.7, 0.98)
                if r.random() < 0.12:
                    x += r.uniform(0.05, 0.15)
                    continue
                tilt = r.uniform(-4, 4) if r.random() < 0.2 else 0
                box(name + "_bk", (bw, d * 0.8, bh), (x + bw / 2, -0.01, z0 + bh / 2), r.choice(cols), g,
                    rot=(0, tilt, 0), bevel=0.006)
                x += bw + 0.006
    return g


def plant(S, loc, s=1.0, parent=None, name="plant", seed=1):
    import random
    r = random.Random(seed)
    g = grp(S, name, loc, parent)
    g.obj.scale = (s, s, s)
    lathe(name + "_pot", [(0, 0), (0.1, 0), (0.13, 0.2), (0.14, 0.22), (0.12, 0.22), (0.11, 0.19), (0, 0.19)],
          (0, 0, 0), "terracotta", g)
    for i in range(9):
        a = i / 9 * math.tau + r.uniform(-0.3, 0.3)
        ln = r.uniform(0.22, 0.4)
        tilt = r.uniform(18, 55)
        lf = ell(name + f"_leaf{i}", (0.05, 0.012, ln / 2), (0, 0, 0.2), r.choice(["leaf", "leaf_d"]), g,
                 rot=(tilt, 0, math.degrees(a)), origin=(0, 0, ln / 2), seg=16)
    return g


def lamp(S, loc, drop=0.8, power=120, color="#FFD9A0", parent=None, name="lamp", shade="accent_d"):
    """pendant lamp hanging from loc (ceiling point)"""
    g = grp(S, name, loc, parent)
    cyl(name + "_cord", 0.008, drop, (0, 0, -drop / 2), "black", g, bevel=0)
    lathe(name + "_shade", [(0.03, 0.0), (0.06, -0.02), (0.22, -0.16), (0.225, -0.165), (0.21, -0.165), (0.05, -0.03),
                            (0.02, -0.01)], (0, 0, -drop), shade, g)
    ell(name + "_bulb", 0.045, (0, 0, -drop - 0.1), "glow_warm", g, seg=16)
    point(name + "_l", (0, 0, -drop - 0.14), power, color, 0.06, g)
    return g


def whiteboard(S, loc, w=1.8, h=1.1, parent=None, name="board", rot=None):
    g = grp(S, name, loc, parent, rot)
    box(name + "_frame", (w + 0.08, 0.04, h + 0.08), (0, 0, 0), "steel", g, bevel=0.012)
    box(name + "_panel", (w, 0.02, h), (0, -0.016, 0), "plastic_w", g, bevel=0.004)
    box(name + "_tray", (w * 0.6, 0.07, 0.025), (0, -0.05, -h / 2 - 0.04), "steel", g, bevel=0.006)
    return g


def door(S, loc, w=0.9, h=1.9, color="accent_d", parent=None, name="door", label=None, glow=None):
    """door on a back wall. glow: emission material name shining through an open gap"""
    g = grp(S, name, loc, parent)
    box(name + "_frame", (w + 0.14, 0.1, h + 0.07), (0, 0, h / 2 + 0.035), "trim", g, bevel=0.01)
    if glow:
        box(name + "_glow", (w, 0.02, h), (0, -0.03, h / 2), glow, g, bevel=0)
    hinge = grp(S, name + "_hinge", (-w / 2, -0.06, 0), g)
    box(name + "_leaf", (w, 0.05, h), (w / 2, 0, h / 2), color, hinge, bevel=0.012)
    ell(name + "_knob", 0.035, (w - 0.1, -0.05, h * 0.5), "brass", hinge, seg=16)
    if label:
        sign(S, label, (0, -0.07, h + 0.28), w=max(0.9, 0.085 * len(label) + 0.2), h=0.22, parent=g, size=0.09,
             name=name + "_lbl")
    g.hinge = hinge
    return g


# ------------------------------------------------------------------ desk things
def monitor(S, loc, w=0.62, h=0.38, rot_z=0, screen="screen_w", parent=None, name="monitor"):
    """returns group; g.screen = Node at the screen centre (y=-0.012 in front) to parent UI onto"""
    g = grp(S, name, loc, parent, (0, 0, rot_z))
    box(name + "_bezel", (w + 0.04, 0.03, h + 0.04), (0, 0, h / 2 + 0.16), "black", g, bevel=0.012)
    box(name + "_scr", (w, 0.004, h), (0, -0.016, h / 2 + 0.16), screen, g, bevel=0)
    box(name + "_neck", (0.05, 0.03, 0.18), (0, 0.02, 0.09), "grey_d", g, bevel=0.008)
    cyl(name + "_foot", 0.13, 0.015, (0, 0.02, 0.008), "grey_d", g)
    g.screen = grp(S, name + "_ui", (0, -0.02, h / 2 + 0.16), g)
    return g


def laptop(S, loc, rot_z=0, open_deg=105, screen="screen_w", parent=None, name="laptop", w=0.36, d=0.25, body="steel"):
    """g.lid = Node (rot x animatable: 0 closed .. open_deg), g.screen = UI anchor on the lid (faces the user at -Y...)
    The laptop opens towards -Y user by default: the screen faces -Y when rot_z=0."""
    g = grp(S, name, loc, parent, (0, 0, rot_z))
    box(name + "_base", (w, d, 0.016), (0, 0, 0.008), body, g, bevel=0.006)
    box(name + "_keys", (w * 0.86, d * 0.55, 0.002), (0, 0.02, 0.017), "grey_d", g, bevel=0)
    lid = grp(S, name + "_lid", (0, d / 2, 0.016), g, (-(open_deg - 90), 0, 0))
    box(name + "_lidm", (w, 0.012, d), (0, 0.006, d / 2), body, lid, bevel=0.005)
    box(name + "_lscr", (w * 0.92, 0.002, d * 0.86), (0, -0.001, d / 2), screen, lid, bevel=0)
    g.lid = lid
    g.screen = grp(S, name + "_ui", (0, -0.004, d / 2), lid)
    return g


def keyboard(S, loc, rot_z=0, parent=None, name="kb"):
    g = grp(S, name, loc, parent, (0, 0, rot_z))
    box(name + "_b", (0.4, 0.14, 0.018), (0, 0, 0.009), "grey_d", g, bevel=0.006)
    for r in range(4):
        box(name + f"_r{r}", (0.37, 0.022, 0.006), (0, -0.045 + r * 0.03, 0.02), "plastic_w", g, bevel=0.002)
    return g


def mug(S, loc, color="ceramic_a", rot_z=0, parent=None, name="mug", s=1.0, steam=False):
    g = grp(S, name, loc, parent, (0, 0, rot_z))
    g.obj.scale = (s, s, s)
    lathe(name + "_b", [(0, 0), (0.042, 0), (0.046, 0.005), (0.046, 0.1), (0.04, 0.1), (0.04, 0.012), (0, 0.012)],
          (0, 0, 0), color, g)
    cyl(name + "_c", 0.039, 0.004, (0, 0, 0.086), mat("coffee", "#3B2416", rough=0.2), g, bevel=0)
    torus(name + "_h", 0.028, 0.008, (0.05, 0, 0.052), color, g, rot=(90, 0, 0), arc=0.5).rotation_euler[1] = -math.pi / 2
    if steam:
        mat("steam", "#FFFFFF", rough=1.0, alpha=0.18)
        for i in range(3):
            n = Node(S, ell(name + f"_st{i}", (0.014, 0.014, 0.03), (0, 0, 0.12), "steam", g, seg=10))
            ph = i * 13
            n.lch(2).add(lambda f, ph=ph: 0.12 + ((f + ph) % 40) / 40 * 0.16 - 0.12)
            n.lch(0).add(lambda f, ph=ph: 0.012 * math.sin((f + ph) * 0.3))
            n.sch(0).add(lambda f, ph=ph: -1 + (0.6 + ((f + ph) % 40) / 40) * math.sin(((f + ph) % 40) / 40 * math.pi))
            n.sch(1).add(lambda f, ph=ph: -1 + (0.6 + ((f + ph) % 40) / 40) * math.sin(((f + ph) % 40) / 40 * math.pi))
    return g


def book(S, loc, size=(0.22, 0.3, 0.04), color="accent", rot_z=0, parent=None, name="book", title=None, tsize=0.022):
    g = grp(S, name, loc, parent, (0, 0, rot_z))
    w, d, h = size
    box(name + "_c", (w, d, h), (0, 0, h / 2), color, g, bevel=0.006)
    box(name + "_p", (w - 0.012, d - 0.012, h * 0.7), (0.006, 0, h / 2), "paper", g, bevel=0)
    if title:
        text(name + "_t", title, tsize, "txt_white", (0, 0, h + 0.001), g, rot=(0, 0, 0), extrude=0.0006, width=w * 0.85,
             font=FONT_BOLD)
    return g


def papers(S, loc, n=3, rot_z=0, parent=None, name="papers", size=(0.21, 0.297), m="paper", lines=True):
    g = grp(S, name, loc, parent, (0, 0, rot_z))
    for i in range(n):
        box(name + f"_{i}", (size[0], size[1], 0.002), (i * 0.006, i * 0.004, 0.002 + i * 0.0022), m, g,
            rot=(0, 0, i * 4 - 3), bevel=0)
    if lines:
        for k in range(6):
            box(name + f"_l{k}", (size[0] * (0.75 if k % 3 else 0.5), 0.006, 0.0004),
                (-0.02 if k % 3 == 0 else 0, size[1] * 0.35 - k * 0.04, 0.002 + n * 0.0022 + 0.0002), "grey", g, bevel=0,
                rot=(0, 0, (n - 1) * 4 - 3))
    return g


def blueprint(S, loc, w=0.7, d=0.5, rot_z=0, parent=None, name="blueprint"):
    """rolled-out technical drawing (blue paper, white lines, a gear)"""
    g = grp(S, name, loc, parent, (0, 0, rot_z))
    mat("bp", "#2C5D9A", rough=0.7)
    mat("bp_line", "#E8F0FA", rough=0.6)
    box(name + "_p", (w, d, 0.002), (0, 0, 0.001), "bp", g, bevel=0)
    for i in range(1, 6):
        box(name + f"_h{i}", (w * 0.9, 0.003, 0.0006), (0, -d / 2 + i * d / 6, 0.0025), "bp_line", g, bevel=0)
    torus(name + "_gear", 0.09, 0.006, (-w * 0.2, 0, 0.003), "bp_line", g, seg=32, rseg=6, flat=0.2)
    torus(name + "_gear2", 0.04, 0.005, (-w * 0.2, 0, 0.003), "bp_line", g, seg=24, rseg=6, flat=0.2)
    box(name + "_rect", (w * 0.25, d * 0.4, 0.0006), (w * 0.22, 0.02, 0.0024), "bp_line", g, bevel=0)
    box(name + "_rect2", (w * 0.25 - 0.012, d * 0.4 - 0.012, 0.0008), (w * 0.22, 0.02, 0.0025), "bp", g, bevel=0)
    for sx in (-1, 1):
        cyl(name + f"_roll{sx}", 0.02, d, (sx * w / 2, 0, 0.02), "bp", g, rot=(90, 0, 0), bevel=0)
    return g


def pizza(S, loc, parent=None, name="pizza", slices_left=8):
    g = grp(S, name, loc, parent)
    box(name + "_box", (0.36, 0.36, 0.02), (0, 0, 0.01), mat("cardboard", "#C9A77A", rough=0.8), g, bevel=0.004)
    mat("crust", "#D9A45B", rough=0.7)
    mat("cheese", "#F2C94C", rough=0.5)
    mat("salami", "#B5382F", rough=0.5)
    g.slices = []
    for i in range(8):
        a = i / 8 * math.tau
        sl = grp(S, name + f"_s{i}", (0, 0, 0.02), g, (0, 0, math.degrees(a)))
        cyl(name + f"_c{i}", 0.15, 0.012, (0, 0, 0.006), "crust", sl, seg=3, bevel=0).scale = (0.53, 0.32, 1)
        sl.obj.children[0].location = (0.075, 0, 0.006)
        sl.obj.children[0].rotation_euler = (0, 0, math.pi)
        cyl(name + f"_ch{i}", 0.13, 0.014, (0.07, 0, 0.007), "cheese", sl, seg=3, bevel=0).scale = (0.5, 0.3, 1)
        sl.obj.children[1].rotation_euler = (0, 0, math.pi)
        cyl(name + f"_sa{i}", 0.018, 0.016, (0.085, 0, 0.008), "salami", sl, seg=12, bevel=0)
        g.slices.append(sl)
    return g


def headphones(S, loc, rot_z=0, parent=None, name="phones"):
    g = grp(S, name, loc, parent, (0, 0, rot_z))
    torus(name + "_band", 0.085, 0.01, (0, 0, 0.06), "black", g, rot=(90, 0, 0), arc=0.5)
    for sx in (-1, 1):
        cyl(name + f"_cup{sx}", 0.045, 0.035, (sx * 0.085, 0, 0.05), "accent", g, rot=(0, 90, 0))
    return g


# ------------------------------------------------------------------ text things
def sign(S, body, loc, w=None, h=0.3, color="accent_d", tcolor="txt_white", size=0.12, parent=None, name="sign",
         rot=None, font=FONT_BOLD, depth=0.03, border=None):
    """board with centred text, readable from -Y"""
    w = w or (len(body) * size * 0.62 + 0.2)
    g = grp(S, name, loc, parent, rot)
    if border:
        box(name + "_bd", (w + 0.04, depth * 0.8, h + 0.04), (0, 0.002, 0), border, g, bevel=0.02)
    box(name + "_b", (w, depth, h), (0, 0, 0), color, g, bevel=min(0.03, h * 0.2))
    text(name + "_t", body, size, tcolor, (0, -depth / 2 - 0.001, 0), g, extrude=0.002, font=font)
    return g


def nameplate(S, name_txt, role, loc, parent=None, name="plate"):
    """small standing plaque: NAME — role"""
    g = grp(S, name, loc, parent)
    w = max(0.7, 0.085 * len(name_txt) + 0.048 * len(role) + 0.3)
    box(name + "_b", (w, 0.05, 0.2), (0, 0, 0.12), "accent_d", g, bevel=0.03, rot=(-12, 0, 0))
    box(name + "_f", (w * 0.5, 0.12, 0.02), (0, 0.02, 0.01), "brass", g, bevel=0.008)
    text(name + "_n", name_txt, 0.11, "txt_white", (-w / 2 + 0.06, -0.03, 0.125), g, rot=(78, 0, 0), extrude=0.003,
         align="LEFT")
    text(name + "_r", role, 0.07, "txt_soft", (w / 2 - 0.06, -0.03, 0.115), g, rot=(78, 0, 0),
         extrude=0.002, align="RIGHT", font=FONT_SEMI)
    return g


def bubble(S, body, loc, kind="speech", size=0.07, width=1.3, parent=None, name="bubble", tail=(-0.3, -0.35),
           color="paper", tcolor="txt_dark", font=FONT_COMIC):
    """comic bubble as a floating paper board. kind: speech (pointed tail) | thought (small circles) | none.
    tail = (dx, dz) offset of the tail tip from the bubble centre. Use .pop(f) / .unpop(f) on the result."""
    lines = _wrap(body, int(width / (size * 0.46)))
    h = len(lines) * size * 1.22 + size * 0.9
    w = max(len(ln) for ln in lines) * size * 0.46 + size * 1.5
    g = grp(S, name, loc, parent)
    if kind == "cloud":
        for i, (cx, cz, r) in enumerate(((-0.34, 0.0, 0.62), (0.0, 0.12, 0.75), (0.34, 0.0, 0.62), (-0.18, -0.2, 0.55),
                                         (0.2, -0.2, 0.55), (-0.5, -0.05, 0.42), (0.5, -0.05, 0.42))):
            ell(name + f"_c{i}", (r * h, 0.03, r * h * 0.82), (cx * w, 0.02, cz * h), color, g, seg=32)
            ell(name + f"_cs{i}", (r * h + 0.018, 0.02, r * h * 0.82 + 0.018), (cx * w, 0.04, cz * h), "ink_t", g, seg=32)
    else:
        box(name + "_sh", (w + 0.03, 0.02, h + 0.03), (0, 0.012, 0), "ink_t", g, bevel=min(h, w) * 0.3, seg=6)
        box(name + "_b", (w, 0.03, h), (0, 0, 0), color, g, bevel=min(h, w) * 0.3, seg=6)
    text(name + "_t", "\n".join(lines), size, tcolor, (0, -0.017, 0), g, extrude=0.001, font=font, line=0.95)
    if kind == "speech":
        dx, dz = tail
        base = V((dx * 0.5, 0, -h / 2 + 0.03))
        tip = V((dx, 0, dz - h / 2 * 0))
        tip.z = -h / 2 + dz
        capsule(name + "_tail", base, tip, size * 0.75, 0.004, color, g, seg=12, flat=0.25)
    elif kind in ("thought", "cloud"):
        dx, dz = tail
        for i, (t, r) in enumerate(((0.35, 0.05), (0.65, 0.035), (0.92, 0.022))):
            ell(name + f"_d{i}", (r, 0.012, r), (dx * t, 0, -h / 2 + dz * t), color, g, seg=16)
    g.w, g.h = w, h
    return g


def _wrap(s, n):
    out = []
    for para in s.split("\n"):
        line = ""
        for wd in para.split():
            if len(line) + len(wd) + 1 > n and line:
                out.append(line)
                line = wd
            else:
                line = (line + " " + wd).strip()
        out.append(line)
    return out


def card(S, title, lines=(), loc=(0, 0, 0), w=0.5, h=0.32, color="paper", accent="accent", parent=None, name="card",
         tsize=0.06, lsize=0.036, rot=None):
    """info card: accent bar, bold title, a few lines. Readable from -Y."""
    g = grp(S, name, loc, parent, rot)
    box(name + "_b", (w, 0.012, h), (0, 0, 0), color, g, bevel=0.02)
    box(name + "_a", (w * 0.86, 0.004, 0.018), (0, -0.008, h / 2 - 0.04), accent, g, bevel=0.004)
    text(name + "_t", title, tsize, "txt_dark", (-w * 0.43, -0.008, h / 2 - 0.1), g, extrude=0.0008, align="LEFT")
    for i, ln in enumerate(lines):
        text(name + f"_l{i}", ln, lsize, mat("txt_grey", "#4A5560", rough=0.6), (-w * 0.43, -0.008,
             h / 2 - 0.1 - tsize * 1.3 - i * lsize * 1.5), g, extrude=0.0006, align="LEFT", font=FONT_SEMI)
    return g


def ui_text(S, body, parent, loc=(0, 0, 0), size=0.03, color="txt_dark", align="LEFT", name="ui", font=FONT_SEMI):
    """flat text on a screen anchor (Node from monitor/laptop .screen)"""
    return Node(S, text(name, body, size, color, loc, parent, extrude=0.0003, align=align, font=font))


def ui_bar(S, parent, loc, w, h, color="accent", name="bar"):
    """flat bar whose left edge sits at loc (scale x to grow it to the right)"""
    return Node(S, box(name, (w, 0.001, h), loc, color, parent, bevel=0, origin=(w / 2, 0, 0)))


def neon(S, body, loc, size=0.3, color="glow_pink", parent=None, name="neon", light=60, lcolor="#FF4FB0", font=FONT_BOLD,
         rot=(90, 0, 0)):
    """glowing sign text (tube look) with a coloured point light"""
    g = grp(S, name, loc, parent)
    t = text(name + "_t", body, size, color, (0, 0, 0), g, extrude=0.004, bevel=0.006, font=font, rot=rot)
    g.text = t
    if light:
        g.light = point(name + "_l", (0, -0.4, 0), light, lcolor, 0.3, g)
    return g


def star(S, loc, r=0.1, color="glow_warm", parent=None, name="star", pts=5, depth=0.02):
    import bmesh
    import bpy
    bm = bmesh.new()
    vs = []
    for i in range(pts * 2):
        a = i / (pts * 2) * math.tau + math.pi / 2
        rr = r if i % 2 == 0 else r * 0.45
        vs.append(bm.verts.new((rr * math.cos(a), 0, rr * math.sin(a))))
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in ext["geom"]:
        if isinstance(v, bmesh.types.BMVert):
            v.co.y += depth
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(color))
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    if parent is not None:
        o.parent = parent.obj if isinstance(parent, Node) else parent
    return Node(S, o)


# ------------------------------------------------------------------ little actors and effects
class Bot:
    """mini agent robot (cute helper): body, head with glowing eyes, antenna; hover-bobs. root Node = .n"""

    def __init__(self, S, name="bot", loc=(0, 0, 0), s=1.0, color="plastic_w", eye="glow_a"):
        self.S = S
        self.n = grp(S, name, loc)
        self.n.obj.scale = (s, s, s)
        self.body = grp(S, name + "_bd", (0, 0, 0.0), self.n)
        box(name + "_body", (0.16, 0.13, 0.14), (0, 0, 0.1), color, self.body, bevel=0.045, seg=4)
        box(name + "_chest", (0.07, 0.01, 0.04), (0, -0.066, 0.1), "accent", self.body, bevel=0.008)
        self.head = grp(S, name + "_hd", (0, 0, 0.19), self.body)
        box(name + "_head", (0.2, 0.15, 0.13), (0, 0, 0.075), color, self.head, bevel=0.05, seg=4)
        box(name + "_visor", (0.15, 0.012, 0.07), (0, -0.072, 0.075), "black", self.head, bevel=0.02)
        self.eyes = []
        for sx in (-1, 1):
            e = Node(S, ell(name + f"_eye{sx}", (0.017, 0.006, 0.021), (sx * 0.035, -0.08, 0.078), eye, self.head, seg=12))
            self.eyes.append(e)
        cyl(name + "_ant", 0.005, 0.06, (0, 0, 0.17), "steel", self.head, bevel=0)
        ell(name + "_antb", 0.015, (0, 0, 0.205), eye, self.head, seg=10)
        for sx in (-1, 1):
            ell(name + f"_arm{sx}", (0.022, 0.022, 0.045), (sx * 0.1, 0, 0.09), "grey", self.body, seg=12)
            cyl(name + f"_wh{sx}", 0.03, 0.02, (sx * 0.06, 0, 0.03), "grey_d", self.n, rot=(0, 90, 0))
        ph = S.rng.uniform(0, 9)
        self.body.lch(2).add(lambda f: 0.008 * math.sin(f * 0.25 + ph))
        self.head.rch(2).add(lambda f: 6 * math.sin(f * 0.07 + ph))
        self.blinks = [S.rng.randint(1, max(2, S.frames)) for _ in range(max(1, S.frames // 70))]
        for e in self.eyes:
            e.sch(2).mul(lambda f: 0.15 if any(0 <= f - b <= 2 for b in self.blinks) else 1.0)

    def at(self, f, x=None, y=None, z=None, h=None, ease="io"):
        self.n.loc(f, x, y, z, ease)
        if h is not None:
            self.n.rot(f, z=h, ease=ease)
        return self

    def hop(self, f, h=0.08, dur=8):
        z = self.body.lch(2)
        z.key(f, 0)
        z.key(f + dur / 2, h, "out")
        z.key(f + dur, 0, "in")
        return self


def confetti(S, f0, origin, n=60, spread=1.6, up=3.2, colors=("accent", "accent_l", "paper", "brass", "red"), dur=70,
             name="conf", size=0.035, seed=5, gravity=6.0, floor=0.0):
    """burst of paper confetti at frame f0 (analytic ballistics + flutter); hidden before and after"""
    import random
    r = random.Random(seed)
    for i in range(n):
        p = Node(S, box(f"{name}{i}", (size, size * 0.6, 0.002), origin, r.choice(colors), bevel=0))
        a = r.uniform(0, math.tau)
        sp = r.uniform(0.2, 1.0) * spread
        vx, vy, vz = math.cos(a) * sp, math.sin(a) * sp * 0.7, r.uniform(0.5, 1.0) * up
        drag = r.uniform(0.9, 1.6)
        ph = r.uniform(0, 9)
        sx, sy, sz = [r.uniform(8, 25) for _ in range(3)]
        delay = r.randint(0, 3)

        def posf(f, vx=vx, vy=vy, vz=vz, drag=drag, ph=ph, delay=delay):
            t = max(0.0, (f - f0 - delay) / 24)
            k = (1 - math.exp(-drag * t)) / drag
            x = origin[0] + vx * k + 0.06 * math.sin(t * 5 + ph) * min(t, 1)
            y = origin[1] + vy * k
            vt = gravity / (drag * 3.0)         # terminal fall speed (paper flutters down slowly)
            z = origin[2] + vz * k - vt * (t - k)
            return x, y, max(floor + 0.004, z)

        for ax in range(3):
            p.lch(ax).default = 0.0
            p.lch(ax).add(lambda f, ax=ax, posf=posf: posf(f)[ax])
        for ax, sp_ in enumerate((sx, sy, sz)):
            p.rch(ax).add(lambda f, sp_=sp_, ph=ph, posf=posf: 0.0 if posf(f)[2] <= floor + 0.005 else (f - f0) * sp_ + ph * 40)
        S.vis(p.obj, f0 + delay, f0 + dur + r.randint(0, 20))
    return None


def coin(S, loc=(0, 0, 0), r=0.04, name="coin", parent=None):
    g = grp(S, name, loc, parent)
    cyl(name + "_c", r, r * 0.22, (0, 0, 0), "coin", g, bevel=r * 0.05)
    torus(name + "_r", r * 0.72, r * 0.07, (0, 0, r * 0.11), "coin", g, seg=24, rseg=6)
    return g


def progress(S, loc, w=0.6, h=0.07, parent=None, name="prog", color="accent"):
    """progress bar; .fill is a Node whose scale x (0..1) is the progress"""
    g = grp(S, name, loc, parent)
    box(name + "_bg", (w + 0.03, 0.02, h + 0.03), (0, 0, 0), "paper", g, bevel=0.02)
    box(name + "_tr", (w, 0.012, h), (0, -0.008, 0), "paper_a", g, bevel=0.012)
    g.fill = Node(S, box(name + "_fill", (w, 0.014, h * 0.8), (-w / 2, -0.012, 0), color, g, bevel=0.01, origin=(w / 2, 0, 0)))
    return g
