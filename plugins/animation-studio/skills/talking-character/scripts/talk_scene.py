# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0", "svgelements==1.9.6"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Step 2: the dialogue as an editable Synfig scene - figures speak, listen, look at each other and act on words.

  uv run talk_scene.py [--project .] [--render] [--jobs 8]
Reads project.json, analysis/dialogue.json + assignment.json (speak.py). Output: scenes/dialogue.sif,
with --render scenes/dialogue/f.0000.png ..., analysis/actions_dialogue.json (gesture times -> film-finish sounds.py).

Dialogue direction instead of beats - per figure and moment:
  speaking    mouth from Rhubarb; looks at the addressee ("(to tim)", else the last speaker / the other figure /
              the camera when alone); head accents + brow on the stressed words; figures with arms gesture openly
  listening   turns to the speaker after a short reaction delay, blinks on the turn, sometimes nods when a line ends
  directions  "(looks up)" etc. hold for their chunk; gestures on words (cheer, point, scare, surprise, scratch, nod, sad,
              shrug, wave, jump, lean) - figures without arms hop / lean instead
  idle        breathing, blinks at seeded random intervals
  camera      "camera": "static" | "cuts" (two-shot first, close-ups on the speaker per line) | "auto"
Figures (project.json "figures"): {"svg": "<path>|skill:characters/assets/figures/tim.svg", "voice", "place",
  "size", "mouth" (mouth size), "follow": ["antenne"] (parts that swing after the head)} or {"kind": "screen"}
  for the Computer (a face inside the set's screen rectangle; "(screen "TEXT")" shows text instead).
Variation (listening style, accent strength, gesture style, blink rhythm, camera shots) comes from the creative seed.

The Computer's face and screen texts come from characters/computer.py (shared with animated-music-video).
Generic pieces that could move to toon-2d later: svg_rig() (SVG figure + pose tracks -> layers), tracks/keys helpers.
"""
import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use("song-analysis", "toon-2d", "characters")
import creative  # noqa: E402
from lipsync import mouth_layers  # noqa: E402
from motion import approx, spring_follow, squash_keys  # noqa: E402
from sif import V, R, anim, comp_vec, group, circle, region, hexc, canvas, image  # noqa: E402
from song_project import Project  # noqa: E402
from svg2sif import normalize, load_svg, emit  # noqa: E402
from computer import computer, screen_texts  # noqa: E402

INK = hexc("#2b1d14")
TL, BR = (-6.9, 4.25), (6.9, -3.51)
VIEW = "-6.9 4.25 6.9 -3.51"
REST = {"arm_l": 5.0, "arm_r": -5.0, "head": 0.0, "look": (0.0, 0.0), "brow": 0.0, "sq": 1.0, "by": 0.0}
LOOKS = {"camera": (0.0, 0.0), "up": (0.0, 0.12), "down": (0.0, -0.07), "away": None, "left": (-0.09, 0.0),
         "right": (0.09, 0.0)}


class Tracks:
    """Keyframe tracks of one figure: put(track, frame, value[, interp]); later keys on the same frame win."""

    def __init__(self, n):
        self.n = n
        self.k = defaultdict(dict)

    def put(self, tr, f, v, interp=None):
        f = int(round(f))
        if 0 <= f <= self.n:
            self.k[tr][f] = (f, v) if interp is None else (f, v, interp)

    def hold(self, tr, f0, f1, v):
        self.put(tr, f0, v)
        self.put(tr, f1, v)

    def keys(self, tr, rest=None):
        out = [self.k[tr][f] for f in sorted(self.k[tr])]
        return out or [(0, REST.get(tr, rest) if rest is None else rest)]

    def busy(self, tr, f, r):
        return any(abs(g - f) <= r for g in self.k[tr])


def box(desc, x0, y0, x1, y1, fill, amount=None):
    return region(desc, fill, [(x0, y0, 0, 0), (x1, y0, 0, 0), (x1, y1, 0, 0), (x0, y1, 0, 0)], amount=amount)


def load_set(P, name):
    if str(name).startswith("color:"):
        return {"back": [], "front": [], "color": name[6:], "scale": 0.8, "floor": -3.2, "places": {},
                "screen": [2.6, 2.6, 6.2, -0.2]}, None
    for d in (P.dir / "sets" / name, _studio.skill_dir("toon-2d") / "assets" / "sets" / name):
        if (d / "set.json").exists():
            return json.loads((d / "set.json").read_text(encoding="utf-8")), d
    raise SystemExit(f"set '{name}' not found (project sets/<name>/set.json or toon-2d assets/sets/<name>/)")


def cues_list(cues):
    return [(float(t), s) for t, s in cues] or [(0.0, "X")]


def svg_rig(name, cfg, P, tr, cues, fps, x0, floor, K, end):
    """SVG figure (plugin rig convention) driven by Tracks -> one group layer. Returns (layer, pivots)."""
    plain = normalize(P.path(cfg["svg"]), out_dir=P.cache)
    root, PIV = load_svg(plain, scale=1 / 72, origin=(200, 590))
    msize = float(cfg.get("mouth", 0.58))
    k_fig = K * float(cfg.get("size", 1.0))

    def pivot(pid, kids, **kw):
        if pid not in PIV:
            return group(pid, kids, **kw)
        px, py = PIV[pid]
        return group(pid, kids, origin=(px, py), offset=V(px, py), **kw)

    head_keys = tr.keys("head")
    by_keys = tr.keys("by")
    hx, hy = PIV.get("kopf", (0, 4))

    def follow_keys(pid):
        """Follow-through (antenna, leaf, ears): damped spring driven by the head movement and hops."""
        px, py = PIV.get(pid, (hx, hy + 2))

        def pos(t):
            a = np.radians(approx(head_keys, t))
            dx, dy = px - hx, py - hy
            return (x0 + k_fig * (hx + dx * np.cos(a) - dy * np.sin(a)),
                    floor + K * approx(by_keys, t) + k_fig * (hy + dx * np.sin(a) + dy * np.cos(a)))
        ks = spring_follow(pos, end, fps, root_angle=lambda t: approx(head_keys, t), gain_x=0.06, gain_y=0.05,
                           gain_rot=0.8, rest_deg=0.0)
        return [ks[i] for i in range(0, len(ks), 2)] + [ks[-1]]

    wrap = {
        "arm_l": lambda kids, p: pivot("arm_l", kids, angle=anim("angle", tr.keys("arm_l"))),
        "arm_r": lambda kids, p: pivot("arm_r", kids, angle=anim("angle", tr.keys("arm_r"))),
        "kopf": lambda kids, p: pivot("kopf", kids + mouth_layers(cues_list(cues), fps, center=PIV.get("mund", (0, 6)),
                                                                  size=msize, ink=INK, offset_frames=-1),
                                      angle=anim("angle", head_keys)),
        "auge_l": lambda kids, p: pivot("auge_l", kids, scale=anim("vector", tr.keys("blink", (1, 1)))),
        "auge_r": lambda kids, p: pivot("auge_r", kids, scale=anim("vector", tr.keys("blink", (1, 1)))),
        "pupille_l": lambda kids, p: group("pupille_l", kids, offset=anim("vector", tr.keys("look"))),
        "pupille_r": lambda kids, p: group("pupille_r", kids, offset=anim("vector", tr.keys("look"))),
        "brauen": lambda kids, p: group("brauen", kids, offset=comp_vec(R(0), anim("real", tr.keys("brow")))),
    }
    for pid in cfg.get("follow", []):
        wrap[pid] = (lambda pid_: lambda kids, p: pivot(pid_, kids, angle=anim("angle", follow_keys(pid_))))(pid)
    xa = anim("real", [(f, x0 + v * K) for f, v in tr.keys("x", 0.0)])
    ya = anim("real", [(k[0], floor + k[1] * K) + tuple(k[2:]) for k in by_keys])
    inner = group(name, emit(root, wrap), origin=(0, 0), scale=anim("vector", squash_keys(tr.keys("sq"), 0.6)))
    fig = group(f"Figure {name}", [inner], offset=comp_vec(xa, ya), scale=V(k_fig, k_fig))
    sh = [(k[0], ((1 - 0.25 * k[1]) * 1.0, (1 - 0.25 * k[1]) * 0.22)) + tuple(k[2:]) for k in by_keys]
    shadow = group(f"Shadow {name}", [circle("Shadow", hexc("#2a2a1a", 0.4), 1.25 * k_fig, (0, 0), feather=0.35 * k_fig)],
                   offset=comp_vec(xa, R(floor + 0.03)), scale=anim("vector", sh))
    return [shadow, fig], PIV


def screen_face(scr, tr, cues, fps, face_on):
    """The Computer (characters/computer.py): eyes follow the look track, lip sync, bounce and tilt from the tracks."""
    x0, y0, x1, y1 = scr
    w, h = x1 - x0, y0 - y1
    look = [(k[0], (k[1][0] * 0.5 * w, k[1][1] * 0.6 * h)) + tuple(k[2:]) for k in tr.keys("look")]
    bounce = [(k[0], (2 - k[1], k[1])) + tuple(k[2:]) for k in tr.keys("sq")]
    tilt = [(k[0], k[1] * 0.5) + tuple(k[2:]) for k in tr.keys("head")]
    return computer(tuple(scr), fps=fps, mouth_cues=cues_list(cues), face_on=face_on, look_keys=look, look_units="units",
                    blink_keys=tr.keys("blink", (1, 1)), bounce_keys=bounce, tilt_keys=tilt)


def screen_text_images(P, scr, events, F):
    """(t0, t1, text, colour) -> text layers on the screen (characters/computer.py screen_texts)."""
    return screen_texts(tuple(scr), events, F, P.cache, tag="screen_dialogue")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    P = Project(a.project)
    P.check("talking-character")                 # project.json validated before any long step
    fps = P.fps
    DL = json.loads((P.analysis / "dialogue.json").read_text(encoding="utf-8"))
    ASG = P.assignment()["figures"]
    lines = DL["lines"]
    N = round(DL["duration"] * fps)
    F = lambda t: int(round(t * fps))
    figs = P["figures"]
    names = list(figs)
    SET, set_dir = load_set(P, P.get("set", "room"))
    K, FLOOR = float(P.get("scale", SET.get("scale", 0.8))), float(P.get("floor", SET.get("floor", -3.0)))
    scr = SET.get("screen", [2.6, 2.6, 6.2, -0.2])
    places = dict(SET.get("places", {}))
    svg_names = [k for k in names if figs[k].get("svg")]
    for i, k in enumerate(svg_names):
        if "place" in figs[k]:
            places[k] = float(figs[k]["place"])
        places.setdefault(k, -4.0 + 8.0 * (i + 0.5) / max(len(svg_names), 1) if len(svg_names) > 1 else 0.0)
    for k in names:
        if figs[k].get("kind") == "screen":
            places[k] = (scr[0] + scr[2]) / 2
    style = {k: {"listen": creative.pick(P, f"listen:{k}", ["nodder", "tilter", "still"]),
                 "accent": creative.rng(P, f"accent:{k}").uniform(3.5, 7.0),
                 "hands": creative.pick(P, f"hands:{k}", ["open", "one", "calm"]) if figs[k].get("hands") is None
                 else figs[k]["hands"]} for k in names}

    def toward(k, j):
        """look vector from k to figure j"""
        if j in LOOKS:
            return LOOKS[j] or (0.09 * (1 if places.get(k, 0) < 0 else -1), -0.03)
        if j not in places or j == k:
            return LOOKS["camera"]
        s = np.sign(places[j] - places[k]) or 1.0
        return (0.09 * s, 0.0 if figs.get(j, {}).get("kind") != "screen" else 0.03)

    def head_for(look):
        return 5.0 * (-np.sign(look[0]) if abs(look[0]) > 0.02 else 0) + (4.0 if look[1] > 0.06 else -3.0 if look[1] < -0.05 else 0)

    def addressee(i, l):
        ev = next((e["look"] for e in l["events"] if e.get("look") and abs(e["t"] - l["t"]) < 0.05), None)
        if ev:
            return ev
        prev = next((lines[j]["who"] for j in range(i - 1, -1, -1) if lines[j]["who"] != l["who"]), None)
        if prev:
            return prev
        others = [o for o in names if o != l["who"]]
        return others[0] if len(others) == 1 else "camera"

    tracks = {k: Tracks(N) for k in names}
    gwin = defaultdict(list)                                  # gesture windows per figure: no talk accents there
    for l in lines:
        for e in l["events"]:
            if e.get("gesture"):
                gwin[e.get("by") or l["who"]].append((F(e["t"]) - 8, F(e["t"]) + 38))
    in_gesture = lambda k, f0, f1: any(a < f1 and f0 < b for a, b in gwin[k])
    gestures_out = []
    for k in names:
        tr = tracks[k]
        rng = creative.rng(P, f"acting:{k}")
        for f in (0,):
            for t_, v in REST.items():
                tr.put(t_, f, v)
        # ---- gaze timeline: (frame, target)
        gaze = [(0, "camera" if len(names) == 1 else (names[1] if k == names[0] else names[0]))]
        for i, l in enumerate(lines):
            if l["who"] == k:
                gaze.append((F(l["t"]) - 3, addressee(i, l)))
                for e in l["events"]:
                    if e.get("look"):
                        # a look holds for the chunk it starts in (or, given in a pause, for the next chunk)
                        ch = next((c for c in l["chunks"] if c["t"] - 0.05 <= e["t"] <= c["end"]), None) or                             next((c for c in l["chunks"] if c["t"] > e["t"]), None)
                        gaze.append((F(e["t"]) - 4, e["look"]))
                        if ch and ch["end"] < l["end"] - 0.05:
                            gaze.append((F(ch["end"] + 0.3), addressee(i, l)))
            else:
                gaze.append((F(l["t"]) + rng.randint(3, 9), l["who"]))
        gaze.sort()
        last_look, blinks = None, []
        for f, target in gaze:
            lv = toward(k, target)
            if lv != last_look:
                f0 = max(f, 0)
                if last_look is not None:
                    tr.put("look", f0 - 1, last_look)
                    tr.put("head", f0 - 1, head_for(last_look))
                tr.put("look", f0 + 2, lv)
                tr.put("head", f0 + 6, head_for(lv))
                blinks.append(f0)
                last_look = lv
        # ---- speaking: accents on stressed words, open hands
        for i, l in enumerate(lines):
            if l["who"] != k or not l["words"]:
                continue
            ws = sorted(l["words"], key=lambda w: -((w["end"] - w["t"]) * (1.4 if w["word"][:1].isupper() and w is not l["words"][0]
                                                                           else 1.0) * (1.3 if "!" in w["word"] else 1.0)))
            n_acc = max(1, int((l["end"] - l["t"]) / 1.6))
            acc = sorted(ws[:n_acc], key=lambda w: w["t"])
            for j, w in enumerate(acc):
                f = F(w["t"])
                if in_gesture(k, f - 4, F(w["end"] + 0.35) + 6):
                    continue
                base = approx(tr.keys("head"), f)
                sgn = 1 if (j + i) % 2 == 0 else -1
                amp = style[k]["accent"]
                tr.put("head", f - 3, base)
                tr.put("head", f + 1, base + sgn * amp * 0.6)
                tr.put("head", f + 7, base - sgn * amp * 0.25)
                tr.put("head", f + 13, base)
                tr.put("brow", f - 2, 0.0)
                tr.put("brow", f + 1, 0.09)
                tr.put("brow", f + 12, 0.0)
                tr.put("sq", f - 3, 0.975)
                tr.put("sq", f + 1, 1.035)
                tr.put("sq", f + 7, 1.0)
                if style[k]["hands"] != "calm" and (j == 0 or style[k]["hands"] == "open"):
                    up = rng.uniform(40, 75)
                    fe = F(w["end"] + 0.35)
                    tr.put("arm_r", f - 4, REST["arm_r"])
                    tr.put("arm_r", f, up)
                    tr.put("arm_r", fe, up * 0.8)
                    tr.put("arm_r", fe + 6, REST["arm_r"])
                    if style[k]["hands"] == "open" and j % 2 == 1:
                        tr.put("arm_l", f - 4, REST["arm_l"])
                        tr.put("arm_l", f, -up)
                        tr.put("arm_l", fe, -up * 0.8)
                        tr.put("arm_l", fe + 6, REST["arm_l"])
        # ---- listening: nod when a line of somebody else ends
        for l in lines:
            if l["who"] == k:
                continue
            fe = F(l["end"])
            if style[k]["listen"] == "nodder" or (style[k]["listen"] == "tilter" and rng.random() < 0.4):
                base = approx(tr.keys("head"), fe)
                tr.put("head", fe + 1, base)
                tr.put("head", fe + 5, base - 6)
                tr.put("head", fe + 11, base)
        # ---- blinks: seeded rhythm + on gaze shifts
        t = rng.uniform(0.6, 1.6)
        while t < DL["duration"]:
            blinks.append(F(t))
            t += rng.uniform(2.4, 4.8)
        blinks.sort()
        last = -99
        tr.put("blink", 0, (1, 1))
        for b in blinks:
            if b - last < 12 or b < 2 or b > N - 3:
                continue
            tr.put("blink", b - 1, (1, 1))
            tr.put("blink", b + 1, (1.05, 0.08), "linear")
            tr.put("blink", b + 3, (1, 1))
            last = b
    # ---- gestures on words (performer = "by" or the speaker)
    for l in lines:
        for e in l["events"]:
            g = e.get("gesture")
            if not g:
                continue
            k = e.get("by") or l["who"]
            if k not in tracks:
                continue
            tr = tracks[k]
            f = F(e["t"])
            arms = bool(figs[k].get("svg")) and figs[k].get("arms", True)
            tgt = toward(k, e.get("target")) if e.get("target") else None
            gestures_out.append({"t": round(e["t"], 3), "figure": k, "gesture": g})
            base_h = approx(tr.keys("head"), f)
            if g == "surprise":                             # a take: eyes pop, body stretches, settles
                for df, v in ((-3, 1.0), (0, 0.9), (3, 1.12), (10, 1.0)):
                    tr.put("sq", f + df, v)
                tr.put("blink", f - 1, (1, 1)); tr.hold("blink", f + 2, f + 12, (1.2, 1.3)); tr.put("blink", f + 22, (1, 1))
                tr.put("brow", f, 0.15); tr.put("brow", f + 20, 0.0)
                tr.put("head", f - 2, base_h); tr.put("head", f + 3, base_h + 4); tr.put("head", f + 10, base_h)
            if g in ("cheer", "jump") and not (arms and g == "cheer" and figs[k].get("hop") is False):
                hop = 0.8 if not arms or g == "jump" else 0.3
                for df, v in ((-4, 1.0), (-1, 0.85), (0, 0.83), (2, 1.2), (7, 1.0), (12, 1.12), (14, 0.72), (17, 1.1),
                              (20, 0.95), (24, 1.0)):
                    tr.put("sq", f + df, v)
                tr.put("by", f - 1, 0.0, "linear")
                tr.put("by", f + 7, hop, "halt")
                tr.put("by", f + 14, 0.0, "linear")
                tr.put("by", f + 24, 0.0)
                tr.put("head", f + 14, base_h)
                tr.put("head", f + 17, base_h - 3)
                tr.put("head", f + 21, base_h + 2)
                tr.put("head", f + 25, base_h)
            if arms and g == "cheer":
                tr.put("arm_l", f - 3, REST["arm_l"]); tr.put("arm_r", f - 3, REST["arm_r"])
                tr.hold("arm_l", f + 1, f + 22, -120); tr.hold("arm_r", f + 1, f + 22, 120)
                tr.put("arm_l", f + 30, REST["arm_l"]); tr.put("arm_r", f + 30, REST["arm_r"])
                tr.put("brow", f, 0.1); tr.put("brow", f + 24, 0.0)
            elif g == "point":
                side = tgt[0] if tgt else 0.09
                arm, ang = ("arm_r", 95) if side >= 0 or not arms else ("arm_l", -95)
                if arms:
                    tr.put(arm, f - 4, REST[arm]); tr.hold(arm, f + 1, f + 24, ang); tr.put(arm, f + 32, REST[arm])
                else:
                    tr.put("head", f - 2, base_h); tr.hold("head", f + 3, f + 20, base_h - 7 * np.sign(side or 1))
                    tr.put("head", f + 28, base_h)
                if tgt:
                    tr.hold("look", f, f + 24, tgt)
            elif g == "scare":
                if arms:
                    tr.put("arm_l", f - 2, REST["arm_l"]); tr.put("arm_r", f - 2, REST["arm_r"])
                    tr.hold("arm_l", f + 2, f + 16, -150); tr.hold("arm_r", f + 2, f + 16, 150)
                    tr.put("arm_l", f + 26, REST["arm_l"]); tr.put("arm_r", f + 26, REST["arm_r"])
                tr.put("brow", f, 0.18); tr.put("brow", f + 20, 0.0)
                for df, v in ((-3, 0.9), (0, 1.14), (6, 1.0)):
                    tr.put("sq", f + df, v)
                tr.put("by", f - 1, 0.0); tr.put("by", f + 3, 0.25); tr.put("by", f + 9, 0.0)
            elif g == "scratch":
                if arms:
                    tr.put("arm_r", f - 3, REST["arm_r"]); tr.hold("arm_r", f + 3, f + 22, 158); tr.put("arm_r", f + 30, REST["arm_r"])
                tr.hold("head", f + 2, f + 22, base_h + 9); tr.put("head", f + 30, base_h)
                tr.hold("look", f + 1, f + 22, (0.0, 0.08)); tr.put("brow", f, -0.03)
            elif g == "nod":
                for df, v in ((0, base_h), (4, base_h - 8), (9, base_h + 3), (13, base_h - 6), (18, base_h)):
                    tr.put("head", f + df, v)
            elif g == "sad":
                tr.hold("head", f + 4, f + 28, base_h - 10); tr.put("head", f + 36, base_h)
                tr.hold("look", f + 2, f + 28, (0.0, -0.07)); tr.put("brow", f, -0.06); tr.put("brow", f + 30, 0.0)
                tr.hold("sq", f + 4, f + 28, 0.96); tr.put("sq", f + 34, 1.0)
            elif g == "shrug":
                if arms:
                    tr.put("arm_l", f - 2, REST["arm_l"]); tr.put("arm_r", f - 2, REST["arm_r"])
                    tr.hold("arm_l", f + 3, f + 16, -45); tr.hold("arm_r", f + 3, f + 16, 45)
                    tr.put("arm_l", f + 24, REST["arm_l"]); tr.put("arm_r", f + 24, REST["arm_r"])
                tr.hold("head", f + 3, f + 16, base_h + 7); tr.put("head", f + 24, base_h)
                tr.put("brow", f + 2, 0.12); tr.put("brow", f + 18, 0.0)
                tr.hold("sq", f + 3, f + 16, 1.04); tr.put("sq", f + 22, 1.0)
            elif g == "wave":
                if arms:
                    tr.put("arm_r", f - 3, REST["arm_r"])
                    for j, df in enumerate(range(1, 26, 4)):
                        tr.put("arm_r", f + df, 135 if j % 2 == 0 else 160)
                    tr.put("arm_r", f + 33, REST["arm_r"])
                else:
                    for j, df in enumerate(range(0, 20, 5)):
                        tr.put("head", f + df, base_h + (6 if j % 2 == 0 else -6))
                    tr.put("head", f + 24, base_h)
            elif g == "lean":
                s = -np.sign(tgt[0]) if tgt else 1
                tr.hold("head", f + 3, f + 24, base_h + 7 * s); tr.put("head", f + 32, base_h)
    # ---- breathing where nothing else moves the squash
    for k in names:
        tr = tracks[k]
        ph = creative.rng(P, f"breath:{k}").uniform(0, 1.6)
        t, up = ph, True
        while t < DL["duration"]:
            f = F(t)
            if not tr.busy("sq", f, 10):
                tr.put("sq", f, 1.012 if up else 1.0)
            t += 1.6
            up = not up
        tr.put("sq", N, approx(tr.keys("sq"), N))

    # ---- screen events
    screen_ev = []
    for l in lines:
        for e in l["events"]:
            if e.get("screen"):
                screen_ev.append((e["t"] - 0.05, max(l["end"] + 0.3, e["t"] + 1.5), e["screen"], e.get("color", "#7CFF9B")))
    face_on = [(0, 1.0, "constant")]
    for t0, t1, _, _ in screen_ev:
        face_on += [(F(t0), 0.0, "constant"), (F(t1), 1.0, "constant")]

    # ---- compose
    box_tl = tuple(SET.get("image_box", [TL[0], TL[1], BR[0], BR[1]])[:2])
    box_br = tuple(SET.get("image_box", [TL[0], TL[1], BR[0], BR[1]])[2:])
    back = []
    if SET.get("color"):
        back.append(box("Background", -9, 6, 9, -5, hexc(SET["color"])))
    for i, img in enumerate(SET.get("back", [])):
        back.append(image(f"Set back {i}", (set_dir / img).as_posix(), box_tl, box_br))
    screens = [k for k in names if figs[k].get("kind") == "screen"]
    if SET.get("glow") and screens:
        x0, y0, x1, y1 = scr
        back.append(circle("Screen glow", hexc(SET["glow"], 0.35), 0.9 * (x1 - x0), ((x0 + x1) / 2, (y0 + y1) / 2),
                           feather=0.7 * (x1 - x0)))
    monitor = []
    for k in screens:
        monitor += screen_face(scr, tracks[k], ASG.get(k, []), fps, face_on)
    monitor += screen_text_images(P, scr, screen_ev, F)
    figures, pivs = [], {}
    for k in svg_names:
        lay, pivs[k] = svg_rig(k, figs[k], P, tracks[k], ASG.get(k, []), fps, places[k], FLOOR, K, N)
        figures += lay
    front = []
    if SET.get("desk"):
        dk = SET["desk"]
        front += [box("Desk", -9, dk["top"], 9, -5, hexc(dk.get("color", "#6b4a33"))),
                  box("Desk edge", -9, dk["top"] + 0.12, 9, dk["top"] - 0.05, hexc("#8a6446"))]
    for i, img in enumerate(SET.get("front", [])):
        front.append(image(f"Set front {i}", (set_dir / img).as_posix(), box_tl, box_br))
    layers = (back + figures + front + monitor) if SET.get("desk") else (back + monitor + figures + front)

    # ---- camera: static, or cuts between a two-shot and close-ups on the speaker
    view = P.get("view") or SET.get("view") or VIEW
    vx0, vy0, vx1, vy1 = [float(v) for v in view.split()]
    vc = ((vx0 + vx1) / 2, (vy0 + vy1) / 2)
    mode = P.get("camera", "auto")
    if mode == "auto":
        mode = "cuts" if len(names) > 1 and DL["duration"] > 9 else "static"
    shots = []
    if mode == "cuts":
        r = creative.rng(P, "camera")
        zoom = float(P.get("close_zoom", 1.55))
        for i, l in enumerate(lines):
            if i == 0 or r.random() < 0.35:
                shots.append((F(l["t"]) - 6 if i else 0, 1.0, vc))
                continue
            k = l["who"]
            if figs[k].get("kind") == "screen":
                c = ((scr[0] + scr[2]) / 2, (scr[1] + scr[3]) / 2)
            else:
                hx, hy = pivs[k].get("kopf", (0, 4))
                kf = K * float(figs[k].get("size", 1.0))
                c = (places[k] + kf * hx, FLOOR + kf * hy)
            hw, hh = (vx1 - vx0) / 2 / zoom, (vy0 - vy1) / 2 / zoom
            c = (min(max(c[0], box_tl[0] + hw), box_br[0] - hw), min(max(c[1], box_br[1] + hh), box_tl[1] - hh))
            shots.append((max(F(l["t"]) - 6, 0), zoom, c))
        shots.append((N, 1.0, vc))                      # last frame value only (constant)
    if shots:
        sc = [(f, (s, s), "constant") for f, s, c in shots[:-1]]
        off = [(f, (vc[0] - s * c[0], vc[1] - s * c[1]), "constant") for f, s, c in shots[:-1]]
        scene = group("Camera", layers, origin=(0, 0), offset=anim("vector", off), scale=anim("vector", sc))
    else:
        cam = [(0, (1.0, 1.0)), (N, (1.0 + float(P.get("push_in", 0.0)),) * 2, "linear")]
        scene = group("Camera", layers, origin=vc, offset=V(*vc), scale=anim("vector", cam))
    out_dir = P.dir / "scenes"
    out_dir.mkdir(exist_ok=True)
    sif = out_dir / "dialogue.sif"
    sif.write_text(canvas([scene], w=P.size[0], h=P.size[1], fps=P.fps, end=N, name=P.get("name", "Dialogue"), view=view), encoding="utf-8")
    (P.analysis / "actions_dialogue.json").write_text(json.dumps(gestures_out, ensure_ascii=False), encoding="utf-8")
    print(f"-> {sif.relative_to(P.dir)}: {N} frames, figures {names}, gestures {len(gestures_out)}, "
          f"screen texts {len(screen_ev)}, camera {mode} ({max(len(shots) - 1, 0)} shots), styles "
          f"{ {k: (v['listen'], v['hands']) for k, v in style.items()} } (seed {creative.seed(P)})")
    if a.render:
        frames = out_dir / "dialogue"
        if frames.exists():
            for p in frames.glob("*.png"):
                p.unlink()
        subprocess.run([sys.executable, str(_studio.skill_dir("toon-2d") / "scripts" / "synfig_parallel.py"), str(sif),
                        str(frames), "--jobs", str(a.jobs)], check=True)
        print(f"-> {frames.relative_to(P.dir)}/f.%04d.png ({len(list(frames.glob('*.png')))} images)")


if __name__ == "__main__":
    main()
