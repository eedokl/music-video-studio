# Stadium broadcast

Technique demo: a lyric video staged as a **live TV broadcast of a stadium concert**, built in three.js.
Every scene is one camera shot + one light look + one LED-wall visual + a lyric style; everything is a
pure function of song time, so the frame-by-frame MP4 export matches playback. The lyrics in
`src/lyrics.ts` are neutral placeholder text with the same line/word structure as the timing data.

What it shows:
- **Stage**: LED wall drawn on a canvas texture, side screens with a live close-up of the singer (second
  camera rendered into a texture), truss, line arrays, moving heads with beams in haze, follow spot,
  flame cannons on big riff hits, CO2 jets at chorus starts, spark curtain on held notes, confetti on a
  chosen word, fireworks in the outro.
- **Band**: singer at the mic stand (leans in while singing, fist pump on "Hey!" words, arm out on held
  notes), guitar, bass, drums and keys moving on the beat; a bow at the end.
- **Crowd**: thousands of instanced fans jumping on the beat, arms up with the energy, phone lights in quiet
  parts; at the end the phone lights form a ring of stars seen from a sky camera.
- **LED-wall visuals** (`src/wall.ts`): one canvas function per idea - clock flip, slide deck with an
  exponential curve, split screen with a stamp, boxes merging into one memo, window + calendar flipping
  back, storm with lightning on hits, beat counter with heartbeat line, HEY! strobe, equalizer, bridge
  with a terminal typing code, branching agent tree + cracking tablet, popping bubble + growing circuit
  tree, three words + wireframe globe, news ticker, menu, split-flap departure board, timeline + table
  with an empty chair, rule book, sunrise, beat-chase stripes, crossed-out words, countdown, finale.
- **Camera**: each scene is a broadcast shot (wide, crowd, close-up, photo pit, wing, behind the drums,
  guitar, crane, LED wall, orbit, sky) with its camera label in the LIVE overlay.
- **Lyrics**: letter-synced lower third (big centre text for chants); held notes stretch with the voice
  (`src/held.json`); scene cuts wait until the previous line is complete and readable.

## Run

Copy `src/` and `index.html` into a project made from `assets/engine-template` (package.json, tsconfig,
scripts/render.mjs), then:

```bash
npm install
npm run dev                       # interactive version (add ?t=60 to start at 1:00)
npm run render                    # -> out/video.mp4 (1080p30)
npm run render -- --fps 1 --width 1280 --height 720 --out out/preview.mp4   # quick preview
```

You supply `public/song.wav` (your song). `src/timing.json`, `src/hits.json` and `src/held.json` are
regenerated for your song by `install_data.py`; then rewrite the lyrics, the scene list and the wall texts.

## Files
- `src/concert.ts` - the 3D concert (stage, lights, band, crowd, effects, camera shots)
- `src/wall.ts` - LED-wall visuals (canvas)
- `src/scenes.ts` - timeline: shot + light look + wall visual + lyric style per scene
- `src/main.ts` - frame loop, broadcast overlay, riff hits, singer performance cues
- `src/lyric.ts` - letter-synced lyrics and held notes; `src/lyrics.ts`, `timing.json`, `hits.json`,
  `held.json`, `vocal.ts` - data from the audio
