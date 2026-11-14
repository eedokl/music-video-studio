# /// script
# requires-python = ">=3.12"
# dependencies = ["svgelements==1.9.6"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Inkscape SVG -> Synfig layers, keeping the group structure (= animatable parts).

Workflow for artists (Inkscape):
  - Draw every moving part as a group with a meaningful id (Object Properties > ID), e.g. head,
    wing_front, eye_l, beak_lower. Groups may be nested (eyes inside the head).
  - Pivot of a part: a small circle with id "pivot_<part>" inside the group (it is not drawn).
  - Circles, ellipses, rectangles and transformations are allowed - normalize() lets Inkscape turn
    everything into plain paths.

Usage:
    from svg2sif import normalize, load_svg, emit
    plain = normalize("bird.svg", out_dir="work")       # Inkscape CLI: objects -> paths
    root, pivots = load_svg(plain, scale=1/80, origin=(200, 380))   # SVG px -> Synfig units
    layers = emit(root, wrap={"wing_front": lambda kids, part: group(..., kids, origin=pivots[...], angle=...)})
Run as a script (test): python svg2sif.py bird.svg  -> bird_static.sif (unanimated, for comparison)

Requires: svgelements (declared in the PEP 723 header: `uv run svg2sif.py`) and Inkscape 1.x (see config.py).
"""
import subprocess
import sys
from pathlib import Path

from svgelements import (SVG, Arc, Close, CubicBezier, Group, Line, Move, Path as SPath,
                         QuadraticBezier, Shape)

import _studio  # noqa: E402
_studio.use()
import config
import derived
from sif import B, R, V, C, group


def normalize(svg_path, out_dir=None):
    """Turn all objects into paths with Inkscape -> <stem>_plain.svg (returns its path).

    out_dir: folder for the plain file (default: next to the source). Use it for SVGs bundled with
    the skill so nothing is written into the skill folder. Inkscape is skipped if the plain file
    was made from exactly this source content (studio-core derived.py - a content hash, not mtimes:
    a restored older SVG or a different SVG of the same name is normalized again).
    """
    src = Path(svg_path).resolve()
    if out_dir is not None:
        out = Path(out_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        dst = out / (src.stem + "_plain.svg")
    else:
        dst = src.with_name(src.stem + "_plain.svg")
    actions = "select-all:all;object-to-path;export-plain-svg"
    if derived.fresh(dst, [src], {"inkscape": actions}):
        return dst
    with derived.build(dst, [src], {"inkscape": actions}) as b:
        subprocess.run([config.need("inkscape"), str(src), "--actions=select-all:all;object-to-path;"
                        f"export-filename:{b.path.as_posix()};export-plain-svg;export-do"],
                       check=True, capture_output=True)
    return dst


class Part:
    def __init__(self, pid):
        self.id, self.items = pid, []   # items: Synfig layers (str) or Part, in drawing order

    def find(self, pid):
        if self.id == pid:
            return self
        for it in self.items:
            if isinstance(it, Part):
                hit = it.find(pid)
                if hit:
                    return hit
        return None


def _color(c, alpha=1.0):
    return C(c.red / 255, c.green / 255, c.blue / 255, (c.alpha / 255) * alpha)


def _bline_split(verts, loop):
    """verts: [(x, y, t_in(x,y), t_out(x,y))] - split tangents (corners possible)."""
    out = []
    for x, y, (ix, iy), (ox, oy) in verts:
        out.append(f"<entry><composite type=\"bline_point\"><point>{V(x, y)}</point><width>{R(1)}</width>"
                   f"<origin>{R(0.5)}</origin><split>{B(True)}</split><t1>{V(ix, iy)}</t1><t2>{V(ox, oy)}</t2>"
                   f"<split_radius>{B(True)}</split_radius><split_angle>{B(True)}</split_angle></composite></entry>")
    return f'<bline type="bline_point" loop="{"true" if loop else "false"}">{"".join(out)}</bline>'


def _subpaths(path, tf):
    """SVG path -> list of (verts, closed) in Synfig coordinates."""
    result = []
    for sp in path.as_subpaths():
        segs = []
        closed = False
        for seg in sp:
            if isinstance(seg, Move):
                continue
            if isinstance(seg, Close):
                closed = True
                if abs(seg.start - seg.end) > 1e-6:
                    segs.append((seg.start, seg.start, seg.end, seg.end))   # closing line
                continue
            if isinstance(seg, Line):
                segs.append((seg.start, seg.start, seg.end, seg.end))
            elif isinstance(seg, CubicBezier):
                segs.append((seg.start, seg.control1, seg.control2, seg.end))
            elif isinstance(seg, QuadraticBezier):
                c1 = seg.start + (seg.control - seg.start) * (2 / 3)
                c2 = seg.end + (seg.control - seg.end) * (2 / 3)
                segs.append((seg.start, c1, c2, seg.end))
            elif isinstance(seg, Arc):
                for cb in seg.as_cubic_curves():
                    segs.append((cb.start, cb.control1, cb.control2, cb.end))
        if not segs:
            continue
        if abs(segs[0][0] - segs[-1][3]) < 1e-6:
            closed = True
        pts = [tf(*s) for s in segs]   # 4 points per segment in Synfig coordinates
        verts = []
        n = len(pts)
        for i, (p0, c1, c2, p1) in enumerate(pts):
            # the incoming tangent at the start point comes from the previous segment
            if i > 0:
                _, _, pc2, pp1 = pts[i - 1]
                t_in = (3 * (pp1[0] - pc2[0]), 3 * (pp1[1] - pc2[1]))
            elif closed:
                _, _, pc2, pp1 = pts[-1]
                t_in = (3 * (pp1[0] - pc2[0]), 3 * (pp1[1] - pc2[1]))
            else:
                t_in = (3 * (c1[0] - p0[0]), 3 * (c1[1] - p0[1]))
            t_out = (3 * (c1[0] - p0[0]), 3 * (c1[1] - p0[1]))
            verts.append((p0[0], p0[1], t_in, t_out))
        if not closed:
            p0, c1, c2, p1 = pts[-1]
            t = (3 * (p1[0] - c2[0]), 3 * (p1[1] - c2[1]))
            verts.append((p1[0], p1[1], t, t))
        result.append((verts, closed))
    return result


def load_svg(svg_path, scale=1 / 80, origin=(0, 0)):
    """-> (root Part, pivots {part: (x, y)}) in Synfig coordinates (y up, origin = SVG point (0,0))."""
    ox, oy = origin

    def tf(*points):
        return [((p.x - ox) * scale, -(p.y - oy) * scale) for p in points]

    def tf4(a, b, c, d):
        return tf(a, b, c, d)

    svg = SVG.parse(str(svg_path), reify=True)
    pivots = {}

    def walk(node, part):
        for el in node:
            eid = el.values.get("id") if hasattr(el, "values") else None
            if isinstance(el, Group):
                if eid and not eid.startswith(("layer", "svg")) and eid != "fips_root":
                    child = Part(eid)
                    part.items.append(child)
                    walk(el, child)
                else:
                    walk(el, part)
                continue
            if not isinstance(el, Shape):
                continue
            if eid and eid.startswith("pivot_"):
                bb = el.bbox()
                cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
                pivots[eid[6:]] = ((cx - ox) * scale, -(cy - oy) * scale)
                continue
            path = SPath(el) if not isinstance(el, SPath) else el
            opacity = float(el.values.get("opacity", 1) or 1)
            subs = _subpaths(path, tf4)
            name = eid or part.id
            for verts, closed in subs:
                if el.fill is not None and el.fill.value is not None and closed:
                    part.items.append(f'<layer type="region" active="true" version="0.1" desc="{name}">'
                                      f'<param name="color">{_color(el.fill, opacity)}</param>'
                                      f'<param name="origin">{V(0, 0)}</param>'
                                      f'<param name="bline">{_bline_split(verts, True)}</param></layer>\n')
            for verts, closed in subs:
                sw = el.implicit_stroke_width if hasattr(el, "implicit_stroke_width") else el.stroke_width
                if el.stroke is not None and el.stroke.value is not None and sw:
                    part.items.append(f'<layer type="outline" active="true" version="0.2" desc="{name} outline">'
                                      f'<param name="color">{_color(el.stroke, opacity)}</param>'
                                      f'<param name="origin">{V(0, 0)}</param>'
                                      f'<param name="bline">{_bline_split(verts, closed)}</param>'
                                      f'<param name="width">{R(sw * scale)}</param><param name="expand">{R(0)}</param>'
                                      f'<param name="sharp_cusps">{B(False)}</param>'
                                      f'<param name="round_tip[0]">{B(True)}</param><param name="round_tip[1]">{B(True)}</param>'
                                      f'<param name="homogeneous">{B(True)}</param></layer>\n')

    root = Part("root")
    walk(svg, root)
    return root, pivots


def emit(part, wrap=None):
    """Part tree -> list of Synfig layers. wrap: {part_id: fn(child_layers, part) -> layer}
    for animated parts; all other parts become plain named groups."""
    wrap = wrap or {}
    out = []
    for it in part.items:
        if isinstance(it, Part):
            kids = emit(it, wrap)
            out.append(wrap[it.id](kids, it) if it.id in wrap else group(it.id, kids))
        else:
            out.append(it)
    return out


if __name__ == "__main__":
    from sif import canvas, rect, hexc
    src = Path(sys.argv[1]).resolve()
    plain = normalize(src)
    root, pivots = load_svg(plain, scale=1 / 50, origin=(200, 200))
    print("Parts:", [it.id for it in root.items if isinstance(it, Part)], "Pivots:", pivots)
    layers = [rect("Paper", hexc("#ffffff"), (-5, 5), (5, -5))] + emit(root)
    src.with_name(src.stem + "_static.sif").write_text(
        canvas(layers, w=400, h=400, end=0, name=src.stem, view="-4 4 4 -4"), encoding="utf-8")
    print("->", src.stem + "_static.sif")
