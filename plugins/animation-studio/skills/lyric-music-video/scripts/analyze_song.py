# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# ///
"""Analyse the song for the lyric video: word timing per letter, riff hits, beat grid, held-note candidates.

  uv run analyze_song.py PROJECT [--best-words auto|always|never] [--no-refine] [--redo]

Uses the building blocks of the plugin, nothing of its own:
  1-3  song-analysis analyze.py --only 1,2,3: lyrics_clean.txt, vocals_lead.wav (stems or Demucs, GPU lock),
       song_sheet.json (track_read.py: Whisper word times aligned to the lyrics, VAD retry, --lang from project.json)
  4    lyric lines -> analysis/timing_raw.json in the engine format: per line {"t","e","words","ends"} with one
       entry per DISPLAY word (line.split(" ") - punctuation-only words such as a dash get the neighbour's time)
  5    song-analysis refine_timing.py: every word start snapped to the real vocal onset -> analysis/timing.json
  6    song-analysis hits.py: riff hits + constant beat grid -> analysis/hits.json ({"hits","big","bpm","offset"})
  6b   held notes shown as performed: song-analysis held_notes.py finds words held clearly longer than the song's
       normal word as one sustained note (also mid-line words whose end Whisper cut short, e.g. "Fifteeeen"),
       picks the ones that matter (one per ~16 lines, 2..4), moves their ends to where the voice stops and measures
       them -> analysis/held_auto.json (install_data.py merges it with a hand-measured held.json; the engine
       stretches these words by itself). project.json: "held_stretch": false turns it off, "held_max": N picks
       N, "held_style": "vowels" (repeated vowel, default) | "stretch" (one widened vowel) | "auto" (seeded).
  7    prints every line (start, end, recognized/total words) and the held-note candidates
  3c   when whole lines were not heard or < 70 % of the words were recognized (Whisper's VAD drops sung passages):
       song-analysis best_words.py -
       Whisper again on the vocals without VAD and on the full mix, the best pass per line (--best-words always|never)
Finished steps are reused; --redo recomputes everything.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
import held_notes  # noqa: E402
import hits as hits_mod  # noqa: E402
from refine_timing import Onsets, refine_lines  # noqa: E402
from song_project import Project  # noqa: E402

SA = _studio.skill_dir("song-analysis") / "scripts"


def norm(w):
    return re.sub(r"[^\wäöüß]", "", w.lower())          # same token rule as track_read.py


def display_lines(P):
    return [" ".join(r.split()) for r in (P.analysis / "lyrics_clean.txt").read_text(encoding="utf-8").splitlines() if r.strip()]


def sheet_to_lines(sheet, lines):
    """track_read words (lyric tokens with a line index) -> engine timing, one entry per display word."""
    by_line = {}
    for w in sheet["words"]:
        by_line.setdefault(w.get("line"), []).append(w)
    out, quality = [], []
    for li, text in enumerate(lines):
        ws = by_line.get(li, [])
        disp = text.split(" ")
        starts, ends, k = [], [], 0
        for dw in disp:
            if norm(dw) and k < len(ws):
                starts.append(round(ws[k]["t"], 3))
                ends.append(round(ws[k]["end"], 3))
                k += 1
            else:   # punctuation-only display word: shown with the end of the word before (or the next start)
                t = ends[-1] if ends else (ws[k]["t"] if k < len(ws) else (out[-1]["e"] if out else 0.0))
                starts.append(round(t, 3))
                ends.append(round(t, 3))
        if not ws:
            raise SystemExit(f"line {li} '{text}' has no words in the sheet - lyrics_clean.txt and song_sheet.json differ "
                             f"(re-run with --redo)")
        out.append({"t": starts[0], "e": round(max(ends), 3), "words": starts, "ends": ends})
        quality.append((sum(w["source"] == "recognized" for w in ws), sum(w["source"] == "aligned" for w in ws), len(ws)))
    return out, quality


def run_song_analysis(P, redo):
    need = [n for n, f in ((1, "lyrics_clean.txt"), (2, "vocals_lead.wav"), (3, "song_sheet.json"))
            if redo or not (P.analysis / f).exists()]
    if need:
        subprocess.run([sys.executable, str(SA / "analyze.py"), str(P.dir), "--only", ",".join(map(str, need))],
                       check=True)


def estimated_lines(sheet):
    by = {}
    for w in sheet["words"]:
        by.setdefault(w.get("line"), []).append(w["source"])
    return [li for li, src in by.items() if not any(x in ("recognized", "aligned") for x in src)]


VOWELS = "aeiouyäöüàáâèéêìíîòóôùúû"


def held_vowel(word):
    """Index of the letter to stretch: first vowel of the last sung vowel group ("wait" -> a, "between" -> second e,
    "roles" -> o, "survive" -> i, "dance" -> a); a silent final e (also before s/d) does not count."""
    w = word.lower()
    end = len(w) - 1
    while end > 0 and not w[end].isalpha():
        end -= 1
    if end > 2 and w[end] in "sd" and w[end - 1] == "e" and w[end - 2] not in VOWELS and w[end - 3] in VOWELS:
        end -= 2                                    # roles, loved
    elif end > 1 and w[end] == "e" and w[end - 1] not in VOWELS:
        end -= 1                                    # dance, survive
    v = end
    while v > 0 and w[v] not in VOWELS:
        v -= 1
    while v > 0 and w[v - 1] in VOWELS and not (w[v - 1] == "y" and v - 1 == 0):
        v -= 1
    if v + 1 <= end and w[v + 1] == w[v]:        # a doubled vowel stretches its second letter: Fifte|e|n
        v += 1
    return max(0, v)


def auto_held(P, on, timing, lines):
    """Pick the held notes that matter, extend their ends in `timing`, measure them -> analysis/held_auto.json."""
    out = P.analysis / "held_auto.json"
    if P.get("held_stretch", True) is False:
        out.unlink(missing_ok=True)
        print("held notes: off (project.json held_stretch false)")
        return []
    cands = held_notes.held_words(on, timing, verbose=True)
    picked = held_notes.pick_held(cands, P.get("held_max"), len(lines))
    held_notes.extend_held(timing, picked)
    res = {}
    if picked:
        specs, meta = [], {}
        for h in picked:
            word = lines[h["line"]].split(" ")[h["word"]]
            name = (norm(word) or "held") + str(h["line"])
            specs.append((name, round(max(0.0, h["t"] - 0.2), 2), round(h["end"] + 0.3, 2)))
            meta[name] = {"auto": True, "line": h["line"], "word": h["word"], "word_t": h["t"], "word_end": h["end"],
                          "vowel": held_vowel(word), "text": word}
        res = held_notes.measure(P.song, specs, P.analysis / "vocals_lead.wav")
        for k in res:
            res[k].update(meta[k])
    out.write_text(json.dumps(res), encoding="utf-8")
    return picked


def best_words(P, passes):
    """song-analysis best_words.py: several Whisper passes, the best per line (GPU python or uv)."""
    sys.path.insert(0, str(SA))
    from analyze import runner
    subprocess.run(runner(["faster-whisper", "soxr", "numpy"]) + [str(SA / "best_words.py"), str(P.dir),
                                                                   "--passes", passes], check=True)


def main():
    ap = argparse.ArgumentParser(description="Song analysis for a lyric music video.")
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--best-words", choices=["auto", "always", "never"], default="auto",
                    help="auto: when whole lines were not heard or < 70 %% of the words recognized")
    ap.add_argument("--passes", default="mix,vocals,vocals-vad")
    ap.add_argument("--no-refine", action="store_true")
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    P = Project(a.project)
    run_song_analysis(P, a.redo)
    sheet_file = P.analysis / "song_sheet.json"
    sheet = json.loads(sheet_file.read_text(encoding="utf-8"))
    missing = estimated_lines(sheet)
    rec_share = sum(w["source"] == "recognized" for w in sheet["words"]) / max(1, len(sheet["words"]))
    weak = bool(missing) or rec_share < 0.7
    if a.best_words == "always" or (a.best_words == "auto" and weak and "word_passes" not in sheet):
        print(f"{len(missing)} lines without a recognized word, {100 * rec_share:.0f} % of the words recognized "
              f"-> song-analysis best_words.py ({a.passes})")
        best_words(P, a.passes)
        sheet = json.loads(sheet_file.read_text(encoding="utf-8"))
    lines = display_lines(P)
    raw, quality = sheet_to_lines(sheet, lines)
    (P.analysis / "timing_raw.json").write_text(json.dumps(raw, indent=0), encoding="utf-8")
    timing = json.loads(json.dumps(raw))
    on = Onsets(P.analysis / "vocals_lead.wav")
    if not a.no_refine:
        print("refining word starts on the vocal onsets (analysis/vocals_lead.wav):")
        refine_lines(on, timing)
    picked = auto_held(P, on, timing, lines)
    (P.analysis / "timing.json").write_text(json.dumps(timing, indent=0), encoding="utf-8")
    hf = P.analysis / "hits.json"
    if a.redo or not hf.exists():
        hf.write_text(json.dumps(hits_mod.analyse(P.song)), encoding="utf-8")
    h = json.loads(hf.read_text(encoding="utf-8"))
    P.p["tempo"] = {"bpm": h["bpm"], "offset": h["offset"], "librosa_bpm": sheet.get("tempo_bpm")}
    P.p["word_passes"] = sheet.get("word_passes", ["track_read"])
    P.file.write_text(json.dumps(P.p, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{'start':>7} {'end':>7}  rec+al/n  line   ({sheet_file.name})")
    for L, (rec, al, n), text in zip(timing, quality, lines):
        flag = "  <- estimated" if rec + al == 0 else ""
        print(f"{L['t']:7.2f} {L['e']:7.2f}  {rec:>2}+{al}/{n:<2}  {text}{flag}")
    tot = sum(q[2] for q in quality)
    print(f"words recognized {sum(q[0] for q in quality)}/{tot}, aligned {sum(q[1] for q in quality)}, "
          f"lines without any recognized word: {sum(1 for q in quality if q[0] + q[1] == 0)}")
    print(f"tempo {h['bpm']} BPM (first beat {h['offset']} s; librosa {sheet.get('tempo_bpm')}), "
          f"{len(h['hits'])} hits, {len(h['big'])} big")
    words = [{"word": w, "t": s, "end": e, "line": li} for li, (L, text) in enumerate(zip(timing, lines))
             for w, s, e in zip(text.split(" "), L["words"], L["ends"]) if norm(w)]
    cs = held_notes.candidates(words, 1.0)
    print(f"\nheld-note candidates ({len(cs)} words > 1 s; pick 2-4, then song-analysis held_notes.py measure):")
    for c in cs[:12]:
        print(f"  line {c['line']:>3}  {c['word']!r:22} {c['t']:7.2f}-{c['end']:7.2f} ({c['dur']:.2f} s)"
              f"{'  last word' if c['last'] else ''}   {c['spec']}")
    if picked:
        print(f"held notes stretched automatically ({len(picked)}, analysis/held_auto.json):")
        for h in picked:
            print(f"  line {h['line']:>3}  {lines[h['line']].split(' ')[h['word']]!r:22} {h['t']:7.2f}-{h['end']:7.2f} "
                  f"({h['dur']:.2f} s){'  last word' if h['last'] else ''}")
    print("-> analysis/timing.json, timing_raw.json, hits.json, held_auto.json")


if __name__ == "__main__":
    main()
