"""Shared video encoding for all scripts: final version (x264, best quality) or fast preview (NVENC).

Turn on the preview: environment variable PREVIEW=1   (e.g. in Git Bash: PREVIEW=1 uv run build.py film)
  (the older variable name VORSCHAU=1 is accepted too)
  - x264 crf 18 (default):  for everything you want to watch or hand on
  - NVENC preview:          much faster on an NVIDIA GPU (reference machine: 803 frames in 1.4 s instead of 32 s),
                            a bit larger, minimally softer - for work in progress
  The NVENC encoder is probed once per run; without it (no NVIDIA GPU / driver, ffmpeg without nvenc) the preview
  falls back to x264 -preset veryfast instead of failing every encode.
Usage in scripts:
  from encoding import h264
  subprocess.run([FF, ..., *h264(), "-pix_fmt", "yuv420p", out])     # instead of "-c:v", "libx264", "-crf", "18"
"""
import os
import subprocess


def _on(var):
    return os.environ.get(var, "").strip().lower() not in ("", "0", "no", "nein", "false", "off")


PREVIEW = _on("PREVIEW") or _on("VORSCHAU")     # second name: legacy variable of older pipelines
_NVENC = None


def nvenc_ok():
    """Can this ffmpeg encode with h264_nvenc on this machine? (one tiny test encode, cached)"""
    global _NVENC
    if _NVENC is None:
        try:
            import config
            r = subprocess.run([config.need("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=s=256x144:d=0.1",
                                "-frames:v", "2", "-c:v", "h264_nvenc", "-f", "null", "-"],
                               capture_output=True, timeout=60)
            _NVENC = r.returncode == 0
        except (OSError, subprocess.SubprocessError, SystemExit):
            _NVENC = False
        if not _NVENC:
            print("   PREVIEW: no NVENC encoder here - fast x264 (veryfast) instead")
    return _NVENC


def h264(crf=18, preset="medium"):
    """ffmpeg options for H.264: NVENC in preview mode (x264 veryfast without NVENC), otherwise x264."""
    if PREVIEW:
        if nvenc_ok():
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", str(crf + 3), "-b:v", "0"]
        return ["-c:v", "libx264", "-crf", str(crf + 3), "-preset", "veryfast"]
    return ["-c:v", "libx264", "-crf", str(crf), "-preset", preset]


def hint():
    if not PREVIEW:
        return "final version (x264)"
    return "PREVIEW (NVENC)" if nvenc_ok() else "PREVIEW (x264 veryfast)"
