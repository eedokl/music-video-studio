# Runs in the configured gpu_python (like track_read.py) - but on the CPU only; no PEP 723 header.
"""Quick song overview on the CPU while the graphics card is busy: no Demucs, no GPU lock, no song_sheet.json.

  analyze.py <project> --quick            (the usual way: lyrics step 1, then this script -> analysis/quick.json)
  python quick_info.py song.wav out.json [--lyrics lyrics_clean.txt] [--vocals lead.wav] [--lang de] [--fps 24]
                       [--model small] [--no-words]

Writes duration, tempo, beats/bars, accents, rough sections, loudness every 2 s (dB), loudness jumps (>= 6 dB from one
2-s block to the next: where a chorus or a break starts) and the sung lines with word times - Whisper `small` on the
CPU (int8) on the mix, or on the lead stem when given. With lyrics the words are aligned to them like track_read.py
does; without lyrics the heard words are grouped into lines at pauses > 0.8 s.
Model of songinfo.py (scenes/spiegel/pipeline), used to plan a video while a long GPU job runs.

PyAV pitfall (faster-whisper 1.2.1 with a newer PyAV): passing a file PATH to WhisperModel.transcribe() fails with
"open() got an unexpected keyword argument 'metadata_errors'" (faster_whisper.audio.decode_audio). Every Whisper call
of this block passes the audio as a 16 kHz float32 numpy array decoded with ffmpeg (track_read.load_audio + soxr),
never a path - keep it that way.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

os.environ["WHISPER_CPU"] = "1"                   # whisper_device: CPU int8, no GPU lock - the GPU stays free
sys.path.insert(0, str(Path(__file__).resolve().parent))
import track_read  # noqa: E402

SR = track_read.SR
STEP = 2.0              # loudness block in seconds
JUMP_DB = 6.0           # loudness jump between two blocks that marks a new part


def loudness(y, sr, step=STEP):
    """[[t, dB], ...] - mean RMS per block of `step` seconds."""
    n = int(step * sr)
    out = []
    for k in range(0, len(y), n):
        seg = y[k:k + n]
        rms = float(np.sqrt(np.mean(seg.astype(np.float64) ** 2))) if len(seg) else 0.0
        out.append([round(k / sr, 1), round(20 * np.log10(rms + 1e-6), 1)])
    return out


def jumps(loud, thresh=JUMP_DB):
    """[{t, from_db, to_db}] where the loudness changes by >= thresh dB between two blocks."""
    return [{"t": b[0], "from_db": a[1], "to_db": b[1]} for a, b in zip(loud, loud[1:]) if abs(b[1] - a[1]) >= thresh]


def heard_lines(words, gap=0.8):
    """Without lyrics: group heard words into lines at pauses > gap seconds."""
    lines, cur = [], []
    for w in words:
        if cur and w["t"] - cur[-1]["end"] > gap:
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    out = []
    for i, ws in enumerate(lines):
        for w in ws:
            w["line"] = i
        out.append({"line": i, "text": " ".join(w["word"] for w in ws), "t": ws[0]["t"], "end": ws[-1]["end"]})
    return out


def main():
    ap = argparse.ArgumentParser(description="Quick CPU-only song overview (no GPU, no Demucs).")
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--lyrics")
    ap.add_argument("--vocals", help="lead stem for the words (default: the mix)")
    ap.add_argument("--lang", default="de")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--model", default="small", help="Whisper model on the CPU (small: ~1 min per 3 min of song)")
    ap.add_argument("--no-words", action="store_true", help="music only (tempo, sections, loudness) - no Whisper")
    a = ap.parse_args()
    src = Path(a.audio).resolve()
    y = track_read.load_audio(src)
    dur = len(y) / SR
    tempo, beats, accents, sections, _ = track_read.music_analysis(y, SR, a.fps)
    loud = loudness(y, SR)
    words, lines = [], []
    if not a.no_words:
        yv = track_read.load_audio(Path(a.vocals).resolve()) if a.vocals else y
        lyrics = Path(a.lyrics).read_text(encoding="utf-8") if a.lyrics else None
        if lyrics is not None and not lyrics.strip():
            lyrics = None
        words, lines = track_read.words_analysis(yv, SR, a.lang, a.model, lyrics, a.fps)   # numpy array, never a path
        if not lyrics:
            lines = heard_lines(words)
    res = {"quick": True, "source": src.name, "fps": a.fps, "duration": round(dur, 2), "tempo_bpm": round(tempo, 1),
           "beats": beats, "accents": accents, "sections": sections, "loudness_2s": loud, "jumps": jumps(loud),
           "words": words, "lines": lines, "whisper": None if a.no_words else f"{a.model} (CPU)"}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"duration {dur:.1f} s, tempo {res['tempo_bpm']} BPM, {len(beats)} beats, {len(sections)} sections")
    for s in sections:
        db = [v for t, v in loud if s["start"] <= t < s["end"]]
        print(f"  section {s['start']:7.2f}-{s['end']:7.2f} s   {np.mean(db) if db else -80:6.1f} dB")
    if res["jumps"]:
        print("loudness jumps:", ", ".join(f"{j['t']:.0f} s ({j['from_db']:.0f}->{j['to_db']:.0f} dB)" for j in res["jumps"]))
    print("loudness:", " ".join(f"{t:.0f}:{v:.0f}" for t, v in loud))
    for l in lines:
        print(f"{l['t']:7.2f}-{l['end']:7.2f}  {l['text']}")
    print("->", a.out)


if __name__ == "__main__":
    main()
