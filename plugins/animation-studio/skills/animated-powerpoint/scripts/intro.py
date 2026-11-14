"""Deck intro: the title slide lights up in a dark room, slides flip faster and faster on the narrator's words, words of
a word cloud fly out of the slide, keywords land exactly on their spoken word, a hard stop on a card where a word is
struck through and another one is written by hand, then a story slide types its title word by word with the voice,
wobbles as if someone shook it from behind and turns over like a page - behind it lies the first frame of the next
clip, so the cut is invisible (reference: S0/S1 of the ai_efficiency film).

  intro.py clips/<name>/intro.json [--from tex|3d|final|sound]

intro.json (paths relative to it; times are frames or time specs as in clip.py: {"line": id, "word": w, "end": true})
  {"deck": "../../deck/deck.json", "size": [1920, 1080], "fps": 24,
   "narration": [{"id": "s0", "audio": "voice/s0.wav", "at": 12},
                 {"id": "s1", "audio": "voice/s1.wav", "at": {"fig": "intro", "event": "story", "offset": 6}}],
   "title_slide": 1,
   "flips": {"slides": [2, 3, 6, 7], "at": {"line": "s0", "word": "10"}, "frames": [12, 10, 8, 7]},
   "cloud": {"words": ["Integration", ...], "from": {"line": "s0", "word": "change", "end": true}, "seed": 3},
   "keys": [{"text": "New Models", "at": {"line": "s0", "word": "models"}, "x": -3.2, "y": 1.2, "color": "#1f7ac0"}],
   "card": {"small": "My AI Journey", "big": ["A ", "year", " of AI"], "strike": 1,
            "strike_at": {"line": "s0", "word": "every"}, "write": "week", "write_at": {"line": "s0", "word": "week"}},
   "story": {"slide": 4, "title": "Who keeps changing my office?", "line": "s1", "pos": [260, 1500]},
   "next_image": "../meet_the_cast/frames_3d/mp_0000.png"}
Defaults: the card comes 4 frames before the strike; the story starts 14 frames after both the first line and the
handwriting end; wobble right after the last title word, page turn after the wobble, 4 frames of the next image.
Steps: tex (textures + intro_stage.json + plan.json) -> 3d (assets/intro25d.html via toon-2d render_multiplane.py)
-> final (look) -> sound (narration + clicks, whooshes, keys, strike, typewriter, knocks, page turn).
Usage: uv run --no-project --with pillow --with numpy --with faster-whisper python intro.py clips/intro/intro.json
"""
import json
import math
import random
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import _studio
_studio.use("toon-2d", "film-finish")
import config  # noqa: E402
import creative  # noqa: E402

HERE = Path(__file__).resolve().parent
COLORS = [(0xE0, 0x8A, 0x1E), (0x8E, 0x44, 0xAD), (0x1F, 0x7A, 0xC0), (0x16, 0x8F, 0x7A), (0x44, 0x6F, 0x5C),
          (0xC0, 0x39, 0x2B), (0x2C, 0x3E, 0x50)]
BLUE, RED = (0x1F, 0x7A, 0xC0), (0xC8, 0x1E, 0x1E)


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def hexcol(c, default):
    if c is None:
        return default
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c)


def font(kind, size):
    from clip import font as f2
    if kind == "hand":
        import os
        for d in [Path(os.environ.get("WINDIR", "")) / "Fonts", Path("/usr/share/fonts/truetype")]:
            for n in ("segoeprb.ttf", "segoepr.ttf", "comicbd.ttf"):
                if (d / n).exists():
                    return ImageFont.truetype(str(d / n), size)
    return f2(kind == "bold", size)


def text_png(text, size, color, kind="bold", pad=20):
    f = font(kind, size)
    l, t, r, b = f.getbbox(text)
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=f, fill=color + (255,))
    return im


class Intro:
    def __init__(self, path):
        from clip import Times
        self.file = Path(path).resolve()
        self.dir = self.file.parent
        self.p = json.loads(self.file.read_text(encoding="utf-8"))
        self.deck_file = (self.dir / self.p.get("deck", "../../deck/deck.json")).resolve()
        self.deck = json.loads(self.deck_file.read_text(encoding="utf-8"))
        self.fps = self.p.get("fps", 24)
        w = self.p.get("size", [1920, round(1920 * self.deck["height"] / self.deck["width"] / 2) * 2])
        self.size = (int(w[0]), int(w[1]))
        self.T = Times(self)
        self.T.events["intro"] = {}

    def slide_png(self, n):
        s = next(x for x in self.deck["slides"] if x["n"] == n)
        return self.deck_file.parent / s["clean"]


def title_word(ws, k0, target):
    """(first, last) Whisper word index of a title word from index k0 on: the same word, several heard words that
    join into it ("A." "I." -> "AI"), or a heard word that starts with it; None when it is not in the line."""
    from narration import norm
    if not target:
        return None
    for i in range(k0, len(ws)):
        joined = ""
        for j in range(i, min(i + 4, len(ws))):
            joined += norm(ws[j]["w"]).replace("'", "")
            if joined == target.replace("'", ""):
                return i, j
            if not target.replace("'", "").startswith(joined):
                break
    for i in range(k0, len(ws)):
        if norm(ws[i]["w"]).startswith(target):
            return i, i
    return None


def plan_and_textures(I):
    P, T, tex = I.p, I.T, I.dir / "tex"
    tex.mkdir(exist_ok=True)
    sw, sh = I.deck["width"], I.deck["height"]
    WS, HS = 16.0, 16.0 * sh / sw
    z0 = (HS / 2) / math.tan(math.radians(15))
    lines = {n["id"]: n for n in P.get("narration", [])}
    first_line = P["narration"][0]["id"] if P.get("narration") else None
    # ---- times
    fl = P.get("flips", {})
    t_flip0 = T(fl.get("at", 40))
    card = P.get("card")
    t_strike = T(card["strike_at"]) if card else None
    t_card = T(card["at"]) if card and card.get("at") is not None else (t_strike - 4 if card else None)
    t_write = T(card["write_at"]) if card and card.get("write") else None
    w_dur = card.get("write_frames", 12) if card else 0
    durs = fl.get("frames") or [max(2, round(12 * 0.84 ** i)) for i in range(len(fl.get("slides", [])))]
    flips, f = [], t_flip0
    for n, d in zip(fl.get("slides", []), durs):
        flips.append((f, n))
        f += d
    keys = [(k, T(k["at"])) for k in P.get("keys", [])]
    cl = P.get("cloud", {})
    t_change = T(cl["from"]) if cl.get("from") is not None else t_flip0
    stop = t_card if t_card is not None else (f + 6)
    first_end = T({"line": first_line, "edge": "end"}) if first_line else stop
    st = P.get("story")
    S1 = T(st["at"]) if st and st.get("at") is not None else max(first_end, (t_write + w_dur) if t_write else stop) + 14
    T.events["intro"]["story"] = S1
    title_times, t_title_end = [], S1 + 40
    if st:
        words = st["title"].split(" ")
        if st.get("line"):
            res = T.words(st["line"])
            import narration
            at = T.line_at(st["line"])
            k0, ws = 0, res["words"]
            for w in words:
                hit = title_word(ws, k0, narration.norm(w))
                if hit is None:                  # not heard: 8 frames after the previous title word
                    print(f"  title word '{w}' not found in the line '{' '.join(x['w'] for x in ws)}' - placed by time")
                    t = (title_times[-1] + 8) if title_times else at
                    title_times.append(t)
                    t_title_end = t + 8
                    continue
                a, b = hit
                title_times.append(at + round(ws[a]["s"] * I.fps))
                t_title_end = at + round(ws[b]["e"] * I.fps)
                k0 = b + 1
        else:
            title_times = [S1 + 30 + 8 * i for i in range(len(words))]
            t_title_end = title_times[-1] + 8
    wob = (t_title_end + 2, t_title_end + 28)
    turn = (wob[1] + 3, wob[1] + 27)
    end = turn[1] + 4 if st else stop + 40
    # ---- textures
    names = {}

    def slide_tex(n):
        if n not in names:
            names[n] = f"tex/slide_{n:02d}.png"
            shutil.copy(I.slide_png(n), I.dir / names[n])
        return f"s{n:02d}"
    title_key = slide_tex(P.get("title_slide", 1))
    for _, n in flips:
        slide_tex(n)
    if st:
        slide_tex(st["slide"])
    wtex = []
    for i, w in enumerate(cl.get("words", [])):
        im = text_png(w, 120, hexcol(None, COLORS[i % len(COLORS)]), "regular" if i % 3 else "bold")
        im.save(tex / f"word_{i:02d}.png")
        wtex.append({"src": f"tex/word_{i:02d}.png", "aspect": im.size[0] / im.size[1]})
    ktex = []
    for i, (k, _) in enumerate(keys):
        im = text_png(k["text"], 170, hexcol(k.get("color"), BLUE))
        im.save(tex / f"key_{i}.png")
        ktex.append({"src": f"tex/key_{i}.png", "aspect": im.size[0] / im.size[1]})
    W4, H4 = 3840, round(3840 * sh / sw)
    year_x = [0, 0]
    if card:
        c = Image.new("RGB", (W4, H4), "white")
        d = ImageDraw.Draw(c)
        fs, fb = font("regular", 150), font("bold", 330)
        d.text((W4 / 2, 720 * H4 / 2160), card.get("small", ""), font=fs, fill=(20, 20, 20), anchor="mm")
        parts = card["big"]
        total = sum(fb.getlength(p) for p in parts)
        x0, y = (W4 - total) / 2, 1150 * H4 / 2160
        xs = []
        for p in parts:
            xs.append(x0)
            d.text((x0, y), p, font=fb, fill=hexcol(card.get("color"), BLUE), anchor="lm")
            x0 += fb.getlength(p)
        c.save(tex / "card.png")
        names["card"] = "tex/card.png"
        k = card.get("strike", 1)
        yl, yr = xs[k], xs[k] + fb.getlength(parts[k])
        s = Image.new("RGBA", (W4, H4), (0, 0, 0, 0))
        ImageDraw.Draw(s).line([(yl - 30, y + 30), (yr + 30, y - 40)], fill=RED + (255,), width=34)
        s.save(tex / "strike.png")
        wk = Image.new("RGBA", (W4, H4), (0, 0, 0, 0))
        if card.get("write"):
            hw = text_png(card["write"], 300, RED, "hand", pad=40).rotate(9, resample=Image.BICUBIC, expand=True)
            wk.alpha_composite(hw, (int(yl - 120), int(y - 560)))
        wk.save(tex / "write.png")
        year_x = [yl / W4, yr / W4]
    bounds = []
    tim = Image.new("RGBA", (W4, H4), (0, 0, 0, 0))
    if st:
        tf = font("bold", 150)
        td = ImageDraw.Draw(tim)
        tx, ty = st.get("pos", [260, 1500])
        title = st["title"]
        td.text((tx + 8, ty + 10), title, font=tf, fill=(0, 30, 70, 120), anchor="lm")
        td.text((tx, ty), title, font=tf, fill=hexcol(st.get("color"), (255, 255, 255)) + (255,), anchor="lm")
        pos = 0
        for w in title.split(" "):
            pos = title.index(w, pos) + len(w)
            bounds.append((tx + tf.getlength(title[:pos]) + 8) / W4)
    tim.save(tex / "title.png")
    nxt = P.get("next_image")
    if nxt:
        Image.open(I.dir / nxt).convert("RGB").save(tex / "next.png")
    else:
        Image.new("RGB", I.size, (28, 26, 24)).save(tex / "next.png")
    # ---- per frame
    seed_rng = random.Random(cl["seed"]) if "seed" in cl else creative.rng(P, "cloud")
    cloud = []
    nwords = len(wtex)
    for i in range(nwords):
        t0 = t_change - 10 + int(i * (stop - t_change + 4) / max(1, nwords)) + seed_rng.randint(-3, 3)
        cloud.append({"i": i, "t0": t0, "x": seed_rng.uniform(-6.5, 6.5) * WS / 16, "y": seed_rng.uniform(-3.6, 3.6) * HS / 9,
                      "vz": seed_rng.uniform(4, 7), "rot": seed_rng.uniform(-0.2, 0.2), "h": seed_rng.uniform(0.35, 0.6)})
    kd = [{"i": i, "t0": t, "x": k.get("x", [-3.2, 0.4, 3.6][i % 3]), "y": k.get("y", [1.2, -1.0, 1.6][i % 3]),
           "vz": 2.6, "rot": 0, "h": k.get("h", 1.1)} for i, (k, t) in enumerate(keys)]
    frames = []
    for f in range(end + 1):
        if f < S1 or not st:
            slide = title_key
            for t, n in flips:
                if f >= t:
                    slide = f"s{n:02d}"
            if t_card is not None and f >= t_card:
                slide = "card"
            glow = smooth(f / 16)
            push = smooth((f - t_flip0) / max(1, stop - t_flip0))
            cam = [0, 0, z0 - 0.35 * smooth(f / max(1, t_flip0)) - 2.2 * push]
            if t_card is not None and f >= t_card:
                cam = [0, 0, z0 - 0.25 * smooth((f - t_card) / 8) - 0.55 * smooth((f - t_strike) / 10)]
            shake = 0.0
            for t, _ in flips:
                if 0 <= f - t < 4:
                    shake = 0.03 * (1 - (f - t) / 4)
            cam[0] += shake * math.sin(f * 2.1)
            cam[1] += shake * math.cos(f * 1.7)
            ws = []
            for w in cloud + kd:
                t = f - w["t0"]
                if t < 0 or f >= stop:
                    continue
                key = w in kd
                z = 0.05 + w["vz"] * t / I.fps + (0 if key else 0.5 * 3.0 * (t / I.fps) ** 2)
                if z > (15.0 if key else 9.5):
                    continue
                ws.append([w["i"], 1 if key else 0, round(w["x"], 3), round(w["y"], 3), round(z, 3),
                           round(w["rot"] * t / I.fps, 3), w["h"], round(min(1, t / 5) * (1 if key else min(1, (9.5 - z) / 3)), 3)])
            fr = {"slide": slide, "glow": round(glow, 3), "cam": [round(v, 4) for v in cam], "words": ws}
            if card:
                fr["strike"] = round(smooth((f - t_strike) / 7), 3)
                fr["write"] = round(smooth((f - t_write) / w_dur), 3) if t_write else 0
            frames.append(fr)
        else:
            rev = 0.0
            for t, g in zip(title_times, bounds):
                if f >= t:
                    rev = g
            wo = 0.0
            if wob[0] <= f <= wob[1]:
                u = (f - wob[0]) / (wob[1] - wob[0])
                wo = math.sin(u * math.pi * 9) * math.sin(u * math.pi)
            tu = smooth((f - turn[0]) / (turn[1] - turn[0]))
            flash = max(0.0, 1 - (f - S1) / 6)
            t_who = title_times[0] if title_times else S1 + 30
            z = z0 - 0.7 * smooth((f - S1) / max(1, t_who - S1)) + 0.7 * smooth((f - wob[0]) / max(1, turn[0] - wob[0]))
            frames.append({"slide": f"s{st['slide']:02d}", "glow": 1, "cam": [0, 0, round(z, 4)], "words": [],
                           "title": round(rev, 4), "wobble": round(wo, 4), "turn": round(tu, 4), "flash": round(flash, 3)})
    cfg = {"width": I.size[0], "height": I.size[1], "fps": I.fps, "end": end, "fov": 30, "out": "frames_3d",
           "slide_w": WS, "slide_h": HS, "slides": {(k if k == "card" else f"s{k:02d}"): v for k, v in names.items()},
           "words": wtex, "keys": ktex, "frames": frames, "year_x": year_x}
    (I.dir / "intro_stage.json").write_text(json.dumps(cfg), encoding="utf-8")
    ev = {"flips": [t for t, _ in flips], "card": t_card, "strike": t_strike, "write": t_write,
          "keys": [t for _, t in keys], "title": title_times, "wobble": list(wob), "turn": list(turn), "story": S1,
          "end": end, "cloud": [w["t0"] for w in cloud]}
    narr = {lid: {"at": T.line_at(lid), "audio": lines[lid]["audio"], "level": lines[lid].get("level", 0)} for lid in lines}
    (I.dir / "plan.json").write_text(json.dumps({"end": end, "events": ev, "narration": narr}, indent=1), encoding="utf-8")
    print("  intro plan:", json.dumps({k: v for k, v in ev.items() if k != "cloud"}))
    return ev


def sound(I):
    import sound as S
    plan = json.loads((I.dir / "plan.json").read_text(encoding="utf-8"))
    E = plan["events"]
    m = S.Mix(plan["end"] + 1, I.fps, I.dir.parent.parent / "cache" / "sfx")
    for lid, ln in plan["narration"].items():
        m.voice(I.dir / ln["audio"], ln["at"], -14 + ln.get("level", 0))
    m.sfx(4, "fit/snap/switch_flip", [], -20)
    if E["card"] is not None:
        m.sfx(E["card"], "riser/build", [], -24)
        m.sfx(E["card"], "cut_hit/air", [], -22)
    for i, f in enumerate(E["flips"]):
        m.sfx(f, "click/snap", [], -22 - (i % 2), 0.1 * ((-1) ** i))
    for i, f in enumerate(E["keys"]):
        m.sfx(f + 6, "whoosh_fast/crisp", ["--dur", "0.5", "--apex", "0.2"], -21, [-0.4, 0.05, 0.4][i % 3])
    for i, f in enumerate(E["cloud"][::3]):
        m.sfx(f + 10, "swish/soft", ["--dur", "0.4", "--apex", "0.15"], -31, 0.5 * ((-1) ** i))
    if E["strike"] is not None:
        m.sfx(E["strike"] + 4, "swish/blade", [], -21, -0.1)
    if E["write"] is not None:
        m.sfx(E["write"] + 4, "swish/stick", ["--dur", "0.4", "--apex", "0.15"], -24, -0.1)
        m.sfx(E["write"] + 12, "pro_pop/tink", [], -27, -0.1)
    if E["title"]:
        m.sfx(E["story"], "whoosh_fast/whip", ["--dur", "0.5", "--apex", "0.1"], -22)
        for f in E["title"]:
            m.sfx(f + 1, "fit/key/medium", [], -20, -0.3)
        for k in range(5):
            m.sfx(E["wobble"][0] + 2 + k * 5, "knock/plastic", [], -23 - k, 0.2 * ((-1) ** k))
        m.sfx(E["turn"][0] + 13, "whoosh_fast/sleeve", ["--dur", "0.8", "--apex", "0.45"], -20, -0.3)
    wav = I.dir / "ton.wav"
    m.write(wav, loudnorm=True)
    S.mux(I.dir / f"{I.dir.name}.mp4", wav)
    print(f"  sound: {m.count} effects + {len(plan['narration'])} lines" + (f" missing {m.missing}" if m.missing else ""))


def main():
    I = Intro(sys.argv[1])
    steps = ["tex", "3d", "final", "sound"]
    start = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else "tex"
    for s in steps[steps.index(start):]:
        if s == "tex":
            plan_and_textures(I)
        elif s == "3d":
            shutil.copy(HERE.parent / "assets" / "intro25d.html", I.dir / "intro25d.html")
            subprocess.run([sys.executable, str(_studio.skill_dir("toon-2d") / "scripts" / "render_multiplane.py"),
                            str(I.dir / "intro_stage.json"), "--page", "/intro25d.html", "--contact", "none"], check=True)
        elif s == "final":
            raw = I.dir / "intro_stage.mp4"
            out = I.dir / f"{I.dir.name}.mp4"
            if I.p.get("look", "standard") != "none":
                subprocess.run([sys.executable, str(_studio.skill_dir("film-finish") / "scripts" / "apply_look.py"),
                                str(raw), "-o", str(out), "--look", I.p.get("look", "standard")], check=True)
            else:
                shutil.copy(raw, out)
            n = json.loads((I.dir / "plan.json").read_text())["end"]
            check = {"frames": n + 1, "seconds": round((n + 1) / I.fps, 2), "size": list(I.size)}
            nxt = I.dir / "tex" / "next.png"
            if I.p.get("next_image"):
                a = np.asarray(Image.open(I.dir / "frames_3d" / f"mp_{n:04d}.png").convert("RGB"), np.int16)
                b = np.asarray(Image.open(nxt).convert("RGB").resize(I.size), np.int16)
                check["last_vs_next"] = round(float(np.abs(a - b).mean()), 3)
            (I.dir / "check.json").write_text(json.dumps(check, indent=1), encoding="utf-8")
            print("  ->", out, check)
        elif s == "sound" and I.p.get("sound", True):
            sound(I)


if __name__ == "__main__":
    main()
