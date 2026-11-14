"""Riff / drum hits and a constant beat grid of a song.

  uv run --no-project --with numpy python hits.py SONG [-o hits.json] [--sheet analysis/song_sheet.json]

hits   sudden loud hits (often right after a short silence) - drive flashes, shakes, lightning, cuts.
       "big" = the strongest third. Different from track_read.py's "accents" (every strong onset): hits are rarer
       and pick the moments a viewer feels as a punch.
grid   one constant tempo + phase (BPM, offset of the first beat) for engines that compute the beat as
       (t - offset) * bpm / 60 (lyric-music-video). Spectral-flux autocorrelation with a mild preference
       for ~120 BPM, then refined on the whole song (refine_tempo: a clearly better constant grid within
       +-0.6 BPM wins - Azure 113.1 -> 113.47, Rock 128.6 -> 129.06, the other test songs unchanged; --coarse
       gives the old result); --sheet also prints track_read's librosa tempo for comparison (half/double tempo
       happens).
Output: {"hits": [s, ...], "big": [s, ...], "bpm": 97.4, "offset": 0.312, "duration": 249.6}
In Python:  from hits import analyse;  res = analyse("song.wav")
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


def spectrum(x, sr, hop=512, n=2048):
    win = np.hanning(n)
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * win
    return np.abs(np.fft.rfft(fr, axis=1)), sr / hop, np.fft.rfftfreq(n, 1 / sr)


def _flux(x, sr):
    mag, fps, _ = spectrum(x, sr)
    mag = np.log1p(mag * 10)
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(axis=1)
    return np.maximum(flux - np.convolve(flux, np.ones(16) / 16, mode="same"), 0), fps


def _comb(f, fps, bpm, n_phase=120):
    """best phase of a constant grid at `bpm` over the whole song -> (mean flux on the grid, phase)"""
    t = np.arange(len(f)) / fps
    period = 60 / bpm
    ph = np.linspace(0, period, n_phase, endpoint=False)
    grid = np.arange(0, t[-1] - period, period)
    sc = np.array([np.interp(grid + p, t, f).mean() for p in ph])
    k = int(np.argmax(sc))
    return float(sc[k]), float(ph[k])


def _phase_steadiness(f, fps, bpm, win=10.0):
    """1 = the best beat phase is the same in every 10 s window (right tempo), ~0 = it drifts (wrong tempo)"""
    t = np.arange(len(f)) / fps
    period = 60 / bpm
    grid = np.arange(0, t[-1], period)
    ph = np.linspace(0, period, 100, endpoint=False)
    angs = []
    for a in np.arange(0, t[-1] - win, win):
        g = grid[(grid >= a) & (grid < a + win)]
        if len(g):
            sc = [np.interp(g + p, t, f).mean() for p in ph]
            angs.append(ph[int(np.argmax(sc))] / period * 2 * np.pi)
    return float(abs(np.mean(np.exp(1j * np.array(angs))))) if angs else 0.0


def refine_tempo(f, fps, bpm0, span=0.6, step=0.01, gain=1.25):
    """The autocorrelation tempo is only as fine as one flux frame at a 4-beat lag (~0.6 BPM at 48 kHz / hop 512;
    the same song gave 113.1 BPM decoded at 48 kHz and 113.5 at 44.1 kHz), and a constant grid that is 0.4 BPM off
    drifts by most of a beat over a 3-minute song. A constant grid is tried at every 0.01 BPM within +-span over the
    WHOLE song. The coarse tempo is kept unless another peak fits clearly better: >= `gain` x the mean flux on the
    grid of the coarse tempo's own peak AND a beat phase at least as steady over 10 s windows (protects songs whose
    tempo wobbles, where two peaks score alike). Returns (bpm, offset) or None (keep the coarse result)."""
    fs = np.convolve(f, np.hanning(5) / np.hanning(5).sum(), mode="same")
    bpms = np.round(np.arange(bpm0 - span, bpm0 + span + 1e-9, step), 2)
    res = [_comb(fs, fps, b) for b in bpms]
    sc = np.array([r[0] for r in res])
    i0 = int(np.argmin(np.abs(bpms - bpm0)))
    near = slice(max(0, i0 - 8), i0 + 9)                 # the coarse tempo's own peak (+-0.08 BPM)
    ip = near.start + int(np.argmax(sc[near]))
    ig = int(np.argmax(sc))
    if abs(ig - ip) <= 8 or sc[ig] < gain * sc[ip]:
        return None
    if _phase_steadiness(fs, fps, bpms[ig]) < _phase_steadiness(fs, fps, bpm0):
        return None
    return float(bpms[ig]), res[ig][1]


def tempo(x, sr, refine=True):
    """-> (bpm, offset of the first beat in s); refine=False: the coarse autocorrelation tempo only (old result)"""
    flux, fps = _flux(x, sr)
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    best, best_bpm = -1, 0
    for bpm in np.arange(70, 181, 0.1):
        lag = fps * 60 / bpm
        s = sum(np.interp(lag * k, np.arange(len(ac)), ac) for k in (1, 2, 4))
        s *= np.exp(-((np.log2(bpm / 120)) ** 2) * 0.5)
        if s > best:
            best, best_bpm = s, bpm
    if refine:
        r = refine_tempo(flux, fps, round(float(best_bpm), 2))
        if r:
            return round(r[0], 2), round(r[1], 3)
    period = 60 / best_bpm
    t = np.arange(len(flux)) / fps
    phases = np.linspace(0, period, 200, endpoint=False)
    scores = [np.interp(np.arange(p, t[-1], period), t, flux).sum() for p in phases]
    return round(float(best_bpm), 2), round(float(phases[int(np.argmax(scores))]), 3)


def hits(x, sr):
    """-> (all hits, big hits) in seconds"""
    mag, fps, f = spectrum(x, sr)
    low = mag[:, (f > 40) & (f < 400)].sum(axis=1)
    e = np.log1p(low * 0.5 + mag.sum(axis=1) * 0.1)
    out, last = [], -10.0
    for i in range(int(fps * 0.4), len(e) - 3):
        jump = e[i:i + 3].mean() - e[i - int(fps * 0.25):i].mean()
        t = i / fps
        if jump > 0.9 and t - last > 0.35:
            out.append((round(t, 3), round(float(jump), 2)))
            last = t
    vals = sorted(j for _, j in out)
    thr = vals[int(len(vals) * 0.65)] if vals else 0
    return [t for t, _ in out], [t for t, j in out if j >= thr]


def analyse(song, refine=True):
    x = decode(song, SR)
    bpm, off = tempo(x, SR, refine)
    h, big = hits(x, SR)
    return {"hits": h, "big": big, "bpm": bpm, "offset": off, "duration": round(len(x) / SR, 2)}


def main():
    ap = argparse.ArgumentParser(description="Riff hits and a constant beat grid.")
    ap.add_argument("song")
    ap.add_argument("-o", "--out", help="hits.json (default: next to the song)")
    ap.add_argument("--sheet", help="song_sheet.json of track_read.py, to compare the tempo")
    ap.add_argument("--coarse", action="store_true", help="autocorrelation tempo only (no whole-song refinement)")
    a = ap.parse_args()
    res = analyse(a.song, not a.coarse)
    out = Path(a.out) if a.out else Path(a.song).with_name("hits.json")
    out.write_text(json.dumps(res), encoding="utf-8")
    print(f"tempo {res['bpm']} BPM, first beat {res['offset']} s, {res['duration']} s")
    if a.sheet:
        sh = json.loads(Path(a.sheet).read_text(encoding="utf-8"))
        print(f"track_read (librosa) tempo: {sh.get('tempo_bpm')} BPM")
    print(f"{len(res['hits'])} hits, {len(res['big'])} big -> {out}; big: {res['big'][:16]}")


if __name__ == "__main__":
    main()
