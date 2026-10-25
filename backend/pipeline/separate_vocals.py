"""Split a song into vocals / accompaniment with Demucs (htdemucs) – for precise lyric timing.

uv run --no-project --python 3.11 --with demucs --with torch==2.5.1 --with torchaudio==2.5.1 --with soundfile --with imageio-ffmpeg python scripts/separate_vocals.py SONG OUTDIR
→ OUTDIR/vocals.wav (16-bit, 48 kHz). Takes a few minutes on CPU for a 4-minute song.

Use the vocal track for transcribe.py (much more precise word times than on the full mix,
fewer skipped lines) and for refine_timing.py (snaps word starts to real vocal onsets).
The full mix stays the soundtrack of the video.
"""
import glob
import os
import subprocess
import sys

song, outdir = sys.argv[1:3]
os.makedirs(outdir, exist_ok=True)
import demucs.separate  # noqa: E402

demucs.separate.main(["--two-stems=vocals", "-n", "htdemucs", "-o", outdir, "--float32", song])
raw = glob.glob(os.path.join(outdir, "htdemucs", "*", "vocals.wav"))[0]
import imageio_ffmpeg  # noqa: E402

dst = os.path.join(outdir, "vocals.wav")
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", raw, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", dst], check=True)
print(dst)
