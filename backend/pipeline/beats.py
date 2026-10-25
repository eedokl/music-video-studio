"""Beat grid of a song: detected beats, fitted constant tempo, downbeat phase.

uv run --no-project --with librosa --with numpy --with imageio-ffmpeg python beats.py AUDIO out.json [--bpb 4]

AUDIO is ideally the drum stem (clean transients); the full mix works too.
Output: {"detected": [...], "bpm": .., "offset": .., "fixed": [...], "residual_ms": .., "mode": "fixed"|"follow",
         "beatsPerBar": 4, "downbeatPhase": k, "duration": ..}
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import librosa  # noqa: E402
import numpy as np  # noqa: E402
from audio_io import mono  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("audio")
ap.add_argument("out")
ap.add_argument("--bpb", type=int, default=4)
a = ap.parse_args()

x, sr = mono(a.audio)
x = x.astype(np.float32)
dur = len(x) / sr
hop = 256
onset = librosa.onset.onset_strength(y=x, sr=sr, hop_length=hop, aggregate=np.median)
tempo, frames = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop, units="frames", tightness=120)
beats = librosa.frames_to_time(frames, sr=sr, hop_length=hop)
if len(beats) < 8:
    raise SystemExit("too few beats detected")

# robust straight-line fit: beat time = offset + k * period, where k is the NEAREST grid position of each
# detected beat (so a skipped or doubled beat does not shift all following indices), outliers dropped
period = float(np.median(np.diff(beats)))
off = float(beats[0])
keep = np.ones(len(beats), bool)
for _ in range(6):
    idx = np.round((beats - off) / period)
    p = np.polyfit(idx[keep], beats[keep], 1)
    period, off = float(p[0]), float(p[1])
    res = beats - (off + np.round((beats - off) / period) * period)
    keep = np.abs(res) < max(0.03, 2.5 * np.std(res[keep]))
idx = np.round((beats - off) / period)
res = beats - (off + idx * period)
res_ms = float(np.sqrt(np.mean(res[keep] ** 2)) * 1000)
# extend the fitted grid over the whole song
k0 = int(np.floor(-off / period))
fixed = [off + k * period for k in range(k0, int((dur - off) / period) + 2) if 0 <= off + k * period <= dur]
mode = "fixed" if res_ms < 30 else "follow"

# follow grid: one beat per grid position (skips filled, doubles removed), each beat from a local
# straight-line fit over ±8 neighbours → follows slow tempo drift, ignores detection jitter
pos = np.round((beats - off) / period).astype(int)
uniq = {}
for k, b in zip(pos, beats):
    if k not in uniq or abs(b - (off + k * period)) < abs(uniq[k] - (off + k * period)):
        uniq[k] = b
ks = np.array(sorted(uniq))
bs = np.array([uniq[k] for k in ks])
smooth = {}
for k in range(ks[0], ks[-1] + 1):
    m = np.abs(ks - k) <= 8
    if m.sum() < 4:
        continue
    q = np.polyfit(ks[m], bs[m], 1)
    r = bs[m] - np.polyval(q, ks[m])
    good = np.abs(r) < max(0.03, 2 * np.std(r))
    if good.sum() >= 3:
        q = np.polyfit(ks[m][good], bs[m][good], 1)
    smooth[k] = float(np.polyval(q, k))
follow = [smooth[k] for k in sorted(smooth)]
# extend with the local tempo to the song edges
while follow and follow[0] - (follow[1] - follow[0]) >= 0:
    follow.insert(0, follow[0] - (follow[1] - follow[0]))
while follow and follow[-1] + (follow[-1] - follow[-2]) <= dur:
    follow.append(follow[-1] + (follow[-1] - follow[-2]))

# downbeat phase: low-frequency energy is strongest on beat 1 (kick)
S = np.abs(librosa.stft(x, n_fft=2048, hop_length=hop))
freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
low = S[freqs < 150].sum(axis=0)
low = low / (low.max() + 1e-9)
grid = np.array(fixed if mode == "fixed" else follow)
fr = np.clip(librosa.time_to_frames(grid, sr=sr, hop_length=hop), 0, len(low) - 1)
scores = [float(low[fr[ph :: a.bpb]].mean()) for ph in range(a.bpb)]
phase = int(np.argmax(scores))

out = {
    "detected": [round(float(b), 4) for b in follow],
    "raw": [round(float(b), 4) for b in beats],
    "bpm": round(60.0 / period, 3),
    "offset": round(float(off % period), 4),
    "fixed": [round(float(b), 4) for b in fixed],
    "residual_ms": round(res_ms, 1),
    "mode": mode,
    "beatsPerBar": a.bpb,
    "downbeatPhase": phase,
    "duration": round(dur, 3),
}
json.dump(out, open(a.out, "w"))
print(f"{len(beats)} beats, {out['bpm']} BPM, residual {res_ms:.1f} ms → mode {mode}, downbeat phase {phase} (scores {np.round(scores, 3)})")
