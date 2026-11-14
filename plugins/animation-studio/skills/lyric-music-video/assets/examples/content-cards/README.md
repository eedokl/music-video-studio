# Content cards – one card per sung item

Technique demo: a lyric video that presents structured content (here 15 roles of a fictional space-station crew)
from a JSON file. Every item gets its own scene exactly while the lyric line that names it is sung.

What it shows:
- **Data-driven scenes**: `src/roles.json` holds families, stages and roles (name, summary, quote, tasks, icon,
  illustration). `src/roles.ts` maps lyric line → role (`SUNG`), so the scene list is generated, not hand-written.
- **Profile card template** (`roleScene()` in `src/scenes.ts`): stage-chain bar with the role's stage(s) lit,
  icon recoloured to the family colour via a CSS mask, family label, "Role n / 15", name, quote, two tasks and
  the illustration dealt in like a card (flip, beat bump, Ken Burns drift, glint on every 4th beat).
- **Per-item visual** on the left (`V` in `src/scenes.ts`): a small animated SVG/HTML diagram that acts out the
  lyric line (noisy wave cleaned up, gauges shrinking, pipeline, neural chip, blueprint drawing, kanban, ...).
- **Recurring motifs**: pre-chorus ring that lights all item icons, chorus mosaic of all items (second chorus on
  the 3D network, final chorus with confetti), a count-up scene and a terminal-style intro and outro.
- Letter-synced lyrics (word times from `timing.json`), current word in the item's family colour, beat bump,
  riff-hit flashes and three held notes stretched with the voice (`held1`..`held3`).

The lyrics in `src/lyrics.ts` are placeholder text that keeps the line and word counts of the timing data;
replace them (and `timing.json`, `hits.json`, `held.json`) with your song's data from `install_data.py`.

## Assets you supply (in `public/`)
- `song.wav` – the song.
- `roles/<name>-icon.png` and `roles/<name>.png` – one line icon (transparent, used as a mask) and one
  illustration per role, named as in `src/roles.json`.
- `src/timing.json`, `src/hits.json`, `src/held.json` – generated from the audio (not included).

## Run
```bash
npm install
npm run dev                                       # interactive version (add ?t=60 to start at 1:00)
npm run render -- --out out/video.mp4             # 1080p30, full quality
npm run render -- --fps 1 --out out/preview.mp4   # fast 1-fps preview of every scene
```
The render needs a headless Chrome once:
`npx @puppeteer/browsers install chrome-headless-shell@stable --path %TEMP%/mvchrome`

## Files
- `src/scenes.ts` – all scenes; `roleScene()` is the per-item template, `V` holds the per-item visuals
- `src/roles.ts` + `src/roles.json` – item data and which lyric line sings which item
- `src/lyric.ts` – letter-synced lyrics + held-note effect
- `src/lyrics.ts`, `src/vocal.ts` – lyrics, sections, beat grid and held-note tracks
- `src/world3d.ts`, `src/mascot.ts` – 3D modes (network for chorus 2) and an optional cloud mascot
