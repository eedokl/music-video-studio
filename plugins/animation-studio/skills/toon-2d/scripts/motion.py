"""Motion helpers for Synfig scenes.

- squash_keys: height-factor keys -> volume-preserving (sx, sy) keys for anim("vector", ...)
- approx:      roughly evaluate keys in Python (for simulations)
- hop_y:       parabola height for jumps (matches keys: contact "linear", apex "halt")
- spring_follow: follow-through (antenna, tail, ear) as a damped spring -> angle keys
"""
import math


def squash_keys(keys, power=0.8):
    """[(f, sy[, interp])] -> [(f, (sx, sy)[, interp])] with sx = sy^-power."""
    return [(k[0], (k[1] ** -power, k[1])) + tuple(k[2:]) for k in keys]


def approx(keys, f):
    """Value of the keys at frame f (halt -> smooth, otherwise linear). Accurate enough for simulations."""
    if f <= keys[0][0]:
        return keys[0][1]
    for k0, k1 in zip(keys, keys[1:]):
        if k0[0] <= f <= k1[0]:
            u = (f - k0[0]) / (k1[0] - k0[0])
            i0 = k0[2] if len(k0) > 2 else "clamped"
            i1 = k1[2] if len(k1) > 2 else "clamped"
            out_ = i0[1] if isinstance(i0, tuple) else i0
            in_ = i1[0] if isinstance(i1, tuple) else i1
            if out_ == "halt" and in_ == "halt":
                u = u * u * (3 - 2 * u)
            elif out_ == "halt":
                u = u * u
            elif in_ == "halt":
                u = 1 - (1 - u) ** 2
            v0, v1 = k0[1], k1[1]
            if isinstance(v0, tuple):
                return tuple(a + (b - a) * u for a, b in zip(v0, v1))
            return v0 + (v1 - v0) * u
    return keys[-1][1]


def hop_y(hops, f):
    """hops: [(start_frame, end_frame, height)] -> height at f (0 on the ground)."""
    for t0, t1, h in hops:
        if t0 <= f <= t1:
            u = (f - t0) / (t1 - t0)
            return 4 * h * u * (1 - u)
    return 0.0


def spring_follow(root_pos, end_frame, fps=24, root_angle=None, freq=2.6, damping=0.12,
                  gain_x=0.075, gain_y=0.045, gain_rot=1.2, rest_deg=4.0, limit_deg=43.0):
    """Damped spring for an appendage hanging from a moving point.

    root_pos(f)   -> (x, y) world position of the root (e.g. top of the head), f as float
    root_angle(f) -> degrees, rotation of the body (the appendage lags behind the rotation)
    Returns: [(frame, angle_deg, "linear")] relative to the body - ready for anim("angle", ...).

    Signs for a character facing right: acceleration to the right tips the tip to the left
    (positive angle), a landing (braking upwards) tips it forward.
    Swing too small/large -> adjust gain_*; longer overshoot -> smaller damping.
    """
    sub = 8
    dt = 1 / fps / sub
    w = 2 * math.pi * freq
    k, c = w * w, 2 * damping * w
    theta, omega = 0.0, 0.0
    rest, lim = math.radians(rest_deg), math.radians(limit_deg)
    h = 0.25  # frames for finite differences

    def acc(t):
        (x0, y0), (x1, y1), (x2, y2) = root_pos(t - h), root_pos(t), root_pos(t + h)
        s = (h / fps) ** 2
        return (x2 - 2 * x1 + x0) / s, (y2 - 2 * y1 + y0) / s

    def rot_acc(t):
        if root_angle is None:
            return 0.0
        return math.radians(root_angle(t + h) - 2 * root_angle(t) + root_angle(t - h)) / (h / fps) ** 2

    out = []
    for f in range(end_frame + 1):
        for i in range(sub):
            t = f + i / sub
            ax, ay = acc(t)
            alpha = -k * (theta - rest) - c * omega + gain_x * ax - gain_y * ay - gain_rot * rot_acc(t)
            omega += alpha * dt
            theta = max(-lim, min(lim, theta + omega * dt))
        out.append((f, math.degrees(theta), "linear"))
    return out


def to_world(p, *transforms):
    """Convert a local point through nested groups into world coordinates.

    transforms: from inside to outside, each (offset, angle_deg, scale, origin) as in group().
    E.g. tongue root inside the squash group -> world:
        to_world(mouth, ((0, 0), 0, (sx, sy), (0, 0)), (pos, lean, (s, s), (0, 0)))
    With approx() for animated values this is only approximate for halt/clamped keys -
    for exact contact hold the pose during the contact (same value on two keys).
    """
    x, y = p
    for offset, angle, scale, origin in transforms:
        sx, sy = scale if isinstance(scale, tuple) else (scale, scale)
        x, y = (x - origin[0]) * sx, (y - origin[1]) * sy
        a = math.radians(angle)
        x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
        x, y = x + offset[0], y + offset[1]
    return x, y
