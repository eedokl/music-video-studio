# /// script
# requires-python = ">=3.12"
# dependencies = []
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""Prepare the spoken lines of a 3D film for lip sync: Rhubarb mouth cues + word times -> speech/lines.json.

  stage_speech.py prepare <project>      every line of project.json "lines" (its wav must exist)
  stage_speech.py show <project>         the lines with their length in frames and their word frames

project.json "lines": [{"id": "l01", "who": "mo", "text": "Hello there!", "audio": "speech/l01.wav",
                        "words": [{"word": "Hello", "t": 0.05}, ...]}]
"audio" defaults to speech/<id>.wav; "words" (start times in seconds, e.g. from the voice block's Whisper check) are
optional - without them the words are spread evenly over the line (good enough for head accents, marked "approx").
Result speech/lines.json: {"lines": [{"id", "who", "text", "duration", "words": [...], "cues": [{"start", "end",
"value"}]}]} - read inside Blender by stage_actor (`figure.say(id, frame)`, `word_frame`, `line_frames`).
The mouth cues are cached per line (speech/mouth/<id>.json, rebuilt when the wav or the text changes).
"""
import argparse
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import _studio  # noqa: E402
_studio.use()
import config  # noqa: E402
import derived  # noqa: E402
from stage_project import FPS, Film  # noqa: E402

SHAPES = "GHX"


def seconds(wav):
    try:
        with wave.open(str(wav)) as w:
            return w.getnframes() / w.getframerate()
    except (wave.Error, EOFError):                      # not plain PCM: ask ffmpeg
        err = subprocess.run([config.need("ffmpeg"), "-hide_banner", "-i", str(wav)], capture_output=True, text=True,
                             errors="replace").stderr
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
        if not m:
            raise SystemExit(f"cannot read the length of {wav}") from None
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def mouth_cues(wav, text, cache):
    spec = {"text": text, "shapes": SHAPES, "v": 1}
    if not derived.fresh(cache, inputs=[wav], spec=spec):
        with derived.build(cache, inputs=[wav], spec=spec) as b:
            txt = Path(str(b.path) + ".txt")
            txt.write_text(text, encoding="utf-8")
            try:
                r = subprocess.run([config.need("rhubarb"), "-f", "json", "--extendedShapes", SHAPES, "-d", str(txt),
                                    "-o", str(b.path), str(wav)], capture_output=True, text=True, errors="replace")
            finally:
                txt.unlink(missing_ok=True)
            if r.returncode != 0:
                raise SystemExit(f"rhubarb failed on {wav.name}: {r.stderr[-400:]}")
    return json.loads(Path(cache).read_text(encoding="utf-8"))["mouthCues"]


def prepare(F):
    out, skipped = [], []
    for ln in F.get("lines") or []:
        wav = F.dir / ln.get("audio", f"speech/{ln['id']}.wav")
        if not wav.exists():                        # the others are prepared (speak --only l01 must not stop here)
            skipped.append(f"{ln['id']} ({wav.name} missing - speak or record it)")
            continue
        if ln.get("redo"):
            skipped.append(f"{ln['id']} (text changed - film3d.py speak speaks it again)")
            continue
        dur = seconds(wav)
        cues = mouth_cues(wav, ln.get("text", ""), F.dir / "speech" / "mouth" / f"{ln['id']}.json")
        words = ln.get("words")
        approx = not words
        if approx:
            toks = ln.get("text", "").split()
            words = [{"word": w, "t": round(dur * i / max(1, len(toks)), 3)} for i, w in enumerate(toks)]
        out.append({"id": ln["id"], "who": ln.get("who", ""), "text": ln.get("text", ""), "duration": round(dur, 3),
                    "words": [{"word": w["word"], "t": w["t"]} for w in words], "cues": cues,
                    **({"approx": True} if approx else {})})
    f = F.dir / "speech" / "lines.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"lines": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{f}: {len(out)} lines" + (f" ({sum(1 for o in out if o.get('approx'))} with estimated word times)"
                                        if any(o.get("approx") for o in out) else ""))
    for s in skipped:
        print(f"WARNING not prepared: {s} - a scene that says it stops", file=sys.stderr)
    return out


def show(F):
    f = F.dir / "speech" / "lines.json"
    if not f.exists():
        raise SystemExit(f"{f} missing - run: stage_speech.py prepare {F.dir}")
    for ln in json.loads(f.read_text(encoding="utf-8"))["lines"]:
        print(f"{ln['id']:14s} {ln['who']:10s} {round(ln['duration'] * FPS):4d} frames  "
              + " ".join(f"{w['word']}@{round(w['t'] * FPS)}" for w in ln["words"]))


def main():
    ap = argparse.ArgumentParser(description="Mouth cues and word times of the spoken lines of a 3D film.")
    ap.add_argument("cmd", choices=("prepare", "show"))
    ap.add_argument("project")
    a = ap.parse_args()
    F = Film(a.project)
    if a.cmd == "prepare":
        F.check()
        prepare(F)
    else:
        show(F)
    return 0


if __name__ == "__main__":
    sys.exit(main())
