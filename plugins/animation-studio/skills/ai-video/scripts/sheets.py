# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "opencv-python-headless==5.0.0.93", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Contact sheets for choosing and reviewing AI material: one row per image or clip (clips: start / middle / end frame),
labelled with the file name and an optional note (e.g. the lip score or the canon check).

  uv run sheets.py out.jpg a.png b.mp4 ...
  from sheets import sheet; sheet("sheet.jpg", [("ai/lipsync/s02_v1_s1.mp4", "r 0.59 lag 0"), ...])
Rows are split into several sheets of `per_sheet` rows (out_1.jpg, out_2.jpg, ...).
"""
import sys
from pathlib import Path

from cvio import imread, video_capture  # noqa: E402  (same folder; unicode-safe cv2 file access)

THUMB_W = 384


def _frames(path, n=3):
    import cv2
    path = Path(path)
    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        im = imread(path)
        return [im] if im is not None else []
    cap = video_capture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    for u in ([0.05, 0.5, 0.95] if n == 3 else [i / max(n - 1, 1) for i in range(n)]):
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(total - 1, int(u * total)))
        ok, f = cap.read()
        if ok:
            out.append(f)
    return out


def sheet(out, rows, per_sheet=8, cols=3):
    """rows = [(path, note), ...] -> list of written sheet files."""
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    th = int(THUMB_W * 9 / 16)
    written = []
    chunks = [rows[i:i + per_sheet] for i in range(0, len(rows), per_sheet)] or [[]]
    for ci, chunk in enumerate(chunks):
        img = Image.new("RGB", (cols * THUMB_W, len(chunk) * (th + 28)), (20, 20, 24))
        d = ImageDraw.Draw(img)
        for ri, (path, note) in enumerate(chunk):
            y = ri * (th + 28)
            d.text((6, y + 4), f"{Path(path).name}   {note or ''}", font=font, fill=(235, 230, 220))
            for k, f in enumerate(_frames(path, cols)[:cols]):
                t = Image.fromarray(cv2.cvtColor(cv2.resize(f, (THUMB_W, th)), cv2.COLOR_BGR2RGB))
                img.paste(t, (k * THUMB_W, y + 28))
        o = Path(out) if len(chunks) == 1 else Path(out).with_name(f"{Path(out).stem}_{ci + 1}{Path(out).suffix}")
        o.parent.mkdir(parents=True, exist_ok=True)
        img.save(o, quality=88)
        written.append(o)
    return written


def shot_sheet(video, shots, out, offset=0.0, us=(0.2, 0.5, 0.8), per_sheet=10):
    """Finished film -> one row per shot with frames at 20/50/80 % of the shot.
    shots = [(t0, t1, label), ...] in the video's time (+ offset: video time = song time - offset)."""
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    cap = video_capture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    th = int(THUMB_W * 9 / 16)
    written = []
    chunks = [shots[i:i + per_sheet] for i in range(0, len(shots), per_sheet)]
    for ci, chunk in enumerate(chunks):
        img = Image.new("RGB", (len(us) * THUMB_W, len(chunk) * (th + 28)), (20, 20, 24))
        d = ImageDraw.Draw(img)
        for ri, (t0, t1, label) in enumerate(chunk):
            y = ri * (th + 28)
            d.text((6, y + 4), f"{label}   {t0:.2f}-{t1:.2f} s", font=font, fill=(235, 230, 220))
            for k, u in enumerate(us):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(round((t0 + u * (t1 - t0) - offset) * fps)))
                ok, f = cap.read()
                if ok:
                    img.paste(Image.fromarray(cv2.cvtColor(cv2.resize(f, (THUMB_W, th)), cv2.COLOR_BGR2RGB)),
                              (k * THUMB_W, y + 28))
        o = Path(out) if len(chunks) == 1 else Path(out).with_name(f"{Path(out).stem}_{ci + 1}{Path(out).suffix}")
        o.parent.mkdir(parents=True, exist_ok=True)
        img.save(o, quality=88)
        written.append(o)
    return written


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    for w in sheet(sys.argv[1], [(p, "") for p in sys.argv[2:]]):
        print("->", w)
