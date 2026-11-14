# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0", "svgelements==1.9.6"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Build (and render) one section of the song as a Synfig scene: a set plus figures that sing, listen, dance and act.

Reads project.json (section, figures, gestures, screen events, actions, lights ...), analysis/song_sheet.json (beats,
words, lines) and analysis/assignment.json (which mouth each figure has when). Everything runs on the song timeline.

Behaviour per beat and figure (first match wins):
  action    an "actions" span runs (typing on a keyboard / air guitar) -> own arms IN FRONT of the body, rig arm off
  gesture   a word from "gestures" is sung now -> scare / cheer / point / scratch / nod / sad
  freeze    the song is quiet (9 dB under its average) -> everybody holds still
  dance     chorus (markers chorus/refrain/hook/drop, or repeated lyric lines) or "dance": "always"; the style per
            figure (arms / bounce / step / twist) comes from the creative seed unless "dance_style" fixes it
  sing      own mouth open -> open gesture, nod on the one
  listen    somebody else sings -> look at them, sway
  idle      otherwise: light sway
Every mode leans the whole body a little (dance 5°, sing 3°, listen 2° toward the singer, idle 1.5°); parts hanging
from the head (haare_hinten, hair, ponytail, antenna ...) turn with the head and swing behind it on a spring.
Figures with "entrance": "flicker" appear like a hologram the first time they sing.
The Computer ("kind": "screen") is a face inside the set's screen rectangle (eyes, cheeks, lip sync); "screen" events
in project.json replace the face for a moment with big text on the screen (a terminal line, a price, a warning);
"screen_badges" keep a label in the corner, "screen_meter" draws a usage bar that fills / turns red on words.

Scene features (project.json keys, documented in SKILL.md; defaults vary with the creative seed):
  "actions"      typing (keyboard prop, alternating key strikes on the beats, keys light up, clicks for sounds.py) and
                 guitar (air guitar, strum arm swings around the elbow on every beat or half beat)
  section "light"  spotlight (dark stage, cones; a figure appears only in its own light while it sings), disco
                 (coloured cones alternating on the beat + seeded confetti), night (room dark from a time/word/silence,
                 the screen keeps glowing, light again on a word)
  "silhouettes"  a dark figure between two set layers (inside the room window) or as a big shadow, on words
  section "inset"  round narrator inset in a corner (lip sync), hidden while that figure is on screen, when another
                 figure sings or after a pause longer than "hold" (2 s)
  section "kind": "panels"   comic page; hard cuts on every lyric line between panels (images or figures)
  section "shot": "screen"   close-up of the Computer's screen (room behind darkened, slow push-in)
  section "camera_move": true   marks camera moves for film-finish fps48.py (panels count as camera moves);
                 "shots": [] / [song s] = the known hard cuts (fps48 then skips its pixel-difference cut detection)
  section "kind": "external" + "inset"   frames from another renderer (multiplane, comic flight): only the inset is
                 rendered (transparent, scenes/<section>_inset/) and laid over scenes/<section>/ by captions.apply
  section "panel_aspect": "16:9"   panels shaped like the screen, the camera covers them (no neighbours visible)
  section "pulse"  heartbeat camera {"every": 0.85, "at": "silence" | "from" | "word", "to" | "until_word", "amount", "push"}
  section "show"   {"lia": {"line": .. | "line_index" | "word" | "from", "while": "singing" | "always"}} figure appears
                 only from then on (flicker), optionally only while it sings
  "screen" events  "tint": "#6b1a1a" (+ "tint_until": word) colours the whole screen; "sections"/"not_sections"
                 "window": "Context Window" pops an app window out over the screen instead of text on it
  "steam"        puffs rise from a figure's head from a word's line until a word (brain melting, overheating)

Rig convention of the SVG figures (see assets/figures/tim.svg): groups arm_l, arm_r, kopf (head), auge_l/r (eyes),
pupille_l/r (pupils), brauen (brows); pivots pivot_<part>; pivot_mund marks the mouth (drawn by lip sync); feet at
SVG point (200, 590). The German part ids are the convention of the bundled figures - keep them for new figures.

Usage: uv run scene.py <section> [--project .] [--render] [--jobs 8]
Output: scenes/<section>.sif (editable in Synfig Studio), with --render scenes/<section>/f.0000.png ...,
        analysis/actions_<section>.json (gesture times, key clicks for sounds.py)
"""
import argparse
import json
import re
import subprocess
import sys

import numpy as np

import _studio  # noqa: E402
_studio.use('song-analysis', 'toon-2d', 'characters')
import config
import creative  # noqa: E402
from media import decode
from song_project import Project, allowed, word_matches
from lipsync import mouth_layers
from motion import squash_keys, approx, spring_follow
from sif import V, R, anim, comp_vec, group, circle, region, hexc, canvas, image, with_blend, clipped, outline, ONTO
from svg2sif import normalize, load_svg, emit
from sets import load_set as _load_set, set_layers
from computer import computer, screen_texts, screen_badges, meter_keys, screen_meter
import scene_fx as fx

INK = hexc("#2b1d14")
TL, BR = (-6.9, 4.25), (6.9, -3.51)
VIEW = "-6.9 4.25 6.9 -3.51"            # 16:9 in Synfig units; the pixel size is project.json "size" (P.size)
CHORUS = re.compile(r"chorus|refrain|hook|drop", re.I)
GESTURES = ("scare", "cheer", "point", "scratch", "nod", "sad")
ACTIONS = ("typing", "guitar")
DANCE_STYLES = ("arms", "bounce", "step", "twist")
SWAY = {"dance": 5.0, "sing": 3.0, "listen": 2.0, "idle": 1.5, "typing": 1.0, "guitar": 3.0}  # body lean per mode
FOLLOW = ("haare_hinten", "haare", "hair", "zopf", "ponytail", "antenne", "antenna")  # parts that swing behind the head
SCREEN_SHOT = (-4.7, 3.35, 4.7, -2.45)                 # screen rectangle of a "shot": "screen" close-up
KEY_SOUNDS = ("fit/key/medium", "fit/key/thock", "fit/key/lubed")
PALETTES = {"neon": ["#ff4fa3", "#3fd0ff", "#ffd23f", "#8a6bff", "#6bff9a"],
            "sunset": ["#ff7a59", "#ffc145", "#ff4f81", "#b45cff", "#ffe8a3"],
            "ice": ["#7fe3ff", "#4f7bff", "#c7f9ff", "#9b8cff", "#ffffff"],
            "carnival": ["#ff3b3b", "#ffd23f", "#2fd17c", "#3f8cff", "#ff7ad9"]}
SPOT_COLOURS = ("#fff1c9", "#ffe0b0", "#e6f0ff")
GUITAR_COLOURS = ("#c0262d", "#2f6fb5", "#e0a030", "#3a3a3a", "#7b3fa0")
PANEL_BG = ["#5fb3a3", "#8a7ad6", "#e0703e", "#4f86c2", "#d96b6b", "#e09f3e", "#6bbf6b", "#c46bd6", "#3fa7c9", "#f0b84a"]
CORNERS = {"br": (5.25, -2.05), "bl": (-5.25, -2.05), "tr": (5.25, 2.8), "tl": (-5.25, 2.8)}


def box(desc, x0, y0, x1, y1, fill, amount=None):
    return region(desc, fill, [(x0, y0, 0, 0), (x1, y0, 0, 0), (x1, y1, 0, 0), (x0, y1, 0, 0)], amount=amount)


def load_set(P, name):
    """A set from the project (<project>/sets/<name>), bundled with toon-2d, or a plain colour ("color:#203040")."""
    if name.startswith("color:"):
        return {"back": [], "front": [], "color": name[6:], "scale": 0.68, "floor": -2.9, "places": {},
                "screen": [-2.4, 3.3, 2.4, 0.2], "view": VIEW}
    own = P.dir / "sets" / name
    return _load_set(str(own) if (own / "set.json").exists() else name)


def as_list(spec):
    if not spec:
        return []
    return [spec] if isinstance(spec, (str, dict)) else list(spec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("section")
    ap.add_argument("--project", default=".")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    P = Project(a.project)
    P.check("animated-music-video")                 # project.json validated before any long step
    fps = P.fps
    A = P.section(a.section)
    S, E = float(A["from"]), float(A["to"])
    N = round((E - S) * fps)
    F = lambda t: round((t - S) * fps)
    sheet = P.sheet()
    beats = [b for b in sheet["beats"] if S - 0.3 <= b["t"] < E + 0.3]
    lines, words = sheet["lines"], sheet["words"]
    ASG = P.assignment()["figures"]
    figs_cfg = P["figures"]
    kind = A.get("kind", "scene")
    shot = A.get("shot")
    default_names = [k for k in figs_cfg if figs_cfg[k].get("kind") == "screen"] if shot == "screen" else list(figs_cfg)
    names = [k for k in A.get("figures", default_names) if k in figs_cfg]
    SET = load_set(P, A.get("set", "stage"))
    lights = {}
    for sp in as_list(A.get("light")):
        sp = {"kind": sp} if isinstance(sp, str) else dict(sp)
        lights[sp.get("kind")] = sp
    K, FLOOR = float(A.get("scale", SET["scale"])), float(A.get("floor", SET["floor"]))
    if "spotlight" in lights and "scale" not in A:
        K *= 1.25                                         # spotlight: closer on the lit figures
    SCREEN = tuple(A.get("screen") or (SCREEN_SHOT if shot == "screen" else SET["screen"]))

    # ---------- who sings when (assignment.json) ----------
    end = max(sheet["duration"], E) + 1
    NS = int(end * fps) + 2

    def active(cues, pad=0.3):
        on = np.zeros(NS, bool)
        for (t, s), nxt in zip(cues, cues[1:] + [[end, "X"]]):
            if s != "X":
                on[max(int((t - pad) * fps), 0): min(int((nxt[0] + pad) * fps) + 1, NS)] = True
        return on

    ACT = {k: active(ASG.get(k, [])) for k in figs_cfg}
    act = lambda k, t: bool(ACT[k][min(max(int(t * fps), 0), NS - 1)])

    def cues_in_window(k):
        c = ASG.get(k, [])
        before = [s for t, s in c if t <= S]
        return [(0.0, before[-1] if before else "X")] + [(t - S, s) for t, s in c if S < t < E + 0.5]

    # ---------- quiet passages, choruses ----------
    y8 = decode(P.song, 8000)
    ref = 20 * np.log10(np.sqrt(np.mean(y8 ** 2)) + 1e-9)

    def quiet(t):
        x = y8[int(t * 8000): int((t + 0.5) * 8000)]
        return (20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9) - ref if len(x) else -60) < -9.0

    markers = P.markers()
    chorus = []
    if markers:
        for i, m in enumerate(markers):
            if CHORUS.search(m["marker"]) and m["line"] < len(lines):
                nxt = markers[i + 1]["line"] if i + 1 < len(markers) else len(lines)
                chorus.append((lines[m["line"]]["t"] - 0.3, lines[nxt]["t"] - 0.1 if nxt < len(lines) else end))
    else:                                                 # no markers: repeated lyric lines = chorus
        from collections import Counter
        count = Counter(l["text"].strip().lower() for l in lines)
        chorus = [(l["t"] - 0.3, l["end"] + 0.5) for l in lines if count[l["text"].strip().lower()] >= 2]
    dance = A.get("dance", "chorus")
    in_dance = lambda t: dance == "always" or (dance == "chorus" and any(c0 <= t < c1 for c0, c1 in chorus))

    # ---------- times from words, lines, markers, silence ----------
    def word_time(prefix, after=None, before=None):
        lo, hi = (S - 0.05) if after is None else after, E if before is None else before
        return next((w["t"] for w in words if word_matches(w["word"], prefix) and lo <= w["t"] < hi), None)

    def line_span(l):
        nxt = next((x["t"] for x in lines if x["t"] > l["t"] + 0.05), None)
        return l["t"], (nxt - 0.05) if nxt is not None and nxt - l["t"] < 8 else l["end"] + 0.3

    def marker_time(text):
        for m in markers:
            if text.lower() in m["marker"].lower() and m["line"] < len(lines) and S - 0.5 <= lines[m["line"]]["t"] < E:
                return lines[m["line"]]["t"] - 0.2
        return None

    def level(t0, t1):
        x = y8[max(int(t0 * 8000), 0): max(int(t1 * 8000), 0)]
        return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9) - ref if len(x) else -60.0

    def abrupt_stop():
        """First moment (from 0.5 s before the section) where the next second is >= 8 dB under the second before and
        quiet (9 dB under the song average) - an abrupt musical stop; else the first quiet beat. Needs the music
        before the stop: in an excerpt project that starts at the stop, give "from" instead."""
        for t in np.arange(max(S - 0.5, 1.0), E, 0.05):
            after = level(t + 0.1, t + 1.0)
            if after < -9.0 and after < level(t - 1.0, t) - 8.0:
                return float(max(t, S))
        return next((b["t"] for b in beats if b["t"] >= S and quiet(b["t"])), None)

    def span_of(spec):
        """(t0, t1) of a light/feature inside the section: from / word / marker / "silence" ... to / until_word / to_marker."""
        t0 = None
        if spec.get("from") is not None:
            t0 = float(spec["from"])
        elif spec.get("word"):
            t0 = word_time(spec["word"])
        elif spec.get("marker"):
            t0 = marker_time(spec["marker"])
        elif spec.get("at") == "silence":
            t0 = abrupt_stop()
        else:
            t0 = S
        if t0 is None:
            return None
        t1 = E
        if spec.get("to") is not None:
            t1 = float(spec["to"])
        elif spec.get("until_word"):
            t1 = word_time(spec["until_word"], after=t0) or E
        elif spec.get("to_marker"):
            t1 = marker_time(spec["to_marker"]) or E
        return max(t0, S), min(t1, E)

    # ---------- gestures on words ----------
    gest = []                                             # (t0, t1, figure, gesture)
    for g in P.get("gestures", []):
        if g.get("figure") not in names or g.get("gesture") not in GESTURES:
            continue
        for w in words:
            if word_matches(w["word"], g["word"]) and S <= w["t"] < E:
                gest.append((w["t"] - 0.1, w["t"] + float(g.get("duration", 1.0)), g["figure"], g["gesture"]))
    gesture_at = lambda k, t: next((x[3] for x in gest if x[2] == k and x[0] <= t < x[1]), None)

    svg_figs = [k for k in names if figs_cfg[k].get("svg")]
    sung_beats = {k: sum(1 for b in beats if S <= b["t"] < E and act(k, b["t"])) for k in names}
    spot = lights.get("spotlight")
    spot_span = span_of(spot) if spot else None
    spot_lead = None
    if spot:                                              # the figure singing most stays lit; the others appear in their light
        spot_lead = spot.get("lead") or (max(svg_figs, key=lambda k: sung_beats[k]) if svg_figs else None)
    places = dict(SET.get("places", {}))
    if spot and svg_figs and not A.get("places"):
        places = {spot_lead: -0.5}
        others = [k for k in svg_figs if k != spot_lead]
        for i, k in enumerate(others):
            places[k] = 3.1 - 2.2 * i if creative.rng(P, f"spot_side:{a.section}").random() < 0.5 else -3.6 + 2.2 * i
        if places.get(spot_lead) is not None and any(places[k] < 0 for k in others):
            places[spot_lead] = 0.8
    places.update(A.get("places", {}))
    for i, k in enumerate(svg_figs):                      # figures without a place: spread evenly
        places.setdefault(k, -4.0 + 8.0 * (i + 0.5) / max(len(svg_figs), 1))

    def keys(k):
        seen = {}
        for it in k:
            if 0 <= it[0] <= N:
                seen[it[0]] = it
        out = [seen[f] for f in sorted(seen)]
        return out or [(0, k[0][1] if k else 0)]

    # ---------- actions in front of the body: typing / air guitar ----------
    act_spans = {k: [] for k in names}                    # figure -> [(t0, t1, action, speed)]
    for spec in P.get("actions", []) + A.get("actions", []):
        k, what = spec.get("figure"), spec.get("action")
        if k not in svg_figs or what not in ACTIONS or (spec.get("sections") and a.section not in spec["sections"]):
            continue
        spans = []
        if spec.get("from") is not None or spec.get("to") is not None:
            spans = [(float(spec.get("from", S)), float(spec.get("to", E)))]
        elif spec.get("line"):
            spans = [line_span(l) for l in lines if l["text"].lower().startswith(spec["line"].lower())]
        elif spec.get("word"):
            spans = [line_span(l) for l in lines if any(word_matches(w["word"], spec["word"]) and w.get("line") == i
                                                        for w in words) for i in [lines.index(l)]]
        elif spec.get("when") in ("listening", "singing", "always"):
            run = None
            for b in beats:
                others = any(act(o, b["t"]) for o in names if o != k)
                ok = {"always": True, "singing": act(k, b["t"]), "listening": others and not act(k, b["t"])}[spec["when"]]
                if spec["when"] != "always" and not spec.get("in_chorus") and in_dance(b["t"]):
                    ok = False                            # dancing wins in a chorus unless "in_chorus": true
                if ok and run is None:
                    run = b["t"]
                elif not ok and run is not None:
                    spans.append((run, b["t"]))
                    run = None
            if run is not None:
                spans.append((run, E))
            for g0, g1, gk, _ in gest:                    # a gesture on a word interrupts a background action
                if gk == k:
                    spans = [p_ for s_ in spans for p_ in ((s_[0], min(s_[1], g0)), (max(s_[0], g1), s_[1])) if p_[1] > p_[0]]
            spans = [s for s in spans if s[1] - s[0] >= float(spec.get("min", 1.0))]
        speed = spec.get("speed") or ("slow" if spec.get("when") else "fast")
        for t0, t1 in spans:
            t0, t1 = max(t0, S), min(t1, E)
            if t1 - t0 > 0.2 and not any(x[0] < t1 and t0 < x[1] for x in act_spans[k]):
                act_spans[k].append((t0, t1, what, speed))
    action_log = []                                       # entries for analysis/actions_<section>.json

    def strike_frames(k, t0, t1, speed):
        """Alternating key strikes on the beat grid: 3-4 per beat (fast) or 2-3 (slow), seeded per figure."""
        per = creative.pick(P, f"typing:{k}:{speed}", (3, 4) if speed == "fast" else (2, 3))
        grid = [b["t"] for b in beats if t0 - 0.6 <= b["t"] <= t1 + 0.6] or list(np.arange(t0, t1 + 0.5, 0.5))
        out, side = [], -1
        for b0, b1 in zip(grid, grid[1:]):
            for j in range(per):
                t = b0 + (b1 - b0) * j / per
                if t0 <= t < t1:
                    out.append((F(t), side))
                    side = -side
        return out

    styles_used = {}
    light_pal = PALETTES[lights["disco"].get("palette") if lights.get("disco", {}).get("palette") in PALETTES
                         else creative.pick(P, f"disco:{a.section}", sorted(PALETTES))] if "disco" in lights else None

    # ---------- one SVG figure ----------
    def figure(k, nr, x=None, scale=None, floor=None, actions=True, front_out=None, back_out=None):
        cfg = figs_cfg[k]
        src = P.path(cfg["svg"])
        plain = normalize(src, out_dir=P.cache)
        root, PIV = load_svg(plain, scale=1 / 72, origin=(200, 590))
        x0 = places[k] if x is None else x
        Kf = K if scale is None else scale
        FL = FLOOR if floor is None else floor
        style = (A.get("dance_style", {}).get(k) if isinstance(A.get("dance_style"), dict) else A.get("dance_style")) \
            or cfg.get("dance_style") or creative.pick(P, f"dance:{k}:{a.section}", DANCE_STYLES)
        styles_used[k] = style
        spans = act_spans.get(k, []) if actions else []
        arm_l, arm_r, head, look, brow, sq, by, step = [], [], [], [], [], [], [], [(0, 0.0)]
        sway = [(0, 0.0)]
        for i, bt in enumerate(beats):
            t, f = bt["t"], F(bt["t"])
            up, down = i % 2 == 0, bt["downbeat"]
            half = f + round((beats[i + 1]["t"] - t) * fps / 2) if i + 1 < len(beats) else f + 5
            others = [o for o in names if o != k and act(o, t)]
            toward = (np.sign(places.get(others[0], 0.0) - x0) if others and others[0] in places else
                      (1.0 if (others and figs_cfg[others[0]].get("kind") == "screen" and x0 < 0) else 0.0))
            ac = next((s for s in spans if s[0] <= t < s[1]), None)
            g = gesture_at(k, t)
            mode = (ac[2] if ac else None) or g or ("freeze" if quiet(t) else "dance" if in_dance(t) else
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
        blink = [(0, (1, 1))]
        for t in np.arange(S + 1.1 + 0.7 * nr, E, 3.7 + 0.4 * nr):
            f = F(t)
            blink += [(f - 1, (1, 1)), (f + 1, (1.05, 0.1), "linear"), (f + 3, (1, 1))]
        cues = cues_in_window(k)
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

        wrap = {
            "arm_l": lambda kids, p: pivot("arm_l", kids, angle=anim("angle", keys(arm_l)),
                                           **({"amount": anim("real", keys(amt_l))} if amt_l else {})),
            "arm_r": lambda kids, p: pivot("arm_r", kids, angle=anim("angle", keys(arm_r)),
                                           **({"amount": anim("real", keys(amt_r))} if amt_r else {})),
            "kopf": lambda kids, p: pivot("kopf", kids + mouth_layers(cues, fps, center=PIV.get("mund", (0, 6)), size=msize,
                                                                      ink=INK, offset_frames=-1), angle=anim("angle", keys(head))),
            "auge_l": lambda kids, p: pivot("auge_l", kids, scale=anim("vector", blink)),
            "auge_r": lambda kids, p: pivot("auge_r", kids, scale=anim("vector", blink)),
            "pupille_l": lambda kids, p: group("pupille_l", kids, offset=anim("vector", keys(look))),
            "pupille_r": lambda kids, p: group("pupille_r", kids, offset=anim("vector", keys(look))),
            "brauen": lambda kids, p: group("brauen", kids, offset=comp_vec(R(0), anim("real", keys(brow)))),
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
        if cfg.get("entrance") == "flicker" and first is not None and F(first + S) > 14:
            f0 = F(first + S) - 14
            amt = anim("real", [(0, 0.0, "constant")] + [(f0 + j, v, "constant") for j, v in
                                                        enumerate([0.6, 0, 0.8, 0.2, 1, 0.4, 1, 1])])
        if spot and k != spot_lead and spot_span and actions:  # spotlight: appears only in its own light while singing
            amt = anim("real", appear_keys(k))
        if actions and show_spec(k):                      # section "show": only from a line / word / time on
            amt = anim("real", show_keys(k))
        squash = anim("vector", squash_keys(keys(sq), 0.6))
        lean = anim("angle", keys(sway))
        inner = group(k, emit(root, wrap), origin=(0, 0), scale=squash, angle=lean)
        kids = [inner]
        puffs = steam_frames(k) if actions else []
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
            for b in beats:
                if act(k, b["t"]):
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
            geo = fx.arm_geometry(src, PIV)
            front = []
            if typ:
                desk = SET.get("desk") if x is None else None
                if desk:                                  # keyboard stands on the desk: hands come down to it
                    top_fig = (desk["top"] - FL) / k_fig
                    geo["hand_dy"] = max(-0.5, min(0.3, top_fig - fx.keyboard_box(geo)[3]))
                strikes = [s for t0, t1, _, sp_ in typ for s in strike_frames(k, t0, t1, sp_)]
                rng = np.random.default_rng(creative.rng(P, f"keys:{k}:{a.section}").randrange(1 << 30))
                kb_col = creative.pick(P, f"keyboard:{k}", (("#3a3f4a", "#5a6170"), ("#e8e4da", "#ffffff"), ("#2b2b33", "#44465a")))
                g2 = geo
                front.append(fx.keyboard(g2, strikes, N, rng, stand=not desk, body=kb_col[0], key=kb_col[1],
                                         amount=None if desk else anim("real", keys(typ_on))))
                front.append(group("Typing arms", fx.typing_arms(g2, strikes, N), origin=(0, 0), scale=squash, angle=lean,
                                   amount=anim("real", keys(typ_on))))
                for j, (f, side) in enumerate(strikes):
                    action_log.append({"t": round(S + f / fps, 3), "figure": k, "gesture": "typing",
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
                colour = figs_cfg[k].get("guitar") or creative.pick(P, f"guitar:{k}", GUITAR_COLOURS)
                front.append(group("Air guitar", fx.air_guitar(geo, frames_, N, body_col=colour), origin=(0, 0),
                                   scale=squash, angle=lean, amount=anim("real", keys(gtr_on))))
                action_log.extend({"t": round(S + f / fps, 3), "figure": k, "gesture": "guitar"} for f in frames_)
            front_out.append(group(f"Front {k}", front, offset=comp_vec(xa, ya), scale=V(k_fig, k_fig), amount=amt))
        return group(f"Figure {k}", kids, offset=comp_vec(xa, ya), scale=V(k_fig, k_fig), amount=amt)

    def show_spec(k):
        sp = (A.get("show") or {}).get(k)
        return {"line": sp} if isinstance(sp, str) else sp

    def show_keys(k):
        """section "show": {"lia": {"line": "Nur noch meeeehr" | "line_index": 77 | "word": "ultra" | "from": s,
        "while": "singing" | "always"}} - hidden before; then flickers in (hologram) and stays, or (singing) is visible
        only while it sings (+-0.5 s), like a figure in the spotlight."""
        sp = show_spec(k)
        t0 = None
        if sp.get("from") is not None:
            t0 = float(sp["from"])
        elif sp.get("line_index") is not None:
            t0 = next((l["t"] for l in lines if l.get("line") == int(sp["line_index"])), None)
        elif sp.get("line"):
            t0 = next((l["t"] for l in lines if S - 0.5 <= l["t"] < E and l["text"].lower().startswith(sp["line"].lower())), None)
        elif sp.get("word"):
            t0 = word_time(sp["word"])
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

    def appear_keys(k):
        """Spotlight: visible while singing (sampled every 6 frames, +-0.5 s), hologram flicker when it appears."""
        ks, on = [(0, 0.0, "constant")], False
        t0, t1 = spot_span
        for f in range(0, N + 1, 6):
            t = S + f / fps
            sing = (not (t0 <= t < t1)) or any(act(k, t + d / fps) for d in range(-12, 13, 6))
            if sing != on:
                ks += ([(f + j, v, "constant") for j, v in enumerate([0.6, 0, 0.8, 0.3, 1])] if sing else [(f, 0.0, "constant")])
                on = sing
        return ks

    # ---------- the Computer: a face in the screen, text screens on cue words ----------
    screen_ev = []                                        # (t0, t1, text, colour)
    tint_ev = []                                          # (t0, t1, colour): the whole screen tinted (e.g. red at "Quota")
    for ev in P.get("screen", []):
        if not allowed(ev, a.section):
            continue
        last = -99
        for w in words:
            if word_matches(w["word"], ev["word"]) and S <= w["t"] < E and w["t"] - last > 1.0:
                if ev.get("text") and not ev.get("window"):
                    screen_ev.append((w["t"] - 0.05, w["t"] + float(ev.get("duration", 1.6)), ev["text"],
                                      ev.get("color", "#7CFF9B")))
                if ev.get("tint"):
                    t1 = word_time(ev["tint_until"], after=w["t"] + 0.05, before=1e9) if ev.get("tint_until") else None
                    tint_ev.append((w["t"] - 0.05, t1 if t1 is not None else w["t"] + float(ev.get("tint_for", ev.get("duration", 1.6))),
                                    ev["tint"]))
                last = w["t"]

    def tint_layers():
        x0, y0, x1, y1 = SCREEN
        return [box("Screen tint", x0, y0, x1, y1, hexc(c), amount=anim("real", keys(span_keys((t0, t1)))))
                for t0, t1, c in tint_ev]

    def screen_face(k, rect=None):
        blinks = [F(t) for t in np.arange(S + 1.7, E, 5.3)]
        bounce = [F(b["t"]) for b in beats if (act(k, b["t"]) or in_dance(b["t"])) and not quiet(b["t"])]
        face_on = [(0, 1.0, "constant")]
        for t0, t1, _, _ in screen_ev:
            face_on += [(F(t0), 0.0, "constant"), (F(t1), 1.0, "constant")]
        return computer(tuple(rect or SCREEN), fps=fps, blink=blinks, bounce=bounce, mouth_cues=cues_in_window(k),
                        face_on=keys(face_on))

    def screen_texts_layers():
        return screen_texts(SCREEN, screen_ev, F, P.cache, tag=f"screen_{a.section}") if screen_ev else []

    def badge_layers():
        """project.json "screen_badges": [{"text": "FREE", "bg": "#3a7d44"}, {"text": "PRO", "on": "pro", "bg": "#2f6fb5"}]
        - a label in the screen corner that changes on a word and keeps its state across sections."""
        spec = P.get("screen_badges", [])
        if not spec or not any(figs_cfg[k].get("kind") == "screen" for k in names):
            return []
        times = []
        for i, b in enumerate(spec):
            t = 0.0 if not b.get("on") else next((w["t"] for w in words if word_matches(w["word"], b["on"])
                                                   and w["t"] >= (times[-1] if times else 0.0)), None)
            times.append(t if t is not None else 1e9)
        items = [(t0, times[i + 1] if i + 1 < len(times) else 1e9, b["text"], b.get("color", "#ffffff"), b.get("bg", "#3a7d44"))
                 for i, (t0, b) in enumerate(zip(times, spec)) if t0 < 1e9]
        return screen_badges(SCREEN, items, F, N, P.cache, tag=f"badge_{a.section}")

    def meter_layers():
        """project.json "screen_meter": {"fill_on": ["limit"], "empty_on": ["upgrade"], "start": 0.55, "creep": 0.0,
        "label": "TOKENS", "style": "bar"|"segments", "sections": [...]} - a usage bar on the Computer's screen; it fills
        and turns red (blinking) on a fill word and empties on an empty word; the state carries over between sections."""
        spec = P.get("screen_meter")
        if not spec or not any(figs_cfg[k].get("kind") == "screen" for k in names) or \
                (spec.get("sections") and a.section not in spec["sections"]):
            return []
        ev = []
        for kind_, key in (("fill", "fill_on"), ("empty", "empty_on")):
            for pre in as_list(spec.get(key)):
                last = -99
                for w in words:
                    if word_matches(w["word"], pre) and w["t"] - last > 1.5:
                        ev.append((w["t"], kind_))
                        last = w["t"]
        style = spec.get("style") or creative.pick(P, "meter_style", ("bar", "segments"))
        lv, rd, bl = meter_keys(ev, F, N, start=float(spec.get("start", 0.55)), creep=float(spec.get("creep", 0.0)),
                                t_start=S, fps=fps)
        return screen_meter(SCREEN, keys(lv), keys(rd), keys(bl), label=spec.get("label"), style=style, out_dir=P.cache,
                            tag=f"meter_{a.section}")

    # ---------- props: own images (painted, FLUX, Krita) placed on the set, optionally shown on a word ----------
    def props():
        """project.json "props": [{"image": "props/gpu.png", "x": -4.6, "height": 2.4, "y": null (= on the floor),
        "sections": ["chorus1"], "show_on": "gpu", "hide_on": "context", "front": false, "bounce": true}]"""
        from PIL import Image as PILImage
        back_l, front_l = [], []
        for i, pr in enumerate(P.get("props", [])):
            if pr.get("sections") and a.section not in pr["sections"]:
                continue
            path = P.path(pr["image"])
            w_px, h_px = PILImage.open(path).size
            h = float(pr.get("height", 2.0)) * K
            w = h * w_px / h_px
            x = float(pr.get("x", 0.0))
            y0 = FLOOR if pr.get("y") is None else float(pr["y"])
            amt = [(0, 1.0, "constant")]
            for key, val in (("show_on", 1.0), ("hide_on", 0.0)):
                if pr.get(key):
                    t = next((w_["t"] for w_ in words if word_matches(w_["word"], pr[key]) and S <= w_["t"] < E), None)
                    if t is not None:
                        if key == "show_on":
                            amt[0] = (0, 0.0, "constant")
                        amt.append((F(t), val, "constant"))
            img = image(f"Prop {i}", path.as_posix(), (x - w / 2, y0 + h), (x + w / 2, y0))
            bounce = [(0, (1.0, 1.0))]
            if pr.get("bounce"):
                for b in beats:
                    if in_dance(b["t"]):
                        f = F(b["t"])
                        bounce += [(f, (1.04, 0.95), "linear"), (f + 5, (1.0, 1.0))]
            layer = group(f"Prop {i}", [img], origin=(x, y0), offset=V(x, y0), scale=anim("vector", keys(bounce)),
                          amount=anim("real", keys(amt)))
            (front_l if pr.get("front") else back_l).append(layer)
        return back_l, front_l

    # ---------- steam from a figure's head ("Hirn wegschmilzt") and app windows popping over the screen ----------
    def steam_frames(k):
        """project.json "steam": [{"word": "hirn", "figure": "tim", "until": "(hirn", "from": "line" | "word",
        "every": 9, "color": "#ffffff", "sections": [...]}] - white puffs rise from the head of the figure, one every
        `every` frames, from the start of the line with the word (or the word itself) until the `until` word / line end.
        Returns [(start frame, x offset, colour)]; figure() draws them inside the figure so they follow its head."""
        out = []
        for i, sp in enumerate(P.get("steam", [])):
            if not allowed(sp, a.section) or sp.get("figure", k) != k:
                continue
            last = -99
            for w in words:
                if not (word_matches(w["word"], sp["word"]) and S <= w["t"] < E and w["t"] - last > 3.0):
                    continue
                last = w["t"]
                ln = lines[w["line"]] if sp.get("from", "line") == "line" and w.get("line") is not None and \
                    w["line"] < len(lines) else None
                t0 = ln["t"] if ln else w["t"]
                t1 = word_time(sp["until"], after=w["t"] + 0.05, before=w["t"] + 8) if sp.get("until") else None
                t1 = t1 or (line_span(ln)[1] if ln else w["t"] + 2.0)
                rng = creative.rng(P, f"steam:{k}:{i}:{round(w['t'], 2)}")
                for n, f0 in enumerate(range(F(t0) + 6, F(t1) + 6, int(sp.get("every", 9)))):
                    out.append((f0, (-1.0 + 1.0 * (n % 3)) + rng.uniform(-0.12, 0.12), sp.get("color", "#ffffff")))
        return out

    def window_layers():
        """project.json "screen" events with "window": "Context Window" (+ "rows": 5, "color": title bar colour,
        "min": 1.5) - instead of text ON the screen an app window pops out over the screen (scale 0 -> 1.12 -> 1) on
        the word and stays until the line ends (at least `min` s)."""
        from pathlib import Path as _P
        from PIL import Image as PILImage, ImageDraw as PILDraw, ImageFont as PILFont
        x0, y0, x1, y1 = SCREEN
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ww, wh = (x1 - x0) * 1.12, (y0 - y1) * 1.05
        out = []
        for i, ev in enumerate(P.get("screen", [])):
            if not ev.get("window") or not allowed(ev, a.section):
                continue
            png = P.cache / f"window_{a.section}_{i}.png"
            W_, H_ = 640, int(640 * wh / ww)
            im = PILImage.new("RGBA", (W_, H_), (0, 0, 0, 0))
            d = PILDraw.Draw(im)
            d.rounded_rectangle((0, 0, W_ - 1, H_ - 1), 14, fill="#f3f6fb", outline="#2b1d14", width=5)
            tb = int(H_ * 0.15)
            d.rounded_rectangle((0, 0, W_ - 1, tb), 14, fill=ev.get("color", "#7a8ba8"), outline="#2b1d14", width=5)
            fnt = None
            for f_ in ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
                       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
                if _P(f_).exists():
                    fnt = PILFont.truetype(f_, int(tb * 0.62))
                    break
            d.text((24, tb * 0.17), str(ev["window"]), font=fnt or PILFont.load_default(), fill="#ffffff")
            for j, x_ in enumerate((W_ - 30, W_ - 62, W_ - 94)):
                d.ellipse((x_ - 11, tb / 2 - 11, x_ + 11, tb / 2 + 11), fill=("#ff6b6b", "#ffd23f", "#6bd36b")[j])
            rows = int(ev.get("rows", 5))
            for j in range(rows):
                yy = tb + (H_ - tb) * (j + 0.7) / (rows + 0.4)
                d.rounded_rectangle((36, yy, 36 + (W_ - 72) * (0.92 if j % 2 == 0 else 0.68), yy + (H_ - tb) * 0.07), 6,
                                    fill="#b8c4d8")
            im.save(png)
            ks = [(0, (0, 0))]
            last = -99
            for w in words:
                if word_matches(w["word"], ev["word"]) and S <= w["t"] < E and w["t"] - last > 1.0:
                    last = w["t"]
                    ln = lines[w["line"]] if w.get("line") is not None and w["line"] < len(lines) else None
                    t1 = max(ln["end"] if ln else w["t"] + 1.6, w["t"] + float(ev.get("min", 1.5)))
                    fc = F(w["t"])
                    ks += [(fc - 1, (0, 0), "linear"), (fc + 3, (1.12, 1.12)), (fc + 6, (0.97, 0.97)), (fc + 9, (1, 1)),
                           (F(t1) - 3, (1, 1), "halt"), (F(t1) + 1, (0, 0), "linear")]
            if len(ks) > 1:
                img = image(f"Window {i}", png.as_posix(), (cx - ww / 2, cy + wh / 2), (cx + ww / 2, cy - wh / 2))
                out.append(group(f"Window {i}", [img], origin=(cx, cy), offset=V(cx, cy), scale=anim("vector", keys(ks))))
        return out

    # ---------- silhouettes between set layers / as a shadow in the spotlight ----------
    def silhouettes(n_back):
        """project.json "silhouettes": [{"word": "lederjacke" | "line": "In der letzten" | "from": s, "to": s,
        "image": null (built-in faceless figure) | "props/man.png", "layer": index into the set's back layers
        (default: the set's "window" layer, else on top of the back layers), "x", "y", "height", "motion": rise|slide|fade,
        "hold": 1.0 (s after the line), "sections": [...]}] -> {layer index: [groups]}."""
        out = {}
        win = SET.get("window") or {}
        for i, sp in enumerate(P.get("silhouettes", [])):
            if sp.get("sections") and a.section not in sp["sections"]:
                continue
            spans = []
            hold = float(sp.get("hold", 1.0))
            if sp.get("from") is not None:
                spans = [(float(sp["from"]), float(sp.get("to", sp["from"] + 3.0)))]
            else:
                for li, l in enumerate(lines):
                    hit = (sp.get("line") and l["text"].lower().startswith(sp["line"].lower())) or \
                          (sp.get("word") and any(w.get("line") == li and word_matches(w["word"], sp["word"]) for w in words))
                    if hit:
                        t0 = l["t"] if sp.get("line") else min(l["t"], word_time(sp["word"], after=l["t"] - 0.05) or l["t"])
                        spans.append((t0, l["end"] + hold))
            spans = [(max(t0, S), min(t1, E)) for t0, t1 in spans if t1 > S and t0 < E and min(t1, E) - max(t0, S) > 0.3]
            if not spans:
                continue
            shadow = not win and spot is not None and sp.get("layer") is None
            layer = sp.get("layer", win.get("layer", n_back) if not shadow else "shadow")
            scale = float(sp.get("height", 3.3 if shadow else 2.2)) / 2.2
            side = creative.rng(P, f"silhouette:{i}").choice((-1, 1))
            x = float(sp.get("x", win.get("x", 3.2 * side if shadow else 3.8 * side)))   # no window: peeks in at the back
            y = float(sp.get("y", win.get("y", 0.9 if shadow else 1.6)))
            motion = sp.get("motion") or creative.pick(P, f"silhouette_motion:{i}", ("rise", "slide", "fade"))
            amt, off = [(0, 0.0, "constant")], [(0, (0.0, -1.4 * scale if motion == "rise" else 0.0))]
            for t0, t1 in spans:
                f0, f1 = F(t0), F(t1)
                if motion == "rise":
                    amt += [(f0, 1.0, "constant"), (f1, 0.0, "constant")]
                    off += [(f0, (0.0, -1.4 * scale), "halt"), (f0 + 12, (0.0, 0.0), "halt"), (f1 - 10, (0.0, 0.0), "halt"),
                            (f1, (0.0, -1.4 * scale), "halt")]
                elif motion == "slide":
                    amt += [(f0, 1.0, "constant"), (f1, 0.0, "constant")]
                    off += [(f0, (-2.0 * scale, 0.0), "halt"), (f0 + 14, (0.0, 0.0), "halt"), (f1 - 12, (0.0, 0.0), "halt"),
                            (f1, (2.0 * scale, 0.0), "halt")]
                else:
                    amt += [(f0, 0.0, "linear"), (f0 + 8, 1.0, "linear"), (f1 - 8, 1.0, "linear"), (f1, 0.0, "linear")]
            alpha = float(sp.get("alpha", 0.75 if shadow else 1.0))
            if sp.get("image"):
                from PIL import Image as PILImage
                path = P.path(sp["image"])
                w_px, h_px = PILImage.open(path).size
                h = 2.2
                w = h * w_px / h_px
                body = [image(f"Silhouette {i}", path.as_posix(), (-w / 2, h / 2), (w / 2, -h / 2))]
            else:
                body = fx.silhouette(alpha=alpha)
            g = group(f"Silhouette {i}", [group("Silhouette move", body, offset=anim("vector", keys(off)))],
                      origin=(0, 0), offset=V(x, y), scale=V(scale, scale), amount=anim("real", keys(amt)))
            out.setdefault(layer, []).append(g)
        return out

    # ---------- lights ----------
    full = [(-12, 9, 0, 0), (12, 9, 0, 0), (12, -8, 0, 0), (-12, -8, 0, 0)]

    def span_keys(span, on=1.0, off=0.0):
        if not span:
            return [(0, off, "constant")]
        return [(0, off, "constant"), (F(span[0]), on, "constant"), (F(span[1]), off, "constant")]

    night = lights.get("night")
    night_k = None
    if night:
        sp_n = span_of(night)
        if sp_n:
            residual = float(night.get("residual", 0.25))
            f0 = F(sp_n[0])
            night_k = [(0, 0.0, "constant"), (max(f0, 0), 1.0, "constant")]
            if sp_n[1] < E and (night.get("until_word") or night.get("to") is not None):
                night_k += [(F(sp_n[1]), 1.0), (F(sp_n[1]) + 30, residual)]
    disco = lights.get("disco")
    disco_span = span_of(disco) if disco else None

    def night_region(alpha, desc):
        return region(desc, hexc(night.get("color", "#03040a"), alpha), full, amount=anim("real", keys(night_k)))

    def darken_onto(layers, alpha, desc):
        """Darken only what these layers draw (ONTO), not what lies under them."""
        if not night_k:
            return layers
        return [group(desc, layers + [with_blend(night_region(alpha, desc + " dark"), ONTO)])]

    # ---------- comic panels (section "kind": "panels") ----------
    def panels_scene():
        import comic_page as cp
        cut_lines = [l for l in lines if S - 0.05 <= l["t"] < E - 0.8]   # a line starting in the last 0.8 s belongs to the next section (no empty panel)
        cuts, cut_line = [S], [None]
        for l in cut_lines:                               # one panel per line; lines closer than 0.3 s share a panel
            if l["t"] > cuts[-1] + 0.3:
                cuts.append(l["t"])
                cut_line.append(l)
        if cut_lines and cut_lines[0]["t"] <= S + 0.3:
            cut_line[0] = cut_lines[0]
        line_specs = [x for x in A.get("panels", []) if x.get("line")]
        idx_specs = [x for x in A.get("panels", []) if not x.get("line")]
        n = len(cuts)
        cols = int(A.get("columns") or (creative.pick(P, f"panel_cols:{a.section}", (3, 3, 2)) if n > 4 else 2))
        rows_pp = 3
        per_page = cols * rows_pp
        pw_px = 370 if cols == 3 else 560
        ph_px = 300 if cols == 3 else 360
        aspect = A.get("panel_aspect")                    # e.g. "16:9": panels shaped like the screen, camera covers them
        if aspect:
            aspect = (lambda a_, b_: float(a_) / float(b_))(*str(aspect).split(":")) if ":" in str(aspect) else float(aspect)
            pw_px = 480 if cols == 3 else 640
            ph_px = round(pw_px / aspect)
        PW = 100 + cols * pw_px + (cols - 1) * 15
        n_rows = min(rows_pp, -(-n // cols))
        PH = 140 + n_rows * (ph_px + 30) + 40
        ppu = 100.0                                       # page pixels per unit
        pal = list(PANEL_BG)
        creative.rng(P, f"panel_bg:{a.section}").shuffle(pal)
        layers, cam_c, figs_in = [], [], []
        page_layers = []
        n_pages = -(-n // per_page)
        for pg in range(n_pages):
            px0 = pg * (PW / ppu + 2.0)                    # pages side by side on the desk
            rects = {}
            for j in range(per_page):
                i = pg * per_page + j
                if i >= n:
                    break
                c, r = j % cols, j // cols
                rects[f"p{i}"] = (50 + c * (pw_px + 15), 140 + r * (ph_px + 30), pw_px, ph_px)
            title = A.get("title") if pg == 0 else ""
            if title is None:
                title = (cut_lines[0]["text"] if cut_lines else P.get("name", "")).strip()[:28]
            page_png = P.cache / f"page_{a.section}_{pg}.png"
            cp.page((PW, PH), rects, title=title or "", footer_right=f"{pg + 1}/{n_pages}" if n_pages > 1 else "",
                    seed=creative.seed(P) + pg).save(page_png)
            to_u = lambda x, y, px0=px0: (px0 + (x - PW / 2) / ppu, (PH / 2 - y) / ppu)
            for key, (x, y, w, h) in rects.items():
                i = int(key[1:])
                (ux0, uy0), (ux1, uy1) = to_u(x, y), to_u(x + w, y + h)
                cx, cy, wu, hu = (ux0 + ux1) / 2, (uy0 + uy1) / 2, ux1 - ux0, uy0 - uy1
                t0 = cuts[i]
                t1 = cuts[i + 1] if i + 1 < n else E
                ln = (cut_line[i] or {}).get("text", "").lower()
                spec = next((x for x in line_specs if ln.startswith(x["line"].lower())), None)
                if spec is None:
                    spec = idx_specs[i] if i < len(idx_specs) else (idx_specs[i % len(idx_specs)] if idx_specs and A.get("cycle_panels") else {})
                content = panel_content(i, spec, t0, t1, wu, hu, pal[i % len(pal)])
                figs_in.append(content[1])
                mask = box("Panel mask", -wu / 2, hu / 2, wu / 2, -hu / 2, hexc("#000000"))
                layers.append(group(f"Panel {i}", [clipped(f"Panel {i} clip", mask, content[0])], origin=(0, 0), offset=V(cx, cy)))
                cam_c.append((cx, cy, hu))
            tl, br = to_u(0, 0), to_u(PW, PH)
            page_layers += [box("Page shadow", tl[0] + 0.12, tl[1] - 0.12, br[0] + 0.12, br[1] - 0.12, hexc("#000000", 0.45)),
                            image(f"Page {pg}", page_png.as_posix(), tl, br)]
        desk = [box("Desk", -60, 40, 60, -40, hexc(A.get("desk_color", "#4a3524")))]
        # camera: hard cut on every line start, slow push-in + small roll and drift inside each panel
        rr = creative.rng(P, f"panel_cam:{a.section}")
        roll = rr.uniform(0.6, 1.6)
        fill0, fill1 = rr.uniform(0.95, 1.05), rr.uniform(1.12, 1.22)   # panel height vs picture height
        off, sc, ang = [], [], []
        vh = TL[1] - BR[1]
        vw = BR[0] - TL[0]
        if aspect:                                        # cover the view: no page edge or neighbour panel in the picture
            fill0, fill1, roll = 1.08 + (fill0 - 0.95) * 0.5, 1.16 + (fill1 - 1.12) * 0.5, roll * 0.5
        for i, (cx, cy, hu) in enumerate(cam_c):
            f0 = F(cuts[i])
            f1 = (F(cuts[i + 1]) if i + 1 < n else N + 1) - 1
            fit = max(vh / hu, vw / (hu * aspect)) if aspect else vh / hu
            s0, s1 = fill0 * fit, fill1 * fit
            d = (0.1 if aspect else 0.15) * (1 if i % 2 else -1)
            rl = roll * (1 if i % 2 else -1)
            off += [(f0, (-cx - d, -cy), ("constant", "linear")), (max(f1, f0), (-cx + d, -cy), ("linear", "constant"))]
            sc += [(f0, (s0, s0), ("constant", "linear")), (max(f1, f0), (s1, s1), ("linear", "constant"))]
            ang += [(f0, rl, ("constant", "linear")), (max(f1, f0), rl * 0.4, ("linear", "constant"))]
        world = group("Comic page", desk + layers + page_layers, origin=(0, 0), offset=anim("vector", off))
        cam = group("Camera", [world], origin=(0, 0), offset=V(0, (TL[1] + BR[1]) / 2), scale=anim("vector", sc),
                    angle=anim("angle", ang))
        return cam, cuts, figs_in

    def panel_content(i, spec, t0, t1, wu, hu, bg):
        """Layers of one panel in panel coordinates (centre 0, 0) and the figures it shows.
        spec: {"layers": [png ...]} | {"image": png} | {"figures": [...], "shot": close|medium|wide, "bg": "#..."} | {}
        (= auto: whoever sings this line, in close-up)."""
        from PIL import Image as PILImage
        out, shown = [], []
        rp = creative.rng(P, f"panel:{a.section}:{i}")
        imgs = spec.get("layers") or ([spec["image"]] if spec.get("image") else [])
        if imgs:
            for j, src in enumerate(imgs):
                im = PILImage.open(P.path(src)).convert("RGBA")
                import comic_page as cp
                crop = cp.crop_aspect(im, wu / hu)
                p = P.cache / f"panel_{a.section}_{i}_{j}.png"
                crop.save(p)
                f0, f1 = F(t0), F(t1)
                z = 1.0 + 0.05 * (j + 1)                  # slow parallax push per layer
                out.append(group(f"Layer {j}", [image(f"Layer {j}", p.as_posix(), (-wu / 2, hu / 2), (wu / 2, -hu / 2))],
                                 origin=(0, 0), scale=anim("vector", [(f0, (1.0, 1.0), "linear"), (f1, (z, z), "linear")])))
            return out, shown
        col = spec.get("bg", bg)
        out.append(box("Panel bg", -wu, hu, wu, -hu, hexc(col)))
        out.append(circle("Panel glow", hexc("#fff6d8", 0.45), 0.55 * wu, (0, 0.1 * hu), feather=0.45 * wu))
        if rp.random() < 0.7:                             # speed lines
            nl = rp.randint(18, 30)
            for j in range(nl):
                ang_ = 2 * np.pi * j / nl + rp.uniform(-0.05, 0.05)
                r0, r1 = 0.35 * hu, 1.2 * wu
                out.append(outline("Speed line", hexc("#ffffff", 0.22), [(np.cos(ang_) * r0, np.sin(ang_) * r0, 0, 0),
                                                                         (np.cos(ang_) * r1, np.sin(ang_) * r1, 0, 0)], 0.03, loop=False))
        who = spec.get("figures")
        if who is None:
            ts = np.arange(t0, max(t1, t0 + 0.1), 0.1)
            cnt = {k: sum(act(k, t) for t in ts) for k in names}
            singers = [k for k in sorted(names, key=lambda k: -cnt[k]) if cnt[k] > 0]
            who = [k for k in singers if figs_cfg[k].get("svg")][:2] or [k for k in singers if figs_cfg[k].get("kind") == "screen"][:1] \
                or svg_figs[:1]
        scr = [k for k in who if figs_cfg[k].get("kind") == "screen"]
        svgs = [k for k in who if figs_cfg[k].get("svg")]
        if scr and not svgs:
            out += screen_face(scr[0], rect=(-0.44 * wu, 0.42 * hu, 0.44 * wu, -0.42 * hu))
            shown += scr
        elif svgs:
            shot_ = spec.get("shot") or rp.choice(("close", "medium") if len(svgs) == 1 else ("medium", "wide"))
            cy_, vh_ = {"close": (5.0, 4.0), "medium": (4.3, 5.8), "wide": (3.8, 8.6)}[shot_]
            xs = [0.0] if len(svgs) == 1 else [-1.6, 1.6]
            figs_ = [figure(k, j, x=xs[j], scale=1.0, floor=0.0, actions=False) for j, k in enumerate(svgs)]
            s = hu / vh_
            out.append(group("Panel figures", figs_, origin=(0, cy_), offset=V(0, 0), scale=V(s, s)))
            shown += svgs
        return out, shown

    # ---------- narrator inset ----------
    def inset_layer(hidden_at=None):
        spec = A.get("inset")
        if not spec:
            return []
        spec = {} if spec is True else (({"figures": [spec]}) if isinstance(spec, str) else dict(spec))
        drawn = set(names) if kind not in ("panels", "external") else set()
        figs = [k for k in (spec.get("figures") or [k for k in figs_cfg if k not in drawn]) if k in figs_cfg]
        narr = P.get("narrator")
        figs.sort(key=lambda k: 0 if k == narr else 1)
        if not figs:
            return []
        R_ = float(spec.get("radius", 1.25))
        corner = spec.get("corner") or creative.pick(P, f"inset_corner:{a.section}", ("br", "bl"))
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
        bob = [(0, 0.0)] + [(F(b["t"]), 4.0 if i % 2 else -4.0) for i, b in enumerate(beats)]
        contents = []
        for k in figs:
            amt = [(0, 0.0, "constant")] + [(f, 1.0 if who[f] == k else 0.0, "constant") for f in [first] + switch + hide]
            cfg = figs_cfg[k]
            if cfg.get("kind") == "screen":
                body = [circle("Screen", hexc("#1d3b5c"), R_, (0, 0))] + screen_face(k, rect=(-1.25 * R_, 1.0 * R_, 1.25 * R_, -1.0 * R_))
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

    # ---------- compose ----------
    out_dir = P.dir / "scenes"
    out_dir.mkdir(exist_ok=True)
    if kind == "external":                                # frames come from another renderer: only post passes here
        import captions
        top = inset_layer() if A.get("inset") else []
        if top:                                           # the inset as a transparent track -> scenes/<section>_inset/
            sif = out_dir / f"{a.section}_inset.sif"
            sif.write_text(canvas(top, w=P.size[0], h=P.size[1], end=N, name=f"{P['name']} - {a.section} inset", view=VIEW), encoding="utf-8")
            print(f"-> {sif.relative_to(P.dir)}: narrator inset over the external frames ({N} frames)")
            if a.render:
                ins = out_dir / f"{a.section}_inset"
                if ins.exists():
                    for p_ in ins.glob("*.png"):
                        p_.unlink()
                subprocess.run([sys.executable, str(_studio.skill_dir("toon-2d") / "scripts" / "synfig_parallel.py"), str(sif),
                                str(ins), "--jobs", str(a.jobs)], check=True)
        elif A.get("inset"):
            print("   inset: nobody of the inset figures sings in this section - no inset")
        if a.render and (A.get("caption") or top):
            captions.apply(P, a.section)
        elif not a.render:
            print("   external section: run with --render to lay the inset/caption over scenes/%s/" % a.section)
        return
    if kind == "panels":
        scene, cuts, figs_in = panels_scene()
        cut_frames = [F(t) for t in cuts]

        def hidden_at(f):
            i = max(j for j, cf in enumerate(cut_frames) if cf <= f) if f >= cut_frames[0] else 0
            return set(figs_in[i])
        top = inset_layer(hidden_at)
        info = f"panels {len(cuts)}, cuts at {[round(t, 2) for t in cuts]}"
    else:
        back = []
        if SET.get("color"):
            back.append(box("Background", -9, 6, 9, -5, hexc(SET["color"])))
        if SET.get("dir"):
            if shot == "screen":                          # close-up: the set behind, a bit bigger
                l, t_, r, b = SET.get("image_box", (-8, 4.5, 8, -4.5))
                cy0 = (t_ + b) / 2
                set_back, set_front = set_layers(str(SET["dir"]), box=(l * 1.2, cy0 + (t_ - cy0) * 1.2, r * 1.2, cy0 + (b - cy0) * 1.2))
                set_front = []
            else:
                set_back, set_front = set_layers(str(SET["dir"]))
        else:
            set_back, set_front = [], []
        sil = silhouettes(len(set_back))
        for idx in sorted([i for i in sil if isinstance(i, int)], reverse=True):
            set_back[min(idx, len(set_back)):min(idx, len(set_back))] = sil[idx]
        back += set_back
        dim = float(A.get("dim", 0.55 if shot == "screen" else 0.0))
        if dim:
            back.append(region("Dim", hexc("#05070d", dim), full))
        if SET.get("glow"):
            glow = [(0, 0.5)]
            for b in beats:
                f = F(b["t"])
                glow += [(f, 0.75 if in_dance(b["t"]) else 0.5, "linear"), (f + 6, 0.45)]
            x0, y0, x1, y1 = SCREEN
            back.append(circle("Screen glow", hexc(SET["glow"], 0.45), 0.9 * (x1 - x0), ((x0 + x1) / 2, (y0 + y1) / 2),
                               feather=0.7 * (x1 - x0), amount=anim("real", keys(glow))))
        if spot and spot_span:                            # dark stage (shadow silhouettes stand in the dark)
            back.append(region("Spotlight dark", hexc("#05040a", float(spot.get("dark", 0.72))), full,
                               amount=anim("real", span_keys(spot_span))))
        back += sil.get("shadow", [])
        if night_k:
            back.append(night_region(float(night.get("level", 0.7)), "Night (room)"))
            x0, y0, x1, y1 = SCREEN
            back.append(circle("Screen light", hexc(SET.get("glow", "#5fb3ff"), 0.3), 1.1 * (x1 - x0), ((x0 + x1) / 2, (y0 + y1) / 2),
                               feather=0.8 * (x1 - x0), amount=anim("real", keys(night_k))))
        monitor = [l for k in names if figs_cfg[k].get("kind") == "screen" for l in screen_face(k)]
        monitor = monitor[:2] + (tint_layers() if monitor else []) + meter_layers() + monitor[2:] + screen_texts_layers() + \
            badge_layers() + (window_layers() if monitor else [])   # tint and bar behind the face, windows on top
        if spot and spot_span and monitor:                # the screen is dimmed in the spotlight unless the Computer speaks
            scr = [k for k in names if figs_cfg[k].get("kind") == "screen"]
            mk = [(0, 0.4)] + [(f, 1.0 if any(act(k, S + f / fps) for k in scr) else 0.4) for f in range(0, N + 1, 4)]
            monitor = [group("Screen (dimmed)", monitor, amount=anim("real", keys(mk)))]
        fronts = []
        auras = []
        figures = [figure(k, i, front_out=fronts, back_out=auras) for i, k in enumerate(svg_figs)]
        props_back, props_front = props()
        figures = auras + props_back + figures + props_front
        lights_back, lights_front = [], []
        if spot and spot_span:
            col = spot.get("color") or creative.pick(P, f"spot_colour:{a.section}", SPOT_COLOURS)
            for k in svg_figs:
                c_ = col if k == spot_lead else (figs_cfg[k].get("aura") or "#c9a6ff")
                am = anim("real", span_keys(spot_span)) if k == spot_lead else anim("real", appear_keys(k))
                lights_back += fx.spot_cone(f"Spotlight {k}", places[k], TL[1] + 0.1, FLOOR - 0.05, c_, amount=am)
        if disco and disco_span:
            bf = [(F(b["t"]), disco_span[0] <= b["t"] < disco_span[1]) for b in beats]
            lights_back += fx.disco_cones(bf, light_pal, N)
            rng = np.random.default_rng(creative.rng(P, f"confetti:{a.section}").randrange(1 << 30))
            count = int(disco.get("confetti", rng.integers(50, 91)))
            lights_front += fx.confetti(rng, max(F(disco_span[0]), 0), min(F(disco_span[1]), N), light_pal, count, N)
        front = []
        if SET.get("desk") and shot != "screen":
            dk = SET["desk"]
            front += [box("Desk", -9, dk["top"], 9, -5, hexc(dk.get("color", "#6b4a33"))),
                      box("Desk edge", -9, dk["top"] + 0.12, 9, dk["top"] - 0.05, hexc("#8a6446"))]
        if SET.get("desk"):
            layers = back + lights_back + darken_onto(figures + front + fronts + set_front, 0.35, "Figures (night)") + \
                lights_front + monitor
        elif night_k:
            layers = back + monitor + lights_back + darken_onto(figures + fronts, 0.35, "Figures (night)") + lights_front + \
                darken_onto(set_front, 0.7, "Set front (night)")
        else:
            layers = back + monitor + lights_back + figures + fronts + lights_front + set_front
        push = float(A.get("push_in", 0.08 if shot == "screen" else 0.0))
        cam = [(0, (1.0, 1.0)), (N, (1.0 + push,) * 2, "linear")]
        if disco and disco_span:                          # disco: stronger camera pulse on the downbeats
            for b in beats:
                if b["downbeat"] and disco_span[0] <= b["t"] < disco_span[1]:
                    f = F(b["t"])
                    base = 1.0 + push * max(f, 0) / max(N, 1)
                    cam += [(f - 1, (base, base)), (f, (base * 1.07,) * 2, "linear"), (f + 6, (base, base))]
            cam = sorted({k_[0]: k_ for k_ in cam}.values())
        pulse = A.get("pulse")
        pspan = span_of(pulse) if pulse else None
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
        scene = group("Camera", layers, origin=(0, 0), offset=V(0, 0), scale=anim("vector", keys(cam) if len(cam) > 2 else cam))
        top = inset_layer()
        info = ""
    sif = out_dir / f"{a.section}.sif"
    sif.write_text(canvas([scene] + top, w=P.size[0], h=P.size[1], end=N, name=f"{P['name']} - {a.section}", view=SET.get("view", VIEW) if kind != "panels" else VIEW),
                   encoding="utf-8")
    (P.analysis / f"actions_{a.section}.json").write_text(
        json.dumps([{"t": round(t0 + 0.1, 3), "figure": k, "gesture": g} for t0, t1, k, g in gest] + action_log,
                   ensure_ascii=False), encoding="utf-8")
    sung = {k: sum(1 for b in beats if act(k, b["t"])) for k in names}
    extra = []
    for k, sp in act_spans.items():
        for t0, t1, what, speed in sp:
            extra.append(f"{k} {what} {t0:.1f}-{t1:.1f}")
    feats = [x for x in (f"actions [{', '.join(extra)}]" if extra else "", f"lights {sorted(lights)}" if lights else "",
                         "inset" if A.get("inset") else "", info) if x]
    print(f"-> {sif.relative_to(P.dir)}: {N} frames, set {A.get('set', 'stage') if kind != 'panels' else 'panels'}, beats sung per figure {sung}, "
          f"dance beats {sum(1 for b in beats if in_dance(b['t']))}, gestures {len(gest)}, screen events {len(screen_ev)}, dance styles {styles_used} (seed {creative.seed(P)})"
          + ("\n   " + "; ".join(feats) if feats else ""))
    if a.render:
        frames = out_dir / a.section
        import shutil
        shutil.rmtree(out_dir / f"{a.section}_raw", ignore_errors=True)      # frames without captions (captions.py)
        if frames.exists():
            for p in frames.glob("*.png"):
                p.unlink()
        subprocess.run([sys.executable, str(_studio.skill_dir("toon-2d") / "scripts" / "synfig_parallel.py"), str(sif), str(frames),
                        "--jobs", str(a.jobs)], check=True)
        print(f"-> {frames.relative_to(P.dir)}/f.%04d.png ({len(list(frames.glob('*.png')))} images)")
        if A.get("caption"):                              # comic caption box typing the sung line
            import captions
            captions.apply(P, a.section)


if __name__ == "__main__":
    main()
