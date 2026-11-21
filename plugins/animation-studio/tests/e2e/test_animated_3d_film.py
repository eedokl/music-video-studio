"""animated-3d-film: film3d.py new -> clip -> idea -> line (a synthetic wav) -> stage_speech prepare -> two tiny clips
rendered in draft quality with Blender -> sound mix -> clip_film cut (dissolve, look, sound)."""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from common import (Test, audio_samples, expect, expect_film, first_loud, frame_colours, full, need, read_json,
                    script, tool, write_json)

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
    # the say() frame moves + a narrator voice-over: only c01 is rendered again (its scene changed, source.json) and
    # of it only the frames that look different (fingerprints, frames.json); the sound is mixed again by itself
    c02_png = d / "out" / "c02_answer" / "draft" / "f_0001.png"
    c01_dir = d / "out" / "c01_opening" / "draft"
    expect((c01_dir / "frames.json").exists(), "the film render wrote no frames.json (fingerprints)")
    m01 = {f.name: f.stat().st_mtime for f in c01_dir.glob("f_*.png")}
    m02 = c02_png.stat().st_mtime
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
    expect("frames that look different" in out.stdout and "mixing again" in out.stdout,
           f"preview after a scene change did not re-render c01's changed frames / mix again:\n{out.stdout[-1500:]}")
    newer = sorted(int(n[2:6]) for n, t in m01.items() if (c01_dir / n).stat().st_mtime > t)
    # (Mo anticipates the line from frame 1 on, so in this short clip every frame really changes)
    expect(re.search(r"CHANGED c01_opening \d+ of 12", out.stdout) and line_at + 1 in newer
           and c02_png.stat().st_mtime == m02, f"after moving say(): re-rendered c01 frames {newer}, c02 kept?")
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
    # a late change (Kit nods at the end): only the last frames are rendered again
    m = {f.name: f.stat().st_mtime for f in drafts.glob("f_*.png")}
    (d / "scenes" / "c01_opening.py").write_text(SCENE.format(
        frames=12, mood="night", cut=9, say=f'mo.say("l01", {line_at})\n    kit.nod(10)'), encoding="utf-8")
    out = ctx.uv(RUN, "film", d, "--q", "draft", "--clips", "c01_opening", timeout=900)
    late = sorted(int(f.name[2:6]) for f in drafts.glob("f_*.png") if f.stat().st_mtime > m[f.name])
    expect(late and 12 in late and 1 not in late and len(late) < 8,
           f"a nod at frame 10 re-rendered frames {late}:\n{out.stdout[-800:]}")
    ctx.note(f"a late nod re-rendered only frames {late[0]}-{late[-1]} of 12 (fingerprints)")
    # --changed with nothing changed: the clip is built and fingerprinted, no frame is touched
    m = {f.name: f.stat().st_mtime for f in drafts.glob("f_*.png")}
    out = ctx.uv(RUN, "film", d, "--q", "draft", "--clips", "c01_opening", "--changed", timeout=900)
    same = all(f.stat().st_mtime == m[f.name] for f in drafts.glob("f_*.png"))
    expect("CHANGED c01_opening 0 of 12" in out.stdout and same,
           f"--changed without a change touched frames:\n{out.stdout[-800:]}")
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


THEATRE_SCENE = '''import stage_actor as K
import stage_sets as sets
import stage_theatre as T

FRAMES = 64


def build(S):
    R = sets.office(S, mood="golden")
    cast = K.cast(S, {"mo": "bear", "kit": "cat"})
    cast["mo"].at(1, -0.5, -0.9, 0, ease="hold")
    cast["kit"].at(1, 0.5, -0.9, 0, ease="hold")
    B = T.show_stage(S)
    ch = T.set_change(S, R, "room", T.stage_change(S, B))
    ch.state(1, "room")
    w = ch.change(4, "stage", frames=30, follow=cast["mo"], crew=1)
    T.Curtain(S, width=3.0, height=2.0, y=-2.4).state(1, True).close(w["lit"], 8).open(w["lit"] + 10, 8)
    T.light_show(S, 46, list(range(46, 64, 6)), ["#FF2E7E", "#2EC5FF"], fly_in=10)
    S.shot(1, (0.0, -6.2, 1.5), (0.0, 0.2, 1.0), lens=28, fstop=8)
'''


def run_theatre(ctx):
    """theatre machinery: an office changes into a show stage in view (light down, follow spot, a stagehand, pieces
    fly and roll away, the stage rolls in), a curtain closes and opens, a light show in haze"""
    need("blender", "ffmpeg")
    d = ctx.dir / "theatre"
    ctx.uv(FILM3D, "new", d, "--title", "E2E theatre", "--seed", "7", "--cast", "mo:bear,kit:cat", "--size", "640x360")
    P = read_json(d / "project.json")
    P["clips"][0]["frames"] = 64
    P["look"] = "none"
    write_json(d / "project.json", P)
    (d / "scenes" / "c01_opening.py").write_text(THEATRE_SCENE, encoding="utf-8")
    ctx.uv(RUN, "clip", d, "c01_opening", "--stills", "1,14,46,58", timeout=900)
    st = d / "out" / "c01_opening" / "stills_draft"
    lum = {}
    for f in (1, 14, 46, 58):
        png = st / f"f_{f:04d}.png"
        expect(png.exists(), f"still {f} missing")
        c = frame_colours(png)[0]
        lum[f] = sum(c) / 3
    expect(lum[14] < 0.6 * lum[1], f"the light did not go down for the change: {lum[1]:.0f} -> {lum[14]:.0f}")
    expect(abs(lum[46] - lum[1]) > 4 or (st / "f_0046.png").read_bytes() != (st / "f_0001.png").read_bytes(),
           "the stage looks like the office")
    expect((st / "f_0058.png").read_bytes() != (st / "f_0046.png").read_bytes(), "the light show changed nothing")
    ctx.note(f"brightness room {lum[1]:.0f} -> change {lum[14]:.0f} -> stage {lum[46]:.0f} -> light show "
             f"{lum[58]:.0f}")


def run_credits(ctx):
    """end credits of a 3D film: an outtake clip from the template (clapperboard, breaking up) and an extra scene are
    rendered with the film but not cut into it; film3d.py credits --draft + preview -> credits with windows, gag and
    the clap sound; film_draft_with_credits = film + credits"""
    need("blender", "ffmpeg")
    d = ctx.dir / "credits"
    ctx.uv(FILM3D, "new", d, "--title", "E2E credits", "--seed", "3", "--cast", "mo:bear,kit:cat", "--size", "640x360")
    P = read_json(d / "project.json")
    P["clips"][0]["frames"] = 12
    P["look"] = "none"
    write_json(d / "project.json", P)
    (d / "scenes" / "c01_opening.py").write_text(SCENE.format(frames=12, mood="golden", cut=8, say="mo.babble(1, 12)"),
                                                 encoding="utf-8")
    ctx.uv(FILM3D, "clip", d, "outtake_01", "--frames", "40", "--credits", "outtake", "--about", "it goes wrong")
    ctx.uv(FILM3D, "clip", d, "extra_bow", "--frames", "12", "--credits", "extra", "--about", "a bow")
    o = (d / "scenes" / "outtake_01.py").read_text(encoding="utf-8")
    expect("O.take(" in o and "crack_up" in o, "the outtake template has no clapperboard / crack_up")
    ctx.uv(FILM3D, "credits", d, "--draft")
    P = read_json(d / "project.json")
    C = P["credits"]
    C["speed"] = 240.0                                        # a short roll for the test
    write_json(d / "project.json", P)
    expect(len(C["gags"]) == 1 and C["gags"][0]["items"][0]["frames"] == "out/extra_bow/film",
           f"draft gags: {C['gags']}")
    outt = [w for w in C["windows"]["outtakes"] if w["label"] == "Outtake"]
    expect(len(outt) == 1 and outt[0]["sounds"], f"draft windows: {C['windows']}")
    out = ctx.uv(FILM3D, "preview", d, timeout=1500)
    film, cr, both = (d / "preview" / x for x in ("film_draft.mp4", "credits_draft.mp4", "film_draft_with_credits.mp4"))
    for f in (film, cr, both):
        expect(f.exists(), f"{f.name} missing: " + out.stdout[-600:])
    nf, nc, nb = (len(frame_colours(f)) for f in (film, cr, both))
    expect(nf == 12, f"the film has {nf} frames - the credit clips were cut into it")
    expect(abs(nb - (nf + nc)) <= 2, f"film {nf} + credits {nc} != {nb}")
    expect((d / "out" / "outtake_01" / "draft" / "f_0040.png").exists(), "the outtake was not rendered")
    ctx.note(f"film {nf} frames (credit clips not cut in), credits {nc} frames with 1 extra scene + outtake window, "
             f"film with credits {nb}")


def song_film(ctx):
    """a film folder on a synthetic song, up to the written plan: (folder, plan, sheet, output of the plan draft)"""
    d = ctx.dir / "film"
    ctx.uv(FILM3D, "new", d, "--title", "E2E song", "--seed", "7", "--cast", "mo:bear,kit:cat", "--size", "640x360")
    song = d / "song"
    (song / "analysis").mkdir(parents=True)
    # the voice: 1.0-2.0 s (line 0), 5.8-6.4 s (line 1), 7.6-8.6 s (line 2, which the "recognition" starts at 7.0)
    voiced = "between(t\\,1\\,2)+between(t\\,5.8\\,6.4)+between(t\\,7.6\\,8.6)"
    for f in (song / "song.wav", song / "analysis" / "vocals_lead.wav"):
        ctx.ff("-f", "lavfi", "-i", f"aevalsrc=0.5*sin(2*PI*220*t)*({voiced}):s=16000:d=10", "-ac", "1", str(f))
    words = [("Hello", 1.0, 1.3, 0), ("there", 1.3, 1.6, 0), ("friend", 1.6, 2.0, 0),
             ("El-Ge-Te-Em", 2.1, 2.3, 1), ("again", 6.0, 6.4, 1),        # first word glued to the line before
             ("Quiet", 7.0, 7.9, 2), ("start", 7.9, 8.2, 2), ("here", 8.2, 8.6, 2)]
    sheet = {"fps": 24, "duration": 10.0, "tempo_bpm": 120.0,
             "beats": [{"t": i * 0.5, "downbeat": i % 4 == 0} for i in range(20)], "accents": [{"t": 1.0}],
             "words": [{"word": w, "t": t, "end": e, "line": n} for w, t, e, n in words],
             "lines": [{"line": 0, "text": "Hello there friend", "t": 1.0, "end": 2.0},
                       {"line": 1, "text": "El-Ge-Te-Em again", "t": 2.1, "end": 6.4},
                       {"line": 2, "text": "Quiet start here", "t": 7.0, "end": 8.6}]}
    write_json(song / "analysis" / "song_sheet.json", sheet)
    out = ctx.uv(FILM3D, "song", d, "--draft", "--target", "4")
    return d, read_json(d / "song_plan.json"), sheet, out


def song_plan(d, plan):
    plan.update(clips=[["c01_a", 0.0, "the first line"], ["c02_b", 5.0, "the chant"]], who={"mo": [0], "all": ["1-2"]},
                groups={"all": ["mo", "kit"]}, show={"El-Ge-Te-Em": "LGTM"})
    write_json(d / "song_plan.json", plan)


def run_song(ctx):
    """a film on a song (no Blender): plan draft -> timing.json / vocal slices / project.json, the two timing
    repairs, the stage_song time helpers, the render estimate of `status`"""
    need("ffmpeg", "rhubarb")
    d, plan, sheet, out = song_film(ctx)
    expect(plan["song"] == "song" and plan["clips"][0][1] == 0.0 and len(plan["clips"]) >= 2
           and (d / "song_lines.txt").read_text(encoding="utf-8").count("\n") == 3, f"plan draft wrong: {plan}")
    expect("line 1" in out.stdout and "moved" in out.stdout, f"the draft did not report the glued word:\n{out.stdout}")
    song_plan(d, plan)
    out = ctx.uv(FILM3D, "song", d)
    T = read_json(d / "timing.json")
    P = read_json(d / "project.json")
    l1 = T["lines"][1]
    expect([(c["name"], c["frames"]) for c in T["clips"]] == [("c01_a", 120), ("c02_b", 120)], f"clips: {T['clips']}")
    expect(l1["who"] == "all" and l1["text"] == "LGTM again" and l1["sung"] == "El-Ge-Te-Em again"
           and l1["words"][0] == {"word": "LGTM", "t": 5.8, "sung": "El-Ge-Te-Em"}, f"line 1 in timing.json: {l1}")
    expect("line 2 starts at 7.00 s while the voice is silent" in out.stdout and '"2:0": 7.6' in out.stdout,
           f"no note for the line placed in silence:\n{out.stdout}")
    expect(P["audio"] == "song/song.wav" and [c["name"] for c in P["clips"]] == ["c01_a", "c02_b"]
           and [x["text"] for x in P["lines"]] == [x["text"] for x in sheet["lines"]], f"project.json: {P}")
    expect("stage_song" in (d / "scenes" / "c02_b.py").read_text(encoding="utf-8"), "no song scene template")
    L = {x["id"]: x for x in read_json(d / "speech" / "lines.json")["lines"]}
    expect(abs(L["l01"]["duration"] - 0.74) < 0.03, f"vocal slice of line 1: {L['l01']['duration']} s, expected 0.74")
    # the fix of the plan silences the note; unchanged slices are kept
    m0 = (d / "speech" / "l00.wav").stat().st_mtime
    plan["fix"] = {"2:0": 7.6}
    write_json(d / "song_plan.json", plan)
    out = ctx.uv(FILM3D, "song", d)
    expect("while the voice is silent" not in out.stdout and (d / "speech" / "l00.wav").stat().st_mtime == m0
           and read_json(d / "timing.json")["lines"][2]["words"][0]["t"] == 7.6, f"after the fix:\n{out.stdout}")
    # the time helpers (no Blender)
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import stage_song as SG; SG.use(sys.argv[2]); "
            "print(SG.f('c02_b', 6.0), SG.word('c02_b', 'LGTM'), SG.word('c02_b', 'Ge-Te'), SG.word('c01_a', 'LGTM'), "
            "SG.singers('all'), [x['n'] for x in SG.lines('c02_b')], SG.bars('c02_b'))")
    out = ctx.run([sys.executable, "-c", code, Path(script("stage-3d", "stage_song.py")).parent, d])
    expect(out.stdout.strip() == "25 20 20 None ('mo', 'kit') [1, 2] [25, 73]", f"stage_song helpers: {out.stdout}")
    # the estimate: 240 missing frames at the 2 s/frame measured on one clip
    (d / "out" / "c01_a" / "film").mkdir(parents=True)
    write_json(d / "out" / "c01_a" / "film" / "speed.json", {"frames": 10, "seconds": 20.0})
    out = ctx.uv(RUN, "status", d, "--q", "film")
    expect("about 8 min" in out.stdout and "measured on 1 clip" in out.stdout, f"status estimate:\n{out.stdout}")
    ctx.note("plan draft, glued first word moved (2.1 -> 5.8 s), line in silence reported and fixed, sung -> written "
             "text, slices kept on a re-run, stage_song helpers, render estimate")


def run_song_stage(ctx):
    """the song scene template in Blender: SG.sing puts a group's line on both figures, SG.groove builds"""
    need("ffmpeg", "blender", "rhubarb")
    d, plan, _, _ = song_film(ctx)
    song_plan(d, plan)
    ctx.uv(FILM3D, "song", d)
    ctx.uv(RUN, "clip", d, "c02_b", "--stills", "30", timeout=600)
    B = read_json(d / "out" / "c02_b" / "build.json")
    expect(sorted(s["id"] for s in B["said"]) == ["l01", "l01", "l02", "l02"] and B["said"][0]["start"] == 20,
           f"build.json said: {B['said']}")
    expect((d / "out" / "c02_b" / "stills_draft" / "f_0030.png").exists(), "no still of the song scene")
    ctx.note("the song template scene renders; both figures of the group sing lines 1 and 2")


TESTS = [Test("animated-3d-film-song", run_song, about="film3d.py song: plan -> timing.json / vocal slices / "
                                                       "project.json, timing repairs, stage_song, render estimate"),
         Test("animated-3d-film-stage-song", run_song_stage, about="the song scene template in Blender: group lip "
                                                                   "sync (SG.sing), groove"),
         Test("animated-3d-film-credits", run_credits, about="credit clips (outtake template, extra scene) rendered "
                                                              "apart from the film; draft + preview -> credits"),
         Test("animated-3d-film-theatre", run_theatre, about="stage_theatre: set change in view (office -> show "
                                                              "stage), curtain, light show in haze"),
         Test("animated-3d-film-actors", run_actors, about='"figures": "rigify": a generated Rigify actor plays a toy '
                                                           "scene; feet planted, arm off the table, contact.json"),
         Test("animated-3d-film-makes", run_makes, about="project.json figures: every make (ragdoll ... marionette, toy) renders and they "
                                                         "differ, an unknown make is refused"),
         Test("animated-3d-film", run_film, about="film3d.py new/clip/line -> stage_speech -> Blender draft render "
                                                  "-> sound mix -> clip_film cut")]
