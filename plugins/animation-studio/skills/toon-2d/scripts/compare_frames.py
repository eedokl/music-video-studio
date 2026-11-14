"""Compare two renders frame by frame: side-by-side contact sheet + difference numbers (reference tests, retakes).

Usage:
  uv run --no-project --with pillow --with numpy python compare_frames.py <A> <B> --frames 0,15,36 [--out cmp.png]
         [--labels reference,rebuild]
A / B: an image sequence pattern (frames/f.%04d.png) or a video file (mp4/gif; frames are extracted with ffmpeg).
Output: a sheet with one row per frame (A | B | amplified difference) and per frame the mean absolute difference
(0-255) and the share of pixels that differ by more than 24 levels. Also the frame counts of A and B.
Rule of thumb: mean < 2 and changed < 2 % = the same picture; mean 2-8 = small shifts (text rendering, antialias,
grain); higher = a visibly different pose or timing.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402


def frames_of(src, tmp):
    """-> (function n -> PIL image or None, frame count)."""
    s = str(src)
    if "%" in s:
        folder = Path(s).parent
        prefix = Path(s).name.split("%")[0]
        n = len([p for p in folder.glob(prefix + "*") if p.suffix.lower() in (".png", ".jpg")])
        return (lambda i: Image.open(s % i).convert("RGB") if Path(s % i).exists() else None), n
    out = Path(tmp) / (Path(s).stem + "_%04d.png")
    subprocess.run([config.need("ffmpeg"), "-v", "error", "-y", "-i", s, "-start_number", "0", str(out)], check=True)
    n = len(list(Path(tmp).glob(Path(s).stem + "_*.png")))
    return (lambda i: Image.open(str(out) % i).convert("RGB") if Path(str(out) % i).exists() else None), n


def diff(a, b):
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    x, y = np.asarray(a, np.int16), np.asarray(b, np.int16)
    d = np.abs(x - y)
    return float(d.mean()), float((d.max(axis=2) > 24).mean() * 100), Image.fromarray(np.clip(d * 4, 0, 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser(description="Side-by-side comparison of two renders.")
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--frames", required=True, help="comma list of frame numbers")
    ap.add_argument("--out", default="compare.png")
    ap.add_argument("--labels", default="A,B")
    ap.add_argument("--width", type=int, default=480, help="tile width")
    a = ap.parse_args()
    la, lb = (a.labels.split(",") + ["B"])[:2]
    with tempfile.TemporaryDirectory() as tmp:
        ta, tb = Path(tmp) / "a", Path(tmp) / "b"
        ta.mkdir()
        tb.mkdir()
        fa, na = frames_of(a.a, ta)
        fb, nb = frames_of(a.b, tb)
        print(f"frames: {la} {na}, {lb} {nb}")
        rows, stats = [], []
        for f in [int(x) for x in a.frames.split(",") if x.strip()]:
            A, B = fa(f), fb(f)
            if A is None or B is None:
                print(f"f{f}: missing in {'A' if A is None else 'B'}")
                continue
            m, changed, D = diff(A, B)
            stats.append((f, m, changed))
            w = a.width
            h = int(A.height * w / A.width)
            row = Image.new("RGB", (3 * w + 20, h + 26), (30, 30, 30))
            for k, im in enumerate((A, B.resize(A.size), D)):
                row.paste(im.resize((w, h), Image.LANCZOS), (k * (w + 10), 26))
            ImageDraw.Draw(row).text((6, 6), f"f{f}   {la} | {lb} | diff x4    mean {m:.1f}  changed {changed:.1f} %",
                                     fill=(255, 255, 255))
            rows.append(row)
            print(f"f{f}: mean abs diff {m:.2f}, changed pixels {changed:.2f} %")
    if not rows:
        sys.exit("no frames to compare")
    sheet = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)), (30, 30, 30))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(a.out)
    if stats:
        print(f"overall: mean {np.mean([s[1] for s in stats]):.2f}, changed {np.mean([s[2] for s in stats]):.2f} % -> {a.out}")


if __name__ == "__main__":
    main()
