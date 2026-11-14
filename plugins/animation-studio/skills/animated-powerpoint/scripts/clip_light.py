"""Light maps for the flat -> rounded shading of the figures (clip.py step "light", also used by scene.py)."""
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

LIGHT = np.array([-0.5, 0.6, 0.62]); LIGHT /= np.linalg.norm(LIGHT)       # from top left front
RIM = np.array([0.75, 0.35]); RIM /= np.linalg.norm(RIM)                  # rim light from the right back


def light_map(job):
    src, dst = job
    if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
        return
    a = np.asarray(Image.open(src))[..., 3].astype(np.float32) / 255
    sil = (a > 0.5).astype(np.float32)
    s = a.shape[0] / 1400.0
    b = ndi.gaussian_filter(sil, 26 * s) * 0.6 + ndi.gaussian_filter(sil, 9 * s) * 0.4
    b = b.astype(np.float32)
    gy, gx = np.gradient(b)
    k = 34.0 * s
    nx, ny, nz = -gx * k, gy * k, np.ones_like(b)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / n, ny / n, nz / n
    li = np.clip(1.0 + 1.1 * (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2] - LIGHT[2]), 0.55, 1.2)
    rim = np.clip(1 - nz, 0, 1) ** 0.8 * np.clip((nx * RIM[0] + ny * RIM[1]) / np.maximum(np.hypot(nx, ny), 1e-4), 0, 1)
    ao = 0.86 + 0.14 * np.clip((b - 0.25) / 0.6, 0, 1)
    out = np.dstack([li / 2, np.clip(rim, 0, 1), ao, np.ones_like(b)])
    Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA").save(dst)


def lights(C):
    jobs = []
    for f in C.p["figures"]:
        n = f["name"]
        (C.dir / "light" / n).mkdir(parents=True, exist_ok=True)
        jobs += [(p, C.dir / "light" / n / ("s." + p.name.split(".")[-2] + ".png"))
                 for p in sorted((C.dir / "frames" / n).glob(f"{n}.*.png"))]
    # bounded: every job holds ~25 full-size float arrays (all CPU threads at once ran out of RAM on 4 figures)
    with ThreadPoolExecutor(min(6, os.cpu_count() or 4)) as ex:
        list(ex.map(light_map, jobs))
    print(f"  light maps: {len(jobs)}")
