"""Size-targeted encodes shared by the video skills: two-pass x264 to hit a file size (small < 30 MB, mail ~12 MB).

    import _studio; _studio.use("film-finish")
    from encode import encode_target
    encode_target(src, out, mb=29.0, width=1280, height=720, audio_k=128, dur=seconds)
    place(tmp, final)   # rename a finished temp file; a file locked by a player keeps a new name
"""
import os
import subprocess
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
from media import ffmpeg  # noqa: E402


def encode_target(src, out, mb, width, height, audio_k, dur):
    vbit = int((mb * 8 * 1024 / max(dur, 1) - audio_k) * 0.95)
    passlog = str(out.with_suffix(""))
    common = [ffmpeg(), "-y", "-v", "error", "-i", str(src), "-vf", f"scale={width}:{height}:flags=lanczos",
              "-c:v", "libx264", "-preset", "slow", "-b:v", f"{vbit}k", "-pix_fmt", "yuv420p"]
    subprocess.run(common + ["-pass", "1", "-passlogfile", passlog, "-an", "-f", "mp4", os.devnull], check=True)
    subprocess.run(common + ["-pass", "2", "-passlogfile", passlog, "-c:a", "aac", "-b:a", f"{audio_k}k",
                             "-movflags", "+faststart", str(out)], check=True)
    for f in Path(out.parent).glob(out.stem + "*.log*"):
        f.unlink(missing_ok=True)


def place(tmp, final):
    try:
        os.replace(tmp, final)
        return final
    except PermissionError:
        alt = final.with_name(f"{final.stem}_{time.strftime('%H%M%S')}{final.suffix}")
        os.replace(tmp, alt)
        print(f"   {final.name} is locked (open in a player?) - new file kept as {alt.name}")
        return alt
