"""Transcribe a song with word timestamps (faster-whisper).

uv run --with faster-whisper --with numpy --with imageio-ffmpeg \
    python scripts/transcribe.py SONG OUT.json [--lyrics lyrics.txt] [--lang en|de|auto] [--model medium]

--lyrics: the known lyric text; its rare words (names, acronyms) are given to Whisper as a hint.
--lang auto: language detection per segment (use for mixed German/English songs).
Prints one line per segment; the JSON keeps every word with start/end.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from audio_io import mono

ap = argparse.ArgumentParser()
ap.add_argument("audio")
ap.add_argument("out")
ap.add_argument("--lyrics")
ap.add_argument("--lang", default="auto")
ap.add_argument("--model", default="medium")
a = ap.parse_args()

from faster_whisper import WhisperModel  # noqa: E402

x, sr = mono(a.audio)
# resample to exactly 16 kHz for any input rate (an integer decimation factor is only exact for 48 kHz –
# for 44.1 kHz it squeezed all word times by 8 %): moving-average low-pass, then linear interpolation
k = max(1, round(sr / 16000))
xs = np.convolve(x, np.ones(k, dtype=np.float32) / k, mode="same") if k > 1 else x
pos = np.arange(0, len(x) - 1, sr / 16000.0)
samples = np.interp(pos, np.arange(len(xs)), xs).astype(np.float32)
print(f"audio {len(x) / sr:.2f} s at {sr} Hz → {len(samples) / 16000:.2f} s at 16 kHz")

prompt = None
if a.lyrics:
    text = " ".join(ln.strip() for ln in Path(a.lyrics).read_text(encoding="utf-8").splitlines() if ln.strip() and not re.match(r"^\s*[\[(]", ln))
    prompt = text[:400]

model = WhisperModel(a.model, device="cpu", compute_type="int8")
kw = dict(word_timestamps=True, initial_prompt=prompt, vad_filter=False)
if a.lang == "auto":
    kw.update(language=None, multilingual=True)
else:
    kw.update(language=a.lang)
segments, info = model.transcribe(samples, **kw)
res = []
for s in segments:
    words = [{"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2)} for w in (s.words or [])]
    res.append({"s": round(s.start, 2), "e": round(s.end, 2), "t": s.text, "words": words})
    print(f"{s.start:7.2f} {s.end:7.2f} {s.text}", flush=True)
Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
