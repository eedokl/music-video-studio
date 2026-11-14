# Status update (2026-11-14, after the overnight runs)

All 17 MISSING items of the first inventory are now covered, except the ones listed at the end:
- Presentation scene stage, lip sync for raster slide figures, deck intro with page turns, walk cycle, soft-edge
  clean-up → animated-powerpoint (scene.py, mouth.py, intro.py, outro.py, routines.py)
- Film cut without a song, film music, SRT/VTT, voice tempo → film-finish cut.py, score.py, subtitles.py; voice tempo.py
- AI clip checks, LTX vocal preparation, typography shots, crowd recipe, Wan clip placement by mouth curve, long
  InfiniteTalk takes, shared Real-ESRGAN upscaler → ai-video / claudia-music-video (mouth.py, clips.py, typo.py,
  ltx.py, infinitetalk.py, upscale.py)
- Brick sets and effects (house fly-in, cloud auction, arena, room rebuilding into the stage, brick words, confetti,
  figures falling apart / assembling) → bricks-3d (layouts.py, sets.py, effects.py)
- Comic caption box typing in time, letter-by-letter lyrics with stretched held words, picture gags → animated-music-video
  captions.py, film-finish overlays.py
- Plus: comic break-out (toon-2d breakout.py), 2D→3D morph (figure_3d.py), end credits with outtakes (credits.py),
  all reference transitions (transitions.py), Shaders looks/iris (shaders_render.py), pop-up version, second audio,
  48 fps (fps48.py), Kdenlive hand-off (edit_handoff.py), scene features (typing/guitar arms, usage bar, spotlight /
  disco / night, silhouette, narrator inset incl. over external sections, fast panels, heartbeat pulse, per-line lyric
  styles, exact/regex word triggers, per-section filters).
Second update (2026-11-14, rest points): everything above is built now.
- HuMo / MiniMax wrappers, mic repair (ai-video humo.py, minimax.py, mic_repair.py; claudia pick.py --repair-mic)
- brick name signs, puppet strings, steam, vanishing coins (bricks-3d textures.py / effects.py, bricks-music-video plan.py)
- ppt scenes S4–S12 as recipes (animated-powerpoint recipes/, props.py)
- effects that had NO script of their own in the reference (found by watching, not by this inventory): comic caption
  box per panel (captions.py "group"), steam from a head and the context window (scene.py "steam", screen "window"),
  inset hidden when another figure sings (scene.py "hold"), filling lines nobody heard (best_words.py --fill),
  held-note stretching anywhere in a line (held_notes.py detect), refined tempo (hits.py refine_tempo)
- the three sound mixers are one: studio-core sfx_mix.py (film-finish sounds.py, animated-short sfx_track.py,
  animated-powerpoint sound.py are thin front ends; outputs identical within 0.1 %)
Lesson: an inventory of SCRIPTS misses effects hidden inside scene scripts - use video-review ref_check.py
(effect checklist + dense strips at every event) when rebuilding a reference.

# Script inventory – reference projects vs. the animation-studio plugin

Audit of 2026-11-14 (read-only on the projects). For every script that was part of a **final, working pipeline**
of a reference project, the table names the plugin file that covers it. Backups (`*.vor_*`), one-off probes and
abandoned variants are not in the tables; they are listed in one line each under "Abandoned / probes".

Status values:
- **covered** – the plugin file does the same job (possibly generalised, English, config-driven).
- **partial** – the core is covered, a named piece is not (the piece is also listed as MISSING when it matters).
- **in progress (agent)** – being added right now by another agent; "on disk" = a first version already exists.
- **MISSING** – nothing in the plugin does it; what is lost is stated.
- **not ported** – deliberately left out (reason given: project-specific data, superseded, rejected tool).

## Summary

| Status | Rows |
|---|---|
| covered | 102 |
| partial | 22 |
| in progress (agent) | 13 (3 rows already on disk: `breakout.py`, `figure_3d.py`, `shaders_render.py`; 10 not yet: `credits.py` ×2, `fps48.py`, 7 scene.py features) – the iris transition is on disk and counted as covered |
| MISSING | 12 rows = 17 distinct missing items (the list below also names items that sit inside partial rows) |
| not ported | 8 |

What is on disk from the parallel agents (checked 2026-11-14): `toon-2d/scripts/breakout.py` (745 lines),
`toon-2d/scripts/figure_3d.py` (646), `film-finish/scripts/shaders_render.py` (420) + `scripts/shaders/`,
`film-finish/scripts/transitions.py` with `"kind": "iris"` and `"shaders": true`. **Not yet on disk:**
`film-finish/scripts/credits.py`, `animated-music-video/scripts/fps48.py`, and none of the new `scene.py` features
(typing/guitar arms, usage bar, spotlight/disco/night, silhouette, narrator inset, fast bridge panels) – `scene.py`
has no code for them yet (424 lines, no matching keywords).

### MISSING, most important first

1. **Generic scene stage for presentation films** (ai_efficiency `buehne/szene.py` + `szene25d.html`): a 2.5D
   room with painted set layers, foreground layers, several rigged slide figures, sprites attached to figures
   (bubbles, star eyes), steam, light tint/rim for night scenes, movable set layers. `animated-powerpoint` only has
   the step-out routine (`stage25d.html`); scenes S3–S12 of the reference film cannot be rebuilt.
2. **Lip sync for raster slide figures** (ai_efficiency `figuren/make_mund.py` + `buehne/mund_sync.py`): 8 mouth
   stages cut from the original drawing (grin squashed column-wise under the upper lip, beak hinge, dark opening
   under a closed smile) and Rhubarb → stage keys. The animated-powerpoint SKILL hands dialogue to
   talking-character, but that skill only rigs SVG figures – slide figures cannot speak.
3. **Generic film cut for non-song films** (old skill `assemble_film.py`, ai_efficiency `schnitt/make_film.py`):
   shot list with stills, clips that keep their own sound, a music bed with ducking, crossfades/wipes/zoom/iris
   between scenes, version variants (letterbox, grade, light leaks). `build.py` only cuts sections on a song
   timeline; `edit_handoff.py` only writes otio/mlt. Presentation films, dialogue films with several scenes and
   short films that join scenes have no cut.
4. **Clip QA for AI video** (claudia-live `v2_auswahl.py`, `v4_messung.py`): hidden scene cut (frame jump > 6 levels
   and > 4× median), frozen stretch (≥ 12 frames nearly still), motion score – used to reject takes before picking.
   `pick.py` only measures lips and canon; jumped or frozen LTX takes pass unnoticed.
5. **Brick-film sets and effects beyond room/stage/rooftop** (lego_test `teil_a.py`, `teil_c_anim.py`,
   `ab_intro.py`, `ab_bridge.py`, `ab_refrain1.py`, `ab_strophe2.py`): house exterior with a fly-through into the
   window, arena, cloud auction, the room rebuilding itself into the stage in stop motion, single bricks moving on
   twos, lettering built from bricks, flying bricks, confetti, a figure falling apart brick by brick.
6. **LTX input-vocal preparation** (claudia-live `bewegung_test_b.normalisieren`, used by `live_v2/v4/v5`): vocal
   window starting in a silence, −16 dBFS RMS, peaks ≤ −1 dBFS, 15 ms ramps. `clips.cut_audio()` only cuts.
7. **Typography shots in the Claudia cut** (trial `schnitt.py`, live `schnitt.py`): NEWSFLASH with ticker, stamps
   on the sung word, split-flap departure board, stamps on the stage screen. `render_shots.py` has only the AI label.
8. **Crowd recipe for LTX** (claudia-live `publikum_test.py` winner A → `publikum_rest.py`, `live_v4.py`):
   `img_compression` 42 + "A cinematic scene of" against frozen crowds. `ltx.py` hard-codes `img_compression` 18.
9. **Caption box that types the lyric in the rhythm of the singing, per comic panel** (prompts_song
   `comic_s2/compose_s2.py`): described in animated-music-video `references/techniques.md`, but no code; the
   lyrics overlay box at the bottom is the nearest substitute.
10. **Wan clip with a mouth placed by its mouth curve** (trial `schnitt.py` + `neuschnitt/abgleich.py`,
    `treffer.json`): entry point and speed of a non-lip-sync clip chosen so the mouth follows the vocal curve.
11. **Voice tempo tightening** (ai_efficiency `ton/tempo.py`): shorten pauses > 0.3 s, cap words per minute,
    per-speaker atempo, fixed silence at line ends. `voice.py` only has pitch/fx.
12. **Film music for films without a song** (ai_efficiency `schnitt/make_musik.py` numpy score per scene mood;
    `make_musik_flott.py` ElevenLabs Music cues laid on the scene lengths).
13. **Deck-intro page turn** (ai_efficiency `s00_intro/make_intro.py` + `intro25d.html`): slides flip, keywords
    revealed on the narrator's words, title typed word by word, seamless hand-over to the first step-out scene.
14. **Shared Real-ESRGAN upscaler** (prompts_song `comic_s2/flux_einbau.py`): upscaling painted panels before depth
    estimation. The only implementation is `esrgan()` inside `animated-powerpoint/scripts/figures.py` – not a
    building block, so toon-2d / animated-music-video comic verses cannot use it (CONVENTIONS: shared code goes into
    a building block).
15. **Long InfiniteTalk takes** (claudia-live `live_v3_bridge.py`, `v5_mikro.py`): one 12.7 s take over the bridge
    instead of four cuts. `ai-video/infinitetalk.py` renders one pass (≤ ~5 s); chaining with motion frames is
    "not wrapped yet".
16. **SRT subtitles from Whisper** (old skill `transcribe.py --srt`). No plugin script writes .srt (subtitles are only
    burned in by `overlays.py`); the English-subtitle idea from the Prompts! making-of has no tool.
17. **Lyric overlay: letter-by-letter reveal and held words that stretch with the voice** (prompts_song
    `make_lyrics_track.py`, "meeeehr Proooompts"). `overlays.py` reveals whole words and highlights the current one.

Smaller gaps folded into "partial" rows: drawn gag icons (kiss mouth, chip, $$$) as pop-up pictures, walk cycle
for slide figures, white soft-edge clean-up of slide parts, HuMo / MiniMax rescue wrappers, mic-repair pass for
Claudia start images, "share of stills" metric, procedural room/stage painters.

### TOOLS.md check

Programs and models used by the plugin's scripts or by the reference pipelines that are **not (correctly) in TOOLS.md**:
- **Wan 2.2 TI2V 5B** and **LTX-Video 2B 0.9.8 distilled** (+ t5xxl / umt5 text encoders) – used by
  `ai-video/comfy_video.py`; no row.
- **Qwen-Image 2512** (lettering inside images) – `comfy_image.py --model qwen`; no row.
- **SDXL Base 1.0** – supported by `comfy_image.py --model sdxl` (style LoRAs); TOOLS only lists the rejected
  watercolour repaint, not the model as an option.
- **InfiniteTalk** row says "no wrapper in ai-video yet" – stale: `ai-video/scripts/infinitetalk.py` exists. Its
  model files (Wan2.1 I2V 14B 480p, LightX2V LoRA, wav2vec2, umt5) are only in the script docstring.
- **HuMo 1.7B / MiniMax H3** are listed as optional, but no plugin script calls them (see partial row).
- **RIFE** is listed but has no `check_tools.py` key yet (fps48.py in progress); **Real-ESRGAN** has the key.
- Python packages missing from the list: **scipy**, **scikit-image** (animated-powerpoint, figure_3d),
  **transformers** (estimate_depth).
- Used only by reference projects, not by the plugin, and not mentioned: **ElevenLabs Music API** (ai_efficiency
  score), **MuseTalk**, **LatentSync** (early lip-sync tests in `tools/lipsync`, abandoned), **Wan 2.1 I2V 14B +
  LightX2V** as a crowd model (claudia-live test B, rejected), **pycairo** (experiment 02, abandoned).
  Everything else used (Synfig, Inkscape, Rhubarb, Blender, Krita, Kdenlive/melt + OTIO, earshot, ComfyUI, FLUX,
  Qwen-Image-Edit, LTX-2.3, Wan2.2-S2V, Depth Anything, MediaPipe, Real-ESRGAN, RIFE, Demucs, Whisper, Qwen3-TTS,
  Piper, ElevenLabs TTS/SFX, System.Speech, PowerPoint COM / PyMuPDF, Node + headless Edge/Chrome, Shaders,
  LDraw, Bark/Animated Drawings/Pencil2D as "not used") is listed.

---

## 1. prompts_song – "Prompts!" (animated-music-video)

Final pipeline (MAKING-OF steps 22–51): `render_all_v2.sh` → `make_full_cut.py` (cut → sounds → title/transitions →
credits → DE/EN → pop-up, optional 48 fps).

| Reference script | Role in the pipeline | Plugin counterpart | Status |
|---|---|---|---|
| `merge_word_times.py` (+ old `track_read.py` on the stems) | word times from lead + backing stems → `song_sheet_stems.json` | `song-analysis/analyze.py` step 3 (`track_read.py`) + `fix_timing.py` (calls from backing-stem bursts) | covered |
| `gender_track.py` (on the lead stem) | earshot male/female every 0.5 s | `song-analysis/analyze.py` step 5 → `gender.json` | covered |
| `assign_voices_v4.py` + `zuteilung_korrekturen.json` | who sings: lead by sound, backing = the other figure, announcer/narrator/whisper rules, ear corrections first | `song-analysis/voices.py` (`assignment.json`, `lines.csv`, `corrections.json`) | covered |
| `lipsync_qa.py` | voice active but no open mouth → gaps | `voices.py` gap report (≥ 0.3 s), `talking-character/check_sync.py` | covered |
| `tim.svg`, `lia.svg` | rigged figures | `characters/assets/figures/` + `characters/figures.py` | covered |
| `sif.py`, `motion.py`, `svg2sif.py`, `lipsync.py`, `krita_assemble.py` (project copies) | Synfig builders, rig, mouths, Krita sets | `toon-2d/scripts/` same names | covered |
| `paint_room.py`, `paint_stage.py` | Python "brush" paints the room and stage layers | results bundled as `toon-2d/assets/sets/room`, `stage`; new sets via FLUX (`comfy_image.py`), Krita, `paint_clearing.py` | not ported (project art; procedural room/stage painter lost) |
| `make_v2_zimmer.py` – core | one scene script for all sets: figures sing/listen/dance on beats, gestures, screen face/texts, tier badge, props on words, push-in | `animated-music-video/scripts/scene.py` (`screen`, `screen_badges`, `props`, `gestures`, `dance_style`, `aura`) | covered |
| `make_v2_zimmer.py` – typing arms + key glow (+ typing times for clicks) | readable typing in front of the desk | `scene.py` | in progress (agent) |
| `make_v2_zimmer.py` – air guitar strumming arm | strum arm in front of the body on half beats | `scene.py` | in progress (agent) |
| `make_v2_zimmer.py` – monitor set usage bar | bar turns red at "limit", empties after upgrade | `scene.py` | in progress (agent) |
| `make_v2_zimmer.py` – spot / disco finale / night mode / heartbeat camera | spotlight verse, coloured cones + confetti, dark room after the stop | `scene.py` | in progress (agent) |
| `make_v2_zimmer.py` – silhouette in the window / giant shadow | cameo between sky and wall layer | `scene.py` | in progress (agent) |
| `make_v2_inset.py` | narrator inset (round frame, lip sync, hidden while the figure sings in picture) | `scene.py` narrator inset | in progress (agent) |
| `render_all_v2.sh`, `rerender_tiers.sh` | regenerate and render all sections (10 Synfig pieces in parallel) | `scene.py <section> --render` + `toon-2d/synfig_parallel.py` | covered |
| `apply_iris.py` | iris-out with Shaders masks on the last section | `film-finish/transitions.py` `"kind": "iris"` (+ `"shaders": true` via `shaders_render.py iris_masks`) | covered (agent work on disk) |
| `gags.py` + `make_gag_track.py` + `make_lettering.py` | keyword → lettering pops on the word, own track on the song timeline | `film-finish/overlays.py` (`gags`) | covered |
| `make_gag_icons.py` | drawn gag pictures (kiss mouth, chip, $$$, company name signs) | `overlays.py` draws text only; pictures only as `scene.py` props | partial (pop-up picture gags) |
| `make_lyrics_track.py` | word-exact lyrics, letters appear when sung, held words stretch | `overlays.py` `"lyrics": true` (word reveal + highlight) | partial (MISSING #17) |
| `comic_s2/comic_lib.py` | brush/ink drawing tools for panels | `toon-2d/comic_page.py` (page, frames, bubbles, crops); panel art now from FLUX | partial (code-drawn panel art superseded by FLUX) |
| `comic_s2/make_comic_s2.py` | comic page + layers + camera on the lines (desk, lift-off, arcs) | `comic_page.py` + `render_multiplane.py --page comic25d` + `multiplane/comic25d.html` | covered |
| `comic_s2/flux_panels.py` | FLUX panel variants to choose from | `ai-video/comfy_image.py --variants` | covered |
| `comic_s2/flux_einbau.py` | crop to panel, Real-ESRGAN, depth relief, own lettering layers | `comic_page.crop_aspect`, `ai-video/estimate_depth.py`; upscaler only inside animated-powerpoint | partial (MISSING #14) |
| `comic_s2/make_tim_track.py`, `tim_ausbruch.py`, `tim_layer.py` | figure breaks out of the comic as a paper stand-up, tracked from the difference render, lip-synced | `toon-2d/scripts/breakout.py` | in progress (agent) – on disk |
| `comic_s2/compose_s2.py` | flight + caption box typing words to the singing + inset + break-out layer | `breakout.py` composes the flight; caption box: none | partial (MISSING #9) |
| `comic_s2/make_bridge.py` + `compose_bridge.py` | fast panels with hard cuts per line + shout words on the word | `scene.py` fast bridge panels (agent); shout words = `overlays.py` gags | in progress (agent) |
| `intro/paint_intro.py` | five painted layers + multiplane camera into the lit window | `toon-2d/render_multiplane.py`; recipe in `techniques.md` | not ported (project art; camera covered) |
| `finish_v2_preview.py` | section + gags + lyrics + sound + look | `film-finish/build.py preview` | covered |
| `make_full_cut.py` (+ old `assemble_film.py`, melt) | all sections frame-exact on the song, one sound track, look once, otio/mlt | `build.py film` + `edit_handoff.py` | covered |
| `blenden_v2.py` | zoom through window, glow, screen zoom, iris on the grin, white flash, title | `film-finish/transitions.py` + `build.py` `title` | covered |
| `make_sfx_v2.py` | earshot sound track (typing clicks, gags, gestures, heartbeat, cash register) | `film-finish/sounds.py` (typing clicks need the typing times from scene.py – agent) | covered |
| `make_en_track_einfach.py` + `make_film_de_en.py` | English song shifted by one global offset, same sounds, second audio track | `film-finish/second_audio.py` | covered |
| `make_film_48fps.py` | RIFE only in camera moves, other frames doubled | `animated-music-video/scripts/fps48.py` (not on disk yet) | in progress (agent) |
| `popup/make_popup_film.py` | pop-up making-of version | `film-finish/popup.py` | covered |
| `abspann/make_abspann.py` | credits with side screens of the film, gags, ducking, laugh-driven mouth | `film-finish/scripts/credits.py` (not on disk yet) | in progress (agent) |
| `abspann/lia3d_rund.py` | Lia morphs into a rounded 3D toon figure (Blender) | `toon-2d/scripts/figure_3d.py` (+ `crossfade`) | in progress (agent) – on disk |

Abandoned / probes: `make_pilot.py`, `make_song.py`, `voices.py`, `export_v1_assignment.py`, `finish_song.py` (v1,
superseded by the v2 scene script) · `assign_voices_v2.py`, `assign_voices_v3.py` (superseded by v4 with stems) ·
`echo_voices.py`, `chorus_roles.py`, `chorus_fine.py`, `verse2_fine.py` (fine male/female tracks, superseded by Suno
stems) · `make_en_track.py` (section-wise re-cut, sounded chopped) · `abspann/laugh.py` (formant synthesis, heard as
a cow), `abspann/laugh_bark.py`, `laugh_bark_gpu.py` (Bark laugh, not taken) · `abspann/lia3d_blender.py` (inflated
picture, rejected) · `popup/make_popup_probe.py` (probe) · `check_lines.py`, `compare_models.py`,
`segment_info.py`, `song_info.py` (one-off checks).

## 2. lego_test – brick film (bricks-music-video)

Final pipeline: `alles_rendern.py` → `render_lego.py --szene ab_<name>.py` per section (+ credits gags) →
`make_abspann_brick.py` → `film_bauen.py --abspann`.

| Reference script | Role in the pipeline | Plugin counterpart | Status |
|---|---|---|---|
| `ldraw_blender.py` | own LDraw importer (BFC, p/48, quality switches) | `bricks-3d/scripts/ldraw.py` | covered |
| `figur.py` | minifig rig (LeoCAD joints) | `bricks-3d/scripts/minifig.py` | covered |
| `lego_helfer.py` | decals, image planes, lights, shader helpers | `bricks-3d/scripts/shading.py` | covered |
| `make_texturen.py` | face atlas, 9 mouths, torso print, screens | `bricks-3d/scripts/textures.py` | covered |
| `film_lib.py` | figures, mouths, blinks, shots, exposure, hand props, render | `bricks-3d/scripts/brickfilm.py` (plan JSON) | covered |
| `sets.py` | room (monitor face), stage | `bricks-3d/scripts/sets.py` + `layouts.py` (room, stage, rooftop) | partial (other sets → MISSING #5) |
| `belichtung.py` | per-shot exposure, smoothed per light group | `brickfilm.py` exposure (`cache/exposure_<section>.json`) | covered |
| `render_lego.py` | Blender with GPU lock, stills / render / blend | `bricks-3d/blender_run.py` + `bricks-music-video/render.py` | covered |
| `alles_rendern.py` | render all sections, then credits and film | `render.py <section>` per section + `film-finish/build.py film` | covered |
| `ab_strophe1/3.py`, `ab_refrain2/3.py`, `ab_ansage_pro/max.py`, `ab_seitwann.py`, `ab_schluss.py` | hand-written shots, keys per word, cameos, coins, screen gags, lights off | `bricks-music-video/plan.py` (seeded shot plan from project.json: gestures, cameo, coins, screen, lights_off, spots_cycle, bulbs_chase) | covered (choreography is project data) |
| `ab_intro.py` + `teil_a.py` | house exterior, fly through trees into the window; room rebuilds into the stage | – | MISSING (#5) |
| `ab_bridge.py`, `teil_c_anim.py` | arena, moving single bricks, brick lettering, confetti, flying bricks | – | MISSING (#5) |
| `ab_strophe2.py` | cloud auction, robot models with neutral signs | robot look in `bricks-3d/assets/cast.json`; set missing | partial |
| `make_tex_b.py`, `make_tex_c.py`, `make_tex_d.py` | project textures (price tag, VERSPRECHEN letters, credit screens) | `textures.py --screens` for screens | not ported (project data) |
| `film_bauen.py` | sections on the song, lettering + lyrics, iris-out on Tim, look, small version | `film-finish/overlays.py` + `build.py film` + `transitions.py` iris | covered |
| `make_abspann_brick.py` | credits roll in five parts, instrumental stems with ducking, sounds | `film-finish/credits.py` (not on disk yet) | in progress (agent) |
| `ab_abspann_*.py` + `ab_abspann_hilfe.py` | five brick gag scenes (fall over, invoice, update, Lia falls apart brick by brick, laugh-driven grin) | plan.py props cover none of these | partial (brick effects MISSING #5; credits roll in progress) |

Abandoned / probes: `szene.py`, `szene2.py` (first 15 s / 41 s tests, superseded by `film_lib.py` + sections) ·
`test_figur.py` (rig test image).

## 3. Lyric videos – global skill `~/.claude/skills/music-video` (lyric-music-video)

| Reference script | Role in the pipeline | Plugin counterpart | Status |
|---|---|---|---|
| `scripts/transcribe.py` | Whisper words with times | `song-analysis/track_read.py` + `best_words.py` (three passes) | covered |
| `scripts/align.py` | lyric lines aligned to Whisper words → timing.json | `track_read.py` alignment + `best_words.py` | covered |
| `scripts/separate_vocals.py` | Demucs vocals | `song-analysis/separate_vocals.py` (GPU lock) | covered |
| `scripts/refine_timing.py` | snap word starts to vocal onsets | `song-analysis/refine_timing.py` | covered |
| `scripts/analyze.py` | BPM, beat offset, riff hits, held-word candidates | `song-analysis/hits.py` + `held_notes.py` (candidates) | covered |
| `scripts/held.py` | loudness + pitch contour of held notes | `held_notes.py measure` | covered |
| `scripts/install_data.py` | write lyrics.ts / timing / hits / held into the project | `lyric-music-video/scripts/install_data.py` | covered |
| `scripts/contact_sheet.py` | grid of frames at given times | `studio-core/frames.py`, `lyric-music-video/render.py sheet` | covered |
| `scripts/audio_io.py` | decode any audio | `studio-core/media.py decode` | covered |
| `assets/engine-template/` (incl. `scripts/render.mjs`) | Vite/TS/three.js engine, frame-exact render | `lyric-music-video/assets/engine-template/` (all files present; render.mjs, lyric.ts, lyrics.ts, vocal.ts updated) + `render.py` | covered |
| `assets/examples/*` (7 videos) | past videos as technique references | `lyric-music-video/assets/examples/*` (all 7, plus index.html each) | covered |

Abandoned / probes: none.

## 4. ai_efficiency – "Who keeps changing my office?" (animated-powerpoint)

Final pipeline: `render_voll_alles.sh` (S2 → intro → S3–S12, each `make_sXX.py --rendern` = Synfig figures →
light maps → three.js) → `schnitt/make_film.py v2` (+ e-mail version).

| Reference script | Role in the pipeline | Plugin counterpart | Status |
|---|---|---|---|
| PowerPoint COM export (steps 3, 7, 20) | clean slides without master shapes, picture positions | `animated-powerpoint/scripts/deck.py` | covered |
| `figuren/upscale_cast.py` | Real-ESRGAN ×4, colour on white + alpha separately | `figures.py --upscale` | covered |
| `figuren/make_parts.py` | cut figures into parts from the original pixels, pivots | `parts.py` (`--auto` + `parts.json`) | covered |
| `figuren/check_rig.py` | parts map, rest pose vs original, test poses | `parts.py` (`parts_check.png`, fidelity numbers) | covered |
| `figuren/putzen_teile.py` | remove white soft-edge remnants outside the contour | – (parts.py grows hidden pieces, no remnant clean-up) | partial |
| `figuren/make_mund.py` | 8 mouth stages per figure in the original's style | – | MISSING (#2) |
| `buehne/mund_sync.py` | Rhubarb (English, with script text) → mouth stage keys | – | MISSING (#2) |
| `buehne/rig_sif.py` | Synfig rig of raster parts (squash, tilt, turn, eyes) | `clip.py write_sif` + `acting.py` | covered (no mouth) |
| `buehne/lebendig.py` | idle life (weight shift, sway, breath, blinks) + walk `schritte()` | `acting.py idle_keys`, `auto_blinks` | partial (walk missing) |
| `buehne/buehne.py`, `probe_fritz/geometrie.py` | slide/world measures, foot measurement | `clip.py fig_geometry` | covered |
| `buehne/make_shading.py`, `probe_fritz/make_shading.py` | light maps flat → round | `clip.py` step `light` | covered |
| `probe_fritz/probe.py` + `fritz25d.html` + `make_assets.py` | step-out clip (slide bulges, pop, tag, landing) | `clip.py` + `acting.py` + `assets/stage25d.html` | covered (reference test 1) |
| `s02_cast/make_s02.py` + `buehne25d.html` + `render_figuren.sh` + `make_assets.py` | four figures step out one after another | `clip.py` (several `step_out` figures follow each other) | covered |
| `buehne/szene.py` + `szene25d.html` | general scene page: set layers, foreground, sprites, steam, tint/rim, moving layers | – | MISSING (#1) |
| `s03_buero` … `s12_lab/make_sXX.py` | scenes 3–12 (dialogue, props, coins, islands, lab) | – (need #1 and #2) | MISSING (#1) |
| `buehne/blasen.py` | thought/dream/speech clouds in the slide's ink style, star eyes | `toon-2d/comic_page.bubble` (speech bubble only) | partial |
| `buehne/requisiten.py` | props in the ink style (signs, chat bubbles, mini bots, cards, holograms, neon) | – | not ported (project content) |
| `buehne/effekte.py` | confetti physics, arc flight | paper bits in `clip.py` | partial |
| `sets/altbuero/make_set.py`, `sets/promptstudio/make_set.py`, `sets/make_sets_2.py` | FLUX sets: logos/pseudo-text painted over, accent colour, foreground split | `ai-video/comfy_image.py`; clean-up by hand | not ported (project data) |
| `ton/stimmen.py` | ElevenLabs voices per role, only changed lines | `voice/scripts/voice.py` engine `elevenlabs` | covered |
| `ton/pruefen.py` | Whisper check of every line, durations, word times | `voice/scripts/hear.py` | covered |
| `ton/tempo.py` | shorten pauses, cap wpm, silence at line ends | – | MISSING (#11) |
| `buehne/tonmix.py`, `buehne/ton_szenen.py`, `s0x/make_ton.py`, `probe_fritz/make_sfx.py`, `schnitt/make_finale_ton.py` | voices + earshot sounds frame-exact per scene | `animated-short/sfx_track.py` (sounds); voice placement in `talking-character/speak.py` | covered |
| `s00_intro/make_intro.py` + `intro25d.html` + `make_ton.py` | deck intro: slides flip, keywords on words, typed title | – | MISSING (#13) |
| `schnitt/make_film.py` (+ `schnittliste.json`) | three versions, transitions, music with ducking, V3 grade/letterbox/leaks, finale with wink | – (`transitions.py` works on song sections only) | MISSING (#3) |
| `schnitt/make_musik.py`, `make_musik_flott.py` | film score (numpy synthesis / ElevenLabs Music) | – | MISSING (#12) |
| `render_voll.sh`, `render_voll_alles.sh`, `render_vorschau*.sh`, `render_alle.sh` | render all scenes in order, preview at 1/3 size | `clip.py` steps (`--only`, `--from`) | covered (for clips) |

Abandoned / probes: `test_animated_drawings/*` (Meta Animated Drawings, rejected) · `s_test_mund/make_test.py`
(mouth test) · `schnitt/v3_fertig.py` (one-off resume) · `figuren/make_fritz_parts.py` (replaced by `make_parts.py`).

## 5. Claudia videos (claudia-music-video / ai-video)

### claudia-video-trial/nachtlauf – "Europe 2031" (V1 → V2 by measurement → V3 per-shot pick)

| Reference script | Role in the pipeline | Plugin counterpart | Status |
|---|---|---|---|
| `prompts_bauen.py` | English prompts per shot and technique (scenes, wardrobe, B-roll) | `claudia-music-video/plan.py` + `jobs.py` + `claudia.py` (canon/LTX rules) | covered |
| `nachtlauf.py` + `nachtlauf.cmd` | phases one model each, GPU lock, resume, starts ComfyUI | `ai-video/night_run.py` (+ `comfy.ensure`) | covered |
| `gemeinsam.py` | paths, LTX lead-in/delay, S2V lengths, audio excerpts | `ai-video/clips.py` (`frame_index`, `ltx_fit`, `s2v_frames`, `cut_audio`) | covered |
| `kontaktbogen.py` | contact sheets per phase + selection template | `ai-video/sheets.py` (written by `pick.py`) | covered |
| `auto_auswahl.py` | pick start image with the streak (canon) | `ai-video/canon.py` + `pick.py start` (also mic check) | covered |
| `analyse.py` | lip score, canon on film frames, share of stills | `ai-video/mouth.py`, `canon.py`, `pick.py` | partial (share-of-stills metric) |
| `v2_vorbereiten.py` | stills → moving LTX clips, 2 more seeds for weak lips | `jobs.py` (`--seeds`, moving B-roll), `ltx.py render("moving")` | covered |
| `v2_auswahl.py` | best seed / S2V per shot by measured lip score | `pick.py clips` | covered |
| `schnitt.py` | whole film: material per shot, LTX delay, S2V upscale, lyrics, grain/vignette, AI label | `render_shots.py` + `make_film.py` (film-finish overlays/build) | partial (typo shots MISSING #7, Wan mouth placement MISSING #10) |
| `v3_schneiden.py` | V3 from per-shot choice V1/V2 without re-render | `video-review/pick_cut.py` + `review.py cut` | covered |
| `vergleich/server.py` + `index.html` + `vergleich.cmd` | browser comparison per shot | `video-review/server.py` + `assets/index.html` | covered |

### claudia-live/nachtlauf – "Europe 2031 – Live" (V1 → V5)

| Reference script | Role in the pipeline | Plugin counterpart | Status |
|---|---|---|---|
| `prompts_bauen.py`, `nachtlauf.py`, `gemeinsam.py`, `kontaktbogen.py`, `auto_auswahl.py` (copies) | as in the trial, live stage looks | as above; live looks in `claudia.py` + `references/versions.md` | covered |
| `lippen_auswahl.py`, `lippen_gegenprobe.py` | lip score against Rhubarb and level curves | `mouth.py` / `pick.py --curve mix` | covered |
| `live_v2.py` | warm start images (Qwen edit), motion prompts, normalised vocals | `qwen_edit.py`, `ltx.py`, `jobs.py`; vocal normalisation – | partial (MISSING #6) |
| `v2_auswahl.py`, `v4_messung.py` | hidden cut, frozen, motion and lip checks per clip | lips only (`pick.py`) | MISSING (#4) |
| `live_v3_bridge.py` | bridge as one long InfiniteTalk take | `ai-video/infinitetalk.py` (one pass ≤ ~5 s) | partial (MISSING #15) |
| `live_v4.py` | reframed close/frontal versions for weak lips, crowd recipe | `jobs.py` variants; `ltx.py` fixed `img_compression` 18 | partial (MISSING #8) |
| `publikum_rest.py` | remaining crowd shots with the winning recipe | – | MISSING (#8) |
| `v4_wahl.py` | candidates per shot across V1–V4 and the choice | `video-review/review.py` (2–9 versions, picks) | covered |
| `v5_mikro.py` | mic repair: Qwen edit only the mic, re-render LTX/InfiniteTalk | `canon.py` detects the wrong mic; repair pass by hand with `qwen_edit.py` | partial |
| `mikro_bogen.py` | mic check sheet per Claudia shot | `sheets.py` + `canon.py` mic test | covered |
| `film_pruefen.py` | decode check, 20/50/80 % sheets, overview | `media.check_video` + `sheets.shot_sheet` | covered |
| `schnitt.py` | live cut, stamps on the stage screen, title "EUROPE 2031 · LIVE" + AI note | `render_shots.py` + `make_film.py` (`ai_label`) | partial (typo shots MISSING #7) |

### tools/lipsync

| Reference script | Role in the pipeline | Plugin counterpart | Status |
|---|---|---|---|
| `ltx/ltx_shot.py` | LTX-2.3 lip-sync workflow (audio frozen via latent mask) | `ai-video/ltx.py` | covered |
| `ltx/messen.py` | mouth openness vs vocal curve | `ai-video/mouth.py` | covered |
| `s2v/s2v_shot.py` | Wan2.2-S2V shot | `ai-video/s2v.py` | covered |
| `vergleich2/infinitetalk_shot.py` | InfiniteTalk pass | `ai-video/infinitetalk.py` | covered |
| `vergleich2/comfy.py` | ComfyUI client | `ai-video/comfy.py` | covered |
| `vergleich2/humo_shot.py`, `minimax_h3_shot.py` | HuMo 1.7B / MiniMax H3 (listed as optional rescue models in TOOLS.md) | – | partial (TOOLS lists them, no wrapper; never used in a final film) |
| `vergleich2/messen.py`, `messen_lang.py`, `nebeneinander.py`, `material.py`, `referenz_lang.py`, `kette*.sh` | model comparison harness | results in `ai-video/references/models.md` | not ported (one-off evaluation) |

Abandoned / probes: trial `bewegung_test.py`; live `bewegung_test.py`, `bewegung_test_b.py` (its `normalisieren` was
reused → MISSING #6), `publikum_test.py` (B Wan 2.1 + LightX2V and C MiniMax rejected; A became the crowd recipe) ·
`tools/lipsync/vergleich2/kandinsky6_shot.py` (rejected) · `tools/lipsync/musetalk/*`, `latentsync/*`, `batch*.sh`,
`dl_*.sh` (early lip-sync tests and downloads).

## 6. Shorts, talking character, toon-2d, film-finish references

| Reference script | Role in the pipeline | Plugin counterpart | Status |
|---|---|---|---|
| `scenes/pip_spricht/make_scene.py` (+ `lipsync.py`, `render.py`, `sif.py`, `motion.py`) | Pip speaks with Rhubarb lip sync | `talking-character` (`new_talk.py`, `speak.py`, `talk_scene.py`, `check_sync.py`) + `characters/pip.py` | covered (mouth track 97 % identical) |
| pip_spricht voice (System.Speech, pitch) | test voice | `voice/voice.py` engine `system` (`pitch`) | covered |
| `scenes/fips/make_scene.py` (+ `svg2sif.py`) | Fips chirps, SVG rig in Synfig | `toon-2d/assets/templates/figure_scene.py` + `characters/figures.py` | covered (121/121 identical) |
| `scenes/fips/make_sound.py`, `chirp_variants.py` | synthetic chirps, earshot picks the most bird-like | `animated-short/sfx_track.py` (earshot bank, e.g. `mallet/celesta`) | not ported (superseded by the sound bank; chirp synthesizer lost) |
| `scenes/lichtung/paint_bg.py` | painterly forest layers | `toon-2d/paint_clearing.py` | covered |
| `scenes/lichtung/krita_assemble.py` | layers → .kra + exports | `toon-2d/krita_assemble.py` | covered |
| `scenes/lichtung/make_scene.py` | Pip and the leaf, multiplane | `animated-short` exercises + `toon-2d/render_multiplane.py` | covered (151/151, 0.16/255) |
| `scenes/lichtung/make_sfx.py` | earshot sounds frame-exact | `animated-short/sfx_track.py` | covered |
| `scenes/comic_25d/make_comic.py` | comic page + layers + depth relief for the 2.5D flight | `toon-2d/comic_page.py` + `render_multiplane.py --page comic25d` + `ai-video/estimate_depth.py` | covered (277/277, 0.15/255) |
| `experiments/01_synfig_ball/make_ball.py` | bouncing-ball exercise | `animated-short/short.py new` + `references/exercises.md` (numbers) | covered (recipe) |
| `experiments/03_pencil2d_bridge/make_pclx.py` | PNG sequence → Pencil2D project | – | not ported (Pencil2D deliberately not used, TOOLS.md) |
| `experiments/04_synfig_scene/make_scene.py` | Pip and the Flower | `toon-2d/assets/example_scene.py` | covered (145/145 identical) |
| `experiments/11_blender/pip_gp.py` | Grease Pencil Pip on twos | `toon-2d/assets/blender_gp_example.py` + `blender_run.py` | covered |
| `experiments/12_shaders/run_job.py` + `render.html` + `make_catalog.mjs` | Shaders headless WebGPU jobs, effect catalogue | `film-finish/scripts/shaders_render.py` + `scripts/shaders/` | in progress (agent) – on disk |
| `experiments/12_shaders/composite.py` | look pass + iris-out on a scene | `film-finish/apply_look.py` + `transitions.py` iris | covered |

Abandoned / probes: `experiments/02_python_character/pip_jump.py` (pycairo, superseded by Synfig) ·
`experiments/11_blender/probe*.py` (API probes).

## 7. Old shared skill `.claude/skills/synfig-animation/scripts`

| Reference script | Role in the pipeline | Plugin counterpart | Status |
|---|---|---|---|
| `sif.py` | Synfig layer builders | `toon-2d/sif.py` | covered |
| `motion.py` | squash, hop, springs | `toon-2d/motion.py` | covered |
| `svg2sif.py` | Inkscape SVG → rig | `toon-2d/svg2sif.py` | covered |
| `lipsync.py` | Rhubarb cues → 9 mouths | `toon-2d/lipsync.py` | covered |
| `render.py` | .sif → frames → MP4/GIF/contact | `toon-2d/render.py` | covered |
| `synfig_parallel.py` | split frame range over processes | `toon-2d/synfig_parallel.py` | covered |
| `render_multiplane.py` + `multiplane/` | three.js multiplane / comic flight | `toon-2d/render_multiplane.py` + `multiplane/` | covered |
| `krita_assemble.py` | Krita layer assembly | `toon-2d/krita_assemble.py` | covered |
| `apply_look.py` | standard look | `film-finish/apply_look.py` | covered |
| `assemble_film.py` | shot list → film.otio / film.mlt / film.mp4, crossfades, clip sound, music | `film-finish/build.py film` (song timeline) + `edit_handoff.py` (otio/mlt) | partial (generic shot-list cut MISSING #3) |
| `kodierung.py` | x264 / NVENC preview switch | `studio-core/encoding.py` (`PREVIEW=1`) | covered |
| `gpu_sperre.py` | one GPU job at a time | `studio-core/gpu_lock.py` | covered |
| `track_read.py` | exposure sheet (beats, words, sections) | `song-analysis/track_read.py` | covered |
| `transcribe.py` | Whisper words, script check, SRT | `voice/hear.py` (check), `track_read.py` (words) | partial (SRT MISSING #16) |
| `whisper_geraet.py` | GPU/CPU Whisper model choice | `song-analysis/whisper_device.py` | covered |
| `separate_vocals.py` | Demucs | `song-analysis/separate_vocals.py` | covered |
| `comfy_image.py` | FLUX / SDXL / Qwen-Image stills | `ai-video/comfy_image.py` | covered |
| `comfy_video.py` | Wan 2.2 TI2V / LTXV image-to-video | `ai-video/comfy_video.py` | covered |
| `estimate_depth.py` | Depth Anything V2 | `ai-video/estimate_depth.py` | covered |
| `assets/example_scene.py`, `assets/blender_gp_example.py` | example scenes | `toon-2d/assets/` same names | covered |
| `references/sif-format.md`, `animation-craft.md` | format and craft notes | `toon-2d/references/` same names | covered |
