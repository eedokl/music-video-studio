# Runs inside Blender's Python (bpy) - imported by stage_actor.cast(), never run with uv.
"""Six other makes of the same figures, applied after they are built (project.json "figures", or cast(style=...)):

  "ragdoll"   sewn rag dolls: woven linen, knit garments, plush tails, seams with hand stitches, coat-button eyes,
              a lumpy stuffing
  "puppet"    hand puppets for a puppet show: coloured fleece with a nap of fine hair, ping-pong eyes with felt
              pupils, a hinged flap mouth with a felt tongue, arm rods, no legs (they play behind a playboard)
  "stopmotion" gothic stop-motion puppets, the hand-made armature kind: a big head on a narrow body, wire-thin limbs,
              huge round porcelain eyes with pin pupils in dark sockets, pale sculpted clay skin with thumb marks,
              black-and-bone striped costumes, a sewn mouth and a stitched skull, no brows
  "clay"      plasticine figures: one colour per figure, thumb marks and finger prints, clay-ball eyes, clay brows
  "paper"     papercraft: every part folded from few flat faces, printed dashed fold lines, glue tabs, flat paper
              eyes and brows
  "marionette" carved and lacquered wood: ball joints, a jaw slot, painted cheeks, strings from head and hands to a
              control cross above each figure (the hand strings hang a little loose)

The rig is not touched: joints, channels and the whole acting API keep working. The flap mouth of a puppet hangs on
the figure's mouth channel, so say(), babble() and moods open it. What cannot work: a button or ping-pong eye does
not blink or widen (moods still move the brows).

A figure is recognised by the names its parts carry (`<name>_head`, `_torso`, `_muzzle` / `_snout`, `_cheek…`,
`_arm…`, `_leg…`, `_eye…`, `_tail…`) and by the role names of its materials (`fur…`, `fur_tail…`, `shirt`, `knit…` /
`accent…`, `vest_…`) - what `Toy` and the helpers of `Char` produce. An own figure can steer the puppet make with a
class attribute, a bundled one with the same keys in its cast entry:

    class Olga(Char):
        puppet = {"fleece": "#DA5F26", "parts": "muzzle", "lid": 0.4}
    K.cast(S, {"mo": {"look": "bear", "fleece": "#EBA52C"}})

keys: fleece / fleece2 / belly (colours: body, tail and ear fur, belly patch), cut (height of the mouth cut in head
space), hinge (y of the jaw hinge), parts (regex of the head parts that are cut, e.g. "muzzle" for a long snout),
open (degrees of the open mouth), eye (radius), flat (1 = ball, 0.3 = disc behind glasses), lift, push, cross, pupil,
lid (0..1 heavy eyelids), brow (colour), fuzz (False = no hair strands: much faster), rods (False = none).
"""
import math
import random
import re

import bmesh
import bpy
from mathutils import Matrix
from mathutils import Vector as V

import stage_core as C
from stage_core import srgb

TAU = math.tau
STYLES = ("toy", "ragdoll", "puppet", "stopmotion", "clay", "paper", "marionette")
FLEECE = ("#EBA52C", "#DA5F26", "#A3BC66", "#8566B8", "#3F9BB0", "#E07A9A")     # given out in cast order
PUPPET = {}                 # {figure name: options} - a project can steer a figure it cannot edit


# ====================================================================== shader helpers
def _math(nt, op, *args):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, v in enumerate(args):
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _rgba(c):
    return srgb(c) if isinstance(c, str) else tuple(c)


def _shade(c, k):
    """a colour made darker (k < 1) or mixed towards white (k > 1); linear RGBA"""
    r, g, b, a = _rgba(c)
    if k <= 1:
        return (r * k, g * k, b * k, a)
    t = k - 1
    return (r + (1 - r) * t, g + (1 - g) * t, b + (1 - b) * t, a)


def _color_of(m, default="#F3EFE6"):
    b = m.node_tree.nodes.get("Principled BSDF") if m.node_tree else None
    if b is not None and not b.inputs["Base Color"].links:
        return tuple(b.inputs["Base Color"].default_value)
    return tuple(m.diffuse_color) if m.diffuse_color else srgb(default)


def _base(m):
    nt = m.node_tree
    nt.nodes.clear()
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(b.outputs[0], o.inputs["Surface"])
    return nt, b


def _noise(nt, vec, scale, detail=3.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    nt.links.new(vec, n.inputs["Vector"])
    return n.outputs["Fac"]


def _bump(nt, b, height, strength, dist=0.002):
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = dist
    nt.links.new(height, bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])


def _mix(nt, fac, a, bcol):
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    for key, v in (("A", a), ("B", bcol)):
        if isinstance(v, (str, tuple, list)):
            mx.inputs[key].default_value = _rgba(v)
        else:
            nt.links.new(v, mx.inputs[key])
    if isinstance(fac, (int, float)):
        mx.inputs["Factor"].default_value = fac
    else:
        nt.links.new(fac, mx.inputs["Factor"])
    return mx.outputs["Result"]


def _weave(nt, pitch):
    """plain weave: thread ridges along the two axes that lie in the surface (object space) -> height 0..1"""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sn = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Normal"], sn.inputs[0])
    h = None
    for ax in "XYZ":
        w = nt.nodes.new("ShaderNodeTexWave")
        w.wave_type, w.bands_direction, w.wave_profile = "BANDS", ax, "SIN"
        w.inputs["Scale"].default_value = 0.314159 / pitch          # one band per `pitch` metres
        w.inputs["Distortion"].default_value = 0.5
        w.inputs["Detail"].default_value = 1.0
        w.inputs["Detail Scale"].default_value = 3.0
        nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
        wgt = _math(nt, "SUBTRACT", 1.0, _math(nt, "MULTIPLY", sn.outputs[ax], sn.outputs[ax]))
        hh = _math(nt, "MULTIPLY", w.outputs["Fac"], wgt)
        h = hh if h is None else _math(nt, "MAXIMUM", h, hh)
    return tc, h


def linen(m, color, dark=None, pitch=0.0042, bump=0.7, check=None):
    """coarse woven cloth; check=(colour, size) prints a gingham check on it"""
    dark = dark or _shade(color, 0.72)
    nt, b = _base(m)
    tc, h = _weave(nt, pitch)
    mott = _noise(nt, tc.outputs["Object"], 14.0, 4.0)
    col = _mix(nt, h, dark, color)
    if check:
        sx = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sx.inputs[0])
        k = TAU / check[1]
        bx = _math(nt, "GREATER_THAN", _math(nt, "SINE", _math(nt, "MULTIPLY", sx.outputs["X"], k)), 0.0)
        bz = _math(nt, "GREATER_THAN", _math(nt, "SINE", _math(nt, "MULTIPLY", sx.outputs["Z"], k)), 0.0)
        col = _mix(nt, _math(nt, "MULTIPLY", _math(nt, "ADD", bx, bz), 0.42), col, check[0])
    col = _mix(nt, _math(nt, "MULTIPLY", mott, 0.22), col, dark)
    nt.links.new(col, b.inputs["Base Color"])
    C._set(b, **{"Roughness": 0.95, "Sheen Weight": 0.5, "Sheen Roughness": 0.4, "Specular IOR Level": 0.15,
                 "Subsurface Weight": 0.04, "Subsurface Scale": 0.03})
    fib = _noise(nt, tc.outputs["Object"], 1400.0, 2.0)
    _bump(nt, b, _math(nt, "ADD", h, _math(nt, "MULTIPLY", fib, 0.35)), bump)
    m.diffuse_color = _rgba(color)
    return m


def _knit_height(nt, tc, col=0.0085, row=0.0062, radius=0.17):
    """rows of V stitches running around the local Z axis -> height 0..1"""
    sx = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sx.inputs[0])
    u = _math(nt, "MULTIPLY", _math(nt, "ARCTAN2", sx.outputs["X"], sx.outputs["Y"]), radius)
    tri = _math(nt, "PINGPONG", u, col / 2)                         # 0 .. col/2
    t = _math(nt, "DIVIDE", tri, col / 2)
    v = _math(nt, "ADD", sx.outputs["Z"], _math(nt, "MULTIPLY", tri, 1.1))
    rows = _math(nt, "ADD", 0.5, _math(nt, "MULTIPLY", 0.5, _math(nt, "SINE", _math(nt, "MULTIPLY", v, TAU / row))))
    wale = _math(nt, "SINE", _math(nt, "MULTIPLY", t, math.pi))      # 0 at the column borders
    return _math(nt, "MULTIPLY", rows, _math(nt, "ADD", 0.25, _math(nt, "MULTIPLY", wale, 0.75)))


def knit(m, color, dark=None, bump=1.0):
    dark = dark or _shade(color, 0.5)
    nt, b = _base(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    h = _knit_height(nt, tc)
    nt.links.new(_mix(nt, h, dark, color), b.inputs["Base Color"])
    C._set(b, **{"Roughness": 0.92, "Sheen Weight": 0.7, "Sheen Roughness": 0.4, "Specular IOR Level": 0.15})
    _bump(nt, b, h, bump, 0.004)
    m.diffuse_color = _rgba(color)
    return m


def knit_over(m, bump=1.0):
    """keep the colours of a material (a vest with its shirt V-neck) and knit its surface"""
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    tc = next((n for n in nt.nodes if n.type == "TEX_COORD"), None)
    bp = next((n for n in nt.nodes if n.type == "BUMP"), None)
    if b is None or tc is None or bp is None:
        return m
    for ln in list(bp.inputs["Height"].links):
        nt.links.remove(ln)
    nt.links.new(_knit_height(nt, tc), bp.inputs["Height"])
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.004
    C._set(b, **{"Sheen Weight": 0.7, "Roughness": 0.92})
    return m


def plush(m, color, dark=None, scale=170.0, bump=1.0):
    """teddy boucle: little curls"""
    dark = dark or _shade(color, 0.7)
    nt, b = _base(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.inputs["Scale"].default_value = scale
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    h = _math(nt, "SUBTRACT", 1.0, _math(nt, "MULTIPLY", vo.outputs["Distance"], 1.6))
    nt.links.new(_mix(nt, h, dark, color), b.inputs["Base Color"])
    C._set(b, **{"Roughness": 1.0, "Sheen Weight": 1.0, "Sheen Roughness": 0.5, "Specular IOR Level": 0.1})
    _bump(nt, b, _math(nt, "ADD", h, _math(nt, "MULTIPLY", _noise(nt, tc.outputs["Object"], 900.0), 0.4)), bump, 0.004)
    m.diffuse_color = _rgba(color)
    return m


def quilt(m, color, dark=None, scale=13.0):
    """padded patchwork: puffy cells with sewn grooves and fine cord ribs (a shell, a cushion, a saddle)"""
    dark = dark or _shade(color, 0.55)
    nt, b = _base(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.feature = "DISTANCE_TO_EDGE"
    vo.inputs["Scale"].default_value = scale
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    puff = _math(nt, "MINIMUM", _math(nt, "MULTIPLY", vo.outputs["Distance"], 9.0), 1.0)
    w = nt.nodes.new("ShaderNodeTexWave")
    w.bands_direction = "DIAGONAL"
    w.inputs["Scale"].default_value = 0.314159 / 0.004
    nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
    nt.links.new(_mix(nt, _math(nt, "POWER", puff, 0.35), dark, _mix(nt, w.outputs["Fac"], dark, color)),
                 b.inputs["Base Color"])
    C._set(b, **{"Roughness": 0.9, "Sheen Weight": 0.6, "Sheen Roughness": 0.4, "Specular IOR Level": 0.15})
    _bump(nt, b, _math(nt, "ADD", _math(nt, "MULTIPLY", _math(nt, "POWER", puff, 0.5), 4.0),
                       _math(nt, "MULTIPLY", w.outputs["Fac"], 0.25)), 1.0, 0.004)
    m.diffuse_color = _rgba(color)
    return m


def soften(m, color=None, rough=0.95, sheen=0.5):
    """a glossy material becomes felt / yarn"""
    b = m.node_tree.nodes.get("Principled BSDF") if m.node_tree else None
    if b is None:
        return m
    if color:
        C._set(b, **{"Base Color": _rgba(color)})
    C._set(b, **{"Roughness": rough, "Coat Weight": 0.0, "Sheen Weight": sheen, "Sheen Roughness": 0.4,
                 "Specular IOR Level": 0.15, "Metallic": 0.0, "Emission Strength": 0.0})
    return m


def fleece(name, color, tint=None, fuzzy=1.2, scale=340.0, bump=0.3):
    m = C.felt(name, "#FFFFFF", fuzz=fuzzy, scale=scale, bump=bump, sss=0.05)
    b = m.node_tree.nodes.get("Principled BSDF")
    C._set(b, **{"Base Color": _rgba(color)})
    if "Sheen Tint" in b.inputs:
        b.inputs["Sheen Tint"].default_value = _rgba(tint or _shade(color, 1.6))
    m.diffuse_color = _rgba(color)
    return m


# ====================================================================== mesh helpers
def objs(name):
    """every object of a figure (its parts are named <name>_...)"""
    return [o for o in bpy.data.objects if o.name.startswith(name + "_")]


def _suffix(o, name):
    return re.sub(r"\.\d+$", "", o.name[len(name) + 1:])


def blank(o):
    """make an object and its children render nothing (the rig keeps its node)"""
    for q in [o] + list(o.children_recursive):
        if q.type == "MESH":
            q.data = bpy.data.meshes.new(q.name + "_none")
        elif q.type == "CURVE":
            q.data.bevel_depth = 0.0
            q.data.extrude = 0.0


def _bbox(o, axis):
    v = [p.co[axis] for p in o.data.vertices]
    return (min(v), max(v)) if v else (0.0, 0.0)


def _cut(bm, co, no, keep=0):
    """bisect; keep: 0 both sides, 1 the side the normal points to, -1 the other. Returns the cut edges."""
    r = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-7, plane_co=co, plane_no=no,
                               clear_inner=keep > 0, clear_outer=keep < 0)
    return [e for e in r["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]


def _chains(edges):
    """ordered vertex chains of a set of edges: [(verts, closed)]"""
    adj = {}
    for e in edges:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, out = set(), []
    for start in sorted(adj, key=lambda v: len(adj[v])):          # open ends first
        if start in seen:
            continue
        chain, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [v for v in adj[cur] if v is not prev and v not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            chain.append(cur)
            seen.add(cur)
        out.append((chain, len(chain) > 2 and chain[0] in adj[chain[-1]]))
    return out


def _stick(bm, a, b, r, seg=6):
    d = b - a
    if d.length < 1e-6:
        return
    m = Matrix.Translation((a + b) / 2) @ V((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=d.length, matrix=m)


def seam(o, co, no, pitch=0.011, length=0.009, r=0.0011, mat="thread", rng=None, groove="seam_line", keep=None):
    """a sewn seam where the plane (object space) cuts the mesh: a thin line with hand stitches across it.
    Keep the plane a little off the mesh's own edge loops (a slightly tilted normal), or the cut finds nothing.
    keep(point) -> bool limits the seam to a part of the cut (e.g. only the front: a sewn mouth)."""
    rng = rng or random.Random(len(o.name))
    src = bmesh.new()
    src.from_mesh(o.data)
    src.normal_update()
    edges = _cut(src, V(co), V(no).normalized())
    st, ln = bmesh.new(), bmesh.new()
    for chain, closed in _chains(edges):
        pts = [(v.co.copy(), v.normal.copy()) for v in chain]
        if closed:
            pts.append(pts[0])
        acc, nxt = 0.0, pitch * 0.5
        for (p0, n0), (p1, n1) in zip(pts, pts[1:]):
            d = p1 - p0
            L = d.length
            if L < 1e-7 or (keep and not (keep(p0) and keep(p1))):
                continue
            _stick(ln, p0 + n0 * 0.0004, p1 + n1 * 0.0004, r * 0.75, 5)
            while nxt <= acc + L:
                t = (nxt - acc) / L
                p, n = p0.lerp(p1, t), n0.lerp(n1, t).normalized()
                across = d.normalized().cross(n).normalized()
                skew = d.normalized() * rng.uniform(0.15, 0.5)            # hand-sewn: slanted, never quite even
                a = (across + skew).normalized() * length * rng.uniform(0.42, 0.58)
                _stick(st, p - a + n * r * 0.6, p + a + n * r * 0.6, r)
                nxt += pitch * rng.uniform(0.85, 1.15)
            acc += L
    src.free()
    for bm, mm, tag in ((st, mat, "_stitch"), (ln, groove, "_seam")):
        for f in bm.faces:
            f.smooth = True
        me = bpy.data.meshes.new(o.name + tag)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(C.mat(mm))
        q = bpy.data.objects.new(o.name + tag, me)
        bpy.context.scene.collection.objects.link(q)
        q.parent = o
    return o


def lumpy(o, amt=0.006, size=0.11):
    """hand-stuffed: gentle bumps and hollows"""
    tx = bpy.data.textures.new(o.name + "_lump", "CLOUDS")
    tx.noise_scale = size
    tx.noise_depth = 1
    md = o.modifiers.new("lump", "DISPLACE")
    md.texture = tx
    md.texture_coords = "LOCAL"
    md.strength = amt
    md.mid_level = 0.5
    return o


def _garments():
    """knit every garment material that exists (role names knit… / accent… / vest_…) - both makes wear wool"""
    for k, m in list(C._MATS.items()):
        if m.get("stage_look"):
            continue
        if k.startswith("vest_"):
            knit_over(m)
        elif k.startswith(("knit", "accent")) and m.node_tree and m.node_tree.nodes.get("Principled BSDF"):
            knit(m, _color_of(m))
        else:
            continue
        m["stage_look"] = 1


# ====================================================================== rag dolls
def _ragdoll_materials():
    M = C._MATS
    for k, m in list(M.items()):
        if m.get("stage_look"):
            continue
        if k.startswith("fur_tail"):
            plush(m, _shade(_color_of(m), 0.93))
        elif k.startswith("fur"):
            linen(m, _shade(_color_of(m), 0.97))
        elif k == "shirt":
            acc = next((_color_of(M[a]) for a in M if a.startswith(("knit", "accent")) and not a.endswith("_d")
                        and "_d_" not in a), srgb("#3E9A6E"))
            linen(m, "#F4EEE0", "#D9CFBA", pitch=0.003, check=(_shade(acc, 1.25), 0.022))
        elif k == "shell":
            quilt(m, _color_of(m))
        elif k in ("shell_rim", "shell_plate"):
            linen(m, _color_of(m), pitch=0.0032, bump=0.9)
        else:
            continue
        m["stage_look"] = 1
    _garments()
    for k, c, kw in (("nose", "#1A1B1F", {}), ("brow", "#2A211B", {"sheen": 0.8}), ("mouth_in", "#5A1522", {}),
                     ("tongue", "#E07F8B", {}), ("tooth", "#F4EFE2", {}), ("beak", "#E0A242", {}),
                     ("gold", "#D9A93F", {"rough": 0.6, "sheen": 0.2})):
        if k in M:
            soften(M[k], c, **kw)
    C.mat("thread", "#5B3A22", rough=0.8, sheen=0.5)
    C.mat("thread_l", "#F1E7D0", rough=0.8, sheen=0.5)
    C.mat("seam_line", "#A8997C", rough=1.0)
    C.mat("button", "#141518", rough=0.16, coat=0.8)
    C.mat("button_rim", "#2A2C31", rough=0.3, coat=0.5)


def button_eye(name, side, eye, head_centre):
    """a four-hole coat button sewn on with a thread cross, in place of the glossy eye"""
    head = eye.parent
    loc = eye.location.copy()
    r = max(_bbox(eye, 0)[1], _bbox(eye, 2)[1]) * 1.12
    out = (loc - head_centre).normalized() if head_centre is not None else V((0, -1, 0))
    out = (out + V((0, -1.2, 0))).normalized()                      # mostly forward, a little along the skull
    blank(eye)
    g = C.empty(f"{name}_button{side}", loc + out * 0.004, head)
    g.rotation_euler = V((0, 0, 1)).rotation_difference(out).to_euler()
    C.cyl(f"{name}_btn{side}", r, r * 0.22, (0, 0, 0), "button", g, seg=40, bevel=r * 0.07)
    C.torus(f"{name}_btnrim{side}", r * 0.86, r * 0.13, (0, 0, r * 0.1), "button_rim", g, seg=40, rseg=10)
    h = r * 0.27
    for i, (hx, hy) in enumerate(((h, h), (-h, h), (h, -h), (-h, -h))):
        C.cyl(f"{name}_btnhole{side}{i}", r * 0.1, r * 0.05, (hx, hy, r * 0.115), "thread_l", g, seg=10, bevel=0)
    for i, sg in enumerate((1, -1)):
        C.capsule(f"{name}_btnthr{side}{i}", (-h, -h * sg, r * 0.135), (h, h * sg, r * 0.135), r * 0.055, r * 0.055,
                  "thread_l", g, seg=8)
    return g


def ragdoll(S, cast, seed=3):
    """turn built figures into rag dolls. cast: {name: figure} (only the names are used)"""
    _ragdoll_materials()
    rng = random.Random(seed)
    for name in cast:
        centre = next((o.location.copy() for o in objs(name) if _suffix(o, name) == "head" and o.type == "MESH"), None)
        for o in objs(name):
            if o.type != "MESH" or not o.data.polygons:
                continue
            s = _suffix(o, name)
            vest = any(m is not None and m.name.startswith("vest_") for m in o.data.materials)
            if re.fullmatch(r"eye[LR]", s):
                button_eye(name, s[-1], o, centre)
            elif s in ("head", "torso"):
                seam(o, (0, 0.012, 0), (0.03, 1, 0.04), rng=rng)                   # over the top, side to side
                if s == "torso":
                    lumpy(o, 0.006)
                    seam(o, (0.004, 0, 0), (1, 0.02, 0.0), rng=rng, mat="thread_l" if vest else "thread")
            elif s in ("muzzle", "snout"):
                seam(o, (0.002, 0, 0), (1, 0.03, 0.02), rng=rng)
            elif re.fullmatch(r"(arm|fore|leg|shin)[LR]_m", s):
                seam(o, (0, 0, 0), (0.72, -0.69, 0.02), rng=rng, pitch=0.012)
                lumpy(o, 0.004, 0.07)
            elif re.fullmatch(r"(arm[LR]_h|foot[LR])", s):
                lo, hi = _bbox(o, 2)
                seam(o, (0, 0, lo + (hi - lo) * 0.3), (0.02, 0.03, 1), rng=rng, pitch=0.012)
            elif re.fullmatch(r"(ear[LR]|t\d|tail\d?|chest|belly)", s):
                lumpy(o, 0.005, 0.08)
                if s in ("chest", "belly"):
                    lo, hi = _bbox(o, 1)
                    seam(o, (0, lo + (hi - lo) * 0.42, 0), (0.02, 1, 0.03), rng=rng, pitch=0.012)
            elif re.fullmatch(r"plate\d+", s):
                lo, hi = _bbox(o, 2)
                seam(o, (0, 0, hi - (hi - lo) * 0.3), (0.01, 0.02, 1), rng=rng, pitch=0.014, length=0.01,
                     mat="thread_l", groove="thread_l")


# ====================================================================== hand puppets
def fuzz(o, length=0.006, per_m2=350000, child=18, slot=1, rough=0.02, seed=1, rad=0.00028, clump=0.0):
    """fleece nap / fur as hair strands on a mesh. Leave the strand direction settings (normal_factor, factor_random)
    alone: touching them makes Blender ignore hair_length (measured in 5.2: 6.5 mm became 80 mm)."""
    area = sum(p.area for p in o.data.polygons)
    sc = o.matrix_basis.to_scale()
    area *= (abs(sc.x * sc.y * sc.z)) ** (2 / 3)
    o.modifiers.new("fuzz", "PARTICLE_SYSTEM")
    ps = o.particle_systems[-1]
    ps.seed = seed
    st = ps.settings
    st.type = "HAIR"
    st.count = max(40, int(area * per_m2 / child))
    st.hair_length = length
    st.emit_from = "FACE"
    st.use_emit_random = True
    st.child_type = "INTERPOLATED"
    st.rendered_child_count = child
    st.child_radius = 0.01
    st.roughness_1, st.roughness_1_size = length * rough * 4, 0.4          # roughness is in metres, not relative
    st.roughness_2 = length * rough * 8
    st.roughness_endpoint = length * rough * 10
    st.clump_factor = clump
    st.material = slot
    st.hair_step = 3
    st.render_step = 3
    for k, v in (("root_radius", rad), ("tip_radius", rad * 0.25), ("radius_scale", 1.0), ("use_close_tip", True)):
        try:
            setattr(st, k, v)
        except (AttributeError, TypeError):
            pass
    return st


def _half(o, co, no, keep, cap_mat):
    """the part of o's mesh on one side of a plane, and the cut face as its own mesh (so no hair grows on it)"""
    out = []
    for cap in (False, True):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        edges = _cut(bm, co, no, keep)
        for e in edges:
            e.smooth = False
        if cap:
            skin = bm.faces[:]
            bmesh.ops.edgeloop_fill(bm, edges=edges, mat_nr=0, use_smooth=False)
            bmesh.ops.delete(bm, geom=skin, context="FACES")
        me = bpy.data.meshes.new(o.name + ("_cap" if cap else "_half"))
        bm.to_mesh(me)
        bm.free()
        for m in ([C.mat(cap_mat)] if cap else o.data.materials):
            me.materials.append(m)
        out.append(me)
    return out


def flap_mouth(S, c, zcut, hinge_y, parts=r"(head|snout|muzzle|cheek.*)", tongue=None, throat=True):
    """cut the head (and what sits on it) at height zcut (head space) into skull and jaw; the jaw hangs on a hinge
    at y = hinge_y. Returns the jaw Node: jaw.rot(f, x=25) opens the mouth."""
    n, head = c.name, c.head.obj
    hinge = V((0, hinge_y, zcut))
    jaw = C.Node(S, C.empty(n + "_flapjaw", hinge, head))
    front, width = 0.0, 0.0
    for o in list(head.children):
        if o.type != "MESH" or not o.data.polygons or not re.fullmatch(parts, _suffix(o, n)):
            continue
        M = o.matrix_basis.copy()
        co = M.inverted() @ V((0, 0, zcut))
        no = (M.to_3x3().transposed() @ V((0, 0, 1))).normalized()
        pts = [M @ v.co for v in o.data.vertices]
        zs = [p.z for p in pts]
        near = [p for p in pts if abs(p.z - zcut) < 0.02]
        if near:
            front = min(front, min(p.y for p in near))
            width = max(width, max(abs(p.x) for p in near))
        if min(zs) >= zcut:
            continue
        low, low_cap = _half(o, co, no, -1, "mouth_felt")
        for me in (low, low_cap):
            q = bpy.data.objects.new(o.name + ("_jaw" if me is low else "_jawcap"), me)
            bpy.context.scene.collection.objects.link(q)
            q.parent = jaw.obj
            q.matrix_parent_inverse = Matrix.Translation(-hinge)
            q.location, q.rotation_euler, q.scale = o.location, o.rotation_euler, o.scale
        if max(zs) > zcut:
            up, up_cap = _half(o, co, no, 1, "mouth_felt")
            q = bpy.data.objects.new(o.name + "_topcap", up_cap)
            bpy.context.scene.collection.objects.link(q)
            q.parent = head
            q.location, q.rotation_euler, q.scale = o.location, o.rotation_euler, o.scale
            o.data = up
        else:
            o.data = bpy.data.meshes.new(o.name + "_none")
    tw, tl = tongue or (max(0.03, width * 0.33), max(0.04, abs(front - hinge_y) * 0.3))
    ty = front * 0.52 + hinge_y * 0.48 - hinge_y
    C.ell(n + "_ptongue", (tw, tl, 0.014), (0, ty, 0.004), "tongue_felt", jaw, seg=24)
    C.capsule(n + "_ptongue_l", (0, ty - tl * 0.8, 0.017), (0, ty + tl * 0.5, 0.017), 0.003, 0.003, "tongue_d", jaw, seg=8)
    if throat:
        C.ell(n + "_throat", (tw * 1.25, tl * 0.7, 0.004), (0, ty + tl * 1.1, 0.002), "throat", jaw, seg=24)
        C.ell(n + "_throat_up", (tw * 1.25, tl * 0.7, 0.004), (0, ty + tl * 1.1 + hinge_y, zcut - 0.002), "throat", head,
              seg=24)
    return jaw


def puppet_eyes(c, r, flat=1.0, lift=0.02, push=0.0, cross=0.2, lid=0.0, skin="fur", pupil=0.42, down=0.06,
                white="peye", black="ppupil"):
    """ping-pong eyes with felt pupils (a little cross-eyed), optional heavy lids in the skin fleece"""
    n, head = c.name, c.head.obj
    for side in "LR":
        if "eye" + side not in c.J:
            continue
        e = c.J["eye" + side].obj
        sx = 1 if e.location.x > 0 else -1
        ctr = V((e.location.x, e.location.y + push, e.location.z + lift))
        blank(e)
        C.ell(f"{n}_peye{side}", (r, r * flat, r), ctr, white, head, seg=40)
        d = V((-sx * cross, -1.0, -down)).normalized()
        p = ctr + V((d.x * r, d.y * r * flat, d.z * r)) * 0.975
        rp = r * pupil
        C.ell(f"{n}_ppupil{side}", (rp, rp * 0.22, rp), p, black, head, seg=24)
        if lid > 0:
            o = C.ell(f"{n}_plid{side}", (r * 1.07, r * flat * 1.09, r * 1.07), ctr, skin, head, seg=40)
            bm = bmesh.new()
            bm.from_mesh(o.data)
            _cut(bm, V((0, 0, r * (1 - 2 * lid))), V((0.0, -0.25, 1.0)).normalized(), 1)
            me = bpy.data.meshes.new(o.name + "_cut")
            bm.to_mesh(me)
            bm.free()
            for m in o.data.materials:
                me.materials.append(m)
            o.data = me
            sol = o.modifiers.new("thick", "SOLIDIFY")
            sol.thickness = r * 0.06


def puppet_brows(c, w, th, dz, mat="pbrow", droop=0.0):
    n = c.name
    for side in "LR":
        if "brow" + side not in c.J:
            continue
        b = c.J["brow" + side].obj
        sx = 1 if b.location.x > 0 else -1
        for q in b.children:
            blank(q)
        C.capsule(f"{n}_pbrow{side}", (-w / 2 * sx, -0.012, dz + droop * w), (w / 2 * sx, -0.012, dz - droop * w * 0.2),
                  th, th * 0.8, mat, b, seg=16)


def rods(c, tgt_local=(0.0, 0.25, -3.0), r=0.0045, length=1.6):
    """the puppeteer's arm rods: from each wrist down below the stage"""
    n = c.name
    tgt = C.empty(n + "_rodtgt", tgt_local, c.root)
    for side in "LR":
        if "hand" + side not in c.J:
            continue
        rod = C.cyl(f"{n}_rod{side}", r, length, (0, 0, 0), "rod", c.J["hand" + side], origin=(0, 0, -length / 2),
                    seg=8, bevel=0)
        k = rod.constraints.new("DAMPED_TRACK")
        k.target = tgt
        k.track_axis = "TRACK_NEGATIVE_Z"


def recolour(c, table):
    """swap materials of one figure: {old material name: new material}"""
    for o in objs(c.name):
        if o.type == "MESH":
            for i, m in enumerate(o.data.materials):
                if m is not None and m.name in table:
                    o.data.materials[i] = table[m.name]


def _puppet_materials():
    C.mat("peye", "#FBFAF5", rough=0.32, sss=0.1)
    C.mat("ppupil", "#0C0C0E", rough=0.55)
    C.felt("mouth_felt", "#8E1B2A", fuzz=0.5, scale=500.0, bump=0.15, tint="#D45A66")
    C.felt("tongue_felt", "#EE7F96", fuzz=0.6, scale=500.0, bump=0.15, tint="#FFC2CF")
    C.mat("tongue_d", "#C95472", rough=0.9)
    C.felt("throat", "#1B0A0E", fuzz=0.3, scale=500.0, bump=0.1, tint="#4A1A22")
    C.mat("rod", "#17181A", rough=0.4, metal=0.6)
    C.felt("pbrow", "#3A2616", fuzz=1.0, scale=500.0, bump=0.3, tint="#8A6A4A")
    M = C._MATS
    for k, col in (("nose", "#1A1B1F"), ("beak", "#F0A22E"), ("tooth", "#F6F1E4")):
        if k in M:
            soften(M[k], col, sheen=0.9)
    _garments()


def _near_white(col):
    r, g, b = col[:3]
    return min(r, g, b) > 0.6 and max(r, g, b) - min(r, g, b) < 0.18


def puppet_options(c):
    """the puppet options of a figure: class attribute `puppet`, cast entry keys, PUPPET[name] (later wins)"""
    o = dict(getattr(c, "puppet", None) or {})
    look = getattr(c, "look_d", None) or {}
    o.update({k: look[k] for k in ("fleece", "fleece2", "belly", "fuzz", "rods") if k in look})
    o.update(look.get("puppet") or {})
    o.update(PUPPET.get(c.name) or {})
    return o


def puppet(S, cast):
    """turn built figures into hand puppets. Returns {name: jaw Node or None}."""
    _puppet_materials()
    jaws = {}
    for i, (name, c) in enumerate(cast.items()):
        o = puppet_options(c)
        head = c.head.obj
        hm = next((q for q in head.children if q.type == "MESH" and _suffix(q, name) == "head"), None)
        fur = [m for q in objs(name) if q.type == "MESH" for m in q.data.materials
               if m is not None and m.name.startswith("fur") and not m.name.startswith("fur_tail")]
        base = _color_of(fur[0]) if fur else srgb("#F3EFE6")
        col = _rgba(o["fleece"]) if o.get("fleece") else (srgb(FLEECE[i % len(FLEECE)]) if _near_white(base) else base)
        skin = fleece(f"fleece_{name}", col)
        fur2 = fleece(f"fleece2_{name}", o.get("fleece2") or _shade(col, 0.6), scale=120.0, bump=0.5)
        belly = fleece(f"fleece_b_{name}", o.get("belly") or _shade(col, 1.75))
        table = {}
        for q in objs(name):
            if q.type != "MESH":
                continue
            s = _suffix(q, name)
            for m in q.data.materials:
                if m is None or m.name in table:
                    continue
                if m.name.startswith("fur_tail"):
                    table[m.name] = fur2
                elif m.name.startswith("fur"):
                    table[m.name] = skin
            if s in ("belly", "chest") or s.startswith(("earin", "disc")):
                for k, m in enumerate(q.data.materials):
                    if m is not None and m.name == "shirt":
                        q.data.materials[k] = belly
        recolour(c, table)

        # ---- the mouth: where the modelled mouth is; figures without one (a beak) keep theirs
        mouth = next((q for q in head.children if _suffix(q, name) == "mouth"), None)
        jaw = None
        if mouth is not None and hm is not None:
            ry = max(abs(v) for v in _bbox(hm, 1))
            zcut = o.get("cut", mouth.location.z + 0.02)
            hinge = o.get("hinge", hm.location.y + 0.6 * ry)
            jaw = flap_mouth(S, c, zcut, hinge, parts=o.get("parts", r"(head|snout|muzzle|cheek.*)"),
                             tongue=o.get("tongue"), throat=o.get("throat", True))
            blank(mouth)
            deg = float(o.get("open", 26.0))
            rest = 0.6 * getattr(c, "mouth_rest", 0.0)           # a resting mouth is nearly shut
            jaw.rch(0).add(lambda f, c=c, deg=deg, rest=rest: deg * C.clamp(c.mouth_ch.eval(f) - rest, 0.0, 1.4))
        jaws[name] = jaw

        # ---- eyes and brows, sized from the eyes the figure had
        eye = c.J.get("eyeL")
        if eye is not None and eye.obj.type == "MESH" and eye.obj.data.vertices:
            r0 = _bbox(eye.obj, 0)[1]
            gl = next((q for q in head.children if re.fullmatch(r"gl-?\d", _suffix(q, name))), None)
            if gl is not None:                              # behind glasses: flat discs that fit the rims
                R = _bbox(gl, 0)[1]
                r = o.get("eye", R * 0.78)
                flat = o.get("flat", 0.3)
                push = o.get("push", gl.location.y + 0.004 - eye.obj.location.y)      # the discs sit in the rims
                lift, down = o.get("lift", 0.0), 0.0
            else:
                r, flat = o.get("eye", r0 * 1.9), o.get("flat", 1.0)
                push, lift, down = o.get("push", -0.4 * r0), o.get("lift", 1.6 * r0), 0.06
            puppet_eyes(c, r, flat=flat, lift=lift, push=push, cross=o.get("cross", 0.15), lid=o.get("lid", 0.0),
                        skin=skin, pupil=o.get("pupil", 0.42), down=down)
            if o.get("brow"):
                C.felt(f"pbrow_{name}", o["brow"], fuzz=1.0, scale=500.0, bump=0.3)
            puppet_brows(c, r0 * 2.4, r0 * 0.42, (0.01 if gl is not None else r0 * 3.0),
                         f"pbrow_{name}" if o.get("brow") else "pbrow")

        # ---- no legs, no glass in the frames, hair, rods
        for q in objs(name):
            if q.type != "MESH":
                continue
            s = _suffix(q, name)
            if re.match(r"(leg|shin|foot|toe)", s) or s.startswith("lens"):
                blank(q)
                continue
            if o.get("fuzz", True) is False or not q.data.polygons or not q.data.materials or q.data.materials[0] is None:
                continue
            mn = q.data.materials[0].name
            if mn == fur2.name:
                fuzz(q, 0.03, 160000, child=24, rough=0.06, rad=0.0004, clump=0.15, seed=len(s))
            elif mn in (skin.name, belly.name) and "lid" not in s:
                fuzz(q, 0.0065, 380000, seed=len(s))
        if o.get("rods", True):
            rods(c)
    return jaws


# ====================================================================== gothic stop-motion puppets
BONE, INK, PALE = "#CFCABB", "#131317", "#B4BCC8"


def clay(m, color, dark="#646C7E", lumps=0.45):
    """hand-sculpted modelling clay / foam latex: matte, soft thumb marks, a little paint in the hollows"""
    nt, b = _base(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    big = _noise(nt, tc.outputs["Object"], 26.0, 2.0)
    fine = _noise(nt, tc.outputs["Object"], 420.0, 2.0)
    nt.links.new(_mix(nt, _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, big), 0.55), color, dark),
                 b.inputs["Base Color"])
    C._set(b, **{"Roughness": 0.62, "Specular IOR Level": 0.35, "Subsurface Weight": 0.12, "Subsurface Scale": 0.02,
                 "Sheen Weight": 0.1})
    _bump(nt, b, _math(nt, "ADD", big, _math(nt, "MULTIPLY", fine, 0.06)), lumps, 0.006)
    m.diffuse_color = _rgba(color)
    return m


def _stripe_fac(nt, tc, n=14, rings=None):
    """0/1 stripes, a little wobbly as if painted by hand: n around the local Z axis, or rings of a height along Z"""
    sx = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sx.inputs[0])
    if rings:
        v = _math(nt, "MULTIPLY", sx.outputs["Z"], TAU / rings)
    else:
        v = _math(nt, "MULTIPLY", _math(nt, "ARCTAN2", sx.outputs["X"], sx.outputs["Y"]), float(n))
    wob = _math(nt, "MULTIPLY", _noise(nt, tc.outputs["Object"], 30.0, 2.0), 1.2)
    return _math(nt, "GREATER_THAN", _math(nt, "SINE", _math(nt, "ADD", v, wob)), 0.0)


def stripes(m, a=INK, b_=BONE, n=14, rings=None):
    nt, b = _base(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(_mix(nt, _stripe_fac(nt, tc, n, rings), a, b_), b.inputs["Base Color"])
    C._set(b, **{"Roughness": 0.85, "Sheen Weight": 0.5, "Sheen Roughness": 0.4, "Specular IOR Level": 0.2})
    _bump(nt, b, _noise(nt, tc.outputs["Object"], 600.0, 2.0), 0.25, 0.002)
    m.diffuse_color = _rgba(b_)
    return m


def stripes_over(m, a=INK, b_=BONE, n=16):
    """a vest material with its shirt V-neck: the vest gets the stripes"""
    nt = m.node_tree
    tc = next((x for x in nt.nodes if x.type == "TEX_COORD"), None)
    mx = next((x for x in nt.nodes if x.type == "MIX"), None)
    if tc is None or mx is None:
        return m
    nt.links.new(_mix(nt, _stripe_fac(nt, tc, n), a, b_), mx.inputs["A"])
    mx.inputs["B"].default_value = srgb("#BEB8A8")
    return m


def _pale(col):
    """the clay colour of a fur colour: white stays the pale grey-blue, a colour is kept as a greyed tint of it"""
    if _near_white(col):
        return srgb(PALE)
    p, (r, g, b) = srgb(PALE), col[:3]
    lum = 0.3 * r + 0.6 * g + 0.1 * b
    return tuple(0.55 * p[i] + 0.45 * (0.5 * (r, g, b)[i] + 0.5 * lum) for i in range(3)) + (1.0,)


def _stopmotion_materials():
    M = C._MATS
    for k, m in list(M.items()):
        if m.get("stage_look"):
            continue
        if k.startswith("fur_tail"):
            stripes(m, rings=0.05)
        elif k.startswith("fur"):
            clay(m, _pale(_color_of(m)))
        elif k == "shirt":
            clay(m, "#C9C4B4", "#857F74", lumps=0.2)
        elif k.startswith("vest_"):
            stripes_over(m)
        elif k.startswith(("knit", "accent")) and m.node_tree and m.node_tree.nodes.get("Principled BSDF"):
            if k.endswith("_d") or "_d_" in k:
                soften(m, INK)
            else:
                stripes(m, n=12)
        elif k == "shell":
            quilt(m, "#4A4460", "#1E1B2A", scale=11.0)
        elif k in ("shell_rim", "shell_plate"):
            soften(m, "#262232")
        else:
            continue
        m["stage_look"] = 1
    for k, col, kw in (("nose", "#0E0E11", {}), ("mouth_in", "#1A0A10", {}), ("tongue", "#8A4A58", {}),
                       ("tooth", "#CFC6A2", {}), ("beak", "#A9A28C", {}), ("gold", "#6E6038", {"rough": 0.5, "sheen": 0.1})):
        if k in M:
            soften(M[k], col, **kw)
    C.mat("sm_eye", "#F4F2EA", rough=0.18, coat=0.6, sss=0.05)          # porcelain
    C.mat("sm_pupil", "#050506", rough=0.3)
    C.mat("sm_socket", "#2A2130", rough=0.95)
    C.mat("sm_thread", "#0F0F12", rough=0.85, sheen=0.4)
    C.mat("sm_seam", "#6B6470", rough=1.0)


def stopmotion(S, cast, thin=0.5, head=1.16, waist=0.86):
    """turn built figures into gothic stop-motion puppets. A figure's class attribute `stopmotion = {...}` (or the
    same key in a bundled figure's cast entry) can set thin / head / waist / eye / pupil."""
    _stopmotion_materials()
    for name, c in cast.items():
        o = dict(getattr(c, "stopmotion", None) or {})
        o.update((getattr(c, "look_d", None) or {}).get("stopmotion") or {})
        th, hd, wa = o.get("thin", thin), o.get("head", head), o.get("waist", waist)
        # ---- proportions: a big head on a narrow body, wire limbs
        if "body" in c.J:
            c.J["body"].obj.scale = (wa, wa, 1.0)
        c.head.obj.scale = (hd / wa, hd / wa, hd)
        for q in objs(name):
            if q.type != "MESH":
                continue
            s = _suffix(q, name)
            if re.fullmatch(r"(arm|fore|leg|shin)[LR]_m", s):
                q.scale = (th, th, 1.0)
            elif re.fullmatch(r"arm[LR]_h", s):
                q.scale = (0.7, 0.7, 1.15)                    # long narrow hands
            elif re.fullmatch(r"foot[LR]", s):
                q.scale = (0.62, 1.2, 0.7)                    # long pointed shoes
            elif s == "neck":
                q.scale = (0.55, 0.55, 1.0)
        # ---- eyes: huge, round, pin pupils, dark sockets; no brows
        e = c.J.get("eyeL")
        if e is not None and e.obj.type == "MESH" and e.obj.data.vertices:
            gl = next((q for q in c.head.obj.children if re.fullmatch(r"gl-?\d", _suffix(q, name))), None)
            r0 = _bbox(e.obj, 0)[1]
            locs = {s: c.J["eye" + s].obj.location.copy() for s in "LR" if "eye" + s in c.J}
            if gl is not None:
                R, flat, lift = o.get("eye", _bbox(gl, 0)[1] * 0.8), 0.3, 0.0
                push = gl.location.y + 0.004 - e.obj.location.y
            else:
                R, flat, lift, push = o.get("eye", r0 * 1.95), 0.85, r0 * 1.2, -0.25 * r0
            puppet_eyes(c, R, flat=flat, lift=lift, push=push, cross=0.06, pupil=o.get("pupil", 0.15), down=0.0,
                        white="sm_eye", black="sm_pupil")
            if gl is None:
                for s, p in locs.items():
                    C.ell(f"{name}_socket{s}", (R * 1.2, R * 0.4, R * 1.2), (p.x, p.y + push + R * 0.5, p.z + lift),
                          "sm_socket", c.head, seg=32)
            for s in "LR":
                if "brow" + s in c.J:
                    for q in c.J["brow" + s].obj.children:
                        blank(q)
        # ---- the stitched skull and the sewn mouth
        kids = {(_suffix(q, name)): q for q in c.head.obj.children if q.type == "MESH" and q.data.polygons}
        if "head" in kids:
            seam(kids["head"], (0.02, 0, 0.0), (1, 0.12, 0.45), pitch=0.016, length=0.013, r=0.0013, mat="sm_thread",
                 groove="sm_seam")
        mouth = next((q for q in c.head.obj.children if _suffix(q, name) == "mouth"), None)
        mz = kids.get("muzzle") or kids.get("snout")
        if mouth is not None and mz is not None:
            z = mouth.location.z + 0.012 - mz.location.z
            seam(mz, (0, 0, z), (0.02, 0.03, 1), pitch=0.012, length=0.016, r=0.0012, mat="sm_thread", groove="sm_thread",
                 keep=lambda p: p.y < -0.01)


# ====================================================================== plasticine, paper, wood
_SOFT = (r"(head|torso|chest|belly|muzzle|snout|cheek.*|ear.*|neck|tail.*|t\d|tuft.*|disc.*|(arm|fore|leg|shin)[LR]_m"
         r"|arm[LR]_h|foot[LR])")
CLAY = ("#86B84C", "#F3B52F", "#EA652B", "#5F84DA", "#E0719A", "#3FA7A0")       # given out in cast order


def _opts(c, key):
    """the options of a figure for a make: class attribute <key> = {...}, or the same key in its cast entry"""
    o = dict(getattr(c, key, None) or {}) if isinstance(getattr(c, key, None), dict) else {}
    o.update((getattr(c, "look_d", None) or {}).get(key) or {})
    return o


def _eye_size(c):
    """(radius of the modelled eye, the glasses object or None) - (None, None) for a figure without eyes"""
    e = c.J.get("eyeL")
    if e is None or e.obj.type != "MESH" or not e.obj.data.vertices:
        return None, None
    gl = next((q for q in c.head.obj.children if re.fullmatch(r"gl-?\d", _suffix(q, c.name))), None)
    return _bbox(e.obj, 0)[1], gl


def _fur_colour(name):
    fur = [m for q in objs(name) if q.type == "MESH" for m in q.data.materials
           if m is not None and m.name.startswith("fur") and not m.name.startswith("fur_tail")]
    return _color_of(fur[0]) if fur else srgb("#F3EFE6")


def _refur(c, skin, tail):
    """give one figure its own body and tail material (figures may share "fur")"""
    table = {}
    for q in objs(c.name):
        if q.type == "MESH":
            for m in q.data.materials:
                if m is not None and m.name.startswith("fur"):
                    table[m.name] = tail if m.name.startswith("fur_tail") else skin
    recolour(c, table)


def _vest_surface(m, height=None, strength=0.0, **bsdf):
    """a vest material keeps its colours (shirt V-neck); its surface gets another bump and finish"""
    nt = m.node_tree
    bp = next((n for n in nt.nodes if n.type == "BUMP"), None)
    tc = next((n for n in nt.nodes if n.type == "TEX_COORD"), None)
    if bp is not None:
        if height == "lumps" and tc is not None:
            for ln in list(bp.inputs["Height"].links):
                nt.links.remove(ln)
            nt.links.new(_noise(nt, tc.outputs["Object"], 17.0, 2.0), bp.inputs["Height"])
            bp.inputs["Distance"].default_value = 0.006
        bp.inputs["Strength"].default_value = strength
    b = nt.nodes.get("Principled BSDF")
    if b is not None:
        C._set(b, **bsdf)


def plasticine(m, color, prints=0.16, lumps=0.6):
    """modelling clay: soft lumps from the thumbs, fine ridges of finger prints here and there, a waxy sheen"""
    nt, b = _base(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    big = _noise(nt, tc.outputs["Object"], 17.0, 2.0)
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_type, w.wave_profile = "RINGS", "SIN"
    w.inputs["Scale"].default_value = 55.0
    w.inputs["Distortion"].default_value = 9.0
    w.inputs["Detail"].default_value = 2.0
    w.inputs["Detail Scale"].default_value = 1.2
    nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
    patch = _math(nt, "GREATER_THAN", _noise(nt, tc.outputs["Object"], 9.0, 1.0), 0.52)
    ridges = _math(nt, "MULTIPLY", w.outputs["Fac"], patch)
    nt.links.new(_mix(nt, _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, big), 0.35), color, "#000000"),
                 b.inputs["Base Color"])
    C._set(b, **{"Roughness": 0.42, "Coat Weight": 0.12, "Coat Roughness": 0.3, "Subsurface Weight": 0.18,
                 "Subsurface Scale": 0.02, "Specular IOR Level": 0.45})
    _bump(nt, b, _math(nt, "ADD", big, _math(nt, "MULTIPLY", ridges, prints)), lumps, 0.006)
    m.diffuse_color = _rgba(color)
    return m


def claymation(S, cast):
    """turn built figures into plasticine figures. Options (class attribute / cast entry `clay`): color, color2"""
    M = C._MATS
    for k, m in list(M.items()):
        if m.get("stage_look"):
            continue
        if k == "shirt":
            plasticine(m, "#F4E8CC")
        elif k.startswith("vest_"):
            _vest_surface(m, "lumps", 0.6, **{"Roughness": 0.42, "Sheen Weight": 0.0, "Coat Weight": 0.12})
        elif k.startswith(("knit", "accent")) and m.node_tree and m.node_tree.nodes.get("Principled BSDF"):
            plasticine(m, _color_of(m))
        elif k in ("shell", "shell_plate", "shell_rim"):
            plasticine(m, {"shell": "#A9733C", "shell_plate": "#7C4F26", "shell_rim": "#8C5C2C"}[k])
        else:
            continue
        m["stage_look"] = 1
    for k, col in (("nose", "#17171A"), ("mouth_in", "#6A1522"), ("tongue", "#EC7C8E"), ("tooth", "#F6F1E4"),
                   ("beak", "#F2A32C"), ("gold", "#E2B43C"), ("ink", "#17171A")):
        if k in M:
            soften(M[k], col, rough=0.45, sheen=0.0)
    plasticine(C.mat("cl_eye", "#F5F2E8"), "#F5F2E8", prints=0.05, lumps=0.2)
    soften(C.mat("cl_pupil", "#0E0E10"), rough=0.4, sheen=0.0)
    plasticine(C.mat("cl_brow", "#3A2616"), "#3A2616", lumps=0.3)
    for i, (name, c) in enumerate(cast.items()):
        o = _opts(c, "clay")
        base = _fur_colour(name)
        col = _rgba(o["color"]) if o.get("color") else (srgb(CLAY[i % len(CLAY)]) if _near_white(base) else base)
        _refur(c, plasticine(C.mat(f"clay_{name}", "#808080"), col),
               plasticine(C.mat(f"clay2_{name}", "#808080"), o.get("color2") or _shade(col, 0.62)))
        r0, gl = _eye_size(c)
        if r0 is not None:
            if gl is not None:
                puppet_eyes(c, _bbox(gl, 0)[1] * 0.75, flat=0.3, lift=0.0, cross=0.08, pupil=0.36, down=0.0,
                            push=gl.location.y + 0.004 - c.J["eyeL"].obj.location.y, white="cl_eye", black="cl_pupil")
            else:
                puppet_eyes(c, r0 * 1.55, flat=0.9, lift=r0 * 0.5, push=-0.1 * r0, cross=0.1, pupil=0.4, down=0.03,
                            white="cl_eye", black="cl_pupil")
            puppet_brows(c, r0 * 2.2, r0 * 0.36, (0.008 if gl is not None else r0 * 1.9), "cl_brow")
        for q in objs(name):
            if q.type == "MESH" and q.data.polygons and re.fullmatch(_SOFT, _suffix(q, name)):
                lumpy(q, 0.003 if _suffix(q, name) == "head" else 0.006, 0.09)


def paper_mat(m, color, fibre=0.2):
    nt, b = _base(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    f = _noise(nt, tc.outputs["Object"], 900.0, 3.0)
    mott = _noise(nt, tc.outputs["Object"], 40.0, 2.0)
    nt.links.new(_mix(nt, _math(nt, "MULTIPLY", mott, 0.12), color, "#8A8578"), b.inputs["Base Color"])
    C._set(b, **{"Roughness": 0.93, "Specular IOR Level": 0.15, "Subsurface Weight": 0.06, "Subsurface Scale": 0.01})
    _bump(nt, b, f, fibre, 0.001)
    m.diffuse_color = _rgba(color)
    return m


def _craft_sheet(folded, dash=0.011, gap=0.008, tab=0.014, seed=5):
    """what makes a paper model a cut-out sheet: printed dashed fold lines on the creases and glue tabs (flaps of
    the neighbouring part, a shade darker) lying over some of the edges. Applies the fold (decimate) modifiers."""
    paper_mat(C.mat("pp_tab", "#DDD6C4"), "#DDD6C4")
    C.mat("pp_fold", "#8C8A84", rough=0.9)
    rng = random.Random(seed)
    dg = bpy.context.evaluated_depsgraph_get()
    for o in folded:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        o.modifiers.clear()
        o.data = me
    for o in folded:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.normal_update()
        lines, tabs = bmesh.new(), bmesh.new()
        for e in bm.edges:
            if len(e.link_faces) != 2:
                continue
            a, b = e.verts[0].co, e.verts[1].co
            d = b - a
            L = d.length
            if L < 0.012 or e.calc_face_angle(0.0) < math.radians(9):
                continue
            n = (e.link_faces[0].normal + e.link_faces[1].normal).normalized()
            u = d / L
            t = gap * 0.5
            while t + dash * 0.6 < L:
                _stick(lines, a + u * t + n * 0.0006, a + u * min(L, t + dash) + n * 0.0006, 0.0007, 4)
                t += dash + gap
            if rng.random() < 0.16 and L > 0.03:
                f = rng.choice(e.link_faces)
                inw = f.normal.cross(u)
                if (f.calc_center_median() - a).dot(inw) < 0:
                    inw = -inw
                h, ins, up = min(tab, L * 0.45), u * L * 0.22, f.normal * 0.0009
                tabs.faces.new([tabs.verts.new(q + up) for q in (a + u * L * 0.08, b - u * L * 0.08, b - ins + inw * h,
                                                                 a + ins + inw * h)])
        bm.free()
        for g, mm, tag in ((lines, "pp_fold", "_folds"), (tabs, "pp_tab", "_tabs")):
            m2 = bpy.data.meshes.new(o.name + tag)
            g.to_mesh(m2)
            g.free()
            m2.materials.append(C.mat(mm))
            q = bpy.data.objects.new(o.name + tag, m2)
            bpy.context.scene.collection.objects.link(q)
            q.parent = o
            q.visible_shadow = False


def papercraft(S, cast):
    """turn built figures into folded paper models (the colours of the figures stay)"""
    M = C._MATS
    for k, m in list(M.items()):
        if m.get("stage_look"):
            continue
        if k.startswith("fur_tail"):
            paper_mat(m, _shade(_color_of(m), 0.93))
        elif k.startswith("fur"):
            paper_mat(m, _color_of(m))
        elif k == "shirt":
            acc = next((_color_of(M[a]) for a in M if a.startswith(("knit", "accent")) and not a.endswith("_d")
                        and "_d_" not in a), srgb("#3E9A6E"))
            paper_mat(m, _shade(acc, 1.8))
        elif k.startswith("vest_"):
            _vest_surface(m, None, 0.0, **{"Roughness": 0.93, "Sheen Weight": 0.0})
        elif k.startswith(("knit", "accent")) and m.node_tree and m.node_tree.nodes.get("Principled BSDF"):
            paper_mat(m, _color_of(m))
        elif k in ("shell", "shell_plate", "shell_rim"):
            paper_mat(m, _color_of(m))
        else:
            continue
        m["stage_look"] = 1
    for k, col in (("nose", "#1B1C20"), ("mouth_in", "#7A2030"), ("tongue", "#EE8E9C"), ("tooth", "#FFFFFF"),
                   ("beak", "#F0A63A"), ("gold", "#E8C25A"), ("ink", "#1B1C20"), ("brow", "#1B1C20")):
        if k in M:
            soften(M[k], col, rough=0.93, sheen=0.0)
    paper_mat(C.mat("pp_black", "#1B1C20"), "#1B1C20")
    paper_mat(C.mat("pp_white", "#FFFFFF"), "#FFFFFF")
    hard = _SOFT + r"|shell|hem|collar|scarf.*|plate\d+|nose|beak\d?|teeth|earin.*|bow.*|knot|tag"
    folded = []
    for name, c in cast.items():
        r0, _ = _eye_size(c)
        centre = next((q.location.copy() for q in objs(name) if q.type == "MESH" and _suffix(q, name) == "head"),
                      V((0, 0, 0)))
        for q in objs(name):
            if q.type != "MESH" or not q.data.polygons:
                continue
            s = _suffix(q, name)
            if re.fullmatch(r"eye[LR]", s):                   # a flat octagon of black paper with a white square
                r = _bbox(q, 0)[1] * 1.25
                loc, head = q.location.copy(), q.parent
                out = ((loc - centre).normalized() + V((0, -1.2, 0))).normalized()
                blank(q)
                g = C.empty(f"{name}_ppeye{s[-1]}", loc + out * 0.006, head)
                g.rotation_euler = V((0, 0, 1)).rotation_difference(out).to_euler()
                C.cyl(f"{name}_ppdisc{s[-1]}", r, 0.002, (0, 0, 0), "pp_black", g, seg=8, bevel=0)
                C.box(f"{name}_ppdot{s[-1]}", (r * 0.42, r * 0.42, 0.002), (-r * 0.3, -r * 0.3, 0.002), "pp_white", g,
                      bevel=0)
                continue
            if not re.fullmatch(hard, s):
                continue
            for p in q.data.polygons:                         # folded: every face flat, few of them
                p.use_smooth = False
            want = 150 if s in ("head", "torso", "shell") else 60
            if len(q.data.polygons) > want:
                md = q.modifiers.new("fold", "DECIMATE")
                md.ratio = max(0.02, want / (2 * len(q.data.polygons)))
                md.use_collapse_triangulate = True
                folded.append(q)
        for s in "LR":                                        # brows: strips of black paper
            b = c.J.get("brow" + s)
            if b is None or r0 is None:
                continue
            for q in b.obj.children:
                blank(q)
            C.box(f"{name}_ppbrow{s}", (r0 * 2.3, 0.002, r0 * 0.5), (0, -0.01, 0), "pp_black", b, bevel=0)
    _craft_sheet(folded)


def wood_mat(m, c1, c2, scale=16.0):
    """turned, lacquered wood with a fine grain (c1 light, c2 dark)"""
    nt, b = _base(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale * 0.08, scale)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 3.0, 6.0
    nz.inputs["Distortion"].default_value = 1.2
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    nt.links.new(_mix(nt, nz.outputs["Fac"], c2, c1), b.inputs["Base Color"])
    C._set(b, **{"Roughness": 0.32, "Coat Weight": 0.5, "Coat Roughness": 0.12})
    _bump(nt, b, nz.outputs["Fac"], 0.15, 0.002)
    m.diffuse_color = _rgba(c1)
    return m


def lacquer(m, color):
    nt, b = _base(m)
    C._set(b, **{"Base Color": _rgba(color), "Roughness": 0.28, "Coat Weight": 0.6, "Coat Roughness": 0.1})
    m.diffuse_color = _rgba(color)
    return m


def _string(name, slack, parent, loc):
    """a string of unit length along +Y (STRETCH_TO scales that axis only); slack = how far it bows out, in metres"""
    bm = bmesh.new()
    n = 14
    pts = [V((0.7 * slack * math.sin(math.pi * i / n) * (1.0 - 0.35 * i / n), i / n,
              0.7 * slack * math.sin(math.pi * i / n) * (1.0 - 0.35 * i / n))) for i in range(n + 1)]
    for a, b in zip(pts, pts[1:]):
        _stick(bm, a, b, 0.0016, 5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(C.mat("mr_string"))
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.parent = parent.obj if isinstance(parent, C.Node) else parent
    o.location = loc
    o.visible_shadow = False
    return o


def marionette(S, cast):
    """turn built figures into string puppets of carved, lacquered wood. Options (`marionette`): strings (False =
    none), slack (metres the hand strings bow out, default 0.11)"""
    M = C._MATS
    for k, m in list(M.items()):
        if m.get("stage_look"):
            continue
        if k.startswith("fur_tail"):
            col = _color_of(m)
            wood_mat(m, *(("#9A6A3A", "#6B4420") if _near_white(col) else (_shade(col, 0.6), _shade(col, 0.38))))
        elif k.startswith("fur"):
            col = _color_of(m)
            wood_mat(m, *(("#E2C493", "#B78D56") if _near_white(col) else (_shade(col, 0.95), _shade(col, 0.62))))
        elif k == "shirt":
            wood_mat(m, "#F0E4C8", "#D9C8A0")
        elif k.startswith("vest_"):
            _vest_surface(m, None, 0.0, **{"Roughness": 0.28, "Sheen Weight": 0.0, "Coat Weight": 0.6,
                                           "Coat Roughness": 0.1})
        elif k.startswith(("knit", "accent")) and m.node_tree and m.node_tree.nodes.get("Principled BSDF"):
            lacquer(m, _color_of(m))
        elif k in ("shell", "shell_plate", "shell_rim"):
            lacquer(m, _color_of(m))
        else:
            continue
        m["stage_look"] = 1
    C.mat("mr_joint", "#B78D56", rough=0.3, coat=0.5)
    C.mat("mr_string", "#EDE6D2", rough=0.9)
    C.mat("mr_cheek", "#E8705E", rough=0.35, coat=0.4)
    C.mat("mr_line", "#3A2616", rough=0.6)
    wood_mat(C.mat("mr_cross", "#8A5E38"), "#8A5E38", "#5E3C1E", scale=10.0)
    for name, c in cast.items():
        o = _opts(c, "marionette")
        parts = {_suffix(q, name): q for q in objs(name) if q.type == "MESH" and q.data.polygons}
        for s, q in parts.items():                             # turned limbs with ball joints
            if re.fullmatch(r"(arm|fore|leg|shin)[LR]_m", s):
                r = _bbox(q, 0)[1]
                q.scale = (0.8, 0.8, 0.94)
                C.ell(f"{name}_ball_{s}", r * 1.12, (0, 0, 0), "mr_joint", q.parent, seg=20)
        hm = parts.get("head")
        mouth = next((q for q in c.head.obj.children if _suffix(q, name) == "mouth"), None)
        if hm is not None:                                     # painted cheeks, the slots of a hinged jaw
            rx, ry, rz = (_bbox(hm, i)[1] for i in range(3))
            hc = hm.location
            for sx in (1, -1):
                d = V((sx * 0.62, -0.72, -0.22)).normalized()
                g = C.empty(f"{name}_cheekp{sx}", (hc.x + d.x * rx, hc.y + d.y * ry, hc.z + d.z * rz), c.head)
                g.rotation_euler = V((0, 0, 1)).rotation_difference(V((d.x / rx, d.y / ry, d.z / rz)).normalized()).to_euler()
                C.cyl(f"{name}_cheekd{sx}", rx * 0.2, 0.004, (0, 0, 0), "mr_cheek", g, seg=24, bevel=0.001)
            if mouth is not None and mouth.type == "MESH" and mouth.data.vertices:
                jm = parts.get("muzzle") or parts.get("snout") or hm
                w = _bbox(mouth, 0)[1] * 0.95
                y0 = jm.location.y - _bbox(jm, 1)[1] * (0.82 if jm is not hm else 0.93)
                zl = mouth.location.z - jm.location.z
                for sx in (1, -1):
                    seam(jm, (sx * w - jm.location.x, 0, 0), (1, 0.03, 0.02), pitch=99.0, r=0.0055, mat="mr_line",
                         groove="mr_line", keep=lambda p, zl=zl: p.z < zl + 0.004 and p.y < 0.0)
                C.capsule(f"{name}_jawslot", (-w, y0 - 0.004, mouth.location.z), (w, y0 - 0.004, mouth.location.z), 0.004,
                          0.004, "mr_line", c.head, seg=8)
        if o.get("strings", True):                              # the strings and the control cross
            cross = C.empty(f"{name}_cross", (0, 0, getattr(c, "head_z", 0.7) + 0.95), c.root)
            C.box(f"{name}_cross_a", (0.5, 0.035, 0.022), (0, 0, 0), "mr_cross", cross, bevel=0.004)
            C.box(f"{name}_cross_b", (0.035, 0.34, 0.022), (0, -0.02, 0.022), "mr_cross", cross, bevel=0.004)
            top = (_bbox(hm, 2)[1] + hm.location.z) if hm is not None else 0.3
            for jn, off in (("head", (0, 0, 0)), ("handL", (0.23, 0, 0)), ("handR", (-0.23, 0, 0))):
                if jn not in c.J:
                    continue
                tgt = C.empty(f"{name}_strt_{jn}", off, cross)
                st = _string(f"{name}_string_{jn}", 0.0 if jn == "head" else o.get("slack", 0.11), c.J[jn],
                             (0, 0, top if jn == "head" else 0.0))
                k = st.constraints.new("STRETCH_TO")
                k.target, k.rest_length, k.volume = tgt, 1.0, "NO_VOLUME"


# ====================================================================== entry
def dress(S, cast, style):
    """apply a make to built figures (called by stage_actor.cast): one of STYLES"""
    if style in (None, "", "toy"):
        return None
    if style == "ragdoll":
        return ragdoll(S, cast)
    if style == "puppet":
        return puppet(S, cast)
    if style == "stopmotion":
        return stopmotion(S, cast)
    if style == "clay":
        return claymation(S, cast)
    if style == "paper":
        return papercraft(S, cast)
    if style == "marionette":
        return marionette(S, cast)
    raise ValueError(f'figures "{style}" unknown - one of {", ".join(STYLES)}')
