---
name: talking-character
description: "Make classical 2D cartoon scenes where characters TALK: a dialogue script (\"Tim: ... / Computer: ...\") or a real recording becomes voices with a fixed voice per character (Qwen3-TTS), lip sync per figure (Rhubarb), an editable Synfig scene where figures speak, listen, look at each other and gesture on words, camera cuts, subtitles, sound effects and the standard film look. Use this whenever the user wants a character to say something, a dialogue or conversation scene, a talking head, a sketch between Tim, Lia and the Computer (or their own Inkscape figures), a spoken intro/announcement, lip sync for a line or a recording, or wants to change, re-voice or re-time such a scene – even if they only paste a few lines of dialogue and say \"animate this\"."
---

# talking-character – dialogue scenes with lip sync

Building blocks: `voice` (TTS, fixed voices, Whisper check), `toon-2d` (Synfig, svg2sif, lip-sync mouths, motion),
`characters` (tim.svg, lia.svg), `film-finish` (subtitles, sounds, look, film), `studio-core` (config, media,
creative seed, GPU lock), `song-analysis` (project layout, Whisper word alignment).
Scripts: `${CLAUDE_PLUGIN_ROOT}/skills/talking-character/scripts/`. Run them with
`uv run "<script>" ...`.

**Building blocks** (shared code + docs of this plugin, not skills - read the one you need):
`${CLAUDE_PLUGIN_ROOT}/skills/<block>/BLOCK.md` for `studio-core`, `song-analysis`, `toon-2d`, `characters`, `voice`, `ai-video`, `bricks-3d`, `film-finish`. In those files
`<plugin>` stands for `${CLAUDE_PLUGIN_ROOT}`. First use on a machine: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py" --setup` (finds the programs).

## 1 Interview (short)

Ask only what is missing: who talks (bundled Tim, Lia, the Computer – or the user's own SVG figure), what about,
how long (default 15–20 s), language (default German), script by the user or by you, a recording or TTS voices,
where (set: `room` = Tim's room with the monitor, `stage`, `color:#hex`, or a project set).

## 2 Creative brief (before building)

Write the dialogue with **direction**, not just text – invent from *this* topic:
- a turn in the middle (misunderstanding, surprise, a reveal) and a punchline at the end;
- 2–4 gestures on the words that carry the meaning (`(scare) Der Kuchen!`), one look direction
  (`(looks up)`, `(to computer)`), pauses where a cartoon timing needs them (`(beat)`, `(pause 1.2)`);
- for the Computer one or two screen gags (`(screen "REIM.EXE")`) instead of its face.
Record each idea with `creative.add_idea(P, "ai", "...", "dialogue")` (user ideas: `by: "user"`, they win).
Never reuse the reference dialogue as a template. A new creative seed gives new listening styles, accent
strengths, hand gestures, blink rhythm and camera shots for the same script.

Script format (full list in `scripts/dialogue.py`):
```
Tim: (to computer) Computer, ich brauche ein Gedicht. Schnell!
Computer: (screen "REIM.EXE") Gerne, Tim. (beat) Rosen sind rot ...
Tim: (scare) Der Kuchen! (point at computer) Den hab ich vergessen!
(pause 0.8)
Pip: (surprise) Oh! (looks up) (pause 1.1) Ein Blatt!
```
Directions: `(pause s)` `(beat)` `(to <name>)` `(looks up|down|away|camera)` `(interrupts)` `(quick)` `(slow)`
`(screen "TEXT")`, gestures `cheer point scare surprise scratch nod sad shrug wave jump lean`
(`(nod tim)` = the listener Tim nods here; `(point at computer)` = towards).

## 3 Build

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/talking-character/scripts"
python "$S/new_talk.py" <folder> --script dialogue.txt [--set room] [--recording take.wav] [--seed N]
uv run "$S/make.py" --project <folder> --to voices     # voices only: let the user hear <folder>/song.wav
uv run "$S/make.py" --project <folder> --from scene    # then scene, subtitles, sounds, film, check
```
(Without `--to` / `--from` it runs all steps in one go - fine when nobody wants to hear the voices first.)
`make.py` checks project.json first (studio-core `project_check.py`): every figure's `"voice"` must be a voice of the cast (voice block `assets/cast.json` or project `"voices"`) – not a role like "male" – else it stops with exit code 2 before any voice is made. `"size": [w, h]` = frame size (default 1280x720).
`make.py` runs: `speak.py` (voices, timeline, Rhubarb per line, word times) → `talk_scene.py --render`
(scenes/dialogue.sif + frames) → film-finish `overlays.py dialogue` (subtitles) → `sounds.py` (gesture sounds,
earshot) → `build.py film` (look, film.mp4 / film_small / film_mail, 0 decode errors) → `check_sync.py`.
`--from scene` re-runs from a later step (voices are cached in `lines/` and only re-spoken when a text changes);
`--to <step>` stops after a step.
A single figure (no other figure, no screen) stands in the middle of the set (the set's `places` are dialogue spots); `"place": x` moves it.
Harmless lines in make.log from the Qwen3-TTS library: "SoX could not be found", a flash-attn warning, and on
some Windows machines a cmd "AutoRun" registry message - the voices are fine (check the Whisper score per line).

project.json keys (besides the song-analysis ones): `script`, `recording`, `figures` {name: {svg | kind: screen,
voice, place, size, mouth, follow, arms, hands}}, `voices` (overrides, see the voice block), `set`, `view`,
`camera` (`auto` | `static` | `cuts`), `close_zoom`, `direction` {lead_in, gap, jitter, quick, slow, interrupts,
tail}, `subtitles` (true), `sounds` (optional: gesture sounds are on without it; `false` switches them off; a
list of extra rules as in film-finish `sounds.py`, e.g. `"sounds": [{"sfx": "ui_pop/blip", "word": "hallo"}]`),
`pronounce`, `look`.

Own figure: Inkscape SVG with the rig convention of the characters block (groups `kopf`, `auge_l/r`,
`pupille_l/r`, optional `arm_l/r`, `brauen`; pivots `pivot_<part>`; `pivot_mund` where the mouth goes; feet at
(200, 590); 72 px = 1 unit). Parts that should swing after the head (antenna, ears, a leaf) go into `"follow"`.
A figure without arms (`"arms": false`) hops and leans instead of gesturing.

## 4 Review checkpoints

1. After `speak.py`: the line table (times, Whisper score per line). Lines under 0.8 → fix the text
   (`pronounce`) or re-take; let the user hear `song.wav` before rendering.
2. After the scene: look at 3–4 single frames (`synfig scenes/dialogue.sif -t png --time 40f -o x.png`) –
   placement, who looks at whom, the screen texts.
3. After the film: `check_sync.py` numbers – agreement mouth-open vs voice ≥ 0.85, 0 silent gaps; open
   `contact_sheet.png`; give the user `film.mp4`.

References: `references/reference-tests.md` (rebuild of "Pip spricht", fresh Tim/Computer dialogue).
