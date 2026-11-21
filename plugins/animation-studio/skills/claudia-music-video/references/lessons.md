# Lessons from Europe 2031 (studio, V1 -> V2) and Europe 2031 - Live

| rule | why (what happened) |
|---|---|
| Never "young" in a prompt; write "28-year-old" / "late twenties" | image models drift her teenage |
| Identity text unchanged in every prompt; streak mentioned once | rewording or repeating gave two streaks |
| Mic: "single thin beige headset microphone, boom along her right cheek"; mic negatives always | "thin headset microphone" alone changed mic count, colour and side between clips; one S2V clip gave her a handheld mic (rejected) |
| Check start images for TWO microphones (canon.py mic test) | Qwen-Edit drew a boom on both cheeks in half of the variants despite the negatives (Europe 2031 V2 start images 4/7/27/40, plugin test 2 of 4) |
| Repair a two-mic start image by retouching the WRONG boom only (mask + OpenCV fill + FLUX refine on the mask), Qwen-Edit only as second try | the reference V5 repair (Qwen-Edit "change only the microphone" on the whole image) still left two mics on live start 17; the retouch changes only the masked pixels (face, streak, correct mic stay identical); clean when the boom lies on skin (2/6 test images), a visible patch where it crossed the hair edge or a 3/4 jaw - so every repair is checked by eye (mic_repair test 2026-11-14) |
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
