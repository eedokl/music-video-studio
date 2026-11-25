# /// script
# requires-python = "==3.12.*"
# dependencies = ["facexlib==0.3.0", "numpy==2.5.4", "opencv-python-headless==5.0.0.93", "torch==2.15.0",
#                 "torchvision==0.29.2"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# torchvision = { index = "pytorch-cpu" }
# ///
"""Optional face tracker for face_pass.py: RetinaFace (facexlib, MIT) on the CPU - all faces of every frame.

face_pass.py tracks with MediaPipe by default (small CPU wheel, no torch). MediaPipe's detector is made for near faces;
face_pass gets around that with upscaled search windows, which held on the frontal far shots tested (a profile face
was lost in half the frames - RetinaFace kept it in all). RetinaFace is the backup
for what windows cannot rescue: faces under ~40 px in the frame, strong profiles, crowds, fast pans where the face
jumps out of the window. Choose it with project.json "face_fix": {"tracker": "retinaface"} or --tracker retinaface.

Runs in its own environment (CPU PyTorch, ~250 MB once in the uv cache), so the GPU stays free for ComfyUI;
~0.5-0.8 s per 1024x576 frame. Weights detection_Resnet50_Final.pth (~105 MB) are downloaded on first use into
config "retinaface_dir" (default ~/.cache/facexlib); copy an existing file there to skip the download.

  uv run face_track_retina.py <clip.mp4> -o faces.json [--conf 0.5]
     -> {"W", "H", "frames": [[[cx, cy, width, score], ...] per frame]}  (width = box width in picture pixels)
"""
import argparse
import json
import os
import sys
from pathlib import Path

WEIGHTS = "detection_Resnet50_Final.pth"


def weights_dir():
    d = os.environ.get("RETINAFACE_DIR")
    if not d:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "studio-core" / "scripts"))
            import config
            d = config.get("retinaface_dir")
        except Exception:
            d = None
    d = Path(d) if d else Path.home() / ".cache" / "facexlib"
    d.mkdir(parents=True, exist_ok=True)
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--conf", type=float, default=0.5)
    a = ap.parse_args()
    import cv2
    import torch
    from facexlib.detection import init_detection_model
    torch.set_num_threads(max(1, (os.cpu_count() or 4) - 1))
    net = init_detection_model("retinaface_resnet50", half=False, device="cpu", model_rootpath=str(weights_dir()))
    cap = cv2.VideoCapture(str(a.clip))
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames = []
    with torch.no_grad():
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            det = net.detect_faces(bgr, conf_threshold=a.conf)
            frames.append([[round(float((d[0] + d[2]) / 2), 1), round(float((d[1] + d[3]) / 2), 1),
                            round(float(d[2] - d[0]), 1), round(float(d[4]), 3)] for d in det])
    cap.release()
    Path(a.out).write_text(json.dumps({"W": W, "H": H, "frames": frames}), encoding="utf-8")
    print(f"{len(frames)} frames, faces in {sum(bool(f) for f in frames)}")


if __name__ == "__main__":
    main()
