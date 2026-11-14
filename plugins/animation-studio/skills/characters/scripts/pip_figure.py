"""Pip - the code-drawn character (pear-shaped body, belly, cheeks, two eyes, mouth swap, spring antenna).

Pip is drawn in Synfig layers directly from Python (no SVG). One call builds the whole rig from timing lists:

    import _studio; _studio.use("toon-2d", "characters")
    from pip_figure import pip
    layers = pip(end=144, x_keys=X, y_keys=Y, sq_keys=SQ, lean_keys=LEAN, hops=HOPS, ground=-2.6,
                 eye_keys=EYES, look_keys=LOOK, mouth_open=[(0, 0), (72, 1), (92, 0)])
    # -> [shadow, Pip group]; put them into the canvas layer list (shadow under Pip)

Rig (nested groups, origin of everything = the feet, bottom centre):
  "Pip"     offset = (x_keys, ground + y_keys)   angle = lean_keys (negative = leans right/forward)   scale = size
  "Squash"  scale = squash_keys(sq_keys) about the feet (height factor sy, width sy^-0.8)
    "Antenna"  root (0, 2.9), angle baked per frame by a spring (follow-through) from x/hops/sq/lean
    body, belly, cheeks
    "Eye" x2   centre (+-0.42, 2.12), scale = eye_keys (blink: (1.05, 0.08); fright: (1.25, 1.35))
      "Pupil"  offset = eye centre + look_keys (look direction, ~0.1 units)
    mouth: "Smile" / "Mouth open" switched by mouth_open (0/1, constant) - or lip sync via mouth_cues
Local units: body 2.95 high, 2.64 wide; with size 0.62 Pip is ~1.8 units tall (default 16x9 view).

Keys are (frame, value[, interp]) as everywhere in toon-2d. Pip faces right (pupils at +x); mirror with size<0 x
by passing flip=True.
"""
from motion import approx, hop_y, spring_follow, squash_keys
from sif import V, R, anim, comp_vec, group, circle, outline, shape, hexc

COLORS = {"body": "#fbb53f", "belly": "#ffe2a0", "cheek": "#f0807a", "antenna": "#ec5a4f",
          "antenna_glint": "#ffb3a6", "mouth": "#9e3b3b", "tongue": "#e8787a", "ink": "#3b2418"}
BODY = [(0, 0, 2.6, 0), (1.32, 1.05, 0, 2.2), (0, 2.95, -2.0, 0), (-1.32, 1.05, 0, -2.2)]
EYE_X, EYE_Y = 0.42, 2.12
MOUTH = (0, 1.62)


def blink(frames, keys=None):
    """Eye-scale keys with a blink (4 frames) at each frame in `frames`; merge with other eye keys yourself."""
    k = list(keys or [(0, (1, 1))])
    for b in frames:
        k += [(b - 2, (1, 1)), (b, (1.05, 0.08), "linear"), (b + 2, (1, 1))]
    return sorted(k, key=lambda x: x[0])


def pip(end, x_keys, y_keys, sq_keys=None, lean_keys=None, hops=None, ground=-2.6, size=0.62, fps=24,
        eye_keys=None, look_keys=None, mouth_open=None, mouth_cues=None, mouth_size=0.55, colors=None,
        name="Pip", antenna=True, antenna_kicks=(), shadow=True, flip=False, amount=None):
    """Build Pip; returns [shadow, pip_group] (or [pip_group] with shadow=False).

    x_keys / y_keys: position (y = height above `ground`, contacts "linear", apexes "halt").
    hops: [(start, end, height)] - only for the antenna simulation (parabolic path); None = derive from y_keys.
    mouth_cues: Rhubarb cues (lipsync.load_cues) - replaces the smile/O swap with lip sync.
    antenna_kicks: [(frame, degrees)] - something hits the antenna (a peck, a flick): a decaying wobble
        (~3 Hz, half-life ~8 frames) is added on top of the spring follow-through.
    """
    c = dict(COLORS, **(colors or {}))
    ink = hexc(c["ink"])
    sq_keys = sq_keys or [(0, 1.0)]
    lean_keys = lean_keys or [(0, 0)]
    eye_keys = eye_keys or [(0, (1, 1))]
    look_keys = look_keys or [(0, (0.10, 0.0))]
    mirror = -1 if flip else 1

    parts = []
    if antenna:
        def head(t):
            h = hop_y(hops, t) if hops else approx(y_keys, t)
            return (approx(x_keys, t), h + 2.95 * size * approx(sq_keys, t))
        ang = spring_follow(head, end, fps, root_angle=lambda t: approx(lean_keys, t))
        if antenna_kicks:
            import math
            def kick(f):
                s = 0.0
                for f0, deg in antenna_kicks:
                    if f >= f0:
                        t = (f - f0) / fps
                        s += deg * math.exp(-t / 0.33) * math.cos(2 * math.pi * 3.0 * t)
                return s
            ang = [(f, a + kick(f)) + tuple(r) for f, a, *r in ang]
        parts.append(group("Antenna", [
            outline("Antenna stalk", ink, [(0, 2.85, 0.0, 0.5), (0.05, 3.75, 0.1, 0.5)], 0.09, loop=False),
            circle("Antenna ball ink", ink, 0.24, (0.05, 3.85)),
            circle("Antenna ball", hexc(c["antenna"]), 0.18, (0.05, 3.85)),
            circle("Antenna ball glint", hexc(c["antenna_glint"]), 0.05, (0.0, 3.92)),
        ], origin=(0, 2.9), offset=V(0, 2.9), angle=anim("angle", ang)))
    parts.append(shape("Body", hexc(c["body"]), ink, BODY, 0.09))
    parts.append(group("Belly", [circle("Belly", hexc(c["belly"]), 0.78, (0, 0))], offset=V(0, 0.95), scale=V(1, 0.78)))
    parts += [group("Cheek", [circle("Cheek", hexc(c["cheek"], 0.55), 0.2, (0, 0), feather=0.06)],
                    offset=V(sx * 0.82, 1.62), scale=V(1, 0.6)) for sx in (-1, 1)]
    eye_scale = anim("vector", eye_keys)
    for ex in (-EYE_X, EYE_X):
        pupil = group("Pupil", [circle("Pupil", ink, 0.15, (0, 0)), circle("Glint", hexc("#ffffff"), 0.05, (-0.05, 0.06))],
                      offset=anim("vector", [(k[0], (ex + k[1][0], EYE_Y + k[1][1])) + tuple(k[2:]) for k in look_keys]))
        inner = [group("Eye shape", [circle("Eye ink", ink, 0.33, (0, 0)), circle("Eye", hexc("#ffffff"), 0.27, (0, 0))],
                       offset=V(ex, EYE_Y), scale=V(1, 1.22)), pupil]
        parts.append(group("Eye", inner, origin=(ex, EYE_Y), offset=V(ex, EYE_Y), scale=eye_scale))
    if mouth_cues is not None:
        from lipsync import mouth_layers
        parts += mouth_layers(mouth_cues, fps, center=MOUTH, size=mouth_size, ink=ink, offset_frames=-1)
    else:
        on = mouth_open or [(0, 0)]
        parts.append(outline("Smile", ink, [(-0.28, 1.72, 0.3, -0.35), (0, 1.55, 0.55, 0), (0.28, 1.72, 0.3, 0.35)],
                             0.075, loop=False, amount=anim("real", [(f, 1 - v, "constant") for f, v in on])))
        parts.append(group("Mouth open", [circle("Mouth ink", ink, 0.17, (0, 0)), circle("Mouth", hexc(c["mouth"]), 0.12, (0, 0)),
                                          circle("Tongue", hexc(c["tongue"]), 0.06, (0, -0.05))],
                           offset=V(*MOUTH), scale=V(0.9, 1.15), amount=anim("real", [(f, v, "constant") for f, v in on])))
    squash = group("Squash", parts, scale=anim("vector", squash_keys(sq_keys)))
    pos = comp_vec(anim("real", x_keys), anim("real", [(k[0], ground + k[1]) + tuple(k[2:]) for k in y_keys]))
    body = group(name, [squash], offset=pos, scale=V(size * mirror, size), angle=anim("angle", lean_keys), amount=amount)
    if not shadow:
        return [body]
    yk = [(k[0], k[1], k[2] if len(k) > 2 else "clamped") for k in y_keys]
    sh = group("Shadow", [circle("Shadow", hexc("#2a3a1a"), 0.9, (0, 0), feather=0.25)],
               offset=comp_vec(anim("real", x_keys), R(ground)),
               scale=anim("vector", [(f, ((1 - 0.22 * h) * 0.95 * size / 0.62, (1 - 0.22 * h) * 0.22 * size / 0.62), i)
                                     for f, h, i in yk]),
               amount=anim("real", [(f, 0.35 - 0.1 * h, i) for f, h, i in yk]))
    return [sh, body]
