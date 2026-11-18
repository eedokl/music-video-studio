# Runs inside Blender's Python (bpy) - started by stage_run.py, never with uv.
"""Theatre machinery for the stage: set changes in view of the audience (walls fly out, furniture rolls off, a floor
rolls out, the light goes down to a follow spot and comes up on the new world, stagehands in black cross the
stage), a curtain that opens and closes, a concert light show (moving heads with real beams in haze), dimming and
a follow spot that keeps a figure in its light.

A set change works on "worlds": every piece of scenery belongs to one world (a name such as "room" or "stage") and
has a way of leaving - "fly" (up into the fly loft), "roll" (sideways off stage), "sink" (down through the floor),
"unroll" (a floor or carpet that rolls up towards its origin: put the node origin at the edge it rolls to) or an
own offset (x, y, z) in metres. Lights and glowing materials belong to worlds too.

    import stage_theatre as T
    ch = T.Change(S)
    ch.piece(room["walls"], "room", "fly"); ch.piece(room["desk"], "room", "roll")
    ch.piece(stage["arch"], "stage", "fly"); ch.piece(stage["floor"], "stage", "unroll")
    ch.lights("room", room["lights"]); ch.lights("stage", stage["lights"]); ch.glow("stage", bulbs_mat)
    ch.state(1, "room")
    when = ch.change(120, "stage", frames=40, follow=tim, crew=2)   # -> {"dark", "away", "there", "lit"}

World: metres, Z up, the audience (camera) on the -Y side; "roll" leaves to the nearer side.
"""
import math

import bmesh
import bpy
import stage_core as _C
from mathutils import Vector
from stage_core import Node, capsule, cyl, ell, emit, empty, mat, spot

V = Vector
AWAY = {"fly": (0, 0, 5.0), "sink": (0, 0, -3.0), "roll": (7.0, 0, 0)}     # how far a piece goes (roll: x sign)
TINY = 0.0005


# ====================================================================== lights
def lights_base(lights):
    """{name: light object} -> {name: energy now} (the levels dim() works from)"""
    return {k: lo.data.energy for k, lo in lights.items()}


def dim(S, lights, f, factor, ease="io", base=None, skip=()):
    """key every light of a dict at frame f to factor x its base level (base: lights_base() taken at build time)"""
    base = base or lights_base(lights)
    for k, lo in lights.items():
        if k in skip:
            continue
        S.ch(lo.data, "energy", 0, base[k]).key(f, base[k] * factor, ease)


def _strength(S, m):
    """the stage channel of a material's emission strength (an Emission node or a Principled BSDF)"""
    nt = m.node_tree
    n = next((x for x in nt.nodes if x.type == "EMISSION"), None)
    if n is not None:
        return S.ch(nt, f'nodes["{n.name}"].inputs[1].default_value', 0), n.inputs[1].default_value
    n = next(x for x in nt.nodes if x.type == "BSDF_PRINCIPLED")
    return S.ch(nt, f'nodes["{n.name}"].inputs["Emission Strength"].default_value', 0), \
        n.inputs["Emission Strength"].default_value


# ====================================================================== the set change
class Change:
    def __init__(self, S):
        self.S = S
        self.pieces = []          # (node, world, offset, kind, rest location, rest scale)
        self.light = {}           # world -> [(lights dict, base)]
        self.glows = {}           # world -> [(channel, strength)]

    def piece(self, node, world, how="fly", away=None):
        """a piece of scenery (Node) that belongs to `world`; how = fly | roll | sink | unroll | (dx, dy, dz)"""
        n = node if isinstance(node, Node) else Node(self.S, node)
        o = n.obj
        if isinstance(how, (tuple, list)):
            off, kind = tuple(how), "move"
        elif how == "unroll":
            off, kind = (0, 0, 0), "unroll"
        else:
            off, kind = AWAY[how], "move"
            if how == "roll":
                x = o.matrix_world.translation.x
                off = ((1 if x >= 0 else -1) * (away or off[0]), 0, 0)
            elif away is not None:
                off = (0, 0, math.copysign(away, off[2]))
        self.pieces.append((n, world, off, kind, tuple(o.location), tuple(o.scale)))
        return n

    def lights(self, world, lights):
        """lights (dict name -> light object) of a world; their levels now are the full levels"""
        self.light.setdefault(world, []).append((lights, lights_base(lights)))

    def glow(self, world, material, strength=None):
        """an emission material (bulbs, signs, screens) that is lit only in its world"""
        ch, s = _strength(self.S, material)
        self.glows.setdefault(world, []).append((ch, strength if strength is not None else s))

    # ---- keys
    def _put(self, n, off, kind, rest, scl, f, there, ease):
        if kind == "unroll":
            v = 1.0 if there else TINY
            n.scl(f, scl[0], scl[1] * v, scl[2] * v, ease)
        else:
            d = (0, 0, 0) if there else off
            n.loc(f, rest[0] + d[0], rest[1] + d[1], rest[2] + d[2], ease)

    def _light(self, world, f, factor, ease):
        for ls, base in self.light.get(world, []):
            dim(self.S, ls, f, factor, ease, base)

    def _glow(self, world, f, factor, ease="hold"):
        for ch, s in self.glows.get(world, []):
            ch.key(f, s * factor, ease)

    def worlds(self):
        return {w for _, w, *_ in self.pieces} | set(self.light) | set(self.glows)

    def state(self, f, world):
        """from frame f on: `world` stands and is lit, every other world is gone and dark (a hard cut)"""
        for n, w, off, kind, rest, scl in self.pieces:
            self._put(n, off, kind, rest, scl, f, w == world, "hold")
        for w in self.worlds():
            self._light(w, f, 1.0 if w == world else 0.0, "hold")
            self._glow(w, f, 1.0 if w == world else 0.0)

    def change(self, f0, to, frames=36, follow=None, crew=0, chase=True):
        """the change in view of the audience from frame f0: the light goes down to a follow spot (on `follow`: a
        figure or a point; None = no spot), the pieces of the other worlds leave (fly, roll ...), the pieces of `to`
        come in (flying pieces with an overshoot), crew = number of stagehands crossing in the dark, and the new
        light comes up (bulbs of `to` light one after the other with chase=True). Returns the frames of the phases
        {"dark", "away", "there", "lit"}. Call state(1, <old world>) first if the clip starts in the old world."""
        S = self.S
        a, m, e = f0, f0 + int(frames * 0.35), f0 + frames
        old = [w for w in self.worlds() if w != to]
        for w in old:
            self._light(w, a + 2, 1.0, "hold")
            self._light(w, a + 8, 0.08, "out")
            self._light(w, m + 4, 0.0, "io")
            self._glow(w, a + 6, 0.0)
        self._light(to, a, 0.0, "hold")
        self._glow(to, a, 0.0)
        for i, (n, w, off, kind, rest, scl) in enumerate(self.pieces):
            st = i % 3                                         # pieces do not all move at once
            if w != to:
                self._put(n, off, kind, rest, scl, a + 6 + st, True, "hold")
                self._put(n, off, kind, rest, scl, m + 6 + st, False, "in")
            else:
                self._put(n, off, kind, rest, scl, m, False, "hold")
                self._put(n, off, kind, rest, scl, e - 2 + st, True,
                          "back" if kind == "move" and off[2] > 0 else "out3")
        self._light(to, e, 0.08, "hold")
        self._light(to, e + 6, 1.0, "out")
        for ch, s in self.glows.get(to, []):
            if chase:
                for j in range(6):
                    ch.key(e + j, s * (j + 1) / 6, "hold")
            else:
                ch.key(e, s, "hold")
        if follow is not None:
            follow_spot(S, follow, a + 2, e + 6)
        for k in range(crew):
            hand = stagehand(S, f"crew{k}_{f0}")
            side = 1 if k % 2 == 0 else -1
            y = -0.6 - 0.5 * k
            hand.show(a + 4 + 3 * k, e + 2)
            hand.walk(a + 4 + 3 * k, e - 2, (side * 5.5, y), (-side * 5.5, y))
        return dict(dark=a + 8, away=m + 8, there=e, lit=e + 6)


# ====================================================================== follow spot
def follow_spot(S, target, f0, f1, power=1600.0, angle=26.0, loc=(0.0, -5.0, 4.6), color="#FFF2DD", fade=6):
    """a spot from the front that keeps `target` (a Char - aimed at its chest - or a world point) in its light
    from f0 to f1 (fading in and out over `fade` frames). Returns the light object."""
    aim = empty(f"follow_aim_{f0}")
    if hasattr(target, "pos"):
        h = getattr(target, "body_z0", 0.3) * getattr(target, "size", 1.0) + 0.15
        for i in range(3):
            S.ch(aim, "location", i, 0.0).add(lambda f, i=i: (target.pos(f) + V((0, 0, h)))[i])
    else:
        aim.location = target
    lo = spot(f"follow_{f0}", loc, tuple(aim.location), power=0.0, angle=angle, blend=0.3, color=color, radius=0.03)
    c = lo.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"
    en = S.ch(lo.data, "energy", 0, 0.0)
    en.key(f0, 0.0, "hold")
    en.key(f0 + fade, power, "out")
    en.key(f1 - fade, power)
    en.key(f1, 0.0, "io")
    return lo


# ====================================================================== stagehands
class Stagehand(Node):
    """a stagehand in black (hood, head torch) built from primitives; walk() crosses the stage with steps"""

    def __init__(self, S, name, loc=(0, -6, 0), height=1.7):
        k = height / 1.7
        black = mat("crew_black", "#0C0C10", rough=0.8)
        skin = mat("crew_skin", "#C89B7B", rough=0.6, sss=0.1)
        super().__init__(S, empty(name, loc))
        self.obj.scale = (k, k, k)
        capsule(name + "_body", (0, 0, 0.78), (0, 0, 1.32), 0.17, 0.19, black, self)
        ell(name + "_head", (0.11, 0.12, 0.13), (0, 0, 1.52), black, self)
        _C.box(name + "_eyes", (0.13, 0.02, 0.035), (0, -0.112, 1.54), skin, self, bevel=0.01)
        cyl(name + "_torch", 0.025, 0.02, (0, -0.12, 1.62), "steel" if "steel" in _C._MATS else black, self,
            rot=(90, 0, 0))
        self.arms, self.legs = {}, {}
        for s, n in ((1, "L"), (-1, "R")):
            a = Node(S, empty(f"{name}_arm{n}", (s * 0.22, 0, 1.30), self))
            capsule(f"{name}_arm{n}m", (0, 0, 0), (0, 0, -0.55), 0.055, 0.05, black, a)
            b = Node(S, empty(f"{name}_leg{n}", (s * 0.09, 0, 0.80), self))
            capsule(f"{name}_leg{n}m", (0, 0, 0), (0, 0, -0.76), 0.07, 0.06, black, b)
            self.arms[n], self.legs[n] = a, b

    def walk(self, f0, f1, a, b, step=7, ease="lin", carry=False):
        """from (x, y) a to b between f0 and f1: heading, bob, leg and arm swing (carry=True: arms forward, as if
        pushing or carrying something)"""
        dx, dy = b[0] - a[0], b[1] - a[1]
        self.loc(f0, a[0], a[1], 0, "hold")
        self.loc(f1, b[0], b[1], 0, ease)
        self.rot(f0, 0, 0, math.degrees(math.atan2(dx, -dy)), "hold")
        on = lambda f: f0 <= f <= f1                                           # noqa: E731
        self.lch(2).add(lambda f: 0.03 * abs(math.sin(math.pi * (f - f0) / step)) if on(f) else 0.0)
        for k, s in (("L", 1), ("R", -1)):
            self.legs[k].rch(0).add(lambda f, s=s: s * 28 * math.sin(math.pi * (f - f0) / step) if on(f) else 0.0)
            if carry:
                self.arms[k].rot(f0, -70, 0, 0, "hold")
            else:
                self.arms[k].rch(0).add(lambda f, s=s: -s * 22 * math.sin(math.pi * (f - f0) / step) if on(f) else 0.0)
        return self

    def show(self, f_on=None, f_off=None, deep=True):
        super().show(f_on, f_off, deep)
        return self


def stagehand(S, name, loc=(0, -6, 0), height=1.7):
    return Stagehand(S, name, loc, height)


# ====================================================================== curtain
class Curtain:
    """a velvet curtain in two halves across x = x0 ± width/2 at depth y: open(f) gathers both halves to the
    sides, close(f) draws them together (folds as tubes - they catch the light)"""

    def __init__(self, S, width=8.0, height=4.2, y=1.4, x0=0.0, color="#7A0F18", folds=None, name="curtain",
                 valance=True):
        self.S = S
        velvet = mat(name + "_velvet", color, rough=0.75, sheen=0.6)
        n = folds or max(8, int(width / 0.28))
        self.halves = []
        for side in (-1, 1):
            g = Node(S, empty(f"{name}_{'L' if side > 0 else 'R'}", (x0 + side * width / 4, y, 0)))
            for i in range(n // 2):
                x = -width / 4 + (i + 0.5) * width / n
                cyl(f"{name}_{side}_{i}", 0.17 * width / 8.0 * 1.0, height, (x, 0.06 if i % 2 else 0, height / 2),
                    velvet, g, seg=16, bevel=0)
            self.halves.append((g, side))
        self.width, self.x0 = width, x0
        if valance:
            _C.box(name + "_valance", (width + 0.6, 0.3, 0.45), (x0, y - 0.2, height - 0.2), velvet, bevel=0.02)

    def _set(self, f, open_, ease):
        for g, side in self.halves:
            x = self.x0 + side * (self.width / 2 - self.width * 0.06 if open_ else self.width / 4)
            g.loc(f, x, None, None, ease)
            g.scl(f, 0.22 if open_ else 1.0, 1, 1, ease)

    def open(self, f, frames=30, ease="io"):
        self._set(f, False, "hold")
        self._set(f + frames, True, ease)
        return self

    def close(self, f, frames=30, ease="io"):
        self._set(f, True, "hold")
        self._set(f + frames, False, ease)
        return self

    def state(self, f, open_):
        self._set(f, open_, "hold")
        return self


# ====================================================================== light show
def _haze(name, density):
    km = bpy.data.materials.new(name)
    km.use_nodes = True
    nt = km.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    vs = nt.nodes.new("ShaderNodeVolumeScatter")
    vs.inputs["Anisotropy"].default_value = 0.55                    # forward scattering
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = 0.9
    nz.inputs["Detail"].default_value = 5.0
    nz.inputs["Roughness"].default_value = 0.62
    nz.inputs["W"].driver_add("default_value").driver.expression = "frame / 70"        # the haze drifts
    cr = nt.nodes.new("ShaderNodeMapRange")
    cr.inputs["From Min"].default_value = 0.38
    cr.inputs["From Max"].default_value = 0.70
    cr.inputs["To Min"].default_value = density * 0.25
    cr.inputs["To Max"].default_value = density * 2.2
    nt.links.new(tc.outputs["Generated"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], cr.inputs["Value"])
    nt.links.new(cr.outputs["Result"], vs.inputs["Density"])
    nt.links.new(vs.outputs[0], o.inputs["Volume"])
    return km


def light_show(S, f_on, beats, colors, f_off=None, xs=(-2.6, -0.9, 0.9, 2.6), y=0.55, z=3.4, angle=11.0,
               power=3200.0, haze=2.2, length=5.0, truss=True, fly_in=24):
    """a concert rig: moving heads on a truss above the stage, narrow beams in haze (real volume light - figures cut
    shadow lanes into it). On from f_on (to f_off), colours and pans change on every beat (beats = clip frames), the
    beams cross. The haze only exists while the show is on (it costs render time: ~2x per frame). fly_in = frames
    in which the rig comes down from the fly loft before f_on (0: it hangs there from the start). -> [head Nodes]"""
    metal = mat("truss", "#2A2C30", rough=0.35, metal=0.9)
    black = mat("head_black", "#121214", rough=0.4, metal=0.3)
    rig = Node(S, empty("show_rig"))
    if fly_in:
        rig.loc(1, 0, 0, 4.0, "hold")
        rig.loc(max(1, f_on - fly_in), 0, 0, 4.0, "hold")
        rig.loc(max(2, f_on - 2), 0, 0, 0.0, "out3")
    if truss:
        tr = Node(S, empty("truss", (0, y, z + 0.32), rig))
        span = (max(xs) - min(xs)) + 2.4
        for dy in (-0.12, 0.12):
            for dz in (-0.1, 0.1):
                cyl(f"truss_{dy}_{dz}", 0.018, span, ((max(xs) + min(xs)) / 2, dy, dz), metal, tr, rot=(0, 90, 0),
                    seg=12)
    heads = []
    f_off = f_off or S.frames + 1
    for i, x in enumerate(xs):
        k = Node(S, empty(f"mh{i}", (x, y, z), rig))
        _C.box(f"mh{i}_yoke", (0.34, 0.06, 0.04), (0, 0, 0.2), black, k, bevel=0.01)
        cyl(f"mh{i}_body", 0.13, 0.32, (0, 0, 0), black, k, seg=24)
        lens = emit(f"mh{i}_lens", "#FFFFFF", 0.0)
        cyl(f"mh{i}_glass", 0.105, 0.01, (0, 0, -0.165), lens, k, seg=24)
        ld = bpy.data.lights.new(f"mh{i}_light", "SPOT")
        ld.energy = 0.0
        ld.spot_size, ld.spot_blend, ld.shadow_soft_size = math.radians(angle), 0.25, 0.04
        lo = bpy.data.objects.new(f"mh{i}_light", ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.parent = k.obj
        lo.location = (0, 0, -0.18)
        r = length * math.tan(math.radians(angle / 2)) * 1.05
        me = bpy.data.meshes.new(f"mh{i}_beam")
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=r, radius2=0.11, depth=length)
        bm.to_mesh(me)
        bm.free()
        beam = bpy.data.objects.new(f"mh{i}_beam", me)
        bpy.context.scene.collection.objects.link(beam)
        beam.parent = k.obj
        beam.location = (0, 0, -0.18 - length / 2)
        me.materials.append(_haze(f"mh{i}_haze", haze))
        beam.visible_shadow = False
        hr = S.ch(beam, "hide_render", 0, 1.0)
        hr.key(1, 1.0, "hold")
        hr.key(f_on, 0.0, "hold")
        hr.key(f_off, 1.0, "hold")
        en = S.ch(ld, "energy", 0, 0.0)
        en.key(1, 0.0, "hold")
        en.key(f_on, 0.0, "hold")
        en.key(f_on + 4, power, "out")
        en.key(f_off - 4, power, "hold")
        en.key(f_off, 0.0, "in")
        em = next(n for n in lens.node_tree.nodes if n.type == "EMISSION")
        lc = S.ch(lens.node_tree, f'nodes["{em.name}"].inputs[1].default_value', 0, 0.0)
        lc.key(f_on, 0.0, "hold")
        lc.key(f_on + 4, 40.0, "out")
        lc.key(f_off, 0.0, "in")
        for j, fb in enumerate(beats):
            if fb < f_on or fb >= f_off:
                continue
            c = _C.srgb(colors[(j + i * 2) % len(colors)])
            for ax in range(3):
                S.ch(ld, "color", ax).key(fb, c[ax], "hold")
                S.ch(lens.node_tree, f'nodes["{em.name}"].inputs[0].default_value', ax).key(fb, c[ax], "hold")
            side = 1 if (j + i) % 2 else -1                     # pan out -> in, the other side on every beat
            k.rot(fb, -8 + 20 * ((j + i) % 2) + 6 * ((j + i) % 3 == 0), side * (16 + 8 * (i % 2)) + x * 6, 0, "io")
        heads.append(k)
    return heads


# ====================================================================== a ready stage
def show_stage(S, width=9.0, depth=7.0, y_back=1.4, arch=2.3, curtain_color="#7A0F18", spots=("#FF4D99", "#4DB3FF",
               "#FFCC4D"), name="stage"):
    """a show stage in the same place as a room: a velvet backdrop (y_back), an arch of light bulbs, a black lacquer
    floor with footlights along its front edge and coloured spots. For Change: {"backdrop", "arch" (fly), "floor"
    (unroll - rolls out from the back towards the audience), "lights" {name: light}, "bulbs" (material)}"""
    from stage_core import area, box, torus
    B = {}
    velvet = mat(name + "_velvet", curtain_color, rough=0.75, sheen=0.6)
    B["backdrop"] = bd = Node(S, empty(name + "_backdrop"))
    n = int(width / 0.28) + 4
    for i in range(n):
        x = -width / 2 - 0.5 + i * 0.28
        cyl(f"{name}_fold{i}", 0.17, 4.2, (x, y_back + (0.06 if i % 2 else 0), 2.1), velvet, bd, seg=16, bevel=0)
    box(name + "_valance", (width + 1.4, 0.3, 0.45), (0, y_back - 0.2, 3.9), velvet, bd, bevel=0.02)
    B["bulbs"] = emit(name + "_bulb", "#FFB060", 3.0)
    B["arch"] = ar = Node(S, empty(name + "_arch"))
    brass = mat(name + "_brass", "#B08A45", rough=0.3, metal=1.0)
    torus(name + "_arch", arch, 0.035, (0, y_back - 0.28, 0.4), brass, ar, rot=(90, 0, 0), arc=0.5)
    for i in range(23):
        w = math.pi * i / 22
        ell(f"{name}_bulb{i}", 0.06, (-arch * math.cos(w), y_back - 0.32, 0.4 + arch * math.sin(w)), B["bulbs"], ar,
            seg=12)
    B["floor"] = fl = Node(S, empty(name + "_floor", (0, y_back - 0.1, 0)))     # origin at the back: rolls out
    box(name + "_lacquer", (width, depth, 0.004), (0, -depth / 2, 0.003), mat(name + "_lacquer", "#0B0B0E",
        rough=0.12, coat=1.0), fl, bevel=0)
    box(name + "_edge", (width, 0.08, 0.06), (0, -depth + 0.3, 0.03), brass, fl, bevel=0.01)
    foot = emit(name + "_footlight", "#FFD7A0", 4.0)
    for i in range(15):
        ell(f"{name}_foot{i}", 0.03, (-width * 0.39 + i * width * 0.78 / 14, -depth + 0.25, 0.07), foot, fl, seg=10)
    L = B["lights"] = {}
    L["front"] = area(name + "_front", (0, -3.5, 3.0), (0, 0.3, 0.8), power=420, size=1.8, color="#FFE6CC")
    L["rim"] = area(name + "_rim", (0, 2.5, 3.0), (0, 0.3, 0.8), power=500, size=1.4, color="#99A0FF")
    for i, c in enumerate(spots):
        x = (i - (len(spots) - 1) / 2) * 1.7
        L[f"spot{i}"] = spot(f"{name}_spot{i}", (x, -0.6, 4.2), (x * 0.6, 0.3, 0), power=900, angle=28, blend=0.4,
                             color=c, radius=0.05)
    return B


def set_change(S, R, world, ch=None, skip=("room",), table="table", fly_above=1.2):
    """register a whole set (the dict a set builder returns, e.g. stage_sets.office) as `world` of a Change: high
    pieces (lamps, boards, windows: origin above fly_above m) fly out, the rest rolls off to the nearer side, a rug
    rolls up, the things on the table roll with the table, lights (light objects in the dict) belong to the world.
    skip = keys that stay (the room itself). -> the Change"""
    ch = ch or Change(S)
    lights, nodes = {}, []
    for k, v in R.items():
        if k in skip:
            continue
        for x in (v if isinstance(v, (list, tuple)) else [v]):
            o = x.obj if isinstance(x, Node) else x
            if isinstance(o, bpy.types.Object) and o.type == "LIGHT":
                lights[f"{k}{len(lights)}"] = o
            elif isinstance(x, Node):
                nodes.append((k, x))
    t = R.get(table)
    tz, tx = (t.obj.matrix_world.translation.z, t.obj.matrix_world.translation.x) if isinstance(t, Node) else (0, 0)
    top = max((c.matrix_world.translation.z + c.dimensions.z / 2 for c in t.obj.children_recursive
               if c.type == "MESH"), default=tz) if isinstance(t, Node) else None
    off_t = ((1 if tx >= 0 else -1) * AWAY["roll"][0], 0, 0)
    for k, n in nodes:
        z = n.obj.matrix_world.translation.z
        if k == "rug":
            ch.piece(n, world, "unroll")
        elif k == table or top is not None and abs(z - top) < 0.12 and z < fly_above:
            ch.piece(n, world, off_t)
        elif z > fly_above:
            ch.piece(n, world, "fly")
        else:
            ch.piece(n, world, "roll")
    if top is not None:                          # loose things on the table top (pens, cups ... not in the dict)
        ms = [c for c in t.obj.children_recursive if c.type == "MESH"]
        lo = [min(c.matrix_world.translation[i] - c.dimensions[i] / 2 for c in ms) for i in range(2)]
        hi = [max(c.matrix_world.translation[i] + c.dimensions[i] / 2 for c in ms) for i in range(2)]
        taken = set()
        for n, *_ in ch.pieces:
            taken.add(n.obj.name)
            taken.update(c.name for c in n.obj.children_recursive)
        for o in list(bpy.context.scene.objects):
            p = o.matrix_world.translation
            if (o.parent is None and o.type in ("MESH", "EMPTY") and o.name not in taken and top - 0.05 < p.z < top + 0.3
                    and lo[0] - 0.05 < p.x < hi[0] + 0.05 and lo[1] - 0.05 < p.y < hi[1] + 0.05):
                ch.piece(Node(S, o), world, off_t)
    if lights:
        ch.lights(world, lights)
    return ch


def stage_change(S, stage, ch=None):
    """register a show_stage() as the world "stage" of a Change (made if ch is None) -> the Change"""
    ch = ch or Change(S)
    ch.piece(stage["backdrop"], "stage", "fly")
    ch.piece(stage["arch"], "stage", "fly")
    ch.piece(stage["floor"], "stage", "unroll")
    ch.lights("stage", stage["lights"])
    ch.glow("stage", stage["bulbs"])
    return ch
