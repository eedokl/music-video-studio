"""Typography shots drawn in code (never by a model - models garble letters): technique "typo", or a "typo" entry on
any shot to draw over its material. Clay #D97757 and off-white, Bahnschrift Bold (Arial Bold elsewhere).

project.json shot:
  "typo": {"kind": "newsflash", "text": "NEWSFLASH", "label": "BREAKING", "ticker": "+++ EUROPE 2031 +++ ..."}
  "typo": {"kind": "stamps", "words": ["REGULIEREN", "ANALYSIEREN"], "ground": "paper|screen|material"}
          each stamp slams down on its SUNG word (song sheet word times; evenly spread if not found);
          ground "screen" = dark stage screen (live version), "material" = over the shot's clip/still
  "typo": {"kind": "departures", "title": "ABFLUG  DEPARTURES", "rows": [["09:40", "SAN FRANCISCO", "BOARDING"], ...]}
          split-flap board over the material, the rows settle one after another
  "typo": {"kind": "title", "text": "EUROPE 2031", "accent": "2031", "note": "Images and video AI-generated ..."}
Shots that show the sung words themselves should set "lyrics": false (no lyrics box on top).
Ported from the Europe 2031 cut (claudia-video-trial schnitt.py shots 33/36/37/39/62; live: stamps on the screen).
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
CLAY = (217, 119, 87)
OFFWHITE = (245, 240, 232)
_F = {}


def F(size, bold=True):
    key = (size, bold)
    if key not in _F:
        f = None
        for name in ("bahnschrift.ttf", "arialbd.ttf" if bold else "arial.ttf", "DejaVuSans-Bold.ttf"):
            try:
                f = ImageFont.truetype(name, size)
                if name == "bahnschrift.ttf":
                    try:
                        f.set_variation_by_name("Bold" if bold else "SemiLight")
                    except Exception:
                        pass
                break
            except OSError:
                continue
        _F[key] = f or ImageFont.load_default()
    return _F[key]


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def ground(kind):
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    if kind == "paper":
        g = np.ones((H, W, 3), np.float32) * np.array([222, 215, 200], np.float32)
        return g + np.random.default_rng(3).normal(0, 6, (H, W, 1)).astype(np.float32)
    if kind == "dawn":
        return (np.array([40, 60, 90], np.float32) * (1 - yy) + np.array([230, 160, 90], np.float32) * yy) * \
            np.ones((H, W, 3), np.float32)
    return np.array([20, 28, 38], np.float32) * (1 - yy * 0.5) * np.ones((H, W, 3), np.float32)   # dark screen


def _np(img):
    return np.asarray(img.convert("RGB"), dtype=np.float32)


def newsflash(T, u, t):
    img = Image.new("RGB", (W, H), (8, 10, 14))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 4):
        d.line([(0, y), (W, y)], fill=(12, 15, 20))
    k = ease(u / 0.18)
    f = F(int(150 + 40 * (1 - k)))
    txt = T.get("text", "NEWSFLASH")
    x = (W - d.textlength(txt, font=f)) / 2 + (1 - k) * 120
    d.text((x + 5, 260), txt, font=f, fill=(0, 0, 0))
    d.text((x, 255), txt, font=f, fill=CLAY)
    ticker = (T.get("ticker") or "+++ " + txt + " +++") + "     "
    d.rectangle([(0, H - 128), (W, H - 78)], fill=OFFWHITE)
    off = 240 - (t * 260) % max(400, d.textlength(ticker, font=F(32, False)))
    d.text((off + 230, H - 121), ticker * 4, font=F(32, False), fill=(20, 20, 24))
    d.rectangle([(0, H - 128), (230, H - 78)], fill=CLAY)
    d.text((22, H - 122), T.get("label", "BREAKING"), font=F(34), fill=OFFWHITE)
    return _np(img)


def _stamp(word, alpha):
    f = F(84)
    tw = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(word, font=f))
    st = Image.new("RGBA", (tw + 80, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    col = (*CLAY, int(235 * alpha))
    d.rectangle([(6, 6), (tw + 73, 143)], outline=col, width=9)
    d.text((40, 22), word, font=f, fill=col)
    holes = (np.random.default_rng(len(word)).random((150, tw + 80)) > 0.12)        # rubber-stamp texture
    arr = np.asarray(st).copy()
    arr[..., 3] = (arr[..., 3] * holes).astype(np.uint8)
    return Image.fromarray(arr)


def stamps(T, base, u, t, times):
    img = Image.fromarray(np.clip(base * 0.82, 0, 255).astype(np.uint8)).convert("RGBA")
    for i, (w, tz) in enumerate(zip(T["words"], times)):
        if t < tz:
            continue
        k = ease((t - tz) / 0.09)
        sc = 1.5 - 0.5 * k
        st = _stamp(w, min(1.0, 0.3 + k))
        st = st.resize((int(st.width * sc), int(st.height * sc)), Image.LANCZOS).rotate([-7, 5][i % 2], expand=True,
                                                                                         resample=Image.BICUBIC)
        cx, cy = W // 2 + [-60, 70][i % 2], [250, 450][i % 2]
        wobble = 6 * (1 - k) * math.sin((t - tz) * 90)
        img.alpha_composite(st, (int(cx - st.width / 2 + wobble), int(cy - st.height / 2)))
    return _np(img)


def departures(T, base, u, t):
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rows = T.get("rows") or [["09:40", "SAN FRANCISCO", "BOARDING"]]
    x0, y0, bw = 620, 60, 600
    d.rectangle([(x0, y0), (x0 + bw, y0 + 84 + 54 * len(rows))], fill=(10, 12, 16, 235))
    d.text((x0 + 24, y0 + 14), T.get("title", "DEPARTURES"), font=F(30), fill=OFFWHITE)
    d.line([(x0 + 20, y0 + 58), (x0 + bw - 20, y0 + 58)], fill=(60, 64, 70), width=2)
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    rng = np.random.default_rng(int(t * 24))

    def flap(s, ok):
        return s if ok else "".join(c if c == " " else chars[rng.integers(len(chars))] for c in s)
    for r, (tm, dest, status) in enumerate(rows):
        done = u > 0.12 + r * 0.1
        y = y0 + 76 + r * 54
        d.text((x0 + 24, y), flap(tm, done), font=F(30), fill=(235, 200, 120, 255))
        d.text((x0 + 130, y), flap(dest, done), font=F(30), fill=OFFWHITE)
        d.text((x0 + 420, y), flap(status, done), font=F(26), fill=(*CLAY, 255))
    img.alpha_composite(ov)
    return _np(img)


def title(T, base, u, t):
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    a = ease((t - 0.6) / 1.2) if t > 0.6 else 0
    spacing = 30 * (1 - ease(t / 3.0))
    f = F(118)
    text, acc = T.get("text", ""), T.get("accent", "")
    parts = [(text[:len(text) - len(acc)], OFFWHITE), (acc, CLAY)] if acc and text.endswith(acc) else [(text, OFFWHITE)]
    width = sum(d.textlength(s, font=f) + spacing * len(s) for s, _ in parts)
    x = (W - width) / 2
    for s, col in parts:
        for ch in s:
            d.text((x + 3, 284), ch, font=f, fill=(0, 0, 0, int(140 * a)))
            d.text((x, 280), ch, font=f, fill=(*col, int(255 * a)))
            x += d.textlength(ch, font=f) + spacing
    if T.get("note"):
        b = ease((t - 3.5) / 1.5) if t > 3.5 else 0
        fw = d.textlength(T["note"], font=F(20, False))
        d.rectangle([((W - fw) / 2 - 14, H - 78), ((W + fw) / 2 + 14, H - 40)], fill=(8, 10, 14, int(160 * b)))
        d.text(((W - fw) / 2, H - 70), T["note"], font=F(20, False), fill=(*OFFWHITE, int(220 * b)))
    img.alpha_composite(ov)
    return _np(img)


def word_times(T, s, sheet_words):
    """Sung times of the stamp words inside the shot (matching by word start), else evenly spread."""
    t0, t1 = s["from"], s["to"]
    n = len(T.get("words", []))
    out = []
    for i, w in enumerate(T.get("words", [])):
        key = w.lower().strip(".,!?\"'")[:6]
        hit = [x["t"] for x in sheet_words if t0 - 0.2 <= x["t"] < t1 and x["word"].lower().strip(".,!?\"'„“").startswith(key)]
        out.append(hit[0] if hit else t0 + (i + 0.3) * (t1 - t0) / max(n, 1))
    return out


def draw(s, base, u, t, sheet_words=()):
    """Frame of a typo shot. base = the shot's material frame (float RGB) or None. t = song time."""
    T = s["typo"]
    k = T.get("kind")
    tl = t - s["from"]
    if k == "newsflash":
        return newsflash(T, u, tl)
    if k == "stamps":
        g = T.get("ground", "material" if base is not None else "paper")
        b = base if (g == "material" and base is not None) else ground("screen" if g == "screen" else "paper")
        return stamps(T, b, u, t, word_times(T, s, sheet_words))
    b = base if base is not None else ground("dawn" if k == "title" else "screen")
    if k == "departures":
        return departures(T, b, u, tl)
    if k == "title":
        return title(T, b, u, tl)
    raise ValueError(f"unknown typo kind {k}")
