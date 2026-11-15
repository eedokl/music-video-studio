"""animated-3d-film: film3d.py new -> clip -> idea -> line (a synthetic wav) -> stage_speech prepare -> two tiny clips
rendered in draft quality with Blender -> sound mix -> clip_film cut (dissolve, look, sound)."""
from common import (Test, audio_samples, expect, expect_film, first_loud, full, need, read_json, script, write_json)

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
    ctx.note(f"2 clips, 20 draft frames ({B['device']}), line on frame {line_at} heard at {t:.3f} s, looks cinema + ad")


TESTS = [Test("animated-3d-film", run_film, about="film3d.py new/clip/line -> stage_speech -> Blender draft render "
                                                  "-> sound mix -> clip_film cut")]
