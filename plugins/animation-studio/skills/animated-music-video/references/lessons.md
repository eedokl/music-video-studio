# Lessons from "Prompts!" (full song, 4:08, three characters)

Every rule comes from a real mistake or from the user's feedback while making the reference film.

## Voices and mouths

- **Two questions, two sources.** *Who* sings is decided by the sound (earshot "man singing" vs "woman singing");
  *as whom* by the lyrics. Pitch does not separate them: the male singer often sits at 200–350 Hz.
- A section that names the hero in the 3rd person and never says "I" is **narrated**: it goes to the narrator while
  the hero acts the content out (worry, aha finger, head scratch, fright).
- AI songs (Suno) do not reliably follow the stage directions in the lyrics – never assign voices from directions
  alone. Exception: whispers, which earshot cannot hear; there the label decides.
- **Stems beat Demucs.** Calls in brackets live on "Backing Vocals". Whisper hardly hears short calls; their times
  come from the level bursts of the backing track (song-analysis does this in step 3b).
- **The ear wins.** Corrections by ear go into a separate file applied last, so every automatic re-run keeps them.
- Lip-sync check: voice activity per frame against open mouth shapes per frame; gaps ≥ 0.3 s (held notes) are filled
  with alternating open shapes C/B.
- A figure used as a PNG exported from the SVG (comic, credits) has **no mouth** unless you keep two exports: one
  with a default mouth (shape X) and one without.

## Picture

- **Show actions on the object.** Typing with hands hidden below the desk edge at hip height was misread. Elbows out,
  hands visible on the keyboard, keys lighting up. Check every repeated pose for unwanted readings.
- What must be in front of the body (typing, guitar, holding things) gets its own arm layers; rig arms sit behind
  the body and the hand "disappears behind the back" – reviewers notice at once.
- Text never inside panels or moving layers – the camera crops it. Gags and lyrics are screen overlays after
  rendering. Word-by-word lyrics: highlight the sung word; every word stays ≥ 0.8 s before the box fades.
- Gags the picture already shows are left out in that scene.
- Companies only as neutral lettering, the antagonist as a faceless silhouette. Image models get "no text, no logos";
  lettering is set by us.
- After script changes, spot-check data-driven badges and states in every scene (a misplaced comment once disabled a
  tier badge for the rest of the film).
- Figures must not cover the screen face: place them left and right of it (stage set default).

## Sound

- Effects ~9 dB under the music, soft sounds, 6 kHz low-pass, 10 ms fades. Hard unfiltered clicks over music sounded
  like "a broken speaker".
- Scenes write their action times (gestures, typing) to JSON; sounds are placed from that and land on the frame.
- The sound bank has no laughter or voices: use a user-made sound or a voice model; a TTS-pitched laugh sounds bad.
- Second language version: re-cutting the song to the picture sounded chopped – the original song with one global
  offset was preferred.

## Cut and build

- **One timeline for everything.** If the master audio gets a longer intro, only lengthen the intro shot instead of
  shifting all data.
- Full cut: every section from its exact song frame, clips silent, the song as one continuous track (no audio
  seams), hard cuts on section boundaries, look once over everything.
- Fixed order in one script: cut → sounds → transitions/title → credits (rebuild them after the film if they show
  film excerpts) → append credits → second language.
- **Only one session builds the film files.** Parallel builds produced broken MP4s and locked files; write to temp
  names and check every file with `ffmpeg -v error -i film.mp4 -map 0 -f null -`.
- The look must not use `-shortest` (AAC is a few ms shorter and cut the last frames).
- Compute transitions from the untouched cut file, otherwise a second run doubles every transition.
- Synfig uses only ~1.6 cores per run: render in parallel chunks (toon-2d `synfig_parallel.py`, 3–4x faster).
  `PREVIEW=1` encodes with NVENC – for work-in-progress files only.
