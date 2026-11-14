# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Repair word times after Whisper alignment, using the vocal tracks themselves (step 3b of analyze.py).

Two known failure modes of Whisper on songs (measured on "Prompts!": 16 of 58 words off by > 0.3 s):
  1. Calls in brackets "(Prompts!)" are sung on the BACKING track - Whisper on the lead track never hears them, so the
     alignment only estimates them. With a backing stem, every bracket group gets the next level burst of the backing
     track after the lead word before it (lesson from Prompts!: call times come from backing level bursts).
  2. Order errors: words must be in sung order; a lead word that starts before the previous one moves right behind it.
  3. A word separated from the rest of its line by a long gap (> 1.2 s and > 3x the line's usual word spacing) was
     matched to a wrong sound; it moves next to its line.
Lines get their start/end from their words again. The original sheet is kept as song_sheet_raw.json.
Usage: python fix_timing.py [<project>]   (analyze.py runs it automatically after the exposure sheet)
"""
import json
import shutil
import sys

import numpy as np

import _studio  # noqa: E402
_studio.use("song-analysis")
from media import decode  # noqa: E402
from song_project import Project  # noqa: E402

RATE = 100                     # activity resolution: 10 ms


def activity(path):
    y = decode(path, 16000)
    hop = 16000 // RATE
    k = len(y) // hop
    rms = np.sqrt(np.mean(y[: k * hop].reshape(k, hop) ** 2, axis=1))
    db = 20 * np.log10(rms + 1e-12)
    on = db > np.percentile(db, 90) - 22
    on = np.convolve(on.astype(float), np.ones(5) / 5, mode="same") > 0.5     # 50 ms smoothing
    return on


CALL_WINDOW = 4.0                     # s after the word before a bracket call in which its backing burst may lie


def bursts(on, min_len=0.08):
    """[(start_s, end_s)] of active stretches."""
    out, s = [], None
    for i, v in enumerate(list(on) + [False]):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if (i - s) / RATE >= min_len:
                out.append((s / RATE, i / RATE))
            s = None
    return out


def fix(P):
    f = P.analysis / "song_sheet.json"
    sheet = json.loads(f.read_text(encoding="utf-8"))
    words, lines = sheet["words"], sheet["lines"]
    if not words:
        return 0
    raw = P.analysis / "song_sheet_raw.json"
    if not raw.exists():
        shutil.copy(f, raw)
    lead_on = activity(P.analysis / "vocals_lead.wav")
    lead_b = bursts(lead_on)
    lead_starts = [s for s, e in lead_b]
    back_b = bursts(activity(P.analysis / "vocals_backing.wav")) if (P.analysis / "vocals_backing.wav").exists() else []
    fps = sheet.get("fps", 24)
    moved = 0
    # mark bracket groups
    in_br, group, groups = False, None, []
    for i, w in enumerate(words):
        if w["word"].startswith("("):
            in_br, group = True, [i]
        elif in_br:
            group.append(i)
        if in_br and w["word"].rstrip(".,!?…").endswith(")"):
            groups.append(group)
            in_br = False
    call_idx = {i for g in groups for i in g}
    prev_end = 0.0
    used_back = set()
    i = 0
    while i < len(words):
        w = words[i]
        if i in call_idx and back_b:
            g = next(g for g in groups if i in g)
            before = words[i - 1]["t"] if i > 0 else 0.0
            cand = [(k, b) for k, b in enumerate(back_b) if before + 0.05 <= b[0] <= before + CALL_WINDOW
                    and k not in used_back]       # a call answers its own line - never a burst 40 s later
            if not cand and words[g[0]]["t"] > before + CALL_WINDOW:
                s0 = (words[i - 1]["end"] if i > 0 else 0.0) + 0.05      # stray call: right after its line
                for j, wi in enumerate(g):
                    words[wi]["t"], words[wi]["end"] = round(s0 + 0.25 * j, 3), round(s0 + 0.25 * (j + 1), 3)
                    words[wi]["source"] = "after_line"
                    moved += 1
            if cand:
                k, (s, e) = cand[0]
                used_back.add(k)
                span = min(max(e - s, 0.15 * len(g)), 0.6 * len(g) + 0.6)   # a held backing note is not a long call
                for j, wi in enumerate(g):
                    t0 = s + span * j / len(g)
                    if abs(words[wi]["t"] - t0) > 0.02:
                        moved += 1
                    words[wi]["t"], words[wi]["end"] = round(t0, 3), round(s + span * (j + 1) / len(g), 3)
                    words[wi]["source"] = "backing"
            i = g[-1] + 1                                # no burst left: keep the aligned times
            continue
        if i not in call_idx and w["t"] < prev_end - 0.05:      # order error: right after the previous word
            dur = max(0.12, w["end"] - w["t"])
            w["t"], w["end"] = round(prev_end + 0.02, 3), round(prev_end + 0.02 + dur, 3)
            w["source"] = "reordered"
            moved += 1
        if i not in call_idx:
            prev_end = max(prev_end, w["t"] + 0.05)
        i += 1
    # 3. the first words of a line cut off from the rest by a long gap were matched to a wrong sound: move that block
    #    (keeping its spacing) right in front of the rest of the line. Calls in brackets are not counted.
    for l in lines:
        ws = [w for k, w in enumerate(words) if w.get("line") == l["line"] and k not in call_idx]
        if len(ws) < 2:
            continue
        gaps = [b["t"] - a["t"] for a, b in zip(ws, ws[1:])]
        normal = sorted(g for g in gaps if g < 1.2)
        step = normal[len(normal) // 2] if normal else 0.35
        k = max(range(len(gaps)), key=lambda j: gaps[j])
        if gaps[k] > max(1.2, 3 * step) and k + 1 <= len(ws) - (k + 1):
            # ...unless the block was really heard there (all its words recognized by Whisper, the last one ending
            # > 1 s before the rest) and the voice keeps singing through the gap with no other line's word in it:
            # then the line spans the gap - a held note or a repeat missing from the lyrics. Roles chorus 2 sings
            # "One signal, one signal, fifteeeen roles": moving the heard "One signal!" made the text 2.7 s late.
            # (A recognized word that merely STARTS too early - its end touches the rest - is still moved.)
            g0, g1 = ws[k]["end"], ws[k + 1]["t"]
            seg = lead_on[int(g0 * RATE):int(g1 * RATE)]
            heard = all(w.get("source") == "recognized" for w in ws[: k + 1])
            other = any(g0 < w["t"] < g1 and w.get("line") != l["line"] for w in words)
            if heard and g1 - g0 > 1.0 and len(seg) and seg.mean() > 0.4 and not other:
                continue
            shift = ws[k + 1]["t"] - step - ws[k]["t"]
            for w in ws[: k + 1]:
                w["t"], w["end"] = round(w["t"] + shift, 3), round(min(w["end"] + shift, ws[k + 1]["t"]), 3)
                w["source"] = "regrouped"
                moved += 1
    for w in words:
        w["frame"], w["end_frame"] = round(w["t"] * fps), round(w["end"] * fps)
    for l in lines:
        ws = [w for w in words if w.get("line") == l["line"]]
        if ws:
            l["t"], l["end"] = min(w["t"] for w in ws), max(w["end"] for w in ws)
            l["frame"], l["end_frame"] = round(l["t"] * fps), round(l["end"] * fps)
    f.write_text(json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")
    return moved


if __name__ == "__main__":
    n = fix(Project(sys.argv[1] if len(sys.argv) > 1 else "."))
    print(f"3b word times repaired: {n} words moved")
