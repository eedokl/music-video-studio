# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""LTX-2.5 22B distilled (community GGUF quant) through the local ComfyUI - EXPERIMENTAL, one use only:

  multishot  start image + the LEAD VOCALS of a passage -> ONE clip with a real cut inside (two shots, e.g. close-up
             -> frontal medium shot), the person keeps singing the given vocals across the cut. LTX-2.3 cannot cut.

Everything else stays with ltx.py (LTX-2.3): on the reference machine 2.5 is not faster (12.4 s per step against ~7),
its mouth opens wider but it pushes the camera in and drifts more. Use it for a sung passage of 6-8 s that wants a cut.
Expect to throw takes away: in the tests 1 of 10 takes that were long enough to cut was usable (references/multishot.md).
Workflow after ComfyUI's template video_ltx2_5_i2v, ONE stage at full size (the two-stage variant with the spatial
upscaler turned hard cuts into dissolves and peaked at 47 GB RAM against 39):
  audio -> LTXVAudioVAEEncode -> LTXVFreezeLatent (noise mask 0: the vocals stay fixed) -> LTXVConcatAVLatent
  image -> LTXVPreprocess -> LTXVImgToVideoInplace (first frame, strength 0.7)
  LTXVDualCFGGuider video 1 / audio 1, euler (not euler_ancestral), no modality guidance, 8 distilled steps
Model files (roles in assets/models.json; override: config comfy_models): diffusion_models/LTX-2.5-Distilled-Q4_K_M.gguf
(community quant, loaded by the node pack ComfyUI-GGUF), text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot,
vae/ltx-2.5-video-vae-bf16, vae/ltx-2.5-audio-vae-bf16 (the last three from the gated repo Lightricks/LTX-2.5: the user
accepts its terms on Hugging Face and logs in). The official transformers need 24-32 GB VRAM; the GGUF runs on 16 GB.
Cost (RTX 5060 Ti 16 GB, 48 GB RAM): ~295 s per 193 frames (8 s), peak ~39 GB RAM. ComfyUI's memory is flushed before
every clip - a second 8 s job right after the first failed with a file-read error at 47 GB.
Licence: LTX-2 Community License (free under USD 10M revenue) - AI-generated content must be labelled.

Prompt rules (LTX multi-shot guide + our trial, Europe 2031 chorus, 2026-11-20):
  - ONE chronological paragraph; every cut is a sentence ("A hard cut transitions to a frontal medium shot ... of ...").
    Shot lists and numbered beats do not cut.
  - After a cut repeat the person's identifiers word for word (hair, clip, microphone, clothes) - never "she".
  - Say that the song continues across the cut.
  - The face must stay LARGE after the cut: medium shot or closer, frontal. In a wide shot the face was ~70 px wide and
    broke (smeared mouth, another person). "Slightly from the side" became a full profile. check_cuts() refuses both.
  - The cut lands where the song changes (a new line, a shout) - plan the shot so that such a point lies in the
    middle. A 4.4 s shot with one unbroken line did not cut at all.
  - Two shots per clip. Render 3 seeds or more: the others grew a second hair clip, lost the streak or cut twice -
    pick.py checks three frames of every shot (canon.measure_frames) and the number of cuts.
Usage:
  uv run ltx25.py multishot start.png vocals.wav "opening shot prompt" --cut "frontal medium shot from the waist up" \
         --who "the woman with the black bob ..." --action "she shouts Hey! Hey! and raises her fist" \
         -o clip.mp4 [--frames 193] [--seed 7] [--strength 0.7] [--song-start 56.08] [--dry-run]
  --dry-run prints the prompt, the frame count and the node classes (no ComfyUI, no GPU).
From Python: ltx25.render(img, wav, prompt, out, frames, seed, cuts=1, meta=...) -> out.mp4 + out.json;
ltx25.multishot_prompt(opening, cuts, ending), ltx25.check_cuts(cuts), ltx25.frames_for(seconds).
"""
import argparse
import json
import math
import re
import shutil
import time
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import clips  # noqa: E402
import comfy_models  # noqa: E402

UNET, GEMMA, VAE_VIDEO, VAE_AUDIO = "ltx25_unet", "gemma4_ltx25_te", "ltx25_video_vae", "ltx25_audio_vae"   # models.json roles
SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"    # template video_ltx2_5_i2v, stage 1
NEG = ("pc game, console game, video game, cartoon, childish, ugly, static, frozen face, blurry mouth, text, letters, "
       "subtitles, watermark, logo")                       # no "scene cut" here: the cut is wanted
W, H = 1280, 704
FPS = 24
LEAD_IN = 0.25
DELAY_FRAMES = 0            # not measured for 2.5 (2.3: 1); pick.py measures the lag of every clip anyway
MIN_SECONDS = 6.0           # a 4.4 s shot did not cut in 6 renders; 7.7 s and 8 s shots cut every time
MAX_FRAMES = 193            # 8 s; longer is untested on 48 GB RAM
STRENGTH = 0.7
SMALL_FACE = ("wide", "full shot", "full-body", "full body", "long shot", "total", "establishing", "aerial", "extreme long")
TURNED = ("from behind", "from the back", "profile", "from the side", "side view", "over the shoulder", "over-the-shoulder")
TRANSITION = "A hard cut transitions to"


def frames_for(seconds, lead_in=LEAD_IN):
    """Frames (8n+1) covering lead-in + passage + 2 spare frames, at most MAX_FRAMES."""
    n = (seconds + lead_in) * FPS + 2
    return min(int(math.ceil((n - 1) / 8)) * 8 + 1, MAX_FRAMES)


def check_cuts(cuts, sung=True):
    """Problems of the shots after a cut -> list of strings. cuts: [{"framing": ..., "action": ...}, ...]."""
    errs = []
    if not cuts:
        errs.append("no cut given - a single shot is LTX-2.3's job (engine ltx)")
    if len(cuts) > 2:
        errs.append(f"{len(cuts) + 1} shots in one clip - two shots are tested, three at most")
    for i, c in enumerate(cuts, 2):
        f = (c.get("framing") or "").lower()
        if not f:
            errs.append(f"shot {i}: no framing - say e.g. 'frontal medium shot from the waist up'")
        if sung and any(w in f for w in SMALL_FACE):
            errs.append(f"shot {i}: '{c.get('framing')}' - the face gets too small to sing (it broke at ~70 px); "
                        "use a medium shot or closer")
        if sung and any(w in f for w in TURNED):
            errs.append(f"shot {i}: '{c.get('framing')}' - turned away, the singing mouth and the canon cannot be "
                        "checked; use a frontal framing")
    return errs


def cut_sentence(framing, who, action, place="", transition=TRANSITION):
    """One cut as prose: the transition, the new framing, the person's identifiers again, what happens."""
    f = framing.strip().rstrip(".")
    art = "an" if f[:1].lower() in "aeiou" else "a"
    act = action.strip().rstrip(".")
    return (f"{transition} {art} {f} from a new camera position{(' ' + place.strip().rstrip('.')) if place else ''}: "
            f"{who.strip().rstrip('.')}, facing the camera, the face large and sharp in the frame. "
            f"{act[0].upper() + act[1:]}.")


def multishot_prompt(opening, cuts, ending="", audio="The song continues unchanged across the cut."):
    """opening = the complete prompt text of shot 1 (without the look ending); cuts = [{"framing", "who", "action",
    "place"?, "transition"?}]; ending = the look sentence(s) for the whole clip."""
    parts = [opening.strip()]
    for c in cuts:
        parts.append(cut_sentence(c["framing"], c["who"], c["action"], c.get("place", ""), c.get("transition", TRANSITION)))
        parts.append(audio)
    if ending:
        parts.append(ending.strip())
    return " ".join(p for p in parts if p)


def clean_positive(prompt):
    """No "no text"-style phrases and no "single shot" promise in the positive prompt."""
    import ltx
    p = ltx.clean_positive(prompt)
    return re.sub(r"\s{2,}", " ", re.sub(r"\bContinuous single shot\.?", "", p, flags=re.I)).strip()


def workflow(img, wav, prompt, neg, frames, seed, strength=STRENGTH, prefix="animation-studio/ltx25", w=W, h=H):
    dur = frames / FPS
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": comfy_models.file(UNET)}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": comfy_models.file(GEMMA), "type": "ltxv", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": comfy_models.file(VAE_AUDIO)}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": comfy_models.file(VAE_VIDEO)}},
        "10": {"class_type": "LoadImage", "inputs": {"image": img}},
        "11": {"class_type": "ImageScale", "inputs": {"image": ["10", 0], "upscale_method": "lanczos", "width": w,
                                                     "height": h, "crop": "center"}},
        "12": {"class_type": "LTXVPreprocess", "inputs": {"image": ["11", 0], "img_compression": 18}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "21": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": neg}},
        "22": {"class_type": "LTXVConditioning", "inputs": {"positive": ["20", 0], "negative": ["21", 0],
                                                           "frame_rate": float(FPS)}},
        "30": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": w, "height": h, "length": frames, "batch_size": 1}},
        "31": {"class_type": "LTXVImgToVideoInplace", "inputs": {"vae": ["4", 0], "image": ["12", 0], "latent": ["30", 0],
                                                                "strength": strength, "bypass": False}},
        "40": {"class_type": "LoadAudio", "inputs": {"audio": wav}},
        "41": {"class_type": "TrimAudioDuration", "inputs": {"audio": ["40", 0], "start_index": 0.0, "duration": dur}},
        "42": {"class_type": "LTXVAudioVAEEncode", "inputs": {"audio": ["41", 0], "audio_vae": ["3", 0]}},
        "44": {"class_type": "LTXVFreezeLatent", "inputs": {"latent": ["42", 0]}},
        "45": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["31", 0], "audio_latent": ["44", 0]}},
        "50": {"class_type": "LTXVDualCFGGuider", "inputs": {"model": ["1", 0], "positive": ["22", 0], "negative": ["22", 1],
                                                            "video_cfg": 1.0, "audio_cfg": 1.0}},
        "51": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "52": {"class_type": "ManualSigmas", "inputs": {"sigmas": SIGMAS}},
        "53": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "54": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["53", 0], "guider": ["50", 0], "sampler": ["51", 0],
                                                                  "sigmas": ["52", 0], "latent_image": ["45", 0]}},
        "55": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["54", 0]}},
        "60": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["55", 0], "vae": ["4", 0], "tile_size": 512,
                                                         "overlap": 64, "temporal_size": 64, "temporal_overlap": 16}},
        "70": {"class_type": "SaveImage", "inputs": {"images": ["60", 0], "filename_prefix": prefix}},
    }


def render(image, audio, prompt, out, frames=MAX_FRAMES, seed=7, strength=STRENGTH, neg=None, meta=None, cuts=1):
    """Start image + vocals + a multi-shot prompt -> out.mp4 (24 fps) + out.json (clips.py conventions).
    cuts = number of cuts the prompt asks for (meta "cuts_expected": the picker must not call them hidden cuts)."""
    import comfy
    if (frames - 1) % 8 or frames > MAX_FRAMES:
        raise ValueError(f"frames must be 8n+1 and <= {MAX_FRAMES}, got {frames}")
    comfy.ensure()
    comfy.lock("ltx25_multishot", "comfy:ltx25")
    comfy.free()                      # every 8 s clip starts with empty ComfyUI memory (RAM peak, see module doc)
    pos = clean_positive(prompt)
    neg = neg or NEG
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    tag = f"{out.parent.name}_{out.stem}"
    wf = workflow(comfy.upload(image, f"ltx25_{tag}{Path(image).suffix}"), comfy.upload(audio, f"ltx25_{tag}{Path(audio).suffix}"),
                  pos, neg, frames, seed, strength, f"animation-studio/ltx25/{tag}")
    hist = comfy.run(wf, timeout=3 * 3600)
    fdir = out.with_suffix("")
    n = comfy.fetch_frames(comfy.outputs(hist, "70"), fdir)
    comfy.frames_to_mp4(fdir, out, FPS)
    shutil.rmtree(fdir, ignore_errors=True)
    m = dict(kind="ltx25_multishot", model="ltx25", fps=FPS, frames=n, seed=seed, strength=strength, image=str(image),
             prompt=pos, negative=neg, cuts_expected=int(cuts), seconds=round(time.time() - t0, 1),
             delay_frames=DELAY_FRAMES)
    m.update(meta or {})
    clips.write_meta(out, **m)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["multishot"])
    ap.add_argument("image")
    ap.add_argument("audio")
    ap.add_argument("prompt", help="shot 1; with --cut the cut sentence is appended, without it the text is used as it is")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--cut", help="framing of shot 2, e.g. 'frontal medium shot from the waist up'")
    ap.add_argument("--who", help="the person's identifiers, repeated after the cut")
    ap.add_argument("--action", default="the person keeps singing", help="what happens in shot 2")
    ap.add_argument("--place", default="", help="e.g. 'in the same dark conference room'")
    ap.add_argument("--ending", default="Cinematic photographic 35mm film look.")
    ap.add_argument("--frames", type=int, default=MAX_FRAMES, help=f"8n+1, at most {MAX_FRAMES} (= 8 s)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--strength", type=float, default=STRENGTH, help="how strictly frame 0 follows the image")
    ap.add_argument("--song-start", type=float, default=0.0, help="song time of the audio's first sample (for cutting)")
    ap.add_argument("--ignore-checks", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if (a.frames - 1) % 8 or a.frames > MAX_FRAMES:
        raise SystemExit(f"--frames must be 8n+1 and at most {MAX_FRAMES} (e.g. 121, 161, 193)")
    prompt, n_cuts = a.prompt, len(re.findall(r"\bcuts? (to|transitions?|jumps?)\b|\bmatch cut\b|\bdissolves? into\b", a.prompt, re.I))
    if a.cut:
        if not a.who:
            raise SystemExit("--cut needs --who (the person's identifiers are repeated after the cut)")
        cuts = [{"framing": a.cut, "who": a.who, "action": a.action, "place": a.place}]
        probs = check_cuts(cuts)
        if probs and not a.ignore_checks:
            raise SystemExit("cut problems (--ignore-checks renders anyway):\n  " + "\n  ".join(probs))
        prompt, n_cuts = multishot_prompt(a.prompt, cuts, a.ending), 1
    if a.dry_run:
        wf = workflow(Path(a.image).name, Path(a.audio).name, clean_positive(prompt), NEG, a.frames, a.seed, a.strength)
        print(json.dumps({"model": "ltx25", "frames": a.frames, "seconds": round(a.frames / FPS, 2), "size": f"{W}x{H}",
                          "cuts": n_cuts, "prompt": clean_positive(prompt),
                          "nodes": {k: v["class_type"] for k, v in wf.items()},
                          "estimate_s": round(295 * a.frames / MAX_FRAMES)}, indent=1))
        return
    print("->", render(a.image, a.audio, prompt, a.out, a.frames, a.seed, a.strength, meta={"song_start": a.song_start},
                       cuts=n_cuts))


if __name__ == "__main__":
    main()
