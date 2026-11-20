# Studio version vs live version

Both use the same pipeline; `project.json "version"` changes the defaults (looks, wardrobe options, framings) and
the brief.

## studio (story video)

Claudia in real places that come from the lyrics, B-roll pictures of the song's images. Reference: Europe 2031
(Brussels offices, rooftop in a storm, server hall, archive, airport gate, glass towers; 62 shots, 3:17).
- Looks: `grey_morning`, `night`, `studio`, `storm`, `golden`, `quiet` - or the brief's own looks per place.
- B-roll: one concrete image per line (a projector showing empty charts, a driverless car into the sun ...), people
  only anonymous / from behind / as silhouettes. Typo cards (stamps, newsflash, departure board) can be drawn in code
  on top - never let a model write them.
- Ideas come from the lyric's meaning and its jokes; keep a visual thread (one recurring object or colour).

## live (concert video)

Claudia performing the song on a concert stage. Reference: Europe 2031 - Live (69 shots, 3:40): 34 LTX lip-sync shots
(close, medium, from the side, from below out of the audience), 5 S2V for held notes and vocalises, 5 Claudia shots
without singing (from behind toward the audience, dancing wide shots), 25 B-roll (light rig, audience from behind
with hands and phone lights, drummer silhouette, guitar/keyboard hands, confetti, the studio film's motifs on the LED
screen), typo on the screen.
- Looks per song part: `intro`, `verse`, `chorus`, `spoken`, `bridge`, `finale` (plan.py maps [Verse]/[Chorus]/... markers).
- The stage text (`STAGE` in claudia.py) is added to every start image; wardrobe gets pushed-up sleeves etc.
- Shots from behind: the streak must be on the image RIGHT (pick.py checks that side when the framing says "from behind").
- Screens: negative "face on a screen, person on the screen"; audience hands are weak in all models - keep them
  small, backlit or out of focus.
- Live versions of a song often differ from the lyrics sheet (extra lines, vocalises): run song-analysis on the live
  audio and correct lyrics.txt before planning.

## Cut in code (any version)

`code_film.py` cuts a studio or live project a second way: cut as data on the beat grid, text and graphics drawn in
code, B-roll as stills moved in code. Reference: Europe 2031 in this method (3:17, 37 sung takes, 72 plates; 154 parts
at pace `fast`, 115 at `medium`, 89 at `calm`; about 2.5 h GPU for stills and takes, 3 min to render the film).
Choose the pace for the song. See film-finish `references/code-cut.md`.

## Hand-offs

- V1/V2 comparison and review: video-review skill (films + review.json + selection.json + picks.log).
- A cartoon version of the same song: animated-music-video skill; a pure lyric video: lyric-music-video.
