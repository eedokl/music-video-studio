"""Paint the background layers of a forest clearing in a painterly style (many soft brush dabs) - no GPU, no AI.

Result: <out>/01_sky.png, 02_far_trees.png, 03_mid_trees.png, 04_light_rays.png, 05_meadow_path.png,
06_foreground.png (RGBA, 1280x720) - a ready multiplane layer set (see multiplane.json in SKILL.md) that
krita_assemble.py can turn into a layered .kra for painting over by hand.
Ground line: y = 600 px (= -3.0 Synfig units with the default 16x9 view), horizon 455 px, sun top right.

Usage: uv run --no-project --with numpy --with pillow python paint_clearing.py --out layers [--seed 7]
The seed changes every dab (crowns, grass, flowers, clouds); seed 7 reproduces the reference clearing.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ap = argparse.ArgumentParser(description="Paint the layers of a forest clearing (multiplane set).")
ap.add_argument("--out", default="layers")
ap.add_argument("--seed", type=int, default=7)
args = ap.parse_args()

W, H = 1280, 720
HORIZON = 455          # back edge of the forest
GROUND_Y = 600         # where the character stands (y = -3.0 units)
SUN = (1010, -40)      # light from the top right
rng = np.random.default_rng(args.seed)
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def new_layer():
    return np.zeros((H, W, 4), np.float32)  # premultiplied RGBA


def dab(L, x, y, rx, ry, col, a=1.0, angle=0.0, soft=0.55):
    """One soft, slightly oval brush dab (premultiplied 'over')."""
    r = int(max(rx, ry) * 1.2) + 2
    x0, x1 = max(int(x) - r, 0), min(int(x) + r, W)
    y0, y1 = max(int(y) - r, 0), min(int(y) + r, H)
    if x0 >= x1 or y0 >= y1:
        return
    px, py = xx[y0:y1, x0:x1] - x, yy[y0:y1, x0:x1] - y
    c, s = np.cos(angle), np.sin(angle)
    u, v = (px * c + py * s) / rx, (-px * s + py * c) / ry
    d = np.sqrt(u * u + v * v)
    m = np.clip((1 - d) / soft, 0, 1) * a
    m = m * (0.85 + 0.15 * rng.random(m.shape, dtype=np.float32))  # bristle texture
    m = m[..., None]
    patch = L[y0:y1, x0:x1]
    patch[..., :3] = col * m + patch[..., :3] * (1 - m)
    patch[..., 3:] = m + patch[..., 3:] * (1 - m)


def jitter(col, amt=0.05):
    return np.clip(col + rng.normal(0, amt, 3).astype(np.float32), 0, 1)


def lit(col, light, nx, ny):
    """Dab colour by position: brighter top right (sun), darker bottom left."""
    k = np.clip(0.5 + 0.5 * (nx * 0.6 - ny * 0.8), 0, 1)
    return np.clip(col * (0.62 + 0.38 * k) + light * 0.32 * k ** 2, 0, 1)


def crown(L, cx, cy, rad, base, light, n=None, flat=1.0):
    """Tree crown from many dabs, light from the top right."""
    n = n or int(rad * 2.2)
    for _ in range(n):
        ang = rng.uniform(0, 2 * np.pi)
        rr = rad * np.sqrt(rng.random())
        nx, ny = np.cos(ang) * rr / rad, np.sin(ang) * rr / rad * flat
        x, y = cx + nx * rad, cy + ny * rad * flat
        size = rng.uniform(0.12, 0.26) * rad
        dab(L, x, y, size, size * rng.uniform(0.55, 0.9), jitter(lit(base, light, nx, ny), 0.035),
            rng.uniform(0.55, 0.9), rng.uniform(0, np.pi))


def save(L, name, blur=0.0):
    a = np.clip(L[..., 3:], 1e-6, 1)
    rgb = np.where(L[..., 3:] > 1e-6, L[..., :3] / a, 0)
    img = Image.fromarray((np.dstack([rgb, L[..., 3:]]) * 255).clip(0, 255).astype(np.uint8), "RGBA")
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    img.save(OUT / name)
    print("painted:", OUT / name)


LIGHT = hexrgb("#fff1c4")

# ---------------- 01 sky ----------------
L = new_layer()
t = (yy / HORIZON).clip(0, 1)[..., None]
L[..., :3] = hexrgb("#8fbfd6") * (1 - t) + hexrgb("#f4e7c3") * t
sund = np.sqrt((xx - SUN[0]) ** 2 + (yy - SUN[1]) ** 2)[..., None]
L[..., :3] = np.clip(L[..., :3] + hexrgb("#fff3c8") * np.exp(-sund / 380) * 0.45, 0, 1)
L[..., 3] = 1
for cx, cy, s in ((260, 90, 1.0), (640, 60, 0.7), (180, 210, 0.5)):
    for _ in range(int(60 * s)):
        dab(L, cx + rng.normal(0, 70 * s), cy + rng.normal(0, 14 * s), 40 * s, 22 * s,
            jitter(hexrgb("#fbf6ea"), 0.02), 0.35)
save(L, "01_sky.png", blur=1.5)

# ---------------- 02 far trees (cool, desaturated = aerial perspective) ----------------
L = new_layer()
far = hexrgb("#86a8a0")
for x in range(-40, W + 60, 34):
    top = HORIZON - 120 - 60 * np.sin(x / 140) - rng.uniform(0, 50)
    crown(L, x, top + 40, rng.uniform(45, 70), far, hexrgb("#d9e6d0"), flat=1.3)
    for y in np.arange(top + 60, HORIZON + 20, 18):
        dab(L, x + rng.normal(0, 10), y, 34, 22, jitter(far * 0.92, 0.02), 0.9)
save(L, "02_far_trees.png", blur=2.2)

# ---------------- 03 middle trees (frame the clearing) ----------------
L = new_layer()
trunk = hexrgb("#5a4030")
mid, mid_dark = hexrgb("#4f7d48"), hexrgb("#3d6440")
trees = [(70, 1.25), (230, 0.95), (1080, 1.0), (1230, 1.3), (390, 0.7), (930, 0.72)]
for tx, s in trees:
    base_y = HORIZON + 40 * s
    # trunk with a lit edge on the right
    for y in np.arange(base_y, 120 * (2 - s), -6):
        w = 16 * s * (1 + (base_y - y) / 900)
        dab(L, tx + rng.normal(0, 1.5), y, w, 7, jitter(trunk, 0.03), 0.95)
        dab(L, tx + w * 0.45, y, w * 0.35, 6, jitter(trunk * 1.45, 0.03), 0.6)
    # crown clouds
    for cx, cy, r in ((0, -330, 150), (-90, -250, 110), (90, -260, 115), (0, -190, 90), (-40, -400, 100)):
        crown(L, tx + cx * s, base_y + cy * s * (1.1 if s > 0.9 else 1.0), r * s,
              mid if s > 0.8 else mid * 1.08, LIGHT)
save(L, "03_mid_trees.png", blur=0.6)

# ---------------- 04 light rays ----------------
L = new_layer()
for k in range(5):
    x0 = 620 + k * 110 + rng.uniform(-30, 30)
    wdt = rng.uniform(30, 70)
    # band from top right diagonally down to the left
    dist = np.abs((xx - x0) + (yy - 0) * 0.55) - wdt
    fade = np.clip(1 - yy / 700, 0, 1)
    m = np.clip(-dist / 40, 0, 1) * fade * rng.uniform(0.10, 0.2)
    L[..., :3] = L[..., :3] * (1 - m[..., None]) + hexrgb("#fff2b8") * m[..., None]
    L[..., 3] = m + L[..., 3] * (1 - m)
save(L, "04_light_rays.png", blur=6)

# ---------------- 05 meadow with path ----------------
L = new_layer()
g_far, g_near = hexrgb("#9cbf6e"), hexrgb("#6f9a4c")
t = ((yy - HORIZON) / (H - HORIZON)).clip(0, 1)[..., None]
grass = g_far * (1 - t) + g_near * t
# clearing brighter in the middle (sun spot)
spot = np.exp(-(((xx - 700) / 420) ** 2 + ((yy - 600) / 140) ** 2))[..., None]
grass = np.clip(grass + LIGHT * spot * 0.22, 0, 1)
ground = (yy >= HORIZON + 12 * np.sin(xx / 90)).astype(np.float32)
L[..., :3] = grass * ground[..., None]
L[..., 3] = ground
# path: from the bottom centre, narrower towards the back
path_c = 640 + (yy - H) * -0.25 * 0 + 30 * np.sin(yy / 60)
half = 40 + (yy - HORIZON).clip(0) * 0.9
pm = np.clip((half - np.abs(xx - path_c)) / 25, 0, 1) * (yy > HORIZON + 30)
path_col = hexrgb("#d9c08a") * (0.9 + 0.1 * t[..., 0:1].squeeze()[..., None])
L[..., :3] = L[..., :3] * (1 - pm[..., None] * 0.85) + path_col * pm[..., None] * 0.85
# grass texture and flower dabs
for _ in range(2600):
    x, y = rng.uniform(0, W), rng.uniform(HORIZON + 10, H)
    if pm[int(y), int(x)] > 0.3:
        continue  # keep the path clear
    depth = (y - HORIZON) / (H - HORIZON)
    col = jitter((g_far * (1 - depth) + g_near * depth) * rng.uniform(0.85, 1.12), 0.03)
    dab(L, x, y, 3 + 9 * depth, 1.5 + 3 * depth, col, 0.5, rng.uniform(-0.4, 0.4))
for _ in range(160):
    x, y = rng.uniform(0, W), rng.uniform(HORIZON + 30, H)
    depth = (y - HORIZON) / (H - HORIZON)
    col = [hexrgb("#f6f1e4"), hexrgb("#f4cf5a"), hexrgb("#e9a3b8")][rng.integers(3)]
    dab(L, x, y, 2 + 4 * depth, 2 + 3 * depth, col, 0.9)
# contact shadows under the trees
for tx, s in trees:
    dab(L, tx, HORIZON + 10, 60 * s, 9 * s, hexrgb("#3f5a33"), 0.55, soft=1.0)
save(L, "05_meadow_path.png", blur=0.5)

# ---------------- 06 foreground (dark leaves in front of the character) ----------------
L = new_layer()
fg = hexrgb("#2f4c33")
for cx, cy, r in ((40, 720, 170), (190, 760, 120), (1250, 700, 190), (1100, 770, 110),
                  (60, -30, 160), (240, -60, 120), (1200, -40, 150)):
    crown(L, cx, cy, r, fg, hexrgb("#7aa067"), n=int(r * 3))
save(L, "06_foreground.png", blur=1.2)

