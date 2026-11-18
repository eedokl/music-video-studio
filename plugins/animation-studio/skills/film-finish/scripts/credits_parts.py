"""Renderers of the parts of the end credits (credits.py): the rolling text with its scene windows (film excerpts and
outtakes) and the gag scenes (also the post-credits scene). Every renderer yields / returns 1280x720 RGB frames.
Imported only - no CLI."""
import math

from PIL import Image, ImageDraw, ImageFilter

from credits_media import (BG_COL, CREAM, GOLD, GREY, INK, H, W, clamp, ease, envelope, font, nframes, rgb,
                           video_frames)


# ============================================================ drawing helpers of the gag scenes
def draw_mouth(img, shape, x, y, s=1.0, scale=1.0, open_=0.0):
    """Expression mouths: smile, o, open, flat, grin (white, for silhouettes), none. open_ 0..1 = audio-driven opening."""
    d = ImageDraw.Draw(img)
    r = lambda v: v * s
    if shape == "grin":
        gw = 36 * s * scale
        if open_ > 0.05:
            d.chord((x - gw, y - r(6), x + gw, y + gw * (0.9 + 0.8 * open_)), 0, 180, fill=(243, 243, 243))
            d.chord((x - gw * 0.6, y + gw * 0.5, x + gw * 0.6, y + gw * (0.9 + 0.7 * open_)), 0, 180, fill=(20, 10, 12))
        else:
            d.arc((x - gw, y, x + gw, y + gw * 0.9), 20, 160, fill=(243, 243, 243), width=max(2, int(r(8))))
        return
    if open_ > 0.05 and shape != "none":                     # talking/laughing: an open mouth sized by the loudness
        ry = r(6 + 26 * open_)
        d.ellipse((x - r(20), y - r(6), x + r(20), y - r(6) + ry + r(8)), fill=(122, 31, 43), outline=INK,
                  width=max(2, int(r(5))))
        return
    if shape == "smile":
        d.arc((x - r(26), y - r(22), x + r(26), y + r(12)), 20, 160, fill=INK, width=max(2, int(r(6))))
    elif shape == "o":
        d.ellipse((x - r(13), y - r(8), x + r(13), y + r(20)), fill=(122, 31, 43), outline=INK, width=max(2, int(r(5))))
    elif shape == "open":
        d.ellipse((x - r(24), y - r(6), x + r(24), y + r(36)), fill=(122, 31, 43), outline=INK, width=max(2, int(r(5))))
        d.ellipse((x - r(12), y + r(16), x + r(12), y + r(32)), fill=(232, 120, 120))
    elif shape == "flat":
        d.line((x - r(18), y + r(6), x + r(18), y + r(6)), fill=INK, width=max(2, int(r(6))))


def paste(img, fig, x, y_feet, ang=0.0, alpha=1.0):
    t = fig.rotate(ang, expand=True, resample=Image.BICUBIC) if ang else fig
    if alpha < 1:
        t = t.copy()
        t.putalpha(t.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(t, (int(x - t.width / 2), int(y_feet - t.height)))


def item_alpha(it, t):
    a0, a1 = it.get("at", -1e9), it.get("to", 1e9)
    if not a0 <= t < a1:
        return 0.0
    a = 1.0
    if it.get("fade_in"):
        a = min(a, clamp((t - a0) / it["fade_in"]))
    if it.get("fade_out"):
        a = min(a, clamp((a1 - t) / it["fade_out"]))
    return a


def step_at(steps, t):
    cur = None
    for s in sorted(steps, key=lambda s: s.get("at", 0)):
        if t >= s.get("at", 0):
            cur = s
    return cur


def figure_pose(it, t, f, fps):
    """Position of a figure item after its "moves": -> (x, feet y, angle), or None while a "rise" has not begun."""
    x, y, ang = float(it.get("x", 640)), float(it.get("feet", 700)), 0.0
    for mv in it.get("moves", []):
        do = mv.get("do")
        at, dur = float(mv.get("at", mv.get("from", 0))), float(mv.get("dur", 0.5))
        if do == "bob" and mv.get("from", 0) <= t < mv.get("to", 1e9):
            half = max(1, round(float(mv.get("period", 0.25)) * fps / 2))
            y -= float(mv.get("amp", 6)) if (f // half) % 2 else 0
        elif do == "jump" and at <= t < at + dur:
            y -= float(mv.get("height", 40)) * math.sin(math.pi * clamp((t - at) / dur))
        elif do == "fall" and t >= at:
            u = ease(clamp((t - at) / dur))
            x += float(mv.get("dx", -120)) * u
            y += float(mv.get("dy", 650)) * u * u
            ang += float(mv.get("angle", 75)) * u
        elif do == "rise":
            if t < at:
                return None
            y += float(mv.get("from", 450)) * (1 - ease(clamp((t - at) / dur)))
        elif do == "tilt" and mv.get("from", 0) <= t < mv.get("to", 1e9):
            ang += float(mv.get("angle", -8))
        elif do == "drift" and t >= mv.get("from", 0):
            u = clamp((t - mv["from"]) / max(1e-6, mv.get("to", mv["from"] + 1) - mv["from"]))
            x += float(mv.get("dx", 0)) * u
            y += float(mv.get("dy", 0)) * u
        elif do == "sink" and t >= at:
            u = ease(clamp((t - at) / dur))
            y += float(mv.get("dy", 90)) * u
            if t < mv.get("until", 1e9):
                ang += float(mv.get("angle", -14)) * u
        elif do == "startle" and t >= at:
            u = clamp((t - at) / dur)
            y -= float(mv.get("up", 150)) * u
            if t >= at + dur:
                y += float(mv.get("settle", 40)) * (1 - math.exp(-(t - at - dur) * fps / 4))
        elif do == "wave" and mv.get("from", 0) <= t < mv.get("to", 1e9):
            ang += float(mv.get("angle", 1.8)) * math.sin(f * float(mv.get("speed", 1 / 3)))
    return x, y, ang


def mouth_at_time(mspec, t):
    """Mouth shape and width scale at time t: a fixed shape or [[t, shape(, scale)], ...] (scale eases in 0.42 s)."""
    shape, scale = "smile", 1.0
    if isinstance(mspec, str):
        return mspec, scale
    prev = 1.0
    for e in sorted(mspec, key=lambda e: e[0]):
        if t >= e[0]:
            shape = e[1]
            sc = float(e[2]) if len(e) > 2 else 1.0
            scale = prev + (sc - prev) * ease(clamp((t - e[0]) / 0.42))
            prev = sc
    return shape, scale


def audio_drive(au, env, f, fps):
    """Mouth opening (0..1) and shoulder shake (px) of an audio-driven figure in frame f."""
    k = f - nframes(au.get("at", 0), fps)
    lv = float(env[k]) if 0 <= k < len(env) else 0.0
    if k < 0:
        return 0.0, 0
    return clamp(k / 4) * clamp(0.15 + 1.1 * lv), int(float(au.get("shake", 7)) * lv * math.sin(f * 1.9))


def card_image(c):
    """A paper card prop: title, rows of (left, right), a red total line."""
    rows = c.get("rows", [])
    h = 200 + 46 * len(rows)
    img = Image.new("RGBA", (300, h), (0, 0, 0, 0))
    k = ImageDraw.Draw(img)
    fr, ft = font("script", 24), font("script_b", 30)
    k.rectangle((0, 0, 299, h - 1), fill=(251, 251, 245), outline=INK, width=4)
    k.text((26, 22), c.get("title", ""), font=font("impact", 46), fill=INK)
    k.line((26, 86, 274, 86), fill=INK, width=3)
    for i, (a, b) in enumerate(rows):
        k.text((26, 104 + i * 46), a, font=fr, fill=INK)
        k.text((274 - k.textlength(b, font=fr), 104 + i * 46), b, font=fr, fill=INK)
    if c.get("total"):
        y = 120 + 46 * len(rows)
        k.line((26, y, 274, y), fill=INK, width=3)
        a, b = c["total"]
        k.text((26, y + 12), a, font=ft, fill=(192, 38, 45))
        k.text((274 - k.textlength(b, font=ft), y + 12), b, font=ft, fill=(192, 38, 45))
    return img


def wrap(text, f_, width):
    """Greedy word wrap at a pixel width."""
    rows, cur = [], ""
    for w in str(text).split():
        tt = (cur + " " + w).strip()
        if f_.getlength(tt) > width:
            rows.append(cur)
            cur = w
        else:
            cur = tt
    rows.append(cur)
    return rows


# ============================================================ gag scenes (and the post-credits scene)
class Gag:
    """One gag scene (or the post-credits scene): a set, items in list order, sounds, zoom, lights out."""

    def __init__(self, spec, A, fps, kind="gag"):
        self.s, self.A, self.fps, self.kind = spec, A, fps, kind
        self.n = nframes(float(spec.get("duration", 6)), fps)
        self.back, self.front = A.set_layers(spec.get("set"))
        self.envs = {}
        self._glow = {}
        for it in spec.get("items", []):
            if it.get("type", "figure") == "figure" and it.get("audio"):
                self.envs[id(it)] = envelope(A.path(it["audio"]["file"]), fps)
        self.draw = {"figure": self.figure, "screen": self.screen, "banner": self.banner, "bubble": self.bubble,
                     "caption": self.no_draw, "bang": self.bang, "prop": self.prop, "count": self.count,
                     "clip": self.clip_item, "desk": self.desk, "spot": self.spot, "zzz": self.zzz}

    # ---- sound events (frame offset in the gag, source, level, low-pass, voice)
    def sounds(self):
        ev = [(nframes(x.get("at", 0), self.fps), x["sfx"], float(x.get("level", 1.0)), 6000, False)
              for x in self.s.get("sounds", [])]
        for it in self.s.get("items", []):
            au = it.get("audio")
            if au:
                ev.append((nframes(au.get("at", 0), self.fps), au["file"], float(au.get("level", 0.8)), 9000, True))
            if it.get("type") == "count" and it.get("sfx"):
                every = nframes(it.get("every", 0.5), self.fps)
                at = nframes(it.get("at", 0), self.fps)
                for k in range(int(it.get("moves", it.get("n", 10) - 1))):
                    ev.append((at + every * k + every // 2, it["sfx"], float(it.get("level", 0.7)), 6000, False))
        return ev

    # ---- items: every drawer has the signature (img, item, t, frame, mouths)
    def figure(self, img, it, t, f, mouths):
        a = item_alpha(it, t)
        if a <= 0:
            return
        fig, (mx, my), s = self.A.figure(it)
        pose = figure_pose(it, t, f, self.fps)
        if pose is None:
            return
        x, y, ang = pose
        shape, scale = mouth_at_time(it.get("mouth", "smile"), t)
        open_, shake = 0.0, 0
        au = it.get("audio")
        if au:
            open_, shake = audio_drive(au, self.envs[id(it)], f, self.fps)
        y += shake
        if shape == "grin":       # white grin on a dark silhouette: drawn on top, also after lights out
            def m(im, xx=x - fig.width / 2 + mx, yy=y - fig.height + my):
                draw_mouth(im, "grin", xx, yy, s, scale, open_)
            paste(img, fig, x, y, ang, a)
            m(img)
            if it.get("keep_mouth", True):
                mouths.append(m)
            return
        f2 = fig.copy()           # mouth drawn into a copy of the figure, so it turns with it
        draw_mouth(f2, shape, mx, my, s, scale, open_)
        paste(img, f2, x, y, ang, a)

    def _screen_glow(self, x0, y0, x1, y1, glow):
        key = (x0, y0, x1, y1, glow)
        if key not in self._glow:
            g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((x0 - 160, y0 - 120, x1 + 160, y1 + 120), fill=(95, 179, 255, int(min(255, 70 * glow))))
            self._glow[key] = g.filter(ImageFilter.GaussianBlur(60))
        return self._glow[key]

    def screen(self, img, it, t, f, mouths=None):
        st = step_at(it.get("steps", []), t) or {}
        x0, y0, x1, y1 = it.get("box", [700, 170, 1180, 500])
        sh = (0, 0)
        if st.get("shake") and t - st.get("at", 0) < st["shake"]:
            sh = (int(6 * math.sin(f * 2.1)), int(4 * math.cos(f * 1.7)))
        if st.get("shake_x"):
            sh = (int(5 * math.sin(f * 2)), 0)
        x0, x1, y0, y1 = x0 + sh[0], x1 + sh[0], y0 + sh[1], y1 + sh[1]
        glow = float(st.get("glow", 1.0)) if not st.get("shake") or t - st.get("at", 0) < st.get("shake", 0) else 1.0
        img.alpha_composite(self._screen_glow(x0, y0, x1, y1, glow))
        d = ImageDraw.Draw(img)
        d.rectangle((x0, y0, x1, y1), fill=(28, 31, 38), outline=INK, width=6)
        d.rectangle((x0 + 22, y0 + 22, x1 - 22, y1 - 22), fill=(107, 26, 26) if st.get("red") else (29, 59, 92))
        if it.get("stand", True):
            d.rectangle((x0 + 210, y1, x0 + 270, it.get("stand_to", 552)), fill=(48, 52, 62))
        self._screen_text(d, st, x0, y0, x1)
        bar = st.get("bar")
        if bar is not None:
            if isinstance(bar, (list, tuple)):
                nxt = [s["at"] for s in it["steps"] if s.get("at", 0) > st.get("at", 0)]
                span = (min(nxt) if nxt else st.get("at", 0) + 5) - st.get("at", 0)
                bar = bar[0] + (bar[1] - bar[0]) * clamp((t - st.get("at", 0)) / span)
            d.rectangle((x0 + 60, y0 + 210, x1 - 60, y0 + 240), outline=(232, 251, 255), width=3)
            d.rectangle((x0 + 64, y0 + 214, x0 + 64 + (x1 - x0 - 128) * bar, y0 + 236), fill=(95, 211, 138))
        elif st.get("eyes", True):
            for ex in (x0 + 170, x1 - 170):
                d.ellipse((ex - 22, y1 - 105, ex + 22, y1 - 61), fill=(232, 251, 255))
                d.ellipse((ex - 9, y1 - 92, ex + 9, y1 - 74), fill=(29, 59, 92))

    @staticmethod
    def _screen_text(d, st, x0, y0, x1):
        """Title (shrunk to fit) and the text lines of a screen step."""
        cx = (x0 + x1) / 2
        title, line = str(st.get("title", "")), str(st.get("line", ""))
        tf = font("impact", 46)
        while d.textlength(title, font=tf) > x1 - x0 - 60 and tf.size > 20:
            tf = font("impact", tf.size - 2)
        d.text((cx - d.textlength(title, font=tf) / 2, y0 + 60), title, font=tf, fill=(255, 243, 176))
        lf = font("script_b", 28)
        for i, row in enumerate(line.split("\n")):
            d.text((cx - d.textlength(row, font=lf) / 2, y0 + 150 + 40 * i), row, font=lf, fill=(232, 251, 255))

    def banner(self, img, it, t, f=None, mouths=None):
        st = step_at(it.get("steps", [{"at": 0, "text": it.get("text", "")}]), t)
        if not st:
            return
        d = ImageDraw.Draw(img)
        f_ = font("script_b", 28)
        txt = st["text"]
        tw = d.textlength(txt, font=f_)
        y = it.get("y", 90)
        d.rounded_rectangle((W / 2 - tw / 2 - 24, y, W / 2 + tw / 2 + 24, y + 60), 10, fill=(29, 59, 92), outline=INK, width=4)
        d.text((W / 2 - tw / 2, y + 10), txt, font=f_, fill=(232, 251, 255))

    def bubble(self, img, it, t, f=None, mouths=None):
        a0 = it.get("at", 0)
        u = (t - a0) * self.fps
        sc = 0.2 + u / 5 if u < 4 else 1.0 + 0.1 * math.exp(-(u - 4) / 2) * math.cos((u - 4) * 1.5)
        f_ = font("script_b", int(it.get("size", 30)))
        rows = wrap(it["text"], f_, it.get("width", 360))
        bw = int(max(f_.getlength(r) for r in rows) + 60)
        bh = int(len(rows) * f_.size * 1.3 + 40)
        x, y = it.get("x", 640), it.get("y", 200)
        tx, ty = it.get("tail", [x - bw / 3, y + bh])
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.polygon([(x - bw * 0.15, y + bh * 0.3), (x + bw * 0.05, y + bh * 0.3), (tx, ty)], fill="white", outline=INK, width=4)
        d.ellipse((x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2), fill="white", outline=INK, width=4)
        d.polygon([(x - bw * 0.13, y + bh * 0.28), (x + bw * 0.03, y + bh * 0.28), (tx, ty)], fill="white")
        for i, r in enumerate(rows):
            d.text((x - f_.getlength(r) / 2, y - bh / 2 + 20 + i * f_.size * 1.3), r, font=f_, fill=INK)
        if abs(sc - 1) > 0.01:                  # pop with a small overshoot, scaled about the bubble centre
            big = layer.resize((max(1, int(W * sc)), max(1, int(H * sc))), Image.BICUBIC)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            layer.paste(big, (int(x - x * sc), int(y - y * sc)))
        img.alpha_composite(layer)

    def no_draw(self, img, it, t, f=None, mouths=None):
        """Captions are drawn later, over the front layers (caption())."""

    def caption(self, img, it, t):
        d = ImageDraw.Draw(img)
        f_ = font("script_b", 30)
        a = clamp((t - it.get("at", 0)) * self.fps / 8)
        tw = d.textlength(it["text"], font=f_)
        d.rectangle((W / 2 - tw / 2 - 26, 628, W / 2 + tw / 2 + 26, 690), fill=BG_COL)
        d.text((W / 2 - tw / 2, 640), it["text"], font=f_, fill=tuple(int(v * a) for v in CREAM))

    def bang(self, img, it, t, f=None, mouths=None):
        span = max(1e-6, it.get("to", it.get("at", 0) + 0.67) - it.get("at", 0))
        s = float(it.get("size", 1.0)) * (1 + float(it.get("grow", 0.4)) * (1 - (t - it.get("at", 0)) / span))
        ImageDraw.Draw(img).text((it.get("x", 150), it.get("y", 420)), it["text"], font=font("impact", 70 * s),
                                 fill=rgb(it.get("color"), GOLD), stroke_width=5, stroke_fill=(23, 18, 13))

    def prop(self, img, it, t, f, mouths=None):
        if "_img" not in it:
            it["_img"] = card_image(it["card"]) if it.get("card") else self.A.image(it["image"])
        p = it["_img"]
        at = it.get("at", 0)
        path = it.get("path", "static")
        x, y = float(it.get("x", 640)), float(it.get("y", 300))
        if path == "drop":                      # swings in from the top and settles (a sheet of paper)
            fl = (t - at) * self.fps
            u = clamp((t - at) / float(it.get("dur", 1.67)))
            rot = float(it.get("swing", 25)) * math.sin(fl / 4.0) * (1 - u) + float(it.get("angle", 4))
            q = p.rotate(rot, expand=True, resample=Image.BICUBIC)
            img.alpha_composite(q, (int(x + float(it.get("sway", 120)) * math.sin(fl / 5.0) * (1 - u) - q.width / 2),
                                    int(y - 800 + 800 * ease(u))))
        elif path == "fall":                    # hangs in the air for a moment, then falls and wobbles
            t0 = at + float(it.get("hold", 0.08))
            u = clamp((t - t0) / float(it.get("dur", 0.5)))
            yy = y + float(it.get("drop", 360)) * u * u
            ang = float(it.get("angle", -20)) * u if u < 1 else float(it.get("angle", -20)) + 6 * math.sin(f)
            q = p.rotate(ang, expand=True)
            img.alpha_composite(q, (int(x - q.width / 2), int(yy)))
        else:
            q = p.rotate(float(it.get("angle", 0)), expand=True, resample=Image.BICUBIC) if it.get("angle") else p
            img.alpha_composite(q, (int(x - q.width / 2), int(y)))

    def count(self, img, it, t, f, mouths=None):
        d = ImageDraw.Draw(img)
        cols = [rgb(c) for c in it.get("colors", ["#c0262d", "#2f6db3", "#1f1f1f"])]
        (ax, ay), (bx, by) = it.get("source", [430, 510]), it.get("target", [850, 510])
        n, every = int(it.get("n", 10)), nframes(it.get("every", 0.5), self.fps)
        fl = f - nframes(it.get("at", 0), self.fps)
        moves = int(it.get("moves", n - 1))
        moved = min(max(fl, 0) // every, moves)

        def chip(x, y, c):
            d.ellipse((x - 46, y - 14, x + 46, y + 14), fill=c, outline=(23, 18, 13), width=3)
            d.ellipse((x - 30, y - 9, x + 30, y + 9), outline=(240, 240, 240), width=2)
        for i in range(n - moved):
            chip(ax, ay - i * 12, cols[i % len(cols)])
        for i in range(moved):
            chip(bx, by - i * 12, cols[(i + 1) % len(cols)])
        if 0 <= fl < every * moves and fl % every < every // 2:
            u = (fl % every) / (every // 2)
            chip(ax + (bx - ax) * u, ay - 130 - 60 * math.sin(math.pi * u), cols[moved % len(cols)])

    def clip_item(self, img, it, t, f=None, mouths=None):
        if t >= it.get("at", 0):
            self.clip(img, it, t)

    def clip(self, img, it, t):
        fps_c = float(it.get("fps", self.fps))
        k = int((t - it.get("at", 0)) * fps_c + 1e-6)
        sc = float(it.get("scale", 1.0))
        frames = self.A.clip(it["frames"], (W, H) if it.get("fit") else None, None, float(it.get("from", 0)))
        if k >= len(frames):
            if not it.get("hold_last"):
                return
            k = len(frames) - 1
        fr = frames[k]
        if sc != 1.0:
            fr = fr.resize((int(fr.width * sc), int(fr.height * sc)), Image.LANCZOS)
        a = item_alpha(it, t)
        if a < 1:
            fr = fr.copy()
            fr.putalpha(fr.getchannel("A").point(lambda v: int(v * a)))
        img.alpha_composite(fr, (int(it.get("x", 0)), int(it.get("y", 0))))

    def desk(self, img, it, t=None, f=None, mouths=None):
        d = ImageDraw.Draw(img)
        if it.get("box"):
            d.rectangle(tuple(it["box"]), fill=rgb(it.get("color"), INK))
            return
        y = it.get("y", 548)
        d.rectangle((0, y + 12, W, H), fill=rgb(it.get("color"), (138, 90, 60)), outline=INK, width=5)
        d.rectangle((0, y, W, y + 18), fill=(176, 122, 82), outline=INK, width=4)
        if it.get("keyboard", [240, 520]):
            kx, ky = it.get("keyboard", [240, 520])
            d.rectangle((kx, ky + 8, kx + 280, ky + 32), fill=(58, 63, 74), outline=INK, width=3)

    def spot(self, img, it, t=None, f=None, mouths=None):
        if "_img" not in it:
            sp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            x, a, b = it.get("x", 640), it.get("top", 80), it.get("bottom", 260)
            ImageDraw.Draw(sp).polygon([(x - a, 0), (x + a, 0), (x + b, H), (x - b, H)],
                                       fill=(255, 241, 201, int(it.get("alpha", 40))))
            it["_img"] = sp.filter(ImageFilter.GaussianBlur(20))
        img.alpha_composite(it["_img"])

    def zzz(self, img, it, t, f=None, mouths=None):
        d = ImageDraw.Draw(img)
        for k in range(3):
            p = ((t - it.get("at", 0)) * self.fps / 14 + k / 3) % 1
            d.text((it.get("x", 420) + 70 * p, it.get("y", 420) - 160 * p), "z", font=font("impact", 30 + 24 * p),
                   fill=(232, 251, 255))

    # ---- the frame: items, front layers, captions, zoom, lights out, fades
    def draw_items(self, img, t, f, mouths):
        for it in self.s.get("items", []):
            kind = it.get("type", "figure")
            if kind not in ("figure", "clip") and item_alpha(it, t) <= 0:
                continue
            if kind in self.draw:
                self.draw[kind](img, it, t, f, mouths)

    def zoom(self, img, t):
        z = self.s.get("zoom")
        if not (z and t >= z["at"]):
            return img
        zz = 1 + (float(z.get("to", 2.0)) - 1) * ease(clamp((t - z["at"]) / float(z.get("dur", 0.8))))
        cx, cy = z.get("center", [W / 2, H / 2])
        big = img.resize((int(W * zz), int(H * zz)), Image.BICUBIC)
        x0 = int(min(max(cx * zz - W / 2, 0), big.width - W))
        y0 = int(min(max(cy * zz - H / 2, 0), big.height - H))
        return big.crop((x0, y0, x0 + W, y0 + H))

    def lights_out(self, img, t, f, mouths):
        lo = self.s.get("lights_out")
        if not (lo and t >= lo["at"]):
            return img
        img = Image.blend(img, Image.new("RGBA", (W, H), (0, 0, 0, 255)), clamp((t - lo["at"]) / lo.get("fade", 0.125)))
        if lo.get("keep_mouths", True) and f < self.n - 8:
            for m in mouths:
                m(img)
        return img

    def fade(self, img, f):
        black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        if self.s.get("fade", True):
            if f < 8:
                img = Image.blend(black, img, f / 8)
            if self.kind == "gag" and f >= self.n - 8:
                img = Image.blend(black, img, (self.n - f) / 8)
        return img

    def render(self, f):
        t = f / self.fps
        img = self.back.copy()
        mouths = []
        self.draw_items(img, t, f, mouths)
        for fr in self.front:
            img.alpha_composite(fr)
        for it in self.s.get("items", []):
            if it.get("type") == "caption" and item_alpha(it, t) > 0:
                self.caption(img, it, t)
        img = self.zoom(img, t)
        img = self.lights_out(img, t, f, mouths)
        return self.fade(img, f).convert("RGB")


# ============================================================ text roll + scene windows
STYLE = {"head": ("impact", 64, GOLD, 90), "head2": ("script_b", 30, GOLD, 64), "sub": ("script", 26, CREAM, 44),
         "role": ("script", 24, GREY, 32), "name": ("script_b", 30, CREAM, 48), "gap": ("script", 26, CREAM, 40)}
LAYOUTS = {   # text column centre, window size, window boxes (alternating), tilt sign
    "text_left": {"cx": 410, "win": (440, 248), "boxes": [(790, 220)]},
    "text_right": {"cx": 870, "win": (440, 248), "boxes": [(40, 220)]},
    "text_center": {"cx": 640, "win": (330, 186), "boxes": [(870, 160), (20, 330)]},
}


def roll_lines(text):
    lines, y = [], 0
    for e in text:
        e = [e] if isinstance(e, str) else list(e)
        kind = e[0]
        if kind == "role" and len(e) > 2:                       # ["role", "Tim", "the user"] = role + name
            seq = [("role", e[1]), ("name", e[2])]
        else:
            seq = [(kind, e[1] if len(e) > 1 else "")]
        for k, txt in seq:
            fk, size, col, dy = STYLE.get(k, STYLE["sub"])
            lines.append((y, txt, font(fk, size), col))
            y += dy
    return lines, y


class Roll:
    def __init__(self, P, C, A, n_parts, layout, rng):
        self.P, self.C, self.A, self.fps = P, C, A, P.fps
        self.lines, h = roll_lines(C.get("text", []))
        self.speed = float(C.get("speed", 57.6)) / self.fps
        total = h + H * float(C.get("end_at", 0.55))
        self.part_n = int(total / self.speed / n_parts)
        self.L = LAYOUTS[layout]
        # the seeded draws in this order (the default argument is drawn even when "tilt" is given)
        self.tilt = float(C.get("windows", {}).get("tilt", rng.choice([2.5, 3, 3.5])))
        self.tilt_sign = 1 if "tilt" in C.get("windows", {}) else rng.choice([1, -1])
        self.dy = int(C.get("windows", {}).get("dy", 0 if C.get("layout") else rng.choice([-30, 0, 0, 30])))
        self.bg = Image.new("RGB", (W, H), rgb(C.get("background"), BG_COL))
        self.roll_f = 0
        self.win_k = 0

    def window_card(self, fr, k, label=None):
        cw, ch = self.L["win"]
        card = Image.new("RGB", (cw + 16, ch + 16), CREAM)
        if fr.mode == "RGBA":                     # transparent frames (e.g. a 3D figure render) on a dark backdrop
            fr = Image.alpha_composite(Image.new("RGBA", fr.size, (44, 38, 58, 255)), fr)
        card.paste(fr.convert("RGB"), (8, 8))
        if label:
            d = ImageDraw.Draw(card)
            f_ = font("script_b", 18)
            tw = d.textlength(label, font=f_) + 20
            d.rounded_rectangle((14, 12, 14 + tw, 40), 8, fill=(224, 71, 63))
            d.text((24, 13), label, font=f_, fill="white")
        ang = self.tilt * self.tilt_sign * (-1 if k % 2 else 1)
        return card.rotate(ang, expand=True, resample=Image.BICUBIC, fillcolor=self.bg.getpixel((0, 0)))

    def draw_text(self, img):
        """The rolling text at the current roll position (lines fade in at the bottom and out at the top)."""
        d = ImageDraw.Draw(img)
        off = H - self.roll_f * self.speed
        cx = self.L["cx"]
        for yy, txt, f_, col in self.lines:
            yp = off + yy
            if -80 < yp < H + 20 and txt:
                a = clamp(min(yp / 90, (H - yp) / 90))
                d.text((cx - d.textlength(txt, font=f_) / 2, yp), txt, font=f_,
                       fill=tuple(int(v * a + self.bg.getpixel((0, 0))[j] * (1 - a)) for j, v in enumerate(col)))

    def draw_window(self, img, frames, il, ln, label):
        """Frame il of a window shown ln frames long, blended in / out over 12 frames."""
        fr = frames[il % len(frames)]
        card = self.window_card(fr, self.win_k - 1, label)
        ca = clamp(min(il / 12, (ln - il) / 12))
        boxes = self.L["boxes"]
        bx, by = boxes[(self.win_k - 1) % len(boxes)]
        box = (bx, by + self.dy, bx + card.width, by + self.dy + card.height)
        img.paste(Image.blend(img.crop(box), card, ca), box[:2])

    def frames(self, part, wins, fade_in=True, fade_out=True):
        """Yield the frames of one text part; wins = [(loader -> window frames, label), ...] shown one after another."""
        n = self.part_n
        wins = wins or []
        slot = n / max(1, len(wins))
        cur, frames = -1, None
        for i in range(n):
            img = self.bg.copy()
            self.draw_text(img)
            if wins:
                j = min(int(i / slot), len(wins) - 1)
                if j != cur:
                    cur, frames = j, wins[j][0]()
                    self.win_k += 1
                if frames:
                    il, ln = i - int(round(j * slot)), int(round((j + 1) * slot)) - int(round(j * slot))
                    self.draw_window(img, frames, il, ln, wins[j][1])
            if fade_in and i < 12:
                img = Image.blend(Image.new("RGB", (W, H)), img, i / 12)
            if fade_out and i >= n - 10:
                img = Image.blend(Image.new("RGB", (W, H)), img, (n - i) / 10)
            self.roll_f += 1
            yield img


def push_in(base, cw, ch, n):
    """A still as n frames of a slow push-in (8 %)."""
    out = []
    for i in range(n):
        z = 1 + 0.08 * i / max(1, n - 1)
        big = base.resize((int(cw * z), int(ch * z)), Image.BICUBIC)
        x0, y0 = (big.width - cw) // 2, (big.height - ch) // 2
        out.append(big.crop((x0, y0, x0 + cw, y0 + ch)))
    return out


def window_loader(spec, film, A, size, n):
    """-> a function that loads the n frames of one scene window: a film excerpt ({"film": s}) or an outtake
    ({"outtake": {"path", "from"}}; a still gets a push-in). Loaded only when the window comes up."""
    cw, ch = size
    if "film" in spec:
        return lambda: [f.convert("RGB") for f in video_frames(film, spec["film"], n, (cw, ch))]
    o = spec["outtake"]

    def load():
        fr = A.clip(o["path"], (cw, ch), n, float(o.get("from", 0)))
        return fr if len(fr) != 1 else push_in(fr[0], cw, ch, n)
    return load
