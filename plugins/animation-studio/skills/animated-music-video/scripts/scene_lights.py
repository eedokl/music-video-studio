"""Section "light" of scene.py: spotlight cones, disco cones + confetti, night darkening (c = scene_context.SceneContext;
the light specs, spans and night keys are computed in its build).
"""
import numpy as np

import creative  # noqa: E402
from sif import anim, group, region, hexc, with_blend, ONTO
from scene_context import FULL, TL
from scene_figures import appear_keys
import scene_fx as fx

SPOT_COLOURS = ("#fff1c9", "#ffe0b0", "#e6f0ff")


def night_region(c, alpha, desc):
    return region(desc, hexc(c.night.get("color", "#03040a"), alpha), FULL, amount=anim("real", c.keys(c.night_k)))


def darken_onto(c, layers, alpha, desc):
    """Darken only what these layers draw (ONTO), not what lies under them."""
    if not c.night_k:
        return layers
    return [group(desc, layers + [with_blend(night_region(c, alpha, desc + " dark"), ONTO)])]


def light_layers(c):
    """(cones behind the figures, confetti in front of them) of the spotlight and the disco light."""
    P, F, N = c.P, c.F, c.N
    lights_back, lights_front = [], []
    spot, spot_span = c.spot, c.spot_span
    if spot and spot_span:
        col = spot.get("color") or creative.pick(P, f"spot_colour:{c.section}", SPOT_COLOURS)
        for k in c.svg_figs:
            c_ = col if k == c.spot_lead else (c.figs_cfg[k].get("aura") or "#c9a6ff")
            am = anim("real", c.span_keys(spot_span)) if k == c.spot_lead else anim("real", appear_keys(c, k))
            lights_back += fx.spot_cone(f"Spotlight {k}", c.places[k], TL[1] + 0.1, c.FLOOR - 0.05, c_, amount=am)
    disco, disco_span = c.disco, c.disco_span
    if disco and disco_span:
        bf = [(F(b["t"]), disco_span[0] <= b["t"] < disco_span[1]) for b in c.beats]
        lights_back += fx.disco_cones(bf, c.light_pal, N)
        rng = np.random.default_rng(creative.rng(P, f"confetti:{c.section}").randrange(1 << 30))
        count = int(disco.get("confetti", rng.integers(50, 91)))
        lights_front += fx.confetti(rng, max(F(disco_span[0]), 0), min(F(disco_span[1]), N), c.light_pal, count, N)
    return lights_back, lights_front
