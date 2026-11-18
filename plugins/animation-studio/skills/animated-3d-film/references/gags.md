# Gags in the deadpan spoof style (Zucker–Abrahams–Zucker school)

For films where the user asks for gags "pushed to the extreme", a spoof, slapstick in a serious frame or
"Naked Gun / Airplane-style" jokes. These are craft rules and gag *types* - invent the actual gags for the film's
own story and characters; never copy scenes, lines or characters of existing films.

## The rules of the style
- **Everyone plays it straight.** Nobody in the scene knows it is funny. No winks, no laughing at their own joke,
  no "comedy" faces: neutral or earnest moods (`"neutral"`, `"focus"`, `"stern"`), normal speed. The absurd thing
  happens, the characters treat it as normal and go on. The deadpan is the joke's amplifier.
- **Density.** A gag every few seconds, in three layers at once: the foreground action, a background gag
  (something odd going on behind, never commented on) and a sound or sign gag. A viewer should find new jokes
  on the second watch.
- **Commit fully, then go one step further.** Take the idea literally and keep going past the point where it
  should stop (the escalation is the gag: the coffee keeps being poured after the cup is full ... the table ...
  the floor).
- **Running gags pay off three times:** plant it (quietly, early), repeat it with a variation, pay it off big
  near the end - ideally at the worst possible moment. One or two per film, not more.
- **Serious frame.** The style needs a genre it parodies (a heist film, a disaster film, a cop show, a nature
  documentary, a corporate training video): its music, its lighting, its camera language played 100 % straight.
  The cinematic look of stage-3d is ideal for this - keep it, do not make the film look "funny".
- **Timing:** hold a beat after the absurd moment (8-16 frames of nothing), then cut. Do not linger, do not
  explain.

## Gag types that work with 3D figures on a stage
| type | how it works | stage-3d means |
|---|---|---|
| Literal metaphor | an idiom said in the dialogue happens physically ("let's clear the table" - stagehands carry the whole table away mid-sentence) | `stage_theatre.Change`, `stagehand().walk(carry=True)` |
| Background gag | behind the serious talk something escalates silently (a plant slowly grows to the ceiling, a figure keeps trying to get through a door) | a second figure / prop on its own keys in the back; shallow depth of field keeps the front clear |
| Theatre reveal | the "real" location is a set: a wall falls over, the window is a painted flat carried off, stagehands walk through the shot | `Change.change(...)`, `piece(..., "fly")`, a crew crossing during a serious moment |
| Wrong scale | an object is far too big or small and nobody notices (a giant keyboard, a tiny phone) | props scaled in the scene, played straight |
| Camera gag | the camera itself becomes a physical thing: a character bumps into it, the lens fogs up, a figure walks "behind" the frame edge and appears on the other side | `S.shot` moves, `cam.handheld`, a figure keyed past the frame edge |
| Sign gag | a sign, label or screen text says something absurdly literal or contradicts the scene | `stage_core.text`, image materials on screens |
| Sound gag | the sound does not match the action (a tiny tap makes a huge crash, a door creaks like a ship) | voice / sfx blocks; mix in the film's sound track |
| Overreaction / underreaction | a trivial thing gets a dramatic reaction (light change, music sting, slow zoom); a disaster gets none | `follow_spot`, `dim`, `light_show` for the trivial thing; `take()` held deadpan |
| Repetition with a twist | the same action three times, the third breaks the pattern | key the same pose block three times, change the third |
| Fourth wall | a character notices the light, the stagehands, the editing ("did someone cut?") - once per film at most | a glance into the lens (`look` at the camera position) |

## Working method
1. In the creative brief list the gags per clip in three columns: foreground / background / sound-or-sign, plus
   the running gags with their plant - repeat - payoff clips.
2. Build the serious version first (staging, light, acting), then layer the gags on - the deadpan frame must
   stand on its own.
3. On the contact sheet check that each gag reads in its frame (big enough, lit, not hidden behind a figure) and
   that the characters' faces stay serious.
4. Cut ruthlessly: a gag that needs explaining goes.
