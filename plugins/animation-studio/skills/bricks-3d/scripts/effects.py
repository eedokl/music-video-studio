"""Stop-motion brick effects inside Blender (keyed on twos by brickfilm.py; all seeded, nothing hand-placed):

  SetFlight     the set's bricks fly in and assemble ("in") or fly apart ("out") - a room rebuilding into a stage is
                "out" at the end of one section and "in" at the start of the next
  BrickWord     a word in a 3x5 pixel font built from 1x1 bricks that fly in one by one; optional "fall" time: the
                bricks tumble down to the floor (a sign that falls apart)
  Confetti      1x1 tiles in party colours rain and tumble in front of the camera area
  Tower         a stack of bricks that grows one brick per time (beats) - "the biggest model", piles of chips ...
  Steam         puffs of white round plates rise from a figure's head (or a fixed point, e.g. the GPU) and grow
  Strings       marionette strings from a puppeteer's hands to the heads of other figures (thin glowing threads)
  figure_fx     a minifig falls apart part by part ("fall_apart") or assembles itself from flying parts ("assemble")
Coordinates are LDraw units (floor y = 0, up = -y). Used through plan props, see brickfilm.py.
"""
import math

import numpy as np

import ldraw as L

PIXEL = {   # 3x5 pixel font, rows top to bottom
    "A": [".X.", "X.X", "XXX", "X.X", "X.X"], "B": ["XX.", "X.X", "XX.", "X.X", "XX."], "C": [".XX", "X..", "X..", "X..", ".XX"],
    "D": ["XX.", "X.X", "X.X", "X.X", "XX."], "E": ["XXX", "X..", "XX.", "X..", "XXX"], "F": ["XXX", "X..", "XX.", "X..", "X.."],
    "G": [".XX", "X..", "X.X", "X.X", ".XX"], "H": ["X.X", "X.X", "XXX", "X.X", "X.X"], "I": ["XXX", ".X.", ".X.", ".X.", "XXX"],
    "J": ["..X", "..X", "..X", "X.X", ".X."], "K": ["X.X", "X.X", "XX.", "X.X", "X.X"], "L": ["X..", "X..", "X..", "X..", "XXX"],
    "M": ["X.X", "XXX", "X.X", "X.X", "X.X"], "N": ["X.X", "XXX", "XXX", "X.X", "X.X"], "O": [".X.", "X.X", "X.X", "X.X", ".X."],
    "P": ["XX.", "X.X", "XX.", "X..", "X.."], "Q": [".X.", "X.X", "X.X", "XX.", ".XX"], "R": ["XX.", "X.X", "XX.", "X.X", "X.X"],
    "S": [".XX", "X..", ".X.", "..X", "XX."], "T": ["XXX", ".X.", ".X.", ".X.", ".X."], "U": ["X.X", "X.X", "X.X", "X.X", "XXX"],
    "V": ["X.X", "X.X", "X.X", "X.X", ".X."], "W": ["X.X", "X.X", "X.X", "XXX", "X.X"], "X": ["X.X", "X.X", ".X.", "X.X", "X.X"],
    "Y": ["X.X", "X.X", ".X.", ".X.", ".X."], "Z": ["XXX", "..X", ".X.", "X..", "XXX"],
    "0": ["XXX", "X.X", "X.X", "X.X", "XXX"], "1": [".X.", "XX.", ".X.", ".X.", "XXX"], "2": ["XX.", "..X", ".X.", "X..", "XXX"],
    "3": ["XX.", "..X", ".X.", "..X", "XX."], "4": ["X.X", "X.X", "XXX", "..X", "..X"], "5": ["XXX", "X..", "XX.", "..X", "XX."],
    "6": [".XX", "X..", "XXX", "X.X", "XXX"], "7": ["XXX", "..X", ".X.", ".X.", ".X."], "8": ["XXX", "X.X", "XXX", "X.X", "XXX"],
    "9": ["XXX", "X.X", "XXX", "..X", "XX."], "!": [".X.", ".X.", ".X.", "...", ".X."], "?": ["XX.", "..X", ".X.", "...", ".X."],
    ".": ["...", "...", "...", "...", ".X."], "-": ["...", "...", "XXX", "...", "..."], "$": [".XX", "XX.", ".X.", ".XX", "XX."],
    "%": ["X.X", "..X", ".X.", "X..", "X.X"], "+": ["...", ".X.", "XXX", ".X.", "..."], " ": ["...", "...", "...", "...", "..."],
    "Ä": ["X.X", ".X.", "X.X", "XXX", "X.X"], "Ö": ["X.X", "...", "XXX", "X.X", "XXX"], "Ü": ["X.X", "...", "X.X", "X.X", "XXX"],
}
PARTY = [4, 14, 1, 2, 22, 25, 26, 322, 191]


def key(ob, f, m_ld, visible=True):
    ob.rotation_mode = "QUATERNION"
    ob.matrix_world = L.to_blender(m_ld)
    ob.keyframe_insert("location", frame=f)
    ob.keyframe_insert("rotation_quaternion", frame=f)
    ob.keyframe_insert("scale", frame=f)
    ob.hide_render = not visible
    ob.keyframe_insert("hide_render", frame=f)


def rot(a):
    return L.RX(a[0]) @ L.RY(a[1]) @ L.RZ(a[2])


def word_pixels(text, centre_x, top_y, z, pixel=20):
    """-> LDraw positions (x, y, z) of the bricks of a word (3x5 font, one brick per pixel, 24 LDU per row)"""
    text = text.upper()
    width = len(text) * 4 * pixel - pixel
    x0 = centre_x - width / 2 + pixel / 2
    out = []
    for i, ch in enumerate(text):
        for r, line in enumerate(PIXEL.get(ch, PIXEL["?"])):
            for c, v in enumerate(line):
                if v == "X":
                    out.append((x0 + (i * 4 + c) * pixel, top_y + r * 24 * pixel / 20, z))
    return out


class SetFlight:
    """All set bricks (not floors or big planes) fly in to their places ("in") or away ("out") within [t, t + d]."""

    def __init__(self, objects, t, d, mode, seed):
        rng = np.random.default_rng(seed)
        self.t, self.d, self.mode = t, d, mode
        self.items = []
        for ob in objects:
            if max(ob.dimensions) > 0.2:                     # baseplates and backdrops stay
                continue
            m = np.array(ob.matrix_world)
            delay = rng.uniform(0, 0.55)
            off = np.array([rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), rng.uniform(0.06, 0.22)])  # metres, up
            spin = rng.uniform(-3.0, 3.0, 3)
            self.items.append((ob, m, delay, off, spin))

    def __call__(self, f, t, last=False):
        from mathutils import Euler, Matrix
        for ob, m, delay, off, spin in self.items:
            frac = (t - self.t) / max(self.d, 1e-3)
            u = min(max((frac - delay) / 0.45, 0.0), 1.0)
            k = (1 - u) ** 2 if self.mode == "in" else u ** 1.6
            vis = frac >= delay if self.mode == "in" else u < 1.0
            M = Matrix(m.tolist())
            loc = M.to_translation() + __import__("mathutils").Vector(off * k)
            q = M.to_quaternion() @ Euler(tuple(spin * k), "XYZ").to_quaternion()
            ob.rotation_mode = "QUATERNION"
            ob.location, ob.rotation_quaternion = loc, q
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("rotation_quaternion", frame=f)
            ob.hide_render = not vis
            ob.keyframe_insert("hide_render", frame=f)

    def active(self, t):
        return self.t - 0.15 <= t <= self.t + self.d + 0.15


class BrickWord:
    """A word of 1x1 bricks: each brick flies in from a random point and lands staggered over [t, t + d]; with
    `fall` the bricks tumble to the floor from that time on (and stay there)."""

    def __init__(self, text, t, d, at, colours, seed, pixel=20, fall=None, until=None):
        rng = np.random.default_rng(seed)
        self.items = []
        pos = word_pixels(text, at[0], at[1], at[2], pixel)
        s = pixel / 20
        for k, p in enumerate(pos):
            ob = L.part("3005", colours[k % len(colours)], L.T(*p), f"word_{seed}_{k}")
            arrive = t + d * (k / max(len(pos) - 1, 1)) ** 0.8
            start = np.array(p) + np.array([rng.uniform(-500, 500), rng.uniform(-500, -250), rng.uniform(-400, -100)])
            ground = np.array([p[0] + rng.uniform(-60, 60), -12 * s, p[2] + rng.uniform(-120, -20)])
            self.items.append((ob, np.array(p, float), start, arrive, rng.uniform(-540, 540, 3), ground,
                               rng.uniform(0, 0.5), rng.uniform(-200, 200, 3)))
        self.s, self.fall, self.until, self.fly = s, fall, until, 0.7
        self.t0, self.t1 = t - 0.9, t + d + 0.2

    def active(self, t):
        return (self.t0 <= t <= self.t1 or (self.fall is not None and self.fall - 0.1 <= t <= self.fall + 1.2)
                or (self.until is not None and abs(t - self.until) < 0.2))

    def __call__(self, f, t, last=False):
        S = np.diag([self.s, self.s, self.s, 1.0])
        for ob, p, start, arrive, spin, ground, fdel, fspin in self.items:
            if self.until is not None and t >= self.until:
                key(ob, f, L.T(*p) @ S, False)
                continue
            if t < arrive - self.fly:
                key(ob, f, L.T(*start) @ S, False)
                continue
            if self.fall is not None and t >= self.fall + fdel:
                u = min(1.0, (t - self.fall - fdel) / 0.5)
                q = p + (ground - p) * u * u
                key(ob, f, L.T(*q) @ rot(fspin * u) @ S)
                continue
            u = min(1.0, (t - (arrive - self.fly)) / self.fly)
            e = 1 - (1 - u) ** 3
            key(ob, f, L.T(*(start + (p - start) * e)) @ rot(spin * (1 - e)) @ S)


class Confetti:
    """n 1x1 tiles fall and tumble in a box around `centre` (x, z) from t to until (loops every 3.2 s)."""

    def __init__(self, n, t, until, centre, spread, seed):
        rng = np.random.default_rng(seed)
        self.t, self.until = t, until
        self.items = []
        for k in range(n):
            ob = L.part("3070b", PARTY[k % len(PARTY)], L.T(0, -500, 0), f"confetti_{seed}_{k}")
            self.items.append((ob, centre[0] + rng.uniform(-spread[0], spread[0]), centre[1] + rng.uniform(-spread[1], spread[1]),
                               rng.uniform(0, 3.0), rng.uniform(110, 170), rng.uniform(0, 360, 3), rng.choice([-1, 1])))

    def active(self, t):
        return self.t - 0.2 <= t and (self.until is None or t <= self.until + 0.2)

    def __call__(self, f, t, last=False):
        for ob, x, z, ph, v, w, sg in self.items:
            on = t >= self.t + ph * 0.3 and (self.until is None or t < self.until)
            if not on:
                key(ob, f, L.T(x, -500, z), False)
                continue
            dt = (t - self.t - ph * 0.3) % 3.2
            y = -440 + v * dt
            key(ob, f, L.T(x + 25 * math.sin(dt * 3 + ph) * sg, y, z) @ L.RX(w[0] + 300 * dt) @ L.RY(w[1] + 200 * dt * sg), y < -2)


class Tower:
    """A stack of bricks at (x, y_floor, z) that grows by one brick at each time in `times`."""

    def __init__(self, times, at, colours, seed, part="3003"):
        rng = np.random.default_rng(seed)
        self.items = []
        for k, tk in enumerate(times):
            m = L.T(at[0] + rng.uniform(-1.5, 1.5), at[1] - 24 * (k + 1), at[2]) @ L.RY(rng.uniform(-3, 3))
            self.items.append((L.part(part, colours[k % len(colours)], m, f"tower_{seed}_{k}"), m, tk))

    def active(self, t):
        return True

    def __call__(self, f, t, last=False):
        for ob, m, tk in self.items:
            ob.hide_render = t < tk
            ob.keyframe_insert("hide_render", frame=f)


class Steam:
    """Steam puffs (1x1 round plates, stop motion on twos): each puff starts at one of `times`, rises ~80 LDU over
    `life` s, drifts sideways and grows. The source is a figure's head (brickfilm sets `self.src` from the figure's
    head matrix on every pose, `follow` = figure name) or a fixed point `at` (x, y, z)."""

    def __init__(self, times, seed, follow=None, at=None, colour=15, life=0.9, big=()):
        rng = np.random.default_rng(seed)
        self.follow, self.life = follow, life
        self.src = np.array(at if at is not None else (0, -100, 0), float)
        self.items = []
        for k, ta in enumerate(times):
            ob = L.part("6141", colour, L.T(0, -500, 0), f"steam_{seed}_{k}")
            self.items.append((ob, ta, float(rng.uniform(-14, 14)), 0.4 if k in big else 0.0))
        self.t0, self.t1 = (min(times) - 0.1, max(times) + life + 0.1) if times else (0, 0)

    def active(self, t):
        return self.t0 <= t <= self.t1

    def __call__(self, f, t, last=False):
        for ob, ta, dx, extra in self.items:
            u = (t - ta) / self.life
            if not 0.0 <= u < 1.0:
                key(ob, f, L.T(*self.src) @ L.T(0, -40, 0), False)
                continue
            g = 0.9 + 1.3 * u + extra
            p = self.src + np.array([dx * (1 + u), -34 - 80 * u, -12])   # above the head top, a little in front
            key(ob, f, L.T(*p) @ L.RX(90) @ np.diag([g, g, g, 1.0]))


class Strings:
    """Marionette strings: from the nearer hand of the puppeteer to the top of each target head, visible in
    [t, until). brickfilm calls update(f, t, mats_all) on every pose (twos) - the strings follow the figures."""

    def __init__(self, puppeteer, targets, t, until, seed, colour=(0.85, 0.85, 0.8), radius=0.8):
        import bpy
        import bmesh
        self.puppeteer, self.targets, self.t, self.until = puppeteer, list(targets), t, until
        m = bpy.data.materials.new(f"String_{seed}")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*colour, 1)
        b.inputs["Emission Color"].default_value = (colour[0] * 0.7, colour[1] * 0.7, colour[2] * 0.7, 1)
        b.inputs["Emission Strength"].default_value = 2.0                  # thin threads stay readable at night
        self.obs = {}
        for name in self.targets:
            me = bpy.data.meshes.new(f"string_{seed}_{name}")
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=False, segments=6, radius1=1.0, radius2=1.0, depth=1.0)
            bmesh.ops.translate(bm, vec=(0, 0, 0.5), verts=bm.verts)     # unit cylinder from z=0 to z=1
            bm.to_mesh(me)
            bm.free()
            me.materials.append(m)
            ob = bpy.data.objects.new(me.name, me)
            bpy.context.scene.collection.objects.link(ob)
            ob.hide_render = True
            self.obs[name] = ob
        self.r = radius * L.LDU

    def active(self, t):
        return True

    def update(self, f, t, mats_all):
        from mathutils import Vector
        pm = mats_all.get(self.puppeteer)
        for name, ob in self.obs.items():
            tm = mats_all.get(name)
            on = pm is not None and tm is not None and self.t <= t < (self.until if self.until is not None else 1e9)
            if on:
                head = np.asarray(tm["head"], float) @ np.array([0, -4, 0, 1.0])     # head origin = top, + stud
                hands = [np.asarray(pm[h], float)[:3, 3] for h in ("hand_r", "hand_l")]
                hand = min(hands, key=lambda q: abs(q[0] - head[0]))
                a = L.to_blender(L.T(*hand)).to_translation()
                b = L.to_blender(L.T(*head[:3])).to_translation()
                d = Vector(b) - Vector(a)
                ob.rotation_mode = "QUATERNION"
                ob.location = a
                ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized()) if d.length > 1e-9 else                     ob.rotation_quaternion
                ob.scale = (self.r, self.r, max(d.length, 1e-6))
                ob.keyframe_insert("location", frame=f)
                ob.keyframe_insert("rotation_quaternion", frame=f)
                ob.keyframe_insert("scale", frame=f)
            ob.hide_render = not on
            ob.keyframe_insert("hide_render", frame=f)


def figure_fx(events, mats, t, floor, seed_base):
    """Apply fall_apart / assemble events of one figure to its part matrices -> (mats, hidden parts)."""
    hidden = set()
    for ev in events:
        a, d = ev["t"], ev.get("d", 1.2)
        if ev["kind"] == "fall_apart" and (t < a or any(e["kind"] == "assemble" and a < e["t"] <= t for e in events)):
            continue                                             # not yet, or rebuilt by a later "assemble"
        if ev["kind"] == "assemble" and t >= a + d:
            continue
        for i, k in enumerate(sorted(mats)):
            rng = np.random.default_rng(seed_base * 31 + i)
            delay = rng.uniform(0, 0.45) * d
            u = min(max((t - a - delay) / max(d * 0.5, 1e-3), 0.0), 1.0)
            m = np.array(mats[k], float)
            p = m[:3, 3].copy()
            ang = rng.uniform(-120, 120, 3) + np.array([90, 0, 0])
            if ev["kind"] == "fall_apart":                       # drop to the floor, tumble, scatter
                g = np.array([p[0] + rng.uniform(-45, 45), floor - 6, p[2] + rng.uniform(-45, 45)])
                e = u * u
                q = p + (g - p) * e
                R = rot(ang * e)[:3, :3] @ m[:3, :3]
            else:                                                # fly in from above and land in place
                if t < a + delay and not any(e["kind"] == "fall_apart" and e["t"] < a for e in events):
                    hidden.add(k)                                # (after a fall the parts start from the floor)
                g = np.array([p[0] + rng.uniform(-160, 160), p[1] - rng.uniform(220, 380), p[2] + rng.uniform(-160, 60)])
                e = (1 - u) ** 2
                q = p + (g - p) * e
                R = rot(ang * e)[:3, :3] @ m[:3, :3]
            n = np.eye(4)
            n[:3, :3], n[:3, 3] = R, q
            mats[k] = n
    return mats, hidden
