# Word times by hand (vocoder, robot and speech-synthesis voices)

Whisper is trained on natural speech. A vocoder line, a talk-box, a speech synthesiser or a flat spoken voice under
a loud sequencer comes back unheard ("<- estimated"), or with word starts padded by up to a second, and the repairs
of `analyze_song.py` (silence fix, repeat fix) have no reliable word to start from. First seen on a 4.5-minute
electro song: 39 lines, three voices (flat male voice, speech synthesis, vocoder); none of the automatic passes was
usable for the vocoder hook. The hand timing took less time than the attempts to repair the automatic one.

## 1. Fix the beat grid first
Everything else is placed against the bars. `analyze_song.py` prints where the grid comes from; "grid fitted to N
bass drum attacks" is trustworthy. A flux grid on machine music can be a few tenths of a BPM off (119.7 instead of
119.40 = more than a beat after 4.5 minutes). Then `bar(b) = offset + b * 4 * 60 / bpm` and the song's parts are
whole numbers of bars (8-bar verses, 8-bar hooks).

## 2. Read the word starts off the vocal stem
`analysis/vocals_lead.wav` (Demucs or the Suno stem) keeps a vocoder as a clear envelope even where Whisper hears
nothing. Compute the RMS envelope (10 ms hop), list the rises after a gap (start of a phrase) and the dips inside
a phrase (syllables), and print them next to the bar positions. A small `uv run` script with numpy is enough; the
song sheet picture (`analysis/song_sheet.png`) helps to find the phrases.
- A sung line is one or more **phrases**; note per phrase the start of every display word and the end of the phrase.
- Words that are not separated in the envelope (fast spoken syllables) are spread evenly inside their phrase.
- **Repeated hooks**: measure the clearest occurrence, then place the others by the bar pattern (same position in
  the bar, 8 or 16 bars later) and check each against its envelope rise. A hook that cannot be seen in the stem at
  all (buried in the intro) is placed by the pattern alone - say so in the delivery.
- A hook that spells letters ("El-Ge-Te-Em") may be ONE display word in `lyrics.txt`; keep the syllable offsets as
  a constant in the scene code (the scene lights one letter per syllable).

## 3. Write them down in the project
`timing_hand.py` in the project folder: a list per lyric line of `([word starts], phrase end)`; the script builds
`{"t", "e", "words", "ends"}` per line (a word ends where the next starts, the last at the phrase end), checks the
number of words per line against the automatic file and writes `analysis/timing.json`. Keep the automatic result
as `analysis/timing_auto_backup.json` (and `hits_auto_backup.json` when you set bpm / offset by hand). Never run
`analyze_song.py --redo` afterwards - it overwrites both. Then `install_data.py PROJECT`.
Set `"held_stretch": false` in project.json: held-note detection needs the voice's own loudness and pitch and
finds nonsense on a vocoder.

## 4. Check
`sync_check.py` (share of words shown while the stem is silent) and clips with `--sheet` on the first word of each
part. You still cannot hear the result: name the lines you are least sure of (quiet outro lines, words under a
loud fill) so the user listens to exactly those.
