# Multiplane camera and 2.5D comic flight (render_multiplane.py)

Both run three.js (bundled in `scripts/multiplane/vendor`, MIT) in headless Edge/Chrome, served by a tiny node
server (`scripts/multiplane/server.mjs`); every frame is saved as `mp_NNNN.png`. GPU (ANGLE/D3D11) by default,
`--software` = SwiftShader (only without a usable GPU; ~3x slower). A watchdog aborts after `--startup` seconds
(default 60) without a new frame, or as soon as the page logs `ERROR` (e.g. a missing image), and prints the page URL
to open in a normal browser. Headless Edge hands off to child processes; the script stops only the processes of its
own temporary profile. If renders get slow, look for leftover `msedge --headless` processes of *your* runs.
Git Bash may rewrite `/_mp/...` arguments – use `--page multiplane|comic25d` (names, no slash).

## Multiplane camera (`--page multiplane`, default)

1. Background layers as PNGs (Krita, `paint_clearing.py`, AI stills cut into layers).
2. The animated part alone with transparent background: a scene variant without background images and without
   camera groups (Synfig renders alpha) → `frames/<name>.%04d.png`.
3. `multiplane.json` in the scene folder (paths relative to it; list = back to front):
   ```json
   {"fps": 24, "end": 150, "fov": 30, "overscan": 1.13, "out": "frames_mp",
    "planes": [{"src": "layers/01_sky.png", "dist": 120},
               {"src": "layers/05_meadow_path.png", "dist": 26},
               {"src": "frames/hero.%04d.png", "dist": 26, "sequence": true, "start": 0, "last": 150},
               {"src": "layers/04_light_rays.png", "dist": 22, "blend": "add"},
               {"src": "layers/06_foreground.png", "dist": 9, "overscan": 1.36}],
    "camera": [{"frame": 0, "x": -1.2, "y": 0.25, "z": 0},
               {"frame": 150, "x": 0.4, "y": -0.3, "z": 4.5}]}
   ```
   Put the character on the **same `dist` as its ground layer** (listed after it) so feet never slide.
   Camera `z` = dolly in (positive = closer); optional `pan`/`tilt` in degrees; each segment eases in/out
   (`"ease": "linear"` on the later key switches that off). Plane keys: `opacity`, `x`, `y`, `blend: "add"`.
4. `render_multiplane.py <scene>/multiplane.json --gif` → `multiplane.mp4`, `contact_mp.png`. Check the sheet for
   visible layer edges.

**Overscan:** each plane is scaled to fill the frame from the start position × overscan, which also zooms the
composition. Use the minimum that hides edges: for a camera offset `|x|` and a plane at distance `d`, need
`overscan ≥ 1 + |x| / (d · 0.476)` (16:9, fov 30); near planes need the most. Better: paint layers wider.

The same depth math works in Blender: camera `sensor_fit = "VERTICAL"`, `angle = fov` (see blender_gp_example.py).

## 2.5D comic flight (`--page comic25d`)

A comic page is a card with transparent panel windows; behind each window its scene stands as a diorama, visible
only through that window (stencil). Per panel either **layers** at depths (multiplane, best quality) or a **relief**
from a flat image + grayscale depth map (white = near).

- Page PNG (`comic_page.page(...)`): paper, title, ink frames; panel areas fully transparent (alpha 0).
- Layer images use the panel's aspect ratio (`comic_page.crop_aspect`, `figure_closeup` for character close-ups).
- Speech bubbles (`comic_page.bubble`) are flat layers just behind the window (depth ≈ 0.4) so they stay crisp.
- `comic.json`:
  ```json
  {"width": 1280, "height": 720, "fps": 24, "end": 276, "fov": 30, "out": "frames_comic", "background": "#2f2621",
   "page": {"src": "page.png", "px_per_unit": 100},
   "panels": [{"id": "p1", "rect": [50, 140, 1140, 560], "layers": [{"src": "p1_sky.png", "depth": 18}, ...]},
              {"id": "p3", "rect": [635, 730, 555, 560],
               "relief": {"src": "p3_color.png", "depthmap": "p3_depth.png", "base": 4.0, "amount": 3.0, "segments": 220},
               "layers": [{"src": "p3_bubble.png", "depth": 0.4}]}],
   "camera": [{"frame": 0, "view": "page", "dist": 1.0}, {"frame": 78, "view": "p1", "push": 0.0},
              {"frame": 98, "view": "p1", "push": 0.5, "dx": -0.6}, {"frame": 276, "view": "page", "dist": 1.0}]}
  ```
  `rect` = [x, y, w, h] in page px; layer `depth` in page units behind the page (panel width ≈ 5–11 units, useful
  depths 0.4–18); `blend: "add"` for light; `overscan` per layer. Camera keys: `view` "page" or a panel id,
  `dist` (page), `push` (0 = panel fills the frame, 0.5 = closer, negative = further), `dx`/`dy` (sideways, in 10 %
  of the panel size). Segments ease in/out.
- **Relief from any flat artwork:** `_studio.use("ai-video")` → `estimate_depth.py panel.png` → `panel_depth.png`
  (Depth Anything V2 Small, GPU lock). Keep `--edgefix 7`: without it ink outlines smear into streaks at figure
  edges during camera moves. Automatic relief + edgefix comes close to hand-separated layers for gentle moves; for
  strong push-ins or sideways moves past a figure, separated layers look cleaner. For own art you can build the depth
  map from the known layers (bright = near; soft shadows kept flat).
- **Comic on a desk** (optional): `"desk": ["#4a3524", "#1a120c"]` (wood + lamp light behind the page; the grain is
  seeded by `"seed"`), `"lift_height": 0.45` (the panel the camera is on lifts off the page with overshoot, dark
  hole + shadow; a key with `"lift": false` stays flat), `"overscan": 1.3` for tilted views. Camera keys take
  `pitch`/`yaw`/`roll` in degrees (camera circles the target): overview ~30° pitch + a few degrees roll, panels
  ~8–10°, swoop over the page (page key with `dx`/`dy`, `dist` 0.5) between distant panels. Halve very deep layers
  (> 6) when tilting.
- **Parallax rule for tilted views:** seen from above (pitch > 0) deep layers slide UP behind the top window edge,
  from below (pitch < 0) DOWN behind the bottom edge. Content at the bottom of a panel (labels) → look from above;
  content at the top (a head) → look from below.
- Text that must stay readable (captions, lyrics) belongs in a fixed screen overlay composited after the flight
  (film-finish overlays), not inside the panels – pushes and drifts crop panel edges.
- Speed: 277 frames in ~21 s on the GPU (frames are saved in the background while the next one renders).

## A figure breaks out of the comic (breakout.py)

From the reference film "Prompts!" (verse 2: Tim climbs out of the token sea, flips forward, dances, then hangs on
marionette strings). Any figure, any panel:

1. Put the figure into its panel as its **own layer** (a PNG of the rig – rest pose or a variant with props; a crop
   from `figure_closeup` works). It may be cut by the panel edge, the water line or a foreground layer.
2. `breakout.json` next to the comic config (all keys: docstring of `breakout.py`):
   ```json
   {"comic": "comic.json", "panel": "p2", "layer": "p2_lia.png", "figure": "lia",
    "start": 120, "end": 280, "fit": "kopf",
    "song": {"start_t": 33.0, "project": "../song", "figure": "lia", "sing_from_t": 39.2},
    "phases": [{"action": "climb", "to": 134, "cut": "auto", "size": 560},
               {"action": "crouch", "to": 139},
               {"action": "jump", "to": 147, "target": [980, 760], "size": 520, "height": 180},
               {"action": "land", "to": 154}, {"action": "dance", "to": 230, "sway": 14},
               {"action": "wave", "to": 280}],
    "splash": {"kind": "drops", "count": 12, "color": "#9be07a"}}
   ```
   Times: flight frames (`to`) or song seconds (`to_t`, needs `song.start_t` = song time of flight frame 0).
   Vocabulary: `climb` (pulls itself up, follows the panel, cut below `cut`), `crouch`, `jump`/`flip` (arc to
   `target` = feet point in px; `scale` = clip px → screen px or `size` = figure height in px; `turns`), `land`,
   `shake` (wet dog), `dance` / `marionette` (on the song's beats, else `bpm`; `strings`), `wave`, `hold`.
   Each phase may set `mouth`; from `sing_from_t` on the mouths come from the song's `assignment.json`
   (`song.figure` = the figure's name there). A beak (`schnabel_unten`) opens instead of a mouth, wings stand in
   for arms (`rig` overrides part ids).
3. `uv run breakout.py breakout.json --jobs 6`
   Steps `flight,track,clip,compose` (rerun single steps with `--steps compose`, quick look `--range 620-700`).
   Existing flight frames are reused; work files (track.json, clip.sif, clip/, rest.png) in `breakout_work/`.

Tuning:
- The rig's head is fitted into the tracked difference (`fit`, default `kopf`; `all` = whole rest pose), so the
  paper figure starts exactly on top of the painted one. If the panel shows a close-up, give `climb` a `size`
  (standing height in px) or a `scale_factor` (< 1 = smaller, scaled about the head) – otherwise the stand-up is huge.
- `follow: true` (default) keeps the stand-up attached to the panel while the camera still moves; the reference
  used fixed screen positions (`follow: false`).
- The jump target should be in front of the panel the camera goes to next; keep the figure big (feet below the
  frame edge is fine) – it now lives on the screen, the flight continues behind it.
- Style: `rim` (white cut edge, px at clip size), `edge_color`/`edge_offset` (cardboard edge), `shadow` (opacity),
  `lift` [before, after the jump] (shadow offset = height above the page).
- Text overlays (caption boxes, insets) go on top afterwards (film-finish) – the break-out output is a flight.

## A 2D figure turns into a 3D toon figure (figure_3d.py)

From the "Prompts!" credits gag (Lia becomes round part by part, turns once and pops). Generic for any rig SVG:
- Every filled shape is inflated (round cross-section from the distance to its outline: circle → sphere, arm →
  tube; `depth` 0.8 = a bit flatter than round, `part_depth` per part id). Strokes without fill become tubes;
  fills under 30 % opacity (glasses) are skipped. A shape lying ≥ 90 % on a much bigger earlier shape (eyes,
  pupils, cheeks, the mouth) hugs its surface as a thin decal (`decal_depth`). Stacking follows the drawing order,
  so the front view equals the drawing; the flat start state is the drawing in painter order.
- Toon material (2 tones, hard edge) + ink outline (inverted hull, thickness = stroke width / 2 × `outline`).
- Framing: `px_per_svg_px` + `feet_screen` = where the SVG feet point lands; `flat_2d.png` is the Inkscape export in
  exactly this framing (with the same default mouth) – the crossfade input.
- Actions: `morph` (`order` bottom_up | top_down | list of ids, `last` ids or fill colours, `spin`, `lift`),
  `turn` (`degrees`, `lift` in units of 100 SVG px), `pop`, `hold` (`flat: true` flattens back).
- `figure_3d.py crossfade --flat <out>/flat_2d.png --frames3d <out> --out <dir> --fade 6` lays the drawing over the
  first frames, fading out. The `.blend` is saved for an artist.
- Hair drawn as a cap on the front of the head: list its id or fill colour in `"wrap"` so it also covers the back
  (as far as the drawing covers the head – a short cap leaves the lower back of the head in skin colour).
- Tested: Lia with the credits timing vs the hand-built reference, silhouette IoU 0.85 on average (0.72 at the side
  view); Tim and Fips with no per-figure code.
- Limits: shapes are inflated one by one, so a headset band or a hat brim stays a tube *on* the surface (not around
  the head); parts behind the body (hair) become a thick slab behind it; hands/feet are as round as they are drawn.
