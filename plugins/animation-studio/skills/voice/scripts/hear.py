# Runs in the configured gpu_python (CUDA venv); without it the caller falls back to `uv run --with ...` (config.gpu_runner) - no PEP 723 header.
"""Whisper check of spoken lines: does the audio say the script? Plus word times for subtitles and gestures.

Runs in the GPU python (config key `gpu_python`, faster-whisper) or via uv on the CPU - started by voice.py:
  python hear.py job.json            job.json: [{"path": "line.wav", "text": "expected text", "language": "de"}]
Writes job.out.json: {path: {"heard": "...", "score": 0..1, "words": [{"word", "t", "end", "source"}]}}
score = similarity of the expected and the heard text (lower case, punctuation removed); >= 0.8 is fine.
Word times: the SCRIPT words aligned to the recognized words (song-analysis track_read.align_lyrics), so a
misheard word still gets a time. Whisper takes the shared GPU lock itself (song-analysis whisper_device).
"""
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use("song-analysis")
import config  # noqa: E402

config.setup_env()


def norm_text(t):
    t = t.lower().replace("ß", "ss")
    return " ".join(re.sub(r"[^\wäöü ]", " ", t).split())


NUMBER = re.compile(r"\d|^(null|eins?|zwei|drei|vier|fuenf|fünf|sechs|sieben|acht|neun|zehn|elf|zwoelf|zwölf|hundert|tausend|"
                    r"prozent|percent|.*zig$|.*ssig$|.*ßig$|zero|one|two|three|four|five|six|seven|eight|nine|ten|hundred)")


def similarity(expected, heard):
    """Text similarity; numbers are compared without their spelling ('neunzig Prozent' == '90 %')."""
    a, b = norm_text(expected), norm_text(heard)
    plain = difflib.SequenceMatcher(None, a, b).ratio()
    strip = lambda t: " ".join(w for w in t.split() if not NUMBER.search(w))
    return max(plain, difflib.SequenceMatcher(None, strip(a), strip(b)).ratio())


def main():
    job_file = Path(sys.argv[1])
    job = json.loads(job_file.read_text(encoding="utf-8"))
    import numpy as np
    from media import decode
    from track_read import align_lyrics
    from whisper_device import whisper_model
    model, where, name = whisper_model("auto")
    print(f"  Whisper {name} on {where}: checking {len(job)} line(s)", flush=True)
    out = {}
    for it in job:
        y = decode(it["path"], 16000)
        y = np.concatenate([np.zeros(4000, np.float32), y, np.zeros(8000, np.float32)])   # a little air around it
        segs, _ = model.transcribe(y, language=it.get("language") or None, beam_size=5, word_timestamps=True,
                                   vad_filter=False, condition_on_previous_text=False)
        rec = [{"word": w.word.strip(), "start": max(0.0, w.start - 0.25), "end": max(0.0, w.end - 0.25)}
               for s in segs for w in s.words]
        heard = " ".join(r["word"] for r in rec).strip()
        score = similarity(it["text"], heard)
        words, _ = align_lyrics(rec, it["text"], 24) if norm_text(it["text"]) else ([], [])
        out[it["path"]] = {"heard": heard, "score": round(score, 3),
                           "words": [{"word": w["word"], "t": w["t"], "end": w["end"], "line": w["line"],
                                      "source": w["source"]} for w in words]}
    job_file.with_suffix(".out.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
