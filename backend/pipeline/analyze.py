"""Tempo, riff hits and long held words of a song.

uv run --with numpy --with imageio-ffmpeg python scripts/analyze.py SONG [--timing timing.json --lyrics lyrics.txt]
  → prints BPM + first beat offset, writes hits.json next to SONG (or --hits PATH),
    and (with --timing/--lyrics) lists words held longer than 1 s = candidates for the held-note effect.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np  # noqa: E402
from audio_io import mono  # noqa: E402


def spectrum(x, sr, hop=512, n=2048):
    win = np.hanning(n)
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * win
    return np.abs(np.fft.rfft(fr, axis=1)), sr / hop, np.fft.rfftfreq(n, 1 / sr)


def tempo(x, sr):
    mag, fps, _ = spectrum(x, sr)
    mag = np.log1p(mag * 10)
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(axis=1)
    flux = np.maximum(flux - np.convolve(flux, np.ones(16) / 16, mode="same"), 0)
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    best, best_bpm = -1, 0
    for bpm in np.arange(70, 181, 0.1):
        lag = fps * 60 / bpm
        s = sum(np.interp(lag * k, np.arange(len(ac)), ac) for k in (1, 2, 4))
        s *= np.exp(-((np.log2(bpm / 120)) ** 2) * 0.5)
        if s > best:
            best, best_bpm = s, bpm
    period = 60 / best_bpm
    t = np.arange(len(flux)) / fps
    phases = np.linspace(0, period, 200, endpoint=False)
    scores = [np.interp(np.arange(p, t[-1], period), t, flux).sum() for p in phases]
    return round(float(best_bpm), 2), round(float(phases[int(np.argmax(scores))]), 3)


def hits(x, sr):
    """sudden loud hits (often right after a short silence) – drive flashes / shakes / lightning"""
    mag, fps, f = spectrum(x, sr)
    low = mag[:, (f > 40) & (f < 400)].sum(axis=1)
    e = np.log1p(low * 0.5 + mag.sum(axis=1) * 0.1)
    out, last = [], -10.0
    for i in range(int(fps * 0.4), len(e) - 3):
        jump = e[i:i + 3].mean() - e[i - int(fps * 0.25):i].mean()
        t = i / fps
        if jump > 0.9 and t - last > 0.35:
            out.append((round(t, 3), round(float(jump), 2)))
            last = t
    vals = sorted(j for _, j in out)
    thr = vals[int(len(vals) * 0.65)] if vals else 0
    return [t for t, _ in out], [t for t, j in out if j >= thr]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--hits")
    ap.add_argument("--timing")
    ap.add_argument("--lyrics")
    a = ap.parse_args()
    x, sr = mono(a.audio)
    bpm, off = tempo(x, sr)
    print(json.dumps({"bpm": bpm, "offset": off, "duration": round(len(x) / sr, 2)}))
    h, big = hits(x, sr)
    path = a.hits or os.path.join(os.path.dirname(os.path.abspath(a.audio)), "hits.json")
    json.dump({"hits": h, "big": big}, open(path, "w"))
    print(f"{len(h)} hits, {len(big)} big → {path}; big: {big[:16]}")
    if a.timing and a.lyrics:
        from align import lyric_lines

        T = json.load(open(a.timing))
        L = lyric_lines(a.lyrics)
        print("\nheld-note candidates (word sung > 1 s):")
        for i, (t, l) in enumerate(zip(T, L)):
            ws = l.split(" ")
            for j, (s, e) in enumerate(zip(t["words"], t["ends"])):
                if e - s > 1.0:
                    print(f"  line {i:2d} word {j}: {ws[j]!r:22} {s:7.2f}–{e:7.2f} ({e - s:.2f} s){'  last word' if j == len(ws) - 1 else ''}")
