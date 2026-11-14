"""bricks-music-video: synthetic song + song sheet + assignment -> setup.py -> render.py (plan.py, textures, Blender
EEVEE through blender_run.py, draft quality) for a 1 s section -> build.py film.
Blender takes the shared GPU lock (studio-core gpu_lock) like every brick render: it waits for other GPU jobs."""
from common import FPS, Test, expect, full, expect_film, need, read_json, script, song_sheet, assignment, tone, write_json

NEW = script("song-analysis", "new_project.py")
SETUP = script("bricks-music-video", "setup.py")
RENDER = script("bricks-music-video", "render.py")
BUILD = script("film-finish", "build.py")

WORDS = [("Hey", 0.02, 0.20, 0)]


def run_bricks(ctx):
    need("ffmpeg", "blender", "ldraw_dir")
    song = tone(ctx, ctx.dir / "song.wav", 1.5)
    lyr = ctx.dir / "lyrics.txt"
    lyr.write_text("Hey\n", encoding="utf-8")
    d = ctx.dir / "bricks"
    ctx.uv(NEW, d, "--song", song, "--lyrics", lyr, "--language", "en")
    write_json(d / "analysis" / "song_sheet.json", song_sheet(1.5, WORDS))
    write_json(d / "analysis" / "assignment.json", assignment(["tim", "lia", "computer"], {"tim": [(0.02, 0.2)]}))
    S, E = 0.0, 1.0                        # (sections < 0.6 s work too since plan.py keeps the start cut)
    ctx.uv(SETUP, d, "--sections", f"verse:{S}-{E}", "--set", "room", "--seed", "4711")
    P = read_json(d / "project.json")
    P["sounds"] = False
    P["look"] = "standard" if full() else "none"                         # the look is checked by other tests
    write_json(d / "project.json", P)
    ctx.uv(RENDER, "verse", "--project", d, "--percent", "50", "--samples", "8", timeout=420)
    n = round(E * FPS) - round(S * FPS)
    got = len(list((d / "scenes" / "verse").glob("f.*.png")))
    expect(got >= n - 1, f"Blender rendered {got} frames, the section needs {n}")
    expect((d / "bricks" / "verse.json").exists(), "plan.py wrote no bricks/verse.json")
    ctx.uv(BUILD, "film", "--project", d, timeout=600)
    expect_film(ctx, d / "film.mp4", n)
    ctx.note(f"plan + textures + EEVEE ({got} frames, 50 %, 8 samples) -> film {n} frames")


TESTS = [Test("bricks-music-video", run_bricks, slow=True,
              about="setup.py + render.py (plan, textures, Blender EEVEE draft) for 1 s -> build.py film")]
