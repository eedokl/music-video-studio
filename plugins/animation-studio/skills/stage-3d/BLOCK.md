<!-- Building block of the animation-studio plugin - a reference document, NOT a skill (it is not loaded
     into every session). User skills point here. `<plugin>` = the plugin folder, the path that
     the variable CLAUDE_PLUGIN_ROOT stands for in the SKILL.md files. -->
# stage-3d – character films in Blender, written as Python scenes (building block)

*A headless Blender (Cycles) stage for 3D character films in the look of a premium animated advertisement: own animation tracks with easing baked per frame, a soft toy rig with an acting API (poses, moods, walk, hop, look, two-bone arm IK, lip sync from Rhubarb cues), the bundled neutral figure in three looks, props and a ready-made office set with five light moods, colour palettes, camera/shot helpers with depth of field, resumable renders in a fast draft and a film quality, labelled contact sheets. Used by animated-3d-film; not called by the user directly.*

**Run a script of this block:** `uv run "<plugin>/skills/stage-3d/scripts/<script>.py" ...` - the script names in the tables below live in `<plugin>/skills/stage-3d/scripts/`; each script declares its own packages (PEP 723), so no `--with`. A script whose first line says it runs in another interpreter (Blender, gpu_python, tts_python) is started by the scripts that need it.

A film is a project folder: `project.json` (the clips in order, sizes, palette, look, spoken lines - format in
`stage_project.py`), `scenes/<clip>.py` (one Python module per clip: `FRAMES`, optional `SEED`, `build(S)`),
`speech/` (spoken lines), `out/<clip>/…` (renders). The cut with sound and look is `film-finish` `clip_film.py`.

## Setup (once per machine)
- Blender 4.2+ (tested 5.2 LTS): config key `blender`. Check: `uv run "<plugin>/skills/stage-3d/scripts/stage_run.py" check`
- A graphics card is used when Cycles finds one (OptiX, CUDA, HIP, Metal, oneAPI), otherwise the CPU (slow).
- Lip sync needs `rhubarb`; the cut needs `ffmpeg`.
- Realistic actors (`"figures": "rigify"`): a folder of `<name>/figur.blend` - per project in `actors/`, or for the
  machine config key `actors3d` (`check_tools.py --set actors3d=<folder>`).

## Scripts
| script | runs in | what |
|---|---|---|
| `stage_run.py clip <project> <clip> --stills 1,40,90 --sheet` | uv | key frames in draft quality + labelled `out/<clip>/sheet.png` (`--every 20` = a strip through the clip, `--q film` for hero stills, `--range a b [--overwrite]` for frames, `--save` writes a .blend, `--contact` measures actors' feet and hands → `out/<clip>/contact.json`) |
| `stage_run.py film <project> --q draft\|film [--clips a,b]` | uv | every missing frame of every clip (resumable; holds the shared GPU lock) |
| `stage_run.py status <project> [--q film]` | uv | rendered / missing frames per clip |
| `stage_speech.py prepare\|show <project>` | uv | Rhubarb mouth cues + word times of project.json `lines` → `speech/lines.json`; `show` prints the word frames |
| `stage_film.py` | Blender | builds one clip and renders it (started by stage_run.py); writes `out/<clip>/build.json` (cuts, spoken lines with their frames) |
| `stage_core.py` | Blender | `Stage`, `Node`, channels and easing, primitives, materials, text, cameras, lights, palettes, render settings |
| `stage_actor.py` | Blender | the rig `Char` + acting API, poses, moods, lip sync, the bundled figure `Toy`, `cast()` |
| `stage_rig.py` | Blender | realistic actors: Rigify figures (`"figures": "rigify"`, `"actors"`) with the same acting API, Rhubarb face sliders, feet planted on the floor with steps, arms kept out of furniture (`contact()` after the bake), `report()` = `--contact` |
| `stage_looks.py` | Blender | six other makes of the same figures: `ragdoll` (cloth, seams, button eyes), `puppet` (fleece, flap mouth, arm rods), `stopmotion` (gothic armature puppets: clay skin, huge eyes, stripes), `clay` (plasticine), `paper` (papercraft), `marionette` (wooden string puppets) |
| `stage_props.py` / `stage_sets.py` / `stage_shots.py` | Blender | props; the office set with light moods; `closeup`, `medium`, `two_shot`, `ots` |
| `stage_project.py` | any | `Film`: project.json, clips, frame paths, missing frames |

Qualities: **draft** (half size, 24 samples, ~0.7 s/frame on an RTX 5060 Ti - contact sheets and the whole-film
preview), preview, **film** (full size, 40 samples + OpenImageDenoise, motion blur, ~3.7 s/frame), final (128
samples, hero stills). Details and measurements: [references/render-speed.md](references/render-speed.md).

## A scene module

```python
import stage_actor as K, stage_core as C, stage_props as P, stage_sets as sets, stage_shots as shots
FRAMES = 240

def build(S):
    R = sets.office(S, mood="golden")              # or build a set from stage_props / stage_core
    cast = K.cast(S, {"mo": "bear", "kit": {"look": "cat", "glasses": True}})
    sets.seat(cast)
    mo, kit = cast["mo"], cast["kit"]
    end = mo.say("l01", 24)                         # lip sync + head accents; returns the end frame
    mo.pose(K.word_frame("l01", "build", 24), "present")
    kit.look(30, mo.face_pos(1)); kit.mood(end, "skeptic")
    S.shot(1, (0, -5.2, 1.6), (0, 0.8, 0.9), loc1=(0, -4.6, 1.5), lens=40, fstop=4)     # every shot is a cut
    shots.closeup(S, end + 2, kit)
```

World: metres, Z up. Figures are ~0.85 m tall and **face −Y at heading 0**; the camera normally stands on the −Y
side, so +X is screen right. Frames are 1..FRAMES at 24 fps (fixed). All angles are degrees.
The full API (channels and easing, `Node`, camera, every acting call, poses, moods, props) and the craft rules
(cinematography, light, acting, the working method with contact sheets) are in
[references/guide.md](references/guide.md) - **read it before writing a scene**.

## Colours and light (what makes the look)
- **Palette** - project.json `"palette"`: `"ivory"` (default: plaster walls, dark walnut, ink blue, one coral
  accent), `"petrol"`, `"forest"`, or own colours `{"base": "ivory", "accent": "#C24F2D", "rug": "#333A50"}`
  (keys: `stage_core.PALETTES`). Materials are named by role: `accent`, `accent_d`, `accent_l`, `wall_accent`,
  `wall_soft`, `paper_a`, `ceramic_a`, `coin`, `screen_a`, `glow_a`, `txt_accent`, `txt_soft`, `rug` plus the neutrals
  (`walnut`, `oak`, `floor_wood`, `paper`, `trim`, `brass`, `steel`, `black` …). The older names `green`, `green_d`,
  `wall_green`, `txt_green` … still work and mean the accent.
- **Light mood** - `sets.office(S, mood=...)`: `"golden"` (default: low warm sun raking through a window cross,
  dark room), `"dusk"` (pink sky, lamps doing the work), `"night"` (moon blue + lamps), `"dawn"`, `"day"` (bright and
  even). Give a film a light arc: the mood per clip tells the time. Own sets: `stage_sets.LIGHT` shows the values
  (key, fill, two rims, window, lamps, sun beam) to start from; `sets.sunbeam()` works in any room.
- **Keep it low-key.** White figures need a mid or dark background (the ink wainscot, wood, night blue) - never
  white on white - and a picture that is bright everywhere reads flat: one clear light direction, real shadows,
  practical lamps. Check exposure on the contact sheet; lower the lights rather than raising them.
- The finish (`film-finish` `clip_film.py`, project.json `"look"`): `"cinema"` (default: darker, warm halation,
  vignette, grain) or `"ad"` (bright and clean).

## Figures
- Bundled: `Toy` in the looks `bear`, `cat`, `bunny` (`stage_actor.LOOKS`: fur and scarf colours, ears, tail,
  `glasses`) - `K.cast(S, {"name": "bear" | {"look": "cat", "size": 0.9, "accent": "#27637A"}})`.
- An own cast: subclass `Char` in the project (`scenes/cast.py`), write `build()` from primitives hanging on the
  joints (`self.j`, `self.limb`, `self.eye`, `self.brows`, `self.mouth_cavity`, `self.glasses`; `Toy.build` is the
  model, `vest_mat` gives a knit vest with a shirt V-neck), add own moves (ears, tail) as methods, and pass the
  class: `K.cast(S, {"olga": Olga})`. Keep a figure recognisable: silhouette (ears, tail), one garment, one habit.
- Mouths: project.json `"lips": "soft"` (default) or `"strong"` (wider opening while speaking).
- **The make of the figures** - project.json `"figures"`: `"toy"` (default: the smooth felt toys as modelled),
  `"ragdoll"`, `"puppet"`, `"stopmotion"`, `"clay"`, `"paper"` or `"marionette"`. It re-dresses every figure `cast()` builds - bundled or own - and leaves the rig alone,
  so a finished film can be rendered in another make without touching a scene. One clip only: `K.cast(S, {...},
  style="puppet")`; a cast not built by `cast()`: `K.dress(S, figures)` once all figures exist.
  - `"ragdoll"`: woven linen in the fur colour, knit garments, plush tails, sewn seams with hand stitches (head,
    muzzle, torso, limbs, hands, feet), four-hole button eyes, a slightly lumpy stuffing. Costs no render time.
  - `"puppet"`: hand puppets for a puppet show - fleece with a nap of fine hair, ping-pong eyes with felt pupils, a
    hinged flap mouth with a felt tongue that hangs on the mouth channel (`say()`, `babble()` and moods open it),
    arm rods, no legs: stage them behind a playboard or a desk edge that hides them from the chest down. White
    figures get a fleece colour each (gold, rust, sage, plum ... in cast order; own: `{"look": "bear", "fleece":
    "#DA5F26"}`). The hair about doubles the render time; `"fuzz": False` in a figure's options leaves it out.
  - `"stopmotion"`: gothic stop-motion puppets of the hand-made armature kind - a big head on a narrow body,
    wire-thin limbs, huge round porcelain eyes with pin pupils in dark sockets, no brows, pale sculpted clay skin
    with thumb marks, black-and-bone striped garments and tails, a sewn mouth and a stitched skull. Costs no render
    time. It only reads in low-key light: use the `"night"` or `"dusk"` office mood (or a cold key from the side and
    one small warm light), dark walls, and keep glowing screens dim - in a bright "ad" picture it looks like a white
    toy in a striped jumper.
  - `"clay"`: plasticine - one colour per figure (white figures get green, yellow, orange, blue ... in cast order;
    own: `{"look": "bear", "clay": {"color": "#EA652B"}}`), thumb marks and finger-print ridges, clay-ball eyes and
    clay brows, garments in clay of their own colour. The closest to the toys, works in any light. No render cost.
  - `"paper"`: papercraft - every part is folded from few flat faces, with printed dashed fold lines on the creases
    and glue tabs over some edges, flat paper eyes and brows; the figures keep their colours (white stays paper
    white - give it a mid or dark background). It needs a clear light direction, or the facets disappear.
  - `"marionette"`: carved, lacquered wood with a grain, ball joints at shoulders, elbows, hips and knees, a jaw
    slot, painted red cheeks, and strings from the head and both hands to a control cross above each figure (the hand
    strings hang a little loose). The eyes stay as modelled and still blink. The cross follows the figure's place,
    not its spins: after a somersault the strings would be wound round it - avoid spins, or `{"strings": False}`.
    Leave headroom: the cross hangs about a metre above the head.
  - `"rigify"`: **realistic actors** - every part is played by a Rigify figure (`<actors>/<name>/figur.blend`, e.g.
    from the 3D figure kit; `"actors": {"mo": "tim"}` casts them). Same scenes, same acting calls; the face
    sliders take moods, blinks and Rhubarb mouth shapes; after the bake the feet are planted on the floor and step,
    and arms are moved out of desks and tables. Fits sets for ~1 m figures; see [references/guide.md](references/guide.md)
    "Realistic actors". A single actor in any make: `K.cast(S, {"tim": {"actor": "tim"}})`.
  - Limits: button, ping-pong, clay, paper and porcelain eyes do not blink or widen (moods still move the brows); a figure with a beak or
    without a modelled mouth keeps its own mouth. Details, the option keys (`cut`, `hinge`, `parts`, `eye`, `lid` ...)
    and how an own `Char` class sets them: the docstring of `stage_looks.py` and
    [references/guide.md](references/guide.md) "Other makes".

## Known limits
- Realistic actors: hands rest on a table only if the shoulders are above its top (otherwise contact moves the
  arms under or over it); fingers keep the pose of the file; walking faster than about 1 m per metre of figure
  height per second gives long running strides; the contact pass adds ~5 s per clip and actor.
- `Char.reach()` ignores the lean of the body (re-aim after a big `body=` override); a channel with a single key is
  constant before that key; `core.text` size is roughly the line height (cap height ≈ 0.4 × size).
- Speech: lip sync needs English dialogue text for Rhubarb's recogniser to be at its best; other languages still
  give usable open/close shapes.
- EEVEE is an experimental second engine (`stage_run.py ... --engine eevee`, frames in `out/<clip>/<q>_eevee/`): the
  picture comes out close to Cycles, with speckle on the edges of white figures at draft samples - but with this
  block's light Cycles settings it is not a speed-up (measured: [references/render-speed.md](references/render-speed.md)).
