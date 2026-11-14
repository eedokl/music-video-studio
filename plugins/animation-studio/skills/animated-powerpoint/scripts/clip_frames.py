"""Per-frame values of the 2.5D stage (clip.py step "plan" -> stage.json "frames"): camera with shakes, every
figure's feet / shading / shadow / tag, the slide bulge, the paper bits (simple physics) and the sparkles."""
import math

import acting as A

GRAV = -14.0             # paper bits: gravity (world units / s^2), three sub-steps per frame


def shaken(cam, shakes, fr):
    """Camera shake after a heavy landing: 14 frames, decaying."""
    for sa in shakes:
        tt = fr - sa
        if 0 <= tt < 14:
            s_ = 0.07 * math.exp(-tt / 4)
            cam = list(cam)
            cam[1] += s_ * math.sin(tt * 2.6)
            cam[0] += s_ * 0.6 * math.sin(tt * 3.7)
    return cam


def bulge_of(g, fr, feet, R_ret):
    """How far the slide bulges at figure g: pushed before take-off, stretched until the pop, then it rings out
    (and once more when the figure hops back in)."""
    R, q = g["R"], g["q"]
    L = R.L
    bp, pop = R.bulge, g["pop"]
    b = 0.0
    if bp["pre"] <= fr < L:
        b = 0.12 * A.smooth((fr - bp["pre"]) / 8)
    elif L <= fr < pop:
        b = max(0.12, feet[2])
    elif fr >= pop:
        tt = fr - pop
        b = bp["amp"] * q * math.exp(-tt / bp["decay"]) * math.cos(2 * math.pi * tt / bp["period"])
    if R_ret is not None and fr >= R_ret + 22:
        tt = fr - R_ret - 22
        b = -0.22 * q * math.exp(-tt / 4.0) * math.cos(2 * math.pi * tt / 7.0)
    elif R_ret is not None and fr >= R_ret:
        b = 0.0
    return b


def shadow_of(C, q, feet):
    """Soft shadow + contact shadow under the feet, fading in as the figure leaves the slide plane."""
    height = feet[1] - C.floor
    out_of_slide = A.smooth((feet[2] - 0.4 * q) / (1.0 * q))
    return {"x": feet[0], "z": feet[2] - 0.2 * q, "s": 2.2 * q * (1 + 0.22 * height / q),
            "a": 0.38 * out_of_slide * max(0.0, 1 - height / (4.5 * q)),
            "contact": 0.62 * out_of_slide * max(0.0, 1 - height / (0.35 * q))}


def tag_of(g, fr, R_ret):
    """Name tag scale: pops in with an overshoot, hides after tag_hide, folds away before the return hop."""
    tag = 0.0
    t0 = g["tag_t"]
    if fr >= t0 and (R_ret is None or fr < R_ret - 6):
        u = (fr - t0) / 12
        tag = 1.0 if u >= 1 else (1.18 * math.sin(u * math.pi * 0.62) / math.sin(math.pi * 0.62) if u < 0.6
                                  else 1.0 + 0.09 * math.cos((u - 0.6) / 0.4 * math.pi) * (1 - u) / 0.4)
        if g.get("tag_hide") is not None and fr > g["tag_hide"]:
            tag *= max(0.0, 1 - (fr - g["tag_hide"]) / 8)
    if R_ret is not None and R_ret - 14 <= fr < R_ret - 6 and fr >= t0:
        tag = 1 - A.smooth((fr - R_ret + 14) / 8)
    return tag


def figure_frame(C, G, names, fr, R_ret):
    """All figures at frame fr -> (figure values, out-of-slide bit mask, strongest bulge, its centre, its sigma,
    {name: (feet, shade)})."""
    figd, out_mask, bulge, bc, bs = [], 0, 0.0, [0, 0], 1.25
    feet_now = {}
    for i, n in enumerate(names):
        g = G[n]
        if g.get("watch"):
            figd.append({"feet": [round(v, 4) for v in g["slot"]], "shade": 0,
                         "shadow": {"x": 0, "z": 0, "s": 1, "a": 0, "contact": 0}, "tag": 0})
            continue
        R, q = g["R"], g["q"]
        L = R.L
        feet = R.feet(fr)
        shade = A.smooth((fr - R.shade0) / 20)
        if R_ret is not None and fr >= R_ret:
            feet = A.return_path(fr, R_ret, g["land"], g["slot"])
            shade = 1 - A.smooth((fr - R_ret) / 18)
        feet_now[n] = (feet, shade)
        outside = fr >= (R.outline if R.outline is not None else L) and not (R_ret is not None and fr >= R_ret + 22)
        if outside:
            out_mask |= 1 << i
        b = bulge_of(g, fr, feet, R_ret)
        if abs(b) > abs(bulge):
            bulge, bc, bs = b, [g["slot"][0], g["slot"][1] + R.bulge["h"] * q], R.bulge["sigma"] * q
        shadow = shadow_of(C, q, feet)
        tag = tag_of(g, fr, R_ret)
        figd.append({"feet": [round(v, 4) for v in feet], "shade": round(shade, 4),
                     "shadow": {k: round(v, 4) for k, v in shadow.items()}, "tag": round(tag, 4)})
    return figd, out_mask, bulge, bc, bs, feet_now


def step_bits(C, G, bits, fr, R_ret, dt):
    """Advance the paper bits one frame (they fly from the pop on, rest on the floor) -> their values."""
    pieces = []
    for bt in bits:
        g = G[bt["fig"]]
        if bt["pos"] is None:
            bt["pos"] = list(bt["p"])
        active = fr >= g["pop"] and (R_ret is None or fr < R_ret)
        if active and not bt["rest"]:
            for _ in range(3):
                bt["v"][1] += GRAV * dt
                bt["v"][0] *= 0.985
                bt["v"][2] *= 0.985
                bt["pos"] = [p + v * dt for p, v in zip(bt["pos"], bt["v"])]
                bt["ang"] = [a + r * dt for a, r in zip(bt["ang"], bt["rot"])]
                if bt["pos"][1] <= C.floor + 0.01:
                    bt["pos"][1] = C.floor + 0.01
                    bt["rest"] = True
                    bt["ang"] = [math.pi / 2, 0, bt["ang"][2]]
                    break
        pieces.append([round(v, 4) for v in bt["pos"] + bt["ang"]] + [round(bt["size"], 4), 1 if active else 0])
    return pieces


def sparkle_frame(G, sparks, fr, cam, feet_now):
    """Sparkles at frame fr: pop in in 4 frames, fade in 10; they turn with the figure towards the camera."""
    sp = []
    for s_ in sparks:
        t_ = fr - s_["f"]
        if 0 <= t_ < 14 and s_["fig"] in feet_now:
            (fx, fy, fz), shade = feet_now[s_["fig"]]
            ry = shade * math.atan2(cam[0] - fx, cam[2] - fz)
            dx, dy = s_["d"]
            sp.append([round(fx + dx * math.cos(ry), 4), round(fy + dy, 4), round(fz + 0.12 - dx * math.sin(ry), 4),
                       round((t_ / 4 if t_ < 4 else max(0.0, 1 - (t_ - 4) / 10)) * 0.9 * G[s_["fig"]]["q"], 4),
                       round(t_ * 0.12, 3), 1])
        else:
            sp.append([0, 0, 0, 0, 0, 0])
    return sp


def stage_frames(C, G, names, cam_keys, shakes, bits, sparks, R_ret, end):
    """-> ({out-of-slide mask: slide state index}, [per-frame values]) for frames 0..end."""
    states, frames = {}, []
    dt = 1 / C.fps / 3
    for fr in range(end + 1):
        cam = shaken(A.keyed(cam_keys, fr), shakes, fr)
        figd, out_mask, bulge, bc, bs, feet_now = figure_frame(C, G, names, fr, R_ret)
        pieces = step_bits(C, G, bits, fr, R_ret, dt)
        sp = sparkle_frame(G, sparks, fr, cam, feet_now)
        states.setdefault(out_mask, len(states))
        fd = {"cam": [round(v, 4) for v in cam[:3]], "look": [round(v, 4) for v in cam[3:]],
              "state": states[out_mask], "bulge": round(bulge, 4), "bulge_center": [round(v, 4) for v in bc],
              "bulge_sigma": round(bs, 4), "figs": figd, "bits": pieces}
        if sparks:
            fd["sparkles"] = sp
        frames.append(fd)
    return states, frames
