---
name: animated-3d-film
description: "Make a 3D character film in Blender that looks like a premium animated advertisement - soft toy figures that act and speak with lip sync, sets with real light (golden hour, dusk, night), cutaways, close-ups with depth of field, a film-look finish - written as Python scenes, rendered headless with Cycles on the graphics card, first as a fast preview of the whole film and then in film quality. Use whenever the user wants a 3D animation, a Blender film, an explainer or story told by 3D characters, a 'cinematic' or 'ad-like' remake of a script or of a 2D film, an own 3D cast, or wants to change, re-light, re-cut or re-render such a film (project.json with \"clips\" + scenes/*.py) - even if they only say 'make it 3D' or 'like a Pixar-style ad'. Brick films: bricks-music-video; 2D cartoons: animated-short / talking-character; photorealistic AI video: claudia-music-video."
---

# Animated 3D film

A 3D film here is a folder of small Python scene modules – one per clip – that build a Blender scene from code:
set, light, figures, acting on exact frames, cameras. Nothing is modelled by hand, everything can be changed and
rendered again. It is reviewed on contact sheets, then as a **fast preview of the whole film**, and only then
rendered in film quality (that is the long step: hours).

Scripts here: `${CLAUDE_PLUGIN_ROOT}/skills/animated-3d-film/scripts/` – `film3d.py` (new / clip / idea / line /
speak / sound / preview / render / status). Run it with
`uv run "${CLAUDE_PLUGIN_ROOT}/skills/animated-3d-film/scripts/film3d.py" ...` (it declares its packages).

**Building blocks** (shared code + docs of this plugin, not skills - read the one you need):
`${CLAUDE_PLUGIN_ROOT}/skills/<block>/BLOCK.md` for `studio-core`, `song-analysis`, `toon-2d`, `characters`, `voice`, `ai-video`, `bricks-3d`, `stage-3d`, `film-finish`. In those files
`<plugin>` stands for `${CLAUDE_PLUGIN_ROOT}`. First use on a machine: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py" --setup` (finds the programs).

Read first: `stage-3d` BLOCK.md and its `references/guide.md` (the scene API, the craft rules, the working method).
Needs Blender 4.2+ (config key `blender`), ffmpeg, Rhubarb; a graphics card makes it practical.

## 1. Interview (short – skip what the request already says)

- **What is the film?** A script or story the user brings, a remake of an existing film (then its sound track
  and timing may be reused), or "surprise me". How long? (30–90 s is a good size; minutes are a big render.)
- **Who plays?** The bundled toy figures (bear, cat, bunny – colours, glasses, sizes free) or an own cast that must
  stay recognisable (then every figure gets its own class – step 4). They can also be made of something else:
  sewn **rag dolls** (cloth, seams, button eyes), **hand puppets** for a puppet show (fleece, flap mouths,
  played from behind a playboard) or gothic **stop-motion puppets** (thin limbs, huge eyes, clay skin, stripes;
  wants a dark, cold-lit film), **plasticine** figures, **papercraft** figures (folded, with fold lines and glue
  tabs) or wooden **marionettes** on strings - project.json `"figures": "ragdoll"` / `"puppet"` / `"stopmotion"` /
  `"clay"` / `"paper"` / `"marionette"`, see stage-3d BLOCK.md
  "Figures"; an existing film can be re-rendered in another make without changing a scene.
  Or **realistic actors in a real world**: Rigify figures (e.g. Tim and Claudia from the 3D figure kit) that
  act with the same calls, speak with face sliders, plant their feet and keep their hands out of desks -
  `"figures": "rigify"`, `"actors": {"mo": "tim", "kit": "claudia"}` (`film3d.py new ... --figures rigify`);
  they need `<project>/actors/<name>/figur.blend` or the config key `actors3d` (stage-3d guide "Realistic actors").
- **Sound?** Spoken lines by the voice block, recorded wavs, an existing finished sound track, music.
- **Look?** Default: ivory walls, dark walnut, one coral accent, low golden light, the darker "cinema" finish.
  Other palettes / a bright "ad" finish on request.
- **Fast or detail?** Always say what the two cost and ask before a long render: the fast preview (draft quality,
  about 1 hour for 4 minutes of film on an RTX 5060 Ti) shows timing, acting, lip sync and cuts; the film
  quality takes about five times as long. Default: preview first, decide after watching it.

## 2. Creative brief (before any code)

1. `film3d.py new <folder> --title "..." [--cast mo:bear,kit:cat] [--seed N]` → `project.json` (with a **seed**),
   `scenes/c01_opening.py` (a working template).
2. Invent the film from *this* request and record it: `film3d.py idea <folder> "..."` (user ideas `--by user`,
   they always win): the one thing each scene is about, a visual idea per scene (a prop, a light, a place), a
   running detail, the last picture. Give every figure a body language (how it stands, what it does when it doubts).
3. Plan a **light arc**: the time of day per clip (`mood`: golden → dusk → night → dawn, or what the story needs).
   Plan **few, long shots** with real close-ups and cutaways instead of many short ones.
   Room changes can happen **as a theatre set change in view** instead of a cut (walls fly out, furniture rolls
   off, a show stage rolls in, stagehands cross, a follow spot) and a finale can get a **concert light show** -
   stage-3d `stage_theatre.py`. For a spoof / deadpan gag film read [references/gags.md](references/gags.md)
   and plan the gags per clip (foreground / background / sound-or-sign, running gags with plant and payoff).
4. Write the clip list: name, length in frames (24 fps), what happens, the lines spoken. Show it to the user in
   one short block when they are around. `film3d.py clip <folder> c02_plan --frames 240 --about "..." [--xfade 8]`
   adds each clip (and its scene file).

## 3. Lines and sound

- Lines: `film3d.py line <folder> l01 mo "Hello Kit!"` for each; voices in project.json `"voices"` (voice block:
  describe a character voice, never clone a real person). `film3d.py speak <folder>` speaks the missing lines,
  checks them with Whisper, stores the word times and prepares the lip sync. Recorded wavs: put them at
  `speech/<id>.wav`, then `speak` only prepares them. A changed text (`line` again) is spoken again by the next
  `speak`; a recording only gets a warning (record it again). `speak --again` re-speaks the spoken lines and keeps
  recordings unless they are named with `--only`.
- A narrator (voice-over, no figure says it, so no `say()`): `film3d.py line <folder> l07 narrator "..." --at
  c03_night:40` places it on that clip frame. A line that is neither said in a scene nor has `--at` is not in the
  sound - `sound` warns.
- `uv run "${CLAUDE_PLUGIN_ROOT}/skills/stage-3d/scripts/stage_speech.py" show <folder>` prints every line's length
  and word frames – the scenes are blocked on these numbers (`figure.say("l01", frame)`, `K.word_frame(...)`).
- An existing finished sound track (a remake): set project.json `"audio"`, keep every clip exactly as long as its
  stretch of the sound, and take the frames of its events from the old project.
- A new film: after the scenes exist, `film3d.py sound <folder> [--music music.wav]` mixes every line on the frame
  its scene says it → `sound/film.wav`. `preview` / `render` mix it again by themselves (same music) when a line, a
  `say()` frame or a clip length changed; a track you set by hand in `"audio"` is never mixed over. Music without a song: film-finish `score.py`; sound effects: its `sounds.py`
  ideas apply, or mix own effects into the music bed.

## 4. Build the scenes

- One module per clip (`scenes/<clip>.py`: `FRAMES`, `build(S)`), following `stage-3d/references/guide.md`.
  Order per clip: set and light → cast → acting on the sound frames → cameras.
- An own cast: `scenes/cast.py` with one `Char` subclass per figure (stage-3d BLOCK.md "Figures"); render a pose
  sheet of each figure and fix the design before any scene uses it.
- Sets beyond the office: build them in the clip (or a shared `scenes/<set>.py`) from `stage_props` /
  `stage_core`; keep the palette, give every place its own light.
- Many clips: they are independent – several agents can write them in parallel, each owning its scene files, all
  reading the guide; nobody edits the plugin while they work.

## 5. Contact-sheet review (the checkpoint per clip – always)

`uv run "${CLAUDE_PLUGIN_ROOT}/skills/stage-3d/scripts/stage_run.py" clip <folder> <clip> --every 20 --sheet` →
`out/<clip>/sheet.png` (tiles carry frame numbers; at most ~24 per sheet, dense strips with `--stills` for key
actions). Look at every tile: framing and headroom, faces hidden, white on white, floating or intersecting props,
readable text, mouths, **exposure – too bright and too even is the usual mistake**; every tile should pass as a
still of an advertisement. Fix and render again until it does; finish each clip with a few `--q film` stills.

## 6. Fast preview of the whole film, then the decision

`film3d.py preview <folder>` renders every clip in draft quality (resumable), mixes the lines if no sound track is
set, and cuts `preview/film_draft.mp4` with sound and look. Watch for what stills cannot show: timing, acting in
motion, lip sync, cuts, the sound against the picture. Send it to the user and ask: changes first, or render in
detail? Changed clips are found by themselves: a clip whose scene module, project settings (size, palette, lips,
seed, cast) or spoken lines changed is rendered again by the next `preview` / `render` (key in
`out/<clip>/<q>/source.json`), the others are kept. The scene's `FRAMES` must equal the clip's `"frames"` in
project.json (the build stops otherwise). By hand: `stage_run.py clip <folder> <clip> --range a b --q draft
--overwrite`, then cut again (`uv run "${CLAUDE_PLUGIN_ROOT}/skills/film-finish/scripts/clip_film.py" <folder> --q draft`).

## 6b. End credits with outtakes (when the film gets credits)

Credits like an animated feature: the rolling text in blocks, **extra scenes** full screen between the blocks
(a last gag, an epilogue), **outtakes "from the shoot"** in windows beside the text (a clapperboard, a shot of the
film goes wrong, the actors break up laughing, look into the lens, a stagehand walks in) and an optional
**post-credits scene** after black.
1. Add the clips of the credits: `film3d.py clip <folder> outtake_01 --frames 120 --credits outtake` (scene from
   the outtake template: `stage_outtake.take()` = camera + clapperboard, `crack_up()`, `to_camera()`; keep the
   actions big - the take plays in a window) and `film3d.py clip <folder> extra_epilogue --frames 168 --credits
   extra`. With three or more extra scenes the last one becomes the post-credits scene. Each scene module can
   list its sounds: `SFX = [(frame, "earshot id or file", level)]`. These clips are rendered with the film but
   not cut into it.
2. `film3d.py credits <folder> --draft` writes project.json `"credits"`: the text (cast, actors, tools), the extra
   scenes as gags, the outtakes plus seeded excerpts of the film clips as windows, the sounds, the music bed
   (`"music": {"file": ...}`, default the film's sound - give it a real instrumental when there is one). Rewrite
   the text with the real names and credits (film-finish BLOCK.md "credits.py" has every key).
3. `preview` / `render` build the credits by themselves from then on (`preview/credits_draft.mp4` +
   `preview/film_draft_with_credits.mp4`, or `credits.mp4` + `film_with_credits.mp4`); alone:
   `film3d.py credits <folder> [--q draft|film] [--to 20]`. Check `credits_sheet.png`.

## 7. Film render and finish

`film3d.py render <folder>` – film quality for every clip (resumable: stop and start again any time; after a fix
only the frames that look different are rendered again; after a plugin update `stage_run.py film <folder> --q film
--changed` finds the frames it changes; the computer stays awake meanwhile), then the cut:
`film.mp4` + `film_small.mp4` (< 30 MB) + `film_mail.mp4`, each decode-checked. While it runs, cut what is done
(`clip_film.py <folder> --clips c01_opening,c02_plan`) to show progress. After a late change render only those
frames (`--range a b --q film --overwrite`) and cut again.
Per-clip finishing touches: `out/<clip>/post.json` (`fade`, `white`, `saturation` keys), dissolves = `"xfade"` in
project.json, the look = `"look"` (`cinema` / `ad` / `standard` / `none`).

Hand over: the film files, the project folder (every scene is editable code), the seed and the ideas from
project.json; say plainly what you checked only on stills and what you watched in motion.

How the skill was tested against the original project: `references/reference-tests.md`.
