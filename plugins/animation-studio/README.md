# animation-studio

A Claude Code plugin that makes music videos and short animated films on your own machine – classical 2D cartoons
in which characters really sing, brick films, 3D character films in an advertisement look, typographic lyric videos, photorealistic AI-singer videos, animated
presentation figures, talking characters and short 2D scenes. Every kind of film is one **user skill**; everything two
kinds of film share lives once in a **building block**.

Every user skill was tested by rebuilding finished films of its kind and measuring the result against them (see
"Reference tests").

## User skills – what you ask for

| Skill | Ask for example | Builds with |
|---|---|---|
| `animated-music-video` | "Make a cartoon video of this chorus with Tim and Lia singing it." | Synfig scenes on painted sets, lip sync per figure, dancing on the beat, gestures, props, gags, lyrics |
| `bricks-music-video` | "Turn the second verse into a brick film." | Blender + LDraw minifigs, stop-motion timing on twos, printed mouth decals, comic lettering |
| `lyric-music-video` | "A lyric video for our team song that presents the roles from this page." | three.js scenes rendered frame-exact; every letter on the voice; a new visual identity every time |
| `claudia-music-video` | "A Claudia music video for this song, live on stage." | start images (Qwen-Image-Edit / FLUX), LTX-2.3 lip sync and moving B-roll, takes picked by measuring the mouth |
| `animated-powerpoint` | "Let the four figures from slide 5 step out of the slide." | figures cut from the deck, rigged, animated in classic style (entrances, gestures, walk, lip sync for raster figures), a 2.5D stage for whole scenes, a deck intro with page turns and a finale – clips that fit back into the deck |
| `talking-character` | "Tim asks the Computer about context windows – 20 seconds." | script → character voices (Qwen3-TTS / Piper / system) → lip sync → dialogue direction |
| `animated-short` | "A bouncing-ball exercise", "Pip finds a flower", "a new Fips gag." | the 12 principles as keyframes, editable Synfig scenes, sound cues |
| `animated-3d-film` | "Tell this script as a 3D film with toy characters, like a premium ad." | Blender scenes written as Python (Cycles on the GPU): acting figures with lip sync, sets with light moods, close-ups and cutaways, a fast whole-film preview before the film render, cinema look; the figures as felt toys, sewn rag dolls or hand puppets |
| `video-review` | "Show me V1 and V2 side by side per shot and cut the best of both." | synced browser comparison, picks per shot, frame-exact cut without re-rendering |
| `film-tools` | "Put the film look on this video", "make it small enough for e-mail", "check this file". | quick finishing jobs on any existing video: look, small/mail versions, contact sheet, decode check, cutting clips into a film |

## Building blocks – used by the user skills (reference docs `skills/<block>/BLOCK.md`, not skills: they cost no context until a user skill needs them)

| Block | Contents |
|---|---|
| `studio-core` | finding programs (`check_tools.py`, machine config), shared GPU lock, encoding, media helpers, frame comparison, creative seed |
| `song-analysis` | song project, vocal separation, beats, Whisper words aligned to the lyrics and repaired from the vocal tracks, Rhubarb mouths, who sings when (sound + lyrics), held notes, hits, sync checks |
| `toon-2d` | Synfig layer builders, SVG → rig, lip-sync mouth drawings, motion helpers, parallel rendering, painted sets, multiplane camera and 2.5D comic flight, Krita sets, Blender Grease Pencil |
| `characters` | figure sheets and rigs: Tim, Lia, Computer (screen face), Pip, Fips, Claudia's canon; how to add a figure |
| `voice` | fixed character voices, text-to-speech with Whisper checks and retakes |
| `ai-video` | ComfyUI client, FLUX / Qwen-Image-Edit images, LTX-2.3 and Wan2.2-S2V video, Depth Anything, mouth measurement, canon checks, night runs with milestones |
| `bricks-3d` | LDraw importer, minifig rig, decals, sets, EEVEE film runner |
| `stage-3d` | Blender stage for character films: animation tracks with easing, toy rig with acting API and lip sync, props, office set with five light moods, colour palettes, shot helpers, resumable draft / film renders, contact sheets |
| `film-finish` | gag (text and picture) and lyrics overlays, sound effects, full cut on the song timeline, frame-computed transitions (zoom through, glow, screen zoom, iris, flash, dip), title, end credits with gags and outtakes, pop-up version, second audio language, 48 fps, cuts for films without a song, generated film music, subtitles, Kdenlive hand-off, the cut of 3D films from rendered clips with the cinema / ad look, Shaders looks, the standard film look, output sizes (full / < 30 MB / ~12 MB mail), decode checks |

```
 user skills      animated-music-video  bricks-music-video  lyric-music-video  claudia-music-video
                  animated-powerpoint   talking-character   animated-short     video-review
                  animated-3d-film
                          │                    │                   │                 │
 building blocks  song-analysis · toon-2d · characters · voice · ai-video · bricks-3d · stage-3d · film-finish
                          └──────────────────────┬──────────────────────────────────┘
 foundation                                  studio-core
```

## Fresh every time – the creative seed

The plugin should never produce the same routine twice. Each project carries a `seed` and an `ideas` list:

- Every user skill has a **creative brief** step: before building, Claude reads the lyrics or the script and invents
  ideas that belong to *this* song – a concrete image per line, props, gags, reactions, an ending – and records them
  (`by: "ai"`). Ideas from the user are recorded with `by: "user"` and always win.
- Everything the ideas leave open (dance style per figure, camera choices, blink timing, set picks, gesture variants,
  lyric-video identity dice) is varied with the seed: **same seed → same film, new seed → a new take**.
- The reference projects teach techniques, never templates; the lyric-video skill keeps a catalogue of past
  identities precisely so that a new video looks different.

## Install

From GitHub (the repository contains a marketplace in `.claude-plugin/marketplace.json`):

```
claude plugin marketplace add eedokl/music-video-studio
claude plugin install animation-studio@music-video-studio
```

Or from a local copy: `claude plugin marketplace add <folder with .claude-plugin/marketplace.json>`, then install the
same way (a local marketplace loads the plugin in place; edits apply after `/reload-plugins`).

Then, once per machine, ask Claude: **"set up animation-studio"**. Claude runs the studio-core tool check
(`check_tools.py --setup`, from the installed plugin folder - you do not need to know where that is). It finds the
installed programs and writes `~/.animation-studio/config.json` (outside the plugin, so it survives
updates). Missing tools are listed with install hints – Claude asks before installing anything. Paths can also be set
by hand (`--set key=value`) or with environment variables. See `TOOLS.md` for every program and model, what it is
used for and what we recommend.

## How a film is made (common pattern)

1. **Interview** – one round of questions for what is missing (song, lyrics, stems, part, cast, purpose, ideas).
2. **Listen / read** – song-analysis (or the script for dialogues, the deck for slides).
3. **Creative brief** – ideas per line or slide, recorded; a short plan the user can react to.
4. **Build** – per section / shot; contact sheets are read by Claude before anything is shown.
5. **Review checkpoints** – who sings what (`lines.csv`), start images, stills, previews; the user's ear and eye win
   (`corrections.json`, manual picks).
6. **Finish** – film-finish cut, look and output versions, each checked for decode errors; `video-review` to compare
   versions and cut the best of both.

All times are song seconds, so any part can be rebuilt on its own and every layer (mouths, gags, lyrics, sounds)
stays in sync. Every build script first validates the project file (studio-core `project_check.py`): a wrong type, an
overlapping section or a voice that is not in the cast stops the build in seconds with a message naming the key
(exit code 2); unknown keys only warn, with a did-you-mean. `"size": [w, h]` in project.json sets the frame size of
the film (default 1280x720).

## Reference tests (summary)

| Skill | Reference | Result |
|---|---|---|
| animated-music-video | a cartoon music video with three singing figures (one chorus, later the whole song) | who sings: 84–97 % frame agreement; word timing median 0.04–0.10 s; 0 lip-sync gaps; whole film frame-identical in length incl. credits, second language track, pop-up version and 48 fps |
| bricks-music-video | the brick-film version of the same song | open/closed mouth agrees on 98.5–98.7 % of frames; all cuts on beats; beat offset 10 ms |
| lyric-music-video | seven typographic lyric videos | tempo and hits identical or closer to the beat; words closer to the voice than every original (median 80–105 ms vs 110–440 ms) |
| claudia-music-video | an AI-singer music video | lip score on the comparable shot 0.58 vs 0.22; one microphone in 6/6 frames (the reference had two); mouth measurement reproduces the reference log exactly |
| animated-powerpoint | a presentation whose four figures step out of the slides | slide export, upscale and timing identical; nine scenes as reusable recipes: event frames identical or ±1–3 frames, loudness ±0.5 LUFS |
| talking-character | a short talking-figure clip | mouth track 97 % identical, same 166 frames |
| animated-short | two character shorts, a comic flight, a multiplane shot | identical or within GPU rounding (mean ≤ 0.16 of 255) |
| video-review | a three-version music video | 4727/4729 frames from the same source version, audio bit-identical |

How to check a rebuild against a reference: `video-review/scripts/ref_check.py` (effect checklist + dense
side-by-side strips at every event). Each skill's `references/reference-tests.md` has the method and the numbers.

## Rules everyone follows

- One AI model on the GPU at a time (shared lock); never delete another job's lock.
- Only one session builds a project's final film; every output is decode-checked.
- Label AI-made content. Company names only as neutral lettering, no logos, no real politicians.
- Claudia is an open character ("Claudia by anabology"); her canon is in `characters/references/claudia.md`.
- Nothing is installed or downloaded without asking the user.

## Known limits

- Synfig figures are cut-out rigs (flat colours); hand-drawn effects (joy eyes, soft shading) need extra drawings.
- Automatic slide-figure rigging finds head, pupils and body; arms, tails and wings still need a hand-drawn polygon.
- FLUX lettering on painted images is not detected automatically – pick from the contact sheet.
- Not exercised on the GPU in the tests: Wan2.2-S2V jobs, the Claudia live-stage version, Cycles brick renders.
- Large libraries and models (LDraw, model weights) are not bundled; `check_tools.py` says where to get them.

## Platforms – what needs Windows

The plugin was built and measured on Windows 11, but almost everything runs wherever uv, ffmpeg and the external
programs run (Linux, macOS): the scripts are plain Python with forward-slash paths, fonts fall back to DejaVu /
macOS fonts, and every program path can be set by hand (`check_tools.py --set key=value` or `ANIMATION_STUDIO_<KEY>`).
Windows-only:

| Feature | Why | Elsewhere |
|---|---|---|
| animated-powerpoint `deck.py` slide export from `.pptx` | Microsoft PowerPoint through COM (PowerShell, read-only) | slides are composed from their pictures (text missing) – export the slides as PDF/PNG and import those (PyMuPDF) |
| voice engine `system` | Windows speech (System.Speech, SSML) | use `qwen` (Qwen3-TTS) or `piper`; a cast entry falls back to the next engine; the talking-character e2e test SKIPs |
| `check_tools.py --setup` automatic search | globs for `*.exe` under `Program Files` / drive roots | only PATH is searched – set the paths with `--set` (or environment variables) |
| `.cmd` / `.bat` launchers (earshot, ComfyUI start script) | started through `cmd /d /s /c` (studio-core `config.py`), ComfyUI with `start /min` | give a shell script / executable instead; ComfyUI is started as a detached process |
| browser clean-up after headless renders | leftover `msedge.exe` / `chrome.exe` children are ended with PowerShell (toon-2d `render_multiplane.py`) | a plain `kill`; GPU flags without `--use-angle=d3d11` |
| `ai-video/cvio.py` non-ASCII video paths | Windows short names for OpenCV | paths are used as they are |
| e2e tests' directory links | `mklink /J` junctions | symlinks |

Edge is only one choice for the headless browser (config key `browser`: Chrome, Chromium or chrome-headless-shell
work the same). The reference timings in TOOLS.md and the "16 GB VRAM" rules are from the Windows machine.

## Checking the plugin

`python tests/smoke.py` (from the plugin folder) compiles every script, runs `--help` on every CLI, checks that every
script run with uv declares all its third-party imports in its PEP 723 header, checks that every flag a SKILL.md
shows exists, that the `_studio.py` copies are identical, that no new module name collides between skills and that no
machine path slipped in. Run it before every release and bump `version` in `.claude-plugin/plugin.json` - installed
users only get an update when the version changes.

`python tests/e2e/run.py` (from the plugin folder) runs the end-to-end tests: per film type a tiny build (a few seconds
of synthetic input - ffmpeg tones and test pictures, small JSON files - one section or shot) from the first build script
to the final film file, so a break anywhere in a build path shows up. Slow model steps are replaced by synthetic
analysis files (song sheet, voice assignment, timing, clip metadata) or a fake job runner; everything after them runs
the real scripts with `uv run --offline` (no downloads, no network, no AI job on the GPU). Covered: animated-music-video
(one section through overlays, sounds with `"sounds": true` / `false` / a list, `build.py film`; two sections with
fractional boundaries: frame count and cut frame against the sound), animated-short, talking-character (Windows
system voice), animated-powerpoint (scene finishing path with a faked and with the real 2.5D stage render, sound cue
positions), claudia-music-video (fake LTX clips + meta -> `render_shots.py` -> `make_film.py`), film-finish `cut.py`,
video-review (per-frame provenance of the cut), lyric-music-video, bricks-music-video (Blender EEVEE draft, takes the
GPU lock), the night-run kill-and-resume (`.part` outputs), an interrupted caption pass, the up-front project check
(a bad project.json - "sounds" as a string, overlapping sections, a talking figure voiced "male" - is rejected with
exit code 2 in under a second, before anything is rendered) and `"size": [640, 360]` (an animated-music-video film,
its small/mail versions and frame count at that size), and the acting layer of the cartoon scenes (`"acting"`:
listeners turn to the singer, off = unchanged scene).
- `python tests/e2e/run.py --list` names the tests, `run.py animated-music-video claudia` runs a selection (name or
  prefix), `--skip-slow` skips the ones marked slow, `-v` streams the build logs, `--profile` prints the slowest
  commands per test (`log.txt` has every output line with its elapsed seconds), `--keep` keeps the temp folders.
- Default is the fast mode: it only drops work a test does not check (the film look where the test protects frame
  counts or sync - the look itself is tested in the one-section, short, powerpoint and cut tests; a 2 s instead of a
  3 s section in the one-section music-video test). `--full` runs everything real (before a release).
- Each test builds in its own temp folder and prints PASS / FAIL / SKIP with the reason and its runtime; the exit code
  is 1 when a test fails. A failed test keeps its folder (`log.txt` holds every command and its output).
- A test SKIPs when a program it needs is not configured (studio-core `config.py`: synfig, rhubarb, earshot, blender +
  ldraw_dir, node + browser). The tests use a copy of `~/.animation-studio/config.json`, never the file itself.
- lyric-music-video needs the engine's `node_modules` (`npm install` is a download): set
  `ANIMATION_STUDIO_E2E_NODE_MODULES=<an existing lyric-video project>/video/node_modules` - its packages are linked
  into the temp project and unlinked afterwards; without it the test SKIPs.
- The whole suite takes about 2 minutes on the studio machine (1-21 s per test; the first run after a plugin update
  builds the uv environments of the test drivers once, ~10 s each).

See `CONVENTIONS.md` before adding or changing a skill.
