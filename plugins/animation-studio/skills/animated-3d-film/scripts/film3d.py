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
  film3d.py line <folder> <id> <who> "text" [--audio speech/<id>.wav] [--at c02_plan:30]
      add / change a spoken line; --at places a voice-over (narrator, no say() in a scene) on a clip frame.
      Changed text: a spoken line is spoken again by the next `speak`; a recording is only warned about.
  film3d.py speak <folder> [--engine system] [--only l01,l02] [--again]
      -> speaks the lines that have no wav yet or whose text changed (voice block), stores their word times,
         prepares the lip sync (stage-3d stage_speech.py -> speech/lines.json). Recorded wavs are only prepared;
         --again speaks the spoken lines again (recordings only when named with --only).
  film3d.py sound <folder> [--music music.wav --music-level -18]
      -> sound/film.wav: every spoken line on the frame its scene says it (out/<clip>/build.json) or on its "at"
         frame + optional music; sets project.json "audio". preview / render mix it again by themselves when a
         line, a say() frame or a clip length changed (a finished track set by hand in "audio" stays as it is).
  film3d.py preview <folder> [--clips c01,c02]     FAST: every clip in draft quality + the cut -> preview/film_draft.mp4
  film3d.py render <folder> [--clips c01,c02]      DETAIL: film quality + the cut -> film.mp4 (+ small / mail versions)
      Frames are resumable; a clip whose scene, project settings (size, palette, lips, seed, cast) or spoken lines
      changed since its frames is rendered again (out/<clip>/<q>/source.json).
  film3d.py status <folder>                        rendered frames per clip, in both qualities
"""
import argparse
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import _studio  # noqa: E402
_studio.use("stage-3d", "film-finish", "voice")
import config  # noqa: E402
import creative  # noqa: E402
import derived  # noqa: E402
from stage_project import FPS, Film  # noqa: E402

HERE = Path(__file__).resolve().parent
STAGE = _studio.skill_dir("stage-3d") / "scripts"
FINISH = _studio.skill_dir("film-finish") / "scripts"
TEMPLATE = HERE.parent / "assets" / "template" / "scene.py"
SOUND = "sound/film.wav"                                  # the mix film3d.py makes (a hand-set "audio" is kept)
LOOKS = ("bear", "cat", "bunny")                          # the bundled toys (stage-3d stage_actor.LOOKS, Blender only)


def parse_size(s):
    try:
        w, h = (int(x) for x in s.lower().split("x"))
    except ValueError:
        sys.exit(f"--size {s}: expected WIDTHxHEIGHT, e.g. 1920x1080")
    if w % 4 or h % 4 or not (32 <= w <= 7680 and 32 <= h <= 4320):
        sys.exit(f"--size {s}: width and height must be multiples of 4 (the draft renders half of it and H.264 "
                 "needs even sizes), 32..7680 x 32..4320")
    return w, h


def parse_cast(s):
    cast = {}
    for x in s.split(","):
        name, sep, look = x.strip().partition(":")
        if not sep or not name or not look:
            sys.exit(f"--cast {s}: expected name:look pairs, e.g. mo:bear,kit:cat")
        if look not in LOOKS:
            sys.exit(f"--cast: unknown look '{look}' (bundled: {', '.join(LOOKS)}; an own look is a dict in "
                     "project.json \"cast\", see stage-3d guide.md)")
        cast[name] = look
    return cast


def wav_of(F, ln):
    return F.dir / ln.get("audio", f"speech/{ln['id']}.wav")


def spoken(ln):
    """made by the voice block (a recording has neither the flag nor word times from the voice check)"""
    return bool(ln.get("spoken") or ln.get("words"))


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
    w, h = parse_size(a.size)
    cast = parse_cast(a.cast) if a.cast else {"mo": "bear", "kit": "cat", "bea": "bunny"}
    p = {"title": a.title or d.name, "kind": "film3d", "fps": FPS, "size": [w, h], "ideas": [], "look": "cinema", "palette": "ivory",
         "cast": cast, "clips": [{"name": "c01_opening", "frames": 120, "about": "everybody says hello"}],
         "lines": [], "audio": None}
    if a.seed is not None:
        p["seed"] = a.seed
    if a.figures != "toy":
        p["figures"] = a.figures
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
    audio = a.audio or ln.get("audio") or f"speech/{a.id}.wav"        # a custom path stays without --audio
    if "text" in ln and ln["text"] != a.text:
        was_spoken = spoken(ln)
        ln.pop("words", None)                             # word times belong to the old take
        if (F.dir / audio).exists() and audio == ln.get("audio"):
            if was_spoken:                                # the next `speak` makes the new take
                ln["redo"] = True
                print(f"{a.id}: the text changed - `film3d.py speak` speaks it again")
            else:
                print(f"WARNING {a.id}: the text changed but {audio} is a recording of the old text - record it "
                      "again (the lip sync and the sound follow the wav)", file=sys.stderr)
    if a.at is not None:
        clip, sep, fr = a.at.partition(":")
        if not sep or not fr.isdigit() or int(fr) < 1:
            sys.exit(f"--at {a.at}: expected <clip>:<frame>, e.g. c02_plan:30")
        F.clip(clip)
        ln["at"] = a.at
    ln.update(who=a.who, text=a.text, audio=audio)
    F.save()
    print(f"{len(lines)} lines")


def cmd_speak(a):
    F = Film(a.folder)
    F.check()
    only = a.only.split(",") if a.only else None
    lines = F.get("lines") or []
    if only and (bad := [i for i in only if i not in {ln["id"] for ln in lines}]):
        sys.exit(f"--only: no such line {', '.join(bad)}")
    todo = [ln for ln in lines if (not only or ln["id"] in only)
            and (not wav_of(F, ln).exists() or ln.get("redo") or (a.again and (only or spoken(ln))))]
    kept = [ln["id"] for ln in lines if a.again and not only and wav_of(F, ln).exists() and not spoken(ln)]
    if kept:
        print(f"--again keeps the recordings {', '.join(kept)} (name them with --only to speak them instead)")
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
            ln["spoken"] = True
            ln.pop("redo", None)
            ln.pop("words", None)
            if r.get("words"):
                ln["words"] = [{"word": w["word"], "t": round(w["t"], 3)} for w in r["words"]]
            print(f"   {ln['id']}: {r.get('engine')} score {r.get('score')}")
        F.save()
    run(STAGE / "stage_speech.py", "prepare", F.dir)


def seconds(wav):
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def sound_plan(F):
    """([(seconds, wav, id)], unbuilt clips, unplaced line ids): every line on the frame its scene says it
    (out/<clip>/build.json "said") or on its "at" frame (voice-over)."""
    lines = {ln["id"]: ln for ln in F.get("lines") or []}
    places, start, unbuilt, starts = [], 0, [], {}
    for name, n, _ in F.clips:
        starts[name] = start
        b = F.out(name) / "build.json"
        if not b.exists():
            unbuilt.append(name)
        else:
            for s in json.loads(b.read_text(encoding="utf-8")).get("said", []):
                if s["id"] in lines:
                    places.append(((start + s["start"] - 1) / FPS, s["id"]))
        start += n
    said = {i for _, i in places}
    for ln in lines.values():
        clip, _, fr = str(ln.get("at") or "").partition(":")
        if ln["id"] not in said and clip in starts and fr.isdigit():
            places.append(((starts[clip] + int(fr) - 1) / FPS, ln["id"]))
    placed = {i for _, i in places}
    return ([(t, wav_of(F, lines[i]), i) for t, i in sorted(places)], unbuilt,
            [i for i in lines if i not in placed])


def sound_key(F, places, music, level):
    inputs = [w for _, w, _ in places] + ([Path(music)] if music else [])
    spec = {"places": [[round(t, 4), i] for t, _, i in places], "frames": F.frames, "music": music, "level": level}
    return inputs, spec


def cmd_sound(a):
    F = Film(a.folder)
    F.check()
    places, unbuilt, unplaced = sound_plan(F)
    if unbuilt:
        sys.exit(f"not built yet: {', '.join(unbuilt)} - run `film3d.py preview` (or render one still per clip) first")
    if unplaced:
        print(f"WARNING: the lines {', '.join(unplaced)} are said in no scene and have no \"at\" - they are NOT in "
              "the sound. A voice-over: film3d.py line <folder> <id> <who> \"text\" --at <clip>:<frame>",
              file=sys.stderr)
    gone = [str(w) for _, w, _ in places if not w.exists()]
    if gone:
        sys.exit(f"missing wavs: {', '.join(gone)} - run `film3d.py speak` (or record them) first")
    music = str(Path(a.music).resolve()) if a.music else None
    total = F.frames / FPS
    out = F.dir / SOUND
    if out.exists() and derived.recorded(out) is None and F.get("audio") != SOUND:
        sys.exit(f"{out} exists and was not mixed by film3d.py - move it away, or set it as project.json \"audio\" "
                 "(then it is used as it is and never mixed over)")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(".mixing." + out.name)
    cmd = [config.need("ffmpeg"), "-y", "-v", "error", "-f", "lavfi", "-t", f"{total:.4f}", "-i",
           "anullsrc=r=48000:cl=stereo"]
    fc, mix = [], ["[0:a]"]
    for i, (t, wav, _) in enumerate(places, 1):
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
    cmd += ["-filter_complex", ";".join(fc), "-map", "[out]", "-t", f"{total:.4f}", "-ar", "48000", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        sys.exit(f"ffmpeg failed while mixing the sound: {r.stderr[-600:]}")
    os.replace(tmp, out)
    inputs, spec = sound_key(F, places, music, a.music_level)
    derived.record(out, inputs, spec)
    F.p["audio"] = SOUND
    if music:
        F.p["sound"] = {"music": music, "music_level": a.music_level}
    else:
        F.p.pop("sound", None)
    F.save()
    print(f"{out}: {len(places)} spoken lines{' + music' if a.music else ''}, {seconds(out):.2f} s "
          f"(film {total:.2f} s)")


def refresh_sound(folder):
    """Mix sound/film.wav (again) when the lines, a say() frame, an "at" or a clip length changed since its mix.
    A track set by hand in project.json "audio" is never touched."""
    F = Film(folder)
    au = F.get("audio")
    if not F.get("lines") or au not in (None, SOUND):
        return
    places, unbuilt, _ = sound_plan(F)
    if unbuilt:
        if au:
            print(f"WARNING: {', '.join(unbuilt)} not built - {SOUND} may not fit the picture (build every clip)",
                  file=sys.stderr)
        return
    snd = F.get("sound") or {}
    inputs, spec = sound_key(F, places, snd.get("music"), snd.get("music_level", -18.0))
    if au == SOUND and derived.fresh(F.dir / SOUND, inputs, spec):
        return
    if au == SOUND and derived.recorded(F.dir / SOUND) is None:     # mixed by 0.5.0 (maybe with music): ask
        print(f"WARNING: {SOUND} has no mix record (older version) and may not fit the picture any more - run "
              "`film3d.py sound <folder> [--music ...]` once", file=sys.stderr)
        return
    print(f"{'the lines / clip lengths changed since ' + SOUND + ' was mixed - mixing again' if au else 'mixing the spoken lines'}",
          flush=True)
    cmd_sound(argparse.Namespace(folder=folder, music=snd.get("music"), music_level=snd.get("music_level", -18.0)))


def build(a, q):
    F = Film(a.folder)
    F.check()
    clips = ["--clips", a.clips] if a.clips else []
    run(STAGE / "stage_run.py", "film", F.dir, "--q", q, *clips)
    refresh_sound(a.folder)
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
    n.add_argument("--figures", choices=("toy", "ragdoll", "puppet", "stopmotion"), default="toy",
                   help="the make of the figures: felt toys (default), sewn rag dolls, hand puppets or gothic "
                        "stop-motion puppets")
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
    ln.add_argument("--at", help="voice-over: <clip>:<frame> where the line starts (a narrator has no say())")
    s = sub.add_parser("speak")
    s.add_argument("folder")
    s.add_argument("--engine")
    s.add_argument("--only")
    s.add_argument("--again", action="store_true",
                   help="speak the spoken lines again (recorded wavs only when named with --only)")
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
