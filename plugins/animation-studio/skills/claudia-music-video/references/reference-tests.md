# Reference test: Europe 2031 (studio version)

Reference project: `claudia-video-trial` (song "Europe Twenty Thirty One", 62 shots, V1 -> V2 by measurement;
final films `nachtlauf/claudia_europe2031*.mp4`, measurement `nachtlauf/analyse.py`, `v2_auswahl.log`, `V2_ANALYSE.md`).
Live version for later tests: `claudia-live` (69 shots, `lippen_auswahl.py` with Rhubarb + level curve).

## How the test is run

Excerpt 9.0-24.0 s (lines "PowerPoint und Strategien" ... "Europe sagt: Wir pruefen das noch.") = reference shots
4-7 (two LTX lip-sync shots, two B-roll moving clips in V2). Scratch folder outside the plugin:

```
new_project.py <test>/europe2031_part --song "Europe Twenty Thirty One.wav" --lyrics songext-suno.txt \
   --lead "stems/0 Lead Vocals.wav" --backing "stems/1 Backing Vocals.wav" --from 9 --to 24 \
   --lyrics-from PowerPoint --lyrics-to "Europe sagt" --language de
analyze.py <proj> --only 1,2,3,4
plan.py <proj> --version studio            -> 4 shots: s01 broll, s02 lipsync, s03 broll, s04 lipsync
(brief written by hand: new ideas - projector for empty chairs, metro escalator, driverless car, archive folders)
jobs.py <proj>  ->  night_run.py <proj>/jobs.json  ->  pick.py all  ->  render_shots.py  ->  make_film.py
compare_test.py (test folder): lip scores with both vocal curves, canon on film frames, shot sheets side by side
```

The measurement port was checked first: plugin `mouth.py` on the reference clips with the reference curve gives
exactly the numbers of `v2_auswahl.log` (shot 4 s1/s2 r0 0.417/0.591, shot 7 s1/s2 0.216/0.223, same mouth ranges).

## Result (2026-11-13)

GPU: 18 jobs, 27:39 min including ~8 min waiting for other sessions' GPU jobs (FLUX 4 x ~10 s, Qwen-Edit 4 x ~35 s,
depth 4, LTX 6 x 80-130 s). Film: 15.0 s, 0 decode errors (film.mp4 / film_small.mp4 22.7 MB, film_mail.mp4 11.6 MB).

Lip score of the chosen clips (r at lag 0 / at the chosen lag; the same code as analyse.py):

| shot | line | plugin (plugin curve) | plugin (reference curve) | reference V2 (reference curve) | reference V2 (plugin curve) |
|---|---|---|---|---|---|
| s04 = ref 07 | Europe sagt: "Wir pruefen das noch." | **0.579** @0 (s2: 0.560) | 0.473 | 0.223 (S2V V1: -0.07) | 0.259 |
| s02 (ref 05 was B-roll) | while the future's on amphetamines. | 0.348 / **0.543** @+2 (s2: 0.213) | 0.152 | - | - |
| ref 04 (B-roll here) | PowerPoint und Strategien | - | - | 0.591 | 0.381 |

Canon on 3 film frames per Claudia shot: plugin 6/6 one mic on her right cheek, streak on the image left 5/6 (the
6th frame lies in the 2.5 s end fade-out of the excerpt); reference V2 shots 4 and 7: streak 6/6 but **two
microphones in 6/6 frames** (now caught by canon.py; the reference V2 start images 4, 7, 27, 40 all have two mics,
27 has no streak).

Automatic picks vs. eye: the canon check (streak + mic) chose the right start image in both shots after the mic test
was added (before it, s02_v2 with two mics and a star on the coat won); B-roll s01_v1 had FLUX lettering on the
chart -> v2 by hand; s03_v2 had letterbox bars (now rejected automatically).

Sheets: `experiments/plugin-tests/claudia-music-video/comparison_sheet.jpg` (left reference V2 shots 4-7, right
plugin s01-s04), `reference_v2_shots.jpg`, `plugin_shots.jpg`, `europe2031_part/sheet_clips.jpg`, `film_shots.jpg`;
numbers in `comparison.json`, `reference_lips.json`.

Findings / open:
- The vocal curve matters as much as the clip: Rhubarb on the excerpt's Suno lead stem vs. the reference's
  whole-song curve moves r by up to 0.4 (ref shot 4: 0.591 vs 0.381; s02: 0.543@+2 vs 0.152@0). For s02 the two curves
  disagree on the lag - look at it before trusting +2; consider `--curve mix`.
- Lyrics overlay style comes from film-finish (yellow highlight, script font); the reference used Clay #D97757 caps.

## Test 2 (2026-11-14): S2V, re-placed Wan clip, typography, clip checks, vocal levelling

Full-song project (`europe2031_s2v`, Rhubarb on the Suno lead stem), sections at the reference shot times.

**S2V really used in the reference:** V1 used S2V for shots 2, 7, 14, 46, 49, 60 (+19 from the lip-sync test); V2
kept S2V for 2, 14, 46, 60 and replaced 7 and 49 by LTX (S2V r ~ 0 there). Old Wan clips re-placed by mouth curve:
shots 20 (w_rooftop, entry 58, tempo 0.9), 23 and 61.

Re-shot 14 ("THE YESTERDAY! ... yesterday", held call) and 46 ("Kein Drama, kein Weltuntergang"): same start image
(reference q3), seed 31, 20 steps, same vocal window (61 frames @16 fps from the shot start). `plan.py --s2v` picks
shot 46's line on its own (held-note rule). r = lip score at lag 0 (same code as analyse.py/v2_auswahl.py; mouth
timestamps 1000/24 as there - with the clip's real fps the reference S2V measured 0.514 instead of the logged 0.53):

| clip | r, reference curve | r, plugin curve | r, mix curve | mouth range | streak | mic | GPU |
|---|---|---|---|---|---|---|---|
| reference 14 S2V | **0.53** (= log) | 0.56 | 0.61 | 0.25 | 3/3 | two | - |
| plugin 14 S2V | 0.45 | 0.48 | 0.52 | 0.28 | 3/3 | two (start image) | 882 s |
| plugin 14 LTX s1 | 0.50 | 0.49 | 0.56 | 0.26 | 3/3 | two | 99 s |
| plugin 14 InfiniteTalk | 0.42 | 0.39 | 0.49 | 0.23 | 3/3 | two | 427 s |
| reference 46 S2V | **0.39** (= log) | -0.14 | -0.02 | 0.65 | 3/3 | two | - |
| plugin 46 S2V | **0.51** | -0.09 | 0.04 | 0.61 | 3/3 | one | 844 s |
| plugin 46 LTX s1 | 0.55 | 0.23 | 0.10 | 0.32 | 3/3 | two | 89 s |

Reading: the S2V path works end to end (jobs -> night_run S2V phase -> 16 fps clip placed by frame repetition ->
pick -> render); results are in the reference's range (one seed each: 46 better, 14 worse). The mouth range of S2V
is 2x LTX on 46 (more expressive), as before. The two-mic frames come from the reference start images (q3), which
already had two mics; S2V happened to drop one on 46. Pick chose S2V for 14 (with the +0.05 S2V bonus) and LTX for 46
(the plugin curve disagrees there: Rhubarb on the Suno lead stem vs. the reference's curve correlate only 0.41 in
that window - no ground truth; check by eye).

**Old Wan clip re-placed by mouth curve** (shot 20, "Hey! Hey! Hey!", copied into the project as ai/wan/):
reference placement entry 58 / tempo 0.9 gives r 0.857 on the reference curve with `clips.frame_index` (log: 0.878
with abgleich's interpolation) -> the offset/tempo placement works. `mouth.py fit`: on the reference curve it finds
entry 34 / 0.9 (r 0.85); on the plugin lead curve entry 28 / 1.1 (r 0.25 there, 0.75 on the reference curve). The
calls sit on the backing stem: the lead Rhubarb curve correlates 0.01 with the reference curve in that window, the
loudness curve 0.74. A lead+backing Rhubarb curve (`--curve both`) overfitted the 1.8 s window (0.63 on itself,
-0.47 on the reference curve) - fit placements on windows >= ~1.5 bars and prefer `mix` for calls.

**Typography** (shots 33 NEWSFLASH, 36 stamps, 39 departure board over the reference gate still, 62 title):
same layout, fonts, colours and timing as the reference cut; stamps land on the sung words from the song sheet.
Differences: the reference stamps sit on a moving desk clip and its title on a FLUX sky (`"ground": "material"`).
Sheet: `s2v_typo_comparison.jpg` (left reference V2, right plugin).

**Clip checks** (`mouth.motion_check` vs claudia-live `v4_messung.json`): 12/12 clips identical (hidden cuts,
frozen, motion value), e.g. shot_40_s3 9 cuts, shot_02_s1 frozen, motion 0.14. File `clip_qa_check.txt`.

**Vocal levelling** (`clips.prepare_vocal` vs the live V2 LTX inputs): 4/4 windows sample-identical (corr 1.0000,
max diff 0.0001, same RMS -16.4...-17.0 dBFS and peaks). File `vocal_prep_check.txt`.

Sheets and numbers: `s2v_comparison_sheet.jpg`, `s2v_comparison.json`, `s2v_typo_comparison.jpg`, `wan_placement.txt`
(experiments/plugin-tests/claudia-music-video/).

## Test 3 (2026-11-14): Europe 2031 Live - crowd recipe, long InfiniteTalk take, upscaler

Live project `europe2031_live` (live song, Demucs vocals `stems/gesang.wav` as lead, reference instrumental).

**Crowd recipe** (shot 19, reference start image `v4/start_19.png`, seed 5 like reference s4), motion = mean frame
difference (`mouth.motion_check`, identical to v4_messung):

| clip | motion | cuts | frozen |
|---|---|---|---|
| reference s1-s3 plain prompt | 0.38 / 0.92 / 0.11 | 0 | 2 of 3 frozen |
| reference s4 / s5 crowd recipe | 16.4 / 16.6 | 0 | no |
| plugin plain (img_compression 18) | 0.82 | 0 | no |
| plugin recipe, first try ("A cinematic scene of" + motion text) | 7.76 | 0 | no |
| plugin recipe, final (`ltx.crowd_prompt`: "A cinematic scene of a rowdy, packed concert audience going wild." + motion) | **9.41** | 0 | no |

The reference recipe clips gain part of their motion by drifting away from the start image (new framings, faces
close to the lens); the plugin clip keeps the image and moves the crowd. Recipe confirmed: x11 motion vs plain.

**Long InfiniteTalk take** (bridge, shots 50-53, 150.93-163.65 s = 12.7 s, reference start image `v2/start_52.png`,
seed 31): `infinitetalk.py` chained 81+81+81+81+45 = 333 frames @25 fps in one ComfyUI job, 1384 s GPU (reference:
349 frames, ~19 min). Lip score per third (best lag +-3, reference curve = the live project's rhubarb_gesang.json):

| clip | r thirds (reference curve) | mouth range | streak | mic |
|---|---|---|---|---|
| reference bridge_s1 | 0.19 / 0.02 / 0.02 | 0.77 / 0.71 / 0.84 | 2/2 | two |
| reference bridge_s2 | 0.26 / -0.07 / 0.05 | 0.56 / 0.62 / 0.76 | 3/3 | two |
| plugin b50 | **0.27 / -0.00 / 0.12** | 0.79 / 0.66 / 0.73 | 3/3 | two (start image) |

No visible seams at the pass joins (sheet). Low r for all three: the soft bridge has little consonant structure.

**Upscaler** (`upscale.py`, S2V clip 832x480 -> 1280x720, 61 frames, 2.5 min): Laplacian sharpness 237 vs 48
(Lanczos). Real-ESRGAN x4plus smooths the freckles (a canon detail) - for close-ups of Claudia judge by eye; Lanczos
stays the default in render_shots. Sheet `upscale_test/upscale_compare.jpg` (left Lanczos, right Real-ESRGAN).

Sheets: `live_comparison_sheet.jpg`, numbers `live_comparison.json` (experiments/plugin-tests/claudia-music-video/).

## Test 3 (2026-11-14): mic repair, HuMo and MiniMax wrappers

**Mic repair** (`ai-video/mic_repair.py`, `pick.py start --repair-mic`, night-run hook after qwen_edit) on the start
images that had two microphones: Europe 2031 reference V2 starts 4 (v3), 7, 27, 40 (v2, the variants the film used),
plugin test s02_v2, and claudia-live V5 start 17 (already "repaired" there with Qwen-Edit, still two mics).
Inputs and outputs: `experiments/plugin-tests/claudia-music-video/mic_repair/` (`input/`, `repaired/` + sheet,
`repaired_v2/` second try with 4 FLUX seeds, `telea/` CPU-only retouch).

| image | before | method that passed | canon after | by eye |
|---|---|---|---|---|
| ref 04 v3 | two | retouch + FLUX (4.5 s) | one | clean |
| ref 40 v2 | two | retouch + FLUX | one | clean (faint line at the chin) |
| ref 07 v2 | two | retouch + FLUX | one | boom gone, textured patch on the cheek/jaw edge (both tries) |
| plugin s02_v2 | two | retouch + FLUX | one | boom gone, dark hair tuft painted on the jaw; 2nd try failed the check |
| ref 27 v2 | mic on the wrong cheek only | Qwen-Edit seed 1200 + retouch | one | mic now on her right cheek, blotchy skin where the old one was |
| live 17 (3/4 view) | two | Qwen-Edit seed 1201 + retouch (after 2 Qwen seeds drew two mics again) | one | blotchy patch on the chin |

Reading: canon passes 6/6, the eye 2/6 clean + 4 usable only with a visible patch. Qwen-Edit "change only the
microphone" (the reference V5 recipe) drew two booms again in 3 of 3 seeds - it cannot be the repair on its own;
removing the wrong boom with a mask is the part that works. FLUX fills skin well but paints hair/texture where the
mask crosses the hair edge. Open: a skin-only refine (lower denoise, mask clipped to the face hull) or a better
inpainting model; until then every repair is flagged for an eye check in picks.log / sheet_start.jpg. GPU: ~65 s per
retouch incl. FLUX load, Qwen path ~30 min incl. cold load (mostly waiting for the model).

**HuMo wrapper** (`ai-video/humo.py`, engine `humo`): 1.7B, s04_v1 start image + the s04 vocal window, 49 frames,
240 s GPU. Runs end to end (clip + json); the face drifts into an extreme close-up (streak cut off at the top -> canon
streak check fails), freckles exaggerated - as in the 2026-11-12 comparison. Rescue engine only.
`experiments/plugin-tests/claudia-music-video/humo_test/` (clip, sheet).

**MiniMax wrapper** (`ai-video/minimax.py`): local H3 backend checked by dry run (workflow as in the comparison
script, >= 124 frames); cloud backend: request building, key redaction and opt-in checked without any API call
(no `--send`, no key used).

## Engine `ltx25` (a cut inside one sung shot) - 0.12.0, 2026-11-20

Scratch copy of the claudia3 test project with one or two shots (`experiments/plugin-github-test/claudia3_ltx25` on the
reference machine), built only with the plugin: `jobs.py --no-depth` -> `night_run.py --phases ltx25` -> `pick.py clips`.
- **s05, 4.4 s** ("Out of the comfort zone, can you survive?"), cut to a frontal medium shot, then to a frontal
  close-up "from a new camera position at the railing": 6 clips (2 wordings x 3 seeds), ~180 s each. No clip cut;
  pick.py wrote "cut missing (0 of 1: a dissolve or no cut)" for all six. Lip scores 0.33-0.42 (the LTX-2.3 seed
  rendered next to them: 0.06, rejected for flicker in the rain).
- **s08 stretched to 7.7 s** ("Europe twenty thirty one, are we still alive? Hey! Hey! Wake up, Baby, wake up now."),
  cut to a frontal medium shot further back on the deck: 3 clips, ~292 s each. All three cut at 5.3 s, on "Hey!", and
  cut again about a second later; after the cut the streak was gone in all three. pick.py: "1 unwanted cut(s)" /
  "2 unwanted cut(s)" plus a canon reason on each. Lip scores -0.10 / -0.04 / 0.18.
- A changed prompt re-rendered the three finished clips and kept the old ones in `ai/ltx25/replaced/` (fingerprints).
- Result: the path works end to end and the picker catches the faults; the engine itself gave no usable take in
  these 9 clips. Details and the earlier hand trial (1 usable take of 7): ai-video `references/multishot.md`.
