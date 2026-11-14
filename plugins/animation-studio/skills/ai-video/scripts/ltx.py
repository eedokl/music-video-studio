# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# ///
"""LTX-2.3 22B distilled (fp8) image+audio -> video through the local ComfyUI. Two uses:

  lipsync  start image + the LEAD VOCALS of the shot -> the person sings those words (default for sung lines)
  moving   start image + the INSTRUMENTAL of the shot -> real motion for B-roll / "moving stills" (no singing)

Workflow after ComfyUI's template video_ltx2_3_ia2v, one stage (no spatial upscaler):
  audio -> LTXVAudioVAEEncode -> SetLatentNoiseMask(mask 0: the audio is NOT denoised, it stays fixed)
  image -> LTXVPreprocess -> LTXVImgToVideoInplace (first frame, strength) -> LTXVConcatAVLatent -> 8 euler steps
Model files: checkpoints/ltx-2.3-22b-distilled-fp8.safetensors, text_encoders/gemma_3_12B_it_fp8_scaled.safetensors.
Cost (RTX 5060 Ti 16 GB): ~150 s per 97 frames warm, model load ~7 min cold, peaks ~45 GB system RAM.
Licence: LTX-2 Community License (free under USD 10M revenue) - AI-generated content must be labelled.

Prompt lessons (measured, Europe 2031):
  - NEVER write "no text"/"no letters" in the positive prompt: LTX paints garbled lettering. Text, letters, logos,
    scene cuts go into the NEGATIVE prompt only (NEG_MOVING does that).
  - Every prompt needs one light/look sentence matching the start image, otherwise LTX jumps to another scene.
  - Crowds (audiences jumping, clapping): img_compression 42 instead of 18 and a prompt starting "A cinematic scene
    of ..." - the start image binds less, the crowd moves (claudia-live publikum_test, recipe A won over Wan 2.1 +
    LightX2V and MiniMax H3; used for all crowd shots in Live V4). CROWD_COMPRESSION, crowd_prompt().
  - Lip-sync: quote the sung words, "her lips clearly form every word, the mouth opens wide on the vowels and closes on
    m, b and p". Seeds vary a lot - render 2-4 and pick by measurement (mouth.py).
Usage:
  uv run ltx.py lipsync start.png vocals.wav "prompt" -o clip.mp4 [--frames 97] [--seed 31] [--strength 1.0]
  uv run ltx.py moving still.png music.wav "prompt" -o clip.mp4 [--frames 97] [--seed 7]
"""
import argparse
import re
import shutil
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import clips  # noqa: E402
import comfy  # noqa: E402

CKPT = "ltx-2.3-22b-distilled-fp8.safetensors"
GEMMA = "gemma_3_12B_it_fp8_scaled.safetensors"
SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"   # template, stage 1 (distilled)
NEG_LIPSYNC = ("pc game, console game, video game, cartoon, childish, ugly, static, frozen face, blurry mouth, "
               "text, letters, subtitles, watermark, logo, scene cut")
NEG_MOVING = ("text, letters, words, subtitles, captions, title, watermark, logo, typography, scene cut, "
              "sudden scene change, cartoon, ugly, static")
W, H = 1280, 704
CROWD_COMPRESSION = 42
NO_TEXT = re.compile(r",?\s*\bno (text|letters|words|logos?|lettering|typography|subtitles|captions)\b[^,.]*", re.I)


def clean_positive(prompt):
    """Remove "no text"-style phrases from a positive LTX prompt (they cause garbled lettering)."""
    p = NO_TEXT.sub("", prompt)
    return re.sub(r"\s{2,}", " ", p).strip()


def crowd_prompt(prompt, crowd="a rowdy, packed concert audience going wild"):
    """The crowd recipe's opening: "A cinematic scene of <a crowd going wild>." before the shot's own motion text.
    (Measured on Europe 2031 Live shot 19, same image and seed: plain prompt motion 0.8, "A cinematic scene of " +
    the motion text 7.8, with the crowd sentence as in the reference recipe see reference-tests.)"""
    p = prompt.strip()
    return p if p.lower().startswith("a cinematic scene of") else f"A cinematic scene of {crowd}. {p}"


def workflow(img, wav, prompt, neg, frames, seed, strength=1.0, prefix="animation-studio/ltx", w=W, h=H, compression=18):
    dur = frames / clips.LTX_FPS
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "LTXAVTextEncoderLoader", "inputs": {"text_encoder": GEMMA, "ckpt_name": CKPT, "device": "default"}},
        "3": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": CKPT}},
        "10": {"class_type": "LoadImage", "inputs": {"image": img}},
        "11": {"class_type": "ImageScale", "inputs": {"image": ["10", 0], "upscale_method": "lanczos", "width": w,
                                                     "height": h, "crop": "center"}},
        "12": {"class_type": "LTXVPreprocess", "inputs": {"image": ["11", 0], "img_compression": compression}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "21": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": neg}},
        "22": {"class_type": "LTXVConditioning", "inputs": {"positive": ["20", 0], "negative": ["21", 0],
                                                           "frame_rate": float(clips.LTX_FPS)}},
        "30": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": w, "height": h, "length": frames, "batch_size": 1}},
        "31": {"class_type": "LTXVImgToVideoInplace", "inputs": {"vae": ["1", 2], "image": ["12", 0], "latent": ["30", 0],
                                                                "strength": strength, "bypass": False}},
        "40": {"class_type": "LoadAudio", "inputs": {"audio": wav}},
        "41": {"class_type": "TrimAudioDuration", "inputs": {"audio": ["40", 0], "start_index": 0.0, "duration": dur}},
        "42": {"class_type": "LTXVAudioVAEEncode", "inputs": {"audio": ["41", 0], "audio_vae": ["3", 0]}},
        "43": {"class_type": "SolidMask", "inputs": {"value": 0.0, "width": w, "height": h}},
        "44": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["42", 0], "mask": ["43", 0]}},
        "45": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["31", 0], "audio_latent": ["44", 0]}},
        "50": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["22", 0], "negative": ["22", 1], "cfg": 1.0}},
        "51": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "52": {"class_type": "ManualSigmas", "inputs": {"sigmas": SIGMAS}},
        "53": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "54": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["53", 0], "guider": ["50", 0], "sampler": ["51", 0],
                                                                  "sigmas": ["52", 0], "latent_image": ["45", 0]}},
        "55": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["54", 0]}},
        "60": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["55", 0], "vae": ["1", 2], "tile_size": 768,
                                                         "overlap": 64, "temporal_size": 4096, "temporal_overlap": 4}},
        "70": {"class_type": "SaveImage", "inputs": {"images": ["60", 0], "filename_prefix": prefix}},
    }


def render(mode, image, audio, prompt, out, frames=97, seed=31, strength=1.0, neg=None, meta=None, w=W, h=H,
           compression=18):
    """Image + sound file -> out.mp4 (24 fps) + out.json (clips.py conventions; `meta` adds song_start etc.)."""
    if mode not in ("lipsync", "moving"):
        raise ValueError(mode)
    comfy.ensure()
    comfy.lock(f"ltx_{mode}", "comfy:ltx23")
    pos = clean_positive(prompt)
    neg = neg or (NEG_LIPSYNC if mode == "lipsync" else NEG_MOVING)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    tag = f"{out.parent.name}_{out.stem}"
    wf = workflow(comfy.upload(image, f"ltx_{tag}{Path(image).suffix}"), comfy.upload(audio, f"ltx_{tag}{Path(audio).suffix}"),
                  pos, neg, frames, seed, strength, f"animation-studio/ltx/{tag}", w, h, compression)
    hist = comfy.run(wf, timeout=3 * 3600)
    fdir = out.with_suffix("")
    n = comfy.fetch_frames(comfy.outputs(hist, "70"), fdir)
    comfy.frames_to_mp4(fdir, out, clips.LTX_FPS)
    shutil.rmtree(fdir, ignore_errors=True)
    m = dict(kind=f"ltx_{mode}", fps=clips.LTX_FPS, frames=n, seed=seed, strength=strength, compression=compression,
             image=str(image),
             prompt=pos, negative=neg, seconds=round(time.time() - t0, 1),
             delay_frames=clips.LTX_DELAY_FRAMES if mode == "lipsync" else 0)
    m.update(meta or {})
    clips.write_meta(out, **m)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["lipsync", "moving"])
    ap.add_argument("image")
    ap.add_argument("audio")
    ap.add_argument("prompt")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--frames", type=int, default=97, help="8n+1 (97 = 4 s)")
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--strength", type=float, default=1.0, help="how strictly frame 0 follows the image (0.7-1.0)")
    ap.add_argument("--song-start", type=float, default=0.0, help="song time of the audio's first sample (for cutting)")
    ap.add_argument("--compression", type=int, default=18, help="img_compression of the start image (crowds: 42)")
    a = ap.parse_args()
    out = render(a.mode, a.image, a.audio, a.prompt, a.out, a.frames, a.seed, a.strength, meta={"song_start": a.song_start},
                 compression=a.compression)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
