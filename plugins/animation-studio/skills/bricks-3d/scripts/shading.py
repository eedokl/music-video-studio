"""Blender helpers for brick films: printed faces and torsos as shader decals, glowing parts, image planes, lights,
easing, key-pose timelines and stop-motion keys. Sizes in LDraw units (LDU) unless noted.

Decals instead of textures on the mesh: LDraw parts have no UVs. The face is projected cylindrically onto the head
(+-75 degrees around the front), torso prints planar onto the torso front. Mouth and eyes are atlases (one tile per
shape) switched by a Value node - keyframe `value.default_value` to change the mouth on every frame.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

import ldraw as L

LDU = L.LDU


def bl(x, y, z):
    """LDraw point -> Blender point (m)."""
    return Vector((x * LDU, z * LDU, -y * LDU))


def math_node(nt, op, a, b=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            nt.links.new(x, n.inputs[i])
    return n.outputs[0]


def mix_rgb(nt, fac, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    nt.links.new(fac, n.inputs[0])
    for sock, idx in ((a, 6), (b, 7)):
        if isinstance(sock, tuple):
            n.inputs[idx].default_value = sock
        else:
            nt.links.new(sock, n.inputs[idx])
    return n.outputs[2]


def atlas_tex(nt, image, u, v, tiles, idx_sock):
    """Tile idx of a horizontal atlas at (u, v) in 0..1 -> (colour, alpha masked to the tile)."""
    uu = math_node(nt, "DIVIDE", math_node(nt, "ADD", u, idx_sock), tiles)
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(uu, comb.inputs[0])
    nt.links.new(v, comb.inputs[1])
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(str(image), check_existing=True)
    t.extension = "CLIP"
    nt.links.new(comb.outputs[0], t.inputs["Vector"])
    mask = math_node(nt, "MULTIPLY",
                     math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", u, 0.0), math_node(nt, "LESS_THAN", u, 1.0)),
                     math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", v, 0.0), math_node(nt, "LESS_THAN", v, 1.0)))
    return t.outputs["Color"], math_node(nt, "MULTIPLY", t.outputs["Alpha"], mask)


def base_material(name, code):
    m = L.material(code).copy()
    m.name = name
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    return m, nt, bsdf, tuple(bsdf.inputs["Base Color"].default_value)


def face(ob, code, eyes_png, mouths_png, name, ground=None, mouth_tiles=9):
    """Face cylindrically on the head. -> (blink Value socket, mouth Value socket)"""
    v = np.array([ob.data.vertices[i].co[:] for i in range(len(ob.data.vertices))])
    r = np.hypot(v[:, 0], v[:, 1])
    band = v[r > r.max() * 0.97]
    z0, z1 = band[:, 2].min(), band[:, 2].max()
    m, nt, bsdf, g0 = base_material(name, code)
    ground = ground or g0
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    angle = math_node(nt, "ARCTAN2", sep.outputs[0], math_node(nt, "MULTIPLY", sep.outputs[1], -1.0))
    u = math_node(nt, "ADD", math_node(nt, "DIVIDE", angle, 2 * math.radians(75)), 0.5)
    vv = math_node(nt, "DIVIDE", math_node(nt, "SUBTRACT", sep.outputs[2], float(z0)), float(z1 - z0))
    blink = nt.nodes.new("ShaderNodeValue")
    mouth = nt.nodes.new("ShaderNodeValue")
    ec, ea = atlas_tex(nt, eyes_png, u, vv, 2, blink.outputs[0])
    mc, ma = atlas_tex(nt, mouths_png, u, vv, mouth_tiles, mouth.outputs[0])
    c = mix_rgb(nt, ea, ground, ec)
    c = mix_rgb(nt, ma, c, mc)
    nt.links.new(c, bsdf.inputs["Base Color"])
    ob.material_slots[0].link = "OBJECT"
    ob.material_slots[0].material = m
    return blink.outputs[0], mouth.outputs[0]


def front_print(ob, code, png, name, width=44, height=32):
    """Image planar on the torso front (origin = top edge, width x height in LDU)."""
    m, nt, bsdf, ground = base_material(name, code)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    nsep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Normal"], nsep.inputs[0])
    u = math_node(nt, "ADD", math_node(nt, "DIVIDE", sep.outputs[0], width * LDU), 0.5)
    v = math_node(nt, "ADD", math_node(nt, "DIVIDE", sep.outputs[2], height * LDU), 1.0)
    zero = nt.nodes.new("ShaderNodeValue").outputs[0]
    col, alpha = atlas_tex(nt, png, u, v, 1, zero)
    front = math_node(nt, "LESS_THAN", nsep.outputs[1], -0.3)
    c = mix_rgb(nt, math_node(nt, "MULTIPLY", alpha, front), ground, col)
    nt.links.new(c, bsdf.inputs["Base Color"])
    for s in ob.material_slots:
        if s.material and s.material.name.startswith(f"LD_{code}_"):
            s.link = "OBJECT"
            s.material = m


def flat_material(obs, name, colour, roughness=0.85, specular=0.05):
    """One matte colour over whole objects (silhouette figures)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = colour
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Specular IOR Level"].default_value = specular
    for ob in obs:
        for s in ob.material_slots:
            s.link = "OBJECT"
            s.material = m
    return m


def hair_accent(ob, streak=None, clip_png=None, base=(0.008, 0.008, 0.01, 1)):
    """Recolour a hair piece: base colour, optional ONE coloured streak on the figure's right side (-x, screen left)
    and an image clip (e.g. a star) on its left side (+x, screen right). Sizes from the mesh."""
    v = np.array([ob.data.vertices[i].co[:] for i in range(len(ob.data.vertices))])
    x0, y0, z0 = v.min(0)
    x1, y1, z1 = v.max(0)
    w, d, h = x1 - x0, y1 - y0, z1 - z0
    m = bpy.data.materials.new(f"{ob.name}_hair")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.3
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    nsep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Normal"], nsep.inputs[0])
    x, y, z = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    c = base
    if streak:
        band = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", x, float(x0 + 0.20 * w)),
                         math_node(nt, "LESS_THAN", x, float(x0 + 0.33 * w)))
        not_back = math_node(nt, "LESS_THAN", nsep.outputs[1], 0.35)
        c = mix_rgb(nt, math_node(nt, "MULTIPLY", band, not_back), base, tuple(streak))
    else:
        c = mix_rgb(nt, math_node(nt, "MULTIPLY", x, 0.0), base, base)
    if clip_png:
        s_ = 0.30 * h
        u = math_node(nt, "ADD", math_node(nt, "DIVIDE", math_node(nt, "SUBTRACT", y, float(y0 + 0.35 * d)), float(s_)), 0.5)
        vv = math_node(nt, "ADD", math_node(nt, "DIVIDE", math_node(nt, "SUBTRACT", z, float(z0 + 0.55 * h)), float(s_)), 0.5)
        uu = math_node(nt, "SUBTRACT", 1.0, u)
        zero = nt.nodes.new("ShaderNodeValue").outputs[0]
        sc_, sa = atlas_tex(nt, clip_png, uu, vv, 1, zero)
        side = math_node(nt, "GREATER_THAN", nsep.outputs[0], 0.4)
        c = mix_rgb(nt, math_node(nt, "MULTIPLY", sa, side), c, sc_)
    nt.links.new(c, bsdf.inputs["Base Color"])
    for s in ob.material_slots:
        s.link = "OBJECT"
        s.material = m


def glow_material(name, colour, strength):
    """Emission (LEDs, a glowing graphics card, bulbs) -> (material, strength socket to keyframe)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*colour, 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m, em.inputs["Strength"]


def set_material(ob, m):
    for s in ob.material_slots:
        s.link = "OBJECT"
        s.material = m


def image_material(name, path, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(str(path), check_existing=True)
    nt.links.new(t.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def plane(name, centre_ld, M, width, height, mat):
    """Rectangle (LDU) in the local x/y plane of LDraw matrix M, normal towards -z (front), with UVs."""
    sc = bpy.context.scene
    w, h = width / 2, height / 2
    cx, cy, cz = centre_ld
    pts = [(cx - w, cy + h, cz), (cx + w, cy + h, cz), (cx + w, cy - h, cz), (cx - w, cy - h, cz)]
    me = bpy.data.meshes.new(name)
    Mb = L.S @ Matrix(np.asarray(M).tolist())
    me.from_pydata([tuple(Mb @ Vector(p)) for p in pts], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = c
    me.update()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


def light(name, kind, where, aim, colour, watts, size=0.05):
    """Area/point/spot light at Blender point `where` aimed at `aim` (Blender point or None)."""
    sc = bpy.context.scene
    ld = bpy.data.lights.new(name, kind)
    ld.color = colour
    ld.energy = watts
    if kind == "AREA":
        ld.size = size
    if kind in ("POINT", "SPOT"):
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(ob)
    ob.location = where
    if aim is not None:
        e = bpy.data.objects.new(name + "_aim", None)
        sc.collection.objects.link(e)
        e.location = aim
        ob.constraints.new("TRACK_TO").target = e
    return ob


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


STEP = {"show"}      # switched, not eased: a hidden cameo must not fade in over half a section


class Timeline:
    """Key poses [(song time, changes)] -> smoothly eased pose (dict) at any time; changes accumulate."""

    def __init__(self, neutral, keys):
        state, self.k = dict(neutral), []
        for t, d in sorted(keys, key=lambda x: x[0]):
            state.update(d)
            if self.k and abs(self.k[-1][0] - t) < 1e-9:  # same time: the later key wins (no 1-frame flash)
                self.k[-1] = (t, dict(state))
            else:
                self.k.append((t, dict(state)))
        if not self.k:
            self.k = [(0.0, dict(neutral))]

    def __call__(self, t):
        if t <= self.k[0][0]:
            return dict(self.k[0][1])
        for (ta, a), (tb, b) in zip(self.k, self.k[1:]):
            if ta <= t <= tb:
                e = ease((t - ta) / max(tb - ta, 1e-6))
                return {x: (b[x] if t >= tb else a[x]) if x in STEP else a[x] + (b[x] - a[x]) * e for x in a}
        return dict(self.k[-1][1])


def make_constant():
    """All keyframes CONSTANT (stop motion), incl. Blender 5 layered actions."""
    sources = [o.animation_data for o in bpy.data.objects] + [l.animation_data for l in bpy.data.lights] + \
        [c.animation_data for c in bpy.data.cameras] + [s.animation_data for s in bpy.data.scenes] + \
        [m.node_tree.animation_data for m in bpy.data.materials if m.node_tree] + \
        [w.node_tree.animation_data for w in bpy.data.worlds if w.node_tree]
    for d in sources:
        if not (d and d.action):
            continue
        fcs = list(getattr(d.action, "fcurves", []) or [])
        for layer in getattr(d.action, "layers", []):
            for strip in layer.strips:
                for cb in strip.channelbags:
                    fcs += list(cb.fcurves)
        for fc in fcs:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
