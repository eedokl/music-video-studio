# Scene recipes – ready-made scenes for the figures after they stepped out

Each recipe in `recipes/` is one complete scene built with `scripts/scene.py` (stage, figures, camera, sprites,
narration with lip sync, sound cues) and `scripts/props.py` (drawn props). They were rebuilt from the scenes S4–S12
of the reference film (see `reference-tests.md`) and are meant to be **varied**, not copied: every recipe reads its
defaults and then `recipe.json` in the clip folder (cast, positions, texts, keywords, voices, set images, seed).
Ideas from the creative brief go into recipe.json or into a copy of the recipe – the timing is always derived from
the spoken words, so new voice files re-time the whole scene.

```
project/
  deck/ figures/                 (deck.py, figures.py, parts.py, mouth.py as usual)
  clips/<scene>/recipe.json      {"cast": {...}, "voices": {"narrator": {"audio": "voice/n.wav", "text": "..."}}, ...}
  clips/<scene>/voice/*.wav      the voice lines (talking-character / TTS / recorded)
  clips/<scene>/set/*.png        painted sets (back layer 1920x1088 + an optional front/table layer)
uv run --no-project --with pillow --with numpy --with scipy --with scikit-image --with faster-whisper \
   python "${CLAUDE_PLUGIN_ROOT}/skills/animated-powerpoint/recipes/<recipe>.py" clips/<scene> [--plan]
```
`--plan` only plans (word times, Synfig files, events.json) – check the events, then run without it
(Synfig → light maps → three.js → post → look → sound; `<scene>.mp4` + `ton.wav` + `events.json`).
`"text"` of a voice line helps Rhubarb (lip sync); keywords (`"words"`) are matched against Whisper's words
(a written word also matches a Whisper word that starts with it: "chat" → "chatbot").

| Recipe | Story beats | Cast roles | Stage features used |
|---|---|---|---|
| `s04_rumor.py` | news told at the table, dream cloud on the keyword, double take, thought cloud, four close-ups as hard cuts on role words, star eyes | explorer, guide, guardian, builder | painted set + steam, `cloud`, `star_eye` on `pupils()`, cut camera, lip sync, a silent thought (`mouth_rest`) |
| `s05_split_screen.py` | sign, typing with key flashes, chat bubbles, a bot jumps out, cards fan out, info card, split screen to a second room, double take, deadpan blink | builder, explorer, guardian | two scenes (`side` rendered first) + `post` with `split_frame` |
| `s06_three_parts.py` | hall: hop past doors, overshoot + slide back, into the light; office: check sign + confetti, a confetti piece past a face; machine: document through stations, findings arc into a bin (rim bounce), counters | builder, explorer, guardian, guide | three scenes + `join`, figure opacity + contact shadow, `confetti`, `arc`, `pipeline_board`, `counters` post |
| `s07_night_holograms.py` | neon flickers on, hologram per spoken keyword, the last one takes off as a rocket, prompt line, app panels orbit, glitch double take | builder | dark background, figure `tint` + `rim`, additive sprites, `holo`, `neon` |
| `s08_coin_rain.py` | coins rain and pile up, counter, three coins hit a head, balance tips to value, calendar sheets fly | guide, guardian | physics-like sprites, `scale_parts`, `counter_box` post, `head_top()` |
| `s09_progress_bar.py` | book pops, progress bar grows beside a head and sags on "but", warm light, caught look into the camera | guide, guardian | `book`, `progress_frame/fill` (sprite `sx`), additive `warm_light` |
| `s10_islands.py` | four island dioramas drift apart, walls grow, colour fades, title card + figures, spotlights per call, islands snap back on the names, the hesitant one rushes after | guardian, guide, explorer, builder | floor layer (`rotx`), movable layers (`lpos`), contact shadows, `island_floor`, `light_cone`, colour grade + title post |
| `s12_together.py` | sign, chain of steps pops and a light pulse runs along it, bots carry documents, cheer with three confetti bursts, a piece lands on a head | all four | `sign` chain, bots, `confetti`, `head_top()` |

What the recipes taught the stage (all generic, in `scene.py` / `props.py`):
`painted_set` + `set_point` (set pixels → world), `pupils`, `head_top`, `mouth_rest`, `confetti`, `arc`, `cut_camera`,
`post` hooks (frames_post/), `split_frame`, `join` (several scenes, one track), `sound(..., align="start")` for
swells and blooms, contact shadows for scene figures, `recipe_config`, `save_events`; props: comic clouds, star eye,
signs, cards, info card, check sign, neon, holograms, bot, chat bubble, documents, coins, balance, calendar sheet,
book, progress bar, lights, island floor, pipeline board, counters.

Keys use the generic channels `gesture` (the figure's gesture part: arm or wing) and `follow` (all other jointed
parts: tail, shell), so a recipe works with any rigged cast; per-part names (`tail`, `wing_r` …) still win.
