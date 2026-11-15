# Runs inside Blender's Python (bpy) - started by stage_run.py, never with uv.
"""stage-3d core: scene setup, animation tracks (own easing, baked per frame), mesh primitives, materials, text,
cameras/shots and render settings for character films rendered with Cycles.

Runs inside Blender 4.2+ (tested 5.2 LTS, headless). Conventions: metres, Z up, characters face -Y (camera usually
at -Y), angles in degrees in all track APIs, frames are integers at 24 fps (frame 1 = first frame of a clip).
PROJECT is the film project folder (set by stage_film.py before a scene is built): renders go to PROJECT/out,
load_json() and the spoken lines are read relative to it.
"""
import json
import math
import os
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

V = Vector
PROJECT = Path(os.environ.get("STAGE3D_PROJECT") or Path.cwd())
FPS = 24


def find_font(*names):
    """first of the font files found in STAGE3D_FONT_DIR / the system font folders, else None (Blender's own font)"""
    dirs = [os.environ.get("STAGE3D_FONT_DIR"), os.path.join(os.environ.get("WINDIR", ""), "Fonts"),
            os.path.expanduser("~/Library/Fonts"), "/Library/Fonts", "/System/Library/Fonts/Supplemental",
            "/usr/share/fonts", os.path.expanduser("~/.fonts")]
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for n in names:
            f = os.path.join(d, n)
            if os.path.isfile(f):
                return f
        if d.startswith("/usr") or d.endswith(".fonts"):          # Linux font folders are nested
            for root, _, files in os.walk(d):
                for n in names:
                    if n in files:
                        return os.path.join(root, n)
    return None


# bold / semibold / hand-lettered font for 3D text; an environment variable names another TTF
FONT_BOLD = os.environ.get("STAGE3D_FONT_BOLD") or find_font("segoeuib.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf")
FONT_SEMI = os.environ.get("STAGE3D_FONT_SEMI") or find_font("seguisb.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf")
FONT_COMIC = os.environ.get("STAGE3D_FONT_COMIC") or find_font("comicbd.ttf", "Comic Sans MS Bold.ttf",
                                                               "DejaVuSans-Bold.ttf")

WHITE = "#F3EFE6"
INK = "#15171A"
BLUE = "#2F6FB5"

# The colours of a film: one accent family on warm neutrals. The props and sets read PAL when they are built
# (stage_props.palette()), so call set_palette() first - stage_film.py does it from project.json "palette"
# (a name of PALETTES, or a dict of overrides, optionally with "base": "<name>").
PALETTES = {
    "ivory": {    # the default: plaster walls, dark walnut, ink blue and one coral accent
        "accent": "#D9603B", "accent_l": "#EE9270", "accent_d": "#A8432A", "wall_accent": "#262B3A",
        "wall": "#EDE6DA", "wall_warm": "#C9BBA8", "wall_soft": "#DDD2C4", "paper_a": "#F1E8DC",
        "rug": "#2D3346", "ceramic": "#D9603B", "coin": "#D9B36A", "txt_accent": "#C24F2D",
        "txt_soft": "#F4C9B5", "screen": "#6FD6C8", "glow": "#FF9A6B",
        "oak": "#B98F68", "oak2": "#96704C", "walnut": "#4B2F22", "walnut2": "#2F1D15",
        "floor": "#6B4A36", "floor2": "#4A3122",
    },
    "petrol": {   # petrol blue with terracotta
        "accent": "#27637A", "accent_l": "#5C9DB3", "accent_d": "#18404F", "wall_accent": "#2A5567",
        "wall": "#EDE3D2", "wall_warm": "#C4AE97", "wall_soft": "#C9D8DE", "paper_a": "#E3EBEF",
        "rug": "#B5654A", "ceramic": "#C8553D", "coin": "#E0B44C", "txt_accent": "#1F5266",
        "txt_soft": "#A9D8E6", "screen": "#7CCBE8", "glow": "#5CD8FF",
        "oak": "#C79A6B", "oak2": "#A87B4E", "walnut": "#7A5236", "walnut2": "#553623",
        "floor": "#9C7350", "floor2": "#7C5638",
    },
    "forest": {   # deep green on walnut
        "accent": "#2E6B4F", "accent_l": "#4F9B76", "accent_d": "#1F4A37", "wall_accent": "#2F5E49",
        "wall": "#EDE3D2", "wall_warm": "#BDA78E", "wall_soft": "#C3D1BE", "paper_a": "#E4EDE2",
        "rug": "#3B6E57", "ceramic": "#2E6B4F", "coin": "#3FA06E", "txt_accent": "#2E6B4F",
        "txt_soft": "#A8E6C5", "screen": "#7BE0A6", "glow": "#5CFFA0",
        "oak": "#C79A6B", "oak2": "#A87B4E", "walnut": "#7A5236", "walnut2": "#553623",
        "floor": "#9C7350", "floor2": "#7C5638",
    },
}
DEFAULT_PALETTE = "ivory"
PAL = dict(PALETTES[DEFAULT_PALETTE])


def set_palette(p=None):
    """choose the film colours: a name of PALETTES or a dict of overrides ({"base": "forest", "rug": "#884422"})"""
    if not p:
        p = DEFAULT_PALETTE
    if isinstance(p, str):
        if p not in PALETTES:
            raise ValueError(f'palette "{p}" unknown - one of {", ".join(PALETTES)} or a dict of colours')
        p = PALETTES[p]
    else:
        p = dict(PALETTES[p.get("base", DEFAULT_PALETTE)], **{k: v for k, v in p.items() if k != "base"})
        bad = [k for k in p if k not in PALETTES[DEFAULT_PALETTE]]
        if bad:
            raise ValueError(f"palette keys unknown: {bad} - known: {', '.join(PALETTES[DEFAULT_PALETTE])}")
    PAL.clear()
    PAL.update(p)
    return PAL


# ------------------------------------------------------------------ small helpers
def srgb(h, a=1.0):
    if not isinstance(h, str):
        return (*h[:3], a)
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c], a)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def _ease(kind, t):
    if kind == "lin":
        return t
    if kind == "in":
        return t * t
    if kind == "out":
        return 1 - (1 - t) ** 2
    if kind == "out3":
        return 1 - (1 - t) ** 3
    if kind == "hold":
        return 0.0 if t < 1 else 1.0
    if kind == "back":          # overshoot and settle
        c = 2.2
        u = t - 1
        return 1 + (c + 1) * u ** 3 + c * u ** 2
    if kind == "spring":
        return 1 - math.exp(-6 * t) * math.cos(11 * t) if t < 1 else 1.0
    if kind == "bounce":
        if t < 0.55:
            return (t / 0.55) ** 2
        if t < 0.85:
            u = (t - 0.55) / 0.3
            return 1 - 0.18 * (1 - (2 * u - 1) ** 2)
        u = (t - 0.85) / 0.15
        return 1 - 0.05 * (1 - (2 * u - 1) ** 2)
    return smooth(t)            # "io"


class Ch:
    """scalar channel: keys (frame, value, ease of the segment arriving at the key) + additive layers"""

    def __init__(self, default=0.0):
        self.keys = []
        self.default = default
        self.layers = []
        self.mlayers = []
        self._sorted = True

    def key(self, f, v, ease="io"):
        self.keys = [k for k in self.keys if k[0] != f]
        self.keys.append((f, float(v), ease))
        self._sorted = False
        return self

    def add(self, fn):
        self.layers.append(fn)

    def last(self, f=1e9):
        self._sort()
        v = self.default
        for k in self.keys:
            if k[0] <= f:
                v = k[1]
        return v

    def _sort(self):
        if not self._sorted:
            self.keys.sort(key=lambda k: k[0])
            self._sorted = True

    def base(self, f):
        self._sort()
        ks = self.keys
        if not ks:
            return self.default
        if f <= ks[0][0]:
            return ks[0][1]
        if f >= ks[-1][0]:
            return ks[-1][1]
        lo, hi = 0, len(ks) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ks[mid][0] <= f:
                lo = mid
            else:
                hi = mid
        a, b = ks[lo], ks[hi]
        t = (f - a[0]) / (b[0] - a[0])
        return a[1] + (b[1] - a[1]) * _ease(b[2], t)

    def eval(self, f):
        v = self.base(f)
        for fn in self.layers:
            v += fn(f)
        for fn in self.mlayers:
            v *= fn(f)
        return v

    def mul(self, fn):
        self.mlayers.append(fn)


class Stage:
    """one clip: owns the Blender scene, all tracks and the shot list"""

    def __init__(self, name, frames, seed=1):
        self.name, self.frames = name, frames
        self.rng = random.Random(seed)
        self.tracks = {}            # (id, path, index) -> Ch
        self.scale = {}             # (id, path) -> factor (deg->rad)
        self.steps = []             # (id, path, frame): hard cut, no motion-blur streak
        self.shots = []
        self.cams = []
        reset()
        sc = bpy.context.scene
        sc.frame_start, sc.frame_end = 1, frames
        sc.render.fps = FPS
        self.scene = sc

    # ---- tracks
    def ch(self, idb, path, index=0, default=None, deg=False):
        k = (idb, path, index)
        if k not in self.tracks:
            if default is None:
                cur = idb.path_resolve(path)
                default = cur[index] if hasattr(cur, "__len__") else cur
                if deg:
                    default = math.degrees(default)
            self.tracks[k] = Ch(float(default))
            if deg:
                self.scale[k] = math.pi / 180
        return self.tracks[k]

    def step(self, idb, path, f):
        self.steps.append((idb, path, f))

    def vis(self, obj, f_on=None, f_off=None):
        """show an object only between f_on and f_off (render + viewport), children are not affected"""
        c = self.ch(obj, "hide_render", 0, default=0.0)
        if f_on is not None and f_on > 1:
            c.key(1, 1, "hold")
            c.key(f_on, 0, "hold")
        else:
            c.key(1, 0, "hold")
        if f_off is not None:
            c.key(f_off, 1, "hold")

    # ---- shots
    def shot(self, f0, loc, aim, loc1=None, aim1=None, f1=None, lens=50, lens1=None, fstop=2.8, focus=None,
             ease="io", shake=0.0, roll=0.0, name=None):
        """camera cut at f0. loc/aim -> loc1/aim1 until f1 (default: next shot). focus: point or Node/obj"""
        cam = Cam(self, name or f"cam{len(self.shots):02d}_{f0}", lens, fstop)
        cam.f0 = f0
        self.shots.append((f0, cam))
        cam.pending = (loc, aim, loc1, aim1, f1, lens1, focus, ease, shake, roll)
        return cam

    def _finish_shots(self):
        self.shots.sort(key=lambda s: s[0])
        for i, (f0, cam) in enumerate(self.shots):
            end = self.shots[i + 1][0] - 1 if i + 1 < len(self.shots) else self.frames
            loc, aim, loc1, aim1, f1, lens1, focus, ease, shake, roll = cam.pending
            f1 = f1 or end
            cam.move(f0, loc, aim, "hold")
            if loc1 is not None or aim1 is not None:
                cam.move(f1, loc1 if loc1 is not None else loc, aim1 if aim1 is not None else aim, ease)
            if lens1:
                cam.lens(f0, cam.data.lens)
                cam.lens(f1, lens1, ease)
            if focus is not None:
                cam.focus(f0, focus)
            if shake:
                cam.handheld(shake)
            if roll:
                cam.roll(f0, roll, "hold")
            m = self.scene.timeline_markers.new(cam.obj.name, frame=f0)
            m.camera = cam.obj
        if self.shots:
            self.scene.camera = self.shots[0][1].obj

    # ---- bake everything into Blender actions (one key per frame, linear)
    def bake(self):
        self._finish_shots()
        steps = {}
        for idb, path, f in self.steps:
            steps.setdefault((idb, path), set()).add(f)
        by_id = {}
        for (idb, path, idx), ch in self.tracks.items():
            if ch.keys or ch.layers or ch.mlayers:
                by_id.setdefault(idb, []).append((path, idx, ch))
        frames = list(range(1, self.frames + 1))
        for idb, lst in by_id.items():
            act = bpy.data.actions.new("a_" + idb.name)
            slot = act.slots.new(id_type=idb.id_type, name=idb.name)
            layer = act.layers.new("L")
            strip = layer.strips.new(type="KEYFRAME")
            cb = strip.channelbag(slot, ensure=True)
            if idb.animation_data is None:
                idb.animation_data_create()
            idb.animation_data.action = act
            idb.animation_data.action_slot = slot
            for path, idx, ch in lst:
                k = self.scale.get((idb, path, idx), 1.0)
                st = steps.get((idb, path), ())
                pts = []
                prev = None
                for f in frames:
                    v = ch.eval(f) * k
                    if f in st and prev is not None:
                        pts.append((f - 0.002, prev))
                    pts.append((f, v))
                    prev = v
                if path in ("hide_render", "hide_viewport"):
                    pts = [(f, 1.0 if v > 0.5 else 0.0) for f, v in pts]
                fc = cb.fcurves.new(path, index=idx)
                fc.keyframe_points.add(len(pts))
                flat = [x for p in pts for x in p]
                fc.keyframe_points.foreach_set("co", flat)
                fc.keyframe_points.foreach_set("interpolation", [1] * len(pts))   # LINEAR
                fc.update()


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.curves, bpy.data.actions):
        for x in list(coll):
            coll.remove(x)
    _MATS.clear()
    _FONTS.clear()


# ------------------------------------------------------------------ nodes (animated transforms)
class Node:
    """wrapper around an object with keyable loc / rot (deg) / scale"""

    def __init__(self, S, obj):
        self.S, self.obj = S, obj

    def _set(self, path, f, vals, ease, deg=False):
        for i, v in enumerate(vals):
            if v is not None:
                self.S.ch(self.obj, path, i, deg=deg).key(f, v, ease)
        return self

    def loc(self, f, x=None, y=None, z=None, ease="io"):
        return self._set("location", f, (x, y, z), ease)

    def rot(self, f, x=None, y=None, z=None, ease="io"):
        return self._set("rotation_euler", f, (x, y, z), ease, deg=True)

    def scl(self, f, x=None, y=None, z=None, ease="io"):
        if y is None and z is None and x is not None:
            y = z = x
        return self._set("scale", f, (x, y, z), ease)

    def lch(self, i):
        return self.S.ch(self.obj, "location", i)

    def rch(self, i):
        return self.S.ch(self.obj, "rotation_euler", i, deg=True)

    def sch(self, i):
        return self.S.ch(self.obj, "scale", i)

    def cut(self, f):
        """mark frame f as a hard jump for all transform channels (no motion blur streak)"""
        for p in ("location", "rotation_euler", "scale"):
            self.S.step(self.obj, p, f)
        return self

    def show(self, f_on=None, f_off=None, deep=True):
        objs = [self.obj] + (list(self.obj.children_recursive) if deep else [])
        for o in objs:
            if o.type != "EMPTY":
                self.S.vis(o, f_on, f_off)
        return self

    def pop(self, f, dur=7, to=1.0):
        """pop in with overshoot (scale 0 -> to)"""
        s0 = 0.001
        if f > 1:
            self.scl(f - 1, s0, s0, s0, "hold")
        self.scl(f, s0, s0, s0, "hold")
        self.scl(f + dur, to, to, to, "back")
        return self

    def unpop(self, f, dur=5):
        cur = self.sch(0).last(f)
        self.scl(f, cur, cur, cur)
        self.scl(f + dur, 0.001, 0.001, 0.001, "in")
        return self

    def world(self):
        bpy.context.view_layer.update()
        return self.obj.matrix_world.translation.copy()


def empty(name, loc=(0, 0, 0), parent=None, rot=None):
    o = bpy.data.objects.new(name, None)
    o.empty_display_size = 0.05
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    if rot:
        o.rotation_euler = [math.radians(a) for a in rot]
    if parent is not None:
        o.parent = parent.obj if isinstance(parent, Node) else parent
    return o


def _obj(name, me, loc, rot, parent, mats):
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]):
        if m is not None:
            me.materials.append(m if not isinstance(m, str) else mat(m))
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    if rot:
        o.rotation_euler = [math.radians(a) for a in rot]
    if parent is not None:
        o.parent = parent.obj if isinstance(parent, Node) else parent
    return o


def _finish(bm, name, smooth_shade=True, paint=None):
    for f in bm.faces:
        f.smooth = smooth_shade
        if paint:
            f.material_index = paint(f.calc_center_median())
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def ell(name, r, loc=(0, 0, 0), m=None, parent=None, rot=None, seg=40, paint=None, origin=(0, 0, 0), warp=None):
    """ellipsoid with radii r; origin = offset of the mesh relative to the object origin; warp(co)->co"""
    if isinstance(r, (int, float)):
        r = (r, r, r)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1.0,
                              matrix=Matrix.Translation(V(origin)) @ Matrix.Diagonal(V(r)).to_4x4())
    if warp:
        for v in bm.verts:
            v.co = V(warp(v.co))
    return _obj(name, _finish(bm, name, paint=paint), loc, rot, parent, m)


def capsule(name, p0, p1, r0, r1=None, m=None, parent=None, seg=24, flat=1.0):
    """tapered capsule from p0 to p1 (in parent space); object origin at p0; flat<1 flattens local Y"""
    p0, p1 = V(p0), V(p1)
    r1 = r0 if r1 is None else r1
    d = p1 - p0
    L = d.length
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1.0)
    for v in bm.verts:
        if v.co.z >= 0:
            v.co = V((v.co.x * r1, v.co.y * r1 * flat, v.co.z * r1 + L))
        else:
            v.co = V((v.co.x * r0, v.co.y * r0 * flat, v.co.z * r0))
    q = V((0, 0, 1)).rotation_difference(d.normalized()) if L > 1e-6 else None
    if q:
        bmesh.ops.transform(bm, matrix=q.to_matrix().to_4x4(), verts=bm.verts)
    return _obj(name, _finish(bm, name), p0, None, parent, m)


def box(name, size, loc=(0, 0, 0), m=None, parent=None, rot=None, bevel=0.008, seg=3, origin=(0, 0, 0), paint=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(V(origin)) @ Matrix.Diagonal(V(size)).to_4x4())
    if bevel > 0:
        b = min(bevel, min(size) * 0.45)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, segments=seg, profile=0.5, affect="EDGES")
    o = _obj(name, _finish(bm, name, smooth_shade=bevel > 0, paint=paint), loc, rot, parent, m)
    return o


def cyl(name, r, h, loc=(0, 0, 0), m=None, parent=None, rot=None, r2=None, seg=48, bevel=0.004, origin=(0, 0, 0)):
    """cylinder/cone along Z, centred; r2 = top radius"""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r if r2 is None else r2,
                          depth=h, matrix=Matrix.Translation(V(origin)))
    if bevel > 0:
        rim = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6 and len(e.link_faces) == 2
               and any(len(f.verts) > 4 for f in e.link_faces)]
        if rim:
            bmesh.ops.bevel(bm, geom=rim, offset=min(bevel, h * 0.4), segments=2, profile=0.5, affect="EDGES")
    me = _finish(bm, name)
    o = _obj(name, me, loc, rot, parent, m)
    autosmooth(o)
    return o


def autosmooth(o, angle=40):
    try:
        md = o.modifiers.new("smooth", "NODES")
        o.modifiers.remove(md)
    except Exception:
        pass
    me = o.data
    try:
        me.set_sharp_from_angle(angle=math.radians(angle))
    except Exception:
        pass


def torus(name, R, r, loc=(0, 0, 0), m=None, parent=None, rot=None, seg=48, rseg=12, arc=1.0, flat=1.0):
    """torus in the XY plane; arc<1 = partial ring (starts at angle 0); flat scales the tube along Z"""
    bm = bmesh.new()
    n = max(3, int(seg * arc))
    rings = []
    for i in range(n + (0 if arc >= 1 else 1)):
        a = i / n * math.tau * arc
        ring = []
        for j in range(rseg):
            b = j / rseg * math.tau
            rr = R + r * math.cos(b)
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), r * math.sin(b) * flat)))
        rings.append(ring)
    m_ = len(rings)
    for i in range(m_ if arc >= 1 else m_ - 1):
        a, b = rings[i], rings[(i + 1) % m_]
        for j in range(rseg):
            bm.faces.new((a[j], b[j], b[(j + 1) % rseg], a[(j + 1) % rseg]))
    if arc < 1:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    return _obj(name, _finish(bm, name), loc, rot, parent, m)


def lathe(name, profile, loc=(0, 0, 0), m=None, parent=None, rot=None, seg=48):
    """revolve a profile [(r, z), ...] around Z (closed at the ends where r == 0)"""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(i / seg * math.tau), r * math.sin(i / seg * math.tau), z))
                          for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new((a[0], b[j], b[i]))
            elif len(b) == 1:
                bm.faces.new((a[i], a[j], b[0]))
            else:
                bm.faces.new((a[i], a[j], b[j], b[i]))
    o = _obj(name, _finish(bm, name), loc, rot, parent, m)
    autosmooth(o, 50)
    return o


def plane(name, w, h, loc=(0, 0, 0), m=None, parent=None, rot=None, origin=(0, 0, 0)):
    """plane in XZ (faces -Y), UV 0..1"""
    bm = bmesh.new()
    ox, oy, oz = origin
    vs = [bm.verts.new((x * w / 2 + ox, oy, z * h / 2 + oz)) for x, z in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new("UVMap")
    for lp, co in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp[uv].uv = co
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return _obj(name, me, loc, rot, parent, m)


def tube(name, pts, r, m=None, parent=None, loc=(0, 0, 0), rot=None, cyclic=False, res=12, taper=None):
    """smooth tube along points (bezier-ish NURBS); taper = list of radius factors per point"""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 4
    cu.resolution_u = res
    cu.use_fill_caps = True
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (*p, 1.0)
        if taper:
            sp.points[i].radius = taper[i]
    sp.use_cyclic_u = cyclic
    sp.use_endpoint_u = not cyclic
    sp.order_u = min(4, len(pts))
    if m is not None:
        cu.materials.append(m if not isinstance(m, str) else mat(m))
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    if rot:
        o.rotation_euler = [math.radians(a) for a in rot]
    if parent is not None:
        o.parent = parent.obj if isinstance(parent, Node) else parent
    return o


_FONTS = {}


def text(name, body, size=0.1, m=None, loc=(0, 0, 0), parent=None, rot=(90, 0, 0), extrude=0.004, font=FONT_BOLD,
         align="CENTER", valign="CENTER", bevel=0.0, spacing=1.0, width=None, line=1.0):
    """3D text; default orientation: readable from -Y (standing upright)"""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.align_x, cu.align_y = align, valign
    cu.space_character = spacing
    cu.space_line = line
    if font:
        if font not in _FONTS:
            _FONTS[font] = bpy.data.fonts.load(font)
        cu.font = _FONTS[font]
    if width:
        cu.text_boxes[0].width = width
    if m is not None:
        cu.materials.append(m if not isinstance(m, str) else mat(m))
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = [math.radians(a) for a in rot]
    if parent is not None:
        o.parent = parent.obj if isinstance(parent, Node) else parent
    return o


def subsurf(o, lv=1):
    md = o.modifiers.new("sub", "SUBSURF")
    md.levels = md.render_levels = lv
    return o


def join(objs, name=None):
    """merge mesh objects into the first one (keeps materials)"""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    if name:
        objs[0].name = name
    return objs[0]


# ------------------------------------------------------------------ materials
_MATS = {}


def _new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    if b is None:
        nt.nodes.clear()
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(b.outputs[0], out.inputs[0])
    return m, nt, b


def _set(b, **kw):
    for k, v in kw.items():
        if k in b.inputs:
            b.inputs[k].default_value = v


def mat(name, color=None, rough=0.5, metal=0.0, emit=0.0, emit_color=None, sss=0.0, sheen=0.0, coat=0.0,
        alpha=1.0, spec=0.5, trans=0.0, ior=1.45):
    """cached principled material; mat("name") returns an existing one"""
    if name in _MATS:
        return _MATS[name]
    if color is None:
        raise KeyError(name)
    m, nt, b = _new_mat(name)
    c = srgb(color)
    _set(b, **{"Base Color": c, "Roughness": rough, "Metallic": metal, "Subsurface Weight": sss,
               "Subsurface Scale": 0.03, "Sheen Weight": sheen, "Sheen Roughness": 0.45, "Coat Weight": coat,
               "Coat Roughness": 0.08, "Alpha": alpha, "Specular IOR Level": spec, "Transmission Weight": trans,
               "IOR": ior})
    if "Subsurface Radius" in b.inputs:
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.6, 0.45)
    if emit:
        _set(b, **{"Emission Color": srgb(emit_color or color), "Emission Strength": emit})
    m.diffuse_color = c
    _MATS[name] = m
    return m


def felt(name, color, fuzz=1.0, rough=0.9, sss=0.12, scale=260.0, bump=0.12, tint="#FFFFFF"):
    """soft flocked/felt toy surface: sheen + fine noise bump + a little subsurface"""
    if name in _MATS:
        return _MATS[name]
    m, nt, b = _new_mat(name)
    c = srgb(color)
    _set(b, **{"Base Color": c, "Roughness": rough, "Sheen Weight": 0.75 * fuzz, "Sheen Roughness": 0.35,
               "Subsurface Weight": sss, "Subsurface Scale": 0.04, "Specular IOR Level": 0.25})
    if "Sheen Tint" in b.inputs:
        b.inputs["Sheen Tint"].default_value = srgb(tint)
    if "Subsurface Radius" in b.inputs:
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.75, 0.6)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 3.0
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.002
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = c
    _MATS[name] = m
    return m


def emit(name, color, strength=3.0):
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = srgb(color)
    e.inputs["Strength"].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    m.diffuse_color = srgb(color)
    _MATS[name] = m
    return m


def glass(name="glass", tint="#F4F8FF", gloss=0.015):
    """cheap lens glass: mostly transparent with a glossy reflection"""
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = srgb(tint)
    gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.03
    fr = nt.nodes.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.5
    mp = nt.nodes.new("ShaderNodeMath")
    mp.operation = "MULTIPLY_ADD"
    mp.inputs[1].default_value = 0.35
    mp.inputs[2].default_value = gloss
    mx = nt.nodes.new("ShaderNodeMixShader")
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(fr.outputs[0], mp.inputs[0])
    nt.links.new(mp.outputs[0], mx.inputs[0])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(gl.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], o.inputs[0])
    _MATS[name] = m
    return m


def image_mat(name, path, emit_strength=0.0, alpha=True, rough=0.6, tint=None):
    """image texture material (UV). emit_strength>0: self-lit screen/slide"""
    if name in _MATS:
        return _MATS[name]
    m, nt, b = _new_mat(name)
    img = bpy.data.images.load(str(path), check_existing=True)
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = img
    tx.extension = "CLIP"
    nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
    _set(b, Roughness=rough)
    if emit_strength:
        nt.links.new(tx.outputs["Color"], b.inputs["Emission Color"])
        _set(b, **{"Emission Strength": emit_strength})
    if alpha:
        nt.links.new(tx.outputs["Alpha"], b.inputs["Alpha"])
        try:
            m.surface_render_method = "DITHERED"
        except Exception:
            pass
    _MATS[name] = m
    return m


def wood(name, c1="#B98A5A", c2="#8A5E38", scale=6.0, rough=0.45, coat=0.25):
    if name in _MATS:
        return _MATS[name]
    m, nt, b = _new_mat(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale * 0.08, scale)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.0
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Distortion"].default_value = 1.2
    rp = nt.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].color = srgb(c2)
    rp.color_ramp.elements[0].position = 0.3
    rp.color_ramp.elements[1].color = srgb(c1)
    rp.color_ramp.elements[1].position = 0.7
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"])
    nt.links.new(rp.outputs["Color"], b.inputs["Base Color"])
    _set(b, **{"Roughness": rough, "Coat Weight": coat, "Coat Roughness": 0.15})
    m.diffuse_color = srgb(c1)
    _MATS[name] = m
    return m


# ------------------------------------------------------------------ camera
class Cam:
    def __init__(self, S, name, lens=50, fstop=2.8):
        self.S = S
        self.data = bpy.data.cameras.new(name)
        self.data.lens = lens
        self.data.sensor_width = 36
        self.data.clip_start, self.data.clip_end = 0.05, 300
        self.data.dof.use_dof = fstop is not None
        if fstop is not None:
            self.data.dof.aperture_fstop = fstop
        self.obj = bpy.data.objects.new(name, self.data)
        S.scene.collection.objects.link(self.obj)
        self.rig = empty(name + "_rig")             # carries position and aim; the camera only rolls inside it
        self.obj.parent = self.rig
        self.aim = empty(name + "_aim")
        self.foc = empty(name + "_focus")
        tt = self.rig.constraints.new("TRACK_TO")
        tt.target, tt.track_axis, tt.up_axis = self.aim, "TRACK_NEGATIVE_Z", "UP_Y"
        self.data.dof.focus_object = self.aim
        self.n, self.na, self.nf = Node(S, self.rig), Node(S, self.aim), Node(S, self.foc)
        S.cams.append(self)

    def move(self, f, loc=None, aim=None, ease="io"):
        if loc is not None:
            self.n.loc(f, *loc, ease=ease)
        if aim is not None:
            self.na.loc(f, *aim, ease=ease)
        return self

    def roll(self, f, deg, ease="io"):
        """tilt the horizon (degrees, positive = clockwise in the picture)"""
        self.S.ch(self.obj, "rotation_euler", 2, 0.0, deg=True).key(f, -deg, ease)
        return self

    def lens(self, f, mm, ease="io"):
        self.S.ch(self.data, "lens", 0).key(f, mm, ease)
        return self

    def fstop(self, f, v, ease="io"):
        self.S.ch(self.data.dof, "aperture_fstop", 0).key(f, v, ease)
        return self

    def focus(self, f, p, ease="io"):
        """focus on a point (separate from the aim point)"""
        self.data.dof.focus_object = self.foc
        if isinstance(p, Node):
            p = p.world()
        self.nf.loc(f, *p, ease=ease)
        return self

    def handheld(self, amp=0.01, speed=1.0):
        ph = [self.S.rng.uniform(0, 100) for _ in range(6)]
        for i in range(3):
            self.n.lch(i).add(lambda f, i=i: amp * (math.sin(f * 0.11 * speed + ph[i]) * 0.6
                                                    + math.sin(f * 0.047 * speed + ph[i + 3]) * 0.4))
        return self


# ------------------------------------------------------------------ lights / world
def area(name, loc, aim=(0, 0, 0), power=300, size=2.0, color="#FFFFFF", size_y=None, spread=None, parent=None):
    li = bpy.data.lights.new(name, "AREA")
    li.energy = power
    li.color = srgb(color)[:3]
    li.shape = "RECTANGLE" if size_y else "SQUARE"
    li.size = size
    if size_y:
        li.size_y = size_y
    if spread is not None:
        li.spread = math.radians(spread)
    o = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (V(aim) - V(loc)).to_track_quat("-Z", "Y").to_euler()
    if parent is not None:
        o.parent = parent.obj if isinstance(parent, Node) else parent
    return o


def spot(name, loc, aim=(0, 0, 0), power=800, angle=40, blend=0.4, color="#FFFFFF", radius=0.05):
    li = bpy.data.lights.new(name, "SPOT")
    li.energy = power
    li.color = srgb(color)[:3]
    li.spot_size = math.radians(angle)
    li.spot_blend = blend
    li.shadow_soft_size = radius
    o = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (V(aim) - V(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


def point(name, loc, power=50, color="#FFFFFF", radius=0.1, parent=None):
    li = bpy.data.lights.new(name, "POINT")
    li.energy = power
    li.color = srgb(color)[:3]
    li.shadow_soft_size = radius
    o = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    if parent is not None:
        o.parent = parent.obj if isinstance(parent, Node) else parent
    return o


def sun(name, rot=(50, 0, 30), power=3.0, color="#FFF1DD", angle=3.0):
    li = bpy.data.lights.new(name, "SUN")
    li.energy = power
    li.color = srgb(color)[:3]
    li.angle = math.radians(angle)
    o = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = [math.radians(a) for a in rot]
    return o


def world(top="#BFD4EA", bottom="#F2E8DA", strength=0.6):
    """soft vertical gradient environment"""
    w = bpy.data.worlds.new("world")
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sx = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.3
    mr.inputs["From Max"].default_value = 0.7
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.inputs["A"].default_value = srgb(bottom)
    mx.inputs["B"].default_value = srgb(top)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], sx.inputs[0])
    nt.links.new(sx.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], mx.inputs["Factor"])
    nt.links.new(mx.outputs["Result"], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs[0])
    bpy.context.scene.world = w
    return bg


def fog(name, size, loc, density=0.02, color="#FFFFFF", aniso=0.6):
    """volume box for light beams"""
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    vs = nt.nodes.new("ShaderNodeVolumeScatter")
    vs.inputs["Color"].default_value = srgb(color)
    vs.inputs["Density"].default_value = density
    vs.inputs["Anisotropy"].default_value = aniso
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(vs.outputs[0], o.inputs["Volume"])
    b = box(name, size, loc, m, bevel=0)
    b.visible_shadow = False
    return b, vs


# ------------------------------------------------------------------ render
QUALITY = {  # samples, adaptive threshold, share of the frame size, motion blur
    "draft": (24, 0.08, 0.5, False),       # whole-film preview and contact sheets
    "preview": (48, 0.05, 0.5, False),
    "film": (40, 0.05, 1.0, True),         # the film render (denoised)
    "final": (128, 0.02, 1.0, True),       # hero stills
}


def gpu_setup():
    """Cycles on the graphics card: OptiX, else CUDA / HIP / Metal / oneAPI, else the CPU. Returns the name used."""
    try:
        pr = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        return "CPU"
    for kind in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            pr.compute_device_type = kind
            pr.get_devices()
        except (TypeError, RuntimeError):
            continue
        if any(d.type == kind for d in pr.devices):
            for d in pr.devices:
                d.use = d.type == kind
            return kind
    return "CPU"


EEVEE_SAMPLES = {"draft": 16, "preview": 32, "film": 64, "final": 128}


def eevee_setup(S, quality="film"):
    """EEVEE (rasteriser with screen-space ray tracing): much faster than Cycles, but light from glowing surfaces,
    soft bounce light and subsurface are approximations - an experimental second engine, the look is tuned for Cycles"""
    sc = S.scene
    for name in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = name
            break
        except TypeError:
            continue
    S.device = "EEVEE"
    ev = sc.eevee
    for k, v in (("taa_render_samples", EEVEE_SAMPLES[quality]), ("use_raytracing", True), ("use_shadows", True),
                 ("shadow_ray_count", 3), ("shadow_step_count", 12), ("use_gtao", True), ("use_bloom", False),
                 ("use_volumetric_shadows", True), ("volumetric_samples", 64), ("motion_blur_steps", 3),
                 ("use_fast_gi", True), ("fast_gi_method", "GLOBAL_ILLUMINATION"), ("ray_tracing_method", "SCREEN")):
        try:
            setattr(ev, k, v)
        except (AttributeError, TypeError):
            pass
    try:
        ev.ray_tracing_options.resolution_scale = "1"
        ev.ray_tracing_options.use_denoise = True
    except (AttributeError, TypeError):
        pass
    for o in sc.objects:                                  # soft shadows from every light
        if o.type == "LIGHT":
            try:
                o.data.use_shadow = True
                o.data.use_shadow_jitter = True
                o.data.shadow_jitter_overblur = 10
            except AttributeError:
                pass


def render_setup(S, quality="film", res=(1920, 1080), transparent=False, engine="cycles"):
    sc = S.scene
    if engine == "eevee":
        eevee_setup(S, quality)
        q = QUALITY[quality]
        sc.render.resolution_x, sc.render.resolution_y = int(res[0]), int(res[1])
        sc.render.resolution_percentage = int(100 * q[2])
        sc.render.film_transparent = transparent
        sc.render.use_motion_blur = q[3]
        sc.render.motion_blur_shutter = 0.35
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGB"
        sc.render.image_settings.compression = 15
        sc.view_settings.view_transform = "AgX"
        try:
            sc.view_settings.look = "AgX - Medium High Contrast"
        except Exception:
            pass
        return
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    S.device = gpu_setup()
    cy.device = "CPU" if S.device == "CPU" else "GPU"
    q = QUALITY[quality]
    cy.samples, cy.adaptive_threshold = q[0], q[1]
    cy.use_adaptive_sampling = True
    cy.use_denoising = True
    cy.denoiser = "OPENIMAGEDENOISE"
    try:
        cy.denoising_use_gpu = True
    except Exception:
        pass
    cy.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces = 6, 3, 3
    cy.transmission_bounces, cy.transparent_max_bounces, cy.volume_bounces = 4, 8, 0
    cy.caustics_reflective = cy.caustics_refractive = False
    cy.sample_clamp_indirect = 6.0
    cy.blur_glossy = 1.0
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = int(res[0]), int(res[1])
    sc.render.resolution_percentage = int(100 * q[2])
    sc.render.film_transparent = transparent
    sc.render.use_motion_blur = q[3]
    sc.render.motion_blur_shutter = 0.35
    try:
        sc.render.motion_blur_position = "START"
    except Exception:
        pass
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.compression = 15
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    cy.filter_width = 1.5


def render(S, out_dir, frames=None, stills=None, overwrite=False):
    """frames: (f0, f1) range -> out_dir/f_####.png ; stills: list of frames"""
    import time
    sc = S.scene
    out_dir = Path(out_dir)
    if not out_dir.is_absolute():               # Blender resolves a relative render path against the drive root
        out_dir = PROJECT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = stills if stills else range(frames[0], frames[1] + 1)
    t0 = time.time()
    n = 0
    for f in todo:
        png = out_dir / f"f_{f:04d}.png"
        if png.exists() and not stills and not overwrite:
            continue
        sc.frame_set(f)
        sc.render.filepath = str(png)
        bpy.ops.render.render(write_still=True)
        n += 1
        print(f"RENDERED {S.name} {f} ({(time.time() - t0) / n:.2f}s/frame)", flush=True)


def load_json(rel):
    """a JSON file of the project (path relative to the project folder)"""
    return json.loads((PROJECT / rel).read_text(encoding="utf-8"))
