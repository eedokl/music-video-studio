<!-- Building block of the animation-studio plugin - a reference document, NOT a skill (it is not loaded
     into every session). User skills point here. `<plugin>` = the plugin folder, the path that
     the variable CLAUDE_PLUGIN_ROOT stands for in the SKILL.md files. -->
# bricks-3d – brick films in Blender (building block)

*Brick films in Blender from the open LDraw parts library - own LDraw importer (no stud logos), minifigure rig with poses, printed faces with 9 lip-sync mouth shapes and blinks as shader decals, brick sets (room, stage, rooftop, house exterior with fly-in, arena, cloud auction) with anchors, brick effects (sets building themselves, flying brick lettering, confetti, towers, figures falling apart, steam puffs, marionette strings), name signs on torsos, stop-motion timing on twos with jitter, beat bounce, cameo silhouettes, props (coins, glowing GPU, talking monitor, spots), per-shot auto exposure and headless EEVEE rendering to scenes/<section>/f.%04d.png. Used by bricks-music-video; not called by the user directly.*

Everything a brick-film skill needs inside Blender, driven by a **plan JSON** (data, editable by hand). The user skill
(e.g. `bricks-music-video/scripts/plan.py`) writes the plan; this skill turns it into frames.

## Setup (once per machine)
- Blender 4.2+ (tested 5.2 LTS): config key `blender` (`check_tools.py --setup` finds it).
- LDraw parts library: config key **`ldraw_dir`** – see [references/ldraw-setup.md](references/ldraw-setup.md).
- Check: `python "<plugin>/skills/bricks-3d/scripts/blender_run.py" --check`

## Scripts
| script | runs in | what |
|---|---|---|
| `blender_run.py <script> -- <args>` | Python | Blender headless with the shared GPU lock (`bricks_blender`); `--check` |
| `brickfilm.py -- <plan.json> --render \| --stills 10,200 \| --blend` | Blender | the film runner: set, figures, mouths, poses, camera, exposure, frames |
| `textures.py <dir> --screens screens.json --signs signs.json` | uv + pillow | face atlases (eyes 2 tiles, mouths 9 tiles X A–H), torso prints, name signs (white label + LEDs, neutral lettering), hair clip, skyline, monitor screens |
| `ldraw.py` | Blender | LDraw importer (`part(name, colour, matrix)`, quality switches gaps/bevel/wobble/abs, `T/RX/RY/RZ`) |
| `minifig.py` | Blender | rig: `build`, `pose(F, angles)` (head, arm_r/l, hand_r/l, leg_r/l) |
| `shading.py` | Blender | decals (`face`, `front_print`, `hair_accent`), glow, image planes, lights, `Timeline`, `make_constant` |
| `sets.py` / `layouts.py` | Blender / pure Python | sets and their anchors: room, stage, rooftop, house (night exterior + room behind the window, camera flight path), arena (podium, stands, chip mountain), cloud (auction above the clouds); palettes, moods, mirror |
| `effects.py` | Blender | stop-motion brick effects: set builds itself / flies apart, word of flying bricks (can collapse), confetti, growing tower, figure falls apart / assembles, steam puffs from a head or a point, marionette strings (puppeteer hands → target heads, follow the poses) |
| `assets/cast.json` | data | minifig looks: tim, lia (Claudia canon), silhouette, robot, rocker, singer |

Plan format: docstring of `brickfilm.py`. Coordinates are LDraw units (1 LDU = 0.4 mm, floor y = 0, up = −y,
front = −z); a minifig's neck is 72 LDU above its feet, the face at y ≈ −84.

## Techniques that matter (learned on the reference film, details in [references/techniques.md](references/techniques.md))
- **Stop motion:** figures, props and lights keyed on twos (12 poses/s) with a slight per-pose jitter; mouths and
  blinks on ones; every key CONSTANT. Figures dip on each beat (bounce).
- **Lip sync:** mouth tile = Rhubarb shape from `song-analysis` `assignment.json` (X A B C D E F G H) on every frame.
  The monitor "computer" speaks with the same shapes on its screen face.
- **Sharp figures:** real-scale macro → depth of field is huge; use f/22 (medium/close) to f/32 (wide).
- **Light:** no area light closer than ~10 cm to a face (burns white/pink under AgX); EEVEE shadow rays 3 / steps 12
  against sparkle; spot cones visible only at their rim (Layer Weight) so figures do not look milky.
- **Exposure:** measured per shot from small test renders (night target 0.40, only darker), smoothed so cuts in the
  same light do not jump; cached in the project (`cache/exposure_<section>.json`, `--remeasure` to redo).
- **No logos, own characters:** the LDraw stud has no logo; never call the film a "LEGO" film; companies only as
  neutral lettering.
- Cameo figures (e.g. the anonymous silhouette with a white grin) slide in at the set's `outside` anchor.
- Coins: a stack can start full (`times` = section start) and vanish (`gone` per coin) – all at once or one per beat.
- Name signs replace the look's torso print (`sign_tex` in the plan figure); strings are thin emissive cylinders keyed
  per pose (object keys, so they stay CONSTANT like everything else); steam puffs start 34 LDU above the head origin
  (= the head top) and rise 80 LDU in 0.9 s while they grow.
- Brick effects are seeded (same seed, same flight paths) and keyed on twos like the figures; a shot may carry a
  `path` (camera and aim polylines, one eased flight) – the house intro flies through the garden into the window.

## Speed
EEVEE at 1280×720, 32 samples: ~0.4–0.6 s per frame on an RTX-class GPU (scene build ~20 s, exposure measuring
~3 renders per shot). Drafts: `--percent 50 --samples 16`. `--cycles` = path tracing (~5 s/frame, overnight).
