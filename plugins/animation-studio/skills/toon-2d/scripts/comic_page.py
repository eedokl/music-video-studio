"""Build the pieces of a 2.5D comic flight: the page with transparent panel windows, speech bubbles, panel crops.

    import comic_page as cp
    PANELS = {"p1": (50, 140, 1140, 560), "p2": (50, 730, 555, 560), "p3": (635, 730, 555, 560)}  # x, y, w, h (page px)
    cp.page((1240, 1420), PANELS, title="Pip and the Leaf", footer_left="Page 1", footer_right="To be continued ...",
            seed=3).save("page.png")
    cp.bubble((1100, 1110), "Oh!", tail_to=(300, 420), font_size=120).save("p2_bubble.png")
    cp.crop_aspect(img, w / h, cx=0.5, cy=0.55)                 # a layer cut to the panel's aspect ratio
    cp.flat_preview("page.png", {"p1": ["p1_sky.png", ...]}, PANELS).save("page_flat.png")   # printed look

Page: paper colour + fine paper grain, title, footer, ink frames 8 px; panel areas fully transparent (alpha 0) -
comic25d.html shows each panel's diorama through these windows. Layer images use the panel's aspect ratio.
Fonts: a TrueType file name or path (default "segoeprb.ttf", Segoe Print Bold on Windows); falls back to DejaVu
or Pillow's built-in font when it is missing.
Needs pillow + numpy (imported by scripts that declare them, e.g. breakout.py).
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

INK = (43, 29, 20)
PAPER = (246, 240, 226)
FONTS = ["segoeprb.ttf", "comicbd.ttf", "DejaVuSans-Bold.ttf"]


def font(size, name=None):
    for n in ([name] if name else []) + FONTS:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def crop_aspect(img, aspect, cx=0.5, cy=0.5, zoom=1.0):
    """Cut-out with aspect ratio `aspect` (w/h) around (cx, cy) relative; zoom > 1 = tighter."""
    w, h = img.size
    cw = min(w, h * aspect) / zoom
    ch = cw / aspect
    x0 = min(max(cx * w - cw / 2, 0), w - cw)
    y0 = min(max(cy * h - ch / 2, 0), h - ch)
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch)))


def alpha_bbox(img, thresh=200, min_px=150):
    """Bounding box (x0, y0, x1, y1) of the opaque part of an RGBA image (e.g. a character render)."""
    a = np.array(img.getchannel("A"))
    rows = np.where((a > thresh).sum(1) > min_px)[0]
    cols = np.where((a > thresh).sum(0) > min_px)[0]
    return cols.min(), rows.min(), cols.max(), rows.max()


def clamp_box(box, size):
    """Shift a crop box into the image (keeping its size where possible)."""
    x0, y0, x1, y1 = box
    w, h = size
    dx = -x0 if x0 < 0 else (w - x1 if x1 > w else 0)
    dy = -y0 if y0 < 0 else (h - y1 if y1 > h else 0)
    return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)


def figure_closeup(img, aspect, out_width, height_factor=2.3, shift=(-0.15, -0.35)):
    """Crop around the opaque figure of an RGBA render: the crop is height_factor x the figure height, centred on
    the figure shifted by `shift` x figure height (negative y = more headroom). Returns the resized crop."""
    bx0, by0, bx1, by1 = alpha_bbox(img)
    fh = by1 - by0
    side = int(fh * height_factor)
    cx, cy = (bx0 + bx1) / 2 + fh * shift[0], (by0 + by1) / 2 + fh * shift[1]
    box = clamp_box((int(cx - side * aspect / 2), int(cy - side / 2), int(cx + side * aspect / 2), int(cy + side / 2)),
                    img.size)
    return img.crop(box).resize((out_width, int(out_width / aspect)), Image.LANCZOS), box


def bubble(size, text, tail_to, font_size, font_name=None, ink=INK):
    """Speech bubble (ellipse + tail) with text on a transparent image of `size`; tail points to tail_to (px)."""
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(font_size, font_name)
    tb = d.textbbox((0, 0), text, font=f)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    bx, by = int(w * 0.1), int(h * 0.08)
    ew, eh = int(tw * 1.55), int(th * 2.1)
    cx, cy = bx + ew / 2, by + eh / 2
    tail = [(cx - ew * 0.12, cy + eh * 0.3), (cx + ew * 0.1, cy + eh * 0.35), tail_to]
    d.polygon(tail, fill=(255, 255, 255, 255), outline=ink)
    d.ellipse((bx, by, bx + ew, by + eh), fill=(255, 255, 255, 255), outline=ink, width=6)
    d.line([tail[0], tail[2]], fill=ink, width=6)
    d.line([tail[1], tail[2]], fill=ink, width=6)
    d.ellipse((bx + 6, by + 6, bx + ew - 6, by + eh - 6), fill=(255, 255, 255, 255))   # hide the tail seam
    d.text((cx - tw / 2 - tb[0], cy - th / 2 - tb[1]), text, font=f, fill=ink)
    return img


def page(size, panels, title="", footer_left="", footer_right="", seed=3, paper=PAPER, ink=INK,
         title_size=66, footer_size=30, font_name=None, frame_width=8):
    """Comic page with paper grain, title, footers, ink frames and transparent panel windows."""
    pw, ph = size
    rng = np.random.default_rng(seed)
    pap = np.ones((ph, pw, 3), np.float32) * np.array(paper, np.float32) / 255
    pap += rng.normal(0, 0.012, (ph, pw, 1)).astype(np.float32)          # paper grain
    img = Image.fromarray((pap.clip(0, 1) * 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    if title:
        tf = font(title_size, font_name)
        tb = d.textbbox((0, 0), title, font=tf)
        d.text(((pw - (tb[2] - tb[0])) / 2, 40), title, font=tf, fill=ink)
    sf = font(footer_size, font_name)
    if footer_right:
        d.text((pw - 360, ph - 95), footer_right, font=sf, fill=ink)
    if footer_left:
        d.text((50, ph - 95), footer_left, font=sf, fill=ink)
    alpha = np.array(img.getchannel("A"))
    for x, y, w, h in panels.values():
        alpha[y:y + h, x:x + w] = 0                                      # windows
    img.putalpha(Image.fromarray(alpha))
    d = ImageDraw.Draw(img)
    half = frame_width // 2
    for x, y, w, h in panels.values():
        d.rectangle((x - half, y - half, x + w + half - 1, y + h + half - 1), outline=ink + (255,), width=frame_width)
    return img


def flat_preview(page_png, panel_layers, panels, paper=PAPER):
    """The page as printed: each panel's layers (back to front) composited into its window."""
    pg = Image.open(page_png).convert("RGBA")
    flat = Image.new("RGBA", pg.size, paper + (255,))
    for key, names in panel_layers.items():
        x, y, w, h = panels[key]
        comp = Image.new("RGBA", (w, h))
        for n in names:
            comp = Image.alpha_composite(comp, Image.open(n).convert("RGBA").resize((w, h), Image.LANCZOS))
        flat.paste(comp, (x, y))
    return Image.alpha_composite(flat, pg).convert("RGB")
