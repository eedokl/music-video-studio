# Looks of the reference film

Fifteen worlds, each drawn the way computers of its year could draw. The files are in
`assets/examples/time-travel/src/worlds/` of this skill. They show techniques; a new film needs its own worlds.

| world (year) | how it is made | what to take from it |
|---|---|---|
| `oszi` (1962) | a plane fixed to the camera with a small fragment shader (trace, graticule, tube edge); the far portal is the only thing in the world | a world without a flight: things that travel with the camera; a trace driven by the voice's on/off times |
| `urdraht` (1970) | `lines()` only, one colour; letters as strokes that appear per syllable | vector letters from a stroke table |
| `pruefstand`, `alles_gruen`, `produktion` (1974-80) | wire frame with one accent colour each; a gate that counts down, rows that light up six beats ahead, a door that opens like an iris | events on local beats (`tau / BEAT`); `setOpen` on a word |
| `raster` (1983) | `res = 200`, `look = { levels: 4, dither: 1, scan: 0.18 }`, unlit and flat-shaded meshes, textures of 2 x 2 pixels | a world in its own resolution; stepped motion (`Math.floor(lb * 2)`) |
| `polygon` (1993) | `res = 360`, 24 colour levels, `MeshLambertMaterial({ flatShading })`, one sun, no textures; signs with solid boards | a little story told with boxes (a man walks home, a cube sinks away, screens change colour on words) |
| `textur` (1998) | `res = 540`, unlit meshes with drawn textures in hard pixels, halo sprites; the wall texture's offset accelerates on a word | "faster" without changing the flight speed |
| `shader` (2007) | full resolution, `MeshStandardMaterial`, one shadow light that travels with the camera, instanced bodies, points | shadows over a long road (move the light, not the map) |
| `spiegel` (2019) | one ray-marching shader: spheres, floor, sky, two bounces, soft shadows; the lines as panes that are mirrored | a world as a shader, the portal and the traveller inside it |
| `ki` (2025) | ray marching in a space that sways; goods that blend between ball and box; `noise(tau)`: the picture arrives as noise and clears in ten steps; a word is misspelt for a third of a second | the look pass's noise; events on words inside a shader (uniforms set in `update`) |
| `leere` (2027) | white background, dark lines and type, boxes that shrink to nothing on a word | a bright world between two dark ones |
| `botstadt` (2040) | the shared city (`stadt.js`: rows of towers to the horizon, a sky dome, a small environment map, a mirrored copy under a see-through street, windows that follow the song's eight frequency bands), bloom and a film tone curve (`CITY_LOOK`), a guided tour by `path(tau, D)` (up over the roofs and down again), drones that form the hook's letters in front of the camera, lyric lines built into the city | a cheap reflection; a world that listens (`levelsAt`); a flight of its own; real bloom |
| `rueckfall` | the same city with `dyn(tau)`: every two bars another resolution, look and material set, down to the wire frame | one world that changes its era while we fly |
| `schluss` (1974) | `travel` brakes, `noExit`, `landing`; everything fades except four letters that shrink to a point | an ending |

## The look pass

After a world is drawn, the engine "develops" its picture: `look.levels` (colour levels per channel, in display
values), `look.dither` (4 x 4 ordered dither, strength), `look.scan` (scan lines at the world's own line count),
then `noise(tau)` (coarse coloured noise mixed in), and lays the developed next world into the portal's hole.
`glow` is a small blurred copy of the finished picture laid over it (screen blend) - cheap bloom; its strength
blends towards the next world's in the last 1.2 seconds. `look.bloom` / `threshold` / `tone` / `exposure` is the real
thing: what is brighter than the threshold is blurred and added back (not over the portal), then a film tone curve.

## Resolution

`res` is the picture's height; the width follows 16:9. Without `soft` the picture is shown in hard pixels and
without anti-aliasing (old machines); with `soft` it is filtered (for expensive worlds). A world seen through a
portal is always shown in its own resolution, whatever the world around the portal uses.
