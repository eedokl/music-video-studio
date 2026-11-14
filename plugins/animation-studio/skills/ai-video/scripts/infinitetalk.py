# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""InfiniteTalk (Wan2.1-I2V-14B 480p fp8 + InfiniteTalk patch + LightX2V, 6 steps) through the local ComfyUI:
start image + vocals -> singing face that stays closest to the start image (framing, light, face).
Best for held notes and long sung passages (lip-sync comparison: most even hits over 12 s, r 0.58 on a held call vs
S2V 0.53), ~80 s GPU per second of video, 832x480 at 25 fps (upscaled in the cut).
Up to 81 frames (3.2 s) are one pass; longer takes are CHAINED automatically: 81-frame passes, each continuing from
the last 9 frames of the one before (previous_frames, motion_frame_count 9; the node moves the audio window itself),
so one 12.7 s take replaces four cuts (claudia-live V3 bridge: parts 81+81+81+81+61). parts_for() splits.
Model files: diffusion_models/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ, loras/lightx2v_I2V_14B_480p_cfg_step_distill_
rank64_bf16, model_patches/wan2.1_infiniteTalk_multi_fp16, audio_encoders/wav2vec2-chinese-base_fp16,
text_encoders/umt5_xxl_fp8_e4m3fn_scaled, vae/Wan2_1_VAE_bf16 (names from assets/models.json; override: config comfy_models).
Usage:
  uv run infinitetalk.py start.png vocals.wav "prompt" -o clip.mp4 [--frames 97] [--seed 31]
"""
import argparse
import math
import shutil
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import clips  # noqa: E402
import comfy  # noqa: E402
import comfy_models  # noqa: E402

FPS = 25
W, H = 832, 480
LEAD_IN = 0.25
NEG = "static, frozen face, closed mouth, blurry, deformed, cartoon"


def frames_for(seconds, lead_in=LEAD_IN):
    """4n+1 frames at 25 fps covering lead-in + shot + 0.28 s."""
    n = int(math.ceil((seconds + lead_in + 0.28) * FPS))
    return (n - 1 + 3) // 4 * 4 + 1


PASS, MOTION = 81, 9


def parts_for(frames):
    """Pass lengths (4n+1 each) whose chained output (first + (n - 9) per extension) covers `frames`."""
    if frames <= PASS:
        return [frames]
    parts, left = [PASS], frames - PASS
    while left > PASS - MOTION:
        parts.append(PASS)
        left -= PASS - MOTION
    last = left + MOTION
    parts.append((last - 1 + 3) // 4 * 4 + 1)
    return parts


def workflow(img, wav, prompt, frames, seed, prefix):
    wf = _single(img, wav, prompt, frames, seed, prefix)
    parts = parts_for(frames)
    if len(parts) == 1:
        return wf
    for k in ("30", "40", "41", "42", "43", "44", "50", "60"):
        wf.pop(k)
    prev = None
    for i, n in enumerate(parts):
        b = 100 + i * 20
        wf[f"{b}"] = {"class_type": "WanInfiniteTalkToVideo", "inputs": {
            "mode": "single_speaker", "model": ["2", 0], "model_patch": ["5", 0], "positive": ["20", 0],
            "negative": ["21", 0], "vae": ["4", 0], "width": W, "height": H, "length": n, "start_image": ["11", 0],
            "audio_encoder_output_1": ["13", 0], "motion_frame_count": MOTION, "audio_scale": 1.0,
            **({"previous_frames": prev} if prev else {})}}
        wf[f"{b + 1}"] = {"class_type": "CFGGuider", "inputs": {"model": [f"{b}", 0], "positive": [f"{b}", 1],
                                                                "negative": [f"{b}", 2], "cfg": 1.0}}
        wf[f"{b + 2}"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
        wf[f"{b + 3}"] = {"class_type": "BasicScheduler", "inputs": {"model": [f"{b}", 0], "scheduler": "normal",
                                                                     "steps": 6, "denoise": 1.0}}
        wf[f"{b + 4}"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed + i}}
        wf[f"{b + 5}"] = {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": [f"{b + 4}", 0], "guider": [f"{b + 1}", 0], "sampler": [f"{b + 2}", 0], "sigmas": [f"{b + 3}", 0],
            "latent_image": [f"{b}", 3]}}
        wf[f"{b + 6}"] = {"class_type": "VAEDecode", "inputs": {"samples": [f"{b + 5}", 0], "vae": ["4", 0]}}
        if prev is None:
            prev = [f"{b + 6}", 0]
        else:                                          # drop the frames the pass repeats, append the new ones
            wf[f"{b + 7}"] = {"class_type": "ImageFromBatch", "inputs": {"image": [f"{b + 6}", 0],
                                                                         "batch_index": [f"{b}", 4], "length": 4096}}
            wf[f"{b + 8}"] = {"class_type": "ImageBatch", "inputs": {"image1": prev, "image2": [f"{b + 7}", 0]}}
            prev = [f"{b + 8}", 0]
    wf["60"] = {"class_type": "SaveImage", "inputs": {"images": prev, "filename_prefix": prefix}}
    return wf


def _single(img, wav, prompt, frames, seed, prefix):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": comfy_models.file("wan21_i2v_480p"),
                                                     "weight_dtype": "default"}},
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "strength_model": 1.0,
              "lora_name": comfy_models.file("lightx2v_i2v_lora")}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": comfy_models.file("umt5_xxl"), "type": "wan",
                                                     "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": comfy_models.file("wan21_vae_bf16")}},
        "5": {"class_type": "ModelPatchLoader", "inputs": {"name": comfy_models.file("infinitetalk_patch")}},
        "6": {"class_type": "AudioEncoderLoader", "inputs": {"audio_encoder_name": comfy_models.file("wav2vec2_zh")}},
        "10": {"class_type": "LoadImage", "inputs": {"image": img}},
        "11": {"class_type": "ImageScale", "inputs": {"image": ["10", 0], "upscale_method": "lanczos", "width": W,
                                                     "height": H, "crop": "center"}},
        "12": {"class_type": "LoadAudio", "inputs": {"audio": wav}},
        "13": {"class_type": "AudioEncoderEncode", "inputs": {"audio_encoder": ["6", 0], "audio": ["12", 0]}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": prompt}},
        "21": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["20", 0]}},
        "30": {"class_type": "WanInfiniteTalkToVideo", "inputs": {"mode": "single_speaker", "model": ["2", 0],
               "model_patch": ["5", 0], "positive": ["20", 0], "negative": ["21", 0], "vae": ["4", 0], "width": W,
               "height": H, "length": frames, "start_image": ["11", 0], "audio_encoder_output_1": ["13", 0],
               "motion_frame_count": 9, "audio_scale": 1.0}},
        "40": {"class_type": "CFGGuider", "inputs": {"model": ["30", 0], "positive": ["30", 1], "negative": ["30", 2], "cfg": 1.0}},
        "41": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "42": {"class_type": "BasicScheduler", "inputs": {"model": ["30", 0], "scheduler": "normal", "steps": 6, "denoise": 1.0}},
        "43": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "44": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["43", 0], "guider": ["40", 0], "sampler": ["41", 0],
                                                                  "sigmas": ["42", 0], "latent_image": ["30", 3]}},
        "50": {"class_type": "VAEDecode", "inputs": {"samples": ["44", 0], "vae": ["4", 0]}},
        "60": {"class_type": "SaveImage", "inputs": {"images": ["50", 0], "filename_prefix": prefix}},
    }


def render(image, audio, prompt, out, frames=97, seed=31, meta=None):
    """One take of any length (chained passes beyond 81 frames) -> out.mp4 (25 fps) + out.json."""
    comfy.ensure()
    comfy.lock("infinitetalk", "comfy:infinitetalk")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tag = f"{out.parent.name}_{out.stem}"
    t0 = time.time()
    wf = workflow(comfy.upload(image, f"it_{tag}{Path(image).suffix}"), comfy.upload(audio, f"it_{tag}{Path(audio).suffix}"),
                  prompt, frames, seed, f"animation-studio/infinitetalk/{tag}")
    hist = comfy.run(wf, timeout=6 * 3600)
    fdir = out.with_suffix("")
    n = comfy.fetch_frames(comfy.outputs(hist, "60"), fdir)
    comfy.frames_to_mp4(fdir, out, FPS)
    shutil.rmtree(fdir, ignore_errors=True)
    m = dict(kind="infinitetalk", fps=FPS, frames=n, parts=parts_for(frames), seed=seed, image=str(image), prompt=prompt, delay_frames=0,
             seconds=round(time.time() - t0, 1))
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
    ap.add_argument("--song-start", type=float, default=0.0)
    a = ap.parse_args()
    print("->", render(a.image, a.audio, a.prompt, a.out, a.frames, a.seed, meta={"song_start": a.song_start}))


if __name__ == "__main__":
    main()
