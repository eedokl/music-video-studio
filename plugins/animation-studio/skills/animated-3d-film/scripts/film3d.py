# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.4"]
# [tool.uv]
# exclude-newer = "2026-11-14T00:00:00Z"
# ///
"""A 3D character film as a project: brief + creative seed, clips (one scene module each), spoken lines, the fast
whole-film preview and the film render.

Usage (uv run film3d.py ...):
  film3d.py new <folder> --title "The Big Plan" [--cast mo:bear,kit:cat,bea:bunny] [--seed 4711] [--size 1920x1080]
      -> <folder>/project.json and scenes/c01_opening.py (a working template scene)
  film3d.py clip <folder> <name> --frames 240 [--about "what happens"] [--xfade 8]
      -> adds the clip to project.json (end of the film) and writes scenes/<name>.py from the template
  film3d.py idea <folder> "Kit hides the plan under the mug" [--by user|ai] [--where c02_plan]
  film3d.py line <folder> <id> <who> "text" [--audio speech/<id>.wav]      add / change a spoken line
  film3d.py speak <folder> [--engine system] [--only l01,l02]
      -> speaks the lines that have no wav yet (voice block), stores their word times, prepares the lip sync
         (stage-3d stage_speech.py -> speech/lines.json). Recorded wavs are only prepared.
  film3d.py sound <folder> [--music music.wav --music-level -18]
      -> sound/film.wav: every spoken line on the frame its scene says it (out/<clip>/build.json) + optional music;
         sets project.json "audio"
  film3d.py preview <folder> [--clips c01,c02]     FAST: every clip in draft quality + the cut -> preview/film_draft.mp4
  film3d.py render <folder> [--clips c01,c02]      DETAIL: film quality + the cut -> film.mp4 (+ small / mail versions)
  film3d.py status <folder>                        rendered frames per clip, in both qualities
"""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import _studio  # noqa: E402
_studio.use("stage-3d", "film-finish", "voice")
import config  # noqa: E402
import creative  # noqa: E402
from stage_project import FPS, Film  # noqa: E402

HERE = Path(__file__).resolve().parent
STAGE = _studio.skill_dir("stage-3d") / "scripts"
FINISH = _studio.skill_dir("film-finish") / "scripts"
TEMPLATE = HERE.parent / "assets" / "template" / "scene.py"


def run(script, *args):
    print("$", script.name, *[str(a) for a in args], flush=True)
    r = subprocess.run([*config.script_cmd(script), *[str(a) for a in args]])
    if r.returncode != 0:
        sys.exit(f"step failed: {script.name}")


def scene_file(F, name, frames, about, cast):
    f = F.dir / "scenes" / f"{name}.py"
    if f.exists():
        return f
    f.parent.mkdir(parents=True, exist_ok=True)
    (f.parent / "__init__.py").touch()
    f.write_text(TEMPLATE.read_text(encoding="utf-8").replace("__CLIP__", name).replace("__ABOUT__", about or "...")
                 .replace("__FRAMES__", str(frames)).replace("__CAST__", json.dumps(cast)), encoding="utf-8")
    return f


def cast_of(F):
    return F.get("cast") or {"mo": "bear", "kit": "cat", "bea": "bunny"}


def cmd_new(a):
    d = Path(a.folder).resolve()
    f = d / "project.json"
    if f.exists():
        sys.exit(f"{f} exists already")
    d.mkdir(parents=True, exist_ok=True)
    w, h = (int(x) for x in a.size.lower().split("x"))
    cast = dict(x.split(":") for x in a.cast.split(",")) if a.cast else {"mo": "bear", "kit": "cat", "bea": "bunny"}
    p = {"title": a.title or d.name, "kind": "film3d", "fps": FPS, "size": [w, h], "ideas": [], "look": "cinema", "palette": "ivory",
         "cast": cast, "clips": [{"name": "c01_opening", "frames": 120, "about": "everybody says hello"}],
         "lines": [], "audio": None}
    if a.seed is not None:
        p["seed"] = a.seed
    f.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    F = Film(d)
    creative.seed(F)
    scene_file(F, "c01_opening", 120, "everybody says hello", cast)
    print(f"3D film '{p['title']}' seed {F.p['seed']} -> {f}")


def cmd_clip(a):
    F = Film(a.folder)
    if any(c[0] == a.name for c in F.clips):
        sys.exit(f"clip '{a.name}' exists already")
    if not a.name.isidentifier():
        sys.exit(f"'{a.name}' is not a valid clip name (letters, digits, _)")
    c = {"name": a.name, "frames": a.frames}
    if a.about:
        c["about"] = a.about
    if a.xfade:
        c["xfade"] = a.xfade
    F.p.setdefault("clips", []).append(c)
    F.save()
    print(scene_file(F, a.name, a.frames, a.about, cast_of(F)))


def cmd_idea(a):
    F = Film(a.folder)
    creative.add_idea(F, a.by, a.text, a.where)
    print(f"{len(F.p['ideas'])} ideas")


def cmd_line(a):
    F = Film(a.folder)
    lines = F.p.setdefault("lines", [])
    ln = next((x for x in lines if x["id"] == a.id), None)
    if ln is None:
        ln = {"id": a.id}
        lines.append(ln)
    if ln.get("text") != a.text:
        ln.pop("words", None)                             # word times belong to the old take
    ln.update(who=a.who, text=a.text, audio=a.audio or f"speech/{a.id}.wav")
    F.save()
    print(f"{len(lines)} lines")


def cmd_speak(a):
    F = Film(a.folder)
    F.check()
    only = a.only.split(",") if a.only else None
    todo = [ln for ln in F.get("lines") or [] if (not only or ln["id"] in only)
            and (a.again or not (F.dir / ln.get("audio", f"speech/{ln['id']}.wav")).exists())]
    if todo:
        import voice
        items = [{"who": ln["who"], "text": ln["text"], "out": str(F.dir / ln.get("audio", f"speech/{ln['id']}.wav"))}
                 for ln in todo]
        for it in items:
            Path(it["out"]).parent.mkdir(parents=True, exist_ok=True)
        res = voice.speak(items, project_dir=str(F.dir), seed=creative.seed(F), language=F.get("language", "en"),
                          engine=a.engine, pronounce=F.get("pronounce"))
        for ln, r in zip(todo, res):
            ln.setdefault("audio", f"speech/{ln['id']}.wav")
            if r.get("words"):
                ln["words"] = [{"word": w["word"], "t": round(w["t"], 3)} for w in r["words"]]
            print(f"   {ln['id']}: {r.get('engine')} score {r.get('score')}")
        F.save()
    run(STAGE / "stage_speech.py", "prepare", F.dir)


def seconds(wav):
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def cmd_sound(a):
    F = Film(a.folder)
    F.check()
    lines = {ln["id"]: ln for ln in F.get("lines") or []}
    places, start, unbuilt = [], 0, []
    for name, n, _ in F.clips:
        b = F.out(name) / "build.json"
        if not b.exists():
            unbuilt.append(name)
        else:
            for s in json.loads(b.read_text(encoding="utf-8")).get("said", []):
                ln = lines.get(s["id"])
                if ln:
                    places.append(((start + s["start"] - 1) / FPS, F.dir / ln.get("audio", f"speech/{s['id']}.wav")))
        start += n
    if unbuilt:
        sys.exit(f"not built yet: {', '.join(unbuilt)} - run `film3d.py preview` (or render one still per clip) first")
    total = F.frames / FPS
    out = F.dir / "sound" / "film.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [config.need("ffmpeg"), "-y", "-v", "error", "-f", "lavfi", "-t", f"{total:.4f}", "-i",
           "anullsrc=r=48000:cl=stereo"]
    fc, mix = [], ["[0:a]"]
    for i, (t, wav) in enumerate(places, 1):
        cmd += ["-i", str(wav)]
        ms = max(0, round(t * 1000))
        fc.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}:all=1[v{i}]")
        mix.append(f"[v{i}]")
    if a.music:
        k = len(places) + 1
        cmd += ["-stream_loop", "-1", "-i", str(Path(a.music).resolve())]
        fc.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={a.music_level}dB,"
                  f"afade=t=out:st={max(0.0, total - 1.5):.3f}:d=1.5[m]")
        mix.append("[m]")
    fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,alimiter=limit=0.95[out]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[out]", "-t", f"{total:.4f}", "-ar", "48000", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        sys.exit(f"ffmpeg failed while mixing the sound: {r.stderr[-600:]}")
    F.p["audio"] = "sound/film.wav"
    F.save()
    print(f"{out}: {len(places)} spoken lines{' + music' if a.music else ''}, {seconds(out):.2f} s "
          f"(film {total:.2f} s)")


def build(a, q):
    F = Film(a.folder)
    F.check()
    clips = ["--clips", a.clips] if a.clips else []
    run(STAGE / "stage_run.py", "film", F.dir, "--q", q, *clips)
    if q == "draft" and F.get("lines") and not F.get("audio") and not a.clips:
        cmd_sound(argparse.Namespace(folder=a.folder, music=None, music_level=-18))
    run(FINISH / "clip_film.py", F.dir, "--q", q, *clips)


def cmd_status(a):
    for q in ("draft", "film"):
        run(STAGE / "stage_run.py", "status", a.folder, "--q", q)


def main():
    ap = argparse.ArgumentParser(description="A 3D character film project: scenes, lines, preview, render.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("folder")
    n.add_argument("--title")
    n.add_argument("--cast", help="name:look pairs, looks: bear, cat, bunny (e.g. mo:bear,kit:cat)")
    n.add_argument("--seed", type=int)
    n.add_argument("--size", default="1920x1080")
    c = sub.add_parser("clip")
    c.add_argument("folder")
    c.add_argument("name")
    c.add_argument("--frames", type=int, required=True)
    c.add_argument("--about")
    c.add_argument("--xfade", type=int, default=0)
    i = sub.add_parser("idea")
    i.add_argument("folder")
    i.add_argument("text")
    i.add_argument("--by", default="ai")
    i.add_argument("--where", default="")
    ln = sub.add_parser("line")
    ln.add_argument("folder")
    ln.add_argument("id")
    ln.add_argument("who")
    ln.add_argument("text")
    ln.add_argument("--audio")
    s = sub.add_parser("speak")
    s.add_argument("folder")
    s.add_argument("--engine")
    s.add_argument("--only")
    s.add_argument("--again", action="store_true", help="speak lines again that have a wav already")
    so = sub.add_parser("sound")
    so.add_argument("folder")
    so.add_argument("--music")
    so.add_argument("--music-level", type=float, default=-18.0)
    for name in ("preview", "render"):
        b = sub.add_parser(name)
        b.add_argument("folder")
        b.add_argument("--clips")
    st = sub.add_parser("status")
    st.add_argument("folder")
    a = ap.parse_args()
    if a.cmd == "preview":
        return build(a, "draft")
    if a.cmd == "render":
        return build(a, "film")
    return {"new": cmd_new, "clip": cmd_clip, "idea": cmd_idea, "line": cmd_line, "speak": cmd_speak,
            "sound": cmd_sound, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
