# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Small media helpers every skill needs: decode audio, durations, voice activity, video check, contact sheet.

    import media
    y = media.decode("song.wav", 16000)          # mono float32
    media.duration("film.mp4")                   # seconds
    media.check_video("film.mp4")                # "" = decodes without a single error
    media.contact_sheet("film.mp4", "sheet.png") # 3x3 frames spread over the video
"""
import re
import subprocess
from pathlib import Path

import config
from encoding import video_size  # noqa: F401  (re-exported)

FPS = 24


def ffmpeg():
    return config.need("ffmpeg")


def decode(path, sr=16000):
    """Audio of any file -> mono float32 numpy array at sample rate sr."""
    import numpy as np
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def duration(path):
    r = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True, errors="replace").stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def has_audio(path):
    r = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True, errors="replace").stderr
    return "Audio:" in r


def voice_activity(path, fps=FPS, sr=16000):
    """Per frame: is a voice audible on this vocal track? (level above a threshold relative to the loud part)"""
    import numpy as np
    y = decode(path, sr)
    k = int(len(y) * fps / sr)
    if k == 0:
        return np.zeros(0, bool)
    # frame i covers samples int(i*sr/fps) .. int((i+1)*sr/fps): no drift when sr/fps is not an integer (16000/24)
    edges = (np.arange(k + 1) * sr / fps).astype(np.int64)
    rms = np.sqrt(np.add.reduceat(y[: edges[-1]].astype(np.float64) ** 2, edges[:-1]) / np.diff(edges))
    db = 20 * np.log10(rms + 1e-12)
    v = db > np.percentile(db, 90) - 24
    return np.convolve(v.astype(float), np.ones(3) / 3, mode="same") > 0.5


def check_video(path):
    """Decode the whole file; returns "" when there is not a single error line."""
    r = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-map", "0", "-f", "null", "-"], capture_output=True,
                       text=True, errors="replace")
    return r.stderr.strip()


def video_fps(path):
    """Frame rate of the first video stream (from ffmpeg's stream line), None when not found."""
    r = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True, errors="replace").stderr
    m = re.search(r"Video:.*?([\d.]+) fps", r) or re.search(r"Video:.*?([\d.]+) tbr", r)
    return float(m.group(1)) if m else None


def contact_sheet(video_or_pattern, out, cols=3, rows=3, width=640, fps=None, start=None, end=None):
    """Contact sheet of cols x rows frames spread evenly over a video or an image sequence (f.%04d.png).
    fps: of the image sequence (default 24); for a video the file's own frame rate is used (48 fps, 30 fps ...).
    Prints which frame (and second) each tile shows, in reading order - the PNG itself carries no labels (the
    ffmpeg of some installs has no drawtext). start / end (seconds, videos only): only that stretch - with
    cols x rows >= its frames this is a dense strip of every frame (e.g. 1 s at 24 fps: cols=6, rows=4)."""
    src = str(video_or_pattern)
    is_seq = "%" in src
    if is_seq:
        fps = fps or FPS
        n = len(list(Path(src).parent.glob("*.png")))
    else:
        fps = video_fps(src) or fps or FPS
        n = int(duration(src) * fps)
    f0 = 0
    if not is_seq and (start is not None or end is not None):
        s0 = max(0.0, float(start or 0.0))
        s1 = min(duration(src), float(end)) if end is not None else duration(src)
        f0, n = int(round(s0 * fps)), max(1, int(round((s1 - s0) * fps)))
    step = max(1, n // (cols * rows))
    ranged = not is_seq and (start is not None or end is not None)
    rng = ["-ss", f"{f0 / fps:.4f}", "-t", f"{n / fps:.4f}"] if ranged else []
    inp = ["-framerate", str(fps), "-i", src] if is_seq else [*rng, "-i", src]
    subprocess.run([ffmpeg(), "-y", "-v", "error", *inp, "-vf",
                    f"select='not(mod(n\\,{step}))',scale={width}:-1,tile={cols}x{rows}", "-frames:v", "1", str(out)],
                   check=True)
    tiles = [f0 + f for f in range(0, n, step)][: cols * rows]
    print(f"{out}: tiles left->right, top->bottom = frames " +
          ", ".join(f"{f} ({f / fps:.2f} s)" for f in tiles))
    return out


def compare(a, b):
    """A/B of two videos as text: size, length, file size, picture difference (PSNR / SSIM over the whole clip,
    the second one scaled to the first one's size) and whether the sound is bit-identical."""
    rows = []
    for v in (a, b):
        w, h = video_size(v)
        rows.append(f"{v}: {w}x{h}, {duration(v):.2f} s, {Path(v).stat().st_size / 1e6:.2f} MB")
    w, h = video_size(a)
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(a), "-i", str(b), "-lavfi",
                        f"[1:v]scale={w}:{h},split[b1][b2];[0:v]split[a1][a2];[a1][b1]psnr;[a2][b2]ssim",
                        "-f", "null", "-"], capture_output=True, text=True, errors="replace").stderr
    psnr = re.search(r"PSNR .*?average:([\d.inf]+)", r)
    ssim = re.search(r"SSIM .*?All:([\d.]+)", r)

    def audio_md5(v):
        o = subprocess.run([ffmpeg(), "-v", "error", "-i", str(v), "-map", "0:a:0?", "-f", "md5", "-"],
                           capture_output=True, text=True).stdout.strip()
        return o or None
    ma, mb = audio_md5(a), audio_md5(b)
    rows.append("picture: " + (f"PSNR {float(psnr.group(1)):.1f} dB" if psnr else "PSNR ?") +
                (f", SSIM {float(ssim.group(1)):.3f}" if ssim else "") +
                "  (PSNR > 40 dB / SSIM > 0.98: hard to see; < 30 dB: clearly different)")
    rows.append("sound: " + ("bit-identical" if ma and ma == mb else "no sound in one of them" if not (ma and mb)
                             else "different (python ear.py ab a b: how it sounds different)"))
    return "\n".join(rows)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "sheet":
        import argparse
        ap = argparse.ArgumentParser(prog="media.py sheet")
        ap.add_argument("video")
        ap.add_argument("out", nargs="?", default="contact_sheet.png")
        ap.add_argument("--from", dest="start", type=float, help="only from this second")
        ap.add_argument("--to", dest="end", type=float, help="only up to this second")
        ap.add_argument("--cols", type=int, default=3)
        ap.add_argument("--rows", type=int, default=3)
        ap.add_argument("--width", type=int, default=640, help="width of one tile")
        s = ap.parse_args(sys.argv[2:])
        contact_sheet(s.video, s.out, s.cols, s.rows, s.width, start=s.start, end=s.end)
    elif len(sys.argv) in (4, 5) and sys.argv[1] == "frame":
        out = sys.argv[4] if len(sys.argv) == 5 else "frame.png"
        fps = video_fps(sys.argv[2]) or FPS
        last = max(0.0, duration(sys.argv[2]) - 1.0 / fps)        # the container length ends after the last frame
        t = min(max(0.0, float(sys.argv[3])), last)
        if t < float(sys.argv[3]):
            print(f"({sys.argv[3]} s is after the last frame - taking the last frame at {t:.2f} s)")
        pre = max(0.0, t - 2.0)                                     # fast seek before, exact seek while decoding
        for tt in (t, t - 1.0 / fps, t - 2.0 / fps):                  # the audio may outlast the picture a little
            Path(out).unlink(missing_ok=True)
            subprocess.run([ffmpeg(), "-y", "-v", "error", "-ss", f"{pre:.4f}", "-i", sys.argv[2],
                            "-ss", f"{max(0.0, tt - pre):.4f}", "-frames:v", "1", out], check=True)
            if Path(out).exists():
                t = tt
                break
        else:                                       # the sound outlasts the picture by more: the real last frame
            subprocess.run([ffmpeg(), "-y", "-v", "error", "-sseof", "-3", "-i", sys.argv[2], "-update", "1",
                            "-an", out], check=True)
            if not Path(out).exists():
                raise SystemExit(f"no frame at {t:.2f} s in {sys.argv[2]}")
            print(f"(the picture ends before {t:.2f} s - taking its last frame)")
        print(f"{out}: frame {int(round(t * fps))} ({t:.2f} s), {'x'.join(map(str, video_size(out)))}")
    elif len(sys.argv) == 4 and sys.argv[1] == "compare":
        print(compare(sys.argv[2], sys.argv[3]))
    elif len(sys.argv) >= 3 and sys.argv[1] == "check":
        bad = 0
        for v in sys.argv[2:]:
            err = check_video(v)
            bad += bool(err)
            print(f"{v}: {'x'.join(map(str, video_size(v)))}, {duration(v):.2f} s, " + ("0 decode errors" if not err else "ERRORS: " + err[:300]))
        sys.exit(1 if bad else 0)
    else:
        print("usage: python media.py sheet <video or frames/f.%04d.png> [out.png] [--from s --to s --cols 6 --rows 4]\n"
              "       python media.py check <video> [...]     (decode check, exit 1 on errors)\n"
              "       python media.py compare <a> <b>         (A/B: size, length, PSNR/SSIM, sound identical?)\n"
              "       python media.py frame <video> <second> [out.png]   (one full-size frame)")
