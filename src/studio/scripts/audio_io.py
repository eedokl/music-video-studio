"""Load any audio file (wav, mp3, m4a, ...) as float32 arrays. Shared by the analysis scripts."""

import sys as _sys

if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles

import os
import subprocess
import tempfile
import wave

import numpy as np


def _decode_to_wav(path: str) -> str:
    """Decode non-wav audio with the ffmpeg binary shipped by imageio-ffmpeg."""
    import imageio_ffmpeg

    out = os.path.join(tempfile.mkdtemp(), "audio.wav")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", path, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", out], check=True)
    return out


def load(path: str):
    """Return (stereo [n, 2] float32, sample_rate)."""
    if not path.lower().endswith(".wav"):
        path = _decode_to_wav(path)
    try:
        with wave.open(path) as w:
            sr, ch, raw = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    except wave.Error:  # e.g. 32-bit float wav (Demucs output) – let ffmpeg convert it
        with wave.open(_decode_to_wav(path)) as w:
            sr, ch, raw = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    x = x.reshape(-1, ch)
    if ch == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2], sr


def mono(path: str):
    x, sr = load(path)
    return x.mean(axis=1), sr


def duration(path: str) -> float:
    x, sr = load(path)
    return len(x) / sr
