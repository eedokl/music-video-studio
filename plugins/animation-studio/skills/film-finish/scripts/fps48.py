"""48 fps version of the film: RIFE frame interpolation ONLY in camera moves, every other frame doubled.

Why: figure animation and lip sync are drawn on 24 fps and look wrong when interpolated (mouths and poses melt);
camera flights (comic pages, multiplane intros) get smoother with in-between frames. So:
  - sections marked "camera_move": true in project.json (sections with "kind": "panels" count too) -> RIFE
  - inside such a section never across a cut; the frame before a cut is doubled instead. Where the cuts are KNOWN,
    pixel differences are not used (a fast camera move or a caption box popping up is no cut):
      section "shots": [song seconds of the hard cuts inside it] ([] = one continuous shot, e.g. a comic flight)
      "kind": "panels"  -> the cuts are the panel line starts
    only sections without this information fall back to the frame difference (--cut-threshold)
  - all other frames are doubled -> poses and mouths stay exactly as rendered
Input: film.mp4 (finished film with look and sound) - build it first with build.py film.
Output: film_48fps.mp4 (same sound, 48 fps), checked for decode errors.
RIFE: rife-ncnn-vulkan (config key "rife" = path of rife-ncnn-vulkan.exe, model folder rife-v4.6 next to it or
config key "rife_model"); runs under the shared GPU lock; needs "-g 0" (else it may pick the integrated GPU) and
RGB images (no alpha).
Usage: uv run --no-project --with numpy --with pillow python fps48.py [--project .] [--src film.mp4] [--cut-threshold 28]
"""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use("song-analysis")
import config  # noqa: E402
from encoding import h264  # noqa: E402
from media import check_video, ffmpeg  # noqa: E402
from song_project import Project  # noqa: E402

W, H = 1280, 720


def move_ranges(P, n_frames):
    """Film-frame ranges [a, b) of the camera-move sections (film frame 0 = start of the first section)."""
    secs = sorted(P.sections(), key=lambda s: s["from"])
    t0, fps = secs[0]["from"], P.fps
    out, cuts = [], set()
    lines = P.sheet()["lines"] if (P.analysis / "song_sheet.json").exists() else []
    for s in secs:
        if not (s.get("camera_move") or s.get("kind") == "panels"):
            continue
        a, b = round((s["from"] - t0) * fps), min(round((s["to"] - t0) * fps), n_frames)
        known = s.get("shots") is not None or s.get("kind") == "panels"
        if b - a > 1:
            out.append((a, b, known))
        if s.get("kind") == "panels":                     # panel cuts sit on the line starts (as scene.py cuts them)
            last = -1e9
            for l in lines:
                if s["from"] - 0.05 <= l["t"] < s["to"] - 0.3 and l["t"] > max(last, s["from"]) + 0.3:
                    cuts.add(round((l["t"] - t0) * fps))
                    last = l["t"]
        cuts |= {round((float(t) - t0) * fps) for t in (s.get("shots") or [])}
    return out, cuts


def read_frames(src, a, b, fps):
    """Frames a..b-1 of the video as RGB arrays."""
    raw = subprocess.run([ffmpeg(), "-v", "error", "-ss", f"{a / fps:.4f}", "-i", str(src), "-frames:v", str(b - a),
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--src", default="film.mp4")
    ap.add_argument("--cut-threshold", type=float, default=28.0, help="mean abs. difference (0-255) that counts as a cut")
    a = ap.parse_args()
    P = Project(a.project)
    src = P.path(a.src)
    if not src.exists():
        raise SystemExit(f"{src} missing - build the film first (build.py film)")
    fps = P.fps
    n = int(subprocess.run([ffmpeg(), "-v", "error", "-i", str(src), "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "gray",
                            "-s", "16x9", "-"], capture_output=True, check=True).stdout.__len__() / 144)   # frame count
    ranges, panel_cuts = move_ranges(P, n)
    interp = {}                                           # film frame i -> RGB array between i and i+1
    if ranges:
        exe = config.need("rife")
        model = config.get("rife_model") or str(Path(exe).parent / "rife-v4.6")
        from gpu_lock import acquire
        acquire("fps48", model="rife")                    # one GPU job at a time
        from PIL import Image
        for k, (r0, r1, known) in enumerate(ranges):
            fr = read_frames(src, r0, r1, fps)
            cut = {c - r0 - 1 for c in panel_cuts if r0 < c < r1}
            if not known:                                 # no shot list: hard cuts from the frame difference
                diff = [np.abs(fr[j + 1].astype(np.int16) - fr[j].astype(np.int16)).mean() for j in range(len(fr) - 1)]
                cut |= {j for j, d in enumerate(diff) if d > a.cut_threshold}
            with tempfile.TemporaryDirectory(dir=P.cache) as tmp:
                d_in, d_out = Path(tmp) / "in", Path(tmp) / "out"
                d_in.mkdir()
                d_out.mkdir()
                for j, im in enumerate(fr):
                    Image.fromarray(im).save(d_in / f"{j:08d}.png")         # RGB, no alpha
                r = subprocess.run([exe, "-i", str(d_in), "-o", str(d_out), "-m", model, "-g", "0"],
                                   capture_output=True, text=True, errors="replace")
                res = sorted(d_out.glob("*.png"))
                if r.returncode or len(res) < 2 * len(fr) - 1:
                    raise SystemExit(f"RIFE failed ({r.returncode}): {(r.stderr or r.stdout)[-400:]}")
                for j in range(len(fr) - 1):              # output 2j = original, 2j+1 = in-between of j and j+1
                    if j not in cut:
                        interp[r0 + j] = np.array(Image.open(res[2 * j + 1]).convert("RGB"))
            print(f"   camera move {k + 1}: film frames {r0}-{r1}, {len(fr) - 1 - len(cut)} in-betweens, {len(cut)} cuts kept hard"
                  f" ({'known shots' if known else 'cuts from frame difference'})")
    out = P.dir / "film_48fps.mp4"
    tmp_out = P.cache / "film_48fps_tmp.mp4"
    dec = subprocess.Popen([ffmpeg(), "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen([ffmpeg(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-framerate", str(2 * fps), "-i", "-", "-i", str(src), "-map", "0:v", "-map", "1:a", "-c:a", "copy",
                            *h264(), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp_out)], stdin=subprocess.PIPE)
    size, i = W * H * 3, 0
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        enc.stdin.write(buf)
        enc.stdin.write(interp[i].tobytes() if i in interp else buf)
        i += 1
    enc.stdin.close()
    rc_enc, rc_dec = enc.wait(), dec.wait()
    if rc_enc or rc_dec or i == 0 or not tmp_out.exists():
        tmp_out.unlink(missing_ok=True)
        raise SystemExit(f"48 fps encode failed (encoder exit {rc_enc}, decoder exit {rc_dec}, {i} frames) - "
                         f"{out.name} left unchanged")
    shutil.move(str(tmp_out), str(out))
    err = check_video(out)
    print(f"-> {out.name}: {2 * i} frames at {2 * fps} fps, {len(interp)} from RIFE, "
          f"{out.stat().st_size / 1e6:.1f} MB, {'0 decode errors' if not err else 'ERRORS: ' + err[:300]}")


if __name__ == "__main__":
    main()
