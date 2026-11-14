"""Drawn props and comic elements in the ink style of the slides, for scene.py sprites (Pillow, no AI).

Every function saves an RGBA PNG and returns its aspect ratio (width / height) - pass that to Scene.sprite(aspect=..).
Colours: INK (line), PAPER (fill) and an accent (default the green of the reference deck - pass the deck's accent,
e.g. clip.accent_color(geometry) or a colour picked from the slide). Lettering: comic for speech/thought, sans for signs.

  comic bubbles   cloud(text, path, kind="thought"|"dream"|"speech")   star_eye(path)   question_mark(path)
  signs, cards    sign(text, path)   project_card(title, line, path)   info_card(title, [(number, text)], path)
                  check_sign(text, path)   neon(text, path)   calendar_sheet(path)   book(title, path)
  chat / tech     chat_bubble(path)   mini_bot(path)   key_flash(path)   document(text, path, check|cross)
                  holo(kind, path, title)  kind: bars | line | surface | wafer | app | code | rocket | check | prompt
  things          coin(path)   scale_parts(base, beam, pan_left, pan_right, labels)   confetti_piece(path, colour)
                  progress_frame(path, label)   progress_fill(path)
  light           soft_light(path) (door gap)   warm_light(path) (radial)   light_cone(path) (spotlight)
  sets            island_floor(path, tone) (round floor plate seen from above)
"""
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

INK = (22, 22, 24, 255)
GREEN = (0x44, 0x6F, 0x5C, 255)
PAPER = (250, 249, 244, 255)
_FONTS = {"comic": ["comicbd.ttf", "DejaVuSans-Bold.ttf"], "bold": ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
          "regular": ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]}
_DIRS = [Path(os.environ.get("WINDIR", "")) / "Fonts", Path("/usr/share/fonts/truetype/dejavu"),
         Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental")]


def font(kind, size):
    for d in _DIRS:
        for n in _FONTS[kind]:
            if (d / n).exists():
                return ImageFont.truetype(str(d / n), int(size))
    return ImageFont.load_default()


def rgba(c):
    return tuple(c) + (255,) if len(c) == 3 else tuple(c)


def _save(im, path):
    im.save(path)
    return im.size[0] / im.size[1]


# ------------------------------------------------------------------ comic elements
def _cloud_mask(W, H, rng, puffs=14):
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    rmax = min(W, H) * 0.18
    cx, cy, rx, ry = W / 2, H / 2, W / 2 - rmax - 12, H / 2 - rmax - 12
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    for i in range(puffs):
        a = 2 * math.pi * i / puffs + rng.uniform(-0.1, 0.1)
        r = min(W, H) * rng.uniform(0.13, 0.18)
        px, py = cx + rx * math.cos(a), cy + ry * math.sin(a)
        d.ellipse((px - r, py - r, px + r, py + r), fill=255)
    return m


def cloud(text, path, kind="thought", colour=INK, size=None, seed=1, accent=GREEN):
    """Thought cloud (bubbles to the lower left), dream cloud (bubbles to the right, accent sparkles) or speech bubble
    (rounded, tail down). Text in upper case comic lettering, \\n for lines."""
    import numpy as np
    rng = np.random.default_rng(seed)
    lines = text.upper().split("\n")
    fs = size or 120
    f = font("comic", fs)
    tw = max(f.getlength(ln) for ln in lines)
    th = fs * 1.15 * len(lines)
    W, H = int(tw * 1.55 + 120), int(th * 1.9 + 220)
    W = max(W, int(H * 1.5))
    pad = 140 if kind != "speech" else 60
    if kind == "speech":
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).rounded_rectangle((20, 20, W - 20, H - 20), radius=int(H * 0.35), fill=255)
    else:
        m = _cloud_mask(W, H, rng)
    full = Image.new("L", (W, H + pad), 0)
    full.paste(m, (0, 0))
    d = ImageDraw.Draw(full)
    if kind == "thought":
        for (fx, fy, r) in ((0.30, 1.02, 34), (0.22, 1.10, 22), (0.16, 1.16, 13)):
            d.ellipse((W * fx - r, H * fy - r, W * fx + r, H * fy + r), fill=255)
    elif kind == "speech":
        d.polygon([(W * 0.30, H - 40), (W * 0.42, H - 40), (W * 0.24, H + pad - 10)], fill=255)
    elif kind == "dream":
        for (fx, fy, r) in ((0.62, 1.02, 30), (0.70, 1.10, 19), (0.76, 1.16, 11)):
            d.ellipse((W * fx - r, H * fy - r, W * fx + r, H * fy + r), fill=255)
    a = np.asarray(full).astype(np.float32) / 255
    inner = np.asarray(full.filter(ImageFilter.MinFilter(19))).astype(np.float32) / 255
    px = np.zeros((H + pad, W, 4), np.float32)
    px[..., :3] = np.array(INK[:3]) / 255
    px[..., 3] = a
    px[inner > 0.5, :3] = 1.0                                   # white inside, ~9 px ink rim
    out = Image.fromarray((px * 255).astype(np.uint8), "RGBA").filter(ImageFilter.SMOOTH)
    dd = ImageDraw.Draw(out)
    y = H / 2 - th / 2 + fs * 0.1
    for ln in lines:
        dd.text((W / 2, y + fs * 0.55), ln, font=f, fill=rgba(colour), anchor="mm")
        y += fs * 1.15
    if kind == "dream":
        for (fx, fy) in ((0.12, 0.25), (0.88, 0.22), (0.9, 0.75)):
            x0, y0 = W * fx, H * fy
            for ang in (0, 60, 120):
                dx, dy = 26 * math.cos(math.radians(ang)), 26 * math.sin(math.radians(ang))
                dd.line([(x0 - dx, y0 - dy), (x0 + dx, y0 + dy)], fill=rgba(accent), width=8)
    return _save(out, path)


def star_eye(path, s=200):
    """White disc (covers the pupil) with a black star and a highlight - hang two on a figure's eyes."""
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((s * 0.06, s * 0.06, s * 0.94, s * 0.94), fill=(255, 255, 255, 255))
    pts = []
    for i in range(10):
        r = s * (0.44 if i % 2 == 0 else 0.19)
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((s / 2 + r * math.cos(a), s / 2 + r * math.sin(a)))
    d.polygon(pts, fill=INK)
    d.ellipse((s * 0.40, s * 0.30, s * 0.50, s * 0.40), fill=(255, 255, 255, 255))
    return _save(im, path)


def question_mark(path, s=300, colour=INK):
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((s / 2, s / 2), "?", font=font("comic", s * 0.9), fill=rgba(colour), anchor="mm",
                            stroke_width=10, stroke_fill=PAPER)
    return _save(im, path)


# ------------------------------------------------------------------ signs and cards
def sign(text, path, accent=GREEN, height=260):
    """Wall sign: paper board with ink rim, inner accent rim, text in the accent colour."""
    f = font("bold", height * 0.55)
    w = int(f.getlength(text) + height * 0.9)
    im = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 6, w - 6, height - 6), radius=height // 6, fill=PAPER, outline=INK, width=10)
    d.rounded_rectangle((26, 26, w - 26, height - 26), radius=height // 9, outline=rgba(accent), width=5)
    d.text((w / 2, height / 2 + 4), text, font=f, fill=rgba(accent), anchor="mm")
    return _save(im, path)


def project_card(title, line, path, W=900, H=560, accent=GREEN):
    """Index card: title in the accent colour, a short description (wrapped), ink rim, slight shadow."""
    im = Image.new("RGBA", (W + 24, H + 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((18, 22, W + 18, H + 22), radius=34, fill=(0, 0, 0, 60))
    d.rounded_rectangle((4, 4, W, H), radius=34, fill=PAPER, outline=INK, width=10)
    d.rectangle((30, 30, W - 26, 52), fill=rgba(accent))
    ft = font("bold", 92)
    while ft.getlength(title) > W - 90 and ft.size > 50:
        ft = font("bold", ft.size - 4)
    d.text((W / 2, 150), title, font=ft, fill=rgba(accent), anchor="mm")
    fu = font("regular", 58)
    lines, cur = [], ""
    for w in line.split():
        t = (cur + " " + w).strip()
        if fu.getlength(t) > W - 120:
            lines.append(cur)
            cur = w
        else:
            cur = t
    lines.append(cur)
    y = 270
    for ln in lines[:4]:
        d.text((W / 2, y), ln, font=fu, fill=(40, 40, 44, 255), anchor="mm")
        y += 72
    return _save(im, path)


def info_card(title, rows, path, W=1500, H=900, accent=GREEN):
    """Big card with key figures: rows = [(number, "text\\nline 2"), ...] side by side."""
    im = Image.new("RGBA", (W + 30, H + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((22, 28, W + 22, H + 28), radius=50, fill=(0, 0, 0, 70))
    d.rounded_rectangle((4, 4, W, H), radius=50, fill=PAPER, outline=INK, width=12)
    d.rounded_rectangle((4, 4, W, 190), radius=50, fill=rgba(accent), outline=INK, width=12)
    d.rectangle((16, 120, W - 8, 190), fill=rgba(accent))
    d.line([(4, 190), (W, 190)], fill=INK, width=12)
    d.text((W / 2, 100), title, font=font("bold", 120), fill=PAPER, anchor="mm")
    fz, ft = font("bold", 150), font("regular", 66)
    for i, (num, text) in enumerate(rows):
        cx = W * (i + 0.5) / len(rows)
        d.text((cx, 420), num, font=fz, fill=rgba(accent), anchor="mm")
        yy = 580
        for part in text.split("\n"):
            d.text((cx, yy), part, font=ft, fill=(40, 40, 44, 255), anchor="mm")
            yy += 80
    return _save(im, path)


def check_sign(text, path, W=1400, H=520, accent=GREEN):
    """Pill with a big check mark + text (e.g. BUILD\\nSUCCESSFUL)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 8, W - 8, H - 8), radius=H // 2 - 8, fill=PAPER, outline=INK, width=14)
    r = H * 0.36
    cx, cy = H * 0.52, H / 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba(accent), outline=INK, width=10)
    d.line([(cx - r * 0.5, cy), (cx - r * 0.12, cy + r * 0.4), (cx + r * 0.55, cy - r * 0.42)], fill=PAPER,
           width=int(r * 0.24), joint="curve")
    f = font("comic", H * 0.26)
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        d.text((H * 0.95 + (W - H * 0.95) / 2, H / 2 + (i - (len(lines) - 1) / 2) * H * 0.3), ln, font=f,
               fill=rgba(accent), anchor="mm")
    return _save(im, path)


def neon(text, path, colour=(255, 80, 210), height=300):
    """Neon lettering: bright core + soft glow (use with add=True on a dark wall)."""
    import numpy as np
    f = font("comic", height * 0.55)
    w = int(f.getlength(text) + height)
    base = Image.new("L", (w, height), 0)
    ImageDraw.Draw(base).text((w / 2, height / 2), text, font=f, fill=255, anchor="mm")
    g1 = np.asarray(base.filter(ImageFilter.GaussianBlur(height * 0.09)), np.float32)
    g2 = np.asarray(base.filter(ImageFilter.GaussianBlur(height * 0.03)), np.float32)
    b = np.asarray(base, np.float32)
    a = np.minimum(255, (g1 * 1.6 + g2 * 0.8).astype(int))
    core = b / 255
    rgb = [(colour[k] * (1 - core) + 255 * core).astype(int) for k in range(3)]
    out = np.dstack(rgb + [np.maximum(a, b.astype(int))]).astype(np.uint8)
    return _save(Image.fromarray(out, "RGBA"), path)


def calendar_sheet(path, text="DAY", W=260, H=300, accent=GREEN):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 6, W - 6, H - 6), radius=18, fill=PAPER, outline=INK, width=8)
    d.rectangle((14, 14, W - 14, 80), fill=rgba(accent))
    for x in (60, W - 60):
        d.ellipse((x - 12, 0, x + 12, 24), fill=INK)
    d.text((W / 2, 180), text, font=font("bold", 70), fill=INK, anchor="mm")
    return _save(im, path)


def book(title, path, W=700, H=420, accent=GREEN):
    """Open book seen from above: accent cover, title on the left page, lines on the right."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 30, W - 10, H - 10), radius=20, fill=rgba(accent), outline=INK, width=10)
    d.rectangle((W / 2 - 8, 30, W / 2 + 8, H - 10), fill=INK)
    page = [(30, 20), (W / 2, 50), (W - 30, 20), (W - 30, H - 40), (W / 2, H - 20), (30, H - 40)]
    d.polygon(page, fill=PAPER)
    d.line(page + [page[0]], fill=INK, width=8)
    d.line([(W / 2, 50), (W / 2, H - 20)], fill=INK, width=6)
    f = font("bold", 40)
    for i, ln in enumerate(title.split("\n")):
        d.text((W * 0.27, 120 + i * 52), ln, font=f, fill=rgba(accent), anchor="mm")
    for i in range(6):
        d.line([(W / 2 + 40, 110 + i * 40), (W - 70, 110 + i * 40)], fill=(120, 120, 126, 255), width=7)
    return _save(im, path)


# ------------------------------------------------------------------ chat and tech
def chat_bubble(path, dots=3, left=True, tinted=False, accent=GREEN):
    W, H = 360, 260
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = (232, 240, 236, 255) if tinted else PAPER
    d.rounded_rectangle((10, 10, W - 10, H - 70), radius=60, fill=fill, outline=INK, width=10)
    tx = 70 if left else W - 70
    tip = tx - 40 if left else tx + 40
    d.polygon([(tx - 30, H - 78), (tx + 30, H - 78), (tip, H - 12)], fill=fill)
    d.line([(tx - 30, H - 74), (tip, H - 12), (tx + 30, H - 74)], fill=INK, width=10, joint="curve")
    for i in range(dots):
        cx = W / 2 + (i - (dots - 1) / 2) * 70
        d.ellipse((cx - 18, (H - 70) / 2 - 8, cx + 18, (H - 70) / 2 + 28), fill=rgba(accent) if tinted else INK)
    return _save(im, path)


def mini_bot(path, s=300, accent=GREEN):
    """Small friendly bot: speech-bubble head, antenna, two eyes, smile, accent belly."""
    im = Image.new("RGBA", (s, int(s * 1.25)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([(s / 2, 40), (s / 2, 80)], fill=INK, width=9)
    d.ellipse((s / 2 - 20, 14, s / 2 + 20, 54), fill=rgba(accent), outline=INK, width=7)
    d.rounded_rectangle((30, 76, s - 30, 76 + s * 0.52), radius=46, fill=PAPER, outline=INK, width=10)
    ey = 76 + s * 0.22
    for ex in (s * 0.36, s * 0.64):
        d.ellipse((ex - 17, ey - 20, ex + 17, ey + 20), fill=INK)
        d.ellipse((ex - 6, ey - 13, ex + 3, ey - 4), fill=(255, 255, 255, 255))
    d.arc((s * 0.36, ey + 6, s * 0.64, ey + 46), 20, 160, fill=INK, width=8)
    by = 76 + s * 0.52 + 8
    d.rounded_rectangle((s * 0.24, by, s * 0.76, by + s * 0.42), radius=30, fill=rgba(accent), outline=INK, width=10)
    d.ellipse((s * 0.44, by + s * 0.13, s * 0.56, by + s * 0.25), fill=PAPER)
    return _save(im, path)


def key_flash(path, s=120, accent=GREEN):
    """Three short strokes above a keyboard - flash it on every key stroke."""
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for a in (-35, 0, 35):
        r = math.radians(a - 90)
        d.line([(s / 2 + 22 * math.cos(r), s * 0.8 + 22 * math.sin(r)),
                (s / 2 + 52 * math.cos(r), s * 0.8 + 52 * math.sin(r))], fill=rgba(accent), width=9)
    return _save(im, path)


def document(text, path, W=300, H=380, check=False, cross=False, accent=GREEN):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    outline = [(8, 8), (W - 80, 8), (W - 8, 80), (W - 8, H - 8), (8, H - 8)]
    d.polygon(outline, fill=PAPER, outline=INK)
    d.line(outline + [outline[0]], fill=INK, width=10)
    d.line([(W - 80, 8), (W - 80, 80), (W - 8, 80)], fill=INK, width=8)
    for i in range(4):
        d.line([(40, 150 + i * 50), (W - 50 - (i % 2) * 50, 150 + i * 50)], fill=(90, 90, 96, 255), width=10)
    if text:
        d.text((W / 2 - 20, 85), text, font=font("bold", 80), fill=rgba(accent), anchor="mm")
    if check:
        d.ellipse((W - 130, H - 130, W - 20, H - 20), fill=rgba(accent), outline=INK, width=7)
        d.line([(W - 108, H - 76), (W - 84, H - 50), (W - 44, H - 100)], fill=PAPER, width=14)
    if cross:
        d.line([(W - 120, H - 120), (W - 30, H - 30)], fill=(190, 40, 40, 255), width=16)
        d.line([(W - 30, H - 120), (W - 120, H - 30)], fill=(190, 40, 40, 255), width=16)
    return _save(im, path)


def holo(kind, path, title="", W=640, H=420, colour=(60, 230, 230), second=(255, 90, 210), prompt="> build me a dashboard", seed=0):
    """Glowing hologram panel (dark see-through, glowing rim); kind: bars | line | surface | wafer | app | code |
    rocket | check | prompt (a typed prompt line)."""
    import random
    import zlib
    rng = random.Random(zlib.crc32((kind + title).encode()) + seed)
    pad = 40
    im = Image.new("RGBA", (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((pad, pad, W + pad, H + pad), radius=28, outline=tuple(colour) + (255,),
                                           width=16)
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(im)
    c, m = tuple(colour) + (255,), tuple(second) + (255,)
    d.rounded_rectangle((pad, pad, W + pad, H + pad), radius=28, fill=(10, 30, 60, 170), outline=c, width=6)
    x0, y0, x1, y1 = pad + 40, pad + 90, W + pad - 40, H + pad - 40
    if title:
        d.text(((x0 + x1) / 2, pad + 48), title, font=font("bold", 52), fill=c, anchor="mm")
    if kind == "bars":
        n = 7
        for i in range(n):
            h = rng.uniform(0.25, 1.0) * (y1 - y0)
            bx = x0 + i * (x1 - x0) / n
            d.rectangle((bx + 8, y1 - h, bx + (x1 - x0) / n - 8, y1), fill=c if i % 3 else m)
    elif kind == "line":
        pts = [(x0 + i * (x1 - x0) / 12, y1 - (0.2 + 0.6 * (i / 12) + rng.uniform(-0.12, 0.12)) * (y1 - y0))
               for i in range(13)]
        d.line(pts, fill=c, width=8, joint="curve")
        for p in pts[::3]:
            d.ellipse((p[0] - 9, p[1] - 9, p[0] + 9, p[1] + 9), fill=m)
    elif kind == "surface":
        for k in range(9):
            pts = [(x0 + i * (x1 - x0) / 20, y0 + 20 + k * (y1 - y0 - 30) / 9 + 30 * math.sin(i * 0.5 + k * 0.6))
                   for i in range(21)]
            d.line(pts, fill=c if k % 2 else m, width=4)
    elif kind == "wafer":
        cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, (y1 - y0) / 2
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c, width=6)
        s = r / 5
        for i in range(-5, 5):
            for j in range(-5, 5):
                px, py = cx + i * s, cy + j * s
                if (px + s / 2 - cx) ** 2 + (py + s / 2 - cy) ** 2 < (r - s * 0.6) ** 2:
                    d.rectangle((px + 3, py + 3, px + s - 3, py + s - 3), fill=m if rng.random() < 0.12 else c)
    elif kind == "app":
        pw = (y1 - y0) * 0.55
        d.rounded_rectangle(((x0 + x1) / 2 - pw / 2, y0 - 10, (x0 + x1) / 2 + pw / 2, y1), radius=24, outline=c, width=6)
        for k in range(4):
            yy = y0 + 30 + k * 55
            d.rounded_rectangle(((x0 + x1) / 2 - pw / 2 + 20, yy, (x0 + x1) / 2 + pw / 2 - 20, yy + 38), radius=10,
                                fill=m if k == 0 else c)
    elif kind == "code":
        for k in range(7):
            ind = [0, 1, 2, 2, 1, 2, 0][k]
            w = rng.uniform(0.3, 0.8) * (x1 - x0)
            d.rounded_rectangle((x0 + ind * 40, y0 + k * 40, x0 + ind * 40 + w, y0 + k * 40 + 20), radius=10,
                                fill=c if k % 3 else m)
    elif kind == "rocket":
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        body = [(cx, y0), (cx + 50, cy), (cx + 50, y1 - 40), (cx - 50, y1 - 40), (cx - 50, cy)]
        d.polygon(body, outline=c, fill=(10, 30, 60, 0), width=6)
        d.line(body + [body[0]], fill=c, width=7)
        d.ellipse((cx - 20, cy - 10, cx + 20, cy + 30), outline=m, width=6)
        d.polygon([(cx - 30, y1 - 40), (cx + 30, y1 - 40), (cx, y1 + 10)], fill=m)
    elif kind == "check":
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        d.line([(cx - 80, cy), (cx - 20, cy + 60), (cx + 90, cy - 70)], fill=c, width=24, joint="curve")
    elif kind == "prompt":
        d.rounded_rectangle((x0, y0 + 30, x1, y0 + 120), radius=20, outline=c, width=5)
        d.text((x0 + 24, y0 + 75), prompt, font=font("regular", 36), fill=c, anchor="lm")
        d.rectangle((x0 + 24, y0 + 150, x0 + 44, y0 + 190), fill=m)
    return _save(im, path)


# ------------------------------------------------------------------ things
def coin(path, s=200, text="T", colour=(0x5E, 0x8F, 0x77)):
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((6, 6, s - 6, s - 6), fill=rgba(colour), outline=INK, width=9)
    d.ellipse((30, 30, s - 30, s - 30), outline=(200, 225, 210, 255), width=6)
    d.text((s / 2, s / 2 + 4), text, font=font("bold", s * 0.5), fill=PAPER, anchor="mm")
    return _save(im, path)


def scale_parts(base, beam, pan_left, pan_right, labels=("TOKENS", "VALUE"), accent=GREEN):
    """Balance in three parts: column (fixed), beam (turns), two labelled pans (hang straight).
    -> (aspect base, aspect beam, aspect pan); the right label is in the accent colour."""
    b = Image.new("RGBA", (300, 700), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    d.rectangle((130, 60, 170, 640), fill=PAPER, outline=INK, width=8)
    foot = [(40, 690), (260, 690), (190, 630), (110, 630)]
    d.polygon(foot, fill=PAPER, outline=INK)
    d.line(foot + [foot[0]], fill=INK, width=8)
    d.ellipse((115, 25, 185, 95), fill=rgba(accent), outline=INK, width=8)
    a1 = _save(b, base)
    bal = Image.new("RGBA", (1400, 80), (0, 0, 0, 0))
    ImageDraw.Draw(bal).rounded_rectangle((6, 16, 1394, 64), radius=24, fill=PAPER, outline=INK, width=8)
    a2 = _save(bal, beam)
    asp = []
    for p, t, col in ((pan_left, labels[0], INK), (pan_right, labels[1], rgba(accent))):
        s = Image.new("RGBA", (500, 520), (0, 0, 0, 0))
        d = ImageDraw.Draw(s)
        d.line([(250, 10), (60, 330)], fill=INK, width=6)
        d.line([(250, 10), (440, 330)], fill=INK, width=6)
        d.chord((30, 230, 470, 430), 0, 180, fill=PAPER, outline=INK, width=9)
        d.text((250, 470), t, font=font("bold", 64), fill=col, anchor="mm")
        asp.append(_save(s, p))
    return a1, a2, asp[0]


def confetti_piece(path, colour, shape=0):
    im = Image.new("RGBA", (80, 50), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if shape == 0:
        d.rectangle((4, 4, 76, 46), fill=rgba(colour), outline=INK, width=4)
    else:
        d.ellipse((14, 4, 56, 46), fill=rgba(colour), outline=INK, width=4)
    return _save(im, path)


CONFETTI_COLOURS = [(0x44, 0x6F, 0x5C, 255), (250, 249, 244, 255), (120, 170, 140, 255), (230, 200, 90, 255)]


def confetti_set(tex_dir, colours=CONFETTI_COLOURS, prefix="confetti"):
    """confetti_0..n.png (rectangles and dots alternating) -> list of srcs relative to the scene (tex/...)."""
    out = []
    for i, c in enumerate(colours):
        confetti_piece(Path(tex_dir) / f"{prefix}{i}.png", c, shape=i % 2)
        out.append(f"tex/{prefix}{i}.png")
    return out


def progress_frame(path, W=700, H=120, label="AI skills"):
    im = Image.new("RGBA", (W, H + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((W / 2, 30), label, font=font("comic", 46), fill=INK, anchor="mm")
    d.rounded_rectangle((6, 66, W - 6, H + 64), radius=H // 2, fill=PAPER, outline=INK, width=10)
    return _save(im, path)


def progress_fill(path, W=660, H=80, colour=(0x5E, 0x8F, 0x77)):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, W, H), radius=H // 2, fill=rgba(colour))
    return _save(im, path)


# ------------------------------------------------------------------ light
def soft_light(path, W=300, H=600, colour=(255, 236, 170)):
    """Soft light rectangle (door gap, additive)."""
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rectangle((W * 0.12, H * 0.06, W * 0.88, H * 0.98), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(W * 0.08))
    im = Image.new("RGBA", (W, H), tuple(colour) + (0,))
    im.putalpha(m)
    return _save(im, path)


def warm_light(path, s=512, colour=(255, 214, 140)):
    import numpy as np
    yy, xx = (np.mgrid[:s, :s] - s / 2 + 0.5) / (s / 2)
    a = np.clip(1 - np.hypot(xx, yy), 0, 1) ** 2
    px = np.dstack([np.full((s, s), c) for c in colour] + [a * 255]).astype("uint8")
    return _save(Image.fromarray(px, "RGBA"), path)


def light_cone(path, W=500, H=900, colour=(255, 236, 190)):
    """Spotlight cone from above (additive)."""
    import numpy as np
    yy, xx = np.mgrid[:H, :W].astype(float)
    t = yy / H
    width = 0.12 + 0.38 * t
    a = np.clip(1 - np.abs(xx / W - 0.5) / width, 0, 1) ** 1.5 * (0.25 + 0.75 * t) * np.clip((1 - t) * 6, 0, 1)
    px = np.dstack([np.full((H, W), c) for c in colour] + [a * 200]).astype("uint8")
    return _save(Image.fromarray(px, "RGBA"), path)


# ------------------------------------------------------------------ sets
def island_floor(path, tone=(244, 242, 234), s=800):
    """Round floor plate seen from above, ink rim and a shadow edge (lay it flat: layer rotx=-pi/2)."""
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((20, 40, s - 20, s - 10), fill=(60, 58, 54, 255))
    d.ellipse((20, 20, s - 20, s - 30), fill=tuple(tone) + (255,), outline=INK, width=14)
    for r in (0.62, 0.36):
        m = s * (1 - r) / 2
        d.ellipse((m, m - 5, s - m, s - m - 5), outline=(215, 212, 204, 255), width=6)
    return _save(im, path)


# ------------------------------------------------------------------ boards and overlays
def pipeline_board(path, title, stations, bin_text="", pass_text="", xs=None, belt_y=640, size=(1920, 1088),
                   accent=GREEN):
    """A process drawn on paper: title, station boxes (title + subtitle) with arrows, a conveyor belt below, a waste
    bin under the gap between the last two stations. -> (station x pixels, belt y pixel, bin x pixel)."""
    W, H = size
    n = len(stations)
    xs = xs or [round(W / 2 + (i - (n - 1) / 2) * 365) for i in range(n)]
    im = Image.new("RGB", size, PAPER[:3])
    d = ImageDraw.Draw(im)
    ink, g = INK[:3], tuple(accent[:3])
    d.text((W / 2, 90), title, font=font("bold", 78), fill=ink, anchor="mm")
    d.rounded_rectangle((90, belt_y, W - 90, belt_y + 60), radius=30, fill=(225, 225, 220), outline=ink, width=8)
    for x in range(130, W - 100, 70):
        d.line([(x, belt_y + 12), (x + 24, belt_y + 48)], fill=(150, 150, 150), width=6)
    for x in (130, W - 130):
        d.ellipse((x - 44, belt_y - 14, x + 44, belt_y + 74), outline=ink, width=8)
    for i, ((t, u), x) in enumerate(zip(stations, xs)):
        d.rounded_rectangle((x - 160, 250, x + 160, belt_y - 70), radius=30, fill=(255, 255, 255), outline=ink, width=9)
        d.rectangle((x - 140, 270, x + 140, 290), fill=g)
        d.text((x, 345), t, font=font("bold", 33), fill=g, anchor="mm")
        d.text((x, 400), u, font=font("regular", 29), fill=(60, 60, 64), anchor="mm")
        d.polygon([(x - 40, belt_y - 70), (x + 40, belt_y - 70), (x, belt_y - 25)], fill=ink)
        if i < n - 1:
            d.line([(x + 175, 420), (xs[i + 1] - 175, 420)], fill=ink, width=8)
            d.polygon([(xs[i + 1] - 175, 420), (xs[i + 1] - 200, 405), (xs[i + 1] - 200, 435)], fill=ink)
    bx = (xs[-2] + xs[-1]) / 2
    rim = [(bx - 90, 780), (bx + 90, 780), (bx + 70, 990), (bx - 70, 990)]
    d.polygon(rim, fill=(235, 235, 230), outline=ink)
    d.line(rim + [rim[0]], fill=ink, width=9)
    for k in (-40, 0, 40):
        d.line([(bx + k, 810), (bx + k * 0.8, 965)], fill=ink, width=5)
    if bin_text:
        d.text((bx, 1030), bin_text, font=font("regular", 30), fill=(90, 90, 96), anchor="mm")
    if pass_text:
        d.text((xs[-1], 770), pass_text, font=font("regular", 30), fill=g, anchor="mm")
    im.save(path)
    return xs, belt_y, bx


def counters(im, values, u, show=True, x0=160, dx=300, y=960, accent=GREEN):
    """Post overlay: numbers rolling up (u 0 -> 1) with a label below - values [(number, label, prefix), ...]."""
    if not show:
        return im
    d = ImageDraw.Draw(im)
    fb, fr = font("bold", 64), font("regular", 30)
    for i, (v, label, pre) in enumerate(values):
        x = x0 + i * dx
        d.text((x, y), f"{pre}{int(round(v * u)):,}", font=fb, fill=tuple(accent[:3]), anchor="mm")
        d.text((x, y + 50), label, font=fr, fill=(60, 60, 64), anchor="mm")
    return im


def counter_box(im, value, label, alpha=1.0, box=(1370, 40, 1880, 170), accent=GREEN):
    """Post overlay: a rattling counter in a paper box (top right by default), faded with alpha."""
    if alpha <= 0:
        return im
    out = im.copy()
    d = ImageDraw.Draw(out)
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=26, fill=PAPER[:3], outline=INK[:3], width=6)
    cx = (x0 + x1) / 2
    d.text((cx, y0 + 42), f"{value:,}", font=font("bold", 66), fill=tuple(accent[:3]), anchor="mm")
    d.text((cx, y0 + 100), label, font=font("regular", 32), fill=(60, 60, 64), anchor="mm")
    return out if alpha >= 1 else Image.blend(im, out, alpha)
