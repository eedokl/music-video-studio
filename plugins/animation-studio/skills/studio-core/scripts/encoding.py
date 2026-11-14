"""Shared video encoding for all scripts: final version (x264, best quality) or fast preview (NVENC).

Turn on the preview: environment variable PREVIEW=1   (e.g. in Git Bash: PREVIEW=1 uv run ... make_full_cut.py)
  (the older variable name VORSCHAU=1 is accepted too)
  - x264 crf 18 (default):  803 frames in 32 s, 11 MB - for everything you want to watch or hand on
  - NVENC (RTX 5060 Ti):    803 frames in 1.4 s, 16 MB - for work in progress; a bit larger, minimally softer
Usage in scripts:
  from encoding import h264
  subprocess.run([FF, ..., *h264(), "-pix_fmt", "yuv420p", out])     # instead of "-c:v", "libx264", "-crf", "18"
"""
import os


def _on(var):
    return os.environ.get(var, "").strip().lower() not in ("", "0", "no", "nein", "false", "off")


PREVIEW = _on("PREVIEW") or _on("VORSCHAU")     # second name: legacy variable of older pipelines


def h264(crf=18, preset="medium"):
    """ffmpeg options for H.264: NVENC in preview mode, otherwise x264."""
    if PREVIEW:
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", str(crf + 3), "-b:v", "0"]
    return ["-c:v", "libx264", "-crf", str(crf), "-preset", preset]


def hint():
    return "PREVIEW (NVENC)" if PREVIEW else "final version (x264)"
