"""Align the known lyric lines to Whisper's word timestamps → timing.json.

uv run python scripts/align.py words.json lyrics.txt timing.json

lyrics.txt: one sung line per row. Lines starting with "[" or "(" (section headers, stage directions
like "(Robotic voice)") are skipped. Write the lyrics AS PERFORMED: if the singer repeats a phrase,
repeat the line – check the transcription for repeats before aligning.

Output per line: {"t": start, "e": end, "words": [start per display word], "ends": [end per display word]}
Printed "matched/total" per line shows how well it matched (0/n = estimated from neighbours).
"""
import sys as _sys
if hasattr(_sys.stdout, 'reconfigure'):
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # Windows consoles

import difflib
import json
import re
import sys


def lyric_lines(path):
    return [l.strip() for l in open(path, encoding="utf-8") if l.strip() and not re.match(r"^\s*[\[(]", l)]


def norm(x):
    return re.sub(r"[^\w]", "", x.lower())


if __name__ == "__main__":
    words_json, lyrics_txt, out = sys.argv[1:4]
    segs = json.load(open(words_json, encoding="utf-8"))
    ww = [w for s in segs for w in s["words"]]
    wt = [norm(w["w"]) for w in ww]
    lines = lyric_lines(lyrics_txt)
    lt, owner = [], []
    for i, l in enumerate(lines):
        for tok in l.replace("-", " ").replace("–", " ").replace("—", " ").split():
            if norm(tok):
                lt.append(norm(tok))
                owner.append(i)

    sm = difflib.SequenceMatcher(a=lt, b=wt, autojunk=False)
    blocks = sm.get_matching_blocks()
    times = [None] * len(lt)
    ends = [None] * len(lt)
    for a, b, n in blocks:
        for k in range(n):
            times[a + k] = ww[b + k]["s"]
            ends[a + k] = ww[b + k]["e"]

    known = [i for i, t in enumerate(times) if t is not None]
    for i in range(len(times)):
        if times[i] is None:
            prev = max([k for k in known if k < i], default=None)
            nxt = min([k for k in known if k > i], default=None)
            if prev is not None and nxt is not None:
                f = (i - prev) / (nxt - prev)
                times[i] = times[prev] + f * (times[nxt] - times[prev])
            elif prev is not None:
                times[i] = times[prev] + 0.35 * (i - prev)
            else:
                times[i] = times[nxt] - 0.35 * (nxt - i)
            ends[i] = times[i] + 0.3

    res = []
    for li, text in enumerate(lines):
        idx = [k for k, o in enumerate(owner) if o == li]
        disp = text.split(" ")
        starts, wends, k = [], [], 0
        for dw in disp:
            parts = [p for p in re.split(r"[-–—\s]+", dw) if norm(p)]
            if not parts:  # punctuation-only display word (e.g. a dash): reuse the neighbour's time
                j = idx[min(k, len(idx) - 1)]
                starts.append(round(ends[j] if k >= len(idx) else times[j], 2))
                wends.append(starts[-1])
                continue
            starts.append(round(times[idx[k]], 2))
            wends.append(round(ends[idx[min(k + len(parts) - 1, len(idx) - 1)]], 2))
            k += len(parts)
        matched = sum(1 for k in idx if any(a <= k < a + n for a, b, n in blocks))
        res.append({"t": starts[0], "e": round(max(ends[k] for k in idx), 2), "words": starts, "ends": wends, "matched": matched, "total": len(idx)})
        print(f"{starts[0]:7.2f} {res[-1]['e']:7.2f} {matched}/{len(idx)}  {text}")
    json.dump(res, open(out, "w"), indent=0)
