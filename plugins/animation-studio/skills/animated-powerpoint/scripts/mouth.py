# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0", "scipy==1.18.1"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Lip sync for raster slide figures: mouth stages cut from the original drawing + Rhubarb -> stage keys per frame.

  mouth.py figures/<name>                 cut head_base.png + mouth_0..7.png from head.png (config "mouth" in parts.json)
  mouth.py figures/<name> --clean         also remove small white soft-edge flecks outside the ink outline from every
                                          part (originals kept as <part>_orig.png) - they show on grey/colour sets
parts.json "mouth" (coordinates in original.png pixels, like the polygons):
  {"kind": "open",  "upper": [[x, y], ...], "lower": [[x, y], ...]}
        an open grin: the mouth below the upper lip is squashed COLUMN BY COLUMN under the lip line (squashing the
        whole mouth would tear the curved upper edge from the lip); rest = 1.0 (the original grin)
  {"kind": "line",  "x": [x0, x1], "band": [y0, y1], "depth": 100}   depth optional, default half of x1 - x0
        a closed smile line: a dark mouth opens under the topmost ink line, only inside the head, closing 24 px before
        the corner (no hook into the chin line); from 0.55 with a light tongue; rest = 0 (closed)
  {"kind": "beak",  "poly": [[x, y], ...], "hinge_x": 402, "tip_x": 320, "lift": 62}
        a beak: the lower beak hinges down, most at the tip, a dark gap behind it; rest = 0
Stages: 0, .1, .25, .4, .55, .7, .85, 1.0 (mouth_0 .. mouth_7). Check image: mouth_check.png (stages 0/1/3/5/7).
Rig: clip.py puts head_base + the 8 stages into the head group (one visible per frame) when the figure speaks
(a narration line with "speaker": <name>, or figure "talk": [line ids]). talking-character can use the same
files for raster figures: mouth_keys() turns Rhubarb cues into stage keys.
Usage: uv run mouth.py figures/fritz
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

STAGES = [0.0, 0.1, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0]
INK = np.array([0.07, 0.07, 0.08], np.float32)
SHAPE_TO_STAGE = {     # Rhubarb shape -> stage (A closed lips ... D wide open, X rest)
    "open": {"A": 1, "B": 3, "C": 5, "D": 7, "E": 6, "F": 2, "G": 2, "H": 4, "X": 2},
    "line": {"A": 0, "B": 3, "C": 4, "D": 7, "E": 5, "F": 2, "G": 1, "H": 4, "X": 0},
    "beak": {"A": 0, "B": 3, "C": 4, "D": 7, "E": 5, "F": 2, "G": 1, "H": 4, "X": 0}}


def poly_mask(shape, pts):
    im = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(im).polygon([tuple(p) for p in pts], fill=1)
    return np.asarray(im).astype(bool)


def top_curve(pts, W):
    xs, ys = np.array([p[0] for p in pts], float), np.array([p[1] for p in pts], float)
    o = np.argsort(xs)
    xs, ys = xs[o], ys[o]
    out = np.full(W, np.nan)
    cols = np.arange(W)
    inside = (cols >= xs.min()) & (cols <= xs.max())
    out[inside] = np.interp(cols[inside], xs, ys)
    return out


def column_squash(part, top, s):
    H, W = part.shape[:2]
    pm = part.copy()
    pm[..., :3] *= pm[..., 3:4]
    yy, xx = np.mgrid[:H, :W].astype(np.float32)
    t = np.nan_to_num(top, nan=H + 10)[None, :].astype(np.float32)
    src_y = np.where(yy >= t, t + (yy - t) / max(s, 1e-3), yy)
    out = np.stack([ndi.map_coordinates(pm[..., c], [src_y, xx], order=1, mode="constant") for c in range(4)], -1)
    a = out[..., 3:4]
    out[..., :3] = np.where(a > 1e-4, out[..., :3] / np.maximum(a, 1e-4), 0)
    return np.clip(out, 0, 1)


def clean_edges(img, max_px=6000):
    """Remove small light flecks that touch the transparent outside (the white soft edge of the original)."""
    out = img.copy()
    lum = img[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    light = (img[..., 3] > 0.03) & (lum > 0.45)
    empty = ndi.binary_dilation(img[..., 3] <= 0.03, iterations=2)
    lab, n = ndi.label(light)
    if n == 0:
        return out, 0
    size = ndi.sum(np.ones_like(lum), lab, np.arange(1, n + 1))
    at_edge = ndi.maximum(empty, lab, np.arange(1, n + 1))
    drop = np.zeros(n + 1, bool)
    drop[1:] = (size < max_px) & at_edge.astype(bool)
    m = ndi.binary_dilation(drop[lab], iterations=2) & ~((lum < 0.45) & (img[..., 3] > 0.5))
    out[m, 3] = 0
    return out, int(m.sum())


def cut_open(cfg, head):
    H, W = head.shape[:2]
    m = poly_mask((H, W), cfg["upper"] + cfg["lower"]) & (head[..., 3] > 0.5)    # soft edge stays in the head
    part = np.zeros_like(head)
    part[m] = head[m]
    base = head.copy()
    base[m, :3] = 1.0
    base[m, 3] = 1.0
    top = top_curve(cfg["upper"], W)
    return base, [column_squash(part, top, max(s, 0.1)) if s < 0.999 else part for s in STAGES], 7


def cut_line(cfg, head, s_px):
    H, W = head.shape[:2]
    lum = head[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    ink = (head[..., 3] > 0.5) & (lum < 0.45)
    xa, xb = cfg["x"]
    y0, y1 = cfg["band"]
    depth0 = cfg.get("depth") or round(0.5 * (xb - xa))     # default: half the mouth width (a fixed 72 px gave a
    #                                                      wide mouth only a slit when open - user test)
    top = np.full(W, np.nan)
    for x in range(xa, xb + 1):
        ys = np.nonzero(ink[y0:y1, x])[0]
        if len(ys):                 # only the TOPMOST stroke (near the corner the chin line lies below)
            run = ys[: np.argmax(np.diff(np.r_[ys, 10 ** 6]) > 2) + 1] if x > (xa + xb) / 2 else ys
            top[x] = y0 + run.mean()
    ok = ~np.isnan(top)
    top = np.interp(np.arange(W), np.nonzero(ok)[0], top[ok])
    top = ndi.gaussian_filter1d(top, 6)
    yy, xx = np.mgrid[:H, :W].astype(np.float32)
    edge = ndi.distance_transform_edt(ndi.binary_fill_holes(ndi.binary_closing(head[..., 3] > 0.5, iterations=6)))
    inside_x = np.clip((edge - 20 * s_px) / (6 * s_px), 0, 1) * ((xx >= xa) & (xx <= xb))
    free = np.full(W, 1e3)
    for x in range(xa, xb + 1):
        y0x = int(top[x]) + 12
        ys = np.nonzero(ink[y0x:y0x + 200, x])[0]
        if len(ys):
            free[x] = max(0.0, ys[0] + 12 - 16)
    free = ndi.gaussian_filter1d(ndi.minimum_filter1d(free, 61), 25)
    imgs = []
    for s in STAGES:
        img = np.zeros((H, W, 4), np.float32)
        if s > 0:
            u = np.clip((xx - (xa + 40)) / (xb - xa - 64), 0, 1)
            depth = depth0 * s * np.clip(np.sin(np.pi * u), 0, 1) ** 0.9 * (1 - 0.6 * u) ** 1.3
            depth = np.minimum(depth, free[None, :] + 0 * depth)
            tt = top[None, :] + 0 * yy
            a = np.clip(tt + depth + 0.5 - yy, 0, 1) * np.clip(yy - (tt - 3) + 0.5, 0, 1) * inside_x
            img[..., :3] = INK
            img[..., 3] = a
            if s >= 0.55:
                cx, cy = (xa + xb) / 2, top[int((xa + xb) / 2)] + depth0 * s * 0.82
                rx, ry = (xb - xa) * 0.2, depth0 * s * 0.34
                d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
                tongue = (d < 1) & (a > 0.5)
                img[tongue, :3] = 0.93
                img[tongue & (d > 1 - 7 / ry), :3] = INK
        imgs.append(img)
    base, _ = clean_edges(head)
    return base, imgs, 0


def cut_beak(cfg, head):
    H, W = head.shape[:2]
    m = poly_mask((H, W), cfg["poly"]) & (head[..., 3] > 0.5)
    part = np.zeros_like(head)
    part[m] = head[m]
    base = head.copy()
    base[m, :3] = 1.0
    gx, sx = cfg["hinge_x"], cfg["tip_x"]
    yy, xx = np.mgrid[:H, :W].astype(np.float32)
    w = np.clip((gx - xx) / (gx - sx), 0, 1)
    imgs = []
    for s in STAGES:
        shift = cfg.get("lift", 62) * s * w
        src_y = yy - shift
        moved = np.stack([ndi.map_coordinates(part[..., c] * (part[..., 3] if c < 3 else 1), [src_y, xx], order=1)
                          for c in range(4)], -1)
        a = moved[..., 3:4]
        moved[..., :3] = np.where(a > 1e-4, moved[..., :3] / np.maximum(a, 1e-4), 0)
        gap = np.zeros((H, W, 4), np.float32)
        if s > 0:
            reach = np.zeros((H, W), bool)
            for k in np.linspace(0, 1, 12):
                reach |= ndi.map_coordinates(m.astype(np.float32), [yy - shift * k, xx], order=0) > 0.5
            gap[reach, :3] = INK
            gap[reach, 3] = 1.0
        out = gap.copy()
        al = moved[..., 3:4]
        out[..., :3] = moved[..., :3] * al + out[..., :3] * (1 - al)
        out[..., 3] = np.maximum(out[..., 3], moved[..., 3])
        imgs.append(np.clip(out, 0, 1))
    return base, imgs, 0


def save(arr, path):
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(path)


def make(fig_dir, clean=False):
    d = Path(fig_dir)
    pj = json.loads((d / "parts.json").read_text(encoding="utf-8"))
    if clean:
        for p in pj["parts"]:
            src = d / f"{p}_orig.png" if (d / f"{p}_orig.png").exists() else d / f"{p}.png"
            img = np.asarray(Image.open(src).convert("RGBA")).astype(np.float32) / 255
            out, n = clean_edges(img)
            if not (d / f"{p}_orig.png").exists():
                Image.open(d / f"{p}.png").save(d / f"{p}_orig.png")
            save(out, d / f"{p}.png")
            print(f"  clean {p}: {n} px removed")
    cfg = pj.get("mouth")
    if not cfg:
        print("  no 'mouth' in parts.json - nothing to cut")
        return None
    head = np.asarray(Image.open(d / "head.png").convert("RGBA")).astype(np.float32) / 255
    kind = cfg["kind"]
    if kind == "open":
        base, imgs, rest = cut_open(cfg, head)
    elif kind == "line":
        base, imgs, rest = cut_line(cfg, head, pj.get("scale", 1.0))
    elif kind == "beak":
        base, imgs, rest = cut_beak(cfg, head)
    else:
        raise SystemExit(f"unknown mouth kind '{kind}' (open | line | beak)")
    save(base, d / "head_base.png")
    for i, im in enumerate(imgs):
        save(im, d / f"mouth_{i}.png")
    meta = {"kind": kind, "stages": STAGES, "rest": rest}
    (d / "mouth.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    # rest pose must equal the head (fidelity), check sheet
    st = np.zeros_like(head)
    for layer in (base, imgs[rest]):
        a = layer[..., 3:]
        st[..., :3] = layer[..., :3] * a + st[..., :3] * (1 - a)
        st[..., 3:] = a + st[..., 3:] * (1 - a)
    o = head[..., :3] * head[..., 3:] + (1 - head[..., 3:])
    r = st[..., :3] * st[..., 3:] + (1 - st[..., 3:])
    sil = head[..., 3] > 0.5
    meta["rest_vs_head"] = round(float((np.abs(o - r).max(-1) * 255)[sil].mean()), 3)
    (d / "mouth.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    ys, xs = np.nonzero(np.max([im[..., 3] for im in imgs], 0) > 0.1)
    box = (max(xs.min() - 60, 0), max(ys.min() - 80, 0), xs.max() + 60, ys.max() + 60)
    row = []
    for i in (0, 1, 3, 5, 7):
        c = Image.new("RGBA", (head.shape[1], head.shape[0]), (205, 205, 215, 255))
        c.alpha_composite(Image.open(d / "head_base.png"))
        c.alpha_composite(Image.open(d / f"mouth_{i}.png"))
        if (d / "eyes.png").exists():
            c.alpha_composite(Image.open(d / "eyes.png"))
        row.append(c.crop(box).convert("RGB"))
    th = 200
    row = [im.resize((int(im.size[0] * th / im.size[1]), th)) for im in row]
    sheet = Image.new("RGB", (sum(im.size[0] for im in row), th), "white")
    x = 0
    for im in row:
        sheet.paste(im, (x, 0))
        x += im.size[0]
    sheet.save(d / "mouth_check.png")
    print(f"  {d.name}: mouth '{kind}', rest {rest}, rest pose vs head {meta['rest_vs_head']}/255 -> mouth_check.png")
    return meta


def rhubarb_cues(wav, text=None, cache=None):
    import _studio
    _studio.use()
    import config
    wav = Path(wav)
    # -r phonetic: language-independent. Rhubarb's default recognizer is English-only and gives a German (or any
    # non-English) line an almost closed mouth (user test). Its dialog text (-d) only helps that English recognizer,
    # so `text` is not passed on. ".phonetic" in the cache name: results of the old English run are not reused.
    out = Path(cache or wav.parent) / (wav.stem + ".mouth.phonetic.json")
    if not out.exists() or out.stat().st_mtime < wav.stat().st_mtime:
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [config.need("rhubarb"), "-r", "phonetic", "-f", "json", "--extendedShapes", "GHX", "-q",
               "-o", str(out), str(wav)]
        subprocess.run(cmd, check=True, capture_output=True)
    return json.loads(out.read_text(encoding="utf-8"))["mouthCues"]


def ensure(fig_dir):
    """Cut the mouth stages on first use; stop with a hint when the figure has no "mouth" block in parts.json
    (parts.py --auto never writes one) - instead of a FileNotFoundError on mouth.json later."""
    d = Path(fig_dir)
    if not (d / "mouth.json").exists():
        make(d)
    if not (d / "mouth.json").exists():
        raise SystemExit(f"figure '{d.name}' speaks but has no mouth stages: add a \"mouth\" block to "
                         f"{d / 'parts.json'} (kinds open | line | beak, see mouth.py), or drop its \"speaker\"/\"talk\"")


def mouth_keys(fig_dir, lines, fps=24, lead=1, cache=None):
    """lines: [(wav, start_frame, text or None)] -> [(frame, stage)] (the mouth one frame early reads in sync).
    Rest = the original drawing; X inside a line = slightly open for open grins; long pauses go back to rest."""
    meta = json.loads((Path(fig_dir) / "mouth.json").read_text(encoding="utf-8"))
    table, rest = SHAPE_TO_STAGE[meta["kind"]], meta["rest"]
    keys = [(0, rest)]
    for wav, start, text in sorted(lines, key=lambda z: z[1]):
        cs = rhubarb_cues(wav, text, cache)
        for i, c in enumerate(cs):
            f0 = start + round(c["start"] * fps) - lead
            f1 = start + round(c["end"] * fps) - lead
            s = table[c["value"]]
            if c["value"] == "X" and (i == 0 or i == len(cs) - 1 or f1 - f0 > 10):
                s = rest
            keys.append((max(f0, 0), s))
        if cs:
            keys.append((start + round(cs[-1]["end"] * fps), rest))
    d = {}
    for f, s in keys:
        d[f] = s
    out, last = [], None
    for f in sorted(d):
        if d[f] != last:
            out.append((f, d[f]))
            last = d[f]
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("figure", help="figure folder, e.g. figures/robo")
    ap.add_argument("--clean", action="store_true", help="also remove white soft-edge flecks outside the outline")
    a = ap.parse_args()
    make(a.figure, clean=a.clean)
