# stage-3d – scene author's guide (API, craft, working method)

Read this before writing or changing a scene module (`scenes/<clip>.py` of a 3D film project).
Scripts named here live in `skills/stage-3d/scripts/` of this plugin (how to run them: BLOCK.md).

## World conventions

Metres, Z up. Figures are ~0.85 m tall (own casts: up to ~1.3 m) and **face -Y at heading 0**; the camera is
normally on the -Y side looking towards +Y, so +X is screen right. Heading is in degrees about Z, positive turns
the figure towards +X (screen right). Anatomical left = +X when facing the camera.
Frames are 1..FRAMES at 24 fps. All angles in the APIs are degrees.

## Animation model (stage_core)

Every animatable value is a channel (`Ch`) with keys `(frame, value, ease)`; the ease belongs to the segment
*arriving* at the key: `"io"` (default, smooth), `"lin"`, `"in"`, `"out"`, `"out3"`, `"hold"` (stay on the old
value, jump at the key – use it for cuts), `"back"` (overshoot), `"spring"`, `"bounce"`. Channels also take
additive layers `ch.add(lambda f: ...)` and multiplicative ones `ch.mul(...)`. Everything is sampled per frame
when the clip is built – you never touch Blender keyframes. A channel with one key is constant.

```python
n = Node(S, obj)                 # or P.grp(S, name, loc) for an empty group
n.loc(f, x, y, z, ease)          # any component may be None
n.rot(f, x, y, z, ease)          # degrees
n.scl(f, s) / n.scl(f, x, y, z)
n.lch(i) / n.rch(i) / n.sch(i)   # the raw channel, e.g. n.lch(2).add(lambda f: 0.02 * math.sin(f * 0.1))
n.pop(f, dur=7) / n.unpop(f)     # scale 0 -> 1 with overshoot / back to 0   (signs, bubbles, cards, stars)
n.show(f_on, f_off)              # render visibility of the object and its children
n.cut(f)                         # declare a teleport at frame f (prevents a motion-blur streak)
S.vis(obj, f_on, f_off)          # visibility of one object
S.ch(idblock, "data_path", index, default)   # any other property, e.g. S.ch(light.data, "energy", 0, 0.0)
```
Objects that should not exist yet: `pop()` them or `show()` them; an object that was never keyed is always there.
Primitives (`ell, capsule, box, cyl, torus, lathe, plane, tube, text`), materials (`mat, felt, emit, glass,
image_mat, wood`), lights (`area, spot, point, sun, world, fog`): see the docstrings in `stage_core.py`.
`C.load_json("rel/path.json")` reads a file of the project (e.g. a list of sound frames).

### Camera

```python
cam = S.shot(f0, loc, aim, loc1=None, aim1=None, f1=None, lens=50, fstop=2.8, focus=None, ease="io", shake=0.0, roll=0.0)
```
A cut at frame `f0` to a new camera at `loc` looking at `aim`; it optionally travels to `loc1/aim1` until `f1`
(default: until the next cut). The shot list is the edit of the clip. More moves: `cam.move(f, loc, aim, ease)`,
`cam.lens(f, mm)`, `cam.focus(f, point)`, `cam.fstop(f, v)`, `cam.roll(f, deg)`, `cam.handheld(amp)`. Depth of
field focuses on the aim point unless `focus` is given. `fstop=None` disables DOF. Helpers (they read the
figure's position at `fref` or `f0`):

```python
shots.closeup(S, f0, char, dist=1.9, yaw=14, up=0.03, lens=65, push=0.08, fref=None, dz=-0.04)   # head & shoulders
shots.medium(S, f0, char, dist=3.0, yaw=10, lens=50, dz=-0.15)                                    # waist up
shots.two_shot(S, f0, a, b) ; shots.ots(S, f0, speaker, listener)
```
`yaw` rotates the camera around the figure relative to *its heading* (0 = straight in front of it). The default
distances suit figures of ~1.2 m; for the small bundled toys go closer (`dist=1.3` / `2.2`) and check that the
table does not hide them.

## Figures (stage_actor)

```python
cast = K.cast(S, {"mo": "bear", "kit": {"look": "cat", "glasses": True}, "olga": Olga})   # looks or Char subclasses
c.at(f, x, y, heading, ease="hold")    # place / move the root (use ease="hold" for the initial placement)
c.walk(f0, f1, x, y)                   # walks there with steps and bob (turns to face the way); returns step frames
c.turn(f, heading, dur=8) ; c.face_to(f, point, dur=8)
c.hop(f, h=0.18, dur=10, to=(x, y), spin=0)      # anticipation, jump, squash on landing (land = f + dur)
c.squash(f, amt, dur) ; c.stretch(f, amt, dur) ; c.take(f) ; c.bounce(f0, f1, per, h) ; c.tremble(f0, f1)
c.pose(f, "name", ease, **overrides)   # see POSES; "<name>_m" mirrors a pose to the other hand
c.hands(f, R=(x, y, z), L=(...), pole=(out, back, up))   # hand targets in body-box units (see Char.hand_target)
c.reach(f, "R", world_point)           # hand to a world position (2-bone IK, clamps to arm length)
c.head_to(f, yaw, pitch, roll) ; c.look(f, world_point)  # look() turns the head only (max ~85 deg)
c.mood(f, "name") ; c.brows_set(f, up, tilt) ; c.blink(f) ; c.nod(f) ; c.shake(f)
c.say("l05", f0)                       # lip sync (mouth cues of the line) + head accents; returns the end frame
c.babble(f0, f1)                       # silent chatter
c.attach(obj, "handR", loc, rot)       # put a prop into a hand
c.pos(f) ; c.head_pos(f) ; c.face_pos(f)      # world points (for cameras, looks, bubbles)
K.word_frame("l05", "rocks", f0)       # frame at which a word of a line is spoken (line starts at f0)
K.line_frames("l05")                   # length of a line in frames
K.typing_generic(c, f0, f1)            # alternating forearms on a keyboard
```
Spoken lines are the `lines` of project.json, prepared with `stage_speech.py prepare` (`show` prints every word
frame). Only lines spoken by a figure in the picture get `say()`; a narrator is voice-over and gets `"at":
"<clip>:<frame>"` in project.json (`film3d.py line ... --at c02_plan:30`). The frame given to `say()` is where the
line sits in the film's sound. A line missing from speech/lines.json stops the build with its id; `K.word_frame`
warns when the word is not in the line.
Poses: `rest crossed chin think point point_l point_side point_side_l point_up cheer fist fist_down shrug present
present_l open type hold hold_up mug sip hips wave slump lean_back read sit stand high5 duck face glasses`.
Moods: `neutral happy smile excited worried sad skeptic stern surprised dreamy focus thinking sleepy hopeful proud`.
Body/head joint overrides: `c.pose(f, "open", body=(lean_fwd, tilt, twist), head=(pitch_down, roll, yaw))`.
All figures breathe, sway and blink on their own; `c.follow(f)` lets ears / tails swing after a stop.

Give every figure a body language and keep it through the film (slow and deliberate vs. never still; what the
ears, the tail, the brows do when it doubts or is sure) – that is what makes a cast recognisable.

## Props and sets (stage_props, stage_sets)

`P.palette()` creates the shared materials (the office calls it). Props: `room, window, desk, shelf, plant, lamp,
whiteboard, door, monitor, laptop, keyboard, mug, book, papers, blueprint, pizza, headphones, sign, nameplate,
bubble (speech / thought / cloud), card, ui_text, ui_bar, neon, star, Bot, confetti, coin, progress` – signatures
and what they return in `stage_props.py`. `sets.office(S, mood=..., poster=(headline, text), book=...,
ceiling=False)` returns its nodes (table, board, window, lamps, mugs, laptop …); `sets.seat(cast)` places the cast
at the table (`sets.PLACES`, `sets.TABLE_Z` = table top). Palettes and light moods: BLOCK.md.

## The look: a premium animated advertisement

- **Cinematography**: think commercial. Establish, then go in: medium shots, close-ups, **cutaways and inserts**
  (hands on a keyboard, a mug, a screen, a detail of a prop), reaction shots, over-the-shoulder, low hero
  angles, slow push-ins, gentle orbits. Fewer, longer shots carry more than many short ones: 3–6 s is a good
  length, and no static camera for longer than ~3 s (use `loc1`/`push`). Cut on action and on the words of the
  voice. Shallow depth of field on close-ups (f/1.8–2.8), deeper on wides (f/4). Compose on thirds, leave
  headroom, keep every figure you mean to show fully in frame (hops and raised arms included!), never put the
  camera inside or behind objects by accident. Go really close for details – a close-up that shows the felt.
- **Light and colour**: low-key by default. One clear light direction (the window, the low sun), a cool fill far
  below it, a rim light on the figures; practical lights (lamps, screens, neon) doing real work. White figures
  **always get a mid or dark background** (the dark wainscot, wood, night blue), never white on white. One accent
  colour per film (the palette), a second one only for a special place. Let the light tell the time: a light arc
  across the film (golden hour → dusk → night → dawn) gives it a shape.
- **Acting**: play the story beats, anticipation before every big move, hold key poses long enough to read,
  overlap actions between figures (someone always reacts), use the eyes/brows (`mood`) on every beat, let figures
  look at what the story is about. Silent figures are never frozen.
- **Screens**: a screen that matters shows real content – render a small HTML page to images and put them on the
  screen with `image_mat` (emissive) instead of building UI from boxes.
- **Text** in the picture must be spelled exactly as in the script, large enough to read at the film size, and
  must not contain company names or logos.
- Keep it fast to render: no volumetrics unless the shot lives from it (and then check `--q film` stays under
  ~7 s/frame), moderate geometry, lights not stronger than needed (check for blown-out whites on the sheet).

## Working method

1. Read the script of your clip and the frames of its sounds and lines, then skim `stage_actor.py` / `stage_props.py`.
2. Build the set, place the cast, block the action on the sound frames, then cut the cameras.
3. Render contact sheets (`stage_run.py clip <project> <clip> --every 20 --sheet`, at most ~24 frames per sheet)
   and **look at them critically**: framing, heads cut off, things hiding faces, text legibility, white-on-white,
   floating/intersecting props, mouths, exposure (too bright is the usual mistake). Almost every shot needs one
   or two corrections – iterate until each frame of the sheet could be a still from an advertisement.
4. Check key actions with dense strips (e.g. `--stills 96,98,100,102,104,106,108,110`).
5. Finish with 4–6 `--q film` stills of your best moments and check the s/frame it prints.
6. Never render whole ranges while authoring; the film render is one central step (`stage_run.py film`).
   Several people (or agents) can write clips in parallel when each owns its scene files and nobody edits the
   shared library – helpers a clip needs live in its own module.
