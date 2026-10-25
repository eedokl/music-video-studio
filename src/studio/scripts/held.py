"""Vocal loudness + pitch contour of held notes → held.json (30 values per second).

uv run --with numpy --with imageio-ffmpeg python scripts/held.py SONG held.json NAME:START:END [NAME:START:END ...]
e.g.  held.py song.wav src/held.json fifteen1:71.0:75.4 roles3:183.1:186.4
Take START/END from the held-note candidates of analyze.py (start a bit before, end a bit after).
The vocal is isolated roughly with mid-minus-side; pitch has octave errors on full mixes,
src/vocal.ts folds and smooths it, so only use it for gentle motion.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from audio_io import load

FPS = 30


def analyse(x, sr, a, b):
    mid = (x[:, 0] + x[:, 1]) / 2
    side = (x[:, 0] - x[:, 1]) / 2
    n = 4096
    win = np.hanning(n)
    f = np.fft.rfftfreq(n, 1 / sr)
    band = (f > 200) & (f < 4000)
    env, pitch = [], []
    for i in range(int((b - a) * FPS)):
        c = int((a + i / FPS) * sr)
        M = np.abs(np.fft.rfft(mid[c - n // 2 : c + n // 2] * win))
        S = np.abs(np.fft.rfft(side[c - n // 2 : c + n // 2] * win))
        spec = np.maximum(M - S, 0)
        env.append(float(np.sqrt((spec[band] ** 2).sum())))
        best, bf = 0, 0
        for f0 in np.arange(90, 700, 2.0):
            s = sum(spec[j] / (h + 1) for h, j in enumerate(int(np.rint(f0 * hh * n / sr)) for hh in (1, 2, 3, 4)) if j < len(spec))
            if s > best:
                best, bf = s, f0
        pitch.append(float(bf))
    env = np.array(env) / max(env)
    env = np.convolve(env, np.ones(3) / 3, mode="same")
    p = np.array(pitch)
    voiced = env > 0.25
    semis = np.where(voiced, 12 * np.log2(p / np.median(p[voiced])), 0) if voiced.any() else np.zeros_like(p)
    return {"t0": a, "fps": FPS, "env": [round(v, 3) for v in env.tolist()], "pitch": [round(v, 2) for v in semis.tolist()]}


if __name__ == "__main__":
    audio, out, *specs = sys.argv[1:]
    x, sr = load(audio)
    res = {}
    for sp in specs:
        name, a, b = sp.split(":")
        res[name] = analyse(x, sr, float(a), float(b))
        print(f"{name}: {a}–{b}, peak loudness at {float(a) + int(np.argmax(res[name]['env'])) / FPS:.2f}s")
    Path(out).write_text(json.dumps(res))
