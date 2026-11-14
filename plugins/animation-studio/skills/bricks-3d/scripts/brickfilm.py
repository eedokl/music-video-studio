# Runs inside Blender's own Python (started by blender_run.py) - no uv / PEP 723 header.
"""Render one section of a brick film inside Blender from a plan (JSON written by a user skill's planner).

Run through blender_run.py (GPU lock, Blender from the config):
  python blender_run.py brickfilm.py -- <plan.json> --render            frames -> plan["out"]/f.0000.png ...
  python blender_run.py brickfilm.py -- <plan.json> --stills 10,120      test frames -> plan["stills"]/still_0010.png
  python blender_run.py brickfilm.py -- <plan.json> --blend              save <out>/../<section>.blend to look at
  extra switches: --percent 50 (resolution), --samples 16, --no-exposure, --remeasure, --cycles, --from-frame N

Plan (all times are song seconds; points are LDraw coordinates, see layouts.py):
  section, from, to, fps, seed, out, stills, textures, exposure_file
  render   {width, height, samples, quality: "gaps=0.2,bevel=0.3,wobble=0.6,abs=1", jitter: 0.3}
  set      {kind, flip, palette{...}, coins, screen_tiles}
  beats    [t, ...]                         figures dip on every beat (bounce), glow/spots pulse
  figures  [{name, look, place [x,z], yaw, floor, bounce, mouth [[t, shape]], blinks [t], keys [[t, {pose}]],
             sign, sign_tex (name sign printed on the torso, textures.py --signs), screen: true for the talking monitor}]
           pose keys: yaw head arm_r arm_l hand_r hand_l leg_r leg_l (deg), hop lean x z (LDU/deg), hair (0..1 flies
           off), head_off (0..1 pops off and spins), grin (silhouette mouth tile), show (0 hides)
  screen   {tiles: n, events [[t0, t1, tile]], light [[r,g,b] per tile]}   room monitor
  props    [{kind: coins, times, gone (optional: per coin the time it vanishes)}, {kind: glow}, {kind: spots_cycle}, {kind: bulbs_chase}, {kind: dim, t, factor},
            {kind: set_flight, t, d, mode: in|out}        the set's bricks fly in and assemble / fly apart (effects.py)
            {kind: brick_word, text, t, d, at [x,y_top,z], colours, pixel, fall, until}   word of flying 1x1 bricks
            {kind: confetti, t, until, n, centre [x,z], spread [dx,dz]}
            {kind: tower, times, at [x,y_floor,z], colours}  a stack growing one brick per time
            {kind: fall_apart | assemble, figure, t, d}     a minifig falls apart / builds itself part by part
            {kind: steam, times, figure | at [x,y,z], big [i]} puffs rise from a head (or a point) and grow
            {kind: strings, figure, targets [names], t, until} marionette strings puppeteer hands -> target heads]
  shots    [{t0, t1, cam [[x,y,z],[x,y,z]], aim [[..],[..]], lens, focus [x,y,z], fstop, shake,
             path: {cam: [[x,y,z], ...], aim: [...], focus: [...]} (optional: one eased flight through all points)}]
Stop motion: figures, props and lights are keyed on twos (12 poses/s) with a slight per-pose jitter; mouths and blinks
on ones; every key is CONSTANT. Exposure: measured per shot on small test renders (night target, only darker), smoothed
so cuts in the same light do not jump; stored in exposure_file and reused.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import effects as E  # noqa: E402
import ldraw as L  # noqa: E402
import minifig  # noqa: E402
import shading as H  # noqa: E402
import sets  # noqa: E402
from layouts import MOODS  # noqa: E402

SHAPES = "XABCDEFGH"
NEUTRAL = dict(yaw=0, arm_r=8, arm_l=8, hand_r=0, hand_l=0, head=0, hop=0, lean=0, leg_r=0, leg_l=0, hair=0, x=0, z=0,
               head_off=0, grin=0, show=1)
CAST = json.loads((HERE.parent / "assets" / "cast.json").read_text(encoding="utf-8"))


def arg(args, name, default=None, cast=str):
    return cast(args[args.index(name) + 1]) if name in args else default


class Film:
    def __init__(self, plan_path, args):
        self.plan = pl = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        self.args = args
        self.fps = pl.get("fps", 24)
        self.t0, self.t1 = pl["from"], pl["to"]
        self.N = int(round((self.t1 - self.t0) * self.fps))
        self.tex = Path(pl["textures"])
        r = pl.get("render", {})
        L.set_quality(r.get("quality", "gaps=0.2,bevel=0.3,wobble=0.6,abs=1"))
        L.seed_wobble(pl.get("seed", 1))
        self.jitter = float(r.get("jitter", 0.3))
        self.rng = np.random.default_rng(int(pl.get("seed", 1)) + 17)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.sc = sc = bpy.context.scene
        sc.render.fps = self.fps
        sc.frame_start, sc.frame_end = 0, self.N - 1
        sc.render.resolution_x, sc.render.resolution_y = r.get("width", 1280), r.get("height", 720)
        sc.render.resolution_percentage = arg(args, "--percent", 100, int)
        sc.render.engine = "BLENDER_EEVEE"
        for k, v in (("taa_render_samples", arg(args, "--samples", r.get("samples", 48), int)), ("use_raytracing", True),
                     ("use_shadows", True), ("shadow_ray_count", 3), ("shadow_step_count", 12)):
            if hasattr(sc.eevee, k):                    # 1/6 shadow rays sparkle under close area lights
                setattr(sc.eevee, k, v)
        sc.view_settings.view_transform = "AgX"
        if "--cycles" in args:
            sc.render.engine = "CYCLES"
            sc.cycles.samples = 128
            sc.cycles.use_denoising = True
            try:
                prefs = bpy.context.preferences.addons["cycles"].preferences
                prefs.compute_device_type = "OPTIX"
                prefs.get_devices()
                for d in prefs.devices:
                    d.use = d.type == "OPTIX"
                sc.cycles.device = "GPU"
            except Exception:
                pass
        self.beats = pl.get("beats", [])
        spec = dict(pl["set"])
        spec["screen_tiles"] = pl.get("screen", {}).get("tiles", 1)
        spec.setdefault("seed", int(pl.get("seed", 1)))
        self.Z = sets.build(spec["kind"], spec, self.tex)
        mood = MOODS[spec["palette"].get("mood", "night_blue")]
        self.world(tuple(spec["palette"].get("sky") or mood["world"]))
        self.camera()
        self.figs = {}
        for fd in pl.get("figures", []):
            self.figure(fd)
        self.effects(pl.get("props", []), int(pl.get("seed", 1)))
        ef = pl.get("exposure_file")
        self.exposure = json.loads(Path(ef).read_text(encoding="utf-8")) if ef and Path(ef).exists() and \
            "--remeasure" not in args else {}
        if self.exposure and set(self.exposure) != {f"{x['t0']:g}" for x in pl["shots"]}:
            print("exposure cache is from another shot plan - measuring again", flush=True)
            self.exposure = {}

    def effects(self, props, seed):
        """Brick effects of the plan (effects.py); figure effects are applied in matrices()."""
        self.fx, self.fig_fx = [], {}
        for i, p in enumerate(props):
            k, sd = p["kind"], seed * 101 + i
            if k == "set_flight":
                self.fx.append(E.SetFlight(self.Z["parts"], p["t"], p.get("d", 1.0), p.get("mode", "in"), sd))
            elif k == "brick_word":
                self.fx.append(E.BrickWord(p["text"], p["t"], p.get("d", 1.4), p["at"], p.get("colours", [4, 14, 1, 2]), sd,
                                           p.get("pixel", 20), p.get("fall"), p.get("until")))
            elif k == "confetti":
                self.fx.append(E.Confetti(int(p.get("n", 120)), p["t"], p.get("until"), p.get("centre", [0, -60]),
                                          p.get("spread", [320, 220]), sd))
            elif k == "tower":
                self.fx.append(E.Tower(p["times"], p["at"], p.get("colours", [1, 4, 14, 2]), sd, p.get("part", "3003")))
            elif k in ("fall_apart", "assemble") and p.get("figure") in self.figs:
                self.fig_fx.setdefault(p["figure"], []).append(dict(p, seed=sd))
            elif k == "steam" and (p.get("figure") in self.figs or p.get("at")):
                self.fx.append(E.Steam(p["times"], sd, follow=p.get("figure") if p.get("figure") in self.figs else None,
                                       at=p.get("at"), colour=p.get("colour", 15), big=p.get("big", [])))
            elif k == "strings" and p.get("figure") in self.figs:
                self.fx.append(E.Strings(p["figure"], [n for n in p.get("targets", []) if n in self.figs], p["t"],
                                         p.get("until"), sd))

    # ------------------------------------------------------------ helpers
    def bounce(self, t, strength):
        d = min([t - b for b in self.beats if b <= t] or [1.0])
        return strength * math.exp(-d / 0.12)

    def world(self, colour, strength=1.0):
        w = bpy.data.worlds.new("World")
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (*colour, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = strength
        self.sc.world = w

    def camera(self):
        sc = self.sc
        self.cam = cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.clip_start = 0.002
        cam.data.clip_end = 50
        cam.data.dof.use_dof = True
        self.focus = bpy.data.objects.new("Focus", None)
        sc.collection.objects.link(self.focus)
        cam.data.dof.focus_object = self.focus
        self.aim = bpy.data.objects.new("CameraAim", None)
        sc.collection.objects.link(self.aim)
        cam.constraints.new("TRACK_TO").target = self.aim

    # ------------------------------------------------------------ figures
    def figure(self, fd):
        name = fd["name"]
        if fd.get("screen"):                              # the talking monitor is not a minifig
            self.figs[name] = dict(fd=fd, obs={}, screen=True)
            return
        look = CAST["looks"][fd.get("look", "tim")]
        colours = dict(look["colours"])
        obs = minifig.build(name, colours, L.T(0, -72, 0), parts=look.get("parts"))
        style = look.get("face", "classic")
        ground = tuple(look["silhouette"]) if look.get("silhouette") else None
        blink, mouth = H.face(obs["head"], colours["head"], self.tex / f"{style}_eyes.png", self.tex / f"{style}_mouths.png",
                              f"{name}_face", ground)
        if fd.get("sign_tex") and (self.tex / fd["sign_tex"]).exists():     # name sign instead of the look's print
            H.front_print(obs["torso"], colours["torso"], self.tex / fd["sign_tex"], f"{name}_sign")
        elif look.get("torso_print"):
            H.front_print(obs["torso"], colours["torso"], self.tex / f"torso_{look['torso_print']}.png", f"{name}_torso")
        if "hair" in obs and (look.get("hair_streak") or look.get("hair_clip")):
            H.hair_accent(obs["hair"], look.get("hair_streak"), self.tex / look["hair_clip"] if look.get("hair_clip") else None)
        if look.get("silhouette"):
            H.flat_material([o for k, o in obs.items() if k != "head"], f"{name}_silhouette", tuple(look["silhouette"]))
        for ob in obs.values():
            ob.rotation_mode = "QUATERNION"
        neutral = dict(NEUTRAL, yaw=fd.get("yaw", 0.0), x=fd["place"][0], z=fd["place"][1])
        keys = [(t, d) for t, d in fd.get("keys", [])] or [(self.t0, {})]
        self.figs[name] = dict(fd=fd, obs=obs, plan=H.Timeline(neutral, keys), blink=blink, mouth=mouth,
                               cues=fd.get("mouth", []), blinks=fd.get("blinks", []), silhouette=bool(look.get("silhouette")))

    @staticmethod
    def shape_at(cues, t):
        s = "X"
        for tc, c in cues:
            if tc <= t + 1e-6:
                s = c
            else:
                break
        return SHAPES.index(s) if s in SHAPES else 0

    def matrices(self, fig, t, jit):
        p = fig["plan"](t)
        fd = fig["fd"]
        h = minifig.HEIGHT
        floor = fd.get("floor", 0.0)
        F = L.T(p["x"] + jit[0], floor - h + self.bounce(t, fd.get("bounce", 1.2)) - p["hop"], p["z"] + jit[1]) @ \
            L.RY(p["yaw"] + jit[2]) @ L.T(0, h, 0) @ L.RX(p["lean"]) @ L.T(0, -h, 0)
        w = dict(p)
        for k in ("arm_r", "arm_l", "head"):
            w[k] = p[k] + jit[3] * (1.6 if k != "head" else 1.0)
        mats = minifig.pose(F, w)
        fig["hidden"] = set()
        if self.fig_fx.get(fd["name"]):
            mats, fig["hidden"] = E.figure_fx(self.fig_fx[fd["name"]], mats, t, floor, self.fig_fx[fd["name"]][0]["seed"])
        if p.get("hair", 0) > 0.01:                       # hair flies off and spins
            mats["hair"] = mats["head"] @ L.T(0, -46 * p["hair"], 0) @ L.RY(220 * p["hair"]) @ L.RX(25 * p["hair"])
        if p.get("head_off", 0) > 0.01:                   # head pops off and spins
            k = p["head_off"]
            mats["head"] = mats["head"] @ L.T(0, -60 * k, 0) @ L.RY(540 * k)
            if p.get("hair", 0) <= 0.01:
                mats["hair"] = mats["head"]
        return p, mats

    # ------------------------------------------------------------ shots
    def shot(self, t):
        sh = self.plan["shots"]
        for s in sh:
            if s["t0"] <= t < s["t1"]:
                return s
        return sh[-1] if t >= sh[-1]["t0"] else sh[0]

    def ev_at(self, t, table):
        return float(table.get(f"{self.shot(t)['t0']:g}", 0.0))

    # ------------------------------------------------------------ run
    def run(self):
        sc, pl, Z = self.sc, self.plan, self.Z
        scr = pl.get("screen", {})
        props = pl.get("props", [])
        coin_times = next((p["times"] for p in props if p["kind"] == "coins"), [])
        coin_gone = next((p.get("gone") or [] for p in props if p["kind"] == "coins"), [])
        glow = any(p["kind"] == "glow" for p in props)
        spots_cycle = any(p["kind"] == "spots_cycle" for p in props)
        chase = any(p["kind"] == "bulbs_chase" for p in props)
        dims = sorted([(p["t"], p["factor"]) for p in props if p["kind"] == "dim"])
        screen_fig = next((f for f in self.figs.values() if f.get("screen")), None)
        jit = np.zeros(4)
        for f in range(self.N):
            t = self.t0 + f / self.fps
            sc.frame_current = f
            # ---- ones: mouths, blinks, camera, exposure, screen
            for fig in self.figs.values():
                if fig.get("screen"):
                    continue
                if fig["silhouette"]:
                    fig["mouth"].default_value = float(round(fig["plan"](t)["grin"]))
                else:
                    fig["mouth"].default_value = float(self.shape_at(fig["cues"], t))
                fig["mouth"].keyframe_insert("default_value", frame=f)
                fig["blink"].default_value = 1.0 if any(a <= t < a + 0.1 for a in fig["blinks"]) else 0.0
                fig["blink"].keyframe_insert("default_value", frame=f)
            s = self.shot(t)
            u = H.ease((t - s["t0"]) / max(s["t1"] - s["t0"], 1e-6))
            shake = float(s.get("shake", 0.0))
            wob = np.array([math.sin(t * 7.1), math.sin(t * 5.3 + 1), math.sin(t * 6.7 + 2)]) * shake
            if s.get("path"):                             # one eased flight through all points (house fly-in)
                cam_p, aim_p = along(s["path"]["cam"], u), along(s["path"]["aim"], u)
                foc_p = along(s["path"].get("focus") or s["path"]["aim"], u)
            else:
                pa, pb = np.array(s["cam"][0], float), np.array(s["cam"][1], float)
                za, zb = np.array(s["aim"][0], float), np.array(s["aim"][1], float)
                cam_p, aim_p, foc_p = pa + (pb - pa) * u, za + (zb - za) * u, np.array(s["focus"], float)
            self.cam.location = H.bl(*(cam_p + wob))
            self.aim.location = H.bl(*aim_p)
            self.focus.location = H.bl(*foc_p)
            self.cam.data.lens = s["lens"]
            self.cam.data.dof.aperture_fstop = s.get("fstop", 32.0 if s["lens"] <= 40 else 22.0)
            sc.view_settings.exposure = self.ev_at(t, self.exposure)
            for ob, prop in ((self.cam, "location"), (self.aim, "location"), (self.focus, "location")):
                ob.keyframe_insert(prop, frame=f)
            self.cam.data.keyframe_insert("lens", frame=f)
            self.cam.data.dof.keyframe_insert("aperture_fstop", frame=f)
            sc.view_settings.keyframe_insert("exposure", frame=f)
            if Z["screen"] is not None:
                ev = next((e for e in scr.get("events", []) if e[0] <= t < e[1]), None)
                talking = screen_fig is not None and \
                    any(abs(t - tc) < 0.5 and c != "X" for tc, c in screen_fig["fd"].get("mouth", []))
                tile = ev[2] if ev else scr.get("idle", 0)
                Z["screen"].key(f, tile, face=1.0 if (talking and not ev) else 0.0,
                                mouth=self.shape_at(screen_fig["fd"].get("mouth", []), t) if screen_fig else 0)
                col = scr.get("light", [])
                if col and "screen" in Z["lights"]:
                    Z["lights"]["screen"].data.color = tuple(col[min(tile, len(col) - 1)])
                    Z["lights"]["screen"].data.keyframe_insert("color", frame=f)
            if f % 2:
                continue
            # ---- twos: figures, props, lights
            if self.jitter > 0:
                jit = self.rng.uniform(-1, 1, 4) * self.jitter * np.array([0.5, 0.5, 0.6, 1.0])
            mats_all = {}
            for name, fig in self.figs.items():
                if fig.get("screen"):
                    continue
                p, mats = self.matrices(fig, t, jit * (1.0 if p_moving(fig, t) else 0.5))
                mats_all[name] = mats
                show = p.get("show", 1) > 0.5
                for k, ob in fig["obs"].items():
                    ob.matrix_world = L.to_blender(mats[k])
                    ob.keyframe_insert("location", frame=f)
                    ob.keyframe_insert("rotation_quaternion", frame=f)
                    ob.hide_render = not show or k in fig.get("hidden", ())
                    ob.keyframe_insert("hide_render", frame=f)
            pulse = self.bounce(t, 1.0)
            if glow and Z["gpu"] is not None:
                Z["gpu"].default_value = 0.8 + 1.0 * pulse
                Z["gpu"].keyframe_insert("default_value", frame=f)
            for k, c in enumerate(Z["coins"]):
                c.hide_render = not (k < len(coin_times) and t >= coin_times[k]) or                     (k < len(coin_gone) and coin_gone[k] is not None and t >= coin_gone[k])
                c.keyframe_insert("hide_render", frame=f)
            nb = len([b for b in self.beats if b <= t])
            if spots_cycle and Z["spots"]:
                cols = [s_["colour"] for s_ in Z["spots"]]
                for i, s_ in enumerate(Z["spots"]):
                    c = cols[(i + nb) % len(cols)]
                    s_["light"].data.color = c
                    s_["light"].data.energy = 2.5 * (0.7 + 0.6 * pulse)
                    s_["em"].inputs["Color"].default_value = (*c, 1)
                    s_["light"].data.keyframe_insert("color", frame=f)
                    s_["light"].data.keyframe_insert("energy", frame=f)
                    s_["em"].inputs["Color"].keyframe_insert("default_value", frame=f)
            if chase and Z["bulbs"]:
                for i, st in enumerate(Z["bulbs"]):
                    st.default_value = 2.2 if (i + nb) % 2 else 0.6
                    st.keyframe_insert("default_value", frame=f)
            for fx in self.fx:                            # brick effects on twos
                if isinstance(fx, E.Strings):             # strings follow the figures on every pose
                    fx.update(f, t, mats_all)
                    continue
                if getattr(fx, "follow", None) in mats_all:   # steam rises from the figure's head
                    fx.src = np.asarray(mats_all[fx.follow]["head"], float)[:3, 3]
                if fx.active(t) or f == 0 or f >= self.N - 2:
                    fx(f, t)
            if dims:
                fac = 1.0
                for td, fc in dims:
                    if t >= td:
                        fac = fc
                sets.dim(Z, f, fac)
        H.make_constant()
        self.output()

    # ------------------------------------------------------------ exposure
    def measure(self, target=0.40):
        """Exposure per shot from 3 small test renders each (mean luminance -> stops, only darker, at most 2.5),
        then smoothed: one base value for the section, each shot at most -0.5/+0.3 stops away from it."""
        sc = self.sc
        keep = (sc.render.resolution_percentage, sc.eevee.taa_render_samples, sc.render.filepath)
        sc.render.resolution_percentage = 30
        sc.eevee.taa_render_samples = 8
        d = Path(self.plan["stills"]) / "measure"
        d.mkdir(parents=True, exist_ok=True)
        res = {}
        for s in self.plan["shots"]:
            vals = []
            for u in (0.25, 0.5, 0.75):
                f = min(max(int(round((s["t0"] + u * (s["t1"] - s["t0"]) - self.t0) * self.fps)), 0), self.N - 1)
                sc.frame_set(f)
                sc.view_settings.exposure = 0.0
                sc.render.filepath = str(d / f"m_{f:04d}.png")
                bpy.ops.render.render(write_still=True)
                img = bpy.data.images.load(sc.render.filepath)
                px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)
                vals.append(float((px[:, :3] @ np.array([0.2126, 0.7152, 0.0722])).mean()))
                bpy.data.images.remove(img)
            m = max(float(np.mean(vals)), 1e-3)
            res[f"{s['t0']:g}"] = round(max(-2.5, min(0.0, 2.2 * math.log2(target / m))), 2)
        base = float(np.median(list(res.values()))) if res else 0.0
        for k in res:
            res[k] = round(max(-2.5, min(0.0, base + max(-0.5, min(0.3, res[k] - base)))), 2)
        print(f"exposure per shot (base {base:+.2f}): {res}", flush=True)
        ef = self.plan.get("exposure_file")
        if ef:
            Path(ef).write_text(json.dumps(res, indent=1), encoding="utf-8")
        self.exposure = res
        for f in range(self.N):
            sc.view_settings.exposure = self.ev_at(self.t0 + f / self.fps, res)
            sc.view_settings.keyframe_insert("exposure", frame=f)
        H.make_constant()
        sc.render.resolution_percentage, sc.eevee.taa_render_samples, sc.render.filepath = keep

    def output(self):
        sc, a = self.sc, self.args
        if ("--render" in a or "--stills" in a) and not self.exposure and "--no-exposure" not in a:
            self.measure()
        if "--blend" in a:
            out = Path(self.plan["out"])
            out.parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=str(out.parent / f"{self.plan['section']}.blend"))
        if "--stills" in a:
            d = Path(self.plan["stills"])
            d.mkdir(parents=True, exist_ok=True)
            for f in map(int, arg(a, "--stills").split(",")):
                sc.frame_set(min(max(f, 0), self.N - 1))
                sc.render.filepath = str(d / f"still_{f:04d}.png")
                bpy.ops.render.render(write_still=True)
        if "--render" in a:
            d = Path(self.plan["out"])
            d.mkdir(parents=True, exist_ok=True)
            sc.frame_start = arg(a, "--from-frame", 0, int)
            sc.render.filepath = str(d / "f.")
            sc.render.image_settings.file_format = "PNG"
            bpy.ops.render.render(animation=True)


def along(points, u):
    """Point at u (0..1) on the polyline through `points`, by arc length."""
    P = np.array(points, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    if len(P) == 1 or seg.sum() < 1e-9:
        return P[0]
    s = u * seg.sum()
    for i, l in enumerate(seg):
        if s <= l or i == len(seg) - 1:
            return P[i] + (P[i + 1] - P[i]) * min(s / max(l, 1e-9), 1.0)
        s -= l


def p_moving(fig, t):
    """Is the figure between two different key poses right now? (jitter is stronger while it moves)"""
    a, b = fig["plan"](t - 0.04), fig["plan"](t + 0.04)
    return any(abs(a[k] - b[k]) > 0.5 for k in ("arm_r", "arm_l", "yaw", "head", "x", "z"))


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not args:
        raise SystemExit("usage: blender -b --python brickfilm.py -- <plan.json> [--render | --stills 10,100 | --blend]")
    Film(args[0], args[1:]).run()


if __name__ == "__main__":
    main()
