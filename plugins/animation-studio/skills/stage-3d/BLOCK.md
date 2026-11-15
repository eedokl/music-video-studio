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

## Scripts
| script | runs in | what |
|---|---|---|
| `stage_run.py clip <project> <clip> --stills 1,40,90 --sheet` | uv | key frames in draft quality + labelled `out/<clip>/sheet.png` (`--every 20` = a strip through the clip, `--q film` for hero stills, `--range a b [--overwrite]` for frames, `--save` writes a .blend) |
| `stage_run.py film <project> --q draft\|film [--clips a,b]` | uv | every missing frame of every clip (resumable; holds the shared GPU lock) |
| `stage_run.py status <project> [--q film]` | uv | rendered / missing frames per clip |
| `stage_speech.py prepare\|show <project>` | uv | Rhubarb mouth cues + word times of project.json `lines` → `speech/lines.json`; `show` prints the word frames |
| `stage_film.py` | Blender | builds one clip and renders it (started by stage_run.py); writes `out/<clip>/build.json` (cuts, spoken lines with their frames) |
| `stage_core.py` | Blender | `Stage`, `Node`, channels and easing, primitives, materials, text, cameras, lights, palettes, render settings |
| `stage_actor.py` | Blender | the rig `Char` + acting API, poses, moods, lip sync, the bundled figure `Toy`, `cast()` |
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

## Known limits
- `Char.reach()` ignores the lean of the body (re-aim after a big `body=` override); a channel with a single key is
  constant before that key; `core.text` size is roughly the line height (cap height ≈ 0.4 × size).
- Speech: lip sync needs English dialogue text for Rhubarb's recogniser to be at its best; other languages still
  give usable open/close shapes.
- EEVEE is not supported (materials and lights are tuned for Cycles).
