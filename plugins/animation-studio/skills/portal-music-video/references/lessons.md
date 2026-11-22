# Lessons of the reference film

What went wrong while the first portal film was built, how it showed, and what the engine or the skill does about it.

## The beat grid was wrong and nobody saw it in stills

The film was built on 119.7 BPM with the first bar line at 0.346 s - an early value from the song project. The
grid fitted to the bass drum later was 119.4 BPM / 0.056 s. Measured against the song's 125 riff hits:

| grid | median distance of a hit to the nearest beat | first third | last third |
|---|---|---|---|
| 119.4 / 0.056 | 29 ms | 20 ms | 38 ms |
| 119.7 / 0.346 | 155 ms | 223 ms | 85 ms |

Every crossing and every pulse of the film sat up to a quarter second beside the music, and the first full render
was made that way. The film's structure survived the correction (the same number of beats per world), only two
constants changed. **Take `bpm` and `offset` from `analysis/hits.json`, and check them** - the same measurement:

```python
import json, statistics
h = json.load(open("analysis/hits.json"))
b = 60 / h["bpm"]
print(statistics.median(abs((t - h["offset"]) / b - round((t - h["offset"]) / b)) * b for t in h["hits"]))   # seconds
```

A median clearly above 50 ms, or a first third and last third that differ a lot (drift), means the grid is off.

## Hitches

The viewer said it "sometimes feels like stutter" while a frame took 1-4 ms. Timing every frame of the film
showed two fixed causes:

- 45-190 ms the first time a world or a word appeared: shaders were compiled and textures uploaded at that
  moment. Now `engine.warmUp()` shows everything once and draws every world in both roles before the start.
- about 30 ms at every crossing: a world was drawn with one clipping plane while it was seen through a portal and
  with none afterwards, so its materials switched to other shader programs. Now both passes use one plane (the
  second one cuts nothing).

A third change: the picture's clock runs on the screen's frame times and only follows the sound's clock slowly;
reading the sound's clock per frame gave uneven steps.

What is left are 0.3 % of the frames at 15-50 ms in random places (not felt by the viewer).

## One frame of the old world at every portal

The camera cannot see a portal that is nearer than its near plane (0.05 units = 8 ms of flight). For that instant
the old world behind the opening flashed up - one frame, at every crossing. A continuity check in steps of a frame
(33 ms) never landed on it; steps of 2 ms found it. The engine now hands over to the next world 20 ms before the
crossing (`EARLY`), drawn from in front of its entrance - the very picture the portal showed. `flight.py check`
measures in steps of a 60th of a second around the crossing; when a flash is suspected, step finer by hand.

## Things that looked wrong

- **Pixel noise all over a ray-marched world**: `smin(d, prod, k)` with `prod = 1e5` as "no object". The blend
  computes `1e5 + (d - 1e5)`, which leaves a distance in steps of 0.008. Guard the blend.
- **Black speckles**: `pow(1. - dot(-rd, n), 5.)` with a base slightly below zero; mirrored rays started 0.03
  units off a swaying surface and hit it again.
- **The next world shining through every line**: transparent materials blended alpha the usual way; the alpha
  channel is the portal mask (`over()`).
- **A cube that looked like glass**: it was a mirror, and a mirror in front of a sky shows the sky. It became
  lacquer with bright edges.
- **Words nobody could read**: signs 13 units ahead are passed after two seconds, cut off at the frame's edge by
  then. 24 units ahead, set higher, long lines smaller.
- **Signs hidden behind gate beams**: place them half-way between two gates.
- **Flat green slabs**: glowing letters at eye level with a wide lens filled the frame; they went above the road.
- **A reflection that read as an abyss**: the upside-down city under a ground that was too see-through; 0.84
  opacity and two lane lines made it a wet street.
- **A pink portal**: additive materials pushed the picture's alpha above 1, and the next world was subtracted
  where it should have been laid in. The engine clamps alpha now.
- **A colour that would not change**: a three.js material copies the `Color` passed to its constructor - keep the
  material and change `material.color`.
- **A world that throws in `update()`** leaves the page half loaded; the error is only in the console (or in the
  message of `flight.py check`, exit code 3).
- **An alpha map is read from brightness**, not from the canvas's alpha: draw it black to white.
- **Cast shadows over a whole city** cost 2 ms a frame and were hardly seen; they are off there.
- **The first frame after a portal jumped once**: an overlay fixed to the camera belonged to one world only; it
  fades out before the crossing.

## Rendering on the CPU

A headless Edge with the software renderer (`--use-angle=swiftshader --enable-unsafe-swiftshader`) draws the film
exactly like the graphics card, 0.2-1.4 s per 1080p frame in one browser depending on the world. Frames depend
only on their time, so five browsers shared the work: 8176 frames in 31 minutes on 20 cores. Checking the whole
film for slow frames on the software renderer is pointless and takes as long as a render - `check --cpu` skips it.

## Working on it

- Show the film live in the browser while building; render only for the file. The user followed along and
  redirected after almost every step.
- Still frames prove that a world looks right, not that the film runs right. Say which of the two was checked.
