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
    hop = sr // fps
    k = len(y) // hop
    if k == 0:
        return np.zeros(0, bool)
    rms = np.sqrt(np.mean(y[: k * hop].reshape(k, hop) ** 2, axis=1))
    db = 20 * np.log10(rms + 1e-12)
    v = db > np.percentile(db, 90) - 24
    return np.convolve(v.astype(float), np.ones(3) / 3, mode="same") > 0.5


def check_video(path):
    """Decode the whole file; returns "" when there is not a single error line."""
    r = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-map", "0", "-f", "null", "-"], capture_output=True,
                       text=True, errors="replace")
    return r.stderr.strip()


def contact_sheet(video_or_pattern, out, cols=3, rows=3, width=640, fps=FPS):
    """Contact sheet of cols x rows frames spread evenly over a video or an image sequence (f.%04d.png)."""
    src = str(video_or_pattern)
    is_seq = "%" in src
    if is_seq:
        n = len(list(Path(src).parent.glob("*.png")))
    else:
        n = int(duration(src) * fps)
    step = max(1, n // (cols * rows))
    inp = ["-framerate", str(fps), "-i", src] if is_seq else ["-i", src]
    subprocess.run([ffmpeg(), "-y", "-v", "error", *inp, "-vf",
                    f"select='not(mod(n\\,{step}))',scale={width}:-1,tile={cols}x{rows}", "-frames:v", "1", str(out)],
                   check=True)
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "sheet":
        print(contact_sheet(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "contact_sheet.png"))
    else:
        print("usage: python media.py sheet <video or frames/f.%04d.png> [out.png]")
