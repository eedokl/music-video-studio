# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Render clips of a 3D film project with Blender (headless, Cycles) - stills with a contact sheet, or the frames.

  stage_run.py check                                  Blender found? which version?
  stage_run.py clip <project> <clip> --stills 1,40,90 [--sheet] [--q draft]     key frames (+ labelled sheet.png)
  stage_run.py clip <project> <clip> --every 20 --sheet                         a strip through the whole clip
  stage_run.py clip <project> <clip> --range 1 120 [--q film] [--overwrite]     a frame range
  stage_run.py film <project> [--q draft|film] [--clips c01,c02] [--overwrite]  every missing frame of every clip
  stage_run.py status <project> [--q film]            frames rendered / missing per clip

--engine eevee (clip / film / status) renders with EEVEE instead of Cycles - experimental, several times faster,
frames in out/<clip>/<q>_eevee/ (stage-3d BLOCK.md says what differs).
Qualities: draft (half size, 24 samples - the whole-film preview and all contact sheets), preview, film (full size,
40 samples + denoiser, motion blur), final (128 samples, hero stills). `film` skips frames that exist, so it can be
stopped and started again; after changing a scene render its frames again with `clip ... --range a b --overwrite`.
Output: <project>/out/<clip>/<q>/f_####.png, stills in out/<clip>/stills_<q>/, the sheet in out/<clip>/sheet.png.
Blender comes from the config key `blender`; the shared GPU lock is held while it runs (job "stage3d_blender").
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402
from stage_project import ENGINES, QUALITIES, Film, folder  # noqa: E402

HERE = Path(__file__).resolve().parent


def blender(project, clip, *args):
    """run stage_film.py in Blender; its progress lines are passed on, the rest of Blender's chatter is dropped"""
    from gpu_lock import acquire
    acquire("stage3d_blender", model="blender")
    cmd = [config.need("blender"), "-b", "--factory-startup", "--python-exit-code", "1", "--python",
           str(HERE / "stage_film.py"), "--", str(project), clip, *[str(a) for a in args]]
    env = dict(os.environ, PYTHONUNBUFFERED="1", STAGE3D_PROJECT=str(project))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", env=env)
    tail, show = [], ("BUILT", "RENDERED", "DONE", "Traceback", "Error", "  File ", "SystemExit")
    for line in p.stdout:
        line = line.rstrip()
        tail = (tail + [line])[-25:]
        if line.startswith(show) or "Error" in line:
            print(line, flush=True)
    if p.wait() != 0:
        print("\n".join(tail), file=sys.stderr)
        raise SystemExit(f"Blender failed on clip {clip} (exit {p.returncode})")


def sheet(F, clip, q, frames, cols=4, width=480):
    """labelled contact sheet of rendered stills -> out/<clip>/sheet.png"""
    from PIL import Image, ImageDraw
    tiles = [(f, F.out(clip, "stills_" + q) / f"f_{f:04d}.png") for f in frames]
    tiles = [(f, p) for f, p in tiles if p.exists()]
    if not tiles:
        return None
    w0, h0 = Image.open(tiles[0][1]).size
    h = round(width * h0 / w0)
    rows = (len(tiles) + cols - 1) // cols
    img = Image.new("RGB", (cols * width, rows * h), (20, 20, 20))
    d = ImageDraw.Draw(img)
    for i, (f, p) in enumerate(tiles):
        x, y = (i % cols) * width, (i // cols) * h
        img.paste(Image.open(p).convert("RGB").resize((width, h), Image.LANCZOS), (x, y))
        d.rectangle((x, y, x + 46, y + 16), fill=(0, 0, 0))
        d.text((x + 4, y + 2), str(f), fill=(255, 255, 255))
    out = F.out(clip) / "sheet.png"
    img.save(out)
    print(f"SHEET {out}  frames: {', '.join(str(f) for f, _ in tiles)}", flush=True)
    return out


def cmd_check(a):
    b = config.need("blender")
    v = subprocess.run([b, "-b", "--version"], capture_output=True, text=True, errors="replace").stdout.splitlines()
    print(f"blender    {b}  ({v[0] if v else '?'})")
    return 0


def cmd_clip(a):
    F = Film(a.project)
    F.check()
    name, n, _ = F.clip(a.clip)
    if not (F.dir / "scenes" / f"{name}.py").exists():
        raise SystemExit(f"scenes/{name}.py missing in {F.dir}")
    args = ["--q", a.q, "--engine", a.engine]
    stills = None
    if a.stills:
        stills = [int(x) for x in a.stills.split(",")]
        args += ["--stills", a.stills]
    elif a.every:
        stills = list(range(1, n + 1, a.every))
        args += ["--every", a.every]
    elif a.range:
        args += ["--range", *a.range] + (["--overwrite"] if a.overwrite else [])
    if a.save:
        args.append("--save")
    blender(F.dir, name, *args)
    if stills and a.sheet:
        sheet(F, name, folder(a.q, a.engine), stills)
    return 0


def cmd_film(a):
    F = Film(a.project)
    F.check()
    only = a.clips.split(",") if a.clips else None
    fq = folder(a.q, a.engine)
    todo = [(c, n, n if a.overwrite else len(F.missing(c, fq))) for c, n, _ in F.clips if not only or c in only]
    total = sum(m for _, _, m in todo)
    print(f"{F.dir.name}: {total} of {sum(n for _, n, _ in todo)} frames to render in quality '{a.q}'", flush=True)
    t0, done = time.time(), 0
    for c, n, m in todo:
        if not m:
            continue
        blender(F.dir, c, "--q", a.q, "--engine", a.engine, "--range", 1, n, *(["--overwrite"] if a.overwrite else []))
        done += m
        left = (time.time() - t0) / done * (total - done)
        print(f"FILM {c} done - {done}/{total} frames, about {left / 60:.0f} min left", flush=True)
    miss = {c: len(F.missing(c, fq)) for c, _, _ in todo if F.missing(c, fq)}
    if miss:
        raise SystemExit(f"frames still missing: {miss}")
    print(f"FILM complete: {sum(n for _, n, _ in todo)} frames in out/<clip>/{fq}/ ({(time.time() - t0) / 60:.1f} min)")
    return 0


def cmd_status(a):
    F = Film(a.project)
    tot = miss = 0
    for c, n, _ in F.clips:
        m = len(F.missing(c, folder(a.q, a.engine)))
        tot, miss = tot + n, miss + m
        print(f"{c:24s} {n - m:5d} / {n:5d}" + ("" if not m else f"   missing {m}"))
    print(f"{'total':24s} {tot - miss:5d} / {tot:5d}   ({a.q})")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Render clips of a 3D film project with Blender.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    c = sub.add_parser("clip")
    c.add_argument("project")
    c.add_argument("clip")
    c.add_argument("--q", default="draft", choices=QUALITIES)
    c.add_argument("--stills")
    c.add_argument("--every", type=int)
    c.add_argument("--range", nargs=2, type=int)
    c.add_argument("--sheet", action="store_true")
    c.add_argument("--overwrite", action="store_true")
    c.add_argument("--save", action="store_true")
    f = sub.add_parser("film")
    f.add_argument("project")
    f.add_argument("--q", default="draft", choices=QUALITIES)
    f.add_argument("--clips")
    f.add_argument("--overwrite", action="store_true")
    s = sub.add_parser("status")
    s.add_argument("project")
    s.add_argument("--q", default="film", choices=QUALITIES)
    for x in (c, f, s):
        x.add_argument("--engine", default="cycles", choices=ENGINES,
                       help="eevee = experimental fast rasteriser; its frames go to out/<clip>/<q>_eevee/")
    a = ap.parse_args()
    return {"check": cmd_check, "clip": cmd_clip, "film": cmd_film, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
