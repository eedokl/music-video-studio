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

### Other makes: rag dolls, hand puppets, stop-motion puppets, clay, paper, marionettes (stage_looks)

project.json `"figures": "ragdoll"`, `"puppet"`, `"stopmotion"`, `"clay"`, `"paper"` or `"marionette"` (or `K.cast(S, {...}, style=...)` for one clip) re-dresses the
built figures; scenes, poses and lip sync stay as they are.

- **Rag dolls** read through texture and seams, so they need light that rakes across the cloth (a clear key from
  the side) and at least a few shots close enough to see the stitches; in a wide shot they look like the toys in
  cream. Button eyes cannot blink or widen: play surprise and doubt with the brows, the head and the whole body.
- **Hand puppets** are played from below: only the upper body shows. Put a playboard, a desk or a wall edge in
  front of them at chest height (`at(f, x, y, h, z=...)` lifts a figure so its chest meets the edge), let them come
  up from below and sink away instead of walking on, and keep the camera at or below eye level so it does not look
  behind the board. They act with the whole head: big head turns and tilts, bounces on the beat, arms thrown up -
  small finger acting is lost. `jaws = K.dress(...)` / `stage_looks.puppet()` returns the jaw nodes; a jaw also
  takes keys of its own (`jaw.rot(f, x=28)`, degrees) on top of the mouth channel, e.g. for singing on the beat.
- **Stop-motion puppets** have no brows and eyes that cannot change: they act with the tilt of the big head, the
  shoulders and long holds - play them slower, hold poses a beat longer, and move in clear steps rather than in
  flowing arcs (key poses with `ease="hold"` or short `"out"` moves, a held pose every few frames, reads as animated
  "on twos"). Light them low-key and cold with one warm practical; compose with a lot of dark around the figure.
  An own class can set `stopmotion = {"thin": 0.5, "head": 1.16, "waist": 0.86, "eye": 0.06, "pupil": 0.15}`.
- **Clay** figures are the toys in plasticine: everything of the toy acting works. Animate them "on twos" (hold
  every pose for two frames: key with short steps) if the film should feel like stop motion.
- **Paper** figures live from their facets: a hard key from the side, little fill. Fast moves read well (the
  silhouette is angular), tiny mouth shapes do not - let them gesture.
- **Marionettes** hang: let them bob and sway a little (`bounce` with a small height, slow head tilts), land softly
  after hops, never spin. Frame them with the strings going out of the top of the picture, or show the crosses on
  purpose in a wide shot.
- An own figure steers its puppet make with a class attribute, e.g. `puppet = {"fleece": "#EBA52C", "parts":
  "muzzle", "hinge": -0.03}` for a long snout (cut only the muzzle - cutting head and muzzle gives a stacked mouth),
  `{"lid": 0.4}` for heavy eyelids; `stage_looks.PUPPET["name"] = {...}` does the same from a scene.
- Check both makes on close-up stills first (`stage_run.py clip ... --stills`): mouth cut height, eyes behind
  glasses and seams are the places that need a look.

### Realistic actors: Rigify figures in a real world (stage_rig)

project.json `"figures": "rigify"` plays every part with a **Rigify-rigged figure** (a `figur.blend` per actor -
e.g. from the 3D figure kit) instead of a toy; `"actors": {"mo": "tim", "kit": "claudia"}` casts them (default: the
actor of the same name, else the project's own actors - or all - in alphabetical order). One actor in any film: `K.cast(S, {"tim":
{"actor": "tim", "height": 1.05}})`. Actors are looked for in `<project>/actors/<name>/figur.blend`, then in the
machine-config folder `actors3d` (env `STAGE3D_ACTORS`, several folders separated by `;` / `:`).

- **Same acting API.** A `RigActor` is a `Char`: its invisible joint skeleton is laid out on the rig's proportions
  and the rig bones copy it, so `pose`, `hands`, `reach`, `look`, `walk`, `hop`, `turn`, `nod`, `take`, `say`,
  `babble`, `mood` work unchanged, and a finished toy film can be re-rendered with actors. `size`/`height` scale
  an actor; `body_z0`, `head_z`, `eye_z` come from the rig (camera aims with `face_pos` stay right).
- **Face**: sliders on the head bone (`stage_rig.FACE`: lids, mouth open/wide/narrow/shut, smile, mouth corners,
  eyes wide/narrow, brows up, inner brows up/down) take blinks, moods, `brows_set`, `take` and the Rhubarb shapes of
  `say()` (mixes from `<actor>/mundformen.json`, else `stage_rig.SHAPES`). The values in the file are the rest face;
  moods add to them (0..2).
- **Contact, after the bake** (`stage_rig.contact`, automatic): the legs are IK and the **feet stand on the floor**
  under them (rug, step, stage - a ray down from the ankle): a foot stays put until the body has moved away, then
  makes a step; while walking the steps follow a gait cycle fitted to the speed (stride 1.5 x leg length, 6..16
  frames per cycle); lifted feet (hops, sitting) go with the leg; soles stay flat when the body leans. **Arms do
  not reach through furniture**: hand, finger and sleeve vertices are tested against desks, tables, keyboards,
  monitors ... (names in `stage_rig.OBSTACLE`, or `stage_rig.obstacle(obj)` / `obstacle(obj, on=False)`); an arm
  that is in one is turned about the shoulder, up or down - whichever frees it with the smaller angle - and faded
  in and out. `STAGE3D_CONTACT=0` switches both off (feet then only follow the legs).
- **Measure it**: `stage_run.py clip <project> <clip> --stills ... --contact` writes `out/<clip>/contact.json`
  (shoes below the floor, hand points in furniture, per frame) and prints a summary line - check it before a long
  render, and look at feet and hands on close stills.
- **Scale**: the bundled sets are built for ~0.85 m toys (table top 0.5 m). Actors of about 1 m (the kit's
  figures) fit them; tall adults need their own sets - or `height=` - and walking speeds that fit their legs
  (a 1 m figure walks about 1 m/s; faster reads as running with long strides).
- `walk()` of an actor adds no leg swing (the feet step by themselves) - only bob, hip sway and arm swing.
  `hold_prop(obj, side)` puts a prop on the rig's hand bone; `attach()` (on the Char hand joint) works as well.
- The actor contract (what a `figur.blend` needs): the docstring of `stage_rig.py`.

## Theatre: set changes in view, curtain, light show (stage_theatre)

A room change does not have to be a cut: the audience sees the set change like in a theatre. Every piece of
scenery belongs to a **world** and has a way of leaving; `Change` animates the swap.

```python
import stage_theatre as T
R = sets.office(S, mood="dusk")
B = T.show_stage(S)                       # backdrop, bulb arch, lacquer floor with footlights, spots
ch = T.stage_change(S, B)                 # the show stage as world "stage"
T.set_change(S, R, "room", ch)            # the whole office as world "room" (table things go with the table)
ch.state(1, "room")
w = ch.change(24, "stage", frames=40, follow=mo, crew=2)   # -> {"dark", "away", "there", "lit"} frames
mo.pose(w["lit"], "cheer")
T.light_show(S, 110, beats, ["#FF2E7E", "#2EC5FF", "#FFD12E"])   # finale: moving heads in haze on the beat
```

- `ch.piece(node, world, how)`: how = `"fly"` (up into the fly loft, comes back with an overshoot), `"roll"`
  (sideways to the nearer side), `"sink"`, `"unroll"` (scales to nothing towards its origin - put the origin at the
  edge it rolls to; floors, carpets, runners) or an own offset `(dx, dy, dz)`. `ch.lights(world, {name: light})`,
  `ch.glow(world, material)` (bulbs, signs; they light one after the other when the world arrives).
- `ch.change(f0, to, frames, follow=<figure or point>, crew=n)`: old light to a glow, a follow spot on the
  figure, the old pieces leave in a staggered order, the new ones arrive, n stagehands in black cross in the dark,
  the new light comes up. Reverse it with another `change(..., "room")`. `ch.state(f, world)` = a hard cut.
- `Curtain(S, width, height, y)` with `.open(f, frames)` / `.close(f, frames)` / `.state(f, open_)`;
  `follow_spot(S, figure, f0, f1)`; `dim(S, lights, f, factor)`; `stagehand(S, name).walk(f0, f1, a, b, carry=True)`.
- `light_show(...)`: the rig flies in `fly_in` frames before `f_on`; the haze is real volume light and costs render
  time (about 2x per frame while it is on) - keep it to the finale. It needs a dark stage: dim the other lights.
- Played straight, the change itself is a gag (a wall falls away in the middle of a serious line); see
  `animated-3d-film/references/gags.md` for the deadpan spoof style.

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
