# /// script
# requires-python = ">=3.12"
# dependencies = ["faster-whisper==1.2.1", "numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Narration / voice lines of a clip: length and word times, so tags, gestures and figures can land on a word.

clip.json:
  "narration": [{"id": "fritz", "audio": "voice/fritz.wav", "at": 56, "level": 0},
                {"id": "felix", "audio": "voice/felix.wav",
                 "at": {"max": [{"fig": "felix", "event": "land", "offset": -12}, {"line": "fritz", "edge": "end", "offset": 6}]}}]
Words come from Whisper (song-analysis whisper_device: large-v3 on the GPU under the GPU lock, "small" on the CPU
with WHISPER_CPU=1; WHISPER_MODEL=large-v3 forces the accurate model) and are cached next to the clip in narration/<id>.json; a <audio>.words.json beside the audio
({"words": [{"w": "builder", "s": 1.23, "e": 1.61}], "duration": 4.38}) is used instead when it exists.
Usage (prints the words): uv run narration.py <audio> [--lang de]   (default: detected)
"""
import json
import os
import re
import sys
from pathlib import Path

import _studio
_studio.use("song-analysis")
import config  # noqa: E402
from media import decode, duration  # noqa: E402


def norm(w):
    return re.sub(r"[^\w']", "", w.lower())


def words(audio, cache_dir, lang=None):
    """-> {"duration": s, "words": [{"w", "s", "e"}]} (cached). lang None = Whisper detects the language (a German
    line transcribed as English gives wrong word times - user test)."""
    audio = Path(audio)
    side = audio.with_suffix(".words.json")
    if side.exists():
        return json.loads(side.read_text(encoding="utf-8"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    c = cache_dir / (audio.stem + f".{lang or 'auto'}.json")
    if c.exists() and c.stat().st_mtime >= audio.stat().st_mtime:
        return json.loads(c.read_text(encoding="utf-8"))
    from whisper_device import whisper_model
    model, where, name = whisper_model(os.environ.get("WHISPER_MODEL", "auto"))   # e.g. large-v3 on the CPU
    segs, _ = model.transcribe(decode(audio, 16000).astype("float32"), language=lang, word_timestamps=True)   # own decode: no PyAV
    ws = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for sg in segs for w in sg.words]
    res = {"duration": round(duration(audio), 3), "words": ws, "whisper": f"{name} ({where})"}
    c.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def word_time(res, word, nth=1, end=False):
    """Seconds of the nth occurrence of word (-1 = last); falls back to words that start with it."""
    hits = [x for x in res["words"] if norm(x["w"]) == norm(word)]
    if not hits:            # Whisper joins compounds ("chat bot" -> "chatbot"): the word a written word starts with
        hits = [x for x in res["words"] if norm(x["w"]).startswith(norm(word)) and norm(word)]
    if not hits:
        raise SystemExit(f"word '{word}' not in the line: {' '.join(x['w'] for x in res['words'])}")
    x = hits[nth - 1 if nth > 0 else nth]
    return x["e"] if end else x["s"]


if __name__ == "__main__":
    lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else None
    r = words(sys.argv[1], Path(sys.argv[1]).parent / "narration_cache", lang)
    print(json.dumps(r, indent=1))
