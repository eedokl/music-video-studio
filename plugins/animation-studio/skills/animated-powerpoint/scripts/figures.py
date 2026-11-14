# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0", "scipy==1.18.1"]
# ///
"""Find the characters on a slide and cut each one out exactly as drawn (no redrawing).

  figures.py --deck deck/deck.json --slide 5 [--picture 18] [--names helmut hans fritz felix] [--upscale 4]
             [--min-area 0.01] [--out figures]

Source: the picture with transparency on that slide (largest first), or --picture <id>; a picture without alpha
is cut from its background colour; a slide without pictures (page images) is cut from the clean slide.
Every connected blob larger than --min-area of the source is a figure (sorted left to right, named by --names
or fig1, fig2 ...). Soft edge pixels go to the nearer figure, so neighbours never leak into each other.
--upscale N: the whole source is enlarged once (Real-ESRGAN anime model when the config key "realesrgan" points to
realesrgan-ncnn-vulkan, colour on white and alpha separately – ncnn has no alpha; otherwise Lanczos), so parts
stay crisp when the camera comes close.

Output figures/<name>/original.png (RGBA crop) + figure.json:
  {"source": ..., "upscale": 4, "crop": [x0, y0, x1, y1] in the enlarged source, "inside": [x, y] (a core pixel),
   "to_slide": {"ax", "ay", "ox", "oy"}  slide px = o + a * enlarged-source px,  "slide": n, "slide_size": [w, h]}
and figures/contact_figures.png (all figures with their names) to check the split.
Usage: uv run figures.py ...
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

import _studio
_studio.use()
import config  # noqa: E402


def esrgan(rgba, factor):
    """Real-ESRGAN x4 (anime model for colour, general model for alpha). Uses the shared upscaler of the ai-video
    building block when it is there; the local copy below stays as the fallback."""
    try:
        _studio.use("ai-video")
        import upscale
        if upscale.exe():
            return upscale.upscale_rgba(rgba, factor, model="anime")
    except (SystemExit, ImportError):
        pass
    exe = config.get("realesrgan")
    if not exe or not Path(exe).exists():
        return None
    from gpu_lock import acquire
    acquire("animated-powerpoint upscale", model="ncnn:realesrgan")
    tmp = Path(tempfile.mkdtemp(prefix="upscale_"))
    a = rgba.astype(np.float32) / 255
    rgb = a[..., :3] * a[..., 3:] + (1 - a[..., 3:])                       # on white
    Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).save(tmp / "rgb.png")
    al = (a[..., 3] * 255 + 0.5).astype(np.uint8)
    Image.fromarray(np.stack([al] * 3, -1)).save(tmp / "alpha.png")
    for src, dst, model in (("rgb.png", "rgb_x.png", "realesrgan-x4plus-anime"),   # anime model: clean ink lines
                            ("alpha.png", "alpha_x.png", "realesrgan-x4plus")):     # general model: soft alpha edges
        r = subprocess.run([exe, "-i", str(tmp / src), "-o", str(tmp / dst), "-n", model, "-s", "4", "-g", "0"],
                           capture_output=True, text=True, cwd=str(Path(exe).parent))
        if r.returncode or not (tmp / dst).exists():
            print("  Real-ESRGAN failed, using Lanczos:", r.stderr[-300:])
            return None
    rgb4 = np.asarray(Image.open(tmp / "rgb_x.png").convert("RGB"))
    al4 = np.asarray(Image.open(tmp / "alpha_x.png").convert("L"))
    out = np.dstack([rgb4, al4])
    if factor != 4:
        h, w = rgba.shape[:2]
        out = np.asarray(Image.fromarray(out, "RGBA").resize((w * factor, h * factor), Image.LANCZOS))
    return out


def enlarge(rgba, factor):
    if factor <= 1:
        return rgba, "none"
    out = esrgan(rgba, factor)
    if out is not None:
        return out, "realesrgan"
    h, w = rgba.shape[:2]
    return np.asarray(Image.fromarray(rgba, "RGBA").resize((w * factor, h * factor), Image.LANCZOS)), "lanczos"


def silhouette(rgba):
    """Core mask: alpha where the source has transparency, else everything that differs from the border colour."""
    a = rgba[..., 3]
    if a.min() < 250:
        return a > 128
    rgb = rgba[..., :3].astype(np.int16)
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bg = np.median(border, axis=0)
    m = np.abs(rgb - bg).max(-1) > 40
    m = ndi.binary_closing(m, iterations=3)
    return ndi.binary_fill_holes(m)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deck", default="deck/deck.json")
    ap.add_argument("--slide", type=int, required=True)
    ap.add_argument("--picture", type=int, help="picture id from deck.json (default: largest with alpha)")
    ap.add_argument("--names", nargs="*")
    ap.add_argument("--upscale", type=int, default=4)
    ap.add_argument("--min-area", type=float, default=0.01, help="fraction of the source area")
    ap.add_argument("--out", default="figures")
    a = ap.parse_args()
    dp = Path(a.deck).resolve()
    deck = json.loads(dp.read_text(encoding="utf-8"))
    S = next(s for s in deck["slides"] if s["n"] == a.slide)
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    pics = S["pictures"]
    if a.picture is not None:
        pic = next(p for p in pics if p["id"] == a.picture)
    else:
        cand = sorted(pics, key=lambda p: (-p["alpha"], -p["rect"][2] * p["rect"][3]))
        pic = cand[0] if cand else None
    if pic:
        src = np.asarray(Image.open(dp.parent / pic["file"]).convert("RGBA")).copy()
        x0, y0, x1, y1 = pic["visible"]                      # PowerPoint crop: the hidden part is not on the slide
        vis = np.zeros(src.shape[:2], bool)
        vis[y0:y1, x0:x1] = True
        src[~vis, 3] = 0
        m = pic["map"]
        source_name = pic["file"]
    else:
        src = np.asarray(Image.open(dp.parent / S["clean"]).convert("RGBA")).copy()
        m = {"ax": 1.0, "ay": 1.0, "ox": 0.0, "oy": 0.0}
        source_name = S["clean"]
    big, how = enlarge(src, a.upscale)
    f = big.shape[0] / src.shape[0]
    src_name = f"source_s{a.slide:02d}_{pic['id'] if pic else 'slide'}.png"
    Image.fromarray(big, "RGBA").save(out / src_name)
    core = silhouette(big)
    if big[..., 3].min() >= 250:                             # opaque source: the cut-out gets alpha from the mask
        big = big.copy()
        big[..., 3] = (ndi.gaussian_filter(core.astype(np.float32), 1.0) * 255).astype(np.uint8)
    lab, n = ndi.label(ndi.binary_dilation(core, iterations=max(2, int(3 * f))))   # bridge 1-px gaps
    lab = lab * core
    areas = ndi.sum(core, lab, range(1, n + 1))
    keep = [i + 1 for i, ar in enumerate(areas) if ar >= a.min_area * core.size]
    if not keep:
        raise SystemExit("no figure found - lower --min-area or pick the picture with --picture")
    # small pieces close to a figure belong to it (a mug handle, steam, a hat that does not touch the head)
    gap = 0.04 * np.hypot(*core.shape)
    biggest = max(areas[i - 1] for i in keep)
    dist_big = {i: ndi.distance_transform_edt(lab != i) for i in keep if areas[i - 1] >= 0.25 * biggest}
    for i in range(1, n + 1):
        if i in dist_big or not areas[i - 1]:
            continue
        piece = lab == i
        near = min(dist_big, key=lambda j: dist_big[j][piece].min())
        if dist_big[near][piece].min() <= gap:
            lab[piece] = near
    keep = [i for i in keep if i in dist_big] or keep
    keep.sort(key=lambda i: np.nonzero(lab == i)[1].mean())
    names = (a.names or []) + [f"fig{i + 1}" for i in range(len(keep))]
    # soft edge -> nearer figure
    dist = np.stack([ndi.distance_transform_edt(lab != i) for i in keep])
    owner = np.argmin(dist, axis=0)
    sheet = []
    for k, i in enumerate(keep):
        name = names[k]
        mine = lab == i
        near = ndi.binary_dilation(mine, iterations=int(12 * f)) & (owner == k)
        ys, xs = np.nonzero(near)
        pad = int(4 * f)
        cx0, cy0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
        cx1, cy1 = min(big.shape[1], xs.max() + pad + 1), min(big.shape[0], ys.max() + pad + 1)
        crop = big[cy0:cy1, cx0:cx1].copy()
        crop[..., 3] = np.where(near[cy0:cy1, cx0:cx1], crop[..., 3], 0)
        d = out / name
        d.mkdir(exist_ok=True)
        Image.fromarray(crop, "RGBA").save(d / "original.png")
        iy, ix = ndi.center_of_mass(mine[cy0:cy1, cx0:cx1])
        if not mine[int(iy) + cy0, int(ix) + cx0]:
            yy, xx = np.nonzero(mine[cy0:cy1, cx0:cx1])
            j = np.argmin((yy - iy) ** 2 + (xx - ix) ** 2)
            iy, ix = yy[j], xx[j]
        fig = {"name": name, "slide": a.slide, "deck": str(Path(dp).relative_to(out.parent)).replace("\\", "/")
               if out.parent in dp.parents else str(dp), "source": f"{out.name}/{src_name}",
               "picture": pic["id"] if pic else None, "upscale": round(f, 4), "upscaler": how,
               "crop": [int(cx0), int(cy0), int(cx1), int(cy1)], "inside": [int(ix), int(iy)],
               "to_slide": {"ax": m["ax"] / f, "ay": m["ay"] / f, "ox": m["ox"], "oy": m["oy"]},
               "slide_size": [deck.get("width"), deck.get("height")], "source_file": source_name}
        (d / "figure.json").write_text(json.dumps(fig, indent=1), encoding="utf-8")
        sheet.append((name, Image.fromarray(crop, "RGBA")))
        print(f"  {name}: crop {fig['crop']} ({cx1 - cx0}x{cy1 - cy0} px)")
    th = 420
    tiles = [im.resize((max(1, round(im.width * th / im.height)), th)) for _, im in sheet]
    W = sum(t.width for t in tiles) + 20 * (len(tiles) + 1)
    c = Image.new("RGB", (W, th + 60), (235, 235, 235))
    dr = ImageDraw.Draw(c)
    x = 20
    for (name, _), t in zip(sheet, tiles):
        c.paste(t, (x, 10), t)
        dr.text((x, th + 20), name, fill=(0, 0, 0))
        x += t.width + 20
    c.save(out / "contact_figures.png")
    print(f"-> {len(keep)} figures in {out} (upscale {how} x{f:g})")


if __name__ == "__main__":
    sys.exit(main())
