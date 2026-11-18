"""animated-3d-film: film3d.py new -> clip -> idea -> line (a synthetic wav) -> stage_speech prepare -> two tiny clips
rendered in draft quality with Blender -> sound mix -> clip_film cut (dissolve, look, sound)."""
import os
import re
import subprocess
import time
from pathlib import Path

from common import (Test, audio_samples, expect, expect_film, first_loud, full, need, read_json, script, tool,
                    write_json)

FILM3D = script("animated-3d-film", "film3d.py")
RUN = script("stage-3d", "stage_run.py")
SPEECH = script("stage-3d", "stage_speech.py")
CUT = script("film-finish", "clip_film.py")

SCENE = '''import stage_actor as K
import stage_sets as sets
import stage_shots as shots

FRAMES = {frames}


def build(S):
    sets.office(S, mood="{mood}")
    cast = K.cast(S, {{"mo": "bear", "kit": {{"look": "cat", "glasses": True}}}})
    sets.seat(cast)
    mo, kit = cast["mo"], cast["kit"]
    {say}
    kit.look(3, mo.face_pos(1))
    S.shot(1, (0, -5.0, 1.5), (0, 0.8, 0.8), loc1=(0, -4.7, 1.5), lens=40, fstop=4)
    shots.closeup(S, {cut}, mo, dist=1.3)
'''


def run_film(ctx):
    need("ffmpeg", "blender", "rhubarb")
    d = ctx.dir / "film"
    size = "1920x1080" if full() else "640x360"                # draft quality renders half of it
    ctx.uv(FILM3D, "new", d, "--title", "E2E 3D", "--seed", "4711", "--cast", "mo:bear,kit:cat", "--size", size)
    ctx.uv(FILM3D, "clip", d, "c02_answer", "--frames", "8", "--about", "kit answers", "--xfade", "3")
    ctx.uv(FILM3D, "idea", d, "Kit looks at Mo while Mo speaks")
    P = read_json(d / "project.json")
    expect(P.get("seed") == 4711 and len(P.get("ideas", [])) == 1 and [c["name"] for c in P["clips"]] ==
           ["c01_opening", "c02_answer"], f"project.json after new/clip/idea is wrong: {P}")
    expect((d / "scenes" / "c02_answer.py").exists(), "film3d.py clip wrote no scene file")
    # a spoken line: quiet, then a loud tone (the mark the sound mix is measured against)
    ctx.uv(FILM3D, "line", d, "l01", "mo", "Hello there")
    (d / "speech").mkdir(exist_ok=True)
    ctx.ff("-f", "lavfi", "-i", "aevalsrc=0.5*sin(2*PI*330*t)*gt(t\\,0.1):s=44100:d=0.3", "-ac", "1",
           str(d / "speech" / "l01.wav"))
    P = read_json(d / "project.json")
    P["clips"][0]["frames"] = 12
    write_json(d / "project.json", P)
    line_at = 5
    (d / "scenes" / "c01_opening.py").write_text(SCENE.format(frames=12, mood="golden", cut=9,
                                                             say=f'mo.say("l01", {line_at})'), encoding="utf-8")
    (d / "scenes" / "c02_answer.py").write_text(SCENE.format(frames=8, mood="night", cut=6, say="kit.nod(2)"),
                                                encoding="utf-8")
    ctx.uv(SPEECH, "prepare", d)
    L = read_json(d / "speech" / "lines.json")["lines"]
    expect(len(L) == 1 and L[0]["cues"] and abs(L[0]["duration"] - 0.3) < 0.02 and len(L[0]["words"]) == 2,
           f"speech/lines.json wrong: {L}")
    ctx.uv(RUN, "clip", d, "c01_opening", "--stills", "1,10", "--sheet", timeout=600)
    expect((d / "out" / "c01_opening" / "sheet.png").exists(), "no contact sheet")
    ctx.uv(FILM3D, "preview", d, timeout=1200)
    B = read_json(d / "out" / "c01_opening" / "build.json")
    expect(B["cuts"] == [1, 9] and [s["id"] for s in B["said"]] == ["l01"] and B["said"][0]["start"] == line_at,
           f"build.json wrong: {B}")
    for c, n in (("c01_opening", 12), ("c02_answer", 8)):
        got = len(list((d / "out" / c / "draft").glob("f_*.png")))
        expect(got == n, f"{c}: {got} draft frames, expected {n}")
    expect(read_json(d / "project.json").get("audio") == "sound/film.wav", "preview did not mix the sound")
    film = d / "preview" / "film_draft.mp4"
    expect_film(ctx, film, 20, tol_audio=0.06)
    t = first_loud(audio_samples(film), 48000, 8000)
    want = (line_at - 1) / 24 + 0.1
    expect(t is not None and abs(t - want) <= 1.5 / 24, f"the line's tone starts at {t} s, expected {want:.3f} s")
    ctx.uv(CUT, d, "--q", "draft", "--clips", "c02_answer", "--look", "ad")
    part = d / "preview" / "film_draft_c02_answer.mp4"
    expect_film(ctx, part, 8, tol_audio=0.06)
    # the say() frame moves + a narrator voice-over: only c01 is rendered again (its scene changed, source.json), the
    # sound is mixed again by itself (it used to stay and slide against the picture)
    c02_png = d / "out" / "c02_answer" / "draft" / "f_0001.png"
    c01_png = d / "out" / "c01_opening" / "draft" / "f_0001.png"
    m01, m02 = c01_png.stat().st_mtime, c02_png.stat().st_mtime
    line_at = 7
    (d / "scenes" / "c01_opening.py").write_text(SCENE.format(frames=12, mood="golden", cut=9,
                                                             say=f'mo.say("l01", {line_at})'), encoding="utf-8")
    ctx.ff("-f", "lavfi", "-i", "aevalsrc=0.5*sin(2*PI*440*t)*gt(t\\,0.1):s=44100:d=0.3", "-ac", "1",
           str(d / "speech" / "narr.wav"))
    ctx.uv(FILM3D, "line", d, "l02", "narrator", "Meanwhile", "--audio", "speech/narr.wav", "--at", "c02_answer:3")
    ctx.uv(FILM3D, "line", d, "l02", "narrator", "Meanwhile", "--at", "c02_answer:3")    # no --audio: the path stays
    expect(read_json(d / "project.json")["lines"][1]["audio"] == "speech/narr.wav", "line without --audio reset the path")
    out = ctx.uv(FILM3D, "line", d, "l01", "mo", "Hello again")
    expect("recording of the old text" in out.stdout, f"no warning for a changed recorded line:\n{out.stdout}")
    ctx.uv(FILM3D, "line", d, "l01", "mo", "Hello there")
    ctx.uv(SPEECH, "prepare", d)
    out = ctx.uv(FILM3D, "preview", d, timeout=1200)
    expect("rendering the clip again" in out.stdout and "mixing again" in out.stdout,
           f"preview after a scene change did not render c01 again / mix again:\n{out.stdout[-1500:]}")
    expect(c01_png.stat().st_mtime > m01 and c02_png.stat().st_mtime == m02,
           "c01 should be rendered again (scene changed), c02 kept (unchanged)")
    smp = audio_samples(film)
    t = first_loud(smp, 48000, 8000)
    want = (line_at - 1) / 24 + 0.1
    expect(t is not None and abs(t - want) <= 1.5 / 24, f"after moving say(): the line starts at {t} s, expected {want:.3f}")
    t2 = first_loud(smp, 48000, 8000, start=0.58)
    want2 = (12 + 3 - 1) / 24 + 0.1
    expect(t2 is not None and abs(t2 - want2) <= 1.5 / 24, f"narrator line at {t2} s, expected {want2:.3f} s")
    # scene FRAMES and project.json frames must agree (smaller: endless "missing", larger: silently cut)
    P = read_json(d / "project.json")
    P["clips"][0]["frames"] = 13
    write_json(d / "project.json", P)
    out = ctx.run(["uv", "run", "--offline", RUN, "clip", d, "c01_opening", "--stills", "1"], check=False, timeout=600)
    expect(out.returncode != 0 and "make them the same" in out.stdout, f"FRAMES mismatch not reported:\n{out.stdout[-800:]}")
    P["clips"][0]["frames"] = 12
    write_json(d / "project.json", P)
    # a changed clip whose re-render is stopped half way: the resume must render the rest (no old frame may stay)
    (d / "scenes" / "c01_opening.py").write_text(SCENE.format(frames=12, mood="night", cut=9,
                                                             say=f'mo.say("l01", {line_at})'), encoding="utf-8")
    t_change = time.time() - 1
    drafts = d / "out" / "c01_opening" / "draft"
    cmd = ["uv", "run", "--offline", str(RUN), "film", str(d), "--q", "draft", "--clips", "c01_opening"]
    ctx.log("$ " + " ".join(cmd) + "   (stopped after 2 frames)")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    seen, stopped = 0, False
    for ln in p.stdout:
        ctx.log("  " + ln.rstrip())
        seen += ln.startswith("RENDERED c01_opening")
        if seen >= 2:
            if os.name == "nt":                         # the whole tree: uv -> python -> Blender
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
            else:
                p.kill()
            stopped = True
            break
    p.wait(60)
    left = sorted(drafts.glob("f_*.png"))
    expect(all(f.stat().st_mtime >= t_change for f in left),
           f"old frames survived the start of the re-render: {[f.name for f in left if f.stat().st_mtime < t_change]}")
    ctx.uv(RUN, "film", d, "--q", "draft", "--clips", "c01_opening", timeout=900)
    left = sorted(drafts.glob("f_*.png"))
    expect(len(left) == 12 and all(f.stat().st_mtime >= t_change for f in left),
           f"after the resume: {len(left)} frames, old ones {[f.name for f in left if f.stat().st_mtime < t_change]}")
    ctx.note(f"re-render {'stopped after 2 frames and ' if stopped else '(finished before the stop) '}resumed with new frames only")
    ctx.note(f"2 clips, 20 draft frames ({B['device']}), line moved to frame {line_at} heard at {t:.3f} s, narrator at {t2:.3f} s, only the changed clip re-rendered, looks cinema + ad")


def run_makes(ctx):
    """the makes of the figures: one tiny clip in every make - all different pictures"""
    need("blender")
    d = ctx.dir / "makes"
    ctx.uv(FILM3D, "new", d, "--title", "E2E makes", "--seed", "7", "--cast", "mo:bear,kit:cat", "--size", "640x360",
           "--figures", "ragdoll")
    P = read_json(d / "project.json")
    expect(P.get("figures") == "ragdoll", f"film3d.py new --figures ragdoll wrote {P.get('figures')!r}")
    P["clips"][0]["frames"] = 4
    write_json(d / "project.json", P)
    (d / "scenes" / "c01_opening.py").write_text(SCENE.format(frames=4, mood="golden", cut=3, say="mo.babble(1, 4)"),
                                                 encoding="utf-8")
    still, seen = d / "out" / "c01_opening" / "stills_draft" / "f_0004.png", {}
    makes = ("ragdoll", "puppet", "stopmotion", "clay", "paper", "marionette", "toy")
    for make in makes:
        P["figures"] = make
        write_json(d / "project.json", P)
        ctx.uv(RUN, "clip", d, "c01_opening", "--stills", "4", timeout=900)
        expect(still.exists() and still.stat().st_size > 20000, f"figures {make}: no still")
        seen[make] = still.read_bytes()
    expect(len(set(seen.values())) == len(makes), "two makes rendered the same picture")
    P["figures"] = "wool"
    write_json(d / "project.json", P)
    out = ctx.run(["uv", "run", "--offline", RUN, "clip", d, "c01_opening", "--stills", "4"], check=False, timeout=600)
    expect(out.returncode != 0, "an unknown make of the figures was not refused")
    ctx.note(f"close-up of one figure in {len(makes)} makes ({', '.join(makes)}): all different pictures; unknown "
             "make refused")


ACTOR_SCENE = '''import stage_actor as K
import stage_sets as sets

FRAMES = 40


def build(S):
    sets.office(S, mood="day")
    cast = K.cast(S, {"mo": {"look": "bear", "height": 1.05}, "kit": {"look": "cat", "height": 1.05}})
    mo, kit = cast["mo"], cast["kit"]
    mo.at(1, -0.8, -0.03, 0, ease="hold")             # at the table: hanging hands are in its top
    kit.at(1, -1.6, -1.6, 90, ease="hold")
    kit.walk(4, 38, 2.4, -1.6)
    mo.mood(6, "happy").babble(8, 30)
    S.shot(1, (0.4, -6.2, 1.1), (0.4, -0.8, 0.9), lens=30, fstop=8)
'''


def run_actors(ctx):
    """realistic actors: a Rigify figure generated in Blender plays a toy scene unchanged ("figures": "rigify"),
    feet stand on the floor, hands hanging into the table are moved off it, contact.json measures both"""
    need("blender")
    d = ctx.dir / "actors"
    ctx.uv(FILM3D, "new", d, "--title", "E2E actors", "--seed", "7", "--cast", "mo:bear,kit:cat", "--size", "640x360",
           "--figures", "rigify")
    P = read_json(d / "project.json")
    expect(P.get("figures") == "rigify", f"film3d.py new --figures rigify wrote {P.get('figures')!r}")
    P["clips"][0]["frames"] = 40
    P["look"] = "none"
    write_json(d / "project.json", P)
    blend = d / "actors" / "testy" / "figur.blend"
    blend.parent.mkdir(parents=True)
    ctx.run([tool("blender"), "-b", "--factory-startup", "--python-exit-code", "1", "--python",
             Path(__file__).with_name("make_actor.py"), "--", blend], timeout=600)
    expect(blend.exists(), "make_actor.py wrote no figur.blend")
    (d / "scenes" / "c01_opening.py").write_text(ACTOR_SCENE, encoding="utf-8")
    out = ctx.uv(RUN, "clip", d, "c01_opening", "--stills", "1,20,36", "--contact", timeout=900)
    expect(out.stdout.count("ACTOR ") == 2, "the two parts were not played by actors: " + out.stdout[-800:])
    steps = int(re.search(r"CONTACT 2 actors: (\d+) foot steps", out.stdout).group(1))
    moved = int(re.search(r"(\d+) arm frames moved", out.stdout).group(1))
    expect(steps >= 3, f"the walking actor made only {steps} steps")
    expect(moved > 0, "the hands in the table were not moved off it")
    C = read_json(d / "out" / "c01_opening" / "contact.json")
    deep = max([x["cm"] for x in C["feet"]], default=0.0)
    expect(deep < 1.5, f"shoes {deep} cm below the floor")
    expect(not C["hands"], f"hands still in the table in {len(C['hands'])} measurements")
    stills = sorted((d / "out" / "c01_opening" / "stills_draft").glob("f_*.png"))
    expect(len(stills) == 3 and all(f.stat().st_size > 20000 for f in stills), "missing stills")
    P["actors"] = {"mo": "nobody"}
    write_json(d / "project.json", P)
    bad = ctx.run(["uv", "run", "--offline", RUN, "clip", d, "c01_opening", "--stills", "1"], check=False, timeout=600)
    expect(bad.returncode != 0 and "not found" in bad.stdout, "an unknown actor was not refused")
    ctx.note(f"generated Rigify actor plays a toy scene: {steps} foot steps, {moved} arm frames moved off the table, "
             f"shoes at most {deep} cm below the floor, no hand in the table; unknown actor refused")


TESTS = [Test("animated-3d-film-actors", run_actors, about='"figures": "rigify": a generated Rigify actor plays a toy '
                                                           "scene; feet planted, arm off the table, contact.json"),
         Test("animated-3d-film-makes", run_makes, about="project.json figures: every make (ragdoll ... marionette, toy) renders and they "
                                                         "differ, an unknown make is refused"),
         Test("animated-3d-film", run_film, about="film3d.py new/clip/line -> stage_speech -> Blender draft render "
                                                  "-> sound mix -> clip_film cut")]
