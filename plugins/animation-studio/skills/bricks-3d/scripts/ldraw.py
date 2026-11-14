"""Small LDraw importer for Blender (runs inside Blender's Python: bpy + numpy only).

- reads .dat/.ldr recursively (line types 1, 3, 4; BFC winding incl. INVERTNEXT and mirrored matrices)
- high-resolution primitives from p/48 when present (rounder studs)
- studs without logos (the standard LDraw stud has none - keep it that way, no brand logos in films)
- one mesh per (part, colour, gap), shared by all instances; smooth shading by angle
- materials from LDConfig.ldr (Principled BSDF, ABS-like plastic)
- real size: 1 LDU = 0.4 mm; LDraw y-down / front -z  ->  Blender z-up / front -y

Library folder: config key `ldraw_dir` (env LDRAW_DIR or ~/.animation-studio/config.json). See
references/ldraw-setup.md for where to get the library.

Quality switches (set QUALITY before the first part() call), ideas after Renderbricker:
  gaps    LDU each brick shrinks per side -> visible seams between bricks (not on minifig parts)
  bevel   LDU radius of rounded edges (bevel modifier by angle)
  wobble  degrees / tenth LDU random offset per brick (hand-built look; not on minifig parts)
  abs     plastic material: slightly varying roughness, a little subsurface
"""
import math
import re
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402

LDU = 0.0004                                   # metres per LDraw unit
CONV = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))      # (x,y,z)_ld -> (x, z, -y)
S = Matrix.Scale(LDU, 4) @ CONV               # LDraw part space -> Blender mesh space
S_INV = S.inverted()

QUALITY = dict(gaps=0.0, bevel=0.0, wobble=0.0, abs=False)
MINIFIG = ("3626", "973", "3815", "3816", "3817", "3818", "3819", "3820", "3901", "12890", "14045", "62711", "62810",
           "40233", "87991", "92081", "3624", "18984", "21778", "64798", "11256")

_geo, _path, _mesh, _mat = {}, {}, {}, {}
_colours = None
_lib = None
_rng = np.random.default_rng(31)


def library():
    """LDraw library folder from the machine config; stops with a clear message if it is missing."""
    global _lib
    if _lib is None:
        v = config.get("ldraw_dir")
        if not v or not (Path(v) / "LDConfig.ldr").exists():
            raise SystemExit("LDraw library not found: set the config key ldraw_dir (folder with LDConfig.ldr, parts/, p/), "
                             "e.g. `python check_tools.py --set ldraw_dir=/path/to/ldraw` - see bricks-3d/references/"
                             "ldraw-setup.md")
        _lib = Path(v)
    return _lib


def seed_wobble(seed):
    """Make the hand-built wobble reproducible per film (creative seed)."""
    global _rng
    _rng = np.random.default_rng(int(seed))


# ------------------------------------------------------------------ files
def find(name):
    n = name.strip().replace("\\", "/").lower()
    if not n.endswith((".dat", ".ldr", ".mpd")):
        n += ".dat"
    if n in _path:
        return _path[n]
    L = library()
    cand = [L / "p" / "48" / n, L / "parts" / n, L / "p" / n, L / "models" / n, Path(n)]
    if n.startswith("48/"):
        cand.insert(0, L / "p" / n)
    for k in cand:
        if k.exists():
            _path[n] = k
            return k
    _path[n] = None
    return None


def matrix_from(t):
    x, y, z, a, b, c, d, e, f, g, h, i = map(float, t)
    return np.array([[a, b, c, x], [d, e, f, y], [g, h, i, z], [0, 0, 0, 1]], float)


def geometry(name):
    """Triangles of a file in its own space, winding CCW = outside. Colour 16 stays 16 (inherits)."""
    key = name.strip().replace("\\", "/").lower()
    if key in _geo:
        return _geo[key]
    p = find(key)
    if p is None:
        print(f"LDraw: missing {name}")
        _geo[key] = (np.zeros((0, 3, 3)), np.zeros(0, int))
        return _geo[key]
    tris, cols = [], []
    ccw, invert_next = True, False
    for row in p.read_text(encoding="utf-8", errors="replace").splitlines():
        t = row.split()
        if not t:
            continue
        if t[0] == "0":
            if len(t) >= 3 and t[1] == "BFC":
                w = [x.upper() for x in t[2:]]
                if "INVERTNEXT" in w:
                    invert_next = True
                if "CW" in w:
                    ccw = False
                if "CCW" in w:
                    ccw = True
            continue
        if t[0] == "1" and len(t) >= 15:
            col = int(t[1])
            m = matrix_from(t[2:14])
            st, sc = geometry(" ".join(t[14:]))
            if len(st):
                v = st @ m[:3, :3].T + m[:3, 3]
                if (np.linalg.det(m[:3, :3]) < 0) != invert_next:
                    v = v[:, ::-1, :]
                tris.append(v)
                cols.append(np.where(sc == 16, col, sc) if col != 16 else sc)
            invert_next = False
            continue
        if t[0] in ("3", "4"):
            col = int(t[1])
            pts = np.array(list(map(float, t[2:2 + 3 * int(t[0])])), float).reshape(-1, 3)
            for f in ([pts[[0, 1, 2]]] if t[0] == "3" else [pts[[0, 1, 2]], pts[[0, 2, 3]]]):
                tris.append((f if ccw else f[::-1])[None])
                cols.append(np.array([col]))
    res = (np.concatenate(tris), np.concatenate(cols).astype(int)) if tris else (np.zeros((0, 3, 3)), np.zeros(0, int))
    _geo[key] = res
    return res


# ------------------------------------------------------------------ materials
def colours():
    global _colours
    if _colours is None:
        _colours = {}
        for z in (library() / "LDConfig.ldr").read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.search(r"!COLOUR\s+(\S+)\s+CODE\s+(\d+)\s+VALUE\s+#([0-9A-Fa-f]{6})", z)
            if m:
                a = re.search(r"ALPHA\s+(\d+)", z)
                _colours[int(m.group(2))] = dict(name=m.group(1), hex=m.group(3), alpha=int(a.group(1)) if a else 255,
                                                 chrome="CHROME" in z, metal="METAL" in z, rubber="RUBBER" in z)
    return _colours


def srgb_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(code):
    """Linear RGB of an LDraw colour code."""
    f = colours().get(code, dict(hex="FF00FF"))
    return tuple(srgb_lin(int(f["hex"][i:i + 2], 16) / 255) for i in (0, 2, 4))


def material(code):
    if code in _mat:
        return _mat[code]
    f = colours().get(code, dict(name=f"c{code}", hex="FF00FF", alpha=255, chrome=False, metal=False, rubber=False))
    m = bpy.data.materials.new(f"LD_{code}_{f['name']}")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    col = rgb(code)
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = 0.6 if f["rubber"] else 0.22
    b.inputs["Specular IOR Level"].default_value = 0.5
    if QUALITY["abs"] and f["alpha"] == 255 and not (f["chrome"] or f["metal"] or f["rubber"]):
        nt = m.node_tree
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 900.0                 # fine blotches (fingerprints, moulding)
        nz.inputs["Detail"].default_value = 4.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = 0.16
        mr.inputs["To Max"].default_value = 0.34
        nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
        nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
        b.inputs["IOR"].default_value = 1.55
        b.inputs["Subsurface Weight"].default_value = 0.06
        b.inputs["Subsurface Scale"].default_value = 0.0006
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.8, 0.6)
    if f["chrome"] or f["metal"]:
        b.inputs["Metallic"].default_value = 1.0
        b.inputs["Roughness"].default_value = 0.15
    if f["alpha"] < 255:
        b.inputs["Transmission Weight"].default_value = 1.0
        b.inputs["Roughness"].default_value = 0.05
    m.diffuse_color = (*col, 1)
    _mat[code] = m
    return m


# ------------------------------------------------------------------ meshes + objects
def is_minifig(name):
    return Path(name).stem.lower().startswith(MINIFIG)


def mesh(name, colour, smooth_deg=35.0):
    gap = QUALITY["gaps"] if not is_minifig(name) else 0.0
    key = (name.lower(), colour, gap)
    if key in _mesh:
        return _mesh[key]
    tris, cols = geometry(name)
    cols = np.where(cols == 16, colour, cols)
    keep = cols != 24                                          # 24 = edge colour, lines are not rendered
    tris, cols = tris[keep], cols[keep]
    v = tris.reshape(-1, 3)
    if gap > 0 and len(v):                                     # shrink each side by `gap` LDU around the centre
        lo, hi = v.min(0), v.max(0)
        mid, ext = (lo + hi) / 2, np.maximum(hi - lo, 1e-6)
        v = mid + (v - mid) * np.maximum(ext - 2 * gap, ext * 0.5) / ext
    v = (np.c_[v, np.ones(len(v))] @ np.array(S).T)[:, :3]
    q = np.round(v / (LDU * 0.02)).astype(np.int64)            # weld at 0.02 LDU
    _, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    verts = v[first]
    faces = inv.reshape(-1, 3)
    ok = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    faces, cols = faces[ok], cols[ok]
    me = bpy.data.meshes.new(f"{Path(name).stem}_{colour}")
    me.from_pydata(verts.tolist(), [], faces.tolist())
    codes = sorted(set(cols.tolist()))
    for c in codes:
        me.materials.append(material(c))
    idx = {c: i for i, c in enumerate(codes)}
    me.polygons.foreach_set("material_index", np.array([idx[c] for c in cols.tolist()], np.int32))
    me.update()
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(smooth_deg))
    _mesh[key] = me
    return me


def to_blender(m_ld):
    """4x4 LDraw world matrix (numpy or Matrix) -> Blender matrix_world."""
    return S @ Matrix(np.asarray(m_ld).tolist()) @ S_INV


def part(name, colour, m_ld=None, objname=None, collection=None):
    """Place one LDraw part. m_ld = 4x4 LDraw matrix (T/RX/RY/RZ below)."""
    me = mesh(name, colour)
    ob = bpy.data.objects.new(objname or me.name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    m = np.eye(4) if m_ld is None else np.asarray(m_ld, float)
    if QUALITY["wobble"] > 0 and not is_minifig(name):         # hand-built: a hair crooked and shifted
        u = QUALITY["wobble"]
        w = _rng.uniform(-u, u, 3)
        d = _rng.uniform(-u * 0.1, u * 0.1, 3) * np.array([1, 0.3, 1])
        m = m @ T(*d) @ RY(w[1]) @ RX(w[0] * 0.4) @ RZ(w[2] * 0.4)
    ob.matrix_world = to_blender(m)
    if QUALITY["bevel"] > 0:
        b = ob.modifiers.new("Bevel", "BEVEL")
        b.width = QUALITY["bevel"] * LDU
        b.segments = 2
        b.limit_method = "ANGLE"
        b.angle_limit = math.radians(40)
        b.use_clamp_overlap = True
        b.harden_normals = True
    return ob


def set_quality(spec):
    """'gaps=0.2,bevel=0.3,wobble=0.6,abs=1' -> QUALITY"""
    for kv in (spec or "").split(","):
        if "=" in kv:
            k, v = kv.split("=")
            QUALITY[k.strip()] = (v.strip() == "1") if k.strip() == "abs" else float(v)


# ------------------------------------------------------------------ LDraw matrices (degrees)
def T(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def RX(g):
    c, s = math.cos(math.radians(g)), math.sin(math.radians(g))
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]], float)


def RY(g):
    c, s = math.cos(math.radians(g)), math.sin(math.radians(g))
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], float)


def RZ(g):
    c, s = math.cos(math.radians(g)), math.sin(math.radians(g))
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], float)
