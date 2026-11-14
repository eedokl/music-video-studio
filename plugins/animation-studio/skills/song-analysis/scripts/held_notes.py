"""Held notes: find long sung words and measure their loudness + pitch contour (30 values per second).

  candidates  uv run --no-project --with numpy python held_notes.py candidates analysis/song_sheet.json [--min 1.0]
              (or a lines timing + its lyrics:  candidates timing.json --lyrics lyrics_clean.txt)
              -> words sung longer than --min seconds, longest first, with a suggested NAME:START:END
  measure     uv run --no-project --with numpy python held_notes.py measure SONG held.json NAME:START:END ...
              [--vocals analysis/vocals_lead.wav]
              e.g. measure song.wav held.json survive1:90.4:92.5 dance:219.8:222.4
              START ~0.2 s before the word, END ~0.3 s after it.
  detect      uv run --no-project --with numpy python held_notes.py detect VOCALS.wav timing.json [--lyrics lyrics_clean.txt]
              [--min 1.0 --ratio 2.5] [--out timing_held.json]
              [--pick N]  -> words held clearly longer than the song's normal word as one sustained note, judged on
              the voice (also mid-line words whose end Whisper cut short), the N that matter picked; --out writes
              the timing with the picked words' ends moved to where the voice stops.
              In Python: held_words(vocals, lines) -> pick_held(cands) -> extend_held(lines, picked).
Output held.json: {"name": {"t0": start, "fps": 30, "env": [0..1 loudness], "pitch": [semitones around the median]}}
With --vocals the isolated vocal track is measured directly (cleaner); without, the voice is isolated roughly
with mid-minus-side from the stereo mix. Pitch has octave errors on full mixes - fold and smooth it before use
(lyric-music-video's vocal.ts does) and use it only for gentle motion.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("song-analysis")
from media import ffmpeg  # noqa: E402

FPS = 30
SR = 48000


def stereo(path, sr=SR):
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def analyse(x, sr, a, b, isolated=False):
    """x: stereo [n, 2]. isolated=True: x is a vocal track (no mid/side subtraction)."""
    mid = (x[:, 0] + x[:, 1]) / 2
    side = (x[:, 0] - x[:, 1]) / 2
    n = 4096
    win = np.hanning(n)
    f = np.fft.rfftfreq(n, 1 / sr)
    band = (f > 200) & (f < 4000)
    env, pitch = [], []
    for i in range(int((b - a) * FPS)):
        c = int((a + i / FPS) * sr)
        lo, hi = c - n // 2, c + n // 2
        if lo < 0 or hi > len(mid):
            env.append(0.0)
            pitch.append(0.0)
            continue
        M = np.abs(np.fft.rfft(mid[lo:hi] * win))
        spec = M if isolated else np.maximum(M - np.abs(np.fft.rfft(side[lo:hi] * win)), 0)
        env.append(float(np.sqrt((spec[band] ** 2).sum())))
        best, bf = 0, 0
        for f0 in np.arange(90, 700, 2.0):
            s = sum(spec[j] / (h + 1) for h, j in enumerate(int(round(f0 * hh * n / sr)) for hh in (1, 2, 3, 4)) if j < len(spec))
            if s > best:
                best, bf = s, f0
        pitch.append(float(bf))
    env = np.array(env) / max(max(env), 1e-9)
    env = np.convolve(env, np.ones(3) / 3, mode="same")
    p = np.maximum(np.array(pitch), 1e-3)
    voiced = env > 0.25
    semis = np.where(voiced, 12 * np.log2(p / np.median(p[voiced])), 0) if voiced.any() else np.zeros_like(p)
    return {"t0": a, "fps": FPS, "env": [round(v, 3) for v in env.tolist()], "pitch": [round(v, 2) for v in semis.tolist()]}


def measure(song, specs, vocals=None):
    """specs: [(name, start, end)] -> held.json dict"""
    x = stereo(vocals or song)
    res = {}
    for name, a, b in specs:
        res[name] = analyse(x, SR, float(a), float(b), isolated=bool(vocals))
        peak = float(a) + int(np.argmax(res[name]["env"])) / FPS
        print(f"{name}: {float(a):.2f}-{float(b):.2f}, peak loudness at {peak:.2f} s")
    return res


def candidates(words, min_len=1.0):
    """words: [{"word","t","end","line"}] -> held candidates, longest first."""
    out = []
    last_of_line = {}
    for i, w in enumerate(words):
        last_of_line[w.get("line")] = i
    for i, w in enumerate(words):
        d = w["end"] - w["t"]
        if d > min_len:
            name = re.sub(r"[^a-z0-9]", "", w["word"].lower()) or "held"
            out.append({"word": w["word"], "line": w.get("line"), "t": w["t"], "end": w["end"], "dur": round(d, 2),
                        "last": last_of_line.get(w.get("line")) == i,
                        "spec": f"{name}:{max(0, w['t'] - 0.2):.2f}:{w['end'] + 0.3:.2f}"})
    return sorted(out, key=lambda c: -c["dur"])


def held_words(vocals, lines, min_len=1.0, ratio=2.5, voiced=0.75, extend=False, verbose=False):
    """Words held clearly longer than the song's normal word (a sung note shown as performed: "Fifteeeen").

    vocals: isolated vocal track (path or refine_timing.Onsets); lines: [{"t","e","words","ends"}] (refined timing).
    A word counts as long when the time it owns (its start up to the next word of the line; a line's last word:
    its end) is >= max(min_len, ratio x the median word-to-word time of the song) and the voice sounds through
    >= `voiced` of it. Whisper often ends a held word after a few hundred ms and leaves a gap before the next word;
    such a word's "end" is where the voice stops (never into the next word). A held NOTE is one sustained sound:
    "onsets" counts new vocal attacks inside the word; "sustained" = at most ~0.9 attacks per second (a word that
    hides several sung syllables or mis-timed neighbours is long but not held).
    Returns [{"line","word","t","end","dur","last","onsets","sustained"}] in song order. extend=True writes the
    ends of all returned words into `lines`; usually pick first (pick_held) and extend only those (extend_held).
    """
    from refine_timing import Onsets
    on = vocals if isinstance(vocals, Onsets) else Onsets(vocals)
    ioi = [b - a for L in lines for a, b in zip(L["words"], L["words"][1:]) if b - a > 0.02]
    typical = float(np.median(ioi)) if ioi else 0.4
    need = max(min_len, ratio * typical)
    fps = on.fps

    def share(a, b):
        lo, hi = max(int(a * fps), 0), min(int(b * fps), len(on.db))
        return float((on.db[lo:hi] > on.mid).mean()) if hi > lo else 0.0

    def attacks(a, b):
        """new vocal attacks (loudness rise > 8 dB, >= 0.12 s apart) inside [a, b]"""
        lo, hi = max(int(a * fps), 0), min(int(b * fps), len(on.rise))
        r, got = on.rise[lo:hi], []
        for k in np.argsort(-r):
            if r[k] < 8:
                break
            if all(abs(int(k) - j) > 0.12 * fps for j in got):
                got.append(int(k))
        return len(got)

    out = []
    for li, L in enumerate(lines):
        ws, es = L["words"], L.get("ends") or []
        for i, s in enumerate(ws):
            if i >= len(es):
                break
            last = i == len(ws) - 1
            e = es[i]
            if last:
                own = e
            else:
                own = ws[i + 1] - 0.05
                if ws[i + 1] - s < 0.15:          # punctuation-only display word or collapsed word
                    continue
            if own - s < need or share(s, own) < voiced:
                continue
            if not last:
                e = max(e, min(own, on.voiced_until(max(s + 0.1, min(e, own) - 0.05), own, max_dip=0.15)))
            if e - s < need:
                continue
            n = attacks(s + 0.15, e - 0.1)
            out.append({"line": li, "word": i, "t": round(s, 3), "end": round(e, 3), "dur": round(e - s, 2),
                        "last": last, "onsets": n, "sustained": n / max(0.1, e - s) <= 0.9})
    if extend:
        extend_held(lines, out)
    if verbose:
        print(f"long words: {len(out)} (>= {need:.2f} s = max({min_len}, {ratio} x typical word {typical:.2f} s), "
              f"voice through >= {int(voiced * 100)} %), sustained notes: {sum(h['sustained'] for h in out)}")
    return out


def pick_held(cands, k=None, n_lines=None):
    """The held notes that matter: sustained candidates, longest first, at most k (default: one per ~16 lyric
    lines, 2..4 - the reference videos stretched 2-4 notes). Returned in song order."""
    if k is None:
        k = min(4, max(2, round((n_lines or 32) / 16)))
    best = sorted((c for c in cands if c["sustained"]), key=lambda c: -c["dur"])[:max(0, int(k))]
    return sorted(best, key=lambda c: c["t"])


def extend_held(lines, held):
    """Write the measured ends of held words into the lines timing (in place)."""
    for h in held:
        L = lines[h["line"]]
        if h["end"] > L["ends"][h["word"]]:
            L["ends"][h["word"]] = h["end"]
            L["e"] = max(L["e"], h["end"])
    return lines


def words_from(path, lyrics=None):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(d, dict):
        return d["words"]
    rows = [r.strip() for r in Path(lyrics).read_text(encoding="utf-8").splitlines() if r.strip()] if lyrics else []
    out = []
    for li, L in enumerate(d):
        texts = rows[li].split(" ") if li < len(rows) else [f"w{k}" for k in range(len(L["words"]))]
        for k, (s, e) in enumerate(zip(L["words"], L["ends"])):
            out.append({"word": texts[k] if k < len(texts) else f"w{k}", "t": s, "end": e, "line": li})
    return out


def main():
    ap = argparse.ArgumentParser(description="Held notes: candidates and loudness/pitch measurement.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("timing", help="song_sheet.json or a lines timing.json")
    c.add_argument("--lyrics", help="lyric lines for a lines timing (one sung line per row)")
    c.add_argument("--min", type=float, default=1.0)
    d = sub.add_parser("detect")
    d.add_argument("vocals")
    d.add_argument("timing", help="lines timing.json (refined)")
    d.add_argument("--lyrics", help="lyric lines, one sung line per row (for the printed words)")
    d.add_argument("--min", type=float, default=1.0)
    d.add_argument("--ratio", type=float, default=2.5)
    d.add_argument("--pick", type=int, help="how many held notes to pick (default: one per ~16 lines, 2..4)")
    d.add_argument("--out", help="write the timing with the picked held words' ends extended")
    m = sub.add_parser("measure")
    m.add_argument("song")
    m.add_argument("out")
    m.add_argument("specs", nargs="+", help="NAME:START:END")
    m.add_argument("--vocals", help="isolated vocal track (better than mid/side of the mix)")
    a = ap.parse_args()
    if a.cmd == "candidates":
        cs = candidates(words_from(a.timing, a.lyrics), a.min)
        print(f"{len(cs)} words sung longer than {a.min} s (pick the 2-4 that matter: long, emotional, phrase end):")
        for x in cs:
            print(f"  line {x['line']!s:>3}  {x['word']!r:22} {x['t']:7.2f}-{x['end']:7.2f} ({x['dur']:.2f} s)"
                  f"{'  last word' if x['last'] else ''}   {x['spec']}")
    elif a.cmd == "detect":
        lines = json.loads(Path(a.timing).read_text(encoding="utf-8"))
        rows = [r.split(" ") for r in Path(a.lyrics).read_text(encoding="utf-8").splitlines() if r.strip()] \
            if a.lyrics else []
        cands = held_words(a.vocals, lines, a.min, a.ratio, verbose=True)
        picked = pick_held(cands, a.pick, len(lines))
        for h in cands:
            w = rows[h["line"]][h["word"]] if h["line"] < len(rows) and h["word"] < len(rows[h["line"]]) else "?"
            print(f"  line {h['line']:>3} word {h['word']:>2} {w!r:18} {h['t']:7.2f}-{h['end']:7.2f} ({h['dur']:.2f} s)"
                  f"  {h['onsets']} attacks{'' if h['sustained'] else ' (not one note)'}"
                  f"{'  last word' if h['last'] else ''}{'   <- picked' if h in picked else ''}")
        if a.out:
            extend_held(lines, picked)
            Path(a.out).write_text(json.dumps(lines, indent=0), encoding="utf-8")
            print("->", a.out)
    else:
        specs = [s.split(":") for s in a.specs]
        Path(a.out).write_text(json.dumps(measure(a.song, specs, a.vocals)), encoding="utf-8")
        print("->", a.out)


if __name__ == "__main__":
    main()
