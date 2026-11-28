# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""TEST MODEL - start images and picture edits with Qwen-Image 2.1 (int8 + the official Turbo LoRA, 8 steps): the same
call as qwen_edit.py (Qwen-Image-Edit 2511), to compare the two on a shot.

LICENCE: Qwen-Image 2.1, its Turbo LoRA and the Comfy-Org repack are under the Qwen RESEARCH LICENSE - research and
evaluation only, no commercial use without a separate licence from Qwen. Pictures for a film that is published or
sold: use qwen_edit.py (2511, Apache 2.0). Every run prints this note.

Model files: diffusion_models/qwen_image_2.1_int8_convrot.safetensors, text_encoders/qwen3vl_8b_int8_convrot.safetensors,
vae/qwen_image_2.1_vae_bf16.safetensors, loras/qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors - names from
assets/models.json; override: config comfy_models.
Usage:
  uv run qwen21.py --ref sheet.png [--ref closeup.png] "prompt" -o start.png [--seed 1]
         [--width 1280 --height 720] [--negative "..."] [--variants 3]
From Python: edit([ref1, ref2], prompt, "start.png", seed=1, neg="...")
What the comparison of 838 pictures showed (references/models.md): 2.1 keeps a face, a headset and small figures in
wide shots better and edits a finished picture more exactly (mic on/off, outfit, background, night); 2511 has the
stronger light, acting and gestures, real profiles and camera angles. At most THREE references - one sheet per person:
with four to seven the model paints the person several times. ~15-25 s per image once loaded.
The model works in multiples of 32: other sizes are rendered a little larger and cropped around the centre.
"""
import argparse
import sys
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import comfy  # noqa: E402
import comfy_models  # noqa: E402

UNET, TE, VAE, TURBO = "qwen21", "qwen21_te", "qwen21_vae", "qwen21_turbo_lora"   # roles in assets/models.json
NEG = "illustration, drawing, anime, cartoon, 3d render, teenage, childlike, text, logo, watermark, deformed hands, blurry"
SIGMAS = "1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0"   # ComfyUI's turbo template
MAX_REFS = 3
LICENCE = ("[qwen21] TEST MODEL under the Qwen Research License: research and evaluation only - "
           "for a film that is published or sold use qwen_edit.py (2511)")
_uploaded = {}
_told = []


def workflow(refs, prompt, w, h, seed, neg=NEG, ref_res=1024):
    """refs = names in ComfyUI's input folder (comfy.upload). After ComfyUI's template
    image_qwen_image_2_1_turbo_image_edit.json."""
    W, H = -(-w // 32) * 32, -(-h // 32) * 32
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": comfy_models.file(UNET), "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": comfy_models.file(TE), "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": comfy_models.file(VAE)}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": comfy_models.file(TURBO),
                                                              "strength_model": 1.0}},
        "5": {"class_type": "QwenImage21Cache", "inputs": {"model": ["4", 0], "device": "auto", "dtype": "default"}},
        "7": {"class_type": "EmptyLatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}},
    }
    enc = {"clip": ["2", 0], "vae": ["3", 0], "prompt": prompt, "negative_prompt": neg, "resolution": ref_res}
    for i, r in enumerate(refs):
        wf[str(10 + i)] = {"class_type": "LoadImage", "inputs": {"image": r}}
        enc[f"images.image_{i + 1}"] = [str(10 + i), 0]
    wf["6"] = {"class_type": "TextEncodeQwenImage21", "inputs": enc}
    wf["20"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
    wf["21"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
    wf["22"] = {"class_type": "ManualSigmas", "inputs": {"sigmas": SIGMAS}}
    wf["23"] = {"class_type": "CFGGuider", "inputs": {"model": ["5", 0], "positive": ["6", 0], "negative": ["6", 1], "cfg": 1.0}}
    wf["24"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["20", 0], "guider": ["23", 0], "sampler": ["21", 0],
                                                                  "sigmas": ["22", 0], "latent_image": ["7", 0]}}
    wf["30"] = {"class_type": "VAEDecode", "inputs": {"samples": ["24", 0], "vae": ["3", 0]}}
    wf["31"] = {"class_type": "ImageCrop", "inputs": {"image": ["30", 0], "width": w, "height": h,
                                                      "x": (W - w) // 2, "y": (H - h) // 2}}
    wf["32"] = {"class_type": "SaveImage", "inputs": {"images": ["31", 0], "filename_prefix": "animation-studio/qwen21"}}
    return wf


def edit(refs, prompt, out, w=1280, h=720, seed=1, neg=NEG, timeout=1800):
    """Local reference images -> one picture (PNG). Returns seconds taken."""
    refs = list(refs)
    if len(refs) > MAX_REFS:
        raise ValueError(f"qwen21: {len(refs)} references - at most {MAX_REFS} (with more the model paints the person "
                         "several times); use one sheet per person")
    if not _told:
        _told.append(1)
        print(LICENCE, file=sys.stderr, flush=True)
    comfy.ensure()
    comfy.lock("qwen21", "comfy:qwen21")
    names = [_uploaded.setdefault(str(Path(r).resolve()), comfy.upload(r)) for r in refs]
    t0 = time.time()
    h_ = comfy.run(workflow(names, prompt, w, h, seed, neg), timeout=timeout)
    imgs = comfy.outputs(h_)
    if not imgs:
        raise RuntimeError("ComfyUI returned no image")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    comfy.fetch(imgs[0], out)
    return time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt")
    ap.add_argument("--ref", action="append", required=True, help=f"reference image (1-{MAX_REFS}, order matters)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--negative", default=NEG)
    ap.add_argument("--variants", type=int, default=1)
    a = ap.parse_args()
    out = Path(a.out)
    for k in range(a.variants):
        dst = out if a.variants == 1 else out.with_name(f"{out.stem}_v{k + 1}{out.suffix}")
        dt = edit(a.ref, a.prompt, dst, a.width, a.height, a.seed + k, a.negative)
        print(f"-> {dst} ({dt:.1f} s, seed {a.seed + k})")


if __name__ == "__main__":
    main()
