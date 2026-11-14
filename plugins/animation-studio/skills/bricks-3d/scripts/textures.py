# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Printed decals for brick films (Pillow, runs outside Blender): minifig faces with 9 mouth shapes (Rhubarb X A-H),
blink tiles, torso prints, a hair clip, a night skyline and the monitor screens of a film.

Faces are drawn in the minifig printing style: black lines, few flat colours. Every face style is an atlas
<style>_eyes.png (2 tiles: open, closed) + <style>_mouths.png (9 tiles X A B C D E F G H).
Styles: classic (smile, dot eyes), glasses (Tim), calm (Claudia-like: straight brows, freckles, thin headset mic),
lashes, robot (LED eyes, grille mouth), grin (silhouette: no face, only a white grin; tiles X=none, A=grin, B=laugh).
Torso prints: hoodie, blazer, dress, tee_star, plain; name signs (--signs: a white label with neutral lettering
and three LEDs, for robots / bidders - company names only as plain text, never logos). Screens: one tile per entry of a screens list
({"kind": "text"|"terminal"|"heart"|"code"|"bar"|"face", "text": "...", "color": "#rrggbb"}) -> screens.png + computer_face.png.

Usage (normally called by the user skill):
  uv run textures.py <out_dir> [--screens screens.json] [--signs signs.json] [--seed 7]
  signs.json: [{"text": "OPEN", "file": "torso_sign_open.png"}, ...]  (written by the planner / render.py)
"""
import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

K = 2                     # supersampling
N = 512                   # face tile size
INK = (28, 22, 18, 255)
MOUTH_RED = (110, 24, 24, 255)
TONGUE = (205, 90, 90, 255)
WHITE = (250, 250, 245, 255)
SHAPES = "XABCDEFGH"
FONTS_MONO = ["C:/Windows/Fonts/consolab.ttf", "C:/Windows/Fonts/consola.ttf", "/System/Library/Fonts/Menlo.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]


def font(size):
    for f in FONTS_MONO:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def blank(w=N, h=N):
    return Image.new("RGBA", (w * K, h * K), (0, 0, 0, 0))


def done(img):
    return img.resize((img.width // K, img.height // K), Image.LANCZOS)


def p(u, v):
    """u, v in 0..1 (v=0 bottom) -> pixel (supersampled)"""
    return (u * N * K, (1 - v) * N * K)


def box(u, v, ru, rv):
    (x0, y0), (x1, y1) = p(u - ru, v + rv), p(u + ru, v - rv)
    return [x0, y0, x1, y1]


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------------ eyes
def eyes(style, open_):
    img = blank()
    d = ImageDraw.Draw(img)
    lw = int(0.02 * N * K)
    rnd = random.Random(5)
    for s in (-1, 1):
        if style == "glasses":
            u = 0.5 + s * 0.135
            d.ellipse(box(u, 0.60, 0.095, 0.11), outline=INK, width=lw)
            if open_:
                d.ellipse(box(u, 0.595, 0.032, 0.05), fill=INK)
                d.ellipse(box(u + 0.012, 0.615, 0.011, 0.016), fill=WHITE)
            else:
                d.arc(box(u, 0.61, 0.045, 0.035), 20, 160, fill=INK, width=lw)
            d.line([p(u - 0.07, 0.765 + 0.01 * s), p(u + 0.07, 0.765 - 0.01 * s)], fill=INK, width=int(lw * 1.1))
            d.line([p(u + s * 0.095, 0.62), p(u + s * 0.2, 0.64)], fill=INK, width=lw)
        elif style == "calm":
            u = 0.5 + s * 0.125
            lw2 = int(0.016 * N * K)
            if open_:
                d.ellipse(box(u, 0.59, 0.036, 0.05), fill=INK)
                d.ellipse(box(u + 0.012, 0.61, 0.011, 0.015), fill=WHITE)
                d.line([p(u + s * 0.03, 0.625), p(u + s * 0.06, 0.645)], fill=INK, width=lw2)
            else:
                d.line([p(u - 0.04, 0.59), p(u + 0.04, 0.59)], fill=INK, width=lw2)
            d.line([p(u - 0.06, 0.70), p(u + 0.06, 0.70 - 0.004 * s)], fill=INK, width=int(lw2 * 1.3))
            for _ in range(9):                                           # freckles
                fu, fv = u - s * 0.02 + rnd.uniform(-0.06, 0.06), 0.47 + rnd.uniform(-0.035, 0.035)
                d.ellipse(box(fu, fv, 0.007, 0.007), fill=(176, 104, 62, 230))
        elif style == "lashes":
            u = 0.5 + s * 0.13
            if open_:
                d.ellipse(box(u, 0.59, 0.045, 0.07), fill=INK)
                d.ellipse(box(u + 0.016, 0.62, 0.016, 0.022), fill=WHITE)
                for k in (-1, 0, 1):
                    d.line([p(u + s * 0.035, 0.64 + k * 0.025), p(u + s * 0.075, 0.665 + k * 0.035)], fill=INK, width=lw)
            else:
                d.arc(box(u, 0.60, 0.05, 0.035), 20, 160, fill=INK, width=lw)
            d.arc(box(u, 0.73, 0.06, 0.03), 200, 340, fill=(90, 50, 140, 255), width=int(lw * 1.2))
            d.ellipse(box(u + s * 0.02, 0.42, 0.05, 0.03), fill=(240, 140, 150, 150))
        elif style == "robot":
            u = 0.5 + s * 0.13
            if open_:
                d.rounded_rectangle(box(u, 0.6, 0.05, 0.05), radius=8 * K, fill=(90, 230, 255, 255))
            else:
                d.line([p(u - 0.05, 0.6), p(u + 0.05, 0.6)], fill=(90, 230, 255, 255), width=8 * K)
        elif style == "grin":
            pass
        else:                                                            # classic
            u = 0.5 + s * 0.12
            if open_:
                d.ellipse(box(u, 0.6, 0.032, 0.045), fill=INK)
                d.ellipse(box(u + 0.01, 0.615, 0.01, 0.013), fill=WHITE)
            else:
                d.arc(box(u, 0.61, 0.04, 0.03), 20, 160, fill=INK, width=lw)
            d.line([p(u - 0.05, 0.71), p(u + 0.05, 0.715 - 0.01 * s)], fill=INK, width=lw)
    if style == "calm":                                                  # thin headset mic, her right side = image left
        lw2 = int(0.016 * N * K)
        d.line([p(0.11, 0.60), p(0.17, 0.40), p(0.38, 0.31)], fill=(30, 30, 34, 255), width=int(lw2 * 0.8), joint="curve")
        d.ellipse(box(0.39, 0.31, 0.018, 0.018), fill=(30, 30, 34, 255))
    return done(img)


# ------------------------------------------------------------------ mouths
def mouth(shape, ink=INK, deadpan=False):
    img = blank()
    d = ImageDraw.Draw(img)
    lw = int(0.018 * N * K)
    u, v = 0.5, 0.30
    if shape == "X" and deadpan:
        d.line([p(u - 0.07, v + 0.005), p(u + 0.07, v)], fill=ink, width=lw)
    elif shape == "X":
        d.arc(box(u, v + 0.06, 0.12, 0.07), 20, 160, fill=ink, width=lw)
    elif shape == "A":                                    # M B P: lips closed
        d.line([p(u - 0.1, v), p(u + 0.1, v)], fill=ink, width=int(lw * 1.2))
    elif shape == "B":                                    # slightly open, teeth
        d.rounded_rectangle(box(u, v, 0.11, 0.04), radius=int(0.03 * N * K), fill=MOUTH_RED, outline=ink, width=lw)
        d.rectangle(box(u, v + 0.015, 0.085, 0.012), fill=WHITE)
    elif shape == "C":                                    # open
        d.ellipse(box(u, v, 0.1, 0.07), fill=MOUTH_RED, outline=ink, width=lw)
        d.rectangle(box(u, v + 0.035, 0.07, 0.013), fill=WHITE)
    elif shape == "D":                                    # wide open
        d.chord(box(u, v + 0.03, 0.13, 0.12), 0, 180, fill=MOUTH_RED, outline=ink, width=lw)
        d.rectangle(box(u, v + 0.015, 0.11, 0.014), fill=WHITE)
        d.ellipse(box(u, v - 0.06, 0.06, 0.03), fill=TONGUE)
    elif shape == "E":                                    # rounded
        d.ellipse(box(u, v, 0.075, 0.06), fill=MOUTH_RED, outline=ink, width=lw)
    elif shape == "F":                                    # puckered (u, w)
        d.ellipse(box(u, v, 0.04, 0.045), fill=MOUTH_RED, outline=ink, width=lw)
    elif shape == "G":                                    # F, V: teeth on the lower lip
        d.rounded_rectangle(box(u, v, 0.1, 0.035), radius=int(0.02 * N * K), fill=MOUTH_RED, outline=ink, width=lw)
        d.rectangle(box(u, v + 0.005, 0.075, 0.018), fill=WHITE)
    elif shape == "H":                                    # L: tongue up
        d.ellipse(box(u, v, 0.09, 0.065), fill=MOUTH_RED, outline=ink, width=lw)
        d.ellipse(box(u, v + 0.02, 0.045, 0.028), fill=TONGUE)
    return done(img)


def robot_mouth(shape):
    img = blank()
    d = ImageDraw.Draw(img)
    hi = {"X": 0.012, "A": 0.008, "B": 0.03, "C": 0.05, "D": 0.07, "E": 0.05, "F": 0.04, "G": 0.025, "H": 0.05}[shape]
    d.rectangle(box(0.5, 0.32, 0.12, hi), fill=(30, 34, 40, 255))
    for k in range(-4, 5):
        d.line([p(0.5 + k * 0.025, 0.32 - hi), p(0.5 + k * 0.025, 0.32 + hi)], fill=(120, 130, 140, 255), width=2 * K)
    return done(img)


def grin(kind):
    """Silhouette: no face, only a white grin (1) or a laugh (2); 0 = nothing."""
    img = blank()
    d = ImageDraw.Draw(img)
    if kind == 1:
        d.chord(box(0.5, 0.40, 0.2, 0.13), 0, 180, fill=WHITE)
        d.chord(box(0.5, 0.445, 0.2, 0.06), 0, 180, fill=(0, 0, 0, 0))
        for k in range(-3, 4):
            d.line([p(0.5 + k * 0.05, 0.36), p(0.5 + k * 0.05, 0.33)], fill=(60, 60, 60, 255), width=3 * K)
    elif kind == 2:
        d.chord(box(0.5, 0.42, 0.21, 0.17), 0, 180, fill=WHITE)
        d.chord(box(0.5, 0.40, 0.16, 0.10), 0, 180, fill=(70, 10, 10, 255))
    return done(img)


def atlas(images, path, tile_w=N, tile_h=N):
    a = Image.new("RGBA", (tile_w * len(images), tile_h), (0, 0, 0, 0))
    for i, b in enumerate(images):
        a.paste(b, (i * tile_w, 0))
    a.save(path)


def face_set(style, out, lip=None):
    """<style>_eyes.png + <style>_mouths.png"""
    atlas([eyes(style, True), eyes(style, False)], out / f"{style}_eyes.png")
    if style == "robot":
        ms = [robot_mouth(m) for m in SHAPES]
    elif style == "grin":
        ms = [grin(0), grin(1), grin(2)] + [grin(0)] * 6
    elif style == "calm":
        ms = [mouth(m, (150, 70, 62, 255), deadpan=True) for m in SHAPES]
    elif style == "lashes":
        ms = [mouth(m, (150, 30, 70, 255)) for m in SHAPES]
    else:
        ms = [mouth(m) for m in SHAPES]
    atlas(ms, out / f"{style}_mouths.png")


# ------------------------------------------------------------------ torso prints (44 x 32 LDU front)
def torso(kind, out):
    w, h = 440, 320
    img = Image.new("RGBA", (w * K, h * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = lambda x, y: (x * K, y * K)
    if kind == "hoodie":
        d.arc([s(150, -40)[0], s(150, -40)[1], s(290, 40)[0], s(290, 40)[1]], 0, 180, fill=(90, 15, 15, 255), width=7 * K)
        for x0 in (196, 244):
            dx = -6 if x0 < 220 else 6
            d.line([s(x0, 30), s(x0 + dx, 120)], fill=(245, 225, 200, 255), width=6 * K)
            d.ellipse([s(x0 - 9 + dx, 116), s(x0 + 9 + dx, 134)], fill=(245, 225, 200, 255))
        d.polygon([s(140, 210), s(300, 210), s(330, 312), s(110, 312)], fill=(0, 0, 0, 60), outline=(40, 10, 10, 200))
    elif kind == "blazer":
        d.polygon([s(165, 0), s(275, 0), s(262, 40), s(220, 215), s(178, 40)], fill=(238, 236, 230, 255))
        d.rectangle([s(172, 0), s(268, 26)], fill=(226, 224, 218, 255))
        rev = (45, 48, 54, 255)
        d.line([s(178, 40), s(150, 120), s(220, 215)], fill=rev, width=5 * K)
        d.line([s(262, 40), s(290, 120), s(220, 215)], fill=rev, width=5 * K)
        for y in (240, 282):
            d.ellipse([s(212, y - 7), s(228, y + 7)], fill=(30, 32, 36, 255))
        d.line([s(110, 250), s(170, 250)], fill=rev, width=4 * K)
        d.line([s(270, 250), s(330, 250)], fill=rev, width=4 * K)
    elif kind == "dress":
        d.arc([s(160, -50)[0], s(160, -50)[1], s(280, 40)[0], s(280, 40)[1]], 0, 180, fill=(245, 225, 200, 255), width=8 * K)
        d.ellipse([s(250, 70), s(290, 110)], fill=(250, 205, 40, 255), outline=(150, 110, 10, 255), width=3 * K)
        d.rectangle([s(100, 215), s(340, 250)], fill=(4, 120, 122, 255))
    elif kind == "tee_star":
        c, ra, ri = (220, 150), 70, 30
        pts = [(c[0] + (ra if i % 2 == 0 else ri) * math.cos(math.pi * i / 5 - math.pi / 2),
                c[1] + (ra if i % 2 == 0 else ri) * math.sin(math.pi * i / 5 - math.pi / 2)) for i in range(10)]
        d.polygon([s(*q) for q in pts], fill=(255, 214, 10, 255), outline=(40, 30, 10, 255))
    elif kind == "robot_panel":
        d.rounded_rectangle([s(120, 90), s(320, 200)], radius=14 * K, fill=(40, 44, 52, 255), outline=(20, 20, 24, 255), width=3 * K)
        for x in (160, 220, 280):
            d.ellipse([s(x - 10, 135), s(x + 10, 155)], fill=(90, 230, 255, 255))
    img.resize((w, h), Image.LANCZOS).save(out / f"torso_{kind}.png")


def name_sign(text, path):
    """Name sign printed on a torso front (44 x 32 LDU): white rounded label with the text, three LEDs below
    (the reference robots' chest signs)."""
    w, h = 440, 320
    img = Image.new("RGBA", (w * K, h * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = lambda x, y: (x * K, y * K)
    d.rounded_rectangle([s(90, 90), s(350, 190)], radius=14 * K, fill=(245, 245, 240, 255), outline=(40, 40, 40, 255),
                        width=4 * K)
    size = 64 if len(text) <= 7 else 50 if len(text) <= 9 else 40 if len(text) <= 11 else 32
    f = font(size * K)
    while d.textlength(text, font=f) > 240 * K and size > 16:     # long names shrink to fit the label
        size -= 2
        f = font(size * K)
    d.text(s(220, 140), text, font=f, fill=(20, 20, 24, 255), anchor="mm")
    for x in (150, 220, 290):
        d.ellipse([s(x - 9, 225), s(x + 9, 243)], fill=(90, 230, 255, 255))
    img.resize((w, h), Image.LANCZOS).save(path)


def star_clip(out):
    g = 256
    img = Image.new("RGBA", (g * K, g * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, ra, ri = g * K / 2, g * K * 0.46, g * K * 0.2
    pts = [(c + (ra if i % 2 == 0 else ri) * math.cos(math.pi * i / 8 - math.pi / 2),
            c + (ra if i % 2 == 0 else ri) * math.sin(math.pi * i / 8 - math.pi / 2)) for i in range(16)]
    d.polygon(pts, fill=(217, 119, 87, 255), outline=(150, 70, 50, 255))
    img.resize((g, g), Image.LANCZOS).save(out / "clip_star.png")


def skyline(out, seed=7, moon=True):
    rnd = random.Random(seed)
    w, h = 1200, 900
    a = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(a)
    for y in range(h):
        k = y / h
        d.line([(0, y), (w, y)], fill=(int(10 + 30 * k), int(14 + 26 * k), int(40 + 50 * k)))
    for _ in range(90):
        d.point((rnd.randrange(w), rnd.randrange(h // 2)), fill=(200, 210, 255))
    if moon:
        mx = rnd.randint(120, 1000)
        d.ellipse([mx, 90, mx + 100, 190], fill=(240, 235, 210))
    x = 0
    while x < w:
        bw, bh = rnd.randint(60, 150), rnd.randint(250, 650)
        d.rectangle([x, h - bh, x + bw, h], fill=(18, 22, 38))
        for wy in range(h - bh + 20, h - 10, 28):
            for wx in range(x + 10, x + bw - 14, 22):
                if rnd.random() < 0.45:
                    d.rectangle([wx, wy, wx + 10, wy + 14], fill=rnd.choice([(255, 210, 120), (255, 190, 90), (150, 210, 255)]))
        x += bw + rnd.randint(4, 20)
    a.save(out / "skyline.png")


# ------------------------------------------------------------------ screens
def screen_tile(ev, seed=3):
    w, h = 640, 480
    kind = ev.get("kind", "text")
    col = rgb(ev.get("color", "#78e6ff"))
    bg = rgb(ev.get("background", "#080e1a"))
    a = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(a)
    if kind == "heart":
        a.paste((40, 8, 30), [0, 0, w, h])
        cx, cy, r = w // 2, h // 2 - 20, 120
        pink = (255, 70, 130)
        d.ellipse([cx - 2 * r + 20, cy - r, cx + 20, cy + r], fill=pink)
        d.ellipse([cx - 20, cy - r, cx + 2 * r - 20, cy + r], fill=pink)
        d.polygon([(cx - 2 * r + 28, cy + 30), (cx + 2 * r - 28, cy + 30), (cx, cy + 2 * r + 20)], fill=pink)
        if ev.get("text"):
            d.text((cx, h - 50), ev["text"], font=font(44), fill=(255, 220, 235), anchor="mm")
    elif kind == "code":
        rnd = random.Random(seed)
        rows = ev.get("lines") or ["def song(x):", "  return x+1", "for p in prompts:", "  tokens -= 1", "# TODO",
                                   "import idea", "while True:", "  hope()"]
        for i in range(9):
            d.text((40 + rnd.randint(0, 60), 40 + i * 46), rnd.choice(rows), font=font(34), fill=col)
    elif kind == "bar":
        share = float(ev.get("value", 1.0))
        d.text((w // 2, 170), ev.get("text", ""), font=font(100 if len(ev.get("text", "")) <= 6 else 64), fill=col, anchor="mm")
        d.rectangle([60, 380, 580, 420], outline=(90, 110, 130), width=4)
        d.rectangle([66, 386, 66 + int(508 * share), 414], fill=col)
    elif kind == "terminal":                                         # left-aligned prompt lines, one highlighted
        for i, z in enumerate(ev.get("lines", ["> _"])):
            hl = i == ev.get("highlight", -1)
            d.text((40, 60 + i * 72), z, font=font(40), fill=rgb(ev.get("highlight_color", "#ffaa5a")) if hl else col)
    elif kind == "face":
        pass                                                         # the talking face is drawn by computer_face.png
    else:
        text = ev.get("text", "")
        rows = text.split("\n")
        size = 150 if max(len(r) for r in rows) <= 5 else 96 if max(len(r) for r in rows) <= 9 else 56 if max(
            len(r) for r in rows) <= 16 else 40
        y0 = h / 2 - (len(rows) - 1) * size * 0.6
        for i, r in enumerate(rows):
            d.text((w / 2, y0 + i * size * 1.2), r, font=font(size), fill=col, anchor="mm")
    return a


def computer_face(out):
    """Talking monitor face (cyan on transparent), one tile per mouth shape."""
    w, h = 640, 480
    tiles = []
    for shape in SHAPES:
        img = Image.new("RGBA", (w * K, h * K), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = (120, 230, 255, 255)
        s = lambda x, y: (x * K, y * K)
        for x in (220, 420):
            d.rounded_rectangle([s(x - 40, 120), s(x + 40, 210)], radius=24 * K, fill=c)
        opening = {"X": 0, "A": 0, "B": 10, "C": 30, "D": 55, "E": 34, "F": 26, "G": 14, "H": 32}[shape]
        wide = {"E": 70, "F": 40}.get(shape, 120)
        if opening == 0:
            d.line([s(320 - wide, 330), s(320 + wide, 330)], fill=c, width=12 * K)
        else:
            d.rounded_rectangle([s(320 - wide, 330 - opening), s(320 + wide, 330 + opening)], radius=20 * K, outline=c,
                                width=12 * K)
        tiles.append(img.resize((w, h), Image.LANCZOS))
    atlas(tiles, out / "computer_face.png", w, h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--screens", help="JSON list of screen tiles")
    ap.add_argument("--signs", help="JSON list of name signs [{text, file}]")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for style in ("classic", "glasses", "calm", "lashes", "robot", "grin"):
        face_set(style, out)
    for kind in ("hoodie", "blazer", "dress", "tee_star", "robot_panel"):
        torso(kind, out)
    for sg in (json.loads(Path(a.signs).read_text(encoding="utf-8")) if a.signs else []):
        name_sign(sg["text"], out / sg["file"])
    star_clip(out)
    skyline(out, a.seed)
    screens = json.loads(Path(a.screens).read_text(encoding="utf-8")) if a.screens else [{"kind": "code"}]
    s = Image.new("RGB", (640 * len(screens), 480))
    for i, ev in enumerate(screens):
        s.paste(screen_tile(ev, a.seed + i), (i * 640, 0))
    s.save(out / "screens.png")
    computer_face(out)
    print(f"textures -> {out} ({len(screens)} screens)")


if __name__ == "__main__":
    main()
