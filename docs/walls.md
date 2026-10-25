# LED wall visuals (`scene.wall`)

The LED wall is a 1280×720 canvas redrawn every frame. Times inside params are anchors
(`{"kind":"word","line":"l3","word":2}`, `{"kind":"bar","bar":12}`, `{"kind":"time","t":40.2}`) or plain seconds.

## Built-in types

| type | params |
|---|---|
| `title` | `title`, `subtitle`, `stars` (bool), `reveal` (s after scene start), `color`, `glow` |
| `bigword` | `text`, `sub`, `color`, `flash` (alternate on the beat) |
| `words` | `title`, `items: [{text, at, color?}]` – words pop in at their anchors (1–4 items) |
| `list` | slide: `title`, `color`, `items: [{text, at}]` (bullets appear) |
| `split` | `left: {title, text, at, bg}`, `right: {title, text, at, bg, stamp, stampAt}` |
| `counter` | `from`, `to`, `at`, `step` (s per step), `label`, `labelAt` |
| `clock` | `time` ("07:59"), `flipTo` ("08:00"), `flipAt`, `label` |
| `chart` | `at`, `dur`, `label`, `color`, `shape` ("up" exponential / "down") |
| `ticker` | `banner`, `text` (scrolling), `sub`, `color` |
| `board` | departure board: `title`, `rows: [[time, place, info, status], …]`, `at` |
| `eq` | equaliser bars, `title` |
| `stars` | EU star ring, `text` in the middle, `glow` |
| `image` | `src` (file in the project folder, e.g. "assets/photo.jpg"), `title`, `dim` |

## Custom visuals

`{"type":"custom","module":"walls/myvisuals.js","fn":"rocket","params":{...}}` – an ES module in the
project folder. Each exported function draws one frame:

```js
// walls/myvisuals.js
export function rocket(g, w, h, c, params, api) {
  // g: CanvasRenderingContext2D, w=1280, h=720
  // c: { t, local (s since scene start), beat (fractional), pulse (1 on the beat → 0), hit (riff flash 0..1) }
  // api.W(line, word, edge?) → screen time of a word ("l12" or 12), api.E(line) → end of a line,
  // api.at(anchor), api.timeAtBeat(b), api.image(src)
  // helpers: api.txt(g, text, x, y, size, color, align?, font?, alpha?), api.fitTxt(...maxW...),
  //          api.star, api.starRing, api.bg(g, w, h, top, bottom), api.radial, api.typed,
  //          api.clamp, api.prog, api.easeOut, api.easeOutBack, api.easeInOut, api.hash,
  //          colours api.GOLD/BLUE/RED, fonts api.HEAVY ("Anton") / api.MONO ("Space Mono")
  api.bg(g, w, h, '#05060c', '#000');
  const k = api.clamp((c.t - api.W('l4', 3)) / 1.2);           // starts when word 3 of line l4 is sung
  api.txt(g, "LET'S GO!", w / 2, h / 2 - k * 200, 110, '#fff');
}
```

Rules: draw only from `c` and params (no Math.random, no timers – the MP4 export renders frames in
any order). Optionally `export function setApi(api)` to receive the api once per frame at module level.
