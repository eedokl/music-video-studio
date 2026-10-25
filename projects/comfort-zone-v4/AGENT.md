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





