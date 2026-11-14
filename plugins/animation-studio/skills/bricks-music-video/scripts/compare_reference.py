# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==13.0.0"]
# ///
"""Side-by-side sheet: frames of this project next to a reference render at the same song times (reference tests).

  uv run compare_reference.py --ours "scenes/verse3/f.{:04d}.png" \
      --ref "<reference>/frames/f_{:04d}.png" --ref-shift 0 --times 1.0,2.9,6.6 -o compare.jpg [--project .]
--times are project seconds; our frame = round(t * fps); reference frame = round((t + ref-shift) * fps), so ref-shift is
how many seconds the reference frame 0 lies BEFORE our time 0 (negative) or after. Each row: time, lyric word, ours, ref.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for f in ("C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--ref-shift", type=float, default=0.0)
    ap.add_argument("--times", required=True)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--project", default=".")
    ap.add_argument("--labels", default="plugin,reference")
    ap.add_argument("--width", type=int, default=560)
    ap.add_argument("-o", "--out", default="compare.jpg")
    a = ap.parse_args()
    times = [float(x) for x in a.times.split(",")]
    words = []
    sheet = Path(a.project) / "analysis" / "song_sheet.json"
    if sheet.exists():
        words = json.loads(sheet.read_text(encoding="utf-8"))["words"]
    w = a.width
    h = int(w * 9 / 16)
    head = 34
    sheet_img = Image.new("RGB", (120 + 2 * w + 30, head + len(times) * (h + 10)), (24, 24, 28))
    d = ImageDraw.Draw(sheet_img)
    lo, hi = a.labels.split(",")
    d.text((130, 6), lo, font=font(20), fill=(240, 240, 240))
    d.text((140 + w + 10, 6), hi, font=font(20), fill=(240, 240, 240))
    for i, t in enumerate(times):
        y = head + i * (h + 10)
        word = next((x["word"] for x in reversed(words) if x["t"] <= t + 0.02), "")
        d.text((8, y + 8), f"{t:.2f} s", font=font(18), fill=(255, 210, 63))
        d.text((8, y + 34), word[:12], font=font(16), fill=(200, 200, 200))
        for k, (pat, tt) in enumerate(((a.ours, t), (a.ref, t + a.ref_shift))):
            f = int(round(tt * a.fps))
            p = Path(pat.format(f))
            if p.exists():
                im = Image.open(p).convert("RGB").resize((w, h), Image.LANCZOS)
                sheet_img.paste(im, (120 + k * (w + 10), y))
            else:
                d.rectangle([120 + k * (w + 10), y, 120 + k * (w + 10) + w, y + h], outline=(120, 40, 40))
                d.text((130 + k * (w + 10), y + h // 2), f"missing frame {f}", font=font(16), fill=(220, 120, 120))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    sheet_img.save(a.out, quality=88)
    print(f"-> {a.out} ({len(times)} rows)")


if __name__ == "__main__":
    main()
