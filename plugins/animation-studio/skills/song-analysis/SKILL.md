---
name: song-analysis
description: "Building block of the animation-studio plugin – listens to a song for every music-video skill: song project folder, vocal separation (stems or Demucs), beats/bars/accents, word and line times from Whisper aligned to the lyrics and repaired from the vocal tracks, Rhubarb mouth shapes per vocal track, male/female voice track (earshot) and the assignment of who sings when to which figure. Use it through the music-video skills of the plugin, or directly when the user only wants a song's timing, an exposure sheet or a lip-sync track."
user-invocable: false
---

# song-analysis

Everything is measured on **song seconds** and written to `<project>/analysis/`.

## Project folder (`scripts/song_project.py`)

`new_project.py <folder> --song s.mp3 [--lyrics t.txt] [--lead vocals.wav --backing backing.wav] [--from s --to s]
[--lyrics-from "first sung line" --lyrics-to "last sung line"] [--language de|en|auto] [--name ...]`
creates `song.wav`, `stems/`, `lyrics.txt` and `project.json` (figures, narrator, announcements – each user skill
adds its own keys). An excerpt must come with lyrics trimmed to the sung lines.
Word triggers of all skills go through `song_project.word_matches(word, trigger)`: prefix (default, case-insensitive,
edge punctuation stripped), `"=pro"` exact word, `"re:^verkauf(t)?$"` regex; `"(word"` only calls in brackets.
`song_project.allowed(rule, section)` is the shared `"sections"` / `"not_sections"` filter, `Project.section_at(t)`
the section of a song second.

## Steps (`scripts/analyze.py <folder> [--redo] [--only 3,5]`)

1. lyrics → `lyrics_clean.txt` + `markers.json` ([Chorus], [Verse - Tim], [Spoken - narrator] with line numbers);
   warns when there are more words than can be sung in the excerpt
2. vocals: stems if given, otherwise Demucs (`separate_vocals.py`, GPU lock) → `vocals_lead.wav` (+ `vocals_backing.wav`)
3. `track_read.py`: tempo, beats with bar/beat/downbeat, accents, sections, words and lines (Whisper large-v3 on the
   GPU, small on the CPU; VAD first, retried without VAD when too few words are recognised; `--lang auto` for mixed
   languages) → `song_sheet.json` / `.csv` / `.png`
   3b. `fix_timing.py` repairs word times from the vocal tracks: calls in brackets get the backing stem's level
   bursts, order errors are fixed, a line start cut off by a long gap moves back to its line
   (measured on "Prompts!": mean error 0.38 → 0.21 s)
   3c. when lyric lines collapse onto one time (a repeated final chorus) or fewer than 60 % of the words are
   recognised, `best_words.py` runs automatically (`--no-best` skips it)
4. Rhubarb (phonetic, language independent) per vocal track → `lead_mouth.json`, `backing_mouth.json`
5. earshot "a man singing" vs "a woman singing" every 0.5 s → `gender.json` (skipped without earshot)

More tools, mostly used for lyric videos where every letter must hit the voice (see their docstrings):

| Script | Does |
|---|---|
| `best_words.py` | three Whisper passes (full mix, vocals without VAD, vocals with VAD), best pass per line merged in sung order, then `fix_timing` – rescues lines Whisper did not hear (Comfort Zone: 143 → 271 of 300 words). Repeated identical lines keep their sung order: each copy may take the timing of any copy of the same text that fits the order, and a line whose heard words lie in two occurrences keeps only one (before, the "Prompts!" final chorus collapsed: lines 63–69 all at 211.4 s; now 193.6 … 208.1 s, strictly increasing). Passes of a second model: `mix@large-v3`. `--fill --passes mix@large-v3,vocals@large-v3` keeps the sheet and only fills lines NOBODY heard (small Whisper put "Wer wird reich?" and "Der Typ ..." on one start, which cost the bridge a panel; large-v3 separates them) |
| `refine_timing.py` | snaps word starts to the real vocal onsets; a silence ≥ 0.2 s at a word start moves the word behind it; a line's last word is stretched while the voice holds it |
| `hits.py` | riff/drum hits and a constant beat grid (`hits`, `big`, `bpm`, `offset`); the autocorrelation tempo is refined on the whole song when another constant grid within ±0.6 BPM fits clearly better (Azure 113.1 → 113.47 BPM, confirmed by librosa's beats: median deviation 67 → 12 ms; `--coarse` = old result) |
| `held_notes.py` | candidates for held notes and their measured envelope (`--vocals`); `detect` / `held_words()` finds words held clearly longer than the song's normal word as one sustained note, judged on the voice – also mid-line words whose end Whisper cut short ("Fifteeeen") – `pick_held()` the 2-4 that matter, `extend_held()` moves their ends to where the voice stops |
| `sync_check.py` | word start vs. vocal onset, share of words shown before any voice, comparison with a reference timing |

`analyze.py` keeps the raw Whisper words in `analysis/whisper_raw.json`; rows that are only a `(stage direction)`
are not treated as sung lines (calls like "(Hey!)" are kept).

## Who sings (`scripts/voices.py <folder>`)

Writes `assignment.json` (mouth shapes per figure on the song timeline) and `lines.csv` (evidence per lyric line).
Rules: announcements / robotic markers → the `announcer` figure; narrator markers → the narrator; whispered /
spoken lines naming a figure → that figure; male → the `male` figure (narrated sections → narrator); female → the
`female` figure; backing stem → always the *other* figure; `corrections.json` (`from`, `to`, `figure`, `reason`) is
applied last – the listener's ear wins. Held notes are filled so no voice goes without a moving mouth; the script
reports lip-sync gaps ≥ 0.3 s.

## Pitfalls

- Sample rates: always resample properly (44.1 kHz files once drifted 8 % with integer down-sampling).
- Suno stems must come from the same version as the mix – check by correlating the stem sum with the mix.
- Whisper hears short shouted calls and vocoder parts badly; whispered lines cannot be classified male/female.
