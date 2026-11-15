# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4", "pillow==13.0.0"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Type-check, preview, clip and final render of the lyric video (headless Chrome, frame-exact), plus the delivery versions.

  uv run render.py PROJECT check
  ... render.py PROJECT preview [--fps 1] [--every 6 | --times 4,12,20]   1-fps run of the WHOLE song + contact sheet
  ... render.py PROJECT clip --from 88 --to 98 [--fps 10]                 timing check around tight cuts / held notes
  ... render.py PROJECT final [--crf 20] [--title "Song Title"] [--look none|standard] [--from S --to S]
  ... render.py PROJECT versions out/<title>.mp4                           only (re)make the smaller copies
  ... render.py PROJECT sheet VIDEO --times 4,12,20                        contact sheet of any video
  sheet --times are seconds of THAT file: for a clip made with --from 88, 2.5 = song time 90.5. preview --times are
  song times, snapped to the preview's frames (at --fps 1: whole seconds) and labelled with the time shown.

final writes to <project>/out/:
  <title>.mp4             full quality (CRF 20, 1080p30)
  <title>_compressed.mp4  CRF 28 -preset slow, same size, looks the same (~1/5)
  <title>_small.mp4       < 30 MB: 1280x720, two-pass  (film-finish encode.encode_target)
  <title>_mail.mp4        ~12 MB: 960x540, two-pass, AAC 64k (mail attachments grow ~33 % by base64)
Every file is decoded once (0 errors expected), its duration compared with the rendered range and its audio
stream checked. Files are rendered to *_tmp first; a file locked by a video player is kept under a new name.
--look standard lays film-finish's paper + grain + vignette over the full file before the copies are made
(off by default: a lyric video brings its own look; grain that changes every frame multiplies the file size).
The browser: config "chrome" (check_tools.py --set chrome=PATH, env ANIMATION_STUDIO_CHROME), or a chrome-headless-shell in
%TEMP%/mvchrome or ~/.cache/puppeteer - downloaded there with npx only after the user agreed (INSTALL_BROWSER=1).
Do not edit files of the project while a render runs (Vite reloads the page).
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "film-finish")
import config  # noqa: E402
from encode import over_note, encode_target, place  # noqa: E402   film-finish: two-pass size target, locked-file handling
from frames import sheet_at  # noqa: E402
from media import check_video, duration, ffmpeg, has_audio, video_size  # noqa: E402
from song_project import Project  # noqa: E402

FF_DIR = _studio.skill_dir("film-finish") / "scripts"


def tool(name):
    return shutil.which(name) or shutil.which(name + ".cmd") or name


def find_browser():
    for p in (config.get("chrome"),):                             # explicit choice (config or ANIMATION_STUDIO_CHROME)
        if p and Path(p).exists():
            return p
    bases = [Path(tempfile.gettempdir()) / "mvchrome" / "chrome-headless-shell",
             Path.home() / ".cache" / "puppeteer" / "chrome-headless-shell"]
    for b in bases:
        hits = sorted(glob.glob(str(b / "*" / "chrome-headless-shell-*" / "chrome-headless-shell*")))
        hits = [h for h in hits if h.endswith((".exe", "chrome-headless-shell"))]
        if hits:
            return hits[-1]
    # the machine's general browser (config "browser", e.g. Edge) last: chrome-headless-shell is faster and
    # renders identically; a full Edge/Chrome runs in new headless mode (render.mjs)
    p = config.get("browser")
    if p and Path(p).exists():
        return p
    return None


def ensure_browser(video):
    b = find_browser()
    if b:
        return b
    dest = Path(tempfile.gettempdir()) / "mvchrome"
    if os.environ.get("INSTALL_BROWSER") != "1":            # never download without the user's OK
        raise SystemExit("no headless Chrome found. Ask the user, then either set INSTALL_BROWSER=1 to download "
                         f"chrome-headless-shell into {dest} (short path on purpose), or point to an installed "
                         "Chrome/Edge: check_tools.py --set chrome=PATH")
    print(f"installing chrome-headless-shell into {dest} (approved by the user)")
    subprocess.run([tool("npx"), "--yes", "@puppeteer/browsers", "install", "chrome-headless-shell@stable",
                    "--path", str(dest)], cwd=video, check=True)
    b = find_browser()
    if not b:
        raise SystemExit("headless Chrome still missing - set ANIMATION_STUDIO_CHROME=<chrome.exe> or check_tools.py --set chrome=PATH")
    return b


def video_dir(P):
    v = P.dir / P.get("video", "video")
    if not (v / "node_modules").exists():
        print("node_modules missing - npm install")
        subprocess.run([tool("npm"), "install", "--no-audit", "--no-fund"], cwd=v, check=True)
    return v


def tsc(video):
    r = subprocess.run([tool("npx"), "tsc", "--noEmit"], cwd=video, capture_output=True, text=True, errors="replace")
    if r.returncode:
        print(r.stdout[-4000:], r.stderr[-2000:])
        raise SystemExit("TypeScript errors - fix them before rendering")
    print("tsc: no errors")


def run_render(P, out, fps=30, crf=20, t0=None, t1=None, query=None, width=1920, height=1080):
    video = video_dir(P)
    env = dict(os.environ, FFMPEG=ffmpeg(), ANIMATION_STUDIO_CHROME=ensure_browser(video))
    out = Path(out).resolve()
    tmp = out.with_name(out.stem + "_tmp.mp4")
    tmp.unlink(missing_ok=True)
    cmd = ["node", "scripts/render.mjs", "--fps", str(fps), "--crf", str(crf), "--out", str(tmp),
           "--width", str(width), "--height", str(height)]
    if t0 is not None:
        cmd += ["--from", str(t0)]
    if t1 is not None:
        cmd += ["--to", str(t1)]
    if query:
        cmd += ["--query", query]
    r = subprocess.run(cmd, cwd=video, env=env)
    if r.returncode or not tmp.exists() or tmp.stat().st_size < 1000:
        raise SystemExit(f"render failed (exit {r.returncode}) - no new file; check for leftover node/chrome processes")
    out.parent.mkdir(parents=True, exist_ok=True)
    return place(tmp, out)


def verify(f, expect=None):
    err = check_video(f)
    d = duration(f)
    ok_d = expect is None or abs(d - expect) < 0.15
    print(f"   {Path(f).name}: {Path(f).stat().st_size / 1e6:.1f} MB, {d:.2f} s{'' if ok_d else f' (expected {expect:.2f})'}, "
          f"audio {'yes' if has_audio(f) else 'MISSING'}, {'0 decode errors' if not err else 'ERRORS: ' + err[:200]}")
    return not err and ok_d and has_audio(f)


def versions(full, dur):
    full = Path(full)
    out = []
    comp = full.with_name(full.stem + "_compressed_tmp.mp4")
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(full), "-c:v", "libx264", "-preset", "slow", "-crf", "28",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(comp)], check=True)
    out.append(place(comp, full.with_name(full.stem + "_compressed.mp4")))
    # the smaller of full / compressed is the reference: a version is copied only when that one is already under the
    # size AND the side limit, and an encode never aims above it (user test: a 24 s clip got a _small identical to the
    # 16 MB full film and a 960x540 _mail bigger than the 5 MB _compressed)
    ref = min((full, out[-1]), key=lambda f: f.stat().st_size)
    W, H = video_size(full)
    for suffix, mb, w, h, ak in (("_small", 29.0, 1280, 720, 96), ("_mail", 12.0, 960, 540, 64)):
        tmp = full.with_name(full.stem + suffix + "_tmp.mp4")
        if ref.stat().st_size < mb * 1e6 and W <= w:
            shutil.copy(ref, tmp)
            print(f"   {suffix}: a copy of {ref.name} (already under {mb:g} MB and {w} px)")
        else:
            encode_target(full, tmp, min(mb, ref.stat().st_size / 1.024e6), w, h, ak, dur, limit_mb=mb)
        out.append(place(tmp, full.with_name(full.stem + suffix + ".mp4")))
        over = over_note(out[-1], mb)
        if over:
            print(f"   {out[-1].name}: {out[-1].stat().st_size / 1e6:.1f} MB{over}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Render the lyric video.")
    ap.add_argument("project")
    ap.add_argument("what", choices=["check", "preview", "clip", "final", "versions", "sheet"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--fps", type=float)
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--from", dest="t0", type=float)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--title")
    ap.add_argument("--look", default="none")
    ap.add_argument("--query", help="extra page parameters, e.g. staticgrain")
    ap.add_argument("--times")
    ap.add_argument("--every", type=float, default=6.0)
    ap.add_argument("--out")
    a = ap.parse_args()
    P = Project(a.project)
    P.check("lyric-music-video")                 # project.json validated before any long step
    outdir = P.dir / "out"
    outdir.mkdir(exist_ok=True)
    song = duration(P.song)
    if a.what in ("sheet", "versions"):            # like every other path: relative to the project (cwd as fallback)
        if not a.file:
            raise SystemExit(f"{a.what} needs a video file, e.g. out/<title>.mp4")
        f = Path(a.file)
        a.file = str(f if f.is_absolute() or not (P.dir / f).exists() else P.dir / f)
        if not Path(a.file).exists():
            raise SystemExit(f"{a.file} not found (relative paths are read from the project folder)")
    if a.what == "check":
        tsc(video_dir(P))
    elif a.what == "sheet":
        times = [float(x) for x in a.times.split(",")]
        print(sheet_at(a.file, a.out or str(Path(a.file).with_suffix(".jpg")), times))
    elif a.what == "preview":
        tsc(video_dir(P))
        f = run_render(P, a.out or outdir / "preview.mp4", fps=a.fps or 1, crf=28, t0=a.t0, t1=a.t1, query=a.query)
        t0 = a.t0 or 0
        times = [float(x) for x in a.times.split(",")] if a.times else \
            [round(t0 + 1 + i * a.every, 1) for i in range(int(((a.t1 or song) - t0 - 1) // a.every) + 1)]
        pf = a.fps or 1                                  # the preview only has frames on its own grid: show and label
        shown = [t0 + round((t - t0) * pf) / pf for t in times]   # the frame that is really there (user test:
        if any(abs(x - t) > 0.01 for x, t in zip(shown, times)):  # 4.6 s was labelled 4.6 but showed 5.0)
            print(f"   preview at {pf} fps: times snapped to its frames - for exact times render a clip around them")
        sheets = []
        for k in range(0, len(shown), 12):               # 12 frames per sheet (4 x 3)
            s = outdir / f"preview_sheet_{k // 12 + 1}.jpg"
            # the preview starts at --from: its clock is song time - t0; labels = song time
            sheet_at(f, s, [t - t0 for t in shown[k:k + 12]], cols=4, width=400,
                     labels=[f"{t:.2f} s" for t in shown[k:k + 12]])
            sheets.append(s.name)
        print(f"-> {Path(f).name}; contact sheets (labels = song time): {', '.join(sheets)}")
    elif a.what == "clip":
        if a.t0 is None or a.t1 is None:
            raise SystemExit("clip needs --from and --to")
        f = run_render(P, a.out or outdir / f"clip_{a.t0:g}-{a.t1:g}.mp4", fps=a.fps or 10, crf=23, t0=a.t0, t1=a.t1,
                       query=a.query)
        verify(f, a.t1 - a.t0)
    elif a.what in ("final", "versions"):
        title = a.title or P.get("name", "music-video")
        t0, t1 = a.t0 or 0.0, min(a.t1 or song, song)
        if a.what == "final":
            tsc(video_dir(P))
            full = run_render(P, outdir / f"{title}.mp4", fps=a.fps or 30, crf=a.crf, t0=a.t0, t1=a.t1, query=a.query)
            if a.look != "none":
                looked = Path(full).with_name(Path(full).stem + "_look_tmp.mp4")
                subprocess.run([sys.executable, str(FF_DIR / "apply_look.py"), str(full), "-o", str(looked),
                                "--look", a.look], check=True)
                full = place(looked, Path(full))
        else:
            full = Path(a.file)
        files = [Path(full)] + versions(full, t1 - t0)
        print("checking every file:")
        ok = all([verify(f, t1 - t0) for f in files])
        print("all files OK" if ok else "SOME FILES FAILED THE CHECK - see above")


if __name__ == "__main__":
    main()
