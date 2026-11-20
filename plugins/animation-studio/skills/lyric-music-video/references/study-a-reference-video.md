# Studying a reference video

*The steps that hold for any reference video (frames by seeking, sound first, what may be taken) are in
`skills/studio-core/references/reference-video.md` of this plugin; this file adds what lyric videos need.*

When the user names a video as a reference ("like this one", "replicate its scenes"), what you take from it depends
on how closely you look. A frame every 2 seconds shows *what* is on screen. It does not show how the lyric enters,
what moves with the beat or where text scrolls - on the first video studied this way the user had to send it back
twice for exactly these three things.

## 1. Three passes, coarse to fine

| Pass | Step | What it tells you |
|---|---|---|
| Overview | 2 s, whole video | the scene list by time, backgrounds, type, which lyric line each scene belongs to |
| Detail | 0.5 s on the busy scenes, larger tiles | the exact content of each scene (labels, numbers, order of appearance) |
| Motion | 0.05-0.2 s on one line of each kind (a verse line, a chorus line, a list, a transition) | entrances, what is highlighted while a word is sung, scrolling, cuts |

For the motion pass crop to the region you study (the lyric strip: the bottom quarter) so that 20 frames fit one
sheet at readable size.

## 2. Measure the beat instead of guessing it

Pulses of 1-2 % are invisible on contact sheets. Draw each frame to a small canvas (160 x 90) and compute numbers:

- **Whole-frame brightness and the width of the bright pixels** every 0.04 s over two seconds of a static title card:
  a pulse shows as a jump that decays (found: +4 % brightness, +1.5 % size every 0.70 s = the beat, in the choruses).
- **Change per frame in a 16 x 9 grid of blocks** every 0.05 s over a whole verse: list the times where the change
  jumps. Events one beat apart (0.70 s), half a beat apart (0.35 s) or continuous (a counter, a curve) stand out at
  once - this is how "one chess move per beat, the highlight every half beat, nothing pulsing in the verses" was found.
- Then look at the frames around three of those times, enlarged, to see *what* happened.

A video element that is paused and seeked gives exact frames; reading frames while it plays is throttled by the
browser (2 frames per second arrived instead of 30).

## 3. What to write down per scene

Time, lyric line, background, the elements in order of appearance, **what each one is timed to** (the sung word, the
beat, half beats, continuous), how the lyric is shown (position, entrance, what marks the current word, what happens
to sung words), the transition out. That last column - timed to what - is the one a coarse look leaves empty.

## 4. Mapping onto another song

A translated or re-recorded song has other line times, gaps and tempo. Map scene by lyric line, not by time; a scene
that lived in a pause the new song does not have (a quote between chorus and verse) moves to where there is room (a
long outro) - say so in the report. Use the new song's own beat grid.

## 5. What you may take

Scene ideas, structure, timing principles and the general look: rebuild everything in code. Do not take frames,
images or logos from the video; write on-screen text yourself (translate, do not transcribe long passages). Name the
original and its author in the credits and in the README, and tell the user that publishing a close re-staging is
their call (asking the author is the safe way).

## 6. Practical notes

- An ad may play first: the page then reports another duration - wait until the duration is the video's, or use the
  player's skip button.
- Long-running page scripts: start them without waiting and read the result later; a tool call that waits for 20
  seeks may return before they are done.
- Compare your render with the reference the same way: `render.py PROJECT clip --from A --to B --sheet` gives every
  frame of your version for the same stretch.
