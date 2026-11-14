"""Clip basics shared by every step of clip.py (and by scene.py / intro.py through clip's re-exports):
the clip file with its slide and world size (Clip), a figure's geometry on the slide (fig_geometry) and the time specs
of clip.json (Times)."""
import json
import math
from pathlib import Path

PX_PER_SU = 108          # Synfig render resolution (px per unit)
H_REF = 3.80             # height (world) of the reference figure (Fritz on slide 5) the camera moves were made for
WORLD_W = 16.0


class Clip:
    def __init__(self, path):
        self.file = Path(path).resolve()
        self.dir = self.file.parent
        self.p = json.loads(self.file.read_text(encoding="utf-8"))
        if "seed" not in self.p:                     # SKILL: the project's seed lives in project.json (user test:
            for up in (self.dir.parent.parent, self.dir.parent):   # it was ignored) - clips/<name>/clip.json
                pj = up / "project.json"
                if pj.exists():
                    s = json.loads(pj.read_text(encoding="utf-8")).get("seed")
                    if s is not None:
                        self.p["seed"] = s           # in memory; a clip's own "seed" still wins
                        self._seed_from_project = True
                    break
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
        p = {k: v for k, v in self.p.items() if not (k == "seed" and getattr(self, "_seed_from_project", False))}
        self.file.write_text(json.dumps(p, indent=1, ensure_ascii=False), encoding="utf-8")


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
            self._words[lid] = narration.words(self.C.dir / n["audio"], self.C.dir / "narration",
                                                  n.get("lang") or self.C.p.get("lang"))   # None = detected
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
