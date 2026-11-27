# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Where does a multi-shot clip cut - and is it a hard cut or a dissolve?

A video model asked for "a hard cut" sometimes fades from one shot into the next (or through black) instead. On small
grey frames a hard cut is ONE big jump of the frame-to-frame difference; a dissolve is a run of middling differences.

  uv run cut_check.py clip.mp4 [more.mp4 ...] [--json]
  uv run cut_check.py clip.mp4 --harden [-o clip_hc.mp4]     replace the dissolve by a hard cut

--harden keeps the clip's length and timing: the blended frames of the first half show the last clean frame of shot 1,
those of the second half the first clean frame of shot 2 (a few frames stand still on each side - use it where nobody
speaks at the cut). The clip's .json (clips.py meta) is copied; a clip that already cuts hard is copied unchanged.

Measured 2026-11 (LTX-2.5, two people in a car): hard cuts peak at 66-75, the frames around them at 0-3; dissolves
ran 8-11 frames at 5-10 each, a fade through black 23 frames. Of 17 takes with a cut 4 dissolved (all in the first batch).
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use()
from media import ffmpeg  # noqa: E402

W, H = 64, 36
HARD = 25.0          # one frame-to-frame difference above this = a hard cut
SOFT = 2.5           # differences above this that stand next to each other = a dissolve (still frames: 0-2)
REACH = 30           # frames around the strongest change that may belong to it


def differences(path):
    """Mean absolute difference between neighbouring frames (grey, 64x36) -> np.array of len frames - 1."""
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo",
                          "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, H * W).astype(np.float32)
    return np.abs(np.diff(f, axis=0)).mean(1)


def find(path, fps=24):
    """-> {"kind": "hard" | "dissolve" | "none", "frame": first frame of shot 2 (hard) or middle of the dissolve,
    "t": seconds, "peak", "first", "last": the blended frames of a dissolve (inclusive), "frames"}.
    A dissolve is found by how far the picture moved away from the frames before it, so a fade through black counts."""
    d = differences(path)
    if not len(d):
        return {"kind": "none", "frames": 1}
    k = int(d.argmax())
    if d[k] >= HARD:
        return {"kind": "hard", "frame": k + 1, "t": round((k + 1) / fps, 3), "peak": round(float(d[k]), 1), "frames": len(d) + 1}
    # the longest run of raised differences near the strongest one
    lo = hi = k
    while lo > max(0, k - REACH) and d[lo - 1] > SOFT:
        lo -= 1
    while hi < min(len(d) - 1, k + REACH) and d[hi + 1] > SOFT:
        hi += 1
    if hi - lo + 1 < 3 or d[lo:hi + 1].sum() < HARD:
        return {"kind": "none", "peak": round(float(d[k]), 1), "frames": len(d) + 1}
    first, last = lo + 1, hi                          # frames that are a blend of both shots
    return {"kind": "dissolve", "frame": (first + last + 1) // 2, "t": round((first + last + 1) / 2 / fps, 3),
            "peak": round(float(d[k]), 1), "first": first, "last": last, "frames": len(d) + 1}


def harden(path, out=None, fps=24):
    """Replace a dissolve by a hard cut -> out (default <clip>_hc.mp4). Returns (out, the find() result of the source)."""
    path = Path(path)
    out = Path(out) if out else path.with_name(path.stem + "_hc" + path.suffix)
    r = find(path, fps)
    meta = path.with_suffix(".json")
    if r["kind"] != "dissolve":
        if out != path:
            shutil.copy2(path, out)
    else:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(path), "-start_number", "0", str(d / "i%05d.png")], check=True)
            a, b, mid = r["first"] - 1, r["last"] + 1, r["frame"]
            for n in range(r["frames"]):
                src = a if r["first"] <= n < mid else b if mid <= n <= r["last"] else n
                shutil.copy(d / f"i{min(src, r['frames'] - 1):05d}.png", d / f"o{n:05d}.png")
            subprocess.run([ffmpeg(), "-y", "-v", "error", "-framerate", str(fps), "-start_number", "0", "-i", str(d / "o%05d.png"),
                            "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(out)], check=True)
    if meta.exists() and out != path:
        m = json.loads(meta.read_text(encoding="utf-8"))
        if r["kind"] == "dissolve":
            m["hardened"] = {"from": path.name, "first": r["first"], "last": r["last"], "cut": r["frame"]}
        out.with_suffix(".json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return out, r


def line(path, r):
    if r["kind"] == "hard":
        return f"{Path(path).name:28s} hard cut at frame {r['frame']} ({r['t']:.2f} s), peak {r['peak']:.0f}"
    if r["kind"] == "dissolve":
        return (f"{Path(path).name:28s} DISSOLVE frames {r['first']}-{r['last']} (middle {r['t']:.2f} s), peak {r['peak']:.0f}"
                "  -> --harden, or another seed")
    return f"{Path(path).name:28s} no cut found (strongest change {r.get('peak', 0):.0f})"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--json", action="store_true", help="print the results as JSON")
    ap.add_argument("--harden", action="store_true", help="write a copy with the dissolve replaced by a hard cut")
    ap.add_argument("-o", "--out", help="with --harden and ONE clip: the output file")
    a = ap.parse_args()
    if a.out and len(a.clips) != 1:
        raise SystemExit("-o takes one clip")
    res = {}
    for c in a.clips:
        if a.harden:
            out, r = harden(c, a.out, a.fps)
            res[c] = dict(r, out=str(out))
            if not a.json:
                print(line(c, r) + (f"\n  -> {out}" if r["kind"] == "dissolve" else "  (copied unchanged)"))
        else:
            r = res[c] = find(c, a.fps)
            if not a.json:
                print(line(c, r))
    if a.json:
        print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
