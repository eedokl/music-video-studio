# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# ///
"""Text-to-image with the local ComfyUI: painted backgrounds, B-roll stills, concept images, comic panels.

Models (files in ComfyUI's models folders):
  flux = FLUX.1 schnell fp8 (default, Apache 2.0): checkpoints/flux1-schnell-fp8.safetensors - 4 steps, cfg 1, exact content
  sdxl = SDXL Base 1.0: checkpoints/sd_xl_base_1.0.safetensors - style LoRAs, negative prompt
  qwen = Qwen-Image 2512 fp8: diffusion_models/qwen_image_2512_fp8_e4m3fn + text_encoders/qwen_2.5_vl_7b_fp8_scaled +
         vae/qwen_image_vae - correct lettering inside the image, ~3x slower
Usage:
  uv run comfy_image.py "prompt ..." -o image.png [--width 1280 --height 720] [--seed 1]
         [--model flux|sdxl|qwen] [--steps N] [--variants 4] [--negative "..."] [--lora file --lora-strength 0.8]
         [--repaint image.png --strength 0.45]
  --variants N: N images with seeds seed..seed+N-1 -> image_1.png ... image_N.png (to choose from)
  --repaint: img2img - take an image as template and paint it again (e.g. FLUX composition, SDXL + LoRA look)
From Python (other skills):  _studio.use("ai-video"); from comfy_image import generate; generate(prompt, "bg.png")
Notes: keep sizes divisible by 16 (1280x720 works). FLUX invents lettering now and then - write "no text, no letters,
no logos" at the end of a still's prompt (stills only; never in an LTX video prompt) and check the contact sheet.
FLUX has no alpha channel: for cut-outs paint on a flat colour and key it out.
Takes the shared GPU lock (model "comfy:<model>") - one AI job at a time.
"""
import argparse
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import comfy  # noqa: E402

MODELS = {   # name: (checkpoint, steps, cfg, sampler, scheduler, latent node)
    "flux": ("flux1-schnell-fp8.safetensors", 4, 1.0, "euler", "simple", "EmptySD3LatentImage"),
    "sdxl": ("sd_xl_base_1.0.safetensors", 28, 6.5, "dpmpp_2m", "karras", "EmptyLatentImage"),
    "qwen": ("qwen_image_2512_fp8_e4m3fn.safetensors", 30, 2.5, "euler", "simple", "EmptySD3LatentImage"),
}
QWEN_TE, QWEN_VAE = "qwen_2.5_vl_7b_fp8_scaled.safetensors", "qwen_image_vae.safetensors"
SDXL_NEG = "photo, 3d render, blurry, lowres, text, watermark, signature, deformed, ugly"


def workflow(prompt, w, h, seed, steps=None, model="flux", neg=None, lora=None, lora_strength=0.8, init=None, denoise=1.0):
    ckpt, st, cfg, sampler, sched, latent = MODELS[model]
    steps = steps or st
    neg = neg if neg is not None else ("" if model == "flux" else SDXL_NEG)
    M = "8" if lora else "1"                 # with a LoRA, model and text encoder run through the LoRA node
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": [M, 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": [M, 1]}},
        "4": {"class_type": latent, "inputs": {"width": w, "height": h, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": [M, 0], "positive": ["2", 0], "negative": ["3", 0],
                                                   "latent_image": ["4", 0], "seed": seed, "steps": steps, "cfg": cfg,
                                                   "sampler_name": sampler, "scheduler": sched, "denoise": denoise}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "animation-studio/image"}},
    }
    if model == "qwen":                      # separate loaders instead of a checkpoint; time shift as in the template
        wf["1"] = {"class_type": "VAELoader", "inputs": {"vae_name": QWEN_VAE}}
        wf["11"] = {"class_type": "UNETLoader", "inputs": {"unet_name": ckpt, "weight_dtype": "default"}}
        wf["12"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": QWEN_TE, "type": "qwen_image", "device": "default"}}
        wf["13"] = {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["11", 0], "shift": 3.1}}
        wf["2"]["inputs"]["clip"] = ["12", 0]
        wf["3"]["inputs"]["clip"] = ["12", 0]
        wf["5"]["inputs"]["model"] = ["13", 0]
        wf["6"]["inputs"]["vae"] = ["1", 0]
        if init:
            raise SystemExit("--repaint is not available for qwen")
    if init:                                 # repaint (img2img): uploaded image instead of an empty latent
        wf["9"] = {"class_type": "LoadImage", "inputs": {"image": init}}
        wf["10"] = {"class_type": "ImageScale", "inputs": {"image": ["9", 0], "upscale_method": "lanczos",
                                                          "width": w, "height": h, "crop": "center"}}
        wf["4"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["1", 2]}}
    if lora:
        wf["8"] = {"class_type": "LoraLoader", "inputs": {"model": ["1", 0], "clip": ["1", 1], "lora_name": lora,
                                                         "strength_model": lora_strength, "strength_clip": lora_strength}}
    return wf


def generate(prompt, out, w=1280, h=720, seed=1, steps=None, model="flux", neg=None, lora=None, lora_strength=0.8,
             init=None, denoise=1.0, timeout=None):
    """One image -> out (PNG). `init` = name returned by comfy.upload (repaint). Returns seconds taken."""
    comfy.ensure()
    comfy.lock("comfy_image", "comfy:" + model)
    t0 = time.time()
    h_ = comfy.run(workflow(prompt, w, h, seed, steps, model, neg, lora, lora_strength, init, denoise),
                   timeout=timeout or (2700 if model == "qwen" else 900))
    imgs = comfy.outputs(h_)
    if not imgs:
        raise RuntimeError("ComfyUI returned no image")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    comfy.fetch(imgs[0], out)
    return time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--steps", type=int, default=None, help="default: flux 4, sdxl 28, qwen 30")
    ap.add_argument("--model", choices=sorted(MODELS), default="flux")
    ap.add_argument("--negative", default=None, help="useful for sdxl/qwen only")
    ap.add_argument("--variants", type=int, default=1)
    ap.add_argument("--lora", help="file in models/loras, e.g. watercolor_v1_sdxl.safetensors (sdxl only)")
    ap.add_argument("--lora-strength", type=float, default=0.8)
    ap.add_argument("--repaint", help="existing image as template (img2img)")
    ap.add_argument("--strength", type=float, default=0.45, help="repaint: 0 = unchanged, 1 = completely new")
    a = ap.parse_args()
    comfy.ensure()
    comfy.lock("comfy_image", "comfy:" + a.model)
    out = Path(a.out)
    init = comfy.upload(a.repaint) if a.repaint else None
    for k in range(a.variants):
        dst = out if a.variants == 1 else out.with_name(f"{out.stem}_{k + 1}{out.suffix}")
        dt = generate(a.prompt, dst, a.width, a.height, a.seed + k, a.steps, a.model, a.negative, a.lora, a.lora_strength,
                      init, a.strength if init else 1.0)
        print(f"-> {dst} ({dt:.1f} s, seed {a.seed + k})")


if __name__ == "__main__":
    main()
