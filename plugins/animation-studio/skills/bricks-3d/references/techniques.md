# Brick-film techniques (from the "Prompts!" brick film, 2026-11)

## Importer
- Line types 1/3/4, BFC winding incl. INVERTNEXT and mirrored matrices; one mesh per (part, colour) shared by all
  instances; weld at 0.02 LDU, smooth by angle 35°. Edge colour 24 is dropped (no line rendering).
- LDraw → Blender: (x, y, z) → (x, z, −y) × 0.0004 m (real size).
- Quality "C" (default): `gaps=0.2,bevel=0.3,wobble=0.6,abs=1` – seams between bricks, rounded edges, hand-built
  wobble (seeded), ABS plastic with fine roughness noise and a little subsurface. Minifig parts get no gaps/wobble.

## Minifig rig (LeoCAD minifig wizard joints)
- Origin = neck; head at −24, arms at (±15.552, 8.88) tilted 9.791°, hands at (∓5, 19, −10) rotated 45°, hips +32,
  legs +44. **+x is the figure's LEFT.** Arm/leg sign −1 so that positive angles swing forward.
- Lean pivots at the feet; hop lifts the whole figure; `hair` (0..1) lets the hair fly up and spin, `head_off`
  pops the head off.

## Faces and prints
- Decals via shader (no UVs on LDraw parts): head = cylinder ±75° around the front; torso = planar, front faces
  only (normal test). Atlases switched by a Value node: eyes 2 tiles, mouths 9 tiles X A B C D E F G H.
- Claudia canon for the "lia" look: black bob, ONE clay streak on her right (screen left), eight-pointed clay star
  clip on her left (screen right), thin headset mic, freckles, deadpan mouth at rest.

## Camera
- Shot sizes used by the planner: wide (lens 40, 400–470 LDU), medium (45), medium-close (50), low-angle close
  (32, ~180 LDU, camera below the face – for fist pumps and big moments), two-shot (40), reveal (30, singer and
  the cameo/target together), detail (55, window/cameo/prop). Moves inside a shot are small: push in ×0.88, pull
  out ×1.1, truck 18 LDU, or hold.
- Aperture f/22 (lens > 40) or f/32: at real scale anything wider blurs the figures (user feedback).

## Light and exposure
- Lights stay in the room; close-ups are therefore brighter than wides → exposure per shot (test renders at 30 %,
  8 samples, 3 per shot), target mean 0.40, only darker (≤ −2.5 stops), then each shot ≤ −0.5/+0.3 stops from the
  section median.
- Screen light ~3 cm before a face: 0.015 W only. Key/fill specular 0.45. Shadow rays 3, steps 12.
- Moods: night_blue (reference), warm_lamp, neon – key/fill/rim colours and the world colour.

## Timing
- Body and props on twos, mouth on ones, constant keys. Jitter per pose (±0.15 LDU, ±0.2° yaw, ±0.3° arms –
  scaled by `render.jitter`, 0 = locked). Bounce: dip of `bounce` LDU on every beat, decaying in 0.12 s.

## More sets and brick effects (added with the full-song test, 2026-11-14)
- **house**: Tim's room is built as usual and a facade with a lit window stands in front of it (z −160), garden plates,
  fence, seeded trees left and right of the flight line, a glowing moon and stars. The room lights move inside the
  facade; a warm area light shines out of the window, a weak blue sun is the moon. The section is ONE shot: the camera
  flies along a polyline (garden → fence → window → into the room) with one ease over the whole section (`path`).
- **arena**: podium of 1×/2×/3× stacked 2×4 bricks; spots 1–3 stand on it (`spot_floor`), stands of dark bricks, a
  glowing stadium strip (chases on the beat like bulbs), a pyramid of chips with the cameo on top.
- **cloud**: white floor, seeded heaps of round bricks as clouds, lectern with a gavel, four rising rows of seats (the
  cameo sits in the last), 160 gold coin tiles as a sea, moon and stars; the palette's `sky` sets the world colour.
- **Effects** (`effects.py`, keyed on twos, seeded): set bricks fly in/out (floors and big planes stay; staggered
  delays 0–55 % of the time, 45 % flight, tumbling) – a room collapsing at the end of one section and a stage building
  itself at the start of the next reads as one rebuild; brick words in a 3×5 pixel font (1×1 bricks, `pixel` scales
  them) fly in one by one and can tumble down later; confetti (1×1 tiles, looping fall with wobble); towers growing
  one brick per beat; a minifig falling apart (parts drop and tumble to the floor) or building itself (parts fly in
  from above) – a later `assemble` repairs an earlier `fall_apart`.
- The planner gives a brick word its own wide shot (cut on the word, camera distance fitted to the word width) and
  frames the monitor every other shot while the computer sings.
- `show` keys switch instead of easing (a hidden cameo faded in over half a section before) and two keys at the same
  time merge (the later wins).
