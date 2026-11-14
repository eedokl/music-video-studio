# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Start images that keep a character's identity: Qwen-Image-Edit 2511 (fp8, Lightning 4 steps) puts the person from
one or two reference images into a new scene described by the prompt.

Model files: diffusion_models/qwen_image_edit_2511_fp8_lightning_4steps.safetensors, text_encoders/
qwen_2.5_vl_7b_fp8_scaled.safetensors, vae/qwen_image_vae.safetensors (optional loras/qwen-image-edit-2511-multiple-angles-lora)
- names from assets/models.json; override: config comfy_models.
Usage:
  uv run qwen_edit.py --ref face.png --ref closeup.png "prompt" -o start.png [--seed 1]
         [--width 1280 --height 720] [--negative "..."] [--variants 3]
From Python: edit([ref1, ref2], prompt, "start.png", seed=1, neg="...")
Method that held a character best (Europe 2031): TWO references - image 1 = face + whole look, image 2 = a close-up of
the identity details (streak, clip) - and a prompt that starts "Keep the exact face, hair, ... of the woman in image 1
(image 2 shows the same woman in close-up, use it only for her face, ..., not for the framing): <identity text>".
For wide shots one reference and the short identity text work better. ~20-30 s per image once loaded (load ~9 min cold).
"""
import argparse
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import comfy  # noqa: E402
import comfy_models  # noqa: E402

UNET, TE, VAE = "qwen_image_edit", "qwen_vl_te", "qwen_vae"   # model file roles in assets/models.json
ANGLES_LORA = "qwen_edit_angles_lora"
NEG = "illustration, drawing, anime, cartoon, 3d render, teenage, childlike, text, logo, watermark, deformed hands, blurry"
_uploaded = {}


def workflow(refs, prompt, w, h, seed, neg=NEG, steps=4, lora=0.0):
    """refs = names in ComfyUI's input folder (comfy.upload)."""
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": comfy_models.file(UNET), "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": comfy_models.file(TE), "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": comfy_models.file(VAE)}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.1}},
        "5": {"class_type": "CFGNorm", "inputs": {"model": ["4", 0], "strength": 1.0}},
        "20": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
    }
    pos = {"clip": ["2", 0], "vae": ["3", 0], "prompt": prompt}
    negd = {"clip": ["2", 0], "vae": ["3", 0], "prompt": neg}
    for i, r in enumerate(refs):
        li, sc = str(10 + 2 * i), str(11 + 2 * i)
        wf[li] = {"class_type": "LoadImage", "inputs": {"image": r}}
        wf[sc] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": [li, 0], "upscale_method": "lanczos",
                                                                      "megapixels": 1.0, "resolution_steps": 1}}
        pos[f"image{i + 1}"] = [sc, 0]
        negd[f"image{i + 1}"] = [sc, 0]
    wf["6"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": pos}
    wf["7"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": negd}
    wf["8"] = {"class_type": "FluxKontextMultiReferenceLatentMethod",
               "inputs": {"conditioning": ["6", 0], "reference_latents_method": "index_timestep_zero"}}
    wf["9"] = {"class_type": "FluxKontextMultiReferenceLatentMethod",
               "inputs": {"conditioning": ["7", 0], "reference_latents_method": "index_timestep_zero"}}
    model = ["5", 0]
    if lora:
        wf["30"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["5", 0], "strength_model": lora,
                                                                    "lora_name": comfy_models.file(ANGLES_LORA)}}
        model = ["30", 0]
    wf["21"] = {"class_type": "KSampler", "inputs": {"model": model, "positive": ["8", 0], "negative": ["9", 0],
                                                     "latent_image": ["20", 0], "seed": seed, "steps": steps, "cfg": 1.0,
                                                     "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
    wf["22"] = {"class_type": "VAEDecode", "inputs": {"samples": ["21", 0], "vae": ["3", 0]}}
    wf["23"] = {"class_type": "SaveImage", "inputs": {"images": ["22", 0], "filename_prefix": "animation-studio/qwen_edit"}}
    return wf


def edit(refs, prompt, out, w=1280, h=720, seed=1, neg=NEG, lora=0.0, timeout=1800):
    """Local reference images -> one start image (PNG). Returns seconds taken."""
    comfy.ensure()
    comfy.lock("qwen_edit", "comfy:qwen_edit")
    names = [_uploaded.setdefault(str(Path(r).resolve()), comfy.upload(r)) for r in refs]
    t0 = time.time()
    h_ = comfy.run(workflow(names, prompt, w, h, seed, neg, lora=lora), timeout=timeout)
    imgs = comfy.outputs(h_)
    if not imgs:
        raise RuntimeError("ComfyUI returned no image")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    comfy.fetch(imgs[0], out)
    return time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt")
    ap.add_argument("--ref", action="append", required=True, help="reference image (1-3, order matters)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--negative", default=NEG)
    ap.add_argument("--variants", type=int, default=1)
    ap.add_argument("--angles-lora", type=float, default=0.0, help="strength of the multiple-angles LoRA (0 = off)")
    a = ap.parse_args()
    out = Path(a.out)
    for k in range(a.variants):
        dst = out if a.variants == 1 else out.with_name(f"{out.stem}_v{k + 1}{out.suffix}")
        dt = edit(a.ref, a.prompt, dst, a.width, a.height, a.seed + k, a.negative, a.angles_lora)
        print(f"-> {dst} ({dt:.1f} s, seed {a.seed + k})")


if __name__ == "__main__":
    main()
