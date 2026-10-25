"""Helpers of the standalone analysis scripts (src/studio/scripts)."""

import wave

import align
import audio_io
import numpy as np
import pytest


def write_wav(path, samples: np.ndarray, sr: int = 22050):
    """16-bit PCM wav; samples: float in [-1, 1], shape (n,) or (n, channels)."""
    x = samples if samples.ndim == 2 else samples[:, None]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def test_lyric_lines_skip_headers_and_stage_directions(tmp_path):
    f = tmp_path / "lyrics.txt"
    f.write_text("[Verse 1]\nFirst line\n(Robotic voice)\n\n  Second line  \n", encoding="utf-8")
    assert align.lyric_lines(f) == ["First line", "Second line"]


def test_norm():
    assert align.norm("Don't-Stop!") == "dontstop"


def test_load_mono_wav_returns_stereo(tmp_path):
    t = np.arange(2205) / 22050
    tone = 0.5 * np.sin(2 * np.pi * 440 * t)
    write_wav(tmp_path / "mono.wav", tone)
    x, sr = audio_io.load(str(tmp_path / "mono.wav"))
    assert sr == 22050
    assert x.shape == (2205, 2)
    assert x.dtype == np.float32
    np.testing.assert_allclose(x[:, 0], x[:, 1])
    np.testing.assert_allclose(x[:, 0], tone, atol=1e-4)


def test_load_stereo_wav_keeps_channels(tmp_path):
    left, right = np.full(100, 0.25), np.full(100, -0.5)
    write_wav(tmp_path / "st.wav", np.stack([left, right], axis=1), sr=8000)
    x, sr = audio_io.load(str(tmp_path / "st.wav"))
    assert sr == 8000
    assert x[:, 0] == pytest.approx(0.25, abs=1e-4)
    assert x[:, 1] == pytest.approx(-0.5, abs=1e-4)
