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
Run every script with `uv run <script>.py`: each declares its own pinned packages; the mediapipe measurement scripts
(`pick.py`, ai-video `mouth.py` / `canon.py`) also pin Python 3.12.

**Building blocks** (shared code + docs of this plugin, not skills - read the one you need):
`${CLAUDE_PLUGIN_ROOT}/skills/<block>/BLOCK.md` for `studio-core`, `song-analysis`, `toon-2d`, `characters`, `voice`, `ai-video`, `bricks-3d`, `stage-3d`, `film-finish`. In those files
`<plugin>` stands for `${CLAUDE_PLUGIN_ROOT}`. First use on a machine: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py" --setup` (finds the programs).

## 1. Interview (short, one question at a time, with a default)

- **Song** (wav/mp3), **lyrics**, **stems** if any (Suno: lead + backing vocals; better lip measurement).
- **Version**: `studio` (story video in real places around the song's topic) or `live` (concert stage, band
  silhouettes, audience from behind, light show). See `references/versions.md`.
- Whole song or an excerpt (pilot)? Night run tonight or a few shots now?
- Anything fixed: places, wardrobe, people (anonymous, from behind), things that must not appear.
- **Reference images of Claudia** (the plugin ships none, the start images need two): her face with mic and clip +
  a close-up with the one streak and the clip - the user's own (claudia.gallery sheets, download only with their OK,
  or stills of an earlier Claudia film). Put them into the project and set project.json `"character_refs"`.
  **Check the references by eye before the run:** the mic boom must run along HER RIGHT cheek (image left, the streak
  side) - Qwen copies the mic from image 1, so a reference with the mic on her left cheek gives wrong mics in most
  start images (user tests: a claudia.gallery sheet had it there; the Europe 2031 film's references had it right).
- Check the machine once: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py"`; this skill also
  needs config `face_landmarker`, `claudia_refs` (or project `character_refs`), optionally `comfy_start`.

## 2. Song project and analysis (song-analysis)

```
uv run ".../song-analysis/scripts/new_project.py" <proj> --song song.wav --lyrics lyrics.txt \
    --lead lead.wav --backing backing.wav [--from 9 --to 24 --lyrics-from "..." --lyrics-to "..."] --language de
uv run ".../song-analysis/scripts/analyze.py" <proj> --only 1,2,3,4
```
Check `analysis/song_sheet.png`: the sung lines must sit on the vocals (they become the cuts and the lip curve).

## 3. Shot plan + creative brief

`uv run "$S/plan.py" <proj> --version studio|live [--lipsync 0.5] [--no-s2v]` - one shot per sung
line on the beat, techniques `lipsync` / `broll` / `claudia_moving`, framings and cameras drawn with the creative seed.

**Another lead or a second character** (the film stays in Claudia's photographic style, with someone else in it):
describe the people in project.json and name them per shot - the plugin then takes identity text, reference images,
negatives and checks from the shot's cast, and none of Claudia's canon (microphone, streak, mic repair):

```
"lead": "oliver",
"characters": {
  "oliver": {"pronoun": "he", "full": "<identity text, pasted into every image prompt>", "far": "<short, for wide shots>",
             "video": "<short, for video prompts>", "keep": "face, head shape, skin and hair",
             "refs": ["refs/front.jpg", "refs/threequarter.jpg"],
             "options": {"headband": "a black running headband around his forehead"},
             "wardrobe": "<default clothes>", "negative": "beard, bald head, glasses"},
  "claudia": {"base": "claudia", "mic": false, "refs": ["refs/claudia_close.png"]}   // Claudia as a guest, no stage mic
}
```
`"sheet": true` on a character = its first reference is a **views sheet** (front, three-quarter and profile of the same
person side by side on one picture, bare of anything that should not travel into every shot: cap, logo, a hand at the
head) and the second a close-up of the face; the prompt then tells the picture model that the sheet shows one person.
Measured on one man (see `references/lessons.md`): closer to him than two single photos, and no cap or logo any more.
Shot keys: `"who": "oliver"` | `"claudia"` | `["oliver", "claudia"]` (default: the lead; two people = one reference
each, the first one sings), an option switched on by its key (`"headband": true`), `"wardrobe"` / `"wardrobe2"`.
Start images of such shots have no measured canon: `pick.py` takes the first variant and the sheet says "check by eye" - or, with the config key `face_id_model`
(ai-video `face_id.py`), the variant whose face is most like the character's `refs`, with a warning when none is.
**Every shot that shows a character of the film is `lipsync` or `claudia_moving` with `who`** - a person described in
a `broll` subject has no reference image and comes out as a stranger.

**Engines for sung shots** (field `engine`, default `ltx`):

| engine | when | cost |
|---|---|---|
| `ltx` (LTX-2.3) | default: text-heavy lines, fast syllables, best image | ~2.5 min per seed, 2 seeds |
| `s2v` (Wan2.2-S2V) | held, emotional notes and slow lines < 4.7 s (close-up) - **on by default**: plan.py marks shots holding a sung word >= 0.7 s, ranked by held seconds - 0.25 x words per second, max a quarter of the sung shots and 6 per film, not in [Speaker] parts (`engine_reason` says why); `--no-s2v` = LTX only | 11-18 min per shot, 832x480 @16 fps; + 1 LTX seed, the measurement / takes.py picks |
| `infinitetalk` | long sung passages (one take instead of several cuts, chained 81-frame passes) or held notes where the start image must stay | ~80 s per second of video, 832x480 @25 fps; + 1 LTX seed when <= 4.7 s |
| `ltx25` (LTX-2.5) | experimental, by hand only: ONE cut inside a sung shot of 6-8 s (few takes are usable - tell the user before the run) - add `"cuts": [{"framing": "frontal medium shot from the waist up", "action": "..."}]`; frontal and medium or closer after the cut (jobs.py refuses wide / profile); needs extra model files (ai-video `references/multishot.md`) | ~5 min per seed, 3 seeds (`ltx25_seeds`); pick.py rejects a missing or extra cut, a lost streak, a second hair clip |
| `humo` / `minimax` | rescue for plosive-heavy lines where LTX measured ~0 (HuMo 1.7B / local MiniMax H3); both rejected as default (static face / robotic body) | HuMo ~130 s, H3 ~42 s per second of video (H3 renders >= 5.2 s); + 1 LTX seed, the measurement picks |

Why S2V by default for held notes: in the Europe 2031 studio film (same rule) V3 kept S2V in 5 of 6 such shots
(lip scores 0.63 / 0.53 / 0.40 / 0.39; one with ~0 was still chosen for its expression, one switched to LTX); in the
live film the sung S2V shots scored good / medium. One S2V seed is a lottery, so the LTX seed rendered next to it is
the safety net - compare both in takes.py. Show the user the time (`night_run.py --dry-run`) before the run.

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
    (`manner` = how she sings, e.g. "softly", "with energy", "tiredly into the camera"; `action` = a small movement,
    e.g. "the wind blows her hair", "a slight sway of the head" - plan.py proposes both from the look. The LTX prompt
    is built like the Europe 2031 night run V1: "she sings <manner>, <action>. She sings the words "...". <mouth>".
    "deadpan" is her face, not a way to sing: bound to the words ("sings deadpan: ...") it kept mouths shut.
    The same holds for every mood word in `manner` - "quietly", "dryly", "lazy", "tired": LTX obeys the adjective and
    mumbles or shuts the mouth (jobs.py prints a hint). Write how the words are sung - "warmly and articulates
    every syllable with a clearly moving mouth" - and put the mood into the face or the action. A shot that ends
    on a long held word may say `"hold_last": true` (one sentence asking for an open mouth until the note ends).)
  - Only for shots with two or three separate actions on the beat (gesture lists, chorus energy, "Hey!" shouts):
    add a `timeline` `[[0, 1.0, "she punches her fist up on each Hey"], [1.0, 3.1, "she walks ..., one step on every
    beat"]]` - one concrete action per span, no hold words ("small head movements", "static camera", "upright"), and a
    camera move on the downbeat. The times count from the shot start (jobs.py shifts them by the LTX lead-in). Such a
    shot renders mixed with 4 LTX seeds (unless `--seeds` is given): odd seeds with the plain prompt (A, without a
    downbeat camera), even seeds with the timeline prompt (B) - with a single LTX seed only B -, files
    `<shot>_<img>_s<k>_pa.mp4` / `_pb.mp4`, the user picks by eye (GPU test 2026-11-15, s08 "Hey!": B 2:0, all three
    actions on the beat; the lip score says little for shouts, the takes page says so) (`prompt_style`: "timeline" / "plain" forces one). Close-ups, spoken
    and quiet shots stay plain: in the A/B test (2026-11-15, 8 shots) B won 3 of 3 multi-action shots, A the other 5.
  - broll: `subject` (what we see, people only anonymous/from behind), `motion` (what moves), `look`
- Record every idea: `creative.add_idea(P, "ai", idea, shot)`; user ideas (`by: "user"`) always win.
Reference shots (Europe 2031: projector screens, paper stacks, storms, server halls) show *techniques*; each song gets
new pictures. A new seed (`project.json "seed"`) gives a new take of plan, wardrobe, seeds and camera moves.
**Checkpoint:** show the shot list (time, line, technique, idea) and ask for changes before any GPU time.

### Long takes with movement (option)

`uv run "$S/plan.py" <proj> --takes long` (project.json `"takes": "long"`) plans the film in takes of 6-9 s instead
of one shot per line: one take = one place = two to four sung lines, she walks, dances or gestures through it and
the camera travels; every sung take is LTX lip-sync, rendered at 1024x576 with up to 217 frames. Offer it when the
user wants more movement or longer scenes, or names a video of that kind as the model. Ask, do not assume: the
default stays the short plan.
- **`"speed": 1.18`** on a shot whose take reads as slow motion: the vocals are slowed for the render and the cut
  shows the clip that much faster (lips in real time, body faster). Shot by shot, after looking at the takes - some
  takes look unnatural faster, and slow motion suits others. A faster take is shorter (7.6 s at 1.18).
- **`timeline`** on a take that should be richer: two or three things happening one after the other. It adds
  gestures, not walking speed.
- pick.py then prefers the take that moves most among those with about the same lip score; lip scores of long
  takes lie lower than those of short ones without the mouths being worse.
- `uv run "$A/film_motion.py" film.mp4 [--shots project.json]` gives take length and movement of a film, the same way
  for every film (and for a reference video's own numbers).
What held and what did not, the speed test, the mirror and back-view tricks: `references/long-takes.md`.

## 4. Prompts and night run

```
uv run "$S/jobs.py" <proj> [--start 2 --seeds 2 --broll 2]     # prompts.json + jobs.json (checks project.json first)
uv run "$S/jobs.py" <proj> --only s05 --all-starts [--start 3] # MORE TAKES of a shot: clips from every start image
uv run "$A/night_run.py" <proj>/jobs.json --dry-run   # jobs + time estimate
uv run "$A/night_run.py" <proj>/jobs.json             # GPU (waits for the shared lock)
```
**Start images first**: run `night_run.py <proj>/jobs.json --phases flux,qwen_edit`, look at the start-image sheets
with the user (headset side and size, cables, clothes, the right person), fix them, and only then run the clips -
a wrong start image wastes every take made from it (`references/lessons.md`, "Review rounds on a finished cut").
Vocal inputs of LTX / InfiniteTalk start in a silence and are levelled (-16 dBFS sung RMS, peaks <= -1 dBFS,
15 ms ramps - `clips.prepare_vocal`, identical to the live reference). `jobs.py` refuses prompts that break the canon/LTX rules (see `references/lessons.md`). Order: FLUX stills -> Qwen
start images -> pick hook (canon check) -> depth -> LTX lip-sync + moving -> S2V. Resumable; `milestones.log`.
`jobs.py` also prints **direction hints** (not errors): a hand named at the hair, raised eyebrows, laptops / phones
(brand logos), a person of the film in B-roll, the same action in many shots - fix the brief before the night run.
**Changed jobs are redone**: the night run keeps a fingerprint of every output (`jobs_made.json`: prompt, seed, the
picked start image and that image's fingerprint). Rewrite a shot in the brief, run `jobs.py --only <shot>` and the
night run again - its images and clips are made anew, the old files move to `ai/<kind>/replaced/`. `--status` /
`--dry-run` show them as "to redo". After a plugin update that rewords prompts, `--keep-stale` adopts what is there.
Rough cost: ~10 min loading + per lip-sync shot 2 seeds x ~2.5 min, per B-roll ~2.5 min; a 3-min song ~4-7 h.
Keep other big programs closed (LTX peaks near 45 GB RAM). Only ever one GPU job: never kill other jobs or locks.

## 5. Pick by measurement, then look

`uv run "$S/pick.py" all <proj>` - canon check for start images, lip score for every seed (best lag within +-3
frames, closed mouths, hidden scene cuts and frozen stretches rejected ("frozen" = the picture stops, measured
against the clip's own motion, so a calm shot with a static camera is not frozen); moving clips warned when they
barely move; when every moving clip of a shot has a hidden cut or freezes, the automatic pick is the still with the depth
move - the clips stay on the takes page; a hand pick on another start image is rated but never the automatic pick), contact sheets `sheet_start.jpg`, `sheet_broll.jpg`, `sheet_clips.jpg`, log in
`picks.log`. Start images that fail only on the microphone (two booms, or the boom on the wrong cheek): make more
variants (`jobs.py --only <shot> --start 5`) and stage her frontally. The repair is **off by default** (it left grey
patches on the cheek in 3 of 6 images); opt in with `jobs.py --repair-mic` or project `"mic_repair": true`, then the
night-run hook repairs them (`pick.py start --repair-mic`, ai-video `mic_repair.py`: wrong boom
retouched + FLUX texture, else Qwen-Edit "change only the microphone"; result `ai/start/<shot>_v<k>m.png`,
re-checked). **The headset added afterwards** (`"mic": "added"` in project.json, or on one shot; opt-in): the start
image is made WITHOUT a microphone (`ai/start_bare/`, from references whose headset was edited away once,
`ai/refs_bare/`), then a second edit adds only a small beige headset - limited to her face (ai-video
`face_edit.py`), so the rest of the picture stays as it is. Each picture gets `"mic_tries"` (default 2) tries
(`<shot>_v1.png`, `_v1b.png`); the pick takes one headset on the right side that was really added (cheek line share
against the bare picture). On six test shots 24 of 24 tries were right (painted in one step: 19 of 38 wrong side,
cables, doubles); it costs about 1.5 min more per shot and the capsule colour varies, so look at the sheets first.
Not used for shots from behind, shots with other people and given start images. **Look at the sheets**: mic (one, beige, her right cheek), one streak, adult face, no lettering, no scene
jump, Christian/others not recognisable. Override in `selection.json["manual"]`; new start image -> run the night
run again for that shot (`--only s05`), new clips get new names. A re-made start image that the canon check scores
LOWER than the old one is not taken automatically (nothing is re-rendered): put it into `manual.start` first.
Weak shots (score < 0.2): 2 more seeds with a stronger mouth sentence (`variants.seeds` 4), another start image, or
B-roll instead. The lip curve is `mix` by default (Rhubarb + vocal level, as the live film measured: Rhubarb alone
went negative in loud choruses where the lips were right); `--curve rhubarb|level|both` or project `"lip_curve"`
overrides it. Vocalises without words ("Ooh") measure weak whatever the mouth does: judge them by eye (takes.py marks them).
S2V/InfiniteTalk clips are 832x480: `"$A/upscale.py" clip.mp4 clip_720p.mp4` (Real-ESRGAN) before the cut if they
look soft (render_shots otherwise scales with Lanczos). The clip's json is copied to `clip_720p.json`; use it with
`selection.json["manual"]["clip"]["s07"] = {"file": "ai/s2v/s07_v2_720p.mp4", "lag": <lag of the original pick>}`.

**Checkpoint - compare the takes by eye (recommended, no GPU):** `uv run "$S/takes.py" <proj> --serve` makes a small
preview of every take on the song (placed exactly as render_shots places it, with the song's sound) and opens a page
built like the user's own V1/V2 compare tool: the shot list on the left (badge = current take, yellow dot = changed
since the last cut), the takes of one shot side by side (lip score / motion / warnings from picks.log, automatic pick
marked), keys 1-9 choose, up/down change the shot, space plays all takes together (sound from the chosen one), loop,
"next shot after a choice". Every shot also offers its **still** (start image / B-roll picture with the depth camera
move) instead of a clip - the official way when every seed of a moving clip fails (claudia3: LTX drove the ferry into
the camera). A take made on a start image that is no longer the chosen one is marked yellow ("made on start image v2,
not the chosen v4 - check mic / streak"; claudia3 had a second mic in the film that way), as is a take on a mic repair.
**Build cut** runs `render_shots.py --only <changed shots>` + `make_film.py` and shows the new film on the page.
Offer it to the user before the cut, and let the user choose - do not pre-choose for them: in the Europe 2031 night
run the eye preferred natural movement over the highest lip score (V3 took the V1 take in 11 of 17 singing shots), in
claudia3 the user took LTX in 3 of 4 shots where S2V measured (and looked to the tester) better. Previews take ~0.2 s
each (CPU); the page is local only (127.0.0.1).
**Far faces (after the choice, before the cut):** in wide shots LTX smears a small face (crooked, half-closed eyes,
changing every frame). `uv run "$S/face_fix.py" <proj> --list` measures the picked sung takes (CPU) and names the
"far" ones (face under 85 px at 1024 wide in the take's small part); without `--list` it rebuilds only their face
(ai-video `face_pass.py`: LTX-2.3 + Lightricks pixel upscaler IC-LoRA on the face crop, the start image's face as
anchor, vocals riding along; ~5 min GPU per take; where the take comes close it fades back to the original between
85 and 130 px) -> `<clip>_g.mp4` + `<clip>_g.sheet.jpg` (top original, bottom fixed) and the fixed clip as the shot's
manual clip; the generated face stays in `ai/lipsync/face_pass/`, so `--blend` re-blends without GPU. Tell the user the cost and show the sheets; a shot where the face
looks more made-up or a streak widened goes back to its original clip. Opt out: project `"face_fix": false`, shot
`"face_fix": false`; several faces in the frame: shot `"face_hint": [x, y]`. Why and the compared ways:
`references/lessons.md` "Far faces".
**More takes later:** project.json shot `"seed"` (moving clip) or `"s2v_seed"` / `"s2v_seeds": 2` (S2V) - a seed
other than the default goes into the file name (`<shot>_<img>_sd<seed>.mp4`), so the old take stays and the night
run does not skip the job as done; `jobs.py --only s01,s08` replaces only those shots' jobs in jobs.json / prompts.json.
The mic measurement of start images is a hint, not a proof (claudia3: a repaired image with two booms measured "ok"):
look at `sheet_start.jpg` yourself before the lip-sync phase.

## 6. Cut

Every build script checks project.json first (studio-core `project_check.py`, details in song-analysis "Project check"): a wrong type, an impossible section (from >= to, duplicate name) or an unknown transition stop it in seconds with exit code 2 and the key named; unknown keys and overlapping sections (build.py cuts at the next start) only warn. `"size": [w, h]` = shot size (default 1280x720).

```
uv run "$S/render_shots.py" <proj>
uv run "$S/make_film.py" <proj>
```
render_shots: every shot to `scenes/<shot>/` (clip placed on the song with lead-in, delay and lag; still + depth
parallax as fallback; grain + vignette; AI label in the last 3 s - set `ai_label`, e.g. "Images and video
AI-generated (...) - Claudia by anabology"). make_film: lyrics overlay, `film.mp4` / `film_small.mp4` / `film_mail.mp4`
(0 decode errors), `film_sheet.png`, `film_shots.jpg`, `review.json`. build.py says "look none" on purpose: plan.py
sets `"look": "none"` because the photographic finish (grain + vignette) is already in the shots; `"look": "standard"`
adds the paper texture on top.
**Checkpoint:** the user watches V1.

### Cut in code (option)

`uv run "$S/code_film.py" <proj> [--pace calm|medium|fast] [--plan-only] [--from K --to K]` cuts the same picked
material a second way: the cut is data on the beat grid (jump-ins on word onsets, stills moved in code and reframed on
the beat), and lyrics, labels, ticker and cards are drawn in code frame by frame -> `film_code_v01.mp4` (next free
number, `film.mp4` is untouched) + sheet. Offer it when the user wants a graphic layer that follows words and beats, a
faster or data-driven cut, or names the film Y2Y2R / "You're Too Young to Remember" as the model.
- **Ask for the pace** (project.json `"pace"`, default `calm`): `calm` holds every take for its whole line, `fast`
  cuts stills every beat in a chorus. The first film in this method was judged "a bit too fast" at `fast`.
- B-roll needs only its picked image here (no B-roll clips): for a film made only this way, skip the moving B-roll jobs.
- Start images for sung shots should be frontal for this cut (the face is framed into the upper half and tracked).
- The graphic layer is project.json `"code_layer"` (worlds per look with grade and accent colour, accents per line,
  meter, clock, ticker of dated facts with sources, overlays anchored to words, dust, iris out) and per shot `"code"`
  (pattern, beats, tag, cam, `overlays`: small pieces on a word of that shot - stamp, check, sight, rings, cards,
  flip, quote; propose one per shot or none and let the user pick, never fill them in unasked). Schema, overlay types and findings: `${CLAUDE_PLUGIN_ROOT}/skills/film-finish/references/code-cut.md`.
- Review on the frame numbers burned into the scene slug; change project.json and re-render a range with `--from/--to`
  (seconds, no GPU). Needs config `node` and `browser`.

## 7. Review and V2

Hand `film.mp4`, `review.json`, `selection.json` and `picks.log` to the **video-review** skill for the review and,
after fixes, the V1/V2 comparison. Typical V2 work: more seeds for weak lips, moving clips instead of stills,
re-pick with lag, re-run shots whose clip jumped scenes or invented letters (only the negative prompt mentions text).

References: `references/lessons.md` (rules with their reasons), `references/versions.md` (studio vs live),
`references/long-takes.md` (takes of 6-9 s with movement, shot speed),
`references/reference-tests.md` (test against Europe 2031). Models and timings: ai-video `references/models.md`.
