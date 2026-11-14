# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Whole talking scene in one go: voices -> scene -> render -> subtitles -> sounds -> film (look) -> check.

  uv run make.py [--project .] [--from scene]
         [--redo-voices] [--engine system] [--jobs 8]
Steps (--from starts later, finished earlier steps are kept):
  voices    speak.py           script -> lines/*.wav, song.wav, analysis/dialogue.json, assignment.json
  scene     talk_scene.py      scenes/dialogue.sif + frames scenes/dialogue/f.%04d.png
  overlays  film-finish overlays.py dialogue   subtitles (word by word, "subtitles": false switches them off)
  sounds    film-finish sounds.py              gesture sounds (earshot; "sounds": false switches them off)
  film      film-finish build.py film          film.mp4, film_small.mp4, film_mail.mp4 with the look, 0 decode errors
  check     check_sync.py                      lip-sync numbers + contact_sheet.png
"""
import argparse
import subprocess
import sys
from pathlib import Path

import _studio  # noqa: E402
_studio.use("song-analysis")
import config  # noqa: E402
from song_project import Project  # noqa: E402

HERE = Path(__file__).resolve().parent
FINISH = _studio.skill_dir("film-finish") / "scripts"
STEPS = ["voices", "scene", "overlays", "sounds", "film", "check"]


def run(*cmd):
    print(">", " ".join(str(c) for c in cmd[1:3]), flush=True)
    subprocess.run(config.script_cmd(cmd[0]) + [str(c) for c in cmd[1:]], check=True)   # each step: its own packages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--from", dest="start", choices=STEPS, default="voices")
    ap.add_argument("--redo-voices", action="store_true")
    ap.add_argument("--engine", choices=["qwen", "piper", "system"])
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    d = Path(a.project).resolve()
    todo = STEPS[STEPS.index(a.start):]
    if "voices" in todo:
        run(HERE / "speak.py", "--project", d, *(["--redo"] if a.redo_voices else []),
            *(["--engine", a.engine] if a.engine else []))
    P = Project(d)
    if "scene" in todo:
        run(HERE / "talk_scene.py", "--project", d, "--render", "--jobs", a.jobs)
    ov = d / "overlays" / "dialogue.mov"
    if "overlays" in todo:
        if P.get("subtitles", True) or P.get("gags"):
            run(FINISH / "overlays.py", "dialogue", "--project", d)
        elif ov.exists():
            ov.unlink()
    if "sounds" in todo:                              # sounds.py handles "sounds": false itself (removes a stale track)
        run(FINISH / "sounds.py", d)
    if "film" in todo:
        run(FINISH / "build.py", "film", "--project", d)
    if "check" in todo:
        run(HERE / "check_sync.py", "--project", d)


if __name__ == "__main__":
    main()
