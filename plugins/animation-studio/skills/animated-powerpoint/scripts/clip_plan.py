"""clip.py step "plan": timing and acting of every figure, then the per-frame stage values and the Synfig scenes.

Order of the passes (later ones use the events of earlier ones, time specs resolve against them):
  routines   start, take-off, pop, landing per step_out figure (routines.py style), one after the other
  gestures   gestures and name tags (may sit on words of the narration)
  reactions  landed figures with a fist / wave cheer while a later figure is stuck
  ending     group finale / return hop, the clip length, when tags hide
  keys       Synfig keys per figure: routine + idle + blinks + eyes following the others; mouths; watchers
  camera     automatic shots (or clip.json "camera"), shakes
  extras     paper bits, sparkles (look_up: glasses flash)
then clip_frames.py (per-frame values), clip_sif.py (one .sif per figure), clip_stage.py (stage.json, plan.json)."""
import json
import math

import numpy as np
from PIL import Image

import _studio
_studio.use("toon-2d")
import acting as A  # noqa: E402
import creative  # noqa: E402
import routines as RT  # noqa: E402
from clip_core import H_REF, Times, fig_geometry  # noqa: E402
from clip_frames import stage_frames  # noqa: E402
from clip_sif import write_sif  # noqa: E402
from clip_stage import plan_meta, stage_config  # noqa: E402


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


# ----------------------------------------------------------------- timing passes
def plan_routines(C, P, G, T, movers, multi):
    """Pass 1: the routines in order (start, take-off, pop, landing); landing place and camera side per figure.
    -> last landing frame."""
    spread = P.get("spread", 1.0 if not multi else 1.18)          # several figures: landing places further apart
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
    return max(G[f["name"]]["R"].land_f for f in movers)


def plan_gestures(G, T, movers):
    """Pass 2: gestures and name tags (may sit on words of the narration)."""
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


def plan_reactions(G, T, movers):
    """Landed figures with a fist / wave cheer while a later figure is stuck."""
    for i, f in enumerate(movers):
        R = G[f["name"]]["R"]
        if R.style != "stuck":
            continue
        for f2 in movers[:i]:
            if f2["gesture"] in ("fist", "wave") and f.get("cheer", True):
                at = T.events[f["name"]]["stuck"] - 6
                RT.merge(G[f2["name"]]["R"].keys, RT.gesture_keys(f2["gesture"], at))
                T.events[f2["name"]].setdefault("cheer", []).append(at)


def plan_ending(P, G, T, movers, order, last_land, multi):
    """End, group finale, return hop; when the tags hide. Sets P["end"].
    -> (G0 group start or None, end of the routines, R_ret return frame or None, end)."""
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
    if R_ret is not None and T.cfg:                  # never hop back while someone still talks (user test)
        speech_end = max(T({"line": lid, "edge": "end"}) for lid in T.cfg)
        if R_ret < speech_end + 8:
            print(f"  return hop moved from frame {R_ret} to {speech_end + 8}: the narration runs until frame "
                  f"{speech_end} (\"hold\" adds time after the routine, not after the speech)")
            R_ret = speech_end + 8
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
    return G0, end_routine, R_ret, end


# ----------------------------------------------------------------- Synfig keys
def dedup_keys(k):
    """One key per frame (the last one wins) in eyes, head and blink."""
    dedup = {}
    for ch in ("eyes", "head", "blink"):
        dedup = {}
        for x in k[ch]:
            dedup[x[0]] = x
        k[ch] = [dedup[fr] for fr in sorted(dedup)]


def mover_keys(P, G, T, movers, order, windows, G0, R_ret, end, multi):
    """Synfig keys per step_out figure: routine + idle + blinks + eyes following the others."""
    keys = {}
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
        dedup_keys(k)
        keys[n] = k
    return keys


def mouth_keys(C, G, T, figs, keys):
    """Figures that speak (narration "speaker" / figure "talk"): Rhubarb -> mouth stages."""
    for f in figs:
        n = f["name"]
        talk = [lid for lid, ln in T.cfg.items() if ln.get("speaker") == n] + list(f.get("talk", []))
        if talk and n in keys:
            import mouth
            mouth.ensure(G[n]["dir"])
            keys[n]["mouth"] = mouth.mouth_keys(G[n]["dir"], [(C.dir / T.cfg[lid]["audio"], T.line_at(lid),
                                                               T.cfg[lid].get("text")) for lid in talk],
                                                fps=C.fps, cache=C.dir / "narration")


def watcher_keys(P, G, figs, order, windows, R_ret, end, keys):
    """Watchers: alive, flat in the slide, eyes follow the acting figure."""
    for f in figs:
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


# ----------------------------------------------------------------- camera
def camera_keys(C, P, G, T, movers, order, G0, end_routine, R_ret, end):
    """Automatic shots per figure (in the slide, take-off, flight, landing, hold), group shot, return; or the
    clip.json "camera" shot list. -> (sorted camera keys, shake frames)."""
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
    return cam_keys, shakes


# ----------------------------------------------------------------- extras
def paper_bits(P, G, order):
    """Paper bits that fly off where a figure tears out of the slide (count per style: routines.BITS)."""
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
    return bits


def eye_rims(g):
    """Where a glint sits on each eye: the glasses rim / eye outline up-left of the pupil (crop px)."""
    im = np.asarray(Image.open(g["dir"] / "original.png").convert("RGBA")).astype(np.float32) / 255
    dark = (im[..., 3] > 0.5) & (im[..., :3].mean(-1) < 0.35)
    rims = []
    for ex, ey in g["parts_cfg"].get("eyes") or []:
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
    return rims


def sparkles(G, order):
    """Sparkles of the look_up gesture (glasses flash): figure, frame, offset from the feet (world)."""
    sparks = []
    for n in order:
        g = G[n]
        eyes = g["parts_cfg"].get("eyes") or []
        rims = eye_rims(g) if eyes and g["R"].keys.get("sparkle") else []
        for j, fr0 in enumerate(g["R"].keys.get("sparkle", [])):
            if rims:
                dx, dy = g["su"](*rims[j % len(rims)])
                sparks.append({"fig": n, "f": fr0, "d": [dx * g["su_world"], dy * g["su_world"]]})
    return sparks


def figure_events(G, T, order, R_ret, G0):
    """Events per figure for plan.json (sound cues, scenes): routine events + look, sparkle, return."""
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
    return events


# ----------------------------------------------------------------- the step
def plan(C):
    P = C.p
    figs = P["figures"]
    G = {f["name"]: fig_geometry(C, f["name"]) for f in figs}
    T = Times(C)
    movers = [f for f in figs if f.get("action", "step_out") == "step_out"]
    if not movers:
        raise SystemExit("no figure with action step_out")
    multi = len(movers) > 1
    last_land = plan_routines(C, P, G, T, movers, multi)
    plan_gestures(G, T, movers)
    order = [f["name"] for f in movers]
    plan_reactions(G, T, movers)
    G0, end_routine, R_ret, end = plan_ending(P, G, T, movers, order, last_land, multi)
    windows = {n: (G[n]["start"] + 10, G[n]["R"].land_f + 30) for n in order}
    keys = mover_keys(P, G, T, movers, order, windows, G0, R_ret, end, multi)
    mouth_keys(C, G, T, figs, keys)
    watcher_keys(P, G, figs, order, windows, R_ret, end, keys)
    cam_keys, shakes = camera_keys(C, P, G, T, movers, order, G0, end_routine, R_ret, end)
    names = [f["name"] for f in figs]
    bits = paper_bits(P, G, order)
    sparks = sparkles(G, order)
    states, frames = stage_frames(C, G, names, cam_keys, shakes, bits, sparks, R_ret, end)
    for n in names:                                                # Synfig scenes
        write_sif(C, G[n], keys[n], end, gesture_part=next((f.get("gesture_part") for f in figs if f["name"] == n), None))
    events = figure_events(G, T, order, R_ret, G0)
    stage = stage_config(C, P, G, figs, names, order, states, len(sparks), end, frames)
    (C.dir / "stage.json").write_text(json.dumps(stage), encoding="utf-8")
    meta = plan_meta(G, T, movers, names, order, states, events, end)
    (C.dir / "plan.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    C.save()
    print(f"  plan: {end + 1} frames, events {json.dumps(events)}")
    return meta
