# Example: time travel through computer graphics

The fifteen worlds of the reference film, its plan and its song data - a technique demo, not a template. A German
synth-pop song about code that nobody reviews becomes a journey from an oscilloscope (1962) through wire frame,
fat pixels, shaded polygons, textures, real light, ray tracing and a "generated" world to a city of gates (2040),
and back down through all of it to a point of light.

- `src/plan.js` - the fifteen worlds in order, `END_YEAR`, the companion.
- `src/song.js` - beat grid and the word times of every line, written by hand (a new project gets this file from
  `flight.py data`; the example's worlds read their lines from it by name).
- `src/stadt.js` - the city of gates, drawable in the manner of five eras (shared by two worlds).
- `src/worlds/*.js` - one world each; `references/looks.md` of the skill says what each one shows.

To run it: make a flight (`new_flight.py`), copy this folder's `src/` over the flight's `src/` (engine.js, kit.js,
portal.js, spectrum.js and main.js stay), supply a song of the same length as `flight/public/song.wav` (4:32; the original is
not included, any audio will do to look at the pictures) and start `node serve.mjs 5245`. The film uses the fonts
Archivo 900 and IBM Plex Mono 600 (`FONT_FLAT` / `FONT_MONO` in song.js); without them the browser's fallback fonts
show and the type sits a little differently.

Open one world to see how a technique was built. Do not copy whole worlds into a new film.
