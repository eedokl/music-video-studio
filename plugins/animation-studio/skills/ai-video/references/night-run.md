# Night run: job format, phases, picks

A user skill writes `<project>/jobs.json`; `night_run.py` computes it. Paths are relative to the jobs file.

```json
{"phases": ["flux", "qwen_edit", "depth", "ltx", "s2v", "wan"],
 "selection": "selection.json",
 "hooks": {"after:qwen_edit": ["uv", "run", "...", "pick.py", "auto", "<project>"]},
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
| `wan` | comfy:wan | image, prompt, seconds, seed, neg, meta |

- **Order:** stills first, then the pick hook (canon check chooses start images), depth, then the videos - each
  model is loaded once. `{img}` in `out` is the picked image's variant tag: a new pick makes new clips, old ones stay.
- **Resume:** existing outputs are skipped; just start again after a crash. `--only s02,s05` and `--phases ltx`
  recompute parts; `--status` shows done/open per phase; `--dry-run` lists jobs with a time estimate.
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
