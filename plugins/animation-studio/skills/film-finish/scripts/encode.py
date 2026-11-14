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


MIN_VIDEO_K, MIN_AUDIO_K = 120, 48


def encode_target(src, out, mb, width, height, audio_k, dur):
    """Two-pass encode aimed at mb (x 1.024 MB). The result is checked: one re-encode with a corrected bitrate when it
    came out too big; a film too long for the size even at the minimum bitrate gets a warning, never a failed encode."""
    out = Path(out)
    limit = mb * 1.024e6
    budget = mb * 8 * 1024 / max(dur, 1)                    # kbit/s for picture + sound
    if budget - audio_k < 4 * MIN_VIDEO_K:                  # long film: give the picture the bits, not the sound
        audio_k = max(MIN_AUDIO_K, min(audio_k, int(budget * 0.15)))
    vbit = max(MIN_VIDEO_K, int((budget - audio_k) * 0.95))
    for attempt in (1, 2):
        _two_pass(src, out, width, height, vbit, audio_k)
        size = out.stat().st_size
        if size <= limit:
            return out
        if attempt == 1 and vbit > MIN_VIDEO_K:
            # over: scale the video bitrate by what was missed (audio part stays), a little extra margin
            vbit = max(MIN_VIDEO_K, int(vbit * (limit - audio_k * 125 * dur) / max(size - audio_k * 125 * dur, 1) * 0.95))
            print(f"   {out.name}: {size / 1e6:.1f} MB > {limit / 1e6:.1f} MB - re-encoding at {vbit} kbit/s")
        else:
            break
    print(f"   WARNING: {out.name} is {size / 1e6:.1f} MB, over the {limit / 1e6:.1f} MB target "
          f"({dur:.0f} s is too long for this size at {MIN_VIDEO_K} kbit/s)")
    return out


def _two_pass(src, out, width, height, vbit, audio_k):
    passlog = str(out.with_suffix(""))
    common = [ffmpeg(), "-y", "-v", "error", "-i", str(src), "-vf", f"scale={width}:{height}:flags=lanczos",
              "-c:v", "libx264", "-preset", "slow", "-b:v", f"{vbit}k", "-pix_fmt", "yuv420p"]
    try:
        subprocess.run(common + ["-pass", "1", "-passlogfile", passlog, "-an", "-f", "mp4", os.devnull], check=True)
        subprocess.run(common + ["-pass", "2", "-passlogfile", passlog, "-c:a", "aac", "-b:a", f"{audio_k}k",
                                 "-movflags", "+faststart", str(out)], check=True)
    finally:
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
