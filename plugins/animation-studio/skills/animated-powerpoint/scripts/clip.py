"""Build and render one presentation clip: figures step out of the flat slide into a 2.5D room.

  clip.py clips/<name>/clip.json [--only plan|synfig|light|tex|3d|final] [--jobs 8]

clip.json (paths relative to it):
  {"deck": "../../deck/deck.json", "slide": 5, "figures_dir": "../../figures",
   "size": [1920, 1080],                  output size; default = 1920 x slide aspect (fits the presentation)
   "fps": 24, "look": "standard" | "none", "ending": "stay" | "return" (return = loopable, last frame = first),
   "boil": 0.0012,                        line boil in the room (0 = off)
   "hold": 36,                            ending "return": frames the tag stays before the hop back
   "figures": [{"name": "fritz", "action": "step_out", "start": 22, "tag": ["Fritz", "Builder"],
                "gesture": "fist", "spin": "flip", "gesture_part": "arm_r", "land": [-0.3, 3.2]},
               {"name": "hans", "action": "watch"}],
   "tail": 0,                              extra frames at the end
   "camera": [[0, [0, 0, 16.79, 0, 0, 0]], [{"fig": "fritz", "event": "land", "offset": 6}, [-4.2, -1.7, 12.4, 1, -2.6, 2.6]]]}
                                           optional own camera keys (time specs allowed) instead of the automatic shots
Figures not listed stay in the slide picture. "start" = first frame of the routine (look around); the routines of
several step_out figures follow each other when "start" is left out.
Steps (each writes into the clip folder, a later step reuses the earlier results):
  plan    acting keys + per-frame stage values -> <fig>.sif, stage.json
  synfig  Synfig renders every figure alone (transparent) -> frames/<fig>/<fig>.NNNN.png   (toon-2d render.py)
  light   light maps for flat -> rounded -> light/<fig>/s.NNNN.png
  tex     slide states (figures removed, dashed outlines), room, shadow, name tags -> tex/
  3d      three.js stage in headless Edge/Chrome -> frames_3d/mp_NNNN.png, stage.mp4      (toon-2d render_multiplane.py)
  final   look (film-finish apply_look.py) -> <name>.mp4, first/last frame PNG, contact sheet, in/out check
  sound   narration + sound effects on the event frames (sound.py, earshot) -> ton.wav, muxed into <name>.mp4
Usage: uv run --no-project --with pillow --with numpy --with scipy --with scikit-image [--with faster-whisper] python clip.py
       clips/x/clip.json            (faster-whisper when the clip has narration: word times)
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

import _studio
_studio.use("toon-2d", "film-finish")
import acting as A  # noqa: E402
import config  # noqa: E402
import creative  # noqa: E402
from sif import anim, canvas, group, image  # noqa: E402

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
PX_PER_SU = 108          # Synfig render resolution (px per unit)
H_REF = 3.80             # height (world) of the reference figure (Fritz on slide 5) the camera moves were made for
WORLD_W = 16.0


class Clip:
    def __init__(self, path):
        self.file = Path(path).resolve()
        self.dir = self.file.parent
        self.p = json.loads(self.file.read_text(encoding="utf-8"))
        self.deck_file = (self.dir / self.p.get("deck", "../../deck/deck.json")).resolve()
        self.deck = json.loads(self.deck_file.read_text(encoding="utf-8"))
        self.slide = next(s for s in self.deck["slides"] if s["n"] == self.p["slide"])
        self.fig_root = (self.dir / self.p.get("figures_dir", "../../figures")).resolve()
        self.fps = self.p.get("fps", 24)
        sw, sh = self.deck["width"], self.deck["height"]
        self.slide_px = (sw, sh)
        self.ppw = sw / WORLD_W                                     # slide px per world unit
        self.Ws, self.Hs = WORLD_W, sh / self.ppw
        self.floor = -self.Hs / 2
        w = self.p.get("size", [1920, round(1920 * sh / sw / 2) * 2])
        self.size = (int(w[0]), int(w[1]))
        self.fov = 30.0
        self.z0 = (self.Hs / 2) / math.tan(math.radians(self.fov / 2))   # frontal: the slide fills the frame

    def save(self):
        self.file.write_text(json.dumps(self.p, indent=1, ensure_ascii=False), encoding="utf-8")


def fig_geometry(C, name):
    d = C.fig_root / name
    fj = json.loads((d / "figure.json").read_text(encoding="utf-8"))
    rig = json.loads((d / "rig.json").read_text(encoding="utf-8"))
    pj = json.loads((d / "parts.json").read_text(encoding="utf-8"))
    t = fj["to_slide"]
    cx0, cy0 = fj["crop"][:2]

    def world(x, y):              # crop px -> world
        sx, sy = t["ox"] + t["ax"] * (cx0 + x), t["oy"] + t["ay"] * (cy0 + y)
        return sx / C.ppw - C.Ws / 2, C.Hs / 2 - sy / C.ppw
    su_px = rig["su_px"]
    su_world = su_px * t["ax"] / C.ppw
    fx, fy = rig["feet"]
    l, tp, r, b = rig["view"]
    scale = pj.get("scale", 1.0)
    g = {"name": name, "dir": d, "fig": fj, "rig": rig, "parts_cfg": pj, "su_world": su_world,
         "feet_world": world(fx, fy), "height": (fy - rig["top"]) / su_px * su_world,
         "plane_w": (r - l) * su_world, "center_above_feet": (tp + b) / 2 * su_world, "center_dx": (l + r) / 2 * su_world,
         "px": int(round((r - l) * PX_PER_SU)),
         "blobs": [{"dx": round((bb["x"] - fx) / su_px * su_world, 4), "w": round(bb["w"] / su_px * su_world * 1.35, 4),
                    "dz": round(-0.4 * bb["dz_px"] / (48 * scale), 4)} for bb in rig["blobs"]]}
    g["su"] = lambda x, y: ((x - fx) / su_px, (fy - y) / su_px)
    return g


# ----------------------------------------------------------------- plan: acting + stage values
class Times:
    """Resolves time specs of clip.json: a frame number, or
       {"fig": "felix", "event": "land", "offset": -12}        an event of a figure (start, take_off, pop, land, tag, ...)
       {"line": "felix", "word": "spots", "nth": 1, "end": false, "offset": 0}   a word of a narration line
       {"line": "fritz", "edge": "end", "offset": 6}          start/end of a narration line
       {"max": [spec, ...]} / {"min": [spec, ...]}"""
    def __init__(self, C):
        self.C, self.events, self.lines, self._words = C, {}, {}, {}
        self.cfg = {n["id"]: n for n in C.p.get("narration", [])}

    def words(self, lid):
        if lid not in self._words:
            import narration
            n = self.cfg[lid]
            self._words[lid] = narration.words(self.C.dir / n["audio"], self.C.dir / "narration", n.get("lang", "en"))
        return self._words[lid]

    def line_at(self, lid):
        if lid not in self.lines:
            if lid not in self.cfg:
                raise SystemExit(f"narration line '{lid}' is not defined")
            self.lines[lid] = self(self.cfg[lid].get("at", 0))
        return self.lines[lid]

    def __call__(self, spec):
        if spec is None or isinstance(spec, (int, float)):
            return None if spec is None else int(round(spec))
        if "max" in spec or "min" in spec:
            vals = [self(x) for x in spec.get("max", spec.get("min"))]
            return (max if "max" in spec else min)(vals) + int(spec.get("offset", 0))
        off = int(spec.get("offset", 0))
        if "fig" in spec:
            ev = self.events.get(spec["fig"], {})
            if spec.get("event", "start") not in ev:
                raise SystemExit(f"time spec {spec}: that event is not known yet (figures are planned in order)")
            v = ev[spec.get("event", "start")]
            return (v[0] if isinstance(v, list) else v) + off
        if "line" in spec:
            import narration
            at, w = self.line_at(spec["line"]), self.words(spec["line"])
            if "word" in spec:
                t = narration.word_time(w, spec["word"], spec.get("nth", 1), spec.get("end", False))
            else:
                t = w["duration"] if spec.get("edge") == "end" else 0.0
            return at + int(round(t * self.C.fps)) + off
        raise SystemExit(f"unknown time spec {spec}")


def look_keys(G, n, intervals, own):
    """Eyes (+ small head turns) of figure n following the figure that is acting: intervals [(a, b, m)]."""
    eyes, head = [], []
    g = G[n]

    def x_at(name, t):
        h = G[name]
        if "R" in h and t >= h["R"].L:
            return h["land"][0]
        return h["slot"][0]
    iv = sorted(intervals)
    for i, (a, b, m) in enumerate(iv):
        nxt = iv[i + 1][0] if i + 1 < len(iv) else None
        if nxt is not None:
            b = min(b, nxt - 2)
        if b - a < 8:
            continue
        d1 = max(-0.09, min(0.09, 0.03 * (x_at(m, a + 6) - x_at(n, a + 6))))
        d2 = max(-0.09, min(0.09, 0.03 * (x_at(m, b) - x_at(n, b))))
        eyes += [(a, (0, 0)), (a + 6, (round(d1, 3), 0.0)), (b, (round(d2, 3), -0.02))]
        head += [(a, 0), (a + 8, 3 if d1 > 0 else -3), (b, 3 if d2 > 0 else -3)]
        if nxt is None or nxt > b + 8:
            eyes.append((b + 6, (0, 0)))
            head.append((b + 8, 0))

    def free(k):
        return all(not (o0 - 8 <= k[0] <= o1 + 8) for o0, o1 in own)
    return [k for k in eyes if free(k)], [k for k in head if free(k)]


def plan(C):
    import routines as RT
    P = C.p
    figs = P["figures"]
    G = {f["name"]: fig_geometry(C, f["name"]) for f in figs}
    T = Times(C)
    movers = [f for f in figs if f.get("action", "step_out") == "step_out"]
    if not movers:
        raise SystemExit("no figure with action step_out")
    multi = len(movers) > 1
    spread = P.get("spread", 1.0 if not multi else 1.18)          # several figures: landing places further apart
    # ---- pass 1: routines in order (start, take-off, pop, landing)
    t = 22
    landed = []
    for f in movers:
        n = f["name"]
        g = G[n]
        q = g["height"] / H_REF
        FX, FY = g["feet_world"]
        style = f.get("style", "jump")
        T.events[n] = {}
        s = T(f.get("start")) if f.get("start") is not None else t
        T.events[n]["start"] = s
        if "land" in f:
            LX, LZ = FX + f["land"][0] * q, f["land"][1] * q
        else:
            LX, LZ = FX * spread - 0.3 * q * (1 if FX >= 0 else -1), 3.2 * q
        if landed:          # camera from the side where no figure stands yet
            mean_x = sum(G[m]["land"][0] for m in landed) / len(landed)
            side = -1 if mean_x > LX else 1
        else:
            side = -1 if FX >= 0 else 1
        side = f.get("camera_side", side)
        g.update(q=q, side=side, start=s, land=[LX, C.floor, LZ], slot=[FX, FY, 0.0], style=style)
        f.setdefault("gesture", creative.pick(P, f"gesture:{n}", ["fist", "wave", "nod"]))
        f.setdefault("spin", creative.pick(P, f"spin:{n}", ["flip", "flip", "none"]) if style == "jump" else "none")
        pop_at = T(f.get("pop_at")) if f.get("pop_at") is not None else None
        R = RT.build(style, s, g, f["spin"], -1 if side < 0 else 1, pop_at)
        g["R"], g["L"] = R, R.L
        if R.pop is None:
            R.pop = next((fr for fr in range(R.L, R.land_f) if R.feet(fr)[2] >= R.bulge["pop_z"] * q), R.L + 6)
        g["pop"] = R.pop
        T.events[n].update(R.events, take_off=R.L, pop=R.pop, land=R.land_f)
        landed.append(n)
        t = R.land_f + 10
    last_land = max(G[f["name"]]["R"].land_f for f in movers)
    # ---- pass 2: gestures, tags (may sit on words of the narration)
    for f in movers:
        n, g = f["name"], G[f["name"]]
        R = g["R"]
        gl = f.get("gestures") or [{"kind": f["gesture"], "at": f.get("gesture_at")}]
        for gg in gl:
            at = T(gg.get("at")) if gg.get("at") is not None else R.land_f + 19
            RT.merge(R.keys, RT.gesture_keys(gg["kind"], at, eye_dir=f.get("look_dir", 1)))
            T.events[n].setdefault("gesture", []).append(at)
        tag_t = T(f["tag_at"]) if f.get("tag_at") is not None else getattr(R, "tag_default", R.land_f + 42)
        g["tag_t"] = tag_t
        T.events[n]["tag"] = tag_t
    # ---- reactions: landed figures with a fist/wave cheer while a later figure is stuck
    order = [f["name"] for f in movers]
    for i, f in enumerate(movers):
        R = G[f["name"]]["R"]
        if R.style != "stuck":
            continue
        for f2 in movers[:i]:
            if f2["gesture"] in ("fist", "wave") and f.get("cheer", True):
                at = T.events[f["name"]]["stuck"] - 6
                RT.merge(G[f2["name"]]["R"].keys, RT.gesture_keys(f2["gesture"], at))
                T.events[f2["name"]].setdefault("cheer", []).append(at)
    # ---- end, group finale, return
    ending = P.get("ending", "stay")
    finale = P.get("finale", "group" if len(movers) >= 3 else None)
    end_routine = max(last_land + A.SETTLE, max(G[n]["tag_t"] for n in order) + 51)
    G0 = None
    if finale == "group" and ending != "return":
        G0 = max(G[n]["tag_t"] for n in order) + 14
        GL = P.get("group_frames", 64)
        end_routine = G0 + GL - 1
        for k, n in enumerate(order):
            f = next(x for x in movers if x["name"] == n)
            kind = {"look_up": "wave", "wag": "nod", "shake": "nod"}.get(f["gesture"], f["gesture"])
            if kind in A.GESTURE_ARM:
                RT.merge(G[n]["R"].keys, RT.gesture_keys(kind, G0 + 20 + 7 * k))
                T.events[n]["group_gesture"] = [kind, G0 + 20 + 7 * k]
    R_ret = end_routine - 30 + P.get("hold", 36) if ending == "return" else None
    end = (R_ret + 22 + 24 if ending == "return" else end_routine) + P.get("tail", 0)
    P["end"] = end
    tag_hold = P.get("tag_hold", 150 if multi else None)
    for n in order:
        g = G[n]
        hide = None
        if tag_hold:
            hide = g["tag_t"] + tag_hold
        if G0 is not None:
            hide = min(hide or 10 ** 6, G0 - 10) if n != order[-1] else G0 + 20
        g["tag_hide"] = hide
    # ---- Synfig keys per figure: routine + idle + blinks + eyes following the others
    keys = {}
    windows = {n: (G[n]["start"] + 10, G[n]["R"].land_f + 30) for n in order}
    for f in movers:
        n, g = f["name"], G[f["name"]]
        R = g["R"]
        k = R.keys
        own = [(g["start"], R.land_f + 50)]
        for a in T.events[n].get("gesture", []):
            if f["gesture"] == "look_up":
                own.append((a - 4, a + 52))
        # glance in a beat: towards the landed figures
        lx = [G[m]["land"][0] for m in order if m != n and G[m]["R"].land_f < g["start"]]
        gdir = 0.08 if (lx and sum(lx) / len(lx) > g["slot"][0]) else -0.08
        k["eyes"] = [(e[0], (gdir if e[1][0] == "glance" else e[1][0], e[1][1])) + tuple(e[2:]) for e in k.get("eyes", [])]
        iv = [(windows[m][0], windows[m][1], m) for m in order if m != n]
        if G0 is not None:
            iv = [(a, min(b, G0 - 4), m) for a, b, m in iv if a < G0 - 12]
        e2, h2 = look_keys(G, n, iv, own)
        k["eyes"] = sorted([(0, (0, 0))] + k["eyes"] + e2, key=lambda x: x[0])
        k["head"] = sorted([(0, 0)] + [x for x in k.get("head", []) if x[0] > 0] + h2, key=lambda x: x[0])
        rng = creative.rng(P, f"idle:{n}")
        ramps = [(R.land_f + 16, R.land_f + 40, 0, 1)]
        if R_ret is not None:
            rk = A.return_keys(R_ret, k["spin"][-1][1])
            for kk, v in rk.items():
                k[kk] = [x for x in k.get(kk, []) if x[0] < rk[kk][0][0]] + v
            ramps.append((R_ret - 22, R_ret - 10, 1, 0))
        k.update(A.idle_keys(rng, end, ramps))
        blinks = A.auto_blinks(rng, R.land_f + 40, R_ret - 24 if R_ret else end)
        pre = A.auto_blinks(creative.rng(P, f"preblink:{n}"), 0, g["start"] - 6) if multi else [(0, 1)]
        k["blink"] = sorted([b for b in pre if b[0] > 0] + k.get("blink", []) + [b for b in blinks if b[0] > R.L + 90],
                            key=lambda x: x[0])
        dedup = {}
        for ch in ("eyes", "head", "blink"):
            dedup = {}
            for x in k[ch]:
                dedup[x[0]] = x
            k[ch] = [dedup[fr] for fr in sorted(dedup)]
        keys[n] = k
    for f in figs:                                                 # figures that speak: Rhubarb -> mouth stages
        n = f["name"]
        talk = [lid for lid, ln in T.cfg.items() if ln.get("speaker") == n] + list(f.get("talk", []))
        if talk and n in keys:
            import mouth
            mouth.ensure(G[n]["dir"])
            keys[n]["mouth"] = mouth.mouth_keys(G[n]["dir"], [(C.dir / T.cfg[lid]["audio"], T.line_at(lid),
                                                               T.cfg[lid].get("text")) for lid in talk],
                                                fps=C.fps, cache=C.dir / "narration")
    for f in figs:                                                 # watchers: alive, flat, eyes follow
        if f.get("action") != "watch":
            continue
        n, g = f["name"], G[f["name"]]
        g.update(q=g["height"] / H_REF, slot=[*g["feet_world"], 0.0], watch=True)
        rng = creative.rng(P, f"watch:{n}")
        e2, h2 = look_keys(G, n, [(windows[m][0], windows[m][1], m) for m in order], [])
        k = {"eyes": [(0, (0, 0))] + e2 + [(end - 12, (0, 0))], "blink": A.auto_blinks(rng, 0, end - 8)}
        ramps = [(10, 40, 0, 0.5)] + ([(end - 40, end - 16, 0.5, 0)] if R_ret is not None else [])
        k.update(A.idle_keys(rng, end, ramps))
        keys[n] = k

    # ---- camera
    cam_keys = [(0, [0, 0, C.z0, 0, 0, 0])]
    for i, f in enumerate(movers):
        n, g = f["name"], G[f["name"]]
        R = g["R"]
        q, side, (FX, FY), (LX, F, LZ) = g["q"], g["side"], g["feet_world"], g["land"]
        look1 = [FX, FY + 2.02 * q, 0]
        look2 = [FX + 0.9 * (LX - FX), FY + 1.07 * q, 1.2 * q]
        look3 = [LX - 0.03 * side, F + 1.9 * q, LZ - 0.6 * q]
        look4 = [LX - 0.53 * side, F + 2.0 * q, LZ - 0.7 * q]
        a0, a1, a2 = R.cam_anchor
        if i == 0:
            cam_keys.append((g["start"] + 2, [0, 0, C.z0, 0, 0, 0]))
        else:                    # the next figure in the slide, seen from its camera side (closer than the line-up)
            lk = [FX, FY + 1.6 * q, 0.6]
            if g["start"] + 8 < a0 - 6:
                cam_keys.append((g["start"] + 8, [FX + 3.3 * side, lk[1] + 0.5, 14.0] + lk))
            if R.style != "jump":
                cam_keys.append((a0, [FX + 2.7 * side, FY + 1.7 * q, 14.0, FX, FY + 0.9 * q, 1.0]))
        if i + 1 < len(movers):
            nxt = G[movers[i + 1]["name"]]
            hold = max(a2 + 12, nxt["start"] - 8)
        else:
            hold = G0 - 6 if G0 is not None else end_routine
        if i == 0 or R.style == "jump":
            cam_keys.append((a0, [look1[0] + 0.13, look1[1] + 0.05 * q, 14.0 * q] + look1))
        cam_keys += [(a1, [look2[0] + 0.8 * side, look2[1] + 0.9 * q, look2[2] + 13.4 * q] + look2),
                     (a2, [look3[0] + 5.2 * side, look3[1] + 0.9 * q, look3[2] + 9.8 * q] + look3),
                     (hold, [look4[0] + 7.1 * side, look4[1] + 1.1 * q, look4[2] + 10.5 * q] + look4)]
    if G0 is not None:
        xs = [G[n]["land"][0] for n in order]
        mx = (min(xs) + max(xs)) / 2
        hs = C.Hs / 9.0
        lz = sum(G[n]["land"][2] for n in order) / len(order)
        cam_keys += [(G0 + 28, [mx, C.floor + 3.7 * hs, lz + 15.4 * hs, mx, C.floor + 2.4 * hs, lz - 1.6 * hs]),
                     (end, [mx, C.floor + 3.8 * hs, lz + 16.2 * hs, mx, C.floor + 2.5 * hs, lz - 1.6 * hs])]
    if R_ret is not None:
        cam_keys += [(R_ret - 4, cam_keys[-1][1]), (R_ret + 22, [0, 0, C.z0, 0, 0, 0]), (end, [0, 0, C.z0, 0, 0, 0])]
    if P.get("camera"):          # a shot list of your own: [[time spec, [x, y, z, look_x, look_y, look_z]], ...]
        cam_keys = [(T(k[0]), [float(v) for v in k[1]]) for k in P["camera"]]
    cam_keys.sort(key=lambda k: k[0])
    shakes = [G[n]["R"].shake_at for n in order if getattr(G[n]["R"], "shake_at", None)]

    # ---- paper bits
    names = [f["name"] for f in figs]
    rng = creative.rng(P, "bits")
    bits = []
    for n in order:
        g = G[n]
        R = g["R"]
        cx, cy = g["slot"][0], g["slot"][1] + R.bulge["h"] * g["q"]
        for _ in range(RT.BITS[R.style]):
            a = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(0.3, 1.6) * g["q"]
            bits.append({"fig": n, "p": [cx + math.cos(a) * r, cy + math.sin(a) * r * 1.3, 0.85],
                         "v": [math.cos(a) * rng.uniform(1.5, 4), math.sin(a) * rng.uniform(1, 4) + 2.0,
                               rng.uniform(2.5, 6)],
                         "rot": [rng.uniform(-9, 9), rng.uniform(-9, 9), rng.uniform(-9, 9)],
                         "size": rng.uniform(0.06, 0.16), "pos": None, "ang": [0, 0, 0], "rest": False})
    # ---- sparkles (look_up: glasses flash)
    sparks = []
    for n in order:
        g = G[n]
        eyes = g["parts_cfg"].get("eyes") or []
        rims = []
        if eyes and g["R"].keys.get("sparkle"):
            im = np.asarray(Image.open(g["dir"] / "original.png").convert("RGBA")).astype(np.float32) / 255
            dark = (im[..., 3] > 0.5) & (im[..., :3].mean(-1) < 0.35)
            for ex, ey in eyes:            # the glint sits on the glasses rim / eye outline up-left of the pupil
                pt, left_pupil = (ex - 30, ey - 50), False
                for t in range(4, 400):
                    x, y = int(ex - 0.53 * t), int(ey - 0.85 * t)
                    if not (0 <= x < dark.shape[1] and 0 <= y < dark.shape[0]):
                        break
                    if not dark[y, x]:
                        left_pupil = True
                    elif left_pupil:
                        pt = (x, y)
                        break
                rims.append(pt)
        for j, fr0 in enumerate(g["R"].keys.get("sparkle", [])):
            if rims:
                dx, dy = g["su"](*rims[j % len(rims)])
                sparks.append({"fig": n, "f": fr0, "d": [dx * g["su_world"], dy * g["su_world"]]})

    states, frames = {}, []
    dt, grav = 1 / C.fps / 3, -14.0
    for fr in range(end + 1):
        cam = A.keyed(cam_keys, fr)
        for sa in shakes:
            tt = fr - sa
            if 0 <= tt < 14:
                s_ = 0.07 * math.exp(-tt / 4)
                cam = list(cam)
                cam[1] += s_ * math.sin(tt * 2.6)
                cam[0] += s_ * 0.6 * math.sin(tt * 3.7)
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
            if abs(b) > abs(bulge):
                bulge, bc, bs = b, [g["slot"][0], g["slot"][1] + bp["h"] * q], bp["sigma"] * q
            height = feet[1] - C.floor
            out_of_slide = A.smooth((feet[2] - 0.4 * q) / (1.0 * q))
            shadow = {"x": feet[0], "z": feet[2] - 0.2 * q, "s": 2.2 * q * (1 + 0.22 * height / q),
                      "a": 0.38 * out_of_slide * max(0.0, 1 - height / (4.5 * q)),
                      "contact": 0.62 * out_of_slide * max(0.0, 1 - height / (0.35 * q))}
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
            figd.append({"feet": [round(v, 4) for v in feet], "shade": round(shade, 4),
                         "shadow": {k: round(v, 4) for k, v in shadow.items()}, "tag": round(tag, 4)})
        pieces = []
        for bt in bits:
            g = G[bt["fig"]]
            if bt["pos"] is None:
                bt["pos"] = list(bt["p"])
            active = fr >= g["pop"] and (R_ret is None or fr < R_ret)
            if active and not bt["rest"]:
                for _ in range(3):
                    bt["v"][1] += grav * dt
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
        sp = []
        for s_ in sparks:
            t_ = fr - s_["f"]
            u = t_ / 14
            if 0 <= t_ < 14 and s_["fig"] in feet_now:                       # pops in 4 frames, fades in 10
                (fx, fy, fz), shade = feet_now[s_["fig"]]
                ry = shade * math.atan2(cam[0] - fx, cam[2] - fz)
                dx, dy = s_["d"]
                sp.append([round(fx + dx * math.cos(ry), 4), round(fy + dy, 4), round(fz + 0.12 - dx * math.sin(ry), 4),
                           round((t_ / 4 if t_ < 4 else max(0.0, 1 - (t_ - 4) / 10)) * 0.9 * G[s_["fig"]]["q"], 4),
                           round(t_ * 0.12, 3), 1])
            else:
                sp.append([0, 0, 0, 0, 0, 0])
        states.setdefault(out_mask, len(states))
        fd = {"cam": [round(v, 4) for v in cam[:3]], "look": [round(v, 4) for v in cam[3:]],
              "state": states[out_mask], "bulge": round(bulge, 4), "bulge_center": [round(v, 4) for v in bc],
              "bulge_sigma": round(bs, 4), "figs": figd, "bits": pieces}
        if sparks:
            fd["sparkles"] = sp
        frames.append(fd)
    # ---- Synfig scenes
    for n in names:
        write_sif(C, G[n], keys[n], end, gesture_part=next((f.get("gesture_part") for f in figs if f["name"] == n), None))
    events = {}
    for n in order:
        g = G[n]
        events[n] = {"style": g["style"], **{k: v for k, v in T.events[n].items()}}
        if g["style"] == "jump":
            events[n].update(look_left=g["start"] + 3, look_right=g["start"] + 12)
        if g["R"].keys.get("sparkle"):
            events[n]["sparkle"] = g["R"].keys["sparkle"]
        if R_ret is not None:
            events[n].update(back_take_off=R_ret, back_in_slot=R_ret + 22)
    if G0 is not None:
        events["_group"] = {"start": G0}
    stage = {
        "width": C.size[0], "height": C.size[1], "fps": C.fps, "end": end, "fov": C.fov, "out": "frames_3d",
        "floor_y": C.floor, "boil": P.get("boil", 0.0012),
        "slide": {"w": C.Ws, "h": C.Hs, "states": [f"tex/slide_{m:02x}.png" for m in states]},
        "tex": {"floor": "tex/floor.png", "wall": "tex/wall.png", "shadow": "tex/shadow.png",
                "sparkle": "tex/sparkle.png"},
        "sparkles": len(sparks),
        "figures": [{"name": n, "src": f"frames/{n}/{n}.%04d.png", "light": f"light/{n}/s.%04d.png",
                     "plane_w": G[n]["plane_w"], "center_above_feet": G[n]["center_above_feet"],
                     "center_dx": G[n]["center_dx"], "foot_blobs": G[n]["blobs"],
                     "tag": tag_cfg(C, G[n], figs) if n in order else None} for n in names],
        "frames": frames}
    (C.dir / "stage.json").write_text(json.dumps(stage), encoding="utf-8")
    lines = {lid: {"at": T.line_at(lid), "audio": T.cfg[lid]["audio"], "level": T.cfg[lid].get("level", 0),
                   "seconds": T.words(lid)["duration"]} for lid in T.cfg}
    meta = {"end": end, "events": events, "narration": lines, "states": {f"{m:02x}": i for m, i in states.items()},
            "figures": {n: {k: G[n][k] for k in ("feet_world", "height", "plane_w", "px", "su_world")} for n in names},
            "land": {n: [round(v, 3) for v in G[n]["land"]] for n in order},
            "variants": {f["name"]: {k: f.get(k) for k in ("style", "gesture", "spin")} for f in movers}}
    (C.dir / "plan.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    C.save()
    print(f"  plan: {end + 1} frames, events {json.dumps(events)}")
    return meta


def tag_cfg(C, g, figs):
    f = next(x for x in figs if x["name"] == g["name"])
    if not f.get("tag"):
        return None
    q, side, (LX, F, LZ) = g["q"], g["side"], g["land"]
    movers = [x for x in figs if x.get("action", "step_out") == "step_out"]
    narrow = min(1.0, C.size[0] / C.size[1] / (16 / 9))                     # 4:3: closer
    if len(movers) > 1:          # a line-up: small tags, always on the same side (+x), so they never cover a neighbour
        d = f.get("tag_offset", 1.75)
        return {"src": f"tex/tag_{g['name']}.png", "w": 2.1 * narrow, "aspect": 380 / 900,
                "pos": [LX + d * q * narrow, F, LZ + 0.5 * q]}
    d = f.get("tag_offset", 3.0)
    return {"src": f"tex/tag_{g['name']}.png", "w": 2.8 * q, "aspect": 380 / 900,
            "pos": [LX - d * side * q * narrow, F, LZ + 0.6 * q]}


def write_sif(C, g, keys, end, gesture_part=None):
    """Synfig rig from the original parts: position -> tilt -> idle weight -> breath -> squash (feet) -> spin (centre)
    -> parts; jointed parts in angle groups (+ inner idle groups), eyes move and blink inside the head."""
    rig, d = g["rig"], g["dir"]
    W, H = rig["size"]
    su = g["su"]
    tl, br = su(0, 0), su(W, H)
    piv = {k: su(*v) for k, v in rig["pivots"].items()}
    com = su(*rig["com"])
    parts = rig["parts"]
    joints = [p for p in parts if p in piv and p not in ("head", "body", "eyes")]
    gp = gesture_part or next((p for p in ("arm_r", "arm_l", "arm", "hand_r", "wing_r", "wing", "wing_l")
                               if p in joints), None)

    def img(p):
        return image(p, (d / f"{p}.png").as_posix(), tl=tl, br=br)

    def angle_group(p, kids, k, idle):
        if idle in keys:
            kids = [group(f"{p}_idle", kids, origin=piv[p], angle=anim("angle", keys[idle]))]
        if k and k in keys:
            return group(p, kids, origin=piv[p], angle=anim("angle", keys[k]))
        return group(p, kids, origin=piv[p])

    layers = []
    for p in parts:
        if p == "eyes":
            continue
        if p == "head" and "head" in piv:
            kids = [img("head")]
            if keys.get("mouth") and (d / "head_base.png").exists():        # lip sync: base + one stage per frame
                mk = keys["mouth"]
                kids = [image("head_base", (d / "head_base.png").as_posix(), tl=tl, br=br)]
                for i in range(8):
                    vis = [(f, 1.0 if s == i else 0.0, "constant") for f, s in mk]
                    kids.append(group(f"mouth_{i}", [image(f"mouth_{i}", (d / f"mouth_{i}.png").as_posix(), tl=tl, br=br)],
                                      amount=anim("real", vis)))
            if "eyes" in parts:
                a = np.asarray(Image.open(d / "eyes.png"))[..., 3] > 128
                ys, xs = np.nonzero(a)
                ec = su(xs.mean(), ys.mean())
                ek = keys.get("eyes", [(0, (0, 0))])
                bk = keys.get("blink", [(0, 1)])
                kids.append(group("eyes", [img("eyes")], origin=ec,
                                  offset=anim("vector", [(k[0], (ec[0] + k[1][0], ec[1] + k[1][1])) + tuple(k[2:])
                                                         for k in ek]),
                                  scale=anim("vector", [(k[0], (1, k[1]), k[2] if len(k) > 2 else "linear")
                                                        for k in bk])))
            layers.append(angle_group("head", kids, "head", "idle_head"))
        elif p in joints:
            ch = p if p in keys else ("gesture" if p == gp else "follow")        # keys by part name win (scenes)
            layers.append(angle_group(p, [img(p)], ch, "idle_part"))
        else:
            layers.append(img(p))
    if "eyes" in parts and "head" not in piv:
        layers.append(img("eyes"))
    gr = group("spin", layers, origin=com, angle=anim("angle", keys.get("spin", [(0, 0)])))
    gr = group("squash", [gr], origin=(0, 0), scale=anim("vector", keys.get("sq", [(0, (1, 1))])))
    if "tilt" in keys:                                     # whole figure tips over its feet (hop, waddle)
        gr = group("tilt", [gr], origin=(0, 0), angle=anim("angle", keys["tilt"]))
    if "idle_breath" in keys:
        gr = group("breath", [gr], origin=(0, 0), scale=anim("vector", [(f, (1, v)) for f, v in keys["idle_breath"]]))
    if "idle_tilt" in keys:
        gr = group("weight", [gr], origin=(0, 0), angle=anim("angle", keys["idle_tilt"]))
    gr = group(g["name"], [gr], origin=(0, 0), offset=anim("vector", keys["pos"]) if "pos" in keys else None)
    l, t, r, b = rig["view"]
    sif = canvas([gr], w=g["px"], h=g["px"], fps=C.fps, end=end, name=g["name"], view=f"{l} {t} {r} {b}")
    (C.dir / f"{g['name']}.sif").write_text(sif, encoding="utf-8")


# ----------------------------------------------------------------- light maps
LIGHT = np.array([-0.5, 0.6, 0.62]); LIGHT /= np.linalg.norm(LIGHT)       # from top left front
RIM = np.array([0.75, 0.35]); RIM /= np.linalg.norm(RIM)                  # rim light from the right back


def light_map(job):
    src, dst = job
    if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
        return
    a = np.asarray(Image.open(src))[..., 3].astype(np.float32) / 255
    sil = (a > 0.5).astype(np.float32)
    s = a.shape[0] / 1400.0
    b = ndi.gaussian_filter(sil, 26 * s) * 0.6 + ndi.gaussian_filter(sil, 9 * s) * 0.4
    b = b.astype(np.float32)
    gy, gx = np.gradient(b)
    k = 34.0 * s
    nx, ny, nz = -gx * k, gy * k, np.ones_like(b)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / n, ny / n, nz / n
    li = np.clip(1.0 + 1.1 * (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2] - LIGHT[2]), 0.55, 1.2)
    rim = np.clip(1 - nz, 0, 1) ** 0.8 * np.clip((nx * RIM[0] + ny * RIM[1]) / np.maximum(np.hypot(nx, ny), 1e-4), 0, 1)
    ao = 0.86 + 0.14 * np.clip((b - 0.25) / 0.6, 0, 1)
    out = np.dstack([li / 2, np.clip(rim, 0, 1), ao, np.ones_like(b)])
    Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA").save(dst)


def lights(C):
    jobs = []
    for f in C.p["figures"]:
        n = f["name"]
        (C.dir / "light" / n).mkdir(parents=True, exist_ok=True)
        jobs += [(p, C.dir / "light" / n / ("s." + p.name.split(".")[-2] + ".png"))
                 for p in sorted((C.dir / "frames" / n).glob(f"{n}.*.png"))]
    # bounded: every job holds ~25 full-size float arrays (all CPU threads at once ran out of RAM on 4 figures)
    with ThreadPoolExecutor(min(6, os.cpu_count() or 4)) as ex:
        list(ex.map(light_map, jobs))
    print(f"  light maps: {len(jobs)}")


# ----------------------------------------------------------------- textures
def rest_mask(g):
    a = None
    for p in g["rig"]["parts"]:
        al = np.asarray(Image.open(g["dir"] / f"{p}.png"))[..., 3].astype(np.float32) / 255
        a = al if a is None else np.maximum(a, al)
    return a


def dashed_outline(mask, size, dash=34, gap=22, width=9):
    from skimage import measure
    sil = ndi.binary_fill_holes(mask > 0.5)
    sil = ndi.binary_opening(sil, iterations=4)
    outer = ndi.gaussian_filter((ndi.distance_transform_edt(~sil) < 15).astype(np.float32), 6)
    cont = max(measure.find_contours(outer, 0.5), key=len)
    seg = np.hypot(*np.diff(cont, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    img = Image.new("L", size, 0)
    dr = ImageDraw.Draw(img)
    for i in range(len(cont) - 1):
        if (s[i] % (dash + gap)) < dash:
            (y0, x0), (y1, x1) = cont[i], cont[i + 1]
            dr.line([(x0, y0), (x1, y1)], fill=255, width=width)
    return ndi.gaussian_filter(np.asarray(img).astype(np.float32) / 255, 0.7)


def accent_color(g):
    im = np.asarray(Image.open(g["dir"] / "original.png").convert("RGBA")).astype(np.float32) / 255
    rgb, a = im[..., :3], im[..., 3]
    chroma = rgb.max(-1) - rgb.min(-1)
    m = (a > 0.9) & (chroma > 0.15)
    if m.sum() < 200:
        return (70, 70, 74)
    return tuple(int(v * 255) for v in np.median(rgb[m], axis=0))


def font(bold, size):
    names = ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["segoeui.ttf", "arial.ttf",
                                                                                 "DejaVuSans.ttf"]
    dirs = [Path(os.environ.get("WINDIR", "")) / "Fonts", Path("/usr/share/fonts/truetype/dejavu"),
            Path("/Library/Fonts")]
    for dd in dirs:
        for n in names:
            if (dd / n).exists():
                return ImageFont.truetype(str(dd / n), size)
    return ImageFont.load_default()


def room_textures(tex):
    """Room textures shared by clips and scenes: floor, back wall, soft contact shadow, four-point sparkle."""
    rng = np.random.default_rng(3)
    n = 2048
    noise = ndi.gaussian_filter(rng.normal(0, 1, (n, n)), 1.2) * 4 + ndi.gaussian_filter(rng.normal(0, 1, (n, n)), 18) * 30
    yy, xx = np.mgrid[:n, :n] / n
    pool = np.exp(-(((xx - 0.5) / 0.38) ** 2 + ((yy - 0.42) / 0.30) ** 2))
    v = 168 + 62 * pool + noise
    Image.fromarray(np.clip(np.dstack([v, v * 0.985, v * 0.95]), 0, 255).astype(np.uint8)).save(tex / "floor.png")
    hh, ww = 1024, 2048
    yy, xx = np.mgrid[:hh, :ww]
    glow = np.exp(-(((xx - ww / 2) / (ww * 0.32)) ** 2 + ((yy - hh * 0.55) / (hh * 0.45)) ** 2))
    v = 38 + 70 * glow + ndi.gaussian_filter(rng.normal(0, 1, (hh, ww)), 2) * 2
    Image.fromarray(np.clip(np.dstack([v * 1.05, v * 0.98, v * 0.9]), 0, 255).astype(np.uint8)).save(tex / "wall.png")
    s = 256
    yy, xx = (np.mgrid[:s, :s] - s / 2 + 0.5) / (s / 2)
    a = np.clip(1 - np.hypot(xx, yy), 0, 1) ** 1.6
    Image.fromarray(np.dstack([np.zeros((s, s, 3)), a * 255]).astype(np.uint8), "RGBA").save(tex / "shadow.png")
    r = np.hypot(xx, yy) + 1e-6                                       # four-point sparkle (glasses flash)
    ang = np.arctan2(yy, xx)
    rays = np.abs(np.cos(2 * ang)) ** 18
    star = np.clip(1 - r / (0.12 + 0.88 * rays), 0, 1) ** 1.5 + np.clip(1 - r / 0.25, 0, 1) ** 2
    Image.fromarray(np.dstack([np.full((s, s), 255.0), np.full((s, s), 252.0), np.full((s, s), 235.0),
                               np.clip(star, 0, 1) * 255]).astype(np.uint8),
                    "RGBA").save(tex / "sparkle.png")


def textures(C):
    tex = C.dir / "tex"
    tex.mkdir(exist_ok=True)
    deck_dir = C.deck_file.parent
    names = [f["name"] for f in C.p["figures"]]
    G = {n: fig_geometry(C, n) for n in names}
    sw, sh = C.slide_px
    by_source = {}
    for n in names:
        by_source.setdefault(G[n]["fig"]["source"], []).append(n)
    plate_name = C.slide.get("plate")
    plate = Image.open(deck_dir / (plate_name or C.slide["clean"])).convert("RGBA").resize((sw, sh), Image.LANCZOS)
    full = plate.copy()
    masks = {}
    for src_rel, members in by_source.items():
        g0 = G[members[0]]
        src = np.asarray(Image.open(C.fig_root / Path(src_rel).name).convert("RGBA")).astype(np.float32)
        fm_all = np.zeros(src.shape[:2], np.float32)
        f = g0["fig"]["upscale"]
        for n in members:
            g = G[n]
            m = rest_mask(g)
            x0, y0 = g["fig"]["crop"][:2]
            full_m = np.zeros(src.shape[:2], np.float32)
            full_m[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = m
            masks[n] = full_m
            fm_all = np.maximum(fm_all, full_m)
        ring = ndi.binary_dilation(fm_all > 0.05, iterations=int(10 * f)) & (src[..., 3] < 128)
        cut = src.copy()
        cut[..., 3] *= 1 - np.maximum(np.clip(fm_all * 1.15, 0, 1), ring)
        t = g0["fig"]["to_slide"]
        pic = next((p for p in C.slide["pictures"] if p["id"] == g0["fig"]["picture"]), None)
        if pic:
            vx0, vy0, vx1, vy1 = [int(round(v * f)) for v in pic["visible"]]
            vis = Image.fromarray(cut.astype(np.uint8), "RGBA").crop((vx0, vy0, vx1, vy1))
            r = pic["rect"]
            plate.alpha_composite(vis.resize((round(r[2]), round(r[3])), Image.LANCZOS), (round(r[0]), round(r[1])))
        else:   # figure painted into the slide: fill the hole from the surrounding background
            hole = ndi.binary_dilation(fm_all > 0.05, iterations=int(6 * f))
            rgb = src[..., :3]
            _, (iy, ix) = ndi.distance_transform_edt(hole, return_indices=True)
            filled = rgb[iy, ix]
            soft = ndi.gaussian_filter(filled, (6 * f, 6 * f, 0))
            rgb2 = np.where(hole[..., None], soft, rgb)
            im = Image.fromarray(np.dstack([rgb2, np.full(hole.shape, 255.0)]).astype(np.uint8), "RGBA")
            plate = im.resize((sw, sh), Image.LANCZOS)
        # masks on the slide (for outlines)
        for n in members:
            g = G[n]
            m_img = Image.fromarray((masks[n] * 255).astype(np.uint8), "L")
            W0, H0 = m_img.size
            sm = m_img.resize((round(W0 * t["ax"]), round(H0 * t["ay"])), Image.LANCZOS)
            canvas_m = Image.new("L", (sw, sh), 0)
            canvas_m.paste(sm, (round(t["ox"]), round(t["oy"])))
            masks[n] = np.asarray(canvas_m).astype(np.float32) / 255
    base = np.asarray(plate.convert("RGB")).astype(np.float32)
    k = 0
    stage = json.loads((C.dir / "stage.json").read_text(encoding="utf-8"))
    order = list(stage["slide"]["states"])
    dashes = {}
    for st in order:
        mask_bits = int(Path(st).stem.split("_")[1], 16)
        img = base.copy()
        for i, n in enumerate(names):
            if mask_bits >> i & 1:
                if n not in dashes:
                    dashes[n] = dashed_outline(masks[n], (sw, sh), dash=round(34 * sw / 3840), gap=round(22 * sw / 3840),
                                               width=max(2, round(9 * sw / 3840)))
                col = np.array(accent_color(G[n]), np.float32)
                al = np.clip(dashes[n], 0, 1)[..., None] * 0.8
                img = img * (1 - al) + col * al
        Image.fromarray(img.astype(np.uint8)).save(C.dir / st)
        k += 1
    room_textures(tex)
    for f in C.p["figures"]:
        if not f.get("tag"):
            continue
        W, H = 900, 380
        card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(card)
        dr.rounded_rectangle((10, 10, W - 10, H - 10), radius=36, fill=(250, 249, 244, 255), outline=(30, 30, 32, 255),
                             width=9)
        title, sub = (f["tag"] + [""])[:2]
        dr.text((W / 2, 140 if sub else H / 2), title, font=font(True, 150), fill=accent_color(G[f["name"]]) + (255,),
                anchor="mm")
        if sub:
            dr.text((W / 2, 280), sub, font=font(False, 92), fill=(40, 40, 44, 255), anchor="mm")
        card.save(tex / f"tag_{f['name']}.png")
    print(f"  textures: {k} slide states, room, tags")


# ----------------------------------------------------------------- render + finish
def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], **kw)
    if r.returncode:
        raise SystemExit(f"failed: {' '.join(str(c) for c in cmd[:3])} ...")


def synfig(C, jobs):
    from render import render_sif
    for f in C.p["figures"]:
        n = f["name"]
        t0 = time.time()
        px = int(fig_geometry(C, n)["px"])          # pass the size: synfig_parallel defaults to 1280x720 (stretches)
        _, cnt = render_sif(C.dir / f"{n}.sif", C.dir / "frames" / n, width=px, height=px, jobs=jobs)
        print(f"  synfig {n}: {cnt} frames in {time.time() - t0:.0f} s")


def three(C):
    page = C.dir / "stage25d.html"
    shutil.copy(ASSETS / "stage25d.html", page)
    run([sys.executable, _studio.skill_dir("toon-2d") / "scripts" / "render_multiplane.py", C.dir / "stage.json",
         "--page", "/stage25d.html", "--contact", "none"])


def final(C):
    from render import contact_sheet
    name = C.dir.name
    raw = C.dir / "stage.mp4"
    out = C.dir / f"{name}.mp4"
    look = C.p.get("look", "standard")
    if look and look != "none":
        run([sys.executable, _studio.skill_dir("film-finish") / "scripts" / "apply_look.py", raw, "-o", out,
             "--look", look])
    else:
        shutil.copy(raw, out)
    ff = config.need("ffmpeg")
    end = C.p["end"]
    run([ff, "-y", "-v", "error", "-i", out, "-vf", "select=eq(n\\,0)", "-frames:v", "1", C.dir / "first.png"])
    run([ff, "-y", "-v", "error", "-sseof", "-0.2", "-i", out, "-update", "1", "-q:v", "1", C.dir / "last.png"])
    frames = sorted({0, 22, 40} | {int(x) for x in np.linspace(0, end, 9)})
    pattern = str(C.dir / "frames_3d" / "mp_%04d.png")
    contact_sheet(pattern, C.dir / "contact.png", [f for f in frames if f <= end][:12])
    # clean in/out: first frame of the 3D render vs. the slide as shown in the presentation
    sl = Image.open(C.deck_file.parent / C.slide["clean"]).convert("RGB").resize(C.size, Image.LANCZOS)
    f0 = Image.open(C.dir / "frames_3d" / "mp_0000.png").convert("RGB")
    fl = Image.open(C.dir / "frames_3d" / f"mp_{end:04d}.png").convert("RGB")
    d0 = np.abs(np.asarray(f0, np.int16) - np.asarray(sl, np.int16)).mean()
    dl = np.abs(np.asarray(fl, np.int16) - np.asarray(f0, np.int16)).mean()
    check = {"first_vs_slide": round(float(d0), 3), "last_vs_first": round(float(dl), 3), "frames": end + 1,
             "size": list(C.size), "seconds": round((end + 1) / C.fps, 2)}
    (C.dir / "check.json").write_text(json.dumps(check, indent=1), encoding="utf-8")
    print(f"-> {out}  ({check})")


STEPS = ["plan", "synfig", "light", "tex", "3d", "final", "sound"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("--only", choices=STEPS)
    ap.add_argument("--from", dest="start", choices=STEPS, default="plan")
    ap.add_argument("--jobs", type=int, default=max(2, (os.cpu_count() or 8) // 2))
    a = ap.parse_args()
    C = Clip(a.clip)
    steps = STEPS
    todo = [a.only] if a.only else steps[steps.index(a.start):]
    t0 = time.time()
    for s in todo:
        if s == "plan":
            plan(C)
        elif s == "synfig":
            synfig(C, a.jobs)
        elif s == "light":
            lights(C)
        elif s == "tex":
            textures(C)
        elif s == "3d":
            three(C)
        elif s == "final":
            final(C)
        elif s == "sound":
            if C.p.get("sound", True):
                import sound
                T = Times(C)              # event-anchored cues need the figures' events of the plan step
                T.events = {n: e for n, e in json.loads((C.dir / "plan.json").read_text(encoding="utf-8"))["events"]
                            .items() if not n.startswith("_")}
                sound.mux(C.dir / f"{C.dir.name}.mp4", sound.make(C.dir, C.p, T))
    print(f"  done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    sys.exit(main())
