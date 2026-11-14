"""Tighten or loosen the tempo of a spoken line WITHOUT changing its pitch - to fit a slot (a shot, a beat, a gap in
the dialogue) or to follow "too slow / too fast" feedback. Technique of the ai_efficiency voices (ton/tempo.py).

  uv run --no-project --with numpy python tempo.py line.wav -o line_fit.wav --slot 2.4      fit into 2.4 s
  uv run --no-project --with numpy python tempo.py line.wav -o out.wav --factor 1.08          8 % faster
  ... [--max-pause 0.40] [--new-pause 0.30] [--tail 0.0] [--wpm-max 172 --text "the words"] [--min 0.8 --max 1.35]
Neither --slot nor --factor: only the pauses are tightened. (Also as `voice.py tempo ...`, and as "slot"/"tempo"
per item in voice.speak().)

Steps (the original file is never changed unless -o is the same path):
  1. pauses inside the line longer than --max-pause (0.40 s) become --new-pause (0.30 s); the lead-in is trimmed to
     50 ms. Only when the line must get SHORTER - a line that is slowed down keeps its pauses.
  2. pitch-neutral time stretch with ffmpeg atempo (WSOLA; chained for factors outside 0.5-2). factor > 1 = faster.
     With --slot the factor is chosen so the line (+ --tail) fills the slot; it is clamped to --min/--max (default
     0.80-1.35: beyond that speech sounds hurried or drunk) and the result says "fits": false when the clamp hit.
     --wpm-max caps the speed-up at that many words per minute (needs the word count: --text or words).
  3. --tail seconds of silence appended (air before the next line; the ai_efficiency scenes used 0.28 s).
  4. word times (Whisper words of voice.speak) are mapped through the same time map - no new Whisper run needed.
Reference: the ai_efficiency voices settled at 1.00-1.08x per speaker after a first, faster round drew the feedback
"too fast, makes nervous" - keep speed-ups small; tighten pauses first.
Python:
    import tempo
    r = tempo.fit("in.wav", "out.wav", slot=2.4, words=[{"word", "t", "end"}, ...])
    # -> {"factor", "before", "after", "pauses_cut", "fits", "words"}
"""
import argparse
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
from media import ffmpeg  # noqa: E402

EDGE = 0.05


def _native_rate(path):
    r = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True, errors="replace").stderr
    m = re.search(r"Audio:.*?(\d+) Hz", r)
    return int(m.group(1)) if m else 48000


def read(path):
    try:
        with wave.open(str(path)) as w:
            sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
            raw = w.readframes(n)
            width = w.getsampwidth()
    except (wave.Error, EOFError):                     # 32-bit float WAV, mp3, ...: the wave module cannot read it
        sr, width = _native_rate(path), None
    if width != 2:                                     # anything else: let ffmpeg convert
        raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-ac", "1", "-f", "s16le", "-ar", str(sr), "-"],
                             capture_output=True, check=True).stdout
        ch = 1
    y = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    return (y.reshape(-1, ch).mean(1) if ch > 1 else y), sr


def write(path, y, sr):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


def silent(y, sr, db=-38):
    hop = sr // 100
    n = len(y) // hop
    rms = np.sqrt((y[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    return 20 * np.log10(rms / (rms.max() + 1e-9)) < db, hop


def shorten_pauses(y, sr, max_pause=0.40, new_pause=0.30, edge=EDGE):
    """-> (signal, time map [(t_old, t_new), ...], pauses cut). Lead-in trimmed to `edge`, tail to 0.14 s."""
    st, hop = silent(y, sr)
    runs, i = [], 0
    while i < len(st):
        if st[i]:
            j = i
            while j < len(st) and st[j]:
                j += 1
            runs.append((i * hop, j * hop))
            i = j
        else:
            i += 1
    keep, pos, cut = [], 0, 0
    for a, b in runs:
        if a == 0:
            pos = max(0, b - int(edge * sr))
            continue
        if b >= len(y) - hop:
            keep.append((pos, min(len(y), a + int(0.14 * sr))))
            pos = None
            break
        if (b - a) / sr > max_pause:
            h = int(new_pause / 2 * sr)
            keep.append((pos, a + h))
            pos = b - h
            cut += 1
    if pos is not None:
        keep.append((pos, len(y)))
    fade = int(0.008 * sr)
    out, tmap, t_new = [], [], 0.0
    for a, b in keep:
        seg = y[a:b].copy()
        if len(seg) > 2 * fade:
            seg[:fade] *= np.linspace(0, 1, fade)
            seg[-fade:] *= np.linspace(1, 0, fade)
        tmap.append((a / sr, t_new))
        t_new += len(seg) / sr
        tmap.append((b / sr, t_new))
        out.append(seg)
    return (np.concatenate(out) if out else y), tmap, cut


def atempo_chain(f):
    parts = []
    while f > 2.0:
        parts.append(2.0)
        f /= 2.0
    while f < 0.5:
        parts.append(0.5)
        f /= 0.5
    parts.append(f)
    return ",".join(f"atempo={p:.5f}" for p in parts)


def fit(src, dst, slot=None, factor=None, max_pause=0.40, new_pause=0.30, tail=0.0, wpm_max=None, n_words=None,
        words=None, min_factor=0.80, max_factor=1.35):
    y, sr = read(src)
    before = len(y) / sr
    need_shorter = (slot is not None and before + tail > slot) or (factor is not None and factor > 1)
    if need_shorter or (slot is None and factor is None):
        y2, tmap, cut = shorten_pauses(y, sr, max_pause, new_pause)
    else:
        y2, tmap, cut = y, [(0.0, 0.0), (before, before)], 0
    mid = len(y2) / sr
    fits = True
    if factor is None:
        factor = mid / max(slot - tail, 0.05) if slot is not None else 1.0
    if n_words is None and words:
        n_words = len(words)
    if wpm_max and n_words and factor > 1:
        factor = min(factor, max(1.0, mid * wpm_max / (60 * n_words)))
    clamped = min(max(factor, min_factor), max_factor)
    if slot is not None and abs(clamped - factor) > 1e-6:
        fits = False
    factor = clamped
    tmp = Path(dst).with_suffix(".tempo_tmp.wav")
    write(tmp, y2, sr)
    if abs(factor - 1) > 1e-4:
        raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(tmp), "-af", atempo_chain(factor), "-ac", "1",
                              "-ar", str(sr), "-f", "s16le", "-"], capture_output=True, check=True).stdout
        y3 = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    else:
        y3 = y2
    tmp.unlink(missing_ok=True)
    if tail > 0:
        y3 = np.concatenate([y3, np.zeros(int(tail * sr), np.float32)])
    write(dst, y3, sr)
    ta, tn = np.array([m[0] for m in tmap]), np.array([m[1] for m in tmap])
    remap = lambda t: round(float(np.interp(t, ta, tn)) / factor, 3)
    new_words = [{**w, "t": remap(w["t"]), "end": remap(w["end"])} for w in (words or [])]
    after = len(y3) / sr
    if slot is not None and after > slot + 0.02:
        fits = False
    return {"factor": round(factor, 4), "before": round(before, 3), "after": round(after, 3), "pauses_cut": cut,
            "fits": fits, "words": new_words}


def add_args(ap):
    ap.add_argument("wav")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--slot", type=float, help="seconds the line (+ tail) must fill")
    ap.add_argument("--factor", type=float, help="speed factor (>1 faster) instead of --slot")
    ap.add_argument("--max-pause", type=float, default=0.40)
    ap.add_argument("--new-pause", type=float, default=0.30)
    ap.add_argument("--tail", type=float, default=0.0)
    ap.add_argument("--wpm-max", type=float)
    ap.add_argument("--text", help="the spoken text (word count for --wpm-max)")
    ap.add_argument("--min", type=float, default=0.80, dest="min_factor")
    ap.add_argument("--max", type=float, default=1.35, dest="max_factor")


def run_args(a):
    r = fit(a.wav, a.out, a.slot, a.factor, a.max_pause, a.new_pause, a.tail, a.wpm_max,
            len(a.text.split()) if a.text else None, None, a.min_factor, a.max_factor)
    print(json.dumps({k: v for k, v in r.items() if k != "words"}))
    return r


def main():
    ap = argparse.ArgumentParser(description="Pitch-neutral tempo change of a spoken line (fit a slot).")
    add_args(ap)
    run_args(ap.parse_args())


if __name__ == "__main__":
    main()
