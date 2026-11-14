# industrial-riff – stamped lyrics driven by riff hits

Technique demo for a hard, riff-driven song (industrial rock, ~97 BPM, mixed vocals). Dark industrial look:
concrete and steel, signal red, steel blue and gold, film grain, white flashes and screen shakes on the riff hits.
The lyrics in `src/lyrics.ts` are neutral placeholder text with the same line and word structure as the
measured timing data; replace them (and the scene texts) with your own song.

What it demonstrates:
- **Metal-press lyrics**: every letter is stamped in at the moment it is sung (`LEAD` in `src/lyric.ts`),
  word start/end times from Whisper in `src/timing.json`, lines shown as performed (repeats included).
- **Riff hits** (sudden loud hits after short silences, `src/hits.json`) drive white flashes, screen shake,
  RGB split and the lightning of the 3D storm.
- **Held notes** stretched with the voice (`src/held.json`, loudness + pitch per frame; two chorus words and one
  in the final chorus).
- **One scene per lyric idea**: stamped title with a ring of stars filling on the beat, rainy skyline with a
  flip clock, a wall of meetings, a slide deck flipping on the beat, an exponential chart, split screen
  (fast side deploys, slow side stamps "IN REVIEW"), five committees feeding one report, night city 3D mode,
  silhouette at a rainy window, minutes whose date runs backwards, 3D storm choruses with a glitching year and an
  EKG line, red-alarm "HEY!" scenes with one word slammed per hit, code typing itself, an agent tree, a tablet
  that shatters, a boardroom of "BUBBLE!" shouts, a growing circuit tree, three words stamped over a 3D globe,
  breaking news ticker, gala curtain, a four-course menu, split-flap departure board, quiet bridge, a question
  mark drawn on, timeline + empty chair, rulebook without author, golden dawn, crossed-out words, a rolling year
  odometer and a steel roller shutter slamming down (sparks, dust, spray-painted stencil, beacon, stars burning
  through the steel).

## Run

Copy the folder next to the engine template files (`package.json`, `tsconfig.json`, `scripts/render.mjs` from
`assets/engine-template/`), then:

```bash
npm install
npm run dev                       # interactive version (add ?t=60 to start at 1:00)
npm run render -- --out out/video.mp4            # -> out/video.mp4 (1080p30, full quality)
npm run render -- --fps 1 --out out/preview.mp4   # fast 1-fps preview of every scene
```

The render needs a headless Chrome once:
`npx @puppeteer/browsers install chrome-headless-shell@stable --path %TEMP%/mvchrome`

**You supply** `public/song.wav` (your song) and the matching analysis data (`src/timing.json`, `src/hits.json`,
`src/held.json`, `src/vocal.ts` track names), which the skill's `install_data.py` writes for your song. The data
included here only fits the placeholder structure.

## Files
- `src/scenes.ts` – every scene (texts, timing, animation)
- `src/lyric.ts` – stamped, letter-synced lyrics and the held-note effect
- `src/world3d.ts` – 3D modes; `storm` (rain, lightning, ring of stars), `city` and `globe`
- `src/main.ts` – hit flashes, screen shake, grain, scene cuts, MP4 render hook
- `src/lyrics.ts`, `src/timing.json`, `src/hits.json`, `src/held.json`, `src/vocal.ts` – data from the audio
