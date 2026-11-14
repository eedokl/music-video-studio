---
name: bricks-music-video
description: "Make a brick-film (stop-motion minifigure) music video for a song: plastic-brick sets built from the open LDraw library in Blender, minifigures that sing with lip sync, gesture on the words and bounce on the beat, cameo silhouettes, props and screen gags, cuts on the beat, comic lettering and lyrics, sound effects and the studio look. Use this whenever the user wants a brick film, brickfilm, LEGO-style / minifig / Klemmbaustein / Steine video, a stop-motion toy video for a song, or wants an existing song or part of it 'in bricks' - even if they only attach a song and say 'make it out of bricks'. Also to continue, re-cut or fix such a project (folders with project.json + bricks/<section>.json)."
---

# Brick-film music video

A song becomes a stop-motion brick film: **song-analysis** (timing, words, who sings, mouth shapes) → **creative
brief** → **shot plan** per section (`plan.py`, editable JSON) → **Blender frames** (bricks-3d) → **film-finish**
(lettering, lyrics, sounds, look, film files). Every time is a song second. Own characters only; never call it a
"LEGO" film, no brand logos (the LDraw studs have none).

Scripts (run with `uv run --no-project python ...` unless noted):
`S=${CLAUDE_PLUGIN_ROOT}/skills` – `$S/song-analysis/scripts/{new_project,analyze,voices}.py`,
`$S/bricks-music-video/scripts/{setup,plan,render,compare_reference}.py`, `$S/film-finish/scripts/{overlays,sounds,build}.py`.

## 1 · Interview (short)
Ask only what you cannot hear or guess: the song file (+ lyrics, stems if they exist), which part (whole song or an
excerpt for a pilot), who the figures are (Tim/Lia defaults, or the user's own: shirt colour, hair, glasses …), and
anything they already imagine. Check the machine once: `python $S/bricks-3d/scripts/blender_run.py --check`
(needs config keys `blender` and `ldraw_dir`; see bricks-3d/references/ldraw-setup.md).

## 2 · Song project + analysis
```
python $S/song-analysis/scripts/new_project.py <proj> --song song.wav --lyrics lyrics.txt [--lead vocals.wav]
      [--from 131 --to 150 --lyrics-from "first line" --lyrics-to "last line"] --language de
uv run --no-project --with numpy python $S/song-analysis/scripts/analyze.py <proj>
uv run --no-project --with numpy python $S/song-analysis/scripts/voices.py <proj>
python $S/bricks-music-video/scripts/setup.py <proj> --sections "verse:0-19,chorus:19-41" [--cameo mann:silhouette]
```
Put a marker line like `[Verse 3 - Tim, male lead]` above the lyric lines – it helps voices.py. Read
`analysis/lines.csv` (who sings which line) and fix mistakes in `corrections.json` (the ear wins).

## 3 · Creative brief (do not skip – the reference is a technique, not a template)
Read the lyrics with their times and invent images that come from *this* song, then write them into project.json
and log them with `creative.add_idea(P, "ai", "...", section)` (user ideas: `"user"`, they always win):
- **Set per section** (`sections[].set`: room / stage / rooftop / house / arena / cloud) and mood – vary between
  sections. `house` = the night exterior with a lit window: the whole section is one camera flight through the garden
  into the window (an intro); `arena` = winners' podium (figures on spots 1–3 stand on it), stands, chip mountain with
  the cameo on top; `cloud` = auction above the clouds (lectern, rows of seats, sea of coins).
- **Gestures on words** (`gestures`): chest, open_arms, point (target = anchor or figure), point_cam, reach, shrug,
  cheer, fist, headshake, type, laugh, scare, look, slump, kiss, wave, scratch, nod, jump, puppet, puppeteer. Lines without a rule get
  a seeded singing gesture automatically; listeners look at the singer.
- **Props** (`props`): `cameo` (a figure appears at the set's window/door – e.g. an anonymous silhouette with a white
  grin), `coins` (stack grows one per beat), `hair` (hair flies), `head_pop`, `lights_off`; brick effects:
  `brick_word` (a word of flying 1x1 bricks, optional `fall` = it collapses), `confetti`, `tower` (grows one brick
  per beat), `fall_apart` / `assemble` (a figure falls apart / builds itself part by part). `"nth": -1` = only the last
  occurrence of the word in the section; `"section": "chorus3"` on any rule = only there (escalating gags on a
  repeated word: hair flies in chorus 2, the head pops off in chorus 3).
  More props: `steam` (puffs of white round plates rise from a figure's head – "my brain melts"; `"anchor": "gpu"`
  = from a machine instead; `duration`, `rate`, `burst` = a last big puff), `strings` (marionette strings from a
  puppeteer's hands to the heads of `targets`; the targets jerk like puppets on the beat, the puppeteer works the
  strings, a cameo puppeteer stays in view, the shot is a wide one; `until` s after the word, default section end),
  `coins` with `"from_start": true` (the stack is already there) and `coins_vanish` (all coins gone at once on the
  word – "Ultra abonniert" – or `"one_by_one": true`, one per beat, top first; the shot frames stack and singer).
- **Name signs** on robots/bidders: `figures.<name>.sign: "MODELL"`, per section `sections[].signs: {"bot1":
  "OPEN"}` (wins); `bricks.signs: "auto"` gives every robot without a sign a seeded word from `bricks.sign_pool`.
  Neutral lettering only – a company name is fine as plain text, never a logo.
- **Set changes**: `bricks.enter: "assemble"` (the set builds itself from flying bricks) and `bricks.exit: "collapse"`
  (it flies apart) – a room that rebuilds into a stage is `exit` on the room section + `enter` on the stage section.
- **Monitor screens** (`screen`, room set): text, terminal, heart, code, bar – switched on a word.
- **Lettering** (`gags`, film-finish): short comic words on keywords (HAHA, $$$, TOKENS!), max two at once, corners.
- An ending image for the last section.
Anchors: room – window, outside, monitor, desk, keyboard, coins, gpu, rack; stage – curtain, keyboard, gpu, arch;
rooftop – door, skyline, antenna, parapet; house – window, monitor, desk; arena – podium, chips, stands, letters;
cloud – lectern, coins, seats, letters. When the monitor figure (the computer) sings or announces, every other shot
frames the screen face. Options in `"bricks"`: `flip`, `palette`, `camera: calm|lively`,
`samples`, `jitter`, `idle_screen`, `spots` (who stands where). Same seed → same film; new seed → new take.

## 4 · Plan, look at stills, then render
```
python $S/bricks-music-video/scripts/render.py <section> --project <proj> --stills 24,120,240,400
python $S/bricks-music-video/scripts/render.py <section> --project <proj> [--preview]
```
`render.py` runs `plan.py` (→ `bricks/<section>.json`: shots with times/kinds/cameras, keys per figure, props),
the textures, and Blender with the GPU lock. **Checkpoint:** show the stills (Read the PNGs) – framing, faces
sharp, nothing burnt white, cameo visible, coins/screen right. Edit project.json and re-plan, or hand-edit
`bricks/<section>.json` and render with `--keep-plan`. Drafts: `--percent 50 --samples 16`.
Cuts land on beats near line starts, cameos get their own reveal/detail shot, big moves (fist, cheer, jump) a
low-angle close-up; shots are 1–3 s.

## 5 · Finish (film-finish)
```
uv run --no-project --with pillow --with numpy python $S/film-finish/scripts/overlays.py <section> --project <proj>
uv run --no-project --with numpy python $S/film-finish/scripts/sounds.py <proj>        # gesture/pop sounds (earshot)
uv run --no-project --with pillow python $S/film-finish/scripts/build.py preview <section> --project <proj>
uv run --no-project --with pillow --with numpy python $S/film-finish/scripts/build.py film --project <proj>
```
Set `"lyrics": true` on a section for word-by-word lyrics. **Checkpoint:** watch the preview with the user, then the
film (film.mp4, film_small.mp4 < 30 MB, film_mail.mp4).

## Review list
Lip sync matches the voice (mouth closed in pauses) · cuts on the beat · the singer is in frame when singing · figures
sharp, faces not burnt · cameo readable · lettering never over a face · film length = section length.

Reference test and numbers: [references/reference-tests.md](references/reference-tests.md).
