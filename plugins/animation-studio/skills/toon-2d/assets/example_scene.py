"""Scene "Pip and the Flower" (6 s, 24 fps) as a Synfig file - the complete reference example of toon-2d.

Beats (frames):
  0-36    Pip hops into the picture in two jumps, lands, settles
  46-62   discovers the bud, leans forward curiously
  60-72   the bud trembles
  72-86   the bud blooms (overshoot) - Pip gets a fright ("take")
  86-131  crouch, jump for joy, landing, settle
  131-144 hold, blink

All main moves are keyframes (editable in Synfig Studio). Only the antenna (follow-through) is computed by a
spring simulation and baked as one key per frame.

Start a scene from it:  python new_scene.py <folder> --from example   (copies this file as make_scene.py)
Run:    uv run --no-project python make_scene.py [out.sif]   -> scene.sif next to make_scene.py (like the templates)
Render: uv run --no-project python <toon-2d>/scripts/render.py scene.sif --gif --contact 0,15,36,52,74,97,109,118,140
"""
import math
import sys
from pathlib import Path

try:
    import _toon  # noqa: F401  (scene folder made by new_scene.py: puts the toon-2d scripts on the path)
except ModuleNotFoundError as e:
    if e.name != "_toon":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))   # run in place inside the plugin

from motion import approx, hop_y, spring_follow, squash_keys  # noqa: E402
from sif import (V, R, A, anim, comp_vec, group, circle, rect, linear_gradient,  # noqa: E402
                 region, outline, shape, hexc, canvas)

FPS, END = 24, 144
GROUND = -2.6
INK = hexc("#3b2418")
PIP_SCALE = 0.62

# ======================================================================
# Timing data (one source for the Synfig keys AND the antenna simulation)
# ======================================================================
# Pip height: (frame, height, interp)  contacts linear, apex halt
Y_KEYS = [(0, 0, "linear"), (8, 0, "linear"), (15, 1.3, "halt"), (22, 0, "linear"),
          (29, 1.1, "halt"), (36, 0, "linear"), (100, 0, "linear"), (109, 2.3, "halt"),
          (118, 0, "linear")]
X_KEYS = [(0, -8.2, "linear"), (8, -8.2, "linear"), (22, -4.5, "linear"),
          (36, -1.0, ("linear", "halt")), (41, -0.82, "halt")]
# Squash: height factor sy (width = sy^-0.8 -> volume stays)
SQ_KEYS = [(0, 1.0), (6, 1.0), (8, 0.82, "linear"), (10, 1.2), (14, 1.0, "halt"), (20, 1.12),
           (22, 0.8, "linear"), (24, 1.18), (28, 1.0, "halt"), (34, 1.12), (36, 0.68, "linear"),
           (39, 1.1), (42, 0.95), (46, 1.0, "halt"),
           (64, 1.0, "halt"), (70, 0.86, "halt"), (74, 1.22), (78, 0.97), (83, 1.0, "halt"),
           (88, 1.0, "halt"), (97, 0.7, "halt"), (100, 1.32, "linear"), (105, 1.06), (109, 0.97, "halt"),
           (116, 1.16), (118, 0.64, "linear"), (121, 1.13), (124, 0.94), (127, 1.03), (131, 1.0, "halt"),
           (137, 1.025, "halt"), (144, 1.0, "halt")]
# Lean in degrees (negative = to the right / forward)
LEAN_KEYS = [(0, -8), (34, -8), (36, -13, "linear"), (40, 6), (44, -2), (48, 0, "halt"),
             (52, 0, "halt"), (61, -12, "halt"), (68, -10, "halt"), (71, -14), (75, 8), (82, 0, "halt"),
             (118, 0, "halt"), (121, -4), (125, 2), (129, 0, "halt")]

HOPS = [(8, 22, 1.3), (22, 36, 1.1), (100, 118, 2.3)]  # jumps (start, end, height)


def simulate_antenna():
    """Follow-through: spring at the top of the head, baked as one angle key per frame."""
    def head(t):
        return (approx(X_KEYS, t), hop_y(HOPS, t) + 2.95 * PIP_SCALE * approx(SQ_KEYS, t))
    return spring_follow(head, END, FPS, root_angle=lambda t: approx(LEAN_KEYS, t))


# ======================================================================
# Background
# ======================================================================
def background():
    L = [linear_gradient("Sky", (0, 4.5), (0, GROUND),
                         [(0, hexc("#7fb8e6")), (0.7, hexc("#cfe6ef")), (1, hexc("#f6ecd2"))])]
    # sun with a soft glow
    L.append(circle("Sun glow", hexc("#fff4c0", 0.55), 1.6, (4.2, 2.0), feather=1.2))
    L.append(circle("Sun", hexc("#ffe27a"), 0.75, (4.2, 2.0)))

    # clouds drift slowly
    def cloud(cx, cy, s):
        return [circle("Cloud", hexc("#ffffff", 0.92), r * s, (cx + dx * s, cy + dy * s))
                for dx, dy, r in ((0, 0, 0.55), (0.6, 0.15, 0.7), (1.3, 0, 0.5), (0.65, -0.25, 0.55))]
    drift = comp_vec(anim("real", [(0, 0, "linear"), (END, 0.9, "linear")]), R(0))
    L.append(group("Clouds", cloud(-4.8, 2.1, 0.8) + cloud(0.6, 2.5, 0.55), offset=drift))
    # hills (lighter at the back = aerial perspective)
    L.append(circle("Hill back", hexc("#a9cf8a"), 9.0, (5.5, -10.2)))
    L.append(circle("Hill back 2", hexc("#b5d797"), 8.0, (-6.0, -9.3)))
    L.append(circle("Hill front", hexc("#8dbf6a"), 10.0, (-1.0, -12.0)))
    L.append(rect("Ground", hexc("#7fb35c"), (-9, GROUND), (9, -5)))
    L.append(rect("Ground edge", hexc("#6a9c4b"), (-9, GROUND + 0.02), (9, GROUND - 0.05)))
    # a few blades of grass as detail
    for gx in (-6.8, -3.4, 4.6, 6.9):
        L.append(outline("Grass", hexc("#5f9142"),
                         [(gx, GROUND, 0.05, 0.3, 1), (gx + 0.12, GROUND + 0.35, 0.15, 0.2, 0.2)], 0.05, loop=False))
    return L


# ======================================================================
# Flower
# ======================================================================
def flower():
    fx = 1.75
    bloom = 72
    stem = outline("Stem", hexc("#4f8a3a"),
                   [(0, 0, 0.3, 0.9, 1.2), (0.15, 1.65, 0.0, 0.9, 0.9)], 0.09, loop=False)
    leaf = group("Leaf", [shape("Leaf", hexc("#6fb04f"),
                                INK, [(0, 0, 0.6, 0.6), (0.6, 0.15, 0.1, -0.5)], 0.035)],
                 offset=V(0.06, 0.55), angle=A(15))
    leaf2 = group("Leaf 2", [shape("Leaf", hexc("#6fb04f"),
                                   INK, [(0, 0, -0.6, 0.6), (-0.6, 0.15, -0.1, -0.5)], 0.035)],
                  offset=V(0.1, 0.9), angle=A(-10))

    # the bud shrinks away, the petals pop open with overshoot
    bud = group("Bud", [circle("Bud ink", INK, 0.27, (0, 0)),
                        circle("Bud", hexc("#7cbf58"), 0.22, (0, 0)),
                        circle("Bud tip", hexc("#e889a8"), 0.1, (0, 0.13))],
                scale=anim("vector", [(0, (1, 1)), (60, (1, 1)), (66, (1.12, 0.92)), (70, (0.9, 1.15)),
                                      (bloom, (1.0, 1.0)), (bloom + 3, (0, 0), "linear")]))
    petals = []
    for i in range(6):
        a = i * 60 + 90
        px, py = 0.33 * math.cos(math.radians(a)), 0.33 * math.sin(math.radians(a))
        petals.append(circle("Petal ink", INK, 0.27, (px, py)))
    for i in range(6):
        a = i * 60 + 90
        px, py = 0.33 * math.cos(math.radians(a)), 0.33 * math.sin(math.radians(a))
        petals.append(circle("Petal", hexc("#f28fb0"), 0.225, (px, py)))
    petals += [circle("Centre ink", INK, 0.2, (0, 0)), circle("Centre", hexc("#ffd34d"), 0.16, (0, 0)),
               circle("Centre glint", hexc("#fff3b0"), 0.05, (-0.05, 0.05))]
    bloom_grp = group("Blossom", petals,
                      scale=anim("vector", [(0, (0, 0)), (bloom, (0, 0), "linear"), (bloom + 4, (1.3, 1.3)),
                                            (bloom + 8, (0.9, 0.9)), (bloom + 12, (1.05, 1.05)),
                                            (bloom + 16, (1, 1), "halt")]),
                      angle=anim("angle", [(bloom, -40), (bloom + 10, 8), (bloom + 16, 0, "halt")]))
    head = group("Flower head", [bloom_grp, bud], offset=V(0.15, 1.65), origin=(0, 0))

    # gentle sway, trembling before the bloom, swinging out afterwards
    sway = [(f, 3 * math.sin(f / 48 * 2 * math.pi), "auto") for f in range(0, 60, 6)]
    sway += [(60 + i * 2, 4 * (-1) ** i, "linear") for i in range(6)]
    sway += [(bloom, 0), (bloom + 5, -9), (bloom + 11, 6), (bloom + 17, -3), (bloom + 23, 1.5)]
    sway += [(f, 2.5 * math.sin((f - 96) / 48 * 2 * math.pi), "auto") for f in range(96, END + 1, 6)]
    return group("Flower", [stem, leaf, leaf2, head], offset=V(fx, GROUND), origin=(0, 0), scale=V(1.35, 1.35),
                 angle=anim("angle", sway))


def sparkles():
    L = []
    star = []
    for i in range(8):
        r = 0.28 if i % 2 == 0 else 0.07
        a = math.radians(i * 45 + 90)
        star.append((r * math.cos(a), r * math.sin(a), 0, 0))
    for j, (sx, sy, d) in enumerate(((1.0, 0.7, 0), (2.9, 0.4, 2), (1.5, -0.1, 4), (2.6, 1.2, 3))):
        t = 74 + d
        L.append(group(f"Sparkle {j}", [region("Star", hexc("#ffe680"), star)],
                       offset=V(sx, sy), origin=(0, 0),
                       scale=anim("vector", [(0, (0, 0)), (t, (0, 0), "linear"), (t + 4, (1.2, 1.2)),
                                             (t + 10, (0.8, 0.8)), (t + 16, (0, 0), "linear")]),
                       angle=anim("angle", [(t, 0, "linear"), (t + 16, 120, "linear")])))
    return L


# ======================================================================
# Pip (code-drawn character: pear body, belly, cheeks, eyes, mouth swap, spring antenna)
# ======================================================================
def pip():
    # body: pear shape, origin = bottom centre (the feet)
    body = [(0, 0, 2.6, 0), (1.32, 1.05, 0, 2.2), (0, 2.95, -2.0, 0), (-1.32, 1.05, 0, -2.2)]
    ant_angle = anim("angle", simulate_antenna())
    antenna = group("Antenna", [
        outline("Antenna stalk", INK, [(0, 2.85, 0.0, 0.5), (0.05, 3.75, 0.1, 0.5)], 0.09, loop=False),
        circle("Antenna ball ink", INK, 0.24, (0.05, 3.85)),
        circle("Antenna ball", hexc("#ec5a4f"), 0.18, (0.05, 3.85)),
        circle("Antenna ball glint", hexc("#ffb3a6"), 0.05, (0.0, 3.92)),
    ], origin=(0, 2.9), offset=V(0, 2.9), angle=ant_angle)

    belly = group("Belly", [circle("Belly", hexc("#ffe2a0"), 0.78, (0, 0))],
                  offset=V(0, 0.95), scale=V(1, 0.78))
    cheeks = [group("Cheek", [circle("Cheek", hexc("#f0807a", 0.55), 0.2, (0, 0), feather=0.06)],
                    offset=V(sx * 0.82, 1.62), scale=V(1, 0.6)) for sx in (-1, 1)]

    # eyes: blink + big eyes for the fright
    eye_scale = anim("vector", [(0, (1, 1)), (43, (1, 1)), (45, (1.05, 0.08), "linear"), (47, (1, 1)),
                                (71, (1, 1), "halt"), (74, (1.25, 1.35)), (80, (1.15, 1.22)), (90, (1, 1), "halt"),
                                (134, (1, 1)), (136, (1.05, 0.08), "linear"), (138, (1, 1))])
    look = [(0, (0.10, 0.0)), (46, (0.10, 0.0), "halt"), (52, (0.13, -0.06), "halt"),
            (72, (0.12, -0.02), "halt"), (76, (0.12, 0.06)), (96, (0.05, 0.0), "halt"),
            (102, (0.0, 0.1), "halt"), (118, (0.05, 0.0), "halt"), (128, (0.13, -0.03), "halt")]
    eyes = []
    for ex in (-0.42, 0.42):
        ey = 2.12
        pupil = group("Pupil", [circle("Pupil", INK, 0.15, (0, 0)),
                                circle("Glint", hexc("#ffffff"), 0.05, (-0.05, 0.06))],
                      offset=anim("vector", [(k[0], (ex + k[1][0], ey + k[1][1])) + k[2:] for k in look]))
        eye_inner = [group("Eye shape", [circle("Eye ink", INK, 0.33, (0, 0)),
                                         circle("Eye", hexc("#ffffff"), 0.27, (0, 0))],
                           offset=V(ex, ey), scale=V(1, 1.22)), pupil]
        eyes.append(group("Eye", eye_inner, origin=(ex, ey), offset=V(ex, ey), scale=eye_scale))

    # mouth: smile / open "O" (switched by amount with constant interpolation)
    open_on = [(0, 0), (72, 0), (73, 1), (92, 0), (99, 0), (100, 1), (119, 0)]
    smile_amt = anim("real", [(f, 1 - v, "constant") for f, v in open_on])
    open_amt = anim("real", [(f, v, "constant") for f, v in open_on])
    mouth = [
        outline("Smile", INK, [(-0.28, 1.72, 0.3, -0.35), (0, 1.55, 0.55, 0), (0.28, 1.72, 0.3, 0.35)],
                0.075, loop=False, amount=smile_amt),
        group("Mouth open", [circle("Mouth ink", INK, 0.17, (0, 0)), circle("Mouth", hexc("#9e3b3b"), 0.12, (0, 0)),
                             circle("Tongue", hexc("#e8787a"), 0.06, (0, -0.05))],
              offset=V(0, 1.62), scale=V(0.9, 1.15), amount=open_amt),
    ]

    sq = anim("vector", squash_keys(SQ_KEYS))
    squash = group("Squash", [antenna] + [shape("Body", hexc("#fbb53f"), INK, body, 0.09)]
                   + [belly] + cheeks + eyes + mouth, scale=sq)

    pos = comp_vec(anim("real", X_KEYS), anim("real", [(f, GROUND + h, i) for f, h, i in Y_KEYS]))
    pip_grp = group("Pip", [squash], offset=pos, scale=V(PIP_SCALE, PIP_SCALE),
                    angle=anim("angle", LEAN_KEYS))

    # shadow follows x, gets smaller and fainter with height
    sh_scale = anim("vector", [(f, ((1 - 0.22 * h) * 0.95, (1 - 0.22 * h) * 0.22), i) for f, h, i in Y_KEYS])
    sh_amt = anim("real", [(f, 0.35 - 0.1 * h, i) for f, h, i in Y_KEYS])
    shadow = group("Shadow", [circle("Shadow", hexc("#2a3a1a"), 0.9, (0, 0), feather=0.25)],
                   offset=comp_vec(anim("real", X_KEYS), R(GROUND)), scale=sh_scale, amount=sh_amt)
    return [shadow, pip_grp]


if __name__ == "__main__":
    layers = background() + [flower()] + pip() + sparkles()
    here = Path(__file__).resolve().parent              # scene folder (has _toon.py); cwd when run inside the plugin
    default = (here if (here / "_toon.py").exists() else Path.cwd()) / "scene.sif"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.write_text(canvas(layers, end=END, name="Pip and the Flower", view="-6 3.0 6 -3.75"), encoding="utf-8")
    print("written:", out)
