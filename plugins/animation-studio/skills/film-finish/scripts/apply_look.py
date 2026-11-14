"""Lay the project look over a video: paper + film grain + vignette (overlay image sequence, multiplied, looped).

Usage:
  uv run --no-project python apply_look.py film.mp4 [-o film_look.mp4] [--look standard|<look folder>] [--strength 1.0]

The overlay frames live in <skill>/assets/look/<look>/mp_0000.jpg ... (+ look.json describing how they were made).
--strength < 1 mixes the look in more weakly (0 = off). The audio is copied unchanged.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402
from encoding import h264  # noqa: E402  (preview: PREVIEW=1 -> NVENC)

LOOKS = Path(__file__).resolve().parent.parent / "assets" / "look"


def video_info(src):
    """-> (width, height, frame rate as ffmpeg string) of the first video stream."""
    ffprobe = config.get("ffprobe")
    if ffprobe:
        info = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                               "stream=width,height,r_frame_rate", "-of", "csv=p=0", str(src)],
                              capture_output=True, text=True).stdout.strip().split(",")
        if len(info) >= 3:
            return info[0], info[1], info[2]
    # fallback without ffprobe: parse the stream line of "ffmpeg -i"
    err = subprocess.run([config.need("ffmpeg"), "-hide_banner", "-i", str(src)],
                         capture_output=True, text=True, errors="replace").stderr
    line = next((l for l in err.splitlines() if "Video:" in l), "")
    size = re.search(r"\b(\d{2,5})x(\d{2,5})\b", line)
    rate = re.search(r"([\d.]+)\s*fps", line) or re.search(r"([\d.]+)\s*tbr", line)
    if not size or not rate:
        sys.exit(f"Could not read the video size/frame rate of {src}")
    return size.group(1), size.group(2), rate.group(1)


def main():
    ap = argparse.ArgumentParser(description="Apply the film look (paper, grain, vignette) to a video.")
    ap.add_argument("video")
    ap.add_argument("-o", "--out")
    ap.add_argument("--look", default="standard")
    ap.add_argument("--strength", type=float, default=1.0)
    a = ap.parse_args()

    src = Path(a.video).resolve()
    out = Path(a.out).resolve() if a.out else src.with_name(src.stem + "_look.mp4")
    look = LOOKS / a.look                                   # a look name, or a folder made by shaders_render.py
    if not (look / "mp_0000.jpg").exists() and (Path(a.look) / "mp_0000.jpg").exists():
        look = Path(a.look).resolve()
    if not (look / "mp_0000.jpg").exists():
        sys.exit(f"Look missing: {look}")
    w, h, rate = video_info(src)
    s = max(0.0, min(1.0, a.strength))
    # overlay looped, scaled to the video size; multiply; strength via mixing with the original
    fc = (f"[1:v]scale={w}:{h},format=gbrp[o];[0:v]format=gbrp,split[v][orig];"
          f"[v][o]blend=all_mode=multiply:shortest=1[m];"
          f"[orig][m]blend=all_expr='A*(1-{s})+B*{s}':shortest=1,scale=out_range=tv,format=yuv420p[out]")
    # out_range=tv: the JPEG overlay would otherwise make the output full range (yuvj420p)
    cmd = [config.need("ffmpeg"), "-y", "-loglevel", "error", "-i", str(src),
           "-stream_loop", "-1", "-framerate", rate, "-i", str(look / "mp_%04d.jpg"),
           "-filter_complex", fc, "-map", "[out]", "-map", "0:a?", *h264(), "-c:a", "copy", str(out)]
    # no -shortest: the picture decides the length (AAC is often a few ms shorter)
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        sys.exit(r.stderr[-2000:])
    print(f"Look '{a.look}' (strength {s}) -> {out}")


if __name__ == "__main__":
    main()
