"""A 2D rig figure (SVG, characters convention) becomes a rounded 3D toon figure in Blender.

Every filled shape of the SVG is "inflated" like a balloon (round cross-section from the distance to its outline:
an ellipse becomes an ellipsoid, an arm a tube), coloured with its fill, toon-shaded with an ink outline (inverted
hull, thickness from its stroke). Stroke-only lines (brows, glasses, headset) become tubes. Shapes that lie on top
of an earlier, bigger shape (eyes, pupils, cheeks, the mouth) hug its surface as thin decals. Drawing order is kept:
in the flat state every part is a sheet in painter order, so frame 0 matches the 2D drawing and can crossfade.
The orthographic camera reproduces the 2D framing exactly (SVG px -> screen px).

Two modes in one file:
  launcher (normal Python): reads the SVG, builds the meshes (numpy/scipy), takes the GPU lock, runs Blender
  inside Blender: builds objects, toon materials, outlines, shape keys and the actions, renders RGBA frames

Usage:
  uv run --no-project --with svgelements --with numpy --with scipy --with pillow python figure_3d.py fig3d.json
  uv run ... python figure_3d.py --figure lia --out lia3d --actions morph:24,turn:23,pop:4 [--still 30]
  uv run ... python figure_3d.py crossfade --flat <out>/flat_2d.png --frames3d <out> --out <dir> [--fade 6]

fig3d.json (paths relative to it; all keys optional except figure):
  {"figure": "lia",                      # bundled name (tim, lia, fips) or an SVG; "feet" [x, y] for own SVGs
   "out": "lia3d", "width": 1280, "height": 720,
   "px_per_svg_px": 1.0, "feet_screen": [640, 640],   # where the SVG feet point lands in the picture
   "mouth": "o",                         # o | smile | none - drawn at pivot_mund when the SVG has no mouth
   "depth": 0.8, "part_depth": {"haare_hinten": 0.6},  # roundness (1 = as deep as wide), per part id
   "decal_depth": 0.12, "outline": 1.0,  # outline = factor on stroke width / 2
   "skip": ["pupille_x"],                # part ids left out
   "wrap": ["#4a3426"],                  # ids / fill colours that also cover the back (hair drawn as a front cap)
   "actions": [{"action": "morph", "frames": 24, "order": "bottom_up", "last": ["haare_hinten", "#6b4cc0"],
                "spin": 12, "lift": 0.1},
               {"action": "turn", "frames": 23, "degrees": 360, "lift": 0.6},
               {"action": "pop", "frames": 4},
               {"action": "hold", "frames": 12}],
   "flat_2d": true}                      # also export the 2D drawing in the same framing (crossfade input)
Actions: morph (parts round one after another; order bottom_up | top_down | a list of part ids; "last" ids or fill
colours go last; decals follow the part they sit on), turn (degrees about the vertical axis through the feet,
lift in units of 100 SVG px), pop (grows 18 % and vanishes), hold (keeps the pose; "flat": true goes back flat).
Output: <out>/f.NNNN.png (RGBA), <out>/figure_3d.blend (for an artist), <out>/flat_2d.png, contact sheet.
"""
import json
import math
import sys
from pathlib import Path

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

INK = "#2b1d14"
UNIT = 100.0                      # SVG px per Blender unit


# =========================================================================== launcher side
def _load_cfg(argv):
    import argparse
    ap = argparse.ArgumentParser(description="2D rig figure -> rounded 3D toon figure in Blender.")
    ap.add_argument("config", nargs="?", help="fig3d.json")
    ap.add_argument("--figure")
    ap.add_argument("--out")
    ap.add_argument("--actions", help="short form, e.g. morph:24,turn:23,pop:4")
    ap.add_argument("--still", type=int, help="render only this frame (quick look)")
    ap.add_argument("--no-render", action="store_true", help="only build the meshes / the .blend")
    a = ap.parse_args(argv)
    if a.config:
        path = Path(a.config).resolve()
        cfg = json.loads(path.read_text(encoding="utf-8"))
        base = path.parent
    else:
        cfg, base = {}, Path.cwd()
    if a.figure:
        cfg["figure"] = a.figure
    if a.out:
        cfg["out"] = a.out
    if a.actions:
        cfg["actions"] = [{"action": k, "frames": int(v)} for k, v in (x.split(":") for x in a.actions.split(","))]
    if "figure" not in cfg:
        ap.error("figure missing (config or --figure)")
    cfg.setdefault("out", "figure3d")
    cfg.setdefault("actions", [{"action": "morph", "frames": 24}, {"action": "turn", "frames": 24},
                               {"action": "hold", "frames": 8}])
    return cfg, base, a


def hex_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _shapes(svg_file, skip):
    """Walk the normalized SVG: -> list of dicts (part ids, fill, stroke, width, opacity, polylines) + pivots."""
    import numpy as np
    from svgelements import SVG, Group, Shape, Path as SPath
    svg = SVG.parse(str(svg_file), reify=True)
    out, piv = [], {}

    def color(c):
        if c is None or c.value is None:
            return None
        return ("#%02x%02x%02x" % (c.red, c.green, c.blue), c.alpha / 255)

    def walk(node, parts):
        for el in node:
            eid = el.values.get("id") if hasattr(el, "values") else None
            if isinstance(el, Group):
                named = eid and not eid.startswith(("layer", "svg"))
                if named and eid in skip:
                    continue
                walk(el, parts + [eid] if named else parts)
                continue
            if not isinstance(el, Shape):
                continue
            if eid and eid.startswith("pivot_"):
                bb = el.bbox()
                piv[eid[6:]] = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
                continue
            path = el if isinstance(el, SPath) else SPath(el)
            op = float(el.values.get("opacity", 1) or 1)
            fill, stroke = color(el.fill), color(el.stroke)
            sw = el.implicit_stroke_width if hasattr(el, "implicit_stroke_width") else el.stroke_width
            polys = []
            for sp in path.as_subpaths():
                sp = SPath(sp)
                try:
                    L = sp.length()
                except Exception:
                    L = 0
                if not L:
                    continue
                n = max(24, int(L / 1.5))
                pts = sp.npoint(np.linspace(0, 1, n))
                closed = bool(abs(complex(*pts[0]) - complex(*pts[-1])) < 1e-3) or any(
                    type(s).__name__ == "Close" for s in sp)
                polys.append((pts.tolist(), closed))
            if polys:
                out.append({"parts": parts, "id": eid or (parts[-1] if parts else "shape"),
                            "fill": fill and (fill[0], fill[1] * op), "stroke": stroke and (stroke[0], stroke[1] * op),
                            "sw": float(sw or 0), "polys": polys})
    walk(svg, [])
    return out, piv


def build_meshes(cfg, base, work):
    """SVG -> meshes with a flat (painter order) and a round state, in SVG px relative to the feet."""
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy import ndimage
    from scipy.spatial import Delaunay
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _studio
    _studio.use("toon-2d", "characters")
    from figures import FIGURES, svg_path
    from svg2sif import normalize
    name = cfg["figure"]
    info = FIGURES.get(str(name).lower(), {})
    src = svg_path(name) if str(name).lower() in FIGURES else (base / name)
    feet = tuple(cfg.get("feet", info.get("feet", (200, 590))))
    plain = normalize(src, out_dir=work / "cache")
    shapes, piv = _shapes(plain, set(cfg.get("skip", [])))
    import xml.etree.ElementTree as ET
    root = ET.parse(plain).getroot()
    vb = [float(v) for v in (root.get("viewBox") or f"0 0 {root.get('width')} {root.get('height')}").split()]
    SS = 2                                                  # raster supersampling
    Wr, Hr = int(vb[2] * SS) + 2, int(vb[3] * SS) + 2
    # default mouth (the rig leaves it to lip sync)
    mouth = cfg.get("mouth", "o")
    if "mund" in piv and mouth != "none" and not any("mund" in s["parts"] for s in shapes):
        mx, my = piv["mund"]
        hp = [p for p in ("kopf",) if any(p in s["parts"] for s in shapes)]
        if mouth == "o":
            t = np.linspace(0, 2 * np.pi, 48)
            pts = np.c_[mx + 12 * np.cos(t), my + 6 + 15 * np.sin(t)].tolist()
            shapes.append({"parts": hp + ["mund"], "id": "mund", "fill": ("#7a1f2b", 1.0), "stroke": (INK, 1.0),
                           "sw": 4.0, "polys": [(pts, True)]})
        else:
            t = np.linspace(0.15 * np.pi, 0.85 * np.pi, 20)
            pts = np.c_[mx + 22 * np.cos(t), my - 14 + 18 * np.sin(t)].tolist()
            shapes.append({"parts": hp + ["mund"], "id": "mund", "fill": None, "stroke": (INK, 1.0), "sw": 5.0,
                           "polys": [(pts, False)]})

    depth = float(cfg.get("depth", 0.8))
    part_depth = cfg.get("part_depth", {})
    decal_k = float(cfg.get("decal_depth", 0.12))
    wrap_ids = set(cfg.get("wrap", []))                     # ids / fill colours that wrap round the back (hair)
    F = np.full((Hr, Wr), np.nan, np.float32)               # front surface so far (SVG px)
    BK = np.full((Hr, Wr), np.nan, np.float32)              # back surface so far
    OWN = np.full((Hr, Wr), -1, np.int32)                   # which mesh is in front there
    COL = np.zeros((Hr, Wr, 3), np.float32)
    meshes = []

    def raster(polys, closed_fill=True, width=0):
        im = Image.new("L", (Wr, Hr), 0)
        d = ImageDraw.Draw(im)
        for pts, closed in polys:
            q = [(x * SS, y * SS) for x, y in pts]
            if closed_fill and len(q) > 2:
                d.polygon(q, fill=255)
            if width:
                d.line(q, fill=255, width=max(1, int(width * SS)), joint="curve")
        return np.asarray(im) > 127

    def sample(arr, xs, ys):
        xi = np.clip(np.round(np.asarray(xs) * SS).astype(int), 0, Wr - 1)
        yi = np.clip(np.round(np.asarray(ys) * SS).astype(int), 0, Hr - 1)
        return arr[yi, xi]

    for order, sh in enumerate(shapes):
        label = f"{sh['parts'][-1] if sh['parts'] else 'figure'} {order:02d}"
        k_part = depth
        for p in sh["parts"]:
            k_part = float(part_depth.get(p, k_part))
        fill = sh["fill"] if sh["fill"] and sh["fill"][1] >= 0.3 else None
        closed_polys = [(p, c) for p, c in sh["polys"] if c or fill]
        if fill and closed_polys:
            M = raster(closed_polys)
            if M.sum() < 4:
                continue
            under = ~np.isnan(F) & M
            cover = under.sum() / M.sum()
            owners = OWN[under]
            parent = int(np.bincount(owners[owners >= 0]).argmax()) if owners.size and (owners >= 0).any() else -1
            parent_area = meshes[parent]["area"] if parent >= 0 else 0
            decal = cover >= 0.9 and parent >= 0 and M.sum() < 0.35 * parent_area
            dist = ndimage.distance_transform_edt(M) / SS     # SVG px to the outline
            dmax = float(dist.max())
            prof = np.sqrt(np.clip(dist * (2 * dmax - dist), 0, None))   # round cross-section (sphere for a circle)
            kk = decal_k if decal else k_part
            # vertices: outline samples + interior grid
            g = float(np.clip(dmax / 5, 1.5, 6.0))
            bpts = []
            for pts, _ in closed_polys:
                pts = np.asarray(pts)
                seg = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
                if seg[-1] <= 0:
                    continue
                n = max(12, int(seg[-1] / (g * 0.8)))
                s = np.linspace(0, seg[-1], n, endpoint=False)
                bpts.append(np.c_[np.interp(s, seg, pts[:, 0]), np.interp(s, seg, pts[:, 1])])
            bpts = np.concatenate(bpts)
            ys, xs = np.mgrid[vb[1]:vb[1] + vb[3]:g, vb[0]:vb[0] + vb[2]:g]
            gx, gy = xs.ravel(), ys.ravel()
            keep = sample(M, gx, gy) & (sample(dist, gx, gy) > g * 0.45)
            ipts = np.c_[gx[keep], gy[keep]]
            P = np.r_[bpts, ipts]
            nb = len(bpts)
            if len(P) < 3:
                continue
            tri = Delaunay(P).simplices
            cen = P[tri].mean(1)
            tri = tri[sample(M, cen[:, 0], cen[:, 1])]
            pr = sample(prof, P[:, 0], P[:, 1]) * kk
            pr[:nb] = 0.0
            if decal:
                base_z = sample(np.nan_to_num(F, nan=0.0), P[:, 0], P[:, 1])
                zf, zb = base_z + pr + 0.6, base_z - 1.5
                wraps = ((M.sum() > 0.2 * parent_area and meshes[parent]["kind"] == "round")
                         or fill[0] in wrap_ids or bool(wrap_ids & set(sh["parts"])))
                if wraps:                                  # a big cap (hair on the head): wraps round the back
                    back = sample(np.nan_to_num(BK, nan=0.0), P[:, 0], P[:, 1])
                    zb = np.minimum(zb, back - pr - 0.6)
            else:
                inner = M & (prof >= 0.3 * prof.max()) & ~np.isnan(F)
                c = float(np.percentile((F - prof * kk)[inner], 90)) + 1.0 if inner.any() else 0.0
                if not inner.any() and (under.any()):
                    c = float(np.nanmax(F[under])) * 0.5
                zf, zb = c + pr, c - pr
                wraps = fill[0] in wrap_ids or bool(wrap_ids & set(sh["parts"]))
                if wraps and under.any():
                    back = sample(np.nan_to_num(BK, nan=0.0), P[:, 0], P[:, 1])
                    zb = np.minimum(zb, back - pr * 0.5 - 0.6)
            ni = len(P) - nb
            verts_xy = np.r_[P, P[nb:]]
            z_round = np.r_[zf, zb[nb:]]
            back_idx = np.r_[np.arange(nb), np.arange(nb, len(P)) + ni]
            faces = np.r_[tri, back_idx[tri][:, ::-1]]
            col = fill[0]
            if fill[1] < 0.99:                             # translucent fill: mix with what is under it
                under_col = COL[M & ~np.isnan(F)].mean(0) if under.any() else np.array(hex_rgb("#ffffff"))
                mixed = np.array(hex_rgb(col)) * fill[1] + under_col * (1 - fill[1])
                col = "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in mixed)
            # update the front field with this mesh's front surface
            zfield = (np.nan_to_num(F, nan=0.0) + prof * kk + 0.6) if decal else (c + prof * kk)
            newF = np.where(M, np.fmax(np.nan_to_num(F, nan=-1e9), zfield), F)
            F = np.where(M, newF, F).astype(np.float32)
            if decal:
                bfield = (np.nan_to_num(BK, nan=0.0) - prof * kk - 0.6) if wraps else None
            elif wraps:
                bfield = np.fmin(c - prof * kk, np.nan_to_num(BK, nan=1e9) - prof * kk * 0.5 - 0.6)
            else:
                bfield = c - prof * kk
            if bfield is not None:
                BK = np.where(M, np.fmin(np.nan_to_num(BK, nan=1e9), bfield), BK).astype(np.float32)
            OWN[M] = len(meshes)
            COL[M] = hex_rgb(col)
            outline = (sh["stroke"][0], sh["sw"]) if sh["stroke"] and sh["sw"] > 0 else None
            meshes.append({"name": "mund" if sh["id"] == "mund" else label, "parts": sh["parts"], "kind": "decal" if decal else "round",
                           "color": col, "outline": outline, "order": order, "area": int(M.sum()),
                           "parent": parent, "cy": float(P[:, 1].mean()), "cx": float(P[:, 0].mean()),
                           "xy": verts_xy.tolist(), "z": z_round.tolist(), "faces": faces.tolist()})
        # strokes without fill (or open paths): tubes on the surface
        if sh["stroke"] and sh["sw"] > 0 and (not fill or sh["stroke"][0] != (fill or ("",))[0]):
            if fill:                                       # a filled shape's outline is the inverted hull
                continue
            r = sh["sw"] / 2
            for pts, closed in sh["polys"]:
                pts = np.asarray(pts)
                seg = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
                if seg[-1] <= 0:
                    continue
                n = max(6, int(seg[-1] / 3))
                s = np.linspace(0, seg[-1], n)
                C = np.c_[np.interp(s, seg, pts[:, 0]), np.interp(s, seg, pts[:, 1])]
                base_z = sample(np.nan_to_num(F, nan=0.0), C[:, 0], C[:, 1])
                zc = base_z + r * 0.6
                T = np.gradient(C, axis=0)
                T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
                N2 = np.c_[-T[:, 1], T[:, 0]]
                ring = 8
                vx, vy, vz = [], [], []
                for i in range(n):
                    for j in range(ring):
                        a = 2 * math.pi * j / ring
                        vx.append(C[i, 0] + N2[i, 0] * r * math.cos(a))
                        vy.append(C[i, 1] + N2[i, 1] * r * math.cos(a))
                        vz.append(zc[i] + r * math.sin(a))
                faces = []
                for i in range(n - 1):
                    for j in range(ring):
                        a0, a1 = i * ring + j, i * ring + (j + 1) % ring
                        faces.append([a0, a1, a1 + ring, a0 + ring])
                cap0, cap1 = list(range(ring))[::-1], [(n - 1) * ring + j for j in range(ring)]
                faces += [cap0, cap1]
                M = raster([(C.tolist(), False)], closed_fill=False, width=sh["sw"])
                ow = OWN[M]
                parent = int(np.bincount(ow[ow >= 0]).argmax()) if (ow >= 0).any() else -1
                zfield = np.nan_to_num(F, nan=0.0) + r * 1.6
                F = np.where(M, np.fmax(np.nan_to_num(F, nan=-1e9), zfield), F).astype(np.float32)
                OWN[M] = len(meshes)
                meshes.append({"name": label + " line", "parts": sh["parts"], "kind": "tube",
                               "color": sh["stroke"][0], "outline": None, "order": order, "area": int(M.sum()),
                               "parent": parent,
                               "cy": float(C[:, 1].mean()), "cx": float(C[:, 0].mean()),
                               "xy": np.c_[vx, vy].tolist(), "z": list(map(float, vz)), "faces": faces,
                               "zc": float(np.mean(zc))})
    # tubes/decals: parent = the mesh they sit on (for the morph order)
    for i, m in enumerate(meshes):
        if m["parent"] == i:
            m["parent"] = -1
    return {"feet": feet, "viewbox": vb, "pivots": piv, "meshes": meshes, "svg": str(src), "plain": str(plain)}


def export_flat_2d(cfg, data, out):
    """The 2D drawing in exactly the 3D framing (Inkscape PNG export) + the default mouth -> flat_2d.png."""
    import subprocess
    from PIL import Image, ImageDraw
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _studio
    _studio.use("toon-2d")
    import config
    W, H = cfg.get("width", 1280), cfg.get("height", 720)
    s = float(cfg.get("px_per_svg_px", 1.0))
    fx, fy = cfg.get("feet_screen", (W / 2, H * 0.89))
    vb = data["viewbox"]
    tmp = out / "_svg.png"
    subprocess.run([config.need("inkscape"), data["svg"], "--export-type=png", f"--export-filename={tmp}",
                    f"--export-width={round(vb[2] * s * 2)}"], check=True, capture_output=True)
    fig = Image.open(tmp).convert("RGBA").resize((round(vb[2] * s), round(vb[3] * s)), Image.LANCZOS)
    tmp.unlink()
    for m in data["meshes"]:
        if m["name"] == "mund" and "mund" in data["pivots"]:
            mx, my = data["pivots"]["mund"]
            d = ImageDraw.Draw(fig)
            if m["kind"] == "tube":
                d.arc(((mx - 22) * s, (my - 32) * s, (mx + 22) * s, (my + 4) * s), 27, 153, fill=INK, width=round(5 * s))
            else:
                d.ellipse(((mx - 12) * s, (my - 9) * s, (mx + 12) * s, (my + 21) * s), fill="#7a1f2b", outline=INK,
                          width=max(1, round(4 * s)))
            break
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    feet = data["feet"]
    img.alpha_composite(fig, (round(fx - (feet[0] - vb[0]) * s), round(fy - (feet[1] - vb[1]) * s)))
    img.save(out / "flat_2d.png")
    return out / "flat_2d.png"


def crossfade(argv):
    """2D frames/still over the 3D frames, fading out over the first --fade frames."""
    import argparse
    from PIL import Image
    ap = argparse.ArgumentParser(description="Crossfade the 2D drawing into the 3D frames.")
    ap.add_argument("--flat", required=True, help="2D still (flat_2d.png) or a pattern 2d/f.%%04d.png")
    ap.add_argument("--frames3d", required=True, help="folder with f.NNNN.png from figure_3d")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fade", type=int, default=6)
    ap.add_argument("--background", help="optional background image (RGB) under both")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    frames = sorted(Path(a.frames3d).glob("f.[0-9][0-9][0-9][0-9].png"))
    bg = Image.open(a.background).convert("RGBA") if a.background else None
    for i, f in enumerate(frames):
        img = Image.open(f).convert("RGBA")
        if bg is not None:
            img = Image.alpha_composite(bg.resize(img.size), img)
        if i < a.fade:
            flat = Image.open(a.flat % i if "%" in a.flat else a.flat).convert("RGBA").resize(img.size)
            al = 1 - i / a.fade
            flat.putalpha(flat.getchannel("A").point(lambda v: int(v * al)))
            img.alpha_composite(flat)
        img.save(out / f.name)
    print(f"crossfade: {len(frames)} frames -> {out}")


def launcher(argv):
    import subprocess
    if argv and argv[0] == "crossfade":
        return crossfade(argv[1:])
    cfg, base, a = _load_cfg(argv)
    out = (base / cfg["out"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    data = build_meshes(cfg, base, out)
    cfg["_base"] = str(base)
    (out / "meshes.json").write_text(json.dumps({"cfg": cfg, "data": data}), encoding="utf-8")
    kinds = {}
    for m in data["meshes"]:
        kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
    print(f"meshes: {len(data['meshes'])} ({', '.join(f'{v} {k}' for k, v in kinds.items())})")
    if cfg.get("flat_2d", True):
        print("2D in the same framing:", export_flat_2d(cfg, data, out))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _studio
    _studio.use()
    import config
    from gpu_lock import acquire
    acquire("figure_3d", model="blender")
    args = ["--", str(out / "meshes.json")] + (["--still", str(a.still)] if a.still is not None else []) + \
           (["--no-render"] if a.no_render else [])
    r = subprocess.run([config.need("blender"), "-b", "--factory-startup", "--python-exit-code", "1",
                        "--python", str(Path(__file__).resolve()), *args])
    if r.returncode:
        raise SystemExit("Blender failed")
    if a.still is None and not a.no_render:
        try:
            _studio.use("toon-2d")
            from render import contact_sheet, pick_frames
            n = len(list(out.glob("f.[0-9][0-9][0-9][0-9].png")))
            contact_sheet(str(out / "f.%04d.png"), out.with_name(out.name + "_contact.png"), pick_frames("auto", n))
            print("contact sheet:", out.with_name(out.name + "_contact.png"))
        except SystemExit as e:
            print("(no contact sheet:", e, ")")


# =========================================================================== Blender side
def lin(h):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in hex_rgb(h)) + (1,)


def blender_main(argv):
    import bpy
    meshes_json = Path(argv[0])
    still = int(argv[argv.index("--still") + 1]) if "--still" in argv else None
    no_render = "--no-render" in argv
    J = json.loads(meshes_json.read_text(encoding="utf-8"))
    cfg, data = J["cfg"], J["data"]
    out = meshes_json.parent
    W, H = cfg.get("width", 1280), cfg.get("height", 720)
    s = float(cfg.get("px_per_svg_px", 1.0))
    fx, fy = cfg.get("feet_screen", (W / 2, H * 0.89))
    feet = data["feet"]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.render.fps = cfg.get("fps", 24)

    cam = bpy.data.cameras.new("camera")
    cam.type = "ORTHO"
    cam.ortho_scale = max(W, H) / (UNIT * s)
    co = bpy.data.objects.new("camera", cam)
    co.location = (0, 0, 40)
    cam.clip_start, cam.clip_end = 20, 60
    sc.collection.objects.link(co)
    sc.camera = co
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(-35), math.radians(-30), 0)      # from the front, top left
    sc.collection.objects.link(sun)

    mats = {}

    def toon(hexcol, shade=0.72):
        if hexcol in mats:
            return mats[hexcol]
        m = bpy.data.materials.new(hexcol)
        m.use_nodes = True
        nt = m.node_tree
        for nd in list(nt.nodes):
            nt.nodes.remove(nd)
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
        s2r = nt.nodes.new("ShaderNodeShaderToRGB")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        b = lin(hexcol)
        ramp.color_ramp.elements[0].color = tuple(c * shade for c in b[:3]) + (1,)
        ramp.color_ramp.elements[1].position = 0.12
        ramp.color_ramp.elements[1].color = b
        emi = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(dif.outputs[0], s2r.inputs[0])
        nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], emi.inputs["Color"])
        nt.links.new(emi.outputs[0], o.inputs[0])
        mats[hexcol] = m
        return m

    def ink_mat(hexcol):
        key = "ink" + hexcol
        if key in mats:
            return mats[key]
        m = bpy.data.materials.new(key)
        m.use_nodes = True
        m.use_backface_culling = True
        n = m.node_tree.nodes
        n.remove(n["Principled BSDF"])
        e = n.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = lin(hexcol)
        m.node_tree.links.new(e.outputs[0], n["Material Output"].inputs[0])
        mats[key] = m
        return m

    ROOT = bpy.data.objects.new("Figure", None)
    ROOT.location = ((fx - W / 2) / (UNIT * s), (H / 2 - fy) / (UNIT * s), 0)
    sc.collection.objects.link(ROOT)
    OUTL = float(cfg.get("outline", 1.0))
    FULL = {}                                   # full outline thickness per object
    objs = []
    for idx, m in enumerate(data["meshes"]):
        xy, z, faces = m["xy"], m["z"], m["faces"]
        flat_z = idx * 1.2                     # painter order; wide enough against z-fighting
        zc = m.get("zc", sum(z) / len(z))
        flat = [((x - feet[0]) / UNIT, (feet[1] - y) / UNIT,
                 (flat_z + ((zz - zc) * 0.04 if m["kind"] == "tube" else 0)) / UNIT) for (x, y), zz in zip(xy, z)]
        rnd = [((x - feet[0]) / UNIT, (feet[1] - y) / UNIT, zz / UNIT) for (x, y), zz in zip(xy, z)]
        me = bpy.data.meshes.new(m["name"])
        me.from_pydata(flat, [], faces)
        me.update()
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(m["name"], me)
        sc.collection.objects.link(ob)
        ob.parent = ROOT
        me.materials.append(toon(m["color"]))
        if m["outline"]:
            me.materials.append(ink_mat(m["outline"][0]))
            sol = ob.modifiers.new("outline", "SOLIDIFY")
            sol.thickness = m["outline"][1] / 2 * OUTL / UNIT
            sol.offset, sol.use_flip_normals, sol.material_offset = 1, True, 1
            FULL[ob.name] = sol.thickness
        ob.shape_key_add(name="flat")
        k = ob.shape_key_add(name="round")
        for i, c in enumerate(rnd):
            k.data[i].co = c
        objs.append((ob, k, m))

    # ------------------------------------------------ actions
    def key_root(f, spin, lift, scale):
        ROOT.rotation_euler = (0, math.radians(spin), 0)
        ROOT.location.y = (H / 2 - fy) / (UNIT * s) + lift
        ROOT.scale = (scale, scale, scale)
        for path in ("rotation_euler", "location", "scale"):
            ROOT.keyframe_insert(path, frame=f)

    def key_shape(ob, k, v, frame):
        """Shape key 'round' + outline thickness (0 while flat: the hull would poke through the sheets)."""
        k.value = v
        k.keyframe_insert("value", frame=frame)
        sol = ob.modifiers.get("outline")
        if sol:
            sol.thickness = FULL[ob.name] * min(max(v, 0.0), 1.0)
            sol.keyframe_insert("thickness", frame=frame)

    for ob, k, m in objs:
        key_shape(ob, k, 0.0, 0)
    f, spin, lift, scale = 0, 0.0, 0.0, 1.0
    key_root(0, spin, lift, scale)
    for act in cfg["actions"]:
        n = int(act.get("frames", 24))
        kind = act["action"]
        if kind == "morph":
            order = act.get("order", "bottom_up")
            last = set(act.get("last", []))
            ms = [m for _, _, m in objs]

            def own(i):                       # decals/tubes take the stage of the part they sit on
                seen = set()
                while ms[i]["kind"] in ("decal", "tube") and ms[i]["parent"] >= 0 and i not in seen:
                    seen.add(i)
                    i = ms[i]["parent"]
                return i

            def is_last(m):
                return m["color"] in last or any(p in last for p in m["parts"])

            ys = [m["cy"] for m in ms]
            lo, hi = min(ys), max(ys)
            span = max(1, n - 8)
            stage = []
            for i, m in enumerate(ms):
                j = own(i)
                if is_last(ms[j]) or is_last(m):
                    t = span
                elif isinstance(order, list):
                    ids = [p for p in order]
                    hit = [ids.index(p) for p in ms[j]["parts"] if p in ids]
                    t = round(min(hit) / max(1, len(ids) - 1) * (span - 2)) if hit else span - 1
                else:
                    u = (hi - ms[j]["cy"]) / (hi - lo + 1e-9)          # 0 = lowest part (feet)
                    if order == "top_down":
                        u = 1 - u
                    t = round(u * (span - 2))
                stage.append(t)
            for (ob, k, m), t in zip(objs, stage):
                for ff, v in ((f + t, 0.0), (f + t + 4, 1.25), (f + t + 7, 1.0)):
                    key_shape(ob, k, v, ff)
            f += n
            spin += act.get("spin", 0)
            lift = act.get("lift", lift)
            key_root(f, spin, lift, scale)
        elif kind == "turn":
            f += n
            spin += act.get("degrees", 360)
            lift = act.get("lift", lift)
            key_root(f, spin, lift, scale)
        elif kind == "pop":
            key_root(f + max(1, n // 2), spin, lift, scale * 1.18)
            f += n
            scale = 0.0
            key_root(f, spin, lift, 0.0)
        elif kind == "hold":
            if act.get("flat"):
                for ob, k, m in objs:
                    key_shape(ob, k, 1.0, f)
                    key_shape(ob, k, 0.0, f + n)
            f += n
            key_root(f, spin, act.get("lift", lift), scale)
            lift = act.get("lift", lift)
        else:
            raise SystemExit(f"unknown action {kind}")
    sc.frame_start, sc.frame_end = 0, f
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "figure_3d.blend"))
    if no_render:
        return
    if still is not None:
        sc.frame_set(still)
        sc.render.filepath = str(out / f"still_{still:04d}.png")
        bpy.ops.render.render(write_still=True)
        print("still:", sc.render.filepath)
        return
    for p in out.glob("f.[0-9][0-9][0-9][0-9].png"):
        p.unlink()
    sc.render.filepath = str(out / "f.")
    bpy.ops.render.render(animation=True)
    print(f"figure_3d: {f} frames -> {out}")


if __name__ == "__main__":
    if IN_BLENDER:
        blender_main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    else:
        launcher(sys.argv[1:])
