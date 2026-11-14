# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Second audio language: the same film with a second song version (e.g. the English one) as audio track 2.

  python second_audio.py --project . --song song_en.wav --language en [--title English] [--offset 10.5] [--video film.mp4]

The other version stays UNCHANGED and is only shifted as a whole by one global offset (lesson from "Prompts!": cutting
it into sections to fit the picture sounded chopped; the listener preferred the original song, even where it does
not match the mouths exactly). The offset comes from cross-correlating the onset envelopes of both versions:
  - with the full source song of the project (project.json "source": {"path": ...}) both full songs are compared
    (choruses repeat - an excerpt alone can lock onto the wrong chorus)
  - otherwise the project's song.wav excerpt is searched in the other version (warns about repeats)
The same sound effects (analysis/sounds.wav) are mixed in. Picture, mouths and lyrics stay in the first language.
Onset envelopes are computed in numpy (spectral flux of a log-mel spectrogram) - no librosa needed:
  uv run second_audio.py ...
Output: <video stem>_<lang>.mp4 next to the video: track 1 = original (default), track 2 = the other language,
both tagged with ISO 639-2 language codes; decode-checked.
"""
import argparse
import subprocess
from pathlib import Path

import numpy as np

import _studio  # noqa: E402
_studio.use("song-analysis")
from encode import place  # noqa: E402
from media import check_video, decode, duration, ffmpeg  # noqa: E402
from song_project import Project  # noqa: E402

ISO = {"de": "deu", "en": "eng", "fr": "fra", "es": "spa", "it": "ita", "nl": "nld", "pl": "pol", "pt": "por",
       "ja": "jpn", "zh": "zho", "ko": "kor", "tr": "tur", "sv": "swe", "da": "dan", "no": "nor", "fi": "fin"}
NAMES = {"de": "Deutsch", "en": "English", "fr": "Français", "es": "Español", "it": "Italiano"}
SR, HOP = 22050, 256


def mel_bank(n_fft=2048, n_mels=128, sr=SR):
    """Triangular mel filters (Slaney-style spacing, no normalisation) - numpy only."""
    hz2mel = lambda f: 2595 * np.log10(1 + f / 700)
    mel2hz = lambda m: 700 * (10 ** (m / 2595) - 1)
    pts = mel2hz(np.linspace(hz2mel(0), hz2mel(sr / 2), n_mels + 2))
    freqs = np.linspace(0, sr / 2, n_fft // 2 + 1)
    fb = np.zeros((n_mels, len(freqs)), np.float32)
    for i in range(n_mels):
        lo, c, hi = pts[i], pts[i + 1], pts[i + 2]
        fb[i] = np.maximum(0, np.minimum((freqs - lo) / (c - lo + 1e-9), (hi - freqs) / (hi - c + 1e-9)))
    return fb


def onsets(path, n_fft=2048):
    """Onset envelope (spectral flux of the log-mel spectrogram, like librosa.onset.onset_strength) in numpy:
    mel power in dB (80 dB range), frame-to-frame increase, rectified, averaged over the bands; z-normalised."""
    y = decode(path, SR).astype(np.float32)
    y = np.pad(y, n_fft // 2, mode="reflect")
    n = 1 + (len(y) - n_fft) // HOP
    win = np.hanning(n_fft + 1)[:-1].astype(np.float32)
    fb = mel_bank(n_fft)
    mel = np.empty((n, fb.shape[0]), np.float32)
    for a in range(0, n, 2048):                       # STFT in blocks (all at once would need ~2 GB for a song)
        idx = np.arange(a, min(n, a + 2048))[:, None] * HOP + np.arange(n_fft)[None, :]
        mel[a:a + len(idx)] = np.abs(np.fft.rfft(y[idx] * win, axis=1)) ** 2 @ fb.T
    mel = 10 * np.log10(np.maximum(mel, 1e-10))
    mel = np.maximum(mel, mel.max() - 80.0)
    out = np.concatenate([[0.0], np.maximum(0.0, np.diff(mel, axis=0)).mean(axis=1)]).astype(np.float32)
    return (out - out.mean()) / (out.std() + 1e-9)


def best_lag(ref, other, lo, hi):
    """lag (frames) so that other[t + lag] ~ ref[t]; FFT cross-correlation, normalised by overlap."""
    n = 1 << int(np.ceil(np.log2(len(ref) + len(other))))
    c = np.fft.irfft(np.fft.rfft(other, n) * np.conj(np.fft.rfft(ref, n)), n)
    lags = np.arange(n)
    lags[lags > n // 2] -= n
    best, arg = -1e9, 0
    for lag, v in zip(lags, c):
        if lo <= lag <= hi:
            ov = min(len(ref), len(other) - lag) - max(0, -lag)
            if ov > 0:
                s = v / ov
                if s > best:
                    best, arg = s, lag
    return arg, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--song", required=True, help="the other language version of the song")
    ap.add_argument("--language", required=True, help="ISO 639-1 code of the other version, e.g. en")
    ap.add_argument("--title")
    ap.add_argument("--offset", type=float, help="force: other-version seconds = project seconds + offset")
    ap.add_argument("--video", default="film.mp4")
    a = ap.parse_args()
    P = Project(a.project)
    video = P.dir / a.video
    if not video.exists():
        raise SystemExit(f"{video.name} missing - build the film first")
    fps_o = SR / HOP
    if a.offset is not None:
        off = a.offset
        how = "given"
    else:
        src = P.get("source", {}) or {}
        full = Path(src["path"]) if src.get("path") and Path(src["path"]).exists() else None
        other = onsets(a.song)
        if full is not None:                      # compare the full songs, then shift by the excerpt start
            lag, score = best_lag(onsets(full), other, int(-30 * fps_o), int(30 * fps_o))
            off = lag / fps_o + float(src.get("from", 0.0))
            how = f"full songs, score {score:.2f}"
        else:
            ex = onsets(P.song)
            lag, score = best_lag(ex, other, 0, len(other) - len(ex))
            off = lag / fps_o
            how = f"excerpt only (score {score:.2f}) - choruses repeat; pass --offset or source.path if it looks wrong"
    t_start = min(s["from"] for s in P.sections()) if P.sections() else 0.0
    dur = duration(video)
    start = off + t_start                          # where the film's first frame lies in the other version
    pre = max(0.0, -start)
    trim = f"atrim=start={max(start, 0):.4f},asetpts=PTS-STARTPTS"
    pad = f",adelay={int(pre * 1000)}|{int(pre * 1000)}" if pre > 0 else ""
    other_wav = P.cache / f"audio_{a.language}.wav"
    graph = f"[0:a]{trim}{pad},apad,atrim=end={dur:.3f},aresample=48000,aformat=channel_layouts=stereo[o]"
    inputs = ["-i", a.song]
    sounds = P.analysis / "sounds.wav"
    if sounds.exists():                            # the same sound effects as the original track
        inputs += ["-i", str(sounds)]
        graph += (f";[1:a]atrim=start={t_start:.4f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[s];"
                  "[o][s]amix=inputs=2:duration=first:normalize=0[o2]")
        out_label = "[o2]"
    else:
        out_label = "[o]"
    subprocess.run([ffmpeg(), "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", out_label,
                    "-c:a", "pcm_s16le", str(other_wav)], check=True)
    lang1 = P.get("language", "de")
    lang1 = lang1 if lang1 in ISO else "de"
    tmp = P.cache / f"multilang_{a.language}_tmp.mp4"
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(video), "-i", str(other_wav), "-map", "0:v", "-map", "0:a",
                    "-map", "1:a", "-c:v", "copy", "-c:a:0", "copy", "-c:a:1", "aac", "-b:a:1", "192k", "-shortest",
                    "-metadata:s:a:0", f"language={ISO[lang1]}", "-metadata:s:a:0", f"title={NAMES.get(lang1, lang1)}",
                    "-metadata:s:a:1", f"language={ISO.get(a.language, a.language)}",
                    "-metadata:s:a:1", f"title={a.title or NAMES.get(a.language, a.language)}",
                    "-disposition:a:0", "default", "-disposition:a:1", "0", str(tmp)], check=True)
    out = place(tmp, video.with_name(f"{video.stem}_{a.language}.mp4"))
    err = check_video(out)
    print(f"offset {off:+.3f} s ({how}); -> {out.name}: track 1 {lang1}, track 2 {a.language}; "
          f"{'0 decode errors' if not err else err[:200]}")


if __name__ == "__main__":
    main()
