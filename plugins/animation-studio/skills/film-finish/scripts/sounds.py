# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Sound-effect track on the song timeline (earshot sound bank) -> analysis/sounds.wav (build.py mixes it in).

Sources, so every sound lands on its frame:
  - gestures written by the scenes (analysis/actions_*.json): scare -> hit, cheer -> glockenspiel, point -> swish, ...;
    an entry with "sfx" (+ "level", "pan") plays exactly that sound (scene.py: a key click per typing strike)
  - text gags (analysis/gags.json): a soft pop when the lettering pops up
  - toon-2d breakout.py writes analysis/actions_breakout_<panel>.json (climb, splash, jump, landing, coins) - read
    like any actions file
  - project.json "sounds" (true / missing = only the sources above, false = no sound-effect track): a list with
    one rule per entry, each with "sfx", "level" (dB, default -14), "pan" (-1..1), and
      {"word": "limit"}                       start of every matching word (prefix | "=exact" | "re:regex"), >= 1 s apart
      {"at": 217.3}                           a song second
      {"marker": "final chorus"}              a marker of analysis/markers.json (its line start)
      {"every": 0.85, "from": 213.3, "to": 222.5}   a repeating series (e.g. a heartbeat); "from"/"to" may also be
                                              "from_word" / "to_word" (first such word)
    optional: "offset": 0.2 (s, added to every time - a second thump of a double heartbeat), "dur": 0.32 (rendered
    length, earshot --dur), "sections": [...] / "not_sections": [...] (only / never in these sections)
Soft sounds ~9 dB under the music, 6 kHz low-pass and 10 ms fades: hard unfiltered clicks over music sounded like
"a broken speaker" (studio-core sfx_mix.py, shared with the other skills). All sounds: `earshot sfx list`. Without earshot the script says so and writes no track.
Usage: uv run sounds.py [<project>]
"""
import json
import sys

import numpy as np

import _studio  # noqa: E402
_studio.use("song-analysis")
from media import decode  # noqa: E402
from sfx_mix import SR, SfxMix  # noqa: E402
from song_project import Project, allowed, word_matches  # noqa: E402

GESTURE_SOUND = {"scare": ("cut_hit/punch", -14), "cheer": ("mallet/flourish", -15), "point": ("swish/soft", -17),
                 "scratch": ("fit/land.light/finger_wood", -18), "sad": ("downlifter/tape", -17)}
POP = ("ui_pop/blip", -20)


def main():
    args = [x for x in sys.argv[1:] if x != "--project"]           # `sounds.py <folder>` or `--project <folder>`
    P = Project(args[0] if args else ".")
    P.check("film-finish")                 # project.json validated before any long step
    rules = P.get("sounds", [])
    if rules is False:                                # "sounds": false = no sound-effect track at all
        (P.analysis / "sounds.wav").unlink(missing_ok=True)
        print('project.json "sounds": false - no sound-effect track (the film keeps the song only)')
        return
    if rules in (True, None):                         # "sounds": true = the default (gestures, gags), no extra rules
        rules = []
    elif isinstance(rules, dict):
        rules = [rules]
    mix = SfxMix(len(decode(P.song, 8000)) / 8000, cache=P.cache / "sfx_bank", pan_law="equal")
    if not mix.ear:
        print("earshot is not installed - no sound-effect track (the film keeps the song only)")
        return

    events = []                                       # (time, sound, level_db, pan)
    for f in sorted(P.analysis.glob("actions_*.json")):
        for a in json.loads(f.read_text(encoding="utf-8")):
            if a.get("sfx"):                          # the scene names the sound itself (e.g. key clicks of typing)
                events.append((a["t"], a["sfx"], float(a.get("level", -18)), float(a.get("pan", 0.0))))
            elif a["gesture"] in GESTURE_SOUND:
                sid, db = GESTURE_SOUND[a["gesture"]]
                events.append((a["t"], sid, db, 0.0))
    if (P.analysis / "gags.json").exists():
        for gags in json.loads((P.analysis / "gags.json").read_text(encoding="utf-8")).values():
            for g in gags:
                events.append((g["t"] + 1 / P.fps, POP[0], POP[1], -0.3 if "left" in g["place"] else 0.3))
    sheet = P.sheet()
    words, lines = sheet["words"], sheet["lines"]
    first_word = lambda pre: next((w["t"] for w in words if word_matches(w["word"], pre)), None)
    for r in rules:
        times = []
        if r.get("word"):
            last = -99
            for w in words:
                if word_matches(w["word"], r["word"]) and w["t"] - last > 1.0:
                    times.append(w["t"])
                    last = w["t"]
        elif r.get("every"):
            t0 = r.get("from") if r.get("from") is not None else first_word(r["from_word"]) if r.get("from_word") else None
            t1 = r.get("to") if r.get("to") is not None else first_word(r["to_word"]) if r.get("to_word") else None
            if t0 is None or t1 is None:
                print(f"  sound series {r.get('sfx')}: no from/to - skipped")
                continue
            times = list(np.arange(float(t0), float(t1) - 1e-6, float(r["every"])))
        elif r.get("at") is not None:
            times = [float(r["at"])]
        elif r.get("marker"):
            times = [lines[m["line"]]["t"] for m in P.markers()
                     if r["marker"].lower() in m["marker"].lower() and m["line"] < len(lines)][:1]
        sid = r["sfx"] + (f"@{r['dur']}" if r.get("dur") else "")
        for t in times:
            t = float(t) + float(r.get("offset", 0.0))
            if allowed(r, P.section_at(t)):
                events.append((t, sid, float(r.get("level", -14)), float(r.get("pan", 0.0))))

    for t, sid, db, pan in events:
        base, _, dur = sid.partition("@")             # "sub_drop/punch@0.32" = rendered with --dur 0.32
        if 0 <= t < mix.n / SR:
            mix.sfx(t, base, ["--dur", dur] if dur else [], db=db, pan=pan, align="start")
    mix.write(P.analysis / "sounds.wav", lowpass=6000, limit=0.9)
    kinds = {}
    for _, sid, _, _ in events:
        sid = sid.partition("@")[0]
        kinds[sid] = kinds.get(sid, 0) + 1
    print(f"{len(events)} sounds {kinds} -> analysis/sounds.wav")


if __name__ == "__main__":
    main()
