"""Snap word start times to real vocal onsets, using an isolated vocal track.

uv run --no-project --with numpy --with imageio-ffmpeg python scripts/refine_timing.py VOCALS.wav timing.json refined.json [--before 0.30 --after 0.20]

Whisper's word timestamps on a full band mix can be off by ±0.3–0.5 s. With the vocals separated
(see separate_vocals.py), the voice's onsets are clear: for every word we look for the strongest
rise of vocal energy in [start − before, start + after] and move the word start there when the onset
is clearly above the local noise. Word ends follow the next word / keep their duration. Prints the
median correction and how many words were moved, plus per-line start changes > 0.15 s.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np  # noqa: E402
from audio_io import mono  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("vocals")
ap.add_argument("timing")
ap.add_argument("out")
ap.add_argument("--before", type=float, default=0.30)
ap.add_argument("--after", type=float, default=0.20)
a = ap.parse_args()

x, sr = mono(a.vocals)
hop = int(sr * 0.005)  # 5 ms resolution
n = int(sr * 0.03)
frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
rms = np.sqrt((frames ** 2).mean(axis=1)) + 1e-6
db = 20 * np.log10(rms)
# onset strength: rise of loudness over ~40 ms, only counting rises from quiet-ish levels
rise = np.maximum(0, db[8:] - db[:-8])
rise = np.concatenate([np.zeros(8), rise])
fps = sr / hop

T = json.load(open(a.timing))
moved, corr = 0, []
for li, line in enumerate(T):
    old_t = line["words"][0]
    new_starts = []
    for wi, s in enumerate(line["words"]):
        lo, hi = int((s - a.before) * fps), int((s + a.after) * fps)
        lo = max(lo, 0)
        seg = rise[lo:hi]
        if len(seg) == 0:
            new_starts.append(s)
            continue
        k = int(np.argmax(seg))
        peak = seg[k]
        noise = np.median(rise[max(0, lo - int(fps)):hi + int(fps)]) + 1e-6
        loud_after = db[min(len(db) - 1, lo + k + int(0.05 * fps))]
        if peak > max(6.0, 4 * noise) and loud_after > np.percentile(db, 40):
            t = (lo + k) / fps
            # the onset is where the rise starts, a few ms before the steepest point
            t -= 0.02
            new_starts.append(round(t, 3))
            corr.append(t - s)
            moved += 1
        else:
            new_starts.append(s)
    # keep word order monotonic
    for i in range(1, len(new_starts)):
        if new_starts[i] <= new_starts[i - 1] + 0.05:
            new_starts[i] = max(line["words"][i], new_starts[i - 1] + 0.05)
    ends = line.get("ends", [])
    for i in range(len(new_starts)):
        if i < len(ends):
            dur = ends[i] - line["words"][i]
            ends[i] = round(max(new_starts[i] + 0.08, new_starts[i] + dur), 3)
    line["words"] = new_starts
    line["ends"] = ends
    line["t"] = new_starts[0]
    line["e"] = max(line["e"], ends[-1] if ends else line["e"])
    if abs(new_starts[0] - old_t) > 0.15:
        print(f"line {li:2d}: {old_t:7.2f} -> {new_starts[0]:7.2f} ({new_starts[0] - old_t:+.2f})")

# a line's last word never lasts into the next sung line (Whisper often over-extends it, which delays
# the scene cut that waits for the line to finish)
order = sorted(range(len(T)), key=lambda i: T[i]["t"])
for i, j in zip(order, order[1:]):
    line = T[i]
    lim = T[j]["t"] - 0.05
    if line.get("ends") and line["ends"][-1] > lim:
        line["ends"][-1] = round(max(lim, line["words"][-1] + 0.12), 3)
        line["e"] = max(line["ends"])

json.dump(T, open(a.out, "w"), indent=0)
c = np.array(corr) if corr else np.zeros(1)
total = sum(len(l["words"]) for l in T)
print(f"moved {moved}/{total} words; median correction {np.median(c):+.3f} s, quartiles {np.percentile(c, [25, 75]).round(3)}")
