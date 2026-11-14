"""Cut a figure (figures/<name>/original.png) into movable parts – every pixel comes from the original drawing.

  parts.py figures/<name> [--auto]       --auto (or no parts.json yet): writes a first guess parts.json
                                          (head above the neck, the two pupils, body) and cuts with it
Then look at figures/<name>/parts_check.png (parts in colours, guide polygons, pivots) and refine parts.json:
  {"parts": ["tail", "body", "head", "arm_r", "eyes"],       back -> front; "body" = everything not in a polygon
   "poly": {"head": [[x, y], ...], "arm_r": [...], "tail": [...]},   rough polygons in original.png pixels
   "pivots": {"head": [x, y], "arm_r": [x, y], "tail": [x, y]},      joints (cut only where the drawing has a line)
   "eyes": [[x, y], [x, y]], "eye_win": 40, "eye_blob": 0,           pupils (eye_blob > 0: pupils touch glasses;
                                                                         use more than half the rim width, e.g. 12)
   "ext": [["body", ["head", "eyes"], 80], ["tail", ["body"], 110]], hidden pieces under joints, reach in px
   "scale": 1.0,                                                       line widths/seams relative to a 1800-px figure
   "split_fill": false}     true: a fill area that runs into a polygon is split along it (limb fill joined to the body)
Method (learned on the ai_efficiency deck): ink (dark, unsaturated) vs. fill; each fill region goes to the polygon
it mostly lies in; shared ink lines go to the FRONT part; the soft edge to the nearest part; hidden pieces under
joints are grown as white fill with an ink contour (only deeper than 10 px under the occluder, so they never show
in the rest pose); every back part runs 6 px under the front parts (no see-through seam when lit).
Outputs: <part>.png (full crop size, RGBA), rig.json (pivots, feet, foot blobs, centre, Synfig view), parts_check.png,
and the fidelity check: the parts stacked in the rest pose vs. original.png.
Usage: uv run --no-project --with pillow --with numpy --with scipy python parts.py figures/fritz [--auto]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

SU_PX = 200.0                     # Synfig unit = 200 px of the (x4) crop; keeps rigs of all sizes alike


def poly_mask(shape, pts):
    im = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(im).polygon([tuple(p) for p in pts], fill=1)
    return np.asarray(im).astype(bool)


def classify(img):
    rgb = img[..., :3]
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    chroma = rgb.max(-1) - rgb.min(-1)
    core = img[..., 3] > 0.5
    ink = core & (lum < 0.55) & (chroma < 0.12)
    return core, ink, lum


def auto_config(img):
    """First guess: head above the narrowest row of the upper body, pupils = the two biggest compact ink blobs."""
    core, ink, _ = classify(img)
    H, W = core.shape
    ys, xs = np.nonzero(core)
    top, sole = int(ys.min()), int(ys.max())
    h = sole - top
    width = ndi.uniform_filter1d(core.sum(1).astype(np.float32), max(3, h // 40))
    lo, hi = top + int(0.22 * h), top + int(0.6 * h)
    neck = lo + int(np.argmin(width[lo:hi]))
    s = round(h / 1800, 3)
    lab, n = ndi.label(ink)
    eyes = []
    upper = top + int(0.6 * h)
    ref_area = core[top:upper].sum()
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        if sl is None or sl[0].stop > upper:
            continue
        m = lab[sl] == i
        area = m.sum()
        bh, bw = m.shape
        if not (0.0003 * ref_area < area < 0.06 * ref_area) or area < 0.45 * bh * bw or max(bh, bw) > 3 * min(bh, bw):
            continue
        cy, cx = ndi.center_of_mass(m)
        eyes.append((int(area), int(cx + sl[1].start), int(cy + sl[0].start), int(sl[0].stop)))
    eyes.sort(reverse=True)
    pair = []
    for k, e in enumerate(eyes[:6]):
        for e2 in eyes[k + 1:6]:
            if abs(e[2] - e2[2]) < 0.08 * h and abs(e[1] - e2[1]) > 0.05 * W:
                pair = [[e[1], e[2]], [e2[1], e2[2]]]
                neck = max(neck, max(e[3], e2[3]) + int(0.08 * h))      # a head without a neck (mug, ball)
                break
        if pair:
            break
    cols = np.nonzero(core[neck])[0]
    nx = int(cols.mean()) if len(cols) else W // 2
    head = [[0, 0], [W, 0], [W, neck], [0, neck]]
    cfg = {"parts": ["body", "head"] + (["eyes"] if pair else []), "poly": {"head": head},
           "pivots": {"head": [nx, neck]}, "eyes": sorted(pair), "eye_win": int(40 * s) or 4, "eye_blob": 0,
           "ext": [["body", ["head"] + (["eyes"] if pair else []), int(80 * s)]], "scale": s, "auto": True}
    return cfg


def cut(fig_dir, cfg):
    img = np.asarray(Image.open(fig_dir / "original.png").convert("RGBA")).astype(np.float32) / 255
    H, W = img.shape[:2]
    PARTS = cfg["parts"]
    s = cfg.get("scale", 1.0)
    a = img[..., 3]
    core, ink, lum = classify(img)
    fill = core & ~ink
    has_eyes = "eyes" in PARTS and cfg.get("eyes")

    eyes = np.zeros_like(core)
    if has_eyes:
        ink_lab, _ = ndi.label(ink)
        w = cfg.get("eye_win", 40)
        er = cfg.get("eye_blob", 0)
        if er:          # pupils touch glasses/outline: shrink thin lines away, filled blobs stay
            blob_lab, _ = ndi.label(ndi.binary_erosion(ndi.binary_fill_holes(ink) & ink | ink, iterations=er))
        for (ex, ey) in cfg["eyes"]:
            L = blob_lab if er else ink_lab
            win = L[max(0, ey - w):ey + w, max(0, ex - w):ex + w]
            vals, cnt = np.unique(win[win > 0], return_counts=True)
            if not len(vals):
                continue
            blob = L == vals[cnt.argmax()]
            eyes |= (ndi.binary_dilation(blob, iterations=er + 1) & ink) if er else blob
        eyes = ndi.binary_fill_holes(eyes)
        eyes = ndi.binary_dilation(eyes, iterations=2) & core
        if eyes.sum() > 0.03 * core.sum():   # the pupil blob ran into the outline (eye_blob smaller than the rim line)
            raise SystemExit(f"pupils cover {eyes.sum() / core.sum():.0%} of the figure: the pupil search ran into the "
                             f"ink outline - raise eye_blob above half the glasses' line width (Helmut x4: 12) and "
                             f"make eye_win smaller so the window sits on the pupil")

    rough = np.full((H, W), PARTS.index("body"), np.int16)
    for pname, pts in cfg["poly"].items():
        if pname in PARTS:
            rough[poly_mask((H, W), pts)] = PARTS.index(pname)
    label = np.full((H, W), -1, np.int16)
    fl_lab, n = ndi.label(fill)
    for i, sl in enumerate(ndi.find_objects(fl_lab), 1):
        if sl is None:
            continue
        m = fl_lab[sl] == i
        r = rough[sl][m]
        vals, cnt = np.unique(r, return_counts=True)
        sub = label[sl]
        sub[m] = vals[cnt.argmax()] if cnt.max() >= 0.85 * cnt.sum() and not cfg.get("split_fill") else r
    R = max(2, int(24 * s))                                           # ink -> front-most part within line reach
    best = np.full((H, W), -1, np.int16)
    for k in range(len(PARTS)):
        near_k = ndi.binary_dilation(label == k, iterations=R)
        best = np.where(near_k & ink, np.maximum(best, k), best)
    label = np.where(ink, np.where(best >= 0, best, rough), label)
    if has_eyes:
        label[eyes] = PARTS.index("eyes")
    _, (iy, ix) = ndi.distance_transform_edt(~(label >= 0), return_indices=True)
    label = label[iy, ix]

    white = np.array([1, 1, 1], np.float32)
    ink_rgb = np.array([0.07, 0.07, 0.08], np.float32)
    sil = core | ink
    mask = {p: (label == k) & sil for k, p in enumerate(PARTS)}

    def continuation(part_m, occluder_m, d):
        occ_depth = ndi.distance_transform_edt(occluder_m)
        ext = (ndi.distance_transform_edt(~part_m) <= d) & occluder_m & ~part_m
        dist_out = ndi.distance_transform_edt(part_m | ext)
        ink_amt = np.clip(17.0 * s - dist_out, 0, 1) * ext * np.clip((occ_depth - 10 * s) / (4 * s), 0, 1)
        return ext, ink_amt

    exts = {}
    for part, occs, d in cfg.get("ext", []):
        if part not in mask:
            continue
        occ = np.zeros_like(core)
        for o in occs:
            if o in mask:
                occ |= mask[o]
        exts.setdefault(part, []).append(continuation(mask[part], occ, d))
    holes = {"head": ndi.binary_dilation(label == PARTS.index("eyes"), iterations=3)} if has_eyes else {}

    colors = [(0.9, 0.6, 0.2), (0.6, 0.6, 0.6), (0.3, 0.6, 0.95), (0.4, 0.85, 0.4), (0.9, 0.2, 0.6),
              (0.6, 0.3, 0.9), (0.2, 0.8, 0.8), (0.95, 0.85, 0.2)]
    check = np.zeros((H, W, 3), np.float32)
    stack = np.zeros((H, W, 4), np.float32)
    seam_px = max(1, int(round(6 * s)))
    for k, pname in enumerate(PARTS):
        m = label == k
        part = np.zeros((H, W, 4), np.float32)
        part[m] = img[m]
        for ext, ink_amt in exts.get(pname, []):
            f = ext & ~m
            part[f, :3] = white * (1 - ink_amt[f, None]) + ink_rgb * ink_amt[f, None]
            part[f, 3] = 1
        if pname in holes:
            f = holes[pname] & ~m
            part[f, :3] = white
            part[f, 3] = 1
        front = np.isin(label, list(range(k + 1, len(PARTS)))) & sil
        own = m & (a > 0.5)
        if own.any() and front.any():
            dist, (jy, jx) = ndi.distance_transform_edt(~own, return_indices=True)
            seam = (dist <= seam_px) & front & ~m
            part[seam, :3] = img[jy[seam], jx[seam], :3]
            part[seam, 3] = 1
        Image.fromarray((part * 255 + 0.5).astype(np.uint8), "RGBA").save(fig_dir / f"{pname}.png")
        al = part[..., 3:]
        stack[..., :3] = part[..., :3] * al + stack[..., :3] * (1 - al)
        stack[..., 3:] = al + stack[..., 3:] * (1 - al)
        check[m & (a > 0.3)] = colors[k % len(colors)]

    # fidelity: rest pose (parts stacked) vs. original, both over white
    o = img[..., :3] * img[..., 3:] + (1 - img[..., 3:])
    r = stack[..., :3] * stack[..., 3:] + (1 - stack[..., 3:])
    d = np.abs(o - r).max(-1) * 255
    fid = {"mean_abs_in_silhouette": round(float(d[sil].mean()), 3), "pixels_off_by_25": int((d > 25).sum()),
           "silhouette_pixels": int(sil.sum())}

    # check image: parts in colour, guide polygons, pivots
    shade = np.clip(lum, 0.25, 1)[..., None]
    ci = Image.fromarray((check * shade * 255).astype(np.uint8))
    dr = ImageDraw.Draw(ci)
    for pname, pts in cfg["poly"].items():
        dr.line([tuple(p) for p in pts] + [tuple(pts[0])], fill=(255, 40, 40), width=max(2, int(4 * s)))
    piv = dict(cfg.get("pivots", {}))
    for pname, (x, y) in piv.items():
        rr = max(6, int(14 * s))
        dr.ellipse((x - rr, y - rr, x + rr, y + rr), outline=(255, 255, 0), width=max(2, int(4 * s)))
    for ex, ey in cfg.get("eyes", []):
        dr.rectangle((ex - 6, ey - 6, ex + 6, ey + 6), outline=(0, 255, 255), width=2)
    ci.resize((W // 2, H // 2)).save(fig_dir / "parts_check.png")
    return label, sil, fid


def measure(fig_dir, cfg):
    """Feet (sole point), foot blobs for contact shadows, centre, square Synfig view for a full turn."""
    parts = cfg["parts"]
    a = None
    for p in parts:
        al = np.asarray(Image.open(fig_dir / f"{p}.png"))[..., 3] / 255.0
        a = al if a is None else np.maximum(a, al)
    core = a > 0.5
    H, W = core.shape
    ys, xs = np.nonzero(core)
    sole = int(ys.max())
    band_h = max(10, int(90 * cfg.get("scale", 1.0)))
    band = core[sole - band_h:sole + 1].any(0)
    runs, x = [], 0
    while x < W:
        if band[x]:
            x0 = x
            while x < W and band[x]:
                x += 1
            if x - x0 > 0.03 * W:
                bottom = int(np.nonzero(core[:, x0:x].any(1))[0].max())
                runs.append({"x": (x0 + x) / 2, "w": x - x0, "sole": bottom})
        x += 1
    runs.sort(key=lambda r: -r["w"])
    blobs = sorted(runs[:2], key=lambda r: r["x"]) or [{"x": xs.mean(), "w": xs.ptp(), "sole": sole}]
    front = max(blobs, key=lambda r: r["sole"])                  # lowest foot = front foot
    feet = (sum(b["x"] for b in blobs) / len(blobs), front["sole"])
    for b in blobs:                                              # a foot drawn higher stands further back
        b["dz_px"] = front["sole"] - b["sole"]
    com = ((xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2)
    r = float(np.sqrt(((xs - com[0]) ** 2 + (ys - com[1]) ** 2).max())) * 1.18 / SU_PX
    cx, cy = (com[0] - feet[0]) / SU_PX, (feet[1] - com[1]) / SU_PX
    return {"size": [W, H], "parts": parts, "pivots": {k: list(v) for k, v in cfg.get("pivots", {}).items()},
            "feet": [float(feet[0]), float(feet[1])], "blobs": blobs, "com": [float(com[0]), float(com[1])],
            "view": [cx - r, cy + r, cx + r, cy - r], "su_px": SU_PX, "top": int(ys.min())}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("figure")
    ap.add_argument("--auto", action="store_true", help="(re)write parts.json with an automatic first guess")
    a = ap.parse_args()
    d = Path(a.figure).resolve()
    cp = d / "parts.json"
    if a.auto or not cp.exists():
        img = np.asarray(Image.open(d / "original.png").convert("RGBA")).astype(np.float32) / 255
        cfg = auto_config(img)
        cp.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
        print(f"  first guess -> {cp} (check parts_check.png, then refine polygons/pivots)")
    cfg = json.loads(cp.read_text(encoding="utf-8"))
    label, sil, fid = cut(d, cfg)
    rig = measure(d, cfg)
    rig["fidelity"] = fid
    (d / "rig.json").write_text(json.dumps(rig, indent=1), encoding="utf-8")
    counts = {p: int(((label == k) & sil).sum()) for k, p in enumerate(cfg["parts"])}
    print(f"  {d.name}: parts {counts}")
    print(f"  rest pose vs original: mean {fid['mean_abs_in_silhouette']}/255 in the silhouette, "
          f"{fid['pixels_off_by_25']} of {fid['silhouette_pixels']} px off by > 25")


if __name__ == "__main__":
    sys.exit(main())
