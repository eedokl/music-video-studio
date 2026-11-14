---
name: video-review
description: "Compare two or more versions of a finished video with the same timeline shot by shot – side by side, synced, sound from one – pick the better version per shot and cut a new version from the picks without re-rendering (frames are copied from the chosen version, the audio is copied unchanged). Use this whenever the user has several takes/versions/renders of the same film (V1/V2, old vs. new render, two AI-video passes, a re-rendered section) and wants to choose between them, mix the best shots, see \"what changed\", or asks for \"a V3 from the best of both\" – for films from any skill of this plugin or any other video with a shared timeline. Also the reference check when a film is rebuilt after a reference film: effect checklist + dense side-by-side strips at every event moment (ref_check.py)."
---

# Video review – pick per shot, cut without re-rendering

Works for any film whose versions share one timeline (same fps, same shot boundaries – e.g. two renders of a
song project, an AI-video pass redone for some shots, a film before/after a fix). Different frame sizes are fine
(scaled to the size of the audio version).

**Building blocks** (shared code + docs of this plugin, not skills - read the one you need):
`${CLAUDE_PLUGIN_ROOT}/skills/<block>/BLOCK.md` for `studio-core`, `song-analysis`, `toon-2d`, `characters`, `voice`, `ai-video`, `bricks-3d`, `film-finish`. In those files
`<plugin>` stands for `${CLAUDE_PLUGIN_ROOT}`. First use on a machine: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py" --setup` (finds the programs).

## Workflow

1. **Interview (short).** Which files are the versions (2–9)? Which version's sound should the new cut use (usually
   the newest mix)? Which version fills shots nobody picks (default)? Where do the shot boundaries come from?
2. **Create the review** (writes `review.json` + empty `choice.json`, measures per shot how different the versions are):
   ```
   uv run "${CLAUDE_PLUGIN_ROOT}/skills/video-review/scripts/review.py" init \
       film_v1.mp4 film_v2.mp4 --labels V1 V2 --audio v2 --default v2 --name film_v3.mp4 --out review/review.json \
       (--shots shots.json | --project <song project> | --detect)
   ```
   Shot boundaries, best first:
   - `--shots shots.json` – a shot list the film was built from: `[{"start": s, "end"?: s, "nr"?: n, "label"?: text,
     "note"?: text, "info"?: {"v1": "what is in V1"}}]` (also `{"shots": [...]}`; the keys `zeile`/`line`/`text` are read
     as label, `verfahren`/`kind` as note). `--offset` subtracts a lead-in (song time → film time).
   - `--project <dir>` – the sections of a song project (`project.json`, as built by film-finish `build.py film`):
     film time = song time − first section start.
   - `--detect` – hard cuts found in the pictures of all versions (merged; shots ≥ 0.5 s). Tested: finds every listed
     cut; also splits at fast flashes inside a shot (harmless – one more pick).
   Optional `--previews a_small.mp4 b_small.mp4` (lighter browser copies) or later `review.py proxies review.json`
   (writes 960-px copies with a keyframe every 0.5 s – recommended for 4K or very high bitrates).
3. **Review in the browser:** `python "${CLAUDE_PLUGIN_ROOT}/skills/video-review/scripts/review.py" serve review/review.json`
   (standard library only; port 0 = a free port, the URL is printed – give it to the user). The page shows all versions
   side by side, synced to the sound version, looping the current shot:
   `1`…`9` or a click picks a version, `Space` play/pause, `↑↓`/`←→` change shot, `R` restart the shot, `S` switch
   the sound source; "only differing shots" hides shots that are identical in all versions (difference < 1.5/255),
   "next shot after a pick" auto-advances. Every pick is saved at once to `choice.json`. **Cut new version** runs the
   cut in the background and shows the result under the players.
4. **Cut without the page** (same result, bit-identical video stream):
   `uv run "${CLAUDE_PLUGIN_ROOT}/skills/video-review/scripts/review.py" cut review/review.json [--small] [--choice other.json]`
   → `<name>.mp4` (x264 crf 18, or NVENC with `PREVIEW=1`), `<name>.log` (version per shot, frame counts),
   with `--small` (or `"small": true` in review.json) also `<name>_small.mp4` < 29 MB (film-finish two-pass encoder).
5. **Check:** compare the log with the picks; `media.py sheet` for a contact sheet; play the cut once with sound.

## Reference check – rebuilding a known film (`scripts/ref_check.py`)

When a film is REBUILT after a reference (a plugin test, a remake, a new version that must keep every effect), stills
every few seconds and SSIM averages are not enough: they miss behaviour between the stills (a caption box left empty
while a figure breaks out, a narrator inset that stays after its singer stopped, a gag that never reached the film).
Hand-made reference scripts hide effects in a few lines of a scene script, so counting SCRIPTS misses them too.

1. **Effect checklist** (`checklist.json`) – from the reference CODE (grep every scene script for what it draws and
   the conditions/timings) and from WATCHING the reference: one entry per visible element with when it appears AND
   when / why it disappears: `{"id": "inset-lia", "what": "Lia narrator inset, bottom left", "appear": 74.5,
   "disappear": 99.9, "rule": "only while Lia narrates; gone when Tim sings"}`.
2. **Moments** – `ref_check.py events <song project>` lists section starts, line starts and every trigger word of
   gags / screen events / steam / sounds / props / badges / transitions.
3. **Dense strips** – `ref_check.py sheets --ref ref.mp4 --mine film.mp4 --events events.json --checklist
   checklist.json [--offset ref-minus-film s]`: per moment frames at -0.5 / 0 / +0.5 / +1.0 s (checklist: ±0.25 s
   around appear and disappear), reference above, rebuild below -> `refcheck/report.md`, worst SSIM first.
4. **Look at every strip** and fill in the status column (ok / different / missing + what). Fix, rebuild, re-run.
   A low SSIM is only a pointer; a high SSIM does not prove an effect is there – the status column decides.

## How the cut works (`scripts/pick_cut.py`)

All versions are decoded in lock-step as raw YUV 4:2:0 (no colour conversion, so no brightness shift), every output
frame is copied from the version picked for its shot, the result is encoded once; the audio of the sound version is
stream-copied (`-shortest`). A shot starting at `t` owns every frame `f` with `f / fps ≥ t − 1e-6`. Shots without a
pick come from `default`. The length is the shortest version.

`pick_cut(versions, segments, audio, out)` is a plain function (stdlib + ffmpeg) – other skills can import it with
`_studio.use("video-review")` to assemble a film from per-shot alternatives. If a second user skill needs it,
move it to film-finish.

## Files

- `review.json` – title, fps, size, versions `[{id, label, file, preview?}]`, `audio`, `default`, `out`, `shots`
  (`nr, start, end, label, note, info, diff, same`), `same_threshold` (default 1.5). Paths relative to the file.
- `choice.json` – `{"choice": {"<shot nr>": "<version id>"}}`. The older `{"wahl": {"3": 2}}` with 1-based
  indices is read too.
- Server API (for scripting or tests): `GET /api/review`, `GET|POST /api/choice`, `GET /film/<id>` (HTTP Range),
  `GET /film/cut`, `POST /api/cut`, `GET /api/cut` (status + log).

## Quality bar

- Never re-render to mix versions – the frames already exist.
- Sound comes from ONE version, untouched; never cross-fade audio between versions (different mixes drift).
- Versions must share the timeline; `init` warns when lengths differ by more than 1 s – then fix the edit first.

See `references/reference-tests.md` for the test against the user's own "Europe 2031" V3.
