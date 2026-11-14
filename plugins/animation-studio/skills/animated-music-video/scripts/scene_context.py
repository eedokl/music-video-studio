"""SceneContext of scene.py: everything one section's layer builders read, computed once per run.

  SceneContext.build(P, section)    project, section times, song sheet (beats / words / lines), who sings when
                                    (assignment.json), chorus spans, gestures, places, action spans, lights,
                                    screen events ... plus the timing helpers (F, act, word_time, span_of, keys ...)
Shared constants and small helpers of the scene modules (box, as_list, load_set) live here too. The layer builders
are module-level functions taking the context: scene_figures, scene_screen, scene_props, scene_lights, scene_panels,
scene_inset, scene_stage.
"""
import re
from dataclasses import dataclass, field

import numpy as np

import creative
from media import decode
from song_project import allowed, word_matches
from sif import region
from sets import load_set as _load_set

TL, BR = (-6.9, 4.25), (6.9, -3.51)
VIEW = "-6.9 4.25 6.9 -3.51"            # 16:9 in Synfig units; the pixel size is project.json "size" (P.size)
CHORUS = re.compile(r"chorus|refrain|hook|drop", re.I)
GESTURES = ("scare", "cheer", "point", "scratch", "nod", "sad")
ACTIONS = ("typing", "guitar")
SCREEN_SHOT = (-4.7, 3.35, 4.7, -2.45)                 # screen rectangle of a "shot": "screen" close-up
PALETTES = {"neon": ["#ff4fa3", "#3fd0ff", "#ffd23f", "#8a6bff", "#6bff9a"],
            "sunset": ["#ff7a59", "#ffc145", "#ff4f81", "#b45cff", "#ffe8a3"],
            "ice": ["#7fe3ff", "#4f7bff", "#c7f9ff", "#9b8cff", "#ffffff"],
            "carnival": ["#ff3b3b", "#ffd23f", "#2fd17c", "#3f8cff", "#ff7ad9"]}
FULL = [(-12, 9, 0, 0), (12, 9, 0, 0), (12, -8, 0, 0), (-12, -8, 0, 0)]   # a region covering the whole picture


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


@dataclass
class SceneContext:
    P: object                      # song_project.Project
    section: str                   # section name (CLI argument)
    A: dict                        # the section of project.json
    S: float                       # section start / end in song seconds
    E: float
    fps: float
    N: int                         # frames of the section
    beats: list                    # song sheet beats around the section (+-0.3 s)
    lines: list
    words: list
    ASG: dict                      # assignment.json "figures": figure -> [(t, mouth cue)]
    figs_cfg: dict                 # project.json "figures"
    kind: str                      # section kind: scene | panels | external
    shot: object                   # section "shot" (None | "screen")
    names: list                    # figures of this section
    SET: dict                      # the loaded set
    lights: dict                   # light kind -> spec
    K: float                       # figure scale and floor line
    FLOOR: float
    SCREEN: tuple                  # screen rectangle (x0, y0, x1, y1)
    end: float = 0.0               # song end (+1 s) and its frame count: range of the ACT arrays
    NS: int = 0
    ACT: dict = field(default_factory=dict)        # figure -> bool per song frame: sings now (+-0.3 s)
    y8: object = None              # the song at 8 kHz and its average level (dB)
    ref: float = 0.0
    markers: list = field(default_factory=list)
    chorus: list = field(default_factory=list)     # [(t0, t1)] chorus spans
    dance: str = "chorus"
    gest: list = field(default_factory=list)       # (t0, t1, figure, gesture)
    svg_figs: list = field(default_factory=list)   # figures drawn from an SVG rig
    sung_beats: dict = field(default_factory=dict)
    spot: object = None            # spotlight spec, its span and the figure that stays lit
    spot_span: object = None
    spot_lead: object = None
    places: dict = field(default_factory=dict)     # figure -> x on the stage
    act_spans: dict = field(default_factory=dict)  # figure -> [(t0, t1, action, speed)]
    action_log: list = field(default_factory=list) # entries for analysis/actions_<section>.json
    styles_used: dict = field(default_factory=dict)
    light_pal: object = None       # disco palette
    screen_ev: list = field(default_factory=list)  # (t0, t1, text, colour)
    tint_ev: list = field(default_factory=list)    # (t0, t1, colour): the whole screen tinted (e.g. red at "Quota")
    night: object = None           # night spec and its amount keys
    night_k: object = None
    disco: object = None
    disco_span: object = None

    # ---------- timing helpers ----------
    def F(self, t):
        return round((t - self.S) * self.fps)

    def act(self, k, t):
        return bool(self.ACT[k][min(max(int(t * self.fps), 0), self.NS - 1)])

    def active(self, cues, pad=0.3):
        end, fps, NS = self.end, self.fps, self.NS
        on = np.zeros(NS, bool)
        for (t, s), nxt in zip(cues, cues[1:] + [[end, "X"]]):
            if s != "X":
                on[max(int((t - pad) * fps), 0): min(int((nxt[0] + pad) * fps) + 1, NS)] = True
        return on

    def cues_in_window(self, k):
        S, E = self.S, self.E
        c = self.ASG.get(k, [])
        before = [s for t, s in c if t <= S]
        return [(0.0, before[-1] if before else "X")] + [(t - S, s) for t, s in c if S < t < E + 0.5]

    def quiet(self, t):
        y8, ref = self.y8, self.ref
        x = y8[int(t * 8000): int((t + 0.5) * 8000)]
        return (20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9) - ref if len(x) else -60) < -9.0

    def in_dance(self, t):
        dance = self.dance
        return dance == "always" or (dance == "chorus" and any(c0 <= t < c1 for c0, c1 in self.chorus))

    def word_time(self, prefix, after=None, before=None):
        S, E = self.S, self.E
        lo, hi = (S - 0.05) if after is None else after, E if before is None else before
        return next((w["t"] for w in self.words if word_matches(w["word"], prefix) and lo <= w["t"] < hi), None)

    def line_span(self, l):
        nxt = next((x["t"] for x in self.lines if x["t"] > l["t"] + 0.05), None)
        return l["t"], (nxt - 0.05) if nxt is not None and nxt - l["t"] < 8 else l["end"] + 0.3

    def marker_time(self, text):
        S, E, lines = self.S, self.E, self.lines
        for m in self.markers:
            if text.lower() in m["marker"].lower() and m["line"] < len(lines) and S - 0.5 <= lines[m["line"]]["t"] < E:
                return lines[m["line"]]["t"] - 0.2
        return None

    def level(self, t0, t1):
        y8, ref = self.y8, self.ref
        x = y8[max(int(t0 * 8000), 0): max(int(t1 * 8000), 0)]
        return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9) - ref if len(x) else -60.0

    def abrupt_stop(self):
        """First moment (from 0.5 s before the section) where the next second is >= 8 dB under the second before and
        quiet (9 dB under the song average) - an abrupt musical stop; else the first quiet beat. Needs the music
        before the stop: in an excerpt project that starts at the stop, give "from" instead."""
        S, E, level = self.S, self.E, self.level
        for t in np.arange(max(S - 0.5, 1.0), E, 0.05):
            after = level(t + 0.1, t + 1.0)
            if after < -9.0 and after < level(t - 1.0, t) - 8.0:
                return float(max(t, S))
        return next((b["t"] for b in self.beats if b["t"] >= S and self.quiet(b["t"])), None)

    def span_of(self, spec):
        """(t0, t1) of a light/feature inside the section: from / word / marker / "silence" ... to / until_word / to_marker."""
        S, E = self.S, self.E
        t0 = None
        if spec.get("from") is not None:
            t0 = float(spec["from"])
        elif spec.get("word"):
            t0 = self.word_time(spec["word"])
        elif spec.get("marker"):
            t0 = self.marker_time(spec["marker"])
        elif spec.get("at") == "silence":
            t0 = self.abrupt_stop()
        else:
            t0 = S
        if t0 is None:
            return None
        t1 = E
        if spec.get("to") is not None:
            t1 = float(spec["to"])
        elif spec.get("until_word"):
            t1 = self.word_time(spec["until_word"], after=t0) or E
        elif spec.get("to_marker"):
            t1 = self.marker_time(spec["to_marker"]) or E
        return max(t0, S), min(t1, E)

    def gesture_at(self, k, t):
        return next((x[3] for x in self.gest if x[2] == k and x[0] <= t < x[1]), None)

    def keys(self, k):
        """Keyframes inside the section (0..N), one per frame (the last one wins); never empty."""
        seen = {}
        for it in k:
            if 0 <= it[0] <= self.N:
                seen[it[0]] = it
        out = [seen[f] for f in sorted(seen)]
        return out or [(0, k[0][1] if k else 0)]

    def span_keys(self, span, on=1.0, off=0.0):
        if not span:
            return [(0, off, "constant")]
        return [(0, off, "constant"), (self.F(span[0]), on, "constant"), (self.F(span[1]), off, "constant")]

    # ---------- built once ----------
    @classmethod
    def build(cls, P, section):
        fps = P.fps
        A = P.section(section)
        S, E = float(A["from"]), float(A["to"])
        N = round((E - S) * fps)
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
        K, FLOOR = float(A.get("scale", SET.get("scale", 0.68))), float(A.get("floor", SET.get("floor", -2.9)))
        if "spotlight" in lights and "scale" not in A:
            K *= 1.25                                         # spotlight: closer on the lit figures
        if (not SET.get("screen") and not A.get("screen") and shot != "screen"
                and any(figs_cfg[k].get("kind") == "screen" for k in names)):
            print(f"   note: set {A.get('set', 'stage')} has no \"screen\" rectangle - the screen figure uses the stage's "
                  f"(give the section \"screen\": [x0, y0, x1, y1])")
        SCREEN = tuple(A.get("screen") or (SCREEN_SHOT if shot == "screen" else SET.get("screen", [-2.4, 3.3, 2.4, 0.2])))
        c = cls(P=P, section=section, A=A, S=S, E=E, fps=fps, N=N, beats=beats, lines=lines, words=words, ASG=ASG,
                figs_cfg=figs_cfg, kind=kind, shot=shot, names=names, SET=SET, lights=lights, K=K, FLOOR=FLOOR,
                SCREEN=SCREEN)

        # ---------- who sings when (assignment.json) ----------
        c.end = max(sheet["duration"], E) + 1
        c.NS = int(c.end * fps) + 2
        c.ACT = {k: c.active(ASG.get(k, [])) for k in figs_cfg}
        act = c.act

        # ---------- quiet passages, choruses ----------
        c.y8 = decode(P.song, 8000)
        c.ref = 20 * np.log10(np.sqrt(np.mean(c.y8 ** 2)) + 1e-9)
        markers = c.markers = P.markers()
        end = c.end
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
        c.chorus = chorus
        c.dance = A.get("dance", "chorus")
        in_dance = c.in_dance

        # ---------- gestures on words ----------
        gest = c.gest
        for g in P.get("gestures", []):
            if g.get("figure") not in names or g.get("gesture") not in GESTURES:
                continue
            for w in words:
                if word_matches(w["word"], g["word"]) and S <= w["t"] < E:
                    gest.append((w["t"] - 0.1, w["t"] + float(g.get("duration", 1.0)), g["figure"], g["gesture"]))

        svg_figs = c.svg_figs = [k for k in names if figs_cfg[k].get("svg")]
        sung_beats = c.sung_beats = {k: sum(1 for b in beats if S <= b["t"] < E and act(k, b["t"])) for k in names}
        spot = c.spot = lights.get("spotlight")
        c.spot_span = c.span_of(spot) if spot else None
        spot_lead = None
        if spot:                                              # the figure singing most stays lit; the others appear in their light
            spot_lead = spot.get("lead") or (max(svg_figs, key=lambda k: sung_beats[k]) if svg_figs else None)
        c.spot_lead = spot_lead
        places = dict(SET.get("places", {}))
        if spot and svg_figs and not A.get("places"):
            places = {spot_lead: -0.5}
            others = [k for k in svg_figs if k != spot_lead]
            for i, k in enumerate(others):
                places[k] = 3.1 - 2.2 * i if creative.rng(P, f"spot_side:{section}").random() < 0.5 else -3.6 + 2.2 * i
            if places.get(spot_lead) is not None and any(places[k] < 0 for k in others):
                places[spot_lead] = 0.8
        places.update(A.get("places", {}))
        for i, k in enumerate(svg_figs):                      # figures without a place: spread evenly
            places.setdefault(k, -4.0 + 8.0 * (i + 0.5) / max(len(svg_figs), 1))
        c.places = places

        # ---------- actions in front of the body: typing / air guitar ----------
        line_span = c.line_span
        act_spans = c.act_spans = {k: [] for k in names}      # figure -> [(t0, t1, action, speed)]
        for spec in P.get("actions", []) + A.get("actions", []):
            k, what = spec.get("figure"), spec.get("action")
            if k not in svg_figs or what not in ACTIONS or (spec.get("sections") and section not in spec["sections"]):
                continue
            spans = []
            if spec.get("from") is not None or spec.get("to") is not None:
                spans = [(float(spec.get("from", S)), float(spec.get("to", E)))]
            elif spec.get("line"):
                spans = [line_span(l) for l in lines if l["text"].lower().startswith(spec["line"].lower())]
            elif spec.get("word"):
                spans = [line_span(l) for i, l in enumerate(lines)          # lines that contain the word
                         if any(word_matches(w["word"], spec["word"]) and w.get("line") == i for w in words)]
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

        c.light_pal = PALETTES[lights["disco"].get("palette") if lights.get("disco", {}).get("palette") in PALETTES
                               else creative.pick(P, f"disco:{section}", sorted(PALETTES))] if "disco" in lights else None

        # ---------- the Computer: text screens and tints on cue words ----------
        for ev in P.get("screen", []):
            if not allowed(ev, section):
                continue
            last = -99
            for w in words:
                if word_matches(w["word"], ev["word"]) and S <= w["t"] < E and w["t"] - last > 1.0:
                    if ev.get("text") and not ev.get("window"):
                        c.screen_ev.append((w["t"] - 0.05, w["t"] + float(ev.get("duration", 1.6)), ev["text"],
                                            ev.get("color", "#7CFF9B")))
                    if ev.get("tint"):
                        t1 = c.word_time(ev["tint_until"], after=w["t"] + 0.05, before=1e9) if ev.get("tint_until") else None
                        c.tint_ev.append((w["t"] - 0.05, t1 if t1 is not None else w["t"] + float(ev.get("tint_for", ev.get("duration", 1.6))),
                                          ev["tint"]))
                    last = w["t"]

        # ---------- lights: night amount keys, disco span ----------
        night = c.night = lights.get("night")
        if night:
            sp_n = c.span_of(night)
            if sp_n:
                residual = float(night.get("residual", 0.25))
                f0 = c.F(sp_n[0])
                c.night_k = [(0, 0.0, "constant"), (max(f0, 0), 1.0, "constant")]
                if sp_n[1] < E and (night.get("until_word") or night.get("to") is not None):
                    c.night_k += [(c.F(sp_n[1]), 1.0), (c.F(sp_n[1]) + 30, residual)]
        disco = c.disco = lights.get("disco")
        c.disco_span = c.span_of(disco) if disco else None
        return c
