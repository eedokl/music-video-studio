# Local AI models: what to use for what (measured on an RTX 5060 Ti 16 GB, 48 GB RAM, ComfyUI 0.43)

| job | model | time | notes |
|---|---|---|---|
| still / B-roll | FLUX.1 schnell fp8 | ~9 s per 1280x720 image, load ~2.5 min | invents lettering now and then (screens, boards) - check sheets, use variant 2 |
| lettering in the image | Qwen-Image 2512 fp8 | ~3x FLUX | correct text; reloads ~28 GB per image on 16 GB RAM machines |
| character start image | Qwen-Image-Edit 2511 fp8 Lightning (4 steps) | ~20-30 s, load ~9 min cold | two refs (face + identity close-up) hold the canon best; one ref + short identity for wide shots |
| sung shot (default) | LTX-2.3 22B distilled fp8, ia2v, one stage 1280x704 | ~150 s per 97 frames warm, load ~7 min | sharpest; mouth a bit tame; fast syllables good (r 0.92 in a test), plosives weak |
| held note / climax | Wan2.2-S2V 14B fp8, 20 steps, 832x480 @16 fps | ~11-18 min per 4 s | most expressive mouth; drifts to profile and misses words on runs > 4 s |
| long sung passage (12 s) | InfiniteTalk (480p, 4 chained parts) | ~19 min per 12 s | most even lip hits over long takes, holds the face (`infinitetalk.py`, chained passes) |
| B-roll motion / moving still | LTX-2.3 ia2v with the instrumental | ~110-150 s per clip | real motion instead of Ken Burns; music gives rhythm; crowds: img_compression 42 + "A cinematic scene of" |
| background motion without sound | Wan 2.2 TI2V 5B | ~400 s per 4 s | do not animate characters with it |
| rescue: plosive-heavy line where LTX measures ~0 | HuMo 1.7B (`humo.py`) or MiniMax H3 local (`minimax.py`) | ~130 s / ~42 s per second of video | rejected as default (static face / robotic body) but kept as rescue engines next to an LTX seed; H3 renders >= 124 frames |
| repair a start image with two mics | `mic_repair.py`: OpenCV fill + FLUX schnell masked refine, else Qwen-Image-Edit | ~10 s (+ model load) | only the masked pixels change in the retouch; canon.py re-check |
| depth for parallax | Depth Anything V2 Small | ~1 s per image | Apache-2.0; Base/Large are non-commercial |

Rejected as default (user decision, lip-sync comparison 2026-11-12; HuMo 1.7B and H3 have wrappers as rescue engines): LatentSync and MuseTalk (not usable for singing),
HuMo 1.7B (face too static), HuMo 17B (does not fit 16 GB VRAM: 81 min per step), MiniMax H3 (good lips, robotic
rest, licence unchecked), Kandinsky 6 Lite (~40 min per clip, poor B-roll).

Lip-sync comparison (r = mouth vs vocals, best lag +-3; A fast syllables / B plosives / C held call):
LTX-2.3 0.92 / -0.03 / -, S2V - / - / 0.53, InfiniteTalk 0.90 / 0.20 / 0.58, HuMo 17B 0.39 / 0.22 / 0.55,
HuMo 1.7B 0.78 / 0.55 / 0.64, MiniMax H3 0.64 / 0.49 / 0.37.
No model closes the lips reliably on short p/b/m sounds.

Licences: LTX-2 Community License (free under USD 10M revenue, AI content must be labelled); Wan, Qwen, FLUX
schnell, Depth Anything Small: Apache-2.0.
