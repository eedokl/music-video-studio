# Synfig .sif format notes (Synfig 1.4 / 1.5)

Everything here was learned by trial against the renderer. When Synfig refuses a file, the error names the XML
line – open the generated .sif at that line. Synfig prints its messages in the system language; the German wording
of a message is given in brackets where it was seen that way.

## Gotchas that cost time

| Symptom | Cause / fix |
|---|---|
| Unexpected element `<distance>` (`Unerwartetes Element <distance>`) | Circle `radius`/`feather` must be `<real>`, not `<distance>`. |
| No unit in timecode, FRAMES assumed (`Keine Einheit in Timecode …`) | Bare numbers in `time=` are frames. Write `time="12f"` (`anim` does). |
| Invalid value "ease" (`Ungültiger Wert „ease“`) | Ease in/out is called `halt` in the file. TCB is `auto`. |
| `<composite>` is missing link 6 (split_radius) | Spline points need `split_radius` and `split_angle` bools (helpers add them). |
| bad time: a waypoint already exists (`Ein Wegpunkt existiert bereits`) | Two keys on one frame in one value. `anim()` dedupes (last wins), but it usually means overlapping key lists – check the intent. Half frames are rounded by Synfig – keep keys on whole frames. |
| File loads but the render fails silently | Render one frame (`render.py --single N`) and read stderr. |
| ffmpeg `Unknown encoder 'libx264'` / `No decoder for stream` | Use an ffmpeg that has libx264 and decodes PNG (config key `ffmpeg`; the ffmpeg bundled with Synfig cannot decode PNG). |
| ffmpeg `No such filter: 'drawtext'` | Many Windows builds lack it; render.py then labels contact sheets with Pillow (`--with pillow`). |
| A gradient hides everything below it | `linear_gradient` is infinite. Clip it: `clipped(desc, mask_shape, [gradient])` (blend ONTO = 13, tested). |
| `TypeError: can only concatenate list (not "str")` | Layer builders return strings. Use `[a, b] + [shape(...)]`, not `[a] + shape(...)`. |

GLib warnings about UWP apps on startup are harmless noise.

## Transform model of a group

`group(origin=o, offset=p, angle=a, scale=s)` maps a child point `q` to `p + Rot(a)·S·(q − o)`.
To rotate/scale a part around its own pivot, set **origin = offset = pivot**. To move something without changing
the pivot, animate only `offset`.

Example – an eye blinking around its own centre at (0.4, 2.1):

```python
group("Eye", [circle("White", WHITE, 0.3, (0.4, 2.1))],      # drawn at its real position
      origin=(0.4, 2.1), offset=V(0.4, 2.1), scale=anim("vector", blink_keys))
```
Drawing the circle at (0, 0) instead would place it at the wrong spot.

Nesting is how rigs are built: outer group = position + lean, inner group = squash (scale) with origin at the feet,
innermost groups = eyes (origin at the eye centre), antenna (origin at its root), etc. Because rotation comes after
scale, a negative x scale on the outer group mirrors the figure while its angle stays world-CCW.

## Animating values

- `anim(kind, keys)` with kind `real`, `angle` (degrees), `vector` (tuple), `color` (xml).
- Separate x/y timing (linear travel + eased bounce): `comp_vec(anim("real", X), anim("real", Y))`.
- Switching drawings (mouth shapes, eye states): animate the layer `amount` 0/1 with `"constant"` interpolation,
  one layer per drawing.
- The interpolation of a segment is set by the left key's *after* and the right key's *before*. Tuples
  `(before, after)` let a key be sharp on one side and eased on the other – a landing key `("linear", "halt")` hits
  hard and then settles softly.
- Baked simulations (spring antenna, falling leaf, contact) are one `"linear"` key per frame.

## Layer reference (parameters the helpers write)

- `circle`: color, radius, feather, origin (centre), amount.
- `rectangle`: color, point1, point2.
- `region` (filled spline) / `outline` (stroked spline): color, origin, bline, width (outline), amount. Bline points
  `(x, y, tx, ty[, width])`; the tangent is about 3× a Bézier handle. A circle-like loop with 4 points of radius r
  uses tangents of length ≈ 1.66·r. Zero tangents give sharp corners (stars, polygons).
- `linear_gradient`: p1, p2, gradient stops `(pos, color)`.
- `import` (`sif.image(desc, path, tl, br)`): PNGs, e.g. painted backgrounds – match `tl`/`br` to the camera view
  so it fills the frame. Tested.
- `group`: amount, origin, transformation (offset, angle, skew_angle, scale), canvas.

Other layer types – **not yet tested**; write them by hand in the same style, render one frame with `--single`, and
check stderr for parameter-name errors: `polygon`, `star`, `blur` (param `size` vector, `type` integer), `shade`
(drop shadow), `noise_distort`, `twirl`, `radial_gradient` (center, radius, gradient), `stretch` (amount vector,
center).

## Blend methods

`with_blend(layer, method)` sets `blend_method`. Tested: `COMPOSITE` (0, default) and `ONTO` (13: draw only where
layers below in the same group are opaque – used by `clipped`). From the Synfig docs, untested: `BEHIND` 12,
`MULTIPLY` 6, `SCREEN` 16, `ADD` 4, `OVERLAY` 20. ONTO is also how to paint shading/highlights that stay inside a
body: put body + shading layers in one group and give the shading ONTO.

## Canvas

`canvas(layers, w, h, fps, end, name, view)`. `view` is `"left top right bottom"` in units and acts as the camera;
zoom in by shrinking it (keep 16:9). Gamma is 1, so hex colours render as written. First layer = bottom.
Frames run 0..end (end + 1 frames).

## Rendering options

`synfig in.sif -t png -o out.png` → `out.0000.png …` for animations. `--begin-time N --end-time M` renders a
range (used by `synfig_parallel.py` and `render.py --single`). `-w/-h` override the size. Untested: `-Q 1..10`
quality (lower = better), `-a N` antialias samples.
