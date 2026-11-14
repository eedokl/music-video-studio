"""Spread a Synfig scene over all CPU cores: split the frame range into chunks and render them at the same time.

Synfig uses only ~1.5 cores per run (measured: 1.6 of 20 on an i5-14600K) - 8 runs in parallel take as long
as 4. Hence: N chunks (default: cores/2) with --begin-time/--end-time, each into its own subfolder,
then moved into the target folder as f.0000.png ... (same names as a normal Synfig run).

Usage: uv run --no-project python synfig_parallel.py scene.sif target_folder [--pattern f.png] [--jobs 10]
       [--width W] [--height H]   (default: the canvas size of the .sif - never stretches)
Several scenes queued one after another do not share the cores - to render several scenes
at the same time, lower --jobs per scene instead.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402


def frame_count(sif):
    head = Path(sif).read_text(encoding="utf-8", errors="replace")[:4000]
    m = re.search(r'end-time="(\d+)f?"', head) or re.search(r'end-time="([\d.]+)s"', head)
    fps = float(re.search(r'fps="([\d.]+)"', head).group(1)) if re.search(r'fps="([\d.]+)"', head) else 24.0
    if not m:
        sys.exit("end-time not found")
    v = m.group(1)
    return (int(v) if "s" not in m.group(0) else round(float(v) * fps)) + 1, fps


def main():
    ap = argparse.ArgumentParser(description="Render a Synfig scene in parallel chunks.")
    ap.add_argument("sif")
    ap.add_argument("out")
    ap.add_argument("--pattern", default="f.png", help="output file pattern (Synfig adds .0000 etc.)")
    ap.add_argument("--jobs", type=int, default=max(2, (os.cpu_count() or 8) // 2))
    ap.add_argument("--width", type=int, help="default: the canvas width in the .sif")
    ap.add_argument("--height", type=int, help="default: the canvas height in the .sif")
    a = ap.parse_args()
    if not (a.width and a.height):                      # take the size from the canvas, never stretch
        head = Path(a.sif).read_text(encoding="utf-8", errors="replace")[:4000]
        mw, mh = re.search(r'<canvas[^>]*\bwidth="(\d+)"', head), re.search(r'<canvas[^>]*\bheight="(\d+)"', head)
        a.width = a.width or (int(mw.group(1)) if mw else 1280)
        a.height = a.height or (int(mh.group(1)) if mh else 720)
    synfig = config.need("synfig")
    n, fps = frame_count(a.sif)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem, ext = Path(a.pattern).stem, Path(a.pattern).suffix
    for old in out.glob(f"{stem}.*{ext}"):
        old.unlink()
    jobs = min(a.jobs, max(1, n // 12))                     # chunks not smaller than ~12 frames
    cuts = [round(i * n / jobs) for i in range(jobs + 1)]
    tmp = out / "_parts"
    shutil.rmtree(tmp, ignore_errors=True)

    def run(k):
        a0, a1 = cuts[k], cuts[k + 1] - 1
        d = tmp / f"{k:02d}"
        d.mkdir(parents=True)
        r = subprocess.run([synfig, a.sif, "-t", "png", "-o", str(d / a.pattern), "-w", str(a.width), "-h", str(a.height),
                            "-q", "--begin-time", f"{a0}", "--end-time", f"{a1}"], capture_output=True, text=True,
                           errors="replace")
        files = sorted(d.glob(f"{stem}.*{ext}"))
        if len(files) != a1 - a0 + 1:
            raise RuntimeError(f"Chunk {k} ({a0}-{a1}): {len(files)} instead of {a1 - a0 + 1} frames\n{r.stderr[-800:]}")
        return k, a0, files

    t0 = time.time()
    with ThreadPoolExecutor(jobs) as ex:
        results = list(ex.map(run, range(jobs)))
    for k, a0, files in results:
        for i, f in enumerate(files):
            f.replace(out / f"{stem}.{a0 + i:04d}{ext}")
    shutil.rmtree(tmp, ignore_errors=True)
    got = len(list(out.glob(f"{stem}.*{ext}")))
    if got != n:
        sys.exit(f"ERROR: {got} instead of {n} frames")
    print(f"{Path(a.sif).name}: {n} frames in {time.time() - t0:.0f} s ({jobs} chunks in parallel) -> {out}")


if __name__ == "__main__":
    main()
