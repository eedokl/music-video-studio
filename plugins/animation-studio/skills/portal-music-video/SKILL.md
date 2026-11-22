---
name: portal-music-video
description: "Turn a song into one continuous flight through worlds joined by portals - a three.js film that runs live in the browser and renders frame-exact to MP4. Each part of the song is a world of its own (its own look, even its own resolution and rendering technique), every world ends in a portal that already shows the next one, and the camera flies through it on the one of a bar with no cut. The lyrics stand in the worlds as signs that appear word by word. Use whenever the user wants a portal video, an endless or continuous flight, a journey or time travel through worlds, eras or styles for a song, a fly-through music video, 'worlds connected by portals', or names the ai-portals idea - even if they only attach a song and say 'fly through it'. No AI model and no GPU job is needed (it can render on the CPU alone). Not for singing characters, brick films, AI singers or plain typographic lyric videos."
---

# Portal music video

A song becomes a flight. The film is a list of worlds (`flight/src/plan.js`), each as long as its part of the song.
Every frame draws two of them: the next world from where the camera would stand in it, and the current one, whose
portal is a hole the next picture is laid into. So what is seen through a portal is exactly the frame after the
crossing - there is no cut, even between a wire-frame world and a ray-traced one. Everything is a pure function of
song time, so the page plays live with sound and renders frame by frame to the same pictures.

The reference film (`assets/examples/time-travel/`): a 4:32 song as fifteen worlds, a journey through the history
of computer graphics - oscilloscope 1962, wire frame, fat pixels, shaded polygons, textures, real light, ray
tracing, a "generated" world, a city of gates, and the fall back through all of it to a single point of light.

**Three things matter most:** the crossings land on the beat grid of the song (measure the grid, do not trust a
guess), every world looks like its own piece and belongs to what is sung in it, and the flight never hitches.

Scripts: `F="${CLAUDE_PLUGIN_ROOT}/skills/portal-music-video/scripts"`, `L="${CLAUDE_PLUGIN_ROOT}/skills/lyric-music-video/scripts"`.
Run them with `uv run "$F/<script>.py" ...`. Tools: ffmpeg, Node.js 20+ with npm, and a Chrome or Edge
(`studio-core/scripts/check_tools.py`); a graphics card is optional.

**Building blocks** (shared code + docs of this plugin, not skills - read the one you need):
`${CLAUDE_PLUGIN_ROOT}/skills/<block>/BLOCK.md` for `studio-core`, `song-analysis`, `toon-2d`, `characters`, `voice`, `ai-video`, `bricks-3d`, `stage-3d`, `film-finish`. In those files
`<plugin>` stands for `${CLAUDE_PLUGIN_ROOT}`. First use on a machine: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py" --setup` (finds the programs).

## 1. Interview first

Ask only for what is not given. One round where possible.

- **Song file** (wav/mp3) and the **lyrics** as performed, with [Section] headers - the headers decide where the
  song is cut into worlds. Stems if there are any (cleaner word times).
- **What is the journey?** A flight needs a line that carries it through the whole song: through time (eras, the
  history of something), through places, through the stages of a process, through styles, through scale (atom to
  galaxy). Ask what the song is about and propose two or three journeys; let the user pick.
- **A traveller?** Something small may fly along through every portal and change with the worlds (in the reference
  film a cube that "grows up" with the graphics). Offer it; some films are better without.
- **On-screen rules** the user has (a name always written a certain way, words that must not appear).
- **Output**: watch live first; a render on request. Ask whether the graphics card is free - when an AI job holds
  it, the film renders on the CPU alone (`--cpu`).

## 2. Creative brief (before building)

1. Write the journey in two lines and one line per part of the song: which world, what happens to the sung words in
   it, how its portal looks. A world is not a backdrop - what is sung must happen in it ("the shop is empty": the
   goods on the shelves shrink away on that word).
2. Say which known film or video the concept would remind a viewer of, and steer away from a copy.
3. Record identity and ideas in the project (studio-core `creative.py`: `creative.add_idea(P, by, idea, where)`;
   the user's ideas with `by="user"` - they win). Show the plan; proceed unless the user wants a say.
4. Plan the **ending**: a flight that loops needs a last world that lands where the first one starts; a flight
   that ends needs a world that brakes (`travel`, `noExit`) and a last picture.

## 3. Build

1. **Song project and analysis** - with the lyric skill's scripts, the song project is the same:
   `uv run "$L/new_video.py" PROJECT --song SONG --lyrics lyrics.txt --language auto --no-install`, then
   `uv run "$L/analyze_song.py" PROJECT` (background; word times, beat grid). Read its table: lines marked
   estimated need the fixes described in the lyric skill (hand timing for vocoder and synthetic voices).
   **Check the beat grid before anything else**: `analysis/hits.json` holds `bpm` and `offset`. A grid that is a
   few tenths of a BPM off looks right for a minute and is a quarter beat off at the end - and every crossing is
   placed on it. The reference film was first built on such a grid; `references/lessons.md` has the measurement
   that shows it (distance of the riff hits to the nearest beat).
2. **The flight**: `uv run "$F/new_flight.py" PROJECT` copies the engine to `PROJECT/flight/`, runs `npm install`
   there, writes `flight/src/song.js` (beat grid, every line with its word times, the song cut into parts on bar
   lines) and prints the parts. The flight already runs through the whole song: every part has one of three
   starter worlds. After a change to the lyrics or the timing: `uv run "$F/flight.py" PROJECT data`.
3. **Watch it live** - this is the normal way to work, not the render: start `node serve.mjs 5245` in
   `PROJECT/flight` (in Claude Code a `.claude/launch.json` entry with `"runtimeArgs": ["<flight>/serve.mjs", "5245"]`
   started with the browser preview) and open `http://localhost:5245/`. A click starts the sound; `?t=<seconds>`
   starts there; space pauses, the arrow keys jump two seconds. There is no build step - reload after an edit.
4. **Rewrite the plan and the worlds**: `flight/src/plan.js` lists the worlds in order (a world module, or
   `{ mod, beats, lines }`). One file per world in `flight/src/worlds/` - `blank.js` is the smallest one; the
   contract, the kit (lines, signs, portal) and the three ways to draw a world (meshes, an own look and resolution,
   a single ray-marching shader) are in `references/world-contract.md`, the looks of the reference film in
   `references/looks.md`. Give every world to its own agent when several are built at once: the contract makes
   them independent (only `plan.js` and `song.js` are shared).
5. **Check**: `uv run "$F/flight.py" PROJECT check` (add `--cpu` when the graphics card is busy) loads the film in
   a headless browser and prints, per world, the picture change before, across and after its portal - a crossing
   that stands out is marked SEAM - then counts slow frames (not with `--cpu`), lists page errors and writes one
   picture per world to `PROJECT/out/flight_check.jpg`. Look at the sheet. Exit code 1 = a seam or a page error.
   Then watch the film once from start to end with sound: hitches and a late beat are felt, not seen in stills.
6. **Render** (only when the user wants a file): `uv run "$F/flight.py" PROJECT final --title "Song Title"` ->
   `out/<title>.mp4` (1920x1080, 30 fps) plus `_small` (< 29 MB) and `_mail` (~12 MB) from film-finish; a piece:
   `uv run "$F/flight.py" PROJECT clip --from 60 --to 70`. Run a final in the background. With `--cpu` nothing touches
   the graphics card (reference: 4:32 min took 31 min on 20 cores, `--workers 5`). A finished film is never
   replaced (`<title> v2`; `--replace` overwrites - only when the user says the old one may go).
7. **Deliver**: the files with their sizes, what each world shows (by part of the song), and what was not checked
   (you cannot hear the result; say whether somebody watched it in one piece).

## 4. Rules for worlds

- **Text follows the words, everything else follows the beat.** Signs show a word when it is sung
  (`roadSign(line, ...)`); what stands along the road is spaced in `STEP`s (the distance flown in one beat), so
  it passes on the beat; pulses use `tau / BEAT`.
- **Pure functions of time.** A world's `update(tau)` computes everything from `tau` - no timers, no
  `Math.random()` (use `hash(n)`), nothing remembered from the frame before. Frames are drawn in any order (the
  render uses several browsers at once), and a world is also drawn at negative `tau`, seen through the portal
  before it.
- **Nothing at z > 0**, and the camera must fit through the portal at the end of its path.
- **Every see-through material goes through `over()`** (kit.js): the picture's alpha channel means "here is the
  portal". A material that blends alpha the usual way lets the next world shine through everywhere.
- **A new look per world, and a reason for it.** The starter worlds and the example show techniques, never
  finished worlds to copy. When two worlds share a look the portal between them is wasted.
- **Signs must be readable while they are read**: a line appears 20-24 units ahead and is flown under about three
  seconds later; long lines are set smaller by `roadSign`. Check the middle picture of every world in the sheet.
- **The ending is part of the plan**, not the last world's problem (see 2.4).

## 5. Technical rules and gotchas (learned the hard way)

- **Hitches come from work done while the film plays.** The engine draws every world once before the start
  (`warmUp`) and keeps the number of clipping planes equal in both passes, so no shader is compiled at a crossing.
  A world that creates textures, materials or geometry in `update` brings the hitch back. `flight.py check`
  counts slow frames; the same place twice = a real cause.
- **The software renderer is correct but slow**: `--cpu` is for renders and for `check`; live work needs the
  graphics card or patience.
- **Ray-marched worlds**: never blend a distance with a placeholder like `1e5` (the result loses all precision
  and the surface turns into pixel noise - guard it: `x < 10. ? smin(d, x, k) : d`); `pow` of a negative base is
  undefined (clamp first); start mirrored rays and shadow rays a clear step off the surface. Cap them at 720
  lines (`res = 720`, `soft = true`).
- **A mirror object reads as glass** when its faces show the same sky as the background. What must stay readable
  as a body gets its own colour and bright edges.
- **Fonts**: the signs use system fonts unless `song.js` exports `FONT_FLAT` / `FONT_MONO` and `index.html` links a
  stylesheet with the `@font-face` rules (put the files in `flight/public/fonts/`); the page waits for them.
- **Beat grid**: see 3.1. When a pulse is visibly late against the music somewhere, the grid is wrong, not the world.
- **Renders are cached in segments** (`flight/out/segments/`), reused after an interruption and thrown away when a
  source file changed. Do not edit the flight while a render runs.
- **Windows paths**: keep PROJECT short (node_modules + MAX_PATH).

## 6. Reference material

- `references/world-contract.md` - the world contract, the plan, the kit, the portal, how to draw the travellers
  yourself, how to end a film.
- `references/looks.md` - the looks of the reference film and how each is made (resolution, colour levels, dither,
  glow, light, ray marching, the picture that arrives as noise).
- `references/lessons.md` - what went wrong while the reference film was built, with the measurements.
- `references/reference-tests.md` - how the skill was checked against the reference film.
- `assets/flight-template/` - the engine and the starter worlds (`new_flight.py` copies it).
- `assets/examples/time-travel/` - the fifteen worlds of the reference film with its plan and song data, as a
  technique demo (its README says how to run it; the song itself is not included).
- Building blocks used: song-analysis (song project), studio-core (`config`, `derived`, `media`, `project_check`),
  film-finish (`encode.py` for the size-targeted copies).
