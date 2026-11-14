# animation-studio

A Claude Code plugin that makes music videos and short animated films on your own machine – classical 2D cartoons
in which characters really sing, brick films, typographic lyric videos, photorealistic AI-singer videos, animated
presentation figures, talking characters and short 2D scenes. Every kind of film is one **user skill**; everything two
kinds of film share lives once in a **building block**.

The plugin grew out of real projects ("Prompts!" with Tim, Lia and the Computer, its brick-film version, six lyric
videos, "Europe 2031" with the singer Claudia, the Pip and Fips shorts, a presentation whose figures step out of the
slides). Each user skill was rebuilt against those projects as references and measured (see "Reference tests").

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
| `video-review` | "Show me V1 and V2 side by side per shot and cut the best of both." | synced browser comparison, picks per shot, frame-exact cut without re-rendering |

## Building blocks – used by the user skills (hidden from the `/` menu)

| Block | Contents |
|---|---|
| `studio-core` | finding programs (`check_tools.py`, machine config), shared GPU lock, encoding, media helpers, frame comparison, creative seed |
| `song-analysis` | song project, vocal separation, beats, Whisper words aligned to the lyrics and repaired from the vocal tracks, Rhubarb mouths, who sings when (sound + lyrics), held notes, hits, sync checks |
| `toon-2d` | Synfig layer builders, SVG → rig, lip-sync mouth drawings, motion helpers, parallel rendering, painted sets, multiplane camera and 2.5D comic flight, Krita sets, Blender Grease Pencil |
| `characters` | figure sheets and rigs: Tim, Lia, Computer (screen face), Pip, Fips, Claudia's canon; how to add a figure |
| `voice` | fixed character voices, text-to-speech with Whisper checks and retakes |
| `ai-video` | ComfyUI client, FLUX / Qwen-Image-Edit images, LTX-2.3 and Wan2.2-S2V video, Depth Anything, mouth measurement, canon checks, night runs with milestones |
| `bricks-3d` | LDraw importer, minifig rig, decals, sets, EEVEE film runner |
| `film-finish` | gag (text and picture) and lyrics overlays, sound effects, full cut on the song timeline, frame-computed transitions (zoom through, glow, screen zoom, iris, flash, dip), title, end credits with gags and outtakes, pop-up version, second audio language, 48 fps, cuts for films without a song, generated film music, subtitles, Kdenlive hand-off, Shaders looks, the standard film look, output sizes (full / < 30 MB / ~12 MB mail), decode checks |

```
 user skills      animated-music-video  bricks-music-video  lyric-music-video  claudia-music-video
                  animated-powerpoint   talking-character   animated-short     video-review
                          │                    │                   │                 │
 building blocks  song-analysis · toon-2d · characters · voice · ai-video · bricks-3d · film-finish
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

The plugin is a folder; a local marketplace makes Claude Code load it in place (edits apply at the next session or
after `/reload-plugins`):

```
claude plugin marketplace add <path>/plugins            # the folder that contains .claude-plugin/marketplace.json
claude plugin install animation-studio@local-animation
```

Then, once per machine:

```
python <plugin>/skills/studio-core/scripts/check_tools.py --setup
```

It finds the installed programs and writes `~/.animation-studio/config.json` (outside the plugin, so it survives
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
stays in sync.

## Reference tests (summary)

| Skill | Reference | Result |
|---|---|---|
| animated-music-video | "Prompts!" first chorus | who sings: 84 % (Tim) / 89 % (Lia) frame agreement; word timing median 0.10 s after the vocal-track repair (mean error 0.38 → 0.21 s); 0 lip-sync gaps; second song (rock, DE/EN, no stems) works with its own ideas |
| bricks-music-video | "Prompts!" brick film, section 7 | open/closed mouth agrees on 98.7 % of frames; all cuts on beats; beat offset 10 ms |
| lyric-music-video | "Europe 2031" / Comfort Zone lyric video | tempo and hits identical; words closer to the voice than the original (median 97 ms vs 200 ms); SSIM 0.97 over the whole song |
| claudia-music-video | "Europe 2031" V2 | lip score on the comparable shot 0.58 vs 0.22; one microphone in 6/6 frames (the reference had two); mouth measurement reproduces the reference log exactly |
| animated-powerpoint | the Helmut / Hans / Fritz / Felix deck | slide export, upscale and timing identical; rest pose at parity with the hand-made rig; scenes S4–S12 as reusable recipes: event frames identical or ±1–3 frames, loudness ±0.5 LUFS |
| talking-character | "Pip spricht" | mouth track 97 % identical, same 166 frames; new Tim/Computer dialogue with Qwen3-TTS |
| animated-short | Pip and the Flower, Fips, comic flight, multiplane | identical or within GPU rounding (mean ≤ 0.16 of 255) |
| video-review | the user's own "Europe 2031" V3 | 4727/4729 frames from the same source version, audio bit-identical |

Full-length rebuilds (night 13/14 Nov 2026) and the rest-point run: "Prompts!" complete with credits, English track,
pop-up and 48 fps (frame-identical length, 31+ picture gags, comic caption boxes per panel, inset rules), the whole
brick film (name signs, puppet strings, steam, vanishing coins), all seven lyric videos (held notes stretched,
refined tempo), the deck. How to check a rebuild: `video-review/scripts/ref_check.py`.

Each skill's `references/reference-tests.md` has the method and the numbers.

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

See `CONVENTIONS.md` before adding or changing a skill.
