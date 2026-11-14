# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0", "svgelements==1.9.6"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""A figure breaks out of a 2.5D comic flight and stands in front of the page as a paper cut-out.

Method (reference film "Prompts!", verse 2: Tim climbs out of the token sea in panel 4):
  1 flight   the comic flight is rendered with the figure's panel layer (the normal flight) and without it
             (render_multiplane.py --page comic25d; the clean config is derived automatically)
  2 track    per frame the screen box of the figure = where the two renders differ; the rig's head (or the whole
             rest pose) is fitted into that box -> screen scale + position of the painted figure (track.json)
  3 clip     the figure as a transparent Synfig clip from its rig SVG (characters convention), body actions per
             phase, mouths: one expression per phase, lip sync from a song project's assignment.json once it sings
  4 compose  from "start" on the clean render replaces the flight and the clip lies on top as a paper stand-up
             (white cut edge, cardboard edge, drop shadow on the page): it follows the track while it climbs out
             (cut at a water line / panel edge), then jumps or flips forward and stays big in the foreground

Usage:
  uv run breakout.py breakout.json
         [--steps flight,track,clip,compose | log] [--range 620-700] [--contact auto|630,646,700] [--jobs 6]

breakout.json (paths relative to it; frames are flight frames, "*_t" keys are song seconds, needs song.start_t):
  {"comic": "comic.json", "panel": "p4", "layer": "p4_03_tim.png",
   "flight": {"with": "frames_comic", "without": "frames_without"},   # existing folders are reused (mp_NNNN.png)
   "figure": "tim",                     # bundled name (tim, lia, fips) or an SVG; "feet"/"scale" for own SVGs
   "start": 630, "end": 1010,           # first frame of the break-out, last frame
   "fit": "kopf",                       # rig part fitted to the painted figure ("all" = whole rest pose)
   "song": {"start_t": 70.9, "project": "<song project>"} or {"start_t", "sheet", "assignment"},
           "figure": "tim", "sing_from_t": 98.4},   # beats for dance/marionette, lip sync from sing_from_t on
   "phases": [{"action": "climb", "to": 642, "cut": 600},
              {"action": "crouch", "to": 646},
              {"action": "flip", "to": 652, "target": [430, 790], "scale": 0.95, "height": 260},
              {"action": "shake", "to": 664, "sway": 22},
              {"action": "dance", "to": 850, "sway": 22},
              {"action": "marionette", "to": 1010, "strings": true}],
   "style": {"rim": 9, "rim_color": "#faf6ec", "edge_color": "#968c78", "edge_offset": [4, 5],
             "shadow": 0.45, "shadow_color": "#140c1e", "lift": [10, 26]},
   "splash": {"kind": "coins", "count": 16, "color": "#ffd23f"},
   "out": "frames_breakout", "seed": 11}

Actions (body in the Synfig clip + motion on screen):
  climb       arms pull up in turns; rises from the painted pose until the feet stand on the cut line
              (keys: cut = screen y | "auto" = bottom of the painted figure, drift = px sideways (25),
              follow = cut line moves with the camera (true), scale_factor = size vs. the painted figure, scaled
              about the top of the fitted part (1.0), offset = [dx, dy] px, size = figure height in px once it
              stands on the cut line - use it when the panel shows a close-up)
  crouch      anticipation squash before a jump; stays where it is (follow: keeps moving with the panel)
  jump, flip  stretched; arc to "target" [x, feet y] px with "scale" (clip px -> screen px) or "size" (figure
              height in px), "height" px; flip = one forward turn ("turns")
  land, shake landing squash / shake like a wet dog            dance   arms up in turns on the beat, bob
  marionette  yanked up on every beat, falls slack; "strings": true draws the strings
  wave        one arm waves                                     hold    breathing, idle
  Foreground phases take "sway" (px) and "sway_period" (frames); every phase may set "mouth" (X A B C D E F G H).
Sound log (compose step, or --steps log alone): every event of the break-out - climb (bubbles), jump/flip (whoosh),
landing (soft pop), coins/drops after the landing - goes to <work>/sound_log.json (flight frames + song seconds) and,
with "song": {"project": ...}, to <project>/analysis/actions_breakout_<panel>.json, which film-finish sounds.py mixes
in like any scene action. "sounds": {"climb": "drip/bubble", "jump": "whoosh_fast/whip", "land": "ui_pop/soft",
"coins": "drip/plink"} overrides the earshot ids, "sounds": false writes no project file.
Output: <out>/f.NNNN.png (flight frames 0..end, 1280x720 or the comic size), <out>.mp4, contact sheet,
        track.json, clip.sif + clip/ (editable in Synfig Studio).
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("toon-2d", "characters")
import config  # noqa: E402
import derived  # noqa: E402

HERE = Path(__file__).resolve().parent
CLIP_W, CLIP_H = 600, 750
INK_HEX = "#2b1d14"
ATTACHED = ("climb", "crouch")
JUMPS = ("jump", "flip")
FOREGROUND = ("land", "shake", "dance", "marionette", "wave", "hold")
ACTIONS = ATTACHED + JUMPS + FOREGROUND
MOUTH_OF = {"climb": "D", "crouch": "C", "jump": "D", "flip": "D", "land": "F", "shake": "E", "dance": "B",
            "marionette": "E", "wave": "X", "hold": "X"}
OPEN = {"X": 0, "A": 0, "B": 0.35, "C": 0.6, "D": 1.0, "E": 0.7, "F": 0.4, "G": 0.2, "H": 0.5}


# ------------------------------------------------------------------ config
class Cfg:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.dir = self.path.parent
        self.c = json.loads(self.path.read_text(encoding="utf-8"))
        c = self.c
        self.fps = c.get("fps", 24)
        song = c.get("song", {})
        self.song = song
        self.start_t = song.get("start_t")
        if song.get("project"):
            proj = self.p(song["project"])
            song.setdefault("sheet", str(proj / "analysis" / "song_sheet.json"))
            song.setdefault("assignment", str(proj / "analysis" / "assignment.json"))
        self.start = self.frame(c, "start")
        self.end = self.frame(c, "end")
        self.comic = self.p(c["comic"])
        fl = c.get("flight", {})
        self.with_dir = self.comic.parent / fl.get("with", json.loads(self.comic.read_text(encoding="utf-8"))
                                                   .get("out", "frames_mp"))
        self.without_dir = self.comic.parent / fl.get("without", f"frames_without_{c['panel']}")
        self.out = self.p(c.get("out", "frames_breakout"))
        self.work = self.p(c.get("work", "breakout_work"))
        self.work.mkdir(parents=True, exist_ok=True)
        self.phases = []
        a = self.start
        for ph in c["phases"]:
            if ph["action"] not in ACTIONS:
                raise SystemExit(f"unknown action {ph['action']!r} - use one of {', '.join(ACTIONS)}")
            b = self.frame(ph, "to")
            self.phases.append(dict(ph, a=a, b=b))
            a = b
        if self.phases[-1]["b"] < self.end:
            self.phases[-1]["b"] = self.end

    def p(self, rel):
        q = Path(rel)
        return q if q.is_absolute() else self.dir / q

    def frame(self, d, key):
        if key in d:
            return int(d[key])
        if key + "_t" in d:
            if self.start_t is None:
                raise SystemExit(f"'{key}_t' needs song.start_t (song time of flight frame 0)")
            return round((float(d[key + "_t"]) - self.start_t) * self.fps)
        raise SystemExit(f"'{key}' (frame) or '{key}_t' (song seconds) missing")

    def phase(self, g):
        for ph in self.phases:
            if ph["a"] <= g < ph["b"]:
                return ph
        return self.phases[-1]

    def beats(self):
        """Beat frames on the flight timeline: song sheet beats, else "bpm" (default 120) from start."""
        sheet = self.song.get("sheet")
        if sheet and self.start_t is not None:
            data = json.loads(self.p(sheet).read_text(encoding="utf-8"))
            return [round((b["t"] - self.start_t) * self.fps) for b in data["beats"]]
        step = self.fps * 60 / float(self.c.get("bpm", 120))
        return [round(self.start + k * step) for k in range(int((self.end - self.start) / step) + 2)]


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def rgb(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


# ------------------------------------------------------------------ 1 flight
def step_flight(C):
    """Render the flight with and without the figure layer unless the frame folders already exist."""
    cfg = json.loads(C.comic.read_text(encoding="utf-8"))
    need_end = C.end

    def have(d, upto):
        return (d / f"mp_{upto:04d}.png").exists()

    def render(conf_path):
        r = subprocess.run([sys.executable, str(HERE / "render_multiplane.py"), str(conf_path), "--page", "comic25d",
                            "--contact", "none"])
        if r.returncode:
            raise SystemExit("flight render failed")

    if not have(C.with_dir, need_end):
        print("flight with the figure ->", C.with_dir)
        if C.with_dir.name != cfg.get("out", "frames_mp"):
            raise SystemExit(f"{C.with_dir} missing and comic.json renders to {cfg.get('out')}")
        render(C.comic)
    if not have(C.without_dir, need_end):
        clean = json.loads(json.dumps(cfg))
        hit = 0
        for p in clean["panels"]:
            if p["id"] == C.c["panel"]:
                n0 = len(p.get("layers", []))
                p["layers"] = [l for l in p.get("layers", []) if Path(l["src"]).name != Path(C.c["layer"]).name]
                hit = n0 - len(p["layers"])
        if not hit:
            raise SystemExit(f"layer {C.c['layer']} not found in panel {C.c['panel']} of {C.comic.name}")
        clean["out"] = C.without_dir.name
        clean["end"] = need_end
        conf = C.comic.with_name(C.comic.stem + f"_without_{C.c['panel']}.json")
        conf.write_text(json.dumps(clean, indent=1), encoding="utf-8")
        print("flight without the figure ->", C.without_dir)
        render(conf)


# ------------------------------------------------------------------ figure + sprites
class Figure:
    def __init__(self, C):
        from figures import FIGURES, load, svg_path
        name = C.c["figure"]
        info = FIGURES.get(str(name).lower(), {})
        src = name if str(name).lower() in FIGURES else str(C.p(name))
        self.svg = svg_path(src)                              # source SVG (an input of the cached stills)
        self.feet = tuple(C.c.get("feet", info.get("feet", (200, 590))))
        self.scale = C.c.get("svg_scale", info.get("scale", 1 / 72))
        self.mouth_size = C.c.get("mouth_size", info.get("mouth") or 0.58)
        self.root, self.PIV = load(src, work_dir=C.work / "cache", feet=self.feet, scale=self.scale)
        H = self.feet[1] * self.scale                         # figure height in units (SVG top at y = 0)
        self.view = (-0.5125 * H, 1.221 * H, 0.5125 * H, -0.061 * H)
        self.ppu = CLIP_W / (self.view[2] - self.view[0])
        self.mid_x = CLIP_W / 2                               # feet point in clip px
        self.feet_y = self.view[1] * self.ppu
        ids = set()

        def walk(p):
            for it in p.items:
                if hasattr(it, "items"):
                    ids.add(it.id)
                    walk(it)
        walk(self.root)
        self.ids = ids
        rig = C.c.get("rig", {})
        wings = "arm_l" not in ids and "fluegel_vorn" in ids
        self.arm_l = rig.get("arm_l", "fluegel_vorn" if wings else "arm_l")
        self.arm_r = rig.get("arm_r", "fluegel_hinten" if wings else "arm_r")
        self.arm_gain = rig.get("arm_gain", 0.5 if wings else 1.0)
        self.head = rig.get("head", "kopf")
        self.beak = rig.get("beak", "schnabel_unten")

    def canvas(self, layers, end, name):
        from sif import canvas
        v = self.view
        return canvas(layers, w=CLIP_W, h=CLIP_H, end=end, name=name, view=f"{v[0]} {v[1]} {v[2]} {v[3]}")


def render_still(sif_text, path, sif=None):
    """One frame of a .sif -> PNG (the .sif is written to `sif`, default next to the PNG)."""
    sif = Path(sif) if sif else path.with_suffix(".sif")
    sif.write_text(sif_text, encoding="utf-8")
    tmp = path.parent / f"_still_{path.stem}"
    tmp.mkdir(exist_ok=True)
    subprocess.run([config.need("synfig"), str(sif), "-t", "png", "-o", str(tmp / "s.png"), "--begin-time", "0",
                    "--end-time", "0", "-w", str(CLIP_W), "-h", str(CLIP_H), "-q"], check=True, capture_output=True)
    got = sorted(tmp.glob("s*.png"))
    if not got:
        raise SystemExit(f"Synfig rendered nothing for {sif}")
    shutil.move(str(got[0]), str(path))
    shutil.rmtree(tmp, ignore_errors=True)
    return path


def cached_still(sif_text, path, svg=None):
    """render_still unless path was rendered (completely) from exactly this .sif text, clip size and source SVG
    (studio-core derived.py: content hashes, record written only after the render succeeded - figure / fit / size /
    scale changes change the text, an edited SVG changes its hash, a killed render never looks fresh). The .sif next
    to the PNG is only for opening it in Synfig Studio."""
    spec = {"sif": sif_text, "w": CLIP_W, "h": CLIP_H}
    inputs = [svg] if svg else []
    if not derived.fresh(path, inputs, spec):
        with derived.build(path, inputs, spec) as b:
            render_still(sif_text, b.path, sif=path.with_suffix(".sif"))
    return path


def sprites(C, F):
    """Rest pose and the fitted part alone, rendered in the clip canvas (cached, see cached_still)."""
    from svg2sif import emit
    rest = C.work / "rest.png"
    fit_png = C.work / "fit_part.png"
    cached_still(F.canvas(emit(F.root), 0, "rest"), rest, F.svg)
    part = C.c.get("fit", "kopf")
    node = F.root.find(part) if part != "all" else None
    if node is None:                                          # fit = the whole rest pose: a copy of rest.png
        fit_png.with_suffix(".sif").unlink(missing_ok=True)
        if not derived.fresh(fit_png, [rest], {"copy_of": "rest"}):
            with derived.build(fit_png, [rest], {"copy_of": "rest"}) as b:
                shutil.copy(rest, b.path)
    else:
        cached_still(F.canvas(emit(node) if node.items else [], 0, "fit"), fit_png, F.svg)
    return rest, fit_png


# ------------------------------------------------------------------ 2 track
def diff_mask(C, f):
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(C.with_dir / f"mp_{f:04d}.png").convert("RGB"), np.int16)
    b = np.asarray(Image.open(C.without_dir / f"mp_{f:04d}.png").convert("RGB"), np.int16)
    m = np.abs(a - b).max(2) > int(C.c.get("diff_threshold", 20))
    cols = np.where(m.sum(0) > 3)[0]
    rows = np.where(m.sum(1) > 3)[0]
    if not len(cols) or not len(rows):
        return None, None
    # fill each row between its outermost pixels: figure colours close to the background leave holes
    filled = np.zeros_like(m)
    for y in rows:
        xs = np.nonzero(m[y])[0]
        filled[y, xs.min():xs.max() + 1] = True
    return filled, (int(cols.min()), int(rows.min()), int(cols.max()), int(rows.max()))


def fit_frame(mask, box, part_alpha, guess=None):
    """Scale s and screen offset (ox, oy) of the clip so the fitted part covers the top of the mask best (IoU)."""
    import numpy as np
    from PIL import Image
    ys, xs = np.nonzero(part_alpha > 128)
    px0, py0, px1, py1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    crop = Image.fromarray(((part_alpha[py0:py1, px0:px1] > 128) * 255).astype(np.uint8))
    pw, ph = px1 - px0, py1 - py0
    x0, top, x1, y1 = box
    best = (-1, None)

    def score(s, dx):
        w, h = max(2, round(pw * s)), max(2, round(ph * s))
        spr = np.asarray(crop.resize((w, h), Image.BILINEAR)) > 127
        X, Y = int(round(dx)), top
        H, W = mask.shape
        band = mask[Y:min(Y + h, y1 + 1, H)]
        # IoU inside the rows the part covers and the columns of the mask box: the window may cut the painted
        # figure, so sprite pixels outside the visible box do not count against the fit
        cx0c, cx1c = max(x0, 0), min(x1 + 1, W)
        m = band[:, cx0c:cx1c]
        sp = np.zeros_like(m)
        sx0, sx1 = max(X, cx0c), min(X + w, cx1c)
        if sx1 > sx0:
            sp[:, sx0 - cx0c:sx1 - cx0c] = spr[:m.shape[0], sx0 - X:sx1 - X]
        inter = (m & sp).sum()
        union = (m | sp).sum()
        return inter / union if union else 0

    if guess is None:
        scales = np.geomspace(0.25, 4.0, 48)
    else:
        scales = np.geomspace(guess[0] / 1.25, guess[0] * 1.25, 21)
    for s in scales:
        w = pw * s
        if guess is None:            # the window may hide either side of the figure: try every overlap
            cands = np.linspace(x0 - w * 0.9, x1 - w * 0.1, 41)
        else:
            left = guess[1] + px0 * s
            cands = np.linspace(left - 24, left + 24, 17)
        for dx in cands:
            v = score(s, dx)
            if v > best[0]:
                best = (v, (s, dx))
    s, dx = best[1]
    for _ in range(2):                                          # refine
        for s2 in np.linspace(s * 0.96, s * 1.04, 9):
            for dx2 in np.linspace(dx - 6, dx + 6, 13):
                v = score(s2, dx2)
                if v > best[0]:
                    best = (v, (s2, dx2))
        s, dx = best[1]
    ox, oy = dx - px0 * s, top - py0 * s                        # clip (0, 0) on screen
    return {"scale": float(s), "ox": float(ox), "oy": float(oy), "iou": float(best[0])}


def step_track(C, F):
    import numpy as np
    from PIL import Image
    rest, fit_png = sprites(C, F)
    part_alpha = np.asarray(Image.open(fit_png).convert("RGBA").getchannel("A"))
    attached_end = max([ph["b"] for ph in C.phases if ph["action"] in ATTACHED] + [C.start + 1])
    t0 = max(0, int(C.c.get("track_from", C.start - 12)))      # flight frames start at mp_0000
    raw, guess = {}, None
    for f in range(t0, attached_end + 1):
        m, box = diff_mask(C, f)
        if m is None:
            continue
        fit = fit_frame(m, box, part_alpha, guess)
        guess = (fit["scale"], fit["ox"])
        raw[f] = dict(fit, box=list(box))
    if not raw:
        raise SystemExit("the two renders do not differ - wrong panel/layer or frames?")
    # smooth scale and position (moving median over 5 frames): the camera moves smoothly
    fs = sorted(raw)
    for key in ("scale", "ox", "oy"):
        vals = [raw[f][key] for f in fs]
        for k, f in enumerate(fs):
            raw[f][key + "_s"] = float(np.median(vals[max(0, k - 2):k + 3]))
    track = {str(f): v for f, v in raw.items()}
    (C.work / "track.json").write_text(json.dumps(track, indent=0), encoding="utf-8")
    ious = [raw[f]["iou"] for f in fs]
    print(f"track: {len(fs)} frames {fs[0]}-{fs[-1]}, fit IoU mean {np.mean(ious):.2f} (min {min(ious):.2f}), "
          f"scale {raw[fs[0]]['scale_s']:.2f}..{raw[fs[-1]]['scale_s']:.2f}")
    return track


def load_track(C):
    t = json.loads((C.work / "track.json").read_text(encoding="utf-8"))
    return {int(k): v for k, v in t.items()}


# ------------------------------------------------------------------ 3 clip (Synfig)
def body_keys(C, F):
    """Per clip frame: arm angles, head tilt, squash, look, brow lift, beak (baked keys, linear)."""
    beats = C.beats()

    def beat_phase(g):
        k = max([i for i, b in enumerate(beats) if b <= g], default=-1)
        return k, g - (beats[k] if k >= 0 else C.start)

    N = C.end - C.start
    keys = {k: [] for k in ("arm_l", "arm_r", "head", "sq", "look", "brow")}
    prev = (-30.0, 30.0)
    for i in range(N + 1):
        g = C.start + i
        ph = C.phase(g)
        act, h, L = ph["action"], g - ph["a"], max(1, ph["b"] - ph["a"])
        brow = 0.14
        if act == "climb":
            p = math.sin(i * 0.9)
            a_l, a_r, hd, s, ly = -150 + 18 * p, 150 + 18 * p, -6, 1.0 + 0.05 * p, 0.08
        elif act == "crouch":
            u = h / L
            a_l, a_r = prev[0] + (-30 - prev[0]) * u, prev[1] + (30 - prev[1]) * u
            hd, s, ly = 0, 1 - 0.18 * u, 0.0
        elif act in JUMPS:
            a_l, a_r, hd, s, ly = -160, 160, 0, 1.1, 0.06
        elif act in ("shake", "land"):
            a_l, a_r = -40 + 25 * math.sin(h * 2.2), 40 + 25 * math.sin(h * 2.2 + 1)
            hd = 14 * math.sin(h * 2.6) * math.exp(-h / 9) if act == "shake" else 0
            if act == "land":
                a_l, a_r = -40, 40
            s, ly = 1 - 0.2 * math.exp(-h / 2.5) * math.cos(h / 1.6), 0.0
        elif act == "dance":
            k, d = beat_phase(g)
            side = 1 if k % 2 else -1
            up = max(0.0, 1 - d / 8)
            a_l = (-140 if side < 0 else 30) + 15 * math.sin(i * 0.4)
            a_r = (140 if side > 0 else -30) + 15 * math.sin(i * 0.4)
            hd, s, ly, brow = 8 * side, 1 - 0.08 * up + 0.04 * (1 - up), 0.0, 0.04
        elif act == "marionette":
            k, d = beat_phase(g)
            yank = math.exp(-d / 3)
            a_l = -35 - 95 * yank * (1 if k % 2 else 0.6)
            a_r = 35 + 95 * yank * (0.6 if k % 2 else 1)
            hd, s, ly = 16 - 10 * yank, 1 + 0.06 * yank, 0.07 * yank
        elif act == "wave":
            a_l, a_r = -12, 125 + 28 * math.sin(h * 0.5)
            hd, s, ly, brow = 6, 1 + 0.015 * math.sin(h / 9), 0.03, 0.06
        else:                                            # hold
            a_l, a_r = -8 + 3 * math.sin(h / 11), 8 - 3 * math.sin(h / 11)
            hd, s, ly, brow = 2 * math.sin(h / 23), 1 + 0.015 * math.sin(h / 12), 0.0, 0.04
        prev = (a_l, a_r)
        keys["arm_l"].append((i, a_l * F.arm_gain, "linear"))
        keys["arm_r"].append((i, a_r * F.arm_gain, "linear"))
        keys["head"].append((i, hd, "linear"))
        keys["sq"].append((i, (s ** -0.6, s), "linear"))
        keys["look"].append((i, (0.0, ly), "linear"))
        keys["brow"].append((i, brow, "linear"))
    return keys


def mouth_cues(C):
    """[(clip seconds, shape)]: one expression per phase, from song.sing_from_t on the song assignment."""
    fps = C.fps
    cues = [((ph["a"] - C.start) / fps, ph.get("mouth", MOUTH_OF[ph["action"]])) for ph in C.phases]
    song = C.song
    if song.get("assignment") and song.get("sing_from_t") is not None and C.start_t is not None:
        data = json.loads(C.p(song["assignment"]).read_text(encoding="utf-8"))
        zut = data["figures"][song.get("figure", C.c["figure"])]
        t_clip0 = C.start_t + C.start / fps
        sing0 = float(song["sing_from_t"]) - t_clip0
        before = [s for t, s in zut if t <= song["sing_from_t"]]
        cues = ([c for c in cues if c[0] < sing0] + [(sing0, before[-1] if before else "X")]
                + [(t - t_clip0, s) for t, s in zut if song["sing_from_t"] < t < C.start_t + C.end / fps + 0.5])
    return cues


def step_clip(C, F, jobs=1):
    from sif import V, R, anim, comp_vec, group, hexc
    from svg2sif import emit
    from figures import around, blink_keys
    from lipsync import mouth_layers
    from render import render_sif
    N = C.end - C.start
    K = body_keys(C, F)
    cues = mouth_cues(C)
    PIV = F.PIV
    blink = blink_keys(list(range(60, N - 4, 70)))
    look = lambda pid: (lambda kids, p: group(pid, kids, offset=anim("vector", K["look"])))
    wrap = {}
    if F.arm_l in F.ids:
        wrap[F.arm_l] = lambda kids, p: around(PIV, F.arm_l, kids, angle=anim("angle", K["arm_l"]))
    if F.arm_r in F.ids:
        wrap[F.arm_r] = lambda kids, p: around(PIV, F.arm_r, kids, angle=anim("angle", K["arm_r"]))
    mouth = []
    if "mund" in PIV:
        mouth = mouth_layers(cues, C.fps, center=PIV["mund"], size=F.mouth_size, ink=hexc(INK_HEX))
    elif F.beak in F.ids:                                        # a beak opens with the mouth shapes
        bk = []
        for t, s in cues:
            f = max(0, round(t * C.fps))
            bk.append((f, -26 * OPEN.get(s, 0.3), "constant"))
        wrap[F.beak] = lambda kids, p: around(PIV, F.beak, kids, angle=anim("angle", [(0, 0, "constant")] + bk))
    if F.head in F.ids:
        wrap[F.head] = lambda kids, p: around(PIV, F.head, kids + mouth, angle=anim("angle", K["head"]))
    for e in ("auge_l", "auge_r"):
        if e in F.ids:
            wrap[e] = (lambda e: lambda kids, p: around(PIV, e, kids, scale=anim("vector", blink)))(e)
    for e in ("pupille_l", "pupille_r"):
        if e in F.ids:
            wrap[e] = look(e)
    if "brauen" in F.ids:
        wrap["brauen"] = lambda kids, p: group("brauen", kids, offset=comp_vec(R(0), anim("real", K["brow"])))
    body = group("Figure", emit(F.root, wrap), origin=(0, 0), offset=V(0, 0), scale=anim("vector", K["sq"]))
    sif = C.work / "clip.sif"
    sif.write_text(F.canvas([body], N, "break-out clip"), encoding="utf-8")
    pattern, n = render_sif(sif, C.work / "clip", width=CLIP_W, height=CLIP_H, jobs=jobs)
    print(f"clip: {n} frames -> {pattern}")


# ------------------------------------------------------------------ 4 compose
class Composer:
    def __init__(self, C, F, track):
        import numpy as np
        from PIL import Image
        self.C, self.F, self.T = C, F, track
        st = C.c.get("style", {})
        self.rim = int(st.get("rim", 9))
        self.rim_col = rgb(st.get("rim_color", "#faf6ec"))
        self.edge_col = rgb(st.get("edge_color", "#968c78"))
        self.edge_off = tuple(st.get("edge_offset", (4, 5)))
        self.sh_op = float(st.get("shadow", 0.45))
        self.sh_col = rgb(st.get("shadow_color", "#140c1e"), 0)
        self.lift = st.get("lift", (10, 26))
        rest = np.asarray(Image.open(C.work / "rest.png").convert("RGBA").getchannel("A")) > 128
        ys, xs = np.nonzero(rest)
        self.body_c = ((xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2)   # rotation centre (clip px)
        self.fig_px = ys.max() - ys.min()
        part = np.asarray(Image.open(C.work / "fit_part.png").convert("RGBA").getchannel("A")) > 128
        ys, xs = np.nonzero(part)
        self.part_top = ((xs.min() + xs.max()) / 2, ys.min())    # top centre of the fitted part (clip px)
        self.tr_frames = sorted(track)
        self.start_fit = self.fit(C.start)
        sp = C.c.get("splash")
        self.splash = []
        if sp:
            rng = np.random.default_rng(C.c.get("seed", 11))
            climb = next((ph for ph in C.phases if ph["action"] == "climb"), C.phases[0])
            for _ in range(int(sp.get("count", 16))):
                self.splash.append((rng.uniform(-0.35, 0.65), rng.uniform(-14, -6), rng.uniform(-9, 9),
                                    climb["a"] + int(rng.integers(0, max(2, climb["b"] - climb["a"] + 4))),
                                    rng.uniform(9, 15)))
            self.splash_kind = sp.get("kind", "coins")
            self.splash_col = rgb(sp.get("color", "#ffd23f" if self.splash_kind == "coins" else "#8fd3ff"))
        self._plan()

    def fit(self, g):
        """Smoothed fit of the painted figure at flight frame g (clamped to the tracked range)."""
        fs = self.tr_frames
        g = min(max(g, fs[0]), fs[-1])
        if g not in self.T:
            g = min(fs, key=lambda f: abs(f - g))
        t = self.T[g]
        return t["scale_s"], t["ox_s"], t["oy_s"]

    def feet_of(self, fit, k=1.0, off=(0, 0)):
        """Feet point + scale on screen; k scales about the top centre of the fitted part (head stays put)."""
        s, ox, oy = fit
        hx, hy = self.part_top
        px, py = ox + hx * s, oy + hy * s
        s2 = s * k
        return px + (self.F.mid_x - hx) * s2 + off[0], py + (self.F.feet_y - hy) * s2 + off[1], s2

    def _plan(self):
        """Screen pose per frame: (feet x, feet y, scale, rotation deg, cut y or None, lifted)."""
        C = self.C
        self.pose = {}
        cur = None
        anchor_shift, anchor_k = (0.0, 0.0), (1.0, (0, 0))
        sway_origin = {}
        run_key, run_start = None, None
        for ph in C.phases:
            key = (ph.get("sway"), ph.get("sway_period"), ph["action"] in FOREGROUND)
            if key != run_key:
                run_key, run_start = key, ph["a"]
            sway_origin[id(ph)] = run_start
        jumped = False
        for g in range(C.start, C.end + 1):
            ph = C.phase(g)
            act, L = ph["action"], max(1, ph["b"] - ph["a"])
            u = (g - ph["a"]) / L
            if act == "climb":
                k, off = ph.get("scale_factor", 1.0), ph.get("offset", (0, 0))
                fx, fy, s = self.feet_of(self.fit(g), k, off)
                fx0, fy0, s0 = self.feet_of(self.fit(ph["a"]), k, off)
                cut = ph.get("cut", "auto")
                if cut == "auto":
                    cut = self.T[min(self.tr_frames, key=lambda f: abs(f - ph["a"]))]["box"][3]
                follow = ph.get("follow", True)
                cut_g = cut + ((fy - fy0) if follow else 0)
                uu = ease(u)
                if "size" in ph:                 # shrink/grow to this standing height (px) while climbing out
                    s = s + (float(ph["size"]) / self.fig_px - s) * uu
                x = fx + ph.get("drift", 25) * uu
                y = fy + (cut_g - fy) * uu
                cur = (x, y, s)
                self.pose[g] = (x, y, s, 0.0, cut_g, False)
                anchor_shift = (fx, fy)
                anchor_k = (k, off)
            elif act == "crouch":
                if cur is None:
                    fx, fy, s = self.feet_of(self.fit(g))
                    cur = (fx, fy, s)
                x, y, s = cur
                if ph.get("follow", True) and not jumped:
                    fx, fy, _ = self.feet_of(self.fit(g), *anchor_k)
                    x, y = x + fx - anchor_shift[0], y + fy - anchor_shift[1]
                self.pose[g] = (x, y, s, 0.0, None, False)
            elif act in JUMPS:
                if g == ph["a"] or not hasattr(self, "_jump0") or self._jump0[0] is not ph:
                    prev = self.pose.get(g - 1)
                    p0 = (prev[0], prev[1], prev[2]) if prev else self.feet_of(self.fit(g))
                    self._jump0 = (ph, p0)
                x0, y0, s0 = self._jump0[1]
                tx, ty = ph.get("target", (C.c.get("width", 1280) * 0.34, 790))
                if "size" in ph:
                    s1 = float(ph["size"]) / self.fig_px
                else:
                    s1 = float(ph.get("scale", s0))
                x = x0 + (tx - x0) * u
                y = y0 + (ty - y0) * u - float(ph.get("height", 260)) * math.sin(math.pi * u)
                s = s0 + (s1 - s0) * u + ph.get("bump", 0.25) * math.sin(math.pi * u)
                turns = ph.get("turns", 1 if act == "flip" else 0)
                rot = 360 * turns * ease(u)
                self.pose[g] = (x, y, s, rot, None, True)
                cur = (tx, ty, s1)
                jumped = True
            else:
                if cur is None:
                    cur = self.feet_of(self.fit(g))
                x, y, s = cur
                amp = ph.get("sway", 22 if act == "dance" else 10 if act == "marionette" else 0)
                per = ph.get("sway_period", 48 if act == "dance" else 44)
                t = g - sway_origin[id(ph)]
                x += amp * math.sin(t / per * 2 * math.pi)
                self.pose[g] = (x, y, s, 0.0, None, jumped)

    def base(self, g):
        from PIL import Image
        C = self.C
        src = C.with_dir / f"mp_{g:04d}.png"
        if g >= C.start:
            alt = C.without_dir / f"mp_{g:04d}.png"
            if alt.exists():
                src = alt
        return Image.open(src).convert("RGBA")

    def cutout(self, spr):
        from PIL import Image, ImageFilter
        a = spr.getchannel("A")
        rim = a.filter(ImageFilter.MaxFilter(self.rim if self.rim % 2 else self.rim + 1))
        ex, ey = self.edge_off
        edge = rim.transform(rim.size, Image.AFFINE, (1, 0, -ex, 0, 1, -ey))
        out = Image.new("RGBA", spr.size, (0, 0, 0, 0))
        out.paste(self.edge_col, (0, 0), edge)
        out.paste(self.rim_col, (0, 0), rim)
        out.alpha_composite(spr)
        return out

    def draw(self, img, g):
        import numpy as np
        from PIL import Image, ImageDraw, ImageFilter
        C, F = self.C, self.F
        if g < C.start or g > C.end:
            return img
        i = g - C.start
        spr = Image.open(C.work / "clip" / f"clip.{i:04d}.png").convert("RGBA")
        spr = self.cutout(spr)
        x, feet, s, rot, cut, lifted = self.pose[g]
        w, h = max(1, round(CLIP_W * s)), max(1, round(CLIP_H * s))
        spr = spr.resize((w, h), Image.LANCZOS)
        ox, oy = round(x - F.mid_x * s), round(feet - F.feet_y * s)
        if rot:
            spr = spr.rotate(-rot, Image.BICUBIC, center=(self.body_c[0] * s, self.body_c[1] * s))
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        layer.paste(spr, (ox, oy), spr)
        if cut is not None:                                   # below the water line / panel edge: still inside
            layer.paste((0, 0, 0, 0), (0, int(round(cut)), img.width, img.height))
        lift = self.lift[1] if lifted else self.lift[0]
        sh = Image.new("RGBA", img.size, self.sh_col)
        sh.putalpha(layer.getchannel("A").point(lambda v: int(v * self.sh_op)).filter(ImageFilter.GaussianBlur(lift / 2)))
        img.alpha_composite(sh, (int(lift), int(lift * 0.8)))
        d = ImageDraw.Draw(img)
        if self.splash:
            ink = rgb(INK_HEX)
            for dx, vy, vx, t0, r in self.splash:
                t = g - t0
                if 0 <= t < 22 and t0 in self.pose:
                    px, py, ps = self.pose[t0][:3]
                    wl = self.pose[t0][4] if self.pose[t0][4] is not None else py
                    hx = px + dx * self.fig_px * ps * 0.27 + vx * t
                    hy = wl - 10 + vy * t + 0.9 * t * t
                    if hy < img.height:
                        if self.splash_kind == "coins":
                            d.ellipse((hx - r, hy - r * 0.8, hx + r, hy + r * 0.8), fill=self.splash_col, outline=ink,
                                      width=3)
                        else:
                            d.ellipse((hx - r * 0.6, hy - r, hx + r * 0.6, hy + r * 0.4), fill=self.splash_col,
                                      outline=ink, width=2)
        img.alpha_composite(layer)
        ph = C.phase(g)
        if ph["action"] == "marionette" and ph.get("strings", True):
            a = np.asarray(layer.getchannel("A")) > 30
            ys, xs = np.nonzero(a)
            if len(xs):
                mid = (xs.min() + xs.max()) / 2
                col = rgb(ph.get("string_color", "#ebebf0"), 220)
                for side in (xs.min(), xs.max()):
                    hy = int(np.nonzero(a[:, side])[0].mean())
                    sway = 6 * math.sin(g / 5 + side)
                    d.line((side + sway, 0, side, hy), fill=col, width=2)
                d.line((mid, 0, mid, int(ys.min())), fill=col, width=2)
        return img


SOUNDS = {"climb": ("drip/bubble", "drip/bloop"), "jump": ("whoosh_fast/whip",), "land": ("ui_pop/soft",),
          "coins": ("drip/plink",), "drops": ("drip/plink",)}


def sound_log(C, comp):
    """Events of the break-out as a sound log (climb, jump, landing, coins) -> work/sound_log.json and, with a song
    project, analysis/actions_breakout_<panel>.json for film-finish sounds.py."""
    own = C.c.get("sounds", {})
    if own is False:
        own = {}
    ids = {k: ((own[k],) if isinstance(own.get(k), str) else tuple(own.get(k) or v)) for k, v in SOUNDS.items()}
    W = C.c.get("width", 1280)
    pan = lambda g: round(max(-0.7, min(0.7, (comp.pose.get(g, (W / 2,))[0] / W - 0.5) * 1.2)), 2)
    ev = []                                          # (flight frame, kind, sfx, level)
    landed = None
    for i, ph in enumerate(C.phases):
        act = ph["action"]
        if act == "climb":
            for j, g in enumerate(range(ph["a"], ph["b"], 4)):
                if j < 3:
                    ev.append((g, "climb", ids["climb"][j % len(ids["climb"])], -16 - j))
        elif act in JUMPS:
            ev.append((ph["a"], "jump", ids["jump"][0], -12))
            landed = ph["b"]
    if landed is not None:
        ev.append((landed, "land", ids["land"][0], -12))
        sp = C.c.get("splash")
        if sp:
            kind = "coins" if sp.get("kind", "coins") == "coins" else "drops"
            ev += [(landed + d, kind, ids[kind][0], -18 - k) for k, d in enumerate((1, 3, 6))]
    ev.sort()
    t_of = (lambda g: round(C.start_t + g / C.fps, 3)) if C.start_t is not None else (lambda g: None)
    log = [{"frame": g, "t": t_of(g), "gesture": kind, "sfx": sfx, "level": lvl, "pan": pan(g)} for g, kind, sfx, lvl in ev]
    (C.work / "sound_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    proj = C.song.get("project")
    if proj and C.start_t is not None and C.c.get("sounds", {}) is not False:
        out = C.p(proj) / "analysis" / f"actions_breakout_{C.c['panel']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps([{k: e[k] for k in ("t", "gesture", "sfx", "level", "pan")} | {"figure": C.c.get("figure")}
                                   for e in log], indent=1), encoding="utf-8")
        print(f"sound log: {len(log)} events -> {out}")
    else:
        print(f"sound log: {len(log)} events -> {C.work / 'sound_log.json'}")
    return log


def step_compose(C, F, rng_=None, contact="auto"):
    from render import contact_sheet, encode, pick_frames
    comp = Composer(C, F, load_track(C))
    if rng_ is None:
        sound_log(C, comp)
    C.out.mkdir(parents=True, exist_ok=True)
    lo, hi = rng_ or (0, C.end)
    for g in range(lo, hi + 1):
        comp.draw(comp.base(g), g).convert("RGB").save(C.out / f"f.{g:04d}.png")
    print(f"compose: frames {lo}-{hi} -> {C.out}")
    if rng_ is None:
        pattern = str(C.out / "f.%04d.png")
        mp4 = C.out.with_suffix(".mp4")
        encode(pattern, mp4, C.fps)
        print("video:", mp4)
        if contact != "none":
            nums = ([C.start - 1] + [ph["a"] for ph in C.phases] + [ph["a"] + 4 for ph in C.phases[:3]]) \
                if contact == "auto" else pick_frames(contact, C.end + 1)
            nums = sorted({n for n in nums if 0 <= n <= C.end})[:12]
            sheet = C.out.with_name(C.out.name + "_contact.png")
            contact_sheet(pattern, sheet, nums)
            print("contact sheet:", sheet)


def main():
    ap = argparse.ArgumentParser(description="A figure breaks out of a 2.5D comic flight (paper stand-up).")
    ap.add_argument("config")
    ap.add_argument("--steps", default="flight,track,clip,compose")
    ap.add_argument("--range", help="compose only these flight frames, e.g. 620-700 (quick look)")
    ap.add_argument("--contact", default="auto")
    ap.add_argument("--jobs", type=int, default=4, help="parallel Synfig processes for the clip")
    a = ap.parse_args()
    C = Cfg(a.config)
    steps = a.steps.split(",")
    if "flight" in steps:
        step_flight(C)
    F = Figure(C)
    if "track" in steps:
        step_track(C, F)
    if "clip" in steps:
        sprites(C, F)
        step_clip(C, F, a.jobs)
    if "log" in steps and "compose" not in steps:     # the sound log alone (no frames)
        sound_log(C, Composer(C, F, load_track(C)))
    if "compose" in steps:
        r = tuple(int(x) for x in a.range.split("-")) if a.range else None
        step_compose(C, F, r, a.contact)


if __name__ == "__main__":
    main()
