"""The SVG figures of scene.py: per-beat behaviour (sing / listen / dance / gestures / actions), blinking, lip sync,
hair on a spring, aura, steam puffs, typing / air guitar in front of the body, spotlight and "show" appearances.

  figure(c, k, nr, ...)       one rig figure as a Synfig group (c = scene_context.SceneContext)
  show_spec / show_keys       section "show": a figure appears only from a line / word / time on
  appear_keys                 spotlight: visible only in its own light while it sings
  steam_frames                project.json "steam": puffs rising from the head
  strike_frames               alternating key strikes on the beat grid (typing)
"""
import numpy as np

import creative  # noqa: E402
from song_project import allowed, word_matches
from lipsync import mouth_layers
from motion import squash_keys, approx, spring_follow
from sif import V, R, anim, comp_vec, group, circle, hexc
from svg2sif import normalize, load_svg, emit
import scene_fx as fx
import scene_acting as acting

INK = hexc("#2b1d14")
DANCE_STYLES = ("arms", "bounce", "step", "twist")
SWAY = {"dance": 5.0, "sing": 3.0, "listen": 2.0, "idle": 1.5, "typing": 1.0, "guitar": 3.0}  # body lean per mode
FOLLOW = ("haare_hinten", "haare", "hair", "zopf", "ponytail", "antenne", "antenna")  # parts that swing behind the head
KEY_SOUNDS = ("fit/key/medium", "fit/key/thock", "fit/key/lubed")
GUITAR_COLOURS = ("#c0262d", "#2f6fb5", "#e0a030", "#3a3a3a", "#7b3fa0")


def strike_frames(c, k, t0, t1, speed):
    """Alternating key strikes on the beat grid: 3-4 per beat (fast) or 2-3 (slow), seeded per figure."""
    per = creative.pick(c.P, f"typing:{k}:{speed}", (3, 4) if speed == "fast" else (2, 3))
    grid = [b["t"] for b in c.beats if t0 - 0.6 <= b["t"] <= t1 + 0.6] or list(np.arange(t0, t1 + 0.5, 0.5))
    out, side = [], -1
    for b0, b1 in zip(grid, grid[1:]):
        for j in range(per):
            t = b0 + (b1 - b0) * j / per
            if t0 <= t < t1:
                out.append((c.F(t), side))
                side = -side
    return out


def _beat_keys(c, k, x0, style, spans, acted=False):
    """Per-beat keyframes of one figure: (arm_l, arm_r, head, look, brow, sq, by, step, sway).
    acted: the acting layer (scene_acting.py) turns eyes and head to the singer - the listen pose keeps only its
    small beat nod here."""
    beats, names, figs_cfg, places, fps, act = c.beats, c.names, c.figs_cfg, c.places, c.fps, c.act
    arm_l, arm_r, head, look, brow, sq, by, step = [], [], [], [], [], [], [], [(0, 0.0)]
    sway = [(0, 0.0)]
    for i, bt in enumerate(beats):
        t, f = bt["t"], c.F(bt["t"])
        up, down = i % 2 == 0, bt["downbeat"]
        half = f + round((beats[i + 1]["t"] - t) * fps / 2) if i + 1 < len(beats) else f + 5
        others = [o for o in names if o != k and act(o, t)]
        toward = (np.sign(places.get(others[0], 0.0) - x0) if others and others[0] in places else
                  (1.0 if (others and figs_cfg[others[0]].get("kind") == "screen" and x0 < 0) else 0.0))
        ac = next((s for s in spans if s[0] <= t < s[1]), None)
        g = c.gesture_at(k, t)
        mode = (ac[2] if ac else None) or g or ("freeze" if c.quiet(t) else "dance" if c.in_dance(t) else
                                                "sing" if act(k, t) else "listen" if others else "idle")
        lean = SWAY.get(mode, 0.0) * (0.5 if style == "bounce" and mode == "dance" else 1.0)
        if mode == "dance" and style == "step":
            lean *= 1 if bt["beat"] % 2 else -1             # lean into the step
        elif mode == "listen" and toward:
            lean *= -toward if up else -toward * 0.3        # lean toward the singer and back a little
        else:
            lean *= 1 if up else -1
        sway.append((f, lean))
        if mode == "typing":                          # look at the keys, small nod; rig arms are hidden
            arm_l.append((f, 8)); arm_r.append((f, -8)); head.append((f, 2 if i % 2 else -2))
            look.append((f, (0.0, -0.07))); brow.append((f, 0.02)); sq += [(f, 0.99), (f + 4, 1.0)]; by.append((f, 0.0))
        elif mode == "guitar":                        # rock: headbang on the beat, deep knees; strum arm in front
            arm_l.append((f, -32)); arm_r += [(f, -16), (half, -2)]
            head += [(f, 12 if down else 8), (half, -6)]; look.append((f, (0.0, -0.04))); brow.append((f, 0.1))
            sq += [(f - 2, 1.04), (f, 0.88), (f + 4, 1.03)]; by += [(f, -0.08), (f + 4, 0.06)]
        elif mode == "dance" and style == "bounce":     # hops on every beat, arms pumping
            arm_l.append((f, -100 if up else -30)); arm_r.append((f, 30 if up else 100))
            head.append((f, 4 if up else -4)); look.append((f, (0.0, 0.04))); brow.append((f, 0.08))
            sq += [(f - 2, 0.9), (f, 1.08), (f + 4, 0.97)]; by += [(f - 2, 0.0), (f + 2, 0.32), (f + 6, 0.0)]
        elif mode == "dance" and style == "step":     # wide side steps, arms swing against the step
            side = 0.6 if bt["beat"] % 2 else -0.6
            arm_l.append((f, -40 if side > 0 else -110)); arm_r.append((f, 110 if side > 0 else 40))
            head.append((f, 8 if side > 0 else -8)); look.append((f, (0.05 * (1 if side > 0 else -1), 0.02)))
            brow.append((f, 0.05)); sq += [(f, 0.95), (f + 4, 1.01)]; by.append((f, 0.0))
            step += [(f - 3, step[-1][1]), (f + 3, side)]
        elif mode == "dance" and style == "twist":    # head and arms twist, small squash, no steps
            arm_l.append((f, -150 if up else -20)); arm_r.append((f, 20 if up else 150))
            head.append((f, -12 if up else 12)); look.append((f, (0.07 if up else -0.07, 0.0))); brow.append((f, 0.1))
            sq += [(f - 1, 1.02), (f, 0.96), (f + 3, 1.0)]; by.append((f, 0.0))
        elif mode == "dance":                         # "arms": arms up/down, side step on the downbeat
            arm_l.append((f, -140 if up else -60)); arm_r.append((f, 60 if up else 140))
            head.append((f, -6 if up else 6)); look.append((f, (0.0, 0.03))); brow.append((f, 0.06))
            sq += [(f - 2, 1.03), (f, 0.93), (f + 4, 1.02)]; by += [(f - 3, 0.1), (f, -0.04), (f + 4, 0.04)]
            if down:
                step += [(f - 3, step[-1][1]), (f + 3, 0.35 if bt["bar"] % 2 else -0.35)]
        elif mode == "sing":
            arm_r.append((f, 110 if down and bt["bar"] % 2 else 35))
            arm_l.append((f, -150 if (down and bt["bar"] % 4 == 0) else -20))
            head.append((f, 7 if down else -2)); look.append((f, (0.0, 0.02))); brow.append((f, 0.07 if down else 0.03))
            sq += [(f - 2, 1.02), (f, 0.96), (f + 4, 1.01)]; by.append((f, 0.0))
        elif mode == "listen" and acted:
            arm_l.append((f, 6)); arm_r.append((f, -6)); head.append((f, 2 if up else -1))
            look.append((f, (0.0, 0.0))); brow.append((f, 0.05)); sq += [(f, 0.99), (f + 4, 1.0)]
            by.append((f, 0.0))
        elif mode == "listen":
            arm_l.append((f, 6)); arm_r.append((f, -6)); head.append((f, 9 * (toward or 1)))
            look.append((f, (0.09 * toward, 0.0))); brow.append((f, 0.05)); sq += [(f, 0.99), (f + 4, 1.0)]
            by.append((f, 0.0))
        elif mode == "freeze":
            arm_l.append((f, 4)); arm_r.append((f, -4)); head.append((f, 0)); look.append((f, (0.0, 0.0)))
            brow.append((f, 0.12)); sq.append((f, 1.0)); by.append((f, 0.0))
        elif mode == "scare":
            arm_l.append((f, -150)); arm_r.append((f, 150)); head.append((f, 0)); look.append((f, (0.0, 0.04)))
            brow.append((f, 0.18)); sq += [(f - 3, 0.9), (f, 1.12), (f + 5, 1.0)]; by += [(f, 0.25), (f + 6, 0.0)]
        elif mode == "cheer":                         # arms up and OUT (V shape) - straight up reads as hands at the head
            arm_l.append((f, -120 if up else -105)); arm_r.append((f, 120 if up else 105))
            head.append((f, 4 if up else -4)); look.append((f, (0.0, 0.05))); brow.append((f, 0.1))
            sq += [(f - 2, 0.92), (f + 2, 1.06), (f + 6, 1.0)]; by += [(f, 0.3 if up else 0.0)]
        elif mode == "point":
            arm_r.append((f, 95)); arm_l.append((f, -5)); head.append((f, -3)); look.append((f, (0.08, 0.02)))
            brow.append((f, 0.08)); sq.append((f, 1.0)); by.append((f, 0.0))
        elif mode == "scratch":
            arm_r.append((f, 160 if up else 150)); arm_l.append((f, -5)); head.append((f, 9))
            look.append((f, (0.0, 0.06))); brow.append((f, -0.03)); sq.append((f, 0.98)); by.append((f, 0.0))
        elif mode == "nod":
            arm_l.append((f, 4)); arm_r.append((f, -4)); head.append((f, 10 if up else -6))
            look.append((f, (0.0, 0.0))); brow.append((f, 0.06)); sq.append((f, 1.0)); by.append((f, 0.0))
        elif mode == "sad":
            arm_l.append((f, 2)); arm_r.append((f, -2)); head.append((f, -10)); look.append((f, (0.0, -0.05)))
            brow.append((f, -0.06)); sq.append((f, 0.96)); by.append((f, -0.05))
        else:
            arm_l.append((f, 5)); arm_r.append((f, -5)); head.append((f, 3 if up else -3))
            look.append((f, (0.0, 0.0))); brow.append((f, 0.0)); sq += [(f, 1.0), (f + 5, 1.01)]; by.append((f, 0.0))
    return arm_l, arm_r, head, look, brow, sq, by, step, sway


def figure(c, k, nr, x=None, scale=None, floor=None, actions=True, front_out=None, back_out=None):
    """One SVG figure. nr staggers the blinks; x / scale / floor override place, set scale and floor (panels);
    actions=False skips actions, steam, spotlight and "show" (panel close-ups). Own arms and props of an action go to
    front_out, an aura to back_out (behind all figures) when given."""
    P, A, S, E, N, F, fps, keys = c.P, c.A, c.S, c.E, c.N, c.F, c.fps, c.keys
    cfg = c.figs_cfg[k]
    src = P.path(cfg["svg"])
    plain = normalize(src, out_dir=P.cache)
    root, PIV = load_svg(plain, scale=1 / 72, origin=(200, 590))
    x0 = c.places[k] if x is None else x
    Kf = c.K if scale is None else scale
    FL = c.FLOOR if floor is None else floor
    style = (A.get("dance_style", {}).get(k) if isinstance(A.get("dance_style"), dict) else A.get("dance_style")) \
        or cfg.get("dance_style") or creative.pick(P, f"dance:{k}", DANCE_STYLES)   # one style per figure for the
    #   whole film (SKILL: "dance style per figure"; per section it switched visibly at a cut - user test); a section's
    #   own "dance_style" still changes it on purpose
    c.styles_used[k] = style
    spans = c.act_spans.get(k, []) if actions else []
    act_k = acting.plan(c, k, x0, spans) if actions else None       # project.json "acting": gaze, nods, brows
    arm_l, arm_r, head, look, brow, sq, by, step, sway = _beat_keys(c, k, x0, style, spans, acted=act_k is not None)
    gaze = brow_act = None
    if act_k:
        head = acting.add_to_keys(c, head, act_k["head"])           # in the head keys: the hair follows them
        gaze = anim("vector", acting.vector_keys(*act_k["gaze"], 0.10, 0.06))
        brow_act = comp_vec(R(0), anim("real", acting.keys(act_k["brow"])))
        c.acting_used[k] = act_k["n"]
    expr = acting.express(c, k) if actions else None                # project.json "expressions"
    if expr:
        head = acting.add_to_keys(c, head, expr["head"])
        c.acting_used.setdefault(k, {})["expressions"] = expr["n"]
    turn = act_k["turn"] if act_k else None

    def turned(layer, part):
        """the face turn: this part of the face slides sideways inside the head outline"""
        if turn is None:
            return layer
        return group(f"acting turn {part}", [layer],
                     offset=anim("vector", acting.vector_keys(turn, turn * 0, acting.TURN[part], 0.0)))

    def eye(pid, kids):
        if expr and pid in PIV:                       # expression: eyes wide / narrowed, under the blink
            px, py = PIV[pid]
            kids = [group(f"expression {pid}", kids, origin=(px, py), offset=V(px, py),
                          scale=anim("vector", acting.vector_keys(expr["eye"] * 0 + 1, expr["eye"], 1.0, 1.0)))]
        return turned(pivot(pid, kids, scale=anim("vector", blink)), "eyes")

    def brows(kids):
        if expr and len(kids) == 2 and "brauen" in PIV:   # each brow lifts and tips on its own
            by_ = PIV["brauen"][1]
            xs = [PIV.get("auge_l", (-0.5, 0))[0], PIV.get("auge_r", (0.5, 0))[0]]
            kids = [group(f"expression brow {j}", [kid], origin=(xs[j], by_),
                          offset=anim("vector", acting.vector_keys(expr[lr] * 0 + xs[j], expr[lr] + by_, 1.0, 1.0)),
                          angle=anim("angle", acting.keys(expr["angle"], sg)))
                    for j, (kid, lr, sg) in enumerate(zip(kids, ("brow_l", "brow_r"), (-1.0, 1.0)))]
        return turned(group("brauen", acted(kids, "brow", brow_act),
                            offset=comp_vec(R(0), anim("real", keys(brow)))), "brows")

    def mouth():
        center = PIV.get("mund", (0, 6))
        m = mouth_layers(cues, fps, center=center, size=msize, ink=INK, offset_frames=-1)
        if expr and expr["mouths"]:                  # silent + expression: its own mouth instead of the sync mouth
            draw = acting.expression_mouths(center, msize, INK)
            m = [group("Mouth sync", m, amount=anim("real", expr["sync"]))] + \
                [group(f"Mouth {n}", draw[n], amount=anim("real", ks)) for n, ks in expr["mouths"].items()]
        return [turned(group("Mouth", m), "mouth")] if (turn is not None or expr) else m
    blink = [(0, (1, 1))]
    for t in np.arange(S + 1.1 + 0.7 * nr, E, 3.7 + 0.4 * nr):
        f = F(t)
        blink += [(f - 1, (1, 1)), (f + 1, (1.05, 0.1), "linear"), (f + 3, (1, 1))]
    cues = c.cues_in_window(k)
    msize = float(cfg.get("mouth", 0.58))

    # rig arms switched off (amount) while an action draws its own arms in front of the body
    typ = [s for s in spans if s[2] == "typing"]
    gtr = [s for s in spans if s[2] == "guitar"]

    def onoff(sp):
        ks = [(0, 0.0, "constant")]
        for t0, t1, _, _ in sp:
            ks += [(F(t0), 1.0, "constant"), (F(t1), 0.0, "constant")]
        return ks
    typ_on, gtr_on = onoff(typ), onoff(gtr)
    amt_l = [(f, 1.0 - v, i) for f, v, i in typ_on] if typ else None
    amt_r = None
    if typ or gtr:
        fr = sorted({x[0] for x in typ_on} | {x[0] for x in gtr_on})
        step_v = lambda ks, f: [v for ff, v, _ in ks if ff <= f][-1]
        amt_r = [(f, (1.0 - step_v(typ_on, f)) * (1.0 - step_v(gtr_on, f)), "constant") for f in fr]

    def pivot(pid, kids, **kw):
        if pid not in PIV:
            return group(pid, kids)
        px, py = PIV[pid]
        return group(pid, kids, origin=(px, py), offset=V(px, py), **kw)

    def acted(kids, name, offset):
        """the acting layer's own offset under the beat offset (both add up)"""
        return kids if offset is None else [group(f"acting {name}", kids, offset=offset)]

    wrap = {
        "arm_l": lambda kids, p: pivot("arm_l", kids, angle=anim("angle", keys(arm_l)),
                                       **({"amount": anim("real", keys(amt_l))} if amt_l else {})),
        "arm_r": lambda kids, p: pivot("arm_r", kids, angle=anim("angle", keys(arm_r)),
                                       **({"amount": anim("real", keys(amt_r))} if amt_r else {})),
        "kopf": lambda kids, p: pivot("kopf", kids + mouth(), angle=anim("angle", keys(head))),
        "auge_l": lambda kids, p: eye("auge_l", kids),
        "auge_r": lambda kids, p: eye("auge_r", kids),
        "brille": lambda kids, p: turned(group("brille", kids), "glasses"),
        "nase": lambda kids, p: turned(group("nase", kids), "nose"),
        "wangen": lambda kids, p: turned(group("wangen", kids, offset=anim("vector", acting.vector_keys(
            expr["cheek"] * 0, expr["cheek"], 1.0, 1.0))) if expr else group("wangen", kids), "cheeks"),
        "pupille_l": lambda kids, p: group("pupille_l", acted(kids, "gaze", gaze), offset=anim("vector", keys(look))),
        "pupille_r": lambda kids, p: group("pupille_r", acted(kids, "gaze", gaze), offset=anim("vector", keys(look))),
        "brauen": lambda kids, p: brows(kids),
    }
    # hair (and other parts hanging from the head): turn with the head, then swing behind it on a spring
    if "kopf" in PIV:
        hx, hy = PIV["kopf"]
        sway_k, head_k, step_k, by_k = keys(sway), keys(head), keys(step), keys(by)
        for pid in FOLLOW:
            tx, ty = PIV.get(pid, (hx, hy + 2.6))             # top of the hair: pivot_<part> or above the neck
            swing = spring_follow(
                lambda f, ty=ty: (x0 + approx(step_k, f) * Kf + np.sin(np.radians(approx(sway_k, f))) * ty * Kf,
                                  FL + approx(by_k, f) * Kf),
                N, fps, root_angle=lambda f: approx(sway_k, f) + approx(head_k, f),
                freq=1.7, damping=0.18, gain_x=0.06, gain_y=0.03, gain_rot=0.9, rest_deg=0.0, limit_deg=14.0)
            wrap[pid] = (lambda kids, p, pid=pid, tx=tx, ty=ty, swing=swing:
                         group(pid, [group(f"{pid} swing", kids, origin=(tx, ty), offset=V(tx, ty),
                                           angle=anim("angle", swing))],
                               origin=(hx, hy), offset=V(hx, hy), angle=anim("angle", keys(head))))
    k_fig = Kf * float(cfg.get("size", 1.0))
    xa = anim("real", [(f, x0 + v * Kf) for f, v in keys(step)])
    ya = anim("real", [(f, FL + v * Kf) for f, v in keys(by)])
    amt = None
    first = next((t for t, s in cues if s != "X"), None)
    song_first = next((t for t, s in c.ASG.get(k, []) if s != "X"), None)   # the first time in the WHOLE song: the
    sang_before = song_first is not None and song_first < S                 # entrance is once per film, not per scene
    if cfg.get("entrance") == "flicker" and first is not None and not sang_before and F(first + S) > 14:
        f0 = F(first + S) - 14
        amt = anim("real", [(0, 0.0, "constant")] + [(f0 + j, v, "constant") for j, v in
                                                    enumerate([0.6, 0, 0.8, 0.2, 1, 0.4, 1, 1])])
    if c.spot and k != c.spot_lead and c.spot_span and actions:  # spotlight: appears only in its own light while singing
        amt = anim("real", appear_keys(c, k))
    if actions and show_spec(c, k):                   # section "show": only from a line / word / time on
        amt = anim("real", show_keys(c, k))
    squash = anim("vector", squash_keys(keys(sq), 0.6))
    lean = anim("angle", keys(sway))
    inner = group(k, emit(root, wrap), origin=(0, 0), scale=squash, angle=lean)
    kids = [inner]
    puffs = steam_frames(c, k) if actions else []
    if puffs:                                         # steam rises from the top of the head (figure units)
        hx, hy = PIV.get("kopf", (0.0, 5.6))
        top = hy + 2.2
        kids.append(group("Steam", [group("Puff", [circle("Puff", hexc(c_, 0.85), 0.45, (0, 0), feather=0.2)],
                                          offset=anim("vector", [(f0, (hx + dx, top), "linear"), (f0 + 20, (hx + dx + 0.45, top + 2.1), "linear")]),
                                          scale=anim("vector", [(f0 - 1, (0, 0)), (f0, (0.6, 0.6), "linear"), (f0 + 20, (1.6, 1.6), "linear")]),
                                          amount=anim("real", [(f0 - 1, 0, "constant"), (f0, 1, "linear"), (f0 + 20, 0, "linear")]))
                                    for f0, dx, c_ in puffs], origin=(0, 0), angle=lean))
    if cfg.get("aura"):                               # glow behind the figure, swells while it sings
        pulse = [(0, (1.0, 1.0))]
        for b in c.beats:
            if c.act(k, b["t"]):
                f = F(b["t"])
                pulse += [(f, (1.12, 1.12), "linear"), (f + 6, (1.0, 1.0))]
        glow = [circle("Aura", hexc(cfg["aura"], 0.5), 3.4, (0, 4.2), feather=2.4),
                circle("Aura core", hexc("#ffffff", 0.35), 1.8, (0, 4.6), feather=1.6)]
        aura = group("Aura", glow, origin=(0, 4.2), offset=V(0, 4.2), scale=anim("vector", keys(pulse)))
        if back_out is not None:                      # behind ALL figures, so it never washes over a neighbour
            back_out.append(group(f"Aura {k}", [aura], offset=comp_vec(xa, ya), scale=V(k_fig, k_fig), amount=amt))
        else:
            kids = [aura] + kids
    if (typ or gtr) and front_out is not None:        # own arms + props in front of the body (and of a desk)
        front_out.append(group(f"Front {k}", _front_actions(c, k, src, PIV, x, x0, FL, k_fig, typ, gtr, typ_on, gtr_on,
                                                           squash, lean),
                               offset=comp_vec(xa, ya), scale=V(k_fig, k_fig), amount=amt))
    return group(f"Figure {k}", kids, offset=comp_vec(xa, ya), scale=V(k_fig, k_fig), amount=amt)


def _front_actions(c, k, src, PIV, x, x0, FL, k_fig, typ, gtr, typ_on, gtr_on, squash, lean):
    """Own arms + keyboard / air guitar of the action spans, in figure units; logs key clicks and strums."""
    P, S, N, F, fps, keys, beats = c.P, c.S, c.N, c.F, c.fps, c.keys, c.beats
    geo = fx.arm_geometry(src, PIV)
    front = []
    if typ:
        desk = c.SET.get("desk") if x is None else None
        if desk:                                  # keyboard stands on the desk: hands come down to it
            top_fig = (desk["top"] - FL) / k_fig
            geo["hand_dy"] = max(-0.5, min(0.3, top_fig - fx.keyboard_box(geo)[3]))
        strikes = [s for t0, t1, _, sp_ in typ for s in strike_frames(c, k, t0, t1, sp_)]
        rng = np.random.default_rng(creative.rng(P, f"keys:{k}:{c.section}").randrange(1 << 30))
        kb_col = creative.pick(P, f"keyboard:{k}", (("#3a3f4a", "#5a6170"), ("#e8e4da", "#ffffff"), ("#2b2b33", "#44465a")))
        g2 = geo
        front.append(fx.keyboard(g2, strikes, N, rng, stand=not desk, body=kb_col[0], key=kb_col[1],
                                 amount=None if desk else anim("real", keys(typ_on))))
        front.append(group("Typing arms", fx.typing_arms(g2, strikes, N), origin=(0, 0), scale=squash, angle=lean,
                           amount=anim("real", keys(typ_on))))
        for j, (f, side) in enumerate(strikes):
            c.action_log.append({"t": round(S + f / fps, 3), "figure": k, "gesture": "typing",
                                 "sfx": KEY_SOUNDS[j % 3], "level": round(-21 + rng.uniform(-2, 2), 1),
                                 "pan": round(float(np.clip(x0 / 8 + (0.08 if side > 0 else -0.08), -0.7, 0.7)), 2)})
    if gtr:
        rate = creative.pick(P, f"strum:{k}", ("beat", "half"))
        frames_ = []
        for t0, t1, _, _ in gtr:
            for i, b in enumerate(beats):
                if t0 <= b["t"] < t1:
                    frames_.append(F(b["t"]))
                    if rate == "half" and i + 1 < len(beats):
                        frames_.append(F((b["t"] + beats[i + 1]["t"]) / 2))
        colour = c.figs_cfg[k].get("guitar") or creative.pick(P, f"guitar:{k}", GUITAR_COLOURS)
        front.append(group("Air guitar", fx.air_guitar(geo, frames_, N, body_col=colour), origin=(0, 0),
                           scale=squash, angle=lean, amount=anim("real", keys(gtr_on))))
        c.action_log.extend({"t": round(S + f / fps, 3), "figure": k, "gesture": "guitar"} for f in frames_)
    return front


def show_spec(c, k):
    sp = (c.A.get("show") or {}).get(k)
    return {"line": sp} if isinstance(sp, str) else sp


def show_keys(c, k):
    """section "show": {"lia": {"line": "Nur noch meeeehr" | "line_index": 77 | "word": "ultra" | "from": s,
    "while": "singing" | "always"}} - hidden before; then flickers in (hologram) and stays, or (singing) is visible
    only while it sings (+-0.5 s), like a figure in the spotlight."""
    S, E, N, F, fps, lines, act = c.S, c.E, c.N, c.F, c.fps, c.lines, c.act
    sp = show_spec(c, k)
    t0 = None
    if sp.get("from") is not None:
        t0 = float(sp["from"])
    elif sp.get("line_index") is not None:
        t0 = next((l["t"] for l in lines if l.get("line") == int(sp["line_index"])), None)
    elif sp.get("line"):
        t0 = next((l["t"] for l in lines if S - 0.5 <= l["t"] < E and l["text"].lower().startswith(sp["line"].lower())), None)
    elif sp.get("word"):
        t0 = c.word_time(sp["word"])
    if t0 is None:
        print(f"   show {k}: start not found - stays hidden")
        return [(0, 0.0, "constant")]
    t0 -= float(sp.get("lead", 0.3))
    ks, on = [(0, 0.0, "constant")], False
    for f in range(max(F(t0), 0), N + 1, 6 if sp.get("while") == "singing" else N + 1):
        t = S + f / fps
        sing = sp.get("while") != "singing" or any(act(k, t + d / fps) for d in range(-12, 13, 6))
        if sing != on:
            ks += ([(f + j, v, "constant") for j, v in enumerate([0.6, 0, 0.8, 0.3, 1])] if sing else [(f, 0.0, "constant")])
            on = sing
    return ks


def appear_keys(c, k):
    """Spotlight: visible while singing (sampled every 6 frames, +-0.5 s), hologram flicker when it appears."""
    S, N, fps, act = c.S, c.N, c.fps, c.act
    ks, on = [(0, 0.0, "constant")], False
    t0, t1 = c.spot_span
    for f in range(0, N + 1, 6):
        t = S + f / fps
        sing = (not (t0 <= t < t1)) or any(act(k, t + d / fps) for d in range(-12, 13, 6))
        if sing != on:
            ks += ([(f + j, v, "constant") for j, v in enumerate([0.6, 0, 0.8, 0.3, 1])] if sing else [(f, 0.0, "constant")])
            on = sing
    return ks


def steam_frames(c, k):
    """project.json "steam": [{"word": "hirn", "figure": "tim", "until": "(hirn", "from": "line" | "word",
    "every": 9, "color": "#ffffff", "sections": [...]}] - white puffs rise from the head of the figure, one every
    `every` frames, from the start of the line with the word (or the word itself) until the `until` word / line end.
    Returns [(start frame, x offset, colour)]; figure() draws them inside the figure so they follow its head."""
    P, S, E, F, lines = c.P, c.S, c.E, c.F, c.lines
    out = []
    for i, sp in enumerate(P.get("steam", [])):
        if not allowed(sp, c.section) or sp.get("figure", k) != k:
            continue
        last = -99
        for w in c.words:
            if not (word_matches(w["word"], sp["word"]) and S <= w["t"] < E and w["t"] - last > 3.0):
                continue
            last = w["t"]
            ln = lines[w["line"]] if sp.get("from", "line") == "line" and w.get("line") is not None and \
                w["line"] < len(lines) else None
            t0 = ln["t"] if ln else w["t"]
            t1 = c.word_time(sp["until"], after=w["t"] + 0.05, before=w["t"] + 8) if sp.get("until") else None
            t1 = t1 or (c.line_span(ln)[1] if ln else w["t"] + 2.0)
            rng = creative.rng(P, f"steam:{k}:{i}:{round(w['t'], 2)}")
            for n, f0 in enumerate(range(F(t0) + 6, F(t1) + 6, int(sp.get("every", 9)))):
                out.append((f0, (-1.0 + 1.0 * (n % 3)) + rng.uniform(-0.12, 0.12), sp.get("color", "#ffffff")))
    return out
