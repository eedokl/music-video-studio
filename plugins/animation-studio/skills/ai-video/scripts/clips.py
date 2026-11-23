"""Conventions every generated clip follows, so that cutting and measuring agree.

Each clip <name>.mp4 has <name>.json next to it:
  {"kind": "ltx_lipsync|ltx_moving|s2v|wan", "song_start": 12.34, "fps": 24, "frames": 97, "delay_frames": 1,
   "lead_in": 0.25, "seed": 41, "strength": 1.0, "image": "...", "prompt": "..."}
Placement on the song timeline (the ONE rule used by the cut and by the lip measurement):
  film time t shows clip frame  floor((t + dt - song_start) * fps) - delay_frames
  dt = lag / 24 s from the measurement (lag > 0: the mouth is late -> show a later frame).
Clips WITHOUT their own sound (e.g. an old Wan clip of her singing) are re-placed by the mouth curve
(mouth.py fit): the json then also has "clip_start" (frame of the clip at song_start) and "tempo" (0.9-1.1):
  frame = clip_start + floor((t + dt - song_start) * fps * tempo) - delay_frames
A clip rendered on SLOWED vocals (shot key "speed", e.g. 1.18: the vocals are stretched to 1/1.18 of their tempo
before the render) is placed by the same rule: its json has "tempo": 1.18, so the film shows it 1.18x faster - the
lips are back in real time, the body moves faster (takes that read as slow motion).
LTX-2.3 starts sluggishly from the still (~0.3 s): clips start LEAD_IN s before the shot and the cut skips that part.
The decoded LTX picture runs ~1 frame (~50 ms) early against its input sound: LTX_DELAY_FRAMES = 1.
"""
import json
import math
import subprocess
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
from media import ffmpeg  # noqa: E402

LTX_FPS = 24
LTX_LEAD_IN = 0.25          # s of vocals before the shot (the sluggish start is cut away)
LTX_DELAY_FRAMES = 1        # LTX picture ~1 frame early -> place it 1 frame later
LTX_MAX_FRAMES = 121        # ~5 s at 1280x704 peaks near 45 GB RAM - longer shots: shorten the lead-in or split
LTX_LONG_SIZE = (1024, 576) # at this size (or smaller) one clip may be ...
LTX_LONG_FRAMES = 217       # ... 9 s long: 7 of 7 renders went through on the reference machine (2026-11)
S2V_FPS = 16
S2V_MAX_SECONDS = 4.7       # longer S2V parts drift to profile; split longer shots


SPEED_MAX = 1.5             # shot "speed": tested at 1.18 (walking takes); above 1.5 the vocals are too slow to sing to


def ltx_frames(seconds, lead_in=LTX_LEAD_IN, speed=1.0):
    """Frames (8n+1) covering lead-in + shot + 2 spare frames; speed > 1 = rendered on vocals slowed to 1/speed and
    shown `speed` times faster, so the clip is that much longer than the shot."""
    n = (seconds + lead_in) * speed * LTX_FPS + 2
    return int(math.ceil((n - 1) / 8)) * 8 + 1


def ltx_max_frames(w=1280, h=704):
    """Longest LTX clip (frames, 8n+1) known to render at this frame size: 121 at 1280x704, 217 at 1024x576 or
    smaller. Only these two points were tried - nothing is interpolated between them."""
    return LTX_LONG_FRAMES if w * h <= LTX_LONG_SIZE[0] * LTX_LONG_SIZE[1] else LTX_MAX_FRAMES


def ltx_fit(seconds, lead_in=LTX_LEAD_IN, max_frames=LTX_MAX_FRAMES, speed=1.0):
    """(frames, lead_in) within max_frames (default LTX_MAX_FRAMES; a long single shot at 1024x576 passes
    ltx_max_frames(1024, 576)): the lead-in shrinks first for long shots."""
    li = lead_in
    while ltx_frames(seconds, li, speed) > max_frames and li > 0.05:
        li = round(li - 0.05, 2)
    return min(ltx_frames(seconds, li, speed), max_frames), li


def ltx_seconds(max_frames=LTX_MAX_FRAMES, speed=1.0, lead_in=0.05):
    """Longest shot (s) one clip of max_frames covers at this speed (smallest lead-in)."""
    return round((max_frames - 2) / LTX_FPS / speed - lead_in, 2)


def stretch_audio(wav, speed):
    """In place: the sound slowed to 1/speed of its tempo, pitch kept (ffmpeg atempo) - the sound input of a clip that
    is shown `speed` times faster afterwards (clip json "tempo")."""
    wav = Path(wav)
    tmp = wav.with_name(wav.stem + ".stretch.wav")
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(wav), "-af", f"atempo={1 / speed:.6f}", str(tmp)], check=True)
    tmp.replace(wav)
    return wav


def s2v_frames(seconds):
    """Frames (4n+1) at 16 fps covering the shot + 0.12 s."""
    return int(math.ceil(((seconds + 0.12) * S2V_FPS - 1) / 4)) * 4 + 1


def cut_audio(src, start, dur, out):
    """Excerpt of a sound file (sample rate kept); start < 0 pads silence in front."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if start >= 0:
        cmd = [ffmpeg(), "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src), str(out)]
    else:
        cmd = [ffmpeg(), "-y", "-v", "error", "-t", f"{dur + start:.3f}", "-i", str(src), "-af",
               f"adelay={int(-start * 1000)}:all=1", str(out)]
    subprocess.run(cmd, check=True)
    return out


def quiet_start(src, start, back=0.5, thresh_db=-40.0):
    """Move a window start back (at most `back` s) into the nearest quiet 10 ms frame, so the model hears the singer
    START instead of a cut-off syllable (claudia-live: windows begin in a silence). Returns the new start."""
    import numpy as np
    import media
    if start <= 0:
        return start
    a = max(0.0, start - back)
    y = media.decode(src, 16000)[int(a * 16000):int(start * 16000) + 160]
    n = 160
    k = len(y) // n
    if k == 0:
        return start
    db = 20 * np.log10(np.sqrt((y[:k * n].reshape(k, n) ** 2).mean(1)) + 1e-9)
    if db[-1] <= thresh_db:
        return start
    quiet = np.nonzero(db <= thresh_db)[0]
    return round(a + (quiet[-1] * n) / 16000, 3) if len(quiet) else start


def prepare_vocal(wav, rms_db=-16.0, peak_db=-1.0, ramp=0.015, voiced_db=-34.0):
    """In place: level the sung part to rms_db (RMS of the frames above voiced_db only), limit peaks to peak_db,
    15 ms fade in/out (claudia-live bewegung_test_b.normalisieren, used for every LTX/InfiniteTalk vocal input since
    Live V2). Returns the measured RMS (dBFS) before levelling."""
    import wave
    import numpy as np
    with wave.open(str(wav), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError(f"{wav}: 16-bit WAV expected")
    x = np.frombuffer(raw, np.int16).astype(np.float32).reshape(-1, ch) / 32768
    m = x.mean(1)
    f = max(1, int(0.01 * sr))
    fr = np.sqrt(np.mean(m[:len(m) // f * f].reshape(-1, f) ** 2, 1)) if len(m) >= f else np.array([0.0])
    voiced = fr[fr > 10 ** (voiced_db / 20)]
    rms = float(np.sqrt(np.mean(voiced ** 2))) if len(voiced) else float(np.sqrt(np.mean(m ** 2)) + 1e-9)
    x = np.clip(x * (10 ** (rms_db / 20) / max(rms, 1e-6)), -10 ** (peak_db / 20), 10 ** (peak_db / 20))
    r = min(int(ramp * sr), len(x) // 2)
    if r > 0:
        rp = np.linspace(0, 1, r, dtype=np.float32)[:, None]
        x[:r] *= rp
        x[-r:] *= rp[::-1]
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    return round(20 * np.log10(max(rms, 1e-9)), 1)


def meta_path(clip):
    return Path(clip).with_suffix(".json")


def write_meta(clip, **m):
    meta_path(clip).write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")


def read_meta(clip):
    return json.loads(meta_path(clip).read_text(encoding="utf-8"))


def frame_index(t, meta, lag=0, n=None):
    """Clip frame shown at song time t (see module doc); clamped to the clip when n is given."""
    i = int(meta.get("clip_start", 0)) + int(math.floor((t + lag / 24.0 - meta["song_start"]) * meta["fps"] *
                                                         meta.get("tempo", 1.0) + 1e-6)) - meta.get("delay_frames", 0)
    return i if n is None else min(max(i, 0), n - 1)
