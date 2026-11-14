"""Scene: <title> (<seconds> s, 24 fps)

Idea (one sentence): <who wants what, what goes wrong, how it ends>
Principles in focus: <e.g. anticipation, squash & stretch, take, follow-through>
Beats (frames):
  0-24    <establish: character enters / is discovered>
  24-60   <want: notices something, anticipation>
  60-96   <action / problem: the big move, the take>
  96-END  <result / button: reaction, settle, hold with a blink>

Run: uv run --no-project python make_scene.py   -> scene.sif ; render.py scene.sif --contact <key frames>
"""
import sys
from pathlib import Path

try:
    import _toon  # noqa: F401  (made by new_scene.py)
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import _studio
    _studio.use("toon-2d", "characters")

from sif import V, R, anim, comp_vec, group, circle, rect, linear_gradient, hexc, canvas  # noqa: E402
from pip import pip, blink  # noqa: E402

HERE = Path(__file__).resolve().parent
FPS, END = 24, 120
GROUND = -2.6

# ---------------- timing: one list per value (frame, value[, interp]) ----------------
X = [(0, -2.0, "linear"), (END, -2.0)]
Y = [(0, 0, "linear"), (40, 0, "linear"), (49, 1.4, "halt"), (58, 0, "linear")]          # one hop
HOPS = [(40, 58, 1.4)]
SQ = [(0, 1.0), (32, 1.0, "halt"), (40, 0.8, "linear"), (42, 1.2), (49, 1.0, "halt"), (56, 1.15),
      (58, 0.7, "linear"), (61, 1.1), (64, 0.95), (68, 1.0, "halt")]
LEAN = [(0, 0), (36, 4, "halt"), (42, -8), (58, -6, "linear"), (62, 5), (68, 0, "halt")]
EYES = blink([20, 90])
LOOK = [(0, (0.1, 0.0)), (30, (0.1, 0.0), "halt"), (34, (0.05, 0.1), "halt")]
MOUTH = [(0, 0), (42, 1), (60, 0)]


def background():
    return [linear_gradient("Sky", (0, 4.5), (0, GROUND), [(0, hexc("#7fb8e6")), (0.7, hexc("#cfe6ef")),
                                                             (1, hexc("#f6ecd2"))]),
            circle("Hill", hexc("#a9cf8a"), 9.0, (5.5, -10.2)),
            rect("Ground", hexc("#7fb35c"), (-9, GROUND), (9, -5))]


layers = background() + pip(END, X, Y, SQ, LEAN, hops=HOPS, ground=GROUND, eye_keys=EYES, look_keys=LOOK,
                            mouth_open=MOUTH)
out = HERE / "scene.sif"
out.write_text(canvas(layers, end=END, name="Scene", view="-6 3.0 6 -3.75"), encoding="utf-8")
print("written:", out)
