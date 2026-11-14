# Glass UI mascot

Technique demo: every lyric line is typed into a piece of fictional software UI (a "cloud console" with invented
services), on a glass look - soft gradient blobs, rounded window-title pills, glass panels, a diagonal wipe between
scenes - with a small cloud mascot (PIP) that reacts to the song. The lyrics in `src/lyrics.ts` are placeholder text
with the same line and word structure as the timing data.

What it shows:
- **Letter-synced lyrics**: every letter pops in while its word is sung, spread over the word's real duration
  (word start/end times in `src/timing.json`); the word being sung is tinted. `LEAD` in `src/lyric.ts` shifts all text.
- **Beat bump**: the lyric block bumps on every beat of the detected grid (`BPM`, `BEAT_OFFSET` in `src/lyrics.ts`).
- **Held notes** (`held: 'all'`, `held: 'right'`): the vowel stretches while the note is held, waves with the
  loudness, a ribbon traces the pitch, the last letters burst in on the release. The scene reacts via `heldFx`
  (a trembling dialog with streaming question marks; the 3D network pulses and flashes). Data: `src/held.json`,
  read by `src/vocal.ts`.
- **UI scenes as pure functions of time**: notification toasts, IAM table, scrolling request log, hub-spoke
  diagram drawn wire by wire, roadmap pin, code diff, kanban board, calendar, terminal sessions typed in sync,
  checklists, timesheet filling up, gauges, pipeline stages, paperwork tower landing on the beat.
- **3D line-art modes** (`src/world3d.ts`): cloud city, exploded-view secret locker, connectivity tunnel, network
  topology, globe.
- **Mascot** (`src/mascot.ts`): SVG cloud with moods (idle, happy, shrug, alarm, sad), bobbing on the beat.
- **Ending**: a monitor types the last line in time with the singing, then switches off like an old CRT
  (squash to a line, then a dot, then black).

## Run

```bash
npm install
npm run dev                       # interactive (add ?t=60 to start at 1:00)
npm run render                    # -> out/video.mp4 (1080p30, full quality)
npm run render -- --fps 1 --out out/preview.mp4   # fast 1-fps preview of every scene
```

The render needs a headless Chrome once:
`npx @puppeteer/browsers install chrome-headless-shell@stable --path %TEMP%/mvchrome`

Copy `src/` and `index.html` into a project made from `assets/engine-template` (it has `package.json`,
`tsconfig.json` and `scripts/render.mjs`).

**You supply**: `public/song.wav` (your song), and `src/timing.json` + `src/held.json` for it
(`install_data.py` writes them; replace the placeholder lines in `src/lyrics.ts` with your lyrics, one entry per
timed line).

## Files
- `src/scenes.ts` - the scene list (texts, timing, animation of every scene)
- `src/lyric.ts` - letter-synced lyric (`LEAD` = timing offset) and the held-note effect
- `src/world3d.ts` - 3D modes: cloud city, secret locker, tunnel, network, globe
- `src/mascot.ts` - the mascot PIP
- `src/vocal.ts` + `src/held.json` - voice loudness/pitch of the two held notes
- `src/lyrics.ts` + `src/timing.json` - lyrics, word start/end times, tempo
- `src/main.ts` - scene cuts, wipe, render hook
