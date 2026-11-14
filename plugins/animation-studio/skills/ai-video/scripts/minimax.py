# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# ///
"""MiniMax video models, two backends:

  comfy  (local, default) MiniMax H3 fl2va in the local ComfyUI: start image + vocals -> singing clip. The given vocal
         track is laid into the conditioning as an audio anchor from frame 0 (node MiniMaxH3AddGuide) - no latent
         surgery. Shortest trained length is 124 frames (5.2 s @24 fps): shorter shots are rendered long and cut.
         1024x576, int8 pruned model + Turbo LoRA (8 steps), ~42 s GPU per second of video. Lip-sync comparison
         2026-11-12: r 0.64 / 0.49 / 0.37 (fast syllables / plosives / held call) - good lips, but the user found the
         rest of the body robotic -> rescue engine for plosive lines only, next to an LTX seed. Licence of the H3
         weights unchecked: check it before a published film.
         Files: diffusion_models/minimax_h3_fl2va_pruned_int8_convrot, loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16,
         text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq, vae/minimax_h3_video_vae_int8_convrot,
         vae/minimax_h3_audio_vae_fp32.
  cloud  (opt-in, PAID) MiniMax's hosted video API (Hailuo image-to-video). It takes a first frame + prompt but NO audio,
         so it is a B-roll / moving-still engine, not lip sync. Strictly opt-in:
           - the key is read ONLY from the environment variable MINIMAX_API_KEY (never from files, never printed,
             never written into logs, json or jobs);
           - without --send the request is only built and shown (key redacted, image as size) = dry run;
           - with --send every call costs credits and the start image + prompt leave the machine: ask the user first.
         Endpoint base: config key `minimax_api_base` (env ANIMATION_STUDIO_MINIMAX_API_BASE), default https://api.minimax.io;
         flow: POST /v1/video_generation -> task_id; GET /v1/query/video_generation?task_id= until Success -> file_id;
         GET /v1/files/retrieve?file_id= -> download_url. Model: --cloud-model (default MiniMax-Hailuo-02). Check the
         current MiniMax API documentation before the first real call (names/prices change).
Usage:
  uv run minimax.py start.png vocals.wav "prompt" -o clip.mp4 [--seed 31] [--song-start 12.3]
         [--frames 124] [--width 1024 --height 576] [--dry-run]                       # local H3
  uv run minimax.py start.png - "prompt" -o broll.mp4 --backend cloud [--duration 6]
         [--resolution 768P] [--cloud-model MiniMax-Hailuo-02] [--send]                 # cloud (dry run without --send)
From Python: minimax.render(img, wav, prompt, out, ...) (local), minimax.cloud_request(...) / cloud_render(...).
"""
import argparse
import base64
import json
import math
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import clips  # noqa: E402
import config  # noqa: E402

FPS = 24
W, H = 1024, 576
MIN_FRAMES = 124
KEY_ENV = "MINIMAX_API_KEY"
DEFAULT_BASE = "https://api.minimax.io"
H3_SUFFIX = (" The scene opens exactly on image 1. She sings along to the given lead vocal track, lip-synced to every "
             "syllable. Static camera, one continuous shot, no cuts.")


# ------------------------------------------------------------------ local H3 (ComfyUI)
def frames_for(seconds, lead_in=0.25):
    """>= 124 frames (shortest trained length), else lead-in + shot + 0.28 s; 4n frames as in the H3 template."""
    n = int(math.ceil((seconds + lead_in + 0.28) * FPS))
    return max(MIN_FRAMES, (n + 3) // 4 * 4)


def workflow(img, wav, prompt, frames, seed, prefix, w=W, h=H, steps=8):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
                                                     "weight_dtype": "default"}},
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "strength_model": 1.0,
              "lora_name": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                                                     "type": "minimax", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_int8_convrot.safetensors"}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "10": {"class_type": "LoadImage", "inputs": {"image": img}},
        "12": {"class_type": "LoadAudio", "inputs": {"audio": wav}},
        "20": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["3", 0], "vae": ["4", 0], "width": w, "height": h,
               "length": frames, "first_frame": ["10", 0], "prompt": prompt.rstrip() + H3_SUFFIX}},
        "21": {"class_type": "MiniMaxH3AddGuide", "inputs": {"positive": ["20", 0], "audio_vae": ["5", 0], "latent": ["20", 1],
               "audio": ["12", 0], "frame_idx": 0}},
        "30": {"class_type": "BasicGuider", "inputs": {"model": ["2", 0], "conditioning": ["21", 0]}},
        "31": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "32": {"class_type": "BasicScheduler", "inputs": {"model": ["2", 0], "scheduler": "simple", "steps": steps, "denoise": 1.0}},
        "33": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "34": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["33", 0], "guider": ["30", 0], "sampler": ["31", 0],
               "sigmas": ["32", 0], "latent_image": ["20", 1]}},
        "40": {"class_type": "VAEDecode", "inputs": {"samples": ["34", 0], "vae": ["4", 0]}},
        "60": {"class_type": "SaveImage", "inputs": {"images": ["40", 0], "filename_prefix": prefix}},
    }


def render(image, audio, prompt, out, frames=MIN_FRAMES, seed=31, w=W, h=H, meta=None):
    """Local H3: start image + vocals (>= frames/24 s) -> out.mp4 (24 fps, no sound) + out.json."""
    import comfy
    if frames < MIN_FRAMES:
        raise SystemExit(f"MiniMax H3 needs >= {MIN_FRAMES} frames (shortest trained length)")
    comfy.ensure()
    comfy.lock("minimax_h3", "comfy:minimax_h3")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tag = f"{out.parent.name}_{out.stem}"
    t0 = time.time()
    wf = workflow(comfy.upload(image, f"h3_{tag}{Path(image).suffix}"), comfy.upload(audio, f"h3_{tag}{Path(audio).suffix}"),
                  prompt, frames, seed, f"animation-studio/minimax_h3/{tag}", w, h)
    hist = comfy.run(wf, timeout=4 * 3600)
    fdir = out.with_suffix("")
    n = comfy.fetch_frames(comfy.outputs(hist, "60"), fdir)
    comfy.frames_to_mp4(fdir, out, FPS)
    shutil.rmtree(fdir, ignore_errors=True)
    m = dict(kind="minimax_h3", fps=FPS, frames=n, seed=seed, image=str(image), prompt=prompt, delay_frames=0,
             seconds=round(time.time() - t0, 1))
    m.update(meta or {})
    clips.write_meta(out, **m)
    return out


# ------------------------------------------------------------------ cloud API (opt-in, paid)
def api_base():
    return (config.get("minimax_api_base") or DEFAULT_BASE).rstrip("/")


def _key():
    k = os.environ.get(KEY_ENV, "").strip()
    return k or None


def cloud_request(image, prompt, model="MiniMax-Hailuo-02", duration=6, resolution="768P"):
    """-> (url, headers WITHOUT the key, body). The image is embedded as a data URL."""
    p = Path(image)
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    body = {"model": model, "prompt": prompt, "duration": int(duration), "resolution": resolution,
            "first_frame_image": f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()}
    return api_base() + "/v1/video_generation", {"Content-Type": "application/json"}, body


def describe(url, headers, body):
    """Printable form of a request: key redacted, image replaced by its size."""
    b = dict(body)
    if "first_frame_image" in b:
        b["first_frame_image"] = f"<data URL, {len(b['first_frame_image'])} chars>"
    return {"POST": url, "headers": dict(headers, Authorization="Bearer <MINIMAX_API_KEY redacted>"), "json": b}


def _call(url, key, body=None, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:                      # never echo the request (it carries the key)
        raise RuntimeError(f"MiniMax HTTP {e.code} on {urllib.parse.urlparse(url).path}") from None


def cloud_render(image, prompt, out, model="MiniMax-Hailuo-02", duration=6, resolution="768P", send=False,
                 poll=10, timeout=1800):
    """Dry run unless send=True. With send=True: PAID call; needs MINIMAX_API_KEY in the environment."""
    url, headers, body = cloud_request(image, prompt, model, duration, resolution)
    if not send:
        return {"dry_run": True, "request": describe(url, headers, body), "key_present": _key() is not None}
    key = _key()
    if not key:
        raise SystemExit(f"cloud backend is opt-in: set {KEY_ENV} in the environment (never in a file of the plugin)")
    r = _call(url, key, body)
    task = r.get("task_id")
    if not task:
        raise RuntimeError(f"MiniMax refused the task: {json.dumps(r.get('base_resp', {}))[:300]}")
    t0 = time.time()
    while time.time() - t0 < timeout:
        q = _call(api_base() + "/v1/query/video_generation?" + urllib.parse.urlencode({"task_id": task}), key)
        st = q.get("status")
        if st == "Success":
            f = _call(api_base() + "/v1/files/retrieve?" + urllib.parse.urlencode({"file_id": q["file_id"]}), key)
            out = Path(out)
            out.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(f["file"]["download_url"], timeout=600) as r2:
                out.write_bytes(r2.read())
            clips.write_meta(out, kind="minimax_cloud", model=model, image=str(image), prompt=prompt, delay_frames=0,
                             seconds=round(time.time() - t0, 1), task_id=task)
            return {"dry_run": False, "out": str(out), "task_id": task}
        if st == "Fail":
            raise RuntimeError(f"MiniMax task {task} failed")
        time.sleep(poll)
    raise TimeoutError(f"MiniMax task {task} not finished after {timeout} s")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("audio", help="vocals (local H3); '-' for the cloud backend")
    ap.add_argument("prompt")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--backend", choices=["comfy", "cloud"], default="comfy")
    ap.add_argument("--frames", type=int, default=MIN_FRAMES)
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--width", type=int, default=W)
    ap.add_argument("--height", type=int, default=H)
    ap.add_argument("--song-start", type=float, default=0.0)
    ap.add_argument("--dry-run", action="store_true", help="local: print the workflow summary only")
    ap.add_argument("--cloud-model", default="MiniMax-Hailuo-02")
    ap.add_argument("--duration", type=int, default=6)
    ap.add_argument("--resolution", default="768P")
    ap.add_argument("--send", action="store_true", help="cloud: really send (PAID, image leaves the machine)")
    a = ap.parse_args()
    if a.backend == "cloud":
        if a.send and a.dry_run:
            raise SystemExit("--send and --dry-run exclude each other")
        r = cloud_render(a.image, a.prompt, a.out, a.cloud_model, a.duration, a.resolution, send=a.send)
        print(json.dumps(r, indent=1))
        return
    if a.audio == "-":
        raise SystemExit("the local H3 backend needs a vocal track")
    if a.dry_run:
        wf = workflow(Path(a.image).name, Path(a.audio).name, a.prompt, a.frames, a.seed, "dry", a.width, a.height)
        print(json.dumps({"backend": "comfy", "frames": a.frames, "seconds": round(a.frames / FPS, 2),
                          "size": f"{a.width}x{a.height}", "nodes": {k: v["class_type"] for k, v in wf.items()},
                          "estimate_s": round(42 * a.frames / FPS)}, indent=1))
        return
    print("->", render(a.image, a.audio, a.prompt, a.out, a.frames, a.seed, a.width, a.height,
                       meta={"song_start": a.song_start}))


if __name__ == "__main__":
    main()
