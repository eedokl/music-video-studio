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

## A film on a song (2026-11-21)

Reference project: the rap video "LGTM" in the animation workspace (21 clips, 5,542 frames, 76 lyric lines, three
MCs and a robot) - built before `film3d.py song` existed, with a hand-written timing script and a project module of
time helpers, from which `song_film.py` and stage-3d `stage_song.py` were made. The project itself was not changed.

| Test | Built with | Compared | Result |
|---|---|---|---|
| the bridge | scratch film folder; `song --draft` on the project's song analysis, then the project's clip list, performers, word fixes and `"show"` written into `song_plan.json`; `film3d.py song` | against the project's hand-made `timing.json` (clips, frames, beats, bars; per line: performer, shown text, start, end, every word time) and a vocal slice byte by byte | 21 clips and 76 lines equal, 0 differ; the slice is identical |
| timing repair | the same run without the hand fix of line 4 | the first word the recognition heard at 17.33 s (the line starts at 25.4 s) | moved by itself to 25.12 s (set by ear: 25.25 s); the two spoken outro lines were reported as starting 0.2 / 0.5 s before the voice |
| plan draft | `song --draft` (target 9 s) | against the clip list the film was made with | 22 clips; 7 of the 21 hand-set cuts hit exactly, 10 within half a second - a start to edit, not the edit |
| render estimate | `stage_run.py status` on the project (104 of 5,542 film frames, nothing measured) | the measured 1.4-3.6 s/frame of its first clips | "about 2.5 h (rough)" - inside the measured 2-5.5 h |
| mail preview | `encode.py film_draft.mp4 --mail` on a copy of the project's preview | size, decode check | 11.9 MB, 0 decode errors, 14 s |

Not covered: the scenes of the reference film still use the project's own helper module, not `stage_song.py`
(same code, moved); `stage_song.sing` / `groove` inside Blender are only covered by the e2e test
`animated-3d-film-stage-song`; `preview --mail` was not run through a whole preview.
