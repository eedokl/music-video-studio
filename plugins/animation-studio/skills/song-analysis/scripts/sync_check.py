# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Measure how well word times sit on the voice: word start (as shown) vs. the nearest clear vocal onset.

  uv run sync_check.py VOCALS.wav timing.json [--lead 0.08] [--ref other_timing.json]

timing.json: the lines format ([{"t","e","words","ends"}]) or a song_sheet.json of track_read.py.
--lead   the words are shown this much before their time (lyric-music-video LEAD) - measured is start - lead.
--ref    a second timing of the same lyrics (e.g. a reference project): also prints the word-by-word difference.
Prints the median / mean / 90th percentile of |shown - onset| in ms, the share within 50 / 100 / 200 ms, the
signed median (negative = text comes before the voice), the share of words shown while the voice stays silent for
0.25 s (text clearly ahead - independent of the onset detector) and the 8 worst lines.
Onsets come from the same detector as refine_timing.py, so refined timings score near 0 by construction -
compare an unrefined vs a refined timing, or two timings against each other (--ref), not refined against itself.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("song-analysis")
from refine_timing import Onsets  # noqa: E402


def load_lines(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(d, dict) and "words" in d:
        groups = {}
        for w in d["words"]:
            groups.setdefault(w.get("line"), []).append(w)
        return [{"t": ws[0]["t"], "words": [w["t"] for w in ws], "ends": [w["end"] for w in ws]}
                for k, ws in sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))]
    return d


def stats(d):
    d = np.abs(np.asarray(d, float))
    if not len(d):
        return {}
    return {"n": int(len(d)), "median_ms": round(float(np.median(d)) * 1000), "mean_ms": round(float(d.mean()) * 1000),
            "p90_ms": round(float(np.percentile(d, 90)) * 1000), "within_50ms": round(float((d <= 0.05).mean()), 3),
            "within_100ms": round(float((d <= 0.10).mean()), 3), "within_200ms": round(float((d <= 0.20).mean()), 3)}


def onset_offsets(on, lines, lead=0.0, window=0.4):
    """Per word: shown start - nearest clear onset (seconds), or None when no clear onset is near."""
    res = []
    for li, L in enumerate(lines):
        for wi, s in enumerate(L["words"]):
            t = on.onset_near(s, window, window)
            res.append((li, wi, None if t is None else (s - lead) - t))
    return res


def silent_starts(on, lines, lead=0.0, hold=0.25):
    """Share of words shown while the voice stays silent for the next `hold` seconds (text clearly ahead of the voice)."""
    n = bad = 0
    for L in lines:
        for s in L["words"]:
            a = int((s - lead) * on.fps)
            seg = on.db[max(a, 0):max(a, 0) + int(hold * on.fps)]
            if len(seg):
                n += 1
                bad += bool((seg < on.mid).all())
    return round(bad / max(n, 1), 3)


def compare(lines, ref):
    """Word-by-word start difference lines - ref (only where the word counts of a line agree)."""
    out = []
    for li, (a, b) in enumerate(zip(lines, ref)):
        if len(a["words"]) == len(b["words"]):
            out += [(li, wi, x - y) for wi, (x, y) in enumerate(zip(a["words"], b["words"]))]
    return out


def main():
    ap = argparse.ArgumentParser(description="Word start vs vocal onset (sync check).")
    ap.add_argument("vocals")
    ap.add_argument("timing")
    ap.add_argument("--lead", type=float, default=0.0)
    ap.add_argument("--ref", help="second timing to compare word by word")
    ap.add_argument("--ref-lead", type=float, default=None, help="lead of the reference (default: --lead)")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=1e9)
    ap.add_argument("--json", help="write the numbers to this file")
    a = ap.parse_args()
    on = Onsets(a.vocals)
    keep = lambda L: a.t0 <= L["t"] <= a.t1
    lines = load_lines(a.timing)
    idx = [i for i, L in enumerate(lines) if keep(L)]
    offs = [o for o in onset_offsets(on, lines, a.lead) if o[0] in idx]
    found = [d for _, _, d in offs if d is not None]
    res = {"timing": str(a.timing), "lead": a.lead, "words": len(offs), "with_onset": len(found),
           "shown_in_silence": silent_starts(on, [lines[i] for i in idx], a.lead),
           "signed_median_ms": round(float(np.median(found)) * 1000) if found else None, **stats(found)}
    print(f"{Path(a.timing).name}: {len(found)}/{len(offs)} words near a clear onset; |shown - onset| "
          f"median {res.get('median_ms')} ms, mean {res.get('mean_ms')} ms, p90 {res.get('p90_ms')} ms; "
          f"within 50/100/200 ms: {res.get('within_50ms')}/{res.get('within_100ms')}/{res.get('within_200ms')}; "
          f"signed median {res['signed_median_ms']} ms (negative = text before the voice); "
          f"shown >= 0.25 s before any voice: {100 * res['shown_in_silence']:.1f} % of words")
    per_line = {}
    for li, _, d in offs:
        if d is not None:
            per_line.setdefault(li, []).append(abs(d))
    worst = sorted(per_line.items(), key=lambda kv: -np.median(kv[1]))[:8]
    print("worst lines:", ", ".join(f"{li} ({np.median(v) * 1000:.0f} ms)" for li, v in worst))
    if a.ref:
        ref = load_lines(a.ref)
        rl = a.lead if a.ref_lead is None else a.ref_lead
        ref_found = [d for li, _, d in onset_offsets(on, ref, rl) if d is not None and li in idx]
        res["reference"] = {"timing": str(a.ref), "lead": rl, "with_onset": len(ref_found), **stats(ref_found),
                            "shown_in_silence": silent_starts(on, [ref[i] for i in idx if i < len(ref)], rl),
                            "signed_median_ms": round(float(np.median(ref_found)) * 1000) if ref_found else None}
        # shown start = time - lead, so the shown difference is (x - lead) - (y - ref_lead)
        dd = [d - (a.lead - rl) for li, _, d in compare(lines, ref) if li in idx]
        res["vs_reference"] = {"words": len(dd), **stats(dd),
                               "signed_median_ms": round(float(np.median(dd)) * 1000) if dd else None}
        r = res["reference"]
        print(f"reference {Path(a.ref).name}: |shown - onset| median {r.get('median_ms')} ms, p90 {r.get('p90_ms')} ms, "
              f"within 100 ms {r.get('within_100ms')}, shown >= 0.25 s before any voice {100 * r['shown_in_silence']:.1f} %")
        v = res["vs_reference"]
        print(f"shown word starts vs reference: {v['words']} words, |diff| median {v.get('median_ms')} ms, "
              f"p90 {v.get('p90_ms')} ms, within 100 ms {v.get('within_100ms')}, signed median {v['signed_median_ms']} ms")
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
