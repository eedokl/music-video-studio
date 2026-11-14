"""Brick sets built from LDraw parts inside Blender (LDraw coordinates, floor y = 0, front = -z).
Anchors and variants live in layouts.py so the shot planner knows where things are.

build(kind, spec, tex) -> dict with handles the film animates:
  screen   Screen (room monitor): tiles from screens.png, talking face from computer_face.png
  gpu      emission strength socket (glows on the beat)
  coins    coin objects (appear one by one)
  lights   {name: light object}, base energies in "base"
  spots    stage/rooftop coloured lights + cone materials (cycle on the beat)
  bulbs    emission sockets of bulb rows
spec: {"kind", "flip", "palette": {...}, "coins": n, "skyline": "<png>", "seed": n}
Sets: room, stage, rooftop, house (exterior + room behind the window), arena, cloud (see layouts.py).
"""
import math

import bpy

import ldraw as L
import shading as H
from layouts import MOODS, SETS


class Screen:
    """Monitor picture: tile from the screens atlas + talking face (mouth shapes of the speaking screen figure)."""

    def __init__(self, M, tex, tiles, width=74, height=62, centre=(0, -38, -10.3)):
        m = bpy.data.materials.new("Screen")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = 1.4
        uvn = nt.nodes.new("ShaderNodeUVMap")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(uvn.outputs[0], sep.inputs[0])
        self.tile = nt.nodes.new("ShaderNodeValue")
        self.mouth = nt.nodes.new("ShaderNodeValue")
        self.face = nt.nodes.new("ShaderNodeValue")
        cc, _ = H.atlas_tex(nt, tex / "screens.png", sep.outputs[0], sep.outputs[1], max(tiles, 1), self.tile.outputs[0])
        gc, ga = H.atlas_tex(nt, tex / "computer_face.png", sep.outputs[0], sep.outputs[1], 9, self.mouth.outputs[0])
        dark = H.mix_rgb(nt, self.face.outputs[0], cc, (0.02, 0.04, 0.08, 1))
        c = H.mix_rgb(nt, H.math_node(nt, "MULTIPLY", ga, self.face.outputs[0]), dark, gc)
        nt.links.new(c, em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        self.strength = em.inputs["Strength"]
        H.plane("Monitor_screen", centre, M, width, height, m)

    def key(self, f, tile, face=0.0, mouth=0, strength=1.4):
        self.tile.outputs[0].default_value = float(tile)
        self.face.outputs[0].default_value = float(face)
        self.mouth.outputs[0].default_value = float(mouth)
        self.strength.default_value = strength
        for s in (self.tile.outputs[0], self.face.outputs[0], self.mouth.outputs[0], self.strength):
            s.keyframe_insert("default_value", frame=f)


class Placer:
    """Positions through the set's flip (mirror left/right)."""

    def __init__(self, flip):
        self.s = -1 if flip else 1

    def T(self, x, y, z):
        return L.T(self.s * x, y, z)

    def RY(self, a):
        return L.RY(self.s * a)

    def bl(self, x, y, z):
        return H.bl(self.s * x, y, z)


def row(P, y, a, b, grid, colour, z=150, parts=None):
    """One course of bricks from x=a to b (running bond by `grid`)."""
    length = {80: "3010", 60: "3622", 40: "3004", 20: "3005"}
    x = a
    while x < b - 1:
        to_joint = (grid - x) % 80 or 80
        lg = max(k for k in length if k <= min(to_joint, 80, b - x))
        ob = L.part(length[lg], colour, P.T(x + lg / 2, y, z))
        if parts is not None:
            parts.append(ob)
        x += lg


def lights(P, kind, mood, Z):
    c = MOODS[mood]
    bl = P.bl
    if kind == "room":
        Z["lights"] = dict(
            key=H.light("Key", "AREA", bl(-220, -320, -280), bl(40, -84, 0), c["key"], 0.8, 0.16),
            key2=H.light("Key2", "AREA", bl(330, -300, -260), bl(190, -84, 10), c["key"], 0.5, 0.12),
            rim=H.light("Rim", "AREA", bl(180, -280, 260), bl(80, -84, 0), c["rim"], 0.9, 0.08),
            window=H.light("WindowLight", "AREA", bl(-200, -150, 280), bl(-60, -60, 0), c["fill"], 0.5, 0.15),
            wall=H.light("WallLight", "AREA", bl(0, -400, -120), bl(0, -120, 150), c["fill"], 0.6, 0.3),
            screen=H.light("ScreenLight", "AREA", bl(70, -80, -20), bl(0, -84, 0), (0.45, 0.85, 1.0), 0.015, 0.03),
        )
    elif kind == "stage":
        Z["lights"] = dict(
            key=H.light("Front", "AREA", bl(0, -300, -350), bl(0, -80, 0), c["key"], 0.7, 0.15),
            rim=H.light("RimB", "AREA", bl(0, -300, 250), bl(0, -80, 0), c["rim"], 0.9, 0.1),
        )
    elif kind == "house":                       # room lights moved inside the facade + moon + window glow outside
        Z["lights"] = dict(
            key=H.light("Key", "AREA", bl(-150, -250, -110), bl(40, -84, 0), c["key"], 0.8, 0.16),
            key2=H.light("Key2", "AREA", bl(300, -250, -110), bl(190, -84, 10), c["key"], 0.5, 0.12),
            rim=H.light("Rim", "AREA", bl(180, -280, 260), bl(80, -84, 0), c["rim"], 0.9, 0.08),
            wall=H.light("WallLight", "AREA", bl(0, -300, -100), bl(0, -120, 150), c["fill"], 0.6, 0.3),
            screen=H.light("ScreenLight", "AREA", bl(70, -80, -20), bl(0, -84, 0), (0.45, 0.85, 1.0), 0.015, 0.03),
            window=H.light("WindowGlow", "AREA", bl(40, -150, -150), bl(40, -40, -500), (1.0, 0.75, 0.45), 0.6, 0.12),
            moon=H.light("MoonSun", "SUN", (0, 0, 1), None, (0.55, 0.65, 1.0), 0.35),
        )
        Z["lights"]["moon"].rotation_euler = (math.radians(55), math.radians(-25), math.radians(20))
    elif kind in ("arena", "cloud"):
        Z["lights"] = dict(
            key=H.light("Front", "AREA", bl(0, -350, -500), bl(0, -80, 0), c["key"], 1.4, 0.2),
            rim=H.light("Edge", "AREA", bl(0, -300, 350), bl(0, -80, 0), c["rim"], 1.0, 0.15),
            fill=H.light("Fill", "AREA", bl(-300, -250, -150), bl(0, -80, 0), c["fill"], 0.5, 0.2),
        )
        if kind == "cloud":
            Z["lights"]["moon"] = H.light("MoonSun", "SUN", (0, 0, 1), None, (0.6, 0.7, 1.0), 0.6)
            Z["lights"]["moon"].rotation_euler = (math.radians(50), math.radians(20), math.radians(-20))
    else:
        Z["lights"] = dict(
            key=H.light("Moon", "AREA", bl(-260, -420, -300), bl(0, -80, 0), (0.75, 0.82, 1.0), 0.9, 0.2),
            fill=H.light("BulbFill", "AREA", bl(200, -250, -200), bl(0, -84, 0), c["key"], 0.45, 0.2),
            rim=H.light("Rim", "AREA", bl(100, -280, 300), bl(0, -84, 0), c["rim"], 0.8, 0.1),
        )
    for k in ("key", "key2"):                    # less gloss: the light spot washes out faces and torsos otherwise
        if k in Z["lights"]:
            Z["lights"][k].data.specular_factor = 0.45
    Z["base"] = {k: l.data.energy for k, l in Z["lights"].items()}


def room(P, spec, tex, Z):
    pal = spec["palette"]
    tl = Z["parts"]
    tl.append(L.part("3811", pal.get("floor", 72), L.T(0, 0, 60)))
    tl.append(L.part("3811", pal.get("floor", 72), L.T(0, 0, -580)))
    win = (-280, -120)
    for r in range(12):
        y = -24 * (r + 1)
        colour = pal["wall"][r % 2]
        grid = -360 + (40 if r % 2 else 0)
        if 3 <= r <= 8:
            row(P, y, -640, win[0], grid, colour, parts=tl)
            row(P, y, win[1], 560, grid, colour, parts=tl)
        else:
            row(P, y, -640, 560, grid, colour, parts=tl)
    for x in (win[0] + 40, win[0] + 120):
        tl.append(L.part("57894", 15, P.T(x, -216, 150)))
    sky = H.image_material("NightCity", spec.get("skyline") or (tex / "skyline.png"), 1.0)
    tl.append(H.plane("NightCity", (-200 * P.s, -150, 0), L.T(0, 0, 300), 520, 390, sky))
    for x in (30, 130):                                             # desk
        for z in (-30, 30):
            tl.append(L.part("3005", 0, P.T(x, -24, z)))
    for z in (-20, 20):
        tl.append(L.part("3795", 70, P.T(80, -32, z)))
    for x in (40, 80, 120):
        for z in (-20, 20):
            tl.append(L.part("3068b", 70, P.T(x, -40, z)))
    tl += [L.part("3069b", 0, P.T(55, -48, -22)), L.part("3069b", 0, P.T(55, -48, -12)),
           L.part("3062b", 15, P.T(28, -64, 28))]
    MON = P.T(88, -40, 18) @ P.RY(30)
    for k in range(3):
        tl.append(L.part("3010", 0, MON @ L.T(0, -24 * (k + 1), 0)))
    tl.append(L.part("3710", 0, MON @ L.T(0, -80, 0)))
    Z["screen"] = Screen(MON, tex, spec.get("screen_tiles", 1))
    GPU = P.T(110, -48, -28)
    tl += [L.part("3020", 0, GPU), L.part("14769", 0, GPU @ L.T(20, -8, 0))]
    glow = L.part("3068b", 57, GPU @ L.T(-20, -8, 0))
    tl.append(glow)
    gm, Z["gpu"] = H.glow_material("GPU_glow", (1.0, 0.16, 0.0), 0.8)
    H.set_material(glow, gm)
    # coins stand at the back right of the desk: in front of the monitor they hid the talking screen
    Z["coins"] = [L.part("14769", 191, P.T(130, -48 - 8 * k, 20), f"coin_{k}") for k in range(int(spec.get("coins", 0)))]
    for k in range(7):                                              # server rack with LEDs
        tl.append(L.part("3003", 0, P.T(240, -24 * (k + 1), 100)))
    for i, c in enumerate([(0.2, 0.9, 1.0), (0.3, 1.0, 0.5)]):
        m, _ = H.glow_material(f"LED_{i}", c, 4.0)
        for k in range(7):
            for j in range(2):
                if (k + j) % 2 == i:
                    tl.append(H.plane(f"led_{k}_{j}", (-8 + 16 * j, -24 * (k + 1) + 12, -20.3), P.T(240, 0, 100), 5, 3, m))


def stage(P, spec, tex, Z):
    pal = spec["palette"]
    tl = Z["parts"]
    tl.append(L.part("3811", pal.get("floor", 0), L.T(0, 0, 60)))
    tl.append(L.part("3811", pal.get("floor", 0), L.T(0, 0, -580)))
    for x in range(-300, 320, 20):                                  # curtain: columns of round bricks
        for k in range(14):
            tl.append(L.part("3062b", pal.get("curtain", 320), L.T(x, -24 * (k + 1), 150 + (10 if (x // 20) % 2 else 0))))
    mats = [H.glow_material(f"Bulb_{i}", (1.0, 0.55, 0.15), 1.5) for i in range(2)]
    for i in range(23):                                             # bulb arch
        w = math.pi * i / 22
        ob = L.part("3062b", 46, L.T(-230 * math.cos(w), -40 - 230 * math.sin(w), 128) @ L.RX(-90))
        H.set_material(ob, mats[i % 2][0])
        tl.append(ob)
    Z["bulbs"] = [st for _, st in mats]
    for i, (x, colour) in enumerate(zip((-170, 0, 170), pal.get("spots", [[1, 0.3, 0.6], [0.3, 0.7, 1], [1, 0.8, 0.3]]))):
        sp = H.light(f"Spot_{i}", "SPOT", H.bl(x, -420, -60), H.bl(x * 0.6, 0, 0), tuple(colour), 2.5, 0.02)
        sp.data.spot_size = math.radians(28)
        sp.data.spot_blend = 0.4
        bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.05, radius2=0.002, depth=0.17, end_fill_type="NOTHING")
        k = bpy.context.active_object
        k.name = f"Cone_{i}"
        a, b = H.bl(x, -420, -60), H.bl(x * 0.6, 0, 0)
        k.location = (a + b) / 2
        k.rotation_mode = "QUATERNION"
        k.rotation_quaternion = (a - b).to_track_quat("Z", "Y")
        km = bpy.data.materials.new(f"Cone_{i}")
        km.use_nodes = True
        km.surface_render_method = "BLENDED"
        nt = km.node_tree
        nt.nodes.clear()
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        add = nt.nodes.new("ShaderNodeAddShader")
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (*colour, 1)
        lw = nt.nodes.new("ShaderNodeLayerWeight")            # cone visible only at its rim, figures stay clear
        lw.inputs["Blend"].default_value = 0.5
        pw = H.math_node(nt, "POWER", lw.outputs["Facing"], 2.0)
        nt.links.new(H.math_node(nt, "MULTIPLY", pw, 0.05), em.inputs["Strength"])
        nt.links.new(tr.outputs[0], add.inputs[0])
        nt.links.new(em.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], o.inputs["Surface"])
        k.data.materials.append(km)
        Z["spots"].append(dict(light=sp, em=em, colour=tuple(colour)))
    G = P.T(230, 0, -40)                                            # graphics card on a plinth
    for k in range(2):
        tl.append(L.part("3001", 72, G @ L.T(0, -24 * (k + 1), 0)))
    tl += [L.part("3020", 0, G @ L.T(0, -56, 0)), L.part("14769", 0, G @ L.T(20, -64, 0))]
    gl = L.part("3068b", 57, G @ L.T(-20, -64, 0))
    gm, Z["gpu"] = H.glow_material("GPU_stage", (1.0, 0.16, 0.0), 0.8)
    H.set_material(gl, gm)
    tl.append(gl)
    K = P.T(-90, 0, -66)                                            # keyboard riser
    for x in (-70, 70):
        tl.append(L.part("3005", 0, K @ L.T(x, -24, 0)))
    tl.append(L.part("3034", 0, K @ L.T(0, -32, 0)))
    for i in range(8):
        tl.append(L.part("3069b", 15 if i % 3 else 0, K @ L.T(-70 + i * 20, -40, 0) @ L.RY(90)))
    Z["coins_at"] = (-150 * P.s, 0, -40)


def rooftop(P, spec, tex, Z):
    pal = spec["palette"]
    tl = Z["parts"]
    tl.append(L.part("3811", pal.get("floor", 72), L.T(0, 0, 60)))
    tl.append(L.part("3811", pal.get("floor", 72), L.T(0, 0, -580)))
    for r in range(2):                                              # parapet at the back
        row(P, -24 * (r + 1), -400, 400, -360 + 40 * r, pal.get("parapet", 71), z=200, parts=tl)
    for x in range(-380, 400, 40):
        tl.append(L.part("3070b", 15, P.T(x, -56, 200)))
    sky = H.image_material("Skyline", spec.get("skyline") or (tex / "skyline.png"), 1.0)
    tl.append(H.plane("Skyline", (0, -260, 0), L.T(0, 0, 520), 1500, 1000, sky))
    for k in range(9):                                              # stair hut with a dark door (cameo entrance)
        for x in (-320, -200):
            tl.append(L.part("3003", 72, P.T(x, -24 * (k + 1), 120)))
            tl.append(L.part("3003", 72, P.T(x, -24 * (k + 1), 160)))
    for k in (7, 8):                                                # lintel over the door
        row(P, -24 * (k + 1), -300, -220, -300, 72, z=120, parts=tl)
    dm = bpy.data.materials.new("Doorway")
    dm.use_nodes = True
    dm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.01, 0.01, 0.012, 1)
    tl.append(H.plane("Doorway", (0, -84, 0), P.T(-260, 0, 175), 80, 168, dm))
    for k in range(10):                                             # antenna with a red light
        tl.append(L.part("3062b", 71, P.T(300, -24 * (k + 1), 160)))
    red, Z["beacon"] = H.glow_material("Beacon", (1.0, 0.05, 0.02), 6.0)
    H.set_material(L.part("3062b", 36, P.T(300, -264, 160)), red)
    mats = [H.glow_material(f"Bulb_{i}", tuple(pal.get("bulbs", [1.0, 0.75, 0.35])), 2.0) for i in range(2)]
    for x in (-360, 360):                                           # string lights between two poles
        for k in range(9):
            tl.append(L.part("3062b", 0, P.T(x, -24 * (k + 1), 190)))
    for i in range(21):
        u = i / 20
        x, y = -360 + 720 * u, -216 + 60 * 4 * u * (1 - u)
        ob = L.part("3062b", 46, P.T(x, y, 190) @ L.RX(-90))
        H.set_material(ob, mats[i % 2][0])
        tl.append(ob)
    Z["bulbs"] = [st for _, st in mats]
    tl.append(L.part("3941", 15, P.T(-200, 0, -30)))               # a round plinth to stand props on
    Z["coins_at"] = (-200 * P.s, -24, -30)


def house(P, spec, tex, Z):
    """Night exterior: Tim's room (room()) behind a facade with a lit window, garden, fence, trees, moon, stars."""
    import numpy as np
    pal = spec["palette"]
    room(P, spec, tex, Z)
    front = Z["parts"].pop(1)                                       # the room's front floor plate -> garden
    bpy.data.objects.remove(front)
    tl = Z["parts"]
    FZ, FX = -160, (-40, 120)
    fac = pal.get("facade", [19, 28])
    for r in range(14):                                             # facade with the window opening
        y = -24 * (r + 1)
        grid = -360 + (40 if r % 2 else 0)
        if 3 <= r <= 8:
            row(P, y, -360, FX[0], grid, fac[r % 2], z=FZ, parts=tl)
            row(P, y, FX[1], 440, grid, fac[r % 2], z=FZ, parts=tl)
        else:
            row(P, y, -360, 440, grid, fac[r % 2], z=FZ, parts=tl)
    for x in (0, 80):
        tl.append(L.part("57894", 15, P.T(x, -216, FZ)))
    for x in range(-340, 440, 40):                                  # roof edge
        tl.append(L.part("3039", pal.get("roof", 320), P.T(x, -360, FZ - 10) @ L.RY(180)))
    for z in (-480, -1120, -1760):                                  # lawn
        for x in (-320, 320):
            tl.append(L.part("3811", 2, L.T(x, 0, z)))
    for x in range(-320, 480, 80):                                  # fence
        tl.append(L.part("33303", 15, P.T(x, -48, -340)))
    rng = np.random.default_rng(int(spec.get("seed", 4)))
    trees, tries = [], 0
    while len(trees) < 7 and tries < 300:                           # trees left and right of the camera path
        tries += 1
        x, z = rng.uniform(-480, 520), rng.uniform(-1700, -420)
        if abs(x - 60) < 150 or any(abs(x - a) < 90 and abs(z - b) < 90 for a, b in trees):
            continue
        trees.append((x, z))
        h = int(rng.integers(2, 5))
        for k in range(h):
            tl.append(L.part("3941", 6, P.T(x, -24 * (k + 1), z)))
        tl.append(L.part("3470", 2, P.T(x, -24 * h, z) @ L.RY(float(rng.uniform(0, 360)))))
    mm, _ = H.glow_material("Moon", (1.0, 0.96, 0.82), 3.0)
    moon = L.part("14769", 15, P.T(520, -620, 1400) @ L.RX(90), "Moon")
    moon.scale = (5, 5, 5)
    H.set_material(moon, mm)
    sm, _ = H.glow_material("Stars", (0.85, 0.9, 1.0), 6.0)
    for i in range(70):
        H.plane(f"star_{i}", (0, 0, 0), L.T(rng.uniform(-1600, 1600), rng.uniform(-1500, -420), 1500), 6, 6, sm)


def arena(P, spec, tex, Z):
    """Winners' podium (3 heights), stadium lights, dark stands at the back, a mountain of chips (cameo on top)."""
    pal = spec["palette"]
    tl = Z["parts"]
    for z in (60, -580, 700):
        tl.append(L.part("3811", pal.get("floor", 72), L.T(0, 0, z)))
    for x, high in ((0, 3), (-80, 2), (80, 1)):                     # podium
        for k in range(high):
            tl.append(L.part("3001", pal.get("podium", 15), P.T(x, -24 * (k + 1), 40)))
    mats = [H.glow_material(f"Stadium_{i}", tuple(pal.get("lights", [1.0, 0.95, 0.8])), 5.0) for i in range(2)]
    for i in range(16):                                             # stadium light strip
        tl.append(H.plane(f"stadium_{i}", (-450 + i * 60, -260, 0), L.T(0, 0, 420), 30, 12, mats[i % 2][0]))
    Z["bulbs"] = [st for _, st in mats]
    for r in range(3):                                              # stands: steps of dark bricks
        for i in range(30):
            for k in range(r + 1):
                tl.append(L.part("3010", pal.get("stands", 0),
                                 P.T(-600 + i * 40 + (20 if r % 2 else 0), -24 * (k + 1), 380 + 40 * r)))
    bx, bz = 250, 190                                               # chip mountain
    for layer in range(7):
        n = 7 - layer
        for i in range(n):
            for j in range(n):
                x, z = bx + (i - (n - 1) / 2) * 40, bz + (j - (n - 1) / 2) * 40
                tl.append(L.part("3068b", 0 if (i + j + layer) % 3 else 72, P.T(x, -8 * (layer + 1), z)))
                if (i * 7 + j * 3 + layer) % 5 == 0:
                    tl.append(L.part("3070b", 82, P.T(x + 10, -8 * (layer + 1) - 8, z + 10)))
    Z["coins_at"] = (-150 * P.s, 0, -40)


def cloud(P, spec, tex, Z):
    """Auction above the clouds: white floor, round-brick clouds, lectern with a gavel, rows of seats rising to the
    back (the cameo sits in the last row), a sea of gold coins in front, moon and stars."""
    import numpy as np
    pal = spec["palette"]
    tl = Z["parts"]
    rng = np.random.default_rng(int(spec.get("seed", 5)))
    for x in (-640, 0, 640):
        for z in (60, -580):
            tl.append(L.part("3811", pal.get("floor", 15), L.T(x, 0, z)))
    cols = pal.get("cloud", [15, 151])
    for c in range(14):                                             # clouds: heaps of round bricks around the edge
        cx = rng.uniform(-700, 700)
        if abs(cx) < 420:
            cz = rng.uniform(420, 680) if rng.random() < 0.6 else rng.uniform(-900, -560)
        else:
            cz = rng.uniform(-700, 600)
        for k in range(int(rng.integers(6, 14))):
            x, z = cx + rng.uniform(-90, 90), cz + rng.uniform(-60, 60)
            for j in range(int(rng.integers(1, 4))):
                tl.append(L.part("3941" if rng.random() < 0.6 else "3062b", int(cols[(k + j) % len(cols)]),
                                 P.T(x, -24 * (j + 1), z)))
    for x in (-20, 20):                                             # lectern
        for k in range(3):
            tl.append(L.part("3005", pal.get("lectern", 70), P.T(x, -24 * (k + 1), 60)))
    tl.append(L.part("3020", pal.get("lectern", 70), P.T(0, -80, 60)))
    tl += [L.part("3005", 70, P.T(10, -96, 55) @ L.RZ(90)), L.part("3062b", 70, P.T(-6, -96, 55))]   # gavel
    for r in range(4):                                              # rows of seats rising to the back
        for i in range(-6, 7):
            for k in range(r + 1):
                tl.append(L.part("3010", pal.get("seats", 72), P.T(i * 80, -24 * (k + 1), 200 + 50 * r)))
    for k in range(160):                                            # sea of gold coins in front
        a, rr = rng.uniform(0, 2 * math.pi), 160 * math.sqrt(rng.uniform(0, 1))
        tl.append(L.part("14769", 191 if k % 3 else 82,
                         P.T(-120 + rr * math.cos(a) * 1.6, -8 - 8 * int(rng.integers(0, 3)), -120 + rr * math.sin(a) * 0.7)
                         @ L.RX(rng.uniform(-25, 25)) @ L.RZ(rng.uniform(-25, 25))))
    mm, _ = H.glow_material("Moon", (1.0, 0.96, 0.82), 3.0)
    moon = L.part("14769", 15, P.T(420, -520, 900) @ L.RX(90), "Moon")
    moon.scale = (5, 5, 5)
    H.set_material(moon, mm)
    sm, _ = H.glow_material("Stars", (0.85, 0.9, 1.0), 6.0)
    for i in range(60):
        H.plane(f"star_{i}", (0, 0, 0), L.T(rng.uniform(-1600, 1600), rng.uniform(-1400, -300), 1200), 6, 6, sm)
    Z["coins_at"] = (150 * P.s, 0, -40)


def build(kind, spec, tex):
    if kind not in SETS:
        raise SystemExit(f"unknown brick set '{kind}' (have: {', '.join(SETS)})")
    P = Placer(spec.get("flip", False))
    Z = dict(parts=[], lights={}, spots=[], bulbs=[], coins=[], screen=None, gpu=None, kind=kind, P=P)
    {"room": room, "stage": stage, "rooftop": rooftop, "house": house, "arena": arena, "cloud": cloud}[kind](P, spec, tex, Z)
    lights(P, kind, spec["palette"].get("mood", "night_blue"), Z)
    if not Z["coins"] and spec.get("coins"):                        # loose coin stack where the set has room for it
        x, y, z = Z.get("coins_at", (60, 0, -60))
        Z["coins"] = [L.part("14769", 191, L.T(x, y - 8 * k, z), f"coin_{k}") for k in range(int(spec["coins"]))]
    return Z


def dim(Z, f, factor, keep=("screen", "window")):
    """Dim the set lights (0 = off); screen and window light stay."""
    for k, l in Z["lights"].items():
        l.data.energy = Z["base"][k] * (1.0 if k in keep else factor)
        l.data.keyframe_insert("energy", frame=f)
