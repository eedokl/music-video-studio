"""Automatic "track reading": music/dialogue -> exposure sheet (frames for beats, bars, accents, words).

Replaces classic marking by hand (an Audacity label track): tells on which frame each beat,
syllable/word and strong accent lies - directly usable as keyframe times.

Usage:
  uv run --no-project --with librosa --with faster-whisper --with matplotlib python track_read.py song.mp3
         [--lyrics text.txt] [--fps 24] [--lang de] [--model small] [--no-words] [--vocals vocals.wav]

Output next to the audio file:
  <name>_sheet.json   everything as data (fps, tempo, beats, bars, accents, sections, words, lines)
  <name>_sheet.csv    exposure sheet: one row per frame with an event (frame, time, bar.beat, accent, word)
  <name>_sheet.png    overview: waveform, bars/beats, accents, words, sections
--lyrics: lyrics (lines = verse lines). Whisper recognizes the words with times, the text is aligned to them;
  misrecognized words get the times of their neighbours - the lyrics are authoritative.
Word "source" values: "recognized" (exact match), "aligned" (matched to a different recognized word),
  "estimated" (interpolated between neighbours).
Whisper runs with its voice-activity filter (VAD) first; if that loses too many sung words (fewer than half of the
  lyric words recognized, or a whole lyric line unheard, or without lyrics < 50 % of the vocal time covered) it runs again without VAD and keeps
  the better result. --lang auto lets Whisper detect the language (songs mixing languages).
Singing is recognized worse than speech; with loud music, separate the vocals first (e.g. separate_vocals.py).
"""
import argparse
import csv
import difflib
import json
import sys
import os
import re
import subprocess
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use('song-analysis')
import config  # noqa: E402

config.setup_env()     # model caches + ffmpeg on PATH before any model import
SR = 22050


def load_audio(path, sr=SR):
    raw = subprocess.run([config.need("ffmpeg"), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def norm(w):
    return re.sub(r"[^\wäöüß]", "", w.lower())


def music_analysis(y, sr, fps):
    import librosa
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    beats = librosa.frames_to_time(beat_frames, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    # bar (4/4): beat 1 = the beat phase with the strongest emphasis
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    strength = onset_env[np.clip(beat_frames, 0, len(onset_env) - 1)] if len(beat_frames) else np.array([])
    phase = int(np.argmax([strength[i::4].mean() if len(strength[i::4]) else 0 for i in range(4)])) if len(strength) >= 8 else 0
    beat_list = []
    for i, t in enumerate(beats):
        k = (i - phase) % 4
        beat_list.append({"t": round(float(t), 3), "frame": int(round(t * fps)), "bar": (i - phase) // 4 + 1,
                          "beat": k + 1, "downbeat": k == 0})
    # accents: strong onsets (peaks of the onset strength), by strength
    peaks = librosa.util.peak_pick(onset_env, pre_max=6, post_max=6, pre_avg=12, post_avg=12, delta=0.3, wait=8)
    times = librosa.frames_to_time(peaks, sr=sr)
    vals = onset_env[peaks] / (onset_env.max() + 1e-9)
    accents = [{"t": round(float(t), 3), "frame": int(round(t * fps)), "strength": round(float(v), 2)}
               for t, v in zip(times, vals) if v >= 0.35]
    # sections (verse/chorus...): repetition structure from chroma
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    k = int(max(2, min(8, len(y) / sr / 10)))
    bounds = librosa.segment.agglomerative(chroma, k)
    btimes = list(librosa.frames_to_time(bounds, sr=sr)) + [len(y) / sr]
    sections = [{"start": round(float(a), 2), "end": round(float(b), 2), "frame": int(round(a * fps))}
                for a, b in zip(btimes[:-1], btimes[1:]) if b - a > 1.0]
    return tempo, beat_list, accents, sections, onset_env


def vocal_coverage(rec, y, sr):
    """Share of the vocal-active time (RMS above 10 % of its 95th percentile) covered by recognized words."""
    hop, win = 512, 2048
    if len(y) < win:
        return 0.0
    n = 1 + (len(y) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    rms = np.sqrt((y[idx] ** 2).mean(axis=1))
    active = rms > 0.1 * (np.percentile(rms, 95) + 1e-12)
    if not active.any():
        return 1.0
    covered = np.zeros(n, bool)
    t = (np.arange(n) * hop + win / 2) / sr
    for r in rec:
        covered |= (t >= r["start"]) & (t <= r["end"])
    return float((covered & active).sum() / active.sum())


def words_analysis(y, sr, lang, model_name, lyrics, fps):
    import soxr
    audio16 = soxr.resample(y, sr, 16000).astype(np.float32)
    from whisper_device import whisper_model
    model, _where, _name = whisper_model(model_name)
    print("Whisper", _name, "on", _where)
    language = None if lang == "auto" else lang      # None: Whisper detects the language

    def transcribe(vad):
        segs, _ = model.transcribe(audio16, language=language, word_timestamps=True, vad_filter=vad)
        return [{"word": w.word.strip(), "start": w.start, "end": w.end, "prob": w.probability}
                for s in segs for w in s.words]

    # VAD first; on sung passages the VAD often drops most vocals -> retry without VAD and keep the better result
    rec = transcribe(True)
    if not lyrics:
        cov = vocal_coverage(rec, y, sr)
        used = "with VAD"
        if cov < 0.5:
            rec2 = transcribe(False)
            cov2 = vocal_coverage(rec2, y, sr)
            print(f"Whisper: VAD words cover {100 * cov:.0f} % of the vocal time -> retry without VAD: {100 * cov2:.0f} %")
            if cov2 > cov:
                rec, used = rec2, "without VAD"
        print("Whisper transcription used:", used)
        return [{"word": r["word"], "t": round(r["start"], 3), "end": round(r["end"], 3), "frame": int(round(r["start"] * fps)),
                 "end_frame": int(round(r["end"] * fps)), "line": None, "source": "recognized"} for r in rec], []
    words, line_list = align_lyrics(rec, lyrics, fps)
    n_rec = sum(w["source"] == "recognized" for w in words)
    used = "with VAD"

    def unheard_lines(ws):
        """lines of 3+ words without a single recognized word (the VAD often drops whole sung lines)"""
        by = {}
        for w in ws:
            by.setdefault(w["line"], []).append(w["source"] == "recognized")
        return sum(1 for v in by.values() if len(v) >= 3 and not any(v))

    deaf = unheard_lines(words)
    if words and (n_rec < len(words) / 2 or deaf):
        rec2 = transcribe(False)
        words2, lines2 = align_lyrics(rec2, lyrics, fps)
        n_rec2 = sum(w["source"] == "recognized" for w in words2)
        print(f"Whisper: with VAD {n_rec}/{len(words)} lyric words recognized, {deaf} lines unheard "
              f"-> retry without VAD: {n_rec2}, {unheard_lines(words2)} lines unheard")
        if (n_rec2, -unheard_lines(words2)) > (n_rec, -deaf):
            words, line_list, used, rec = words2, lines2, "without VAD", rec2
    print("Whisper transcription used:", used)
    raw_out = os.environ.get("TRACK_READ_RAW")             # keep the raw Whisper words for later repair tools
    if raw_out:
        Path(raw_out).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return words, line_list


def align_lyrics(rec, lyrics, fps):
    """Align the lyrics to the recognized words -> (words, lines)."""
    lines = [l.strip() for l in lyrics.splitlines() if l.strip()]
    # tokens that are pure punctuation (e.g. a dash between words) are not words
    lw = [(li, w) for li, line in enumerate(lines) for w in line.split() if norm(w)]
    a, b = [norm(w) for _, w in lw], [norm(r["word"]) for r in rec]
    times = [None] * len(lw)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("equal", "replace"):
            for k in range(min(i2 - i1, j2 - j1)):
                times[i1 + k] = (rec[j1 + k]["start"], rec[j1 + k]["end"], "recognized" if tag == "equal" else "aligned")
    known = [i for i, t in enumerate(times) if t]
    for i, t in enumerate(times):                       # distribute gaps between known words
        if t or not known:
            continue
        prev = max([k for k in known if k < i], default=None)
        nxt = min([k for k in known if k > i], default=None)
        t0 = times[prev][1] if prev is not None else (times[nxt][0] - 0.3 * (nxt - i))
        t1 = times[nxt][0] if nxt is not None else (t0 + 0.3 * (i - prev))
        lo, hi = (prev if prev is not None else i - 1), (nxt if nxt is not None else i + 1)
        u = (i - lo) / (hi - lo)
        start = t0 + (t1 - t0) * (u - 0.5 / (hi - lo))
        times[i] = (max(start, 0), max(start, 0) + (t1 - t0) / (hi - lo), "estimated")
    words = [{"word": w, "t": round(t[0], 3), "end": round(t[1], 3), "frame": int(round(t[0] * fps)),
              "end_frame": int(round(t[1] * fps)), "line": li, "source": t[2]} for (li, w), t in zip(lw, times)]
    line_list = []
    for li, line in enumerate(lines):
        ws = [w for w in words if w["line"] == li]
        if ws:
            line_list.append({"line": li, "text": line, "t": ws[0]["t"], "end": ws[-1]["end"],
                              "frame": ws[0]["frame"], "end_frame": ws[-1]["end_frame"]})
    return words, line_list


def chart(path, y, sr, beats, accents, words, sections, fps):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    dur = len(y) / sr
    # limit the width (long songs would be > 20 000 pixels); for long pieces label only each line's first word
    fig, ax = plt.subplots(figsize=(min(max(12, dur * 0.9), 60), 4), dpi=110)
    if dur > 60:
        firsts, seen = [], set()
        for w in words:
            if w["line"] not in seen:
                seen.add(w["line"])
                firsts.append(w)
        words = firsts
    t = np.linspace(0, dur, len(y[::64]))
    ax.fill_between(t, -np.abs(y[::64]), np.abs(y[::64]), color="#9bb7d4", lw=0)
    for s in sections:
        ax.axvspan(s["start"], s["end"], color=["#f3e7c9", "#e3f0d9"][sections.index(s) % 2], alpha=0.5, zorder=0)
    for b in beats:
        ax.axvline(b["t"], color="#2b1d14" if b["downbeat"] else "#a08b78", lw=1.2 if b["downbeat"] else 0.5)
        if b["downbeat"]:
            ax.text(b["t"], 1.02, f"B{b['bar']}", fontsize=7, transform=ax.get_xaxis_transform())
    for a in accents:
        ax.plot(a["t"], -0.9 * np.abs(y).max(), "v", color="#d1495b", ms=4 + 8 * a["strength"])
    for w in words:
        c = {"recognized": "#1b4965", "aligned": "#5d8a3a", "estimated": "#b5651d"}[w["source"]]
        ax.text(w["t"], 0.55 * np.abs(y).max(), w["word"], rotation=60, fontsize=8, color=c)
    ax.set_xlim(0, dur)
    ax.set_yticks([])
    ax.set_xlabel(f"Seconds  (frame = second x {fps})")
    ax.set_title("Exposure sheet: bars (B), beats, accents (red), words (blue recognized / green aligned / brown estimated)")
    fig.tight_layout()
    fig.savefig(path)


def main():
    ap = argparse.ArgumentParser(description="Track reading: beats, bars, accents, sections and word times of a song.")
    ap.add_argument("audio")
    ap.add_argument("--lyrics", help="lyrics text file (one verse line per line)")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--lang", default="de", help="language code for Whisper, or 'auto' to let Whisper detect it")
    ap.add_argument("--model", default="auto", help="auto = large-v3 on the GPU, small on the CPU")
    ap.add_argument("--no-words", action="store_true")
    ap.add_argument("--vocals", help="separated vocal track (e.g. Demucs vocals.wav) for word recognition")
    a = ap.parse_args()
    src = Path(a.audio).resolve()
    y = load_audio(src)
    tempo, beats, accents, sections, _ = music_analysis(y, SR, a.fps)
    lyrics = Path(a.lyrics).read_text(encoding="utf-8") if a.lyrics else None
    yv = load_audio(Path(a.vocals).resolve()) if a.vocals else y     # words from the vocal track
    words, lines = ([], []) if a.no_words else words_analysis(yv, SR, a.lang, a.model, lyrics, a.fps)
    sheet = {"source": src.name, "fps": a.fps, "duration": round(len(y) / SR, 3), "tempo_bpm": round(tempo, 1),
             "beats": beats, "accents": accents, "sections": sections, "words": words, "lines": lines}
    base = src.with_name(src.stem + "_sheet")
    json.dump(sheet, open(base.with_suffix(".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    events = {}
    for b in beats:
        events.setdefault(b["frame"], {})["bar"] = f"{b['bar']}.{b['beat']}"
    for x in accents:
        events.setdefault(x["frame"], {})["accent"] = x["strength"]
    for w in words:
        e = events.setdefault(w["frame"], {})
        e["word"] = (e.get("word", "") + " " + w["word"]).strip()
    for s in sections:
        events.setdefault(s["frame"], {})["section"] = "new"
    with open(base.with_suffix(".csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f, delimiter=";")
        wr.writerow(["frame", "time_s", "bar.beat", "accent", "word", "section"])
        for fr in sorted(events):
            e = events[fr]
            wr.writerow([fr, f"{fr / a.fps:.3f}", e.get("bar", ""), e.get("accent", ""), e.get("word", ""), e.get("section", "")])
    chart(base.with_suffix(".png"), y, SR, beats, accents, words, sections, a.fps)
    print(f"{src.name}: {sheet['duration']} s, tempo {sheet['tempo_bpm']} BPM, {len(beats)} beats "
          f"({sum(b['downbeat'] for b in beats)} bars), {len(accents)} accents, {len(sections)} sections, {len(words)} words")
    if words and lyrics:
        from collections import Counter
        c = Counter(w["source"] for w in words)
        print("Word times:", ", ".join(f"{k} {v} ({100 * v / len(words):.0f} %)" for k, v in c.most_common()))
    print("->", base.with_suffix(".json").name, base.with_suffix(".csv").name, base.with_suffix(".png").name)


if __name__ == "__main__":
    main()
