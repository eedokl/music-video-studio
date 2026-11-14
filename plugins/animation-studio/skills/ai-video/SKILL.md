---
name: ai-video
description: "Building block of the animation-studio plugin: local AI images and video through ComfyUI - FLUX stills, Qwen-Image-Edit start images that keep a character's identity, LTX-2.3 lip-sync and image-to-video (moving stills), Wan2.2-S2V, Wan 2.2 / LTXV image-to-video, Depth Anything depth maps, lip-sync measurement (mouth openness vs. vocals) for picking seeds and offsets, a canon colour check, contact sheets, and the unattended night run (one model at a time, resumable, milestones). Used by claudia-music-video, toon-2d and other user skills."
user-invocable: false
---

# ai-video

Everything that talks to the local ComfyUI or measures AI clips lives here, written once. User skills build
prompts and job lists; this skill computes and measures them.

Run scripts as `uv run "${CLAUDE_PLUGIN_ROOT}/skills/ai-video/scripts/<script>.py" ...` - every script declares its
own pinned packages (PEP 723 header; the mediapipe measurement scripts also pin Python 3.12) - except
`estimate_depth.py`, which runs in `gpu_python` (see below).
From another skill: `import _studio; _studio.use("ai-video")`, then `import comfy, ltx, mouth, ...`.

## Machine config (studio-core `config.py`)

| key | what | needed for |
|---|---|---|
| `comfy_url` | ComfyUI server (default `http://127.0.0.1:8188`) | all ComfyUI scripts |
| `comfy_start` | script that starts ComfyUI (e.g. a `comfyui.cmd`) - optional; without it the user is asked to start it | night_run, `comfy.ensure()` |
| `comfy_dir` | ComfyUI's base folder (holds `input/` and `output/`) - optional | night_run `--clean-comfy`, free-space check of ComfyUI's drive |
| `face_landmarker` | MediaPipe `face_landmarker.task` | mouth.py, canon.py |
| `realesrgan` | realesrgan-ncnn-vulkan executable | upscale.py (Lanczos fallback) |
| `gpu_python` | CUDA venv with torch + transformers | estimate_depth.py (falls back to uv/CPU) |
| `hf_home` | model cache | estimate_depth.py |
| `gpu_lock_dir` | shared GPU lock folder | every AI run |

Model files must be in ComfyUI's model folders (names in each script's docstring and in `references/models.md`).

## Scripts

| script | does |
|---|---|
| `comfy.py` | client: `ensure()` (starts ComfyUI via `comfy_start`), `lock(name, model)` (GPU lock + flush on a model change), `upload()` (images AND audio through `/upload`, no file-system paths), `run()`, `outputs()`, `fetch_frames()`, `free()` |
| `comfy_image.py` | FLUX.1 schnell (default) / SDXL (+LoRA, repaint) / Qwen-Image (lettering) text-to-image; `generate(prompt, out, ...)` |
| `qwen_edit.py` | Qwen-Image-Edit 2511: the person from 1-2 reference images in a new scene - start images; `edit(refs, prompt, out, ...)` |
| `ltx.py` | LTX-2.3 image+audio -> video: `render("lipsync", img, vocals, ...)` sings the given vocals; `render("moving", img, instrumental, ...)` = moving still / B-roll; `compression=` (crowds 42, `crowd_prompt()`); strips "no text" from positive prompts |
| `s2v.py` | Wan2.2-S2V: most expressive singing, 832x480 @16 fps, ~15 min per 4 s - single held notes only |
| `infinitetalk.py` | InfiniteTalk: start image + vocals, any length (chained 81-frame passes with 9 motion frames), 832x480 @25 fps |
| `upscale.py` | shared Real-ESRGAN upscaler (config `realesrgan`): `upscale_rgba` (colour + alpha separately), `upscale_image`, `upscale_video` (480p AI clips -> 720p) |
| `comfy_video.py` | Wan 2.2 TI2V 5B / LTXV 2B image-to-video without sound (backgrounds, weather) |
| `estimate_depth.py` | Depth Anything V2 Small depth maps (`run([images])` from any interpreter, runs in `gpu_python`) |
| `clips.py` | clip conventions: `<clip>.json` (song_start, fps, delay_frames, lead_in, clip_start, tempo ...), `frame_index()` = the ONE placement rule, `ltx_fit()`/`s2v_frames()` lengths, `cut_audio()`, `quiet_start()`, `prepare_vocal()` |
| `mouth.py` | lip measurement: mouth openness (MediaPipe 13/14 over 78/308) vs vocal curve (Rhubarb / level / mix / both), r for lags -6..+6, `rating()` for seed selection; `motion_check()` hidden cut / frozen / motion; `fit_placement()` entry frame + tempo for clips without own sound |
| `cvio.py` | unicode-safe OpenCV file access: `imread`/`imwrite` (np.fromfile + imdecode / imencode + tofile), `video_capture` (non-ASCII paths on Windows) - use instead of `cv2.imread/imwrite/VideoCapture` |
| `canon.py` | accent colour on the right side of the face (e.g. Claudia's streak), images and videos |
| `mic_repair.py` | repairs start images that fail the mic check (boom on both cheeks / wrong cheek): `retouch` = wrong boom + capsule masked, OpenCV fill + FLUX texture refine on the mask only (rest pixel-identical); `qwen` = Qwen-Edit "change only the microphone" (several seeds); every result re-checked with canon.py, before/after sheet |
| `humo.py` | HuMo 1.7B (17B refused on 16 GB): start image + vocals -> singing clip, 832x480 @25 fps, ~130 s per second; rescue for plosive lines, face static (`--dry-run`) |
| `minimax.py` | MiniMax: `comfy` = local H3 with audio anchor (>= 124 frames, 1024x576 @24 fps, ~42 s per second); `cloud` = hosted Hailuo image-to-video (no audio), opt-in via env `MINIMAX_API_KEY`, dry run unless `--send` (paid) |
| `night_run.py` | unattended run of a jobs.json: phases = one model each, GPU lock per phase, resume, retry after `/free`, hooks between phases (picks), `milestones.log`, `--dry-run` estimate; outputs written under a temp name and renamed when complete; `--min-free-gb`, `--clean-comfy` |
| `sheets.py` | contact sheets: `sheet()` start/middle/end per clip with notes; `shot_sheet()` 20/50/80 % per shot of a film |

## Rules (learned the hard way)

- **One model at a time** (16 GB VRAM, 48 GB RAM): every run goes through the GPU lock; `comfy.lock()` flushes
  ComfyUI on a model change; the night run flushes at every phase start. HuMo 17B does not fit 16 GB. Never kill
  other processes and never delete a lock.
- **LTX prompts:** never "no text" in the positive prompt (garbled letters) - text/letters/logos only negative; one
  light/look sentence matching the start image in every prompt, or LTX jumps to another scene.
- **LTX timing:** clips start 0.25 s before the shot (sluggish start is cut away); the LTX picture runs ~1 frame
  early (`delay_frames = 1`); keep clips <= 121 frames (RAM). The placement rule is `clips.frame_index()`.
- **Seeds vary a lot:** render 2-4 seeds per sung shot, measure (`mouth.py`), reject clips whose mouth stays closed
  (range < 0.1), apply the measured lag: lag > 0 = mouth late -> show the clip dt = +lag/24 s later.
- **Measurement depends on the vocal curve:** Rhubarb on separated vocals fails in loud choruses (choir, bleed) -
  use `--curve mix` (Rhubarb + loudness) there. Faces in profile are not measurable.
- **Mic canon:** Qwen-Edit draws a second headset boom in about half the variants - `canon.py` rejects them,
  `mic_repair.py` repairs the best one (retouch first; Qwen-Edit alone failed on some images in the reference V5 run).
- **Cloud models are opt-in:** keys only from environment variables, never printed or stored; dry run by default.
- **Label AI content** in every film (LTX-2 Community License; plugin rule).

Models, timings and the comparison of lip-sync models: `references/models.md`.
Night-run job format and the selection hand-off: `references/night-run.md`.
