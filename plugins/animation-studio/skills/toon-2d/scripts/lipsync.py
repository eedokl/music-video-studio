"""Lip sync: Rhubarb mouth shapes -> Synfig layers with switching keys.

Rhubarb Lip Sync (program path from config.py, key "rhubarb") turns a voice recording into timed mouth shapes:
  rhubarb -r phonetic -f json --extendedShapes GHX -o mouth.json voice.wav
  (-r phonetic = language independent, needed for non-English; the default recognizer is English only)

Mouth shapes (Preston Blair scheme):
  X rest/smile   A closed (M, B, P)   B slightly open, teeth (K, S, T, EE)
  C open (EH, AE)  D wide open (AA)    E rounded (AO, ER)
  F puckered (UW, OW, W)   G F/V (teeth on the lower lip)   H L (tongue up)

Usage:
    from lipsync import load_cues, mouth_layers
    cues = load_cues("mouth.json")
    layers = mouth_layers(cues, fps=24, center=(0, 1.62), size=0.62, ink=INK)
    # -> list of group layers (one per shape), each with "amount" keys (switched with constant interpolation).
    # Put them into the character's head/squash group instead of a fixed mouth.
"""
import json

import _studio  # noqa: E402
_studio.use('toon-2d')
from sif import (V, R, anim, group, circle, region, outline, ellipse_pts, hexc, with_blend, ONTO)

SHAPES = "XABCDEFGH"


def load_cues(path):
    """[(start_seconds, shape), ...] from Rhubarb JSON."""
    data = json.load(open(path, encoding="utf-8"))
    return [(c["start"], c["value"]) for c in data["mouthCues"]]


def shape_keys(cues, fps=24, offset_frames=0):
    """0/1 keys (constant) per shape. Changes are rounded to whole frames; offset_frames
    shifts everything (e.g. -1: mouth one frame ahead of the sound - often looks more in sync)."""
    frames = []
    for t, s in cues:
        f = max(0, round(t * fps) + offset_frames)
        if frames and frames[-1][0] == f:
            frames[-1] = (f, s)        # same frame: the later shape wins
        else:
            frames.append((f, s))
    keys = {s: [(0, 0.0, "constant")] for s in SHAPES}
    for f, s in frames:
        for k in SHAPES:
            keys[k].append((f, 1.0 if k == s else 0.0, "constant"))
    return keys


def _mouth_hole(desc, cx, cy, w, h, ink, inside="#6b2424", tongue=None, teeth_top=False,
                teeth_bottom=False, line=0.06):
    """Open mouth: dark shape, tongue/teeth inside via ONTO, outline on top."""
    pts = ellipse_pts(w / 2, h / 2, (cx, cy), 8)
    parts = [region(desc, hexc(inside), pts)]
    if tongue:
        tx, ty, tr = tongue
        parts.append(with_blend(circle("Tongue", hexc("#e8787a"), tr, (tx, ty)), ONTO))
    if teeth_top:
        parts.append(with_blend(region("Teeth top", hexc("#ffffff"),
                                       [(cx - w, cy + h * 0.5, 0, 0), (cx + w, cy + h * 0.5, 0, 0),
                                        (cx + w, cy + h * 0.22, 0, 0), (cx - w, cy + h * 0.22, 0, 0)]), ONTO))
    if teeth_bottom:
        parts.append(with_blend(region("Teeth bottom", hexc("#ffffff"),
                                       [(cx - w, cy - h * 0.5, 0, 0), (cx + w, cy - h * 0.5, 0, 0),
                                        (cx + w, cy - h * 0.28, 0, 0), (cx - w, cy - h * 0.28, 0, 0)]), ONTO))
    return [group(desc, parts), outline(desc + " outline", ink, pts, line)]


def mouth_drawings(center=(0, 0), size=0.6, ink=None):
    """The 9 mouth drawings as {shape: [layers]} - coordinates around center, width ~size."""
    ink = ink or hexc("#3b2418")
    cx, cy = center
    s = size
    lw = 0.12 * s
    d = {}
    # X: relaxed smile
    d["X"] = [outline("Mouth X", ink, [(cx - 0.45 * s, cy + 0.1 * s, 0.5 * s, -0.55 * s),
                                       (cx, cy - 0.15 * s, 0.9 * s, 0),
                                       (cx + 0.45 * s, cy + 0.1 * s, 0.5 * s, 0.55 * s)], lw, loop=False)]
    # A: closed, lips pressed
    d["A"] = [outline("Mouth A", ink, [(cx - 0.36 * s, cy, 0.4 * s, -0.08 * s), (cx, cy - 0.04 * s, 0.7 * s, 0),
                                       (cx + 0.36 * s, cy, 0.4 * s, 0.08 * s)], lw * 1.15, loop=False)]
    # B: slightly open, teeth
    d["B"] = _mouth_hole("Mouth B", cx, cy - 0.02 * s, 0.75 * s, 0.22 * s, ink, teeth_top=True,
                         teeth_bottom=True, line=lw)
    # C: open
    d["C"] = _mouth_hole("Mouth C", cx, cy - 0.06 * s, 0.68 * s, 0.4 * s, ink,
                         tongue=(cx, cy - 0.3 * s, 0.22 * s), teeth_top=True, line=lw)
    # D: wide open
    d["D"] = _mouth_hole("Mouth D", cx, cy - 0.12 * s, 0.78 * s, 0.62 * s, ink,
                         tongue=(cx, cy - 0.45 * s, 0.28 * s), teeth_top=True, line=lw)
    # E: rounded
    d["E"] = _mouth_hole("Mouth E", cx, cy - 0.08 * s, 0.48 * s, 0.42 * s, ink,
                         tongue=(cx, cy - 0.3 * s, 0.16 * s), line=lw)
    # F: puckered (small O)
    d["F"] = _mouth_hole("Mouth F", cx, cy - 0.04 * s, 0.26 * s, 0.3 * s, ink, line=lw)
    # G: F/V - upper teeth on the lower lip
    d["G"] = _mouth_hole("Mouth G", cx, cy - 0.02 * s, 0.62 * s, 0.2 * s, ink, teeth_top=True, line=lw) + [
        outline("Lower lip", ink, [(cx - 0.3 * s, cy - 0.12 * s, 0.3 * s, -0.08 * s),
                                   (cx + 0.3 * s, cy - 0.12 * s, 0.3 * s, 0.08 * s)], lw * 0.8, loop=False)]
    # H: L - open, tongue up
    d["H"] = _mouth_hole("Mouth H", cx, cy - 0.08 * s, 0.6 * s, 0.42 * s, ink,
                         tongue=(cx, cy + 0.02 * s, 0.17 * s), line=lw)
    return d


def mouth_layers(cues, fps=24, center=(0, 0), size=0.6, ink=None, offset_frames=0):
    """Finished layers: one group per shape, switched on/off with constant 'amount' keys."""
    keys = shape_keys(cues, fps, offset_frames)
    drawings = mouth_drawings(center, size, ink)
    return [group(f"Mouth {s}", drawings[s], amount=anim("real", keys[s])) for s in SHAPES]
