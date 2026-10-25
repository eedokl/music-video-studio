# Agent reference

# Project format (`projects/<id>/project.json`)

One JSON file is the single source of truth. The analysis pipeline writes the measured parts
(`audio`, `grid`, `lyrics`, `hits`, `held`), the editor and the chat agent change the creative parts
(`scenes`, `events`, `looks`, lyric text/timing fixes). The preview and the MP4 export read the same
file with the same code, so they can never drift apart.

## Two timing anchors

* **Beat grid** (`grid.beats`, `grid.downbeats`) – musical events: scene cuts, light changes, pyro.
* **Word anchors** (`lyrics.lines[].words[]` with `t`/`e`) – the voice: sung text, held notes and
  everything that must follow the singer. Singing is not quantised to the beat, so words carry their
  own measured times (snapped to onsets in the isolated vocal track).

Every scene start and every event refers to one of them through an **anchor**:

```jsonc
{ "kind": "auto" }                                   // scene only: just before its first line, after the previous line is complete + readHold
{ "kind": "beat", "beat": 64, "offset": 0 }           // index into grid.beats (+ seconds)
{ "kind": "bar", "bar": 16, "offset": 0 }             // bar number: beats[downbeatPhase + bar * beatsPerBar]
{ "kind": "word", "line": "l14", "word": 7, "edge": "start" | "end", "offset": 0 }
{ "kind": "time", "t": 4.6 }                          // fallback for free moments (intro, outro)
```

If a word moves in the timeline, every scene/event anchored to it moves along.

## Top level

```jsonc
{
  "format": 1,
  "id": "comfort-zone-v4",
  "title": "Comfort Zone – Live in Brüssel",
  "storyline": "free text: what the video should tell",
  "stylePrompt": "optional: the Suno style prompt or other style notes",
  "world": "concert",                    // which 3D world the preview uses
  "audio": {
    "mix": "audio/mix.wav",              // soundtrack (always)
    "vocals": "audio/vocals.wav",        // lead vocal (Suno stem or Demucs)
    "stems": { "backing": "audio/stems/backing.wav", "drums": "audio/stems/drums.wav" },
    "duration": 219.88
  },
  "grid": {
    "mode": "fixed",                     // fixed: straight line fitted through the detected beats (stable)
                                         // follow: keep the detected beat times (tempo changes, live feel)
    "bpm": 95.7, "offset": 0.116,        // the fitted constant tempo (used when mode = fixed)
    "detected": [0.11, 0.74, ...],       // raw beat times from the analysis
    "beats": [0.116, 0.743, ...],        // the active grid (derived from mode – what anchors use)
    "beatsPerBar": 4, "downbeatPhase": 0, // downbeats = beats[downbeatPhase + k * beatsPerBar]
    "source": "drums|mix|midi"
  },
  "lyrics": {
    "lead": 0.08,                        // text appears this much before the measured word time
    "lines": [
      {
        "id": "l0", "section": "verse1", "text": "Brüssel City, Montag früh,",
        "unsung": false,                 // true: line exists in the lyrics but nobody sings it -> hidden
        "singer": "lead",                // lead | backing | all
        "words": [ { "w": "Brüssel", "t": 10.02, "e": 11.30 }, ... ]
      }
    ]
  },
  "hits": { "hits": [11.146, ...], "big": [11.146, ...] },
  "held": [ { "name": "survive1", "line": "l14", "word": 7, "t0": 57.8, "fps": 30, "env": [...], "pitch": [...] } ],
  "looks": { "chorus": { "beams": ["#e3001b", "#ffcc00"], "wash": "#e3001b", "energy": 0.9, "pattern": "fan", "pyro": true } },
  "scenes": [
    {
      "id": "s3", "name": "Brüssel 07:59",
      "start": { "kind": "auto" },
      "lines": ["l0", "l1"],             // lyric lines shown in this scene
      "shot": "wall", "seed": 3,         // camera shot (see engine) + variation
      "look": "verse1",                  // name in looks, or an inline look object
      "wall": { "type": "clock", "params": { "time": "07:59", "label": "MONTAG · BRÜSSEL" } },
      "lyr": "low",                      // low | big | side | none
      "held": { "l14": "survive1" },     // optional: held-note effect for a line
      "cam": "CAM 2 · LED",               // label in the LIVE overlay
      "notes": "free text for humans / the chat agent"
    }
  ],
  "events": [
    { "type": "co2", "at": { "kind": "word", "line": "l12", "word": 0, "edge": "start" } },
    { "type": "sparks", "at": { ... }, "until": { ... } },
    { "type": "confetti", "at": { ... } },
    { "type": "fireworks", "at": { "kind": "time", "t": 185.6 } }
  ],
  "settings": { "readHold": 0.3 }
}
```

Scenes are kept in time order; a scene ends where the next one starts.

## LED wall visuals (`scene.wall`)

Built-in types with parameters (no code needed): `title`, `bigword`, `words`, `list`, `split`,
`counter`, `clock`, `chart`, `ticker`, `board`, `eq`, `stars`, `image`.
Word-timed items use anchors, e.g. `{ "text": "Vision", "at": { "kind": "word", "line": "l2", "word": 1 } }`.

Custom visuals: `{ "type": "custom", "module": "walls/comfort.js", "fn": "deck", "params": {} }` –
a JavaScript module inside the project folder (written by hand or by the chat agent). See
`frontend/src/engine/walls.ts` for the function signature and helpers.


# Engine reference (concert world)

The preview is a stadium concert in three.js (`frontend/src/engine/concert.ts`): stage with LED wall,
side screens (live close-up of the singer), truss with 25 moving heads, follow spot, band (singer,
guitar, bass, drums, keys), ~5,000 fans, flames, CO2, spark curtain, confetti, fireworks, phone lights.

## Camera shots (`scene.shot`)

| shot | what you see | good for |
|---|---|---|
| `wide` | whole arena from the back, slow dolly | openings, fireworks, story on the wall (small) |
| `crowd` | inside the crowd, heads in front | chants ("Hey!"), energy |
| `singer` | close-up of the singer | quiet / important lines, held notes |
| `pit` | photo pit looking up, LED wall behind | big statements on the wall + singer |
| `wing` | from the side of the stage | spoken parts, variety |
| `drums` | behind the drummer, looking out | hits, outro, band energy |
| `guitar` / `bass` / `keys` | musician close-ups | instrumental parts |
| `crane` | high sweeping crane | chorus openings |
| `wall` | framed on the LED wall | story content that must be readable |
| `top` | straight down over the crowd | phone-light star ring |
| `orbit` | slow orbit around the singer | held notes, pre-chorus |

`scene.seed` varies direction/side of the move.

## Light looks (`scene.look`: a name from `project.looks` or an inline object)

```jsonc
{
  "beams": ["#e3001b", "#ffcc00", "#ffffff"],  // moving-head colours (cycled)
  "wash": "#e3001b",                           // back light / rim colour on the band
  "energy": 0.9,                               // 0..1: crowd jumping, light speed + intensity
  "pattern": "fan",                            // sweep | fan | crowd | up | still | chase
  "strobe": true,                              // strobe beams on riff hits
  "pyro": true,                                // flames on the big riff hits
  "phones": 0.7,                               // 0..1 phone lights in the crowd
  "ring": 1,                                   // 0..1 phone lights form the 12 EU stars (see shot "top")
  "follow": 1,                                 // 0..1 follow spot on the singer
  "blackout": 0,                               // 0..1 stage lights off
  "wallBright": 1                              // LED wall brightness
}
```

Effects that happen at a moment are **events** (`project.events`), not part of a look:
`co2` (at), `sparks` (at … until), `confetti` (at), `fireworks` (at). Use anchors (see project format).

## Singer performance (automatic)

Leans into the mic while singing, fist pump on words starting with "Hey", arm out on held notes
(`project.held` + `scene.held = {"l14": "survive1"}` shows the stretched vowel effect), band bows
in the last seconds.

## Lyrics (`scene.lyr`)

`low` lower third (default) · `big` centre (chants) · `side` left column · `none`.
Letters appear when sung (spread over 65 % of each word, 0.21 s stamp). `lyrics.lead` shifts all text.
Lines with `"unsung": true` are never shown.

## Scene cuts

`start: {"kind":"auto"}` = just before the first word, but only after the previous line is complete
and was readable for `settings.readHold` seconds (up to 0.3 s after the first word when lines flow
together). Use `bar` anchors to cut on a downbeat, `word` anchors to follow a specific word.


# LED wall visuals (`scene.wall`)

The LED wall is a 1280×720 canvas redrawn every frame. Times inside params are anchors
(`{"kind":"word","line":"l3","word":2}`, `{"kind":"bar","bar":12}`, `{"kind":"time","t":40.2}`) or plain seconds.

## Built-in types

| type | params |
|---|---|
| `title` | `title`, `subtitle`, `stars` (bool), `reveal` (s after scene start), `color`, `glow` |
| `bigword` | `text`, `sub`, `color`, `flash` (alternate on the beat) |
| `words` | `title`, `items: [{text, at, color?}]` – words pop in at their anchors (1–4 items) |
| `list` | slide: `title`, `color`, `items: [{text, at}]` (bullets appear) |
| `split` | `left: {title, text, at, bg}`, `right: {title, text, at, bg, stamp, stampAt}` |
| `counter` | `from`, `to`, `at`, `step` (s per step), `label`, `labelAt` |
| `clock` | `time` ("07:59"), `flipTo` ("08:00"), `flipAt`, `label` |
| `chart` | `at`, `dur`, `label`, `color`, `shape` ("up" exponential / "down") |
| `ticker` | `banner`, `text` (scrolling), `sub`, `color` |
| `board` | departure board: `title`, `rows: [[time, place, info, status], …]`, `at` |
| `eq` | equaliser bars, `title` |
| `stars` | EU star ring, `text` in the middle, `glow` |
| `image` | `src` (file in the project folder, e.g. "assets/photo.jpg"), `title`, `dim` |

## Custom visuals

`{"type":"custom","module":"walls/myvisuals.js","fn":"rocket","params":{...}}` – an ES module in the
project folder. Each exported function draws one frame:

```js
// walls/myvisuals.js
export function rocket(g, w, h, c, params, api) {
  // g: CanvasRenderingContext2D, w=1280, h=720
  // c: { t, local (s since scene start), beat (fractional), pulse (1 on the beat → 0), hit (riff flash 0..1) }
  // api.W(line, word, edge?) → screen time of a word ("l12" or 12), api.E(line) → end of a line,
  // api.at(anchor), api.timeAtBeat(b), api.image(src)
  // helpers: api.txt(g, text, x, y, size, color, align?, font?, alpha?), api.fitTxt(...maxW...),
  //          api.star, api.starRing, api.bg(g, w, h, top, bottom), api.radial, api.typed,
  //          api.clamp, api.prog, api.easeOut, api.easeOutBack, api.easeInOut, api.hash,
  //          colours api.GOLD/BLUE/RED, fonts api.HEAVY ("Anton") / api.MONO ("Space Mono")
  api.bg(g, w, h, '#05060c', '#000');
  const k = api.clamp((c.t - api.W('l4', 3)) / 1.2);           // starts when word 3 of line l4 is sung
  api.txt(g, "LET'S GO!", w / 2, h / 2 - k * 200, 110, '#fff');
}
```

Rules: draw only from `c` and params (no Math.random, no timers – the MP4 export renders frames in
any order). Optionally `export function setApi(api)` to receive the api once per frame at module level.

