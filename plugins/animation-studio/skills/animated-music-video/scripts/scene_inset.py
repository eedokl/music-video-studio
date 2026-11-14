"""Section "inset" of scene.py: a round narrator inset in a corner (bust or the Computer's face with lip sync) that
pops in when an inset figure sings and hides while that figure is on screen, when another figure sings or after a
pause longer than "hold" (c = scene_context.SceneContext).
"""
import numpy as np

import creative  # noqa: E402
from lipsync import mouth_layers
from sif import V, anim, group, circle, hexc
from svg2sif import normalize, load_svg, emit
from scene_figures import INK
from scene_screen import screen_face
import scene_fx as fx

CORNERS = {"br": (5.25, -2.05), "bl": (-5.25, -2.05), "tr": (5.25, 2.8), "tl": (-5.25, 2.8)}


def inset_layer(c, hidden_at=None):
    """[inset group] or [] - hidden_at(frame) -> figures in the picture (panels), who never show in the inset then."""
    P, A, S, E, N, F, fps, keys, act, figs_cfg = c.P, c.A, c.S, c.E, c.N, c.F, c.fps, c.keys, c.act, c.figs_cfg
    spec = A.get("inset")
    if not spec:
        return []
    spec = {} if spec is True else (({"figures": [spec]}) if isinstance(spec, str) else dict(spec))
    drawn = set(c.names) if c.kind not in ("panels", "external") else set()
    figs = [k for k in (spec.get("figures") or [k for k in figs_cfg if k not in drawn]) if k in figs_cfg]
    narr = P.get("narrator")
    figs.sort(key=lambda k: 0 if k == narr else 1)
    if not figs:
        return []
    R_ = float(spec.get("radius", 1.25))
    corner = spec.get("corner") or creative.pick(P, f"inset_corner:{c.section}", ("br", "bl"))
    center = CORNERS.get(corner, CORNERS["br"])
    hold = float(spec.get("hold", 2.0))              # bridge breathing pauses of the inset singer up to `hold` s
    others = [k for k in figs_cfg if k not in figs]
    who, cur, run, last_on = [], None, 0, -1e9
    for f in range(N + 1):
        t = S + f / fps
        hid = hidden_at(f) if hidden_at else set()
        cands = [k for k in figs if act(k, t) and k not in hid]
        if cands:
            last_on = t
        # nobody of the inset sings: keep the last one through a short pause, hide it when somebody else takes
        # over (a figure on screen sings) or the pause gets longer
        other_sings = any(act(k, t) for k in others) or any(act(k, t) for k in hid)
        want = cands[0] if cands else (None if cur in hid or other_sings or t - last_on > hold else cur)
        if want != cur:
            run += 1
            if run >= 6 or cur is None or want is None:
                cur, run = want, 0
        else:
            run = 0
        who.append(cur)
    first = next((f for f, w in enumerate(who) if w), None)
    if first is None:
        return []
    switch = [f for f in range(1, N + 1) if who[f] != who[f - 1] and who[f]]
    hide = [f for f in range(1, N + 1) if who[f] is None and who[f - 1]]
    pop = [(0, (0, 0)), (max(first - 1, 0), (0, 0), "linear"), (first + 4, (1.15, 1.15)), (first + 8, (1, 1))]
    for f in switch:
        if f == first:
            continue
        if who[f - 1] is None:
            pop += [(f - 1, (0, 0), "linear"), (f + 4, (1.15, 1.15)), (f + 8, (1, 1))]
        else:
            pop += [(f - 1, (1, 1), "linear"), (f + 2, (0.85, 0.85)), (f + 6, (1.06, 1.06)), (f + 9, (1, 1))]
    for f in hide:
        pop += [(f - 1, (1, 1), "linear"), (f + 5, (0, 0), "linear")]
    bob = [(0, 0.0)] + [(F(b["t"]), 4.0 if i % 2 else -4.0) for i, b in enumerate(c.beats)]
    cues_in_window = c.cues_in_window
    contents = []
    for k in figs:
        amt = [(0, 0.0, "constant")] + [(f, 1.0 if who[f] == k else 0.0, "constant") for f in [first] + switch + hide]
        cfg = figs_cfg[k]
        if cfg.get("kind") == "screen":
            body = [circle("Screen", hexc("#1d3b5c"), R_, (0, 0))] + screen_face(c, k, rect=(-1.25 * R_, 1.0 * R_, 1.25 * R_, -1.0 * R_))
        else:
            src = P.path(cfg["svg"])
            root, PIV = load_svg(normalize(src, out_dir=P.cache), scale=1 / 125, origin=(200, 590))
            geo = fx.arm_geometry(src, {kk: (v[0] * 125 / 72, v[1] * 125 / 72) for kk, v in PIV.items()})
            ey = PIV.get("auge_l", (0, 3.1))[1]
            my = PIV.get("mund", (0, 2.7))[1]
            yc = ey * 0.6 + my * 0.4 + 0.06
            blink = [(0, (1, 1))]
            for t in np.arange(S + 1.1, E, 4.1):
                f = F(t)
                blink += [(f - 1, (1, 1)), (f + 1, (1.05, 0.1), "linear"), (f + 3, (1, 1))]

            def piv(pid, kids, PIV=PIV, **kw):
                if pid not in PIV:
                    return group(pid, kids)
                px, py = PIV[pid]
                return group(pid, kids, origin=(px, py), offset=V(px, py), **kw)
            msz = float(cfg.get("mouth", 0.58)) * 72 / 125
            wrap = {"kopf": lambda kids, p, k=k, piv=piv, PIV=PIV, msz=msz: piv(
                        "kopf", kids + mouth_layers(cues_in_window(k), fps, center=PIV.get("mund", (0, 2.7)), size=msz,
                                                    ink=INK, offset_frames=-1), angle=anim("angle", keys(bob))),
                    "auge_l": lambda kids, p, piv=piv, blink=blink: piv("auge_l", kids, scale=anim("vector", blink)),
                    "auge_r": lambda kids, p, piv=piv, blink=blink: piv("auge_r", kids, scale=anim("vector", blink))}
            glow = cfg.get("aura") or geo["sleeve"]
            h = glow.lstrip("#")
            dark = "#%02x%02x%02x" % tuple(int(int(h[j:j + 2], 16) * 0.22) for j in (0, 2, 4))
            body = [circle("Background", hexc(dark), R_, (0, 0)), circle("Glow", hexc(glow, 0.6), R_ * 0.9, (0, 0.2), feather=0.6),
                    group("Bust", emit(root, wrap), origin=(0, 0), offset=V(0, -yc))]
        contents.append(group(f"Inset {k}", body, amount=anim("real", keys(amt))))
    return [fx.inset(contents, center, R_, keys(pop), frame=spec.get("frame", "#ffd23f"), glow=spec.get("glow", "#c9a6ff"))]
