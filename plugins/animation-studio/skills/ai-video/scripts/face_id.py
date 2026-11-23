# /// script
# requires-python = "==3.12.*"
# dependencies = ["mediapipe==1.2.3", "numpy==2.5.4", "onnxruntime==1.32.0", "opencv-python-headless==5.0.0.93"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Is this the film's character? Face similarity of an image against a character's reference images.

For characters without a measured canon (project.json "characters"): the image model draws a stranger now and then -
mostly when the face is small ("Ein Haus, eine Nacht": all four start images of two medium wide shots showed a slimmer
man; nobody saw it before the takes were rendered). MediaPipe finds the faces and five points (eyes, nose, mouth
corners), the face is aligned to 112x112 and an ArcFace-type ONNX model gives a vector; similarity = cosine against
the mean vector of the references.

Measured on 120 start images of one man (ArcFace w600k_r50): images that showed him 0.49-0.76, the strangers
0.21-0.24. Hence STRANGER = 0.40: below it the image "does not look like the character". Limits:
  - two people in one picture and faces turned away score lower (0.2-0.35 on shots that were accepted) - a hint, not a
    verdict; from behind there is no face and no value
  - the number says "same face", nothing about hair, clothes or hands - the sheet is still looked at

Config: face_id_model = path of an ArcFace-type ONNX recognition model (input 1x3x112x112, e.g. InsightFace buffalo_l
        w600k_r50.onnx - licensed for non-commercial research only; the plugin neither ships nor downloads a model).
        face_landmarker (see mouth.py). CPU, about a second per image.
Usage: uv run face_id.py <ref.jpg>[;<ref2.jpg>] <image> [<image> ...]
       from face_id import available, reference, similarity
"""
import sys
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402
from cvio import imread  # noqa: E402
from mouth import landmarker_model  # noqa: E402

STRANGER = 0.40
# ArcFace 112x112 template: eye (image left), eye (image right), nose tip, mouth corner left, mouth corner right
TEMPLATE = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]], np.float32)
EYE_L, EYE_R, NOSE, MOUTH_L, MOUTH_R = (33, 133), (362, 263), 1, 61, 291   # MediaPipe face mesh, image left / right
_state = {}


def model_path():
    p = config.get("face_id_model")
    return Path(p) if p and Path(p).exists() else None


def available():
    return model_path() is not None


def _landmarker():
    if "lm" not in _state:
        from mediapipe.tasks.python import BaseOptions, vision
        _state["lm"] = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=landmarker_model()), num_faces=4))
    return _state["lm"]


def _session():
    if "ort" not in _state:
        import onnxruntime as ort
        s = ort.InferenceSession(str(model_path()), providers=["CPUExecutionProvider"])
        _state["ort"] = (s, s.get_inputs()[0].name)
    return _state["ort"]


def _points(bgr):
    """Five points per face found, in pixels: [(points 5x2, face width px)]."""
    import cv2
    import mediapipe as mp
    H, W = bgr.shape[:2]
    r = _landmarker().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(cv2.cvtColor(np.ascontiguousarray(bgr), cv2.COLOR_BGR2RGB))))
    out = []
    for f in r.face_landmarks or []:
        p = np.array([[q.x * W, q.y * H] for q in f], np.float32)
        five = np.array([p[list(EYE_L)].mean(0), p[list(EYE_R)].mean(0), p[NOSE], p[MOUTH_L], p[MOUTH_R]], np.float32)
        out.append((five, float(p[:, 0].max() - p[:, 0].min())))
    return out


def _all_points(bgr):
    """Faces of the whole picture plus those of overlapping square cut-outs: MediaPipe's detector misses faces under
    about a tenth of the picture width - exactly the small faces that come out as strangers. Doubles are dropped."""
    H, W = bgr.shape[:2]
    found = _points(bgr)
    side = int(min(H, W) * 0.62)
    xs = sorted({round(x) for x in np.linspace(0, W - side, max(2, int(np.ceil(W / (side / 2))) - 1))})
    ys = sorted({round(y) for y in np.linspace(0, H - side, max(2, int(np.ceil(H / (side / 2))) - 1))})
    for y in ys:
        for x in xs:
            for five, width in _points(bgr[y:y + side, x:x + side]):
                five = five + np.array([x, y], np.float32)
                if all(np.linalg.norm(five[2] - o[2]) > 0.5 * max(width, w) for o, w in found):
                    found.append((five, width))
    return found


def faces(bgr):
    """[(unit vector, face width px)] for every face in the picture."""
    import cv2
    sess, inp = _session()
    out = []
    for five, width in _all_points(bgr):
        M, _ = cv2.estimateAffinePartial2D(five, TEMPLATE, method=cv2.LMEDS)
        if M is None:
            continue
        face = cv2.warpAffine(bgr, M, (112, 112), borderValue=0.0)
        x = (cv2.cvtColor(face, cv2.COLOR_BGR2RGB).astype(np.float32) - 127.5) / 127.5
        v = sess.run(None, {inp: x.transpose(2, 0, 1)[None]})[0][0]
        out.append((v / (np.linalg.norm(v) + 1e-9), width))
    return out


def reference(paths, every=False):
    """Mean unit vector of the reference images (the largest face of each); None when no face is found in any.
    every=True: all faces of each image count (a views sheet shows the same person several times)."""
    vs = []
    for p in paths:
        im = imread(p)
        fs = faces(im) if im is not None else []
        if fs and every:
            vs += [f[0] for f in fs]
        elif fs:
            vs.append(max(fs, key=lambda f: f[1])[0])
    if not vs:
        return None
    v = np.mean(vs, axis=0)
    return v / (np.linalg.norm(v) + 1e-9)


def similarity(path, ref):
    """{"sim": best cosine among the faces (None = no face found), "width": that face's width px, "faces": n}."""
    im = imread(path)
    fs = faces(im) if im is not None else []
    if not fs or ref is None:
        return {"sim": None, "width": 0, "faces": len(fs)}
    v, w = max(fs, key=lambda f: float(f[0] @ ref))
    return {"sim": round(float(v @ ref), 3), "width": round(w), "faces": len(fs)}


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    if not available():
        sys.exit("face_id_model not configured: check_tools.py --set face_id_model=<ArcFace-type .onnx>")
    ref = reference(sys.argv[1].split(";"))
    if ref is None:
        sys.exit("no face found in the reference image(s)")
    for p in sys.argv[2:]:
        r = similarity(p, ref)
        note = "no face" if r["sim"] is None else f"{r['sim']:.3f}{'  STRANGER?' if r['sim'] < STRANGER else ''}"
        print(f"{note:20s} face {r['width']:4d} px  faces {r['faces']}  {p}")


if __name__ == "__main__":
    main()
