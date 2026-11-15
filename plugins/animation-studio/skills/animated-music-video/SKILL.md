---
name: animated-music-video
description: "Turn a song (wav/mp3, optional lyrics and stems) into a classical 2D cartoon music video in which characters really sing it - Tim, Lia and the Computer or the user's own Inkscape figures - as editable Synfig scenes on painted sets: who-sings-what, lip sync, dancing on the beat, gestures and props on keywords, gags, lyrics, sound, transitions and the film look. Use whenever the user wants a cartoon / animated / \"Zeichentrick\" music video, characters singing a song, an animated pilot of a chorus, or to continue or fix such a video (project.json + scenes/) - even if they only attach a song. Text-only lyric videos: lyric-music-video; brick films: bricks-music-video; AI singers: claudia-music-video."
---

# Animated music video

A song becomes a cartoon in which the characters sing it: the sound decides **who** sings, the lyrics decide **as
whom**, every mouth comes from the vocals, every move sits on a beat. Everything lives on **one timeline – the song's
seconds** – so scenes, mouths, gags, lyrics and sounds always fit together and any part can be redone on its own.

Building blocks used (sibling skills of this plugin): `song-analysis` (listen), `toon-2d` (Synfig rig, sets),
`characters` (Tim, Lia, Computer, own figures), `film-finish` (overlays, sounds, cut, look), `studio-core`
(tools, GPU lock, creative seed). Reference film: "Prompts!" (4:08, Tim, Lia and the Computer) – this skill rebuilds
its first chorus with 84–89 % frame agreement of who sings and ~0.1 s median word timing (see
`references/reference-tests.md`).

Scripts (run with `uv run <script> ...`):
- `${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py` – once per machine (`--setup`)
- `${CLAUDE_PLUGIN_ROOT}/skills/song-analysis/scripts/new_project.py`, `analyze.py`, `voices.py`
- `${CLAUDE_PLUGIN_ROOT}/skills/animated-music-video/scripts/scene.py` (+ `captions.py` for comic caption boxes,
  `acting_draft.py` for faces from the lyrics)
- `${CLAUDE_PLUGIN_ROOT}/skills/film-finish/scripts/overlays.py`, `sounds.py`, `build.py`
- `${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/media.py sheet <video> <png>` – contact sheet

**Building blocks** (shared code + docs of this plugin, not skills - read the one you need):
`${CLAUDE_PLUGIN_ROOT}/skills/<block>/BLOCK.md` for `studio-core`, `song-analysis`, `toon-2d`, `characters`, `voice`, `ai-video`, `bricks-3d`, `stage-3d`, `film-finish`. In those files
`<plugin>` stands for `${CLAUDE_PLUGIN_ROOT}`. First use on a machine: `python "${CLAUDE_PLUGIN_ROOT}/skills/studio-core/scripts/check_tools.py" --setup` (finds the programs).

## 1. Interview (one round)

Ask only for what is missing: the **song**; **lyrics** with section markers if they exist (`[Chorus]`,
`[Verse 1 - Tim, male lead]`, `[Spoken - narrator]`); **Suno stems** (Vocals + Backing Vocals) if the song is from
Suno; **which part** (default: one chorus as a pilot – a whole song is hours of iteration); **cast** (Tim, Lia,
Computer, or own figures as Inkscape SVG); **what the song is about** and any ideas the user already has.

## 2. Listen

1. `new_project.py <folder> --song s.mp3 --lyrics t.txt [--lead v.wav --backing b.wav] [--from 38.3 --to 66.7
   --lyrics-from "first sung line" --lyrics-to "last sung line"] [--language de|en|auto]`
   With an excerpt, trim the lyrics to the sung lines – otherwise word times break (the script warns).
2. `analyze.py <folder>` – beats, bars, words (Whisper, VAD retry, repaired from the vocal tracks: calls in brackets
   come from the backing stem), Rhubarb mouths, male/female track (earshot). Look at `analysis/song_sheet.png`.
3. `voices.py <folder>` – who sings each frame. **Show `analysis/lines.csv` to the user** (who sings which line) and
   ask them to listen. Their ear wins: fixes go to `corrections.json`
   (`[{"from": 98.4, "to": 112.6, "figure": "tim", "reason": "..."}]`) and survive every re-run.

## 3. Creative brief – new ideas every time

Before writing sections, read the lyrics line by line and ask: what concrete image, object, prop, gag or reaction
belongs here? Invent for *this* song (a cloud auction, coins raining on the screen at "Tokens", the Computer's screen
overheating at "GPU glühen", Tim hiding behind the desk at "Limit"). Record every idea with
`creative.add_idea(P, "ai"|"user", idea, section)` (studio-core `creative.py`) – user ideas always win. Show the
user a short plan (one line per section: set, who, 2–3 ideas) and go on unless they want a say.
The **seed** in project.json varies everything not fixed by an idea (dance style per figure: arms / bounce / step /
twist, blink timing, ...): same seed → same film, new seed → a new take. Never rebuild "Prompts!" for another song.
Since 0.4.19 the seed picks ONE dance style per figure for the whole film (before: one per figure and section): a
project made before that without `"dance_style"` dances differently when re-rendered - pin the old styles with
`"dance_style": {"tim": "step", ...}` (project or section) if the old film must stay as it was.

## 4. project.json (song seconds everywhere)

```json
{
 "seed": 4711,
 "figures": {
  "tim": {"svg": "skill:characters/assets/figures/tim.svg", "voice": "male"},
  "lia": {"svg": "skill:characters/assets/figures/lia.svg", "voice": "female", "entrance": "flicker", "aura": "#b48cff"},
  "computer": {"kind": "screen", "voice": "announcer"}
 },
 "narrator": "computer",
 "announcements": ["Willkommen", "Upgrade"],
 "sections": [
  {"name": "verse1", "from": 11.6, "to": 38.3, "set": "room", "dance": "never", "lyrics": true},
  {"name": "chorus1", "from": 38.3, "to": 66.7, "set": "stage", "dance": "chorus", "push_in": 0.04,
   "dance_style": {"tim": "step"}}
 ],
 "gags": [{"word": "(tokens", "text": "TOKENS!", "color": "#ffd23f", "place": "auto"}, {"word": "chips", "icon": "chip"}],
 "lyrics_style": "pop",
 "gestures": [{"word": "limit", "figure": "tim", "gesture": "scare"}],
 "screen": [{"word": "gpu", "text": "GPU 100 %\nTEMP 98 °C", "color": "#ff8a5c", "duration": 1.6}],
 "screen_badges": [{"text": "FREE", "bg": "#3a7d44"}, {"text": "PRO", "on": "pro", "bg": "#2f6fb5"}],
 "props": [{"image": "props/gpu.png", "x": -4.7, "height": 2.6, "show_on": "gpu", "bounce": true}],
 "sounds": [{"word": "quota", "sfx": "glitch/burst", "level": -12}],
 "transitions": [{"at": 11.6, "kind": "zoom_through", "center": [0.22, 0.3]}, {"at": 38.3, "kind": "glow"}],
 "title": {"text": "Prompts!", "from": 0.5, "to": 3.5},
 "ideas": [{"by": "ai", "idea": "screen overheats at 'GPU glühen'", "where": "chorus1", "status": "done"}],
 "acting": true,
 "look": "standard"
}
```

- Figures: `voice` male / female / announcer (announcements, robotic parts). `narrator`: narrated sections (lyrics
  talk *about* a figure and never say "I") go to this figure while the hero acts. Own figures:
  `{"svg": "figures/oma.svg", "voice": "female", "size": 0.9, "mouth": 0.5}` – Inkscape SVG with the rig convention
  of the `characters` block (BLOCK.md). `kind: "screen"` draws the figure as a face in the set's screen.
- Sections: `set` = `stage` (full figures, screen at the back), `room` (night room, desk hides legs, monitor),
  `color:#203040`, or an own set in `<project>/sets/<name>/set.json` (copy one from toon-2d `assets/sets/`;
  painted PNGs from Krita or FLUX, `places` = x of each figure's feet, `floor`, `scale`, `screen` rectangle,
  `front` layers, optional `desk`). `dance`: chorus (markers or repeated lines) / always / never. `places` per
  section override the set. Sections should touch; gaps turn black.
- Word triggers (gestures, gags, screen events, badges, meter, props, sounds ...): prefix by default (`"token"`
  matches "Tokens!"), `"=pro"` = exact word (not "Prompts", not "Pro-Limit"), `"re:^verkauf(t)?$"` = regular
  expression on the word without edge punctuation; `"(word"` matches only calls in brackets
  (song-analysis `song_project.word_matches`). Gags, sounds and screen events take `"sections": [...]` /
  `"not_sections": [...]` (e.g. no name gags in a comic flight whose panels already show the names).
- Gestures: scare, cheer, point, scratch, nod, sad on a word. Gags: short shout words / labels on a word – companies only as neutral lettering, never logos.
  Screen events: text on the Computer's screen instead of its face (terminal lines, prices, warnings);
  `"tint": "#6b1a1a"` colours the whole screen from the word on (`"tint_until": "egal"` = until that word, else
  `"tint_for"` / `"duration"` s) – e.g. the screen turns red at "Quota".
  Screen badges: a label that stays in the screen's corner and changes on a word (tier FREE → PRO → MAX, a clock,
  a level, a battery); its state carries over from section to section.
  Props: own images (draw them, paint with FLUX via the `ai-video` block, or Krita) placed on the set, shown on a
  word, bouncing on the beat.
- **acting** (`"acting": true`, off by default; a section may set `"acting": false`): the figures look at each
  other and react instead of only keeping the beat - listeners turn eyes first, then the head, to whoever sings
  (each with its own reaction delay from the seed, so a change of singer runs through the group), keep looking a
  moment after the last note, nod at the end of some lines; a singer looks ahead and glances at a partner at some
  line ends; a listener's brows jump at a gag word; the face on the screen looks down at the singer. Gestures and
  actions win, dancing halves it. Options: `{"strength": 1.0, "glances": true, "nods": true, "brows": true}`.
  `scene.py` prints the counts per figure (`acting {...}`). Turn it on for verses and dialogue-like songs; it
  matters most where figures sing one after the other (`scene_acting.py`).
- **expressions** (`"expressions": [{"figure": "tim", "expression": "shock", "word": "limit" | "line": "Wer
  gewinnt" | "from": 12.7, "duration": 1.5 | "to": 13.9}]`): a face for a moment - `grin`, `skeptical`, `shock`,
  `angry`, `sad`. Each brow lifts and tips on its own, the eyes widen or narrow, the cheeks rise, the head tilts,
  and while the figure is silent it gets the expression's own mouth (o, grin, smirk, frown; a singing mouth always
  wins). Set them where a figure LISTENS and the lyric gives a reason (the other one brags -> skeptical, a price
  is named -> shock) - a reaction per line reads far better than motion on every beat. With `"acting"` the face
  also turns: eyes, glasses, brows, nose, cheeks and mouth slide together inside the head outline toward the one
  it looks at (parts `nase` / `wangen` of the rig, see the `characters` block).
  **Automatic first pass:** `acting_draft.py draft --project <folder>` writes `analysis/acting.json` - per sung
  line who sings it, how loud the voice is against the song's own average and a mood (neutral, happy, cheeky,
  proud, sad, angry, alarm, question). The script only guesses the mood from signal words: **read every line
  yourself and correct `"mood"`** (set `"by": "ai"`, or `"user"` when the user said so - such rows survive every
  later draft; irony and context are yours to read, not the script's). `acting_draft.py apply` then writes the
  expressions: a listener reacts to the line (proud -> skeptical, alarm / angry -> shock for everybody, happy ->
  grin, sad -> sad), the singer shows its own face when nobody listens or the line is sung with force; at most
  one expression per figure at a time with a pause between; hand-set expressions stay and win.
- Transitions (computed frame by frame on the finished cut – no handles, sections stay on their song frames):
  `zoom_through` (the last frame zooms into a window/door/screen while the new scene settles), `glow` (warm light
  burst – a room becomes a stage), `screen_zoom` (camera into a big screen, close-up settles), `iris` (closes onto a
  detail such as a grin, opens from the middle), `white` (flash on a downbeat), `black` (short dip). Each takes
  `"center": [x, y]` (0..1); 6–14 frames. Leave abrupt musical stops as hard cuts. An iris-out ending can close
  early and hold black: `{"kind": "iris", "close": 30, "open": 0, "hold_black": 10}`.
- Title: `{"text", "from", "to", "color"}` plus optional `"place": "top"` (or `"y"` px), `"size"`, `"shadow"`,
  `"animation": "pop"` (scales in with an overshoot wobble, as in "Prompts!"), `"fade_out"` s (film-finish build.py).

### Scene features (from the reference film, generic for any figure and song)

Times can always be given by `"word"` (prefix, like gestures), `"line"` (start of a lyric line), `"marker"` (lyric
marker such as "final chorus"), `"from"`/`"to"` (song seconds) or `"until_word"`; the seed varies everything not set.

```json
"actions": [{"figure": "tim", "action": "typing", "when": "listening"},
            {"figure": "tim", "action": "typing", "line": "Mit den Händen", "speed": "fast"},
            {"figure": "tim", "action": "guitar", "when": "singing", "sections": ["verse3"]}],
"screen_meter": {"fill_on": ["limit"], "empty_on": ["upgrade", "max"], "start": 0.55, "creep": 0.0, "label": "TOKENS"},
"silhouettes": [{"word": "lederjacke", "motion": "rise"}],
"sections": [
 {"name": "verse3", "set": "stage", "light": "spotlight"},
 {"name": "finale", "set": "stage", "light": {"kind": "disco", "marker": "final chorus", "palette": "neon"}},
 {"name": "ending", "set": "room", "light": {"kind": "night", "at": "silence", "until_word": "willkommen"}},
 {"name": "announce", "set": "room", "shot": "screen"},
 {"name": "bridge", "kind": "panels", "figures": [], "inset": {"corner": "bl"}, "caption": true, "camera_move": true,
  "panels": [{"line": "Wer gewinnt", "layers": ["panels/b1_bg.png", "panels/b1_fig.png"]}, {"figures": ["lia"], "shot": "close"}]}
]
```
- **actions** (actions win over gestures; a gesture on a word interrupts a `when` action): `typing` – own arms IN
  FRONT of the body, elbows out, hands always visible ON a keyboard prop (on the desk in sets with a desk, on an X stand
  that appears only while typing elsewhere), alternating key strikes on the beat grid (seed: 3–4 per beat fast, 2–3
  slow; `when` actions default to slow), keys light up, one key click per strike goes to
  `analysis/actions_<section>.json` (`"sfx"`, film-finish `sounds.py` plays it). `guitar` – air guitar across the body,
  strum arm in front swinging around the elbow on every beat or half beat (seed), headbang; guitar colour from the seed
  or figure key `"guitar"`. The rig arms are switched off via `amount` while the action runs. `when`: listening /
  singing / always (outside choruses unless `"in_chorus": true`, spans shorter than `"min"` s dropped).
- **screen_meter**: usage bar on the Computer's screen; fills and turns red (blinking) on a fill word, empties on an
  empty word; the state carries over from section to section (all words of the song are read); style bar / segments (seed).
- **light** per section (string, dict or list; each may have a time span): `spotlight` – dark stage, a cone on every
  figure; the figure singing most stays lit, the others appear (hologram flicker) only in their own coloured light while
  they sing; the screen is dimmed unless the Computer speaks; figures closer (scale x1.25), lead in the middle (cone
  colour from the seed). `disco` – four coloured cones alternating on every beat, seeded confetti (`"confetti": 70`),
  stronger camera pulse on downbeats (palette neon / sunset / ice / carnival from the seed). `night` – the room darkens
  (set 0.7, figures 0.35), the screen keeps glowing over the darkness, light again (fading to `"residual"` 0.25) at
  `until_word`; `"at": "silence"` = the first quiet beat (an abrupt stop).
- **silhouettes**: a faceless dark figure (or `"image"`) between two set layers on words – sets name the layer with
  `"window": {"layer": 1, "x": -5.0, "y": 1.5}` (bundled room: between sky and wall, inside the window); in a spotlight
  section without a window it becomes a big shadow in the dark. Motion rise / slide / fade (seed); `"hold"` s after the line.
- **inset** (section): round frame in a corner (seed: bottom left/right) with a bust of whoever sings among the figures
  not drawn in the section (default; or `"figures"`), lip sync from assignment.json, pops on every change, hidden while
  that figure is on screen (in panels: while it is in the current panel). Also over frames from other renderers
  (multiplane intro, comic flight, break-out): `{"kind": "external", "inset": {"corner": "br", "figures":
  ["computer", "lia"]}}` – `scene.py <section> --render` renders only the inset as a transparent track
  (`scenes/<section>_inset/`) and lays it over `scenes/<section>/` (originals kept in `scenes/<section>_raw/`,
  together with a `"caption"` box; re-running never stacks).
- **show** (section): a figure appears only from a line / word / time on – `"show": {"lia": {"line": "Nur noch
  meeeehr" | "line_index": 77 | "word": "ultra" | "from": s, "while": "singing" | "always"}}`; hologram flicker in,
  `singing` = visible only while it sings (like a figure in the spotlight). E.g. Lia only for the last line.
- **pulse** (section): heartbeat camera – `{"every": 0.85, "at": "silence" | "from": s | "word": .., "to": s |
  "until_word": .., "amount": 0.02, "push": 0.12}`: a small kick every beat of the heart and a slow push-in over the
  span (pair it with a heartbeat sound series, film-finish `sounds.py` `{"every": ...}`).
- **kind "panels"** (section): a comic page (toon-2d `comic_page.py`, 2–3 columns from the seed) lies on a desk; the
  camera cuts hard on every lyric line start to the next panel and pushes in with a little roll. Panel content per
  line (`"line"`) or in order: `"layers"` (painted PNGs, cropped to the panel, slow parallax push), or `"figures"` +
  `"shot"` close/medium/wide (rig figures with lip sync), default: whoever sings the line, sometimes with a listener.
  `"caption": true` types the sung line word by word into a comic caption box (`captions.py`, also usable on comic
  flights rendered elsewhere into scenes/<section>/); shout words stay gags (overlays), never inside panels.
  Caption options: `"group": "panel" | "couplet" | "line"` – on a comic flight all lines read in one panel share ONE
  box (panel times from the comic page's camera keys, found via the section's renderer json or `"comic"`; `"lead"`
  1.5 s: the camera may reach the panel that much after its line starts), lines are joined with " – "; `"places":
  {"p5": "bottom_right"}` per panel; `"ghost": 0.3` shows the words still to come faintly (a held first word never
  leaves an empty box); a box stays until the next one starts (no gap while a figure breaks out of the page).
  `"panel_aspect": "16:9"` shapes the panels like the screen and the camera covers the whole panel (no page edge or
  neighbour panel in the picture; without it the panels are 1.2–1.6 wide and the neighbours show at the sides).
- **shot "screen"**: close-up of the Computer's screen (screen rectangle `[-4.7, 3.35, 4.7, -2.45]` or own
  `"screen"`), set behind 1.2x and darkened (`"dim"` 0.55), push-in 0.08, only screen figures unless `"figures"`.
- **camera_move** (section): marks a camera flight; `film-finish/scripts/fps48.py` interpolates only these (and panel
  sections, never across their cuts) with RIFE and doubles all other frames -> `film_48fps.mp4`. Give `"shots": []`
  (or the song seconds of its hard cuts) for a flight without cuts: then fps48 uses these instead of pixel
  differences, which mistook fast camera moves and caption pops for cuts.
- **screen window**: a `"screen"` event with `"window": "Context Window"` (+ `"rows"`, `"color"`, `"min"`) pops an
  app window out over the Computer's screen (0 -> 1.12 -> 1) on the word until the line ends, instead of text on it.
- **steam**: `"steam": [{"word": "=hirn", "figure": "tim", "until": "(hirn", "from": "line", "every": 9}]` – puffs
  rise from the figure's head (drawn inside the figure, so they follow its dance) from the line start to the word.
- **lyrics** per line (film-finish overlays.py): `"lyrics_skip": ["Pro-Limit", "Ha. Ha."]` (announcements/effects
  without lyrics) and `"lyrics_lines": [{"line": "Mein letzter", "style": "whisper"}, {"contains": "quota", "style":
  {"base": "rock", "size": 46}}, {"index": 71, "style": "pop"}]`, project-wide or per section.

## 5. Build and look

Every build script checks project.json first (studio-core `project_check.py`, details in song-analysis "Project check"): a wrong type, an impossible section (from >= to, duplicate name) or an unknown transition stop it in seconds with exit code 2 and the key named; unknown keys and overlapping sections (build.py cuts at the next start) only warn.
`"size": [w, h]` sets the frame size of scenes and film (default `[1280, 720]`; keep 16:9 – the sets are 16:9).
Per section: `scene.py <section> --project <folder> --render` → `overlays.py <section> --project <folder>` → (all
sections) `sounds.py --project <folder>` → `build.py preview <section> --project <folder>` or `build.py film --project <folder>`.
A word that is still shown at the wrong time (analyze.py warns e.g. "'Out of' sits far before the rest"): add the
missing call to lyrics.txt and re-run `analyze.py --redo`, or edit its `"t"` / `"end"` in `analysis/song_sheet.json`
by hand (keep a copy; `--redo` overwrites it), then re-run `overlays.py`. The mouths come from the vocals (Rhubarb)
and do not change. Then **look at your own result before showing it**:
`media.py sheet film.mp4 sheet.png` and read the image. Check: figures in frame and not covering the screen face,
mouths open when the voice sings, gags readable, nothing repeats mechanically. Fix and rebuild only what changed.
Optional versions: a **48 fps film** (`film-finish/scripts/fps48.py` after `build.py film`, needs RIFE – config key
`rife`, ask before installing), a **pop-up video** (`film-finish/scripts/popup.py --draft`, then rewrite the cards and run it),
**end credits** with gags, film excerpts/outtakes and a post-credits scene (`film-finish/scripts/credits.py --draft`,
then check the text, turn the drafted gags into jokes about this song, build; `build.py film` rebuilds them after every
new film) and a second audio language (see `references/techniques.md`). Deliver `film_small.mp4` (or the section preview); mention `film.mp4`, `film_mail.mp4` and that every scene `.sif`
opens in Synfig Studio for hand animation.

## 6. Extending

`scene.py` is one script for all sets; extend it with new behaviours (a new gesture, a new set feature) instead of
writing scenes from scratch, and keep them seed-driven. Its layer builders sit next to it as `scene_*.py` modules
(`scene_acting.py` = the acting layer) taking one `SceneContext` (`scene_context.py`: section times, beats/words/lines, who sings when, places, lights);
the comment block in `scene.py` says which module holds what. Bigger techniques from the reference film (2.5D comic flight
for a verse, multiplane intro, credits with outtakes, second audio language, 48 fps) are described in
`references/techniques.md`; read `references/lessons.md` before a full song.
