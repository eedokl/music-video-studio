# Runs in the configured gpu_python (CUDA venv); without it the caller falls back to `uv run --with ...` (config.gpu_runner) - no PEP 723 header.
"""Rescue word times when track_read.py lost whole lines: several Whisper passes, the best one per lyric line.

Whisper's voice-activity filter (VAD) often drops sung passages - on "Comfort Zone" track_read's VAD pass heard
51 % of the words, so its retry rule (< 50 %) did not fire and 22 of 58 lines (most of chorus 2, the bridge and the
final chorus) were only estimated. This script transcribes again in several ways, aligns every pass to the lyrics
with track_read.align_lyrics and keeps, PER LINE, the pass that recognized the most words of that line:
  vocals-vad   separated vocals, VAD on        (what track_read does first)
  vocals       separated vocals, VAD off, lyric prompt
  mix          full mix, VAD off, lyric prompt (the old music-video pipeline: robust on dense mixes)
Words of a line that no pass heard stay "estimated" (interpolated between their neighbours again after the merge).
Repeated identical lines (a chorus sung twice at the end) keep their sung order: each copy may take the timing of any
copy of the same text that fits the order (see choose) - before, the repeats collapsed onto one moment.
Then fix_timing.py runs over the result (order errors, cut-off line starts, calls on the backing track).

Writes analysis/song_sheet.json (words + lines replaced, everything else kept; the previous file is saved as
song_sheet_trackread.json) and analysis/best_words.json (which pass won each line).
Passes of a second Whisper model: "<pass>@<model>", e.g. --passes mix,vocals,vocals-vad,mix@large-v3,vocals@large-v3
(small models merge short lines - "Wer wird reich? / Der Typ ..." got one start - a big model often hears them). A pass
of another model wins a line only if it recognizes at least one word more than the main passes (penalty
EXTRA_MODEL_PENALTY), so it fills the gaps without shifting lines the main model already got right.
--fill: keep analysis/song_sheet.json as it is and only fill lines in which NO word was heard (all "estimated", e.g.
squeezed to one moment) from the given passes - typically a bigger model: --fill --passes mix@large-v3,vocals@large-v3.
A pass fills a line only if it recognized at least half of its words and the timing fits between the neighbour lines.
Usage (needs faster-whisper; the GPU python from config.py or uv):
  <gpu_python> best_words.py <project> [--passes mix,vocals,vocals-vad] [--model auto]   (ties go to the first pass)
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("song-analysis")
import config  # noqa: E402

config.setup_env()
import track_read  # noqa: E402
from song_project import Project  # noqa: E402

SCORE = {"recognized": 1.0, "aligned": 0.5}
EXTRA_MODEL_PENALTY = 0.75                      # a pass of a second model ("mix@large-v3") must hear > 0.75 words more


def transcribe(model, audio16, language, vad, prompt):
    segs, _ = model.transcribe(audio16, language=language, word_timestamps=True, vad_filter=vad,
                               initial_prompt=prompt, condition_on_previous_text=False)
    return [{"word": w.word.strip(), "start": w.start, "end": w.end, "prob": w.probability}
            for s in segs for w in (s.words or [])]


def interpolate(words):
    """Re-estimate the words without a source between their known neighbours (same rule as track_read)."""
    known = [i for i, w in enumerate(words) if w["source"] != "estimated"]
    for i, w in enumerate(words):
        if w["source"] != "estimated" or not known:
            continue
        prev = max([k for k in known if k < i], default=None)
        nxt = min([k for k in known if k > i], default=None)
        t0 = words[prev]["end"] if prev is not None else words[nxt]["t"] - 0.3 * (nxt - i)
        t1 = words[nxt]["t"] if nxt is not None else t0 + 0.3 * (i - prev)
        lo, hi = (prev if prev is not None else i - 1), (nxt if nxt is not None else i + 1)
        step = (t1 - t0) / (hi - lo)
        s = max(0.0, t0 + step * (i - lo - 0.5))
        w["t"], w["end"] = round(s, 3), round(s + max(step, 0.12), 3)


def tidy(words, gap=3.0):
    """Inside one line, heard words more than `gap` s apart belong to different occurrences (difflib can pick the
    first word of a line in one chorus and the rest in its repeat). Keep the cluster with the most heard words, mark
    the others "estimated" (they are interpolated again after the merge)."""
    for li in sorted({w["line"] for w in words}):
        ws = [w for w in words if w["line"] == li and w["source"] in SCORE]
        if len(ws) < 2:
            continue
        groups, cur = [], [ws[0]]
        for a, b in zip(ws, ws[1:]):
            if b["t"] - a["end"] > gap:
                groups.append(cur)
                cur = []
            cur.append(b)
        groups.append(cur)
        if len(groups) > 1:
            keep = max(groups, key=lambda g: sum(SCORE[w["source"]] for w in g))
            for g in groups:
                if g is not keep:
                    for w in g:
                        w["source"] = "estimated"
    return words


def line_key(words):
    return " ".join(track_read.norm(w["word"]) for w in words)


def choose(results, passes):
    """Pick a pass per line, maximising the recognized words while the lines stay in sung order.

    A chorus line may be aligned to its first occurrence in one pass and to its repeat in another, so a free
    per-line choice can pull a line a minute away. Dynamic programming over the lines: a line taken from pass p must
    start after the previous TIMED line (and not before its end - 1 s); lines that fit nowhere become "estimated".
    Repeated identical lines (a final chorus sung twice): difflib aligns all copies of a line to ONE occurrence and
    squeezes the others onto a single moment. So every timed copy of the same text in any pass is also a candidate
    for each of its repeats ("from_line"); the sung-order rule then gives each repeat its own, later occurrence.
    -> [{"line", "pass", "from_line", "score"}]
    """
    for p in passes:
        tidy(results[p])
    lines = sorted({w["line"] for w in results[passes[0]]})
    text = {li: line_key([w for w in results[passes[0]] if w["line"] == li]) for li in lines}
    same = {li: [lj for lj in lines if text[lj] == text[li]] for li in lines}
    opt = {}                                    # (li, p, source line) -> (score, first heard t, last heard end)
    for li in lines:
        for p in passes:
            for lj in same[li]:
                ws = [w for w in results[p] if w["line"] == lj]
                sc = sum(SCORE.get(w["source"], 0) for w in ws)
                if ws and sc > 0:
                    heard = [w for w in ws if w["source"] in SCORE]
                    # own alignment first; a copy of another line's timing counts a hair less (ties -> own)
                    opt[(li, p, lj)] = (sc - 0.001 * passes.index(p) - (0.0005 if lj != li else 0)
                                        - (EXTRA_MODEL_PENALTY if "@" in p else 0), heard[0]["t"],
                                        heard[-1]["end"])
    best = {}                                   # key -> (total score, previous key)
    keys = sorted(opt, key=lambda k: (k[0], passes.index(k[1]), k[2]))
    for k in keys:
        sc, t, _ = opt[k]
        best[k] = (sc, None)
        for j in keys:
            if j[0] >= k[0]:
                break
            if j in best and t > opt[j][1] + 0.1 and t >= opt[j][2] - 1.0 and best[j][0] + sc > best[k][0]:
                best[k] = (best[j][0] + sc, j)
    k = max(best, key=lambda x: best[x][0]) if best else None
    picked = {}
    while k:
        picked[k[0]] = k
        k = best[k][1]
    return [{"line": li, "pass": picked[li][1] if li in picked else None,
             "from_line": picked[li][2] if li in picked else None,
             "score": round(opt[picked[li]][0], 2) if li in picked else 0} for li in lines]


def merge(results, passes, choice):
    """Words of the chosen pass per line (copied from the repeat it was matched to); lines without a pass are
    estimated between their neighbours."""
    merged = []
    for c in choice:
        if c["pass"]:
            src = c.get("from_line", c["line"])
            own = [w for w in results[passes[0]] if w["line"] == c["line"]]
            got = [w for w in results[c["pass"]] if w["line"] == src]
            merged += [dict(g, word=o["word"], line=c["line"]) for o, g in zip(own, got)]
        else:                                   # no pass heard this line in the right place: estimate it
            merged += [dict(w, source="estimated") for w in results[passes[0]] if w["line"] == c["line"]]
    interpolate(merged)
    return merged


def fill(P, results, passes, fps):
    """--fill: lines of the existing sheet without any heard word take the timing of the pass that heard most of them
    (>= half of the words, start after the previous line's last heard word, end before the next line's first one)."""
    f = P.analysis / "song_sheet.json"
    sheet = json.loads(f.read_text(encoding="utf-8"))
    words = sheet["words"]
    by_line = {}
    for i, w in enumerate(words):
        by_line.setdefault(w["line"], []).append(i)
    filled = []
    order = sorted(by_line)
    for n, li in enumerate(order):
        idx = by_line[li]
        if any(words[i]["source"] != "estimated" for i in idx):
            continue
        prev_end = max((words[i]["end"] for lj in order[:n] for i in by_line[lj] if words[i]["source"] != "estimated"),
                       default=-1e9)
        nxt = next((lj for lj in order[n + 1:] if any(words[i]["source"] != "estimated" for i in by_line[lj])), None)
        next_end = max((words[i]["end"] for i in by_line[nxt]), default=1e9) if nxt is not None else 1e9
        best = None
        for p in passes:
            got = [w for w in results[p] if w["line"] == li]
            heard = [w for w in got if w["source"] in SCORE]
            if len(got) != len(idx) or len(heard) * 2 < len(idx):
                continue
            if heard[0]["t"] < prev_end - 0.1 or heard[-1]["end"] > next_end - 0.3:
                continue
            sc = sum(SCORE[w["source"]] for w in heard)
            if best is None or sc > best[0]:
                best = (sc, p, got)
        if best:
            for i, g in zip(idx, best[2]):
                words[i] = dict(g, word=words[i]["word"], line=li)
            filled.append((li, best[1]))
            end = max(w["end"] for w in best[2])
            if nxt is not None:                         # words of the next line placed inside the filled line: the
                other = [w for w in results[best[1]] if w["line"] == nxt]   # same pass's timing (or estimated)
                for j, i in enumerate(by_line[nxt]):
                    if words[i]["t"] >= end - 0.05:
                        break
                    o = other[j] if j < len(other) and len(other) == len(by_line[nxt]) else None
                    words[i] = dict(o, word=words[i]["word"], line=nxt) if o and o["source"] in SCORE and o["t"] >= end - 0.05 \
                        else dict(words[i], source="estimated")
    if filled:
        touched = {li for li, _ in filled} | {order[order.index(li) + 1] for li, _ in filled if order.index(li) + 1 < len(order)}
        before = [dict(w) for w in words]
        interpolate(words)                              # re-estimate only inside the filled lines and their next line
        words[:] = [w if w["line"] in touched else b for w, b in zip(words, before)]
        for w in words:
            w["frame"], w["end_frame"] = int(round(w["t"] * fps)), int(round(w["end"] * fps))
        for l in sheet["lines"]:
            ws = [words[i] for i in by_line.get(l["line"], [])] if l["line"] in touched else []
            if ws:
                l.update(t=ws[0]["t"], end=ws[-1]["end"], frame=ws[0]["frame"], end_frame=ws[-1]["end_frame"])
        sheet["filled_lines"] = [{"line": li, "pass": p} for li, p in filled]
        shutil.copy(f, P.analysis / "song_sheet_before_fill.json")
        f.write_text(json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"fill: {len(filled)} unheard line(s) filled: " +
          (", ".join(f"{sheet['lines'][[l['line'] for l in sheet['lines']].index(li)]['text']!r} <- {p}" for li, p in filled)
           or "none"))


def main():
    ap = argparse.ArgumentParser(description="Best-of-several Whisper passes per lyric line.")
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--passes", default="mix,vocals,vocals-vad")
    ap.add_argument("--model", default="auto")
    ap.add_argument("--reuse", action="store_true", help="reuse the cached Whisper passes (cache/rec_<pass>.json)")
    ap.add_argument("--fill", action="store_true", help="only fill lines nobody heard in the existing song_sheet.json")
    a = ap.parse_args()
    P = Project(a.project)
    lyrics = (P.analysis / "lyrics_clean.txt").read_text(encoding="utf-8")
    if not lyrics.strip():
        raise SystemExit("no lyrics - best_words needs lyrics_clean.txt (analyze.py step 1)")
    fps = P.fps
    lang = P.get("language", "de")
    language = None if lang == "auto" else lang
    prompt = " ".join(l.strip() for l in lyrics.splitlines() if l.strip())[:400]
    models, audio, results = {}, {}, {}
    for p in a.passes.split(","):
        kind, _, mname = p.partition("@")
        cached = P.cache / (f"rec_{kind}.json" if not mname else f"rec_{kind}_{mname}.json")
        if a.reuse and cached.exists():
            rec = json.loads(cached.read_text(encoding="utf-8"))
        else:
            mkey = mname or a.model
            if mkey not in models:
                from whisper_device import whisper_model
                m_, where, name = whisper_model(mkey)
                models[mkey] = m_
                print("Whisper", name, "on", where)
            model = models[mkey]
            import soxr
            src = P.song if kind == "mix" else P.analysis / "vocals_lead.wav"
            if str(src) not in audio:
                audio[str(src)] = soxr.resample(track_read.load_audio(src), track_read.SR, 16000).astype("float32")
            rec = transcribe(model, audio[str(src)], language, vad=(kind == "vocals-vad"),
                             prompt=None if kind == "vocals-vad" else prompt)
            cached.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        words, _ = track_read.align_lyrics(rec, lyrics, fps)
        (P.cache / f"words_{p.replace('@', '_')}.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
        results[p] = words
        n = sum(w["source"] == "recognized" for w in words)
        print(f"pass {p:11}: {len(rec)} words heard, {n}/{len(words)} lyric words recognized")
    passes = list(results)
    if a.fill:
        return fill(P, results, passes, fps)
    choice = choose(results, passes)
    merged = merge(results, passes, choice)
    order = [ws[0]["t"] for li in sorted({w["line"] for w in merged}) for ws in [[w for w in merged if w["line"] == li]]]
    back = sum(b <= a for a, b in zip(order, order[1:]))
    if back:
        print(f"warning: {back} line(s) do not start after the previous one")
    for w in merged:
        w["frame"], w["end_frame"] = int(round(w["t"] * fps)), int(round(w["end"] * fps))
    f = P.analysis / "song_sheet.json"
    sheet = json.loads(f.read_text(encoding="utf-8"))
    keep = P.analysis / "song_sheet_trackread.json"
    if not keep.exists():
        shutil.copy(f, keep)
    sheet["words"] = merged
    lines = []
    for li, text in enumerate([l.strip() for l in lyrics.splitlines() if l.strip()]):
        ws = [w for w in merged if w["line"] == li]
        if ws:
            lines.append({"line": li, "text": text, "t": ws[0]["t"], "end": ws[-1]["end"], "frame": ws[0]["frame"],
                          "end_frame": ws[-1]["end_frame"]})
    sheet["lines"] = lines
    sheet["word_passes"] = passes
    f.write_text(json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")
    (P.analysis / "best_words.json").write_text(json.dumps(choice, indent=1), encoding="utf-8")
    raw = P.analysis / "song_sheet_raw.json"          # fix_timing keeps the first version it sees as raw
    shutil.copy(f, raw)
    import fix_timing
    moved = fix_timing.fix(P)
    won = {p: sum(c["pass"] == p for c in choice) for p in passes}
    copied = sum(1 for c in choice if c["pass"] and c["from_line"] != c["line"])
    if copied:
        print(f"{copied} repeated line(s) took the timing of another copy of the same text (sung order kept)")
    rec = sum(w["source"] == "recognized" for w in merged)
    print(f"merged: {rec}/{len(merged)} words recognized; lines won per pass {won}; fix_timing moved {moved} words")


if __name__ == "__main__":
    main()
