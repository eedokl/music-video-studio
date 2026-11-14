<!-- Building block of the animation-studio plugin - a reference document, NOT a skill (it is not loaded
     into every session). User skills point here. `<plugin>` = the plugin folder, the path that
     the variable CLAUDE_PLUGIN_ROOT stands for in the SKILL.md files. -->
# toon-2d – Synfig scenes from Python

*Classical (Disney-style) 2D animation as Synfig scenes written in Python – layer builders (sif.py), motion helpers (squash/stretch, arcs, spring follow-through), Inkscape SVG figures as rigs (svg2sif.py), lip-sync mouths (lipsync.py), painted sets, rendering to frames/MP4/GIF/labelled contact sheets (render.py, parallel Synfig), frame-by-frame comparison of two renders, the three.js multiplane camera and the 2.5D comic flight (render_multiplane.py), painterly multiplane layers without AI (paint_clearing.py), Krita layer assembly (krita_assemble.py) and Blender Grease Pencil (hand-drawn look). Used by animated-short, animated-music-video, talking-character and the other cartoon skills of the plugin.*

A scene is a Python script (`make_scene.py`) that writes a Synfig file (`.sif`, XML); Synfig renders it, ffmpeg
encodes it. The `.sif` stays editable in Synfig Studio, so an animator can take over – that is the point of going
through Synfig instead of drawing frames directly: **keyframes, not baked frames**, wherever possible.

All programs come from the machine config (`studio-core/scripts/config.py`: `synfig`, `ffmpeg`, `inkscape`,
`rhubarb`, `krita`, `blender`, `browser`, `node`); run `check_tools.py --setup` once per machine.
Scripts: `<plugin>/skills/toon-2d/scripts/` (below just `scripts/`). Run with
`uv run "<plugin>/skills/toon-2d/scripts/<script>.py" ...` (each script declares its packages in a PEP 723
header; scene folders' `make_scene.py` too).

## Files

| File | What |
|---|---|
| `scripts/new_scene.py <folder> --from blank\|example\|figure\|none` | scene folder: `_toon.py` path shim (puts toon-2d + characters scripts on `sys.path`; `import _toon` first in every scene script) + `make_scene.py` from a template |
| `scripts/sif.py` | layer builders, each returns an XML **string**: `group`, `circle`, `rect`, `region`, `outline`, `shape` (fill + ink), `ellipse`/`ellipse_pts`, `polygon_pts`, `linear_gradient`, `clipped` (layers only inside a mask), `with_blend`, `image` (PNG), `anim` (keys), `comp_vec` (separate x/y), `canvas`, colours `hexc` |
| `scripts/motion.py` | `squash_keys` (volume-preserving), `hop_y` (parabola), `approx` (evaluate keys in Python), `spring_follow` (follow-through baked to angle keys), `to_world` (local point through nested groups) |
| `scripts/svg2sif.py` | Inkscape SVG → Synfig parts with pivots: `normalize`, `load_svg`, `emit(root, wrap)` |
| `scripts/lipsync.py` | Rhubarb cues → 9 mouth drawings (X A B C D E F G H) switched by constant keys: `load_cues`, `mouth_layers` |
| `scripts/sets.py` | painted sets: `load_set(name)`, `set_layers(name)` → (back, front) image layers; bundled `stage`, `room`, `park` (`assets/sets/`) |
| `scripts/render.py scene.sif` | `.sif` → `frames/<name>.NNNN.png` → MP4 (+ `--gif`, `--contact 0,15,36` labelled sheet, `--single N`, `--audio`, `--jobs N`) |
| `scripts/synfig_parallel.py scene.sif outdir` | split the frame range over N Synfig processes (Synfig uses ~1.5 cores; 152 frames: 27 s instead of 94 s) |
| `scripts/compare_frames.py A B --frames ...` | side-by-side sheet (A \| B \| diff) + mean difference per frame – reference tests and retakes |
| `scripts/render_multiplane.py cfg.json [--page comic25d]` | three.js in headless Edge/Chrome: multiplane camera or 2.5D comic flight → frames, MP4, GIF, contact sheet |
| `scripts/comic_page.py` | comic page with transparent panel windows, speech bubbles, panel crops, flat preview |
| `scripts/breakout.py breakout.json` | a figure **breaks out of a comic panel**: flight with/without its layer, screen track from the difference, Synfig clip of the rig as a paper stand-up (cut edge, cardboard edge, shadow) that climbs out, jumps/flips forward and dances/acts in the foreground; lip sync from `assignment.json` |
| `scripts/figure_3d.py fig3d.json` | a rig SVG becomes a **rounded 3D toon figure** in Blender (inflated parts, toon shader + outline, ortho camera = the 2D framing): morph (parts round one after another), turn, pop, hold → RGBA frames; `figure_3d.py crossfade` blends the 2D drawing into them |
| `scripts/paint_clearing.py --out layers --seed N` | painterly forest-clearing layer set (6 PNGs) for multiplane – CPU only, seconds |
| `scripts/krita_assemble.py krita_set.json` | PNG layers → layered `.kra` + PNG exports, headless (artist paints over the .kra) |
| `scripts/blender_run.py script.py -- args` | run a script in headless Blender |
| `assets/example_scene.py` | **"Pip and the Flower"** – complete 6 s scene: squash/stretch rig, blinking, mouth swap, spring antenna, flower blooming with overshoot, sparkles. Read it before writing a new scene |
| `assets/templates/figure_scene.py` | an SVG figure (Fips) rigged with `wrap=`: hop, flap, head tilt, blink, beak, on the `park` set |
| `assets/templates/blank_scene.py` | beat-list docstring + background + Pip from `characters/scripts/pip_figure.py` |
| `assets/blender_gp_example.py` | Grease Pencil Pip drawn on twos with pressure + boil, painted layers at depth, camera dolly |
| `references/sif-format.md` | format gotchas, transform model, layer parameters, blend methods – read when adding a new layer type or when Synfig refuses a file |
| `references/animation-craft.md` | the 12 principles as concrete keys (frame counts, squash values, take, settle, contact) – read when planning acting |
| `references/multiplane-and-comic.md` | multiplane config, overscan, comic flight config, desk/lift, parallax rules, depth maps |
| `references/blender-grease-pencil.md` | when to choose Blender, the five Grease Pencil pitfalls |
| `references/cutout-from-raster.md` | rigging characters that must look exactly like given raster drawings |

Characters (Tim, Lia, Computer, Pip, Fips, own SVG figures, rig convention) are in the `characters` building block.

## Workflow for a scene

1. **Beats first.** Turn the idea into a beat list with frame ranges at 24 fps (`0-36 hops in`, `46-62 notices`,
   `72-86 take`) and write it as the docstring of `make_scene.py`. Short is good: 3–8 s.
2. **Scene folder.** `python "<plugin>/skills/toon-2d/scripts/new_scene.py" <folder> --from example|figure|blank`. Never write scenes into
   the plugin. The `_toon.py` shim holds no path: it finds the plugin at run time (env `CLAUDE_PLUGIN_ROOT`, else
   the machine config entry `animation_studio_root`, which new_scene.py stores and every plugin script moves to its
   own plugin folder after an update). If it cannot, it stops and says how
   to refresh (`new_scene.py <folder> --from none` keeps make_scene.py).
3. **Rig with nested groups.** `position group (offset, lean angle, base scale)` → `squash group (scale about the
   feet)` → parts. Local origin at the feet (bottom centre) so squash keeps the character on the ground and lean
   pivots at the contact point. Eyes get their own group (origin at the eye centre) for blinks; secondary parts
   (antenna, tail, wings) a group with origin at their root.
4. **One source of timing.** Key lists as Python data near the top (`Y_KEYS`, `SQ_KEYS`, `LEAN_KEYS` …), fed both
   to Synfig (`anim`) and to every simulation (`motion.approx`). Retiming = editing one list.
5. **Render and look.** `ANIMATION_STUDIO_ROOT="<plugin>" uv run make_scene.py` (passes this
   plugin version to the scene; in PowerShell: `$env:ANIMATION_STUDIO_ROOT="<plugin>"` first), then
   `uv run "<plugin>/skills/toon-2d/scripts/render.py" scene.sif --contact 0,15,36,...` (key poses; Pillow
   labels the tiles with frame numbers). Open the contact sheet with the Read tool: silhouette readable, nothing cut
   off by the frame, squash on contacts, characters big enough (zoom with `canvas(view=...)` rather than scaling
   everything). Renders take seconds – iterate. `--jobs 6` from ~100 frames on.
6. **Deliver.** MP4 + GIF + the editable `.sif`; say which parts are keyframes and which are baked simulation.
   Finishing (look, sounds, cut) is `film-finish`.

## Coordinates and conventions

- Units, not pixels. Default view `-8 4.5 8 -4.5` (16×9 units, 80 px per unit at 1280×720); y points **up**.
  Positive angles rotate counter-clockwise: a character facing right leans forward with a **negative** angle.
- Layers: the first in the list is at the **bottom**.
- Times are frames: keys `(frame, value[, interp])`; interp `"halt"` = ease in/out, `"linear"`, `"clamped"`,
  `"auto"` (TCB), `"constant"` (switches), or `(before, after)`. Whole frames only (`anim` keeps the later of two
  keys on one frame – it usually means overlapping lists).
- Colours are written with gamma 1: hex values look as specified.
- Ink outlines: `shape()` / `ellipse()` for splines; for circles stack a slightly larger dark circle under the
  coloured one.
- **Gradients fill the entire plane** and hide everything below: a bare `linear_gradient` only as the bottom-most
  sky, anywhere else `clipped("Water", rect(...), [linear_gradient(...)])`.
- Inside a group with `origin = offset = pivot`, draw children at their real (parent) coordinates.
- Mirror a figure with a negative x scale on its outer group (`V(-s, s)`); world angles stay CCW-positive.
- Single test frames: `render.py --single N` (renders the range N..N; `synfig --time` picked wrong frames).

## Lip sync (dialogue)

1. Voice as WAV (recording or TTS from the `voice` skill).
2. `rhubarb -r phonetic -f json --extendedShapes GHX -o mouth.json voice.wav` (`-r phonetic` is
   language-independent – needed for German; ~1 s for a 7 s line).
3. In the scene: `mouth_layers(load_cues("mouth.json"), FPS, center=<mouth pos in the head group>, size=0.8,
   ink=INK, offset_frames=-1)` instead of a fixed mouth (one frame early reads more in sync). Scene length =
   `mouth.json["metadata"]["duration"] * FPS`. Pip: `pip(..., mouth_cues=cues)`.
4. Act to the sound: takes/accents (squash, lean, eye changes) on stressed syllables – read the cue times.
   Swap drawings for expressions (e.g. "^ ^" joy eyes via constant `amount`) instead of squashing normal eyes.
5. `render.py scene.sif --audio voice.wav` lays the voice into the MP4.
- Mouth size ~0.8 of the head width ratio reads in a medium shot; scale `size` with the framing.
- A rig exported to PNG (comics, credits) has **no mouth** if the SVG leaves it to lip sync – keep one PNG with a
  default mouth (shape X) and one without.
- Lip-sync QA: compare voice activity per frame (`media.voice_activity`) with open mouth shapes and list gaps ≥ 0.3 s;
  fill held notes with alternating open shapes (C/B).

## Readable actions (learned the hard way)

- SVG rig arms sit behind the body (right for dancing). Actions that must read *in front* (typing, strumming,
  holding things) need their own arm layers in front of the body while the rig arm is switched off via `amount` –
  otherwise the hand "disappears behind the back".
- Show an action at the object it acts on; hands hidden below a desk edge get misread. Check every repeated pose for
  unwanted readings (details in `references/animation-craft.md`).

## Painted backgrounds

- Bundled sets (`sets.py`): `park` (blurred park path, view `-4.98 5.0 4.98 -0.6`, floor 0), `room`, `stage`.
- `paint_clearing.py --seed N`: six painterly layers of a forest clearing (sky, far trees, middle trees, light rays,
  meadow with path, dark foreground leaves), ground line at y = −3.0 units; a new seed gives a new clearing.
- AI-painted sets and stills: `_studio.use("ai-video")` → `comfy_image.py` (FLUX; one GPU job at a time via the
  shared lock). Ask for "no text"; letter real text yourself (Pillow).
- Krita: `krita_assemble.py` builds a layered `.kra` from PNG layers and exports any layer combination
  (e.g. `bg_back.png` + transparent `bg_front.png` for parallax) – the artist can paint over it and re-export with
  `--export-only`. Import PNGs into Synfig with `sif.image(desc, path, tl, br)` matching the camera view.

## Multiplane camera and 2.5D comic flight

Synfig moves layers flat; a real multiplane move (near layers slide faster, dolly through foliage) renders the
parts separately and lets three.js do the camera:
- Layers as PNGs + the animated character alone with transparent background (a scene variant without background
  layers: Synfig renders alpha) → `multiplane.json` → `render_multiplane.py multiplane.json --gif` (~13 s for
  150 frames on the GPU). Put the character on the **same `dist` as its ground layer** so the feet never slide.
- Comic flight: a page PNG with transparent panel windows (`comic_page.py`), per panel layers at depths or a relief
  from image + depth map → `comic.json` → `render_multiplane.py comic.json --page comic25d`.
- Depth maps for flat art: `_studio.use("ai-video")` → `estimate_depth.py panel.png` (Depth Anything V2, keep
  `--edgefix 7`).
- Text that must stay readable goes into a screen overlay after the flight (film-finish), not into the panels.
Config keys, overscan formula, camera angles, lift and the parallax rules: `references/multiplane-and-comic.md`.

## Break-out from the comic and 3D morph

- **Break-out** (`breakout.py`): the figure must be its own layer in a panel of the comic flight (e.g. a PNG of the rig,
  `comic_page.figure_closeup`). The script renders the clean flight itself (derived `<comic>_without_<panel>.json`),
  fits the rig's head into the tracked difference (IoU ≈ 0.85–0.93 in tests) and composes all flight frames to
  `<out>/f.NNNN.png` + MP4 + contact sheet. Config, action vocabulary and tuning: `references/multiplane-and-comic.md`.
  It also writes a **sound log** (climb bubbles, jump whoosh, landing pop, coins/drops after the landing; earshot ids,
  override with `"sounds": {...}`): `<work>/sound_log.json` and, with `"song": {"project": ...}`,
  `<project>/analysis/actions_breakout_<panel>.json`, which film-finish `sounds.py` mixes in. `--steps log` writes
  only the log (no frames).
- **3D morph** (`figure_3d.py`, Blender via the GPU lock): any rig SVG; frame 0 is flat in painter order, so the 2D
  drawing crossfades in without a jump (`flat_2d.png` is exported in the same framing). Run with
  `uv run "<plugin>/skills/toon-2d/scripts/figure_3d.py" fig3d.json`.
  Keys and limits: docstring of the script and `references/multiplane-and-comic.md` (last section).

## Blender Grease Pencil

Choose Blender over Synfig when the look should be hand-drawn (variable line weight, boil, frame-by-frame on twos)
or an artist will continue in Blender; Synfig stays better for tweened vector rigs.
`uv run "<plugin>/skills/toon-2d/scripts/blender_run.py" "<plugin>/skills/toon-2d/assets/blender_gp_example.py" -- --layers <layers> --out <dir> [--still 36]`
(96 frames ~25 s with EEVEE; `.blend` saved for the artist). Pitfalls: `references/blender-grease-pencil.md`.

## Tested (reference tests, 2026-11-13)

Rebuilt with these scripts and compared frame by frame (`compare_frames.py`): "Pip and the Flower" (example and a
rebuild with `characters/pip_figure.py`): identical, 145/145 frames; Fips (figure template): identical, 121/121; forest
clearing layers (seed 7): identical; 2.5D comic flight: 277/277 frames, mean difference 0.15/255 (GPU rounding);
multiplane camera: 151/151, 0.16/255; Grease Pencil still: identical; Krita assembly: 6 layers → .kra + 2 exports
in 41 s. Details in `animated-short/references/reference-tests.md`.
Break-out (2026-11-14, `breakout.py`): Tim's break-out from the "Prompts!" comic flight rebuilt from the original
comic inputs (both flights rendered, 1011 frames, track fit IoU 0.84): against the reference layer frames, frames
652–1010 differ by 1.6/255 on average (body keys, mouths, beats, strings identical in method), the climb-out
630–651 by 9.8/255 (reference body phases started 2–3 frames earlier); with default placement the stand-up starts
exactly on the painted head (scale 1.82 instead of the reference's hand-set 1.35). A new page (Lia waist-deep in a
meadow panel) broke out with the defaults (fit IoU 0.93). 3D morph (`figure_3d.py`): Lia with the credits timing
(52 frames) against the hand-built reference: silhouette IoU 0.85 on average (0.72 at the side view, where
the generic hair slab is deeper than the hand-made one); the 2D export and 3D frame 0 match at IoU 0.95. Tim and
Fips rendered with the same script, no per-figure code.

## Quality bar

Animation should feel alive, not mechanical: every move has anticipation, arcs, ease at extremes, squash on impact,
overshoot and settle, and something secondary (blink, breath, follow-through). If a pose looks stiff on the contact
sheet, fix the keys before polishing the background.
