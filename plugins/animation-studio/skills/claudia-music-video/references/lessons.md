# Lessons from Europe 2031 (studio, V1 -> V2) and Europe 2031 - Live

| rule | why (what happened) |
|---|---|
| Never "young" in a prompt; write "28-year-old" / "late twenties" | image models drift her teenage |
| Identity text unchanged in every prompt; streak mentioned once | rewording or repeating gave two streaks |
| Mic: "single thin beige headset microphone, boom along her right cheek"; mic negatives always | "thin headset microphone" alone changed mic count, colour and side between clips; one S2V clip gave her a handheld mic (rejected) |
| Check start images for TWO microphones (canon.py mic test) | Qwen-Edit drew a boom on both cheeks in half of the variants despite the negatives (Europe 2031 V2 start images 4/7/27/40, plugin test 2 of 4) |
| Repair a two-mic start image by retouching the WRONG boom only (mask + OpenCV fill + FLUX refine on the mask), Qwen-Edit only as second try | the reference V5 repair (Qwen-Edit "change only the microphone" on the whole image) still left two mics on live start 17; the retouch changes only the masked pixels (face, streak, correct mic stay identical); clean when the boom lies on skin (2/6 test images), a visible patch where it crossed the hair edge or a 3/4 jaw - so every repair is checked by eye (mic_repair test 2026-11-14) |
| Mic repair is opt-in; a failed mic check = more frontal start variants | lgtm_nc: head turned to the image left put the boom on the visible wrong cheek in 19 of 38 shots; of 6 repaired images 3 kept a grey patch or a boom rest, one lost the mic |
| Two references for close/medium start images (face + streak close-up), one for wide | single reference produced the double streak; the close-up fixed it |
| LTX positive prompt never "no text"; text/letters/logos only in the negative prompt | V1 moving clips 01/06/11 painted garbled letters; re-rendered clean with text only negative |
| Every video prompt has ONE light sentence matching its start image | clip 21 jumped to another scene without one |
| Screens and projections: "no person / no face on the screen" in the negative | live clip 28 turned a projection into a face - Christian would no longer be anonymous |
| LTX seeds vary a lot: 2 seeds per sung shot, 4 for weak ones; pick by measured lip score | same shot ranged from r 0.10 to 0.58 across seeds |
| Reject clips whose mouth stays closed (range < 0.1) | shot 34 V1: mouth practically shut (range 0.005) |
| Apply the measured lag: lag > 0 = mouth late, show dt = +lag/24 later (only when it gains >= 0.08) | V2 shots 35/52/57 gained 0.15-0.5 with +3 frames |
| LTX clips start 0.25 s before the shot; the picture is placed 1 frame later | LTX starts sluggishly from the still; decoded picture ~50 ms early |
| S2V only for single expressive moments < 4.7 s | S2V clips 7 and 49 were expressive but off the words (r ~ 0); long runs drift to profile |
| Moving stills (LTX on the instrumental) instead of Ken Burns | V1 was 48 % stills with parallax - too static; V2 had 1 still left |
| Instrumental from Demucs (or a stem mix), not song minus vocal stems | mastered song != sum of stems: subtraction keeps vocal residue -> LTX makes people sing |
| Loud choruses: measure against Rhubarb AND loudness (`--curve mix`) | separated vocals carry choir/bleed; Rhubarb alone gave negative r for good lips |
| From behind, the streak is on the image right | live start images 36/66 had it on the wrong side |
| Label the film as AI-generated; credit "Claudia by anabology" | LTX licence; plugin rule; Claudia's licence asks for it |
| ComfyUI that ran for days: flush (`/free`) before every phase, retry once | 38 GB private memory -> `HostBuffer.read_file_slice failed` |
| B-roll FLUX stills: check for invented lettering on screens/boards | FLUX ignores "no text" now and then |
| Crowds: LTX img_compression 42 + "A cinematic scene of a rowdy, packed concert audience going wild." (`"recipe": "crowd"`) | plain prompts froze the crowd (motion 0.1-0.9, 2 of 3 frozen); the recipe x11 motion |
| Reject clips with a hidden scene cut or a frozen stretch (pick.py, motion_check) | live V2/V4: LTX jumped to another scene or stopped moving in several takes that measured fine on lips |
| Level every vocal input (-16 dBFS sung RMS, peaks -1 dBFS, ramps); start the window in a silence | live V2 onwards; quiet inputs gave tame mouths |
| Long sung passages: one chained InfiniteTalk take instead of several cuts | live V3 bridge 12.7 s, no seams; lip score like the reference |
| Typography only in code (typo.py), never by a model | models garble letters; stamps must land on the sung word |
| S2V re-adds a second mic between frames even from a one-mic start image; check the whole clip by eye | Europe 2031 re-shoot shot 46 |
| Real-ESRGAN smooths freckles | upscale test on an S2V close-up |
| Profile shots are not measurable (no face found) | live shot 14 - judge by eye |

## Lessons from Das Warum (2026-11-20: another lead, Oliver, with Claudia as a guest; 100 shots, one night run)

| rule | why (what happened) |
|---|---|
| Another character = project.json `characters` + shot `who`; never run Claudia's canon check or mic repair on him | the night-run hook "repaired" four start images of the male lead: headset and orange streak painted onto him |
| A person of the film is never B-roll | FLUX has no reference image: "a man with a black headband and a dog" came out as a stranger in s85 and s98; as `claudia_moving` with `who` it was him |
| "no people" in a B-roll subject is not enough for the moving clip | LTX walked a man with a printed T-shirt into the empty field of s02; people now go into the negative prompt of such clips |
| Do not describe hair or pose through a hand ("pushed back by hand", "runs a hand through his hair") | Qwen drew the hand in the hair in a third of the sung shots - the user noticed the repetition |
| No "raises his eyebrows" in a start image | wide-open staring eyes in the first frames (s05); "a relaxed face, a small smile" fixed it |
| Laptops and phones grow brand logos; write "plain unbranded" or use paper, folders, tools | an apple logo on three of four laptops (s34, s42, s48) |
| Say where people sit ("on chairs along the two long sides of the table, the head of the table empty") | "five colleagues at a meeting table" put one of them inside the table (s48) |
| A look back over the shoulder: "only the backs of their heads" gave a natural profile glance; asking for the glance turned the other person to the camera | s98, four start images |
| A changed prompt must make a new file | the old file counted as "done" (file name only): rewritten shots changed nothing until the files were moved away by hand - hence the job fingerprints |
| More takes = clips from every start image variant (`--all-starts`) | the user asked for "one more version" of seven shots; pinning each variant by hand took a run per variant |
| "Frozen" must be measured against the clip's own motion | the fixed threshold called 71 of 210 clips frozen (calm fields, static camera) and put stills into the cut; the user took the moving clip back in 31 shots. Relative rule: 17, among them the one clip the user called frozen at its start |
| Long lyric lines shrink to fit in every style | 70 letters in "caps" ran out of the picture on the left |
| Check project.json before the night run | a wrong "title" form stopped the cut after 4.5 h of rendering; `jobs.py` runs the check now |

Weak spots that stayed (no model solved them): lips closing on short p/b/m; fast spoken lines with plosives
(LTX r ~ 0 there; HuMo 1.7B / MiniMax were better but rejected for other reasons).

- **Plain vs timeline prompt (A/B test 2026-11-15, Europe 2031 live, 8 shots x 2 seeds, same seeds/images/audio):**
  metrics equal (lip 0.198 vs 0.206, motion 4.39 vs 4.24). By eye the timeline prompt won the multi-action shots
  (gesture list, chorus head bob + arms, "Hey" fist + walk); the plain prompt won close-ups, spoken lines, the quiet
  bridge and the run + jump (weak in all takes). Hence: plain by default, `timeline` only for multi-action shots,
  rendered mixed (A on odd, B on even seeds).

## A live film through many places ("Die bittere Lektion - Ein Haus, eine Nacht", 2026-11: 53 shots, 88 takes)

Another lead (Oliver, sings) and Claudia as a silent part; seven places in one house, one night run.

| rule | why (what happened) |
|---|---|
| People who sit in one room for the whole film look static; change the places and show the ways between them | the first live version (a lecture hall, cut against the graphics film) was rejected: "too static"; the house from the cellar to the garden was accepted |
| Another character: "medium shot from the waist up" with the face named as lit, never "medium wide shot" | c05 and f05: all four start images showed a slimmer stranger - the face was too small for the reference; the closer framing was him in every variant |
| The video model cannot handle things (hand over, turn a page, close a laptop, reach for something): show the state in the start image, the clip only looks | an apple changed hands and doubled, a star flew off; shots with "she already holds the apple" and a glance were clean |
| Clothes never "creased" / "crumpled" | the shirt got holes; "the collar open and the sleeves pushed up unevenly" gave the tired look |
| Two people in one picture: the lead from behind or over the shoulder | his face came out slimmer in every frontal two-shot (e08 stayed that way) |
| Small things on a person: "the small orange hair clip stays fixed in her hair, nothing floats", the head still | the clip drifted through the picture when she turned her head |
| A silent part's start pose already is her look (mouth closed, kind) | a look that had to develop in the clip turned stern or opened the mouth |
| Garbled letters in a clean prompt: another seed (shot `"seed"`), not a longer prompt | e07 painted "GJICEST" on a model railway; "no text" added to the prompt was refused by `jobs.py` (rightly), seed 8107 was clean |
| Measure the face of another character's start images (`face_id.py`, config `face_id_model`) | the four strangers of c05 / f05 scored 0.22-0.26 against his references, every picture that showed him 0.47-0.76; two-shots score lower (0.27-0.49) - a hint there, not a verdict |
| Check every take on 6 frames, not 3 (`sheets.py --frames 6`) | lettering, a fade to black at the end and a camera push-in lay between start, middle and end |
| Re-pick single shots with `pick.py clips --only c05,f05` | measuring all 88 takes again for two new shots took minutes |

## Code cut (Europe 2031 in the Y2Y2R method, 2026-11)

- **Frontal start images for sung shots.** Three-quarter images grew a second microphone when she turned to the lens
  (both seeds); frontal ones never did in 66 takes.
- **Check the microphone cheek in every start image**: the second seed often mirrored it.
- **One sung take in two is usable** (closed mouth, light drifting from red to white, crash zoom in the first second,
  leaving the scene at the end) - two seeds per line were enough for every line.
- **LTX turns medium shots into close-ups by itself**, so the film gets more close-ups than planned and code jump-ins
  stay small (8-12 %).
- **Pace is a choice per song**: the first cut (one picture per beat in the chorus, a cut inside almost every take)
  was "a bit too fast" for the user; `calm` is the default (the user's choice after seeing all three).

## Overlays on a finished live film ("Die bittere Lektion - Ein Haus, eine Nacht", 2026-11)

A film of 53 live shots got a second version with small code pieces only (counters, a struck list, stamps, a check
on the key press, notes flying off a wall, a calendar sheet, an iris out). What the user said, in order:

- **"Keep everything, only add overlays."** The first attempt was built on an older cut of the same song in another
  project folder (graphics and live in turns), so it looked as if scenes had been swapped. Find the current film
  first (`last_render.json`, the newest file the user names), and build a variant as a new file with its own
  work folder - never over the running cut.
- **Dust over the faces had to go** - behind people or not at all (ai-video `near_masks.py`, depth masks).
- **Show the word that is sung**: a sentence being translated on "Uebersetzen", a picture with a detection box on
  "Sehen-Lernen". Pieces that illustrate the lyric were asked for; decoration was not.
- **Notes fly behind the singer**, not in front (matte mask for that one shot).
- **A stamp that stands half a second is not seen**; it was held over the cut for about 2.8 s.
- **A quote belongs on the closing card** (5 s); its two-second flash earlier in the film was removed.
- **Iris out on the last picture**, like the wink ending of an earlier film - the user asked for the known ending
  by pointing at that film.
- Takes are shot with a static camera (the video model does not hold camera moves); the slow push-in and the beat
  pulse come from the cut (`cam`, world `pulse`), and the lyrics are drawn after them so that they stand still.

## One shot on a music hit (title sting "Moneypenny will return", 2026-11)

A single 8.5 s LTX shot from a three-quarter start image (she aims a pistol off-screen, then swings it to the
camera on the hit), 8 takes. What drifted, and what the user chose:

- **The streak moves to the middle of the bangs when she turns to the lens.** In all 4 takes that ended
  frontal with a sharp face; "the single orange streak stays at the side of her bangs" in the prompt did not
  prevent it. It stayed at the side only in a take where her face was out of focus. If the streak matters,
  start frontal or cut before the turn.
- **A dark prop takes the colour of the key light.** The black pistol turned gold under the warm amber key in
  5 of 8 takes; "matte black" plus "golden gun, gold pistol, brass" in the negative prompt kept it dark in one
  of the three takes that had both.
- **"Straight into the camera lens" pulls the focus onto the prop**: the muzzle was sharp and her face soft for
  the rest of the shot. "Points straight into the camera" kept the face sharp with the gun beside it.
- **A black background fills up over 9 s** (a warm glow, lamps, once a whole room) in 4 of 8 takes; "black
  empty background with no lights in it" plus "background lights, bokeh lights, lamps" negative held in one of
  three.
- **A second star clip** appeared once in a tight close-up the model pushed into by itself.
- **The user kept the take with the readable face** (gold pistol, streak in the middle) over the take that had
  streak, prop colour and background right but the focus on the gun. Offer both kinds; do not sort takes by
  canon checks alone.
- Start-image note: Qwen-Edit kept the canon in all three variants for this pose (tuxedo, three-quarter view,
  pure black background, one amber key from the right); the clip must be left out of the scope bars' reach
  (film-finish `sting.py --fit`).

## Review rounds on a finished cut ("El-Ge-Te-Em", 2026-11: 81 shots, three comment rounds by the user)

**Before the takes**

- **Look at the start images before any clip is rendered.** The first night run made 378 jobs; 19 of 38 Claudia
  shots had the headset on the wrong cheek and the clips of all of them were wasted. Run the image phases alone
  (`night_run.py jobs.json --phases flux,qwen_edit`), show the sheets, then run the rest. The user asked for
  exactly this order.
- **The headset in two steps holds the side better than one prompt.** Start image without any microphone (the
  reference images edited bare first), then an add-only edit of that picture. What decided the side was the
  wording: "her right cheek (left side of the image)" put it on the wrong side in 20 of 20 edits; naming ONLY
  the picture side ("on the LEFT side of the picture ... the cheek on the right side of the picture, next to
  the star clip, stays bare") was right in 9 of 10.
- **Add it on the face only, never by an edit of the whole picture.** The add-only edit re-renders everything and
  invents a second microphone in the scene - a desk microphone, one lying on the table, a boom in the air - in
  about 10 of 24 pictures (overlooked at first because only the faces were compared). Editing a square around the
  head and pasting only the face area back (ai-video `face_edit.py`): 24 of 24 with one small headset on the
  right side, also with the head turned, no seam, the rest of the picture untouched. This is project.json
  `"mic": "added"` (opt-in since 0.21.0). Measures that did NOT work for checking: the difference picture between
  the bare and the edited image (the whole picture changes, grain included) and a line measure for cables below
  the chin (jacket collars score like cables) - cables are found by looking.
- **A small headset has to be asked for in sizes**: "one hair-thin skin-coloured wire ... a capsule no bigger
  than a grain of rice" (the user found the default boom "really very big"). It costs accuracy - about 17 of 24
  on the right side - so make three seeds and pick by eye. Rejected: shrinking a placed microphone by a second
  edit (a second microphone every time) and giving the canon reference as a size model (it replaced her face).
- **Look for a cable.** In the bed scenes the model hung a cable from the ear down to the blanket; it runs
  through the whole take and cannot be retouched out of a clip. Fix the start image (remove headset and cable,
  add the small one) and render new takes. In blue night light the capsule takes the orange of the streak -
  "beige" in the prompt plus "orange capsule" in the negative brought back two microphones or the cable; the
  orange one was kept.
- **A reference image can carry the fault**: the second Claudia reference (close-up for streak and clip) shows
  the boom on the picture's right. Check the references against the canon before blaming the prompt.

**Takes**

- **LTX holds the start image at the beginning of a take** - up to 18 frames, then the movement starts at once.
  With the 0.25 s lead-in 6 to 11 of these frames are in the film ("it stands still for a moment, then she
  moves"). Of 45 chosen lip-sync takes seven had 5 to 11 standing frames in the film. What helped, best first:
  - new takes with a longer lead-in (+16 frames: `audio.from` earlier, `frames` + 16, meta `song_start` /
    `lead_in` adjusted), so that the standing frames fall into the skipped lead-in (22 frames instead of 6);
  - a silent clip (`claudia_moving`, B-roll) simply starts later in the take: selection `"lag": 10`;
  - a sung take: the cut moves later by the standing frames, if the take BEFORE it is long enough (a silent one
    may be slowed a little); the lips stay where they are because clips are placed by `song_start`;
  - a transition on the cut. A white flash (6 frames) was not seen and left 4-5 standing frames visible ("I
    still see the stand and no flash"); `zoom_through` over 12 frames was chosen - the incoming picture settles,
    so the standing frames move.
  One user comment to remember: at one cut the short stand was "almost a nice effect" - ask before fixing all.
- **"She sings quietly" makes her mumble.** Three takes with it: mouth range 0.11-0.14, score around 0. With
  "sings softly but articulates every syllable with a clearly moving mouth" and only the words that fall into
  the shot (shot key `sing`): 0.55, 0.33, 0.25.
- **Mood words against a moving mouth - tested, with a control.** Three shots, the same two seeds in every arm,
  longer lead-in in all of them, 20 takes: (0) prompt unchanged, (A) mood words out, (B) A + articulation + a
  sentence for the held last word, (C) B without "natural small head movements and breathing". What it showed:
  - The seed mattered more than any wording: one seed was good and one weak across all arms in two of three shots.
    Never judge a prompt change by one take, and keep a control arm - the longer lead-in alone moves the numbers.
  - Mood words can shut the mouth: "dryly, with a tired smile" - shut with one seed (range 0.07), moving with
    the other; without the words both moved. Where the mouth already moved, taking them out changed nothing.
  - The held-note sentence raised the opening on a 2 s note in both seeds (0.20 -> 0.29 -> 0.34 and 0.24 -> 0.27
    -> 0.30 from arm 0 to A to B); S2V reaches 0.52. Shot key `"hold_last": true` since 0.23.0.
  - Arm C made no difference: the fixed mouth sentence does not hold the mouth back.
- **Why an S2V take looks hectic**: 832x480 scaled up by 1.5, 16 fps repeated to 24, and a mouth that opens two to
  three times as far as in LTX takes (range 0.65-1.09 against 0.2-0.5). Fine on one long note, restless on fast
  words. Two of three such shots were better served by an LTX take of the same start image (lip score 0.32
  against 0.09; 0.21 against 0.31 but the calmer face was chosen).
- **The S2V assignment rests on word lengths, and those came from raw Whisper times.** One "held note of 1.2 s"
  lasted 0.71 s by the times from the lead stem. Check the held word against refined times before S2V is paid for.
- **LTX does not sing a stacked gang chant that opens a line.** "El-Ge-Te-Em - und Freitag fünf bin": ten takes,
  four prompts (also a timed one: "0.9-1.7s: she shouts ... with a wide open mouth"), two audio sources (the Demucs
  vocals and the Suno lead stem): the mouth stayed shut or frozen on the chant every time and moved on the solo
  words right after it. The same word sung mid-line ("Ich sag El-Ge-Te-Em") worked. The cause is not known - two
  explanations were tested and failed (backing vocals in the audio; no instruction). What worked: **cut the shot
  in two** and give the chant to the gang - a 0.8 s B-roll of colleagues shouting, driven by the backing-vocal stem
  as audio (kind ltx_lipsync on a group picture; it moved from the first frame, the instrumental-driven clip did
  not), then the singer from the next word on. Takes are placed by their own `song_start`, so a shot can be split
  at any time without a new take; only the section list changes.
- **Two takes of the same start image are not cut together** inside one line (the Claudia recipe: no jump cuts
  inside a scene) - a split needs a different picture for one half.
- **A take chosen on the takes page before it was rated is saved with lag 0.** Rate first (`pick.py clips --only
  <shot>`), or set the measured lag afterwards: two of three such picks sat one frame off (0.20 -> 0.33).
  After a shot is split, the lag has to be measured over the part that is still shown (-3 -> -1 here).
- **The takes page reads the shot list when it starts.** After adding or splitting a shot, restart it.
- **More takes without disturbing the film**: `jobs.py` with a changed `action` or times re-fingerprints the
  shot, and the night run moves the existing takes (also the one the user chose) to `replaced/`. For a few extra
  takes write a second job file from the existing entries (new seed, new output name, the prompt changed in
  place) and run `night_run.py` on that file.
- **A new take is not automatically the better one**: for one shot all three new takes moved from the first
  frame but measured worse on the lips (around 0 against 0.19) - the old take stayed and the cut was changed.
- **The lip score says little where the lead voice pauses.** In a shot with 0.6 s of singing and 2 s of pause the
  take that kept mouthing scored higher (0.19) than the one that closed the mouth (-0.03); the user chose the
  second. Judge such shots by eye.
- **The takes page saves a choice for every shot.** After the user has been on it, all shots count as "by hand",
  and new takes are rated but never chosen. Enter the new take yourself for the shots the user asked to redo,
  keep a copy of selection.json first, and say which shots you changed.
- **Liquids need a source and a target in the prompt.** "A last drop falls into the empty jug" made water drip
  from a switch on the front panel. Naming the outlet, the path and the landing place, plus "nothing drips from
  the buttons ..." and negatives, gave one realistic take of five (a hand reached in once, the panel leaked
  again once, two showed almost nothing).

**Text**

- **Writing on a prop is added in code, and it must actually be added.** The sticky note of "... auf dem 'Finger
  weg' steht" was planned blank (image models cannot letter) and stayed blank in two cuts - the user noticed.
  The note is the only yellow area on a dark cabinet: find it per frame by colour, smooth the four corners over
  +-3 frames, warp the handwriting onto it and MULTIPLY it into the picture (grain and shading stay); write it a
  little before the words are sung so that it stands when they come.
- **Word times for shown lyrics come from an isolated lead voice.** `refine_timing.py` belongs to the lyric-video
  workflow and is not run by the Claudia pipeline: the lyrics ran on raw Whisper times and the user saw it
  ("the text is not well in sync"). On the Demucs track (lead and backing in one) the refinement halved the
  median error but could not see pauses that the backing vocals fill; two of three hand repairs made from that
  track were wrong. With the Suno lead stem: Whisper again on the stem, then `refine_timing.py` on the stem.
  Ask for the stems at the start of the project, not after the third cut.
- **Suno stems may be shifted against the song in use**: here by 38568 samples (0.8035 s; the song had been
  re-exported with silence at the start) and 8.9 dB louder. Correlate the fresh Suno song with the project's
  song at several places (a constant offset = the same recording) and shift the stems before using them.
- **A line that the film shows elsewhere gets no lyric**: the bot's sentences stand in its chat bubble, so their
  six lines are in `lyrics_skip`. The user asked for it the moment both were on screen.
- Tight lines in fast verses: see film-finish `overlays.py` (the line moves one row up; before that the last
  words of 26 of 51 lines stood under half a second or never appeared).

**Finish**

- **Film grain 5.5 looks gritty in the small mp4** (2x2-pixel grain, "35mm film look" in the prompts and the
  compression add up). The user chose 2.5 (`"finish": {"grain": 2.5}`); the full file shrank from 396 to 175 MB.
  The second film at 5.5 ("Du bist die Maschine") read as "verrauscht" too, so 2.5 is the default since 0.25.1;
  set `"finish": {"grain": 5.5}` only for an explicitly gritty look.
- **Cursive lyrics without the box** were chosen over the caps default for this film: `lyrics_style` with
  `"base": "script"`, a cursive font, `"box": null`, size 42 - legible on bright and dark shots because of the
  dark edge and the darker band at the bottom.
- **Collect, then build.** The user wrote a round of comments and wanted each one answered - what is seen, what
  it is measured as, what could be done - before anything was rendered. Measuring first changed several fixes
  (a standing start turned out to be a line with a pause; a "bad" take was the best by the numbers).

## Lessons from a likeness test of another lead (2026-11-23: one man, 8 scenes x 2 seeds, 4-step Qwen-Image-Edit 2511)

Face similarity (ArcFace) of every start image against 8 photos of him that no variant had seen; his own photos reach
0.79 among each other.

| references | mean | worst picture | seen |
|---|---|---|---|
| two photos (frontal with a cap, three-quarter with a hand at the head and a jacket logo) | 0.65 | 0.48 | cap and logo in many scenes |
| two clean single photos, bare-headed | 0.68 | 0.49 | the red t-shirt of one photo in several scenes; two men side by side until the prompt said "exactly ONE man" |
| **views sheet (front, three-quarter, profile) + close-up of the face** | **0.69** | **0.53** | no cap, no logo; best on small faces and on the singing shot |
| own identity LoRA (musubi-tuner, 840 steps, 768 px), strength 1.0 / 0.6 | 0.63 / 0.65 | 0.52 / 0.47 | at 1.0 flat colours and soft faces |
| full model instead of the 4-step one (20 steps, CFG 4, 5 min a picture) | 0.62 | 0.50 | not closer, ten times slower |

- **What a reference shows travels into every shot** - cap, logo, shirt colour, a hand at the head. Cut references
  to what must stay (head and hair) or build a sheet from clean photos; character key `"sheet": true`.
- **An identity LoRA did not beat the references** on this model and machine (six hours of training). Not tried:
  training at 1024 px with about 3000 steps, or without control images.
- **With the plugin's own wording** (`"sheet": true`, 8 single shots, 4 two-shots with Claudia as a guest): 0.71
  mean, worst 0.65, one man in every picture, exactly two people in every two-shot.
- **Claudia, same test (8 variants x 12 pictures, canon.py):** her face is not the problem - all variants made from
  the three stills in use lie at 0.52-0.56 against them. One boom on the correct cheek: the two Europe 2031
  references 5 of 12 (two booms in 7), a sheet cut from her three stills 8 of 12, the official claudia.gallery face
  sheet (no microphone on it) 7 of 12 with the headset still as image 2 and 5 of 12 with the headset from the text
  alone. The official sheet gives the official face (0.77 against the sheet, 0.52-0.56 with the stills) and lays
  the streak as the sheet has it, from the middle of the bangs toward the image right - canon.py, which expects
  the image left, then calls 10-11 of 12 wrong. Which face and which streak side are canon is the user's decision;
  nothing was changed. 12 pictures a variant: hints, not proof.
- The sheet here was three snapshots of different days. Photos taken in one session (same light, plain wall, bare
  head, no logo) are untested and should do better.

## Lessons from rebuilding a reference video shot for shot (long takes)

A music video with 7.3 s takes and a lot of movement was rebuilt with Qwen-Image-Edit and LTX-2.3 on the same song
(32 shots, two rounds, about 4.5 h GPU). Details and tables: `long-takes.md`.
- **The gap to such a film is movement, not picture or lips**: about 22 of 32 pictures matched the idea in one pass,
  lips measured the same on both films, movement reached about half (median 7.5 against 13.7).
- **Compare by the same measure**: the first verdict "lips are the biggest gap" came from our own scores alone; the
  same measurement on the reference gave the same numbers. Measure the reference before judging against it.
- **Round two pays for framing and single effects** (wider starts, a folding city, the mirror, the back view), not
  for the amount of movement: three seeds and timeline prompts moved the most moving shots from 19-47 % to 29-62 %
  of the reference.
- **A planned change needs its start image picked again** before the clips run - three takes of a re-planned shot
  were rendered on the old picture.
- **Slow motion is steered by the sound, not by words** (shot key `"speed"`), and only shot by shot.
