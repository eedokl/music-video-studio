# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# ///
"""Snap word start times to the real vocal onsets of an isolated vocal track.

Whisper's word times on a full band mix scatter by +-0.3-0.6 s (and even on separated vocals they are loose). With
the vocals isolated (stems or separate_vocals.py) the voice's onsets are clear:
  1. a word whose span starts with (or contains, in its first 70 %) a silence >= 0.2 s starts after that silence -
     Whisper large-v3 lets words begin where the previous word ended, before the pause (up to 1.5 s too early);
  2. otherwise the strongest rise of vocal loudness in [start - before, start + after] becomes the new start when it
     stands clearly above the local noise.
Word ends keep their duration; a line's last word never runs into the next line (Whisper over-extends it, which delays
scene cuts that wait for the line to finish) but lasts as long as the voice holds it (held notes: Whisper ends them early).

Works on two formats (detected automatically):
  lines   [{"t", "e", "words": [start per word], "ends": [end per word]}, ...]   (lyric-music-video timing.json)
  sheet   song_sheet.json of track_read.py ({"words": [{"word", "t", "end", "line", ...}], "lines": [...]})
          -> words get "t"/"end"/"frame"/"end_frame" updated and "refined": true; lines follow their words.

Usage:
  uv run refine_timing.py VOCALS.wav timing.json refined.json [--before 0.30 --after 0.20]
Prints how many words moved, the median correction and lines whose start moved by more than 0.15 s.
In Python:  from refine_timing import refine_lines;  lines = refine_lines(vocals_path, lines)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("song-analysis")
from media import decode  # noqa: E402

SR = 48000
HOP_S = 0.005          # 5 ms resolution


class Onsets:
    """Loudness (dB) and onset strength (rise over ~40 ms) of a vocal track."""

    def __init__(self, vocals, sr=SR):
        x = decode(vocals, sr)
        hop = int(sr * HOP_S)
        n = int(sr * 0.03)
        frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
        rms = np.sqrt((frames ** 2).mean(axis=1)) + 1e-6
        self.db = 20 * np.log10(rms)
        rise = np.maximum(0, self.db[8:] - self.db[:-8])
        self.rise = np.concatenate([np.zeros(8), rise])
        self.fps = sr / hop
        self.loud = np.percentile(self.db, 40)
        self.mid = (np.percentile(self.db, 10) + np.percentile(self.db, 95)) / 2     # voiced / silent threshold

    def gap_onset(self, s, e):
        """Whisper (large-v3) often lets a word start where the previous one ended, before a pause ("another" at
        38.5 s instead of 39.5 s). If the word's span holds a silence >= 0.2 s in its first 70 % followed by voice,
        the word really starts after that silence -> onset time, else None."""
        fps = self.fps
        lo, hi = max(int(s * fps), 0), min(int(min(e, s + 3.0) * fps), len(self.db))
        if hi - lo < int(0.3 * fps):
            return None
        v = self.db[lo:hi] > self.mid
        best, run, need = None, 0, int(0.08 * fps)
        for k in range(len(v)):
            if not v[k]:
                run += 1
                continue
            if run >= 0.2 * fps and k - run < 0.7 * len(v) and v[k:k + need].mean() > 0.7:
                best = k
            run = 0
        if best is None:
            return None
        a = lo + best - int(0.08 * fps)
        j = a + int(np.argmax(self.rise[a:lo + best + int(0.06 * fps)]))
        return max(j / fps - 0.02, s)

    def onset_near(self, s, before=0.30, after=0.20):
        """Clear vocal onset near time s (seconds) or None."""
        fps, rise, db = self.fps, self.rise, self.db
        lo, hi = max(int((s - before) * fps), 0), int((s + after) * fps)
        seg = rise[lo:hi]
        if len(seg) == 0:
            return None
        k = int(np.argmax(seg))
        noise = np.median(rise[max(0, lo - int(fps)):hi + int(fps)]) + 1e-6
        loud_after = db[min(len(db) - 1, lo + k + int(0.05 * fps))]
        if seg[k] > max(6.0, 4 * noise) and loud_after > self.loud:
            return (lo + k) / fps - 0.02          # the onset begins a few ms before the steepest rise
        return None


    def voiced_until(self, t, limit, max_dip=0.1):
        """End of the voiced stretch that contains t (short dips allowed), at most `limit`."""
        fps = self.fps
        i, end, dip = int(t * fps), int(limit * fps), 0
        last = i
        while i < min(end, len(self.db)):
            if self.db[i] > self.mid:
                last, dip = i, 0
            else:
                dip += 1
                if dip > max_dip * fps:
                    break
            i += 1
        return last / fps


def refine_lines(vocals, lines, before=0.30, after=0.20, verbose=True):
    """lines: [{"t","e","words","ends"}] (changed in place and returned)."""
    on = vocals if isinstance(vocals, Onsets) else Onsets(vocals)
    moved, corr = 0, []
    for li, line in enumerate(lines):
        old_t = line["words"][0]
        new, gap = [], set()
        ends0 = line.get("ends", [])
        for i, s in enumerate(line["words"]):
            e = ends0[i] if i < len(ends0) else s + 0.5
            t = on.gap_onset(s, e)
            if t is not None:
                gap.add(i)
            else:
                t = on.onset_near(s, before, after)
            if t is None:
                new.append(s)
            else:
                new.append(round(t, 3))
                corr.append(t - s)
                moved += 1
        for i in range(1, len(new)):                           # keep the word order
            if new[i] <= new[i - 1] + 0.05:
                new[i] = max(line["words"][i], new[i - 1] + 0.05)
        ends = line.get("ends", [])
        for i in range(len(new)):
            if i < len(ends):
                dur = ends[i] - line["words"][i]
                # a word moved over a pause keeps its end; otherwise the word keeps its duration
                ends[i] = round(max(new[i] + 0.08, ends[i] if i in gap else new[i] + dur), 3)
        line["words"], line["ends"], line["t"] = new, ends, new[0]
        line["e"] = max(line["e"], ends[-1] if ends else line["e"])
        if verbose and abs(new[0] - old_t) > 0.15:
            print(f"line {li:2d}: {old_t:7.2f} -> {new[0]:7.2f} ({new[0] - old_t:+.2f})")
    order = sorted(range(len(lines)), key=lambda i: lines[i]["t"])
    for i, j in zip(order, order[1:]):                         # last word ends before the next line starts
        line, lim = lines[i], lines[j]["t"] - 0.05
        if line.get("ends") and line["ends"][-1] > lim:
            line["ends"][-1] = round(max(lim, line["words"][-1] + 0.12), 3)
            line["e"] = max(line["ends"])
    # held notes: a line's last word lasts as long as the voice holds it (Whisper ends held words too early),
    # up to the next line and at most 3 s longer
    longer = 0
    for k, i in enumerate(order):
        line = lines[i]
        if not line.get("ends"):
            continue
        nxt = lines[order[k + 1]]["t"] - 0.05 if k + 1 < len(order) else line["ends"][-1] + 3.0
        e = line["ends"][-1]
        if line["words"][-1] < e < nxt:
            v = on.voiced_until(e - 0.05, min(nxt, e + 3.0))
            if v > e + 0.1:
                line["ends"][-1] = round(v, 3)
                line["e"] = max(line["e"], line["ends"][-1])
                longer += 1
    if verbose:
        print(f"{longer} line endings extended to where the voice stops (held notes)")
        c = np.array(corr) if corr else np.zeros(1)
        total = sum(len(x["words"]) for x in lines)
        print(f"moved {moved}/{total} words; median correction {np.median(c):+.3f} s, "
              f"quartiles {np.percentile(c, [25, 75]).round(3)}")
    return lines


def refine_sheet(vocals, sheet, before=0.30, after=0.20, verbose=True):
    """song_sheet.json dict of track_read.py (changed in place and returned)."""
    fps = sheet.get("fps", 24)
    words = sheet["words"]
    groups = {}
    for i, w in enumerate(words):
        groups.setdefault(w.get("line"), []).append(i)
    keys = [k for k in groups if k is not None]
    lines = [{"t": words[groups[k][0]]["t"], "e": max(words[i]["end"] for i in groups[k]),
              "words": [words[i]["t"] for i in groups[k]], "ends": [words[i]["end"] for i in groups[k]]} for k in keys]
    refine_lines(vocals, lines, before, after, verbose)
    for k, L in zip(keys, lines):
        for i, s, e in zip(groups[k], L["words"], L["ends"]):
            words[i].update(t=round(s, 3), end=round(e, 3), frame=int(round(s * fps)), end_frame=int(round(e * fps)),
                            refined=True)
    for L in sheet.get("lines", []):
        ws = [w for w in words if w.get("line") == L["line"]]
        if ws:
            L.update(t=ws[0]["t"], end=ws[-1]["end"], frame=ws[0]["frame"], end_frame=ws[-1]["end_frame"])
    sheet["refined"] = True
    return sheet


def main():
    ap = argparse.ArgumentParser(description="Snap word starts to vocal onsets.")
    ap.add_argument("vocals")
    ap.add_argument("timing")
    ap.add_argument("out")
    ap.add_argument("--before", type=float, default=0.30)
    ap.add_argument("--after", type=float, default=0.20)
    a = ap.parse_args()
    data = json.loads(Path(a.timing).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "words" in data:
        refine_sheet(a.vocals, data, a.before, a.after)
        Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        refine_lines(a.vocals, data, a.before, a.after)
        Path(a.out).write_text(json.dumps(data, indent=0), encoding="utf-8")
    print("->", a.out)


if __name__ == "__main__":
    main()
