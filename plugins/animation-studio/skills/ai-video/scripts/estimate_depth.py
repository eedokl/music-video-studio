# Runs in the configured gpu_python (CUDA venv); without it run() falls back to `uv run --with ...` on the CPU - no PEP 723 header.
"""Depth maps from flat images (Depth Anything V2) - for parallax / relief on stills (2.5D camera moves, Ken Burns
with depth, multiplane comic flights).

Usage (needs torch + transformers: the configured gpu_python, or uv on the CPU):
  <gpu_python> estimate_depth.py <image> [<image> ...] [--edgefix 7] [--model small|base|large] [--out-dir DIR]
  uv run --no-project --with transformers --with torch --with pillow --with numpy python estimate_depth.py img.png
From Python (any interpreter):  _studio.use("ai-video"); import estimate_depth; estimate_depth.run([img, ...])
Result per image: <image>_depth.png (bright = near, same size as the image), or in --out-dir.
--edgefix R (default 7, 0 = off): grow near areas by R pixels and soften them, so that ink outlines belong entirely
to the figure - otherwise the relief smears them during camera moves.
Model: depth-anything/Depth-Anything-V2-Small-hf (Apache-2.0, commercial use allowed; Base/Large are non-commercial).
First run downloads ~100 MB into hf_home (config); then ~0.5-1 s per image. Takes the GPU lock ("depth:<model>").
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402

HERE = Path(__file__).resolve()


def run(images, edgefix=7, model="small", out_dir=None):
    """Run this script in the configured GPU python (falls back to uv on the CPU). Returns the depth-map paths."""
    py = config.get("gpu_python")
    cmd = ([py] if py and Path(py).exists() else
           ["uv", "run", "--no-project", "--with", "transformers", "--with", "torch", "--with", "pillow", "--with", "numpy",
            "python"])
    cmd += [str(HERE), *map(str, images), "--edgefix", str(edgefix), "--model", model]
    if out_dir:
        cmd += ["--out-dir", str(out_dir)]
    subprocess.run(cmd, check=True)
    return [_target(Path(i), out_dir) for i in images]


def _target(src, out_dir):
    return (Path(out_dir) if out_dir else src.parent) / (src.stem + "_depth.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+")
    ap.add_argument("--edgefix", type=int, default=7)
    ap.add_argument("--model", default="small", choices=["small", "base", "large"],
                    help="small (default, Apache-2.0); base/large = finer edges, non-commercial licence")
    ap.add_argument("--out-dir")
    a = ap.parse_args()
    config.setup_env()                                  # hf_home -> HF_HOME before transformers is imported
    from gpu_lock import acquire
    acquire("estimate_depth", model="depth:" + a.model)
    t0 = time.time()
    import numpy as np
    import torch
    from PIL import Image, ImageFilter
    from transformers import pipeline
    dev = 0 if torch.cuda.is_available() else "cpu"
    pipe = pipeline("depth-estimation", model=f"depth-anything/Depth-Anything-V2-{a.model.capitalize()}-hf", device=dev,
                    torch_dtype=torch.float16 if dev == 0 else None)
    print(f"Depth Anything V2 {a.model} on {'GPU' if dev == 0 else 'CPU'}, loaded in {time.time() - t0:.1f} s", flush=True)
    for arg in a.images:
        src = Path(arg)
        img = Image.open(src).convert("RGB")
        t = time.time()
        d = np.asarray(pipe(img)["predicted_depth"].squeeze().float().cpu().numpy(), dtype=np.float32)   # large = near
        d = (d - d.min()) / (d.max() - d.min() + 1e-6)
        dimg = Image.fromarray((d * 255).astype(np.uint8)).resize(img.size, Image.BICUBIC)
        if a.edgefix > 0:
            dimg = dimg.filter(ImageFilter.MaxFilter(2 * a.edgefix + 1)).filter(ImageFilter.GaussianBlur(a.edgefix * 0.4))
        dst = _target(src, a.out_dir)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dimg.save(dst)
        print(f"{src.name} -> {dst.name} ({time.time() - t:.2f} s)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
