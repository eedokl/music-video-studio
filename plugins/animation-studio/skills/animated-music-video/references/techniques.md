# Techniques beyond stage and room scenes

The reference film "Prompts!" used these. They are recipes – build them into `scene.py`, `film-finish` or a
project script when a song calls for them, and vary them; do not reuse them unchanged.

| Technique | How it works | Building blocks |
|---|---|---|
| **Verse as a 2.5D comic flight** (page lies on a desk, panels lift off, camera timed to the lines) | Comic page with ~6 panels: painted layers + ink figures; camera keyframes on the lyric lines; the read panel lifts off (hole + shadow + frame); arcs between panels; caption box types the words in the rhythm of the singing | toon-2d `render_multiplane.py` + `multiplane/comic25d.html`, ai-video (FLUX panels, Depth Anything relief) |
| **Panels painted with FLUX** | 2 variants per panel, the user picks; "no text, no logos" in the prompt; lettering and company signs as own layers; upscale (Real-ESRGAN) before depth estimation | ai-video `comfy_image.py`, `estimate_depth.py` |
| **A character breaks out of the comic** | The figure is its own layer in a panel; the flight is rendered with and without it, the difference gives its screen track; from the break-out on the clean flight runs and the rig climbs out as a paper stand-up (cut edge, shadow), jumps/flips forward, dances on the beat or hangs on marionette strings, lip-syncs when it sings | toon-2d `breakout.py` (+ `breakout.json`), see `toon-2d/references/multiplane-and-comic.md` |
| **Intro flight** through branches into a lit window | 5 painted layers, the house very wide (5000+ px) because the camera ends close; camera targets computed from layer distance and window position | toon-2d multiplane |
| **Narrator inset** (round frame in a corner) | Bust with lip sync, pops on every change; hidden while the figure itself is in the picture | `scene.py` section `"inset"` |
| **Screen close-up** with usage bar and tier badge | The screen fills the picture, the room behind darkened, slow push-in; bar turns red at "limit", empties after the upgrade | `scene.py` `"shot": "screen"`, `"screen_meter"`, `"screen_badges"` (characters `computer.py`) |
| **Typing / air guitar in front of the body** | Own arm layers in front of the body; the rig arm switched off via `amount`; keys light up; key clicks written for the sounds | `scene.py` `"actions"` (`scene_fx.py`), film-finish `sounds.py` |
| **Spotlight verse**, disco finale with confetti, night | Light cones, a second figure only in its own light; coloured cones alternating on the beat; seeded confetti; dark room with a glowing screen | `scene.py` section `"light"` |
| **Silhouette gag** in a window | A figure passes between the sky layer and the wall layer of the room set (set.json `"window"`); a big shadow in a spotlight | `scene.py` `"silhouettes"` |
| **Transitions**: zoom through a window, light burst, zoom into the screen, iris onto a grin | Computed per frame on the finished cut, always from the untouched cut file; 6–14 frames; abrupt musical stops stay hard cuts | film-finish `transitions.py` (zoom_through, glow, screen_zoom, iris, white, black) |
| **Credits** with outtakes, a laugh, a 3D morph | Side screens show film excerpts – rebuild the credits after every new film; mouth and shoulders follow the loudness of the laugh; 3D morph: the drawn figure crossfades into a rounded 3D toon version of itself (parts round one by one, a turn, a pop) | film-finish `credits.py` (gag vocabulary, `--draft`, audio-driven post-credits figure, `--append`); toon-2d `figure_3d.py` (Blender, any rig SVG) + `figure_3d.py crossfade` |
| **Second audio track** in another language | The other version unchanged, shifted by one global offset (onset cross-correlation of both songs), the same sounds mixed in, muxed as track 2 – section-wise re-cutting sounded chopped | film-finish `second_audio.py` |
| **48 fps** | RIFE frame interpolation only in camera moves (intro, comic), elsewhere frames doubled, never across cuts; RIFE needs `-g 0` and RGB input | film-finish `fps48.py` (sections with `"camera_move"`) |
| **Who sings, finer** (call and response without a backing stem) | A fine male/female track every 0.15 s over the choruses | song-analysis (earshot) |
| **Sets painted in Krita** | A Python "brush" writes a real .kra file the user can paint over and re-export | toon-2d `krita_assemble.py` |
| **Pop-up video version** | Making-of cards pop up at free spots with a pop, held long enough to read; cards drafted from the ideas log, rewritten as true facts | film-finish `popup.py` |
| **Bridge as fast comic panels** | Comic page on a desk, hard cut on every lyric line, push-in + roll per panel; shout words as overlays; caption box types the line | `scene.py` `"kind": "panels"`, `captions.py`, toon-2d `comic_page.py` |
