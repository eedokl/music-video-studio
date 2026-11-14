"""Make new film looks, iris transition masks and effect galleries with Shaders (WebGPU effect library, npm
`shaders` 4.0.6, MIT) - rendered frame-exact in headless Edge/Chrome.

Jobs:
  look     a new look overlay set from a JSON preset -> assets/look/<name>/ (or --out DIR): mp_0000.jpg ... + look.json,
           directly usable by `apply_look.py --look <name>` (or `--look DIR`)
  iris     iris-wipe masks (white = picture visible, black = covered) with centre and progress keys -> m_0000.png ...
           (--numpy = the pure numpy twin, no GPU). In Python: iris_masks(center, frames, size) -> float32 arrays,
           the optional mask provider for {"kind": "iris"} transitions (transitions.py)
  gallery  one picture through N effects for choosing -> g_00_<Effect>.png ... + gallery.png (labelled sheet)
  catalog  catalog.json + shaders-catalog.md of every effect in the installed package (make_catalog.mjs)

Usage (run with: uv run --no-project --with numpy --with pillow python shaders_render.py ...):
  shaders_render.py look  --preset my_look.json --name dusk [--frames 24] [--quality 92] [--out DIR]
  shaders_render.py look  --preset "${CLAUDE_PLUGIN_ROOT}/skills/film-finish/assets/look/standard/look.json" --out x
  shaders_render.py iris  --out DIR [--center 0.5,0.5] [--frames 12] [--direction close|open] [--feather 0.02]
  shaders_render.py gallery --image frame.png --out DIR [--effects effects.json]
  shaders_render.py catalog --out DIR
  shaders_render.py --install            (one-time, only after the user agreed: npm install of shaders@4.0.6)

The npm package is NOT bundled. It lives in the folder of the config key "shaders" (env ANIMATION_STUDIO_SHADERS, or
`check_tools.py --set shaders=DIR`; default ~/.animation-studio/shaders), or --shaders-dir DIR; that folder holds
node_modules/shaders. Programs: config "node" (node + npm), "browser" (Edge/Chrome; "chrome" as fallback).

A look preset is {"components": [...], "frames": 24, "description": "..."} - the same format as look.json.
Pitfalls built in: window.process shim, html/body exactly the canvas size, --force-device-scale-factor=1,
--window-size, --enable-unsafe-webgpu, FilmGrain needs "bias": 0 on a white overlay (warned), and the browser
tree is killed only by its own temporary profile folder.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("toon-2d")
import config  # noqa: E402

HERE = Path(__file__).resolve().parent
PAGE_DIR = HERE / "shaders"
LOOKS = HERE.parent / "assets" / "look"
SERVER = _studio.skill_dir("toon-2d") / "scripts" / "multiplane" / "server.mjs"
VERSION = "4.0.6"
W, H, FPS = 1280, 720, 24

# default gallery: the effects that fit classical 2D films, one each over the same picture
IMG = {"type": "ImageTexture", "props": {"url": "$IMAGE"}}
GALLERY = [
    ["Original", []],
    ["Paper", [{"type": "Paper", "props": {"roughness": 0.7, "grainScale": 1.3, "displacement": 0.12, "seed": 3}}]],
    ["FilmGrain", [{"type": "FilmGrain", "props": {"strength": 0.45, "bias": 0, "animated": True}}]],
    ["FilmStock", [{"type": "FilmStock", "props": {"strength": 1, "halation": 0.6}}]],
    ["Vignette", [{"type": "Vignette", "props": {"color": "#1a1008", "radius": 0.55, "falloff": 0.55, "intensity": 0.9}}]],
    ["Halation", [{"type": "Halation", "props": {}}]],
    ["LightLeak", [{"type": "LightLeak", "props": {"intensity": 0.45, "spread": 0.6}}]],
    ["Watercolor", [{"type": "Watercolor", "props": {"radius": 4, "bleed": 1, "strength": 1, "paper": 0.45}}]],
    ["Glow", [{"type": "Glow", "props": {"intensity": 1.2, "threshold": 0.55, "size": 30}}]],
    ["Godrays", [{"type": "Godrays", "props": {"center": {"x": 0.78, "y": 0}, "density": 0.35, "intensity": 0.55,
                                               "rayColor": "#fff2c0"}}]],
    ["BokehBlur", [{"type": "BokehBlur", "props": {"radius": 18}}]],
    ["TiltShift", [{"type": "TiltShift", "props": {"intensity": 45, "width": 0.25, "center": {"x": 0.5, "y": 0.75}}}]],
    ["Halftone", [{"type": "Halftone", "props": {}}]],
    ["Engraving", [{"type": "Engraving", "props": {}}]],
    ["Posterize", [{"type": "Posterize", "props": {}}]],
    ["IrisWipe", "iris"],
]


# ---------------------------------------------------------------- package + programs

def shaders_dir(arg=None):
    return Path(arg or config.get("shaders") or (Path.home() / ".animation-studio" / "shaders")).expanduser().resolve()


def package_ok(d):
    return (d / "node_modules" / "shaders" / "dist" / "core" / "index.js").exists()


def node_exe():
    n = config.get("node") or shutil.which("node")
    if not n:
        raise SystemExit("node not found - install Node.js or set the config key 'node' (check_tools.py --set node=PATH)")
    return n


def find_browser():
    from render_multiplane import find_browser as fb      # toon-2d: config "browser", PATH, usual install folders
    b = config.get("browser")
    if not (b and Path(b).exists()):
        c = config.get("chrome")
        if c and Path(c).exists():
            return c
    return fb()


def install(d):
    """npm install of the pinned package into d - only call this after the user agreed."""
    node = node_exe()
    npm = next((str(p) for p in (Path(node).parent / "npm.cmd", Path(node).parent / "npm") if p.exists()),
               shutil.which("npm"))
    if not npm:
        raise SystemExit("npm not found next to node or on PATH")
    print(f"Installing npm package shaders@{VERSION} (MIT, ~40 MB with its dependencies typegpu, typed-binary, tinyest,\n"
          f"tsover-runtime) from the npm registry into {d}")
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(PAGE_DIR / "package.json", d / "package.json")
    r = subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=d)
    if r.returncode != 0 or not package_ok(d):
        raise SystemExit("npm install failed")
    print(f"ok - set it once with: check_tools.py --set shaders={d}  (or env ANIMATION_STUDIO_SHADERS)")


def need_package(d):
    if package_ok(d):
        return
    raise SystemExit(
        f"The Shaders npm package is not installed in {d}.\n"
        f"It is optional (only for NEW looks / transition masks; the standard look ships as frames).\n"
        f"Ask the user, then run:  shaders_render.py --install [--shaders-dir DIR]\n"
        f"That downloads shaders@{VERSION} (MIT, ~40 MB incl. typegpu) from the npm registry into that folder.")


def kill_tree(proc, marker):
    from render_multiplane import kill_tree as kt           # only processes with OUR profile folder
    kt(proc, marker)


def free_port():
    from render_multiplane import free_port as fp
    return fp()


# ---------------------------------------------------------------- one job in the browser

def run_job(items, out, d=None, size=(W, H), timeout=300):
    """Render job items (see render.html) -> PNGs in out. Returns the page log; raises SystemExit on failure."""
    d = shaders_dir(d)
    need_package(d)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    jid = "_job_" + uuid.uuid4().hex[:10]
    jdir = d / jid                                       # served from the package folder: /node_modules/... resolves
    jdir.mkdir()
    shutil.copy(PAGE_DIR / "render.html", jdir / "render.html")
    files = {}
    for it in items:                                     # images referenced as local paths -> copied next to the page
        for c in (it.get("preset") or {}).get("components", []):
            _localize(c, jdir, jid, files)
    (jdir / "job.json").write_text(json.dumps({"width": size[0], "height": size[1], "fps": FPS, "items": items}),
                                   encoding="utf-8")
    html = (jdir / "render.html").read_text(encoding="utf-8").replace("1280px", f"{size[0]}px").replace(
        "720px", f"{size[1]}px").replace('width="1280"', f'width="{size[0]}"').replace('height="720"', f'height="{size[1]}"')
    (jdir / "render.html").write_text(html, encoding="utf-8")

    port = free_port()
    srv = subprocess.Popen([node_exe(), str(SERVER), str(d), str(out), str(port)], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, errors="replace")
    time.sleep(0.8)
    prof = tempfile.mkdtemp(prefix="shaders_browser_")
    url = f"http://127.0.0.1:{port}/{jid}/render.html?job=/{jid}/job.json"
    br = subprocess.Popen([find_browser(), "--headless=new", f"--user-data-dir={prof}", "--no-first-run",
                           "--disable-extensions", "--enable-unsafe-webgpu", "--force-device-scale-factor=1",
                           f"--window-size={size[0]},{size[1]}", url],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        log, _ = srv.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        srv.kill()
        log, _ = srv.communicate()
        log = (log or "") + f"\nERROR: timeout after {timeout} s (page: {url})"
    finally:
        kill_tree(br, prof)
        time.sleep(0.5)
        shutil.rmtree(prof, ignore_errors=True)
        shutil.rmtree(jdir, ignore_errors=True)
    missing = [it["name"] for it in items if not (out / it["name"]).exists()]
    if "ERROR" in log or missing:
        raise SystemExit(f"Shaders job failed ({len(missing)} of {len(items)} frames missing):\n{log.strip()[-2000:]}")
    return log


def _localize(comp, jdir, jid, files):
    url = (comp.get("props") or {}).get("url")
    if url and not url.startswith(("http:", "https:", "data:")) and Path(url).is_file():
        src = Path(url).resolve()
        if src not in files:
            files[src] = f"img{len(files)}{src.suffix.lower()}"
            shutil.copy(src, jdir / files[src])
        comp["props"]["url"] = f"/{jid}/{files[src]}"
    for ch in comp.get("children", []) or []:
        _localize(ch, jdir, jid, files)


# ---------------------------------------------------------------- jobs

def look(a):
    preset = json.loads(Path(a.preset).read_text(encoding="utf-8"))
    comps = preset["components"]
    for c in comps:
        if c.get("type") == "FilmGrain" and (c.get("props") or {}).get("bias", 2) != 0:
            print("warning: FilmGrain without \"bias\": 0 puts the grain only into dark areas - invisible on a white "
                  "overlay")
    n = a.frames or preset.get("frames", 24)
    name = a.name or Path(a.preset).stem
    out = Path(a.out).resolve() if a.out else LOOKS / name
    tmp = Path(tempfile.mkdtemp(prefix="shaders_look_"))
    items = [{"name": f"mp_{i:04d}.png", "preset": {"components": comps} if i == 0 else None} for i in range(n)]
    t0 = time.time()
    log = run_job(items, tmp, a.shaders_dir)
    from PIL import Image
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("mp_*.jpg"):
        p.unlink()
    for i in range(n):
        im = Image.open(tmp / f"mp_{i:04d}.png").convert("RGB")
        im.save(out / f"mp_{i:04d}.jpg", quality=a.quality)
        if a.keep_png:
            shutil.copy(tmp / f"mp_{i:04d}.png", out / f"mp_{i:04d}.png")
    shutil.rmtree(tmp, ignore_errors=True)
    ctx = next((l.split("context:")[1].strip() for l in log.splitlines() if "context:" in l), "?")
    meta = {"name": out.name, "description": preset.get("description", f"Look '{out.name}' (multiplied over the film)"),
            "frames": n, "format": f"mp_0000.jpg ... mp_{n - 1:04d}.jpg, {W}x{H}, JPEG quality {a.quality}",
            "made_with": f"Shaders {VERSION} ({ctx}), renderFrame deltaSeconds 1/{FPS}, film-finish/scripts/shaders_render.py",
            "components": comps}
    (out / "look.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"look '{out.name}': {n} frames in {time.time() - t0:.1f} s ({ctx}) -> {out}")
    print(f"use: apply_look.py film.mp4 --look {out.name if not a.out else out}")


def iris_progress(frames, direction="close", ease=True):
    """Progress per frame (0 = picture fully visible, 1 = fully covered). close: frames 1/N..1 (last frame black),
    open: 1..1/N (first frame black, the frame after the last one is clear). Smoothstep easing."""
    us = [(k + 1) / frames for k in range(frames)]
    if direction == "open":
        us = us[::-1]
    return [u * u * (3 - 2 * u) if ease else u for u in us]


def iris_numpy(out, center=(0.5, 0.5), frames=12, direction="close", feather=0.02, size=(W, H), progress=None,
               srgb=True):
    """Pure numpy twin of the Shaders IrisWipe (invert = closes to the centre): distance from the centre normalised
    by the farthest corner, front remapped by +-feather, smoothstep edge, sRGB-encoded like the GPU output
    (measured: 0.014/255 mean difference to the WebGPU masks). Same file names as the WebGPU masks."""
    import numpy as np
    from PIL import Image
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    w, h = size
    asp = w / h
    x = (np.arange(w) + 0.5) / w * asp
    y = (np.arange(h) + 0.5) / h
    cx, cy = center[0] * asp, center[1]
    dist = np.hypot(x[None, :] - cx, y[:, None] - cy) / max(np.hypot(max(cx, asp - cx), max(cy, 1 - cy)), 1e-4)
    c = 1 - dist
    f = max(feather, 1e-4)
    for i, p in enumerate(progress or iris_progress(frames, direction)):
        front = p * (1 + 2 * f) - f
        t = np.clip((c - (front - f)) / (2 * f), 0, 1)
        m = t * t * (3 - 2 * t)
        if srgb:                                         # Shaders blends in linear light and writes sRGB
            m = np.where(m <= 0.0031308, 12.92 * m, 1.055 * np.power(m, 1 / 2.4) - 0.055)
        Image.fromarray((m * 255 + 0.5).astype(np.uint8), "L").save(out / f"m_{i:04d}.png")
    return out


def iris_shaders(out, center=(0.5, 0.5), frames=12, direction="close", feather=0.02, size=(W, H), d=None, progress=None):
    """IrisWipe masks rendered by Shaders (WebGPU): white circle on black."""
    items = []
    for i, p in enumerate(progress or iris_progress(frames, direction)):
        items.append({"name": f"m_{i:04d}.png", "preset": {"components": [
            {"type": "SolidColor", "props": {"color": "#000000"}},
            {"type": "IrisWipe", "props": {"progress": p, "invert": True, "feather": feather,
                                           "center": {"x": center[0], "y": center[1]}},
             "children": [{"type": "SolidColor", "props": {"color": "#ffffff"}}]}]}})
    run_job(items, out, d, size)
    from PIL import Image                                    # store as 8-bit grey like the numpy masks
    for it in items:
        p = Path(out) / it["name"]
        Image.open(p).convert("L").save(p)
    return Path(out)


def iris_mask_files(out, center=(0.5, 0.5), frames=12, direction="close", feather=0.02, size=(W, H), method="auto",
                    d=None):
    """Mask PNGs m_0000.png ... in out: Shaders when the package, node and a browser are there (method auto|shaders),
    else the numpy circle (method numpy, or auto as fallback). Returns (folder, method used)."""
    if method in ("auto", "shaders"):
        try:
            if method == "auto" and not package_ok(shaders_dir(d)):
                raise SystemExit("package not installed")
            return iris_shaders(out, center, frames, direction, feather, size, d), "shaders"
        except SystemExit as e:
            if method == "shaders":
                raise
            print(f"iris: WebGPU masks unavailable ({str(e).splitlines()[0]}) - numpy fallback")
    return iris_numpy(out, center, frames, direction, feather, size), "numpy"


def iris_masks(center=(0.5, 0.5), frames=12, size=(W, H), direction="close", feather=0.02, method="auto", d=None):
    """Mask provider for film-finish/scripts/transitions.py: list of float32 arrays HxW in 0..1 (1 = picture
    visible), one per transition frame, in time order (see iris_progress). WebGPU (Shaders IrisWipe) when
    available, else numpy. centre: 0..1 from the top-left, or pixels when a value is > 1. Cached per argument set,
    so calling it once per frame renders only once. Needs numpy + pillow."""
    import numpy as np
    from PIL import Image
    w, h = int(size[0]), int(size[1])
    cx, cy = (float(v) for v in center)
    if cx > 1 or cy > 1:
        cx, cy = cx / w, cy / h
    key = (round(cx, 4), round(cy, 4), int(frames), w, h, direction, float(feather), method, d)
    if key not in _MASKS:
        tmp = Path(tempfile.mkdtemp(prefix="shaders_iris_"))
        try:
            iris_mask_files(tmp, (cx, cy), int(frames), direction, feather, (w, h), method, d)
            _MASKS[key] = [np.asarray(Image.open(tmp / f"m_{i:04d}.png").convert("L"), np.float32) / 255
                           for i in range(int(frames))]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return _MASKS[key]


_MASKS = {}


def gallery(a):
    out = Path(a.out).resolve()
    img = str(Path(a.image).resolve())
    effects = json.loads(Path(a.effects).read_text(encoding="utf-8")) if a.effects else GALLERY
    items = []
    for i, (name, fx) in enumerate(effects):
        if fx == "iris":                                 # a filter with a child: the picture inside the iris
            comps = [{"type": "SolidColor", "props": {"color": "#000000"}},
                     {"type": "IrisWipe", "props": {"progress": 0.55, "invert": True, "feather": 0.02,
                                                    "center": {"x": 0.3, "y": 0.75}}, "children": [json.loads(json.dumps(IMG))]}]
        else:
            comps = [json.loads(json.dumps(IMG))] + fx
        txt = json.dumps({"components": comps}).replace("$IMAGE", img.replace("\\", "/"))
        items.append({"name": f"g_{i:02d}_{name}.png", "preset": json.loads(txt), "warmup": 6, "delay_ms": 120})
    t0 = time.time()
    run_job(items, out, a.shaders_dir)
    sheet = contact(out, [it["name"] for it in items], out / "gallery.png")
    print(f"gallery: {len(items)} effects in {time.time() - t0:.1f} s -> {out} (sheet {sheet.name})")


def contact(folder, names, dst, cols=4, tw=400):
    from PIL import Image, ImageDraw
    th = tw * H // W
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 24)), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        x, y = (i % cols) * tw, (i // cols) * (th + 24)
        sheet.paste(Image.open(Path(folder) / n).convert("RGB").resize((tw, th)), (x, y + 24))
        d.text((x + 6, y + 5), n.rsplit(".", 1)[0], fill=(235, 235, 235))
    sheet.save(dst)
    return Path(dst)


def catalog(a):
    d = shaders_dir(a.shaders_dir)
    need_package(d)
    out = Path(a.out).resolve()
    subprocess.run([node_exe(), str(PAGE_DIR / "make_catalog.mjs"), str(d), str(out)], check=True)


def main():
    ap = argparse.ArgumentParser(description="Shaders (WebGPU) looks, iris masks, effect gallery, catalogue.")
    ap.add_argument("job", nargs="?", choices=["look", "iris", "gallery", "catalog"])
    ap.add_argument("--install", action="store_true", help=f"npm install shaders@{VERSION} (only with the user's OK)")
    ap.add_argument("--shaders-dir", help="folder holding node_modules/shaders (default: config key 'shaders')")
    ap.add_argument("--out")
    ap.add_argument("--preset", help="look: JSON with components (look.json format)")
    ap.add_argument("--name", help="look: name under assets/look/ (default: preset file name)")
    ap.add_argument("--frames", type=int, help="look: default from the preset or 24; iris: default 12")
    ap.add_argument("--quality", type=int, default=92, help="look: JPEG quality")
    ap.add_argument("--keep-png", action="store_true", help="look: keep the lossless PNGs next to the JPGs")
    ap.add_argument("--center", default="0.5,0.5", help="iris: x,y in 0..1 from the top-left")
    ap.add_argument("--direction", default="close", choices=["close", "open"])
    ap.add_argument("--feather", type=float, default=0.02)
    ap.add_argument("--numpy", action="store_true", help="iris: pure numpy circle, no browser")
    ap.add_argument("--image", help="gallery: the picture")
    ap.add_argument("--effects", help='gallery: JSON [["Name", [components over the picture]], ...]')
    a = ap.parse_args()
    if a.install:
        install(shaders_dir(a.shaders_dir))
        if not a.job:
            return
    if not a.job:
        ap.error("choose a job: look | iris | gallery | catalog (or --install)")
    if a.job == "look":
        if not a.preset:
            ap.error("look needs --preset")
        look(a)
    elif a.job == "iris":
        if not a.out:
            ap.error("iris needs --out")
        c = tuple(float(v) for v in a.center.split(","))
        t0 = time.time()
        folder, how = iris_mask_files(a.out, c, a.frames or 12, a.direction, a.feather,
                                 method="numpy" if a.numpy else "shaders", d=a.shaders_dir)
        print(f"iris {a.direction}: {a.frames or 12} masks ({how}) in {time.time() - t0:.1f} s -> {Path(folder).resolve()}")
    elif a.job == "gallery":
        if not (a.image and a.out):
            ap.error("gallery needs --image and --out")
        gallery(a)
    else:
        if not a.out:
            ap.error("catalog needs --out")
        catalog(a)


if __name__ == "__main__":
    main()
