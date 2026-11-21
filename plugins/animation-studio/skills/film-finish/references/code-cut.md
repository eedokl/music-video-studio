# Code cut: the cut as data, text and graphics in code

A second way to finish a film. Footage stays untouched (sung takes as numbered frames, stills); the cut is a JSON
file on the measured beat grid; lyrics, labels, tickers, counters and cards are drawn by a page, frame by frame, in
headless Edge/Chrome. Method after the film "You're Too Young to Remember" (Direct the Machine); first local film:
Europe 2031, 3:17, 154 parts, all 5,912 frames in 3 minutes.

Use it when the film should carry a graphic layer that follows single words and beats, when cuts inside a shot are
wanted (jump-ins, one-beat reframes), or when the cut will be changed often: a change re-renders in seconds and needs
no GPU. Use `cut.py` / `build.py` for films with transitions, paper look, sounds and credits rolls.

Script: `<plugin>/skills/film-finish/scripts/code_cut.py` (`check`, `render`, `frames`, `sheet`); page: `scripts/code_cut/`;
masks for pieces behind people: `<plugin>/skills/ai-video/scripts/near_masks.py`.
Needs config `node` and `browser`. From a Claudia project: claudia-music-video `code_film.py` writes the work folder.

## Rules (checked by `code_cut.py check`, exit code 2)

1. Shots tile the film, parts tile their shot.
2. Every cut sits on a measured beat or a word onset; exceptions are listed in `"free_cuts"`.
3. A take covers the song time of its part (`"hold": true` on a part = its last frame is held on purpose).
4. Every part has a `why` - one sentence on why this picture is here.
5. Never overwrite a render: `render` refuses an existing file. A variant (more overlays, another ending) is a new
   file next to the film; `<work>/last_render.json` names the current film - read it before building on "the film"
   (a first overlay version was once built on an older cut of the same song in another folder).

`check` also prints notes that are no errors: a stamp, title, lower third or quote that stands too short to read,
and takes that need masks.

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
  their frame `k`; `"strike": k` strikes an item through, `"numbers": false`), `counter` (from-to), `board`
  (departure-board rows), `typer` (text that writes itself), `lower` (lower third), `credits`, and the small pieces
  below.

## Small pieces on words and beats

Few, small, each on a word onset or a beat, none over a face. They make a live film feel directed without
changing the cut (user request on "Die bittere Lektion - Ein Haus, eine Nacht": "keep everything, only add a few
overlays"). Coordinates are in the 1280x720 layout.

| type | what | keys |
|---|---|---|
| `stamp` | a red stamp slams in and is held | `text`, `x`, `y`, `size`, `rot`, `color` |
| `check` | a check mark pops, words appear on their frames | `x`, `y`, `scale`, `words: [{text, k, accent}]`, `sub` |
| `sight` | a look: dots travel from eyes to a target | `from: [x, y]`, `to: [x, y]`, `rise`, `travel` |
| `rings` | a key press or touch: rings spread from a point | `at: [x, y]`, `n`, `r`, `flat` |
| `cards` | notes or cards fly off from a point | `from: [x, y]`, `n`, `size`, `side`, `fan`, `color`, `life` |
| `flip` | a calendar sheet turns over on frame `k` | `x`, `y`, `from: {label, text}`, `to: {label, text}`, `k` |
| `quote` | a quotation card with one marked phrase and the source | `lines`, `mark`, `source`, `size`, `dim` |

- **From a Claudia project write them with anchors, not frame numbers** (claudia-music-video `code_film.py`): in
  project.json `"code_layer": {"overlays": [...]}` or, better, at the shot - `sections[].code.overlays` - so that a
  piece moves with its shot:
  `{"type": "stamp", "text": "SCHALL UND RAUCH", "at": {"line": 17, "word": 7}, "side": "right", "y": 220}`.
  `at` / `until` take `{"line", "word"}`, `{"line", "end": true}`, `{"t": s}`, `{"shot": "s05"}` or `{"k": n}`; inside a
  piece: list items `at` and `strike_at`, check words `at`, flip `flip_at`. Without `until` / `len` a text piece
  stands as long as reading takes, across the cut if the shot is shorter. `"side": "left" | "right"` puts a piece
  beside the face (sung takes are framed with the face in the middle); `x` / `y` override it. `"dust"` and
  `"iris": {"at": ..., "until": ..., "c": [x, y], "r": 180}` go into `code_layer`; the masks are made on the way.
  Which piece belongs to which line is decided when the film is planned (propose one per shot or none, the user
  picks) - the script never chooses pieces by itself.
- **Read off the positions, do not guess them**: `code_cut.py sheet <work> out.jpg K K ... --grid` draws quarter and
  third lines and the frame number on every picture.
- **Text must stand long enough**: a stamp 2 s, a quote 5 s. Where the shot is shorter, let the overlay run on over
  the cut (its `k1` lies in the next part). A stamp that showed for half a second was reported as "not visible".
- **A motif beats a collection**: one piece that returns (every time she reads something: the same small check)
  reads as direction; ten different gadgets read as decoration.
- **The punchline gets the biggest piece** (key press: `rings` + `check` on the sung words), the chorus none - its
  type is already the picture.
- **Do not invent facts in a piece** (a chess move, a percentage): label them as illustration or take real ones.

### Behind people: masks

`"behind": true` on an overlay and `"dust": true` (or `{"n": 70, "color": "#FFD6A0", "a": 1}`) on a world or on the
edit are drawn behind whatever is near in the take. That needs masks: `<gpu_python> <plugin>/skills/ai-video/scripts/near_masks.py <work>` writes
`masks/<take>/NNNN.png` (alpha = near) for every take that needs one and sets `clips.json[take]["masks"]`.

- `--kind depth` (default; Depth Anything V2 Small): a whole film in about a minute on the GPU, soft edges - right
  for dust, haze, glow. Furniture in front counts as near too.
- `--kind matte --takes t1` (an ONNX matting model, config `matte_model`; CPU, about 8 s per frame): clean edges for
  the single shot where notes fly behind a person.
- Without masks dust is left out and "behind" overlays lie in front (`check` says so). Dust over a face was the
  first thing the user asked to remove.

### Ending

- `"iris": {"k0": 4068, "k1": 4104, "c": [0.49, 0.31], "r": 180, "k_small": 4090, "k_hold": 4098}` - an iris out:
  the circle closes to radius `r` around `c` (0..1 of the picture), holds, then shuts. Black follows until the film
  ends or the next card starts.
- A quote the film ends on belongs on a card that stands (`quote`, 5 s or more), not in a two-second flash between
  two other pictures.

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
