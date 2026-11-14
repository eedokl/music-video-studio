"""A regular scene section of scene.py: set layers, silhouettes, screen glow / dim, the Computer's screen, figures,
props, lights, desk and the camera (push-in, disco kicks, heartbeat pulse) - composed into one camera group
(c = scene_context.SceneContext).
"""
import numpy as np

from sif import V, anim, group, circle, region, hexc
from sets import set_layers
from scene_context import FULL, box
from scene_figures import figure
from scene_lights import night_region, darken_onto, light_layers
from scene_props import props, silhouettes
from scene_screen import screen_face, tint_layers, meter_layers, screen_texts_layers, badge_layers, window_layers


def back_layers(c):
    """Everything behind the screen and the figures -> (back layers, set front layers)."""
    A, SET, SCREEN, F, keys = c.A, c.SET, c.SCREEN, c.F, c.keys
    back = []
    if SET.get("color"):
        back.append(box("Background", -9, 6, 9, -5, hexc(SET["color"])))
    if SET.get("dir"):
        if c.shot == "screen":                        # close-up: the set behind, a bit bigger
            l, t_, r, b = SET.get("image_box", (-8, 4.5, 8, -4.5))
            cy0 = (t_ + b) / 2
            set_back, set_front = set_layers(str(SET["dir"]), box=(l * 1.2, cy0 + (t_ - cy0) * 1.2, r * 1.2, cy0 + (b - cy0) * 1.2))
            set_front = []
        else:
            set_back, set_front = set_layers(str(SET["dir"]))
    else:
        set_back, set_front = [], []
    sil = silhouettes(c, len(set_back))
    for idx in sorted([i for i in sil if isinstance(i, int)], reverse=True):
        set_back[min(idx, len(set_back)):min(idx, len(set_back))] = sil[idx]
    back += set_back
    dim = float(A.get("dim", 0.55 if c.shot == "screen" else 0.0))
    if dim:
        back.append(region("Dim", hexc("#05070d", dim), FULL))
    if SET.get("glow"):
        glow = [(0, 0.5)]
        for b in c.beats:
            f = F(b["t"])
            glow += [(f, 0.75 if c.in_dance(b["t"]) else 0.5, "linear"), (f + 6, 0.45)]
        x0, y0, x1, y1 = SCREEN
        back.append(circle("Screen glow", hexc(SET["glow"], 0.45), 0.9 * (x1 - x0), ((x0 + x1) / 2, (y0 + y1) / 2),
                           feather=0.7 * (x1 - x0), amount=anim("real", keys(glow))))
    if c.spot and c.spot_span:                        # dark stage (shadow silhouettes stand in the dark)
        back.append(region("Spotlight dark", hexc("#05040a", float(c.spot.get("dark", 0.72))), FULL,
                           amount=anim("real", c.span_keys(c.spot_span))))
    back += sil.get("shadow", [])
    if c.night_k:
        back.append(night_region(c, float(c.night.get("level", 0.7)), "Night (room)"))
        x0, y0, x1, y1 = SCREEN
        back.append(circle("Screen light", hexc(SET.get("glow", "#5fb3ff"), 0.3), 1.1 * (x1 - x0), ((x0 + x1) / 2, (y0 + y1) / 2),
                           feather=0.8 * (x1 - x0), amount=anim("real", keys(c.night_k))))
    return back, set_front


def monitor_layers(c):
    """The Computer's face in the set's screen with tint, meter, text screens, badges and windows."""
    names, figs_cfg = c.names, c.figs_cfg
    monitor = [l for k in names if figs_cfg[k].get("kind") == "screen" for l in screen_face(c, k)]
    monitor = monitor[:2] + (tint_layers(c) if monitor else []) + meter_layers(c) + monitor[2:] + screen_texts_layers(c) + \
        badge_layers(c) + (window_layers(c) if monitor else [])   # tint and bar behind the face, windows on top
    if c.spot and c.spot_span and monitor:            # the screen is dimmed in the spotlight unless the Computer speaks
        scr = [k for k in names if figs_cfg[k].get("kind") == "screen"]
        mk = [(0, 0.4)] + [(f, 1.0 if any(c.act(k, c.S + f / c.fps) for k in scr) else 0.4) for f in range(0, c.N + 1, 4)]
        monitor = [group("Screen (dimmed)", monitor, amount=anim("real", c.keys(mk)))]
    return monitor


def camera_keys(c):
    """Scale keys of the camera: push-in, disco kicks on the downbeats, heartbeat pulse."""
    A, N, F = c.A, c.N, c.F
    push = float(A.get("push_in", 0.08 if c.shot == "screen" else 0.0))
    cam = [(0, (1.0, 1.0)), (N, (1.0 + push,) * 2, "linear")]
    disco_span = c.disco_span
    if c.disco and disco_span:                        # disco: stronger camera pulse on the downbeats
        for b in c.beats:
            if b["downbeat"] and disco_span[0] <= b["t"] < disco_span[1]:
                f = F(b["t"])
                base = 1.0 + push * max(f, 0) / max(N, 1)
                cam += [(f - 1, (base, base)), (f, (base * 1.07,) * 2, "linear"), (f + 6, (base, base))]
        cam = sorted({k_[0]: k_ for k_ in cam}.values())
    pulse = A.get("pulse")
    pspan = c.span_of(pulse) if pulse else None
    if pspan:                                         # heartbeat: a small camera kick every "every" s + slow push-in
        every, amp, pin = float(pulse.get("every", 0.85)), float(pulse.get("amount", 0.02)), float(pulse.get("push", 0.12))
        qa, qb = pspan
        cam = [k_ for k_ in cam if not (F(qa) - 1 <= k_[0] <= F(qb) + 6)]
        for t in np.arange(qa, qb, every):
            f = F(t)
            base = (1.0 + push * max(f, 0) / max(N, 1)) * (1.0 + pin * (t - qa) / max(qb - qa, 1e-6))
            cam += [(f, (base, base), "halt"), (f + 3, (base * (1 + amp),) * 2, "linear"), (f + 7, (base, base))]
        fe = min(F(qb) + 6, N)
        cam += [(fe, ((1.0 + push * fe / max(N, 1)),) * 2)]
        cam = sorted({k_[0]: k_ for k_ in cam if 0 <= k_[0] <= N}.values())
    return cam


def stage_scene(c):
    """The camera group of a regular scene section."""
    SET = c.SET
    back, set_front = back_layers(c)
    monitor = monitor_layers(c)
    fronts = []
    auras = []
    figures = [figure(c, k, i, front_out=fronts, back_out=auras) for i, k in enumerate(c.svg_figs)]
    props_back, props_front = props(c)
    figures = auras + props_back + figures + props_front
    lights_back, lights_front = light_layers(c)
    front = []
    if SET.get("desk") and c.shot != "screen":
        dk = SET["desk"]
        front += [box("Desk", -9, dk["top"], 9, -5, hexc(dk.get("color", "#6b4a33"))),
                  box("Desk edge", -9, dk["top"] + 0.12, 9, dk["top"] - 0.05, hexc("#8a6446"))]
    if SET.get("desk"):
        layers = back + lights_back + darken_onto(c, figures + front + fronts + set_front, 0.35, "Figures (night)") + \
            lights_front + monitor
    elif c.night_k:
        layers = back + monitor + lights_back + darken_onto(c, figures + fronts, 0.35, "Figures (night)") + lights_front + \
            darken_onto(c, set_front, 0.7, "Set front (night)")
    else:
        layers = back + monitor + lights_back + figures + fronts + lights_front + set_front
    cam = camera_keys(c)
    return group("Camera", layers, origin=(0, 0), offset=V(0, 0), scale=anim("vector", c.keys(cam) if len(cam) > 2 else cam))
