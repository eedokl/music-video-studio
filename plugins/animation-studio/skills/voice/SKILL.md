---
name: voice
description: "Building block of the animation-studio plugin: text-to-speech with a fixed voice per character (Tim, Lia, the Computer, a narrator, or new characters described in project.json), Qwen3-TTS voice design + cloning from a reference sample so a character always sounds the same, Piper and Windows speech as fallbacks, ElevenLabs as an optional cloud engine, a Whisper check that the audio really says the script (with automatic retakes), pitch/effect post-processing. Used by talking-character and any skill that needs spoken lines."
user-invocable: false
---

# voice – spoken lines with a fixed voice per character

Scripts: `${CLAUDE_PLUGIN_ROOT}/skills/voice/scripts/` – run with
`uv run --no-project --with numpy python "${CLAUDE_PLUGIN_ROOT}/skills/voice/scripts/voice.py" ...`

| file | what |
|---|---|
| `voice.py` | API + CLI: `speak()`, `cast()`, `design()`, `hear()`, `spoken()`; `say`, `design`, `pick`, `list`, `tempo` |
| `tempo.py` | pitch-neutral tempo change of a spoken line to fit a slot: pauses > 0.40 s → 0.30 s (only when it must get shorter), ffmpeg atempo with a factor clamped to 0.80–1.35 (`fits: false` when the clamp hit), optional tail silence and words-per-minute cap, Whisper word times re-mapped. CLI `voice.py tempo line.wav -o fit.wav --slot 2.4` (or `--factor 1.08`), `voice.py say ... --slot 2.4`; API: item keys `"slot"` / `"tempo"` / `"tail"` in `speak()` → result gets `"tempo": {factor, before, after, fits}` |
| `tts_worker.py` | runs inside the Qwen3-TTS venv (`tts_python`), started by voice.py; takes the GPU lock |
| `hear.py` | Whisper check + word times (GPU python or uv/CPU); Whisper takes the GPU lock itself |
| `assets/cast.json` | the cast: engine, English voice description, sample sentence, reference, fallbacks, fx presets |
| `assets/voices/<who>.wav` | the reference samples (the fixed voices) of the bundled characters |

## Engines (first available wins: the entry's engine, then its `fallback` list)

| engine | quality | needs (config keys, `check_tools.py --set key=value`) |
|---|---|---|
| `qwen` – Qwen3-TTS 1.7B (VoiceDesign + Base) | natural, expressive; the final choice for character voices | `tts_python` = python.exe of a venv with `qwen-tts` and CUDA torch (`uv venv; uv pip install qwen-tts torch --index-url https://download.pytorch.org/whl/cu128`); models download to `hf_home` (~2 x 4 GB) |
| `piper` – Piper ONNX voices (CPU) | clear, a bit flat, deterministic, instant | `piper` = piper executable (`pip install piper-tts`), `piper_voices` = folder with `<model>.onnx` + `.onnx.json` (e.g. de_DE-thorsten-high) |
| `elevenlabs` – ElevenLabs cloud TTS (optional, opt-in) | very natural, many languages; costs credits; the line text leaves the machine | env `ELEVENLABS_API_KEY` only (never in a file, never printed) + per figure `{"engine": "elevenlabs", "voice_id": "...", "model": "eleven_multilingual_v2"}`. Ask the user before using it; designed/library voices only, never a clone of a real person |
| `system` – Windows System.Speech (SSML) | robotic, instant, always there on Windows | nothing |

Force one with `--engine` or the environment variable `TTS_ENGINE=system`.

## Fixed voice per character (Qwen)

1. **Describe, never clone a real person.** The cast describes age, timbre and temperament in English
   (`design`) plus one or two sentences in the film language (`sample_text`).
2. **Reference once:** `voice.py design <who> --n 3 [--project .]` makes candidates `voices/<who>_k.wav` with
   VoiceDesign, writes `voices/candidates.json` (Whisper score, pitch, length) and takes the clearest as
   `voices/<who>.wav`. Let the user listen; `voice.py pick <who> <k> [--to skill]` changes the choice.
   Without a reference, the first `speak()` designs one automatically (2 candidates) into the project.
   The plugin ships the chosen references of tim, lia and computer only (no candidate takes); the narrator and new
   characters get their reference designed on first use (needs Qwen3-TTS; otherwise the fallback engines speak).
3. **Every line is cloned** from that reference with the Base model (seeded: same seed = same take). The project
   folder's `voices/<who>.wav` wins over the skill's; the skill ships tim, lia and computer.

## Post-processing and the Whisper check

Each line: `pitch` (factor, tempo kept), `fx` (`screen`, `radio`, `small` or any ffmpeg filter), silence trimmed,
level normalised (-20 dBFS RMS, peak -1 dB), 44.1 kHz mono. Then Whisper (large-v3 on the GPU, small on the CPU)
transcribes it: `score` = text similarity, `words` = the script words with times (also for misheard words).
Qwen and ElevenLabs lines under 0.8 are taken again (up to 2 retakes, best take wins); piper/system lines are only flagged.
Numbers are compared without their spelling (Whisper writes "neunzig Prozent" as "90 %").
Stage directions in brackets are removed before speaking; `project.json "pronounce": {"Tokanami": "Tokka-nahmi"}`
fixes pronunciations without changing the subtitles.

## Project overrides

```json
"voices": {
  "pip":  {"engine": "system", "voice": "Hedda", "pitch": 1.23},
  "oma":  {"engine": "qwen", "design": "An old woman around eighty with a warm, slightly shaky voice ...",
           "sample_text": "Na, mein Junge, hast du schon gegessen?", "fallback": [{"engine": "system", "voice": "Hedda", "pitch": 0.9}]}
}
```
`voice.py list --project .` shows the engine each character gets and whether its reference exists.
