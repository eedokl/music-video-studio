# /// script
# requires-python = "==3.12.*"
# dependencies = ["mediapipe==1.2.3", "numpy==2.5.4", "opencv-python-headless==5.0.0.93", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Repair start images whose headset microphone breaks the canon (a boom on BOTH cheeks, or on the wrong cheek only).

canon.py only detects the problem; this script fixes it and checks the result again with canon.py. Two methods, tried
in order (`--methods`), each result re-measured; the first one that passes (streak ok, ONE boom on the expected cheek,
none on the other) is kept:

  retouch  (boom on both cheeks)  the boom on the WRONG cheek is found (white top-hat, thin elongated components that
           reach the cheek between face outline and mouth corner, plus the bright capsule at its mouth end), filled
           with OpenCV Telea inpainting and - when ComfyUI answers - the filled patch is repainted with FLUX.1 schnell
           (masked img2img on a ~2x crop of 512-1024 px, denoise 0.8, 4 seeds, the one
           closest to the fill's coarse colours wins) so skin, hair and jacket get their texture back. Only the
           masked pixels change (feathered paste) - face, streak, clip and the correct mic stay pixel-identical.
           ~10 s (+ FLUX load ~2.5 min cold); CPU-only with --no-refine (Telea alone smears on large capsules).
  qwen     (any case, also "mic missing")  Qwen-Image-Edit 2511 with the source as the only reference and a "change
           only the microphone" prompt (the recipe of the Europe 2031 Live V5 repair), several seeds; a result that
           still has two booms but a correct streak is passed through `retouch` once more.
           ~30 s per seed (+ Qwen load ~9 min cold). Moves pixels slightly (whole image is re-generated).
Nothing passes -> the best attempt is kept as "<stem>_mic_best.png" with a warning: make new start-image variants.
Faces in profile / seen from behind are not measurable (canon.py finds no face) - those are skipped, check by eye.

  uv run mic_repair.py start.png [...] [--out-dir fixed/] [--side image_left] [--methods retouch,qwen]
      [--seeds 3] [--no-refine] [--edit-prompt "..."] [--edit-negative "..."] [--force]
  -> <out-dir>/<stem>_mic.png (passed) + <stem>_mic.json (canon before/after, method) + mic_repair_sheet.jpg
From Python: repair(path, out_dir, edit_prompt=..., edit_neg=...) -> dict (claudia-music-video pick.py --repair-mic).
GPU: FLUX / Qwen go through comfy.lock (shared GPU lock); the lock is released again right after the repair.
Config: face_landmarker (canon.py), comfy_url / comfy_start (comfy.py).
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use()
import canon  # noqa: E402
from cvio import imread, imwrite  # noqa: E402

COLOR = "#D97757"
# generic edit text; character skills pass their own identity-keeping prompt (e.g. claudia.MIC_EDIT)
EDIT = ("Keep image 1 exactly: same person, face, expression, hair, hair accents, outfit, pose, framing, light and "
        "colours. Change only the microphone: exactly one thin beige, skin-coloured headset microphone; its thin boom "
        "runs from the ear along the cheek on the {side} side of the image to the corner of the mouth. Remove every "
        "other microphone, boom or cable, especially any on the cheek on the {other} side of the image. Photographic, "
        "film grain.")
EDIT_NEG = ("second microphone, two microphones, black microphone, dark microphone, microphone boom on both sides, "
            "handheld microphone, microphone stand, changed face, changed hair, text, logo")
REFINE = ("photographic close-up of a woman's cheek and jaw line, natural skin with fine pores and light freckles, "
          "the edge of glossy black bob hair, nothing on her skin, soft film light, 35mm film grain")


def _landmarks(bgr):
    import cv2
    import mediapipe as mp
    r = canon._landmarker().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks:
        return None
    H, W = bgr.shape[:2]
    return np.array([(q.x * W, q.y * H) for q in r.face_landmarks[0]])


def boom_mask(bgr, side="image_left"):
    """Mask (uint8 0/1) of the headset boom + capsule on the WRONG cheek, or None (no face / nothing found)."""
    import cv2
    L = _landmarks(bgr)
    if L is None:
        return None
    H, W = bgr.shape[:2]
    fw = L[454][0] - L[234][0]
    k = max(3, int(fw * 0.04)) | 1
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    line = (th > 20).astype(np.uint8)
    if side == "image_left":                     # wrong cheek = image right: mouth corner 291 .. face edge 454
        mc, edge = L[291], L[454]
        xa, xb = mc[0] + 0.02 * fw, edge[0] + 0.30 * fw
    else:
        mc, edge = L[61], L[234]
        xa, xb = edge[0] - 0.30 * fw, mc[0] - 0.02 * fw
    ya, yb = edge[1] - 0.25 * fw, L[152][1] + 0.02 * fw
    roi = np.zeros_like(line)
    roi[int(max(0, ya)):int(min(H, yb)), int(max(0, xa)):int(min(W, xb))] = 1
    # below the lips the boom may pass the mouth corner (3/4 views: capsule under the corner)
    yl = int(L[17][1])
    xa2, xb2 = (mc[0] - 0.12 * fw, xa) if side == "image_left" else (xb, mc[0] + 0.12 * fw)
    roi[max(0, yl):int(min(H, yb)), int(max(0, xa2)):int(min(W, xb2))] = 1
    line &= roi
    core = np.zeros_like(line)                   # the cheek area canon.py measures
    core[int(L[1][1]):int(L[152][1]), int(min(mc[0], edge[0])):int(max(mc[0], edge[0]))] = 1
    n, lab, st, _ = cv2.connectedComponentsWithStats(line, 8)
    keep = np.zeros_like(line)
    for i in range(1, n):
        area = st[i, cv2.CC_STAT_AREA]
        length = float(np.hypot(st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]))
        if area < 4 or length < 0.08 * fw or area / length > 0.06 * fw:   # small specks / broad highlights
            continue
        comp = lab == i
        if (comp & (core > 0)).any():
            keep[comp] = 1
    ys, xs = np.nonzero(keep)
    if not len(xs):
        return None
    # capsule: bright blob at the boom's low end near the mouth corner
    d = np.hypot(xs - mc[0], ys - mc[1])
    near_mc = d < 0.35 * fw
    if near_mc.any():
        j = np.argmax(np.where(near_mc, ys, -1))
    else:
        j = d.argmin()
    ex, ey = int(xs[j]), int(ys[j])
    K = max(5, int(fw * 0.16)) | 1
    th2 = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (K, K)))
    disc = np.zeros_like(keep)
    cv2.circle(disc, (ex, ey), int(fw * 0.12), 1, -1)
    keep |= ((th2 > 18).astype(np.uint8) & disc)
    # large capsules (close-ups, 3/4 views) are wider than the top-hat: grow by the boom's own colour from its end
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    ref = np.median(lab[ys, xs], axis=0)
    near = (np.linalg.norm(lab - ref, axis=2) < 14).astype(np.uint8)
    big = np.zeros_like(keep)
    cv2.circle(big, (ex, ey), int(fw * 0.16), 1, -1)
    near &= big
    n3, lab3 = cv2.connectedComponents(near | (keep & big), 8)
    seeds = set(np.unique(lab3[max(0, ey - k):ey + k + 1, max(0, ex - k):ex + k + 1])) - {0}
    for i in seeds:
        comp = lab3 == i
        if comp.sum() < (0.16 * fw) ** 2 * 3.14 * 0.6:    # not the whole cheek (skin of the same colour)
            keep[comp] = 1
    return cv2.dilate(keep, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))


def _refine(bgr_filled, mask, seed, prompt=REFINE, denoise=0.8, n_seeds=4):
    """FLUX schnell masked img2img on a square crop around the mask -> repainted crop pasted back (feathered)."""
    import cv2
    import comfy
    import comfy_models
    import tempfile
    ys, xs = np.nonzero(mask)
    H, W = mask.shape
    cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
    s = int(max(xs.max() - xs.min(), ys.max() - ys.min()) * 1.8) + 64
    s = min(s, H, W)
    x0, y0 = int(np.clip(cx - s // 2, 0, W - s)), int(np.clip(cy - s // 2, 0, H - s))
    crop, mcrop = bgr_filled[y0:y0 + s, x0:x0 + s], mask[y0:y0 + s, x0:x0 + s]
    S = int(np.clip(round(2 * s / 64) * 64, 512, 1024))        # ~2x: enough detail, no blur mismatch
    tmp = Path(tempfile.mkdtemp(prefix="mic_repair_"))
    imwrite(tmp / "crop.png", cv2.resize(crop, (S, S), interpolation=cv2.INTER_LANCZOS4))
    soft = cv2.GaussianBlur(cv2.dilate(mcrop * 255, np.ones((5, 5), np.uint8)), (0, 0), 3)
    imwrite(tmp / "mask.png", cv2.resize(soft, (S, S)))
    comfy.ensure()
    comfy.lock("mic_repair", "comfy:flux")
    img, msk = comfy.upload(tmp / "crop.png", f"mic_repair_{seed}_crop.png"), comfy.upload(tmp / "mask.png", f"mic_repair_{seed}_mask.png")
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": comfy_models.file("flux_schnell")}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
        "9": {"class_type": "LoadImage", "inputs": {"image": img}},
        "10": {"class_type": "LoadImageMask", "inputs": {"image": msk, "channel": "red"}},
        "4": {"class_type": "VAEEncode", "inputs": {"pixels": ["9", 0], "vae": ["1", 2]}},
        "11": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["4", 0], "mask": ["10", 0]}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
                                                   "latent_image": ["11", 0], "seed": seed, "steps": 4, "cfg": 1.0,
                                                   "sampler_name": "euler", "scheduler": "simple", "denoise": denoise}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "animation-studio/mic_repair"}},
    }
    # several seeds; keep the one whose COARSE colours stay closest to the OpenCV fill (FLUX should add texture,
    # not invent things - a dark hair tuft or an earring on the jaw scores badly)
    sig = max(2.0, s / 40)
    ref = cv2.GaussianBlur(crop.astype(np.float32), (0, 0), sig)
    mk = mcrop > 0
    best = None
    for k in range(n_seeds):
        wf["5"]["inputs"]["seed"] = seed + k
        h = comfy.run(wf, timeout=900)
        comfy.fetch(comfy.outputs(h)[0], tmp / f"out{k}.png")
        rep = cv2.resize(imread(tmp / f"out{k}.png"), (s, s), interpolation=cv2.INTER_AREA)
        score = float(np.abs(cv2.GaussianBlur(rep.astype(np.float32), (0, 0), sig) - ref)[mk].mean())
        if best is None or score < best[0]:
            best = (score, rep)
    out = bgr_filled.copy()
    out[y0:y0 + s, x0:x0 + s] = best[1]
    return out


def retouch(bgr, side="image_left", refine=True, seed=7):
    """-> (repaired bgr, mask) or (None, None) when no wrong-cheek boom is found. Only masked pixels change."""
    import cv2
    m = boom_mask(bgr, side)
    if m is None:
        return None, None
    filled = cv2.inpaint(bgr, m * 255, 7, cv2.INPAINT_TELEA)
    if refine:
        try:
            filled = _refine(filled, m, seed)
        except (SystemExit, Exception) as ex:          # no ComfyUI: Telea alone
            print(f"[mic_repair] FLUX refine skipped ({str(ex)[:120]}) - Telea only")
    a = cv2.GaussianBlur(cv2.dilate(m, np.ones((5, 5), np.uint8)).astype(np.float32), (0, 0), 2.5)[..., None]
    a = np.clip(a * 1.5, 0, 1)
    return (bgr * (1 - a) + filled * a).astype(np.uint8), m


def passes(m):
    return bool(m and m.get("face") and m.get("streak") and not m.get("wrong") and not m.get("mic_both")
                and not m.get("mic_missing"))


def _short(m):
    if not m or not m.get("face"):
        return "no face"
    return (f"mic {m['mic_expected']:.3f}/{m['mic_other']:.3f} "
            + ("WRONG SIDE ONLY" if m["mic_missing"] and m["mic_both"] else "TWO" if m["mic_both"]
               else "missing" if m["mic_missing"] else "one") + f" streak {'ok' if m['streak'] else 'NO'}")


def repair(src, out_dir, side="image_left", methods=("retouch", "qwen"), seeds=3, refine=True,
           edit_prompt=None, edit_neg=EDIT_NEG, color=COLOR, base_seed=1200, force=False):
    """One start image -> dict(src, before, ok, out, method, after, tries). Writes <stem>_mic.png when it passes."""
    import cv2
    src, out_dir = Path(src), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst, info_f = out_dir / f"{src.stem}_mic.png", out_dir / f"{src.stem}_mic.json"
    if info_f.exists() and not force:
        return json.loads(info_f.read_text(encoding="utf-8"))
    before = canon.measure(src, color, side)
    res = dict(src=str(src), side=side, before=before, ok=False, out=None, method=None, after=None, tries=[])
    if not before or not before.get("face"):
        res["note"] = "no face found (profile / from behind) - check by eye"
    elif passes(before):
        res.update(ok=True, out=str(src), method="none (already canon)", after=before)
    else:
        bgr = imread(src)
        best = None

        def judge(img, how):
            nonlocal best
            p = out_dir / f"{src.stem}_try{len(res['tries']) + 1}.png"
            imwrite(p, img)
            m = canon.measure(p, color, side)
            res["tries"].append(dict(file=p.name, method=how, canon=m))
            print(f"[mic_repair] {src.name}: {how} -> {_short(m)}")
            if passes(m):
                p.replace(dst)
                res["tries"][-1]["file"] = dst.name
                res.update(ok=True, out=str(dst), method=how, after=m)
                return True
            if m and m.get("face") and (best is None or m.get("value", -9) > best[1].get("value", -9)):
                best = (p, m)
            return False

        t0 = time.time()
        try:
            for meth in methods:
                try:
                    if meth == "retouch" and before.get("mic_both") and not before.get("mic_missing"):
                        img, _ = retouch(bgr, side, refine)
                        if img is not None and judge(img, "retouch" + ("+flux" if refine else " (telea)")):
                            break
                    if meth == "qwen":
                        import qwen_edit
                        other = "right" if side == "image_left" else "left"
                        prompt = edit_prompt or EDIT.format(side=side.split("_")[1], other=other)
                        done = False
                        for k in range(seeds):
                            q = out_dir / f"{src.stem}_qwen{k + 1}.png"
                            h, w = bgr.shape[:2]
                            qwen_edit.edit([src], prompt, q, w // 16 * 16, h // 16 * 16, base_seed + k, edit_neg)
                            qi = imread(q)
                            if qi.shape[:2] != bgr.shape[:2]:
                                qi = cv2.resize(qi, (w, h), interpolation=cv2.INTER_LANCZOS4)
                            if judge(qi, f"qwen seed {base_seed + k}"):
                                done = True
                                break
                            mq = res["tries"][-1]["canon"] or {}
                            if mq.get("mic_both") and not mq.get("mic_missing") and mq.get("streak"):
                                img, _ = retouch(qi, side, refine, seed=base_seed + k)
                                if img is not None and judge(img, f"qwen seed {base_seed + k} + retouch"):
                                    done = True
                                    break
                        if done:
                            break
                except (SystemExit, Exception) as ex:      # one failing method (ComfyUI down, model error): next one
                    res["tries"].append(dict(method=meth, error=f"{type(ex).__name__}: {str(ex)[:300]}"))
                    print(f"[mic_repair] {src.name}: {meth} failed ({type(ex).__name__}: {str(ex)[:120]})")
        finally:
            try:
                import comfy
                comfy.unlock()                      # keep GPU jobs short: give the lock back right away
            except Exception:
                pass
        res["seconds"] = round(time.time() - t0, 1)
        if not res["ok"]:
            if best:
                b = out_dir / f"{src.stem}_mic_best.png"
                best[0].replace(b)
                res["best"] = b.name
            res["note"] = "no attempt passes the canon check - make new start-image variants (or pick by eye)"
    if res["ok"] or not any("error" in t for t in res["tries"]):   # a failed method is retried on the next call
        info_f.write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    return res


def sheet(results, out):
    """Before | after (face crops, canon numbers) per repaired image."""
    import cv2
    from PIL import Image, ImageDraw
    rows = []
    for r in results:
        a = imread(r["src"])
        b = imread(r["out"]) if r.get("out") else None
        if b is None and r.get("best"):
            b = imread(Path(r["out_dir"]) / r["best"]) if r.get("out_dir") else None
        L = _landmarks(a)
        if L is not None:
            x0, y0 = L.min(0)
            x1, y1 = L.max(0)
            fw = x1 - x0
            box = [int(max(0, x0 - 0.6 * fw)), int(max(0, y0 - 0.5 * fw)), int(min(a.shape[1], x1 + 0.6 * fw)),
                   int(min(a.shape[0], y1 + 0.35 * fw))]
        else:
            box = [0, 0, a.shape[1], a.shape[0]]
        crop = lambda im: Image.fromarray(cv2.cvtColor(im[box[1]:box[3], box[0]:box[2]], cv2.COLOR_BGR2RGB)).resize(
            (420, int(420 * (box[3] - box[1]) / max(1, box[2] - box[0]))))
        ca = crop(a)
        cb = crop(b) if b is not None else Image.new("RGB", ca.size, "black")
        row = Image.new("RGB", (ca.width * 2 + 10, ca.height + 44), "black")
        row.paste(ca, (0, 44))
        row.paste(cb, (ca.width + 10, 44))
        d = ImageDraw.Draw(row)
        d.text((4, 2), f"{Path(r['src']).name}  BEFORE: {_short(r['before'])}", fill="white")
        d.text((ca.width + 14, 2), f"AFTER ({r.get('method') or 'failed'}): {_short(r.get('after'))}",
               fill="lime" if r["ok"] else "red")
        rows.append(row)
    if not rows:
        return None
    W = max(r.width for r in rows)
    out_im = Image.new("RGB", (W, sum(r.height + 8 for r in rows)), "black")
    y = 0
    for r in rows:
        out_im.paste(r, (0, y))
        y += r.height + 8
    out_im.save(out, quality=90)
    return Path(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out-dir", default=None, help="default: next to each image")
    ap.add_argument("--side", default="image_left", choices=["image_left", "image_right"],
                    help="where the ONE mic belongs (Claudia: image_left = her right cheek)")
    ap.add_argument("--color", default=COLOR, help="accent colour for the streak check")
    ap.add_argument("--methods", default="retouch,qwen")
    ap.add_argument("--seeds", type=int, default=3, help="Qwen-Edit seeds to try")
    ap.add_argument("--no-refine", action="store_true", help="retouch with OpenCV only (no FLUX, no GPU)")
    ap.add_argument("--edit-prompt", default=None)
    ap.add_argument("--edit-negative", default=EDIT_NEG)
    ap.add_argument("--force", action="store_true", help="repair again even if <stem>_mic.json exists")
    a = ap.parse_args()
    results = []
    for f in a.images:
        od = Path(a.out_dir) if a.out_dir else Path(f).parent
        r = repair(f, od, a.side, tuple(a.methods.split(",")), a.seeds, not a.no_refine, a.edit_prompt,
                   a.edit_negative, a.color, force=a.force)
        r["out_dir"] = str(od)
        results.append(r)
        print(json.dumps({k: r.get(k) for k in ("src", "ok", "method", "out", "note")}))
    od = Path(a.out_dir) if a.out_dir else Path(a.images[0]).parent
    s = sheet(results, od / "mic_repair_sheet.jpg")
    if s:
        print("->", s)


if __name__ == "__main__":
    main()
