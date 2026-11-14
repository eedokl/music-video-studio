# Reference tests – animated-music-video

Reference: "Prompts!" (German AI song, 4:08), first chorus 38.3–66.7 s, Suno stems (lead + backing), lyrics with
section markers. The reference was built by hand-written project scripts; the skill rebuilds the part generically.

| Check | Method | Result |
|---|---|---|
| Word timing | words matched to the reference sheet (Whisper on the stems), difference of start times | median 0.10 s, mean 0.21 s after the vocal-track repair (before: mean 0.38 s, 16 of 58 words > 0.3 s off, now 10) |
| Who sings | per frame "mouth open" per figure vs. the reference assignment | Tim 84 % frame agreement (precision 93 %), Lia 89 % (precision 99 %); the spoken narrator line now goes to the Computer (reference: Tim) – intended |
| Lip-sync gaps | voice audible but no open mouth, ≥ 0.3 s | 0 |
| Picture | contact sheets at 2, 6, 10, 14, 17, 21, 25 s side by side | same set, layout, screen face, dance on the chorus beats; differences: reference had song-specific props (GPU tower, tier badge) – now possible with `props` and `screen` events; Lia's aura now an option |
| Film | build, look, three output sizes, decode check | 28.4 s, 0 decode errors, ~13 s build |
| Variety | same project with seeds 1 and 2 | dance styles tim/lia: step/bounce vs. twist/arms |

How to re-run: create a project with `new_project.py --from 38.3 --to 66.7 --lyrics-from "Nur noch mehr Prompts
(Prompts!)" --lyrics-to "Nur noch mehr Prompts (Nur"`, run analyze/voices, one `stage` section, render, build;
compare with the reference chorus video frame by frame.

## Second song (generality)

"Comfort Zone" / "Europe 2031" (rock, German/English mix, no stems), first chorus 47.5–71.2 s, `--language auto`.
Whisper with VAD recognised only 8 of 47 lyric words; the automatic retry without VAD recognised 32. earshot heard
the female voice in 39 of 46 windows, so Lia sings every line and Tim reacts with gestures on words (scare at
"storm", point at "Zukunft", scratch at "survive", cheer at "Hey"). Song-specific ideas recorded in project.json
(storm warning and "EUROPE 2031" on the screen, warm aura instead of the hologram look). 23.7 s, 0 decode errors.

## Scene features (typing, guitar, meter, lights, silhouette, inset, panels, caption, 48 fps)

Each feature was rebuilt on the matching section of "Prompts!" as its own excerpt project (`new_project.py --from/--to
--lyrics-from/--lyrics-to`, Suno stems from `stems_alt`; Whisper small on the CPU because the GPU was busy) and
compared on contact sheets at the same song times (reference v2 section video left, plugin frames right).
Test folder: `experiments/plugin-tests/scene-features/` (`cmp_<section>.png`, `compare.py`).

| Section (song s) | Keys used | Matches | Differs |
|---|---|---|---|
| Verse 1, room (11.6–38.3) | `actions` typing `when: listening`, gesture scare "limit", `silhouettes` word "limit" | own arms in front, hands visible on the desk keyboard, keys light, 3 typing spans while the Computer narrates; scare interrupts typing; antagonist rises inside the window between sky and wall | reference figures bigger (set scale), reference has no silhouette here (shown as a generic test) |
| Announcement close-up (153.0–157.0) | `shot: screen`, `screen_meter` fill "pro-limit"/empty "max", badges PRO→MAX | bar green 55 % → full + red + blinking at "Limit" → nearly empty at "Max"; badge pops at "Max"; dimmed room behind, push-in | plugin screen a bit bigger, mouth larger (scales with the screen) |
| Verse 3, spotlight (131.38–153.0) | `light: spotlight`, `actions` guitar `when: singing`, `silhouettes` line "Ich verkaufte" | dark stage, Tim lit in the middle with air guitar (strum arm in front), Lia appears only in her own violet light when she sings, giant shadow with grin on the left during the first line, screen dimmed | guitar colour from the seed (black vs red) |
| "Seit wann" (157.0–163.3) | `light: {spotlight, lead: tim}` | same layout as reference; without `lead` the figure singing most (Lia) is the lit one | reference fades Lia out darker |
| Bridge (163.3–178.7) | `kind: panels` with the reference panel PNGs, `inset`, `caption` | 7 of 7 detected hard cuts on exactly the expected frames (line starts, frame difference 30–60 vs median 2.5), inset with Tim's bust and lip sync, panel push-in + roll | Whisper small merged "Wer wird reich?/Der Typ" (same start) -> 8 panels instead of 9; reference's shout words come from the gag overlay (not set here); caption box is new |
| Chorus 3 + final (178.4–211.8) | `light: {disco, marker: "final chorus"}`, typing `line: "Mit den Händen"` | keyboard stand appears with typing on both "Mit den Händen" lines; coloured cones alternate per beat and confetti start exactly at the [Final Chorus] marker; camera pulse | palette from the seed (ice vs neon) |
| Ending, room (211.8–246.9) | `light: night` from 0.2 s until "willkommen", meter fill "quota"/empty "abonniert", badge ULTRA | dark from the stop, the screen glows over the darkness, light again after "Willkommen zurück"; red bar at "Quota", ULTRA badge at "Ultra" | reference turns the whole screen red; Lia only for the last line there (no rule for that yet) |

Numbers: typing writes one key click per strike into `actions_<section>.json` (refrain 3: 29 clicks, sounds.py mixes
them: `fit/key/medium|thock|lubed` ~-21 dB); `"at": "silence"` finds the abrupt stop of the full song at 211.9 s
(reference: 212.0) - in an excerpt starting at the stop there is nothing before it, so the test used `"from"`.
Regression: refrain1 and comfortzone projects produce byte-identical `.sif` and actions files with the new scene.py.
Split of scene.py into `scene_*.py` modules + `SceneContext`: all 12 sections of the "Prompts!" project, 12 variant
sections (desk, colour set, disco + spotlight, night, show, pulse, panels with figures / auto / 4:3, external with and
without inset, screen shot) and the e2e projects gave byte-identical `.sif`, actions files and printed lines.

Second song ("Comfort Zone", chorus 47.5–71.2, seed 2031, no stems): `storm` section with disco + Tim's air guitar while
Lia sings (`when: listening, in_chorus: true`) + a STORM meter (segments, fills at "storm", resets at "Zukunft") +
a silhouette peeking at the back at "Zukunft"; `wakeup` as auto panels (Lia close-ups with lip sync, caption box).
23.7 s film, 0 decode errors.

48 fps (`fps48.py`, project "Seit wann" spotlight + bridge panels, `camera_move` on the bridge): RIFE v4.6 under the
GPU lock, 1042 frames at 48 fps, 362 in-betweens only in the bridge, its 7 panel cuts kept hard (the frame before each
cut doubled: pair difference 0.01 vs 1.4 inside the flight), the spotlight section doubled (pair difference 0.02),
0 decode errors. The reference interpolated its whole bridge range, i.e. also across its cuts.
