# stage-3d – render speed (measured)

Measured with Blender 5.2 LTS, Cycles + OptiX on one RTX 5060 Ti 16 GB, 1920x1080 film frames of an office scene
with four figures (reference film, 5,482 frames).

| quality | size | samples | per frame | whole reference film |
|---|---|---|---|---|
| draft | 960x540 | 24, adaptive 0.08 | ~0.7 s | ~1 h |
| film | 1920x1080 | 40, adaptive 0.05, motion blur | ~3.7 s | ~5 h |

- The time is almost all sampling: fixed cost per frame (scene update, saving) ~7 %, denoising ~2 %, motion blur
  ~3 %. So faster means fewer samples or fewer pixels: 28 instead of 40 samples −26 %, 1600x900 −39 %,
  no depth of field −15 %, fast GI −14 %; fewer bounces (4/2/2) only −2 %.
- Several Blender instances on ONE graphics card gain nothing (they share it); `stage_run.py film` renders the
  clips one after another and can be stopped and resumed. More speed needs more cards.
- A GPU at ~97 % load that draws well under its power limit is normal here, not a sign of waiting.
- Building a clip (Python scene → Blender scene, baked animation) takes 0.3–3 s; it is paid once per Blender
  start, so render ranges, not single frames in a loop.

## Cycles vs. EEVEE (2026-11-15, two clips of the reference film: a stage hall and the office, 829 frames)

| | Cycles (OptiX) | EEVEE (ray tracing on) |
|---|---|---|
| draft, 960x540 | 0.44 / 0.57 s per frame (24 samples) | 0.36 / 0.45 s per frame (16 samples) |
| film, 1920x1080, motion blur | 2.4 / 3.8 s per frame (40 samples + denoiser) | 3.8 / 4.35 s per frame (64 samples, 3 motion-blur steps) |

EEVEE is about 20 % faster in draft and slower in film quality with these settings: the usual "EEVEE is many
times faster" compares it with Cycles at hundreds of samples and minutes per frame, and this block's Cycles
already runs at a few seconds. The pictures are close (same lights, colours, depth of field); EEVEE shows speckle
on the lit edges of the white figures at 16 samples and slightly different contact shadows. Not tuned further
(fewer EEVEE samples / one motion-blur step would be faster and noisier).

**Always render the whole film in `draft` first** (timing, acting, lip sync and cuts only show in motion), watch
it, and only then start the film quality.
