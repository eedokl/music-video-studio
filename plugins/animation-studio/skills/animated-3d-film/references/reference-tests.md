# Reference tests (2026-11-15)

Reference project: a 3D film of about four minutes in the animation workspace (not part of the plugin
– 12 clips, 5,482 frames at 1920x1080, rendered before this block existed with the project's own library, from
which stage-3d was made). The reference project was switched to the plugin (its `lib/` is now a thin layer over
`stage_core` / `stage_actor` / `stage_props` / `stage_sets` / `stage_shots`; the four animal figures stay in the
project as `Char` subclasses) and compared with its finished film frames.

| Test | Built with | Compared | Result |
|---|---|---|---|
| every clip, one film-quality still each (one clip: two) | `stage_run.py clip <project> <clip> --q film --stills N`, palette `forest`, office mood `day` | against `out/<clip>/film/f_####.png` of the finished render; mean absolute difference 0–255 and the worst 40x40 px block | 13 stills: mean 0.00–0.16; worst block ≤ 0.2 in 10 clips, 1.3 and 6.1 in two - no block over 8 |
| frame bookkeeping | `stage_run.py status <project> --q film` | the 12 clip folders | 5,482 / 5,482 frames found |
| spoken lines | project data converted to `speech/lines.json` | 35 lines, 13 with mouth cues (the lines spoken in the picture) | a lip-synced still equal to the film frame |

Fresh film through the user skill (scratch folder, bundled toy figures, default palette `ivory`, mood `golden`,
look `cinema`): `film3d.py new` → `clip` → `idea` → `line` → `speak --engine system` (Whisper score 1.0, word times
stored) → `preview`: 2 clips, 180 frames in draft quality in 1.5 min, one spoken line mixed on its frame,
`preview/film_draft.mp4` 7.5 s with sound, 0 decode errors. Light moods (`golden`, `dusk`, `night`, `dawn`, `day`)
and the looks `cinema` / `ad` were compared on contact sheets.

Not covered by these tests: a complete film render through `film3d.py render` (the reference film was rendered
before the move; its frames were only re-checked by sample), an own cast written from scratch with the plugin
docs alone, EEVEE.
