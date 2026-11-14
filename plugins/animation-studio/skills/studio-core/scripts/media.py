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


def contact_sheet(video_or_pattern, out, cols=3, rows=3, width=640, fps=None):
    """Contact sheet of cols x rows frames spread evenly over a video or an image sequence (f.%04d.png).
    fps: of the image sequence (default 24); for a video the file's own frame rate is used (48 fps, 30 fps ...).
    Prints which frame (and second) each tile shows, in reading order - the PNG itself carries no labels (the
    ffmpeg of some installs has no drawtext)."""
    src = str(video_or_pattern)
    is_seq = "%" in src
    if is_seq:
        fps = fps or FPS
        n = len(list(Path(src).parent.glob("*.png")))
    else:
        fps = video_fps(src) or fps or FPS
        n = int(duration(src) * fps)
    step = max(1, n // (cols * rows))
    inp = ["-framerate", str(fps), "-i", src] if is_seq else ["-i", src]
    subprocess.run([ffmpeg(), "-y", "-v", "error", *inp, "-vf",
                    f"select='not(mod(n\\,{step}))',scale={width}:-1,tile={cols}x{rows}", "-frames:v", "1", str(out)],
                   check=True)
    tiles = list(range(0, n, step))[: cols * rows]
    print(f"{out}: tiles left->right, top->bottom = frames " +
          ", ".join(f"{f} ({f / fps:.2f} s)" for f in tiles))
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "sheet":
        contact_sheet(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "contact_sheet.png")
    elif len(sys.argv) >= 3 and sys.argv[1] == "check":
        bad = 0
        for v in sys.argv[2:]:
            err = check_video(v)
            bad += bool(err)
            print(f"{v}: {'x'.join(map(str, video_size(v)))}, {duration(v):.2f} s, " + ("0 decode errors" if not err else "ERRORS: " + err[:300]))
        sys.exit(1 if bad else 0)
    else:
        print("usage: python media.py sheet <video or frames/f.%04d.png> [out.png]\n"
              "       python media.py check <video> [...]     (decode check, exit 1 on errors)")
