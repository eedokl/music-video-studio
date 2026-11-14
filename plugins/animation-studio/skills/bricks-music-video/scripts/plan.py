# /// script
# requires-python = ">=3.12"
# dependencies = []
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Shot plan of one section of a brick music video: set, cast places, gestures on words, cameos, props, cuts on
beats and camera moves -> <project>/bricks/<section>.json (editable; bricks-3d/brickfilm.py renders it).

Inputs: project.json (section, figures, "gestures", "props", "screen", "bricks" options, creative seed + ideas),
analysis/song_sheet.json (beats, words, lines), analysis/assignment.json (mouth shapes per figure).
Variation comes from the creative seed: set variant (palette, mirror), places, which gesture a line gets, shot sizes,
camera sides and moves, blink times. Rules in project.json always win over the seed.

project.json keys read here (all optional except the section):
  figures.<name>.minifig    look from bricks-3d/assets/cast.json (tim, lia, silhouette, robot, rocker, singer)
  figures.<name>.cameo      true -> not on a spot; appears at the set's "outside" anchor on a cameo prop
  figures.<name>.sign       name sign on the torso (neutral lettering, e.g. "OPEN", "MODELL"); per section
                            sections[].signs {"bot1": "SAFE"} wins; bricks.signs "auto" gives every robot without a
                            sign one from bricks.sign_pool (seeded)
  sections[].set            room | stage | rooftop | house | arena | cloud (anything else: picked by the seed);
                            house = night exterior, the whole section is one camera flight into the lit window
  sections[].figures        cast of the section (screen figures talk on the room monitor)
  gestures  [{"word": "Typ", "figure": "tim", "gesture": "point", "target": "outside", "duration": 1.0}]
            gestures: chest open_arms point point_cam reach shrug cheer fist headshake type laugh scare look slump
                      kiss wave scratch nod jump puppet puppeteer  (target = an anchor name of the set or another figure)
  props     [{"word": "Typ", "prop": "cameo", "figure": "mann", "duration": 1.6, "gesture": "laugh"},
             {"word": "Tokens", "prop": "coins", "count": 9},  {"word": "Hirn", "prop": "hair", "figure": "tim"},
             {"word": "Kopf", "prop": "head_pop", "figure": "tim"}, {"word": "Quota", "prop": "lights_off"},
             brick effects (bricks-3d/effects.py, stop motion on twos, seeded):
             {"word": "Prompts", "prop": "brick_word", "text": "PROMPTS!", "duration": 1.6, "nth": -1,
              "fall": 1.4 (s after the word: the bricks tumble down), "pixel": 20, "colours": [14, 4]},
             {"word": "Final", "prop": "confetti", "count": 140, "until": 20},
             {"word": "größte", "prop": "tower", "count": 10, "at": [x, 0, z] | "anchor": "podium"},
             {"word": "fällt", "prop": "fall_apart", "figure": "bot2"}, {"word": "Und", "prop": "assemble",
              "figure": "lia", "nth": 0}  (a figure falls apart / builds itself part by part),
             {"word": "Hirn", "prop": "steam", "figure": "tim", "duration": 2.0, "rate": 4.5, "burst": 0}
              (steam puffs rise from the head; "anchor": "gpu" instead of a figure = from a set point),
             {"word": "hält", "prop": "strings", "figure": "mann", "targets": ["bot1", "bot2"], "until": 3}
              (marionette strings from the puppeteer's hands to the targets' heads; targets dance like puppets on
              the beat, the puppeteer works the strings; a cameo puppeteer is shown for the whole time),
             {"word": "Tim", "prop": "coins", "count": 6, "from_start": true} (the stack is there from the section
              start), {"word": "abonniert", "prop": "coins_vanish", "one_by_one": false} (all coins gone at once,
              or one per beat, top first - tokens being spent)]
            "nth": only the n-th occurrence of the word in the section (0 = first, -1 = last)
  screen    [{"word": "LLM", "kind": "heart", "text": "xoxo", "color": "#ff4682", "duration": 99}]   room monitor
  every gestures/props/screen rule may carry "section": "chorus2" (or a list) - it then applies only there
  bricks    {"flip": false, "palette": 0, "set": "room", "samples": 32, "quality": "...", "jitter": 0.3,
             "idle_screen": {"kind": "code"}, "spots": {"tim": 0, "lia": 1}, "camera": "calm" | "lively",
             "enter": "assemble" (the set builds itself from flying bricks at the section start, "enter_time" 1.0),
             "exit": "collapse" (the set flies apart in the last "exit_time" s) - together: a room rebuilds as a stage}
            (also per section: sections[].bricks overrides the project-level block)
Usage: uv run plan.py <section> [--project .]        (all sections: --all)
"""
import argparse
import hashlib
import json
import re
import math
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "bricks-3d")
import creative  # noqa: E402
from layouts import SETS, anchor, spot, spot_floor  # noqa: E402
from song_project import Project, word_matches  # noqa: E402

CAST = json.loads((_studio.skill_dir("bricks-3d") / "assets" / "cast.json").read_text(encoding="utf-8"))
REST = dict(arm_r=8, arm_l=8, hand_r=0, hand_l=0, head=0, lean=0, hop=0)
SING_POOL = ["chest", "open_arms", "point_cam", "reach", "shrug", "sway", "open_arms", "chest"]
SOUND_OF = {"point": "point", "point_cam": "point", "cheer": "cheer", "fist": "cheer", "scare": "scare",
            "scratch": "scratch", "slump": "sad", "shrug": "scratch"}
FACE_Y = -84
SIGN_POOL = ["MODELL", "OPEN", "SAFE", "FAST", "CHEAP", "SMART", "PRO", "MAX", "BOT"]


def sign_slug(text):
    """file-safe name of a sign texture (umlauts and the like are covered by a short hash)"""
    base = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:24]
    return f"{base}_{hashlib.md5(text.encode('utf-8')).hexdigest()[:6]}"


# ------------------------------------------------------------------ small helpers
def yaw_to(src, dst):
    """Yaw (deg) that turns a figure at src (x, z) to face dst (x, z). Facing for yaw 0 is -z."""
    vx, vz = dst[0] - src[0], dst[1] - src[1]
    return math.degrees(math.atan2(-vx, -vz))


def wrap(a):
    return (a + 180) % 360 - 180


def snap(t, beats, tol=0.3):
    b = min(beats, key=lambda x: abs(x - t)) if beats else t
    return b if abs(b - t) <= tol else t


def open_frames(cues, a, b):
    """seconds of open mouth (not X/A) of a cue list in [a, b)"""
    tot = 0.0
    for (t, s), nxt in zip(cues, cues[1:] + [[b, "X"]]):
        lo, hi = max(t, a), min(nxt[0], b)
        if hi > lo and s not in ("X", "A"):
            tot += hi - lo
    return tot


# ------------------------------------------------------------------ gestures -> key poses
def gesture_keys(g, t, d, ctx):
    """Key poses (absolute times) of one gesture starting on the word at t, lasting d seconds."""
    base = ctx["yaw"]
    beats = [b for b in ctx["beats"] if t - 0.05 <= b <= t + d]
    K = []
    if g == "chest":
        K = [(t - 0.25, dict(arm_r=30)), (t, dict(arm_r=75, hand_r=-40)), (t + d, dict(arm_r=70, hand_r=-40))]
    elif g == "open_arms":
        K = [(t - 0.2, dict(arm_r=15, arm_l=15)), (t, dict(arm_r=38, arm_l=38, hop=2)), (t + 0.25, dict(hop=0)),
             (t + d, dict(arm_r=30, arm_l=30))]
    elif g == "reach":
        K = [(t - 0.2, dict(arm_l=30)), (t, dict(arm_l=85, hand_l=-30)), (t + d, dict(arm_l=80))]
    elif g == "point_cam":
        K = [(t - 0.2, dict(arm_r=40)), (t, dict(arm_r=95, hand_r=30)), (t + d, dict(arm_r=90))]
    elif g == "point" and "target_yaw" not in ctx:          # no such target in this set: point at the camera
        K = gesture_keys("point_cam", t, d, ctx)
    elif g in ("point", "look"):
        ty = ctx.get("target_yaw", base + 90)
        if g == "point":
            K = [(t - 0.3, dict(yaw=base + wrap(ty - base) * 0.6, arm_r=40)),
                 (t - 0.12, dict(yaw=base + wrap(ty - base), arm_r=115, hand_r=30, head=10)),
                 (t + d, dict(arm_r=110)), (t + d + 0.35, dict(yaw=base, **REST))]
        else:                                               # look: turn the head, the body follows a little
            diff = wrap(ty - base)
            look = dict(head=max(-35, min(35, diff * 0.6)), yaw=base + diff * 0.25)
            K = [(t - 0.15, look), (t + d, dict(look))]
    elif g == "shrug":
        K = [(t - 0.15, dict(arm_r=20, arm_l=20)), (t, dict(arm_r=70, arm_l=70, hand_r=90, hand_l=-90)),
             (t + d, dict(arm_r=65, arm_l=65))]
    elif g == "cheer":
        K = [(t - 0.1, dict(arm_r=140, arm_l=140, hop=4)), (t + 0.15, dict(hop=0)), (t + 0.45, dict(arm_r=120, arm_l=120, hop=3)),
             (t + 0.6, dict(hop=0)), (t + d, dict(arm_r=130, arm_l=130))]
    elif g == "fist":
        step = 0.35 if len(beats) < 2 else max(0.25, min(0.5, (beats[1] - beats[0]) * 0.8))
        k, u = 0, t
        while u < t + d - 0.1 and k < 4:
            K += [(u, dict(arm_r=170 + 2 * k, hop=5 if k == 0 else 4)), (u + step * 0.5, dict(arm_r=140, hop=0))]
            u += step
            k += 1
    elif g == "headshake":
        u, s = t, -1
        while u < t + d:
            K.append((u, dict(head=18 * s)))
            u += 0.48
            s = -s
        K.append((u, dict(head=0)))
    elif g == "type":
        ty = ctx.get("target_yaw", base - 80)
        K = [(t - 0.25, dict(yaw=ty, arm_r=70, arm_l=70))]
        u, k = t, 0
        while u < t + d:
            K.append((u, dict(arm_r=80 if k % 2 else 64, arm_l=64 if k % 2 else 80)))
            u += 0.25
            k += 1
        K.append((t + d + 0.3, dict(yaw=base, arm_r=20, arm_l=20)))
    elif g == "laugh":
        u = t
        for k in range(3 if d > 0.6 else 2):
            K += [(u, dict(arm_r=45 + 10 * (k % 2), arm_l=45 + 10 * (k % 2), hop=4, grin=2)), (u + 0.1, dict(hop=0, grin=1))]
            u += 0.13
        K.append((t + d, dict(arm_r=20, arm_l=20, grin=1)))
    elif g == "scare":
        K = [(t, dict(lean=-10, arm_r=85, arm_l=85, hand_r=60, hand_l=-60)), (t + 0.55, dict(lean=-8)),
             (t + min(d, 0.8), dict(lean=0, arm_r=40, arm_l=40, hand_r=90, hand_l=-90))]
    elif g == "slump":
        K = [(t, dict(lean=12, arm_r=0, arm_l=0, head=0)), (t + d, dict(lean=12))]
    elif g == "kiss":
        K = [(t - 0.35, dict(arm_r=125, hand_r=40)), (t + 0.15, dict(arm_r=80, hand_r=0, lean=6)), (t + 0.6, dict(arm_r=10, lean=0))]
    elif g == "wave":
        u, s = t, 1
        K.append((t - 0.2, dict(arm_r=140)))
        while u < t + d:
            K.append((u, dict(arm_r=150, hand_r=35 * s)))
            u += 0.25
            s = -s
    elif g == "scratch":
        K = [(t - 0.2, dict(arm_r=120)), (t, dict(arm_r=160, hand_r=60, head=15)), (t + d, dict(arm_r=155, hand_r=50))]
    elif g == "nod":
        for b in beats or [t]:
            K += [(b, dict(lean=5)), (b + 0.15, dict(lean=0))]
    elif g == "jump":
        K = [(t - 0.1, dict(hop=0, arm_r=40, arm_l=40)), (t + 0.05, dict(hop=10, arm_r=150, arm_l=150)),
             (t + 0.3, dict(hop=0, arm_r=60, arm_l=60))]
    elif g == "puppet":                                     # hanging on strings: arms and head jerk on the beat
        for k, b in enumerate(beats or [t]):
            a = k % 2 == 0
            K.append((b, dict(arm_r=120 if a else 10, arm_l=10 if a else 120, head=20 if a else -20, hop=3 if a else 0)))
        K.append((t + d, dict(arm_r=10, arm_l=10, head=0, hop=0)))
    elif g == "puppeteer":                                  # works the strings: both arms up, alternating
        K = [(t - 0.1, dict(arm_r=110, arm_l=110))]
        for k, b in enumerate([x for x in beats if x > t] or [t + 0.3]):
            K.append((b, dict(arm_r=125 if k % 2 else 95, arm_l=95 if k % 2 else 125)))
    elif g == "sway":
        for k, b in enumerate(beats or [t]):
            K.append((b, dict(arm_r=35 if k % 2 else 15, arm_l=15 if k % 2 else 35)))
    return K


# ------------------------------------------------------------------ the planner
class Planner:
    def __init__(self, P, name):
        self.P = P
        self.A = P.section(name)
        self.name = name
        self.S, self.E = float(self.A["from"]), float(self.A["to"])
        opts = dict(P.get("bricks") or {})
        opts.update(self.A.get("bricks") or {})
        self.o = opts
        sheet = P.sheet()
        self.beats = [b["t"] for b in sheet["beats"]]
        self.bars = [b["t"] for b in sheet["beats"] if b.get("downbeat") or b.get("bar_start")] or self.beats[::4]
        self.words = [w for w in sheet["words"] if self.S - 0.2 <= w["t"] < self.E]
        self.lines = [l for l in sheet["lines"] if l["end"] > self.S and l["t"] < self.E]
        self.assign = P.assignment()["figures"]
        self.figs_cfg = P["figures"]
        self.r = lambda salt: creative.rng(P, f"bricks:{name}:{salt}")

    def words_for(self, prefix):
        return [w for w in self.words if word_matches(w["word"], prefix)]

    def rules(self, key):
        """project.json rules of one kind that apply to this section: a rule may name "section" (a name or a list)
        so a word that comes back in several sections can get a different gag each time"""
        out = []
        for r in self.P.get(key, []):
            sec = r.get("section")
            if sec is None or sec == self.name or (isinstance(sec, list) and self.name in sec):
                out.append(r)
        return out

    # ---------------- set
    def set_spec(self):
        kind = self.o.get("set") or self.A.get("set")
        if kind not in SETS:
            kind = creative.pick(self.P, f"bricks:{self.name}:set", sorted(SETS))
        pals = SETS[kind]["palettes"]
        pi = self.o.get("palette")
        pi = int(pi) if pi is not None else self.r("palette").randrange(len(pals))
        flip = self.o.get("flip")
        flip = bool(flip) if flip is not None else self.r("flip").random() < 0.5
        self.kind, self.flip = kind, flip
        return {"kind": kind, "flip": flip, "palette": pals[pi % len(pals)], "palette_index": pi % len(pals)}

    # ---------------- cast
    def cast(self):
        names = self.A.get("figures") or list(self.figs_cfg)
        has_monitor = self.kind == "room"
        cast, slot = [], 0
        sing = {n: open_frames(self.assign.get(n, []), self.S, self.E) for n in names}
        order = sorted([n for n in names if not self.figs_cfg.get(n, {}).get("cameo")], key=lambda n: -sing.get(n, 0))
        fixed = self.o.get("spots", {})
        r = self.r("cast")
        for n in [x for x in names if x in order]:
            cfg = self.figs_cfg.get(n, {})
            look = cfg.get("minifig") or CAST["figure_defaults"].get(n)
            screen = cfg.get("kind") == "screen" or look == "screen"
            if screen and has_monitor:
                cast.append(dict(name=n, screen=True, mouth=self.assign.get(n, [])))
                continue
            if screen:
                look = "robot"
            if look not in CAST["looks"]:
                look = "tim" if cfg.get("voice") == "male" else "lia" if cfg.get("voice") == "female" else "robot"
            if screen and not sing.get(n):                  # a silent screen figure without a monitor stays home
                continue
            i = fixed.get(n, order.index(n) if n in order else slot)
            (x, z), yaw = spot(self.kind, i, self.flip)
            x += r.uniform(-12, 12)
            z += r.uniform(-8, 8)
            cast.append(dict(name=n, look=look, place=[round(x, 1), round(z, 1)], yaw=round(yaw + r.uniform(-6, 6), 1),
                             bounce=round(r.uniform(0.9, 1.6), 2), mouth=self.assign.get(n, []),
                             floor=spot_floor(self.kind, i)))
            if cast[-1]["floor"]:                           # on a podium: no random shift off the block
                cast[-1]["place"] = [round(v, 1) for v in spot(self.kind, i, self.flip)[0]]
            sign = (self.A.get("signs") or {}).get(n) or cfg.get("sign")
            if not sign and look == "robot" and self.o.get("signs") == "auto":
                sign = self.r(f"sign:{n}").choice(self.o.get("sign_pool") or SIGN_POOL)
            if sign:
                cast[-1]["sign"] = sign
                cast[-1]["sign_tex"] = f"torso_sign_{sign_slug(sign)}.png"
            slot += 1
        for n in names:                                     # cameo figures (silhouettes at the window ...)
            cfg = self.figs_cfg.get(n, {})
            if cfg.get("cameo"):
                ax, ay, az = anchor(self.kind, "outside_hidden", self.flip)
                cast.append(dict(name=n, look=cfg.get("minifig", "silhouette"), place=[ax, az], yaw=0.0, bounce=0.8,
                                 mouth=[], floor=float(SETS[self.kind].get("cameo_floor", 0)), cameo=True))
        self.castd = {c["name"]: c for c in cast}
        return cast

    def pos(self, name):
        c = self.castd[name]
        return (c["place"][0], c["place"][1])

    def target_point(self, target, who=None):
        if target in self.castd and not self.castd[target].get("screen"):
            x, z = self.pos(target)
            if self.castd[target].get("cameo"):
                ax, ay, az = anchor(self.kind, "outside", self.flip)
                return (ax, az)
            return (x, z)
        a = anchor(self.kind, target or "", self.flip)
        if a:
            return (a[0], a[2])
        return None

    def singer_at(self, a, b, exclude=()):
        best, val = None, 0.0
        for n, c in self.castd.items():
            if n in exclude or c.get("screen") or c.get("cameo"):
                continue
            v = open_frames(c["mouth"], a, b)
            if v > val:
                best, val = n, v
        return best

    # ---------------- gestures, cameos, props
    def events(self):
        ev = []                                             # (t, d, figure, gesture, target, source)
        for g in self.rules("gestures"):
            if g.get("figure") not in self.castd:
                continue
            for w in self.words_for(g["word"]):
                d = float(g.get("duration", max(0.6, min(1.6, w.get("end", w["t"] + 0.6) - w["t"] + 0.4))))
                ev.append((w["t"], d, g["figure"], g["gesture"], g.get("target"), "rule"))
        self.cameos, self.coins, self.screen_ev, self.lights, self.fx = [], [], [], [], []
        self.coins_gone, self.strings = [], []
        vanish = []
        for p in self.rules("props"):
            ws = self.words_for(p["word"])
            if p.get("nth") is not None:                    # only the n-th occurrence in the section (-1 = last)
                ws = [ws[int(p["nth"])]] if -len(ws) <= int(p["nth"]) < len(ws) else []
            for w in ws:
                t = w["t"]
                kind = p["prop"]
                if kind == "cameo" and p.get("figure") in self.castd:
                    d = float(p.get("duration", 1.6))
                    self.cameos.append(dict(t=t, d=d, figure=p["figure"], gesture=p.get("gesture")))
                    if p.get("gesture"):
                        ev.append((t + 0.15, max(0.5, d - 0.6), p["figure"], p["gesture"], None, "cameo"))
                elif kind == "coins":
                    n = int(p.get("count", 6))
                    bs = [b for b in self.beats if b >= t - 0.05][:n]
                    while len(bs) < n:
                        bs.append((bs[-1] if bs else t) + 0.45)
                    if p.get("from_start"):                 # the stack is already there
                        bs = [self.S] * n
                    self.coins = bs
                elif kind == "coins_vanish":
                    vanish.append((t, bool(p.get("one_by_one"))))
                elif kind == "steam" and (p.get("figure") in self.castd or p.get("anchor") or p.get("at")):
                    d = float(p.get("duration", 2.0))
                    rate = float(p.get("rate", 4.5))
                    times = [round(t + k / rate, 3) for k in range(max(1, int(d * rate)))]
                    nb = int(p.get("burst", 0))
                    big = list(range(len(times), len(times) + nb))
                    times += [round(t + d + 0.04 * k, 3) for k in range(nb)]
                    fx = dict(kind="steam", times=times, big=big, colour=int(p.get("colour", 15)))
                    if p.get("figure") in self.castd:
                        fx["figure"] = p["figure"]
                    else:
                        a = p.get("at") or anchor(self.kind, p["anchor"], self.flip)
                        if not a:
                            continue
                        fx["at"] = [a[0], a[1] - 20, a[2]]
                    self.fx.append(fx)
                elif kind == "strings" and p.get("figure") in self.castd:
                    tg = [n for n in p.get("targets", []) if n in self.castd and not self.castd[n].get("screen")]
                    if not tg:
                        continue
                    until = min(self.E, t + float(p["until"])) if p.get("until") else self.E
                    self.strings.append(dict(kind="strings", figure=p["figure"], targets=tg, t=round(t, 3),
                                             until=round(until, 3)))
                    for n in tg:
                        ev.append((t, until - t, n, "puppet", None, "prop"))
                    ev.append((t - 0.05, until - t, p["figure"], "puppeteer", None, "prop"))
                    if self.castd[p["figure"]].get("cameo"):    # a cameo puppeteer stays in view the whole time
                        self.cameos.append(dict(t=t, d=until - t, figure=p["figure"], gesture=None, strings=True))
                elif kind in ("hair", "head_pop") and p.get("figure") in self.castd:
                    ev.append((t, float(p.get("duration", 0.9)), p["figure"], kind, None, "prop"))
                elif kind == "brick_word":                  # a word of flying 1x1 bricks
                    at = p.get("at") or list(anchor(self.kind, "letters", self.flip) or (0, -330, 120))
                    fx = dict(kind="brick_word", text=p.get("text", w["word"]).upper(), t=round(t, 3),
                              d=float(p.get("duration", 1.4)), at=at, colours=p.get("colours", [4, 14, 1, 2, 25]),
                              pixel=int(p.get("pixel", 20)))
                    for k2 in ("fall", "until"):                # seconds after the word
                        if p.get(k2) is not None:
                            fx[k2] = round(t + float(p[k2]), 3)
                    self.fx.append(fx)
                elif kind == "confetti":
                    self.fx.append(dict(kind="confetti", t=round(t, 3), n=int(p.get("count", 120)),
                                        until=round(t + float(p["until"]), 3) if p.get("until") else None,
                                        centre=p.get("centre", [0, -40]), spread=p.get("spread", [320, 220])))
                elif kind == "tower":                       # grows one brick per beat
                    n = int(p.get("count", 10))
                    bs = [b for b in self.beats if b >= t - 0.05][:n]
                    while len(bs) < n:
                        bs.append((bs[-1] if bs else t) + 0.45)
                    a = anchor(self.kind, p["anchor"], self.flip) if p.get("anchor") else None
                    at = p.get("at") or ([a[0], 0, a[2]] if a else [-150, 0, 60])
                    self.fx.append(dict(kind="tower", times=[round(x, 3) for x in bs], at=at,
                                        colours=p.get("colours", [1, 4, 14, 2])))
                elif kind in ("fall_apart", "assemble") and p.get("figure") in self.castd:
                    self.fx.append(dict(kind=kind, figure=p["figure"], t=round(t, 3), d=float(p.get("duration", 1.2))))
                elif kind == "lights_off":
                    self.lights.append(dict(kind="dim", t=t, factor=float(p.get("factor", 0.15))))
                    if p.get("until"):
                        self.lights.append(dict(kind="dim", t=t + float(p["until"]), factor=1.0))
        if vanish and self.coins:                           # coins vanish (all at once or one per beat, top first)
            tv, one = vanish[0]
            n = len(self.coins)
            if one:
                bs = [b for b in self.beats if b >= tv - 0.05][:n]
                while len(bs) < n:
                    bs.append((bs[-1] if bs else tv) + 0.45)
                self.coins_gone = list(reversed(bs))
            else:
                self.coins_gone = [tv] * n
        # automatic singing gestures: every line of a singer without a rule gesture gets one (seeded)
        r = self.r("gestures")
        last = None
        for l in self.lines:
            a, b = max(l["t"], self.S), min(l["end"], self.E)
            who = self.singer_at(a, b)
            if not who or any(e[2] == who and a - 0.3 <= e[0] <= b for e in ev):
                continue
            if r.random() < float(self.o.get("gesture_rate", 0.75)):
                g = r.choice([x for x in SING_POOL if x != last])
                last = g
                d = min(1.8, max(0.7, (b - a) * r.uniform(0.4, 0.7)))
                ev.append((a + r.uniform(0.0, 0.25), d, who, g, None, "auto"))
        # listeners look at the singer of each line
        for l in self.lines:
            a, b = max(l["t"], self.S), min(l["end"], self.E)
            who = self.singer_at(a, b)
            for n, c in self.castd.items():
                if n == who or c.get("screen") or c.get("cameo") or not who:
                    continue
                if not any(e[2] == n and a - 0.3 <= e[0] <= b for e in ev) and r.random() < 0.55:
                    ev.append((a + 0.2, max(0.6, b - a - 0.4), n, "look", who, "listen"))
        self.ev = sorted(ev)
        return self.ev

    def keys(self, name):
        c = self.castd[name]
        base = c["yaw"]
        K = [(self.S, {})]
        mine = [e for e in self.ev if e[2] == name]
        for i, (t, d, _, g, target, src) in enumerate(mine):
            nxt = mine[i + 1][0] if i + 1 < len(mine) else self.E + 1
            d = min(d, max(0.3, nxt - t - 0.6))
            ctx = dict(yaw=base, beats=self.beats)
            tp = self.target_point(target) if target else None
            if g == "type" and not tp:
                tp = self.target_point("keyboard") or self.target_point("desk")
            if tp:
                ctx["target_yaw"] = yaw_to(self.pos(name) if not c.get("cameo") else self.target_point(name), tp)
            if g == "hair":
                K += [(t, dict(hair=1.0)), (t + d, dict(hair=1.0)), (t + d + 0.25, dict(hair=0.0))]
                continue
            if g == "head_pop":
                K += [(t, dict(head_off=1.0)), (t + d * 0.5, dict(head_off=0.8)), (t + d, dict(head_off=0.0))]
                continue
            K += gesture_keys(g, t, d, ctx)
            if nxt - (t + d) > 0.5:
                rest = dict(REST, yaw=base)
                if g in ("slump",):
                    continue
                K.append((t + d + 0.35, rest))
        if c.get("cameo"):
            hid = anchor(self.kind, "outside_hidden", self.flip)
            out = anchor(self.kind, "outside", self.flip)
            K.append((self.S, dict(x=hid[0], z=hid[2], show=0)))
            spans = []                                      # cameos close together: ONE appearance (two
            for cm in sorted([x for x in self.cameos if x["figure"] == name], key=lambda x: x["t"]):  # overlapping
                a, b = cm["t"] - 0.45, cm["t"] + cm["d"]    # slide-ins hid the figure in its own shot)
                if spans and a <= spans[-1][1] + 0.6:
                    spans[-1][1] = max(spans[-1][1], b)
                else:
                    spans.append([a, b])
            for a, b in spans:
                K += [(a - 0.05, dict(x=hid[0], z=hid[2], show=1)), (a + 0.4, dict(x=out[0], z=out[2], grin=1)),
                      (b, dict(grin=0)), (b + 0.45, dict(x=hid[0], z=hid[2])), (b + 0.5, dict(show=0))]
        return sorted(K, key=lambda k: k[0])

    # ---------------- shots
    def cut_points(self):
        cuts = [self.S]
        lively = self.o.get("camera", "calm") == "lively"
        maxlen = 2.4 if lively else 3.2
        for l in self.lines:
            t = snap(l["t"] - 0.05, self.beats, 0.3)
            if self.S + 0.8 < t < self.E - 0.8:
                cuts.append(t)
        for x in self.fx:                                   # steam starts in a shot on the steaming figure
            if x["kind"] == "steam" and x.get("figure"):
                cuts.append(snap(x["times"][0] - 0.12, self.beats, 0.2))
        for st in self.strings:                             # the strings appear in a wide shot
            cuts.append(snap(st["t"] - 0.12, self.beats, 0.2))
        if self.coins_gone:                                 # the coins vanish in a shot that shows the stack
            cuts.append(snap(min(self.coins_gone) - 0.5, self.beats, 0.25))
        for cm in [c for c in self.cameos if not c.get("strings")]:     # a cameo gets its own shot
            cuts += [snap(cm["t"] - 0.4, self.beats, 0.2), snap(cm["t"] + min(cm["d"], 1.6), self.beats, 0.25)]
        for x in self.fx:                                   # a brick word gets its own (wide) shot
            if x["kind"] == "brick_word":
                cuts.append(snap(x["t"] - 0.15, self.beats, 0.2))
        for e in self.ev:                                   # big gestures get a cut on their word
            if e[3] in ("fist", "cheer", "jump", "head_pop", "hair") and e[5] != "listen":
                cuts.append(snap(e[0] - 0.12, self.beats, 0.15))
        # the section start is always a cut (a section shorter than 0.6 s has no other), added cuts must leave
        # 0.6 s before the end
        cuts = sorted({round(self.S, 3)} | {round(c, 3) for c in cuts if self.S < c < self.E - 0.6})
        out = []
        for c in cuts:                                      # at least 1.0 s per shot
            if not out or c - out[-1] >= 1.0:
                out.append(c)
        filled = []
        for a, b in zip(out, out[1:] + [self.E]):           # split long shots on a beat
            filled.append(a)
            while b - filled[-1] > maxlen:
                mid = snap(filled[-1] + (b - filled[-1]) / 2, self.beats, 0.3)
                if mid - filled[-1] < 1.0 or b - mid < 1.0:
                    break
                filled.append(mid)
        return filled

    def screen_talks(self, a, b, subj):
        """True when the room monitor's figure speaks more in [a, b) than the singer (announcements, spoken lines)"""
        scr = next((c for c in self.castd.values() if c.get("screen")), None)
        if not scr:
            return False
        talk = open_frames(scr["mouth"], a, b)
        sing = open_frames(self.castd[subj]["mouth"], a, b) if subj in self.castd else 0.0
        return talk > 0.12 * (b - a) and talk > sing

    def camera(self, kind, subj, r, other=None, target=None):
        """-> (cam_a, cam_b, aim_a, aim_b, lens, focus, fstop)"""
        if kind == "letters":                               # the whole brick word and the figures under it
            x0, ytop, z0 = target["at"]
            width = len(target["text"]) * 4 * target.get("pixel", 20)
            dist = max(420.0, width * 0.62 / math.tan(math.radians(24)))
            ym = ytop + 60
            cam = (x0 + r.uniform(-30, 30), ym + 70, z0 - dist)
            camb = (cam[0] * 0.8, cam[1] + 6, z0 - dist * 0.94)
            aim = (x0, ym + 40, z0)
            return cam, camb, aim, aim, 40, (x0, ym, z0 - 60), 32.0
        if kind == "coins":                                 # the coin stack and the subject side by side
            ax, ay, az = anchor(self.kind, "coins", self.flip)
            c = self.castd.get(subj)
            sx, sz = c["place"] if c else (ax, az)
            mx, mz = (sx + ax) / 2, (sz + az) / 2
            side = 1 if ax >= sx else -1                    # look past the subject towards the stack
            cam = (mx + side * r.uniform(40, 70), -105, mz - r.uniform(300, 340))
            camb = (cam[0] - side * 8, cam[1], cam[2] + 14)
            aim = (mx + side * 15, -66, mz)
            return cam, camb, aim, aim, 40, (ax, ay, az), 32.0
        if kind == "monitor":                               # the screen face fills the frame, slow push in
            # sets.room: monitor at (88, -40, 18) turned 30 deg (mirrored with flip), screen centre ~10 LDU before it
            yaw = math.radians((-30 if self.flip else 30) + r.uniform(-8, 8))
            fwd = (-math.sin(yaw), -math.cos(yaw))
            mx, my, mz = anchor(self.kind, "monitor", self.flip)
            sx, sy, sz = mx + 10 * fwd[0], my + 2, mz + 10 * fwd[1]
            cam = (sx + fwd[0] * 175, sy - r.uniform(0, 8), sz + fwd[1] * 175)
            camb = (sx + fwd[0] * 150, cam[1], sz + fwd[1] * 150)
            aim = (sx, sy, sz)
            return cam, camb, aim, aim, 50, aim, 22.0
        c = self.castd[subj] if subj in self.castd else None
        x, z = (c["place"] if c else (0, 0))
        hy = FACE_Y + (c.get("floor", 0) if c else 0)
        yaw = c["yaw"] if c else 0.0
        side = 1 if r.random() < 0.5 else -1
        spread = (0, 14) if kind == "close" else (12, 38)        # close-ups stay near the face axis
        az = math.radians(yaw + side * r.uniform(*spread))
        fwd = (-math.sin(az), -math.cos(az))
        move = r.choice(["in", "out", "truck", "hold", "in"])
        if kind == "wide":
            pts = [p["place"] for p in self.castd.values() if not p.get("screen") and not p.get("cameo")] or [[0, 0]]
            mx = sum(p[0] for p in pts) / len(pts)
            mz = sum(p[1] for p in pts) / len(pts)
            dist, lens, up = r.uniform(400, 470), 40, r.uniform(-60, -35)
            aim = (mx, -70, mz)
            focus = (x, hy + 2, z)
        elif kind == "two" and other:
            ox, oz = self.pos(other)
            mx, mz = (x + ox) / 2, (z + oz) / 2
            dist, lens, up = r.uniform(340, 400), 40, r.uniform(-30, -15)
            aim = (mx, -75, mz)
            focus = (mx, -80, mz)
        elif kind == "close":
            dist, lens, up = r.uniform(165, 200), 32, r.uniform(35, 50)      # low angle hero close-up
            aim = (x, hy - 14, z)
            focus = (x, hy, z)
        elif kind == "medium":
            dist, lens, up = r.uniform(270, 330), 45, r.uniform(-45, -25)
            aim = (x + 25 * fwd[1], -75, z)
            focus = (x, hy + 4, z)
        elif kind == "detail" and target:
            tx, tz = target
            ty = -150 if self.kind == "room" else FACE_Y + float(SETS[self.kind].get("cameo_floor", 0))
            dist, lens, up = r.uniform(220, 270), 55, 0
            az = math.radians(r.uniform(-20, 20) + (15 if self.flip else -15))
            fwd = (-math.sin(az), -math.cos(az))
            cam = (tx + fwd[0] * dist, ty, tz + fwd[1] * dist)
            return cam, (cam[0] - 6 * side, cam[1], cam[2] + 12), (tx, ty, tz), (tx, ty, tz), lens, (tx, ty, tz), 22.0
        elif kind == "reveal" and target:
            tx, tz = target
            mx, mz = (x * 0.6 + tx * 0.4), (z * 0.6 + tz * 0.4)
            dist, lens, up = 330, 30, -25
            aim = (tx * 0.7 + x * 0.3, -120, tz * 0.7 + z * 0.3)
            away = (-(tx - x), -(tz - z))
            n = math.hypot(*away) or 1
            fwd = (away[0] / n * 0.6 - 0.4 * side * 0.5, away[1] / n * 0.6 - 0.8)
            n = math.hypot(*fwd)
            fwd = (fwd[0] / n, fwd[1] / n)
            cam = (x + fwd[0] * dist, -105, z + fwd[1] * dist)
            return cam, (cam[0] - 10, cam[1] - 3, cam[2] + 20), aim, (aim[0] - 10, aim[1] - 3, aim[2] + 5), lens, \
                (x * 0.5 + tx * 0.5, -110, z * 0.5 + tz * 0.5), 32.0
        else:                                               # medium-close
            dist, lens, up = r.uniform(220, 260), 50, r.uniform(-30, -15)
            aim = (x + 20 * fwd[1], -70, z)
            focus = (x, hy + 2, z)
        cam = (aim[0] + fwd[0] * dist, hy + up, aim[2] + fwd[1] * dist)
        k = {"in": 0.88, "out": 1.1, "truck": 1.0, "hold": 0.98}[move]
        camb = (aim[0] + fwd[0] * dist * k + (18 * side if move == "truck" else 0), cam[1] + r.uniform(-4, 4),
                aim[2] + fwd[1] * dist * k)
        fstop = 32.0 if lens <= 40 else 22.0
        return cam, camb, aim, aim, lens, focus, fstop

    def flight_shot(self):
        """house set: the camera flies through the garden, over the fence and into the lit window (one shot)"""
        fl = SETS[self.kind]["flight"]
        r = self.r("flight")
        dx, dy = r.uniform(-40, 40), r.uniform(-25, 10)
        fx = -1 if self.flip else 1
        cam = [[round(fx * x + dx * (1 - i / 4), 1), round(y + dy * (1 - i / 4), 1), z] for i, (x, y, z) in enumerate(fl["cam"])]
        aim = [[fx * x, y, z] for x, y, z in fl["aim"]]
        return [dict(t0=self.S, t1=self.E, kind="flight", subject=None, cam=[cam[0], cam[-1]], aim=[aim[0], aim[-1]],
                     lens=35, focus=aim[-1], fstop=32.0, shake=0.0, path={"cam": cam, "aim": aim})]

    def shots(self):
        if "flight" in SETS[self.kind]:
            return self.flight_shot()
        cuts = self.cut_points()
        r = self.r("shots")
        lively = self.o.get("camera", "calm") == "lively"
        sizes = ["medium", "mclose", "two", "medium", "wide", "mclose", "close"]
        out, prev = [], None
        for i, (a, b) in enumerate(zip(cuts, cuts[1:] + [self.E])):
            subj = self.singer_at(a, b) or next((n for n, c in self.castd.items() if not c.get("screen") and not c.get("cameo")), None)
            others = [n for n, c in self.castd.items() if n != subj and not c.get("screen") and not c.get("cameo")]
            target, kind = None, None
            cm = next((x for x in self.cameos if not x.get("strings")
                       and abs(snap(x["t"] - 0.4, self.beats, 0.2) - a) < 0.35), None)
            strings = next((x for x in self.strings if a - 0.3 <= x["t"] < min(b, a + 0.6)), None)
            big = next((e for e in self.ev if a - 0.05 <= e[0] < min(b, a + 0.6) and e[2] == subj
                        and e[3] in ("fist", "cheer", "jump", "head_pop", "hair")), None)
            pointing = next((e for e in self.ev if a - 0.2 <= e[0] < b and e[3] == "point" and e[4]), None)
            if strings:                                     # puppeteer and puppets in one frame
                kind = "wide"
            elif cm:
                target = self.target_point(cm["figure"])
                pointer = next((e for e in self.ev if e[3] == "point" and abs(e[0] - cm["t"]) < 1.0), None)
                kind = "reveal" if (pointer and prev != "reveal" and r.random() < 0.7) else "detail"
                if pointer:
                    subj = pointer[2]
            elif big:
                kind = "close"
            elif pointing and self.target_point(pointing[4]):
                target = self.target_point(pointing[4])
                kind = "reveal"
                subj = pointing[2]
            elif self.screen_talks(a, b, subj) and prev != "monitor":   # the monitor sings: frame the screen
                kind = "monitor"                            # (every other shot - the figures act it out between)
            elif i == 0:
                kind = r.choice(["medium", "wide", "mclose"]) if not lively else "wide"
            else:
                pool = [s for s in sizes if s != prev and (s != "two" or others)]
                if b - a < 1.3:
                    pool = [s for s in pool if s in ("mclose", "close", "medium")] or pool
                kind = r.choice(pool)
            word = next((x for x in self.fx if x["kind"] == "brick_word" and a - 0.3 <= x["t"] < b), None)
            if word:                                        # a word of bricks builds itself: show all of it
                kind, target = "letters", word
            appear = self.coins and self.coins[0] > self.S + 0.05 and a <= self.coins[0] < b
            gone = self.coins_gone and a <= min(self.coins_gone) < b
            if appear and kind not in ("reveal", "detail", "monitor", "letters", "wide"):
                kind = "medium"                             # coins appear in the shot: keep the desk in frame
            if gone and kind not in ("letters",) and anchor(self.kind, "coins", self.flip):
                kind = "coins"                              # the stack vanishes: frame the stack and the subject
            steam = next((x for x in self.fx if x["kind"] == "steam" and x.get("figure") in self.castd
                          and a < x["times"][-1] + 0.9 and x["times"][0] < b), None)
            if steam and kind not in ("reveal", "detail", "letters", "monitor", "coins"):
                subj = steam["figure"]                      # the steaming head stays in frame, with headroom
                kind = "medium"
            other = others[0] if others else None
            if a >= self.E - 1.2 and i > 0 and kind not in ("reveal", "detail", "monitor", "letters"):
                kind = "wide"
            cam, camb, aim, aimb, lens, focus, fstop = self.camera(
                "two" if kind == "two" else kind, subj, r, other=other, target=target)
            if steam and kind == "medium":                  # tilt up: the puffs rise ~80 LDU above the head
                cam, camb, aim, aimb = [(q[0], q[1] - 28, q[2]) for q in (cam, camb, aim, aimb)]
            shake = round(r.uniform(0.0, 1.5), 2) if lively else 0.0
            out.append(dict(t0=round(a, 3), t1=round(b, 3), kind=kind, subject=subj,
                            cam=[[round(v, 1) for v in cam], [round(v, 1) for v in camb]],
                            aim=[[round(v, 1) for v in aim], [round(v, 1) for v in aimb]],
                            lens=lens, focus=[round(v, 1) for v in focus], fstop=fstop, shake=shake))
            prev = kind
        return out

    # ---------------- screen
    def screen(self):
        idle = self.o.get("idle_screen", {"kind": "code"})
        tiles = [idle]
        events = []
        for s in self.rules("screen"):
            for w in self.words_for(s["word"]):
                tile = {k: v for k, v in s.items() if k not in ("word", "duration")}
                tiles.append(tile)
                events.append([round(w["t"] - 0.05, 3), round(min(self.E, w["t"] + float(s.get("duration", 1.6))), 3),
                               len(tiles) - 1])
        light = []
        for tl in tiles:
            col = tl.get("color", "#78e6ff" if tl.get("kind") != "heart" else "#ff4682").lstrip("#")
            rgb = [int(col[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            light.append([round(0.35 + 0.65 * c, 3) for c in rgb])
        return dict(tiles=len(tiles), tile_specs=tiles, events=events, light=light, idle=0)

    # ---------------- all together
    def plan(self):
        P = self.P
        st = self.set_spec()
        cast = self.cast()
        self.events()
        for c in cast:
            if not c.get("screen"):
                c["keys"] = [[round(t, 3), {k: round(v, 2) for k, v in d.items()}] for t, d in self.keys(c["name"])]
                r = self.r(f"blink:{c['name']}")
                t, bl = self.S + r.uniform(0.3, 1.5), []
                while t < self.E:
                    bl.append(round(t, 2))
                    t += r.uniform(2.4, 4.6)
                c["blinks"] = bl
        shots = self.shots()
        scr = self.screen()
        props = [{"kind": "glow"}]
        if self.coins:
            props.append({"kind": "coins", "times": [round(x, 3) for x in self.coins]})
            if self.coins_gone:
                props[-1]["gone"] = [round(x, 3) for x in self.coins_gone]
            st["coins"] = len(self.coins)
        if self.kind == "stage":
            props.append({"kind": "spots_cycle"})
        if self.kind in ("stage", "rooftop"):
            props.append({"kind": "bulbs_chase"})
        if self.kind in ("arena",):
            props.append({"kind": "bulbs_chase"})
        props += self.lights + self.fx + self.strings
        enter, leave = self.o.get("enter"), self.o.get("exit")
        if enter in ("assemble", "build"):                  # the set builds itself from flying bricks
            props.append({"kind": "set_flight", "t": self.S, "d": float(self.o.get("enter_time", 1.0)), "mode": "in"})
        if leave in ("collapse", "fly_away"):               # ... or flies apart at the end of the section
            d = float(self.o.get("exit_time", 1.0))
            props.append({"kind": "set_flight", "t": round(self.E - d, 3), "d": d, "mode": "out"})
        seed = creative.seed(P)
        plan = {
            "section": self.name, "from": self.S, "to": self.E, "fps": P.fps, "seed": seed,
            "out": str(P.dir / "scenes" / self.name), "stills": str(P.dir / "stills" / self.name),
            "textures": str(P.cache / "bricks_tex"), "exposure_file": str(P.cache / f"exposure_{self.name}.json"),
            "render": {"width": P.size[0], "height": P.size[1], "samples": int(self.o.get("samples", 32)),
                       "quality": self.o.get("quality", "gaps=0.2,bevel=0.3,wobble=0.6,abs=1"),
                       "jitter": float(self.o.get("jitter", 0.3))},
            "set": st, "beats": [round(b, 3) for b in self.beats if self.S - 1 <= b <= self.E + 1],
            "figures": cast, "screen": scr, "props": props, "shots": shots,
        }
        d = P.dir / "bricks"
        d.mkdir(exist_ok=True)
        f = d / f"{self.name}.json"
        f.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        acts = [{"t": round(e[0], 3), "figure": e[2], "gesture": SOUND_OF[e[3]]} for e in self.ev
                if e[3] in SOUND_OF and e[5] != "listen"]
        (P.analysis / f"actions_{self.name}.json").write_text(json.dumps(acts, ensure_ascii=False), encoding="utf-8")
        lens = [s["t1"] - s["t0"] for s in shots]
        on_beat = sum(1 for s in shots[1:] if min([abs(s["t0"] - b) for b in self.beats] or [9]) < 0.06)
        print(f"-> bricks/{self.name}.json: set {self.kind} (palette {st['palette_index']}, flip {self.flip}), "
              f"cast {[c['name'] for c in cast]}, {len(shots)} shots (mean {sum(lens) / max(len(lens), 1):.2f} s, "
              f"{on_beat}/{max(len(shots) - 1, 0)} cuts on a beat), kinds {[s['kind'] for s in shots]}, "
              f"gestures {sum(1 for e in self.ev if e[5] != 'listen')}, cameos {len(self.cameos)}, coins {len(self.coins)}, "
              f"screens {scr['tiles'] - 1}, seed {seed}")
        return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("section", nargs="?")
    ap.add_argument("--project", default=".")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    P = Project(a.project)
    names = [s["name"] for s in P.sections()] if a.all or not a.section else [a.section]
    for n in names:
        Planner(P, n).plan()


if __name__ == "__main__":
    main()
