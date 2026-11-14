"""Size-targeted encodes shared by the video skills: two-pass x264 to hit a file size (small < 30 MB, mail ~12 MB).

    import _studio; _studio.use("film-finish")
    from encode import encode_target
    r = encode_target(src, out, mb=29.0, width=1280, height=720, audio_k=128, dur=seconds)
    r.met, r.size_mb, r.note        # False + a reason when the file is still over the target
    place(tmp, final)   # rename a finished temp file; a file locked by a player keeps a new name
    over_note(path, mb)  # "" or " - OVER the 29 MB target" for the size line callers print
"""
import os
import subprocess
import time
from collections import namedtuple
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
from media import ffmpeg  # noqa: E402


MIN_VIDEO_K, MIN_AUDIO_K = 120, 48
Encoded = namedtuple("Encoded", "path met size_mb target_mb note")


def over_note(path, mb):
    """" - OVER the <mb> MB target" when the file at path is bigger than the target (same x 1.024 rule), else ""."""
    size = Path(path).stat().st_size
    return f" - OVER the {mb:g} MB target" if size > mb * 1.024e6 else ""


def encode_target(src, out, mb, width, height, audio_k, dur):
    """Two-pass encode aimed at mb (x 1.024 MB). The result is checked: one re-encode with a corrected bitrate when it
    came out too big. Never fails because of the size: returns Encoded(path, met, size_mb, target_mb, note) - met is
    False and note says why when the file is still over (the minimum bitrate was the limit = the film is too long
    for this size, or x264 overshot even after the corrected re-encode)."""
    out = Path(out)
    limit = mb * 1.024e6
    budget = mb * 8 * 1024 / max(dur, 1)                    # kbit/s for picture + sound
    if budget - audio_k < 4 * MIN_VIDEO_K:                  # long film: give the picture the bits, not the sound
        audio_k = max(MIN_AUDIO_K, min(audio_k, int(budget * 0.15)))
    vbit = max(MIN_VIDEO_K, int((budget - audio_k) * 0.95))
    tries = []
    for attempt in (1, 2):
        _two_pass(src, out, width, height, vbit, audio_k)
        size = out.stat().st_size
        tries.append(vbit)
        if size <= limit:
            return Encoded(out, True, round(size / 1e6, 2), mb, "")
        if attempt == 1 and vbit > MIN_VIDEO_K:
            # over: scale the video bitrate by what was missed (audio part stays), a little extra margin
            vbit = max(MIN_VIDEO_K, int(vbit * (limit - audio_k * 125 * dur) / max(size - audio_k * 125 * dur, 1) * 0.95))
            print(f"   {out.name}: {size / 1e6:.1f} MB > {limit / 1e6:.1f} MB - re-encoding at {vbit} kbit/s")
        else:
            break
    if tries[-1] <= MIN_VIDEO_K:
        note = (f"still {size / 1e6:.1f} MB at the minimum video bitrate {MIN_VIDEO_K} kbit/s + {audio_k} kbit/s sound - "
                f"{dur:.0f} s is too long for {mb:g} MB")
    else:
        note = (f"still {size / 1e6:.1f} MB after a re-encode at {tries[-1]} kbit/s (first try {tries[0]} kbit/s) - "
                f"x264 overshot the bitrate (a very detailed picture); a slightly smaller target fixes it")
    print(f"   WARNING: {out.name} is over the {mb:g} MB target: {note}")
    return Encoded(out, False, round(size / 1e6, 2), mb, note)


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
