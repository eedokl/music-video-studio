"""Textures of a clip (clip.py step "tex"): slide states with the leaving figures removed and dashed outlines in
their place, the room (shared with scene.py), name tags."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

import props
from clip_core import fig_geometry


def rest_mask(g):
    a = None
    for p in g["rig"]["parts"]:
        al = np.asarray(Image.open(g["dir"] / f"{p}.png"))[..., 3].astype(np.float32) / 255
        a = al if a is None else np.maximum(a, al)
    return a


def dashed_outline(mask, size, dash=34, gap=22, width=9):
    from skimage import measure
    sil = ndi.binary_fill_holes(mask > 0.5)
    sil = ndi.binary_opening(sil, iterations=4)
    outer = ndi.gaussian_filter((ndi.distance_transform_edt(~sil) < 15).astype(np.float32), 6)
    cont = max(measure.find_contours(outer, 0.5), key=len)
    seg = np.hypot(*np.diff(cont, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    img = Image.new("L", size, 0)
    dr = ImageDraw.Draw(img)
    for i in range(len(cont) - 1):
        if (s[i] % (dash + gap)) < dash:
            (y0, x0), (y1, x1) = cont[i], cont[i + 1]
            dr.line([(x0, y0), (x1, y1)], fill=255, width=width)
    return ndi.gaussian_filter(np.asarray(img).astype(np.float32) / 255, 0.7)


def accent_color(g):
    im = np.asarray(Image.open(g["dir"] / "original.png").convert("RGBA")).astype(np.float32) / 255
    rgb, a = im[..., :3], im[..., 3]
    chroma = rgb.max(-1) - rgb.min(-1)
    m = (a > 0.9) & (chroma > 0.15)
    if m.sum() < 200:
        return (70, 70, 74)
    return tuple(int(v * 255) for v in np.median(rgb[m], axis=0))


def font(bold, size):
    """Sans lettering of the tags (props.py fonts: bold / regular)."""
    return props.font("bold" if bold else "regular", size)


def room_textures(tex):
    """Room textures shared by clips and scenes: floor, back wall, soft contact shadow, four-point sparkle."""
    rng = np.random.default_rng(3)
    n = 2048
    noise = ndi.gaussian_filter(rng.normal(0, 1, (n, n)), 1.2) * 4 + ndi.gaussian_filter(rng.normal(0, 1, (n, n)), 18) * 30
    yy, xx = np.mgrid[:n, :n] / n
    pool = np.exp(-(((xx - 0.5) / 0.38) ** 2 + ((yy - 0.42) / 0.30) ** 2))
    v = 168 + 62 * pool + noise
    Image.fromarray(np.clip(np.dstack([v, v * 0.985, v * 0.95]), 0, 255).astype(np.uint8)).save(tex / "floor.png")
    hh, ww = 1024, 2048
    yy, xx = np.mgrid[:hh, :ww]
    glow = np.exp(-(((xx - ww / 2) / (ww * 0.32)) ** 2 + ((yy - hh * 0.55) / (hh * 0.45)) ** 2))
    v = 38 + 70 * glow + ndi.gaussian_filter(rng.normal(0, 1, (hh, ww)), 2) * 2
    Image.fromarray(np.clip(np.dstack([v * 1.05, v * 0.98, v * 0.9]), 0, 255).astype(np.uint8)).save(tex / "wall.png")
    s = 256
    yy, xx = (np.mgrid[:s, :s] - s / 2 + 0.5) / (s / 2)
    a = np.clip(1 - np.hypot(xx, yy), 0, 1) ** 1.6
    Image.fromarray(np.dstack([np.zeros((s, s, 3)), a * 255]).astype(np.uint8), "RGBA").save(tex / "shadow.png")
    r = np.hypot(xx, yy) + 1e-6                                       # four-point sparkle (glasses flash)
    ang = np.arctan2(yy, xx)
    rays = np.abs(np.cos(2 * ang)) ** 18
    star = np.clip(1 - r / (0.12 + 0.88 * rays), 0, 1) ** 1.5 + np.clip(1 - r / 0.25, 0, 1) ** 2
    Image.fromarray(np.dstack([np.full((s, s), 255.0), np.full((s, s), 252.0), np.full((s, s), 235.0),
                               np.clip(star, 0, 1) * 255]).astype(np.uint8),
                    "RGBA").save(tex / "sparkle.png")


def remove_figures(C, G, members, plate, masks):
    """Cut the figures of one source picture out of it -> the plate with the picture put back without them (or, for
    figures painted into the slide, the hole filled from the background); masks[n] = the figure's mask on the slide."""
    sw, sh = C.slide_px
    g0 = G[members[0]]
    src = np.asarray(Image.open(C.fig_root / Path(g0["fig"]["source"]).name).convert("RGBA")).astype(np.float32)
    fm_all = np.zeros(src.shape[:2], np.float32)
    f = g0["fig"]["upscale"]
    for n in members:
        g = G[n]
        m = rest_mask(g)
        x0, y0 = g["fig"]["crop"][:2]
        full_m = np.zeros(src.shape[:2], np.float32)
        full_m[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = m
        masks[n] = full_m
        fm_all = np.maximum(fm_all, full_m)
    ring = ndi.binary_dilation(fm_all > 0.05, iterations=int(10 * f)) & (src[..., 3] < 128)
    cut = src.copy()
    cut[..., 3] *= 1 - np.maximum(np.clip(fm_all * 1.15, 0, 1), ring)
    t = g0["fig"]["to_slide"]
    pic = next((p for p in C.slide["pictures"] if p["id"] == g0["fig"]["picture"]), None)
    if pic:
        vx0, vy0, vx1, vy1 = [int(round(v * f)) for v in pic["visible"]]
        vis = Image.fromarray(cut.astype(np.uint8), "RGBA").crop((vx0, vy0, vx1, vy1))
        r = pic["rect"]
        plate.alpha_composite(vis.resize((round(r[2]), round(r[3])), Image.LANCZOS), (round(r[0]), round(r[1])))
    else:   # figure painted into the slide: fill the hole from the surrounding background
        hole = ndi.binary_dilation(fm_all > 0.05, iterations=int(6 * f))
        rgb = src[..., :3]
        _, (iy, ix) = ndi.distance_transform_edt(hole, return_indices=True)
        filled = rgb[iy, ix]
        soft = ndi.gaussian_filter(filled, (6 * f, 6 * f, 0))
        rgb2 = np.where(hole[..., None], soft, rgb)
        im = Image.fromarray(np.dstack([rgb2, np.full(hole.shape, 255.0)]).astype(np.uint8), "RGBA")
        plate = im.resize((sw, sh), Image.LANCZOS)
    # masks on the slide (for outlines)
    for n in members:
        m_img = Image.fromarray((masks[n] * 255).astype(np.uint8), "L")
        W0, H0 = m_img.size
        sm = m_img.resize((round(W0 * t["ax"]), round(H0 * t["ay"])), Image.LANCZOS)
        canvas_m = Image.new("L", (sw, sh), 0)
        canvas_m.paste(sm, (round(t["ox"]), round(t["oy"])))
        masks[n] = np.asarray(canvas_m).astype(np.float32) / 255
    return plate


def slide_states(C, G, names, plate, masks):
    """One slide picture per state of stage.json (bit i = figure i is out): dashed outline in its accent colour."""
    sw, sh = C.slide_px
    base = np.asarray(plate.convert("RGB")).astype(np.float32)
    k = 0
    stage = json.loads((C.dir / "stage.json").read_text(encoding="utf-8"))
    order = list(stage["slide"]["states"])
    dashes = {}
    for st in order:
        mask_bits = int(Path(st).stem.split("_")[1], 16)
        img = base.copy()
        for i, n in enumerate(names):
            if mask_bits >> i & 1:
                if n not in dashes:
                    dashes[n] = dashed_outline(masks[n], (sw, sh), dash=round(34 * sw / 3840), gap=round(22 * sw / 3840),
                                               width=max(2, round(9 * sw / 3840)))
                col = np.array(accent_color(G[n]), np.float32)
                al = np.clip(dashes[n], 0, 1)[..., None] * 0.8
                img = img * (1 - al) + col * al
        Image.fromarray(img.astype(np.uint8)).save(C.dir / st)
        k += 1
    return k


def tag_card(f, g, path):
    """Name tag card: title in the figure's accent colour, optional second line."""
    W, H = 900, 380
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(card)
    dr.rounded_rectangle((10, 10, W - 10, H - 10), radius=36, fill=(250, 249, 244, 255), outline=(30, 30, 32, 255),
                         width=9)
    title, sub = (f["tag"] + [""])[:2]
    dr.text((W / 2, 140 if sub else H / 2), title, font=font(True, 150), fill=accent_color(g) + (255,),
            anchor="mm")
    if sub:
        dr.text((W / 2, 280), sub, font=font(False, 92), fill=(40, 40, 44, 255), anchor="mm")
    card.save(path)


def textures(C):
    tex = C.dir / "tex"
    tex.mkdir(exist_ok=True)
    deck_dir = C.deck_file.parent
    names = [f["name"] for f in C.p["figures"]]
    G = {n: fig_geometry(C, n) for n in names}
    sw, sh = C.slide_px
    by_source = {}
    for n in names:
        by_source.setdefault(G[n]["fig"]["source"], []).append(n)
    plate_name = C.slide.get("plate")
    plate = Image.open(deck_dir / (plate_name or C.slide["clean"])).convert("RGBA").resize((sw, sh), Image.LANCZOS)
    masks = {}
    for members in by_source.values():
        plate = remove_figures(C, G, members, plate, masks)
    k = slide_states(C, G, names, plate, masks)
    room_textures(tex)
    for f in C.p["figures"]:
        if f.get("tag"):
            tag_card(f, G[f["name"]], tex / f"tag_{f['name']}.png")
    print(f"  textures: {k} slide states, room, tags")
