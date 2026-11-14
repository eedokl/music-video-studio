# Runs in the configured gpu_python (CUDA venv); without it the caller falls back to `uv run --with ...` (config.gpu_runner) - no PEP 723 header.
"""Separate vocals from music (Demucs htdemucs) - only needed when there are no stems (Suno delivers them separately).

Output: <out>/htdemucs/<name>/vocals.wav and no_vocals.wav (for Whisper / track_read --vocals and Rhubarb).
Uses the graphics card if available (a whole 4-min song in 27 s), otherwise the CPU (~2 min).
Model cache: TORCH_HOME from config.py (library default otherwise).
Usage:
  <gpu_python from config.py> separate_vocals.py song.wav [-o sep]
  (with uv instead: uv run --no-project --with demucs --with soundfile python separate_vocals.py song.wav)
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402

config.setup_env()     # torch cache + ffmpeg on PATH (demucs reads the audio with ffmpeg)


def main():
    ap = argparse.ArgumentParser(description="Separate vocals from music with Demucs.")
    ap.add_argument("audio")
    ap.add_argument("-o", "--out", default="sep")
    a = ap.parse_args()
    from gpu_lock import acquire
    acquire("separate_vocals", model="demucs")   # only one AI job at a time
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("Demucs htdemucs on", "GPU" if dev == "cuda" else "CPU")
    subprocess.run([sys.executable, "-m", "demucs", "-n", "htdemucs", "--two-stems", "vocals", "-d", dev, "-o", a.out,
                    a.audio], check=True)
    d = Path(a.out) / "htdemucs" / Path(a.audio).stem
    print("->", d / "vocals.wav", "and", d / "no_vocals.wav")


if __name__ == "__main__":
    main()
