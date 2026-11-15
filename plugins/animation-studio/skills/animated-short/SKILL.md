---
name: animated-short
description: "Make short classical 2D cartoon scenes and animation exercises without a song - a bouncing ball, a flour sack, a take, Pip finding a flower, Fips chirping, a multiplane move through a painted forest, a 2.5D flight into a comic page, or any gag with the bundled or the user's own figures - as editable Synfig scenes rendered to MP4/GIF with sound and the film look. Use whenever the user wants an animated clip, a character doing something (jump, walk, react, land), an exercise of the 12 principles, or asks to \"animate\" anything in 2D - even without saying Synfig; also to change or re-render such a scene (short.json / make_scene.py). Songs: animated-music-video; dialogue: talking-character."
---

# Animated short

A short is 3–10 seconds of acting that reads without words: one character wants something, something happens, they
react. It is built as an editable Synfig scene from Python (keyframes, not baked frames), reviewed on contact sheets,
then finished with sound effects and the standard look.

Building blocks (not skills, shared code + docs of this plugin): `toon-2d` (Synfig scenes, rigs, render, multiplane, comic flight, Blender Grease
Pencil – read its BLOCK.md and `references/animation-craft.md`), `characters` (Tim, Lia, Computer, Pip, Fips, own SVG
figures), `film-finish` (`apply_look.py`), `studio-core` (config, creative seed), `ai-video` (optional painted sets,
depth maps; takes the GPU lock).
Scripts here: `${CLAUDE_PLUGIN_ROOT}/skills/animated-short/scripts/` –
`short.py` (new / idea / variant / finish) and `sfx_track.py` (frame-exact sound effects). Run them with
`uv run "${CLAUDE_PLUGIN_ROOT}/skills/animated-short/scripts/<script>.py" ...` (each script declares its packages).

**Building blocks** (shared code + docs of this plugin, not skills - read the one you need):
`${CLAUDE_PLUGIN_ROOT}/skills/<block>/BLOCK.md` for `studio-core`, `song-analysis`, `toon-2d`, `characters`, `voice`, `ai-video`, `bricks-3d`, `stage-3d`, `film-finish`. In those files
`<plugin>` stands for `${CLAUDE_PLUGIN_ROOT}`. First use on a machine: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py" --setup` (finds the programs).

## 1. Interview (short – 3 questions at most, skip what the request already says)

- **Who?** Pip, Fips, Tim, Lia, the Computer, two of them, or the user's own figure (SVG → see `characters`).
- **What happens?** The situation in one sentence, or "surprise me". Is it an exercise of a principle (bouncing ball,
  flour sack, take, anticipation, follow-through) or a little gag?
- **Look and length?** Code-drawn background, a bundled set (`park`, `room`, `stage`), painted forest layers with a
  multiplane camera, a comic page flight, or hand-drawn Grease Pencil; 3–10 s (default ~6 s). With sound? (default
  yes, if earshot is configured).
If the request is vague, do not ask more: pick something charming and simple, and say what you picked.

## 2. Creative brief: idea + the 12 principles (before any code)

1. `short.py new <folder> --title "..." --template blank|example|figure --principles "anticipation,take,..."`
   creates `short.json` with a **seed**, the scene folder, `_toon.py` and `make_scene.py`.
2. Invent the idea from *this* request – a concrete situation with a want, a problem and a button at the end – and
   record it: `short.py idea <folder> "Fips mistakes Pip's antenna ball for a berry ..."`. User ideas:
   `--by user` (they always win).
3. Choose the principles the scene shows and where (anticipation before the big move, squash on every contact, a
   take with 3–4 frames anticipation, follow-through on antenna/tail/wings, overlap, a hold that breathes, arcs,
   exaggeration) – numbers in `toon-2d/references/animation-craft.md`.
4. Let the seed decide open choices so every short is a new take: `short.py variant <folder> exit up-left
   up-right straight-up` prints the pick and logs it (same seed → same film; another seed → another take).
   The reference scenes are techniques, not templates – never re-animate them unless the user asks for an exercise.

## 3. Beat list

Write the beats with frame ranges at 24 fps as the docstring of `make_scene.py` (the `blank` template has the
skeleton): establish (0–24), want/notice with pupils leading (24–60), anticipation + action / problem (60–96),
reaction + button + a hold with a blink (96–end). Mark which beats are keyframed and which are baked (springs,
falling objects, contacts). Show the beat list to the user in one short block before building when they are around.

## 4. Build

- Start from the template that fits: `example` (Pip and the Flower – code-drawn character, flower, sparkles),
  `figure` (an SVG figure rigged with `wrap=`, park set), `blank` (Pip from `characters/pip_figure.py` on a code-drawn
  meadow). Keep one key list per animated value at the top; feed simulations from the same lists.
- Characters: `pip(...)` for Pip (antenna spring, `antenna_kicks` for hits), `figures.load("fips"|"tim"|"lia"|svg)` +
  `around(...)` for SVG figures, `computer(...)` for the Computer. Two characters touching: hold the carrier, bake the
  contact per frame (craft reference, "Contact").
- Sets: `sets.set_layers("park")` etc., `paint_clearing.py --seed <short seed>` for a painted forest, or code-drawn
  backgrounds (gradient sky clipped, hills as big circles, light and desaturated behind saturated characters).
- Camera: zoom with `canvas(view=...)` so the characters fill about a third of the frame height.
- Multiplane / comic / Grease Pencil variants: see the `toon-2d` BLOCK.md (render the character with transparent
  background and put it on the same depth as its ground layer).

## 5. Contact-sheet review (the checkpoint – always)

`uv run <toon-2d>/scripts/render.py scene.sif --contact <key frames> --jobs 6` –
choose the frames of the key poses from the beat list (contacts, extremes of anticipation and take, the button).
Open `contact.png` (tiles are labelled with frame numbers) and check, fixing keys before polishing:
- silhouettes read; nobody cut off by the frame; characters big enough;
- squash on every contact, stretch before/after; no sliding feet; contacts really touch (zoom by cropping frames);
- the take reads (eyes 1.25–1.35, mouth "O"), pupils lead, holds breathe and blink;
- the idea and every seed pick are visible on the sheet.
Show the sheet to the user and ask for changes before finishing when they are around.

## 6. Finish

`short.py finish` checks short.json first (studio-core `project_check.py`; exit code 2 on wrong types, unknown keys warn).

1. Sound effects: write `sfx_cues.json` in the scene folder – one cue per action frame (landings → `ui_pop/soft`,
   jumps → `swish/*`, discoveries/magic → `mallet/celesta|glock`, big impacts → `whoosh_big/thump_airy`), see
   `scripts/sfx_track.py`. The peak of each sound lands exactly on its frame.
2. `short.py finish <folder> --sif scene.sif --contact <key frames> --jobs 6` renders, adds the sound track, applies
   the standard look **once** (paper + grain + vignette, `film-finish/apply_look.py`; `--no-look` to skip) and writes
   `final/<name>.mp4`, `final/<name>.gif`, `final/contact.png`.
3. Hand over: the MP4 / GIF, the contact sheet, the editable `.sif` (open in Synfig Studio) and say which parts are
   keyframes and which are baked; mention the seed and the ideas from `short.json`.

## Exercises and reference scenes

Key numbers and how to build each one (bouncing ball, flour sack, take, Pip and the Flower, Fips chirps, the
Lichtung multiplane scene, the 2.5D comic flight, Grease Pencil Pip): `references/exercises.md`.
How the skill was tested against the original projects: `references/reference-tests.md`.
