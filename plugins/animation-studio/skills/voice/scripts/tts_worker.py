# Runs in the configured tts_python venv (qwen-tts + CUDA torch), started by voice.py - no uv / PEP 723 header.
"""Qwen3-TTS worker - runs INSIDE the TTS venv (config key `tts_python`), started by voice.py. Not called by hand.

  python tts_worker.py job.json
job.json: {"mode": "design" | "clone", "items": [{"text", "language", "out", "seed",
                                                  "instruct" (design) | "ref_audio", "ref_text" (clone)}]}
design = Qwen3-TTS VoiceDesign: a new voice from an English description (used once per character for the reference).
clone  = Qwen3-TTS Base: every line in the voice of the reference sample -> the character always sounds the same.
Takes the shared GPU lock first (one AI model at a time). Writes 16-bit mono WAVs and job.out.json (durations).
"""
import json
import os
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402

config.setup_env()                     # HF_HOME (model cache) before importing the model code
MODELS = {"design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", "clone": "Qwen/Qwen3-TTS-12Hz-1.7B-Base"}


def save_wav(path, audio, sr):
    import numpy as np
    a = np.clip(np.asarray(audio, dtype=np.float32), -1, 1)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((a * 32767).astype(np.int16).tobytes())
    return len(a) / sr


def main():
    job_file = Path(sys.argv[1])
    job = json.loads(job_file.read_text(encoding="utf-8"))
    mode = job["mode"]
    from gpu_lock import acquire
    acquire(f"tts-{mode}", model="qwen3-tts")
    import torch
    from qwen_tts import Qwen3TTSModel
    cuda = torch.cuda.is_available()
    model = Qwen3TTSModel.from_pretrained(MODELS[mode], device_map="cuda:0" if cuda else "cpu",
                                          dtype=torch.bfloat16 if cuda else torch.float32)
    prompts, out = {}, {}
    for it in job["items"]:
        torch.manual_seed(int(it.get("seed", 0)))
        if cuda:
            torch.cuda.manual_seed_all(int(it.get("seed", 0)))
        if mode == "design":
            wavs, sr = model.generate_voice_design(text=it["text"], language=it["language"], instruct=it["instruct"])
        else:
            key = it["ref_audio"]
            if key not in prompts:
                prompts[key] = model.create_voice_clone_prompt(ref_audio=it["ref_audio"], ref_text=it["ref_text"])
            wavs, sr = model.generate_voice_clone(text=it["text"], language=it["language"], voice_clone_prompt=prompts[key])
        out[it["out"]] = round(save_wav(it["out"], wavs[0], sr), 3)
        print(f"  qwen {mode}: {Path(it['out']).name} ({out[it['out']]:.1f} s)", flush=True)
    job_file.with_suffix(".out.json").write_text(json.dumps(out), encoding="utf-8")
    del model
    if cuda:
        torch.cuda.empty_cache()
    from gpu_lock import release
    release()
    sys.stdout.flush()
    os._exit(0)                        # some CUDA builds hang on interpreter shutdown


if __name__ == "__main__":
    main()
