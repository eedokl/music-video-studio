# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# ///
"""HuMo (ByteDance, Apache 2.0) through the local ComfyUI: reference image + text + vocals -> singing clip.
Rescue engine for lines where LTX-2.3 fails (plosive-heavy lines: lip-sync comparison 2026-11-12, test B r 0.55 vs
LTX -0.03; most even sync over the three tests 0.78 / 0.55 / 0.64). Weak points (user decision): the face looks
static, framing and light drift away from the start image, identity is less stable (1 of 6 samples lost the streak)
-> never the default; render it NEXT to an LTX seed and let the measurement (mouth.py) and the eye pick.
832x480 at 25 fps, length 4n+1 frames, ~130 s GPU per second of video (1.7B, 30 steps, cfg 5); upscale in the cut.
Sizes:
  1.7B  diffusion_models/humo_1.7B_fp16 (default) - 30 steps, cfg 5 (no step-distill LoRA exists for 1.7B)
  17B   diffusion_models/humo_17B_fp8_e4m3fn + loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16, 6 steps,
        cfg 1 - does NOT fit 16 GB VRAM (81 min per step on the reference machine): refused unless --allow-17b
Shared files: text_encoders/umt5_xxl_fp8_e4m3fn_scaled, vae/wan_2.1_vae, audio_encoders/whisper_large_v3_fp16.
ComfyUI node: WanHuMoImageToVideo (core ComfyUI >= 0.3.6x).
Usage:
  uv run humo.py start.png vocals.wav "prompt" -o clip.mp4 [--frames 97] [--seed 31]
         [--size 1.7B|17B] [--steps N] [--song-start 12.3] [--dry-run]
  --dry-run: print the workflow summary (no ComfyUI, no GPU).
From Python: humo.render(img, wav, prompt, out, frames, seed, meta=...) -> out.mp4 + out.json (clips.write_meta).
"""
import argparse
import json
import math
import shutil
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import clips  # noqa: E402

FPS = 25
W, H = 832, 480
LEAD_IN = 0.25
SIZES = {   # size: (unet, lora or None, steps, cfg)
    "1.7B": ("humo_1.7B_fp16.safetensors", None, 30, 5.0),
    "17B": ("humo_17B_fp8_e4m3fn.safetensors", "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", 6, 1.0),
}
NEG = ("overexposed, static, blurry details, subtitles, still image, grey, worst quality, low quality, JPEG artifacts, "
       "ugly, deformed, extra fingers, bad hands, bad face, frozen, closed mouth, cartoon")


def frames_for(seconds, lead_in=LEAD_IN):
    """4n+1 frames at 25 fps covering lead-in + shot + 0.28 s."""
    n = int(math.ceil((seconds + lead_in + 0.28) * FPS))
    return (n - 1 + 3) // 4 * 4 + 1


def workflow(img, wav, prompt, frames, seed, prefix, size="1.7B", steps=None, neg=NEG):
    unet, lora, st, cfg = SIZES[size]
    model = ["2", 0] if lora else ["1", 0]
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "3": {"class_type": "ModelSamplingSD3", "inputs": {"model": model, "shift": 8.0}},
        "4": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan",
                                                     "device": "default"}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "6": {"class_type": "AudioEncoderLoader", "inputs": {"audio_encoder_name": "whisper_large_v3_fp16.safetensors"}},
        "10": {"class_type": "LoadImage", "inputs": {"image": img}},
        "11": {"class_type": "ImageScale", "inputs": {"image": ["10", 0], "upscale_method": "lanczos", "width": W,
                                                     "height": H, "crop": "center"}},
        "12": {"class_type": "LoadAudio", "inputs": {"audio": wav}},
        "13": {"class_type": "AudioEncoderEncode", "inputs": {"audio_encoder": ["6", 0], "audio": ["12", 0]}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 0], "text": prompt}},
        "21": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 0], "text": neg}},
        "30": {"class_type": "WanHuMoImageToVideo", "inputs": {"positive": ["20", 0], "negative": ["21", 0], "vae": ["5", 0],
               "width": W, "height": H, "length": frames, "batch_size": 1, "audio_encoder_output": ["13", 0],
               "ref_image": ["11", 0]}},
        "40": {"class_type": "KSampler", "inputs": {"model": ["3", 0], "seed": seed, "steps": steps or st, "cfg": cfg,
               "sampler_name": "uni_pc", "scheduler": "simple", "positive": ["30", 0], "negative": ["30", 1],
               "latent_image": ["30", 2], "denoise": 1.0}},
        "50": {"class_type": "VAEDecode", "inputs": {"samples": ["40", 0], "vae": ["5", 0]}},
        "60": {"class_type": "SaveImage", "inputs": {"images": ["50", 0], "filename_prefix": prefix}},
    }
    if lora:
        wf["2"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0}}
    return wf


def render(image, audio, prompt, out, frames=97, seed=31, size="1.7B", steps=None, neg=NEG, meta=None, allow_17b=False):
    """Start image + vocals -> out.mp4 (25 fps, no sound) + out.json."""
    import comfy
    if size == "17B" and not allow_17b:
        raise SystemExit("HuMo 17B does not fit 16 GB VRAM (81 min per step measured) - use 1.7B or pass allow_17b")
    comfy.ensure()
    comfy.lock("humo", f"comfy:humo{size}")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tag = f"{out.parent.name}_{out.stem}"
    t0 = time.time()
    wf = workflow(comfy.upload(image, f"humo_{tag}{Path(image).suffix}"), comfy.upload(audio, f"humo_{tag}{Path(audio).suffix}"),
                  prompt, frames, seed, f"animation-studio/humo/{tag}", size, steps, neg)
    hist = comfy.run(wf, timeout=6 * 3600)
    fdir = out.with_suffix("")
    n = comfy.fetch_frames(comfy.outputs(hist, "60"), fdir)
    comfy.frames_to_mp4(fdir, out, FPS)
    shutil.rmtree(fdir, ignore_errors=True)
    m = dict(kind="humo", model=f"humo{size}", fps=FPS, frames=n, steps=steps or SIZES[size][2], seed=seed,
             image=str(image), prompt=prompt, delay_frames=0, seconds=round(time.time() - t0, 1))
    m.update(meta or {})
    clips.write_meta(out, **m)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("audio")
    ap.add_argument("prompt")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--frames", type=int, default=97, help="4n+1 at 25 fps")
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--size", choices=sorted(SIZES), default="1.7B")
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--allow-17b", action="store_true", help="run 17B anyway (needs > 16 GB VRAM)")
    ap.add_argument("--song-start", type=float, default=0.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if (a.frames - 1) % 4:
        raise SystemExit("--frames must be 4n+1 (e.g. 49, 97)")
    if a.dry_run:
        wf = workflow(Path(a.image).name, Path(a.audio).name, a.prompt, a.frames, a.seed, "dry", a.size, a.steps)
        print(json.dumps({"model": a.size, "frames": a.frames, "seconds": round(a.frames / FPS, 2), "size": f"{W}x{H}",
                          "nodes": {k: v["class_type"] for k, v in wf.items()},
                          "estimate_s": round(130 * a.frames / FPS)}, indent=1))
        return
    print("->", render(a.image, a.audio, a.prompt, a.out, a.frames, a.seed, a.size, a.steps,
                       meta={"song_start": a.song_start}, allow_17b=a.allow_17b))


if __name__ == "__main__":
    main()
