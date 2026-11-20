# Code cut: the cut as data, text and graphics in code

A second way to finish a film. Footage stays untouched (sung takes as numbered frames, stills); the cut is a JSON
file on the measured beat grid; lyrics, labels, tickers, counters and cards are drawn by a page, frame by frame, in
headless Edge/Chrome. Method after the film "You're Too Young to Remember" (Direct the Machine); first local film:
Europe 2031, 3:17, 154 parts, all 5,912 frames in 3 minutes.

Use it when the film should carry a graphic layer that follows single words and beats, when cuts inside a shot are
wanted (jump-ins, one-beat reframes), or when the cut will be changed often: a change re-renders in seconds and needs
no GPU. Use `cut.py` / `build.py` for films with transitions, paper look, sounds and credits rolls.

Script: `<plugin>/skills/film-finish/scripts/code_cut.py` (`check`, `render`, `frames`, `sheet`); page: `scripts/code_cut/`.
Needs config `node` and `browser`. From a Claudia project: claudia-music-video `code_film.py` writes the work folder.

## Rules (checked by `code_cut.py check`, exit code 2)

1. Shots tile the film, parts tile their shot.
2. Every cut sits on a measured beat or a word onset; exceptions are listed in `"free_cuts"`.
3. A take covers the song time of its part (`"hold": true` on a part = its last frame is held on purpose).
4. Every part has a `why` - one sentence on why this picture is here.
5. Never overwrite a render: `render` refuses an existing file.

## Pace

Three settings decide how fast a film feels; choose them for the song, not for the method (user verdict on the first
film: the fast cut was "a bit too fast" for a 136 BPM pop song).

| | calm | medium | fast |
|---|---|---|---|
| beats per still | up to 8 | 3 | 2 (1 in a chorus) |
| cuts inside a sung take | none | one jump-in from 4 beats | jump-in from 3 beats, one-beat punch-in in long takes |
| beat pulse of the picture | 0.5 | 0.75 | 1.0 |

Europe 2031 for comparison: fast = 154 parts, median 0.93 s; medium = 115 parts, 1.37 s; calm = 89 parts, 1.87 s.

## edit.json

```json
{"fps": 24, "frames": 7304, "size": [1280, 720], "pace": "medium",
 "worlds": {"club": {"grade": {"contrast": 1.06, "saturate": 1.08, "brightness": 1.0}, "accent": "#FFD23F",
                     "pulse": 1.0, "tracker": "CLAUDIA · LIVE VOCAL"}},
 "accents": {"12": "storm"},
 "chrome": {"label": "AI-GENERATED · CLAUDIA BY ANABOLOGY", "frames": true, "bars": true, "ticker_speed": 3,
            "meter": {"title": "COMFORT ZONE", "k0": 0, "k1": 4927},
            "clock": {"from": [2026, 10, 16, 8, 0, 0], "to": [2031, 0, 1, 0, 0, 0], "k_end": 5473, "power": 3}},
 "ticker": "ticker.json", "fade_in": 10, "fade_out": 40, "free_cuts": [],
 "overlays": [{"type": "shout", "k0": 1816, "k1": 1831, "text": "HEY!"}],
 "shots": [{"id": "s13", "k0": 1365, "k1": 1473, "world": "club", "scene": "THE CLUB", "parts": [
   {"k0": 1365, "k1": 1418, "kind": "take", "src": "t2_s31", "cam": {"z": [1.0, 1.05]}, "why": "first sung line on her"},
   {"k0": 1418, "k1": 1432, "kind": "still", "src": "stills/b_hands_s2.png",
    "cam": {"z": [1.12, 1.2], "c": [0.6, 0.4], "ease": "out"}, "tag": {"text": "HANDS", "at": [0.7, 0.3]},
    "why": "drums enter on this beat: one-beat cutaway"}]}]}
```

- `k` = frame from the film start. `world` picks grade, accent colour, beat pulse and the tracker label.
- `cam`: `z` zoom from-to, `c` / `c1` centre from-to (0..1 of the picture), `ease` smooth | linear | out. A take without
  `c` is framed by its face boxes: the face sits in the upper half (`fx`, `fy` move it, `"face": false` turns it off).
- Lyrics appear word by word, one accent word per line (`accents`: line index -> word). Where a close-up leaves the
  mouth under the words, the lyric block moves to the top for the whole part (`"lyric_top"` on a part forces it).
- `chrome`: top and bottom bar (`"bars": false` removes all of it), meter, clock, label, scene slug with the frame
  number (the handle for review notes), ticker of dated facts `[{"date", "text", "source"}]` - only real, sourced facts.
- Overlay types: `title` (lines, one accent), `shout` (outline word over the frame), `flash`, `list` (items appear on
  their frame `k`), `counter` (from-to), `board` (departure-board rows), `typer` (text that writes itself), `lower`
  (lower third), `credits`.

## Findings from the first film (keep them)

- Correct the plan that writes edit.json, never the generated edit.
- Outline the lyrics; choose the accent colour per world against that world's palette (clay orange fails on red
  club light and on sunrise).
- Decide the lyric position per part, not per frame.
- The video model pushes medium shots into close-ups by itself: jump-ins of 8-12 % are enough.
- B-roll as stills moved in code holds for 1-4 beats; longer holds want a real clip.
- Image models write letters wherever objects carry them (signs, wheels, sleeves) despite "no text": check plates at
  full size, crop with `cam`, or take another seed. Every word on screen is drawn in code.
- Measure the lead stem for sung passages the lyric sheet does not list before planning takes.
