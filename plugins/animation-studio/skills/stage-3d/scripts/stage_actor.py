# Runs inside Blender's Python (bpy) - started by stage_run.py, never with uv.
"""Soft 3D toy figures with an acting API: the rig (`Char`), poses, moods, lip sync, and the bundled neutral
figure `Toy` (bear / cat / bunny looks). A project builds its own cast by subclassing `Char` (see BLOCK.md).

All figures face -Y at heading 0; anatomical left = +X. Joints are empties (Node); meshes hang rigidly on them.
Spoken lines come from PROJECT/speech/lines.json (written by stage_speech.py): per line its duration, the word
times and the Rhubarb mouth cues.
"""
import json
import math

from mathutils import Euler, Matrix

import stage_core as _C
from stage_core import (INK, WHITE, FPS, Ch, Node, V, box, capsule, clamp, cyl, ell, empty, felt,
                        glass, mat, smooth, srgb, torus, tube, _MATS, _new_mat)

OPEN = {"A": 0.04, "B": 0.3, "C": 0.55, "D": 1.0, "E": 0.7, "F": 0.28, "G": 0.22, "H": 0.5, "X": 0.0}
_LINES = None
LIPS = {"strong": False}    # strong: wider mouth opening while speaking (speech_gain per figure); project.json "lips"
SAID = []                   # (clip, first frame, last frame, line id, start frame) of every spoken line


def lines():
    """{id: line} of PROJECT/speech/lines.json"""
    global _LINES
    if _LINES is None:
        f = _C.PROJECT / "speech" / "lines.json"
        if not f.exists():
            raise RuntimeError(f"{f} is missing - prepare the spoken lines first (stage_speech.py)")
        _LINES = {z["id"]: z for z in json.loads(f.read_text(encoding="utf-8"))["lines"]}
    return _LINES


def line_frames(zid):
    return int(round(line(zid)["duration"] * FPS))


def line(zid):
    L = lines()
    if zid not in L:
        raise SystemExit(f'line "{zid}" is not in speech/lines.json - add it (film3d.py line), then speak or record '
                         f"it and prepare it (film3d.py speak)")
    return L[zid]


def word_frame(zid, word, start=0, nth=0):
    """frame (relative to clip, given line start frame) at which a word begins"""
    hits = [w for w in line(zid).get("words", []) if word.lower() in w["word"].lower()]
    if not hits:
        print(f'WARNING word_frame: "{word}" is not a word of line {zid} - the line start {start} is used', flush=True)
        return start
    return start + int(round(hits[min(nth, len(hits) - 1)]["t"] * FPS))


def cues(zid):
    """Rhubarb mouth cues of a line: [{"start", "end", "value"}]"""
    return line(zid)["cues"]


def materials():
    felt("fur", WHITE)
    felt("fur_tail", "#F6F2EA", fuzz=1.2, scale=90.0, bump=0.45)
    felt("knit", _C.PAL["accent"], fuzz=0.35, scale=420.0, bump=0.3, sss=0.03, tint=_C.PAL["accent_l"])
    felt("knit_d", _C.PAL["accent_d"], fuzz=0.35, scale=420.0, bump=0.3, sss=0.03, tint=_C.PAL["accent"])
    felt("shirt", "#FBFAF6", fuzz=0.5, scale=600.0, bump=0.05)
    mat("eye", "#0B0C0E", rough=0.06, coat=1.0)
    mat("ink", INK, rough=0.25, coat=0.6)
    mat("nose", "#101114", rough=0.18, coat=0.8)
    mat("mouth_in", "#35101A", rough=0.5)
    mat("tongue", "#E58B93", rough=0.4, sss=0.3)
    mat("tooth", "#FFFFFF", rough=0.2, coat=0.5)
    mat("beak", "#E2A94F", rough=0.35, coat=0.3, sss=0.1)
    mat("metal", "#D9DCE0", rough=0.25, metal=1.0)
    mat("gold", "#E3B95A", rough=0.25, metal=1.0)
    mat("catch", "#FFFFFF", emit=4.0)
    mat("brow", "#1B1D20", rough=0.5)
    glass("lens")


class Char:
    step_len = 8        # frames per step
    mouth_rest = 0.0
    mouth_closed = 0.08
    mood_mouth = 1.0        # how much moods open the mouth (tortoise / owl keep it shut)
    speech_gain = 1.3       # mouth opening while speaking (1 = the size of the modelled cavity)

    def __init__(self, S, name, size=1.0):
        self.S, self.name, self.size = S, name, size
        self.J = {}
        self.root = Node(S, empty(name))
        self.root.obj.scale = (size,) * 3
        self.sq = self.j("sq", (0, 0, 0), self.root)
        self.heading = self.root.rch(2)
        self.hip = self.j("hip", (0, 0, 0), self.sq)
        self._mouth_targets = []
        from stage_core import Ch
        self.mouth_ch = Ch(self.mouth_rest)
        self.eyes, self.brow = [], {}
        self.arm_geo, self._ik, self.hand_ch = {}, {}, {}
        self.rest = {}
        self.build()
        self._arm_bind()
        self._mouth_bind()
        self.alive()

    # ---- construction helpers
    def j(self, name, loc, parent, rot=None):
        n = Node(self.S, empty(f"{self.name}_{name}", loc, parent, rot))
        self.J[name] = n
        setattr(self, name, n)
        return n

    def eye(self, side, loc, r, catch=True):
        sx = 1 if side == "L" else -1
        e = Node(self.S, ell(f"{self.name}_eye{side}", (r, r * 0.55, r * 1.12), loc, "eye", self.head, seg=24))
        if catch:
            ell(f"{self.name}_catch{side}", r * 0.2, (-r * 0.3, -r * 0.5, r * 0.42), "catch", e, seg=10)
        self.J["eye" + side] = e
        self.eyes.append(e)
        return e

    def brows(self, side, loc, w, th=0.011, tilt=0):
        sx = 1 if side == "L" else -1
        b = Node(self.S, empty(f"{self.name}_brow{side}", loc, self.head))
        tube(f"{self.name}_browm{side}", [(-w / 2, 0, -w * 0.12), (-w / 4, 0, w * 0.03), (w / 4, 0, w * 0.03),
                                             (w / 2, 0, -w * 0.12)], th * 0.75, "brow", b)
        self.J["brow" + side] = b
        self.brow[side] = (b, loc[2], tilt)
        return b

    def mouth_cavity(self, loc, w, d, h, curve=0.0, wrap=0.0, tongue=False, rot=None):
        k, c = curve / max(w * w, 1e-6), wrap / max(w * w, 1e-6)
        m = ell(f"{self.name}_mouth", (w, d, h), loc, "mouth_in", self.head, seg=28, origin=(0, 0, -h * 0.9), rot=rot,
                warp=lambda co: (co.x, co.y + c * co.x * co.x,
                                 (co.z if co.z < -h * 0.9 else -h * 0.9 + (co.z + h * 0.9) * 0.2) + h * 0.7
                                 + k * co.x * co.x))
        n = Node(self.S, m)
        if tongue:
            ell(f"{self.name}_tongue", (w * 0.62, d * 0.9, h * 0.5), (0, -d * 0.2, -h * 0.75), "tongue", n, seg=20)
        self._mouth_targets.append((n, "scl", 2, self.mouth_closed, 1.0))
        self._mouth_targets.append((n, "scl", 0, 1.0, 0.82))
        return n

    def glasses(self, x, y, z, R, r=0.011, lens=True):
        for sx in (1, -1):
            torus(f"{self.name}_gl{sx}", R, r, (x * sx, y, z), "ink", self.head, rot=(90, 0, 0), seg=40, rseg=10)
            if lens:
                cyl(f"{self.name}_lens{sx}", R, 0.004, (x * sx, y, z), "lens", self.head, rot=(90, 0, 0), bevel=0)
            capsule(f"{self.name}_temple{sx}", (x * sx + R * sx, y, z), (x * sx + R * sx * 1.25, y + 0.14, z + 0.01), r * 0.8,
                    r * 0.8, "ink", self.head, seg=8)
        capsule(f"{self.name}_bridge", (-(x - R), y, z + R * 0.15), (x - R, y, z + R * 0.15), r * 0.9, r * 0.9, "ink",
                self.head, seg=8)

    def limb(self, base, side, at, parent, l1, l2, r1, r2, m="fur", hand=None, flat=1.0, m2=None):
        """two-segment limb hanging down: joints <base>S and <fore|shin>S, plus hand/foot node"""
        sx = 1 if side == "L" else -1
        up = self.j(base + side, (at[0] * sx, at[1], at[2]), parent)
        capsule(f"{self.name}_{base}{side}_m", (0, 0, 0), (0, 0, -l1), r1, r1 * 0.92, m, up, flat=flat)
        lo_name = {"arm": "fore", "leg": "shin"}[base] + side
        lo = self.j(lo_name, (0, 0, -l1), up)
        capsule(f"{self.name}_{lo_name}_m", (0, 0, 0), (0, 0, -l2), r1 * 0.92, r2, m2 or m, lo, flat=flat)
        end = self.j({"arm": "hand", "leg": "foot"}[base] + side, (0, 0, -l2), lo)
        if base == "arm":
            self.arm_geo[side] = (V((at[0] * sx, at[1], at[2])), l1, l2)
            self.torso_front = getattr(self, "torso_front", 0.2)
        if hand:
            ell(f"{self.name}_{base}{side}_h", hand, (0, 0, -hand[2] * 0.35), m2 or m, end, seg=20)
        return up, lo, end

    def _arm_bind(self):
        """arm joints follow keyed hand targets (body space) through a 2-bone IK, solved per frame"""
        for side, (sh, l1, l2) in self.arm_geo.items():
            sg = 1 if side == "L" else -1
            rest = self.hand_target(side, (1.12, 0.3, -0.95))
            chs = [Ch(rest[i]) for i in range(3)] + [Ch(v) for v in (1.0, 0.7, -0.5)]
            self.hand_ch[side] = chs
            for jn, k0 in (("arm" + side, 0), ("fore" + side, 3)):
                for i in range(3):
                    self.J[jn].rch(i).add(lambda f, side=side, k=k0 + i: self._solve(side, f)[k])

    def hand_target(self, side, b):
        """body-box units -> body-space point. b=(x: 0 centre..1 shoulder (outward +), y: 1 = torso front surface,
        z: in arm lengths above (+) / below (-) the shoulder)"""
        sh, l1, l2 = self.arm_geo[side]
        sg = 1 if side == "L" else -1
        return V((b[0] * abs(sh.x) * sg, -b[1] * self.torso_front, sh.z + b[2] * (l1 + l2)))

    def _solve(self, side, f):
        f = int(round(f))
        cache = self._ik.setdefault(side, {})
        if f in cache:
            return cache[f]
        sh, l1, l2 = self.arm_geo[side]
        sg = 1 if side == "L" else -1
        c = self.hand_ch[side]
        t = V((c[0].eval(f), c[1].eval(f), c[2].eval(f)))
        hint = V((c[3].eval(f) * sg, c[4].eval(f), c[5].eval(f)))
        d = t - sh
        D = max(1e-4, min(d.length, (l1 + l2) * 0.999))
        dn = d.normalized() if d.length > 1e-6 else V((0, 0, -1))
        a = (l1 * l1 - l2 * l2 + D * D) / (2 * D)
        h = math.sqrt(max(0.0, l1 * l1 - a * a))
        pole = hint - hint.dot(dn) * dn
        pole = pole.normalized() if pole.length > 1e-5 else V((sg, 0, 0))
        e = dn * a + pole * h                    # elbow relative to shoulder
        u = e.normalized()
        v = (dn * D - e).normalized()
        z = -u
        perp = v - v.dot(u) * u
        y = -perp.normalized() if perp.length > 1e-5 else (V((0, 1, 0)) - V((0, 1, 0)).dot(u) * u).normalized()
        x = y.cross(z)
        m = Matrix((x, y, z)).transposed()
        prev = cache.get(f - 1)
        e1 = m.to_euler("XYZ", Euler([math.radians(q) for q in prev[:3]])) if prev else m.to_euler("XYZ")
        bend = math.degrees(math.acos(clamp(u.dot(v), -1, 1)))
        out = (math.degrees(e1.x), math.degrees(e1.y), math.degrees(e1.z), -bend, 0.0, 0.0)
        cache[f] = out
        return out

    def hands(self, f, R=None, L=None, ease="io", pole=None, poleR=None, poleL=None):
        """key hand targets in body-box units (see hand_target); pole = elbow direction hint (out, back, up)"""
        for side, b, pl in (("R", R, poleR or pole), ("L", L, poleL or pole)):
            if side not in self.hand_ch:
                continue
            c = self.hand_ch[side]
            if b is not None:
                if len(b) > 3:
                    pl = b[3:]
                t = self.hand_target(side, b)
                for i in range(3):
                    c[i].key(f, t[i], ease)
                pl = pl or (1.0, 0.7, -0.5)
            if pl is not None:
                for i in range(3):
                    c[3 + i].key(f, pl[i], ease)
        return self

    def reach(self, f, side, p, ease="io", pole=None):
        """key a hand target given as a world point (uses root position/heading at frame f, ignores body lean)"""
        q = V(p) - self.pos(f)
        hd = math.radians(self.heading.eval(f))
        x = q.x * math.cos(-hd) - q.y * math.sin(-hd)
        y = q.x * math.sin(-hd) + q.y * math.cos(-hd)
        t = V((x, y, q.z)) / self.size - V((0, 0, self.body_z0 + self.hip.lch(2).eval(f)))
        c = self.hand_ch[side]
        for i in range(3):
            c[i].key(f, t[i], ease)
        if pole:
            for i in range(3):
                c[3 + i].key(f, pole[i], ease)
        return self

    def _mouth_bind(self):
        for n, kind, idx, a, b in self._mouth_targets:
            ch = n.sch(idx) if kind == "scl" else n.rch(idx)
            ch.key(1, 0.0, "hold")
            ch.keys.clear()
            ch.default = 0.0
            top = 1.0 if (kind == "scl" and idx == 0) else 2.6
            ch.add(lambda f, a=a, b=b, top=top: a + (b - a) * clamp(self.mouth_ch.eval(f), 0, top))

    # ---- life
    def alive(self):
        r = self.S.rng
        ph = [r.uniform(0, 100) for _ in range(8)]
        k = getattr(self, "calm", 1.0)
        self.sq.sch(2).add(lambda f: 0.012 * math.sin(f * 0.13 + ph[0]))
        self.body.rch(0).add(lambda f: 0.7 * k * math.sin(f * 0.045 + ph[1]))
        self.body.rch(1).add(lambda f: 0.6 * k * math.sin(f * 0.031 + ph[2]))
        self.head.rch(0).add(lambda f: 1.3 * k * math.sin(f * 0.052 + ph[3]) + 0.5 * math.sin(f * 0.13 + ph[0] + 1))
        self.head.rch(1).add(lambda f: 1.1 * k * math.sin(f * 0.037 + ph[4]))
        self.head.rch(2).add(lambda f: 1.5 * k * math.sin(f * 0.029 + ph[5]))
        # blinking (multiplicative on eye height)
        self.blinks = []
        f = r.randint(20, 70)
        while f < self.S.frames:
            self.blinks.append(f)
            if r.random() < 0.18:
                self.blinks.append(f + 7)
            f += r.randint(55, 130)
        for e in self.eyes:
            e.sch(2).mul(self._blink_fn)

    def _blink_fn(self, f):
        v = 1.0
        for b in self.blinks:
            d = f - b
            if -2 <= d <= 4:
                v = min(v, 0.08 + 0.92 * (abs(d - 0.5) / 3.0) ** 2 if abs(d - 0.5) < 3 else 1.0)
        return v

    def blink(self, f):
        self.blinks.append(f)
        return self

    def no_blink(self, f0, f1):
        self.blinks = [b for b in self.blinks if not (f0 <= b <= f1)]
        return self

    # ---- staging
    def at(self, f, x=None, y=None, h=None, z=None, ease="io"):
        self.root.loc(f, x, y, z, ease)
        if h is not None:
            self.root.rot(f, z=h, ease=ease)
        return self

    def cut(self, f):
        """teleport cleanly at frame f (call after keying the new position at f)"""
        for n in self.J.values():
            n.cut(f)
        self.root.cut(f)
        return self

    def pos(self, f):
        return V((self.root.lch(0).eval(f), self.root.lch(1).eval(f), self.root.lch(2).eval(f)))

    def head_pos(self, f):
        return self.pos(f) + V((0, 0, self.head_z * self.size))

    def face_pos(self, f, fwd=0.0):
        """world point at eye height (for camera aims / focus); fwd metres in front of the face"""
        h = math.radians(self.heading.eval(f))
        return self.pos(f) + V((math.sin(h) * fwd, -math.cos(h) * fwd, self.eye_z * self.size))

    def pose(self, f, p=None, ease="io", **kw):
        mirror = isinstance(p, str) and p.endswith("_m")        # "<pose>_m" = mirrored (other hand)
        if mirror:
            p = p[:-2]
        d = dict(POSES[p]) if isinstance(p, str) else dict(p or {})
        if mirror:
            d["handR"], d["handL"] = d.get("handL"), d.get("handR")
            d = {k: v for k, v in d.items() if v is not None}
            for k in ("body", "head"):
                if k in d:
                    d[k] = (d[k][0], -d[k][1], -d[k][2])
        if isinstance(p, str) and p in self.rest_over:
            d.update(self.rest_over[p])
        d.update(kw)
        if "handR" in d or "handL" in d:
            self.hands(f, d.pop("handR", None), d.pop("handL", None), ease)
        for jn, val in d.items():
            if jn == "drop":
                self.hip.lch(2).key(f, val * self.body_z0 * 0.8, ease)
            elif jn in self.J:
                self.J[jn].rot(f, *val, ease=ease)
        return self

    def hold(self, f0, f1, p=None, ease="io", **kw):
        self.pose(f0, p, ease, **kw)
        self.pose(f1, p, "hold", **kw)
        return self

    def turn(self, f, h, dur=8, ease="io"):
        self.root.rot(f, z=self.heading.last(f))
        self.root.rot(f + dur, z=h, ease=ease)
        return self

    def face_to(self, f, p, dur=8):
        q = self.pos(f)
        return self.turn(f, math.degrees(math.atan2(p[0] - q[0], -(p[1] - q[1]))), dur)

    def head_to(self, f, yaw=0, pitch=0, roll=0, ease="io"):
        self.head.rot(f, pitch, roll, yaw, ease)
        return self

    def look(self, f, p, ease="io", gain=0.85, roll=0):
        """turn the head towards a world point (body keeps its heading)"""
        q = self.head_pos(f)
        d = V(p) - q
        yaw = math.degrees(math.atan2(d.x, -d.y)) - self.heading.eval(f)
        yaw = (yaw + 180) % 360 - 180
        pitch = -math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
        return self.head_to(f, clamp(yaw * gain, -85, 85), clamp(pitch * gain, -35, 40), roll, ease)

    def squash(self, f, amt=0.15, dur=8):
        """quick squash and spring back (emphasis / landing / surprise)"""
        self.sq.scl(f, 1, 1, 1)
        self.sq.scl(f + 2, 1 + amt * 0.6, 1 + amt * 0.6, 1 - amt, "out")
        self.sq.scl(f + dur, 1, 1, 1, "spring")
        return self

    def stretch(self, f, amt=0.12, dur=10):
        self.sq.scl(f, 1, 1, 1)
        self.sq.scl(f + 3, 1 - amt * 0.5, 1 - amt * 0.5, 1 + amt, "out")
        self.sq.scl(f + dur, 1, 1, 1, "spring")
        return self

    def hop(self, f, h=0.18, dur=10, squash=0.16, to=None, spin=0):
        """anticipate, jump, land with squash. to=(x,y): travel while in the air; spin: degrees of heading turn"""
        a = 4
        self.sq.scl(f - a, 1, 1, 1)
        self.sq.scl(f, 1 + squash * 0.5, 1 + squash * 0.5, 1 - squash, "out")
        self.sq.scl(f + 2, 1 - squash * 0.4, 1 - squash * 0.4, 1 + squash * 0.8, "out")
        self.sq.scl(f + dur - 1, 1 - squash * 0.3, 1 - squash * 0.3, 1 + squash * 0.5)
        self.sq.scl(f + dur + 1, 1 + squash * 0.6, 1 + squash * 0.6, 1 - squash, "out")
        self.sq.scl(f + dur + 8, 1, 1, 1, "spring")
        z = self.sq.lch(2)
        z.key(f, 0.0)
        z.key(f + dur / 2, h / self.size, "out")
        z.key(f + dur, 0.0, "in")
        if to is not None:
            p = self.pos(f)
            self.root.loc(f, p.x, p.y, ease="hold")
            self.root.loc(f + dur, to[0], to[1], ease="lin")
        if spin:
            h0 = self.heading.last(f)
            self.root.rot(f, z=h0)
            self.root.rot(f + dur, z=h0 + spin, ease="io")
        self.follow(f + dur)
        return self

    def follow(self, f):
        """follow-through of tails/ears after a landing or stop (overridden per character)"""
        return self

    def walk(self, f0, f1, x, y, face=True, bob=0.03, swing=28, arms=True, turn=6):
        """walk from the current position to (x, y) between f0 and f1 with steps, bob and arm swing"""
        p = self.pos(f0)
        if face and (abs(x - p.x) + abs(y - p.y)) > 1e-4:
            self.face_to(max(1, f0 - turn), (x, y, 0), turn)
        self.root.loc(f0, p.x, p.y)
        self.root.loc(f1, x, y, ease="io")
        w = lambda f: smooth((f - f0) / 4) * smooth((f1 - f) / 4)     # noqa: E731
        sl = self.step_len
        ph = lambda f: (f - f0) / sl * math.pi                        # noqa: E731
        self.sq.lch(2).add(lambda f: w(f) * bob / self.size * abs(math.sin(ph(f))) if f0 <= f <= f1 else 0.0)
        self.body.rch(1).add(lambda f: w(f) * 4 * math.sin(ph(f)) if f0 <= f <= f1 else 0.0)
        for s, sg in (("L", 1), ("R", -1)):
            self.J["leg" + s].rch(0).add(lambda f, sg=sg: w(f) * swing * sg * math.sin(ph(f)) if f0 <= f <= f1 else 0.0)
            if arms:
                self.J["arm" + s].rch(0).add(
                    lambda f, sg=sg: -w(f) * swing * 0.6 * sg * math.sin(ph(f)) if f0 <= f <= f1 else 0.0)
        return [f0 + int(i * sl) for i in range(1, int((f1 - f0) / sl) + 1)]

    # ---- face
    def mood(self, f, name, ease="io"):
        m = MOODS[name]
        self.brows_set(f, m.get("up", 0), m.get("tilt", 0), ease)
        eo = m.get("eyes", 1.0)
        for e in self.eyes:
            e.sch(2).key(f, eo, ease)
            e.sch(0).key(f, m.get("eyes_w", 1.0), ease)
        if "mouth" in m:
            self.mouth_ch.key(f, max(m["mouth"] * self.mood_mouth, self.mouth_rest * 0.5) if m["mouth"] >= 0
                              else self.mouth_rest, ease)
        return self

    def brows_set(self, f, up=0, tilt=0, ease="io"):
        for s, sg in (("L", 1), ("R", -1)):
            if s not in self.brow:
                continue
            b, z0, t0 = self.brow[s]
            u = up[0 if s == "L" else 1] if isinstance(up, (tuple, list)) else up
            t = tilt[0 if s == "L" else 1] if isinstance(tilt, (tuple, list)) else tilt
            b.loc(f, z=z0 + u * 0.012, ease=ease)
            b.rot(f, y=(t0 + t) * sg, ease=ease)
        return self

    def say(self, zid, f0, gesture=1.0, nod=1.0):
        """lip sync from Rhubarb cues + head accents on word starts. Returns the end frame."""
        cs = cues(zid)
        mc = self.mouth_ch
        rest = mc.last(f0)
        mc.key(max(1, f0 - 2), rest)
        last = f0
        for i, c in enumerate(cs):
            fa = f0 + c["start"] * FPS - 1
            v = OPEN[c["value"]]
            if c["value"] == "X" and 0 < i < len(cs) - 1 and (c["end"] - c["start"]) < 0.4:
                v = 0.12
            mc.key(round(fa), (v ** 0.6) * self.speech_gain if (LIPS["strong"] and v > 0.05) else v * self.mouth_gain,
                   "io")
            last = f0 + round(c["end"] * FPS)
        mc.key(last + 2, rest)
        SAID.append((self.S.name, int(f0) - 3, int(last) + 3, zid, int(f0)))
        words = [f0 + w["t"] * FPS for w in line(zid).get("words", [])]
        strong = words[::2]
        self.head.rch(0).add(lambda f: nod * sum(3.2 * math.exp(-((f - w - 2) / 2.6) ** 2) for w in strong
                                                 if abs(f - w) < 12))
        self.body.rch(0).add(lambda f: gesture * sum(1.2 * math.exp(-((f - w - 3) / 3.5) ** 2) for w in strong
                                                     if abs(f - w) < 14))
        self.sq.sch(2).add(lambda f: gesture * sum(0.012 * math.exp(-((f - w - 2) / 3.0) ** 2) for w in strong
                                                   if abs(f - w) < 12))
        return last

    def babble(self, f0, f1, speed=1.0):
        """silent chatter (background acting)"""
        mc = self.mouth_ch
        rest = mc.last(f0)
        f = f0
        r = self.S.rng
        while f < f1:
            mc.key(f, r.choice((0.2, 0.5, 0.75, 0.35)) * self.mouth_gain)
            f += max(2, int(r.choice((3, 4, 5)) / speed))
        mc.key(f1, rest)
        return self

    def nod(self, f, n=2, amp=10, per=8):
        self.head.rch(0).add(lambda t: amp * math.sin((t - f) / per * math.tau) * smooth((t - f) / 2) * smooth(
            (f + n * per - t) / 3) if f <= t <= f + n * per else 0.0)
        return self

    def shake(self, f, n=2, amp=16, per=8):
        self.head.rch(2).add(lambda t: amp * math.sin((t - f) / per * math.tau) * smooth((t - f) / 2) * smooth(
            (f + n * per - t) / 3) if f <= t <= f + n * per else 0.0)
        return self

    def take(self, f, amp=1.0):
        """classic take: sink (anticipation), pop up wide-eyed, settle"""
        self.squash(f, 0.14 * amp, 6)
        self.stretch(f + 5, 0.14 * amp, 12)
        self.no_blink(f - 2, f + 20)
        for e in self.eyes:
            c = e.sch(2)
            v = c.last(f)
            c.key(f + 4, v)
            c.key(f + 7, 1.3, "out")
            c.key(f + 20, 1.3, "hold")
            c.key(f + 28, v)
        return self

    def tremble(self, f0, f1, amp=1.2):
        self.body.rch(1).add(lambda t: amp * math.sin(t * 2.9) * smooth((t - f0) / 3) * smooth((f1 - t) / 3)
                             if f0 <= t <= f1 else 0.0)
        return self

    def bounce(self, f0, f1, per=10, h=0.05):
        """excited little bounces on the spot"""
        self.sq.lch(2).add(lambda t: h / self.size * abs(math.sin((t - f0) / per * math.pi)) * smooth((t - f0) / 3)
                           * smooth((f1 - t) / 3) if f0 <= t <= f1 else 0.0)
        self.sq.sch(2).add(lambda t: 0.05 * math.cos((t - f0) / per * math.tau) * smooth((t - f0) / 3)
                           * smooth((f1 - t) / 3) if f0 <= t <= f1 else 0.0)
        return self

    def attach(self, obj, hand="handR", loc=(0, 0, 0), rot=None):
        obj.parent = self.J[hand].obj
        obj.location = loc
        if rot:
            obj.rotation_euler = [math.radians(a) for a in rot]
        return obj


def legs(fwd=0, knee=0, out=0):
    return {"legL": (-fwd, -out, 0), "legR": (-fwd, out, 0), "shinL": (knee, 0, 0), "shinR": (knee, 0, 0)}


REST_H = (1.12, 0.3, -0.95)
DOWN = (0.3, 0.2, -1.0)        # elbow pole: down
OUTP = (1.0, 0.3, -0.2)        # elbows out
# hand targets: (x, y, z[, pole...]) in body-box units, see Char.hand_target
POSES = {
    "rest": {"handR": REST_H, "handL": REST_H, **legs(), "body": (0, 0, 0), "head": (0, 0, 0), "drop": 0},
    "crossed": {"handR": (-0.42, 1.2, -0.5, *OUTP), "handL": (-0.42, 1.08, -0.4, *OUTP), "body": (-3, 0, 0)},
    "chin": {"handR": (0.1, 1.05, 0.38, *DOWN), "handL": (-0.4, 1.1, -0.45, *OUTP), "head": (6, 5, -5)},
    "think": {"handR": (0.1, 1.05, 0.38, *DOWN), "handL": REST_H, "head": (-6, 8, 8)},
    "point": {"handR": (0.9, 4.0, 0.05), "handL": REST_H},
    "point_l": {"handL": (0.9, 4.0, 0.05), "handR": REST_H},
    "point_side": {"handR": (4.0, 0.8, 0.1), "handL": REST_H},
    "point_side_l": {"handL": (4.0, 0.8, 0.1), "handR": REST_H},
    "point_up": {"handR": (1.4, 0.8, 1.6), "handL": REST_H},
    "cheer": {"handR": (2.2, 0.4, 1.3), "handL": (2.2, 0.4, 1.3), "body": (-8, 0, 0), "head": (-12, 0, 0)},
    "fist": {"handR": (1.5, 1.0, 0.55, *DOWN), "handL": (1.3, 0.7, -0.5), "body": (-5, 0, 0)},
    "fist_down": {"handR": (1.2, 1.3, -0.15, *DOWN), "handL": (1.3, 0.7, -0.5)},
    "shrug": {"handR": (2.1, 0.9, -0.1, *DOWN), "handL": (2.1, 0.9, -0.1, *DOWN), "head": (0, 10, 0)},
    "present": {"handR": (2.4, 1.3, -0.05, *DOWN), "handL": REST_H},
    "present_l": {"handL": (2.4, 1.3, -0.05, *DOWN), "handR": REST_H},
    "open": {"handR": (2.0, 1.5, -0.25, *DOWN), "handL": (2.0, 1.5, -0.25, *DOWN)},
    "type": {"handR": (0.55, 1.9, -0.55, *OUTP), "handL": (0.55, 1.9, -0.55, *OUTP), "body": (9, 0, 0),
             "head": (10, 0, 0)},
    "hold": {"handR": (0.5, 1.5, -0.45, *OUTP), "handL": (0.5, 1.5, -0.45, *OUTP), "body": (2, 0, 0)},
    "hold_up": {"handR": (0.7, 0.9, 1.3), "handL": (0.7, 0.9, 1.3), "body": (-6, 0, 0), "head": (-12, 0, 0)},
    "mug": {"handR": (0.55, 1.45, -0.2, *DOWN), "handL": REST_H},
    "sip": {"handR": (0.2, 1.25, 0.3, *OUTP), "handL": REST_H, "head": (-6, 0, 0)},
    "hips": {"handR": (1.05, 0.55, -0.62, 1.0, 0.9, 0.1), "handL": (1.05, 0.55, -0.62, 1.0, 0.9, 0.1)},
    "wave": {"handR": (2.0, 0.5, 1.1), "handL": REST_H},
    "slump": {"handR": (1.0, 0.6, -0.98), "handL": (1.0, 0.6, -0.98), "body": (14, 0, 0), "head": (18, 0, 0)},
    "lean_back": {"handR": (1.5, -0.4, -0.7), "handL": (1.5, -0.4, -0.7), "body": (-14, 0, 0), "head": (-8, 0, 0)},
    "read": {"handR": (0.5, 1.5, -0.25, *OUTP), "handL": (0.5, 1.5, -0.25, *OUTP), "body": (6, 0, 0),
             "head": (20, 0, 0)},
    "sit": {**legs(fwd=85, knee=80), "drop": -1},
    "stand": {**legs(), "drop": 0},
    "high5": {"handR": (0.9, 1.8, 1.0), "handL": (1.3, 0.7, -0.5), "body": (-6, 0, 0)},
    "duck": {"handR": (1.3, 1.2, -0.5), "handL": (1.3, 1.2, -0.5), "body": (22, 0, 0), "head": (-10, 0, 0),
             **legs(fwd=30, knee=55)},
    "face": {"handR": (0.45, 1.0, 0.45, *OUTP), "handL": (0.45, 1.0, 0.45, *OUTP)},     # hands to cheeks
    "glasses": {"handR": (0.75, 1.0, 0.62, *DOWN), "handL": REST_H},
}

MOODS = {
    "neutral": {"up": 0, "tilt": 0, "eyes": 1.0, "mouth": -1},
    "happy": {"up": 1.2, "tilt": 4, "eyes": 1.0, "mouth": 0.4},
    "smile": {"up": 0.6, "tilt": 2, "eyes": 0.95, "mouth": -1},
    "excited": {"up": 2.2, "tilt": 2, "eyes": 1.22, "mouth": 0.75},
    "worried": {"up": 1.0, "tilt": 20, "eyes": 1.0, "mouth": 0.05},
    "sad": {"up": 0.2, "tilt": 24, "eyes": 0.8, "mouth": 0.0},
    "skeptic": {"up": (2.4, -0.8), "tilt": (-4, -14), "eyes": 0.72, "mouth": 0.0},
    "stern": {"up": -0.8, "tilt": -14, "eyes": 0.8, "mouth": 0.0},
    "surprised": {"up": 2.8, "tilt": 6, "eyes": 1.32, "mouth": 0.55},
    "dreamy": {"up": 1.4, "tilt": 10, "eyes": 0.55, "mouth": 0.3},
    "focus": {"up": -0.5, "tilt": -8, "eyes": 0.85, "mouth": 0.1},
    "thinking": {"up": (1.8, -0.2), "tilt": (6, -4), "eyes": 0.9, "mouth": 0.0},
    "sleepy": {"up": -0.3, "tilt": 8, "eyes": 0.4, "mouth": 0.0},
    "hopeful": {"up": 1.8, "tilt": 14, "eyes": 1.1, "mouth": 0.15},
    "proud": {"up": 1.0, "tilt": -2, "eyes": 0.7, "mouth": 0.35},
}


def vest_mat(name, z_top, v_depth, v_width, top_white=True, color=None, tint=None, shirt="#FBFAF6"):
    """knit vest with a crisp shirt V-neck, computed in the shader from object coordinates of the torso
    (color / tint default to the accent of the palette)"""
    color, tint = color or _C.PAL["accent"], tint or _C.PAL["accent_l"]
    if name in _MATS:
        return _MATS[name]
    felt(name, color, fuzz=0.35, scale=420.0, bump=0.3, sss=0.03, tint=tint)
    m = _MATS[name]
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    tc = next(n for n in nt.nodes if n.type == "TEX_COORD")
    sx = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sx.inputs[0])

    def math(op, a, bb=None, c=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, bb, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    t = math("MULTIPLY", math("SUBTRACT", sx.outputs["Z"], z_top - v_depth), v_width / v_depth)
    in_v = math("MULTIPLY", math("LESS_THAN", math("ABSOLUTE", sx.outputs["X"]), t), math("LESS_THAN", sx.outputs["Y"], 0.0))
    mask = math("MAXIMUM", in_v, math("GREATER_THAN", sx.outputs["Z"], z_top)) if top_white else in_v
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.inputs["A"].default_value = srgb(color)
    mx.inputs["B"].default_value = srgb(shirt)
    nt.links.new(mask, mx.inputs["Factor"])
    nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])
    return m


def vest_paint(z_top, v_depth, v_width, y_front=0.0, top=0):
    """material index per face for a torso ellipsoid: 0 fur, 1 knit vest, 2 shirt (V-neck)"""
    def paint(c):
        if c.z > z_top:
            return top
        if c.y < y_front and abs(c.x) < v_width * (c.z - (z_top - v_depth)) / v_depth:
            return 2
        return 1
    return paint


# ====================================================================== the bundled neutral figure
LOOKS = {   # ears: round | pointy | long | none ; tail: none | stub | long
    "bear": {"fur": "#F3EFE6", "accent": "#C8553D", "accent_d": "#8E3A2A", "ears": "round", "tail": "stub"},
    "cat": {"fur": "#EDEBE8", "accent": "#2F6FB5", "accent_d": "#214E80", "ears": "pointy", "tail": "long"},
    "bunny": {"fur": "#F5F1EA", "accent": "#D9A441", "accent_d": "#9C742B", "ears": "long", "tail": "stub"},
}


class Toy(Char):
    """a small felt toy with a scarf: one rig, the look decides ears, tail and colours (LOOKS or an own dict)"""
    head_z, eye_z, body_z0 = 0.67, 0.71, 0.12
    mouth_gain = 1.0
    mouth_rest = 0.3
    step_len = 7
    torso_front = 0.15
    rest_over = {}

    def __init__(self, S, name, size=1.0, look="bear"):
        self.look_d = dict(LOOKS["bear"], **(LOOKS[look] if isinstance(look, str) else look))
        super().__init__(S, name, size)

    def build(self):
        n, L = self.name, self.look_d
        fur, acc, accd = f"fur_{n}", f"accent_{n}", f"accent_d_{n}"
        felt(fur, L["fur"])
        felt(acc, L["accent"], fuzz=0.35, scale=420.0, bump=0.3, sss=0.03)
        felt(accd, L["accent_d"], fuzz=0.35, scale=420.0, bump=0.3, sss=0.03)
        body = self.j("body", (0, 0, 0.12), self.hip)
        ell(n + "_torso", (0.155, 0.135, 0.2), (0, 0, 0.2), fur, body, seg=48,
            warp=lambda c: (c.x * (1.0 - 0.22 * c.z / 0.2), c.y * (1.0 - 0.15 * c.z / 0.2), c.z))
        ell(n + "_belly", (0.1, 0.05, 0.13), (0, -0.098, 0.17), "shirt", body, seg=28)
        torus(n + "_scarf", 0.088, 0.03, (0, 0, 0.375), acc, body, flat=0.95, rot=(-6, 0, 0))
        ell(n + "_scarf_knot", (0.03, 0.025, 0.025), (0.05, -0.1, 0.35), accd, body, seg=14)
        capsule(n + "_scarf_end", (0.05, -0.105, 0.34), (0.065, -0.125, 0.25), 0.022, 0.028, acc, body, flat=0.5, seg=12)
        head = self.j("head", (0, 0, 0.385), body)
        ell(n + "_head", (0.18, 0.162, 0.158), (0, 0, 0.17), fur, head, seg=48)
        ears = L.get("ears", "round")
        for s, sx in (("L", 1), ("R", -1)):
            ell(n + f"_cheek{s}", (0.075, 0.07, 0.062), (0.095 * sx, -0.088, 0.115), fur, head, seg=28)
            if ears == "round":
                ell(n + f"_ear{s}", (0.062, 0.03, 0.062), (0.125 * sx, 0.01, 0.3), fur, head, seg=24)
                ell(n + f"_earin{s}", (0.036, 0.012, 0.036), (0.125 * sx, -0.022, 0.3), "shirt", head, seg=18)
            elif ears == "pointy":
                cyl(n + f"_ear{s}", 0.062, 0.13, (0.108 * sx, 0.01, 0.315), fur, head, rot=(0, 18 * sx, 0), r2=0.004,
                    seg=24, bevel=0).scale = (1, 0.5, 1)
                cyl(n + f"_earin{s}", 0.038, 0.08, (0.106 * sx, -0.012, 0.3), "shirt", head, rot=(0, 18 * sx, 0),
                    r2=0.003, seg=20, bevel=0).scale = (1, 0.45, 1)
            elif ears == "long":
                ej = self.j("ear" + s, (0.07 * sx, 0.01, 0.3), head, rot=(0, 8 * sx, 0))
                ell(n + f"_ear{s}", (0.042, 0.026, 0.15), (0, 0, 0.13), fur, ej, seg=24)
                ell(n + f"_earin{s}", (0.022, 0.01, 0.11), (0, -0.02, 0.13), "shirt", ej, seg=16)
        ell(n + "_muzzle", (0.07, 0.055, 0.05), (0, -0.125, 0.135), fur, head, seg=28)
        ell(n + "_nose", (0.024, 0.017, 0.017), (0, -0.182, 0.158), "nose", head, seg=16)
        if L.get("glasses"):
            self.glasses(0.076, -0.15, 0.215, 0.05, 0.008)
        self.eye("L", (0.076, -0.136, 0.215), 0.03)
        self.eye("R", (-0.076, -0.136, 0.215), 0.03)
        self.brows("L", (0.08, -0.137, 0.268), 0.055, 0.01)
        self.brows("R", (-0.08, -0.137, 0.268), 0.055, 0.01)
        self.mouth_cavity((0, -0.14, 0.09), 0.05, 0.04, 0.042, curve=0.014, wrap=0.01, tongue=True)
        for s in "LR":
            self.limb("arm", s, (0.148, 0, 0.3), body, 0.125, 0.115, 0.042, 0.036, m=fur, hand=(0.046, 0.044, 0.05))
        for s in "LR":
            up, lo, end = self.limb("leg", s, (0.075, 0, 0.12), self.hip, 0.04, 0.04, 0.055, 0.045, m=fur)
            ell(n + f"_foot{s}", (0.052, 0.105, 0.036), (0, -0.05, -0.002), fur, end, seg=24)
        tail = L.get("tail", "stub")
        if tail == "stub":
            ell(n + "_tail", (0.05, 0.05, 0.05), (0, 0.135, 0.1), fur, body, seg=20)
        elif tail == "long":
            tj = self.j("tail", (0, 0.12, 0.06), body)
            tube(n + "_tailm", [(0, 0, 0), (0, 0.12, 0.02), (0, 0.2, 0.14), (0, 0.17, 0.3), (0, 0.1, 0.36)], 0.028, fur, tj)

    def alive(self):
        super().alive()
        ph = self.S.rng.uniform(0, 9)
        if "tail" in self.J:
            self.tail.rch(2).add(lambda f: 7 * math.sin(f * 0.09 + ph))
        for s, sg in (("L", 1), ("R", -1)):
            if "ear" + s in self.J:
                self.J["ear" + s].rch(1).add(lambda f, sg=sg: 2.0 * sg * math.sin(f * 0.07 + ph))

    def follow(self, f):
        """long ears swing after a landing or a stop"""
        for s, sg in (("L", 1), ("R", -1)):
            if "ear" + s in self.J:
                self.J["ear" + s].rch(0).add(lambda t: 16 * math.exp(-(t - f) / 6) * math.cos((t - f) * 0.7)
                                             if 0 <= t - f < 30 else 0.0)
        return self


def cast(S, figures):
    """build figures: {"name": "bear" | {"look": "cat", "size": 0.9, "glasses": True} | a Char subclass}.
    Returns {name: figure}; every figure starts in its rest pose."""
    materials()
    out = {}
    for nm, spec in figures.items():
        if isinstance(spec, type):
            c = spec(S, nm)
        else:
            d = {"look": spec} if isinstance(spec, str) else dict(spec)
            look = d.pop("look", "bear")
            size = d.pop("size", 1.0)
            c = Toy(S, nm, size, dict(LOOKS[look], **d) if isinstance(look, str) else dict(look, **d))
        c.pose(1, "rest", "hold")
        out[nm] = c
    return out


def typing_generic(c, f0, f1, per=5, amp=10):
    for s, sg in (("L", 1), ("R", -1)):
        c.J["fore" + s].rch(0).add(lambda t, sg=sg: amp * sg * math.sin((t - f0) / per * math.tau) * smooth(
            (t - f0) / 3) * smooth((f1 - t) / 3) if f0 <= t <= f1 else 0.0)
