# Night run: job format, phases, picks

A user skill writes `<project>/jobs.json`; `night_run.py` computes it. Paths are relative to the jobs file.

```json
{"phases": ["flux", "qwen_edit", "depth", "ltx", "s2v", "infinitetalk", "humo", "minimax_h3", "wan"],
 "selection": "selection.json",
 "hooks": {"after:qwen_edit": ["uv", "run", "${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/pick.py", "auto", "."]},
 "jobs": [
  {"id": "s02/start_v1", "kind": "qwen_edit", "out": "ai/start/s02_v1.png",
   "args": {"refs": ["face.png", "closeup.png"], "prompt": "...", "neg": "...", "seed": 4711}},
  {"id": "s02/ltx_s1", "kind": "ltx_lipsync", "out": "ai/lipsync/s02_{img}_s1.mp4",
   "args": {"image": {"pick": "start", "key": "s02", "candidates": ["ai/start/s02_v1.png", "ai/start/s02_v2.png"]},
            "audio": {"src": "analysis/vocals_lead.wav", "from": 4.33, "dur": 3.4},
            "prompt": "...", "neg": "...", "frames": 81, "seed": 4812, "strength": 1.0,
            "meta": {"song_start": 4.33, "lead_in": 0.25, "shot": "s02"}}}]}
```

| kind | model (lock name) | args |
|---|---|---|
| `flux` | comfy:flux | prompt, seed, w, h, model (flux/sdxl/qwen), neg |
| `qwen_edit` | comfy:qwen_edit | refs, prompt, neg, seed, w, h |
| `depth` | depth:small | image (path or pick) - one subprocess per phase |
| `ltx_lipsync` / `ltx_moving` | comfy:ltx23 | image, audio {src, from, dur}, prompt, neg, frames (8n+1), seed, strength, meta |
| `s2v` | comfy:wan_s2v | image, audio, prompt, frames (4n+1 @16 fps), steps, seed, light, meta |
| `infinitetalk` | comfy:infinitetalk | image, audio, prompt, frames (4n+1 @25 fps, chained passes beyond 81), seed, meta |
| `humo` | comfy:humo1.7B | image, audio, prompt, frames (4n+1 @25 fps), seed, size (1.7B; 17B is refused in the night run - does not fit 16 GB VRAM), steps, neg, meta |
| `minimax_h3` | comfy:minimax_h3 | image, audio, prompt, frames (@24 fps, >= 124: shorter shots are rendered long and cut), seed, meta |
| `wan` | comfy:wan | image, prompt, seconds, seed, neg, meta |

- **Order:** stills first, then the pick hook (canon check chooses start images), depth, then the videos - each
  model is loaded once. `{img}` in `out` is the picked image's variant tag: a new pick makes new clips, old ones stay.
- **Resume:** existing outputs are skipped; just start again after a crash. Outputs are written as
  `<name>.part.<ext>` (+ `.part.json`) and renamed when complete, so a killed job is redone, never taken as done.
  `--only s02,s05` and `--phases ltx` recompute parts; `--status` shows done/open per phase; `--dry-run` lists
  jobs with a time estimate.
- **Preflight:** before the first job night_run starts ComfyUI if needed (as a phase does) and runs `preflight.py`
  for the open jobs of the selected phases: every node class, model file and option value their workflows need
  (`assets/models.json` + the `comfy_models` override) must be offered by ComfyUI's `/object_info`. Anything missing is
  written to `milestones.log` (`preflight MISSING ...`: node class + node pack hint, or model file + loader +
  `models/` folder) and the run stops in seconds with exit code 1 - before any job, no `.part` files - instead of
  failing hours in. Fix the files / node packs or name your files in the override, then start again.
  `--no-preflight` skips the check (e.g. ComfyUI not reachable but only the depth phase should run).
- **GPU lock:** a phase whose lock stays taken too long (another session's long job) is skipped with a message;
  the run goes on with the next phase.
- **Disk:** before the run and before every phase `--min-free-gb` (default 20) must be free on the project drive
  and, with config `comfy_dir` (ComfyUI's base folder), on ComfyUI's drive; otherwise the run stops with a message.
  `--clean-comfy` (needs `comfy_dir`) deletes the files this run created in ComfyUI's `input/` and `output/` after
  each job - uploads that existed before and anything of other jobs are never touched.
- **Hooks** run after their phase also when it had nothing to do, so a new hand pick is taken up. They run in the
  jobs file's folder; `${CLAUDE_PLUGIN_ROOT}` in a hook is replaced at run time by the plugin folder of the running
  night_run.py - never write absolute plugin paths into jobs.json (they break on every plugin update).
- **ComfyUI job timeout:** the job is taken out of ComfyUI's queue (or interrupted if it is running) so later jobs
  do not queue behind a hung one.
- **Errors:** logged with traceback in `milestones.log`, one retry after `POST /free`, then the next job.
  ComfyUI not answering for 15 min -> the phase is skipped (it is started with `comfy_start` if configured).
- **Milestones:** `milestones.log` gets one line per finished job and per phase - read it in the morning.
- **Clip metadata:** every video gets `<clip>.json` (clips.py) so cutting and measuring place it identically.

## Picking (the user skill's job, with ai-video's measurements)

1. Start images: `canon.measure()` per variant -> best one with the identity detail on the right side.
2. Sung clips: `mouth.lip_score()` per seed on the shot window -> `mouth.rating()`; reject closed mouths; store
   the lag. Rhubarb curve by default, `mix` for loud choruses.
3. Contact sheets (`sheets.sheet`) with the numbers for a look by eye - measurements miss wrong microphones,
   extra people, lettering and scene jumps.
4. Hand choices in `selection.json["manual"]` always win; re-run the night run for new start images.

V1/V2 comparison of two cuts (what improved, which shots are still weak) is the video-review skill's job:
hand it both films plus `review.json` / `selection.json`.
