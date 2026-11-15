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

**Always render the whole film in `draft` first** (timing, acting, lip sync and cuts only show in motion), watch
it, and only then start the film quality.
