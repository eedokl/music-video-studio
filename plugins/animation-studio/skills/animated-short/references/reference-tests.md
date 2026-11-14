# Reference tests (2026-11-13)

Scratch folder of the test run: `experiments/plugin-tests/animated-short/` in the animation workspace (outside the
plugin; the reference projects were only read). Every rebuild followed only the plugin's SKILL.md files
(animated-short → toon-2d → characters) and was compared frame by frame with
`toon-2d/scripts/compare_frames.py <reference frames> <rebuild frames> --frames <key frames>` (sheet: reference |
rebuild | difference ×4, plus the mean absolute difference 0–255 and the share of pixels differing by > 24 levels).

| Test | Reference project | Built with | Frames (ref / plugin) | Result |
|---|---|---|---|---|
| Pip and the Flower, example | `experiments/04_synfig_scene` (pip_flower.mp4) | `short.py new --template example`, `render.py` | 145 / 145 | identical at f0,15,36,52,74,97,109,118,140 (mean 0.00; f52: 0.03 – antenna spring rounding) |
| Pip and the Flower, rebuild with `characters/pip_figure.py` | same | `pip(...)` + set/flower/sparkles of the example | 145 / 145 | identical (same numbers) |
| Fips chirps | `scenes/fips` | template `figure`, `figures.load("fips")`, set `park` | 121 / 121 | identical at 12 key frames (mean 0.00) |
| Forest clearing layers | `scenes/lichtung/layers` | `paint_clearing.py --seed 7` | 6 / 6 PNGs | identical |
| 2.5D comic flight | `scenes/comic_25d` (comic.mp4) | `paint_clearing.py`, `comic_page.py`, `render_multiplane.py --page comic25d` | 277 / 277 | mean 0.15 (GPU rounding), changed 0.01 %; all 15 panel/page images identical |
| Multiplane camera | `scenes/lichtung` (multiplane.mp4) | `render_multiplane.py multiplane.json` | 151 / 151 | mean 0.16, changed 0.00 % |
| Grease Pencil Pip | `experiments/11_blender` (still_36.png) | `blender_run.py assets/blender_gp_example.py` | still 36 | identical |
| Krita layer assembly | `scenes/lichtung/lichtung.kra` workflow | `krita_assemble.py krita_set.json` | – | 6 layers → .kra + 2 exports in 41 s, no dialogs |

Durations and keyframe timing are equal by construction (same key lists; frame counts above). Inputs not produced by
the plugin: the three Pip-with-leaf renders used inside the comic panels (from the Lichtung scene) were provided as
art (`comic_25d/input/`), as a user would bring their own panel art.

Fresh idea (creative seed): "The Perch" (`fresh_perch/`, seed 7003): Fips lands on Pip, pecks his antenna ball,
flees straight up; Pip shrugs. Seed picks: exit straight-up, peck sound `ui_pop/blip`, ending shrug-and-blink.
157 frames, 7 sound effects placed on their frames, standard look; `final/perch.mp4` decodes without errors.

Sheets: `cmp_pip_example.png`, `cmp_pip_rebuild.png`, `cmp_fips.png`, `cmp_comic.png`, `cmp_multiplane.png`,
`cmp_blender_still36.png`, `figure_sheet_clean/figure_sheet.png`, `fresh_perch/final/contact.png`.

Re-run: build each test as above, then compare at the listed frames; anything above mean 2 / changed 2 % means the
plugin changed behaviour.
