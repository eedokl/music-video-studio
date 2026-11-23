# Long takes with movement (`"takes": "long"`)

One take = one place = two to four sung lines, 6-9 s in one clip; she walks, dances and gestures through the picture
and the camera travels. The default plan (one shot of 2-5 s per line, B-roll in between) stays as it is.

Where it comes from: a reference music video with takes of 7.3 s on average was analysed frame by frame and rebuilt
shot for shot with the local models on the same song (2026-11-23, 32 shots, 116 clips). What follows is what held
there. Movement numbers are from ai-video `film_motion.py`.

## Switch it on

```
uv run "$S/plan.py" <proj> --takes long        # writes project.json "takes": "long"
```
- plan.py joins sung lines to takes of 6-8.9 s (cuts stay on line starts), every sung take is `lipsync` with engine
  `ltx`, no S2V; each take gets a framing from the knees up or closer, a move and the camera that goes with it
  (`claudia.LONG_MOVES`). Instrumental gaps stay B-roll.
- jobs.py renders LTX clips of such a project at **1024x576 with up to 217 frames** (9 s) instead of 121 frames at
  1280x704. A shot longer than one clip covers gets a hint; the cut then holds the last frame.
- pick.py takes, of the takes whose lip score is within 0.12 of the best, the one that moves most
  (`"pick_by": "lips"` = by score only, `"pick_by": "motion"` forces it on a short-take project).
- Write the brief as always. A take over 9 s: split it at a line change, or `engine: infinitetalk` (keeps the start
  image, moves little).

Cost on the reference machine (RTX 5060 Ti 16 GB, 48 GB RAM): 80-165 s per clip of 6-9 s, 116 of 116 rendered.

## What held, what did not

| | held | did not |
|---|---|---|
| take length | 6-9 s, face stays the same person | over 9 s (untested; 217 frames is the limit tried) |
| body | walking toward the camera, dancing close to the lens, arms wide, pointing, turning | the force of a real dance: 20-60 % of the reference's movement in the most moving shots |
| camera | push-in from medium to close, tracking backward, dolly-in from far (as a timeline) | crash zoom (1 seed of 3, and she left the picture), crane pull-back, whip pan |
| extras | a procession in step, cups lifted together, a crowd streaming past (say that they walk), a group dancing the same moves | faces of extras in wide shots |
| world | a city folding upward, light beams, a glowing ring in her hands | - |
| start image | from the knees up or closer; "medium wide shot, she is seen from head to knees and takes up only the middle third of the picture" gives a real wide start | "wide shot" / "full shot" alone: Qwen pulls in to the face |

Over the whole film the rebuild reached a movement median of 7.5 against 13.7 for the reference; lips measured the
same on both films in three shots where both faces are large (r 0.20-0.27 against 0.23-0.26). So the gap of the
local models is movement - camera and crowd above all - not picture or lips.

## Lip scores of long takes

pick.py scores of 6-9 s takes with a camera move lie lower than those of short takes (median 0.16 in the rebuild,
0.26-0.39 in earlier films) although the mouths follow the words by eye and the reference itself measures no
higher. Do not render more seeds because of a low score alone: twelve more seeds of three such takes all stayed
between -0.37 and +0.09. Look at the mouth on the word starts instead.

## More happening in a take (`timeline`)

A take gains from two or three things happening one after the other - she flips her jacket open, points back at
the group, looks over her shoulder. That is the shot key `timeline` (section 3 of SKILL.md), with a camera move in
it. It does not make her walk faster and it costs lip score when an action turns her away from the lens; use it
where a take should be richer, not everywhere.

## Slow motion: the shot key `"speed"`

Long LTX takes often read as slow motion: a walk measured 1.38 steps per second where a person walks 1.7-2.0.
- **Prompt words do not help.** "natural real-time speed, brisk steps" plus "slow motion" in the negative prompt:
  1.03 steps per second, not faster.
- **`"speed": 1.18` on the shot does**: the vocals are slowed to 1/1.18 of their tempo before the render and the cut
  shows the clip 1.18 times faster (clip json `"tempo"`). Lips are back in real time, the walk measured 1.57 steps
  per second, lip scores stayed about the same.
- **Decide shot by shot.** The user judged one of three test takes unnatural at 1.18 (a runway walk); hair and cloth
  speed up too. Slow motion is right for some takes - leave those at 1.
- A faster take is a shorter take: one clip covers 8.9 s at speed 1, 7.6 s at 1.18, 6.7 s at 1.33. jobs.py says so
  when a shot no longer fits. Range 1-1.5; only 1.18 was rendered.
- The step count comes from the head bobbing while she walks; it only works when the face is large and she is not
  dancing or turning.

## Tricks from the rebuild

- **A mirror**: "we see her in the mirror" put her into the room as well. Describe a wall-mounted screen with a
  frame that shows her and say "she is only on the screen, nobody else is in the room" (a cinema screen worked the
  same way).
- **A shot from behind**: with her face references Qwen turns her to the camera every time. Make it a `broll` shot
  that describes her from behind ("back view of a woman with a glossy black blunt bob in ...") - no face, no
  reference needed.
- **A take that was re-planned needs its start image re-picked** before the clips run (`pick.py start`), or the
  clips stand on the old picture.
- **Wider start, less measured movement**: a figure that fills a third of the picture moves fewer pixels than a
  close one. Compare shots of the same framing.
