"""Classic cartoon acting for slide figures: keyframes per figure for the Synfig rig (squash, spin, joints, eyes,
blink, idle) and the path through the 2.5D room (feet, shading flat -> round, slide bulge, camera).

Actions (one per figure, frames relative to the figure's "start"):
  step_out  looks left/right, blinks, crouches (anticipation), jumps out of the slide (stretch; the slide bulges
            like rubber and lets go with a pop, paper bits, a dashed outline stays), turns into a rounded figure in the
            air (spin optional), lands with squash and follow-through, a gesture, the name tag pops, idles
  watch     stays flat in the slide but is alive: eyes follow the action, blinks, tiny breathing
  return    (ending of a loopable clip) hops back into its slot; the slide is as at the start again
Variants come from the creative seed unless clip.json fixes them: spin ("flip" | "none"), gesture ("fist" |
"wave" | "nod"), side of the camera.
The timing of step_out reproduces the reference clip "Fritz steps out of the slide" (launch 46 frames after start,
pop ~6 frames later, landing 30 frames after launch, gestures 19/30 after landing, tag 42 after landing).
"""
import math

LAUNCH = 46          # start -> take-off
FLIGHT = 30          # take-off -> landing
SETTLE = 93          # landing -> end of the routine (incl. tag and idle)


def shift(keys, d):
    return [(k[0] + d,) + tuple(k[1:]) for k in keys]


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def keyed(keys, f):
    """[(frame, value)] with smooth steps; value = number or list."""
    if f <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f <= f1:
            u = smooth((f - f0) / max(1e-6, f1 - f0))
            if isinstance(v0, (list, tuple)):
                return [a + (b - a) * u for a, b in zip(v0, v1)]
            return v0 + (v1 - v0) * u
    return keys[-1][1]


# ---- step_out: keys relative to take-off (frame 0 = take-off), taken from the reference probe ----
SQ = [(-16, (1, 1)), (-4, (1.12, 0.84), "halt"), (0, (1.10, 0.86)), (3, (0.86, 1.20)), (10, (0.96, 1.05)),
      (16, (0.93, 0.95)), (26, (0.95, 1.02)), (30, (1.0, 1.0)), (32, (1.16, 0.80)), (37, (0.95, 1.07)),
      (43, (1.02, 0.98)), (48, (1, 1))]
GESTURE_SQ = {"fist": [(50, (1.03, 0.96)), (54, (0.99, 1.02)), (58, (1, 1)), (62, (1.03, 0.96)), (66, (0.99, 1.02)),
                       (71, (1, 1))],
              "wave": [(52, (1.01, 0.99)), (60, (1, 1)), (68, (1.01, 0.99)), (74, (1, 1))],
              "nod": [(52, (1.02, 0.97)), (58, (1, 1)), (64, (1.02, 0.97)), (70, (1, 1))]}
HEAD = [(-46, 0), (-42, 3), (-37, 3), (-33, -2), (-28, -2), (-24, 0), (-12, 0), (-4, 2.5), (3, -2), (12, 0),
        (32, 3), (38, -1.5), (44, 0)]
GESTURE_HEAD = {"fist": [(50, 4), (56, 1), (62, 4), (70, 0)], "wave": [(50, 2), (60, -1), (70, 2), (78, 0)],
                "nod": [(50, -5), (55, 2), (60, -5), (66, 1), (72, 0)]}
ARM = [(-12, 0), (-4, -3), (2, 9), (12, 6), (30, 4), (32, -2), (38, 2), (44, -2)]
GESTURE_ARM = {"fist": [(49, 9), (54, 3), (60, 9.5), (66, 4), (72, 6), (92, 5)],
               "wave": [(48, 8), (52, 2), (56, 8), (60, 2), (64, 8), (68, 2), (74, 5)],
               "nod": [(50, 2), (70, 0)]}
FOLLOW = [(-12, 0), (-4, -3), (2, 4), (10, 3), (22, -2), (30, -1), (32, -4), (37, 3.5), (42, -2), (47, 1), (52, 0),
          (60, 1.2), (66, -0.8), (72, 0)]
EYES = [(-46, (0, 0)), (-43, (-0.09, 0.01)), (-37, (-0.09, 0.01)), (-34, (0.09, 0)), (-28, (0.09, 0)), (-24, (0, 0)),
        (-4, (0, -0.03)), (2, (0, 0.03)), (12, (0, 0))]
BLINK = [(-23, 1), (-21, 0.1), (-18, 1), (30, 1), (32, 0.35), (35, 1), (82, 1), (84, 0.1), (87, 1)]
TAG_AT = 72          # after take-off (= 42 after landing)


def step_out_keys(t0, gesture="fist", spin="flip", spin_dir=-1):
    """Synfig keys for a figure taking off at frame t0."""
    g = gesture if gesture in GESTURE_SQ else None              # None / "none": no gesture (added later)
    k = {"sq": shift(SQ + (GESTURE_SQ[g] if g else []), t0), "head": shift(HEAD + (GESTURE_HEAD[g] if g else []), t0),
         "gesture": shift(ARM + (GESTURE_ARM[g] if g else []), t0), "follow": shift(FOLLOW, t0),
         "eyes": shift(EYES, t0), "blink": shift(BLINK, t0)}
    k["spin"] = [(t0 + 8, 0, "halt"), (t0 + 26, 360 * spin_dir, "halt")] if spin == "flip" else [(t0, 0)]
    return k


def return_keys(t0, spin_total):
    """Hop back into the slot: crouch, jump (t0 = take-off), land flat in the slide at t0 + 22.
    spin_total = the spin angle reached on the way out (kept: a full flip is upright again)."""
    return {"sq": [(t0 - 10, (1, 1)), (t0 - 2, (1.1, 0.88), "halt"), (t0, (1.08, 0.9)), (t0 + 3, (0.9, 1.14)),
                   (t0 + 12, (0.97, 1.03)), (t0 + 22, (1, 1)), (t0 + 24, (1.08, 0.92)), (t0 + 30, (1, 1))],
            "head": [(t0 - 10, 0), (t0 - 2, 2), (t0 + 4, -2), (t0 + 22, 0)],
            "gesture": [(t0 - 10, 0), (t0 + 2, 6), (t0 + 22, 0)],
            "follow": [(t0 - 10, 0), (t0 + 2, 4), (t0 + 14, -2), (t0 + 24, 1), (t0 + 30, 0)],
            "eyes": [(t0 - 10, (0, 0))], "blink": [(t0 + 21, 1), (t0 + 23, 0.1), (t0 + 26, 1)],
            "spin": [(t0 + 2, spin_total, "halt"), (t0 + 18, spin_total, "halt")]}


def idle_keys(rng, end, ramps, amp=1.0):
    """Procedural life (weight shift, head/part follow, breathing, irregular blinks), as extra keys that the rig puts
    into their OWN groups. ramps = [(f0, f1, a0, a1)] scale the amplitude (0 while the figure must be in rest pose)."""
    def env(f):
        v = 0.0
        for f0, f1, a0, a1 in ramps:
            if f0 <= f <= f1:
                v = a0 + (a1 - a0) * smooth((f - f0) / max(1, f1 - f0))
            elif f > f1:
                v = a1
        return v

    def noise(a, pmin, pmax, step=6):
        p1, p2 = rng.uniform(pmin, pmax) * 24, rng.uniform(pmin, pmax) * 24 * 1.7
        ph1, ph2 = rng.uniform(0, 6.28), rng.uniform(0, 6.28)
        return [(f, round(env(f) * a * (0.7 * math.sin(2 * math.pi * f / p1 + ph1) + 0.3 * math.sin(
            2 * math.pi * f / p2 + ph2)), 3)) for f in range(0, end + step, step)]
    per = rng.uniform(2.0, 2.5) * 24
    k = {"idle_tilt": noise(0.9 * amp, 3, 5), "idle_head": noise(1.3 * amp, 2, 4), "idle_part": noise(2.0 * amp, 2, 3),
         "idle_breath": [(f, round(1 + env(f) * 0.008 * amp * (0.5 - 0.5 * math.cos(2 * math.pi * f / per)), 4))
                         for f in range(0, end + 4, 4)]}
    return k


def auto_blinks(rng, f0, f1):
    out, f = [(f0, 1)], f0 + rng.randint(20, 60)
    while f < f1 - 6:
        out += [(f, 1), (f + 2, 0.1), (f + 5, 1)]
        if rng.random() < 0.15:
            out += [(f + 8, 0.1), (f + 11, 1)]
        f += rng.randint(60, 120)
    return out


def feet_path(f, t_launch, start, land, apex=1.6):
    """Feet position during a jump from start [x, y, z] to land [x, y, z] (take-off t_launch, FLIGHT frames)."""
    if f <= t_launch:
        return list(start)
    if f >= t_launch + FLIGHT:
        return list(land)
    u = (f - t_launch) / FLIGHT
    x = start[0] + (land[0] - start[0]) * (1 - (1 - u) ** 2)
    z = start[2] + (land[2] - start[2]) * (1 - (1 - u) ** 1.7)
    y = start[1] + (land[1] - start[1]) * u + 4 * apex * u * (1 - u)
    return [x, y, z]


def return_path(f, t0, start, slot, dur=22, apex=1.3):
    if f <= t0:
        return list(start)
    if f >= t0 + dur:
        return list(slot)
    u = (f - t0) / dur
    x = start[0] + (slot[0] - start[0]) * smooth(u)
    z = start[2] + (slot[2] - start[2]) * (u ** 1.4)
    y = start[1] + (slot[1] - start[1]) * u + 4 * apex * u * (1 - u)
    return [x, y, z]
