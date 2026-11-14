"""Drawing helpers for scene.py - everything the scene features draw that is not the rig itself.

  arm_geometry(svg, PIV)                      shoulders, arm length, sleeve and skin colour of a rig figure
  typing_arms(...), keyboard(...)             own arms IN FRONT of the body on a keyboard prop (hands always visible)
  air_guitar(...)                             guitar + strum arm in front of the body, forearm swings around the elbow
  spot_cone(...), disco_cones(...), confetti(...)   lights
  silhouette(...)                             a dark faceless figure (head, shoulders, grin) for window / shadow gags
  inset(...)                                  round narrator inset (glow, frame, round clip)
All coordinates of the figure parts are figure coordinates (feet = (0, 0), units of the rig at scale 1/72); the
reference values come from "Prompts!" (Tim: shoulder (0.86, 3.61), arm length 1.85) and scale with the arm length.
"""
import math
import re

from sif import V, anim, group, circle, region, outline, hexc, clipped

INK_HEX = "#2b1d14"
REF_ARM = 1.85                       # Tim's arm length (shoulder pivot -> hand) in rig units


def _keys(k, n):
    seen = {}
    for it in k:
        if 0 <= it[0] <= n:
            seen[it[0]] = it
    out = [seen[f] for f in sorted(seen)]
    return out or [(0, k[0][1] if k else 0)]


def arm_geometry(svg_path, PIV):
    """Shoulders, arm length (pivot -> hand circle), sleeve colour (first fill of arm_r), skin (hand circle fill)."""
    text = open(svg_path, encoding="utf-8").read()
    m = re.search(r'<g[^>]*id="arm_r"[^>]*>(.*?)</g>', text, re.S)
    sleeve, skin, armlen, hand_r = "#d94c41", "#f2c9a0", REF_ARM, 0.236
    if m:
        body = m.group(1)
        fills = [f for f in re.findall(r'fill="(#[0-9a-fA-F]{6})"', body) if f.lower() != "#ff00ff"]
        if fills:
            sleeve = fills[0]
        c = re.findall(r'<circle[^>]*cx="([\d.]+)"[^>]*cy="([\d.]+)"[^>]*r="([\d.]+)"[^>]*fill="(#[0-9a-fA-F]{6})"', body)
        c = [x for x in c if x[3].lower() not in ("#f0f", "#ff00ff") and float(x[2]) > 5]
        if c and "arm_r" in PIV:
            cx, cy, r, skin = float(c[0][0]), float(c[0][1]), float(c[0][2]), c[0][3]
            hx, hy = (cx - 200) / 72, -(cy - 590) / 72
            sx, sy = PIV["arm_r"]
            armlen = max(0.8, math.hypot(hx - sx, hy - sy))
            hand_r = r / 72
    sh_r = PIV.get("arm_r", (0.86, 3.61))
    sh_l = PIV.get("arm_l", (-sh_r[0], sh_r[1]))
    return {"sh_l": sh_l, "sh_r": sh_r, "len": armlen, "s": armlen / REF_ARM, "sleeve": sleeve, "skin": skin,
            "hand_r": hand_r, "cx": (sh_l[0] + sh_r[0]) / 2}


def hand_pos(geo, side):
    """Hand on the keyboard (figure coords): elbows out, hands apart ON the keys - the lesson of the reference."""
    sh = geo["sh_l"] if side < 0 else geo["sh_r"]
    s, dy = geo["s"], geo.get("hand_dy", 0.0)            # hand_dy: hands lower/higher (keyboard on a desk)
    return (sh[0] - 0.08 * side * s, sh[1] - 0.95 * s + dy), (sh[0] + 0.52 * side * s, sh[1] - 0.75 * s + dy / 2), sh


def keyboard_box(geo):
    (hx, hy), _, _ = hand_pos(geo, 1)
    hw = abs(hx - geo["cx"]) + 0.92 * geo["s"]
    top = hy + 0.04
    return geo["cx"] - hw, top, geo["cx"] + hw, top - 0.32 * geo["s"]


def keyboard(geo, strikes, n_frames, rng, stand=False, light="#bfe9ff", body="#3a3f4a", key="#5a6170", amount=None):
    """Keyboard in front of the figure; keys light up on the strikes [(frame, side)]. stand=True draws an X stand
    down to the floor (stage without a desk)."""
    ink = hexc(INK_HEX)
    x0, y0, x1, y1 = keyboard_box(geo)
    out = []
    if stand:
        for a, b in (((geo["cx"] - 0.7, 0.0), (geo["cx"] + 0.55, y1)), ((geo["cx"] + 0.7, 0.0), (geo["cx"] - 0.55, y1))):
            out.append(outline("Stand leg", ink, [(a[0], a[1], 0, 0), (b[0], b[1], 0, 0)], 0.16, loop=False))
            out.append(outline("Stand leg", hexc("#30343e"), [(a[0], a[1], 0, 0), (b[0], b[1], 0, 0)], 0.1, loop=False))
    pts = [(x0, y0, 0, 0), (x1, y0, 0, 0), (x1, y1, 0, 0), (x0, y1, 0, 0)]
    out += [region("Keyboard", hexc(body), pts), outline("Keyboard outline", ink, pts, 0.05)]
    n = 9
    kw = (x1 - x0 - 0.3) / n
    ky0, ky1 = y0 - 0.06 * geo["s"], y0 - 0.22 * geo["s"]
    flashes = {i: [(0, 0.0, "constant")] for i in range(n)}
    for f, side in strikes:
        i = int(rng.integers(0, n // 2 + 1)) + (n // 2 if side > 0 else 0)
        i = min(i, n - 1)
        flashes[i] += [(f, 1.0, "constant"), (f + 2, 0.0, "constant")]
    for i in range(n):
        kx = x0 + 0.15 + i * kw
        kp = [(kx + 0.02, ky0, 0, 0), (kx + kw - 0.04, ky0, 0, 0), (kx + kw - 0.04, ky1, 0, 0), (kx + 0.02, ky1, 0, 0)]
        out.append(region("Key", hexc(key), kp))
        out.append(region("Key lights up", hexc(light), kp, amount=anim("real", _keys(flashes[i], n_frames))))
    return group("Keyboard prop", out, amount=amount)


def typing_arms(geo, strikes, n_frames):
    """Two arms in front of the body: sleeve from the shoulder over the elbow (out) to the hand on the keys;
    the striking hand dips briefly. strikes: [(frame, side)] with side -1 = left, +1 = right."""
    ink, skin, sleeve = hexc(INK_HEX), hexc(geo["skin"]), hexc(geo["sleeve"])
    hr = geo["hand_r"] * 0.95
    parts = []
    for side in (-1, 1):
        ha, el, sh = hand_pos(geo, side)
        tap = [(0, (0.0, 0.0))]
        for f, sd in strikes:
            if sd == side:
                tap += [(f - 1, (0.0, 0.0), "linear"), (f, (0.0, -0.07), "linear"), (f + 2, (0.0, 0.0), "linear")]
        pts = [(sh[0], sh[1], 0, 0), (el[0], el[1], 0, 0), (ha[0], ha[1], 0, 0)]
        w = 0.31 * geo["s"]
        hand = group("Hand", [circle("Hand outline", ink, hr + 0.05, ha), circle("Hand", skin, hr, ha),
                              circle("Finger", hexc("#e8b58a"), hr * 0.32, (ha[0] - 0.08 * side, ha[1] - 0.12))],
                     offset=anim("vector", _keys(tap, n_frames)))
        parts += [outline("Sleeve outline", ink, pts, w + 0.11, loop=False), outline("Sleeve", sleeve, pts, w, loop=False), hand]
    return parts


def air_guitar(geo, strum_frames, n_frames, body_col="#c0262d", neck_col="#8a5f42"):
    """Air guitar across the body and a strum arm in front of it (forearm + hand swing around the elbow on every
    strum frame). Coordinates from the reference (Tim), scaled with the arm length and the shoulder width."""
    s, wx = geo["s"], abs(geo["sh_r"][0] - geo["cx"]) / 0.86
    ys = geo["sh_r"][1]
    P = lambda x, y: (geo["cx"] + x * wx, ys + (y - 3.61) * s)
    ink, skin, sleeve = hexc(INK_HEX), hexc(geo["skin"]), hexc(geo["sleeve"])
    strum = [(0, 0.0)]
    for f in strum_frames:
        strum += [(f, -12.0, "linear"), (f + 5, 7.0, "linear")]
    SH, EL, HA = (geo["sh_r"][0], geo["sh_r"][1] - 0.03), P(1.38, 2.5), P(0.8, 1.62)
    seg = lambda a, b: [(a[0], a[1], 0, 0), (b[0], b[1], 0, 0)]
    w = 0.31 * s
    neck = seg(P(0.2, 1.75), P(-1.7, 2.75))
    g = [outline("Neck outline", ink, neck, 0.3 * s, loop=False), outline("Neck", hexc(neck_col), neck, 0.2 * s, loop=False),
         circle("Headstock outline", ink, 0.24 * s, P(-1.8, 2.8)), circle("Headstock", hexc("#2b2b2b"), 0.18 * s, P(-1.8, 2.8)),
         circle("Body outline", ink, 0.72 * s, P(0.45, 1.45)), circle("Body", hexc(body_col), 0.65 * s, P(0.45, 1.45)),
         circle("Upper bout", hexc(body_col), 0.5 * s, P(0.05, 1.85)), circle("Sound hole", ink, 0.18 * s, P(0.35, 1.55)),
         outline("Strings", hexc("#e8e8e8"), seg(P(0.55, 1.35), P(-1.7, 2.75)), 0.03, loop=False),
         circle("Fret hand outline", ink, 0.22 * s, P(-1.45, 2.6)), circle("Fret hand", skin, 0.17 * s, P(-1.45, 2.6)),
         outline("Upper arm outline", ink, seg(SH, EL), w + 0.11, loop=False), outline("Upper arm", sleeve, seg(SH, EL), w, loop=False),
         group("Forearm (strum)", [outline("Forearm outline", ink, seg(EL, HA), w + 0.09, loop=False),
                                   outline("Forearm", sleeve, seg(EL, HA), w - 0.02, loop=False),
                                   circle("Strum hand outline", ink, 0.25 * s, HA), circle("Strum hand", skin, 0.2 * s, HA)],
               origin=EL, offset=V(*EL), angle=anim("angle", _keys(strum, n_frames)))]
    return g


def spot_cone(desc, x, top, floor, col, amount=None, width=0.7, spread=2.1, alpha=0.16):
    """Light cone from above onto x plus a bright floor circle."""
    return [region(desc, hexc(col, alpha), [(x - width, top, 0, 0), (x + width, top, 0, 0),
                                             (x + spread, floor, 0, 0), (x - spread, floor, 0, 0)], amount=amount),
            circle(desc + " floor", hexc(col, 0.35), spread * 0.95, (x, floor + 0.05), feather=0.9, amount=amount)]


def disco_cones(beat_frames, palette, n_frames, top=4.4, floor=-3.4, on_level=0.85, off_level=0.4):
    """Four coloured cones crossing the stage, alternating on the beat (pairs swap on every beat)."""
    out = []
    spans = ((-6.0, -1.5), (6.0, 1.5), (-3.5, 2.5), (3.5, -2.5))
    for j, (x0, x1) in enumerate(spans):
        amt = [(0, 0.0, "constant")]
        for i, (f, inside) in enumerate(beat_frames):
            if inside:
                on = (i + j) % 2 == 0
                amt += [(f, on_level if on else 0.0, "constant"), (f + 5, off_level if on else 0.0, "constant")]
            else:
                amt.append((f, 0.0, "constant"))
        out.append(region(f"Disco light {j}", hexc(palette[j % len(palette)], 0.75),
                          [(x0 - 0.3, top, 0, 0), (x0 + 0.3, top, 0, 0), (x1 + 1.6, floor, 0, 0), (x1 - 1.6, floor, 0, 0)],
                          amount=anim("real", _keys(amt, n_frames))))
    return out


def confetti(rng, f0, f1, palette, count, n_frames, x_range=(-6.5, 6.5), top=4.5, bottom=-3.8):
    """Seeded confetti: snippets fall between f0 and f1, spinning, each 40-80 frames long."""
    out = []
    for c in range(count):
        fa = int(rng.uniform(f0, max(f0 + 1, f1 - 30)))
        x = rng.uniform(*x_range)
        dur = int(rng.uniform(40, 80))
        col = palette[c % len(palette)]
        w, h = rng.uniform(0.05, 0.09), rng.uniform(0.03, 0.05)
        out.append(group("Confetti", [region("Snippet", hexc(col), [(-w, -h, 0, 0), (w, -h, 0, 0), (w, h, 0, 0), (-w, h, 0, 0)])],
                         offset=anim("vector", [(fa, (x, top), "linear"), (fa + dur, (x + rng.uniform(-1, 1), bottom), "linear")]),
                         angle=anim("angle", [(fa, 0, "linear"), (fa + dur, rng.uniform(-720, 720), "linear")]),
                         amount=anim("real", [(0, 0.0, "constant"), (fa, 1.0, "constant"), (min(fa + dur, f1 + 10), 0.0, "constant")])))
    return out


def silhouette(col="#05070d", grin="#f3f3f3", glint="#6a6f80", alpha=1.0):
    """Faceless dark figure (head + shoulders + a grin), centre (0, 0), about 2.2 units high."""
    c = hexc(col, alpha)
    return [circle("Head", c, 0.55, (0.0, 0.6)),
            region("Shoulders", c, [(-1.2, -0.6, 0, 0), (-0.8, 0.05, 0.6, 0.4), (0.8, 0.05, 0.6, -0.4), (1.2, -0.6, 0, 0)]),
            region("Body", c, [(-1.2, -0.6, 0, 0), (1.2, -0.6, 0, 0), (1.2, -1.6, 0, 0), (-1.2, -1.6, 0, 0)]),
            outline("Grin", hexc(grin, min(1.0, alpha + 0.1)), [(-0.3, 0.5, 0.2, -0.25), (0.0, 0.35, 0.4, 0), (0.3, 0.5, 0.2, 0.25)],
                    0.05, loop=False),
            circle("Jacket glint", hexc(glint, 0.8 * alpha), 0.12, (0.4, -0.2), feather=0.08)]


def inset(contents, center, radius, pop_keys, frame="#ffd23f", glow="#c9a6ff"):
    """Round inset: glow, ink + coloured frame, contents clipped to the circle. contents: groups (with amounts)."""
    return group("Narrator inset", [
        circle("Glow", hexc(glow, 0.55), radius + 0.35, (0, 0), feather=0.3),
        circle("Frame outline", hexc(INK_HEX), radius + 0.13, (0, 0)),
        circle("Frame", hexc(frame), radius + 0.08, (0, 0)),
        clipped("Round", circle("Mask", hexc("#000000"), radius, (0, 0)), contents),
    ], origin=(0, 0), offset=V(*center), scale=anim("vector", pop_keys))
