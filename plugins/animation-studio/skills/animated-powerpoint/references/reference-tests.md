# animated-powerpoint – reference tests

## 1. Full rebuild of the ai_efficiency clips (2026-11-14)

Reference: `scenes/ai_efficiency` (read only) – the presentation with Helmut, Hans, Fritz and Felix and the film
"Who keeps changing my office?" (V2 final; the LTX video-model trials were rejected and deleted, they are not part of
the reference). Every clip the reference made from the slides was rebuilt with the plugin only, full length, in
`experiments/plugin-tests/ppt-full/` (tools there: `compare.py` side-by-side + per-frame difference, `audiocmp.py`
loudness + onset correlation, `refsheet.py`). Inputs taken from the reference project: the pptx, the narrator
voice files (user audio), the painted office set and the last frame of S12 (user images).

```
deck.py praesentation.pptx --slides 1,2,3,4,5,6,7,9,11,13,15,17,19,20,21,22,25,26 --out deck
figures.py --deck deck/deck.json --slide 5 --names helmut hans fritz felix --upscale 4      (Real-ESRGAN)
parts.py figures/<name> --auto, then parts.json by hand from the grid images (tail/arm/shell/wing polygons, pivots)
mouth.py figures/<name>                                                        ("mouth" in parts.json)
clip.py clips/probe_fritz/clip.json        clip.py clips/meet_the_cast/clip.json   (styles, narration, time specs)
intro.py clips/intro/intro.json            outro.py clips/finale/outro.json        clips/s03_office/make.py (scene.py)
```

| Check | Result |
|---|---|
| Slide export (18 slides) | clean slides vs the reference's PowerPoint exports 0.00–0.66/255; slide 5 0.003/255 |
| Upscale | Real-ESRGAN result identical to the reference `cast_x4.png` (0.0), also through the shared `ai-video/upscale.py` |
| Parts (hand polygons from `parts_check.png`, not copied from the reference) | rest pose vs original 0.29–0.40/255 in the silhouette (reference parts 0.41) |
| Mouth stages | rest pose vs head 0.31–1.04/255; open grins (Fritz, Hans), smile line with tongue (Helmut), beak (Felix) |

| Clip (frames) | Events vs reference | Picture (480×270 grey, mean / max) | Sound |
|---|---|---|---|
| Probe "Fritz steps out" (192) | identical: look 25/34, crouch 56, take-off 68, pop 74, land 98, fists 117/128, tag 140 | frames 0–24 0.3; whole clip 12.9 / 20.8 – a constant 5–14 px camera offset: the probe's hand-set foot point is 0.07 world units right of the measured one (S2 and all later reference scenes use the measured point like the plugin) | onset corr. 0.97, 11/12 peaks within 2 frames, −29.4 LUFS both |
| Meet the cast (603) | identical: narration 56/176/280/364, pops 74/159/280/479, landings 98/188/301/495, tags 102/194/305/525, sparkles 223/226, waddle 390/398/406, stuck 416, beat 463, head shake 503, group 539, end 602 | automatic camera 28.5 / 51.9 (framing differs: the reference shot list was hand-made); with the reference shot list and landing places given as `camera` / `land` keys (`clips/meet_the_cast_refcam`): 9.9 / 15.8 – the rest is paper-bit scatter, idle noise and line boil | onset corr. 0.996, 11/12 peaks, −18.3 vs −18.2 LUFS, 57 cues (ref 53 + 4 lines) |
| Intro S0/S1 (405) | flips 59… vs 58… (Whisper word time, 1 frame), card 159, strike 163, title words ±3, wobble 347–373, turn 376–400, end 404 | 2.9 mean, median 0.23 (max 91 on the flip frames that are one frame late); last frame vs S2's first 3.2 | onset corr. 0.99, 10/12 peaks, −18.0 LUFS both |
| Finale (162) | wink 99/101/108/110, iris 80–98, title 126 | 0.89 / 7.5 (eye measured at 2329.5/944.2 vs hand-set 2329/943 → ≤ 1 px) | 12/12 peaks, −32.3 LUFS both |
| Scene S3 office (226) | identical: fade 73–97, nod 155, Helmut's late nod 195, Fritz babbles on 205, end 225 | 3.5 / 7.9 (frames 0–72 0.0) | onset corr. 0.98, 12/12 peaks, −18.0 LUFS both |
| Walk + lip sync test (180, `clips/walk_test`) | Fritz hops across the office with `steps()` (bob, squash, rocking) and speaks a reference line: Rhubarb → mouth stages | – | open-mouth frames vs voice activity: agreement 0.88 |
| Film cut of the rebuilt clips (film-finish `cut.py`) | shot starts 0 / 405 / 1008 / 1234 = the V2 film's starts | 0 decode errors in all three sizes | – |

Fixes from this test (all in animated-powerpoint): acting styles flutter/hop/stuck + gestures look_up/wag/shake
(`routines.py`); narration + word time specs; reactions (eyes follow, cheering), group finale, tag hold; camera side
away from landed figures and a closer next-figure shot; line-up tags small and on +x (they covered the neighbour);
sparkles on the glasses rim, additive (white on white was invisible); sound step; deck intro, outro, scene stage, mouth
stages + lip sync, white soft-edge clean-up; light maps ran out of RAM with 4 figures × 603 frames (all CPU threads
at once, float64) → bounded threads, float32; Whisper words without PyAV (version clash) → own decode; own camera
keys (`camera`) for a fixed shot list. Backward compatible: the single-figure probe and the 4:3 "return" clip produce
identical stage values as before.

### Scenes S4–S12 as recipes (2026-11-14)

The remaining scenes were rebuilt as reusable recipes (`recipes/`, index `recipes.md`), each run on a clip folder
with the reference voice files, script texts and painted sets copied in (`tools/recipe_inputs.py`), the reference
cast in `recipe.json`, everything else the recipe defaults. Compared with `tools/cmp_recipes.py`: reference frames
vs plugin frames (480×270 grey, mean / max), ton.wav loudness + onset correlation, decode check of the mp4.

| Scene (recipe) | Frames ref / plugin | Events vs reference | Picture mean / max | Sound LUFS ref / plugin, onset corr., peaks |
|---|---|---|---|---|
| S04 `s04_rumor` | 481 / 481 | lines 12/167/233, dream 68, thought 165, double take 72/88, cuts 230/283/321 identical; wing 104 (ref 106), last cut 375 (376) | 12.87 / 70.37 | -17.2 / -17.7, 0.982, 10/12 |
| S05 `s05_split_screen` | 520 / 520 | lines 14/113/257/359, split 237, takes 245/254, info card 195, question 415, deadpan 501 identical; bot 64 (65), cards +1 | 8.61 / 39.07 | -18.4 / -18.8, 0.995, 10/12 |
| S06 `s06_three_parts` | 625 / 625 | all events identical (hall jump 74, stop 58, slide 60; office lines 12/168/277, check 102, confetti 150; machine stops 4/18/40/76/100, rim 102, counters 106); 100+366+159 frames | 5.95 / 20.69 | -16.7 / -16.7, 0.98, 10/12 |
| S07 `s07_night_holograms` | 412 / 412 | lines 14/105/319, rocket 87, prompt 105, app 164-189, glitch 389 identical; word panels 31/54 (32/53) | 2.17 / 4.66 | -18.4 / -18.3, 0.982, 12/12 |
| S08 `s08_coin_rain` | 408 / 407 | guide 14, guardian 96 identical; narrator 206 (207) - the guardian line measures 1 frame shorter, everything after -1 | 8.02 / 53.87 | -16.8 / -17.0, 0.564, 9/12 |
| S09 `s09_progress_bar` | 380 / 380 | lines 12/68/176, learn 270 identical; caught 214 (213), light 216 (215), sag 282 (288: Whisper puts 'But' after a pause 6 frames early) | 9.92 / 54.77 | -17.3 / -17.7, 0.982, 11/12 |
| S10 `s10_islands` | 1053 / 1053 | all 7 lines, calls 378/535/686/790, data 314 identical; drift 61 (62), names 926/939/955/974 (927/939/955/971), hesitant land 986 (983) | 1.04 / 8.84 | -17.8 / -17.8, 0.994, 11/12 |
| S12 `s12_together` | 207 / 207 | all events identical (chain 28-52, pulse 80, bots 12/36/60, cheer 152, head confetti 178) | 4.36 / 6.14 | -18.5 / -18.6, 0.988, 11/12 |

Why the remaining picture difference: (1) the reference idle motion (weight shift, head sway) was seeded with
Python's per-process string hash, so it cannot be reproduced; in wide shots it is the whole residual (edge pixels
only), in close-ups it is magnified; (2) Whisper large-v3 word starts differ from the reference word list by 1–2
frames for most keywords and by 5–6 frames for sentence-initial words after a pause ("But", "They") – camera moves
and pops keyed to those words shift with them; (3) hologram panel contents in the reference were random per run.
Sound: voice pans of the reference dialogue are not available in `sound.py` (centred voices), the rest identical.

Variation check: `s04_rumor.py` with another cast (explorer = Fritz, guide = Helmut, guardian = Hans, builder = Felix),
seed 7 and new cloud texts via recipe.json only – renders without changes (star eyes land on Felix's pupils behind
the glasses, the thought keeps Helmut's line mouth closed); `clips/s04_variant`, 0 decode errors.

Fixes and generic features from this test (animated-powerpoint only): `props.py` (all drawn props, pixel-identical
to the reference textures where the reference was deterministic); scene.py `painted_set`/`set_point`, `pupils`,
`head_top`, `mouth_rest`, `confetti`, `arc`, `cut_camera`, `post` hooks + `frames_post`, `split_frame`, `join`,
`sound(align="start")` (peak measured from the earshot file), contact shadows + floor texture for scene figures
(`clip.room_textures`, shared with the step-out clips, identical output), `recipe_config`, `save_events`; bug fixes:
set images outside the scene folder could not be loaded by the page (now copied into `tex/`), the three.js render
timed out on long scenes (timeout scales with the length), narration keywords that Whisper joins ("chat bot" →
"chatbot") were not found (prefix fallback).


## 2. Fresh deck (generalisation)

`fresh/make_test_deck.py` builds a 4:3 pptx with two drawn transparent pictures ("Pip": pear-shaped, waving arm,
orange scarf; "Mo": a mug with face and handle) plus title and text box. Then:
deck.py → figures.py `--upscale 2` (Lanczos) per picture → `parts.py --auto` (head and pupils found automatically;
for Pip one hand edit: arm polygon + pivot + `split_fill`) → clip with Pip `step_out` (wave, tag "Pip / Plans"),
Mo `watch`, `"ending": "return"`.

| Check | Result |
|---|---|
| Mug handle (separate blob) | attached to Mo automatically |
| Auto rig | Pip: head + both pupils; Mo (no neck): head above the eyes; rest pose 0.03/255 |
| Output | 1920×1440 (deck aspect 4:3), 244 frames, 10.2 s |
| Clean in | first frame vs. slide 0.53/255 |
| Loop | last frame vs. first frame 0.0 – seamless |
| Fix from this test | the name tag left the narrower 4:3 frame → tag distance scales with the aspect; the tag now holds 36 frames before the hop back |
| 2026-11-14 | re-planned with the new plan: stage values identical (244 of 244 frames) |
