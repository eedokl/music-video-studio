# Shaders – making looks and transition masks

[Shaders](https://shaders.com/) (npm `shaders` 4.0.6, MIT) is a WebGPU effect library with ~200 effects
(generators, filters, transitions). film-finish uses it only to MAKE things that are then stored as plain frames:

- the **standard look** (`assets/look/standard`: 24 JPG overlay frames, multiplied over the film by `apply_look.py`)
  was rendered with it – re-rendering it with `shaders_render.py` gives bit-identical frames;
- **new looks** (a dream sequence, a flashback) and **iris masks** for transitions.

It is optional. Builds never depend on it: the look ships as frames, and the iris transition has a numpy twin.

## Setup (once, only with the user's OK)

The package is not bundled. `shaders_render.py --install` prints what it downloads (shaders@4.0.6 + typegpu,
typed-binary, tinyest, tsover-runtime, ~40 MB) and runs `npm install` into the folder of the config key `shaders`
(default `~/.animation-studio/shaders`; set with `check_tools.py --set shaders=DIR` or env `SHADERS`). Needs Node.js
(config `node`) and Edge or Chrome with WebGPU (config `browser`, fallback `chrome`).

## Jobs

```
python shaders_render.py look --preset dream.json --name dream        # -> assets/look/dream/  (apply_look.py --look dream)
python shaders_render.py look --preset dream.json --out <project>/looks/dream   # project folder (apply_look.py --look <folder>)
python shaders_render.py iris --out masks --center 0.3,0.25 --frames 12 --direction close   [--numpy]
python shaders_render.py gallery --image scenes/intro/f.0100.png --out gallery [--effects my_effects.json]
python shaders_render.py catalog --out catalog                         # full catalogue of the installed version
```

Run with `uv run --no-project --with numpy --with pillow python "${CLAUDE_PLUGIN_ROOT}/skills/film-finish/scripts/shaders_render.py" ...`.

- **look**: a preset in `look.json` format: `{"components": [...], "frames": 24, "description": "..."}`. The first
  component is normally a white `SolidColor`; everything else darkens/tints it, because the overlay is
  *multiplied* over the film (white = unchanged). Output: `mp_0000.jpg ...` (quality 92) + `look.json`;
  `--keep-png` keeps the lossless frames. ~30 s for 24 frames.
- **iris**: masks `m_0000.png ...` (white = picture visible). `close` goes from 1/N to fully closed (last frame
  black), `open` the reverse, smoothstep easing. Centre 0..1 from the top-left. In Python:
  `shaders_render.iris_masks(center, frames, size)` returns float32 arrays HxW (0..1) – the optional mask provider
  of the `iris` transition in `transitions.py` (`"shaders": true` on the transition). Cached per argument set.
- **gallery**: one picture through 16 film-relevant effects → `g_NN_<Effect>.png` + labelled sheet
  `gallery.png`. Use it with the user to choose a style. `--effects` takes `[["Name", [components]], ...]`;
  `"$IMAGE"` in a component is replaced by the picture.
- **catalog**: `make_catalog.mjs` writes `catalog.json` + `shaders-catalog.md` (every effect, its role, props with
  defaults and ranges, our film rating). Regenerate it after a package update – never hand-edit prop lists.

## Effects that fit films

| Effect | Use | Notes |
|---|---|---|
| **Paper** | paper texture of the standard look | `roughness` 0.55, `grainScale` 1.2, `displacement` 0 on an overlay (displacement shifts pixels – only on pictures) |
| **FilmGrain** | animated grain | **`bias: 0`** on a white overlay – the default 2 puts grain only into dark areas, so it is invisible on white; `animated: true` + frame-locked time = 24 different grain frames |
| **Vignette** | darker, warm edges | `color` a dark brown (#2b1d14), not black; `radius` 0.78, `intensity` 0.55 in the standard look |
| **Halation** / FilmStock `halation` | red glow around highlights, like film | FilmStock also has 10 measured stock LUTs (`stock`) and gate `weave` |
| **FilmStock** | colour of an analog stock | strong – for a flashback, not the whole film |
| **LightLeak** | warm light bleeding in from an edge | `intensity` 0.15–0.45; good for memories, an opening or an ending |
| **Watercolor** | painterly flattening + pigment edges | dream sequences; makes line art softer – check faces |
| **Halftone** | print dots | comic-book or newspaper flashback |
| **Engraving**, Crosshatch | copper-plate lines | old-story / legend inserts |
| **Duotone**, GradientMap, Posterize | strong colour reductions | music-video breaks, stylised inserts |
| **Scratches** | worn film | with FilmStock + strong grain for an "old reel" |

Transitions (all have `progress` 0..1, `feather`, most `invert`): **IrisWipe** (circle to/from a point – the
classical cartoon ending), **RadialWipe** (clock-hand sweep), **PagePeel** (page curls from a corner: `corner`,
`amount`), **BarnDoors** (split from a centre line). A wipe is a *filter with a child*: the picture goes into
`children`, the background under it. For transitions in a film prefer masks rendered once (like `iris`) over live
effects, and keep them 6–14 frames.

## Strong styles for flashbacks and dreams

Make them as a look (`look` job) and apply them to the section only, e.g.
`{"components": [{"type": "SolidColor", "props": {"color": "#ffffff"}}, {"type": "Paper", ...},
{"type": "FilmGrain", "props": {"strength": 0.5, "bias": 0, "animated": true}},
{"type": "Vignette", "props": {"color": "#3a2410", "radius": 0.6, "intensity": 0.8}}]}` for an old memory.
Effects that need the picture itself (Watercolor, Halftone, Engraving, FilmStock) cannot be an overlay – render
the section's frames through them with a custom job (`ImageTexture` + effect, as the gallery does) or ask before
building such a pass.

## Pitfalls (built into the tool)

- The npm package expects a bundler: the page sets `window.process = {env: {NODE_ENV: 'production'}}`.
- The library sizes its canvas from the parent: html/body exactly 1280x720, browser `--window-size=1280,720
  --force-device-scale-factor=1`, `--enable-unsafe-webgpu`.
- `renderFrame({deltaSeconds: 1/24})` makes time frame-locked (deterministic). A preset change shows only from the
  NEXT rendered frame – the page renders once with `deltaSeconds: 0` after each `updatePreset`.
- Output is sRGB-encoded (blending in linear light): the numpy iris twin applies the same encoding.
- The browser is stopped by its own temporary profile folder – other browser windows are never touched.
