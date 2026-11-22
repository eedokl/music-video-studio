# Reference test

**Reference**: the portal film of a 4:32 German synth-pop song (fifteen worlds, a journey through the history of
computer graphics), built by hand before this skill existed. Its worlds, plan and song data are
`assets/examples/time-travel/`.

## What was rebuilt with the skill

A copy of the analysed song project (project.json, lyrics, song.wav, `analysis/timing.json`, `hits.json`,
`lyrics_clean.txt`, `markers.json`) - never the original project:

1. `new_flight.py PROJECT --no-install` (node_modules linked from an existing project).
2. `flight.py PROJECT check --cpu`.
3. `flight.py PROJECT clip --from 54 --to 56 --cpu --workers 2 --fps 15 --size 1280x720`.

## What was compared

| | by hand | with the skill |
|---|---|---|
| beat grid | 119.7 BPM / 0.346 s at first (wrong, see lessons.md), then 119.4 / 0.056 | 119.4 BPM / 0.056 s from hits.json |
| cut of the song | 15 worlds; crossings at 36.2, 52.3, 62.4, 70.4, 84.5, 102.6, 118.6, 134.7, 150.8, 166.9, 183.0, 191.0, 219.2, 235.2 s | 18 parts; crossings at 8.1, 22.2, 38.3, 54.3, 70.4, 84.5, 102.6, 118.6, 134.7, 152.8, 166.9, 183.0, 191.0, 221.2, 235.2, 251.3, 255.3 s |
| crossings | all seamless (measured) | all 17 seamless (picture change across a portal 7-16, its neighbours 7-15) |
| page errors | none | none |

The automatic cut finds the same bar lines as the hand-made plan from verse 1 to the last hook (70.4 to 191.0 s:
eight of nine; the ninth is 150.8 by hand against 152.8 - a breakdown whose first word comes two seconds after the bar line the hand-made plan used). It differs where
the hand-made plan followed an idea instead of the headers: the intro is one world by hand and three parts by the
headers, verse 1 is two worlds by hand, the outro one world by hand and three parts by the headers. That is the
intended division of labour - the cut is a proposal, `plan.js` is rewritten.

One picture per world from the check sheet was looked at: every starter world shows its lines, the portal and the
next world inside it; fonts were the system fallbacks.

The clip (2 s, 30 frames at 15 fps) decodes without errors, has sound and the expected length.

## Not covered

- A whole film rendered through `flight.py final` (the reference film was rendered with the same render.mjs
  before it moved into the template: 8176 frames, 31 min on the CPU).
- Frame timing on a graphics card through `flight.py check` (measured by hand on the reference film: mean 3 ms,
  0.3 % of the frames over 14 ms).
- Sound: nobody listened to a film made by the skill.
