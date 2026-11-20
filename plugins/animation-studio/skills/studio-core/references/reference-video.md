# Working from a reference video

The user names a video ("same look and feel as this one", "like this trailer"). What follows holds for every kind
of film; the fine points of lyric videos (how text enters, what pulses on the beat) are in
`skills/lyric-music-video/references/study-a-reference-video.md` of this plugin.

## 1. Look at it frame by frame

Open the page in the browser, pause the video element, set its time and take a picture - one every 2-3 s for the
overview, then every 0.2-0.5 s where something happens. A paused and seeked video gives exact frames; a playing one
is throttled.

- An ad may run first: the page then reports the ad's duration. Wait until the duration is the video's own. The
  user may want to let the ad finish rather than have it skipped - ask or wait.
- A channel outro (logo animation, "subscribe") is not part of the film: note where the film itself ends.

Write down per shot: time, framing, what moves, the light (key direction, colour, how dark the background is),
bars (cinema scope?), and the black stretches between shots - a teaser is mostly timing and darkness. For title
cards: case, weight, letter spacing, colour, how they fade.

## 2. Get the sound before the first render

You cannot hear the page. Ask the user at once whether there is a sound track for the new film, and for the file:

- **With the file:** measure it first (film-finish `sting.py analyse track`, or studio-core `ear.py timeline`):
  where it builds, hits, drops out and ends. Plan shot lengths and the moment of every action from those times,
  then render.
- **Without it:** say that the film will be silent, or make an own cue (film-finish `score.py`).

On the first film made this way the picture was cut before the sound existed: the one shot had to be stretched
1.8x to fit the music and went soft, and a second version built from the track replaced it. Sound first is cheaper.

The sound track of the reference itself is somebody's music. Do not pull it from the page. Use it only when the user
supplies the file, say that such a version is for private viewing, and offer an own cue for anything that is
published. When the user replaces the file by a better copy, the same music may start a little later in it
(`sting.py align new old` gives the offset; it was 0.096 s on the first film).

## 3. What you may take

The structure, the timing, the kind of light and framing, the typography in general. Everything is made anew with
our own characters; no frames, logos or music from the video. Name the reference in the README of the project and
tell the user that publishing a close re-staging is their call.

## 4. Compare the same way

Put frames of your film at the same film times next to the reference notes, and when several takes exist, one row
per take at the same times - differences in timing show at once.
