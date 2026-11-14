# /// script
# requires-python = ">=3.12"
# dependencies = ["svgelements==1.9.6"]
# ///
"""Scene template: an SVG figure from the characters skill animated in Synfig ("Fips chirps", 5 s, 24 fps).

Parts from the SVG (group ids) become animated groups here:
  whole bird (hop, squash, lean) > kopf (tilt, nod) > auge_l/r (blink), pupille_l/r (look),
  schnabel_unten (beak opens) ; fluegel_vorn/hinten (wings flap)
Pivots come from the pivot_<part> circles in the SVG.

Beats: 0-20 looks around | 20-48 small hop with flapping | 48-72 tilts the head, blinks |
       72-96 "Peep! Peep!" (beak opens, head nods, wings twitch) | 96-120 happy flapping, hop, landing
Replace the beat list and the key lists with your own idea; keep one key list per animated part.
Run: uv run make_scene.py   -> scene.sif
"""
import sys
from pathlib import Path

try:
    import _toon  # noqa: F401  (made by new_scene.py; stops with a refresh hint if the plugin is not found)
except ModuleNotFoundError as e:
    if e.name != "_toon":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))   # run in place inside the plugin
    import _studio
    _studio.use("toon-2d", "characters")

from motion import squash_keys  # noqa: E402
from sif import V, R, anim, comp_vec, group, circle, hexc, canvas  # noqa: E402
from svg2sif import emit  # noqa: E402
from figures import load, around, blink_keys  # noqa: E402
from sets import load_set, set_layers  # noqa: E402

HERE = Path(__file__).resolve().parent
FPS, END = 24, 120
FIGURE = "fips"            # bundled: fips, tim, lia - or a path to your own SVG (rig convention, see characters)
SET = "park"

root, PIV = load(FIGURE, work_dir=HERE / "cache")

# ---------------- timing (one list per part) ----------------
Y_KEYS = [(0, 0, "linear"), (28, 0, "linear"), (35, 0.9, "halt"), (42, 0, "linear"),
          (100, 0, "halt"), (104, 0.0, "linear"), (110, 0.55, "halt"), (116, 0, "linear")]
SQ = [(0, 1.0), (10, 1.03, "halt"), (20, 1.0, "halt"), (26, 0.86, "halt"), (28, 0.84, "linear"), (30, 1.15),
      (35, 1.0, "halt"), (40, 1.1), (42, 0.75, "linear"), (45, 1.08), (48, 0.97), (52, 1.0, "halt"),
      (72, 1.0, "halt"), (74, 1.04), (77, 0.98, "halt"), (82, 1.04), (85, 0.98, "halt"), (90, 1.0, "halt"),
      (102, 0.9, "halt"), (104, 0.88, "linear"), (106, 1.1), (110, 1.0, "halt"), (114, 1.06), (116, 0.8, "linear"),
      (119, 1.04), (END, 1.0, "halt")]
LEAN = [(0, 0), (26, 3, "halt"), (30, -4), (42, 0, "linear"), (45, 3), (50, 0, "halt"), (END, 0)]
HEAD = [(0, 0), (12, 0, "halt"), (16, 8, "halt"), (20, -6, "halt"), (24, 0, "halt"),
        (52, 0, "halt"), (58, 14, "halt"), (70, 12, "halt"), (72, 0),                     # curious tilt
        (74, -6), (77, 2), (82, -6), (85, 2), (90, 0, "halt"), (END, 0)]                  # nods while peeping
BEAK = [(0, 0), (72, 0, "halt"), (74, 22), (77, 0, "halt"), (81, 0, "halt"), (82, 26), (86, 0, "halt"), (END, 0)]
LOOK = [(0, (0.0, 0.0)), (12, (0.0, 0.0), "halt"), (15, (-0.07, 0.0), "halt"), (19, (0.07, 0.0), "halt"),
        (24, (0.0, -0.02), "halt"), (52, (0.0, -0.02), "halt"), (58, (0.05, 0.05), "halt"), (72, (0.0, -0.02), "halt"),
        (END, (0.0, -0.02))]
BLINKS = [8, 62, 92]


def flap_keys(sign):
    """Wings: sign=-1 front wing (rises with a negative angle), +1 back wing. Whole frames only (Synfig)."""
    k = [(0, 0), (28, 0, "halt")]
    for f in range(29, 42, 3):                                    # flapping during the hop
        k += [(f, sign * 55), (f + 1.5, sign * 10)]
    k += [(44, 0, "halt"), (74, 0, "halt"), (75, sign * 18), (77, 0), (82, 0), (83, sign * 20), (85, 0, "halt")]
    for f in range(96, 116, 2):                                   # happy flapping
        k += [(f, sign * 70), (f + 1, sign * 15)]
    k += [(117, sign * 25), (END, 0, "halt")]
    # round half frames: round(f*2)/2 then to whole frames (anim() keeps the later of two keys on one frame)
    return [(int(round(int(round(f * 2)) / 2)), v) + tuple(rest) for f, v, *rest in k]


# ---------------- animated parts ----------------
blink = blink_keys(BLINKS)
look = lambda pid: (lambda kids, part: group(pid, kids, offset=anim("vector", LOOK)))
WRAP = {
    "kopf": lambda kids, p: around(PIV, "kopf", kids, angle=anim("angle", HEAD)),
    "auge_l": lambda kids, p: around(PIV, "auge_l", kids, scale=anim("vector", blink)),
    "auge_r": lambda kids, p: around(PIV, "auge_r", kids, scale=anim("vector", blink)),
    "pupille_l": look("pupille_l"),
    "pupille_r": look("pupille_r"),
    "schnabel_unten": lambda kids, p: around(PIV, "schnabel_unten", kids,
                                             angle=anim("angle", [(f, -v) + tuple(r) for f, v, *r in BEAK])),
    "fluegel_vorn": lambda kids, p: around(PIV, "fluegel_vorn", kids, angle=anim("angle", flap_keys(-1))),
    "fluegel_hinten": lambda kids, p: around(PIV, "fluegel_hinten", kids, angle=anim("angle", flap_keys(+1))),
}
figure = group("Figure (whole)", emit(root, WRAP),
               offset=comp_vec(R(0), anim("real", Y_KEYS)),
               scale=anim("vector", squash_keys(SQ, 0.7)), angle=anim("angle", LEAN))
shadow = group("Shadow", [circle("Shadow", hexc("#2f3d1d"), 1.3, (0, 0), feather=0.35)],
               offset=V(0, 0.02),
               scale=anim("vector", [(f, ((1 - 0.3 * h), (1 - 0.3 * h) * 0.2), i) for f, h, i in Y_KEYS]),
               amount=anim("real", [(f, 0.5 - 0.2 * h, i) for f, h, i in Y_KEYS]))
info = load_set(SET)
back, front = set_layers(SET)
out = HERE / "scene.sif"
out.write_text(canvas(back + [shadow, figure] + front, end=END, name="Fips chirps", view=info["view"]),
               encoding="utf-8")
print("written:", out, "| parts with pivot:", sorted(PIV))
