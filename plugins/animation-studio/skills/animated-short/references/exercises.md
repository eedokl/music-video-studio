# Exercises and reference scenes

Each entry: what it trains, how to build it with the plugin, the key numbers that worked. All at 24 fps, default
16×9-unit view unless noted. Build in a scene folder from `short.py new` (never inside the plugin).

## Bouncing ball (timing, spacing, squash & stretch, arcs)

Code-drawn: a red circle (radius 0.6, drawn with its bottom at the group origin so it squashes on the ground) + a
highlight + a shadow group on the ground.
- Height keys (frame, height above ground 2.5 below centre): `(0, 5.0) (14, 0) (26, 3.0) (36, 0) (44, 1.6) (51, 0)
  (56, 0.7) (60, 0) (64, 0.2) (67, 0)` – contacts `"linear"`, apexes `"halt"`.
- x separately and linear: −6.5 → 4.5 at frame 60, then rolls out to 5.2 at 72 (`("linear", "halt")`, `"halt"`).
- Scale per contact c (deformation k = max(0.15, 1 − 0.22·i) for the i-th contact): c−2 (1, 1); c−1 stretch
  (1 − 0.18k, 1 + 0.28k); c squash (1 + 0.4k, 1 − 0.38k); c+1 stretch (1 − 0.12k, 1 + 0.2k); c+3 (1, 1) – all
  linear around the contact.
- Shadow: scale (1 − 0.11h, (1 − 0.11h)·0.25), amount 0.55 − 0.08h with the same interpolation as the height.
3 s (72 frames). Variation from the seed: ball material (rubber / bowling ball / balloon – heavier = fewer, lower
bounces and less squash), start height, direction.

## Flour sack (weight and attitude without a face)

A sack as `shape()` with 4–6 bline points, two "ear" corners as small groups with `spring_follow`. Train poses: drop
and land (squash 0.7, ears follow through), jump (anticipation 10 frames down 0.8, stretch 1.2 at take-off), a sad
slump (lean −12°, sy 0.9 held with breathing). Keep the volume (`squash_keys`) – the sack must never look like it
gains or loses flour. No eyes: all acting by silhouette, so check the contact sheet as black shapes (squint).

## Take (surprise)

Any character: 3–4 frames anticipation squash (0.86, eyes narrowing), 3–4 frames to the stretch peak (sy 1.22, eyes
1.25–1.35, mouth "O", lean back +8°), 8–15 frames settle (0.97 → 1.0 with halt), pupils already on the cause 4–6
frames before. In "Pip and the Flower" the bloom at frame 72 triggers the take 70–90.

## Pip and the Flower (6 s) – `toon-2d` template `example`

Beats: 0–36 two hops in (12–14 frames each, contact squash 0.82/0.8/0.68), settle; 46–62 discovers the bud, leans
−12°; 60–72 the bud trembles (±4° every 2 frames); 72–86 bloom with overshoot (scale 0 → 1.3 → 0.9 → 1.05 → 1) and the
take; 86–131 crouch (0.7), jump for joy (2.3 units, 18 frames), landing 0.64, settle; 131–144 hold + blink.
Baked: only the antenna spring. Build: `short.py new pip --template example`, run `make_scene.py`, render with
`--contact 0,15,36,52,74,97,109,118,140`.

## Fips chirps (5 s) – `toon-2d` template `figure`

SVG figure rigged with `wrap=`: 0–20 looks around (head ±8°, pupils ±0.07); 20–48 a small hop (0.9 units, 14
frames) with flapping every 3 frames (±55°); 48–72 tilts the head 14° and blinks; 72–96 "peep peep" (lower beak
22–26°, head nods −6°/+2°, wings twitch 18–20°); 96–120 happy flapping every 2 frames (±70°), a second hop (0.55),
landing squash 0.8. Set `park`, view `-4.98 5.0 4.98 -0.6`. Sounds: synthetic chirps or `mallet/celesta` at high
pitch on the beak openings.

## The Lichtung (forest clearing) – multiplane camera (6.25 s)

Pip on a forest path; an autumn leaf sails in (baked fall path), Pip notices it ("Oh!"), hops twice under it, the
leaf lands on his head (frame 98) and rocks, he squints up, smiles and jumps for joy with the leaf fluttering.
Technique: background = `paint_clearing.py` layers (sky 120, far trees 70, middle trees 36, meadow 26, light rays 22
additive, dark leaves 9 with overscan 1.36), Pip rendered alone with alpha at the meadow's depth, camera
`(0: x −1.2, y 0.25, z 0) → (50: −1.2, 0.3, 0.5) → (96: 0.2, 0, 2.0) → (150: 0.4, −0.3, 4.5)`, overscan 1.13.
Sounds (peaks on frames): 26 `mallet/celesta` G5 (notices), 60 `swish/soft` (take-off), 72 `ui_pop/soft` F#4
(landing), 84 `ui_pop/step` D4, 98 `mallet/glock` A6 (leaf lands – "ting"), 120 `swish/bright`, 132 `ui_pop/soft` C4.

## 2.5D comic flight (11.5 s)

A comic page with three panels (wide establishing shot as multiplane layers; close-up with blurred background +
bubble "Oh!"; relief from a flat image + depth map + bubble "Juhu!"), the camera flies from the page into each panel
and back out. Built with `comic_page.py` (page, bubbles, crops) and `render_multiplane.py comic.json --page comic25d`;
config and camera keys in `toon-2d/references/multiplane-and-comic.md`. A good ending for a short: the page with all
panels as the last frame.

## Grease Pencil Pip (4 s) – hand-drawn look

`toon-2d/assets/blender_gp_example.py`: Pip drawn on twos with pressure and line boil, anticipation 18–28, jump 28–44
(parabola, stretch 1.25), landing squash 0.7, settle with a damped cosine, blink 70–72, painted layers at depth,
camera dolly. Use it when the user wants a sketchy, hand-drawn feel or wants to keep drawing in Blender.

## The Perch (6.5 s) – a fresh idea made with this skill (seed 7003)

Fips mistakes Pip's head for a perch and his red antenna ball for a berry: swoops in (22–50), lands – Pip squashes to
0.78 under him and does a take; Fips eyes the ball, leans back (84–88) and pecks (90) – the antenna whips
(`antenna_kicks=[(90, 32)]`), Fips startles, crouches and shoots straight up (seed pick); Pip shrugs and blinks (seed
pick). Contact: Pip holds x and lean while Fips' feet are baked from Pip's squash per frame.
