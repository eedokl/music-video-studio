# /// script
# requires-python = ">=3.12"
# dependencies = ["faster-whisper==1.2.1", "numpy==2.5.4", "pillow==13.0.0", "scikit-image==0.26.0", "scipy==1.18.1"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""General 2.5D scene stage for presentation films: the slide figures act in painted sets (after they stepped out).

A scene = set layers in the room (painted backgrounds, a table as a front layer), layers in front of the camera
(e.g. a floor plan the camera flies into), rigged slide figures (Synfig, original parts, light maps, line boil, scene
light tint/rim), sprites (bubbles, star eyes, props; in the room or hung on a figure), coffee steam, a camera path,
narration lines (a line with "speaker" makes that figure talk: Rhubarb -> mouth stages, see mouth.py).
Rendered by assets/scene25d.html through toon-2d render_multiplane.py (reference: buehne/szene*.py of ai_efficiency,
scenes S3-S12).

Python (full control, per-frame values from your own code):
    import scene as SC
    S = SC.Scene("clips/s03", deck="../../deck/deck.json", figures_dir="../../figures", end=189)
    S.layer("office", "set/office.png", w=16, h=9.07, z=0, order=0)
    S.layer("table", "set/table.png", w=15.5, h=8.8, z=0.5, order=20)
    S.overlay("plan", "set/plan.png", aspect=1.5, fit=1.2)
    S.figure("fritz", x=1.0, y=-2.55, z=0.25, scale=0.45, order=12, keys={"eyes": [...], "arm_r": [...], "mouth": ...})
    S.camera([(0, [0, 0.2, 15.6, 0, 0, 0]), (189, [-0.2, -0.1, 13.4, -0.2, -0.4, 0])])
    S.per_frame(lambda f, F: F["overlays"].update(plan={"opacity": 1.0, "s": 1 + f / 100}))
    S.build(); S.render()            # plan -> synfig -> light -> 3d -> final (look) -> sound
JSON (same keys): scene.py clips/s03/scene.json  ->  {"end": 189, "layers": [...], "overlays": [...],
    "figures": {"fritz": {"x": 1.0, "y": -2.55, "z": 0.25, "scale": 0.45, "keys": {...}}}, "camera": [...],
    "steam": [{"x": .., "y": .., "z": ..}], "sprites": [...], "narration": [...], "sounds": [...]}
    build() writes the generated per-frame stage config to <scene>/scene_stage.json (never over your scene.json).
Keys per figure (frames): eyes [(f,(dx,dy))], blink [(f,h)], head/<part name> [(f,deg)], sq [(f,(sx,sy))],
tilt [(f,deg)] (over the feet), spin, pos [(f,(x,y))] (Synfig units; hops), mouth [(f,stage 0..7)].
Helpers: nod(), slow_nod(), breathe(), babble() (silent talking: changing mouth stages), steps() (hop/walk cycle:
body bob + squash on every contact + rocking; move the feet in the room with "path"), pop() (sprite pop-in/out).
Every figure gets procedural idle life (weight shift, head/part sway, breathing, irregular blinks) unless idle=False.
"""
import json
import math
import random
import shutil
import subprocess
import sys
from pathlib import Path

import _studio
_studio.use("toon-2d", "film-finish")
import acting as A  # noqa: E402
import clip as CL  # noqa: E402
import config  # noqa: E402

HERE = Path(__file__).resolve().parent
STAGE_MP4 = "scene_stage.mp4"                        # stage video of build()/render() (from scene_stage.json)
smooth, keyed = A.smooth, A.keyed


# ---------------------------------------------------------------- key helpers
def nod(base, t, amp=3):
    return [(t - 4, base), (t + 2, base + amp), (t + 8, base - 1), (t + 14, base)]


def slow_nod(base, t, amp=5):
    return [(t - 6, base), (t + 4, base + amp, "halt"), (t + 9, base + amp), (t + 16, base - 1), (t + 22, base)]


def breathe(start, end, amp=0.008, period=52):
    out, f = [], start
    while f <= end:
        out += [(f, (1, 1), "halt"), (min(f + period // 2, end), (1 + amp * 0.5, 1 + amp), "halt")]
        f += period
    return out


def babble(start, end, rng, rest=7):
    """Silent talking: a new mouth stage every 3-6 frames, back to the rest stage at the end."""
    out, f = [], start
    while f < end:
        out.append((f, rng.choice([2, 3, 4, 5, 6, 3, 1])))
        f += rng.randint(3, 6)
    out.append((end, rest))
    return out


def steps(f0, f1, n, height=0.35, squash=0.12, rock=3.0):
    """n hop/walk steps between f0 and f1 -> {"pos", "sq", "tilt"} keys (body only; move the feet with "path")."""
    pos, sq, tilt = [(f0, (0, 0))], [(f0, (1, 1))], [(f0, 0)]
    d = (f1 - f0) / n
    for i in range(n):
        a = f0 + i * d
        m, e = a + d / 2, a + d
        pos += [(round(m), (0, height), "halt"), (round(e), (0, 0), "linear")]
        sq += [(round(a + 1), (1 + squash, 1 - squash)), (round(a + d * 0.3), (1 - squash * 0.6, 1 + squash * 0.7)),
               (round(e - 1), (1, 1))]
        tilt += [(round(m), rock * (1 if i % 2 else -1))]
    pos.append((round(f1) + 1, (0, 0)))
    sq += [(round(f1) + 1, (1 + squash, 1 - squash)), (round(f1) + 6, (1, 1))]
    tilt.append((round(f1) + 4, 0))
    return {"pos": pos, "sq": sq, "tilt": tilt}


def pop(f, t0, t1, rise=8, fall=6, overshoot=0.15):
    """Sprite size/opacity: pops in at t0 with overshoot, shrinks away after t1 -> (s, a)."""
    if f < t0 or f > t1 + fall:
        return 0.0, 0.0
    if f < t0 + rise:
        u = (f - t0) / rise
        s = 1 + overshoot * math.sin(u * math.pi) if u > 0.5 else smooth(u * 2) * (1 + overshoot)
        return round(s, 4), round(min(1.0, u * 2.5), 4)
    if f > t1:
        u = (f - t1) / fall
        return round(1 - u * 0.4, 4), round(1 - u, 4)
    return 1.0, 1.0


def merge_keys(*dicts):
    out = {}
    for d in dicts:
        for k, v in d.items():
            out[k] = sorted(out.get(k, []) + list(v), key=lambda x: x[0])
    return out


def confetti(t0, origin, n=40, seed=3, floor=-4.4, force=1.0):
    """Confetti burst: n paths f -> sprite dict | None (throw + drag + gravity + flutter + spin), origin [x, y, z]."""
    rng = random.Random(seed)
    paths = []
    for _ in range(n):
        a = rng.uniform(0.15 * math.pi, 0.85 * math.pi)
        v = rng.uniform(4.0, 8.5) * force
        vx, vy, vz = math.cos(a) * v, math.sin(a) * v, rng.uniform(-1, 2.5)
        rot, flutter, delay = rng.uniform(-14, 14), rng.uniform(4, 9), rng.randint(0, 3)

        def path(f, vx=vx, vy=vy, vz=vz, rot=rot, flutter=flutter, delay=delay):
            t = (f - t0 - delay) / 24
            if t < 0:
                return None
            drag = 1 - math.exp(-t * 1.6)
            x = origin[0] + vx / 1.6 * drag + 0.25 * math.sin(t * flutter)
            y = max(floor, origin[1] + vy / 1.6 * drag - 2.2 * t * t)
            z = origin[2] + vz / 1.6 * drag
            return {"p": [round(x, 3), round(y, 3), round(z, 3)], "s": 1.0, "a": round(max(0.0, min(1.0, 3.5 - t)), 3),
                    "rot": round(rot * t, 3)}
        paths.append(path)
    return paths


def arc(t0, start, end, dur=18, height=0.8):
    """f -> [x, y, z] on an eased arc from start to end (None before t0) - things tossed, hopping props."""
    def at(f):
        if f < t0:
            return None
        u = min(1.0, (f - t0) / dur)
        e = u * u * (3 - 2 * u)
        return [start[i] + (end[i] - start[i]) * e + (4 * height * u * (1 - u) if i == 1 else 0) for i in range(3)]
    return at


def cut_camera(shots, f):
    """Camera with hard cuts: shots = [(first_frame, fn(f) -> (cam, look) | key list [(f, [cx,cy,cz,lx,ly,lz])])];
    the last shot that has started is used. Returns (cam, look)."""
    cur = None
    for f0, sh in shots:
        if f >= f0:
            cur = sh
    if callable(cur):
        return cur(f)
    c = keyed(cur, f)
    return list(c[:3]), list(c[3:])


def steam_texture(path):
    from PIL import Image, ImageDraw
    import numpy as np
    W, H = 160, 320
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ys = np.linspace(H - 10, 10, 60)
    d.line([(W / 2 + 28 * math.sin((H - y) / 55.0) * (0.5 + (H - y) / H), y) for y in ys], fill=(60, 60, 64, 255),
           width=7, joint="curve")
    im.save(path)


# ---------------------------------------------------------------- the scene
class Scene:
    def __init__(self, folder, deck="../../deck/deck.json", figures_dir="../../figures", end=None, fps=24,
                 size=(1920, 1080), seed=1, look="standard", fov=30, boil=0.0016, background="#1c1a18"):
        self.dir = Path(folder).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.p = {"deck": deck, "figures_dir": figures_dir, "fps": fps, "seed": seed, "look": look,
                  "narration": [], "sounds": []}
        self.fig_root = (self.dir / figures_dir).resolve()
        self.fps, self.size, self.end, self.fov, self.boil, self.background = fps, tuple(size), end, fov, boil, background
        self.layers, self.overlays, self.sprites, self.steam, self.figs = [], [], [], [], {}
        self.cam_keys, self.hooks, self.posts = [(0, [0, 0, 16.79, 0, 0, 0])], [], []
        self.T = CL.Times(self)

    # -- building blocks
    def layer(self, name, src, w, h, x=0, y=0, z=0, order=0, rotx=None):
        self.layers.append({"name": name, "src": src, "w": w, "h": h, "x": x, "y": y, "z": z, "order": order,
                            **({"rotx": rotx} if rotx is not None else {})})

    def overlay(self, name, src, aspect, fit=1.0, order=0):
        self.overlays.append({"name": name, "src": src, "aspect": aspect, "fit": fit, "order": order})

    def sprite(self, name, src, aspect, h, order=50, fig=None, billboard=False, add=False):
        self.sprites.append({"name": name, "src": src, "aspect": aspect, "h": h, "order": order,
                             **({"fig": fig} if fig else {}), "billboard": billboard, "add": add})

    def add_steam(self, x, y, z, order=30):
        self.steam.append({"x": x, "y": y, "z": z, "order": order})

    def narration(self, lid, audio, at, speaker=None, text=None, level=0):
        self.p["narration"].append({"id": lid, "audio": audio, "at": at, "speaker": speaker, "text": text,
                                    "level": level})
        self.T.cfg[lid] = self.p["narration"][-1]

    def sound(self, at, sfx, args=(), level=-20, pan=0.0, align="peak"):
        """align="peak": the loudest moment of the effect sits on the frame (default); "start": the file starts there
        (swells, blooms, risers)."""
        self.p["sounds"].append({"at": at, "sfx": sfx, "args": list(args), "level": level, "pan": pan, "align": align})

    def figure(self, name, x, y, z=0.25, scale=0.45, order=10, keys=None, idle=True, billboard=False, shadow=False,
               tint=None, rim=None, path=None, shade=1.0, gesture_part=None, talk=()):
        """path: [(frame, [x, y, z])] moves the feet in the room (keyed, smooth)."""
        self.figs[name] = {"x": x, "y": y, "z": z, "scale": scale, "order": order, "keys": keys or {}, "idle": idle,
                           "billboard": billboard, "shadow": shadow, "tint": tint, "rim": rim, "path": path,
                           "shade": shade, "gesture_part": gesture_part, "talk": list(talk)}

    def camera(self, keys):
        self.cam_keys = [(k[0], list(k[1])) for k in keys]

    def per_frame(self, fn):
        """fn(frame, frame_dict) may change cam/look/layers/lpos/overlays/figs/sprites/steam of that frame
        (figs[name] also takes "opacity" and "soft" = contact shadow opacity for figures with shadow=True)."""
        self.hooks.append(fn)

    def post(self, fn):
        """fn(frame, PIL RGB image) -> image, applied to every rendered frame before the look: counters, captions,
        colour grading, split screens (see split_frame). Frames go to frames_post/, scene_stage.mp4 is re-encoded."""
        self.posts.append(fn)

    def mouth_rest(self, name):
        """Rest mouth stage of a figure (open grin = 7, closed line / beak = 0) - for silent or thinking figures."""
        pj = json.loads((self.fig_root / name / "parts.json").read_text(encoding="utf-8"))
        return 7 if pj.get("mouth", {}).get("kind", "open") == "open" else 0

    def head_top(self, name):
        """Top of the head in the figure's Synfig units (origin = sole): drop things on a head."""
        import numpy as np
        from PIL import Image
        g = self.geometry(name)
        a = np.asarray(Image.open(g["dir"] / "head.png"))[..., 3] > 128
        ys, xs = np.nonzero(a)
        return g["su"](xs[ys < ys.min() + 10].mean(), ys.min())

    # -- geometry of a figure at this scene's scale
    def geometry(self, name):
        d = self.fig_root / name
        rig = json.loads((d / "rig.json").read_text(encoding="utf-8"))
        pj = json.loads((d / "parts.json").read_text(encoding="utf-8"))
        fx, fy = rig["feet"]
        su_px = rig["su_px"]
        l, t, r, b = rig["view"]
        s = self.figs[name]["scale"]
        return {"name": name, "dir": d, "rig": rig, "parts_cfg": pj, "su_world": s,
                "plane_w": (r - l) * s, "center_above_feet": (t + b) / 2 * s, "center_dx": (l + r) / 2 * s,
                "px": int(round((r - l) * CL.PX_PER_SU)), "su": lambda x, y: ((x - fx) / su_px, (fy - y) / su_px)}

    def eye_center(self, name):
        """Eye centre in the figure's Synfig units (origin = sole) - aim close-ups at it, hang star eyes on it."""
        import numpy as np
        from PIL import Image
        g = self.geometry(name)
        a = np.asarray(Image.open(g["dir"] / "eyes.png"))[..., 3] > 128
        ys, xs = np.nonzero(a)
        return g["su"](xs.mean(), ys.mean())

    def pupils(self, name):
        """Centres of the pupils (the two biggest blobs of eyes.png, left -> right) in Synfig units - star eyes."""
        import numpy as np
        from PIL import Image
        from scipy import ndimage as ndi
        g = self.geometry(name)
        a = np.asarray(Image.open(g["dir"] / "eyes.png"))[..., 3] > 128
        lab, n = ndi.label(a)
        sizes = ndi.sum(a, lab, range(1, n + 1))
        keep = [int(i) + 1 for i in np.argsort(sizes)[::-1][:2]]
        cs = sorted(ndi.center_of_mass(a, lab, keep), key=lambda c: c[1])
        return [g["su"](c[1], c[0]) for c in cs]

    def painted_set(self, back, front=None, w=16.0, aspect=1920 / 1088, front_z=0.5, order_front=20):
        """A painted set filling the frontal view: back layer at z=0 (w x w/aspect) and an optional front layer
        (table, counter) at front_z, scaled so that it lines up with the back from the default camera."""
        h = w / aspect
        self.set_dims = (w, h)
        self.layer("set", back, w, h, z=0, order=0)
        if front:
            k = (16.79 - front_z) / 16.79
            self.layer("set_front", front, w * k, h * k, z=front_z, order=order_front)

    def set_point(self, px, py, z=0.0, image_w=1920, image_h=1088):
        """Pixel (px, py) of the painted set image -> world (x, y) on a set layer at depth z (scaled like painted_set)."""
        w, h = getattr(self, "set_dims", (16.0, 16.0 * image_h / image_w))
        k = (16.79 - z) / 16.79
        return (px / image_w - 0.5) * w * k, (0.5 - py / image_h) * h * k

    # -- plan: Synfig scenes + per-frame stage config
    def build(self):
        end = self.end
        if end is None:
            ends = [self.T.line_at(n["id"]) + round(self.T.words(n["id"])["duration"] * self.fps)
                    for n in self.p["narration"]]
            end = max(ends) + 16 if ends else 120
            self.end = end
        G = {}
        for n, f in self.figs.items():
            g = self.geometry(n)
            G[n] = g
            k = {kk: list(v) for kk, v in f["keys"].items()}
            talk = [ln["id"] for ln in self.p["narration"] if ln.get("speaker") == n] + f["talk"]
            if talk:
                import mouth
                mouth.ensure(g["dir"])
                mk = mouth.mouth_keys(g["dir"], [(self.dir / self.T.cfg[t]["audio"], self.T.line_at(t),
                                                  self.T.cfg[t].get("text"), self.T.cfg[t].get("lang") or self.p.get("lang"))
                                                 for t in talk], fps=self.fps,
                                      cache=self.dir / "narration")
                k["mouth"] = sorted(k.get("mouth", []) + mk, key=lambda x: x[0])
            if "mouth" in k and not (g["dir"] / "head_base.png").exists():
                import mouth
                mouth.make(g["dir"])
            if f["idle"]:
                rng = random.Random(f"{self.p['seed']}:{n}")
                k.update(A.idle_keys(rng, end, [(0, 1, 1, 1)]))
                if len(k.get("blink", [])) <= 1:
                    k["blink"] = A.auto_blinks(rng, 0, end)
            # the rig's channel names: head / eyes / blink / sq / spin / tilt / pos / mouth / <part>
            CL.write_sif(self, g, k, end, gesture_part=f["gesture_part"])
        frames = []
        for fr in range(end + 1):
            c = keyed(self.cam_keys, fr)
            figs = {}
            for n, f in self.figs.items():
                feet = keyed(f["path"], fr) if f["path"] else [f["x"], f["y"], f["z"]]
                figs[n] = {"feet": [round(v, 4) for v in feet], "shade": f["shade"]}
                if f["shadow"]:
                    figs[n]["soft"] = f["shadow"] if isinstance(f["shadow"], float) else 0.3
            F = {"cam": [round(v, 4) for v in c[:3]], "look": [round(v, 4) for v in c[3:]], "figs": figs,
                 "overlays": {}, "layers": {}, "sprites": {}}
            for h in self.hooks:
                h(fr, F)
            frames.append(F)
        tex = self.dir / "tex"
        tex.mkdir(exist_ok=True)
        for item in self.layers + self.overlays + self.sprites:      # the page only serves the scene folder
            src = (self.dir / item["src"]).resolve()
            if self.dir not in src.parents:
                dst = tex / ("ext_" + src.name)
                if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                    shutil.copy(src, dst)
                item["src"] = f"tex/{dst.name}"
        if self.steam:
            steam_texture(tex / "steam.png")
        texmap = {"steam": "tex/steam.png"}
        if any(f["shadow"] for f in self.figs.values()) or any("tex/floor.png" == L["src"] for L in self.layers):
            CL.room_textures(tex)                      # floor, contact shadow (as in the step-out clips)
            texmap["shadow"] = "tex/shadow.png"
        cfg = {"width": self.size[0], "height": self.size[1], "fps": self.fps, "end": end, "fov": self.fov,
               "out": "frames_3d", "boil": self.boil, "background": self.background,
               "layers": self.layers, "overlays": self.overlays, "sprites": self.sprites, "steam": self.steam,
               "tex": texmap,
               "figs": {n: {"src": f"frames/{n}/{n}.%04d.png", "light": f"light/{n}/s.%04d.png",
                            "plane_w": G[n]["plane_w"], "center_above_feet": G[n]["center_above_feet"],
                            "center_dx": G[n]["center_dx"], "order": f["order"], "billboard": f["billboard"],
                            "shadow": f["shadow"], "su_world": f["scale"],
                            **({"tint": f["tint"]} if f["tint"] else {}), **({"rim": f["rim"]} if f["rim"] else {})}
                        for n, f in self.figs.items()},
               "frames": frames}
        (self.dir / "scene_stage.json").write_text(json.dumps(cfg), encoding="utf-8")
        lines = {ln["id"]: {"at": self.T.line_at(ln["id"]), "audio": ln["audio"], "level": ln.get("level", 0)}
                 for ln in self.p["narration"]}
        (self.dir / "plan.json").write_text(json.dumps({"end": end, "events": {}, "narration": lines, "variants": {}},
                                                       indent=1), encoding="utf-8")
        self._G = G
        print(f"  scene: {end + 1} frames, {len(self.figs)} figures, {len(self.layers)} layers")

    def render(self, jobs=None, steps=("synfig", "light", "3d", "post", "final", "sound")):
        import os
        from render import render_sif
        jobs = jobs or max(2, (os.cpu_count() or 8) // 2)
        if "synfig" in steps:
            for n in self.figs:
                out = self.dir / "frames" / n
                if out.exists():
                    shutil.rmtree(out)
                render_sif(self.dir / f"{n}.sif", out, width=self._G[n]["px"], height=self._G[n]["px"], jobs=jobs)
        if "light" in steps:
            jobs_l = []
            for n in self.figs:
                (self.dir / "light" / n).mkdir(parents=True, exist_ok=True)
                jobs_l += [(p, self.dir / "light" / n / ("s." + p.name.split(".")[-2] + ".png"))
                           for p in sorted((self.dir / "frames" / n).glob(f"{n}.*.png"))]
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(min(6, os.cpu_count() or 4)) as ex:
                list(ex.map(CL.light_map, jobs_l))
        if "3d" in steps:
            shutil.copy(HERE.parent / "assets" / "scene25d.html", self.dir / "scene25d.html")
            subprocess.run([sys.executable, str(_studio.skill_dir("toon-2d") / "scripts" / "render_multiplane.py"),
                            str(self.dir / "scene_stage.json"), "--page", "/scene25d.html", "--contact", "none",
                            "--startup", "180", "--timeout", str(max(1800, 6 * (self.end + 1)))], check=True)
        if "post" in steps and self.posts:
            self.apply_post()
        name = self.dir / f"{self.dir.name}.mp4"
        if "final" in steps:
            finish(self.dir / STAGE_MP4, name, self.p["look"])   # render_multiplane names it after the config
        if "sound" in steps and (self.p["narration"] or self.p["sounds"]):
            import sound
            sound.mux(name, sound.make(self.dir, self.sound_spec(), self.T))
        print("  ->", name)

    def frames_dir(self):
        """Folder of the finished stage frames (post-processed when there are post hooks)."""
        return self.dir / ("frames_post" if self.posts else "frames_3d")

    def apply_post(self):
        from PIL import Image
        src, out = self.dir / "frames_3d", self.dir / "frames_post"
        out.mkdir(exist_ok=True)
        for p in out.glob("mp_*.png"):
            p.unlink()
        for f in range(self.end + 1):
            im = Image.open(src / f"mp_{f:04d}.png").convert("RGB")
            for fn in self.posts:
                im = fn(f, im)
            im.save(out / f"mp_{f:04d}.png")
        encode(out, self.dir / STAGE_MP4, self.fps)

    def sound_spec(self, offset=0):
        """Narration + sound cues with resolved frames; "align" is passed on (the mixer places a "start" cue by its
        first sample, a "peak" cue by its loudest moment - no extra shift here)."""
        P = dict(self.p)
        P["sounds"] = [{**x, "at": self.T(x["at"]) + offset} for x in self.p["sounds"]]
        return P


# ---------------------------------------------------------------- finishing, several scenes in one clip
def encode(frames, mp4, fps=24):
    from encoding import h264
    subprocess.run([config.need("ffmpeg"), "-y", "-v", "error", "-framerate", str(fps), "-i",
                    str(Path(frames) / "mp_%04d.png"), *h264(), "-pix_fmt", "yuv420p", str(mp4)], check=True)


def finish(raw, out, look="standard"):
    if look and look != "none":
        subprocess.run([sys.executable, str(_studio.skill_dir("film-finish") / "scripts" / "apply_look.py"),
                        str(raw), "-o", str(out), "--look", look], check=True)
    else:
        shutil.copy(raw, out)


def split_frame(main, side, t, side_left=True, divider=(52, 50, 47), ink=(20, 20, 22)):
    """Split screen: the side image slides in to half the frame (t 0 -> 1) showing its centre half; the main image
    keeps its centre. Use as a post hook on the main scene with the side scene's rendered frames."""
    from PIL import Image, ImageDraw
    W, H = main.size
    w = round(W / 2 * t)
    img = Image.new("RGB", (W, H))
    x0 = round(W / 4 * t)
    if side_left:
        if w > 0:
            img.paste(side.crop((W * 3 // 4 - w, 0, W * 3 // 4, H)), (0, 0))
        img.paste(main.crop((x0, 0, W - x0, H)), (w, 0))
        e = w
    else:
        img.paste(main.crop((x0, 0, W - x0, H)), (0, 0))
        if w > 0:
            img.paste(side.crop((W // 4, 0, W // 4 + w, H)), (W - w, 0))
        e = W - w
    d = ImageDraw.Draw(img)
    d.rectangle((e - 9, 0, e + 9, H), fill=divider)
    d.line([(e - 10, 0), (e - 10, H)], fill=ink, width=4)
    d.line([(e + 10, 0), (e + 10, H)], fill=ink, width=4)
    return img


def join(folder, scenes, look="standard", fps=24):
    """One clip from several rendered scenes played one after the other (hard cuts; transitions belong into the
    scenes): frames -> <folder>/frames_joined, look -> <folder>/<name>.mp4, narration + sounds of all parts on one track.
    (Not frames_3d: a joined scene may live in the join folder itself, its frames must survive.)"""
    import sound
    folder = Path(folder).resolve()
    out = folder / "frames_joined"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    narr, sounds, k, starts = {}, [], 0, []
    for S in scenes:
        starts.append(k)
        for f in range(S.end + 1):
            shutil.copy(S.frames_dir() / f"mp_{f:04d}.png", out / f"mp_{k + f:04d}.png")
        for ln in S.p["narration"]:
            narr[ln["id"]] = {"at": k + S.T.line_at(ln["id"]), "audio": str((S.dir / ln["audio"]).resolve()),
                              "level": ln.get("level", 0)}
        sounds += S.sound_spec(offset=k)["sounds"]
        k += S.end + 1
    end = k - 1
    (folder / "plan.json").write_text(json.dumps({"end": end, "events": {}, "narration": narr, "variants": {},
                                                  "parts": starts}, indent=1), encoding="utf-8")
    encode(out, folder / "scene.mp4", fps)
    name = folder / f"{folder.name}.mp4"
    finish(folder / "scene.mp4", name, look)
    if narr or sounds:
        sound.mux(name, sound.make(folder, {"fps": fps, "sounds": sounds}))
    print(f"  joined {len(scenes)} scenes: {end + 1} frames, parts start at {starts} -> {name}")
    return starts


def save_events(folder, events):
    """events.json of a recipe: the frames of its story beats (for review, sound and comparisons)."""
    (Path(folder) / "events.json").write_text(json.dumps(events, indent=1), encoding="utf-8")
    print("  events:", json.dumps(events)[:300])


def recipe_config(folder, defaults):
    """A recipe's defaults updated from <folder>/recipe.json (dict values merged one level deep) - vary cast, texts,
    voices, set images and the seed without touching the recipe."""
    P = json.loads(json.dumps(defaults))
    f = Path(folder) / "recipe.json"
    if f.exists():
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            if isinstance(v, dict) and isinstance(P.get(k), dict):
                P[k].update(v)
            else:
                P[k] = v
    return P


def from_json(path):
    path = Path(path).resolve()
    P = json.loads(path.read_text(encoding="utf-8"))
    S = Scene(path.parent, P.get("deck", "../../deck/deck.json"), P.get("figures_dir", "../../figures"), P.get("end"),
              P.get("fps", 24), P.get("size", (1920, 1080)), P.get("seed", 1), P.get("look", "standard"))
    for L in P.get("layers", []):
        S.layer(**L)
    for O in P.get("overlays", []):
        S.overlay(**O)
    for sp in P.get("sprites", []):
        S.sprite(**sp)
    for st in P.get("steam", []):
        S.add_steam(**st)
    for ln in P.get("narration", []):
        S.narration(ln["id"], ln["audio"], ln.get("at", 0), ln.get("speaker"), ln.get("text"), ln.get("level", 0))
    for x in P.get("sounds", []):
        S.sound(x["at"], x["sfx"], x.get("args", ()), x.get("level", -20), x.get("pan", 0), x.get("align", "peak"))
    for n, f in P.get("figures", {}).items():
        S.figure(n, **f)
    if P.get("camera"):
        S.camera(P["camera"])
    return S


if __name__ == "__main__":
    import project_check
    project_check.require(sys.argv[1], skill="animated-powerpoint")   # scene.json validated before the build
    S = from_json(sys.argv[1])
    S.build()
    if "--plan" not in sys.argv:
        S.render()
