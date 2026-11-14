# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==13.0.0", "svgelements==1.9.6"]
# ///
"""Figure sheet: all bundled characters side by side in their rest pose (Tim, Lia, Computer, Pip, Fips), or your own
SVG figures - to show the cast to the user, to check a new figure's scale and pivots, or to pick a cast.

Usage: uv run figure_sheet.py --out sheet_dir [--add my_figure.svg ...]
       [--pivots]
Writes <out>/figure_sheet.sif and <out>/figure_sheet.png (1920x1080). --pivots draws a red dot on every pivot.
All figures stand on one floor line at the scale they have in scenes (Tim/Lia 1/72, Fips 1/80, Pip size 0.62 x 2).
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("toon-2d", "characters")
from sif import V, group, circle, rect, hexc, canvas  # noqa: E402
from svg2sif import emit  # noqa: E402
from lipsync import mouth_layers  # noqa: E402
from figures import FIGURES, load  # noqa: E402
from pip_figure import pip  # noqa: E402
from computer import computer  # noqa: E402

FLOOR = -5.6
INK = hexc("#2b1d14")


def svg_figure(name, x, work, show_pivots, feet=None):
    root, PIV = load(name, work_dir=work, feet=feet)
    kids = emit(root)
    info = FIGURES.get(str(name).lower(), {})
    if "mund" in PIV and info.get("mouth", 0.58):
        kids += mouth_layers([(0.0, "X")], 24, center=PIV["mund"], size=info.get("mouth", 0.58), ink=INK)
    if show_pivots:
        kids += [circle(f"pivot {k}", hexc("#ff2020"), 0.09, p) for k, p in PIV.items()]
    return group(f"Figure {Path(str(name)).stem}", kids, offset=V(x, FLOOR)), PIV


def main():
    ap = argparse.ArgumentParser(description="Render a sheet of all characters in rest pose.")
    ap.add_argument("--out", default="figure_sheet")
    ap.add_argument("--add", nargs="*", default=[], help="own SVG figures (feet at 200,590 assumed)")
    ap.add_argument("--pivots", action="store_true")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    layers = [rect("Paper", hexc("#f3efe6"), (-13, 40), (13, -40)),
              rect("Floor", hexc("#d8d0c0"), (-13, FLOOR), (13, -40))]
    x = -10.5
    for name in ["tim", "lia"]:
        g, piv = svg_figure(name, x, out / "cache", a.pivots)
        layers.append(g)
        print(f"{name}: parts with pivot {sorted(piv)}")
        x += 4.6
    layers += computer((x - 1.9, FLOOR + 4.6, x + 1.9, FLOOR + 1.6))
    layers.append(rect("Computer stand", hexc("#1c1f26"), (x - 0.25, FLOOR + 1.5), (x + 0.25, FLOOR)))
    x += 4.2
    layers += pip(24, [(0, x)], [(0, 0)], ground=FLOOR, size=1.24, antenna=True)
    x += 4.0
    g, piv = svg_figure("fips", x, out / "cache", a.pivots)
    layers.append(g)
    print(f"fips: parts with pivot {sorted(piv)}")
    for extra in a.add:
        x += 4.4
        g, piv = svg_figure(extra, x, out / "cache", a.pivots)
        layers.append(g)
        print(f"{Path(extra).stem}: parts with pivot {sorted(piv)}")
    right = max(13.0, x + 2.5)
    width = right + 13
    bottom = FLOOR - 3.0
    view = f"-13 {bottom + width * 9 / 16:.3f} {right:.3f} {bottom:.3f}"
    if right > 13:
        layers[0:2] = [rect("Paper", hexc("#f3efe6"), (-13, 40), (right, -40)),
                       rect("Floor", hexc("#d8d0c0"), (-13, FLOOR), (right, -40))]
    sif = out / "figure_sheet.sif"
    sif.write_text(canvas(layers, w=1920, h=1080, end=0, name="Figure sheet", view=view), encoding="utf-8")
    subprocess.run([sys.executable, str(_studio.skill_dir("toon-2d") / "scripts" / "render.py"), str(sif), "--single", "0"],
                   check=True)
    (out / "figure_sheet_f0.png").replace(out / "figure_sheet.png")
    print("sheet:", out / "figure_sheet.png")


if __name__ == "__main__":
    main()
