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

# Imported engines ("legacy world", `project.world = "legacy"`)

Videos built earlier with their own hand-made engine (Comfort Zone v3.2, Roles, Azure, …) keep their
ORIGINAL scenes: the old code lives in `legacy/src/` (scenes.ts, world3d.ts, lyric.ts, style.css …) and
runs as its own page. The studio only provides the data and the timeline:

- `scene.legacy` = id of the original scene (see `project.legacy.scenes`) that a studio scene plays.
  Studio scenes can be moved, split, reordered, deleted; two studio scenes may play the same original.
- Word times, unsung lines, held notes, beat grid and text lead come from project.json
  (`legacy/src/lyrics.ts` and `vocal.ts` are shims). `project.legacy.lineMap[i]` says where the original
  engine's line i (used by the original code as `L[i]` / `W(i, w)` / `T0(i)`) is now: `"l12"` (whole studio
  line), `{"id": "l12", "from": 5, "to": 8}` (words of a studio line – after lines were merged/split in an
  updated song) or `null` (no longer sung). It is recomputed at word level on every audio update from
  `project.legacy.origLines` (the original texts).
- No camera shots / looks / LED walls / events here – the look is the original code.
- To change what a scene SHOWS, edit `legacy/src/scenes.ts` (the scene's `build(root)` function; keep
  everything a pure function of `c.t` / `c.local` / `c.beat`, no timers, no Math.random). The studio
  rebuilds the bundle automatically after your reply; a build error is reported back to you.
- A NEW original scene: add an object to the SCENES array in scenes.ts (`id`, `lines`, `theme`,
  optional `three`, `build`) and reference its id from a studio scene (`"legacy": "<id>"`).
