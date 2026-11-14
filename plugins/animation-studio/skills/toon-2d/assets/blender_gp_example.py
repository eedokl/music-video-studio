"""Blender 5.2 headless: Pip as a Grease Pencil drawing (frame by frame, "on twos", pressure + line boil) in front of
painted layers as image planes at real depths; the camera dollies in. Saves a .blend the artist can open and keep
drawing in with a tablet.

Usage (via the launcher, which finds Blender through the machine config key "blender"):
  uv run --no-project python <toon-2d>/scripts/blender_run.py <toon-2d>/assets/blender_gp_example.py -- \
      --layers <folder with 01_sky.png ... 06_foreground.png> --out <folder> [--still 40] [--nobg]
The layer folder is what paint_clearing.py paints (or your own Krita layers with the same names).
Result: <out>/pip_gp.blend, <out>/frames/pip_####.png (or <out>/still_<n>.png)
"""
import math
import random
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return args[args.index(name) + 1] if name in args else default


OUT = Path(arg("--out", ".")).resolve()
LAYERS = Path(arg("--layers", OUT / "layers")).resolve()
STILL = int(arg("--still")) if arg("--still") else None

FPS, END = 24, 96
FOV = 30


def srgb(r, g, b, a=1.0):
    """Hex/sRGB colour -> linear (Blender material colours are linear)."""
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b), a)


INK = srgb(0.23, 0.14, 0.10)

# ---------------- scene ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, END
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 16
sc.view_settings.view_transform = "Standard"     # colours as painted, no Filmic/AgX look
sc.render.image_settings.file_format = "PNG"
world = bpy.data.worlds.new("World")
world.color = (0.9, 0.9, 0.85)
sc.world = world

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.sensor_fit = "VERTICAL"
cam.data.angle = math.radians(FOV)
cam.rotation_euler = (math.pi / 2, 0, 0)        # looks along +Y
sc.collection.objects.link(cam)
sc.camera = cam
tan_half = math.tan(math.radians(FOV / 2))


# ---------------- painted layers as image planes ----------------
def image_plane(name, file, dist, overscan=1.13, add=False):
    img = bpy.data.images.load(str(LAYERS / file))
    h = 2 * dist * tan_half * overscan
    w = h * img.size[0] / img.size[1]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new()
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = c
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.surface_render_method = "BLENDED"
    nt = mat.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    emit = nt.nodes.new("ShaderNodeEmission")
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader") if not add else nt.nodes.new("ShaderNodeAddShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    if add:   # light rays: brighten
        mult = nt.nodes.new("ShaderNodeMixRGB"); mult.blend_type = "MULTIPLY"; mult.inputs[0].default_value = 1
        nt.links.new(tex.outputs["Color"], mult.inputs[1]); nt.links.new(tex.outputs["Alpha"], mult.inputs[2])
        nt.links.new(mult.outputs[0], emit.inputs["Color"])
        nt.links.new(transp.outputs[0], mix.inputs[0]); nt.links.new(emit.outputs[0], mix.inputs[1])
    else:
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        nt.links.new(transp.outputs[0], mix.inputs[1]); nt.links.new(emit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (0, dist, 0)
    sc.collection.objects.link(obj)
    return obj


cam.data.clip_end = 500
if "--nobg" not in args:
    image_plane("Sky", "01_sky.png", 120)
    image_plane("Far trees", "02_far_trees.png", 70)
    image_plane("Middle trees", "03_mid_trees.png", 36)
    image_plane("Meadow", "05_meadow_path.png", 26)
    image_plane("Light rays", "04_light_rays.png", 22, add=True)
    image_plane("Leaves front", "06_foreground.png", 9, overscan=1.4)

# ---------------- Grease Pencil materials ----------------
def gp_mat(name, stroke=None, fill=None):
    m = bpy.data.materials.new(name)
    bpy.data.materials.create_gpencil_data(m)
    g = m.grease_pencil
    # Blender 5.2: show_stroke/show_fill are deprecated no-ops - visibility via alpha
    g.color = stroke if stroke else (0, 0, 0, 0)
    g.fill_color = fill if fill else (0, 0, 0, 0)
    return m


MATS = {
    "body": gp_mat("Body", INK, srgb(0.98, 0.71, 0.25)),
    "belly": gp_mat("Belly", None, srgb(1.0, 0.89, 0.63)),
    "white": gp_mat("Eye", INK, srgb(1, 1, 1)),
    "pupil": gp_mat("Pupil", None, INK),
    "cheek": gp_mat("Cheek", None, srgb(0.94, 0.5, 0.48, 0.55)),
    "line": gp_mat("Line", INK, None),
    "red": gp_mat("Antenna ball", INK, srgb(0.93, 0.35, 0.31)),
}
MAT_IDX = {k: i for i, k in enumerate(MATS)}

gp = bpy.data.grease_pencils.new("Pip")
for m in MATS.values():
    gp.materials.append(m)
layer = gp.layers.new("Pip drawing")
pip_obj = bpy.data.objects.new("Pip", gp)
sc.collection.objects.link(pip_obj)

# Pip stands on the path: same depth as the meadow (just in front), same size as in Synfig
DIST = 25.9
UNIT = 2 * 26 * tan_half * 1.13 / 9          # 1 Synfig unit in Blender units (at meadow depth)
K = UNIT * 0.76                              # Pip local unit -> world
pip_obj.location = (0, DIST, -3.0 * UNIT)    # feet on the Synfig ground y = -3


# ---------------- drawing helpers ----------------
def hermite(p0, p1, m0, m1, n):
    out = []
    for i in range(n):
        t = i / n
        h00, h10, h01, h11 = 2*t**3 - 3*t**2 + 1, t**3 - 2*t**2 + t, -2*t**3 + 3*t**2, t**3 - t**2
        out.append((h00*p0[0] + h10*m0[0] + h01*p1[0] + h11*m1[0], h00*p0[1] + h10*m0[1] + h01*p1[1] + h11*m1[1]))
    return out


BODY = [((0, 0), (2.6, 0)), ((1.32, 1.05), (0, 2.2)), ((0, 2.95), (-2.0, 0)), ((-1.32, 1.05), (0, -2.2))]


def body_points(n=18):
    pts = []
    for i in range(4):
        (p0, m0), (p1, m1) = BODY[i], BODY[(i + 1) % 4]
        pts += hermite(p0, p1, m0, m1, n)
    return pts


def ellipse(cx, cy, rx, ry, n=20):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


class Pen:
    """Draws strokes into a Grease Pencil drawing - 'hand-drawn': line jitter (new per drawing = 'boil')
    and pressure (varying stroke width)."""
    fill_counter = 0

    def __init__(self, drawing, seed, squash):
        self.d, self.rng, self.sx, self.sy = drawing, random.Random(seed), squash ** -0.8, squash

    def xform(self, x, y):
        # XZ plane = the default Grease Pencil drawing plane of Blender ("Front")
        return (x * self.sx * K, 0.0, y * self.sy * K)

    def stroke(self, pts, mat, radius=0.045, cyclic=False, boil=0.012, pressure=True):
        self.d.add_strokes([len(pts)])
        s = self.d.strokes[len(self.d.strokes) - 1]
        ph = self.rng.uniform(0, 6.3)
        for i, (x, y) in enumerate(pts):
            jx, jy = self.rng.gauss(0, boil), self.rng.gauss(0, boil)
            s.points[i].position = self.xform(x + jx, y + jy)
            w = 0.7 + 0.5 * abs(math.sin(i / len(pts) * math.pi * 1.5 + ph)) if pressure else 1.0
            if not cyclic and pressure:
                w *= min(1.0, 4 * i / len(pts), 4 * (len(pts) - 1 - i) / len(pts)) * 0.8 + 0.2   # tapered ends
            s.points[i].radius = radius * K * w
        s.cyclic = cyclic
        s.material_index = MAT_IDX[mat]
        s.fill_opacity = 1.0
        # IMPORTANT (Blender 5.2, undocumented): without fill_id != 0 Grease Pencil draws no fill.
        # Blender's drawing tools set it automatically; from Python set it yourself.
        Pen.fill_counter += 1
        s.fill_id = Pen.fill_counter


# ---------------- motion (one drawing per 2 frames) ----------------
def ease(u):
    return u * u * (3 - 2 * u)


def pose(f):
    """Height (Pip units), squash, blink, look."""
    h, sq = 0.0, 1.0 + 0.025 * math.sin(f / 30 * 2 * math.pi)
    if 18 <= f < 28:
        sq = 1 - 0.18 * ease((f - 18) / 10)                      # anticipation
    elif 28 <= f < 44:
        u = (f - 28) / 16
        h = 4 * 1.8 * u * (1 - u)                                # jump (parabola)
        sq = 1.25 - 0.3 * min(u * 2, 1) + (0.2 if u > 0.75 else 0)   # stretch up, stretch before landing
    elif 44 <= f < 47:
        sq = 0.7                                                 # landing: squash
    elif 47 <= f < 58:
        u = (f - 47) / 11
        sq = 1 + 0.15 * math.cos(u * math.pi * 2.5) * (1 - u)    # settle
    blink = 0.1 if f in (70, 71, 72) else 1.0
    look = (0.0, 0.1) if 24 <= f < 50 else (0.08, -0.02)
    return h, sq, blink, look


def draw_pip(drawing, f):
    h, sq, blink, (lx, ly) = pose(f)
    pen = Pen(drawing, seed=f, squash=sq)
    lift = h / sq   # height is added before the squash
    up = lambda pts: [(x, y + lift) for x, y in pts]
    pen.stroke(up([(0, 2.85), (0.02, 3.3), (0.05, 3.75)]), "line", radius=0.05)                 # antenna
    pen.stroke(up(ellipse(0.05, 3.88, 0.2, 0.2, 14)), "red", radius=0.04, cyclic=True)
    pen.stroke(up(body_points()), "body", radius=0.06, cyclic=True)                          # body
    pen.stroke(up(ellipse(0, 0.95, 0.75, 0.6, 22)), "belly", cyclic=True, boil=0.008)           # belly
    for sx in (-1, 1):
        pen.stroke(up(ellipse(sx * 0.82, 1.62, 0.2, 0.12, 12)), "cheek", cyclic=True, boil=0.0)
        pen.stroke(up(ellipse(sx * 0.42, 2.12, 0.29, 0.36 * blink, 16)), "white", radius=0.035, cyclic=True)
        if blink > 0.5:
            pen.stroke(up(ellipse(sx * 0.42 + lx, 2.12 + ly, 0.14, 0.17, 12)), "pupil", cyclic=True, boil=0.004)
    mouth = [(-0.28, 1.72), (-0.14, 1.6), (0, 1.56), (0.14, 1.6), (0.28, 1.72)]
    if 28 <= f < 50:
        pen.stroke(up(ellipse(0, 1.62, 0.12, 0.16, 12)), "pupil", cyclic=True)              # "Oh!" mouth
    else:
        pen.stroke(up(mouth), "line", radius=0.04)
    drawing.tag_positions_changed()   # needed so Blender recomputes the fills (triangulation)


for f in range(1, END + 1, 2):                     # on twos: a new drawing every 2nd frame
    fr = layer.frames.new(f)
    draw_pip(fr.drawing, f)

# ---------------- camera: slowly in + sideways ----------------
for f, (x, y, z) in ((1, (-1.2, 0, 0.25)), (40, (-0.8, 1.0, 0.1)), (END, (0.3, 4.0, -0.3))):
    cam.location = (x, y, z)
    cam.keyframe_insert("location", frame=f)

OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "pip_gp.blend"))
(OUT / "frames").mkdir(exist_ok=True)
if STILL:
    sc.frame_set(STILL)
    sc.render.filepath = str(OUT / f"still_{STILL}.png")
    bpy.ops.render.render(write_still=True)
else:
    sc.render.filepath = str(OUT / "frames" / "pip_")
    bpy.ops.render.render(animation=True)
