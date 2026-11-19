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
  stage_run.py film <project> --changed [--clips c03]   also the frames that look different now (after a plugin
                                                       update or a change outside scenes/ the source key misses)
  stage_run.py status <project> [--q film]            frames rendered / missing per clip

--engine eevee (clip / film / status) renders with EEVEE instead of Cycles - experimental, several times faster,
frames in out/<clip>/<q>_eevee/ (stage-3d BLOCK.md says what differs).
Qualities: draft (half size, 24 samples - the whole-film preview and all contact sheets), preview, film (full size,
40 samples + denoiser, motion blur), final (128 samples, hero stills). `film` skips frames that exist, so it can be
stopped and started again. A clip whose scene module (or a helper module in scenes/), project settings (size,
palette, lips, figures, seed, cast, frames) or spoken lines changed since its frames were made is rendered again by `film`
(the key is out/<clip>/<q>/source.json) - but only the frames that look different: every film render stores a
fingerprint per frame (out/<clip>/<q>/frames.json, stage_frames.py: poses, faces, light, camera, materials), and a
changed clip is built once, fingerprinted again and only its changed frames (+ neighbours under motion blur) are
deleted and rendered. `--changed` does that check for every clip with frames, even when the key is the same;
`--overwrite` renders everything; `clip ... --range a b --overwrite` renders a part again by hand.
While Blender runs the computer does not go to idle sleep (studio-core awake.py via the GPU lock).
Output: <project>/out/<clip>/<q>/f_####.png, stills in out/<clip>/stills_<q>/, the sheet in out/<clip>/sheet.png.
Blender comes from the config key `blender`; the shared GPU lock is held while it runs (job "stage3d_blender").
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402
import derived  # noqa: E402
from stage_project import ENGINES, QUALITIES, Film, folder  # noqa: E402

HERE = Path(__file__).resolve().parent


def blender(project, clip, *args):
    """run stage_film.py in Blender; its progress lines are passed on, the rest of Blender's chatter is dropped"""
    from gpu_lock import acquire
    acquire("stage3d_blender", model="blender")
    cmd = [config.need("blender"), "-b", "--factory-startup", "--python-exit-code", "1", "--python",
           str(HERE / "stage_film.py"), "--", str(project), clip, *[str(a) for a in args]]
    env = dict(os.environ, PYTHONUNBUFFERED="1", STAGE3D_PROJECT=str(project))
    if config.get("actors3d") and not env.get("STAGE3D_ACTORS"):      # folders of the realistic actors (stage_rig)
        env["STAGE3D_ACTORS"] = config.get("actors3d")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", env=env)
    tail, shown = [], []
    show = ("BUILT", "RENDERED", "DONE", "Traceback", "Error", "  File ", "SystemExit", "ACTOR", "CONTACT", "CHANGED",
            "FINGERPRINT")
    try:
        for line in p.stdout:
            line = line.rstrip()
            tail = (tail + [line])[-25:]
            if line.startswith(show) or "Error" in line:
                print(line, flush=True)
                shown.append(line)
    except BaseException:                          # Ctrl+C / kill: Blender must not render on after the GPU lock
        p.kill()
        p.wait(10)
        raise
    if p.wait() != 0:
        print("\n".join(tail), file=sys.stderr)
        raise SystemExit(f"Blender failed on clip {clip} (exit {p.returncode})")
    return shown


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
    if a.contact:
        args.append("--contact")
    blender(F.dir, name, *args)
    if stills and a.sheet:
        sheet(F, name, folder(a.q, a.engine), stills)
    return 0


def source_key(F, clip, q, engine):
    """What the frames of a clip are made from -> {"key": scene module + helper modules in scenes/ (not the other
    clips) + the project settings the stage reads, "lines": the spoken lines it says (from the last build.json) or
    None before the first build}. Two keys: a first render stopped before build.json existed must not count as
    changed on the resume (that threw its finished frames away)."""
    scenes = F.dir / "scenes"
    names = {c for c, _, _ in F.clips}
    mods = [scenes / f"{clip}.py"] + sorted(p for p in scenes.glob("*.py") if p.stem not in names and p.stem != "__init__")
    b, lj, lines = F.out(clip) / "build.json", F.dir / "speech" / "lines.json", {}
    said = [s["id"] for s in json.loads(b.read_text(encoding="utf-8")).get("said", [])] if b.exists() else []
    if said and lj.exists():
        L = {x["id"]: x for x in json.loads(lj.read_text(encoding="utf-8")).get("lines", [])}
        lines = {i: L.get(i) for i in said}
    spec = {k: F.get(k) for k in ("size", "palette", "lips", "seed", "cast")}
    if F.get("actors"):                                     # only when set: older frames keep their key
        spec["actors"] = F.get("actors")
    if F.get("figures") not in (None, "", "toy"):          # only when set: older frames keep their key
        spec["figures"] = F.get("figures")
    spec.update(clip=clip, frames=F.clip(clip)[1], q=q, engine=engine)
    return {"key": derived.key(mods, spec), "lines": derived.key([], lines) if b.exists() else None}


def same_source(old, new):
    """old = source.json; a side without "lines" (no build.json then) is compatible with any lines"""
    if old.get("key") != new["key"]:
        return False
    return old.get("lines") is None or new["lines"] is None or old["lines"] == new["lines"]


def cmd_film(a):
    F = Film(a.project)
    F.check()
    only = a.clips.split(",") if a.clips else None
    names = [c for c, _, _ in F.clips]
    if only and (bad := [c for c in only if c not in names]):
        raise SystemExit(f"--clips: no such clip {', '.join(bad)} (clips: {', '.join(names)})")
    fq = folder(a.q, a.engine)
    todo = []
    for c, n, _ in F.clips:
        if only and c not in only:
            continue
        k, kf, miss = source_key(F, c, a.q, a.engine), F.out(c, fq) / "source.json", F.missing(c, fq)
        over, check = a.overwrite, False
        if len(miss) < n and not over:                 # frames exist: made from the same scene / settings / lines?
            old = json.loads(kf.read_text(encoding="utf-8")) if kf.exists() else None
            fp = (F.out(c, fq) / "frames.json").exists()
            if a.changed and fp:
                check = True
                print(f"{c}: checking which frames look different (--changed)", flush=True)
            elif old is None or "lines" not in old:  # none (before 0.5.2) or the 0.5.2 one-key format
                print(f"{c}: frames without a current source.json (older version) - taken as they are"
                      + (" (--changed needs the fingerprints of a render since 0.9)" if a.changed else ""), flush=True)
            elif not same_source(old, k) and fp:
                # only the frames that look different go: Blender builds the clip, compares the fingerprints and
                # deletes those; source.json is written after that run (a run stopped before the check redoes it)
                check = True
                print(f"{c}: the scene, the project settings or its lines changed - re-rendering only the frames "
                      f"that look different", flush=True)
            elif not same_source(old, k):
                # the old frames are deleted BEFORE the new key is stored: a re-render stopped half way resumes
                # with only new frames (keeping them mixed old/new frames as "complete")
                gone = [f for f in F.out(c, fq).glob("f_*.png")]
                for f in gone:
                    f.unlink()
                print(f"{c}: the scene, the project settings or its lines changed since these '{a.q}' frames - "
                      f"{len(gone)} old frames deleted, rendering the clip again", flush=True)
                miss = F.missing(c, fq)
        F.out(c, fq).mkdir(parents=True, exist_ok=True)
        if not check:
            derived.write_text(kf, json.dumps(k))      # before rendering: a stopped run resumes with this key
        todo.append((c, n, n if over else len(miss), over, check))
    total = sum(t[2] for t in todo)
    checks = sum(1 for t in todo if t[4])
    print(f"{F.dir.name}: {total} of {sum(t[1] for t in todo)} frames to render in quality '{a.q}'"
          + (f" + the changed frames of {checks} clip(s)" if checks else ""), flush=True)
    t0, done = time.time(), 0
    for c, n, m, over, check in todo:
        if not m and not check:
            continue
        said = blender(F.dir, c, "--q", a.q, "--engine", a.engine, "--range", 1, n, "--fingerprint",
                       *(["--changed"] if check else []), *(["--overwrite"] if over else []))
        if check:                                      # the frames the check deleted were rendered as well
            extra = next((int(x.split()[2]) for x in said if x.startswith("CHANGED ")), 0)
            total += extra
            m += extra
        # again after the build: build.json now names the lines this clip says (the first run had none)
        derived.write_text(F.out(c, fq) / "source.json", json.dumps(source_key(F, c, a.q, a.engine)))
        done += m
        left = (time.time() - t0) / done * (total - done) if done else 0.0
        print(f"FILM {c} done - {done}/{total} frames, about {left / 60:.0f} min left", flush=True)
    miss = {t[0]: len(F.missing(t[0], fq)) for t in todo if F.missing(t[0], fq)}
    if miss:
        raise SystemExit(f"frames still missing: {miss}")
    print(f"FILM complete: {sum(t[1] for t in todo)} frames in out/<clip>/{fq}/ ({(time.time() - t0) / 60:.1f} min)")
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
    c.add_argument("--contact", action="store_true",
                   help="realistic actors: measure shoes below the floor and hands in furniture -> out/<clip>/contact.json")
    f = sub.add_parser("film")
    f.add_argument("project")
    f.add_argument("--q", default="draft", choices=QUALITIES)
    f.add_argument("--clips")
    f.add_argument("--overwrite", action="store_true")
    f.add_argument("--changed", action="store_true",
                   help="also check clips whose source key is the same and re-render the frames that look different")
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
