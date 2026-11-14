# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Frames at given times: contact sheets, side-by-side comparisons and a similarity score between two videos.

  python frames.py sheet VIDEO OUT.jpg --times 3,12,20.5 [--cols 3] [--width 480]
  python frames.py compare OUT.jpg --times 74,80,90 --video ref.mp4 --label original --video new.mp4 --label plugin
         [--offset 0,0] [--width 480] [--json scores.json]
Run with: uv run frames.py ...
sheet    grid of frames at the given seconds (for a 1-fps preview the frame number equals the second).
compare  one row per time, one column per video, labelled; with two videos it also prints a similarity per time:
         SSIM on a 320x180 grey image (1 = identical, > 0.9 looks the same, < 0.5 different picture) and the mean
         absolute difference in grey levels (0-255). --offset shifts each video's clock (a clip that starts at
         song second 72 gets --offset 0,-72 when compared on song time).
In Python:  from frames import frame_at, sheet_at, compare, ssim
"""
import argparse
import json
import subprocess
from pathlib import Path

import config

LABEL_H = 26


def ffmpeg():
    return config.need("ffmpeg")


def duration(path):
    import re
    r = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True, errors="replace").stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 1e9


def frame_at(video, t, width=480):
    """PIL image of the frame at t seconds (clamped to the video), scaled to width."""
    from PIL import Image
    import io
    t = min(max(0.0, float(t)), max(0.0, duration(video) - 0.05))
    raw = subprocess.run([ffmpeg(), "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-vf", f"scale={width}:-2", "-f", "image2pipe", "-c:v", "png", "-"],
                         capture_output=True, check=True).stdout
    if not raw:
        # past the last video frame (the container duration comes from the longer audio, or a 1-fps preview
        # whose last frame starts up to 1 s before the end): decode the last seconds, keep the final frame
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "last.png"
            subprocess.run([ffmpeg(), "-v", "error", "-y", "-ss", f"{max(0.0, t - 5):.3f}", "-i", str(video),
                            "-vf", f"scale={width}:-2", "-update", "1", str(png)], capture_output=True, check=True)
            raw = png.read_bytes() if png.exists() else b""
    if not raw:
        raise RuntimeError(f"no video frame at {t:.2f} s in {video}")
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _label(img, text):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, LABEL_H], fill=(0, 0, 0))
    d.text((6, 6), text, fill=(255, 255, 255))
    return img


def sheet_at(video, out, times, cols=3, width=480, labels=None):
    from PIL import Image
    frames = [frame_at(video, t, width) for t in times]
    h = frames[0].height
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * width, rows * (h + LABEL_H)), (0, 0, 0))
    for i, (t, f) in enumerate(zip(times, frames)):
        tile = Image.new("RGB", (width, h + LABEL_H))
        tile.paste(f, (0, LABEL_H))
        lab = labels[i] if labels else f"{float(t):.2f} s"
        sheet.paste(_label(tile, lab), ((i % cols) * width, (i // cols) * (h + LABEL_H)))
    sheet.save(out, quality=88)
    return out


def ssim(a, b):
    """Mean SSIM of two PIL images on 320x180 grey with 8x8 windows, plus mean absolute grey difference."""
    import numpy as np
    A = np.asarray(a.convert("L").resize((320, 180)), float)
    B = np.asarray(b.convert("L").resize((320, 180)), float)

    def box(x, k=8):
        c = np.cumsum(np.cumsum(np.pad(x, ((1, 0), (1, 0))), 0), 1)
        return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)
    ma, mb = box(A), box(B)
    va, vb, cov = box(A * A) - ma ** 2, box(B * B) - mb ** 2, box(A * B) - ma * mb
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    s = ((2 * ma * mb + c1) * (2 * cov + c2)) / ((ma ** 2 + mb ** 2 + c1) * (va + vb + c2))
    return round(float(s.mean()), 3), round(float(np.abs(A - B).mean()), 1)


def compare(out, times, videos, labels=None, offsets=None, width=480):
    """Rows = times, columns = videos. Returns [{"t", "ssim", "mad"}] when two videos are given."""
    from PIL import Image
    labels = labels or [Path(v).stem for v in videos]
    offsets = offsets or [0.0] * len(videos)
    rows, scores = [], []
    for t in times:
        fr = [frame_at(v, float(t) + o, width) for v, o in zip(videos, offsets)]
        if len(fr) == 2:
            s, d = ssim(fr[0], fr[1])
            scores.append({"t": float(t), "ssim": s, "mad": d})
        rows.append(fr)
    h = rows[0][0].height
    sheet = Image.new("RGB", (len(videos) * width, len(times) * (h + LABEL_H)), (0, 0, 0))
    for r, (t, fr) in enumerate(zip(times, rows)):
        for c, f in enumerate(fr):
            tile = Image.new("RGB", (width, h + LABEL_H))
            tile.paste(f.resize((width, h)), (0, LABEL_H))
            txt = f"{labels[c]}  {float(t):.2f} s"
            if c == len(fr) - 1 and len(fr) == 2:
                txt += f"   SSIM {scores[r]['ssim']:.2f}"
            sheet.paste(_label(tile, txt), (c * width, r * (h + LABEL_H)))
    sheet.save(out, quality=88)
    return scores


def main():
    ap = argparse.ArgumentParser(description="Contact sheets and side-by-side video comparison.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("video")
    s.add_argument("out")
    s.add_argument("--times", required=True)
    s.add_argument("--cols", type=int, default=3)
    s.add_argument("--width", type=int, default=480)
    c = sub.add_parser("compare")
    c.add_argument("out")
    c.add_argument("--times", required=True)
    c.add_argument("--video", action="append", required=True)
    c.add_argument("--label", action="append")
    c.add_argument("--offset", help="comma-separated clock shift per video (seconds)")
    c.add_argument("--width", type=int, default=480)
    c.add_argument("--json")
    a = ap.parse_args()
    times = [float(x) for x in a.times.split(",")]
    if a.cmd == "sheet":
        print(sheet_at(a.video, a.out, times, a.cols, a.width))
        return
    offs = [float(x) for x in a.offset.split(",")] if a.offset else None
    sc = compare(a.out, times, a.video, a.label, offs, a.width)
    for x in sc:
        print(f"{x['t']:8.2f} s  SSIM {x['ssim']:.3f}  mean |diff| {x['mad']:5.1f}")
    if sc:
        import statistics
        print(f"mean SSIM {statistics.mean(x['ssim'] for x in sc):.3f}")
    if a.json:
        Path(a.json).write_text(json.dumps(sc, indent=1), encoding="utf-8")
    print("->", a.out)


if __name__ == "__main__":
    main()
