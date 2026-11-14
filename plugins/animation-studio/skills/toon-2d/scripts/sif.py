"""Small helpers for writing Synfig scenes (.sif) from Python.

Every layer function returns an XML string (one or more layers).
Children for group()/canvas() are a list of such strings (a single string works too).
Layer order: the first layer named is at the very bottom.
Interpolation: "clamped", "auto" (TCB), "linear", "halt" (ease in/out), "constant".
Times are given in frames.
"""


# ---------- Values ----------
def _esc(text):
    """Escape text for XML attributes (layer names) - e.g. quotation marks from lyrics."""
    from xml.sax.saxutils import escape
    return escape(str(text), {"\"": "&quot;"})


def V(x, y):
    return f"<vector><x>{x:.6f}</x><y>{y:.6f}</y></vector>"


def R(v):
    return f'<real value="{v:.6f}"/>'


def A(deg):
    return f'<angle value="{deg:.6f}"/>'


def B(b):
    return f'<bool value="{"true" if b else "false"}"/>'


def C(r, g, b, a=1.0):
    return f"<color><r>{r:.6f}</r><g>{g:.6f}</g><b>{b:.6f}</b><a>{a:.6f}</a></color>"


def hexc(h, a=1.0):
    h = h.lstrip("#")
    return C(*(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)), a)


_MAKERS = {"real": R, "angle": A, "vector": lambda v: V(*v), "color": lambda c: c}


def anim(kind, keys, default="clamped"):
    """keys: [(frame, value), (frame, value, interp), (frame, value, (before, after))]"""
    make = _MAKERS[kind]
    out = []
    # Synfig forbids two keys on the same frame -> the one named later wins
    uniq = {}
    for k in keys:
        uniq[k[0]] = k
    for k in sorted(uniq.values(), key=lambda k: k[0]):
        f, v = k[0], k[1]
        interp = k[2] if len(k) > 2 else default
        before, after = interp if isinstance(interp, tuple) else (interp, interp)
        out.append(f'<waypoint time="{f}f" before="{before}" after="{after}">{make(v)}</waypoint>')
    return f'<animated type="{kind}">' + "".join(out) + "</animated>"


def comp_vec(x_xml, y_xml):
    """Vector from separately animated x/y values."""
    return f'<composite type="vector"><x>{x_xml}</x><y>{y_xml}</y></composite>'


# ---------- Layers ----------
def group(desc, children, offset=None, scale=None, angle=None, origin=(0, 0), amount=None):
    """Transformation: point p -> offset + Rot(angle) * Scale * (p - origin).

    Children are drawn in the parent's coordinates. With origin = offset = pivot
    everything stays in place and rotates/scales around the pivot.
    """
    if isinstance(children, str):
        children = [children]
    offset = offset or V(*origin)
    return f'''<layer type="group" active="true" version="0.3" desc="{_esc(desc)}">
<param name="amount">{amount or R(1)}</param>
<param name="origin">{V(*origin)}</param>
<param name="transformation"><composite type="transformation">
<offset>{offset}</offset><angle>{angle or A(0)}</angle><skew_angle>{A(0)}</skew_angle><scale>{scale or V(1, 1)}</scale>
</composite></param>
<param name="canvas"><canvas>
{"".join(children)}
</canvas></param>
</layer>
'''


def circle(desc, color, radius, center, feather=0.0, amount=None):
    return f'''<layer type="circle" active="true" version="0.2" desc="{_esc(desc)}">
<param name="amount">{amount or R(1)}</param>
<param name="color">{color}</param><param name="radius">{R(radius)}</param>
<param name="feather">{R(feather)}</param><param name="origin">{V(*center)}</param>
</layer>
'''


def rect(desc, color, p1, p2):
    return f'''<layer type="rectangle" active="true" version="0.2" desc="{_esc(desc)}">
<param name="color">{color}</param><param name="point1">{V(*p1)}</param><param name="point2">{V(*p2)}</param>
</layer>
'''


def linear_gradient(desc, p1, p2, stops):
    cols = "".join(f'<color pos="{p:.6f}">{c[7:-8]}</color>' for p, c in stops)
    return f'''<layer type="linear_gradient" active="true" version="0.0" desc="{_esc(desc)}">
<param name="p1">{V(*p1)}</param><param name="p2">{V(*p2)}</param>
<param name="gradient"><gradient>{cols}</gradient></param>
<param name="loop">{B(False)}</param><param name="zigzag">{B(False)}</param>
</layer>
'''


def bline(points, loop):
    """points: [(x, y, tx, ty)] or [(x, y, tx, ty, width)]. Tangent ~ 3x the Bezier handle."""
    entries = []
    for p in points:
        x, y, tx, ty = p[:4]
        w = p[4] if len(p) > 4 else 1.0
        entries.append(
            f"<entry><composite type=\"bline_point\"><point>{V(x, y)}</point><width>{R(w)}</width>"
            f"<origin>{R(0.5)}</origin><split>{B(False)}</split><t1>{V(tx, ty)}</t1><t2>{V(tx, ty)}</t2>"
            f"<split_radius>{B(False)}</split_radius><split_angle>{B(False)}</split_angle>"
            f"</composite></entry>")
    return f'<bline type="bline_point" loop="{"true" if loop else "false"}">{"".join(entries)}</bline>'


def region(desc, color, points, amount=None):
    return f'''<layer type="region" active="true" version="0.1" desc="{_esc(desc)}">
<param name="amount">{amount or R(1)}</param>
<param name="color">{color}</param><param name="origin">{V(0, 0)}</param>
<param name="bline">{bline(points, True)}</param>
</layer>
'''


def outline(desc, color, points, width, loop=True, amount=None):
    return f'''<layer type="outline" active="true" version="0.2" desc="{_esc(desc)}">
<param name="amount">{amount or R(1)}</param>
<param name="color">{color}</param><param name="origin">{V(0, 0)}</param>
<param name="bline">{bline(points, loop)}</param>
<param name="width">{R(width)}</param><param name="expand">{R(0)}</param>
<param name="sharp_cusps">{B(True)}</param><param name="round_tip[0]">{B(True)}</param>
<param name="round_tip[1]">{B(True)}</param><param name="homogeneous">{B(True)}</param>
</layer>
'''


def shape(desc, fill, ink, points, width):
    """Filled shape with an ink outline."""
    return region(desc, fill, points) + outline(desc + " outline", ink, points, width)


def image(desc, path, tl=(-8, 4.5), br=(8, -4.5)):
    """Import an image (PNG), e.g. a background painted in Krita. tl/br = corners in units.
    Path with forward slashes; the default fills the standard view."""
    path = str(path).replace("\\", "/")
    return f'''<layer type="import" active="true" version="0.1" desc="{_esc(desc)}">
<param name="tl">{V(*tl)}</param><param name="br">{V(*br)}</param>
<param name="filename"><string>{path}</string></param>
</layer>
'''


# ---------- Blend methods / masking ----------
# tested: COMPOSITE (default), ONTO (draw only where something is already underneath)
COMPOSITE, ONTO = 0, 13
# according to the Synfig docs, untested: BEHIND 12, MULTIPLY 6, SCREEN 16, ADD 4, OVERLAY 20
BEHIND, MULTIPLY, SCREEN, ADD, OVERLAY = 12, 6, 16, 4, 20


def with_blend(layer_xml, method):
    """Set the blend method of a (single) layer."""
    head, rest = layer_xml.split(">", 1)
    return f'{head}><param name="blend_method"><integer value="{method}"/></param>{rest}'


def clipped(desc, mask, content):
    """Show content only inside the mask (e.g. a gradient only inside the water rectangle).

    Important: otherwise linear_gradient fills the WHOLE area and covers everything below.
    mask: layer string (shape), content: list of layer strings.
    """
    if isinstance(content, str):
        content = [content]
    return group(desc, [mask] + [with_blend(c, ONTO) for c in content])


# ---------- Ellipses / polygons ----------
def ellipse_pts(rx, ry, center=(0, 0), n=8, rotate_deg=0.0):
    """Points + correct tangents for an ellipse (for region/outline/shape)."""
    import math
    cx, cy = center
    d = 2 * math.pi / n
    k = 4 * math.tan(d / 4)  # Synfig tangent = 3x the Bezier handle
    ca, sa = math.cos(math.radians(rotate_deg)), math.sin(math.radians(rotate_deg))
    pts = []
    for i in range(n):
        t = i * d
        x, y = rx * math.cos(t), ry * math.sin(t)
        tx, ty = -rx * math.sin(t) * k, ry * math.cos(t) * k
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca, tx * ca - ty * sa, tx * sa + ty * ca))
    return pts


def ellipse(desc, fill, ink, rx, ry, center=(0, 0), width=0.06, rotate_deg=0.0):
    """Filled ellipse with outline (ink=None -> no outline)."""
    pts = ellipse_pts(rx, ry, center, 8, rotate_deg)
    return shape(desc, fill, ink, pts, width) if ink else region(desc, fill, pts)


def polygon_pts(points):
    """Angular shape: points without tangents (sharp corners)."""
    return [(x, y, 0, 0) for x, y in points]


def canvas(layers, w=1280, h=720, fps=24, end=120, name="Scene", view="-8 4.5 8 -4.5"):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<canvas version="1.2" width="{w}" height="{h}" xres="2834.645669" yres="2834.645669"
  gamma-r="1" gamma-g="1" gamma-b="1" view-box="{view}" antialias="1"
  fps="{fps}" begin-time="0f" end-time="{end}f" bgcolor="0.5 0.5 0.5 1">
<name>{name}</name>
{"".join(layers)}
</canvas>
'''
