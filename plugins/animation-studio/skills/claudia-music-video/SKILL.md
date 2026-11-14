---
name: claudia-music-video
description: "Make a photorealistic AI music video with the singer Claudia (black bob, one clay-orange streak, star clip, beige headset mic) from a song: shot plan on the sung lines, fresh shot ideas from the lyrics, start images that keep her face, lip-synced singing shots (LTX-2.3, Wan2.2-S2V) picked by measured lip score, moving B-roll, cut on the song with lyrics and AI label - as a studio/story video or as a live concert video. Use this whenever the user wants Claudia to sing a song, a Claudia music video or clip, a live/concert version with Claudia, a photoreal AI singer video, or wants to redo, re-pick or re-cut shots of such a video (projects with project.json + jobs.json + selection.json) - even if they just attach a song and say 'Claudia should sing this'."
---

# Claudia music video

Photographic AI music video with Claudia, computed locally overnight (ComfyUI), cut on the song.
Canon: `${CLAUDE_PLUGIN_ROOT}/skills/characters/references/claudia.md` - **read it first**.
Building blocks: song-analysis (song project, words, Rhubarb), ai-video (models, night run, measurement),
film-finish (lyrics overlay, cut, small versions), video-review (V1/V2 comparison).

Scripts: `S="${CLAUDE_PLUGIN_ROOT}/skills/claudia-music-video/scripts"`, `A="${CLAUDE_PLUGIN_ROOT}/skills/ai-video/scripts"`.
Measurement scripts need `uv run --no-project --python 3.12 --with mediapipe --with opencv-python-headless --with numpy --with pillow` (= `MP` below).

## 1. Interview (short, one question at a time, with a default)

- **Song** (wav/mp3), **lyrics**, **stems** if any (Suno: lead + backing vocals; better lip measurement).
- **Version**: `studio` (story video in real places around the song's topic) or `live` (concert stage, band
  silhouettes, audience from behind, light show). See `references/versions.md`.
- Whole song or an excerpt (pilot)? Night run tonight or a few shots now?
- Anything fixed: places, wardrobe, people (anonymous, from behind), things that must not appear.
- Check the machine once: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py"`; this skill also
  needs config `face_landmarker`, `claudia_refs` (or project `character_refs`), optionally `comfy_start`.

## 2. Song project and analysis (song-analysis)

```
uv run --no-project python ".../song-analysis/scripts/new_project.py" <proj> --song song.wav --lyrics lyrics.txt \
    --lead lead.wav --backing backing.wav [--from 9 --to 24 --lyrics-from "..." --lyrics-to "..."] --language de
uv run --no-project --with numpy python ".../song-analysis/scripts/analyze.py" <proj> --only 1,2,3,4
```
Check `analysis/song_sheet.png`: the sung lines must sit on the vocals (they become the cuts and the lip curve).

## 3. Shot plan + creative brief

`uv run --no-project python "$S/plan.py" <proj> --version studio|live [--lipsync 0.5] [--s2v]` - one shot per sung
line on the beat, techniques `lipsync` / `broll` / `claudia_moving`, framings and cameras drawn with the creative seed.

**Engines for sung shots** (field `engine`, default `ltx`):

| engine | when | cost |
|---|---|---|
| `ltx` (LTX-2.3) | default: text-heavy lines, fast syllables, best image | ~2.5 min per seed, 2 seeds |
| `s2v` (Wan2.2-S2V) | a single held, emotional note or call < 4.7 s (close-up); `plan.py --s2v` marks held notes (longest sung word >= 1.4 s, not in [Speaker] parts, max 15 % of sung shots) | ~15 min per shot, 832x480 @16 fps; + 1 LTX seed, the measurement picks |
| `infinitetalk` | long sung passages (one take instead of several cuts, chained 81-frame passes) or held notes where the start image must stay | ~80 s per second of video, 832x480 @25 fps; + 1 LTX seed when <= 4.7 s |
| `humo` / `minimax` | rescue for plosive-heavy lines where LTX measured ~0 (HuMo 1.7B / local MiniMax H3); both rejected as default (static face / robotic body) | HuMo ~130 s, H3 ~42 s per second of video (H3 renders >= 5.2 s); + 1 LTX seed, the measurement picks |

S2V is off by default (GPU time). Measured on Europe 2031 (same start image, seed and vocal window as the
reference): S2V shot 46 r 0.51 (reference 0.39), shot 14 0.45 (reference 0.53) - one S2V seed is a lottery, so the
LTX seed rendered next to it is the safety net.

Other techniques you can set per shot:
- `typo` - drawn typography, no AI: `"typo": {"kind": "newsflash" | "stamps" | "departures" | "title", ...}` (see
  `scripts/typo.py`; stamps land on the sung words; `"ground": "screen"` = on the stage screen of the live version).
  A `typo` entry on a broll/lipsync shot draws over its material (departure board over an airport clip). Set
  `"lyrics": false` when the shot shows the words itself.
- `placed` - an existing clip with a singing mouth but no own sound (e.g. an old Wan clip): `"clip": "ai/wan/x.mp4"`;
  `pick.py` fits entry frame and tempo to the vocal curve (fit windows >= ~1.5 bars; short windows overfit).
- `"recipe": "crowd"` on a B-roll shot of an audience: LTX crowd recipe (img_compression 42, "A cinematic scene of").
- `"start_image"` on any shot: use this image instead of generating start images (re-shoots, a picked still).

Then **write the creative brief** (this is the film - do not skip it, do not copy earlier videos):
- `brief`: concept in one sentence, `wardrobe` (invented for this song), `look` (default), own `looks`
  `{name: [still sentence, short video sentence]}` for the places of this song.
- Per shot, from the line's meaning: `idea` (one concrete picture), and
  - lipsync / claudia_moving: `action` (what she does - one thing), `set` (where), `set_short`, `manner`, `look`
  - broll: `subject` (what we see, people only anonymous/from behind), `motion` (what moves), `look`
- Record every idea: `creative.add_idea(P, "ai", idea, shot)`; user ideas (`by: "user"`) always win.
Reference shots (Europe 2031: projector screens, paper stacks, storms, server halls) show *techniques*; each song gets
new pictures. A new seed (`project.json "seed"`) gives a new take of plan, wardrobe, seeds and camera moves.
**Checkpoint:** show the shot list (time, line, technique, idea) and ask for changes before any GPU time.

## 4. Prompts and night run

```
uv run --no-project python "$S/jobs.py" <proj> [--start 2 --seeds 2 --broll 2]     # prompts.json + jobs.json
uv run --no-project --with numpy python "$A/night_run.py" <proj>/jobs.json --dry-run   # jobs + time estimate
uv run --no-project --with numpy python "$A/night_run.py" <proj>/jobs.json             # GPU (waits for the shared lock)
```
Vocal inputs of LTX / InfiniteTalk start in a silence and are levelled (-16 dBFS sung RMS, peaks <= -1 dBFS,
15 ms ramps - `clips.prepare_vocal`, identical to the live reference). `jobs.py` refuses prompts that break the canon/LTX rules (see `references/lessons.md`). Order: FLUX stills -> Qwen
start images -> pick hook (canon check) -> depth -> LTX lip-sync + moving -> S2V. Resumable; `milestones.log`.
Rough cost: ~10 min loading + per lip-sync shot 2 seeds x ~2.5 min, per B-roll ~2.5 min; a 3-min song ~4-7 h.
Keep other big programs closed (LTX peaks near 45 GB RAM). Only ever one GPU job: never kill other jobs or locks.

## 5. Pick by measurement, then look

`$MP python "$S/pick.py" all <proj>` - canon check for start images, lip score for every seed (best lag within +-3
frames, closed mouths, hidden scene cuts and frozen stretches rejected; moving clips warned when they barely
move), contact sheets `sheet_start.jpg`, `sheet_broll.jpg`, `sheet_clips.jpg`, log in
`picks.log`. Start images that fail only on the microphone (two booms, or the boom on the wrong cheek) are
repaired automatically in the night-run hook (`pick.py start --repair-mic`, ai-video `mic_repair.py`: wrong boom
retouched + FLUX texture, else Qwen-Edit "change only the microphone"; result `ai/start/<shot>_v<k>m.png`,
re-checked). **Look at the sheets**: mic (one, beige, her right cheek), one streak, adult face, no lettering, no scene
jump, Christian/others not recognisable. Override in `selection.json["manual"]`; new start image -> run the night
run again for that shot (`--only s05`), new clips get new names.
Weak shots (score < 0.2): 2 more seeds with a stronger mouth sentence (`variants.seeds` 4), another start image, or
B-roll instead; loud choruses and shouted calls ("Hey! Hey!" live on the backing stem): `--curve mix`.
S2V/InfiniteTalk clips are 832x480: `"$A/upscale.py" clip.mp4 clip_720p.mp4` (Real-ESRGAN) before the cut if they
look soft (render_shots otherwise scales with Lanczos).

## 6. Cut

```
uv run --no-project --with numpy --with pillow --with opencv-python-headless python "$S/render_shots.py" <proj>
uv run --no-project --with numpy --with pillow --with opencv-python-headless python "$S/make_film.py" <proj>
```
render_shots: every shot to `scenes/<shot>/` (clip placed on the song with lead-in, delay and lag; still + depth
parallax as fallback; grain + vignette; AI label in the last 3 s - set `ai_label`, e.g. "Images and video
AI-generated (...) - Claudia by anabology"). make_film: lyrics overlay, `film.mp4` / `film_small.mp4` / `film_mail.mp4`
(0 decode errors), `film_sheet.png`, `film_shots.jpg`, `review.json`.
**Checkpoint:** the user watches V1.

## 7. Review and V2

Hand `film.mp4`, `review.json`, `selection.json` and `picks.log` to the **video-review** skill for the review and,
after fixes, the V1/V2 comparison. Typical V2 work: more seeds for weak lips, moving clips instead of stills,
re-pick with lag, re-run shots whose clip jumped scenes or invented letters (only the negative prompt mentions text).

References: `references/lessons.md` (rules with their reasons), `references/versions.md` (studio vs live),
`references/reference-tests.md` (test against Europe 2031). Models and timings: ai-video `references/models.md`.
