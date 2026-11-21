# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Riff / drum hits and a constant beat grid of a song.

  uv run hits.py SONG [-o hits.json] [--sheet analysis/song_sheet.json]

hits   sudden loud hits (often right after a short silence) - drive flashes, shakes, lightning, cuts.
       "big" = the strongest third. Different from track_read.py's "accents" (every strong onset): hits are rarer
       and pick the moments a viewer feels as a punch.
grid   one constant tempo + phase (BPM, offset of the first beat) for engines that compute the beat as
       (t - offset) * bpm / 60 (lyric-music-video). Spectral-flux autocorrelation with a mild preference
       for ~120 BPM, then refined on the whole song (refine_tempo: a clearly better constant grid within
       +-0.6 BPM wins - Azure 113.1 -> 113.47, Rock 128.6 -> 129.06, the other test songs unchanged; --coarse
       gives the old result); --sheet also prints track_read's librosa tempo for comparison (half/double tempo
       happens).
kicks  a song with a machine-steady bass drum (electro, synth pop, techno) gets its grid from the drum itself:
       the attacks of the 40-160 Hz band are fitted with one straight line (kick_grid). A 4.5-minute electro
       song: flux grid 119.7 BPM = more than a beat of drift by the end, 409 bass drum attacks -> 119.40 BPM,
       no drift. Taken only when the drum sits on at least half of all beats of the song; "grid" in the output says which one
       was used ("kicks" or "flux"); --no-kicks keeps the flux grid.
Output: {"hits": [s, ...], "big": [s, ...], "bpm": 97.4, "offset": 0.312, "duration": 249.6, "grid": "flux"}
        (+ "kicks": number of bass drum attacks on the grid, "kick_spread": their median distance from it in s)
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


def kick_onsets(x, sr, lo=40.0, hi=160.0, sr2=1500):
    """Attacks of the bass drum -> (times in s, strengths). The 40-160 Hz band as an analytic signal at 1.5 kHz
    (one FFT of the whole song, only the band's bins transformed back): its envelope rises within a few ms on a
    kick; an attack is the steepest point of such a rise."""
    n = len(x)
    X = np.fft.rfft(x)
    m = int(n * sr2 / sr)
    Z = np.zeros(m, dtype=complex)
    k0, k1 = int(lo * n / sr), int(hi * n / sr)
    Z[k0:k1] = 2 * X[k0:k1]
    env = np.abs(np.fft.ifft(Z)) * (m / n)
    w = np.hanning(int(sr2 * 0.012) | 1)
    d = np.maximum(0, np.diff(np.convolve(env, w / w.sum(), mode="same")))
    r = int(sr2 * 0.12)                                  # one attack per 0.12 s at most
    idx = [i for i in range(r, len(d) - r) if d[i] > 0 and d[i] == d[i - r:i + r + 1].max()]
    if not idx:
        return np.array([]), np.array([])
    st = d[idx]
    keep = st > 0.2 * np.percentile(st, 90)              # drop the small ripples between the drum hits
    return (np.array(idx)[keep] + 1) / sr2, st[keep]


def kick_grid(x, sr, bpm0, span=1.5, tol=0.03, verbose=False):
    """One constant grid through the bass drum attacks -> (bpm, offset, attacks on the grid, median distance in s)
    or None. Every tempo within +-span BPM of `bpm0` is tried in steps of 0.01 (score: how well the attacks agree
    on one phase), then the attacks within `tol` s of that grid are fitted with a straight line (beat number ->
    time), twice. Taken only when the drum really carries the song: an attack on at least half of ALL beats of the
    song (at least 64) and a median distance below 12 ms. The band also holds bass notes, so the share of attacks
    on the grid says little (electro song: 44 %, but 61 % of the beats covered; four songs with a played drum kit:
    18-35 % of the beats = what scattered bass notes reach by chance)."""
    t, st = kick_onsets(x, sr)
    if len(t) < 64:
        return None
    best = (-1.0, 0.0, 0.0)
    for bpm in np.arange(bpm0 - span, bpm0 + span + 1e-9, 0.01):
        z = (st * np.exp(2j * np.pi * t * bpm / 60)).sum() / st.sum()
        if abs(z) > best[0]:
            best = (abs(z), 60 / bpm, np.angle(z) / (2 * np.pi) * 60 / bpm)
    _, period, off = best
    for _ in range(2):
        nb = np.round((t - off) / period)
        ok = np.abs(t - off - nb * period) < tol
        if ok.sum() < 64:
            return None
        period, off = np.polyfit(nb[ok], t[ok], 1)
    nb = np.round((t - off) / period)
    dist = np.abs(t - off - nb * period)
    ok = dist < tol
    beats = len(x) / sr / period
    spread = float(np.median(dist[ok]))
    if verbose:
        print(f"   kicks: {len(t)} attacks, {int(ok.sum())} on the grid, "
              f"{len(set(nb[ok]))}/{beats:.0f} beats covered, median distance {1000 * spread:.1f} ms, {60 / period:.3f} BPM")
    if len(set(nb[ok])) < max(64, 0.5 * beats) or spread > 0.012:
        return None
    return round(float(60 / period), 3), round(float(off % period), 3), int(ok.sum()), round(spread, 4)


def tempo(x, sr, refine=True, kicks=True, info=None):
    """-> (bpm, offset of the first beat in s); refine=False: the coarse autocorrelation tempo only (old result);
    kicks=False: never the bass drum grid; `info` (a dict) receives "grid" and the kick numbers"""
    bpm, off = _flux_tempo(x, sr, refine)
    k = kick_grid(x, sr, bpm) if kicks and refine else None
    if info is not None:
        info["grid"] = "kicks" if k else "flux"
        if k:
            info["kicks"], info["kick_spread"] = k[2], k[3]
    return (k[0], k[1]) if k else (bpm, off)


def _flux_tempo(x, sr, refine=True):
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


def analyse(song, refine=True, kicks=True):
    x = decode(song, SR)
    info = {}
    bpm, off = tempo(x, SR, refine, kicks, info)
    h, big = hits(x, SR)
    return {"hits": h, "big": big, "bpm": bpm, "offset": off, "duration": round(len(x) / SR, 2), **info}


def main():
    ap = argparse.ArgumentParser(description="Riff hits and a constant beat grid.")
    ap.add_argument("song")
    ap.add_argument("-o", "--out", help="hits.json (default: next to the song)")
    ap.add_argument("--sheet", help="song_sheet.json of track_read.py, to compare the tempo")
    ap.add_argument("--coarse", action="store_true", help="autocorrelation tempo only (no whole-song refinement)")
    ap.add_argument("--no-kicks", action="store_true", help="keep the flux grid even when the bass drum is steady")
    a = ap.parse_args()
    res = analyse(a.song, not a.coarse, not a.no_kicks)
    out = Path(a.out) if a.out else Path(a.song).with_name("hits.json")
    out.write_text(json.dumps(res), encoding="utf-8")
    print(f"tempo {res['bpm']} BPM, first beat {res['offset']} s, {res['duration']} s"
          + (f" (grid from {res['kicks']} bass drum attacks, median distance {1000 * res['kick_spread']:.0f} ms)"
             if res.get("grid") == "kicks" else ""))
    if a.sheet:
        sh = json.loads(Path(a.sheet).read_text(encoding="utf-8"))
        print(f"track_read (librosa) tempo: {sh.get('tempo_bpm')} BPM")
    print(f"{len(res['hits'])} hits, {len(res['big'])} big -> {out}; big: {res['big'][:16]}")


if __name__ == "__main__":
    main()
