---
name: lyric-music-video
description: "Make a lyric music video from a song and its lyrics - kinetic typography and motion graphics in TypeScript + three.js where every letter lands exactly when it is sung, rendered frame-exact to MP4 (full, compressed, < 30 MB, mail). Whisper-aligned words snapped to vocal onsets, flashes on riff hits, held notes stretched with the voice, a fresh visual identity with one scene per lyric idea. Use whenever the user wants a lyric video, a typography video for a song, a team or company song as a video, or a song that presents content (a page, roles, a product, slides) - even if they just attach an audio file. Not for singing cartoon characters, brick films or AI singers."
---

# Lyric music video

A song + lyrics (+ optional source material) becomes a Vite/TypeScript/three.js page where everything is a pure
function of song time, rendered frame by frame in headless Chrome to MP4. The pipeline is proven on seven videos
(see `assets/examples/`: industrial-riff, stadium-broadcast, glass-ui-mascot, content-cards, stage-dodge,
popup-bubbles, office-scenes); the creative part must be new every time.

**Two things matter most:** the text must sit exactly on the voice, and every video must look and feel like its own
piece - inspired by earlier work, never a copy of it.

Scripts: `L="${CLAUDE_PLUGIN_ROOT}/skills/lyric-music-video/scripts"`, `SA="${CLAUDE_PLUGIN_ROOT}/skills/song-analysis/scripts"`.
Run them with `uv run "$L/<script>.py" ...`. Tools are checked with
`studio-core/scripts/check_tools.py` (ffmpeg required; Node.js 20+ and npm for the engine; GPU optional).

**Building blocks** (shared code + docs of this plugin, not skills - read the one you need):
`${CLAUDE_PLUGIN_ROOT}/skills/<block>/BLOCK.md` for `studio-core`, `song-analysis`, `toon-2d`, `characters`, `voice`, `ai-video`, `bricks-3d`, `film-finish`. In those files
`<plugin>` stands for `${CLAUDE_PLUGIN_ROOT}`. First use on a machine: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py" --setup` (finds the programs).

## 1. Interview first

Ask only for what is not already given (check the message, attachments and recent Downloads - a just-downloaded
file matching the song title is very likely it). One round of questions where possible.

- **Song file** (wav/mp3) - required. **Suno stems** (lead/backing vocals) if available: much cleaner timing; they
  must come from the SAME version as the mix (an "(Edit)" version was 3.5-4.6 s off and drifting).
- **Lyrics** as written, with [Section] headers. The performed song often repeats lines - you reconcile that below.
- **Context & story**: what is the song about, who watches it (team, company, friends, public)? **Source material**
  to present (an HTML page, document, roles/products list, images)?
- **Style wishes**: genre/mood, colours/brand, references they like, things to avoid. A named reference video gives
  *ideas*, never the look.
- **Language(s)** sung (mixed German/English is fine: `--language auto`).
- **Output**: default = full quality + `_compressed` + `_small` (< 30 MB) + `_mail` (~12 MB); where to put it
  (default: `<project>/out/`, copied wherever the user wants).

## 2. Creative brief (before building)

Read `references/scene-catalog.md` (all past scenes, techniques, identities, likes and dislikes), then:

1. `brief.py PROJECT` shows the project's seed, six seeded "dice" (lyric entrance, cut style, palette strategy,
   type pairing, space, ending) and the past identities. The dice push you somewhere new - take, bend or overrule
   them; a new seed (`--reroll`) gives a new take.
2. Write the **visual identity** in 2-3 lines (palette, typography, textures, lyric styling, transitions, ending),
   derived from the music and the context, different from every past identity: `brief.py PROJECT --identity "..."`.
3. **One scene per lyric idea**: for every line or line pair ask what the concrete image, object, situation or
   metaphor is ("pack it small and make it fast" -> a waveform squeezed into a chip while RAM/latency gauges
   shrink). Record each: `brief.py PROJECT --idea "..." --where "verse1:3"`. User ideas: `--by user` (they win).
   Choruses may share a motif that evolves; instrumental parts get their own scenes; plan a special **ending** that
   fits the last line.
4. Show the plan (identity + one line per scene) and let the user react if they want a say; otherwise proceed.

## 3. Build

`render.py` checks project.json first (studio-core `project_check.py`: wrong types stop it with exit code 2 and the key named, unknown keys warn).

1. **Project**: `new_video.py PROJECT --song SONG --lyrics lyrics.txt --language auto [--lead v.wav --backing b.wav]
   [--from S --to S --lyrics-from "..." --lyrics-to "..."]` - song project (`project.json` with seed + ideas,
   `song.wav`, `lyrics.txt`), the engine copied to `PROJECT/video/` and `npm install`. Keep PROJECT short on Windows.
2. **Analyse**: `analyze_song.py PROJECT` (run in the background; Demucs + Whisper take the GPU lock and wait for
   other AI jobs). It runs song-analysis (vocals, Whisper word times aligned to the lyrics, repairs), snaps every word
   start to the real vocal onset and stretches held line endings to where the voice stops (`refine_timing.py`),
   finds riff hits + the beat grid (`hits.py`) and prints every line with recognized/total words plus the held-note
   candidates. When whole lines were not heard (Whisper's VAD drops sung passages) it runs `best_words.py`
   automatically: Whisper again on the full mix and on the vocals without VAD, best pass per line in sung order
   (reference song A: 143 -> 271 of 300 words recognized).
   - Lines still marked `<- estimated` were not heard: often shouted chants (fine if the neighbours are good), but
     also repeats or ad-libs missing from `lyrics.txt`. Then **rewrite lyrics.txt as performed** (one sung line per
     row, repeat repeated lines, keep the headers) and run `analyze_song.py PROJECT --redo`. What Whisper actually
     heard is in `cache/rec_<pass>.json`; the aligned words in `analysis/song_sheet.json` ("source").
   - Optional check: `uv run "$SA/sync_check.py" PROJECT/analysis/vocals_lead.wav
     PROJECT/analysis/timing.json --lead 0.08` (share of words shown while the voice is still silent should be ~0).
3. **Held notes** (a held note shown as performed: "aaaall", "riiiight"): `analyze_song.py` already finds the
   words held clearly longer than the song's normal word as one sustained note - judged on the voice, so also a
   mid-line word whose end Whisper cut short - picks the 2-4 that matter (one per ~16 lines), moves their ends to
   where the voice stops and measures them (`analysis/held_auto.json`). The engine stretches them by itself (the
   held vowel repeated ~3x per held second, 5-8 copies, waving with loudness and pitch, a pitch ribbon, the ending
   letters landing on the release; motion phase from the seed). Per project in `project.json`: `"held_stretch":
   false` (off), `"held_max": N`, `"held_style": "vowels"` (default) | `"stretch"` (one vowel that widens) |
   `"auto"` (seeded). Per line in a scene: `{ autoHeld: false }`, or pick by hand - measure more with
   `uv run "$SA/held_notes.py" measure PROJECT/song.wav PROJECT/analysis/held.json
   name:start:end ... --vocals PROJECT/analysis/vocals_lead.wav` and set `{ held: 'name', heldWord: k }`.
4. **Install**: `install_data.py PROJECT` -> `video/src/lyrics.ts` (lines, sections, SONG_END, BPM, BEAT_OFFSET,
   SEED), `timing.json`, `hits.json`, `held.json`, `vocal.ts` track names, `public/song.wav`.
5. **Write the video**: `video/src/scenes.ts` + `video/src/style.css` (see `references/engine.md` for the scene API,
   SungLine/held-note options, 3D modes and recipes). Set the fonts in `video/index.html` (Google Fonts link) AND in
   the `document.fonts.load(...)` list of `main.ts`. Recolour/extend `world3d.ts` if you use 3D. Mark ideas done:
   `brief.py PROJECT --status N done`.
6. **Preview**: `render.py PROJECT preview` (type check, 1-fps render of the whole song, contact sheets every 6 s in
   `out/`; `--times` for one time per scene). Look at every sheet: overlaps, unreadable text, empty frames, leaks from
   earlier scenes, anything that looks copied. Timing-critical moments: `render.py PROJECT clip --from 88 --to 98`
   (10 fps).
7. **Render**: `render.py PROJECT final --title "Song Title"` -> `out/<title>.mp4` (CRF 20, 1080p30, ~6-10 min for
   3-4 min of song on a GPU - run in the background), then `_compressed` (CRF 28), `_small` (< 30 MB, 720p two-pass)
   and `_mail` (~12 MB, 540p, AAC 64k) via film-finish's encoder; every file is decoded, its duration and audio
   checked. `versions out/<title>.mp4` remakes only the copies.
8. **Deliver**: the outputs + the project without node_modules. Tell the user what each scene shows (by section),
   the files and sizes, and caveats (you cannot hear the result - sync was verified by measurement and frames; `LEAD`
   in `lyric.ts` shifts all text).

## 4. Creative rules - new scenes every time

- **Start from the lyrics, not the catalog.** The catalog gives *techniques* (how to animate, sync, stage), never
  finished scenes. When a past scene fits, transform it (new metaphor, layout, motion).
- **A new visual identity per video** - palette, typography, textures, transitions, lyric styling and ending differ
  from all identities in the catalog. Derive it from the music style and the context (brand colours of the source
  material, era, genre mood). Use `SEED` (lyrics.ts) for variation: `hash(i + SEED)`.
- **Present source material faithfully** (names, quotes, tasks) exactly when it is sung. Extract embedded images and
  use them at a size their resolution allows; tone bright white screenshots down on dark stages (light grey cards,
  ~0.85 brightness). Never just place an image: deal it in, let it drift (Ken Burns), bump it on the beat, sweep a
  glint over it.
- **Use the voice**: held-note stretch on the 2-4 most prominent held words (automatic, see 3.3; react to them in
  the scene with `heldFx`), hits for flashes/shakes, the beat for
  bumps and on-beat events (`timeAtBeat`), silences for contrast.
- **A special ending** that fits the last line (past: CRT switch-off, steel shutter, completed signal chain) - invent
  a new one. Long outros (> 6 s after the last line) need beat-driven events, not a static hold.
- Avoid: copying a reference video's look; coloured marker boxes behind sung words (disliked); text that lags the
  voice; cramming text into short scenes (~3 s carries a name, a short quote and 1-2 bullets, no more).
- After the video is done, add its identity and new techniques to `references/scene-catalog.md` (section 1 table and
  the technique lists) so the next video knows what to avoid repeating.

## 5. Technical rules and gotchas (learned the hard way)

- **Deterministic animation**: every style is computed from `c.t`. No CSS transitions/animations, no `setTimeout`,
  no `Math.random()` (use `hash(n)`), no state that depends on frame order except smoothing that settles quickly.
- **No leaks between scenes**: main.ts clears the scene root's inline style on every scene change. Set effects on
  elements you create, not on global layers. Judge the look from the full 1-fps preview from 0 s - a clip started
  mid-song skips earlier scenes and can hide a leak (a leaked `brightness(1.6)` once washed out a whole video).
- **Never cut before the previous text is complete**: a scene cuts only after the previous line's last letter has
  landed plus 0.3 s (`textDone(li) + READ_HOLD`), ideally 0.28 s before its own first word; when lines flow together
  it may cut up to 0.3 s *after* its first word. Use `textDone()` for explicit `start:` values too. A held last
  word (measured in held.json) counts as complete only on its release - the template's `textDone` handles that.
- **LEAD**: words appear `LEAD` (0.08 s, `lyric.ts`) before their time. That is right for refined timing (default).
  With `--no-refine` (unrefined Whisper times) use ~0.2 s.
- **Fonts**: wait for them in render mode (`document.fonts.load` in main.ts) - update the list with the fonts.
- **Windows paths**: deep folders exceed MAX_PATH - keep PROJECT and the headless Chrome short (`%TEMP%/mvchrome`).
- **Browser**: render.py takes config `chrome` / env `ANIMATION_STUDIO_CHROME`, then an existing chrome-headless-shell (%TEMP%/mvchrome,
  ~/.cache/puppeteer), and only then the machine's general `browser` (Edge). A full Edge/Chrome runs in new headless
  mode; on the reference machine Edge still exits at once ("Failed to launch the browser process: Code: 0", even
  outside the sandbox) - use chrome-headless-shell (download only with the user's OK, `INSTALL_BROWSER=1`).
  Launching may need the shell sandbox disabled.
- **Sample rates**: all analysis decodes at a fixed rate through ffmpeg; if text drifts *progressively* against the
  voice, check that the stems and the mix are the same version and length.
- **File size**: grain that changes every frame multiplies the size (950 MB vs 65 MB); for small versions render
  with `--query staticgrain` or no grain. Keep the full file at CRF 20-22 unless the user wants a master.
- **Long renders** run in the background - meanwhile write the README / next scenes, but do not edit files of the
  project being rendered (Vite reloads the page).
- **Verify the final file, not the exit code**: render.py renders to `*_tmp.mp4`, checks decode errors, duration and
  audio, and keeps a new name when a player locks the old file (tell the user). Before re-rendering make sure no old
  `node`/`chrome-headless-shell` of this project is still running (never kill other agents' processes). After a
  visual change sample a frame where it should show (`render.py PROJECT sheet out/x.mp4 --times ...`).
- **Files you didn't create** in output folders (e.g. "... - Kopie.mp4"): leave them alone, mention them.

## 6. Reference material
- `references/scene-catalog.md` - every past scene, technique, identity, like/dislike. Read before designing.
- `references/engine.md` - engine architecture, scene API, SungLine/held-note options, 3D modes, recipes.
- `references/reference-tests.md` - how this skill was checked against the seven reference videos, with numbers.
- `assets/engine-template/` - the starter project (new_video.py copies it).
- `assets/examples/<technique>/` - complete `src/` + `index.html` of the past videos as technique demos with placeholder
  lyrics (open one `scenes.ts` to see how a technique was built; never copy whole scenes). Their `public/` media (song,
  role images) are not included - each README says what to supply.
- Building blocks used: song-analysis (`analyze.py`, `track_read.py`, `refine_timing.py`, `hits.py`,
  `held_notes.py`, `sync_check.py`), studio-core (`config`, `creative`, `media`, `frames.py`), film-finish
  (`encode.py` `encode_target` for the size-targeted copies, `apply_look.py` for `--look standard`).
