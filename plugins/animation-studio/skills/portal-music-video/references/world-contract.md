# The world contract

A flight is `src/plan.js` (which worlds, in order) plus one file per world in `src/worlds/`. The engine
(`src/engine.js`, the same for every film) does the rest: two worlds per frame, the portal, the camera, what flies
along, the look of each world, the corner label.

## The plan

```js
export const ORDER = [
  intro,                                             // a world module: its own `beats`, it reads song.js itself
  { mod: gate_wire, beats: 32, lines: [LINES[0], LINES[1]] },   // or: length and lines given here
];
export const COMPANION = true;   // false: nothing flies along
export const END_YEAR = null;    // worlds with a `year`: where the last world's number runs to
```

The beats of all entries together are the length of the song (`SONG_END / BEAT`); the first and last may be
fractional. `SECTIONS` in `song.js` is the cut that `flight.py data` proposes (parts start on the bar line nearest
to the first word after a [Section] header; 24 beats without words make a part of their own). A crossing happens at
the end of an entry - keep them on bar lines.

## A world module

```js
export const id = 'my_world';
export const beats = 32;             // unless the plan gives it
export const carryColor = 0xffffff;  // colour of what flies along
// optional
export const year = 1983;            // number in the corner, runs towards the next world's year;  or  label = 'text'
export const carryStyle = 'solid';   // 'wire' | 'solid' | 'gem' | 'crate' | 'orb' | 'none'
export const res = 200;              // picture height in pixels (0 = full); shown in hard pixels
export const soft = true;            // with res: shown smooth instead (expensive worlds drawn smaller)
export const look = { levels: 4, dither: 1, scan: 0.18 };   // colour levels per channel, dither, scan lines
                                     // or { bloom: 0.3, threshold: 1.1, tone: 1, exposure: 1 }: real bloom + film tone curve
export const glow = 0.4;             // 0..1: strength of the soft glow laid over the picture
export const flight = { sway: 2, waves: 1, phase: 0, rise: 0.5, hop: 0, fov: 60 };   // the camera's path
export const rollIn = true;          // the camera rolls once around its axis while it enters
export const noExit = true;          // the film ends here: nothing darts ahead to a portal
export function dyn(tau) { ... }     // any of res, soft, look, glow, carryStyle, carryColor, changing over time
export function noise(tau) { ... }   // { amount, seed }: the picture is still partly noise
export function travel(tau) { ... }  // distance flown (default V * tau; must be V * tau for tau < 0)
export function path(tau, D) { ... } // { x, y, look, w }: its own flight - sideways / upward offset in units and a point the
                                     // camera turns to with weight w; x, y, w must be 0 at both portals

export function build({ t0, L, D, beats, lines }) {
  // t0 = song second of the world's start, D = its length in seconds, L = its length in units,
  // lines = what the plan gave: [{ text, words, at }] (at = song second of every word)
  return { scene, portal, update(tau), carry(tau), onPass(info), landing(tau) };   // the last three are optional
}
```

- The camera enters at `z = 0` and leaves through the portal at `z = -L`, flying towards `-z` at `V` units per
  second. One beat = `STEP` units. Build nothing at `z > 0`.
- `tau` is the world's own clock in seconds. It is **negative** while the world is only seen through the portal
  before it - `update` must work there too (words not yet sung are hidden, nothing has happened).
- `update(tau)` is a pure function of `tau`.

## The kit (`src/kit.js`)

| | |
|---|---|
| `lines(positions, { color, width, opacity })` | fat lines from a flat list `[x1,y1,z1, x2,y2,z2, ...]`; width in world units |
| `seg`, `rectXY`, `ringXY`, `boxEdges` | fill such a list |
| `word(text, { font, size, color })` | one word as a plane; `size` = height of a capital in units |
| `sign(words, at, { z, y, size, font, color, posts, board })` | a line across the road; every word appears at its time (world clock) |
| `roadSign(line, t0, L, ahead, opts)` | the same for a song line, placed `ahead` units before the camera at its first word; long lines smaller |
| `sevenSeg()` | a seven-segment digit (`show(0..3 or null)`) |
| `canvasTex(w, h, draw, { pixel, repeat })` | a drawn texture; `pixel` keeps hard pixels |
| `over(material)` | **every see-through material**: alpha blended as coverage (see below) |
| `rausShots(times, t0)` | a `carry` function: extra bodies that overtake the camera at those times |
| `hash(n)`, `ease(x)`, `clamp(x)` | deterministic noise, smoothstep, clamp |
| `FLAT`, `MONO` | the two typefaces of the signs |
| `levelsAt(t, out)` (`src/spectrum.js`) | the song's level in eight frequency bands (bass ... highs, 0..1) at song second `t` - for things that listen (windows as a level meter); written by `flight.py data` |

## The portal (`src/portal.js`)

`makePortal({ shape: 'rect' | 'circle', w, h, r, veil, rim, flat })` returns `{ mesh, mat, setOpen(0..1) }`. Place
the mesh at the end of the road (`z = -L`), give it a frame of your own. `setOpen` grows the opening from the
centre (a door that opens on a word). `flat` is the colour it shows when it is itself seen through another portal.

The opening draws nothing: it writes alpha 0 into the world's picture, and the engine lays the next world into every
pixel with alpha 0. That is why transparent materials must blend alpha as coverage (`over()`): the default blending
squares it, and the next world would shine through every half-transparent line.

A world that draws itself in one shader does the same in its shader: a ray that reaches the portal's disc before
anything else writes `vec4(0, 0, 0, 0)` (or the flat colour when `uFlat` is set), and the world returns
`portal: { mat: { uniforms: { uFlat } } }` so that the engine can switch it (`worlds/mirror_hall.js`).

## Three ways to draw a world

1. **Meshes and lines** (`gate_wire.js`): a three.js scene; signs, lights, materials as usual.
2. **Its own picture** (`pixel_hall.js`): `res` + `look` draw the world small, in few colours, dithered - and the
   portal still shows the next world in the next world's own resolution.
3. **One shader** (`mirror_hall.js`): a full-screen quad that marches rays; reflections, soft shadows, the song
   lines as panes of light that are mirrored too. `carryStyle = 'none'` and `onPass({ cam, items, side })` to draw
   what flies along itself (cut at the portal's plane: `side` is `'here'` or `'next'`).

## What flies along

The engine moves a small body with the camera (a figure of eight, a nod on every beat, a trail) and lets it dart
ahead through every portal. Its shape is the world's `carryStyle`, its colour `carryColor`. `carry(tau)` adds more
bodies (offsets relative to the camera). `landing(tau)` -> `{ x, y, z, k, gone }` lets it settle at a place in the
last world (`k` 0..1) and fade (`gone`).

## Ending a film

- **A loop**: the last entry's portal leads into the first world; make the last picture meet the first.
- **An end**: the last world exports `noExit = true` and a `travel(tau)` that brakes
  (`V * T * (1 - Math.exp(-tau / T))` comes to rest after `V * T` units), returns a portal object without a mesh,
  and fades its own things. The reference film's `schluss.js` shrinks its last word to a point of light.
