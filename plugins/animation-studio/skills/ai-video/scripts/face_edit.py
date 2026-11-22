# /// script
# requires-python = "==3.12.*"
# dependencies = ["mediapipe==1.2.3", "numpy==2.5.4", "opencv-python-headless==5.0.0.93"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Edit only a face: cut a square around the head out of a picture, and paste the edited square's FACE back.

Why: an add-only image edit of the whole picture ("add a headset microphone, keep everything else") re-renders the
whole picture - and invents things outside the face. Measured on El-Ge-Te-Em (2026-11-22, Qwen-Image-Edit, 24 tries
on 12 pictures): about 10 came back with a second microphone somewhere in the scene (a desk microphone, one lying on
the table, a boom in the air). With the edit limited to the head and only the face area pasted back, 6 of 6 were
clean, the rest of the picture stays pixel-identical, and the small object is drawn at four times the resolution.

  crop    the square around the head (side = K x face height, default 2.3), scaled to SIZE (1024) -> crop.png, and
          the box + the face outline -> box.json. No face found (wide shot, from behind): box.json says so.
  paste   the edited square scaled back; only the face outline grown by GROW (1.22: the face and a rim of hair, where
          a headset wire comes out) is taken from it, with a soft edge - a floating object beside the hair stays out.
          No face: the picture is copied unchanged (at that size the edit would not be seen anyway).

The image model runs between the two steps in the caller's process (night_run.py kind qwen_edit with "face": true),
which holds the GPU lock - this script needs no GPU.
  uv run face_edit.py crop  picture.png crop.png box.json [--k 2.3] [--size 1024]
  uv run face_edit.py paste picture.png edited.png box.json out.png [--grow 1.22]
Config: face_landmarker (see mouth.py).
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use()
from cvio import imread, imwrite  # noqa: E402


def face_points(bgr):
    """Face landmarks in pixels (x array, y array), or None when no face is found."""
    import cv2
    import mediapipe as mp
    from canon import _landmarker
    H, W = bgr.shape[:2]
    r = _landmarker().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks:
        return None
    p = r.face_landmarks[0]
    return np.array([q.x for q in p]) * W, np.array([q.y for q in p]) * H


def crop(picture, crop_png, box_json, k=2.3, size=1024):
    """-> the box dict written to box_json ({"face": False} when there is no face)."""
    import cv2
    bgr = imread(picture)
    if bgr is None:
        raise SystemExit(f"cannot read {picture}")
    pts = face_points(bgr)
    if pts is None:
        box = {"face": False}
    else:
        xs, ys = pts
        H, W = bgr.shape[:2]
        cx, cy, fh = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2, ys.max() - ys.min()
        side = int(min(k * fh, H, W))
        x0 = int(min(max(cx - side / 2, 0), W - side))
        y0 = int(min(max(cy - side * 0.52, 0), H - side))
        hull = cv2.convexHull(np.stack([xs, ys], 1).astype(np.float32)).reshape(-1, 2)
        box = {"face": True, "x": x0, "y": y0, "side": side, "size": size, "face_share": round(float(fh / side), 3),
               "hull": [[round(float(a), 1), round(float(b), 1)] for a, b in hull]}
        imwrite(crop_png, cv2.resize(bgr[y0:y0 + side, x0:x0 + side], (size, size), interpolation=cv2.INTER_CUBIC))
    Path(box_json).write_text(json.dumps(box), encoding="utf-8")
    return box


def paste(picture, edited, box_json, out, grow=1.22):
    import cv2
    box = json.loads(Path(box_json).read_text(encoding="utf-8"))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    if not box.get("face"):
        shutil.copy(picture, out)
        return False
    bgr, ed = imread(picture), imread(edited)
    if bgr is None or ed is None:
        raise SystemExit(f"cannot read {picture if bgr is None else edited}")
    x0, y0, side = box["x"], box["y"], box["side"]
    ed = cv2.resize(ed, (side, side), interpolation=cv2.INTER_AREA)
    hull = np.array(box["hull"], np.float32) - [x0, y0]
    c = hull.mean(0)
    m = np.zeros((side, side), np.uint8)
    cv2.fillConvexPoly(m, ((hull - c) * grow + c).astype(np.int32), 255)
    m = (cv2.GaussianBlur(m, (0, 0), side * 0.012).astype(np.float32) / 255)[..., None]
    res = bgr.astype(np.float32)
    res[y0:y0 + side, x0:x0 + side] = ed * m + res[y0:y0 + side, x0:x0 + side] * (1 - m)
    imwrite(out, np.clip(res, 0, 255).astype(np.uint8))
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("crop")
    c.add_argument("picture"), c.add_argument("crop_png"), c.add_argument("box_json")
    c.add_argument("--k", type=float, default=2.3), c.add_argument("--size", type=int, default=1024)
    p = sub.add_parser("paste")
    p.add_argument("picture"), p.add_argument("edited"), p.add_argument("box_json"), p.add_argument("out")
    p.add_argument("--grow", type=float, default=1.22)
    a = ap.parse_args()
    if a.cmd == "crop":
        box = crop(a.picture, a.crop_png, a.box_json, a.k, a.size)
        print("face " + (f"box {box['x']},{box['y']} side {box['side']}" if box.get("face") else "not found"))
    else:
        print("pasted" if paste(a.picture, a.edited, a.box_json, a.out, a.grow) else "no face - picture copied unchanged")


if __name__ == "__main__":
    main()
