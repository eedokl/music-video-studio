# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""How long are the takes of a film and how much moves in them? One number per film, the same for every film -
made to compare a film with a reference video and with earlier films.

Every 0.2 s one frame at 96x54, grey, only the upper 33 rows (burned-in lyrics sit below); movement = mean absolute
difference to the frame before (0..255). A cut = a difference above 12 that is also 3x its neighbours' median.

  uv run film_motion.py film.mp4 [more.mp4 ...] [--json out.json] [--shots project.json]
  --shots: movement per section of that project (median inside each shot, the first 0.25 s after its cut left out)

Read the numbers with care: fast cutting, film grain and a camera moved in code raise the film's median without
anybody moving - compare films made the same way, and long takes shot by shot (--shots).
Measured 2026-11: a reference film of 7 s takes with walking, dancing and camera moves 13.7; the same film rebuilt
with LTX-2.3 long takes 7.5; earlier Claudia films (2-3 s takes) 3.7-8.4.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use()
from media import ffmpeg  # noqa: E402

STEP, W, H, ROWS, CUT = 0.2, 96, 54, 33, 12.0


def series(path):
    """Movement per 0.2 s step of a video -> np.array (len = steps - 1)."""
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-vf", f"fps={1 / STEP},scale={W}:{H}", "-pix_fmt",
                          "gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, H, W)[:, :ROWS].astype(np.float32)
    return np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))


def cuts_of(d):
    out = []
    for i, v in enumerate(d):
        near = np.concatenate([d[max(0, i - 4):i], d[i + 1:i + 5]])
        if v > CUT and len(near) and v > 3 * (np.median(near) + 0.3):
            out.append(i)
    return out


def measure(path):
    """dict(seconds, takes, take_mean_s, take_median_s, take_max_s, motion_median, motion_p90, still_share)."""
    d = series(path)
    if not len(d):
        return {"film": str(path), "seconds": 0.0, "takes": 0}
    cuts = cuts_of(d)
    inner = np.delete(d, cuts) if len(cuts) < len(d) else d
    lens = np.diff([0] + [c + 1 for c in cuts] + [len(d) + 1]) * STEP
    return {"film": str(path), "seconds": round((len(d) + 1) * STEP, 1), "takes": len(lens),
            "take_mean_s": round(float(lens.mean()), 2), "take_median_s": round(float(np.median(lens)), 2),
            "take_max_s": round(float(lens.max()), 1), "motion_median": round(float(np.median(inner)), 2),
            "motion_p90": round(float(np.percentile(inner, 90)), 2), "still_share": round(float((inner < 1.0).mean()), 2)}


def per_shot(path, sections):
    """[{name, from, to, motion}] - median movement inside each section of the film."""
    d = series(path)
    t = (np.arange(len(d)) + 1) * STEP
    rows = []
    for s in sections:
        m = (t > s["from"] + 0.25) & (t <= s["to"])
        rows.append({"name": s["name"], "from": s["from"], "to": s["to"],
                     "motion": round(float(np.median(d[m])), 2) if m.any() else None})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("films", nargs="+")
    ap.add_argument("--json")
    ap.add_argument("--shots", help="project.json: movement per section of the (first) film")
    a = ap.parse_args()
    res = [measure(f) for f in a.films]
    for r in res:
        print(json.dumps(r, ensure_ascii=False))
    if a.shots:
        secs = json.loads(Path(a.shots).read_text(encoding="utf-8")).get("sections") or []
        rows = per_shot(a.films[0], secs)
        res[0]["shots"] = rows
        for r in rows:
            print(f'  {r["name"]:8s} {r["from"]:7.2f}-{r["to"]:7.2f}  motion {r["motion"]}')
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
