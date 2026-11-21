# A 3D film on a song (music video with 3D figures)

The film runs on a finished song: every clip is a stretch of it, the figures sing its lines with lip sync and move
on its beat. Learned on the rap video "LGTM" (21 clips, 5,542 frames, three MCs + a robot, 3:51).

## The way

1. **Analyse the song** (song-analysis BLOCK.md): `new_project.py <film>/song --song song.wav --lyrics lyrics.txt`,
   then `analyze.py` – vocals separated, words timed (Whisper large-v3), beats and downbeats. Result:
   `<film>/song/analysis/song_sheet.json` and `vocals_lead.wav`.
2. `film3d.py new <film> --title ... --cast ...`, then `film3d.py song <film> --draft` → `song_plan.json` (a first
   clip list: cuts on downbeats between lyric lines) and `song_lines.txt` (every line with number and time).
3. **Write the plan** – this is the creative brief of a song film:
   - `"clips"`: one clip per idea of the song (a verse half, a hook half, a break), 8–15 s each, starting on the
     downbeat before its first line. Name them after what happens, not after the lyric.
   - `"who"`: who performs which line. Take it from the **section markers of the lyrics** ([Verse 1 – MC 1], [Hook
     – all]); nobody can hear which of three generated voices raps a line, and a wrong guess shows.
   - `"groups"`: `"all"` = the figures that sing the hook together.
   - `"show"`: sung → written. A song generator needs "El-Ge-Te-Em" to pronounce an abbreviation; the picture
     shows `LGTM`. Every text a scene takes from the song (`SG.line(n)["text"]`, word lists for stickers and
     lyrics) carries the written form; `SG.word(clip, "LGTM")` still finds the sung word.
4. `film3d.py song <film>` → `timing.json`, `speech/l<n>.wav` (the lead voice of each line, for Rhubarb),
   project.json `clips` / `lines` / `audio`, a scene module per new clip (template with `SG.sing` + `SG.groove`).
   **Read its notes**: a line whose first word the recognition put seconds too early (glued to the line before) is
   moved by itself; a line that starts while the voice is silent is reported with the second the voice is first
   heard – check it and write it into `"fix": {"<line>:<word>": seconds}`. Repeated chants ("LGTM! LGTM!") and
   outros over scratches are the usual victims; their end goes into `"end"`. Run `song` again after every change
   of the plan – it only re-cuts what changed.
5. Build the scenes on `stage_song` (stage-3d guide "A film on a song"). **No frame number is typed in**: `SG.f`,
   `SG.word`, `SG.beats`, `SG.bars` – after a timing fix or a moved cut the acting follows, and only the frames
   that look different are rendered again (timing.json is part of every clip's source key).

## Many clips, several authors

A four-minute song is 20 clips; written one after the other it takes a day, by several agents in parallel an hour.
What made that work, and what did not:

- **A shared module first** (`scenes/<film>.py`, imported by every clip): the cast as classes, the set as one
  function, the props that return (a banner, a chair, a sticker). Render a pose sheet of the cast and fix it before
  anybody writes a clip. Keep it in `scenes/` – modules there are part of every clip's source key, a module in
  the project root is not (a change to it re-renders nothing by itself).
- **One reference clip** written and polished by the coordinator (the first hook is a good one): it shows the
  camera language, the density of gags, how singing, groove and cuts are written. Agents copy its craft.
- **A brief** (`BRIEF.md`): the concept in five lines, each figure's body language, the running gags with plant and
  payoff, the light arc (mood per clip), per clip what happens on which line, the rules (texts, palette).
- **A continuity table in the brief – the part that was missing.** Clips written in parallel agree on the figures
  and disagree on the world: a window broken in one hook was whole in the next, the exit door stood on the right
  wall in three clips and on the left in a fourth, the wall clock jumped back five hours. Everything that changes
  during the film or has a place gets a row: *state per clip* (window: whole until c07, broken from c07 on),
  *places* (exit door: right wall, y = 1.2), *the clock per clip*, *where each figure stands at the end of a clip*
  (the next one starts there, or cuts to another angle on purpose). Better still, put it in code: the set function
  takes the clip name and builds the state (`office(S, clip=CLIP)` reads `STATE = {"window": "c07", ...}`).
- The coordinator **looks at every contact sheet** and at the cuts between neighbours (last tile of one clip beside
  the first of the next) – continuity faults only show there.

## Craft notes

- **Figures with a big head** (a robot with a monitor, a helmet, a hat): hands raised beside the head vanish
  behind it – the thumbs-up was invisible from the front. Check every pose the figure uses on its pose sheet; move
  the hand outward for that figure with `rest_over = {"point_up": {"handR": (x, y, z)}}` in its class. Headwear must
  leave the brows free (a cap sits on the back of the head): the brows carry the acting.
- **Glowing faces and screens**: an emission strength of about 2 reads as a lit screen under the "golden" and
  "dusk" moods; 5 burns out to white and loses the eyes. A coloured light that floods the room for a gag wants a
  quarter of what looks right in a still.
- **Scratches and stutters** ("du – du – du hast"): Rhubarb hears noise and the mouth stays shut or flaps. Key
  those mouths by hand on the stutter's beats (open – shut per hit) instead of `say()` for that line.
- **Groups singing**: three mouths on one vocal slice move alike – give each figure its own groove (`amp`,
  `half`), stagger gestures by 2–5 frames, and cut to one face per line in the hooks.
- **Expensive clips**: light shows in haze cost 2–3 times the frames of the office clips. `film3d.py status` says
  how long the missing frames take, from this project's own renders – tell the user before starting the film render.
