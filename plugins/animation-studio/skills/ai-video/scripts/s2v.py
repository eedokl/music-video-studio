"""Wan2.2-S2V 14B (fp8) through the local ComfyUI: start image + vocals -> the most expressive singing (held notes,
climaxes). 832x480 at 16 fps, length 4n+1 frames; ~11-18 min per 4 s shot with 20 steps (cfg 6). Upscale in the cut.
Use it only for single expressive moments under ~4.7 s: on longer runs it turns the face into profile (measured) and
hits the words worse than LTX-2.3; for long sung passages InfiniteTalk was better (see references/models.md).
Model files: diffusion_models/wan2.2_s2v_14B_fp8_scaled, text_encoders/umt5_xxl_fp8_e4m3fn_scaled, vae/wan_2.1_vae,
audio_encoders/wav2vec2_large_english_fp16 (light mode: loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise).
Usage:
  uv run --no-project python s2v.py start.png vocals.wav "prompt" -o clip.mp4 [--frames 61] [--steps 20] [--seed 31] [--light]
"""
import argparse
import shutil
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import clips  # noqa: E402
import comfy  # noqa: E402

W, H = 832, 480
NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，"
       "多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")
# (Wan's standard Chinese negative: garish colours, overexposure, static, blur, subtitles, worst quality, deformed hands ...)


def workflow(img, wav, prompt, neg, frames, steps, cfg, seed, prefix, light=False):
    wf = {
        "37": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_s2v_14B_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "38": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
        "39": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "57": {"class_type": "AudioEncoderLoader", "inputs": {"audio_encoder_name": "wav2vec2_large_english_fp16.safetensors"}},
        "58": {"class_type": "LoadAudio", "inputs": {"audio": wav}},
        "52": {"class_type": "LoadImage", "inputs": {"image": img}},
        "56": {"class_type": "AudioEncoderEncode", "inputs": {"audio_encoder": ["57", 0], "audio": ["58", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["38", 0], "text": prompt}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["38", 0], "text": neg}},
        "54": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["107", 0] if light else ["37", 0], "shift": 8}},
        "93": {"class_type": "WanSoundImageToVideo", "inputs": {"positive": ["6", 0], "negative": ["7", 0], "vae": ["39", 0],
               "width": W, "height": H, "length": frames, "batch_size": 1, "audio_encoder_output": ["56", 0], "ref_image": ["52", 0]}},
        "3": {"class_type": "KSampler", "inputs": {"model": ["54", 0], "positive": ["93", 0], "negative": ["93", 1],
              "latent_image": ["93", 2], "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "uni_pc",
              "scheduler": "simple", "denoise": 1.0}},
        "94": {"class_type": "LatentCut", "inputs": {"samples": ["3", 0], "dim": "t", "index": 0, "amount": 1}},
        "95": {"class_type": "LatentConcat", "inputs": {"samples1": ["94", 0], "samples2": ["3", 0], "dim": "t"}},
        "80": {"class_type": "VAEDecode", "inputs": {"samples": ["95", 0], "vae": ["39", 0]}},
        "96": {"class_type": "ImageFromBatch", "inputs": {"image": ["80", 0], "batch_index": 3, "length": 4096}},
        "99": {"class_type": "SaveImage", "inputs": {"images": ["96", 0], "filename_prefix": prefix}},
    }
    if light:
        wf["107"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["37", 0], "strength_model": 1.0,
                     "lora_name": "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors"}}
    return wf


def render(image, audio, prompt, out, frames=61, steps=20, seed=31, light=False, neg=NEG, meta=None):
    comfy.ensure()
    comfy.lock("s2v", "comfy:wan_s2v")
    steps, cfg = (4, 1.0) if light else (steps, 6.0)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tag = f"{out.parent.name}_{out.stem}"
    t0 = time.time()
    wf = workflow(comfy.upload(image, f"s2v_{tag}{Path(image).suffix}"), comfy.upload(audio, f"s2v_{tag}{Path(audio).suffix}"),
                  prompt, neg, frames, steps, cfg, seed, f"animation-studio/s2v/{tag}", light)
    hist = comfy.run(wf, timeout=4 * 3600)
    fdir = out.with_suffix("")
    n = comfy.fetch_frames(comfy.outputs(hist, "99"), fdir)
    comfy.frames_to_mp4(fdir, out, clips.S2V_FPS)
    shutil.rmtree(fdir, ignore_errors=True)
    m = dict(kind="s2v", fps=clips.S2V_FPS, frames=n, steps=steps, seed=seed, image=str(image), prompt=prompt,
             delay_frames=0, seconds=round(time.time() - t0, 1))
    m.update(meta or {})
    clips.write_meta(out, **m)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("audio")
    ap.add_argument("prompt")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--frames", type=int, default=61, help="4n+1 at 16 fps (61 = 3.8 s)")
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--light", action="store_true", help="4 steps with the Lightning LoRA (fast, weaker)")
    ap.add_argument("--song-start", type=float, default=0.0)
    a = ap.parse_args()
    print("->", render(a.image, a.audio, a.prompt, a.out, a.frames, a.steps, a.seed, a.light, meta={"song_start": a.song_start}))


if __name__ == "__main__":
    main()
