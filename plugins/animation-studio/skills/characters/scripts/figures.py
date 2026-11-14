"""The bundled SVG figures (Tim, Lia, Fips) and helpers to rig any SVG figure that follows the rig convention.

    import _studio; _studio.use("toon-2d", "characters")
    from figures import load, around, blink_keys
    root, PIV = load("fips", work_dir="cache")            # or load("my_figure.svg", feet=(200, 590))
    layers = emit(root, {"kopf": lambda kids, p: around(PIV, "kopf", kids, angle=anim("angle", HEAD)), ...})

Rig convention (Inkscape): every movable part is a group with an id; its pivot is a small circle with id
pivot_<part> inside the group (not drawn, returned in PIV). Ids of the bundled figures (keep them for new figures,
scene builders look for exactly these): arm_l, arm_r, kopf (head), auge_l/auge_r (eyes), pupille_l/pupille_r (pupils),
brauen (brows), koerper (body), beine (legs); pivot_mund marks the mouth position (the mouth itself is drawn by lip
sync). Fips (a bird) adds fluegel_vorn/fluegel_hinten (wings), schnabel_unten/schnabel_oben (beak), schwanz (tail).
"""
from pathlib import Path

import _studio

FIG_DIR = _studio.skill_dir("characters") / "assets" / "figures"

# feet = SVG point that becomes the Synfig origin (bottom centre); scale = Synfig units per SVG px
FIGURES = {
    "tim": {"svg": "tim.svg", "feet": (200, 590), "scale": 1 / 72, "mouth": 0.58,
            "about": "man in his mid twenties, glasses, the developer; 400x600 px SVG, mouth by lip sync"},
    "lia": {"svg": "lia.svg", "feet": (200, 590), "scale": 1 / 72, "mouth": 0.58,
            "about": "the singer (AI persona), headset; same scale as Tim, mouth by lip sync"},
    "fips": {"svg": "fips.svg", "feet": (200, 380), "scale": 1 / 80, "mouth": None,
             "about": "small blue bird; beak opens instead of a mouth, wings flap, hops"},
}


def svg_path(name):
    """Path of a bundled figure ('tim', 'lia', 'fips') or of a given SVG file."""
    key = str(name).lower()
    if key in FIGURES:
        return FIG_DIR / FIGURES[key]["svg"]
    p = Path(name)
    if not p.exists():
        raise SystemExit(f"figure '{name}' not found (bundled: {', '.join(FIGURES)})")
    return p


def load(name, work_dir=None, feet=None, scale=None):
    """Normalize (Inkscape: objects -> paths) and load a figure; returns (root part, pivots in Synfig units).

    work_dir: where the *_plain.svg goes (use the scene folder or a cache folder - never the plugin)."""
    from svg2sif import normalize, load_svg
    info = FIGURES.get(str(name).lower(), {})
    src = svg_path(name)
    plain = normalize(src, out_dir=work_dir or Path.cwd() / "cache")
    return load_svg(plain, scale=scale or info.get("scale", 1 / 72), origin=feet or info.get("feet", (200, 590)))


def around(PIV, pid, kids, **kw):
    """Group that rotates/scales about the pivot of part `pid` (origin = offset = pivot)."""
    from sif import V, group
    if pid not in PIV:
        return group(pid, kids, **kw)
    px, py = PIV[pid]
    return group(pid, kids, origin=(px, py), offset=V(px, py), **kw)


def blink_keys(frames, start=(1, 1)):
    """Eye scale keys: a 4-frame blink at each frame number."""
    k = [(0, start)]
    for b in frames:
        k += [(b - 1, (1, 1)), (b + 1, (1.05, 0.1), "linear"), (b + 3, (1, 1))]
    return k
