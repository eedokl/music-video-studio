# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Cut a film from rendered clips (3D films of the stage-3d block): frames of all clips in project order + the
finished sound track -> film.mp4, with dissolves, per-clip fades and the "ad" look.

  uv run clip_film.py <project> [--q film|draft|preview] [--out film.mp4] [--clips c01_intro,c02_cast]
                                [--look cinema|ad|standard|none] [--allow-missing] [--no-versions]

Per clip: out/<clip>/<q>/f_####.png (stage-3d stage_run.py). A missing frame stops the cut; with --allow-missing the
previous frame is held and the gaps are reported. Between clips: project.json clips[].xfade = frames of the dissolve
INTO the clip (taken from the held last frame of the outgoing clip, so picture and sound stay in sync).
Post effects per clip from out/<clip>/post.json: {"fade": [[frame, 0..1 black]], "white": [[frame, 0..1]],
"saturation": [[frame, value]]} (linear between keys).
Look (project.json "look", default "cinema") - computed per frame here: "cinema" = a darker, low-key picture with
deeper shadows, warm halation around bright areas, a clear vignette and fine grain; "ad" = bright and clean: soft
bloom, gentle contrast, a touch of warmth, light vignette, fine grain; "standard" = the paper/grain/vignette overlay
(apply_look.py); "none".
Sound: project.json "audio" under the whole film; a part of the film (--clips, when they follow each other) gets its
stretch of the sound. Output: <project>/film.mp4 for --q film (+ film_small.mp4 / film_mail.mp4, encode.py),
<project>/preview/film_<q>.mp4 for the other qualities. Every file is decode-checked.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

import _studio  # noqa: E402
_studio.use("stage-3d")
import config  # noqa: E402
from encode import place  # noqa: E402
from media import check_video  # noqa: E402
from stage_project import FOLDERS, FPS, Film  # noqa: E402

HERE = Path(__file__).resolve().parent
LOOKS = ("cinema", "ad", "standard", "none")


def keyed(keys, f, default):
    if not keys:
        return default
    keys = sorted(keys)
    if f <= keys[0][0]:
        return keys[0][1]
    if f >= keys[-1][0]:
        return keys[-1][1]
    for (fa, va), (fb, vb) in zip(keys, keys[1:]):
        if fa <= f <= fb:
            return va + (vb - va) * (f - fa) / max(1e-9, fb - fa)
    return default


_VIG = {}


def vignette(w, h):
    if (w, h) not in _VIG:
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot((x - w / 2) / (w / 2), (y - h / 2) / (h / 2)) / 1.414
        _VIG[(w, h)] = (1 - 0.34 * np.clip((r - 0.45) / 0.55, 0, 1) ** 2)[..., None]
    return _VIG[(w, h)]


def grade(img, rng, strength=1.0, cinema=False):
    """the "ad" look, or with cinema=True the darker "cinema" look. img: float32 0..1 HxWx3"""
    h, w, _ = img.shape
    if cinema:
        return grade_cinema(img, rng, strength)
    # bloom: blurred highlights screened back
    small = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((w // 4, h // 4), Image.BILINEAR)
    hi = np.asarray(small, np.float32) / 255
    hi = np.clip((hi - 0.72) / 0.28, 0, 1) ** 1.5 * hi
    bl = Image.fromarray((hi * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(w / 4 * 0.02))
    bl = np.asarray(bl.resize((w, h), Image.BILINEAR), np.float32) / 255
    img = 1 - (1 - img) * (1 - 0.32 * strength * bl)
    # gentle S-curve + a touch of warmth
    img = img + 0.06 * strength * (img - 0.5) * (1 - np.abs(2 * img - 1))
    img = img * np.array([1.012, 1.0, 0.985], np.float32)
    img = img * vignette(w, h)
    # fine grain (luma), stronger in the mid tones
    g = rng.standard_normal(((h + 1) // 2, (w + 1) // 2)).astype(np.float32)
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)[:h, :w, None]
    lum = img.mean(axis=2, keepdims=True)
    img = img + 0.012 * strength * g * (0.35 + 1.3 * lum * (1 - lum) * 2)
    return np.clip(img, 0, 1)


def grade_cinema(img, rng, s=1.0):
    """low-key film look: the picture a little darker with deeper shadows, warm halation around bright areas,
    a stronger vignette, fine grain"""
    h, w, _ = img.shape
    img = img ** (1 + 0.16 * s)                                   # darker mid tones, whites stay
    small = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((w // 4, h // 4), Image.BILINEAR)
    hi = np.asarray(small, np.float32) / 255
    hi = np.clip((hi - 0.62) / 0.38, 0, 1) ** 1.3 * hi
    halo = Image.fromarray((hi * 255).astype(np.uint8))
    wide = np.asarray(halo.filter(ImageFilter.GaussianBlur(w / 4 * 0.045)).resize((w, h), Image.BILINEAR),
                      np.float32) / 255
    near = np.asarray(halo.filter(ImageFilter.GaussianBlur(w / 4 * 0.012)).resize((w, h), Image.BILINEAR),
                      np.float32) / 255
    glow = (0.30 * s * wide * np.array([1.0, 0.62, 0.38], np.float32)
            + 0.16 * s * near * np.array([1.0, 0.86, 0.7], np.float32))
    img = 1 - (1 - img) * (1 - np.clip(glow, 0, 1))
    img = img + 0.10 * s * (img - 0.5) * (1 - np.abs(2 * img - 1))    # S-curve
    img = img * np.array([1.015, 1.0, 0.975], np.float32)
    img = img * (1 - 1.5 * (1 - vignette(w, h)))
    g = rng.standard_normal(((h + 1) // 2, (w + 1) // 2)).astype(np.float32)
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)[:h, :w, None]
    lum = img.mean(axis=2, keepdims=True)
    img = img + 0.014 * s * g * (0.35 + 1.3 * lum * (1 - lum) * 2)
    return np.clip(img, 0, 1)


def grade_video(src, out, look, seed=7):
    """the "cinema" / "ad" look of the film on another video (e.g. the end credits); the sound is copied"""
    ff = config.need("ffmpeg")
    probe = subprocess.run([ff, "-hide_banner", "-i", str(src)], capture_output=True, text=True, errors="replace").stderr
    import re
    w, h = (int(x) for x in re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", probe).groups())
    dec = subprocess.Popen([ff, "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen([ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                            "-r", str(FPS), "-i", "-", "-i", str(src), "-map", "0:v", "-map", "1:a?", "-c:v", "libx264",
                            "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags",
                            "+faststart", str(out)], stdin=subprocess.PIPE)
    rng, n = np.random.default_rng(seed), w * h * 3
    while True:
        buf = dec.stdout.read(n)
        if len(buf) < n:
            break
        img = np.frombuffer(buf, np.uint8).reshape(h, w, 3).astype(np.float32) / 255
        enc.stdin.write((grade(img, rng, cinema=look == "cinema") * 255 + 0.5).astype(np.uint8).tobytes())
    enc.stdin.close()
    dec.wait()
    if enc.wait() != 0:
        raise SystemExit(f"grading {src} failed")
    return out


def sound_args(F, clips, total):
    """ffmpeg input + output arguments for the sound of these clips ([] , [] = silent film)"""
    au = F.get("audio")
    if not au or not (F.dir / au).exists():
        return [], []
    names = [c[0] for c in F.film_clips]
    idx = [names.index(c[0]) for c in clips]
    if idx != list(range(idx[0], idx[0] + len(idx))):
        print("   the chosen clips do not follow each other - this part is cut without sound")
        return [], []
    start = sum(c[1] for c in F.film_clips[:idx[0]]) / FPS
    return (["-ss", f"{start:.4f}", "-i", str(F.dir / au)],
            ["-map", "0:v:0", "-map", "1:a:0", "-af", "apad", "-c:a", "aac", "-b:a", "256k", "-t", f"{total / FPS:.4f}"])


def cut(F, q, clips, out, look, allow_missing):
    gaps = {c: len(F.missing(c, q)) for c, _, _ in clips if F.missing(c, q)}
    if gaps and not allow_missing:
        raise SystemExit(f"frames missing in quality '{q}': {gaps} - render them (stage-3d stage_run.py film), "
                         f"or cut anyway with --allow-missing")
    total = sum(n for _, n, _ in clips)
    rng = np.random.default_rng(7)
    proc, size, prev_tail, done = None, None, [], 0
    tmp = out.with_name(f".tmp.{out.name}")
    out.parent.mkdir(parents=True, exist_ok=True)
    for clip, n, xf in clips:
        pj = F.out(clip) / "post.json"
        post = json.loads(pj.read_text(encoding="utf-8")) if pj.exists() else {}
        x = xf if prev_tail else 0
        last, tail = None, []
        for f in range(1, n + 1):
            p = F.frame(clip, q, f)
            img = np.asarray(Image.open(p).convert("RGB"), np.float32) / 255 if p.exists() else last
            if img is None:
                img = np.zeros((size[1], size[0], 3) if size else (F.size[1], F.size[0], 3), np.float32)
            if size is None:
                size = (img.shape[1], img.shape[0])
                ain, aout = sound_args(F, clips, total)
                cmd = [config.need("ffmpeg"), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                       f"{size[0]}x{size[1]}", "-r", str(FPS), "-i", "-", *ain, "-c:v", "libx264", "-preset",
                       "slow" if q == "film" else "veryfast", "-crf", "15" if q == "film" else "20", "-pix_fmt",
                       "yuv420p", "-movflags", "+faststart", *aout, "-f", "mp4", str(tmp)]
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            elif (img.shape[1], img.shape[0]) != size:
                raise SystemExit(f"{p}: {img.shape[1]}x{img.shape[0]}, the film is {size[0]}x{size[1]} - render the "
                                 f"clip again in this size")
            last = img
            sat = keyed(post.get("saturation"), f, 1.0)
            if abs(sat - 1.0) > 1e-3:
                lum = (img * np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(axis=2, keepdims=True)
                img = lum + (img - lum) * sat
            fd = keyed(post.get("fade"), f, 0.0)
            if fd > 1e-3:
                img = img * (1 - fd)
            wh = keyed(post.get("white"), f, 0.0)
            if wh > 1e-3:
                img = img + (1 - img) * wh
            if x and f <= x:                              # dissolve from the held last frame of the previous clip
                t = f / (x + 1)
                t = t * t * (3 - 2 * t)
                img = prev_tail[-1] * (1 - t) + img * t
            if f > n - 2:
                tail.append(img)
            res = grade(img, rng, cinema=look == "cinema") if look in ("ad", "cinema") else np.clip(img, 0, 1)
            proc.stdin.write((res * 255 + 0.5).astype(np.uint8).tobytes())
            done += 1
        prev_tail = tail
        print(f"   {clip}: {n} frames" + (f"  (MISSING {gaps[clip]}, held)" if clip in gaps else ""), flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        tmp.unlink(missing_ok=True)
        raise SystemExit("ffmpeg failed while writing the film")
    if look == "standard":
        lk = tmp.with_name(f".tmp.look.{out.name}")
        subprocess.run([sys.executable, str(HERE / "apply_look.py"), str(tmp), "-o", str(lk)], check=True)
        os.replace(lk, tmp)
    final = place(tmp, out)
    err = check_video(final)
    print(f"-> {final}: {done} frames = {done / FPS:.1f} s, {final.stat().st_size / 1e6:.1f} MB, "
          f"{'0 decode errors' if not err else 'ERRORS: ' + err[:300]}")
    if err:
        raise SystemExit(1)
    return final


def main():
    ap = argparse.ArgumentParser(description="Cut a 3D film from its rendered clips, with sound and look.")
    ap.add_argument("project")
    ap.add_argument("--q", default="film", choices=FOLDERS, help="render folder: film, draft, ... or film_eevee, draft_eevee")
    ap.add_argument("--out")
    ap.add_argument("--clips", help="only these clips (comma separated, in project order)")
    ap.add_argument("--look", help="cinema | ad | standard | none (default: project.json \"look\", else cinema)")
    ap.add_argument("--allow-missing", action="store_true")
    ap.add_argument("--no-versions", action="store_true", help="no film_small.mp4 / film_mail.mp4")
    a = ap.parse_args()
    F = Film(a.project)
    F.check()
    only = a.clips.split(",") if a.clips else None
    for c in only or []:
        F.clip(c)
    clips = [c for c in F.film_clips if not only or c[0] in only]
    if not clips:
        raise SystemExit("project.json has no clips")
    look = a.look or F.get("look") or "cinema"
    if look not in LOOKS:
        raise SystemExit(f'look "{look}": clip_film.py knows {", ".join(LOOKS)}')
    part = "" if not only else "_" + "_".join(c[0] for c in clips)[:60]
    out = Path(a.out) if a.out else (F.dir / f"film{part}.mp4" if a.q == "film" else
                                     F.dir / "preview" / f"film_{a.q}{part}.mp4")
    if not out.is_absolute():
        out = F.dir / out
    print(f"{F.dir.name}: {len(clips)} clips, {sum(c[1] for c in clips)} frames, quality '{a.q}', look '{look}'")
    final = cut(F, a.q, clips, out, look, a.allow_missing)
    if a.q == "film" and not only and not a.no_versions:
        subprocess.run([*config.script_cmd(HERE / "encode.py"), str(final)], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
