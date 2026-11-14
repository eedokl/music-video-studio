# Reference tests – talking-character

Test folder: `experiments/plugin-tests/talking-character/` (outside the plugin; reference projects stay untouched).

## 1 Rebuild of "Pip spricht" (reference `scenes/pip_spricht`)

Reference: one line by Pip, Windows voice Hedda pitched up with ffmpeg, Rhubarb (`-r phonetic`), hand-keyed
Synfig scene, 166 frames / 6.9 s at 24 fps.

Rebuild with the plugin (`pip/`):
- figure: `figures/pip.svg` – Pip redrawn as an Inkscape-style SVG with the rig convention (`kopf` pivot at the
  feet, `auge_*`, `pupille_*`, `pivot_mund`, follow parts `antenne` and `blatt`, `"arms": false`);
- set `sets/meadow` = the reference background, `"view"` = the reference camera framing;
- voice: `{"engine": "system", "voice": "Hedda", "pitch": 1.23}` (the reference's raw voice is plain Hedda at
  188 Hz, its final voice 230 Hz -> factor 1.23 measured, not guessed);
- script: `Pip: (surprise) Oh! (looks up) (pause 1.1) Ein Blatt! (pause 1.25) (cheer) Juhu, das ist mein Blatt!`
- `make.py` (Whisper on the CPU: `WHISPER_CPU=1`), then
  `check_sync.py --ref-mouth .../mund.json --ref-voice .../stimme.wav --ref-video .../pip_spricht.mp4`.

| measure | reference | plugin |
|---|---|---|
| film length | 6.90 s, 166 frames | 6.93 s, 166 frames |
| voice onsets (s) | 0.38 / 1.69 / 3.52 / 4.43 | 0.41 / 1.71 / 3.53 / 4.46 (from `song.wav`) |
| open-mouth frames | 54 | 51 |
| mouth open == voice audible | 0.897 | 0.867 |
| open-mouth track vs reference track | – | **0.970** agreement at shift 0 (best shift 0) |
| Whisper check of the lines | – | 1.00 / 1.00 / 1.00 |
| decode errors | – | 0 (film, film_small, film_mail) |

Sheets: `pip/compare_sheets.png` (left reference, right plugin), `pip/contact_sheet.png`.
Same look: shape, colours, framing, leaf, antenna; "Oh!" take with big eyes, looks up at the leaf through the
pause, hop on "Juhu" with squash/stretch and swinging antenna/leaf. Differences: the reference's hand-made
"joy eyes" (^ ^) during the hop and its soft radial shading (svg2sif draws flat colours) are not in the plugin
version; the plugin adds subtitles, a hop sound and the standard look.

Fixes found on the way (all in the skills now):
1. SSML `rate='0%'` means *slowest* in System.Speech -> 13.6 s instead of 4.6 s; prosody attributes only when set.
2. Rhubarb on a trimmed line cannot open the mouth before the sound -> every line gets 0.3 s silence on both
   sides for Rhubarb, cues shifted back (was 2 frames late; best shift -2 -> 0).
3. `lead_in`, `tail` and `(pause s)` are measured to the voice, not to the trimmed file (the 0.03/0.06 s of air
   around every line counts into them) -> 7.20 s -> 6.93 s.
4. A look direction given after the last word of a chunk holds through the pause and the next chunk
   (Pip keeps staring at the leaf while he says "Ein Blatt!").

Recording mode (`pip_recording/`: the reference's own `stimme.wav` as "recording", script without pauses):
Whisper similarity 1.0, 166 frames, mouth vs voice 0.909, open-mouth track vs the reference's 0.976.

## 2 Fresh dialogue: Tim and the Computer (`kuchen/`, seed 2611)

New idea (creative brief recorded in project.json "ideas"): Tim needs a poem for Grandma's 80th birthday, the
Computer opens "REIM.EXE" and rhymes a cliche, Tim scratches his head, the second rhyme reminds him of the cake
(scare + point at the screen), the screen shows "BÄCKEREI: LIEFERUNG 6 MIN", Tim cheers.
`new_talk.py kuchen --script kuchen.txt --seed 2611`, then `make.py` with Qwen3-TTS (references
`voice/assets/voices/tim.wav`, `computer.wav`; Computer with fx "screen").

| measure | Tim | Computer |
|---|---|---|
| Whisper per line (large-v3) | 1.00 / 1.00 / 0.985 / 1.00 | 0.966 ("Pfeilchen") / 1.00 / 1.00 |
| open-mouth frames / voiced frames | 160 / 154 | 150 / 148 |
| mouth open == voice audible | 0.907 | 0.932 |
| precision / recall | 0.844 / 0.877 | 0.887 / 0.899 |
| silent gaps (voice, mouth shut >= 0.3 s) | 0 | 0 |

Film: 19.67 s, 472 frames, 7 lines, 4 gestures (scratch, scare, point, cheer) with earshot sounds, 2 screen
texts, camera "cuts" (7 shots: two-shot, close-ups on Tim and on the screen), subtitles, standard look,
0 decode errors (film, film_small, film_mail). Sheet: `kuchen/contact_sheet.png`.
Same script with Windows voices (`kuchen_system/`, `--engine system`): 25.6 s (Hedda speaks slower),
agreement 0.935 / 0.948 – the pipeline works without the GPU.

Fixes found here: talk accents (hand flicks) overwrote gesture poses (cheer looked one-armed) -> no talk
accents inside a gesture window; an attempt to clear keys instead left a previous gesture's arm raised (removed).
