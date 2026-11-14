# Pop-up bubbles – technique demo

Lyric video in the style of "Pop-Up Video": every sung line pops up as a comic speech bubble with a karaoke
word highlight, and short info nuggets ("facts") pop in anchored to lyric lines. Behind them a three.js world
(server corridor, firewall wall that blocks red packets, a padlock vault, a hero cloud, scan beams, fireworks)
changes its camera path per song section. Keywords of the current line fly through the 3D scene as sprites.
Everything is a function of song time, so seeking and frame-exact export just work.

The lyrics in `src/lyrics.ts` are neutral placeholders (a song about keeping a server console running) – replace
them with your own lines, keep one entry per sung line.

## Run

```bash
npm install
npm run dev                             # http://localhost:5173  (add ?t=60 to start at 1:00)
npm run render                          # -> out/video.mp4 (1080p, 30 fps)
npm run render -- --from 20 --to 30     # quick test clip
```

Keys: Space play/pause · ←/→ seek 5 s · F fullscreen · H hide bubbles.

The render script draws every frame at an exact song time in headless Chrome (`?render=1` mode) and encodes
H.264 + AAC with ffmpeg (from `ffmpeg-static`). Options: `--fps`, `--width`, `--height`, `--out`, `--browser`,
`--crf`. It needs a headless Chrome once:
`npx @puppeteer/browsers install chrome-headless-shell@stable --path %TEMP%/mvchrome`

## You supply
- `public/song.wav` – the track
- `src/timing.json` – start/end/word times per lyric line (`install_data.py` writes it from the song analysis);
  one entry per line in `RAW`, with exactly as many word times as the line has words

## Files
- `src/lyrics.ts` – lyric lines, sections, `KEYWORDS` that fly through the scene and the pop-up info nuggets
  (`FACTS_AT`: line index, title, text)
- `src/popups.ts` – bubble overlay (pop-in, karaoke word highlight, positions)
- `src/world.ts` – 3D scene and per-section camera paths
- `src/audio.ts` – playback, frequency bands, beat detection
- `src/main.ts` – UI, title/credits cards, keyword spawning, render hook

Camera per section: verse = fly down the server corridor through the firewall to the vault; chorus/final = orbit
the hero cloud (fireworks on beats); bridge = red scan beams.
