# Reference tests – bricks-music-video

## Reference
The "Prompts!" brick film (scenes/lego_test of the original studio project): section 7 (verse 3, song 131.0–153.1 s,
`ab_strophe3.py` + `film_lib.py`), hand-written key poses per word, 11 shots, Tim's room at night, the man in the
leather jacket as a grinning silhouette outside the window, heart on the monitor, coins stacking up, lettering and
lyrics added in the final cut. Rendered with EEVEE, quality C, f/22–32, auto exposure per shot.

## Test 1 – rebuild of 131.0–150.0 s with the skill (2026-11-13)
Folder: `experiments/plugin-tests/bricks-music-video/prompts_v3` (outside the plugin).
1. `new_project.py prompts_v3 --song song_full.wav --lead Vocals.wav --backing "Backing Vocals.wav" --from 132.456
   --to 151.456` (song_full has a 1.456 s lead-in, so project time 0 = song 131.0) + lyrics of the 9 sung lines with
   the marker `[Verse 3 - Tim, male lead]`; `analyze.py`, `voices.py`.
2. project.json: section `verse3` 0–19 s, set `room`, figures tim/lia + cameo `mann` (silhouette); `bricks`:
   palette 0, no flip (to match the reference room); the reference's ideas as rules (logged as user ideas):
   gestures on verkaufte/Lachen/Typ (point at mann)/Kichern/Ha/gab (type)/M.I.T (fist)/LLM (Lia kiss)/Küsschen
   (scare)/verkaufen (Lia reach)/Million (shrug, Lia cheer); props: 3 cameos (Typ, Tasche + laugh, Million + cheer),
   coins from "verkaufen"; screen: heart from "LLM"; idle screen = the terminal text; 10 lettering gags.
3. `render.py verse3 --preview`, `sounds.py`, `build.py film`.

Results (script `measure_vs_reference.py` in the test folder):
| what | plugin | reference |
|---|---|---|
| frames / duration | 456 / 19.0 s | same span (section is 530 frames / 22.1 s) |
| shots | 11, mean 1.73 s, 10/10 cuts on a beat | 9 in the same 19 s, mean 2.11 s |
| cuts within 0.5 s of a reference cut | 6/10 | – |
| beats (excerpt analysed alone) | 40, 136 BPM, mean offset 10 ms (max 30 ms) | 42, 136 BPM |
| word times | 48 matched, mean 123 ms, 4 words > 0.3 s (max 0.62 s, "M.I.T.!") | – |
| Tim lip sync | open/closed agree 98.7 % of frames, same Rhubarb shape 67.1 % | Demucs-based assignment |
| Lia lip sync | 143 open frames (backing vocals 141.3–143.0 s) | 1 open frame |
| render | EEVEE 1280×720, 32 samples, ~0.55 s/frame, exposure −0.11…−0.66 stops | 48 samples, −0.03…−0.61 |
| film | film.mp4 5.4 MB, 0 decode errors, look + lettering + lyrics + 17 sound effects | – |

Comparison sheets (test folder): `compare_frames_final.jpg` (raw frames, 11 song times),
`compare_film_final.jpg` (finished film vs brickfilm.mp4), `compare_stills_v1.jpg` (first stills), lip-sync strip
`lipsync_strip_f300-311.jpg` (mouth on ones B→C, body on twos).
Fixes made during the test: cameo shots only start at the cameo (not every shot during it); listeners turn head ±35°
and body 25 % instead of a 60° head twist; wide shots tighter (lens 40, 400–470 LDU: the room ended in frame);
low-angle close-ups stay within 14° of the face axis (the wall top showed).
Verdict: same room, same cameo/heart/coin gags, close framing and timing; shots are a bit shorter and the
lettering uses film-finish's style (smaller, outlined) instead of the reference's big yellow Impact.

## Test 2 – fresh excerpt, different song (claudia-live chorus, song 48.6–63.6 s)
`claudia_chorus`: setup.py `--sections chorus:0-15 --seed 2031` picked the **stage** set; Lia leads (female voice,
78 open-mouth changes), Tim reacts; ideas from the lyrics (storm → lights cut + Tim flinches, "already born" → both
jump + 2031!, "survive" → Tim's hair flies, shrug); camera `lively`. 8 shots (mean 1.88 s, 6/7 cuts on a beat),
spot colours cycle and bulbs chase on the beat, 360/360 frames, film.mp4 5.1 MB, 0 decode errors.
Contact sheet: `contact_claudia_chorus.jpg` – a different set, cast order, camera and gestures than test 1.

## Test 3 – the whole section 7 and the whole song (overnight, 2026-11-14)
Folder: `experiments/plugin-tests/bricks-full` (outside the plugin): `s7/` (section 7 alone), `full/` (whole song),
`tools/` (config_*.py = the project rules, measure_s7.py, lipsync_full.py, full_sheets.py, run_full.sh).

**Section 7 (song 131.0–153.1 s, 22.1 s – the complete finished reference section, not an excerpt).**
`new_project.py s7 --song song_full.wav --lead Vocals --backing "Backing Vocals" --from 132.456 --to 154.556` with
the verse-3 lyrics and their original markers ([Verse 3 - Tim …], [Robotic voice] for "Ha. Ha.", [Tim], …), then
analyze/voices, `setup.py --sections strophe3:0-22.1 --set room --cameo mann:silhouette --seed 131`, rules from
`ab_strophe3.py` + `schrift_strophe3.json` (17 gestures incl. "Woche": Tim slumps / Lia waves, 3 cameos, 9 coins,
heart from "LLM", 10 gag rules → 11 gags), `render.py`, `overlays.py`, `sounds.py`, `build.py film`.

| what | plugin | reference |
|---|---|---|
| frames / duration | 530 / 22.1 s, film 22.1 s, 0 decode errors, 5.6 MB | 530 / 22.1 s |
| shots | 12, mean 1.84 s, 11/11 cuts on a beat, 7/11 within 0.5 s of a reference cut | 11, mean 2.01 s, 3/10 on a beat |
| beats | 44, 136 BPM, mean 10 ms (max 30 ms) from the reference beats | 49 in the section, 136 BPM |
| word times | 51/51 matched, mean 126 ms, 5 > 0.3 s (max 0.62 s, "M.I.T.!") | – |
| Tim lip sync | open/closed agree 98.5 %, same shape 66.8 % (66.7 % where both open), 507 vs 509 open frames | – |
| Lia / computer | Lia 154 open frames (backing vocals 141–143 s) vs 1; computer "Ha. Ha." 11 vs 6 open frames | – |
| coins / cameo / heart | 9 coins from 147.35 every 0.45 s; cameo at 133.1/137.3/148.8; heart from 143.41 | 147.60; 133.3/137.3/148.9; 143.58 |
| gags | 11 at the same words, mean 0.1 s earlier (M.I.T.! 0.6 s – word time) | 11 (one is the original TOKENS PNG) |
| render | EEVEE 1280×720, 32 samples, ~0.6 s/frame, exposure −0.11…−0.92 | 48 samples, −0.03…−0.61 |
Sheets (test folder): `compare_s7_frames.jpg` (raw frames, 20 song times), `s7_film_ours.jpg` / `s7_film_ref.jpg`
(finished films at the same 20 times), `s7_stills.jpg`.

**Whole song (248.4 s, 14 sections).** `new_project.py full --song song_full.wav --lyrics lyrics_original.txt` (all
markers) + stems, analyze/voices, `best_words.py` (refrain 3 had collapsed onto one time), `setup.py --seed 2026`,
`tools/config_full.py` (sections = the reference's 12 + intro split house/room + verse 1 split where Lia builds
herself, snapped to whole frames; sets after DREHBUCH: house → room → stage (room collapses, stage assembles) → room
(Pro) → cloud auction → room → room → room (Max) → stage (Lia) → arena → stage (confetti, PROMPTS! in bricks) → room
(lights out / ULTRA); escalating "Hirn!" via `"section"` rules: scratch / hair flies / head pops off), then
`tools/run_full.sh` (render.py per section, overlays, sounds, build.py film).

| what | result |
|---|---|
| film | film.mp4 248.375 s (reference 248.396), 70.2 MB; film_small 28.8 MB; film_mail 12.0 MB; 0 decode errors each |
| frames | 5961 = sum of the 14 sections, every section complete; EEVEE 1280×720, 32 samples |
| render time | 0.55–1.6 s/frame incl. exposure measuring, ~105 min for the song sharing the GPU lock with other night jobs |
| shots | 122 (house = 1 flight), 101/108 cuts on a beat (strophe2 17/20, refrain3 17/19, others 89–100 %) |
| gags | 81 lettering pops, 134 sound effects, lyrics word by word, 3 transitions (white, glow, white) |
| lip sync vs reference (whole song) | Tim open/closed 80.9 %, Lia 70.5 %, computer 93.3 % (role differences in the choruses) |
Sheets: `sheets/sheet_<section>.jpg` (ours over the reference at 6 times each), `sheets/full_overview.jpg`.
Fixes made during the test: monitor shots for the singing computer (every other shot), `"section"`/`"nth"` on rules,
new sets house/arena/cloud and effects.py, show keys switch instead of easing, overlapping cameos merged, coin stack
moved behind the monitor, stale exposure cache detected, `--blend` creates its folder; song-analysis fix_timing: a
bracket call is placed only within 4 s of its line and spans at most 0.6 s per word.
Not covered at the time: name signs on the robots, puppet strings, steam from Tim's head, the coin stack vanishing at
"Ultra" (all closed in test 4), the iris-out at the end, the post-credits gags.

## Test 4 – the four missing brick gags + the letter N (2026-11-14)
Same folder (`bricks-full`), rules added in `tools/config_full.py`, re-render with `tools/run_gaps.sh` (bridge,
strophe2, refrain1, schluss with the GPU lock, then overlays, sounds, build.py film). New generic options:
`figures.<n>.sign` / `sections[].signs` / `bricks.signs: "auto"` (name signs), props `steam`, `strings`,
`coins` + `from_start`, `coins_vanish`; gestures `puppet`, `puppeteer` (see SKILL.md).

| gap | reference (lego_test) | plugin |
|---|---|---|
| name signs | white chest labels OpenAI/Anthropic/DeepSeek/MODELL (strophe2), OPEN/SAFE/FAST/CHEAP/MODELL (bridge) | same label style (white, rounded, 3 LEDs); 2 robots: OpenAI/Anthropic, OPEN/CHEAP; readable in medium shots, tiny in the bridge's wide shots |
| strings | silhouette's hands → 5 robot heads from "hält" (111.86 film s) to the section end, robots jerk on the beat | from "hält" 111.84 s to the end, 2 robots jerk (`puppet`), the silhouette works them (`puppeteer`), wide shot |
| steam | 14 white round plates from Tim's head 60.4–63.9 s, burst at "(Hirn!)" | 8 puffs from "Hirn" 60.24 s + burst of 4 at 62.04 s, shot on Tim tilted up for headroom |
| coins vanish | 6-coin stack, all gone at "abonniert" (232.2 s) | 6 coins from the section start, all gone at 232.12 s, own "coins" shot (stack + Tim) |
| letter N | – | VERSPRECHEN re-rendered with the fixed N (before it read like a D) |
Film: film.mp4 70.5 MB, film_small 28.8 MB, film_mail 12.0 MB, re-rendered clips bridge/strophe2/refrain1/schluss –
0 decode errors each. Render 82 min for the 4 sections (2946 frames) incl. finish.
Sheets (test folder): `compare_gap1_name_signs.jpg`, `compare_gap2_strings.jpg`, `compare_gap3_steam.jpg`,
`compare_gap4_coins_vanish.jpg`, `compare_gap5_letter_N.jpg` (ref / before / after); script `tools/gap_sheets.py`.
Still different: the reference has 5–6 robots per scene (the project uses 2), the bridge sign in the reference is a
row of lettered 1x1 bricks on pillars (the plugin's brick word is a pixel font), the coin stack stands beside the
monitor instead of in front of it.
