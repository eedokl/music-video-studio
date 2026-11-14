---
name: animated-powerpoint
description: "Bring the figures of a presentation to life: take characters from a pptx, PDF or slide images and animate them in classic cartoon style, exactly as drawn (same line and colours). They step out of the slide into a 2.5D room, land, gesture and talk with lip sync; narration, sound, a deck intro, an outro and painted-set scenes; the clip fits back into the deck (same size, starts and can end on the slide). Use whenever the user wants an animated slide, deck characters \"coming alive\", a presentation intro/teaser/explainer from slide art, a moving mascot, or a video to drop into PowerPoint - even if they only attach a pptx/PDF and say \"make them move\"."
---

# Animated PowerPoint – figures step out of the slide

The figures are never redrawn: they are cut from the original picture into movable parts, so every pixel of the
rest pose is the slide's pixel. Classic acting (anticipation, squash and stretch, arcs, follow-through, overshoot,
idle life) comes from Synfig keys; the 2.5D room (slide as a sheet, light, contact shadows, camera) from three.js.
Building blocks: toon-2d (`sif.py`, `render.py`/`synfig_parallel.py`, `render_multiplane.py` + three.js vendor),
film-finish (`apply_look.py`), studio-core (config, gpu_lock, creative seed). Dialogue: see the end.

Scripts: `${CLAUDE_PLUGIN_ROOT}/skills/animated-powerpoint/scripts/`. Run with
`uv run "${CLAUDE_PLUGIN_ROOT}/skills/animated-powerpoint/scripts/<script>.py" ...` - each script declares its own
pinned packages (PEP 723 header; faster-whisper is included wherever narration is turned into word times for tags,
gestures and lip sync).
Work in a project folder outside the plugin: `deck/`, `figures/`, `clips/<name>/`, `project.json` (seed + ideas).

## Workflow

`clip.py` and `scene.py` check their clip.json / scene.json first (studio-core `project_check.py`): wrong types, and a narration `"speaker"` (or figure `"talk"`) whose figure has no `"mouth"` block in its `parts.json`, stop them with exit code 2 before any render.

1. **Interview + creative brief.** Which deck and slide(s)? Which figures step out, who just watches? Where will
   the clip play (after the slide = start on the slide; as a loop on the slide = `"ending": "return"`)? Text on the
   tags (name + role from the slide)? Read the slide text and notes (`deck.json`) and invent ideas from *this* deck
   (a gesture that fits the role, who reacts to whom, an ending); record them with `creative.add_idea`. User ideas win.
   The decks can be internal: everything stays local, nothing is uploaded.
2. **Import the deck** – `deck.py deck.pptx --slides 5 --out deck` (or a PDF, or slide images).
   PowerPoint (COM, read-only) exports `slide_NN.png`, `clean_NN.png` (no logo/footer/page number from the master,
   no `--hide` shapes – default `"Camera *"` = Cameo/live-camera shapes) and `plate_NN.png` (clean slide without
   its pictures). Every picture is saved with its exact place incl. PowerPoint crop and group transforms.
   Check: `plate` + pictures pasted back = `clean` (tested 0.57/255).
3. **Find the figures** – `figures.py --deck deck/deck.json --slide 5 [--picture ID] --names a b c --upscale 4`.
   Blobs of the picture's alpha (or of the slide, for page images) left → right; small pieces close to a figure are
   attached to it (mug handle, hat); soft edges go to the nearer figure. `--upscale 4` uses Real-ESRGAN (config key
   `realesrgan` → `realesrgan-ncnn-vulkan`, takes the GPU lock; colour on white + alpha separately) or Lanczos.
   Upscale small pictures (< 1500 px figure height); large drawings need `--upscale 1`/`2`. Look at `figures/contact_figures.png`.
4. **Cut each figure into parts** – `parts.py figures/<name> --auto` writes a first guess (head above the neck or
   above the eyes, the two pupils, body) and `parts_check.png`. **Refine `parts.json` by looking at the check image**:
   add polygons for the parts that should move (arm/wing/tail/shell, back → front order), put pivots where the drawing
   has a joint line (sleeve cuff, wing outline), `split_fill: true` when a limb's fill is joined to the body,
   `eye_blob` when pupils touch glasses, `ext` for hidden pieces under joints. Re-run `parts.py figures/<name>`.
   Accept when the rest pose matches the original (printed: mean < 0.5/255 in the silhouette; the rest are soft-edge
   pixels) and the colours in `parts_check.png` follow real lines. Safe angles are small (head ±5°, arm ±9°, tail ±8°).
5. **Write the clip** – `clips/<name>/clip.json` (see `clip.py --help`): slide, figures with
   `"action": "step_out" | "watch"`, `style` (`jump` | `flutter` for winged figures | `hop` hesitant | `stuck` heavy
   figure that jams in the slide – see "Styles"), `start`, `tag` + `tag_at`, `gesture` (`fist` | `wave` | `nod` |
   `look_up` | `wag` | `shake` | `none`) + `gesture_at`, `spin` (`flip` | `none`), `gesture_part`;
   `"ending": "stay" | "return"`, `"finale": "group"` (wide shot of everybody at the end; default with ≥ 3 figures),
   `"look": "standard" | "none"`, `size` (default 1920 × slide aspect). Unfixed variants come from the seed.
   **Narration**: `"narration": [{"id", "audio", "at", "speaker"?}]`; every time (`start`, `tag_at`, `gesture_at`,
   `pop_at`, a line's `at`) can be a frame or a time spec – `{"line": "felix", "word": "spots"}`,
   `{"line": "fritz", "edge": "end", "offset": 6}`, `{"fig": "felix", "event": "land", "offset": -12}`,
   `{"max": [...]}` – so tags pop on the spoken role and figures start after a word. Word times come from Whisper
   (`narration.py`; `WHISPER_MODEL=large-v3` gives the most exact times, also on the CPU).
6. **Build** – `clip.py clips/<name>/clip.json` (plan → synfig → light → tex → 3d → final → sound; `--from <step>` /
   `--only <step>` to redo a part). An 8 s clip takes ~1.5 min. Output: `<name>.mp4` (with look),
   `stage.mp4` (without), `first.png`/`last.png`, `contact.png`, `plan.json` (event frames), `check.json`,
   `ton.wav` + `sound.json` (narration + earshot effects on the event frames, `"sound": false` = silent,
   `"sounds": [...]` extra cues). A 25 s four-figure clip takes ~25 min on a busy machine.
7. **Review checkpoint** – look at `contact.png` (every scene had a framing error the first time in the reference
   project: heads cut off, tags out of frame), check `check.json`: `first_vs_slide` < 3 (clean start on the slide),
   with `"ending": "return"` `last_vs_first` ≈ 0 (seamless loop). Show the user the clip; adjust `start`, gestures,
   camera via `land`, and rebuild from `plan`.
8. **Into the deck** – insert `<name>.mp4` on the slide (or right after it) full-size, "start automatically";
   for a loop set "loop until stopped" (`"ending": "return"`). The first frame equals the slide, so the cut is invisible.

## What the routine does (step_out, frames after `start`)

look left/right with eyes + head (3–24), blink (23), crouch (34–46), take off with stretch (46) while the slide
bulges like rubber and lets go with a pop (≈52, paper bits, a dashed outline in the accent colour stays), in the
air the figure turns from flat to lit and round (shade 0 → 1, turns to the camera, optional flip), lands with
squash (76), follow-through on tail/limbs, gesture twice (95/106), name tag pops (118), then idle (weight shift,
breathing, irregular blinks, head/part sway) so it never freezes. Line boil (`boil`) in the room makes edges feel
drawn. "watch" figures stay flat in the slide but follow the action with their eyes, blink and breathe.

## Styles and the line-up (several figures, `routines.py`)

- `flutter` – eyes dart left/right/up, short crouch, flaps out (a wing beat every 4 frames on the gesture part),
  glides down late and lands softly. `hop` – peeks down over the edge, tips forward and back, small hop.
  `stuck` – waddles forward, jams in the slide (the slide stretches), struggles until `pop_at`, a beat of silence
  with a glance at the others, a last jerk → pop, falls, big squash, head shake, camera shake; tag after recovering.
- `look_up` raises the gesture part and flashes two sparkles on the glasses; `wag` wags the tail.
- Several figures: each `start` defaults to the previous landing + 10 (better: time specs on words). Figures still in
  the slide and landed figures follow whoever acts with eyes and head; landed `fist`/`wave` figures cheer while a
  `stuck` figure struggles; the camera takes the side where nobody stands yet; landing places spread out
  (`spread`, default 1.18), tags are small and on the +x side, they leave before the group shot (`tag_hold`).
  The reference line-up (Fritz jump, Felix flutter, Hans hop, Helmut stuck) is in `references/reference-tests.md`.

## More clip kinds

- **Deck intro** – `intro.py clips/intro/intro.json`: title slide lights up, slides flip faster and faster on a
  word, a word cloud flies out, keywords land on their words, hard stop on a card (strike + handwritten word),
  a story slide types its title word by word with the voice, wobbles, turns like a page onto the first frame of the
  next clip (`next_image`, seamless; `check.json` `last_vs_next`). Page: `assets/intro25d.html`.
- **Outro** – `outro.py clips/finale/outro.json`: the previous scene shrinks into the slide, push-in on a figure's face,
  iris, the figure winks (drawn from the slide: skin colour + lid arc), iris closes, title card; glock on the wink.
- **Scenes after the step-out** – `scene.py` (Python API or `scene.json`): painted set layers, layers in front of the
  camera (floor-plan flight), the rigged slide figures at any scale with keys per part (`eyes`, `head`, `arm_r`,
  `mouth`, `pos`, `tilt` ...), sprites, steam, scene light (`tint`, `rim`), camera path, narration with lip sync,
  extra sounds; helpers `nod`, `slow_nod`, `breathe`, `babble`, `steps` (walk/hop cycle), `pop`.
  Page: `assets/scene25d.html`. Film cut of several clips: film-finish (cut tool, when available) or ffmpeg concat.
  Also: `post` hooks (counters, captions, colour grade, `split_frame` split screens), `join` (several scenes with
  their own sets as one clip and one sound track), `confetti`, `arc`, `painted_set`/`set_point`, `pupils`,
  `head_top`, `sound(..., align="start")`. Drawn props in the slide's ink style: `scripts/props.py`.
- **Scene recipes** – `recipes/s04_rumor.py` … `s12_together.py`: eight complete scenes (news + reactions with
  close-ups, split screen to a second room, three-part hall/office/machine, night holograms, coin rain + balance,
  progress bar, drifting islands called back by name, finale with confetti). Run one on a clip folder with voices +
  set images; vary cast, texts, keywords, sets and seed in `recipe.json`. Index and how to vary them:
  `references/recipes.md`. Use them as a starting point and invent this deck's own beats in the brief.

## Dialogue / voice (lip sync for slide figures)

`mouth.py figures/<name>` cuts 8 mouth stages from the drawing itself (config `"mouth"` in `parts.json`):
`open` – an open grin squashed column by column under the upper lip (rest = the original grin), `line` – a dark
mouth opening under a closed smile line with a tongue from stage 4 (rest = closed), `beak` – the lower beak hinges
down with a dark gap. Check `mouth_check.png` at full size per stage. A narration line with `"speaker": "<name>"`
(clip or scene) makes that figure talk: Rhubarb cues → stage keys (`mouth.mouth_keys`), one stage visible per frame
in the head group. `mouth.py --clean` removes white soft-edge flecks outside the ink outline from all parts (they
show on grey or coloured sets). **talking-character** hand-off: voices are made there (Qwen3-TTS / Piper /
system); for raster slide figures call `mouth.mouth_keys(fig_dir, [(wav, start_frame, text)])` and render with
`scene.py`, since talking-character itself rigs SVG figures only.

## Files

- `scripts/deck.py` (import), `figures.py` (find + upscale), `parts.py` (cut + rig measures + fidelity),
  `acting.py` (keys of the jump routine), `routines.py` (styles + gestures), `clip.py` (build), `narration.py`
  (word times), `sound.py` (narration + effects), `mouth.py` (mouth stages + lip-sync keys), `intro.py`, `outro.py`,
  `scene.py`, `props.py` (drawn props); `recipes/` (ready scenes); `assets/stage25d.html`, `intro25d.html`, `scene25d.html` (three.js pages, copied into the clip folder
  and rendered by toon-2d `render_multiplane.py --page`).
- `references/reference-tests.md` – the full rebuild of the ai_efficiency clips (probe, meet the cast, intro,
  finale, scenes S3–S12) and a fresh 4:3 deck. `references/recipes.md` – the scene recipes.
