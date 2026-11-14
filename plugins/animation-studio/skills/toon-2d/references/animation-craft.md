# Turning the 12 principles into keys

Numbers below are at 24 fps and are starting points that worked; adjust by eye on the contact sheet. Cartoony =
bigger values, fewer frames.

## Timing reference

| Action | Frames |
|---|---|
| Small hop (height ~1–1.5 units) | 12–14 contact to contact |
| Big jump (2+ units) | 16–20 |
| Anticipation crouch before a jump | 8–12 down, hold 2–3 |
| Take (surprise) | 3–4 anticipation squash, 3–4 to the stretch peak, 8–15 settle |
| Settle after landing | 3 bounces over ~10–14 frames, each smaller |
| Blink | 4–5 frames (open → closed in 2, open in 2) |
| Head turn / look | 4–8 frames with halt at both ends |
| Hold that reads | at least 8–12 frames; keep it alive with breathing |
| Bouncing ball | drop from 5 units in 14 frames, then contact to contact 22 / 15 / 9 / 7 frames with heights 3 / 1.6 / 0.7 / 0.2; x linear, rolls out with halt |

## Squash & stretch

- Store the height factor `sy`; width follows `sy^-0.8` (`motion.squash_keys`) so the volume stays.
- Contact frame: `sy` 0.65–0.8 (harder impact = lower). One frame before contact: stretch 1.12–1.2. One to two
  frames after contact: stretch 1.1–1.2 on take-off.
- Keys around contacts: `"linear"` (sharp). Return to 1.0 with `"halt"`.
- Squash about the feet (group origin at the bottom centre) so the character stays planted.
- Bouncing ball: stretch (0.82, 1.28) one frame before contact, squash (1.4, 0.62) on the contact, stretch
  (0.88, 1.2) one frame after, back to (1, 1) two frames later; scale all deformation down ~22 % per bounce.

## Arcs and slow in / slow out

- Jumps: height keys with contact `"linear"` and apex `"halt"` give a near-parabola. Travel in x is a separate
  `"linear"` animation (`comp_vec`) – never ease x and y together, or the arc turns into a straight-ish slide.
- Ease (`"halt"`) into and out of every held pose; linear only for impacts and constant-speed travel.
- A take-off that should feel like a launch: `"halt"` on the ground key, `"linear"` at the exit key (slow start,
  fast end).

## Anticipation → action → follow-through

- Before any big move, go briefly the opposite way: crouch before a jump, lean back before rushing forward or
  pecking, eyes and head before the body.
- Lean: the character leans into travel (negative angle when facing right), whips past vertical on landing
  (+5…+8°) and settles (−2°, 0).
- Follow-through on appendages: `motion.spring_follow` driven by the root's real path. Swing too timid → raise
  `gain_*`; too floppy → raise `freq` or `damping`. A hit on the appendage itself (a peck, a flick): add a decaying
  wobble on top (`characters/pip_figure.py`: `antenna_kicks=[(frame, degrees)]`, ~3 Hz, half-life ~8 frames).
- Overlapping action: stagger parts by 1–3 frames (eyes lead, body, then antenna/tail/wings).

## Contact between two moving things

Tongue catches a fly, hand grabs a ball, a bird lands on a head: hold the carrying body (same x and lean on two
`"halt"` keys) for the whole contact, compute the contact point with `motion.to_world` (or from the body's outline),
and bake the contacting part per frame from the same timing lists – e.g. the bird's feet `y = top * approx(SQ, f)`
while the head squashes under it. Python's `approx` matches linear/held keys exactly, eased segments only roughly.

## Staging and appeal

- Composition first: zoom the camera so characters fill ~1/3 of the frame height; keep the action area clear of busy
  background; light, desaturated background vs saturated characters.
- Clear silhouettes: check key poses on the contact sheet – can you read the action from the shape alone?
- Eyes sell acting: pupils lead the head (look at the thing 4–6 frames before reacting); bigger eyes for surprise
  (scale 1.25–1.35), mouth swap to "O".
- Secondary action keeps holds alive: breathing (`sy` ±2.5 % over ~30 frames), blinks, background drift (clouds), a
  gently swaying plant.

## Readable, unambiguous actions

Show an action at the object it acts on. Hands that disappear behind a desk or table edge at hip/lap height while
making small rhythmic movements toward the body's centre can be misread as sexual – e.g. "typing" with the keyboard
hidden. For typing: elbows out, forearms on the desk, hands clearly visible *on* the keyboard and far apart,
alternating taps, keys lighting up; look at the screen or keyboard. If the normal arm drawing cannot reach the prop,
swap in a dedicated pose drawing (constant `amount` switch). Get an outside viewer to watch previews – they spot
unintended readings the author misses.

## Colour

Saturated characters on lighter, cooler backgrounds. Semi-transparent overlays mix with what is below: red blush at
low alpha on green skin turns brown – use pink (`#ff9aa8`, ~45 %) on green, or warmer reds on yellow/orange. Keep
one dark ink colour for all lines.

## Exaggeration check

If the motion looks correct but boring: push extremes 20–30 % further, shorten the action, lengthen the anticipation
and the hold after it.
