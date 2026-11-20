# /// script
# requires-python = "==3.12.*"
# dependencies = ["mediapipe==1.2.3", "numpy==2.5.4", "opencv-python-headless==5.0.0.93"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Check a character's colour accent on the correct side of the face (e.g. Claudia's ONE clay-orange streak on HER right
= the image's left; her clay star clip on the other side must stay a small spot).

MediaPipe finds the face; pixels of the accent colour (hue +-7, saturated, not dark) are counted in the hair area left and
right of the face, the face itself (landmark hull, +8 %) excluded.
  streak = enough accent on the expected side AND spread over several rows (a vertical band, not a clip-sized spot)
  wrong  = a lot of accent on the other side (a second streak / mirrored image)
  value  = 10 x share(expected side) + row spread - 15 x max(0, share(other side) - 0.04)   (to rank variants)
Microphone (headset boom = a thin bright line across the cheek): white top-hat filter on both cheeks (between the face
outline and the mouth corner, nose tip to chin). mic_other >= 0.015 = a boom on the wrong cheek too (two mics, or
the mic on the wrong side); no boom on the expected cheek = mic missing. Separated cleanly on 12 test images
(single mic: other 0.000; two mics: 0.021-0.041).
Hair clip: `clips` counts the accent-coloured spots in the hair beside the face (the streak lies in the bangs,
nearer the centre); `clip_sides` says where. Canon is ONE - AI video likes to mirror the clip onto the other
side after a cut (LTX-2.5 multi-shot: 3 of 4 seeds). measure_frames() measures chosen frames, e.g. one per shot.
Viewed from BEHIND the sides swap (her right is then the image's right) - and no face is found anyway: check those by eye.

  uv run canon.py img.png [...]
         [--color "#D97757"] [--side image_left]      (videos: 3 frames at 20/50/80 %)
         [--at 0.25,0.75]                             (videos: these positions instead, one result per frame)
Config: face_landmarker (see mouth.py).
"""
import argparse
import json
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use()
from cvio import imread, video_capture  # noqa: E402
from mouth import landmarker_model  # noqa: E402

_lm = None


def _landmarker():
    global _lm
    if _lm is None:
        from mediapipe.tasks.python import BaseOptions, vision
        _lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=landmarker_model()), num_faces=1))
    return _lm


def accent_mask(bgr, color="#D97757", hue_tol=7):
    import cv2
    rgb = np.uint8([[[int(color[i:i + 2], 16) for i in (5, 3, 1)]]])        # hex -> BGR pixel
    hc = int(cv2.cvtColor(rgb, cv2.COLOR_BGR2HSV)[0, 0, 0])
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = (hsv[..., i].astype(int) for i in range(3))
    dh = np.minimum(np.abs(h - hc), 180 - np.abs(h - hc))
    return ((dh <= hue_tol) & (s >= 120) & (v >= 70)).astype(np.uint8)


def accent_spots(bgr, color, x0, x1, y0, y1):
    """Hair clips = spots of the accent colour in the hair BESIDE the face: [(side "left"/"right", area share)].
    Measured on Claudia stills and LTX-2.5 clips: a clip sits 0.49-0.57 face widths from the face centre, between a
    little above the brow line and eye height; the streak stays within 0.30 (the bangs). The colour test is looser
    than accent_mask (dim, blue-lit renders desaturate the clip); black hair around it keeps that safe."""
    import cv2
    fw, fh, cx = x1 - x0, y1 - y0, (x0 + x1) / 2
    rgb = np.uint8([[[int(color[i:i + 2], 16) for i in (5, 3, 1)]]])
    hc = int(cv2.cvtColor(rgb, cv2.COLOR_BGR2HSV)[0, 0, 0])
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, sa, v = (hsv[..., i].astype(int) for i in range(3))
    dh = np.minimum(np.abs(h - hc), 180 - np.abs(h - hc))
    m = ((dh <= 14) & (sa >= 50) & (v >= 35)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, _, stats, cent = cv2.connectedComponentsWithStats(m, 8)
    out = []
    for i in range(1, n):
        w, hh, ar = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT]), int(stats[i, cv2.CC_STAT_AREA])
        dx, dy = (float(cent[i][0]) - cx) / fw, (float(cent[i][1]) - y0) / fh
        if not (0.40 <= abs(dx) <= 0.72 and -0.30 <= dy <= 0.35):
            continue                                  # the bangs (streak), the face, clothes, background
        if ar < 0.0015 * fw * fh or w > 0.30 * fw or hh > 0.30 * fh:
            continue                                  # specks; anything larger than a clip
        out.append(("left" if dx < 0 else "right", round(ar / (fw * fh), 4)))
    return out


def measure_bgr(bgr, color="#D97757", side="image_left"):
    import cv2
    import mediapipe as mp
    H, W = bgr.shape[:2]
    r = _landmarker().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks:
        return dict(face=False, value=-1.0, streak=False, wrong=False)
    p = r.face_landmarks[0]
    xs, ys = np.array([q.x for q in p]) * W, np.array([q.y for q in p]) * H
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    fw, fh, cx, cy = x1 - x0, y1 - y0, (x0 + x1) / 2, (y0 + y1) / 2
    m = accent_mask(bgr, color)
    hull = cv2.convexHull(np.stack([xs, ys], 1).astype(np.float32))
    cv2.fillConvexPoly(m, ((hull - [cx, cy]) * 1.08 + [cx, cy]).astype(np.int32), 0)
    spots = accent_spots(bgr, color, x0, x1, y0, y1)
    ya, yb = int(max(0, y0 - 0.9 * fh)), int(min(H, y1 + 0.1 * fh))
    left = m[ya:yb, int(max(0, x0 - 0.7 * fw)):int(cx)]
    right = m[ya:yb, int(cx):int(min(W, x1 + 0.7 * fw))]
    exp, oth = (left, right) if side == "image_left" else (right, left)
    fe, fo = float(exp.sum()) / (fw * fh), float(oth.sum()) / (fw * fh)
    rows = float((exp.sum(1) > 2).mean()) if exp.size else 0.0
    me, mo = mic_lines(bgr, p, W, H, side)
    mic_both = mo >= 0.015
    value = fe * 10 + rows - max(0.0, fo - 0.04) * 15 - (1.0 if mic_both else 0.0)
    return dict(face=True, expected=round(fe, 4), other=round(fo, 4), rows=round(rows, 2), value=round(value, 3),
                streak=bool(fe >= 0.003 and rows >= 0.03), wrong=bool(fo >= 0.04 and fo > fe),
                mic_expected=round(me, 3), mic_other=round(mo, 3), mic_both=bool(mic_both), mic_missing=bool(me < 0.01),
                face_height=round(fh / H, 3), clips=len(spots),
                clip_sides=sorted(sd for sd, _ in spots))


def mic_lines(bgr, p, W, H, side="image_left"):
    """Share of thin bright line pixels (white top-hat) on the expected and the other cheek."""
    import cv2
    P = lambda i: (p[i].x * W, p[i].y * H)
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    fw = P(454)[0] - P(234)[0]
    k = max(3, int(fw * 0.04)) | 1
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    y0, y1 = int(P(1)[1]), int(P(152)[1])
    res = []
    for a, b in ((234, 61), (291, 454)):            # image-left cheek, image-right cheek
        xa, xb = sorted((int(P(a)[0]), int(P(b)[0])))
        roi = th[max(0, y0):max(0, y1), max(0, xa):max(0, xb)]
        res.append(float((roi > 25).mean()) if roi.size else 0.0)
    return (res[0], res[1]) if side == "image_left" else (res[1], res[0])


def measure(path, color="#D97757", side="image_left"):
    """Image -> dict; video -> worst of 3 frames (20/50/80 %)."""
    import cv2
    path = Path(path)
    if path.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
        cap = video_capture(path)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        res = []
        for u in (0.2, 0.5, 0.8):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(u * n))
            ok, f = cap.read()
            if ok:
                res.append(measure_bgr(f, color, side))
        faces = [r for r in res if r["face"]]
        if not faces:
            return dict(face=False, value=-1.0, streak=False, wrong=False, frames=len(res))
        worst = min(faces, key=lambda r: r["value"])
        return dict(worst, frames=len(res), faces=len(faces), streak_frames=sum(r["streak"] for r in faces))
    bgr = imread(path)
    if bgr is None:
        return None
    return measure_bgr(bgr, color, side)


def measure_frames(path, positions, color="#D97757", side="image_left"):
    """A video at the given positions (0..1 of its length) -> one measure_bgr dict per position ({"face": False} when
    the frame cannot be read)."""
    import cv2
    cap = video_capture(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    res = []
    for u in positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(min(max(u, 0.0), 1.0) * max(n - 1, 0)))
        ok, f = cap.read()
        res.append(dict(measure_bgr(f, color, side), at=round(float(u), 3)) if ok else dict(face=False, at=round(float(u), 3)))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--at", default="", help="videos: positions 0..1, comma separated (one result per frame)")
    ap.add_argument("--color", default="#D97757")
    ap.add_argument("--side", default="image_left", choices=["image_left", "image_right"])
    a = ap.parse_args()
    at = [float(x) for x in a.at.split(",") if x]
    for f in a.files:
        if at and Path(f).suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
            for r in measure_frames(f, at, a.color, a.side):
                print(json.dumps(dict(file=f, **r)))
        else:
            print(json.dumps(dict(file=f, **(measure(f, a.color, a.side) or {}))))


if __name__ == "__main__":
    main()
