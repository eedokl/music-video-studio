# A dialogue of two people (spoken film)

How the sketch "Autopilot" (2026-11, two people in a car, 43 s) got from five rejected looks to a film the user called
"way better". The order matters more than any single step.

## 1 Sound first - get it approved before the first video clip

Every change of the sound moves all times and costs new clips (here ~45 min per round).

- Speak the lines with the voice block. A plain clone of a neutral reference sounded "choppy, badly stressed,
  artificial" to the user. What helped: a **direction per line** (item key `"direction"`, English: "Bone-dry deadpan
  sarcasm, clear stress on 'seit zwanzig Minuten'") - Qwen VoiceDesign then speaks the line itself.
- **Short gaps**: 0.6-0.8 s between two turns sounded read aloud; ~0.25 s reads as a comeback. Keep only the pauses
  the script asks for.
- A directed voice wanders from line to line. `speak()` reports lines whose pitch falls out of the character's range:
  one at 154 Hz among 168-198 Hz was taken for the sat-nav by the user. Speak such a line together with the sentence
  before it as ONE item and split it at the pause.
- Send the user a listening version (voices + background) and wait for the yes. Offer two or three versions.
- One line can be replaced later without touching the rest: build the new track, then splice it onto the approved
  one at the start of that line (short cross-fade) - the samples before it stay identical, only the clips from that
  line on are rendered again.
- ElevenLabs can play a whole exchange in one take (`voice.py dialogue`, cloud, ask first) - the voices are other
  voices then, and the pauses are the model's.

## 2 One master picture, everything else is a crop of it

`ai-video/scripts/master_crops.py` (project key `"master"`): make ONE picture of both people in their places, cut the
singles out of it, change only mouth and gaze inside a crop. Start images made shot by shot gave a passenger behind a
steering wheel and on the back seat.

## 3 A place where nothing has to move

A driving car failed twice: the landscape behind the windows was wrong or frozen. The car now stands in a traffic jam.
Prefer a place whose background may stand still (a parked car, a table, a waiting room, a cockpit in space).

## 4 Every exchange is one clip that starts on the two-shot

`scripts/dialogue_clips.py` (project key `"dialogue"`): LTX-2.5 opens on the two-shot with speaker 1 and cuts to
speaker 2, or stays on the two-shot while they speak one after the other. All 21 clips rendered this way kept the
people, the car and the car behind it; single takes per speaker never agreed.

- Two sections share one clip; each takes its part by the clip's `song_start`. The film plays the clip through, the
  model's own cut stays - it sat 0.05-0.5 s before the second speaker's section in every take.
- At most 8 s per clip (193 frames). A longer exchange: move the last sentence into the next clip.
- `plan` prints the prompts, `render` makes two seeds per clip (~5 min each), `check` measures the cut and writes a
  strip per take, `select A=8 B=7` puts the takes into selection.json.
- **Dissolves**: 4 of the first 9 takes with a cut faded (one through black) instead of cutting; none of the next 8.
  `check` names them, `select --harden` replaces the blend by a hard cut (a few frames stand still on each side).
- **A voice from off** (sat-nav, radio, narrator): list its times in `"dialogue.off"`. They are silenced in the
  lip-sync audio, and a clip that opens on them says "everybody listens, nobody speaks" - the mouths stayed closed.
- Look at every take as a strip: seats, mouths, what is outside. The measures did not show a wrong seat.

## 5 When a single shot is still right

A single person in a calm framing with a background that stands still: when LTX-2.3 does not move the mouth (a start
image that smiles with closed lips, or one with the mouth wide open - it then held the mouth half open and still in 4
of 7 takes), use InfiniteTalk for that shot (`"engine": "infinitetalk"`). Its frozen background is right there and
wrong as soon as something behind the person should move.

## What it costs (RTX 5060 Ti 16 GB)

Voices ~1 min per version of 11 lines; master + crops + edits ~15 min; 5 clips x 2 seeds ~45 min; the cut ~3 min.
