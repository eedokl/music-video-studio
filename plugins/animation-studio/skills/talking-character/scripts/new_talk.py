# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Create a talking-scene project folder from a dialogue script (or a recording + its script).

  python new_talk.py <folder> --script dialogue.txt [--recording take.wav] [--set room] [--seed 123] [--name "..."]
  python new_talk.py <folder> --text "Tim: Hallo!\nComputer: Guten Abend, Tim."
Speakers are matched to the bundled figures: tim, lia (SVG figures of the characters skill) and computer (a face on
the set's screen). Any other speaker needs "svg" (own Inkscape figure, rig convention of the characters skill) or
"kind": "screen", and a voice ("voices" entry with "design" + "sample_text") - the script stops and says so.
Writes <folder>/project.json + dialogue.txt; the creative seed is new unless --seed is given. An existing
project.json (or a different dialogue.txt) is never overwritten without --force.
"""
import argparse
import json
import shutil
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis", "voice")
import creative  # noqa: E402
import voice  # noqa: E402
from dialogue import parse, speakers  # noqa: E402

BUNDLED = {"tim": {"svg": "skill:characters/assets/figures/tim.svg", "voice": "tim"},
           "lia": {"svg": "skill:characters/assets/figures/lia.svg", "voice": "lia"},
           "computer": {"kind": "screen", "voice": "computer"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--script")
    g.add_argument("--text")
    ap.add_argument("--recording")
    ap.add_argument("--set", default="room")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--name")
    ap.add_argument("--language", default="de")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing project.json / dialogue.txt in the folder")
    a = ap.parse_args()
    d = Path(a.folder).resolve()
    text = Path(a.script).read_text(encoding="utf-8") if a.script else a.text.replace("\\n", "\n")
    old_dialogue = d / "dialogue.txt"
    taken = [n for n in ("project.json",) if (d / n).exists()]
    if old_dialogue.exists() and old_dialogue.read_text(encoding="utf-8") != text:
        taken.append("dialogue.txt")
    if taken and not a.force:
        raise SystemExit(f"{d} already has {' and '.join(taken)} - edit it there, or re-run with --force to "
                         "overwrite (figures, voices, direction, ideas and seed are then lost)")
    d.mkdir(parents=True, exist_ok=True)
    (d / "dialogue.txt").write_text(text, encoding="utf-8")
    who = speakers(parse(text))
    if not who:
        raise SystemExit("no 'Name: text' lines in the script")
    cast = voice.cast()
    figures, missing = {}, []
    for w in who:
        if w in BUNDLED:
            figures[w] = dict(BUNDLED[w])
        else:
            figures[w] = {"svg": f"figures/{w}.svg", "voice": w}
            missing.append(w)
    p = {"name": a.name or d.name, "fps": 24, "language": a.language, "script": "dialogue.txt", "set": a.set,
         "figures": figures, "direction": {}, "camera": "auto", "subtitles": True, "look": "standard", "ideas": []}
    if a.seed is not None:
        p["seed"] = a.seed
    if a.recording:
        shutil.copy(a.recording, d / ("recording" + Path(a.recording).suffix))
        p["recording"] = "recording" + Path(a.recording).suffix
    if missing:
        p["voices"] = {w: {"engine": "qwen", "design": "<describe the voice in English: age, timbre, temperament>",
                           "sample_text": "<one or two sentences in the film language>"} for w in missing if w not in cast}
    f = d / "project.json"
    f.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")

    class _P:                                   # creative.seed() stores the seed in project.json
        pass
    P = _P()
    P.p, P.file = p, f
    creative.seed(P)
    print(f"-> {f} (speakers {who}, set {a.set}, seed {p['seed']})")
    for w in missing:
        print(f"   '{w}': put an SVG figure at figures/{w}.svg (or set \"kind\": \"screen\")"
              + ("" if w in cast else " and describe the voice in project.json \"voices\""))


if __name__ == "__main__":
    main()
