# Stage dodge – lyric words as projectiles

Technique demo: a jointed 3D singer on a concert stage (three.js + TypeScript). Every lyric word flies at her and
arrives exactly when it is sung. Words from a "fight" list (red warning plates) are punched, kicked or blocked
away with sparks; all other words are dodged, ducked or spun past. Everything bumps on the beat, the camera cuts
on the beat grid, and every frame is a pure function of song time (seekable, frame-exact MP4 export).

The lyrics in `src/lyrics.ts` are placeholder text with the same line and word structure as the timing data;
replace them (and the `FIGHT` word list) with your own song.

```bash
npm install
npm run dev                      # interactive version (add ?t=60 to start at 1:00)
npm run render                   # -> out/video.mp4 (1080p30)
npm run render -- --from 50 --to 60 --out out/test.mp4   # quick test clip
npm run render -- --crf 28       # smaller file, looks the same
```

The render needs a headless Chrome once:
`npx @puppeteer/browsers install chrome-headless-shell@stable --path %TEMP%/mvchrome`

Keys: Space play/pause, Left/Right seek 5 s, F fullscreen, H hide captions.
Debug: `?shot=medium` (or wide, close, low, orbit, crane, crowd, reverse) locks the camera to one angle.

## You supply
- `public/song.wav` – the song
- `src/timing.json` – line and word start times (`install_data.py` writes it from the song analysis); one entry per
  lyric line, one word time per whitespace-separated word

## Files
- `src/singer.ts` – the jointed singer, beat-synced dance, and the moves (punch, kick, block, dodge, duck, spin)
- `src/words.ts` – which word gets which move, flight paths, knock-away sparks, beat bump
- `src/stage.ts` – stage, LED wall, truss + moving-head beams, amps, drums, smoke, pyro, crowd
- `src/director.ts` – camera shots and hard cuts on the beat grid
- `src/lyrics.ts` – lyrics, sections, tempo, fight-word list
- `src/audio.ts` – playback / analysis; offline analysis for the MP4 export
- `src/main.ts` – UI, captions, frame loop, render hook for `scripts/render.mjs` (from the engine template)
