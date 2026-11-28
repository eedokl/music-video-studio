# Local AI models: what to use for what (measured on an RTX 5060 Ti 16 GB, 48 GB RAM, ComfyUI 0.43)

| job | model | time | notes |
|---|---|---|---|
| still / B-roll | FLUX.1 schnell fp8 | ~9 s per 1280x720 image, load ~2.5 min | invents lettering now and then (screens, boards) - check sheets, use variant 2 |
| lettering in the image | Qwen-Image 2512 fp8 | ~3x FLUX | correct text; reloads ~28 GB per image on machines with 16 GB RAM |
| character start image | Qwen-Image-Edit 2511 fp8 Lightning (4 steps) | ~20-30 s, load ~9 min cold | two refs (face + identity close-up) hold the canon best; one ref + short identity for wide shots |
| character start image / picture edit, **test only** | Qwen-Image 2.1 int8 + Turbo LoRA, 8 steps (`qwen21.py`) | ~15-25 s, load ~2 min | Qwen Research License: research and evaluation only. Comparison below |
| sung shot (default) | LTX-2.3 22B distilled fp8, ia2v, one stage 1280x704 | ~150 s per 97 frames warm, load ~7 min | sharpest; mouth a bit tame; fast syllables good (r 0.92 in a test), plosives weak |
| held note / climax | Wan2.2-S2V 14B fp8, 20 steps, 832x480 @16 fps | ~11-18 min per 4 s | most expressive mouth; drifts to profile and misses words on runs > 4 s |
| long sung passage (12 s) | InfiniteTalk (480p, 4 chained parts) | ~19 min per 12 s | most even lip hits over long takes, holds the face (`infinitetalk.py`, chained passes) |
| a cut inside one sung passage (6-8 s) | LTX-2.5 distilled GGUF Q4_K_M, one stage 1280x704 (`ltx25.py`) | ~295 s per 8 s, ~39 GB RAM | experimental, set by hand: frontal medium shot or closer after the cut, 3+ seeds (1 of 10 takes usable in the tests); see `multishot.md` |
| B-roll motion / moving still | LTX-2.3 ia2v with the instrumental | ~110-150 s per clip | real motion instead of Ken Burns; music gives rhythm; crowds: img_compression 42 + "A cinematic scene of" |
| background motion without sound | Wan 2.2 TI2V 5B | ~400 s per 4 s | do not animate characters with it |
| rescue: plosive-heavy line where LTX measures ~0 | HuMo 1.7B (`humo.py`) or MiniMax H3 local (`minimax.py`) | ~130 s / ~42 s per second of video | rejected as default (static face / robotic body) but kept as rescue engines next to an LTX seed; H3 renders >= 124 frames; H3 licence excludes the EU (see below) - HuMo first |
| repair a start image with two mics | `mic_repair.py`: OpenCV fill + FLUX schnell masked refine, else Qwen-Image-Edit | ~10 s (+ model load) | only the masked pixels change in the retouch; canon.py re-check |
| smeared small face in a wide take | LTX-2.3 + Lightricks pixel spatial upscaler IC-LoRA x2 on the face crop, start-image face as anchor (`face_pass.py`) | ~1.6 s per frame (4-6 min per 7-s take) | only the face ellipse changes; LTX-2.5 does not help (same encoder); KEEP / per-frame FLUX detailer / low-denoise v2v compared and weaker |
| depth for parallax | Depth Anything V2 Small | ~1 s per image | Apache-2.0; Base/Large are non-commercial |

Rejected as default (user decision, lip-sync comparison 2026-11-12; HuMo 1.7B and H3 have wrappers as rescue engines): LatentSync and MuseTalk (not usable for singing),
HuMo 1.7B (face too static), HuMo 17B (does not fit 16 GB VRAM: 81 min per step), MiniMax H3 (good lips, robotic
rest, licence excludes the EU - see below), Kandinsky 6 Lite (~40 min per clip, poor B-roll).

MiniMax H3 licence (read 2026-11-28, LICENSE in MiniMaxAI/MiniMax-H3, "MiniMax H3 Community License", dated
2026-08-02): the grant is limited to the "Applicable Territory" = worldwide WITHOUT the EU, the UK, South Korea and
the USA; clause V.4 forbids using the weights "or any of their Outputs" outside it. Commercial use above 20 million
USD yearly revenue needs a separate authorization. So in the EU the local H3 weights (FL2VA and Ref2VA) are not
licensed, test clips included: do not put local H3 takes into a published film. The hosted API was not checked.

MiniMax H3 Ref2VA test (2026-11-28, `experiments/26_h3_ref2va`, node MiniMaxH3ReferenceToVideo, files
diffusion_models/minimax_h3_ref2va_pruned_int8_convrot + loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16; no
start image, two canon reference images + vocals as <Audio 1>, prompt in the six-section format of
docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md; shot s04 "Europe sagt: Wir prüfen das noch.", 124 frames, 1024x576,
seed 31, one seed only, judged from 16-frame strips):
| take | time | r Rhubarb | r loudness (whole clip / while audio runs) | by eye |
|---|---|---|---|---|
| FL2VA Turbo 8 steps (start image) | 242 s | 0.37 | 0.02 / -0.02 | set and figure exact, head and body nearly frozen, keeps mouthing after the vocals end |
| Ref2VA Turbo 4 steps | 158 s | 0.38 | 0.48 / 0.26 | posterised, over-sharpened, dark streak artefacts in the background - not usable |
| Ref2VA full 20 steps (no LoRA) | 570 s | 0.36 | 0.47 / 0.21 | photographic and clean; bob, star clip, one headset on the correct cheek hold; head tilts, eyes move, mouth closes after the line; shoulders still; streak drawn as a wide double streak |
Reading: the robotic body was partly a Turbo/FL2VA effect, reference sheets work without a start image, lip sync is
not better than FL2VA. Not pursued because of the licence.

Lip-sync comparison (r = mouth vs vocals, best lag +-3; A fast syllables / B plosives / C held call):
LTX-2.3 0.92 / -0.03 / -, S2V - / - / 0.53, InfiniteTalk 0.90 / 0.20 / 0.58, HuMo 17B 0.39 / 0.22 / 0.55,
HuMo 1.7B 0.78 / 0.55 / 0.64, MiniMax H3 0.64 / 0.49 / 0.37.
No model closes the lips reliably on short p/b/m sounds.

Qwen-Image-Edit 2511 against Qwen-Image 2.1 Turbo (838 pictures, 230 shots from eight films, 2026-11-28): 2.1 keeps
the person - a stranger's face in 3 of 227 pictures (2511: 32 of 226), one headset on the right cheek in 28 of 29
(2511: 11 of 28), no stranger in 21 wide shots (2511: 10), three people in one picture all recognisable - and it edits
a finished picture more exactly (mic on/off, outfit, background, night: only what was asked changes). 2511 has the
stronger light and colour, more acting and gestures, real profiles and high/low angles, and it really moves the camera
in a finished picture (2.1 leaves the picture almost as it is; the multiple-angles LoRA moves it most but loses the
face). 2.1 with four to seven references paints the person several times - one sheet per person, three references at
most. The bf16 file, the base model with 20-25 steps, cfg 3, 2K, a reference resolution of 1536 and `<image1>` tags
gave no visible gain.

Licences: Qwen-Image 2.1 (model, Turbo LoRA, Comfy-Org files): Qwen Research License - research and evaluation only,
commercial use needs a licence from Qwen; do not use it for a film that is published or sold. LTX-2 Community License (free under USD 10M revenue, AI content must be labelled); Wan, Qwen-Image 2512 and
Qwen-Image-Edit 2511, FLUX schnell, Depth Anything Small: Apache-2.0.

Exact file names, models/ folders and node classes of every workflow: `assets/models.json` (machine override: config
`comfy_models`); `scripts/preflight.py` checks a running ComfyUI against them.
