"""A 3D film that runs on a song: the song's times as clip frames, who sings which line, acting on the beat.

Read by scene modules (`import stage_song as SG`); the data is PROJECT/timing.json, written by the animated-3d-film
skill (`film3d.py song <project>`, from a song-analysis project and the film's song_plan.json):
  {"fps": 24, "duration": s, "bpm": .., "clips": [{"name", "t0", "t1", "frames", "about"}],
   "beats": [s], "bars": [s], "accents": [s], "groups": {"all": ["mo", "flo"]},
   "lines": [{"n": 4, "id": "l04", "who": "mo" | group, "text": as shown on screen, "sung": as sung,
              "t0", "t1", "words": [{"word", "t"}]}]}                 all times are song seconds

Time:    SG.f(clip, t) = clip frame (1-based) of a song second, SG.t(clip, frame) back, SG.CLIPS[clip] = (t0, t1,
         frames), SG.beats(clip) / SG.bars(clip) / SG.accents(clip) = clip frames of the beats / downbeats / accents,
         SG.word(clip, "word", after=t, nth=0) = clip frame of a sung word (None when it is not sung in the clip),
         SG.lines(clip) = the lyric lines that start in the clip, SG.line(n) = lyric line n.
Singing: SG.sing(cast, clip) keys the lip sync of every line of the clip on its performer(s) -> [(line, first frame,
         end frame)]; a group name ("all") is every figure of timing.json "groups".
Acting:  SG.groove(figure, f0, f1, clip, amp) nods and bounces on the beat; SG.rap(figure, clip, n) changes the
         gesture pose on the words of line n.
The time helpers need no Blender (tests, planning scripts): SG.use(folder) points them at a project.
"""
import json
import math
import os
from pathlib import Path

FPS = 24
_P = {"dir": Path(os.environ.get("STAGE3D_PROJECT") or Path.cwd()), "data": None}


def use(folder):
    """read timing.json of this project folder (inside Blender the project is set already)"""
    _P.update(dir=Path(folder), data=None)
    CLIPS.clear()


def data():
    if _P["data"] is None:
        f = _P["dir"] / "timing.json"
        if not f.exists():
            raise SystemExit(f"{f} missing - a film on a song needs it: film3d.py song <project> (animated-3d-film)")
        _P["data"] = json.loads(f.read_text(encoding="utf-8"))
    return _P["data"]


class _Clips(dict):
    def __missing__(self, k):
        for c in data()["clips"]:
            self[c["name"]] = (c["t0"], c["t1"], c["frames"])
        if k not in self:
            raise SystemExit(f'clip "{k}" is not in timing.json ({", ".join(self) or "no clips"})')
        return self[k]


CLIPS = _Clips()


def f(clip, t):
    """clip frame (1-based) of song second t"""
    return int(round((t - CLIPS[clip][0]) * FPS)) + 1


def t(clip, frame):
    """song second of a clip frame"""
    return CLIPS[clip][0] + (frame - 1) / FPS


def _in(clip, times):
    t0, t1, _ = CLIPS[clip]
    return [f(clip, x) for x in times if t0 <= x < t1]


def beats(clip):
    return _in(clip, data()["beats"])


def bars(clip):
    return _in(clip, data()["bars"])


def accents(clip):
    return _in(clip, data().get("accents", []))


def lines(clip):
    """the lyric lines that start in the clip (dicts as in timing.json, times in song seconds)"""
    t0, t1, _ = CLIPS[clip]
    return [ln for ln in data()["lines"] if t0 <= ln["t0"] < t1]


def line(n):
    for ln in data()["lines"]:
        if ln["n"] == n:
            return ln
    raise SystemExit(f"lyric line {n} is not in timing.json")


def word(clip, w, after=None, nth=0):
    """clip frame at which a sung word starts: the nth word of the clip that contains w (as shown or as sung), at or
    after song second `after`; None when it is not sung in the clip - write `SG.word(...) or <fallback frame>`"""
    t0, t1, _ = CLIPS[clip]
    lo = max(t0, t0 if after is None else after)
    hits = [x["t"] for ln in data()["lines"] for x in ln["words"]
            if (w.lower() in x["word"].lower() or w.lower() in x.get("sung", "").lower()) and lo <= x["t"] < t1]
    return f(clip, hits[min(nth, len(hits) - 1)]) if hits else None


def singers(who):
    """the figure names behind a line's "who" (a group of timing.json "groups", or the name itself)"""
    return tuple(data().get("groups", {}).get(who, (who,)))


def sing(figs, clip, only=None, skip=(), gesture=1.4, nod=1.3):
    """Lip sync of every lyric line of the clip on its performer(s) of `figs` ({name: figure}); lines of figures that
    are not in the clip are left out. Returns [(line dict, first frame, end frame)]."""
    out = []
    for ln in lines(clip):
        if (only and ln["n"] not in only) or ln["n"] in skip:
            continue
        f0 = max(1, f(clip, ln["t0"]))
        end = f0
        for who in singers(ln["who"]):
            if who in figs:
                end = figs[who].say(ln["id"], f0, gesture=gesture, nod=nod)
        out.append((ln, f0, end))
    return out


def groove(c, f0, f1, clip, amp=1.0, half=False):
    """nod the head and bounce the body on every beat between f0 and f1 (half = every second beat). Give every
    figure its own amp (0.3 = barely, 1.3 = all in) - a cast that nods alike looks like one puppet."""
    bs = [b for b in beats(clip) if f0 <= b <= f1][::2 if half else 1]

    def pulse(fr, wd):
        return sum(math.exp(-((fr - b - 1) / wd) ** 2) for b in bs if abs(fr - b) < 10)
    c.head.rch(0).add(lambda fr: 7.0 * amp * pulse(fr, 2.6))
    c.sq.lch(2).add(lambda fr: -0.018 * amp * pulse(fr, 2.8) / c.size)
    c.body.rch(0).add(lambda fr: 2.5 * amp * pulse(fr, 3.2))
    return c


RAP = ("present", "point", "fist_down", "present_l", "open", "point_l", "hips", "shrug")


def rap(c, clip, n, poses=RAP, every=2, rest="rest"):
    """rap hands: a new gesture pose on every `every`-th word of lyric line n, back to `rest` after the line"""
    ln = line(n)
    ws = [f(clip, w["t"]) for w in ln["words"]][::every]
    for i, fr in enumerate(ws):
        c.pose(max(1, fr - 2), poses[(i + n) % len(poses)], "out")
    c.pose(f(clip, ln["t1"]) + 8, rest)
    return c
