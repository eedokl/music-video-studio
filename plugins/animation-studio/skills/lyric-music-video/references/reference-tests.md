# Reference tests of lyric-music-video

Test folder: a scratch folder outside the plugin. The reference projects are only read, never changed.

Test songs (the examples in `assets/examples/` are the reference videos' `src/`, with placeholder lyrics):
| Song | Description | Example(s) |
|---|---|---|
| A | German/English industrial rock, 4:10 (249.6 s), 97.4 BPM, lead + chant voices | `industrial-riff` |
| A2 | second recording of song A, 3:40 (219.9 s), 95.8 BPM | `stadium-broadcast` |
| B | English pop-rock team song, 3:02 (181.6 s), 113.5 BPM | `glass-ui-mascot` |
| C | English stadium electro-rock, 3:32 (212.4 s), 123 BPM, presents a roles page | `content-cards` |
| D | English rock, 3:10 (189.6 s), 129 BPM | `stage-dodge` |
| E | English pop-rock, 3:14 (193.9 s), 137.2 BPM | `popup-bubbles`, `office-scenes` |
| F | German pop, chorus excerpt 22.8 s, with Suno lead/backing stems | (fresh-look test, no example) |

## 1. Song A, rebuilt with the plugin

**Reference**: the original music-video skill's project for song A (lyric video, 249.6 s, 1080p30) - its `src/` is
`assets/examples/industrial-riff/`, its renders the full, compressed, small and mail versions.

**How it was rebuilt**
1. `new_video.py a --song <original public/song.wav> --lyrics a_lyrics.txt --language auto --seed <n>`
   (lyrics = the example's 58 performed lines with [Verse 1]/[Chorus]/[Verse 2]/[Bridge]/[Final Chorus] headers,
   a spoken interjection in its sung place).
2. `analyze_song.py a` - fresh analysis with the building blocks only (Demucs, Whisper large-v3, alignment,
   best_words, refine_timing, hits). Nothing taken over from the original data.
3. `held_notes.py measure` for the three held words (two chorus endings, one in the final chorus) from the printed
   candidates' timing.
4. Test harness only: the example's `src/` + `index.html` copied into `a/video/`, then `install_data.py a`, then
   the interjection moved to index 57 (the original appended it as the last line and its scenes refer to that index).
5. `render.py a final --from 72 --to 100` (28 s excerpt: end of verse 1, a short spoken line, chorus 1 with its
   held note, the first chant) and `render.py a preview` (1 fps, whole song).

**Results**
| Check | Result |
|---|---|
| Tempo / beat grid | 97.4 BPM, first beat 0.028 s - identical to the original |
| Riff hits | 37 hits, 15 big - identical list, times within 11 ms |
| Word recognition | track_read alone: 143/300 words, 22 lines unheard (VAD dropped chorus 2, bridge, final chorus). With best_words (mix + vocals + VAD passes, ordered per-line merge): 271/300 recognized, 1 line unheard (a shouted chant) |
| Shown word start vs. consensus of 3 independent Whisper passes (whole song, 214 words) | plugin: median 97 ms, signed -83 ms (= the intended 0.08 s LEAD), 61 % within 150 ms, 84 % within 300 ms. Original: median 200 ms, signed **+180 ms late**, 34 % / 63 % |
| Same, excerpt 72-100 s | plugin 100 ms (59 % / 85 %), original 305 ms late (18 % / 50 %) |
| Text shown >= 0.25 s before any voice | plugin 0.7 % of words, original 2.0 % |
| Plugin vs original word starts | median shift -333 ms (whole song), -430 ms (excerpt). Inspected by hand: the original is often one word late - e.g. a two-word name: all three Whisper passes and the vocal loudness put its first word at 52.6-53.0 s, the original shows it at 53.9 s (where the second word is sung); another line: voice at 81.0 s, original 82.2 s (= the second word) |
| Held note ends | line-end extension puts the chorus-1 held note at 91.79 s (original 91.80 s) |
| Frame similarity, excerpt (12 times, SSIM on 320x180 grey) | 0.82-0.97, mean 0.878; the one outlier (73 s, 0.26) is the cut to the short spoken line happening 0.85 s earlier because the plugin's timing has its first word at 72.5 s (Whisper: 72.5-72.9 s), not 73.4 s |
| Frame similarity, whole song preview vs original (12 times) | 0.895-0.989, mean 0.968 |
| Durations | excerpt 28.00 s in all four files; preview 250 frames = song |
| Output versions (28 s excerpt) | full 59.0 MB, compressed 15.3 MB, small 28.9 MB (< 30), mail 11.9 MB (~12); 0 decode errors, audio in all |

Side-by-side contact sheets (excerpt and whole song) and the numbers were kept in the test folder.

**Fixes made because of this test**
- best_words.py (new): track_read's VAD pass lost 22 lines; per-line best of three passes, merged with a dynamic
  programme that keeps the lines in sung order (a free per-line choice pulled chorus-1 lines onto chorus 2).
- refine_timing.py: Whisper large-v3 starts a word where the previous one ended, before a pause (a word at
  38.5 s, sung at 39.5 s) - a silence >= 0.2 s inside a word's start now moves the word behind it; a line's last word
  is extended while the voice holds it (held notes ended ~0.9 s early).
- render.mjs: browser and ffmpeg come from env/machine config (no machine paths); examples now include their
  `index.html` (the Google-Fonts link lives there - without it the examples render in fallback fonts).

## 2. Fresh look test - song F (chorus excerpt, 22.8 s)

Purpose: prove that the skill still invents a new identity instead of re-rendering a past one, and test the stems path.

1. `new_video.py f --song <song_full.wav> --lead <Suno Vocals> --backing <Suno Backing Vocals> --from 45.6 --to 68.4`.
   The first attempt used the project's `song.wav` - the new stem check stopped it: that mix is another Suno version
   (1.46 s shorter, lead stem offset -1456 ms). With the matching mix: offset 0 ms.
2. `analyze_song.py f` with Whisper small on the CPU (`WHISPER_CPU=1`, the GPU was busy with other agents' jobs):
   track_read alone recognized 27/44 words; best_words (now also triggered below 70 % recognized) 40/44.
   Text shown >= 0.25 s before any voice: 0 % of words; refine moved 37/44 words (median -85 ms).
3. `brief.py f`: seed dice = drop-on-strings entrance, two colours + paper, hand lettering + clean sans,
   one continuous camera move, "a chain completes" ending. Identity + 7 ideas recorded in project.json.
4. Written for this song only: "Riso night shift" - cream newsprint, fluorescent pink + teal overprint, Caveat Brush
   lyrics dropping in on strings (custom entrance in lyric.ts), one long paper tape with seven stations (cards on
   strings, token rain + counter, keyboard keys pressed on the sung words, GPU fans + rising moon, an overflowing
   window, a melting brain on the song's held note, pull-back over the whole tape as the ending).
   None of the seven catalogued identities uses paper/riso, hand lettering, a single continuous camera or strings.
5. Preview found one rule break - the camera left station 5 before its line was complete; fixed
   by starting each glide at `textDone(previous) + READ_HOLD/2`.
6. `render.py f final`: 22.80 s; full 17.6 MB, compressed 5.3 MB, small 17.6 MB (copy, already < 30 MB), mail
   11.9 MB; 0 decode errors, audio in all.

## 3. Full-length rebuild of all seven reference videos (2026-11-14)

Each video: `new_video.py` with the original `public/song.wav` and the example's lyrics, fresh `analyze_song.py`,
held notes measured with the original names, the example's `src/` + `index.html` copied in (harness only),
`install_data.py`, `render.py preview` + `final` (all four versions). Compared at 20 times over the whole song
(SSIM on 320x180 grey) and word starts vs the consensus (median) of three independent Whisper passes
(mix, vocals, vocals-VAD; song B: passes run separately for the measurement only).

| Example (song) | SSIM mean | Plugin vs consensus: median / signed / within 150 / 300 ms | Original vs consensus | Versions (full/compr./small/mail MB) |
|---|---|---|---|---|
| industrial-riff (A) | 0.927 | 100 / -80 / 64 % / 85 % | 210 / +200 late / 36 % / 64 % | 845 / 84 / 28.5 / 12.0 |
| stadium-broadcast (A2) | 0.307 (see below); 0.916 rendered with the original timing | 100 / -80 / 61 % / 82 % | 880 / -805 (only 24 words match: timing for another take) | 427 / 132 / 28.7 / 12.0 |
| glass-ui-mascot (B) | 0.930 | 100 / -60 / 64 % / 85 % | 110 / +100 / 59 % / 78 % | 76 / 28 / 28.8 / 12.1 |
| content-cards (C) | 0.945 | 83 / -80 / 72 % / 91 % | 120 / +103 / 58 % / 81 % | 73 / 31 / 28.7 / 12.0 |
| stage-dodge (D) | 0.830 | 100 / 0 / 62 % / 83 % | 430 / +430 late / 3 % / 22 % | 301 / 107 / 28.6 / 12.0 |
| popup-bubbles (E) | 0.596 | 105 / -20 / 66 % / 90 % | 440 / +440 late / 3 % / 20 % | 285 / 107 / 28.7 / 12.0 |
| office-scenes (E) | 0.799 | 80 / -20 / 69 % / 92 % | 440 / +440 late / 3 % / 21 % | 35 / 16 / 28.7 / 12.0 |

All 28 files: duration = song, audio present, 0 decode errors. Text shown >= 0.25 s before any voice: 0-3 % of words.
Low SSIM = the same scenes cut at different moments: wherever the original's text is late (stage-dodge,
popup-bubbles, office-scenes: the old pipeline without onset refinement, ~0.44 s late, up to 1.5 s) the plugin shows
the next line/scene earlier; the pop-up bubbles and flying words make this visible in almost every sample. Checked
frame by frame on side-by-side sheets: same scenes, fonts, 3D modes, images and endings in all seven.

**stadium-broadcast (song A2)**: the original's own `src/timing.json` (and held.json) belongs to another, ~8.7 %
faster take: plugin = 1.0871 x original - 0.24 s for all 285 words (residual median 0.18 s), while hits.json and the
audio in the original MP4 equal `public/song.wav` (cross-correlation 0.999, offset 0). So the original video's lyrics
and line-keyed scenes run ahead of the voice, up to ~15 s at the end (the second-to-last line shown at 150 s, sung at
~163 s). Not a plugin or harness bug. Proof: frames at mapped times show the same scene + text, and the plugin
project rendered with the original timing/held data gives SSIM 0.916 over 44 times.

**Checklist** (OK = reproduced; data from the plugin's own analysis):
| Feature | industrial-riff | stadium-broadcast | glass-ui-mascot | content-cards | stage-dodge | popup-bubbles | office-scenes |
|---|---|---|---|---|---|---|---|
| Letter-synced text | OK | OK (original out of sync) | OK | OK (chorus 2 fixed) | OK | OK | OK |
| Held-note stretch | OK breathe1/2, go | OK glow1/2, now, wait | OK all, right | held1 + held3 OK (since the held-word fix); held2 missing | - | - | - |
| Hits / flashes (hits.json) | OK 37/15 = original | OK 104/38 (orig 100/36) | engine uses live audio | OK 41/16 (orig 40/14) | live audio | live audio | live audio |
| Beat grid | 97.4 = | 95.8 (95.7) | 113.47 since the tempo fix (orig 113.6; before 113.1) | 123.0 = | 128.6 = (129.06 after re-analysis) | n/a | 137.2 = |
| 3D modes | OK | OK concert | OK city/vault/globe | OK network | OK stage | OK corridor/cloud | OK line-art |
| Images: deal-in, drift, glint | - | - | - | OK role cards | - | - | - |
| Ending | OK shutter | OK thank-you wall | OK CRT off | OK stage chain | OK | OK | OK |
| Fonts (index.html) | OK | OK | OK | OK | OK | OK | OK |
| Versions full/compressed/small/mail | OK | OK | OK | OK | OK | OK | OK |

Open points: content-cards chorus 2 (`held2`): Whisper puts the held chorus words at 138.0-139.1 s where the lead
stem is silent (the hook is sung 134.3-136.6 s) - a word-placement problem, not a held note. The stadium-broadcast
example's textDone (and the other examples') cuts 2-3 s before a held last word is released (glass-ui-mascot's held
"all?" at 61.4 s: the plugin rebuild is already in the next scene).

**Held notes shown as performed + tempo refinement (2026-11-14, second pass)**
- Held words: song-analysis `held_notes.held_words / pick_held / extend_held`, called by `analyze_song.py`
  (-> `analysis/held_auto.json`), merged by `install_data.py`, stretched by the template's SungLine on its own.
  Song C chorus 1: the held mid-line word was 70.98-71.11 s (Whisper cut it, gap to the next word 73.60) ->
  70.98-73.44 s (voice measured); the only change to the timing (all word starts identical, sync numbers unchanged).
  Rebuild vs original at 71.2 / 72 / 73 s: SSIM 0.86 / 0.84 / 0.96 -> 0.98 / 0.97 / 0.88, the stretched word grows
  with the voice as in the original; whole video SSIM 0.945 (unchanged).
  Automatic picks per song (one per ~16 lines, sustained = <= 0.9 vocal attacks/s): C 3 words, B 3, A 4, A2 3 -
  the reference picks are among them except song A's chorus held word (1.56 s, not among the longest). Template-only test (no held options in the scene): vowels and stretch style
  both checked on a contact sheet.
- Tempo: hits.py's autocorrelation is one flux frame coarse (~0.6 BPM; song B gave 113.1 at 48 kHz, 113.5 at
  44.1 kHz). `refine_tempo` tries constant grids over the whole song within +-0.6 BPM and takes another peak only if
  it fits >= 1.25x better and its beat phase is at least as steady. Result: song B 113.1 -> 113.47, song D
  128.6 -> 129.06, songs A/A2/C/E and F (hits grid 133.2; song_sheet tempo 136.0 from track_read untouched) unchanged.
  Check with librosa's independent beat tracker (median distance of its beats to the grid): song B 67 ms (113.1) /
  46 ms (orig 113.6) / 12 ms (113.47); song D 80 -> 26 ms; song C would get worse at the other peak (122.46: 84 vs
  37 ms) and stays. Song B grid vs the original's grid: mean beat offset 141 -> 52 ms.

**Fixes made because of this test**
- studio-core `frames.py frame_at`: past the last video frame (1-fps preview whose last frame starts up to 1 s
  before the end) the `-sseof -0.1` fallback returned nothing -> PIL.UnidentifiedImageError; render.py preview
  crashed on the last contact sheet of glass-ui-mascot, popup-bubbles and office-scenes (their finals never ran).
  Now decodes the last 5 s and keeps the final frame; raises a clear error if there is still none.
- song-analysis `fix_timing.py` rule 3 (regroup): no longer moves a block of Whisper-recognized words over a > 1 s
  voiced gap with no other line's word in it (a held note or a repeat missing from the lyrics). Song C chorus 2 had
  its hook moved 2.7 s late (and the next line's last word stretched over the gap); now on time. Other six songs
  unchanged.
- engine template `scenes.ts textDone`: a line whose last word is a measured held note (overlaps held.json) is
  complete only at its release (`heldLast()`), so scene cuts no longer chop held notes. engine.md + SKILL.md note it.
