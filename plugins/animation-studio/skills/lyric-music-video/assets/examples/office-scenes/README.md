# office-scenes – one "office software" scene per lyric line

Technique demo: 36 short scenes, each one a mock piece of office / cloud software built in plain HTML/CSS
(team chat, cloud console access table, request log on a tilted plane, network diagram drawn wire by wire,
calendar, ticket board, terminal, spreadsheet, timesheet, video call, gauges, pipeline) or a 3D line-art view
(keynote stage with a projected screen, exploded-view "secret locker", connectivity tunnel, network topology, globe).
The lyric is typed into each scene as big bold text and the word being sung lights up green; props inside the
scene react to single sung words (`W(line, word)` gives a word's start time). A small pixel-art robot (PIP-01)
appears as a teammate with a few moods (idle, alarm, shrug, happy).

The lyrics in `src/lyrics.ts` are neutral placeholder text with the same line and word counts as the timing data.
All product and service names are invented.

```bash
npm install
npm run dev                       # interactive version (add ?t=60 to start at 1:00)
npm run render                    # → out/video.mp4 (1080p30, full quality)
npm run render -- --fps 1 --out out/preview.mp4   # fast 1-fps preview of every scene
```

The folder holds only `index.html` and `src/`. To run it, copy them into a project made from
`assets/engine-template` (package.json, tsconfig.json, scripts/render.mjs). You supply:
- `public/song.wav` – your song
- `src/timing.json` – line/word timings for your lyrics (`install_data.py` writes it); keep one lyric line per
  timing entry and the same number of words per line

The render needs a headless Chrome once:
`npx @puppeteer/browsers install chrome-headless-shell@stable --path %TEMP%/mvchrome`

## Files
- `src/scenes.ts` – the scene list: which lyric lines each scene shows and how it animates (edit texts here)
- `src/lyric.ts` – typed lyric with green highlight and block caret
- `src/world3d.ts` – line-art 3D modes: keynote stage, secret-locker exploded view, connectivity tunnel, network, globe
- `src/mascot.ts` – the pixel-art robot
- `src/lyrics.ts` – lyrics, sections and beat grid (timings from `src/timing.json`)
- `src/main.ts` – scene cuts, 3D stage, render hook
