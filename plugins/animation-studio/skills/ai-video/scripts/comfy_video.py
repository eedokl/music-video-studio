# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# ///
"""Short video from a still with the local ComfyUI, WITHOUT sound: backgrounds with wind, light, clouds, water.

Models:
  wan = Wan 2.2 TI2V 5B (Apache 2.0): diffusion_models/wan2.2_ti2v_5B_fp16 + vae/wan2.2_vae + text_encoders/umt5_xxl_fp8
        24 fps, length 4n+1 frames, 1280x704 - best quality, ~400 s per 4 s
  ltx = LTX-Video 2B 0.9.8 distilled: checkpoints/ltxv-2b-0.9.8-distilled + text_encoders/t5xxl_fp8
        fast (8 steps), length 8n+1 frames, e.g. 1216x704 - for quick previews
For photographic music videos prefer ltx.py (LTX-2.3 with the music as sound track: "moving stills", better motion).
Usage:
  uv run comfy_video.py wan image.png "prompt" -o clip.mp4 [--seconds 4] [--width 1280 --height 704]
         [--seed 1] [--steps N] [--negative "..."]
Result: MP4 (h264, 24 fps) + the frames in <clip>_frames/ (for compositing).
Note: do not animate characters with it (they lose their look, no lips) - backgrounds, light, weather, transitions.
"""
import argparse
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import comfy  # noqa: E402

NEG = ("blurry, distorted, deformed, morphing, flickering, text, watermark, low quality, jpeg artifacts, "
       "extra limbs, melting, person, people, figure walking, smoke, camera movement")   # Wan invents figures/smoke otherwise


def wf_wan(img, prompt, neg, w, h, n, seed, steps):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": img}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["2", 0]}},
        "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {"vae": ["3", 0], "width": w, "height": h, "length": n,
                                                                 "batch_size": 1, "start_image": ["4", 0]}},
        "8": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["8", 0], "positive": ["5", 0], "negative": ["6", 0],
                                                   "latent_image": ["7", 0], "seed": seed, "steps": steps, "cfg": 5.0,
                                                   "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "animation-studio/video"}},
    }


def wf_ltx(img, prompt, neg, w, h, n, seed, steps):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ltxv-2b-0.9.8-distilled.safetensors"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors", "type": "ltxv"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": img}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["2", 0]}},
        "7": {"class_type": "LTXVImgToVideo", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["1", 2],
                                                        "image": ["4", 0], "width": w, "height": h, "length": n,
                                                        "batch_size": 1, "strength": 1.0}},
        "8": {"class_type": "LTXVConditioning", "inputs": {"positive": ["7", 0], "negative": ["7", 1], "frame_rate": 24.0}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["8", 0], "negative": ["8", 1],
                                                   "latent_image": ["7", 2], "seed": seed, "steps": steps, "cfg": 1.0,
                                                   "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "animation-studio/video"}},
    }


def image_to_video(model, image, prompt, out, seconds=4.0, w=None, h=None, seed=1, steps=None, neg=NEG):
    comfy.ensure()
    comfy.lock("comfy_video", "comfy:" + model)
    w = w or (1280 if model == "wan" else 1216)
    h = h or 704
    step = 4 if model == "wan" else 8
    n = int(round(seconds * 24 / step)) * step + 1
    steps = steps or (20 if model == "wan" else 8)
    t0 = time.time()
    wf = (wf_wan if model == "wan" else wf_ltx)(comfy.upload(image), prompt, neg, w, h, n, seed, steps)
    hist = comfy.run(wf, timeout=3 * 3600)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fdir = out.with_name(out.stem + "_frames")
    k = comfy.fetch_frames(comfy.outputs(hist), fdir)
    comfy.frames_to_mp4(fdir, out, 24, crf=18)
    return k, time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", choices=["wan", "ltx"])
    ap.add_argument("image")
    ap.add_argument("prompt")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--steps", type=int)
    ap.add_argument("--negative", default=NEG, help="own negative prompt (e.g. portraits: without 'person')")
    a = ap.parse_args()
    k, dt = image_to_video(a.model, a.image, a.prompt, a.out, a.seconds, a.width, a.height, a.seed, a.steps, a.negative)
    print(f"-> {a.out} ({k} frames, {a.model}, {dt:.0f} s)")


if __name__ == "__main__":
    main()
