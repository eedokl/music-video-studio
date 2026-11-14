"""Acting styles for figures that leave the slide (one per figure, clip.json "style"), built on acting.py.

  jump     (default) look left/right, crouch, jump out with stretch, optional flip, land with squash
           - the reference clip "Fritz steps out of the slide"
  flutter  for winged figures: eyes dart left/right/up, short crouch, flaps out (the gesture part = wing beats every
           4 frames), glides down late (falls with u^1.6), lands softly          - reference: Felix in "Meet the cast"
  hop      hesitant: peeks down over the slide edge, tips forward and back, small hop (apex 0.6)
                                                                                 - reference: Hans in "Meet the cast"
  stuck    heavy figure: waddles forward, gets stuck in the slide (the slide stretches with it), struggles until
           "pop_at", a beat (stops, glances at the others for help), a last jerk -> pop, falls, lands with a big squash,
           shakes the head, camera shake                                         - reference: Helmut in "Meet the cast"
Each style returns a Routine: take-off, pop and landing frames, Synfig keys, the feet path through the room, the slide
bulge, when shading/outline start and the camera anchors. Keys of the reference were written in "block frames" and
are mapped onto the new timing with warp() (piecewise linear between anchors) - the technique of the reference.

Gestures (clip.json "gesture", at "gesture_at" or 19 frames after landing; several: "gestures"):
  fist | wave | nod   (acting.py tables)   look_up  eyes + head up, gesture part raised and held, two sparkles on the
  eyes (glasses flash)   wag  the follow part (tail) wags fast, then slowly   shake  head shake   none
"""
import math

import acting as A

STYLES = ("jump", "flutter", "hop", "stuck")
BITS = {"jump": 26, "flutter": 14, "hop": 18, "stuck": 34}


def warp(start, old, new):
    """Block frames (old anchors) -> clip frames: piecewise linear between the anchors, slope 1 outside."""
    def t(x):
        if x <= old[0]:
            v = new[0] + (x - old[0])
        elif x >= old[-1]:
            v = new[-1] + (x - old[-1])
        else:
            k = next(k for k in range(len(old) - 1) if x <= old[k + 1])
            v = new[k] + (x - old[k]) * (new[k + 1] - new[k]) / (old[k + 1] - old[k])
        return start + round(v)
    return t


def alt(start, end, step, a, b, ease="clamped"):
    out, v, f = [], a, start
    while f <= end:
        out.append((f, v, ease))
        v = b if v == a else a
        f += step
    return out


def jump_path(f, L, dur, start, land, apex, fall_pow=1.0):
    if f <= L:
        return list(start)
    if f >= L + dur:
        return list(land)
    u = (f - L) / dur
    x = start[0] + (land[0] - start[0]) * (1 - (1 - u) ** 2)
    z = start[2] + (land[2] - start[2]) * (1 - (1 - u) ** 1.7)
    y = start[1] + (land[1] - start[1]) * u ** fall_pow + 4 * apex * u * (1 - u)
    return [x, y, z]


class Routine:
    """Result of a style: frames, keys (Synfig), feet(f), bulge parameters, events."""
    def __init__(self, style, start, L, land_f, keys, feet, bulge, shade0, outline, events, cam_anchor, apex=1.6):
        self.style, self.start, self.L, self.land_f = style, start, L, land_f
        self.keys, self.feet, self.bulge, self.shade0 = keys, feet, bulge, shade0
        self.outline, self.events, self.cam_anchor, self.apex = outline, events, cam_anchor, apex
        self.pop = None


def build(style, s, g, spin="flip", spin_dir=-1, pop_at=None):
    """s = start frame; g = figure geometry (slot, land, q). pop_at only for "stuck" (default s + 133)."""
    slot, land, q = g["slot"], g["land"], g["q"]
    if style == "jump":
        L = s + A.LAUNCH
        k = A.step_out_keys(L, "none", spin, spin_dir)
        return Routine("jump", s, L, L + A.FLIGHT, k,
                       lambda f: A.feet_path(f, L, slot, land),
                       {"h": 1.9, "sigma": 1.25, "pop_z": 0.9, "amp": 0.9, "period": 7.5, "decay": 5.0, "pre": L - 8},
                       L + 2, None, {"look_left": s + 3, "look_right": s + 12, "crouch": L - 12},
                       [L - 6, L + 12, L + A.FLIGHT + 6], apex=1.6)
    if style == "flutter":
        T = warp(s, [0, 20, 80, 92, 132], [0, 4, 22, 28, 60])
        L, LD = T(92), T(132)
        k = {"eyes": [(s, (0, 0)), (T(20), (0, 0)), (T(26), (-0.08, 0)), (T(40), (-0.08, 0)), (T(46), (0.08, 0)),
                      (T(60), (0.08, 0)), (T(66), (0, 0.04)), (T(80), (0, 0))],
             "blink": [(s + 9, 1), (s + 11, 0.1), (s + 14, 1), (LD, 1), (LD + 2, 0.2), (LD + 5, 1)],
             "head": [(s, 0), (T(20), 0), (T(26), 3), (T(40), 3), (T(46), -3), (T(60), -3), (T(66), 0)],
             "gesture": [(s, 0), (T(84), 0), (T(90), -4)] + alt(L + 2, LD - 6, 4, 10, -4)
                        + [(LD, -5), (LD + 8, 2), (LD + 16, 0)],
             "sq": [(s, (1, 1)), (T(82), (1, 1)), (T(90), (1.08, 0.9), "halt"), (T(94), (0.92, 1.1)),
                    (T(102), (1, 1)), (LD, (1, 1)), (LD + 2, (1.1, 0.9)), (LD + 8, (0.97, 1.03)), (LD + 14, (1, 1))],
             "spin": [(s, 0)]}
        return Routine("flutter", s, L, LD, k, lambda f: jump_path(f, L, LD - L, slot, land, 0.9, 1.6),
                       {"h": 1.9, "sigma": 1.15, "pop_z": 0.45, "amp": 0.45, "period": 7.5, "decay": 5.0, "pre": L - 8},
                       L + 2, None, {"look_left": T(26), "look_right": T(46), "look_up": T(66), "crouch": T(90),
                                     "wing_beats": [f for f, *_ in alt(L + 2, LD - 6, 8, 1, 0)]},
                       [L - 6, L + 12, LD + 6], apex=0.9)
    if style == "hop":
        T = warp(s, [0, 12, 54, 64, 88], [0, 8, 34, 40, 64])
        L, LD = T(64), T(88)
        k = {"eyes": [(s, (0, 0)), (T(12), (0, 0)), (T(18), (0, -0.09)), (T(34), (0, -0.09)), (T(40), (0, 0)),
                      (T(48), (0, -0.06)), (T(54), (0, 0))],
             "blink": [(T(40), 1), (T(42), 0.1), (T(45), 1), (LD, 1), (LD + 2, 0.2), (LD + 5, 1)],
             "head": [(s, 0), (T(12), 0), (T(20), -3), (T(34), -3), (T(42), 3), (T(52), 3), (T(58), 0)],
             "tilt": [(s, 0), (T(14), 0), (T(24), -2.5), (T(34), -2.5), (T(44), 1.5), (T(54), 0)],
             "sq": [(s, (1, 1)), (T(54), (1, 1)), (T(61), (1.08, 0.9), "halt"), (T(65), (0.94, 1.08)),
                    (T(72), (1, 1)), (LD, (1, 1)), (LD + 2, (1.14, 0.84)), (LD + 8, (0.96, 1.05)), (LD + 14, (1, 1))],
             "gesture": [(s, 0), (LD, 0), (LD + 2, -3), (LD + 8, 3), (LD + 16, 0)],
             "spin": [(s, 0)]}
        return Routine("hop", s, L, LD, k, lambda f: jump_path(f, L, LD - L, slot, land, 0.6),
                       {"h": 2.2, "sigma": 1.3, "pop_z": 0.6, "amp": 0.6, "period": 7.5, "decay": 5.0, "pre": L - 8},
                       L + 2, None, {"peek": T(18), "tip_forward": T(44), "crouch": T(61)},
                       [L - 6, L + 12, LD + 6], apex=0.6)
    if style == "stuck":
        P = (pop_at - s) if pop_at is not None else 133
        P = max(P, 90)
        T = warp(s, [0, 36, 66, 110, 136, 152, 194, 216], [0, 18, 38, 70, P, P + 16, P + 46, P + 60])
        WD, ST, POP, LD = T(66), T(110), T(136), T(152)
        BEAT = POP - 16
        k = {"eyes": [(s, (0, 0)), (T(24), (0, 0)), (T(30), (0.07, 0)), (T(44), (0.07, 0)), (T(50), (0, -0.07)),
                      (T(64), (0, -0.07)), (T(70), (0, 0)), (BEAT, (0, 0)), (BEAT + 3, ("glance", 0.01)),
                      (BEAT + 8, ("glance", 0.01)), (BEAT + 10, (0, 0)), (POP + 2, (0, 0.08)), (LD + 4, (0, 0.08)),
                      (LD + 10, (0, 0))],
             "blink": [(T(56), 1), (T(58), 0.1), (T(62), 1), (LD, 1), (LD + 2, 0.15), (LD + 8, 1)],
             "head": [(s, 0), (T(24), 0), (T(32), 4), (T(48), 4), (T(56), 0), (ST, 0), (ST + 10, -2), (BEAT, -2),
                      (BEAT + 3, 2), (BEAT + 8, 2), (BEAT + 10, -2), (POP, -4), (LD, 3), (LD + 8, -4), (LD + 12, 4),
                      (LD + 16, -4), (LD + 20, 3), (LD + 24, 0)],
             "tilt": [(s, 0), (WD, 0)] + alt(WD + 6, ST - 4, 8, 4, -4) + [(ST, 0)]
                     + alt(ST + 2, BEAT - 2, 2, 1.5, -1.5) + [(BEAT, 0), (POP - 4, 1.5), (POP, 0), (POP + 8, -6),
                                                             (LD, 0)],
             "sq": [(s, (1, 1)), (WD, (1, 1))] + alt(WD + 6, ST - 4, 8, (0.98, 1.02), (1.02, 0.98))
                   + [(ST, (1, 1)), (ST + 12, (1.05, 0.95)), (BEAT, (1.03, 0.97)), (BEAT + 8, (1.03, 0.97)),
                      (POP - 4, (1.1, 0.9)), (POP, (0.9, 1.1)), (LD, (1, 1)), (LD + 2, (1.25, 0.72)),
                      (LD + 8, (0.94, 1.06)), (LD + 14, (1.03, 0.97)), (LD + 20, (1, 1))],
             "follow": [(s, 0), (ST, 0), (ST + 10, -3), (POP, 3), (LD, 0), (LD + 2, -3), (LD + 8, 2), (LD + 14, 0)],
             "spin": [(s, 0)]}

        def feet(f):
            sx, sy, _ = slot
            lx, ly, lz = land
            if f <= WD:
                return [sx, sy, 0.0]
            if f <= ST:
                return [sx, sy, 0.9 * q * (f - WD) / (ST - WD)]
            if f <= POP:
                return [sx, sy, (0.9 + 0.15 * A.smooth((f - ST) / (POP - ST))) * q]
            if f >= LD:
                return [lx, ly, lz]
            u = (f - POP) / (LD - POP)
            return [sx + (lx - sx) * u, sy + (ly - sy) * u * u + 4 * 0.25 * q * u * (1 - u), 1.05 * q + (lz - 1.05 * q) * u]
        r = Routine("stuck", s, WD, LD, k, feet,
                    {"h": 1.6, "sigma": 1.5, "pop_z": None, "amp": 1.1, "period": 9.0, "decay": 6.5, "pre": WD},
                    WD + 14, WD + 30, {"waddle": WD, "waddle_steps": [f for f, *_ in alt(WD + 6, ST - 4, 8, 1, 0)],
                                       "stuck": ST, "beat": BEAT, "head_shake": LD + 8, "recovered": T(194)},
                    [WD - 6, ST, LD + 6], apex=0.25)
        r.pop = POP
        r.shake_at = LD
        r.tag_default = T(194)
        return r
    raise SystemExit(f"unknown style '{style}' (one of {', '.join(STYLES)})")


def gesture_keys(kind, at, has_part=True, eye_dir=1):
    """Keys of one gesture whose main beat is at frame `at` (19 frames after landing by default)."""
    t0 = at - 49                                     # the acting.py tables are relative to take-off (landing = +30)
    sh = A.shift
    if kind in A.GESTURE_ARM:
        return {"sq": sh(A.GESTURE_SQ[kind], t0), "head": sh(A.GESTURE_HEAD[kind], t0),
                "gesture": sh(A.GESTURE_ARM[kind], t0)}
    if kind == "look_up":
        W = at
        return {"eyes": [(W - 4, (0, 0)), (W, (0.07 * eye_dir, 0.07)), (W + 40, (0.07 * eye_dir, 0.07)), (W + 50, (0, 0))],
                "head": [(W - 4, 0), (W + 2, 5), (W + 40, 5), (W + 50, 0)],
                "gesture": [(W + 4, 0), (W + 12, 10, "halt"), (W + 38, 10), (W + 48, 0)],
                "sparkle": [W + 14, W + 17]}
    if kind == "wag":
        return {"follow": [(at - 4, 0)] + alt(at, at + 60, 5, 8, -8) + alt(at + 64, at + 150, 9, 4, -4) + [(at + 156, 0)]}
    if kind == "shake":
        return {"head": [(at - 2, 0), (at, 3), (at + 4, -4), (at + 8, 4), (at + 12, -4), (at + 16, 3), (at + 20, 0)]}
    if kind in (None, "none"):
        return {}
    raise SystemExit(f"unknown gesture '{kind}'")


def merge(keys, extra, mode="splice"):
    """Add gesture keys: for each channel, drop the base keys inside the gesture's frame range, then insert."""
    for ch, v in extra.items():
        if ch == "sparkle":
            keys.setdefault("sparkle", []).extend(v)
            continue
        if not v:
            continue
        a, b = v[0][0], v[-1][0]
        base = [k for k in keys.get(ch, []) if not (a <= k[0] <= b)]
        keys[ch] = sorted(base + list(v), key=lambda k: k[0])
    return keys
