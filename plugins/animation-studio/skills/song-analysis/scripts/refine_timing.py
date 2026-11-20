# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Snap word start times to the real vocal onsets of an isolated vocal track.

Whisper's word times on a full band mix scatter by +-0.3-0.6 s (and even on separated vocals they are loose). With
the vocals isolated (stems or separate_vocals.py) the voice's onsets are clear:
  1. a word whose span starts with (or contains, in its first 70 %) a silence >= 0.2 s starts after that silence -
     Whisper large-v3 lets words begin where the previous word ended, before the pause (up to 1.5 s too early);
  2. otherwise the strongest rise of vocal loudness in [start - before, start + after] becomes the new start when it
     stands clearly above the local noise.
After that two repairs for what the snapping cannot see (reference song "Die bittere Lektion": ~60 of 300 words):
  3. silence_fix: a word (often a line's first, glued to the end of the line before) that starts while the voice is
     silent moves to the next vocal onset before the next line; a run of such words is spread over the voiced stretch;
  4. repeat_fix: sections with the same text whose audio is the same recording a fixed offset apart (the choruses of
     a generated song: 69.30 s) must have the same word times - where they differ, the candidate with the clearer
     onset in both sections wins.
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
        self.sung = np.percentile(self.db, 95) - 11       # clearly sung (0.28 x the loud level): breaths and reverb
        #                                                   tails between lines stay below it

    def is_sung(self, t, d=0.22):
        """The voice is clearly there during [t, t + d]."""
        a = max(int(t * self.fps), 0)
        seg = self.db[a:a + max(1, int(d * self.fps))]
        return bool(len(seg)) and float((seg > self.sung).mean()) > 0.5

    def next_sung(self, t, limit):
        """Start of the next clearly sung stretch (>= 90 ms) in [t, limit) or None."""
        fps, need = self.fps, max(1, int(0.09 * self.fps))
        f, end = max(int(t * fps), 0), min(int(limit * fps), len(self.db) - need)
        v = self.db > self.sung
        while f < end:
            if v[f] and v[f:f + need].mean() > 0.7:
                return f / fps
            f += 1
        return None

    def rise_at(self, t, w=0.06):
        a, b = max(int((t - w) * self.fps), 0), int((t + w) * self.fps)
        return float(self.rise[a:b].max()) if b > a else 0.0

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
        orig = line["words"]
        for i in range(len(new) - 1):                          # two words that were apart must stay apart: snapping
            if new[i + 1] - new[i] < 0.12 <= orig[i + 1] - orig[i]:   # both onto one onset stacked them 0.05 s apart
                k = i if abs(new[i] - orig[i]) >= abs(new[i + 1] - orig[i + 1]) else i + 1   # (user test) - the one
                new[k] = orig[k]                                                             # moved more goes back
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


def _sung_word(text):
    return any(c.isalnum() for c in text)


def silence_fix(vocals, lines, texts=None, verbose=True):
    """Words that start while the voice is silent -> the next vocal onset (before the next line starts).
    texts: the display lines (word lengths spread a run of words; punctuation-only words are left alone)."""
    on = vocals if isinstance(vocals, Onsets) else Onsets(vocals)
    order = sorted(range(len(lines)), key=lambda i: lines[i]["t"])
    nxt_line = {i: lines[j]["words"][0] for i, j in zip(order, order[1:])}
    moved = []
    for li, line in enumerate(lines):
        W, E = line["words"], line.get("ends") or [w + 0.3 for w in line["words"]]
        tx = texts[li].split(" ") if texts and len(texts[li].split(" ")) == len(W) else [None] * len(W)
        k = 0
        while k < len(W):
            punct = (tx[k] is not None and not _sung_word(tx[k])) or (tx[k] is None and E[k] <= W[k])
            if punct or on.is_sung(W[k]):
                k += 1
                continue
            o = on.next_sung(W[k], nxt_line.get(li, W[k] + 3.0))
            if o is None or o - W[k] < 0.15:
                k += 1
                continue
            j = k                                         # the run of words that would now lie at / before the onset
            while j + 1 < len(W) and W[j + 1] < o + 0.10:
                j += 1
            nxt = W[j + 1] if j + 1 < len(W) else None
            if j == k:
                new = [o]
            else:                                         # spread over the voiced stretch up to the next good word
                end = nxt if nxt is not None else max(E[j], on.voiced_until(o, o + 3.0))
                ln = [max(1, len(tx[q] or "xxxx")) if tx[q] is None or _sung_word(tx[q]) else 0 for q in range(k, j + 1)]
                tot, acc, new = max(1, sum(ln)), 0, []
                for n in ln:
                    new.append(o + (end - o) * acc / tot)
                    acc += n
            for q, v in zip(range(k, j + 1), new):
                moved.append((li, q, W[q], v))
                W[q] = round(v, 3)
            for q in range(k, j + 1):
                lim = W[q + 1] if q + 1 < len(W) else None
                E[q] = round(max(min(E[q], lim) if lim is not None and E[q] > W[q] else max(E[q], W[q] + 0.2), W[q] + 0.12), 3)
            k = j + 1
        line["ends"], line["t"] = E, W[0]
        line["e"] = max(line["e"], E[-1])
    if verbose:
        print(f"silence fix: {len(moved)} word(s) started in silence and moved to the next vocal onset")
        for li, q, a, b in moved[:40]:
            w = texts[li].split(" ")[q] if texts and q < len(texts[li].split(" ")) else f"word {q}"
            print(f"  line {li:2d} {w[:16]!r:18} {a:7.2f} -> {b:7.2f}")
    return moved


def _norm_line(t):
    return "".join(c for c in t.lower() if c.isalnum() or c == " ").split()


def repeated_blocks(texts, min_lines=2):
    """[(i, j, n)]: lines i..i+n-1 have the same words as j..j+n-1 (j = the next occurrence, n >= min_lines)."""
    N = [_norm_line(t) for t in texts]
    out, used, i = [], set(), 0
    while i < len(N):
        best = None
        for j in range(i + 1, len(N)):
            if N[j] == N[i] and N[i] and j not in used:
                n = 0
                while j + n < len(N) and i + n < j and N[i + n] == N[j + n]:
                    n += 1
                if n >= min_lines:
                    best = (i, j, n)
                    break
        if best:
            out.append(best)
            used.update(range(best[1], best[1] + best[2]))
            i += best[2]
        else:
            i += 1
    return out


def repeat_fix(vocals, lines, texts, tol=0.12, min_corr=0.85, verbose=True):
    """Same text + same recording a fixed offset apart (choruses of generated songs) -> the same word times.
    The offset is measured on the loudness curve; below min_corr (a new performance) the block is only reported."""
    on = vocals if isinstance(vocals, Onsets) else Onsets(vocals)
    fixed, report = 0, []
    for i, j, n in repeated_blocks(texts):
        a = [(i + k, q) for k in range(n) for q in range(len(lines[i + k]["words"]))]
        d = [lines[j + k]["words"][q] - lines[i + k]["words"][q] for k in range(n) for q in range(len(lines[i + k]["words"]))
             if q < len(lines[j + k]["words"])]
        if len(d) < 4 or any(len(lines[i + k]["words"]) != len(lines[j + k]["words"]) for k in range(n)):
            continue
        t0, t1 = lines[i]["words"][0] - 0.5, lines[i + n - 1]["e"] + 0.5
        fa, fb = int(t0 * on.fps), int(t1 * on.fps)
        ref = on.db[fa:fb] - on.db[fa:fb].mean()
        best = (-1.0, float(np.median(d)))
        for sh in np.arange(-0.4, 0.4001, 1 / on.fps):                # the exact offset: best match of the loudness
            off = float(np.median(d)) + sh
            g = int(round(off * on.fps))
            seg = on.db[fa + g:fb + g]
            if len(seg) != len(ref):
                continue
            seg = seg - seg.mean()
            c = float((ref * seg).sum() / (np.sqrt((ref ** 2).sum() * (seg ** 2).sum()) + 1e-9))
            if c > best[0]:
                best = (c, off)
        corr, off = best
        diff = [(li, q) for li, q in a if abs(lines[li - i + j]["words"][q] - lines[li]["words"][q] - off) > tol]
        report.append((i, j, n, off, corr, len(diff)))
        if corr < min_corr:
            continue
        for li, q in diff:
            l1, l2 = lines[li], lines[li - i + j]
            c1, c2 = l1["words"][q], l2["words"][q] - off                # two candidates in the first section's time
            sc = [on.rise_at(c) + on.rise_at(c + off) + 6 * (on.is_sung(c + 0.02, 0.12) + on.is_sung(c + off + 0.02, 0.12))
                  for c in (c1, c2)]
            c = c1 if sc[0] >= sc[1] else c2
            l1["words"][q], l2["words"][q] = round(c, 3), round(c + off, 3)
            fixed += 1
        for k in range(n):
            for L in (lines[i + k], lines[j + k]):
                W, E = L["words"], L.get("ends") or []
                for q in range(1, len(W)):
                    if W[q] <= W[q - 1] + 0.05:
                        W[q] = round(W[q - 1] + 0.05, 3)
                for q in range(len(E)):
                    lim = W[q + 1] if q + 1 < len(W) else None
                    E[q] = round(max(W[q] + 0.1, min(E[q], lim) if lim is not None else E[q]), 3)
                L["t"] = W[0]
    if verbose:
        for i, j, n, off, corr, nd in report:
            same = "same recording" if corr >= min_corr else "a new performance - not changed"
            print(f"repeat check: lines {i}-{i + n - 1} = {j}-{j + n - 1}, {off:.2f} s apart (match {corr:.2f}: {same}), "
                  f"{nd} word(s) differed by > {tol} s")
        if report:
            print(f"repeat fix: {fixed} word time(s) made equal in both sections")
    return report


def in_silence(vocals, lines, texts=None, lead=0.0):
    """(n, total): sung words that would appear while the voice is still silent for 0.25 s."""
    on = vocals if isinstance(vocals, Onsets) else Onsets(vocals)
    n = tot = 0
    for li, L in enumerate(lines):
        tx = texts[li].split(" ") if texts and len(texts[li].split(" ")) == len(L["words"]) else None
        for q, s in enumerate(L["words"]):
            if tx and not _sung_word(tx[q]):
                continue
            tot += 1
            a = int(max(0, s - lead) * on.fps)
            n += not bool((on.db[a:a + int(0.25 * on.fps)] > on.sung).any())
    return n, tot


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
