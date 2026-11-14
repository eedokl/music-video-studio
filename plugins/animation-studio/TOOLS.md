# Tools and models

Everything the plugin's skills call, what it is used for, and what we recommend. Programs are found through
`studio-core/scripts/check_tools.py` (environment variable `ANIMATION_STUDIO_<KEY>` – plain `FFMPEG`, `SYNFIG`,
`HF_HOME` ... only for the unambiguous keys listed in `config.py` → `~/.animation-studio/config.json` → PATH);
nothing is installed without asking the user. Reference machine: Windows 11, Intel i5-14600K, 16 GB RAM, NVIDIA RTX 5060 Ti
16 GB – timings below are from that machine.

Legend: **required** – the plugin does not work without it · **recommended** – used by default when present ·
**optional** – only for specific skills or techniques · **not recommended** – tested and rejected.

## Core programs

| Tool | Version tested | Used for | Skills | Status |
|---|---|---|---|---|
| uv (Astral) | current | runs every script in its own Python env, pulls Python packages on demand | all | required |
| ffmpeg with libx264 (e.g. the one shipped with Kdenlive) | 8.x | decoding, cutting, mixing, encoding, decode checks | all | required |
| Synfig Studio / synfig CLI | 1.5.5 | 2D scenes as editable `.sif` keyframe files, rendered headless | animated-music-video, animated-short, talking-character, animated-powerpoint | required for 2D |
| Inkscape | 1.4 | SVG characters → paths for the Synfig rig | 2D skills | required for 2D |
| Rhubarb Lip Sync | 1.14 | mouth shapes (9 Preston-Blair shapes) from vocals or speech, language independent (`-r phonetic`) | all with singing/speaking figures | required |
| Blender | 5.2 LTS | brick films (EEVEE), 3D gags, Grease Pencil hand-drawn look | bricks-music-video, toon-2d (optional) | required for bricks |
| Node.js + npm, headless Chrome / Edge | Node 20+, chrome-headless-shell (Puppeteer) | three.js lyric videos (Vite + TypeScript project per video, `npm install` per project), multiplane camera, 2.5D comic flight and the slide stage rendered frame by frame | lyric-music-video, toon-2d, animated-powerpoint | required for those |
| Shaders (npm `shaders` 4.0.6, MIT, WebGPU in headless Edge/Chrome) | 4.0.6 | made the standard look (paper + grain + vignette, re-render bit-identical) and the iris transition masks; new looks, effect gallery, effect catalogue (`film-finish/scripts/shaders_render.py`, `--install` after the user agreed, ~40 MB into the `shaders` config folder) | film-finish | optional – only for new looks/transitions |
| Microsoft PowerPoint (COM, read-only) or PyMuPDF | – | importing decks: slide images, picture positions, crops, group transforms (PDF/images also work) | animated-powerpoint | recommended for .pptx |
| Krita (kritarunner) | 5.x | painted sets as layered `.kra` files the user can paint over | toon-2d | optional |
| Kdenlive with MLT `melt` + OpenTimelineIO (Python package) | Kdenlive 26.08, melt 7.x, otio 0.17 | hand-off of the finished cut for manual editing: `film.otio` (Kdenlive 25.04+ / DaVinci Resolve import) and `film.mlt` (written by melt, plays with `melt film.mlt`) – `film-finish/edit_handoff.py`; the plugin's own film build uses ffmpeg, melt is only needed for the .mlt | film-finish (optional) | optional |
| earshot (CLAP-based "ears") | 0.4 | who sings (male/female per 0.5 s), loudness/timeline check, 252-sound effect bank | song-analysis, film-finish | recommended |
| ComfyUI | 0.43 | runs the image and video models below on the local GPU | ai-video, claudia-music-video, painted panels | required for AI video |
| LDraw parts library | current | brick geometry for the own Blender importer | bricks-3d | required for bricks |
| LeoCAD (knowledge only) | – | the minifig rig uses the joint positions of LeoCAD's minifig wizard; LeoCAD itself is not called | bricks-3d | not needed |
| Puppeteer `@puppeteer/browsers` (npx) | current | downloads chrome-headless-shell for the lyric-video render – only after the user agreed (`INSTALL_BROWSER=1`); an installed Edge/Chrome works too | lyric-music-video | optional |

## AI models (all local)

| Model | Size / precision | Used for | Measured | Status |
|---|---|---|---|---|
| Whisper large-v3 (faster-whisper) | GPU float16 | words with times, lyric alignment; VAD retry for sung choruses | 4-min song ≈ 1.5 min on GPU | recommended (GPU) |
| Whisper small (faster-whisper) | CPU int8 | fallback without GPU | 59 % vs 66 % words recognised (large-v3) on a song | fallback |
| Demucs htdemucs | GPU or CPU | vocal separation when no stems exist | 4-min song 27 s GPU / ~2 min CPU | recommended |
| Suno stems (Vocals, Backing Vocals) | – | best source for lip sync and call-and-response | – | recommended when available |
| FLUX.1 schnell fp8 (Apache 2.0) | 4 steps | painted backgrounds, comic panels, props, start images | ~7 s per image after loading | recommended (default image model) |
| Qwen-Image-Edit 2511 fp8 Lightning (4 steps) | ComfyUI | consistent character start images (Claudia canon) from 1–2 references (`ai-video/qwen_edit.py`) | ~30 s per image, load ~9 min cold; draws two headset mics in about half the variants → `canon.py` mic check, `mic_repair.py` repair | recommended for claudia |
| Qwen-Image 2512 fp8 (+ Qwen2.5-VL 7B text encoder) | ComfyUI | lettering that must be correct inside an image (`comfy_image.py --model qwen`) | ~3× FLUX; reloads ~28 GB per image on 16 GB RAM | optional |
| SDXL Base 1.0 | ComfyUI | style LoRAs, negative prompts, img2img repaint (`comfy_image.py --model sdxl [--lora ...] [--repaint]`) | ~28 steps | optional (the watercolour repaint look itself was rejected, see below) |
| LTX-2.3 22B distilled fp8 + Gemma-3 12B text encoder | ComfyUI | lip-sync video from start image + vocals (audio frozen via latent mask); image-to-video for B-roll | lip score r 0.92 on fast syllables, best image quality, 1280×704 | recommended (default video model) |
| LTX-Video 2B 0.9.8 distilled (+ T5-XXL fp8) | ComfyUI | fast image-to-video previews without sound (`comfy_video.py ltx`) | 8 steps, 1216×704 | optional |
| Wan 2.2 TI2V 5B (+ umt5-xxl fp8, Wan 2.2 VAE) | ComfyUI, Apache 2.0 | image-to-video without sound for backgrounds, weather, light (`comfy_video.py wan`); older Wan clips with a mouth are re-placed by mouth curve (`mouth.py fit`) | ~400 s per 4 s | optional |
| Wan2.2-S2V 14B fp8 (+ wav2vec2 large) | ComfyUI | expressive close-ups, single held emotional notes < 4.7 s (`ai-video/s2v.py`, claudia `plan.py --s2v` / `"engine": "s2v"`) | ~14–15 min per 61 frames @16 fps; plugin re-shoot of two reference shots: r 0.51 (reference 0.39) and 0.45 (reference 0.53) | optional, default off |
| InfiniteTalk (Wan2.1-I2V-14B 480p fp8 + InfiniteTalk patch + LightX2V LoRA, wav2vec2-chinese-base, umt5-xxl) | ComfyUI, Apache 2.0 | held notes and long sung passages; keeps the start image most faithfully (`ai-video/infinitetalk.py`, chained 81-frame passes for long takes; claudia `"engine": "infinitetalk"`) | r 0.90 / 0.20 / 0.58 in the model comparison, ~80 s per second, 832×480 @25 fps (upscale: `upscale.py`) | optional |
| HuMo 1.7B | ComfyUI, Apache 2.0 | rescue run for plosive-heavy lines where LTX fails (`ai-video/humo.py`, claudia `"engine": "humo"` = HuMo clip + 1 LTX seed) | most even sync (0.78 / 0.55 / 0.64), identity less stable; user found the face too static | optional, rescue only |
| MiniMax H3 | ComfyUI | alternative audio-anchored lip sync, local weights (`ai-video/minimax.py`, claudia `"engine": "minimax"`) | 0.64 / 0.49 / 0.37; licence unchecked; user found the rest of the body robotic | optional, rescue only |
| Depth Anything V2 Small (`depth-anything/Depth-Anything-V2-Small-hf`; Large optional via `--model large`) | GPU (gpu_python), CPU fallback | depth maps that turn a flat painting or FLUX panel into a relief for the 2.5D comic flight and multiplane camera; depth for Claudia start images (`ai-video/estimate_depth.py`, used by toon-2d, animated-music-video comic verses, claudia-music-video) | 0.2 s per image on GPU (Large 0.3 s) | recommended |
| MediaPipe FaceLandmarker | CPU | mouth-openness measurement for choosing lip-sync takes | – | required for claudia selection |
| Real-ESRGAN (ncnn-vulkan; x4plus-anime for drawn art, x4plus for photos/video) | GPU, config `realesrgan` | shared upscaler `ai-video/upscale.py`: panels before depth estimation, figures, 480p AI clips (S2V, InfiniteTalk) to 720p; colour and alpha separately | 61-frame S2V clip 832×480 → 1280×720 in seconds | optional (Lanczos fallback) |
| RIFE (ncnn-vulkan) | GPU | 48 fps interpolation in camera moves | needs `-g 0` and RGB input | optional |
| Qwen3-TTS 12Hz 1.7B VoiceDesign + Base | GPU venv (`tts_python`), ~4 GB each | VoiceDesign makes a reference voice per character from an English description; Base speaks every line in that voice, seeded; Whisper scores each take (retake below 0.8) – no voice-actor clones | Whisper 0.97–1.0 per line in the dialogue test | recommended for voices |
| Piper (e.g. de_DE-thorsten-high) | CPU | fast lightweight TTS fallback | – | optional |
| MiniMax Hailuo video API (cloud) | API, `MINIMAX_API_KEY` (env only) | image-to-video B-roll without audio (`ai-video/minimax.py --backend cloud`); dry run unless `--send` (paid, image leaves the machine) | not run (no paid call made) | optional, opt-in |
| ElevenLabs (cloud) | API, `ELEVENLABS_API_KEY` | optional voice engine per figure (opt-in, line text leaves the machine, costs credits); also usable for sound effects such as a laugh (Sound Effects) | – | optional |
| Windows System.Speech (SSML) | – | last fallback voice; works without GPU | the Pip rebuild uses it (pitch ×1.23) | fallback |
| HuMo 17B fp8 | – | – | does not fit 16 GB VRAM: 81 min per step, aborted | not recommended (on 16 GB) |
| Kandinsky 6 Lite | – | – | ~40 min per 5-s clip, B-roll not better than LTX | not recommended |
| Wan 2.1 I2V 14B + LightX2V (crowd test) | – | crowd shots in claudia-live `publikum_test.py` (test B) | lost to LTX-2.3 with img_compression 42 + "A cinematic scene of" (now `ltx.py` crowd recipe) | not recommended for crowds |
| MuseTalk 1.5, LatentSync 1.6 | – | first lip-sync tests on Wan clips (tools/lipsync/musetalk, latentsync; claudia-video-trial lipsync_test 01–04) | not usable for singing | not recommended |
| SDXL + watercolour LoRA repaint | – | painted look over FLUX | rejected by the user | not recommended |

## Python packages (pulled by uv on demand, pinned in each script's PEP 723 header)

numpy, pillow, svgelements, librosa, soxr, faster-whisper, matplotlib, opencv-python-headless, mediapipe, scipy,
scikit-image, transformers (Depth Anything),
opentimelineio, python-pptx and PyMuPDF (slides), demucs/torch (in a CUDA venv for GPU use), qwen-tts (in its own
venv). The lyric-video engine pulls three.js, Vite and TypeScript through npm per project.

## Shared resources

- **GPU lock** (`studio-core/gpu_lock.py`): one AI model at a time; 16 GB VRAM + 16 GB RAM cannot hold two big
  models. Point `gpu_lock_dir` at the same folder as any other GPU pipeline on the machine.
- **Model caches**: set `hf_home` / `torch_home` to a drive with space (models are 5–25 GB each).
- **Licences**: label AI-generated content; company names only as neutral text, no logos; Claudia is an open
  character ("Claudia by anabology").

## Tuned for the reference machine (check on yours)

These defaults come from the machine the plugin was built and measured on (Windows 11, one NVIDIA GPU with 16 GB
VRAM, 16 GB RAM, ComfyUI portable). They are not limits of the method - adjust them for your hardware:
- `ai-video/scripts/night_run.py` load and time estimates per job kind, and `LTX_MAX_FRAMES` in `ltx.py`
- `ai-video/scripts/humo.py` refuses the 17B model without `--allow-17b` (does not fit 16 GB)
- checkpoint, LoRA and custom-node names inside every ComfyUI workflow (built in the ai-video wrapper scripts such as `comfy_image.py`, `comfy_video.py`, `ltx.py`, `humo.py`) -
  they must match the files in your ComfyUI `models/` folders
- 1280x720 as the working size of the song films (`film-finish` `build.py`, `fps48.py`, `overlays.py`,
  `animated-music-video` scenes) - change all of them together
- the "16 GB VRAM / 16 GB RAM: one model at a time" rule in studio-core (the GPU lock is useful on any machine)

## Installed on the reference machine but deliberately not used by the plugin

| Tool | Why not |
|---|---|
| OpenToonz, Tahoma2D, Pencil2D | Hand-drawn / clean-up workflows; script mode and export work, but Claude-driven animation does not need them (Synfig and Blender Grease Pencil cover keyframes and hand-drawn looks). Useful if an artist cleans up frames by hand. |
| Sloom Studio | GUI only, no scripting interface. |
| Audacity | Not needed: track reading (beats, words) and the listening checks are automatic (song-analysis, earshot). |
| Godot (+ Popochiu) | Games, not films – the games reuse the plugin's figures and sets. |
| Bark (suno/bark-small) | Tried for a laugh sound effect; an ElevenLabs sound effect was preferred. |
| rembg, insightface, Animated Drawings | Experiments (background removal, face analysis, drawing-to-animation); not part of any proven pipeline. |
| YuE, ACE-Step 1.5, SoulX-Singer | Singing / song generation for parodies – audio, not video; planned as a separate "song-parody" skill outside this plugin. |
| Comfy Cloud | Not needed since ComfyUI runs locally on a 16 GB GPU. |
