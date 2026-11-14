# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Shared Real-ESRGAN upscaler (realesrgan-ncnn-vulkan): images (with or without alpha), image sequences and videos.

  from upscale import upscale_rgba, upscale_image, upscale_video
  big = upscale_rgba(rgba_uint8, factor=2, model="anime")      # numpy HxWx4 -> (H*f)xWx4, colour and alpha separately
  upscale_image("panel.png", "panel_4x.png", factor=4, model="photo")
  upscale_video("s2v_480p.mp4", "s2v_720p.mp4", width=1280, height=720)   # AI clips 832x480 -> 1280x720
Why colour and alpha separately: ncnn has no alpha channel. Colour is composited on white and upscaled with the
chosen model; alpha is upscaled as a grey image with the general model (soft edges), then both are joined.
Models: "anime" = realesrgan-x4plus-anime (clean ink lines, drawn panels, figures), "photo" = realesrgan-x4plus
(photographic stills and video frames). The network always works at x4; other factors are resized with Lanczos.
Without the config key `realesrgan` (path of realesrgan-ncnn-vulkan) everything falls back to Lanczos (+ unsharp
for videos) and says so. Takes the shared GPU lock ("ncnn:realesrgan").
Measured: S2V close-up 832x480 -> 1280x720, 61 frames in 2.5 min, ~5x sharper than Lanczos - but x4plus smooths
skin detail (Claudia's freckles): judge faces by eye.
CLI: uv run upscale.py in.png|in.mp4 out [--factor 4] [--model photo]
       [--width 1280 --height 720]   (videos: target size; frames are upscaled x4 by the network, then resized)
Videos keep their frames and fps, so the clip's meta (<clip>.json: song_start, fps, delay_frames ...) is copied to
<out>.json (+ "upscaled_from", width, height) - the upscaled clip can replace the original in selection.json.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402

MODELS = {"anime": "realesrgan-x4plus-anime", "photo": "realesrgan-x4plus"}


def exe():
    e = config.get("realesrgan")
    return e if e and Path(e).exists() else None


def _lock():
    from gpu_lock import acquire
    acquire("upscale", model="ncnn:realesrgan")


def _run(src, dst, model):
    """Network x4 on a file or a folder of PNGs. Returns True on success."""
    e = exe()
    if not e:
        return False
    _lock()
    r = subprocess.run([e, "-i", str(src), "-o", str(dst), "-n", MODELS.get(model, model), "-s", "4", "-f", "png"],
                       capture_output=True, text=True, cwd=str(Path(e).parent))
    if r.returncode:
        print("  Real-ESRGAN failed, Lanczos instead:", (r.stderr or "")[-300:], file=sys.stderr)
        return False
    return True


def upscale_rgba(rgba, factor=4, model="anime"):
    """numpy uint8 HxWx3 or HxWx4 -> upscaled array (same channels). Lanczos fallback."""
    import numpy as np
    from PIL import Image
    h, w = rgba.shape[:2]
    size = (int(round(w * factor)), int(round(h * factor)))
    has_a = rgba.shape[2] == 4
    tmp = Path(tempfile.mkdtemp(prefix="upscale_"))
    try:
        a = rgba.astype(np.float32) / 255
        rgb = a[..., :3] * a[..., 3:] + (1 - a[..., 3:]) if has_a else a[..., :3]        # colour on white
        Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).save(tmp / "rgb.png")
        if has_a:
            al = (a[..., 3] * 255 + 0.5).astype(np.uint8)
            Image.fromarray(np.stack([al] * 3, -1)).save(tmp / "alpha.png")
        ok = _run(tmp / "rgb.png", tmp / "rgb_x.png", model) and \
            (not has_a or _run(tmp / "alpha.png", tmp / "alpha_x.png", "photo"))
        if ok:
            rgb4 = Image.open(tmp / "rgb_x.png").convert("RGB").resize(size, Image.LANCZOS)
            parts = [np.asarray(rgb4)]
            if has_a:
                parts.append(np.asarray(Image.open(tmp / "alpha_x.png").convert("L").resize(size, Image.LANCZOS))[..., None])
            return np.concatenate(parts, -1)
        mode = "RGBA" if has_a else "RGB"
        return np.asarray(Image.fromarray(rgba, mode).resize(size, Image.LANCZOS))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def upscale_image(src, dst, factor=4, model="photo"):
    import numpy as np
    from PIL import Image
    im = Image.open(src)
    arr = np.asarray(im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB"))
    out = upscale_rgba(arr, factor, model)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(dst)
    return Path(dst)


def upscale_video(src, dst, width=1280, height=720, model="photo", fps=None):
    """Video -> frames -> network x4 (folder at once) -> resized to width x height -> H.264 (sound dropped)."""
    from media import ffmpeg
    tmp = Path(tempfile.mkdtemp(prefix="upscale_v_"))
    try:
        (tmp / "in").mkdir()
        (tmp / "out").mkdir()
        subprocess.run([ffmpeg(), "-v", "error", "-i", str(src), str(tmp / "in" / "f%05d.png")], check=True)
        net = _run(tmp / "in", tmp / "out", model)
        frames = tmp / ("out" if net else "in")
        rate = fps or _fps(src)
        vf = f"scale={width}:{height}:flags=lanczos" + ("" if net else ",unsharp=5:5:0.8")
        subprocess.run([ffmpeg(), "-y", "-v", "error", "-framerate", str(rate), "-i", str(frames / "f%05d.png"), "-vf", vf,
                        "-c:v", "libx264", "-crf", "15", "-pix_fmt", "yuv420p", str(dst)], check=True)
        _copy_meta(src, dst, width, height)
        return Path(dst), ("realesrgan" if net else "lanczos")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _copy_meta(src, dst, width, height):
    """Same frames, same fps: the clip meta (clips.py) stays valid for the upscaled file."""
    import json
    m = Path(src).with_suffix(".json")
    if m.exists() and Path(src).with_suffix(".json") != Path(dst).with_suffix(".json"):
        try:
            d = json.loads(m.read_text(encoding="utf-8"))
        except ValueError:
            return
        d.update(upscaled_from=Path(src).name, width=width, height=height)
        Path(dst).with_suffix(".json").write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


def _fps(src):
    import re
    from media import ffmpeg
    err = subprocess.run([ffmpeg(), "-i", str(src)], capture_output=True, text=True, errors="replace").stderr
    m = re.search(r"([\d.]+)\s*fps", err)
    return m.group(1) if m else "24"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--factor", type=float, default=4)
    ap.add_argument("--model", default=None, choices=sorted(MODELS))
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    a = ap.parse_args()
    if Path(a.src).suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
        out, how = upscale_video(a.src, a.dst, a.width, a.height, a.model or "photo")
        print(f"-> {out} ({how})")
    else:
        print("->", upscale_image(a.src, a.dst, a.factor, a.model or "anime"), "(realesrgan)" if exe() else "(lanczos)")


if __name__ == "__main__":
    main()
