# Engine reference (assets/engine-template)

The engine lives in `<project>/video/` (copied by `new_video.py`). Its data files come from the song project's
`analysis/` via `install_data.py`; render it with `render.py` (which calls `scripts/render.mjs`).

Vite + TypeScript + three.js. HTML/CSS for 2D scenes, a three.js canvas behind them for 3D modes.
Everything is a **pure function of song time**, which is what makes the MP4 export frame-exact:
`scripts/render.mjs` opens the page in headless Chrome with `?render=1`, calls
`window.__renderFrame(t)` for every frame and pipes screenshots into ffmpeg together with the audio.

## Files
| File | Role |
|---|---|
| `src/main.ts` | Scene manager (builds a scene when its time starts), black-dip cut, riff-hit flash/shake/RGB split (from `hits.json`), film grain hook (stands still; `?movinggrain` moves it every frame = ~10x the file size), `VARIANT` body class, render hook, live player UI |
| `src/scenes.ts` | **The video**: `SCENES` list + timeline rule. This is what you rewrite per song. |
| `src/lyric.ts` | `SungLine` (letter-synced lyric), `HeldWord` (held-note stretch), `heldFx()`, `LEAD` (0.08 s after refine_timing) |
| `src/lyrics.ts` | Lyric lines + sections, `SONG_END`, `BPM`, `BEAT_OFFSET`, `beatAt()`, `beatTime()`, `beatLen()`, `snapBeat(t, div, dir)` – `SEED` – filled by `install_data.py` |
| `src/timing.json` / `hits.json` / `held.json` | Data from the audio: `[{t, e, words[], ends[]}]` per lyric line (one entry per space-separated display word), `{hits, big}`, `{name: {t0, fps, env, pitch}}` |
| `src/vocal.ts` | Reads held.json: `vocalEnv(track, t)` 0..1, `vocalPitch(track, t)` ≈ −6..6 semitones |
| `src/world3d.ts` | 3D modes (storm, city, network, globe, vault, tunnel) – recolour constants at the top per video |
| `src/util.ts` | `mk`, `prog`, `easeOut`, `easeInOut`, `easeOutBack`, `hash`, `popStyle`, `slideIn`, `typed` |
| `src/kit.ts` + `kit.css` | Optional motion-graphics kit: `stage()` (1920 x 1080 in px), `box`, `up` / `pop` / `stamp` / `hit`, self-drawing SVG (`svg`, `path`, `reveal`, `poly`), `subs()` subtitle lyrics, `kinetic()` big type with beat pulse, `flap()` split-flap cell, `chess()` board with moves, `scrollList()` |
| `src/audio.ts` | Playback for the live version |
| `scripts/render.mjs` | Export (browser + ffmpeg from env ANIMATION_STUDIO_CHROME / FFMPEG or the machine config). Options: `--fps 30 --width 1920 --height 1080 --crf 18 --from S --to S --out out/x.mp4 --query movinggrain`; an uncaught error while the page loads stops the render at once (exit 3) |

## Scene API (scenes.ts)
```ts
{
  id: 'approval',
  lines: [11],                 // lyric lines in this scene; the first decides the start time
  theme: 'dark',               // 'dark' | 'light' (#bg colour)
  three: 'network',            // optional 3D background
  opts: { vocal: 0 },          // passed to the 3D mode every frame (mutable: scenes may update it)
  start: 124.0,                // optional explicit start (intros, instrumental parts)
  build(root) {                // create DOM once
    const up = lyrics(root, [11], 'top big', false, { 11: { held: 'all' } });
    return (c) => {            // every frame: c.t, c.u (0..1 in scene), c.local, c.beat, c.pulse
      up(c.t, c.pulse);
      ...set styles from c.t...
    };
  },
}
```
Timeline: a scene runs from its start until the next scene starts. Start rule for lyric scenes:
`min(line.t + 0.3, max(line.t − 0.28, textDone(previousLine) + READ_HOLD))` – just before the first word, but
only after the previous line is fully stamped and was readable for 0.3 s. When a line's last word is a measured held
note (its span overlaps a track in held.json, `heldLast(li)`), `textDone` is the end of the held note: the
HeldWord lands its ending letters on the release, so the cut must not come mid-note (the stadium-broadcast example's
own textDone capped the word at 1.4 s and cut away 2-3 s before "wait." ended). Words appear `LEAD` (0.08 s with refined timing, ~0.2 s without) before their measured time because
unrefined Whisper times on a full mix come ~0.17 s late (song-analysis `refine_timing.py`, run by `analyze_song.py`, fixes that per word).

Helpers in scenes: `W(li, wi)` = time word wi of line li appears, `T0(li)`, `E(li)`;
`lyrics(parent, lines, cls, replace, lineOpts)`.

Lyric classes (template CSS): `top`, `bottom`, `center`, `huge`, plus your own. Current word: `.sw.now`.

## SungLine options
- `{ mode: 'type' }` – typewriter with block caret (terminals, screens).
- `{ autoHeld: false }` – no automatic held-note stretch in this line; `{ heldStyle: 'stretch' }` – style per line
- `{ held: 'track', heldWord?: n, heldVowel?: i }` – held-note stretch on word n (default last), stretching
  letter i (default: vowel of the last syllable; give `heldVowel` for words like "roles" → 1).
- Default mode: letters stamp/pop in (edit the pop formula in `update()` for a different feel per video).

## Held notes – full recipe
Automatic (default): `analyze_song.py` picks the 2-4 sustained held words (song-analysis `held_notes.held_words` /
`pick_held`, also mid-line words like "All" in "One station! All aboard!"), extends their ends to where the
voice stops and measures them into `analysis/held_auto.json`; `install_data.py` merges them into `src/held.json`
as entries with `"auto": true, "line", "word", "word_t", "word_end", "vowel"` (`AUTO_HELD` in vocal.ts). Every
`SungLine` stretches such a word by itself unless the line has `held` set or `autoHeld: false`. `HELD_STYLE` in
lyrics.ts (project.json `held_style`): `'vowels'` repeats the vowel (5-8 copies, ~3 per held second, as in the
reference videos), `'stretch'` widens one vowel up to 4x; `LineOpts.heldStyle` overrides it per line.
By hand:
1. `analyze_song.py` lists words sung > 1 s (song-analysis `held_notes.py candidates` does the same for any timing).
2. `held_notes.py measure PROJECT/song.wav PROJECT/analysis/held.json name:start:end ... --vocals PROJECT/analysis/vocals_lead.wav`
   (start ~0.2 s before the word, end ~0.3 s after; the candidates print a ready spec).
3. `install_data.py PROJECT` copies held.json and updates `TrackName` in vocal.ts.
4. In the scene: `lyrics(..., { li: { held: 'name', heldWord: k } })`; optional reaction with
   `const fx = heldFx(c.t, L[li], 'name')` → `fx.env` (voice loudness while held), `fx.release` (flash after).

## 3D modes
Set `three: 'storm' | 'city' | 'network' | 'globe' | 'vault' | 'tunnel'` and `opts`:
storm `{ energy, scatter, light }` (+ flash/boltSeed injected from hits), city `{ energy }`,
network `{ vocal, release }`, vault `{ cage }`, tunnel `{ success }`. Recolour via the constants at the
top of world3d.ts and the materials in each `build*()`. New world: add a group in the constructor,
a `build*()` and a `case` in `update()` (set the camera first, then compute labels).

## Recipes from past videos
- Recoloured icons: CSS mask (`-webkit-mask: url(icon) center/contain no-repeat; background: var(--fc)`), needs transparent PNG/SVG.
- Source images embedded as base64 in an HTML page: extract with a regex over the `data:image/...;base64,` URIs.
- Silhouettes: separate SVG shapes (one path with overlapping sub-paths creates holes).
- Split-flap board: random letters from `hash(floor(t*20)+i)` until a settle time.
- Odometer: strips with digits 0–9 twice, translateY by a continuous value (so 9 → 0 keeps rolling).
- CRT switch-off: content scaleY → 0.006 with brightness up (0.22 s), white line scaleX → 0.01 (0.28 s), dot fades (0.8 s), LED off.
- Shutter: ribbed panel translateY −100% → 0 with ease-in, tiny bounce, stencil title stamped after.

## Text follows the words, graphics follow the beat
Lyrics appear on the sung word (`W(line, word)`); every *graphic* event lands on the beat grid. Events hung on word
times look almost right and feel loose - measured on a reference video frame by frame: chess moves one per beat,
list ticks and cards one per half beat, stamps and branch points on the beat, a highlight hopping every half beat,
and in the choruses the whole type block bumps (+1.5 %) and brightens on every beat. Verses have no constant pulse.
```ts
const B = beatLen();                              // inside build(), never at module top level
const t0 = snapBeat(W(li, 3), 2);                 // the half beat nearest to the sung word
rows.forEach((r, i) => up(r, c.t, t0 + i * B / 2));          // one row per half beat
stamp(el, c.t, snapBeat(W(li, 7), 2) - 0.1);                 // starts 0.1 s early, lands on the grid
el.style.transform = `scale(${1 + 0.1 * hit(c.t, t0)})`;     // accent on landing
kin(c.t, c.pulse);                                           // kinetic(): bump + brightness on every beat
```
A piece that moves for 0.3 s starts early enough to *arrive* on the beat. Counters and continuous draws (a curve, a
scrolling list) stay continuous; give them a small `c.pulse` bump instead.

## One continuous world instead of scenes
A video may be ONE scene (`start: 0`) that drives its own three.js world: a camera ride whose position is a pure
function of song time (distance = integral of a piecewise-linear speed, so it can stop in a breakdown and double in
a fast part), stations placed where the camera is at their bar (`z = -S(time) - ahead`), lyrics laid over it as
HTML. What worked (a wire-frame factory, 4:33):
- **Own renderer, built once**: a singleton with its own `WebGLRenderer` whose canvas is appended again in `build()`
  (the scene manager rebuilds scenes on a seek); `preserveDrawingBuffer: true` in render mode (`?render`), so that
  the screenshot and the afterglow copy read a finished picture.
- **Fat lines**: `LineSegments2` + `LineMaterial` (three/examples/jsm/lines), `fog: true`, `linewidth` in px - plain
  `LineBasicMaterial` is 1 px on every machine. Set `material.resolution` in `resize()`.
- **Things draw themselves** while the camera approaches: `geometry.instanceCount = ceil(k * segments)` with k from
  the distance - no extra geometry, exact per frame.
- **Afterglow without a bloom pass**: copy the WebGL canvas every frame into a small 2D canvas (960 x 540) over a
  translucent black fill (alpha 0.4 = short trail, 0.13 = long streaks at speed), show that canvas on top with
  `filter: blur(7px) brightness(1.6); mix-blend-mode: screen`. `EffectComposer` + `UnrealBloomPass` turned the whole
  black picture grey (thin lines, threshold useless) and was removed. The trail depends on the frames before: a
  seek shows it after a few frames - render clips from a second earlier than the moment you judge.
- **Picture tube**: render into a `WebGLRenderTarget` (`samples: 4`, otherwise the lines lose their antialiasing),
  then one full-screen `ShaderMaterial` quad: barrel bulge, colour fringe, shifted bands for a glitch; end the
  fragment shader with `#include <colorspace_fragment>` or the picture comes out too dark. Scan lines and vignette
  are a CSS gradient on a div above everything (free, but they change every pixel: file size).
- **Glitches are events**: two or three in a song, on a word that means failure, strength from `hit(t, t0, 0.4)`;
  band offsets from `hash(floor(t * 15))` so every render is the same.
- A piece that travels with the camera (a counter on the horizon) will stand in front of whatever comes next on
  the road: keep it to one side or hide it while a gate or a title is in the picture.

## Effect levels - stages of the build as a page parameter
`export const FX = Number(new URLSearchParams(location.search).get('fx') ?? 4)` and `if (FX >= 3) ...` around each
batch of effects: `/?fx=2&t=95` shows an earlier stage live, `render.py ... --query fx=2` renders it. The user
compares stages without a render per stage, and "less of it" is one number instead of a revert.

## Variants - another cut of the same song
Same song and timing, other scenes (a second look, a homage, a short version): put the scenes into their own file,
register them in `VARIANTS` (scenes.ts) and render with `--variant NAME`. The page gets `?v=NAME`, the body the class
`v-NAME` (scope the variant's CSS with it and hide what it does not use, e.g. `#grain`), the files are named
`preview_NAME.mp4`, `clip_NAME_…`, `<title> (NAME).mp4`. The default cut stays untouched.

## kit.ts in short
`const st = stage(root)` then lay out in pixels: `box(st, 'cls', x, y, text?, w?, h?)`. `subs(st, lines)` shows the
lyric as a subtitle line (word rises in, only the sung word white + underlined, then grey); `kinetic(st, rows)` big
words slamming in from a blurred ghost. Self-drawing line: `const p = path(svg(st), d, colour); reveal(p, 0..1)`.
`scrollList(...)`: `update(n * prog(t, a, b))` lets lines arrive while the list scrolls smoothly, `follow(k)` scrolls
a full list (lines being struck out). Both subtitle and letter-synced lyrics (`SungLine`) may be used in one video.
