"""Acting layer of scene.py (project.json "acting"): the figures look at each other and react.

Without it a figure only knows the beat: a listener turns to the first other singer ON the beat and holds that pose.
With it every figure has a gaze that follows what happens in the song, frame by frame:

  listen    eyes go to whoever sings now (when two sing: the one who started last); the eyes move first, the head
            follows a few frames later; every figure reacts with its own small delay (seed), so a change of singer
            runs through the group instead of snapping on one frame
  hold      after the last note the listeners keep looking at the singer for a moment, then look ahead again
  glance    a singer looks ahead (at the audience) and glances at a partner near the end of some of its lines
  nod       a listener nods at the end of some lines of the other
  brows     a listener's brows jump at a gag word
Gestures and actions (typing, guitar) win: the gaze rests while they run; while dancing it is halved.

  plan(c, k, x0, spans, screen=False) -> None (acting off) or {"gaze": (gx, gy), "head": deg, "brow": v, "n": {...}}
        arrays per section frame 0..N; gaze is normalised (-1..1: full look to the side / up), head in degrees with
        the sign of the rig's head angle toward the partner, brow in rig units
  keys(arr, scale=1.0) / vector_keys(gx, gy, sx, sy)   sparse linear keyframes of such arrays
  add_to_keys(c, base, arr)   base keyframes + array as one keyframe per frame (for the head: the hair follows it)

project.json:  "acting": true | {"strength": 1.0, "glances": true, "nods": true, "brows": true}
               a section may set "acting": false (or its own dict).
"""
import numpy as np

import creative  # noqa: E402
from motion import approx
from song_project import allowed, word_matches

HEAD_DEG = 4.0            # head tilt toward the partner at strength 1 (the face turn does the rest)
NOD_DEG = 6.0
BROW_UP = 0.12
HOLD = 0.8                # s a listener keeps looking after the singer stopped
MIN_LOOK = 8              # frames: a target shorter than this is not worth a turn


def spec(c):
    """The acting settings of this section as a dict, or None when acting is off."""
    a = c.A.get("acting", c.P.get("acting", False))
    if not a:
        return None
    a = dict(a) if isinstance(a, dict) else {}
    return {"strength": float(a.get("strength", 1.0)), "glances": a.get("glances", True), "nods": a.get("nods", True),
            "brows": a.get("brows", True)}


def _dir(c, x0, other, from_screen):
    """Normalised gaze (dx, dy) from a figure at x0 toward another figure of the section."""
    to_screen = c.figs_cfg[other].get("kind") == "screen"
    if to_screen:
        sx = (c.SCREEN[0] + c.SCREEN[2]) / 2
        dx = sx - x0
        return (float(np.clip(dx / 3.0, -1, 1)), 0.45)                 # the screen hangs above the heads
    dx = c.places.get(other, 0.0) - x0
    if from_screen:                                                    # the face on the screen looks down at them
        return (float(np.clip(dx / 4.0, -1, 1)), -0.55)
    return (float(np.sign(dx) * np.clip(abs(dx) / 2.5, 0.6, 1.0)) if abs(dx) > 0.05 else 0.0, 0.0)


def _targets(c, k):
    """Per section frame: the figure k looks at (None = ahead). Raw - before reaction delays."""
    N, fps, S = c.N, c.fps, c.S
    others = [o for o in c.names if o != k]
    hold = round(HOLD * fps)
    out, started, last, last_f = [None] * (N + 1), {}, None, -10 ** 6
    for f in range(N + 1):
        t = S + f / fps
        now = [o for o in others if c.act(o, t)]
        for o in others:
            if o in now:
                started.setdefault(o, f)
            else:
                started.pop(o, None)
        if c.act(k, t):                                                # singing: ahead (glances are added later)
            last = None
        elif now:
            last, last_f = max(now, key=lambda o: started[o]), f       # the one who started last
            out[f] = last
        elif last is not None and f - last_f <= hold:
            out[f] = last
    return out


def _delayed(raw, base_delay, rnd):
    """Step function of targets with a reaction delay per change; short flickers are dropped."""
    N = len(raw) - 1
    runs, f = [], 0
    while f <= N:
        g = f
        while g + 1 <= N and raw[g + 1] == raw[f]:
            g += 1
        runs.append([f, g, raw[f]])
        f = g + 1
    kept = []
    for r in runs:                                                     # drop flickers: merge into the run before
        if kept and (r[1] - r[0] + 1) < MIN_LOOK and r[2] is not None:
            kept[-1][1] = r[1]
        elif kept and kept[-1][2] == r[2]:
            kept[-1][1] = r[1]
        else:
            kept.append(r)
    out = [kept[0][2]] * (N + 1)
    for r in kept[1:]:
        d = base_delay + int(rnd.integers(0, 3))
        for f in range(min(r[0] + d, N + 1), N + 1):
            out[f] = r[2]
    return out


def plan(c, k, x0, spans=(), screen=False):
    a = spec(c)
    if a is None or len(c.names) < 2:
        return None
    N, fps, S, E = c.N, c.fps, c.S, c.E
    rnd = np.random.default_rng(creative.rng(c.P, f"acting:{c.section}:{k}").getrandbits(32))
    base_delay = int(rnd.integers(3, 8))                               # this figure's reaction time in frames
    tgt = _delayed(_targets(c, k), base_delay, rnd)
    tx, ty = np.zeros(N + 1), np.zeros(N + 1)
    for f, o in enumerate(tgt):
        if o is not None:
            tx[f], ty[f] = _dir(c, x0, o, screen)
    counts = {"turns": (tgt[0] is not None) + sum(1 for f in range(1, N + 1) if tgt[f] != tgt[f - 1] and tgt[f] is not None),
              "glances": 0, "nods": 0, "brows": 0, "delay": base_delay}

    def frac(o, t0, t1):
        fs = [c.act(o, t) for t in np.arange(t0, max(t1, t0 + 0.05), 1 / fps)]
        return sum(fs) / max(len(fs), 1)

    others = [o for o in c.names if o != k]
    nod = np.zeros(N + 1)
    for i, ln in enumerate(c.lines):
        if not (S <= ln["t"] and ln["end"] <= E + 0.01):
            continue
        mine = frac(k, ln["t"], ln["end"])
        if a["glances"] and mine > 0.5 and ln["end"] - ln["t"] > 1.0 and rnd.random() < 0.6:
            o = others[int(rnd.integers(0, len(others)))]              # a singer glances at a partner at the line end
            f0, f1 = c.F(ln["end"] - 0.45), c.F(ln["end"] + 0.15)
            dx, dy = _dir(c, x0, o, screen)
            tx[max(f0, 0):min(f1, N) + 1], ty[max(f0, 0):min(f1, N) + 1] = dx, dy
            counts["glances"] += 1
        elif a["nods"] and not screen and mine < 0.2 and any(frac(o, ln["t"], ln["end"]) > 0.5 for o in others) \
                and rnd.random() < 0.5:
            f0 = c.F(ln["end"] + 0.05)                                 # a listener nods when the other's line ends
            for j, v in enumerate((0.45, 0.85, 1.0, 0.8, 0.55, 0.3, 0.12)):
                if 0 <= f0 + j <= N:
                    nod[f0 + j] = max(nod[f0 + j], v)
            counts["nods"] += 1
    brow = np.zeros(N + 1)
    if a["brows"]:
        for g in c.P.get("gags") or []:
            if not isinstance(g, dict) or "word" not in g or not allowed(g, c.section):
                continue
            for w in c.words:
                if S <= w["t"] < E and word_matches(w["word"], g["word"]) and not c.act(k, w["t"]):
                    f0 = c.F(w["t"] + 0.08)
                    for j, v in enumerate((0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 0.75, 0.5, 0.25)):
                        if 0 <= f0 + j <= N:
                            brow[f0 + j] = max(brow[f0 + j], v)
                    counts["brows"] += 1

    # gestures and actions win; dancing halves the gaze; a silent freeze stays a freeze
    w = np.ones(N + 1)
    for f in range(N + 1):
        t = S + f / fps
        if c.gesture_at(k, t) or any(s[0] <= t < s[1] for s in spans):
            w[f] = 0.0
        elif c.in_dance(t):
            w[f] = 0.5
    tx, ty = tx * w, ty * w

    gx, gy, head = np.zeros(N + 1), np.zeros(N + 1), np.zeros(N + 1)
    step = 0.4                                                         # eyes: a full look to the side in ~3 frames
    for f in range(1, N + 1):
        gx[f] = gx[f - 1] + np.clip(tx[f] - gx[f - 1], -step, step)
        gy[f] = gy[f - 1] + np.clip(ty[f] - gy[f - 1], -step, step)
        lead = tx[max(f - 2, 0)]                                       # the head starts two frames after the eyes
        head[f] = head[f - 1] + 0.25 * (lead - head[f - 1])            # ... and eases in
    k_s = a["strength"]
    turn_raw = head.copy()
    head = head * HEAD_DEG * k_s + nod * NOD_DEG * k_s * (w > 0)
    turn = np.clip(turn_raw, -1, 1) * min(k_s, 1.3)   # -1..1: the face turned fully to the left / right
    return {"gaze": (gx * min(k_s, 1.3), gy * min(k_s, 1.3)), "head": head, "brow": brow * BROW_UP * k_s * (w > 0),
            "turn": turn, "n": counts}


def keys(arr, scale=1.0, eps=1e-4):
    """Sparse linear keyframes [(f, v, "linear")] of a per-frame array."""
    n, out = len(arr), [(0, float(arr[0] * scale), "linear")]
    for f in range(1, n):
        prev, nxt = arr[f - 1], arr[f + 1] if f + 1 < n else arr[f]
        if abs((nxt - arr[f]) - (arr[f] - prev)) > eps:                # the slope changes here
            out.append((f, float(arr[f] * scale), "linear"))
    return out


def vector_keys(gx, gy, sx, sy, eps=1e-4):
    n, out = len(gx), [(0, (float(gx[0] * sx), float(gy[0] * sy)), "linear")]
    for f in range(1, n):
        g = f + 1 if f + 1 < n else f
        if abs((gx[g] - gx[f]) - (gx[f] - gx[f - 1])) > eps or abs((gy[g] - gy[f]) - (gy[f] - gy[f - 1])) > eps:
            out.append((f, (float(gx[f] * sx), float(gy[f] * sy)), "linear"))
    return out


def add_to_keys(c, base, arr):
    """base keyframes (scalar) + per-frame array -> one linear keyframe per frame where the array acts, the base
    keys elsewhere. Used for the head angle: hair and other followers read these keys, so they turn with it."""
    base = c.keys(base)
    on = np.abs(arr) > 1e-3
    if not on.any():
        return base
    near = on.copy()
    near[1:] |= on[:-1]
    near[:-1] |= on[1:]
    out = {f: it for f, it in ((it[0], it) for it in base) if not near[min(max(f, 0), len(arr) - 1)]}
    for f in np.flatnonzero(near):
        out[int(f)] = (int(f), float(approx(base, int(f)) + arr[f]), "linear")
    return [out[f] for f in sorted(out)]


# ------------------------------------------------------------------ facial expressions (project.json "expressions")
# brow = (left, right) lift in rig units, angle = degrees each brow is tipped (positive: inner ends down = angry),
# eye = vertical eye scale (1 = normal), mouth = the mouth shown while the figure is silent, head = extra tilt,
# cheek = the cheeks pushed up (a smile reaches the eyes).
EXPRESSIONS = {
    "grin":      {"brow": (0.13, 0.13), "angle": -9, "eye": 0.70, "mouth": "grin", "head": 5, "cheek": 0.09},
    "skeptical": {"brow": (0.22, -0.08), "angle": 11, "eye": 0.70, "mouth": "smirk", "head": -8},
    "shock":     {"brow": (0.22, 0.22), "angle": -8, "eye": 1.25, "mouth": "o", "head": 0},
    "angry":     {"brow": (-0.07, -0.07), "angle": 18, "eye": 0.72, "mouth": "frown", "head": -3},
    "sad":       {"brow": (0.04, 0.04), "angle": -16, "eye": 0.90, "mouth": "frown", "head": -8},
}
# how far each part of the face slides at a full turn (rig units; the head outline, ears and hair stay)
TURN = {"eyes": 0.17, "glasses": 0.17, "brows": 0.15, "nose": 0.27, "cheeks": 0.10, "mouth": 0.20}


def expression_spans(c, k):
    """[(t0, t1, name)] of figure k in this section from project.json "expressions":
    {"figure": k, "expression": name, "word" | "line" | "from": ..., "duration": s | "to": s}."""
    out = []
    for r in c.P.get("expressions") or []:
        if not isinstance(r, dict) or r.get("figure") != k or r.get("expression") not in EXPRESSIONS \
                or not allowed(r, c.section):
            continue
        starts = []
        if r.get("word"):
            starts = [w["t"] - 0.08 for w in c.words if word_matches(w["word"], r["word"])]
        elif r.get("line"):
            starts = [ln["t"] for ln in c.lines if ln["text"].lower().startswith(str(r["line"]).lower())]
        elif r.get("from") is not None:
            starts = [float(r["from"])]
        for t0 in starts:
            t1 = float(r["to"]) if r.get("to") is not None and not r.get("word") else t0 + float(r.get("duration", 1.5))
            if t1 > c.S and t0 < c.E:
                out.append((max(t0, c.S), min(t1, c.E), r["expression"]))
    return sorted(out)


def express(c, k):
    """None, or per-frame arrays {"brow_l", "brow_r", "angle", "eye", "head", "cheek"} plus "mouths": {mouth: on-keys} and
    "sync": on-keys of the lip-sync mouth (off while an expression mouth shows - only on frames the figure is silent)."""
    spans = expression_spans(c, k)
    if not spans:
        return None
    N, fps, S = c.N, c.fps, c.S
    ch = {n: np.zeros(N + 1) for n in ("brow_l", "brow_r", "angle", "head", "cheek")}
    eye = np.ones(N + 1)
    mouth = [None] * (N + 1)
    cues = c.cues_in_window(k)

    def silent(f):
        t = f / fps
        return [s for tt, s in cues if tt <= t + 1 / fps][-1:] in ([], ["X"], ["A"])

    for t0, t1, name in spans:
        e, f0, f1 = EXPRESSIONS[name], c.F(t0), c.F(t1)
        for f in range(max(f0, 0), min(f1 + 6, N) + 1):
            u = min(1.0, (f - f0 + 1) / 3) if f <= f1 else max(0.0, 1 - (f - f1) / 6)   # in: 3 frames, out: 6
            ch["brow_l"][f], ch["brow_r"][f] = e["brow"][0] * u, e["brow"][1] * u
            ch["angle"][f], ch["head"][f] = e["angle"] * u, e["head"] * u
            ch["cheek"][f] = e.get("cheek", 0.0) * u
            eye[f] = 1 + (e["eye"] - 1) * u
            if f <= f1 and silent(f):
                mouth[f] = e["mouth"]

    def onoff(test):
        ks, last = [], None
        for f in range(N + 1):
            v = 1.0 if test(mouth[f]) else 0.0
            if v != last:
                ks.append((f, v, "constant"))
                last = v
        return ks
    kinds = sorted({m for m in mouth if m})
    return {**ch, "eye": eye, "mouths": {m: onoff(lambda x, m=m: x == m) for m in kinds},
            "sync": onoff(lambda x: x is None), "n": [(round(t0 - S, 2), n) for t0, _, n in spans]}


def expression_mouths(center, size, ink):
    """{name: [layers]} - the mouths of the expressions, drawn like the lip-sync mouths (lipsync.mouth_drawings)."""
    from lipsync import _mouth_hole
    from sif import outline
    cx, cy = center
    s, lw = size, 0.12 * size
    return {
        "grin": [outline("Mouth grin", ink, [(cx - 0.6 * s, cy + 0.2 * s, 0.5 * s, -0.9 * s), (cx, cy - 0.3 * s, 1.1 * s, 0),
                                             (cx + 0.6 * s, cy + 0.2 * s, 0.5 * s, 0.9 * s)], lw * 1.1, loop=False)],
        "frown": [outline("Mouth frown", ink, [(cx - 0.42 * s, cy - 0.2 * s, 0.4 * s, 0.55 * s), (cx, cy + 0.04 * s, 0.8 * s, 0),
                                               (cx + 0.42 * s, cy - 0.2 * s, 0.4 * s, -0.55 * s)], lw * 1.1, loop=False)],
        "smirk": [outline("Mouth smirk", ink, [(cx - 0.38 * s, cy - 0.06 * s, 0.4 * s, 0), (cx + 0.1 * s, cy - 0.07 * s, 0.5 * s, 0.05 * s),
                                               (cx + 0.44 * s, cy + 0.16 * s, 0.3 * s, 0.45 * s)], lw * 1.1, loop=False)],
        "o": _mouth_hole("Mouth o", cx, cy - 0.06 * s, 0.34 * s, 0.42 * s, ink, line=lw),
    }
